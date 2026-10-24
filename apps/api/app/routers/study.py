from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import (
    AnswerKey, Exercise, ExerciseOption, GrammarNote, GrammarPattern,
    Lesson, LessonProgress, Sentence, StudyAttempt, Textbook, Vocabulary,
    VocabularyProgress, WordSense, sentence_vocabulary,
)
from app.schemas import (
    ExerciseAttemptRequest, ExerciseAttemptResponse, GrammarNoteRequest,
    GrammarNoteResponse, LessonProgressResponse, StudyFlashcardResponse,
    StudyProgressResponse, VocabularyReviewRequest, VocabularyReviewResponse,
)
from app.security import get_current_owner
from app.services.normalization import normalize_source_text

router = APIRouter(prefix="/study", tags=["study"])

_CIRCLED_DIGITS = "①②③④⑤⑥⑦⑧⑨⑩"
_CIRCLED_LETTERS = "ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙ"


def _choice_aliases(value: str) -> set[str]:
    normalized = normalize_source_text(value).casefold()
    aliases = {normalized}
    if normalized in _CIRCLED_DIGITS:
        index = _CIRCLED_DIGITS.index(normalized) + 1
        aliases.update({str(index), chr(ord("a") + index - 1)})
    elif normalized in _CIRCLED_LETTERS:
        index = _CIRCLED_LETTERS.index(normalized) + 1
        aliases.update({str(index), chr(ord("a") + index - 1)})
    elif normalized.isalpha() and "a" <= normalized <= "j":
        aliases.add(str(ord(normalized) - ord("a") + 1))
    elif normalized.isdigit() and 1 <= int(normalized) <= 10:
        index = int(normalized)
        aliases.update({chr(ord("a") + index - 1), _CIRCLED_DIGITS[index - 1]})
    return aliases


def _approved_vocabulary(session: Session, vocabulary_id: int, owner_id: str) -> Vocabulary:
    item = session.scalar(
        select(Vocabulary).join(Lesson).join(Textbook).where(
            Vocabulary.id == vocabulary_id,
            Vocabulary.review_status == "approved",
            Textbook.owner_id == owner_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Approved vocabulary not found")
    return item


def _owned_lesson(session: Session, lesson_id: int, owner_id: str) -> Lesson:
    lesson = session.scalar(select(Lesson).join(Textbook).where(
        Lesson.id == lesson_id, Textbook.owner_id == owner_id,
    ))
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson


def _approved_grammar(session: Session, grammar_id: int, owner_id: str) -> GrammarPattern:
    grammar = session.scalar(
        select(GrammarPattern).join(Lesson).join(Textbook).where(
            GrammarPattern.id == grammar_id,
            GrammarPattern.review_status == "approved",
            Textbook.owner_id == owner_id,
        )
    )
    if grammar is None:
        raise HTTPException(status_code=404, detail="Approved grammar pattern not found")
    return grammar


@router.get("/lessons/{lesson_id}/flashcards", response_model=list[StudyFlashcardResponse])
def lesson_flashcards(
    lesson_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> list[StudyFlashcardResponse]:
    owned = session.scalar(select(Lesson.id).join(Textbook).where(
        Lesson.id == lesson_id, Textbook.owner_id == owner_id,
    ))
    if owned is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    rows = session.execute(
        select(Vocabulary, VocabularyProgress)
        .outerjoin(VocabularyProgress, (VocabularyProgress.vocabulary_id == Vocabulary.id)
                   & (VocabularyProgress.owner_id == owner_id))
        .where(Vocabulary.lesson_id == lesson_id, Vocabulary.review_status == "approved")
        .order_by(Vocabulary.id)
    ).all()
    result = []
    for item, progress in rows:
        meanings = list(session.scalars(select(WordSense.meaning_vi).where(
            WordSense.vocabulary_id == item.id,
            WordSense.review_status == "approved",
        )).all())
        if meanings:
            examples = list(session.scalars(
                select(Sentence.text_ko)
                .join(sentence_vocabulary, sentence_vocabulary.c.sentence_id == Sentence.id)
                .where(
                    sentence_vocabulary.c.vocabulary_id == item.id,
                    Sentence.review_status == "approved",
                )
                .order_by(Sentence.id)
            ).all())
            result.append(StudyFlashcardResponse(
                vocabulary_id=item.id,
                headword=item.headword,
                meanings_vi=meanings,
                examples=examples,
                status=progress.status if progress else "new",
                next_review_at=progress.next_review_at if progress else None,
            ))
    return result


@router.post("/vocabulary/{vocabulary_id}/review", response_model=VocabularyReviewResponse)
def review_vocabulary(
    vocabulary_id: int,
    payload: VocabularyReviewRequest,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> VocabularyReviewResponse:
    item = _approved_vocabulary(session, vocabulary_id, owner_id)
    approved_meanings = list(session.scalars(select(WordSense.meaning_vi).where(
        WordSense.vocabulary_id == item.id,
        WordSense.review_status == "approved",
    )).all())
    if not approved_meanings:
        raise HTTPException(status_code=409, detail="Vocabulary has no approved meaning")
    answer = normalize_source_text(payload.answer_vi).casefold()
    correct = any(answer == normalize_source_text(meaning).casefold() for meaning in approved_meanings)
    now = datetime.utcnow()
    progress = session.scalar(select(VocabularyProgress).where(
        VocabularyProgress.owner_id == owner_id,
        VocabularyProgress.vocabulary_id == item.id,
    ))
    if progress is None:
        progress = VocabularyProgress(
            owner_id=owner_id, vocabulary_id=item.id,
            status="new", repetitions=0, interval_days=0,
        )
        session.add(progress)
    if correct:
        progress.repetitions += 1
        intervals = (1, 3, 7, 14, 30)
        progress.interval_days = intervals[min(progress.repetitions - 1, len(intervals) - 1)]
        progress.status = "learned" if progress.repetitions >= 5 else "learning"
    else:
        progress.repetitions = 0
        progress.interval_days = 1
        progress.status = "learning"
    progress.last_reviewed_at = now
    progress.next_review_at = now + timedelta(days=progress.interval_days)
    session.add(StudyAttempt(
        owner_id=owner_id, vocabulary_id=item.id,
        response=payload.answer_vi, correct=correct,
    ))
    session.commit()
    return VocabularyReviewResponse(
        vocabulary_id=item.id, correct=correct, status=progress.status,
        repetitions=progress.repetitions, interval_days=progress.interval_days,
        next_review_at=progress.next_review_at,
    )


@router.post("/vocabulary/{vocabulary_id}/learned", response_model=VocabularyReviewResponse)
def mark_vocabulary_learned(
    vocabulary_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> VocabularyReviewResponse:
    item = _approved_vocabulary(session, vocabulary_id, owner_id)
    now = datetime.utcnow()
    progress = session.scalar(select(VocabularyProgress).where(
        VocabularyProgress.owner_id == owner_id,
        VocabularyProgress.vocabulary_id == item.id,
    )) or VocabularyProgress(
        owner_id=owner_id, vocabulary_id=item.id,
        status="new", repetitions=0, interval_days=0,
    )
    progress.status = "learned"
    progress.repetitions = max(progress.repetitions, 5)
    progress.interval_days = 30
    progress.last_reviewed_at = now
    progress.next_review_at = now + timedelta(days=30)
    session.add(progress)
    session.commit()
    return VocabularyReviewResponse(
        vocabulary_id=item.id, correct=True, status=progress.status,
        repetitions=progress.repetitions, interval_days=progress.interval_days,
        next_review_at=progress.next_review_at,
    )


@router.post("/lessons/{lesson_id}/complete", response_model=LessonProgressResponse)
def complete_lesson(
    lesson_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> LessonProgressResponse:
    _owned_lesson(session, lesson_id, owner_id)
    progress = session.scalar(select(LessonProgress).where(
        LessonProgress.owner_id == owner_id, LessonProgress.lesson_id == lesson_id,
    )) or LessonProgress(owner_id=owner_id, lesson_id=lesson_id)
    progress.status = "completed"
    now = datetime.utcnow()
    progress.completed_at = progress.completed_at or now
    progress.last_opened_at = progress.last_opened_at or now
    session.add(progress)
    session.commit()
    return LessonProgressResponse(
        lesson_id=lesson_id, status=progress.status, completed_at=progress.completed_at,
        last_opened_at=progress.last_opened_at,
    )


@router.post("/lessons/{lesson_id}/open", response_model=LessonProgressResponse)
def open_lesson(
    lesson_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> LessonProgressResponse:
    _owned_lesson(session, lesson_id, owner_id)
    progress = session.scalar(select(LessonProgress).where(
        LessonProgress.owner_id == owner_id,
        LessonProgress.lesson_id == lesson_id,
    ))
    now = datetime.utcnow()
    if progress is None:
        progress = LessonProgress(
            owner_id=owner_id, lesson_id=lesson_id, status="in_progress",
            last_opened_at=now,
        )
        session.add(progress)
    else:
        if progress.status != "completed":
            progress.status = "in_progress"
        progress.last_opened_at = now
    session.commit()
    return LessonProgressResponse(
        lesson_id=lesson_id, status=progress.status,
        completed_at=progress.completed_at, last_opened_at=progress.last_opened_at,
    )


@router.post("/exercises/{exercise_id}/attempt", response_model=ExerciseAttemptResponse)
def submit_exercise_attempt(
    exercise_id: int,
    payload: ExerciseAttemptRequest,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> ExerciseAttemptResponse:
    exercise = session.scalar(
        select(Exercise).join(Lesson).join(Textbook).where(
            Exercise.id == exercise_id,
            Exercise.review_status == "approved",
            Textbook.owner_id == owner_id,
        )
    )
    if exercise is None:
        raise HTTPException(status_code=404, detail="Approved exercise not found")
    all_options = []
    approved_options = []
    if exercise.exercise_type in {"multiple_choice", "single_choice"}:
        all_options = list(session.scalars(select(ExerciseOption).where(
            ExerciseOption.exercise_id == exercise.id,
        ).order_by(ExerciseOption.option_index)).all())
        if len(all_options) < 2:
            raise HTTPException(
                status_code=409,
                detail="Multiple-choice exercise is incomplete and needs review",
            )
        approved_options = list(session.scalars(select(ExerciseOption).where(
            ExerciseOption.exercise_id == exercise.id,
            ExerciseOption.review_status == "approved",
        ).order_by(ExerciseOption.option_index)).all())
    answer_key = session.scalar(select(AnswerKey).where(
        AnswerKey.exercise_id == exercise.id,
        AnswerKey.review_status == "approved",
    ).order_by(AnswerKey.id))
    if (
        answer_key is not None
        and exercise.exercise_type in {"multiple_choice", "single_choice"}
        and len(approved_options) < 2
    ):
        raise HTTPException(
            status_code=409,
            detail="Multiple-choice options must be approved before grading",
        )
    correct: bool | None = None
    revealed: str | None = None
    if answer_key is not None:
        expected = normalize_source_text(answer_key.answer_text).casefold()
        submitted = normalize_source_text(payload.answer).casefold()
        correct = submitted == expected
        if exercise.exercise_type in {"multiple_choice", "single_choice"}:
            for option in approved_options:
                option_text = normalize_source_text(option.text).casefold()
                option_label = chr(ord("A") + option.option_index - 1).casefold()
                expected_matches = bool(_choice_aliases(expected) & {
                    option_text, str(option.option_index), option_label,
                })
                submitted_matches = bool(_choice_aliases(submitted) & {
                    option_text, str(option.option_index), option_label,
                })
                if expected_matches:
                    correct = submitted_matches
                    break
        revealed = answer_key.answer_text
    attempt = StudyAttempt(
        owner_id=owner_id, exercise_id=exercise.id,
        response=payload.answer, correct=correct,
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return ExerciseAttemptResponse(
        attempt_id=attempt.id, exercise_id=exercise.id,
        correct=correct, answer_revealed=revealed,
    )


@router.get("/grammar/{grammar_id}/note", response_model=GrammarNoteResponse)
def get_grammar_note(
    grammar_id: int,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> GrammarNoteResponse:
    grammar = _approved_grammar(session, grammar_id, owner_id)
    row = session.scalar(select(GrammarNote).where(
        GrammarNote.owner_id == owner_id,
        GrammarNote.grammar_pattern_id == grammar.id,
    ))
    return GrammarNoteResponse(
        grammar_id=grammar.id,
        note=row.note if row else "",
        updated_at=row.updated_at if row else None,
    )


@router.post("/grammar/{grammar_id}/note", response_model=GrammarNoteResponse)
def save_grammar_note(
    grammar_id: int,
    payload: GrammarNoteRequest,
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> GrammarNoteResponse:
    grammar = _approved_grammar(session, grammar_id, owner_id)
    row = session.scalar(select(GrammarNote).where(
        GrammarNote.owner_id == owner_id,
        GrammarNote.grammar_pattern_id == grammar.id,
    ))
    if row is None:
        row = GrammarNote(
            owner_id=owner_id, grammar_pattern_id=grammar.id, note=payload.note,
        )
        session.add(row)
    else:
        row.note = payload.note
        row.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(row)
    return GrammarNoteResponse(grammar_id=grammar.id, note=row.note, updated_at=row.updated_at)


@router.get("/progress", response_model=StudyProgressResponse)
def study_progress(
    session: Session = Depends(get_session),
    owner_id: str = Depends(get_current_owner),
) -> StudyProgressResponse:
    approved_ids = select(Vocabulary.id).join(Lesson).join(Textbook).where(
        Textbook.owner_id == owner_id, Vocabulary.review_status == "approved",
    )
    approved = session.scalar(select(func.count()).select_from(approved_ids.subquery())) or 0
    learned = session.scalar(select(func.count(VocabularyProgress.id)).where(
        VocabularyProgress.owner_id == owner_id,
        VocabularyProgress.status == "learned",
        VocabularyProgress.vocabulary_id.in_(approved_ids),
    )) or 0
    now = datetime.utcnow()
    due = session.scalar(
        select(func.count(Vocabulary.id))
        .join(Lesson).join(Textbook)
        .outerjoin(
            VocabularyProgress,
            and_(
                VocabularyProgress.vocabulary_id == Vocabulary.id,
                VocabularyProgress.owner_id == owner_id,
            ),
        )
        .where(
            Textbook.owner_id == owner_id,
            Vocabulary.review_status == "approved",
            or_(
                VocabularyProgress.id.is_(None),
                VocabularyProgress.next_review_at.is_(None),
                VocabularyProgress.next_review_at <= now,
            ),
        )
    ) or 0
    attempts = session.scalar(select(func.count(StudyAttempt.id)).where(
        StudyAttempt.owner_id == owner_id,
    )) or 0
    total_lessons = session.scalar(
        select(func.count(Lesson.id)).join(Textbook).where(Textbook.owner_id == owner_id)
    ) or 0
    completed_lessons = session.scalar(
        select(func.count(LessonProgress.id))
        .join(Lesson).join(Textbook)
        .where(
            Textbook.owner_id == owner_id,
            LessonProgress.owner_id == owner_id,
            LessonProgress.status == "completed",
        )
    ) or 0
    last_opened = session.execute(
        select(Lesson.id, Lesson.title)
        .join(LessonProgress, LessonProgress.lesson_id == Lesson.id)
        .join(Textbook)
        .where(
            Textbook.owner_id == owner_id,
            LessonProgress.owner_id == owner_id,
            LessonProgress.last_opened_at.is_not(None),
        )
        .order_by(LessonProgress.last_opened_at.desc(), LessonProgress.id.desc())
        .limit(1)
    ).first()
    return StudyProgressResponse(
        approved_vocabulary=approved, learned_vocabulary=learned,
        due_vocabulary=due, attempts=attempts,
        completed_lessons=completed_lessons, total_lessons=total_lessons,
        last_lesson_id=last_opened.id if last_opened else None,
        last_lesson_title=last_opened.title if last_opened else None,
    )
