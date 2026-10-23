from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Exercise, GrammarPattern, Lesson, Textbook, Vocabulary
from app.schemas import ExerciseResponse, GrammarResponse, LessonResponse, TextbookResponse, VocabularyResponse

router = APIRouter(prefix="/textbooks", tags=["textbooks"])


@router.get("", response_model=list[TextbookResponse])
def list_textbooks(session: Session = Depends(get_session)) -> list[TextbookResponse]:
    textbooks = session.scalars(select(Textbook).order_by(Textbook.volume_number)).all()
    return [TextbookResponse(id=item.id, title=item.title, level=item.level, volume_number=item.volume_number) for item in textbooks]


@router.get("/{textbook_id}/lessons", response_model=list[LessonResponse])
def list_lessons(textbook_id: int, session: Session = Depends(get_session)) -> list[LessonResponse]:
    lessons = session.scalars(select(Lesson).where(Lesson.textbook_id == textbook_id).order_by(Lesson.ordinal, Lesson.start_pdf_page)).all()
    return [LessonResponse(id=item.id, ordinal=item.ordinal, title=item.title, start_pdf_page=item.start_pdf_page, end_pdf_page=item.end_pdf_page, review_status=item.review_status) for item in lessons]


lesson_router = APIRouter(prefix="/lessons", tags=["lessons"])


def _lesson_or_404(session: Session, lesson_id: int) -> Lesson:
    lesson = session.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    return lesson


@lesson_router.get("/{lesson_id}", response_model=LessonResponse)
def get_lesson(lesson_id: int, session: Session = Depends(get_session)) -> LessonResponse:
    item = _lesson_or_404(session, lesson_id)
    return LessonResponse(id=item.id, ordinal=item.ordinal, title=item.title, start_pdf_page=item.start_pdf_page, end_pdf_page=item.end_pdf_page, review_status=item.review_status)


@lesson_router.get("/{lesson_id}/vocabulary", response_model=list[VocabularyResponse])
def lesson_vocabulary(lesson_id: int, session: Session = Depends(get_session)) -> list[VocabularyResponse]:
    _lesson_or_404(session, lesson_id)
    return [VocabularyResponse(id=item.id, headword=item.headword, review_status=item.review_status) for item in session.scalars(select(Vocabulary).where(Vocabulary.lesson_id == lesson_id)).all()]


@lesson_router.get("/{lesson_id}/grammar", response_model=list[GrammarResponse])
def lesson_grammar(lesson_id: int, session: Session = Depends(get_session)) -> list[GrammarResponse]:
    _lesson_or_404(session, lesson_id)
    return [GrammarResponse(id=item.id, pattern=item.pattern, review_status=item.review_status) for item in session.scalars(select(GrammarPattern).where(GrammarPattern.lesson_id == lesson_id)).all()]


@lesson_router.get("/{lesson_id}/exercises", response_model=list[ExerciseResponse])
def lesson_exercises(lesson_id: int, session: Session = Depends(get_session)) -> list[ExerciseResponse]:
    _lesson_or_404(session, lesson_id)
    return [ExerciseResponse(id=item.id, prompt=item.prompt, review_status=item.review_status) for item in session.scalars(select(Exercise).where(Exercise.lesson_id == lesson_id)).all()]
