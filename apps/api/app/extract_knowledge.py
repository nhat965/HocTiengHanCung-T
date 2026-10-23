"""Extract structured records from an existing raw JSON export."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import get_settings
from app.services.knowledge.pipeline import extract_knowledge, write_knowledge_json
from app.services.knowledge.quality import report_dict


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_json", type=Path, help="Private raw extraction JSON")
    parser.add_argument("-o", "--output", required=True, type=Path, help="Private structured JSON output")
    args = parser.parse_args()

    output = args.output.resolve()
    private_root = get_settings().resolved_private_storage_root
    if private_root not in output.parents:
        parser.error(f"output must be inside PRIVATE_STORAGE_ROOT ({private_root})")
    raw = json.loads(args.raw_json.read_text(encoding="utf-8"))
    bundle = extract_knowledge(raw)
    output_path = write_knowledge_json(bundle, output, raw.get("source", {}))
    pages = raw.get("pages", [])
    report_path = output_path.with_name(f"{output_path.stem}-quality.json")
    report_path.write_text(
        json.dumps(
            report_dict(bundle, len(pages), int(raw.get("source", {}).get("page_count") or len(pages))),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Structured records: {output_path}; quality report: {report_path}")


if __name__ == "__main__":
    main()
