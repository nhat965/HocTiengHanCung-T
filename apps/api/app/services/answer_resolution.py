"""Conservative, source-backed answer-key resolution.

This module never generates answers.  It records an appendix candidate only
when a source span exists and it only auto-matches a question when the full
compound key is unique within one source document.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AnswerResolutionCandidate,
    ContentProvenance,
    ExerciseAnswerContext,
    SourceDocument,
    SourcePage,
    SourceSpan,
)

_SPACE = re.compile(r"\s+")
_SAFE_KEY = re.compile(r"[^a-z0-9가-힣]+", re.I)
_LESSON = re.compile(r"^\s*(?:bài|lesson)?\s*(0[1-9]|1[0-5])\s+.+$", re.I)
_GROUP = re.compile(r"^\s*(\d{1,2})\s+.+$")
_QUESTION = re.compile(r"\((\d{1,2})\)")
_SKILLS = {"말하기", "듣기", "읽기", "쓰기", "speaking", "listening", "reading", "writing"}


@dataclass(frozen=True)
class SourceTextBlock:
    text: str
    pdf_page_number: int
    source_span_id: int | None


@dataclass(frozen=True)
class QuestionReference:
    exercise_id: int
    source_document_id: int
    volume_number: int
    lesson_number: int
    skill_section: str
    exercise_group: str
    question_number: str
    question_source_span_id: int

    @property
    def compound_key(self) -> str:
        return compound_key(
            self.volume_number, self.lesson_number, self.skill_section,
            self.exercise_group, self.question_number,
        )


@dataclass(frozen=True)
class AnswerReference:
    source_document_id: int
    volume_number: int | None
    lesson_number: int | None
    skill_section: str | None
    exercise_group: str | None
    question_number: str | None
    answer_text: str
    answer_source_span_id: int | None

    @property
    def compound_key(self) -> str | None:
        if None in {
            self.volume_number, self.lesson_number, self.skill_section,
            self.exercise_group, self.question_number,
        }:
            return None
        return compound_key(
            int(self.volume_number), int(self.lesson_number), str(self.skill_section),
            str(self.exercise_group), str(self.question_number),
        )


def _token(value: str | int) -> str:
    normalized = _SAFE_KEY.sub("-", _SPACE.sub(" ", str(value).strip()).casefold()).strip("-")
    if not normalized:
        raise ValueError("Compound identifier has an empty component")
    return normalized


def compound_key(
    volume_number: int,
    lesson_number: int,
    skill_section: str,
    exercise_group: str,
    question_number: str,
) -> str:
    """Return the only key used for automatic matching in this pipeline."""
    return ":".join((
        f"volume-{_token(volume_number)}", f"lesson-{_token(lesson_number)}",
        f"skill-{_token(skill_section)}", f"group-{_token(exercise_group)}",
        f"question-{_token(question_number)}",
    ))


def extract_appendix_candidates(
    blocks: Iterable[SourceTextBlock], *, source_document_id: int, volume_number: int,
) -> list[AnswerReference]:
    """Extract only explicitly labelled appendix candidates.

    The textbook appendix reuses local numbering.  A line that lacks lesson,
    skill, group, question, text, or source span is emitted as an incomplete
    reference (and will be unresolved), never guessed into a key.
    """
    lesson: int | None = None
    skill: str | None = None
    group: str | None = None
    result: list[AnswerReference] = []
    for block in sorted(blocks, key=lambda item: (item.pdf_page_number, item.source_span_id or -1)):
        text = " ".join(block.text.split())
        if not text:
            continue
        lesson_match = _LESSON.match(text)
        if lesson_match:
            lesson = int(lesson_match.group(1))
            skill = None
            group = None
            continue
        if text in _SKILLS:
            skill = text
            group = None
            continue
        group_match = _GROUP.match(text)
        if group_match and any(marker in text for marker in ("알아", "봅시다", "listen", "read", "write", "speak")):
            group = group_match.group(1)
            continue
        question_matches = list(_QUESTION.finditer(text))
        if not question_matches:
            continue
        # Keep each answer fragment bounded by the next explicit question
        # marker.  We still do not infer any missing marker or hierarchy.
        for index, match in enumerate(question_matches):
            end = question_matches[index + 1].start() if index + 1 < len(question_matches) else len(text)
            answer = text[match.end():end].strip()
            if not answer:
                continue
            result.append(AnswerReference(
                source_document_id=source_document_id,
                volume_number=volume_number if lesson is not None else None,
                lesson_number=lesson,
                skill_section=skill,
                exercise_group=group,
                question_number=match.group(1),
                answer_text=answer,
                answer_source_span_id=block.source_span_id,
            ))
    return result


def _source_document_for_span(session: Session, span_id: int) -> int | None:
    return session.scalar(
        select(SourcePage.source_document_id)
        .join(SourceSpan, SourceSpan.source_page_id == SourcePage.id)
        .where(SourceSpan.id == span_id)
    )


def _add_provenance(session: Session, entity_type: str, entity_id: int, span_id: int) -> None:
    present = session.scalar(select(ContentProvenance.id).where(
        ContentProvenance.entity_type == entity_type,
        ContentProvenance.entity_id == entity_id,
        ContentProvenance.source_span_id == span_id,
        ContentProvenance.extraction_method == "answer-resolution-v1",
        ContentProvenance.extraction_version == "answer-resolution-v1",
    ))
    if present is None:
        session.add(ContentProvenance(
            entity_type=entity_type, entity_id=entity_id, source_span_id=span_id,
            extraction_method="answer-resolution-v1", extraction_version="answer-resolution-v1",
        ))


def persist_resolution_batch(
    session: Session,
    *,
    owner_id: str,
    source_document_id: int,
    questions: Iterable[QuestionReference],
    answers: Iterable[AnswerReference],
) -> dict[str, int]:
    """Upsert evidence, then match only unique compound keys transactionally."""
    source_document = session.scalar(select(SourceDocument).where(
        SourceDocument.id == source_document_id, SourceDocument.owner_id == owner_id,
    ))
    if source_document is None:
        raise ValueError("Resolution source document is not owned by reviewer")
    counts = {"contexts": 0, "candidates": 0, "matched": 0, "needs_review": 0, "unresolved": 0}
    with session.begin_nested():
        contexts: dict[str, ExerciseAnswerContext] = {}
        for question in questions:
            if question.source_document_id != source_document_id:
                raise ValueError("Question context must use the same source document")
            if _source_document_for_span(session, question.question_source_span_id) != source_document_id:
                raise ValueError("Question source span does not belong to source document")
            row = session.scalar(select(ExerciseAnswerContext).where(
                ExerciseAnswerContext.source_document_id == source_document_id,
                ExerciseAnswerContext.compound_key == question.compound_key,
            ))
            exercise_context = session.scalar(select(ExerciseAnswerContext).where(
                ExerciseAnswerContext.exercise_id == question.exercise_id,
            ))
            if row is None and exercise_context is not None:
                if exercise_context.compound_key != question.compound_key:
                    raise ValueError("Exercise already has a different answer compound key")
                row = exercise_context
            if row is None:
                row = ExerciseAnswerContext(
                    source_document_id=source_document_id, exercise_id=question.exercise_id,
                    volume_number=question.volume_number, lesson_number=question.lesson_number,
                    skill_section=question.skill_section, exercise_group=question.exercise_group,
                    question_number=question.question_number, compound_key=question.compound_key,
                    question_source_span_id=question.question_source_span_id,
                )
                session.add(row)
                session.flush()
                counts["contexts"] += 1
            elif row.exercise_id != question.exercise_id and row.review_status in {"verified", "approved"}:
                raise ValueError("Verified question context cannot be remapped")
            contexts[question.compound_key] = row
            _add_provenance(session, "exercise_answer_context", row.id, row.question_source_span_id)

        grouped_answers: dict[str | None, list[AnswerReference]] = {}
        for answer in answers:
            if answer.source_document_id != source_document_id:
                raise ValueError("Answer candidate must use the same source document")
            grouped_answers.setdefault(answer.compound_key, []).append(answer)
        for key, candidates in grouped_answers.items():
            context = contexts.get(key) if key is not None else None
            status = "matched_candidate" if key and context and len(candidates) == 1 else (
                "needs_review" if key and context and len(candidates) > 1 else "unresolved"
            )
            reason = (
                "Unique compound key matched question provenance" if status == "matched_candidate" else
                "Multiple appendix candidates share the compound key" if status == "needs_review" else
                "Missing or unmatched compound-key component"
            )
            for answer in candidates:
                if answer.answer_source_span_id is None:
                    status_for_answer, reason_for_answer = "unresolved", "Answer candidate has no source span"
                elif _source_document_for_span(session, answer.answer_source_span_id) != source_document_id:
                    raise ValueError("Answer source span does not belong to source document")
                else:
                    status_for_answer, reason_for_answer = status, reason
                row = session.scalar(select(AnswerResolutionCandidate).where(
                    AnswerResolutionCandidate.source_document_id == source_document_id,
                    AnswerResolutionCandidate.compound_key == answer.compound_key,
                    AnswerResolutionCandidate.answer_source_span_id == answer.answer_source_span_id,
                    AnswerResolutionCandidate.answer_text == answer.answer_text,
                ))
                if row is None:
                    row = AnswerResolutionCandidate(
                        owner_id=owner_id, source_document_id=source_document_id,
                        question_context_id=context.id if context else None,
                        volume_number=answer.volume_number, lesson_number=answer.lesson_number,
                        skill_section=answer.skill_section, exercise_group=answer.exercise_group,
                        question_number=answer.question_number, compound_key=answer.compound_key,
                        answer_text=answer.answer_text, answer_source_span_id=answer.answer_source_span_id,
                        status=status_for_answer, match_reason=reason_for_answer,
                    )
                    session.add(row)
                    session.flush()
                    counts["candidates"] += 1
                elif row.status not in {"verified", "approved"}:
                    row.question_context_id = context.id if context else None
                    row.status = status_for_answer
                    row.match_reason = reason_for_answer
                    row.version += 1
                if row.answer_source_span_id is not None:
                    _add_provenance(session, "answer_resolution_candidate", row.id, row.answer_source_span_id)
                counts["matched" if status_for_answer == "matched_candidate" else status_for_answer] += 1
    return counts
