from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import (
    AnswerKey,
    Dialogue,
    DialogueTurn,
    Exercise,
    ExerciseOption,
    GrammarPattern,
    Lesson,
    ListeningTrack,
    Passage,
    Sentence,
    SourcePage,
    SourceSpan,
    Textbook,
    Transcript,
    Vocabulary,
    WordSense,
)
from app.schemas import (
    DialogueResponse,
    DialogueTurnResponse,
    ExerciseResponse,
    GrammarResponse,
    LessonResponse,
    ListeningResponse,
    PassageResponse,
    SentenceResponse,
    TextbookResponse,
    VocabularyResponse,
)
from app.security import get_current_owner

router = APIRouter(prefix="/textbooks", tags=["textbooks"])


@router.get("", response_model=list[TextbookResponse])
def list_textbooks(
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> list[TextbookResponse]:
    textbooks = session.scalars(
        select(Textbook).where(Textbook.owner_id == owner_id).order_by(Textbook.volume_number)
    ).all()
    return [TextbookResponse(id=item.id, title=item.title, level=item.level, volume_number=item.volume_number) for item in textbooks]


@router.get("/{textbook_id}/lessons", response_model=list[LessonResponse])
def list_lessons(
    textbook_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> list[LessonResponse]:
    textbook = session.scalar(select(Textbook).where(
        Textbook.id == textbook_id,
        Textbook.owner_id == owner_id,
    ))
    if textbook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Textbook not found")
    lessons = session.scalars(select(Lesson).where(Lesson.textbook_id == textbook_id).order_by(Lesson.ordinal, Lesson.start_pdf_page)).all()
    return [LessonResponse(id=item.id, ordinal=item.ordinal, title=item.title, start_pdf_page=item.start_pdf_page, end_pdf_page=item.end_pdf_page, review_status=item.review_status) for item in lessons]


lesson_router = APIRouter(prefix="/lessons", tags=["lessons"])


def _lesson_or_404(session: Session, lesson_id: int, owner_id: str) -> Lesson:
    lesson = session.scalar(
        select(Lesson).join(Textbook).where(
            Lesson.id == lesson_id,
            Textbook.owner_id == owner_id,
        )
    )
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    return lesson


@lesson_router.get("/{lesson_id}", response_model=LessonResponse)
def get_lesson(
    lesson_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> LessonResponse:
    item = _lesson_or_404(session, lesson_id, owner_id)
    return LessonResponse(id=item.id, ordinal=item.ordinal, title=item.title, start_pdf_page=item.start_pdf_page, end_pdf_page=item.end_pdf_page, review_status=item.review_status)


@lesson_router.get("/{lesson_id}/vocabulary", response_model=list[VocabularyResponse])
def lesson_vocabulary(
    lesson_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    review_status: str | None = Query(None, max_length=32),
) -> list[VocabularyResponse]:
    _lesson_or_404(session, lesson_id, owner_id)
    query = select(Vocabulary).where(Vocabulary.lesson_id == lesson_id)
    if review_status:
        query = query.where(Vocabulary.review_status == review_status)
    rows = session.scalars(query.order_by(Vocabulary.id).offset(offset).limit(limit)).all()
    return [
        VocabularyResponse(
            id=item.id,
            headword=item.headword,
            meanings_vi=list(session.scalars(select(WordSense.meaning_vi).where(WordSense.vocabulary_id == item.id)).all()),
            source_page_number=_source_pdf_page(session, item.source_span_id),
            review_status=item.review_status,
        )
        for item in rows
    ]


@lesson_router.get("/{lesson_id}/grammar", response_model=list[GrammarResponse])
def lesson_grammar(
    lesson_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    review_status: str | None = Query(None, max_length=32),
) -> list[GrammarResponse]:
    _lesson_or_404(session, lesson_id, owner_id)
    query = select(GrammarPattern).where(GrammarPattern.lesson_id == lesson_id)
    if review_status:
        query = query.where(GrammarPattern.review_status == review_status)
    rows = session.scalars(query.order_by(GrammarPattern.id).offset(offset).limit(limit)).all()
    return [
        GrammarResponse(
            id=item.id,
            pattern=item.pattern,
            explanation_vi=item.explanation_vi,
            source_page_number=_source_pdf_page(session, item.source_span_id),
            review_status=item.review_status,
        )
        for item in rows
    ]


@lesson_router.get("/{lesson_id}/exercises", response_model=list[ExerciseResponse])
def lesson_exercises(
    lesson_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    review_status: str | None = Query(None, max_length=32),
) -> list[ExerciseResponse]:
    _lesson_or_404(session, lesson_id, owner_id)
    query = select(Exercise).where(Exercise.lesson_id == lesson_id)
    if review_status:
        query = query.where(Exercise.review_status == review_status)
    rows = session.scalars(query.order_by(Exercise.id).offset(offset).limit(limit)).all()
    return [
        ExerciseResponse(
            id=item.id,
            prompt=item.prompt,
            exercise_type=item.exercise_type,
            options=list(session.scalars(select(ExerciseOption.text).where(
                ExerciseOption.exercise_id == item.id,
            ).order_by(ExerciseOption.option_index)).all()),
            answer=session.scalar(select(AnswerKey.answer_text).where(AnswerKey.exercise_id == item.id)),
            source_page_number=_source_pdf_page(session, item.source_span_id),
            review_status=item.review_status,
        )
        for item in rows
    ]


def _source_pdf_page(session: Session, source_span_id: int | None) -> int | None:
    if source_span_id is None:
        return None
    return session.scalar(
        select(SourcePage.pdf_page_number)
        .join(SourceSpan, SourceSpan.source_page_id == SourcePage.id)
        .where(SourceSpan.id == source_span_id)
    )


@lesson_router.get("/{lesson_id}/sentences", response_model=list[SentenceResponse])
def lesson_sentences(
    lesson_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    review_status: str | None = Query(None, max_length=32),
) -> list[SentenceResponse]:
    _lesson_or_404(session, lesson_id, owner_id)
    query = select(Sentence).where(Sentence.lesson_id == lesson_id)
    if review_status:
        query = query.where(Sentence.review_status == review_status)
    rows = session.scalars(query.order_by(Sentence.id).offset(offset).limit(limit)).all()
    return [
        SentenceResponse(
            id=item.id, identity_id=item.identity_id, text_ko=item.text_ko, text_vi=item.text_vi,
            source_page_number=_source_pdf_page(session, item.source_span_id),
            review_status=item.review_status,
        )
        for item in rows
    ]


@lesson_router.get("/{lesson_id}/reading", response_model=list[PassageResponse])
def lesson_reading(
    lesson_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    review_status: str | None = Query(None, max_length=32),
) -> list[PassageResponse]:
    _lesson_or_404(session, lesson_id, owner_id)
    query = select(Passage).where(Passage.lesson_id == lesson_id)
    if review_status:
        query = query.where(Passage.review_status == review_status)
    rows = session.scalars(query.order_by(Passage.id).offset(offset).limit(limit)).all()
    return [
        PassageResponse(
            id=item.id, title=item.title, text=item.text,
            source_page_number=_source_pdf_page(session, item.source_span_id),
            review_status=item.review_status,
        )
        for item in rows
    ]


@lesson_router.get("/{lesson_id}/listening", response_model=list[ListeningResponse])
def lesson_listening(
    lesson_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    review_status: str | None = Query(None, max_length=32),
) -> list[ListeningResponse]:
    _lesson_or_404(session, lesson_id, owner_id)
    query = select(ListeningTrack).where(ListeningTrack.lesson_id == lesson_id)
    if review_status:
        query = query.where(ListeningTrack.review_status == review_status)
    rows = session.scalars(query.order_by(ListeningTrack.id).offset(offset).limit(limit)).all()
    return [
        ListeningResponse(
            id=item.id, track_identifier=item.track_identifier,
            audio_status=item.audio_status,
            transcript_available=session.scalar(select(Transcript.id).where(
                Transcript.listening_track_id == item.id,
            )) is not None,
            source_page_number=_source_pdf_page(session, item.source_span_id),
            review_status=item.review_status,
        )
        for item in rows
    ]


@lesson_router.get("/{lesson_id}/dialogues", response_model=list[DialogueResponse])
def lesson_dialogues(
    lesson_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> list[DialogueResponse]:
    _lesson_or_404(session, lesson_id, owner_id)
    rows = session.scalars(
        select(Dialogue).where(Dialogue.lesson_id == lesson_id)
        .order_by(Dialogue.id).offset(offset).limit(limit)
    ).all()
    return [
        DialogueResponse(
            id=item.id,
            group_identifier=item.group_identifier,
            topic=item.topic,
            source_page_number=_source_pdf_page(session, item.source_span_id),
            turns=[
                DialogueTurnResponse(
                    turn_index=turn.turn_index,
                    speaker=turn.speaker,
                    text_ko=turn.text,
                    text_vi=turn.text_vi,
                )
                for turn in session.scalars(
                    select(DialogueTurn).where(DialogueTurn.dialogue_id == item.id)
                    .order_by(DialogueTurn.turn_index)
                ).all()
            ],
        )
        for item in rows
    ]
