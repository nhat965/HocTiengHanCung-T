"""Opt-in hybrid extraction helpers.

The current PyMuPDF extraction remains the canonical source.  This package
adds a deterministic Marker sidecar that can be aligned, reviewed, and fed to
the existing knowledge pipeline without changing persistence semantics.
"""

from app.services.hybrid_extraction.pipeline import (
    HybridExtractionResult,
    extract_hybrid,
)

__all__ = ["HybridExtractionResult", "extract_hybrid"]
