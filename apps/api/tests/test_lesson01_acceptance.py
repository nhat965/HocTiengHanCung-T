from sqlalchemy import select

from app import database
from app.models import AnswerKey, ContentProvenance, Exercise, ExerciseOption, Lesson, SourceDocument, SourcePage, SourceSpan, StudyAttempt, Textbook
from app.services.knowledge.persistence import _provenance


def _lesson01_seed(session):
    textbook = Textbook(owner_id="test-owner", title="Volume 4", level="intermediate", volume_number=4)
    session.add(textbook)
    session.flush()
    document = SourceDocument(
        owner_id="test-owner", textbook_id=textbook.id, filename="authorized-fixture.pdf",
        sha256="1" * 64, page_count=338, file_size=1, source_path="private/fixture.pdf", rights_status="authorized",
    )
    session.add(document)
    session.flush()
    question_page = SourcePage(source_document_id=document.id, pdf_page_number=31, raw_text="question")
    answer_page = SourcePage(source_document_id=document.id, pdf_page_number=304, raw_text="answer")
    session.add_all([question_page, answer_page])
    session.flush()
    question_span = SourceSpan(source_page_id=question_page.id, label="raw_block", raw_text="question", normalized_text="question")
    answer_span = SourceSpan(source_page_id=answer_page.id, label="raw_block", raw_text="answer", normalized_text="answer")
    session.add_all([question_span, answer_span])
    session.flush()
    lesson = Lesson(textbook_id=textbook.id, ordinal=1, title="유행", start_pdf_page=18, end_pdf_page=35, segmentation_method="fixture", review_status="approved")
    session.add(lesson)
    session.flush()
    fill = Exercise(
        lesson_id=lesson.id, prompt="Fill two source blanks", source_span_id=question_span.id,
        exercise_type="fill_blank", interaction_config={"blank_count": 2}, review_status="approved", group_identifier="writing-2",
    )
    choice = Exercise(
        lesson_id=lesson.id, prompt="Source multiple choice", source_span_id=question_span.id,
        exercise_type="multiple_choice", review_status="approved", group_identifier="reading-2",
    )
    translation = Exercise(
        lesson_id=lesson.id, prompt="Source translation", source_span_id=question_span.id,
        exercise_type="translation_vi_ko", interaction_config={"translation_direction": "vi_to_ko"}, review_status="approved", group_identifier="writing-1",
    )
    free = Exercise(
        lesson_id=lesson.id, prompt="Source free response", source_span_id=question_span.id,
        exercise_type="free_response", interaction_config={"multiline": True}, review_status="approved", group_identifier="writing-3",
    )
    session.add_all([fill, choice, translation, free])
    session.flush()
    session.add_all([
        ExerciseOption(exercise_id=choice.id, option_index=1, text="A", source_span_id=question_span.id, review_status="approved"),
        ExerciseOption(exercise_id=choice.id, option_index=2, text="B", source_span_id=question_span.id, review_status="approved"),
        ExerciseOption(exercise_id=choice.id, option_index=3, text="C", source_span_id=question_span.id, review_status="approved"),
        AnswerKey(exercise_id=fill.id, answer_text="가 나", source_span_id=answer_span.id, answer_index="fill", review_status="approved"),
        AnswerKey(exercise_id=choice.id, answer_text="B", source_span_id=answer_span.id, answer_index="choice", review_status="approved"),
        AnswerKey(exercise_id=translation.id, answer_text="Source reference", source_span_id=answer_span.id, answer_index="translation", review_status="approved"),
        AnswerKey(exercise_id=free.id, answer_text="Source guidance", source_span_id=answer_span.id, answer_index="free", review_status="approved"),
    ])
    session.commit()
    return lesson.id, fill.id, choice.id, translation.id, free.id


def test_lesson01_exercise_types_are_safe_and_learner_ready(client):
    with database.SessionLocal() as session:
        lesson_id, fill_id, choice_id, translation_id, free_id = _lesson01_seed(session)

    feed = client.get(f"/api/v1/lessons/{lesson_id}/exercises?review_status=approved")
    assert feed.status_code == 200
    rows = {row["id"]: row for row in feed.json()}
    assert rows[fill_id]["interaction_config"] == {"blank_count": 2}
    assert [option["option_index"] for option in rows[choice_id]["options"]] == [1, 2, 3]
    assert rows[translation_id]["interaction_config"]["translation_direction"] == "vi_to_ko"

    fill = client.post(f"/api/v1/study/exercises/{fill_id}/attempt", json={"answer": "가   나"})
    assert fill.status_code == 200
    assert fill.json()["correct"] is True and fill.json()["grading_status"] == "graded"

    choice = client.post(f"/api/v1/study/exercises/{choice_id}/attempt", json={"answer": "2"})
    assert choice.status_code == 200
    assert choice.json()["correct"] is True and choice.json()["grading_status"] == "graded"

    translation = client.post(f"/api/v1/study/exercises/{translation_id}/attempt", json={"answer": "A different valid wording"})
    assert translation.status_code == 200
    assert translation.json() == {
        "attempt_id": translation.json()["attempt_id"], "exercise_id": translation_id,
        "correct": None, "answer_revealed": "Source reference", "grading_status": "reference_available",
    }

    free = client.post(f"/api/v1/study/exercises/{free_id}/attempt", json={"answer": "A multiline response"})
    assert free.status_code == 200
    assert free.json()["correct"] is None
    assert free.json()["answer_revealed"] is None
    assert free.json()["grading_status"] == "pending_review"

    with database.SessionLocal() as session:
        attempts = list(session.scalars(select(StudyAttempt).where(StudyAttempt.exercise_id.in_([fill_id, choice_id, translation_id, free_id]))))
        assert len(attempts) == 4


def test_repeated_option_source_in_one_bundle_does_not_duplicate_provenance(client):
    """Regression: appendix extraction can repeat one option source in a bundle."""
    with database.SessionLocal() as session:
        _, _, choice_id, _, _ = _lesson01_seed(session)
        option = session.scalar(select(ExerciseOption).where(
            ExerciseOption.exercise_id == choice_id,
            ExerciseOption.option_index == 1,
        ))
        assert option is not None
        _provenance(session, "exercise_option", option.id, option.source_span_id, "fixture-v1", "v1")
        _provenance(session, "exercise_option", option.id, option.source_span_id, "fixture-v1", "v1")
        session.commit()
        assert session.scalar(select(ContentProvenance).where(
            ContentProvenance.entity_type == "exercise_option",
            ContentProvenance.entity_id == option.id,
            ContentProvenance.extraction_method == "fixture-v1",
        )) is not None
        assert len(list(session.scalars(select(ContentProvenance).where(
            ContentProvenance.entity_type == "exercise_option",
            ContentProvenance.entity_id == option.id,
            ContentProvenance.extraction_method == "fixture-v1",
        )))) == 1
