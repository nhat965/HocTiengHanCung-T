"""Deterministic, page-level PDF extraction. No LLM is used in this module."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from app.text_sanitizer import sanitize_text


class PdfValidationError(ValueError):
    """Raised when a source cannot be opened safely for extraction."""


@dataclass(frozen=True)
class RawSpan:
    index: int
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    font: str
    size: float
    flags: int
    color: int


@dataclass(frozen=True)
class RawBlock:
    index: int
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    is_header_footer_candidate: bool


@dataclass(frozen=True)
class RawTable:
    index: int
    x0: float
    y0: float
    x1: float
    y1: float
    rows: list[list[str | None]]


@dataclass(frozen=True)
class RawImage:
    index: int
    xref: int | None
    x0: float
    y0: float
    x1: float
    y1: float
    width: int
    height: int
    extension: str
    sha256: str
    data: bytes


@dataclass(frozen=True)
class RawPage:
    pdf_page_number: int
    printed_page_number: str | None
    width: float
    height: float
    rotation: int
    text: str
    blocks: list[RawBlock]
    spans: list[RawSpan]
    tables: list[RawTable]
    images: list[RawImage]
    image_count: int
    korean_character_count: int
    vietnamese_character_count: int
    needs_ocr: bool
    sanitized_nul_count: int = 0


@dataclass(frozen=True)
class RawDocument:
    filename: str
    file_size: int
    sha256: str
    metadata: dict[str, Any]
    page_count: int
    pages: list[RawPage]


_KOREAN = re.compile(r"[\uac00-\ud7a3]")
_VIETNAMESE = re.compile(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.I)
_PRINTED_PAGE = re.compile(r"^\s*(?:-\s*)?(\d{1,3})(?:\s*-)?\s*$")
_IMAGE_EXTENSION = re.compile(r"^[a-z0-9]{1,8}$", re.I)


def _open_pdf(path: Path):
    try:
        import fitz
    except ImportError as error:  # pragma: no cover - dependency/setup failure
        raise RuntimeError("PyMuPDF is required. Install apps/api/requirements.txt first.") from error
    try:
        document = fitz.open(path)
    except Exception as error:
        raise PdfValidationError("PDF cannot be opened or is corrupt") from error
    if document.needs_pass:
        document.close()
        raise PdfValidationError("Password-protected PDFs are not supported for unattended extraction")
    if document.page_count < 1:
        document.close()
        raise PdfValidationError("PDF has no pages")
    return document


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_pdf(path: Path) -> int:
    """Validate a PDF and return its actual page count before registration."""
    document = _open_pdf(path)
    try:
        return document.page_count
    finally:
        document.close()


def _printed_page(blocks: list[RawBlock], height: float) -> str | None:
    for block in reversed(blocks):
        match = _PRINTED_PAGE.match(block.text)
        if match and block.y0 >= height * 0.82:
            return match.group(1)
    return None


def extract_document(path: Path, pages: range | None = None) -> RawDocument:
    """Extract text, layout, tables, and image assets with source provenance."""
    document = _open_pdf(path)
    try:
        page_numbers = pages or range(1, document.page_count + 1)
        extracted: list[RawPage] = []
        for page_number in page_numbers:
            if page_number < 1 or page_number > document.page_count:
                continue
            page = document.load_page(page_number - 1)
            page_height = float(page.rect.height)
            blocks: list[RawBlock] = []
            spans: list[RawSpan] = []
            images: list[RawImage] = []
            sanitized_nul_count = 0
            for index, block in enumerate(page.get_text("blocks", sort=True)):
                x0, y0, x1, y1, text, *_ = block
                sanitized_nul_count += text.count("\x00")
                normalized = sanitize_text(
                    "\n".join(line.rstrip() for line in text.splitlines()).strip()
                )
                blocks.append(RawBlock(
                    index=index,
                    text=normalized,
                    x0=float(x0), y0=float(y0), x1=float(x1), y1=float(y1),
                    is_header_footer_candidate=y0 <= page_height * 0.10 or y1 >= page_height * 0.90,
                ))
            text_dict = page.get_text("dict", sort=True)
            for block in text_dict["blocks"]:
                if block["type"] == 1:
                    image_data = block.get("image", b"")
                    extension = str(block.get("ext", "bin")).lower()
                    if not _IMAGE_EXTENSION.fullmatch(extension):
                        extension = "bin"
                    x0, y0, x1, y1 = map(float, block["bbox"])
                    images.append(RawImage(
                        index=len(images),
                        xref=block.get("xref") or None,
                        x0=x0, y0=y0, x1=x1, y1=y1,
                        width=int(block["width"]),
                        height=int(block["height"]),
                        extension=extension,
                        sha256=hashlib.sha256(image_data).hexdigest(),
                        data=image_data,
                    ))
                    continue
                if block["type"] != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        span_text = span["text"]
                        sanitized_nul_count += span_text.count("\x00")
                        span_text = sanitize_text(span_text)
                        x0, y0, x1, y1 = map(float, span["bbox"])
                        spans.append(RawSpan(
                            index=len(spans),
                            text=span_text,
                            x0=x0, y0=y0, x1=x1, y1=y1,
                            font=str(span["font"]),
                            size=float(span["size"]),
                            flags=int(span["flags"]),
                            color=int(span["color"]),
                        ))
            raw_text = "\n".join(item.text for item in blocks if item.text)
            korean_count = len(_KOREAN.findall(raw_text))
            vietnamese_count = len(_VIETNAMESE.findall(raw_text))
            tables: list[RawTable] = []
            for index, table in enumerate(page.find_tables().tables):
                rows = []
                for row in table.extract():
                    sanitized_row = []
                    for cell in row:
                        if cell is not None:
                            sanitized_nul_count += cell.count("\x00")
                            cell = sanitize_text(cell)
                        sanitized_row.append(cell)
                    rows.append(sanitized_row)
                tables.append(RawTable(
                    index=index,
                    x0=float(table.bbox[0]), y0=float(table.bbox[1]),
                    x1=float(table.bbox[2]), y1=float(table.bbox[3]),
                    rows=rows,
                ))
            image_count = len(images)
            needs_ocr = len(raw_text.strip()) < 24 and image_count > 0
            extracted.append(RawPage(
                pdf_page_number=page_number,
                printed_page_number=_printed_page(blocks, page_height),
                width=float(page.rect.width),
                height=page_height,
                rotation=int(page.rotation),
                text=raw_text,
                blocks=blocks,
                spans=spans,
                tables=tables,
                images=images,
                image_count=image_count,
                korean_character_count=korean_count,
                vietnamese_character_count=vietnamese_count,
                needs_ocr=needs_ocr,
                sanitized_nul_count=sanitized_nul_count,
            ))
        return RawDocument(
            filename=path.name,
            file_size=path.stat().st_size,
            sha256=_sha256(path),
            metadata={key: value for key, value in document.metadata.items() if value is not None},
            page_count=document.page_count,
            pages=extracted,
        )
    finally:
        document.close()


def extract_pages(path: Path, pages: range | None = None) -> list[RawPage]:
    """Extract raw pages without flattening page provenance."""
    return extract_document(path, pages).pages


def write_extraction_json(
    extraction: RawDocument,
    output_path: Path,
    assets_dir: Path | None = None,
) -> Path:
    """Write page data to JSON and extracted images to a neighboring asset folder."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image_dir = assets_dir or output_path.with_name(f"{output_path.stem}_assets")
    image_dir.mkdir(parents=True, exist_ok=True)
    output_base = output_path.parent.resolve()
    page_data: list[dict[str, Any]] = []
    for page in extraction.pages:
        page_record = {
            "pdf_page_number": page.pdf_page_number,
            "printed_page_number": page.printed_page_number,
            "width": page.width,
            "height": page.height,
            "rotation": page.rotation,
            "text": page.text,
            "blocks": [
                {
                    "index": block.index,
                    "text": block.text,
                    "bbox": [block.x0, block.y0, block.x1, block.y1],
                    "is_header_footer_candidate": block.is_header_footer_candidate,
                }
                for block in page.blocks
            ],
            "spans": [
                {
                    "index": span.index,
                    "text": span.text,
                    "bbox": [span.x0, span.y0, span.x1, span.y1],
                    "font": span.font,
                    "size": span.size,
                    "flags": span.flags,
                    "color": span.color,
                }
                for span in page.spans
            ],
            "tables": [
                {
                    "index": table.index,
                    "bbox": [table.x0, table.y0, table.x1, table.y1],
                    "rows": table.rows,
                }
                for table in page.tables
            ],
            "images": [],
            "image_count": page.image_count,
            "korean_character_count": page.korean_character_count,
            "vietnamese_character_count": page.vietnamese_character_count,
            "needs_ocr": page.needs_ocr,
        }
        for image in page.images:
            filename = f"page-{page.pdf_page_number:04d}-image-{image.index:03d}-{image.sha256[:12]}.{image.extension}"
            image_path = image_dir / filename
            image_path.write_bytes(image.data)
            try:
                asset_path = image_path.resolve().relative_to(output_base).as_posix()
            except ValueError:
                asset_path = str(image_path.resolve())
            page_record["images"].append({
                "index": image.index,
                "xref": image.xref,
                "bbox": [image.x0, image.y0, image.x1, image.y1],
                "width": image.width,
                "height": image.height,
                "extension": image.extension,
                "sha256": image.sha256,
                "asset_path": asset_path,
            })
        page_data.append(page_record)
    output = {
        "schema_version": 1,
        "source": {
            "filename": extraction.filename,
            "file_size": extraction.file_size,
            "sha256": extraction.sha256,
            "page_count": extraction.page_count,
            "metadata": extraction.metadata,
        },
        "pages": page_data,
    }
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
