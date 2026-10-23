"""Export a PDF's raw page extraction to JSON and image assets."""
from __future__ import annotations

import argparse
from pathlib import Path

from app.services.pdf_engine import extract_document, write_extraction_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Source PDF to extract")
    parser.add_argument("-o", "--output", required=True, type=Path, help="Destination JSON file")
    parser.add_argument("--assets-dir", type=Path, help="Optional directory for extracted image files")
    args = parser.parse_args()

    extraction = extract_document(args.pdf)
    output_path = write_extraction_json(extraction, args.output, args.assets_dir)
    print(f"Extracted {len(extraction.pages)} of {extraction.page_count} pages to {output_path}")


if __name__ == "__main__":
    main()
