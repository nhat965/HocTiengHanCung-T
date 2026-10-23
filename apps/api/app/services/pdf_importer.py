import hashlib
from pathlib import Path


class ImportPathError(ValueError):
    pass


def resolve_pdf_path(source_path: str, allowed_root: Path) -> Path:
    candidate = Path(source_path).expanduser().resolve()
    root = allowed_root.resolve()
    if root not in candidate.parents and candidate != root:
        raise ImportPathError("PDF path must be inside PDF_IMPORT_ROOT")
    if candidate.suffix.lower() != ".pdf":
        raise ImportPathError("Only .pdf files can be imported")
    if not candidate.is_file():
        raise ImportPathError("PDF file does not exist")
    return candidate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def page_count(path: Path) -> int | None:
    """Return page count when PyMuPDF is available; callers keep import valid if it is not."""
    try:
        import fitz  # PyMuPDF

        with fitz.open(path) as document:
            return document.page_count
    except Exception:
        return None
