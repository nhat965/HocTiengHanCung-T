from __future__ import annotations

import pytest
from sqlalchemy import select

from app import database
from app.models import (
    AnswerKey, AnswerResolutionCandidate, Exercise, ExerciseAnswerContext,
    Lesson, SourceDocument, SourcePage, SourceSpan, Textbook,
)
from app.services.answer_resolution import (
    AnswerReference, QuestionReference, SourceTextBlock, extract_appendix_candidates,
    persist_resolution_batch,
)


def _seed(session, *, group: str = "1", question: str = "1", exercise_type: str = "fill_blank"):
    textbook = Textbook(owner_id="test-owner", title="Volume 4", level="intermediate", volume_number=4)
    session.add(textbook)
    session.flush()
    document = SourceDocument(
        owner_id="test-owner", textbook_id=textbook.id, filename="fixture.pdf", sha256=f"{group}{question}".ljust(64, "0"),
        page_count=338, file_size=1, source_path="private/fixture.pdf", rights_status="authorized",
    )
    session.add(document)
    session.flush()
    question_page = SourcePage(source_document_id=document.id, pdf_page_number=18, raw_text="question")
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
    exercise = Exercise(
        lesson_id=lesson.id, prompt="Source-backed question", source_span_id=question_span.id,
        review_status="approved", exercise_type=exercise_type, group_identifier=group,
    )
    session.add(exercise)
    session.flush()
    return document, exercise, question_span, answer_span


def _question(document, exercise, question_span, *, group="1", question="1"):
    return QuestionReference(
        exercise_id=exercise.id, source_document_id=document.id, volume_number=4, lesson_number=1,
        skill_section="읽기", exercise_group=group, question_number=question,
        question_source_span_id=question_span.id,
    )


def _answer(document, answer_span, *, group="1", question="1", text="정답"):
    return AnswerReference(
        source_document_id=document.id, volume_number=4, lesson_number=1, skill_section="읽기",
        exercise_group=group, question_number=question, answer_text=text,
        answer_source_span_id=answer_span.id,
    )


def test_exact_compound_key_matches_and_reimport_is_idempotent(client):
    with database.SessionLocal() as session:
        document, exercise, question_span, answer_span = _seed(session)
        question = _question(document, exercise, question_span)
        answer = _answer(document, answer_span)
        first = persist_resolution_batch(session, owner_id="test-owner", source_document_id=document.id, questions=[question], answers=[answer])
        second = persist_resolution_batch(session, owner_id="test-owner", source_document_id=document.id, questions=[question], answers=[answer])
        session.commit()
        candidate = session.scalar(select(AnswerResolutionCandidate))
        assert first == {"contexts": 1, "candidates": 1, "matched": 1, "needs_review": 0, "unresolved": 0}
        assert second["contexts"] == 0 and second["candidates"] == 0
        assert candidate.status == "matched_candidate"
        assert candidate.question_context_id is not None
        assert session.scalar(select(ExerciseAnswerContext).where(ExerciseAnswerContext.exercise_id == exercise.id)) is not None


def test_same_question_number_in_two_groups_does_not_cross_match(client):
    with database.SessionLocal() as session:
        document, first_exercise, first_span, answer_span = _seed(session, group="1")
        second_exercise = Exercise(
            lesson_id=first_exercise.lesson_id, prompt="Other group", source_span_id=first_span.id,
            review_status="approved", exercise_type="fill_blank", group_identifier="2",
        )
        session.add(second_exercise)
        session.flush()
        questions = [
            _question(document, first_exercise, first_span, group="1"),
            _question(document, second_exercise, first_span, group="2"),
        ]
        answers = [_answer(document, answer_span, group="1", text="A"), _answer(document, answer_span, group="2", text="B")]
        persist_resolution_batch(session, owner_id="test-owner", source_document_id=document.id, questions=questions, answers=answers)
        session.commit()
        rows = list(session.scalars(select(AnswerResolutionCandidate).order_by(AnswerResolutionCandidate.id)))
        assert [row.status for row in rows] == ["matched_candidate", "matched_candidate"]
        assert {session.get(ExerciseAnswerContext, row.question_context_id).exercise_id for row in rows} == {first_exercise.id, second_exercise.id}


def test_unmatched_and_ambiguous_candidates_are_not_auto_matched(client):
    with database.SessionLocal() as session:
        document, exercise, question_span, answer_span = _seed(session)
        question = _question(document, exercise, question_span)
        counts = persist_resolution_batch(
            session, owner_id="test-owner", source_document_id=document.id, questions=[question],
            answers=[_answer(document, answer_span, group="9", text="missing")],
        )
        assert counts["unresolved"] == 1
        # A different source span makes both candidates separately sourced but ambiguous.
        extra_page = SourcePage(source_document_id=document.id, pdf_page_number=305, raw_text="answer two")
        session.add(extra_page)
        session.flush()
        extra_span = SourceSpan(source_page_id=extra_page.id, label="raw_block", raw_text="two", normalized_text="two")
        session.add(extra_span)
        session.flush()
        persist_resolution_batch(
            session, owner_id="test-owner", source_document_id=document.id, questions=[question],
            answers=[_answer(document, answer_span, text="one"), _answer(document, extra_span, text="two")],
        )
        session.commit()
        matched = list(session.scalars(select(AnswerResolutionCandidate).where(AnswerResolutionCandidate.compound_key == question.compound_key)))
        assert {row.status for row in matched} == {"needs_review"}


def test_appendix_extractor_requires_context_and_source_span():
    rows = extract_appendix_candidates([
        SourceTextBlock("01 유행", 304, 1),
        SourceTextBlock("읽기", 304, 2),
        SourceTextBlock("1 알아봅시다", 304, 3),
        SourceTextBlock("1 (1) ○", 304, 4),
    ], source_document_id=1, volume_number=4)
    assert len(rows) == 1
    assert rows[0].compound_key is not None and "lesson-1" in rows[0].compound_key
    assert rows[0].answer_source_span_id == 4
    split = extract_appendix_candidates([
        SourceTextBlock("01 유행", 304, 1), SourceTextBlock("읽기", 304, 2),
        SourceTextBlock("1 알아봅시다", 304, 3), SourceTextBlock("1 (1) ○ (2) ×", 304, 4),
    ], source_document_id=1, volume_number=4)
    assert [row.answer_text for row in split] == ["○", "×"]


def test_changed_compound_key_cannot_duplicate_an_exercise_context(client):
    with database.SessionLocal() as session:
        document, exercise, question_span, answer_span = _seed(session)
        persist_resolution_batch(
            session, owner_id="test-owner", source_document_id=document.id,
            questions=[_question(document, exercise, question_span, group="1")], answers=[_answer(document, answer_span)],
        )
        with pytest.raises(ValueError, match="different answer compound key"):
            persist_resolution_batch(
                session, owner_id="test-owner", source_document_id=document.id,
                questions=[_question(document, exercise, question_span, group="2")], answers=[],
            )
        assert session.scalar(select(ExerciseAnswerContext).where(ExerciseAnswerContext.exercise_id == exercise.id)).exercise_group == "1"


def test_reviewer_confirm_reject_and_approved_answer_key(client):
    with database.SessionLocal() as session:
        document, exercise, question_span, answer_span = _seed(session)
        persist_resolution_batch(
            session, owner_id="test-owner", source_document_id=document.id,
            questions=[_question(document, exercise, question_span)], answers=[_answer(document, answer_span)],
        )
        session.commit()
        candidate = session.scalar(select(AnswerResolutionCandidate))
        candidate_id, version, exercise_id = candidate.id, candidate.version, exercise.id
    before = client.post(f"/api/v1/study/exercises/{exercise_id}/attempt", json={"answer": "정답"})
    assert before.status_code == 200 and before.json()["correct"] is None
    confirmed = client.post(f"/api/v1/answer-resolution/{candidate_id}/review", json={"action": "confirm", "expected_version": version})
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "verified"
    approved = client.post(f"/api/v1/answer-resolution/{candidate_id}/approve", json={
        "expected_version": confirmed.json()["version"],
        "checks": ["source_text", "source_page", "source_position", "semantic_alignment", "structure"],
    })
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    after = client.post(f"/api/v1/study/exercises/{exercise_id}/attempt", json={"answer": "정답"})
    assert after.status_code == 200 and after.json()["correct"] is True
    rejected = client.post(f"/api/v1/answer-resolution/{candidate_id}/review", json={"action": "reject", "expected_version": approved.json()["version"]})
    assert rejected.status_code == 409


def test_reviewer_can_reject_unresolved_pair(client):
    with database.SessionLocal() as session:
        document, exercise, question_span, answer_span = _seed(session)
        persist_resolution_batch(
            session, owner_id="test-owner", source_document_id=document.id,
            questions=[_question(document, exercise, question_span)], answers=[_answer(document, answer_span, group="9")],
        )
        session.commit()
        candidate = session.scalar(select(AnswerResolutionCandidate))
    response = client.post(f"/api/v1/answer-resolution/{candidate.id}/review", json={"action": "reject", "expected_version": candidate.version, "note": "No matching group"})
    assert response.status_code == 200
    assert response.json()["status"] == "unresolved"


def test_approved_answer_key_is_not_overwritten_and_batch_rolls_back(client):
    with database.SessionLocal() as session:
        document, exercise, question_span, answer_span = _seed(session)
        persist_resolution_batch(
            session, owner_id="test-owner", source_document_id=document.id,
            questions=[_question(document, exercise, question_span)], answers=[_answer(document, answer_span, text="new")],
        )
        session.commit()
        candidate = session.scalar(select(AnswerResolutionCandidate))
        candidate.status = "verified"
        session.add(AnswerKey(exercise_id=exercise.id, answer_text="manual", source_span_id=answer_span.id,
                              answer_index=candidate.compound_key, review_status="approved", content_origin="human_corrected"))
        session.commit()
        candidate_id, version = candidate.id, candidate.version
    conflict = client.post(f"/api/v1/answer-resolution/{candidate_id}/approve", json={
        "expected_version": version,
        "checks": ["source_text", "source_page", "source_position", "semantic_alignment", "structure"],
    })
    assert conflict.status_code == 409
    with database.SessionLocal() as session:
        document = session.scalar(select(SourceDocument))
        exercise = session.scalar(select(Exercise))
        span = session.scalar(select(SourceSpan))
        rollback_exercise = Exercise(
            lesson_id=exercise.lesson_id, prompt="Rollback target", source_span_id=span.id,
            review_status="pending", exercise_type="fill_blank", group_identifier="77",
        )
        session.add(rollback_exercise)
        session.flush()
        bad = QuestionReference(rollback_exercise.id, document.id, 4, 1, "읽기", "77", "1", span.id)
        with pytest.raises(ValueError, match="Answer source span"):
            persist_resolution_batch(
                session, owner_id="test-owner", source_document_id=document.id, questions=[bad],
                answers=[AnswerReference(document.id, 4, 1, "읽기", "77", "1", "bad", 999999)],
            )
        assert session.scalar(select(ExerciseAnswerContext).where(ExerciseAnswerContext.compound_key == bad.compound_key)) is None
