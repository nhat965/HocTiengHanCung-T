from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import GrammarPattern, Lesson, SourcePage, Vocabulary


@dataclass(frozen=True)
class QualityReport:
    source_document_id: int
    processed_pages: int
    pages_needing_ocr: int
    lessons: int
    vocabulary: int
    grammar_patterns: int
    coverage_note: str
    accuracy_note: str


def build_quality_report(session: Session, source_document_id: int) -> QualityReport:
    pages = session.scalars(select(SourcePage).where(SourcePage.source_document_id == source_document_id)).all()
    from app.models import SourceDocument
    textbook_id = session.scalar(select(SourceDocument.textbook_id).where(SourceDocument.id == source_document_id))
    # Vocabulary/grammar are deliberately reported as database coverage, never accuracy.
    return QualityReport(
        source_document_id=source_document_id,
        processed_pages=len(pages),
        pages_needing_ocr=sum(page.needs_ocr for page in pages),
        lessons=session.scalar(select(func.count(Lesson.id)).where(Lesson.textbook_id == textbook_id)) or 0,
        vocabulary=session.scalar(select(func.count(Vocabulary.id)).join(Lesson).where(Lesson.textbook_id == textbook_id)) or 0,
        grammar_patterns=session.scalar(select(func.count(GrammarPattern.id)).join(Lesson).where(Lesson.textbook_id == textbook_id)) or 0,
        coverage_note="Coverage measures persisted extraction output only; it does not validate correctness against the PDF.",
        accuracy_note="Accuracy is unknown until a human review compares extracted records to source spans.",
    )


def write_quality_report(report: QualityReport, output_dir: Path) -> tuple[Path, Path]:
    import json
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"source-{report.source_document_id}-quality.json"
    markdown_path = output_dir / f"source-{report.source_document_id}-quality.md"
    json_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text("# PDF extraction quality report\n\n" + "\n".join(f"- **{key}**: {value}" for key, value in asdict(report).items()) + "\n", encoding="utf-8")
    return json_path, markdown_path
