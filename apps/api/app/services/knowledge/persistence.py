from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AnswerKey,
    ContentProvenance,
    Dialogue,
    DialogueTurn,
    Exercise,
    ExerciseOption,
    GrammarPattern,
    Lesson,
    LessonSection,
    ListeningTrack,
    Passage,
    Sentence,
    SentenceIdentity,
    SourcePage,
    SourceBlock,
    SourceDocument,
    SourceSpan,
    Textbook,
    Transcript,
    Vocabulary,
    WordSense,
)
from app.services.knowledge.types import ExtractionBundle, SourceRef
from app.services.normalization import normalize_korean_key


def _source_span_id(
    session: Session,
    source: SourceRef,
    textbook_id: int,
    source_document_id: int | None,
) -> int | None:
    page_query = select(SourcePage.id).join(SourceDocument).where(
        SourceDocument.textbook_id == textbook_id,
        SourcePage.pdf_page_number == source.pdf_page_number,
    )
    if source_document_id is not None:
        page_query = page_query.where(SourcePage.source_document_id == source_document_id)
    page_ids = list(session.scalars(page_query).all())
    if source_document_id is None and len(page_ids) > 1:
        raise ValueError("source_document_id is required when a textbook has duplicate source page numbers")
    if len(page_ids) != 1:
        return None
    query = select(SourceSpan.id).where(SourceSpan.source_page_id == page_ids[0])
    if source.table_index is not None and source.table_row_index is not None:
        table_label = f"raw_table:{source.table_index}:{source.table_row_index}"
        return session.scalar(query.where(SourceSpan.label == table_label))
    if source.block_index is not None:
        block_id = session.scalar(select(SourceBlock.id).where(
            SourceBlock.source_page_id == page_ids[0],
            SourceBlock.block_index == source.block_index,
        ))
        if block_id is None:
            return None
        return session.scalar(query.where(
            SourceSpan.source_block_id == block_id,
            SourceSpan.label == "raw_block",
        ))
    return None


def _provenance(session: Session, kind: str, entity_id: int, span_id: int | None, method: str, version: str) -> None:
    if span_id is None:
        return
    # SessionLocal deliberately disables autoflush.  A bundle can legitimately
    # mention the same persisted option more than once; keep an unflushed
    # provenance row from being scheduled twice in that single transaction.
    if any(
        isinstance(row, ContentProvenance)
        and row.entity_type == kind
        and row.entity_id == entity_id
        and row.source_span_id == span_id
        and row.extraction_method == method
        and row.extraction_version == version
        for row in session.new
    ):
        return
    present = session.scalar(select(ContentProvenance.id).where(
        ContentProvenance.entity_type == kind,
        ContentProvenance.entity_id == entity_id,
        ContentProvenance.source_span_id == span_id,
        ContentProvenance.extraction_method == method,
        ContentProvenance.extraction_version == version,
    ))
    if present is None:
        session.add(ContentProvenance(
            entity_type=kind,
            entity_id=entity_id,
            source_span_id=span_id,
            extraction_method=method,
            extraction_version=version,
        ))


def persist_bundle(
    session: Session,
    textbook_id: int,
    bundle: ExtractionBundle,
    source_document_id: int | None = None,
) -> dict[str, int]:
    """Idempotently persist an extraction bundle without changing reviewed rows."""
    counts = {
        "lessons": 0, "sections": 0, "vocabulary": 0, "word_senses": 0,
        "grammar": 0, "sentence_identities": 0, "sentences": 0, "dialogues": 0, "dialogue_turns": 0,
        "passages": 0, "exercises": 0, "exercise_options": 0,
        "listening_tracks": 0, "transcripts": 0, "answers": 0,
    }
    lesson_ids: dict[tuple[int, int], int] = {}
    source_span_cache: dict[SourceRef, int | None] = {}

    def resolve_source(source: SourceRef) -> int | None:
        if source not in source_span_cache:
            source_span_cache[source] = _source_span_id(
                session, source, textbook_id, source_document_id,
            )
        return source_span_cache[source]

    with session.begin_nested():
        for item in bundle.lessons:
            span_id = resolve_source(item.source)
            if span_id is None:
                continue
            row = session.scalar(select(Lesson).where(
                Lesson.textbook_id == textbook_id,
                Lesson.ordinal == item.ordinal,
                Lesson.start_pdf_page == item.start_pdf_page,
            ))
            if row is None:
                row = Lesson(
                    textbook_id=textbook_id,
                    ordinal=item.ordinal,
                    title=item.title_ko,
                    start_pdf_page=item.start_pdf_page,
                    end_pdf_page=item.end_pdf_page,
                    segmentation_method=item.extraction_method,
                    review_status=item.review_status,
                    extraction_version=item.extraction_version,
                )
                session.add(row)
                session.flush()
                counts["lessons"] += 1
            elif row.review_status not in {"approved", "reviewed"}:
                changed = any((
                    row.title != item.title_ko,
                    row.end_pdf_page != item.end_pdf_page,
                    row.segmentation_method != item.extraction_method,
                    row.extraction_version != item.extraction_version,
                ))
                if changed:
                    row.title = item.title_ko
                    row.end_pdf_page = item.end_pdf_page
                    row.segmentation_method = item.extraction_method
                    row.extraction_version = item.extraction_version
                    row.version += 1
            lesson_ids[(item.ordinal, item.start_pdf_page)] = row.id
            _provenance(session, "lesson", row.id, span_id, item.extraction_method, item.extraction_version)

        def lesson_for_page(page_number: int) -> int | None:
            matching = [
                item for item in bundle.lessons
                if item.start_pdf_page <= page_number <= (item.end_pdf_page or item.start_pdf_page)
            ]
            if not matching:
                return None
            lesson = max(matching, key=lambda item: item.start_pdf_page)
            return lesson_ids.get((lesson.ordinal, lesson.start_pdf_page))

        for item in bundle.sections:
            lesson_id = lesson_for_page(item.source.pdf_page_number)
            span_id = resolve_source(item.source)
            if lesson_id is None or span_id is None:
                continue
            row = session.scalar(select(LessonSection).where(
                LessonSection.lesson_id == lesson_id,
                LessonSection.section_type == item.section_type,
                LessonSection.source_page_number == item.source.pdf_page_number,
            ))
            if row is None:
                row = LessonSection(
                    lesson_id=lesson_id,
                    section_type=item.section_type,
                    title=item.title[:255],
                    source_span_id=span_id,
                    source_page_number=item.source.pdf_page_number,
                    review_status=item.review_status,
                    extraction_version=item.extraction_version,
                )
                session.add(row)
                session.flush()
                counts["sections"] += 1
            _provenance(session, "lesson_section", row.id, span_id, item.extraction_method, item.extraction_version)

        vocabulary_ids: dict[str, int] = {}
        for item in bundle.vocabulary:
            lesson_id = lesson_for_page(item.source.pdf_page_number)
            row = session.scalar(select(Vocabulary).where(
                Vocabulary.lesson_id == lesson_id,
                Vocabulary.normalized_headword == item.normalized_headword,
            )) if lesson_id is not None else None
            span_id = resolve_source(item.source)
            if span_id is None:
                continue
            if row is None:
                row = Vocabulary(
                    lesson_id=lesson_id,
                    headword=item.headword,
                    normalized_headword=item.normalized_headword,
                    extraction_method=item.extraction_method,
                    confidence=0.0,
                    review_status=item.review_status,
                    source_span_id=span_id,
                    extraction_version=item.extraction_version,
                )
                session.add(row)
                session.flush()
                counts["vocabulary"] += 1
            elif row.review_status not in {"approved", "reviewed"}:
                if row.content_origin != "human_corrected":
                    row.headword = item.headword
                    row.source_span_id = span_id
                    row.version += 1
            vocabulary_ids[item.normalized_headword] = row.id
            _provenance(session, "vocabulary", row.id, span_id, item.extraction_method, item.extraction_version)
            for meaning in item.meanings_vi:
                if row.review_status in {"approved", "reviewed"} or session.scalar(select(WordSense.id).where(
                    WordSense.vocabulary_id == row.id,
                    WordSense.content_origin == "human_corrected",
                )) is not None:
                    continue
                sense = session.scalar(select(WordSense).where(
                    WordSense.vocabulary_id == row.id,
                    WordSense.meaning_vi == meaning,
                    WordSense.source_span_id == span_id,
                ))
                if sense is None:
                    sense = WordSense(
                        vocabulary_id=row.id,
                        meaning_vi=meaning,
                        source_span_id=span_id,
                        review_status=item.review_status,
                    )
                    session.add(sense)
                    session.flush()
                    counts["word_senses"] += 1
                    _provenance(session, "word_sense", sense.id, span_id, item.extraction_method, item.extraction_version)

        grammar_ids: dict[str, int] = {}
        for item in bundle.grammar:
            lesson_id = lesson_for_page(item.source.pdf_page_number)
            row = session.scalar(select(GrammarPattern).where(
                GrammarPattern.lesson_id == lesson_id,
                GrammarPattern.normalized_pattern == item.normalized_pattern,
            )) if lesson_id is not None else None
            span_id = resolve_source(item.source)
            if span_id is None:
                continue
            if row is None:
                row = GrammarPattern(
                    lesson_id=lesson_id,
                    pattern=item.pattern,
                    normalized_pattern=item.normalized_pattern,
                    extraction_method=item.extraction_method,
                    confidence=0.0,
                    review_status=item.review_status,
                    explanation_vi=item.explanation_vi,
                    source_span_id=span_id,
                    extraction_version=item.extraction_version,
                )
                session.add(row)
                session.flush()
                counts["grammar"] += 1
            elif row.review_status not in {"approved", "reviewed"}:
                if row.content_origin != "human_corrected":
                    row.pattern = item.pattern
                    row.explanation_vi = item.explanation_vi
                    row.source_span_id = span_id
                    row.version += 1
            grammar_ids[item.normalized_pattern] = row.id
            _provenance(session, "grammar", row.id, span_id, item.extraction_method, item.extraction_version)

        owner_id = session.scalar(select(Textbook.owner_id).where(Textbook.id == textbook_id))
        sentence_ids: dict[str, int] = {}
        for item in bundle.sentences:
            lesson_id = lesson_for_page(item.source.pdf_page_number)
            row = session.scalar(select(Sentence).where(
                Sentence.lesson_id == lesson_id,
                Sentence.text_ko == item.text_ko,
                Sentence.text_vi == item.text_vi,
            )) if lesson_id is not None else None
            span_id = resolve_source(item.source)
            if span_id is None:
                continue
            normalized_text = normalize_korean_key(item.text_ko)
            identity = session.scalar(select(SentenceIdentity).where(
                SentenceIdentity.owner_id == owner_id,
                SentenceIdentity.normalized_text_ko == normalized_text,
            ))
            if identity is None:
                identity = SentenceIdentity(
                    owner_id=owner_id,
                    canonical_text_ko=item.text_ko,
                    normalized_text_ko=normalized_text,
                )
                session.add(identity)
                session.flush()
                counts["sentence_identities"] += 1
            if row is None:
                row = Sentence(
                    identity_id=identity.id, lesson_id=lesson_id, text_ko=item.text_ko, text_vi=item.text_vi,
                    source_span_id=span_id, review_status=item.review_status,
                    extraction_version=item.extraction_version,
                )
                session.add(row)
                session.flush()
                counts["sentences"] += 1
            elif row.review_status not in {"approved", "reviewed"}:
                row.identity_id = identity.id
                row.source_span_id = span_id
                row.version += 1
            sentence_ids[item.local_id] = row.id
            if row.review_status not in {"approved", "reviewed"}:
                row.vocabulary_items = [
                    session.get(Vocabulary, vocabulary_ids[word])
                    for word in item.vocabulary if word in vocabulary_ids
                ]
                row.grammar_patterns = [
                    session.get(GrammarPattern, grammar_ids[pattern])
                    for pattern in item.grammar_patterns if pattern in grammar_ids
                ]
            _provenance(session, "sentence", row.id, span_id, item.extraction_method, item.extraction_version)

        dialogue_ids: dict[str, int] = {}
        for item in bundle.dialogue_turns:
            lesson_id = lesson_for_page(item.source.pdf_page_number)
            span_id = resolve_source(item.source)
            dialogue = session.scalar(select(Dialogue).where(
                Dialogue.lesson_id == lesson_id,
                Dialogue.group_identifier == item.group_id,
            )) if lesson_id is not None and span_id is not None else None
            if dialogue is None and lesson_id is not None:
                dialogue = Dialogue(
                    lesson_id=lesson_id, source_span_id=span_id,
                    group_identifier=item.group_id,
                )
                session.add(dialogue)
                session.flush()
                counts["dialogues"] += 1
                _provenance(session, "dialogue", dialogue.id, span_id, item.extraction_method, item.extraction_version)
            if dialogue is None:
                continue
            dialogue_ids[item.group_id] = dialogue.id
            turn = session.scalar(select(DialogueTurn).where(
                DialogueTurn.dialogue_id == dialogue.id,
                DialogueTurn.turn_index == item.turn_index,
            ))
            if turn is None:
                turn = DialogueTurn(
                    dialogue_id=dialogue.id, turn_index=item.turn_index,
                    speaker=item.speaker, text=item.text_ko, text_vi=item.text_vi,
                    source_span_id=span_id, review_status=item.review_status,
                )
                session.add(turn)
                session.flush()
                counts["dialogue_turns"] += 1
                _provenance(session, "dialogue_turn", turn.id, span_id, item.extraction_method, item.extraction_version)

        passage_ids: dict[str, int] = {}
        for item in bundle.passages:
            lesson_id = lesson_for_page(item.source.pdf_page_number)
            span_id = resolve_source(item.source)
            if span_id is None:
                continue
            text = "\n\n".join(item.paragraphs)
            passage = session.scalar(select(Passage).where(
                Passage.lesson_id == lesson_id,
                Passage.title == item.title,
                Passage.text == text,
            )) if lesson_id is not None else None
            if passage is None and lesson_id is not None:
                passage = Passage(
                    lesson_id=lesson_id, title=item.title, text=text,
                    source_span_id=span_id, review_status=item.review_status,
                    extraction_version=item.extraction_version,
                )
                session.add(passage)
                session.flush()
                counts["passages"] += 1
                _provenance(session, "passage", passage.id, span_id, item.extraction_method, item.extraction_version)
            if passage is not None:
                passage_ids[item.local_id] = passage.id

        exercise_ids: dict[str, int] = {}
        for item in bundle.exercises:
            lesson_id = lesson_for_page(item.source.pdf_page_number)
            span_id = resolve_source(item.source)
            if span_id is None:
                continue
            parent_id = exercise_ids.get(item.parent_id) if item.parent_id else None
            passage_id = passage_ids.get(item.passage_id) if item.passage_id else None
            prompt = item.prompt or item.instruction or item.local_id
            row = session.scalar(select(Exercise).where(
                Exercise.lesson_id == lesson_id,
                Exercise.group_identifier == item.group_id,
                Exercise.prompt == prompt,
                Exercise.parent_exercise_id == parent_id,
            )) if lesson_id is not None else None
            if row is None and lesson_id is not None:
                row = Exercise(
                    lesson_id=lesson_id, prompt=prompt,
                    source_span_id=span_id, review_status=item.review_status,
                    exercise_type=item.exercise_type, group_identifier=item.group_id,
                    parent_exercise_id=parent_id, passage_id=passage_id,
                    listening_track_id=None, extraction_version=item.extraction_version,
                )
                session.add(row)
                session.flush()
                counts["exercises"] += 1
            if row is None:
                continue
            exercise_ids[item.local_id] = row.id
            _provenance(session, "exercise", row.id, span_id, item.extraction_method, item.extraction_version)
            for option in item.options:
                option_span_id = resolve_source(option.source)
                existing = session.scalar(select(ExerciseOption).where(
                    ExerciseOption.exercise_id == row.id,
                    ExerciseOption.option_index == option.option_index,
                ))
                if existing is None:
                    session.add(ExerciseOption(
                        exercise_id=row.id, option_index=option.option_index,
                        text=option.text, source_span_id=option_span_id,
                    ))
                    session.flush()
                    option_id = session.scalar(select(ExerciseOption.id).where(
                        ExerciseOption.exercise_id == row.id,
                        ExerciseOption.option_index == option.option_index,
                    ))
                    counts["exercise_options"] += 1
                    _provenance(session, "exercise_option", option_id, option_span_id, option.extraction_method, option.extraction_version)
                elif existing.review_status not in {"approved", "reviewed"} and existing.content_origin != "human_corrected":
                    changed = any((
                        existing.text != option.text,
                        existing.source_span_id != option_span_id,
                    ))
                    if changed:
                        existing.text = option.text
                        existing.source_span_id = option_span_id
                        existing.version += 1
                if existing is not None:
                    _provenance(
                        session, "exercise_option", existing.id, option_span_id,
                        option.extraction_method, option.extraction_version,
                    )
            if item.answer is not None and item.answer_source is not None:
                answer_span = resolve_source(item.answer_source)
                if answer_span is not None:
                    answer_row = session.scalar(select(AnswerKey).where(
                        AnswerKey.exercise_id == row.id,
                        AnswerKey.answer_index == item.local_id,
                    ))
                    if answer_row is None:
                        answer_row = session.scalar(select(AnswerKey).where(
                            AnswerKey.exercise_id == row.id,
                            AnswerKey.answer_text == item.answer,
                            AnswerKey.source_span_id == answer_span,
                        ))
                    if answer_row is None:
                        answer_row = AnswerKey(
                            exercise_id=row.id, answer_text=item.answer,
                            source_span_id=answer_span, answer_index=item.local_id,
                        )
                        session.add(answer_row)
                        session.flush()
                        counts["answers"] += 1
                    elif answer_row.review_status not in {"approved", "reviewed"} and answer_row.content_origin != "human_corrected":
                        changed = any((
                            answer_row.answer_text != item.answer,
                            answer_row.source_span_id != answer_span,
                        ))
                        if changed:
                            answer_row.answer_text = item.answer
                            answer_row.source_span_id = answer_span
                            answer_row.version += 1
                    _provenance(session, "answer_key", answer_row.id, answer_span, item.extraction_method, item.extraction_version)

        track_ids: dict[str, int] = {}
        for item in bundle.listening_tracks:
            lesson_id = lesson_for_page(item.source.pdf_page_number)
            span_id = resolve_source(item.source)
            if span_id is None:
                continue
            row = session.scalar(select(ListeningTrack).where(
                ListeningTrack.lesson_id == lesson_id,
                ListeningTrack.track_identifier == item.track_identifier,
            )) if lesson_id is not None else None
            if row is None and lesson_id is not None:
                row = ListeningTrack(
                    lesson_id=lesson_id, source_span_id=span_id,
                    track_identifier=item.track_identifier, audio_status="missing",
                    review_status=item.review_status, extraction_version=item.extraction_version,
                )
                session.add(row)
                session.flush()
                counts["listening_tracks"] += 1
                _provenance(session, "listening_track", row.id, span_id, item.extraction_method, item.extraction_version)
            if row is not None:
                track_ids[item.track_identifier] = row.id

        for item in bundle.transcripts:
            track_id = track_ids.get(item.track_identifier)
            span_id = resolve_source(item.source)
            if track_id is None or span_id is None:
                continue
            if session.scalar(select(Transcript.id).where(
                Transcript.listening_track_id == track_id,
                Transcript.text == item.text,
                Transcript.source_span_id == span_id,
            )) is None:
                session.add(Transcript(
                    listening_track_id=track_id, text=item.text,
                    source_span_id=span_id, review_status=item.review_status,
                ))
                session.flush()
                counts["transcripts"] += 1
                transcript_id = session.scalar(select(Transcript.id).where(
                    Transcript.listening_track_id == track_id,
                    Transcript.text == item.text,
                    Transcript.source_span_id == span_id,
                ))
                _provenance(session, "transcript", transcript_id, span_id, item.extraction_method, item.extraction_version)
        for item in bundle.exercises:
            if not item.listening_track_id or item.local_id not in exercise_ids:
                continue
            track_id = track_ids.get(item.listening_track_id)
            if track_id is not None:
                session.get(Exercise, exercise_ids[item.local_id]).listening_track_id = track_id
    unresolved_pages = sorted({
        source.pdf_page_number
        for source, span_id in source_span_cache.items()
        if span_id is None
    })
    if unresolved_pages:
        bundle.warnings.append(
            "Source span unresolved; review required on page(s): "
            + ", ".join(str(page) for page in unresolved_pages)
        )
    counts["unresolved_sources"] = sum(
        span_id is None for span_id in source_span_cache.values()
    )
    session.flush()
    return counts
