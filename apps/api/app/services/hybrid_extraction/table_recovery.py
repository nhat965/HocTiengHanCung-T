from __future__ import annotations

from copy import deepcopy
from html.parser import HTMLParser
from statistics import median
from typing import Any, Mapping

from app.services.hybrid_extraction.layout_alignment import (
    _raw_span_refs,
    intersection_area,
    scale_bbox,
)
from app.services.hybrid_extraction.marker_adapter import html_to_text
from app.services.hybrid_extraction.types import (
    BBox,
    MarkerBlock,
    MarkerDocument,
    RecoveredCell,
    RecoveredTable,
    SourceSpanRef,
    TableRecoveryResult,
)


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str | None]] = []
        self._row: list[str | None] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.lower() == "tr":
            self._row = []
        elif tag.lower() in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"td", "th"} and self._row is not None and self._cell is not None:
            value = " ".join("".join(self._cell).split()) or None
            self._row.append(value)
            self._cell = None
        elif lowered == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def parse_marker_table_html(html: str | None) -> list[list[str | None]]:
    parser = _TableParser()
    if html:
        parser.feed(html)
        parser.close()
    return parser.rows


def _center(bbox: BBox) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _table_bbox(block: MarkerBlock, raw_page: Mapping[str, Any]) -> BBox:
    return scale_bbox(
        block.bbox,
        from_width=block.page_width,
        from_height=block.page_height,
        to_width=float(raw_page.get("width") or block.page_width),
        to_height=float(raw_page.get("height") or block.page_height),
    )


def _row_groups(refs: list[SourceSpanRef], expected: int) -> list[list[SourceSpanRef]]:
    if not refs:
        return []
    ordered = sorted(refs, key=lambda item: (_center(item.bbox)[1], _center(item.bbox)[0], item.span_index))
    heights = [max(1.0, item.bbox[3] - item.bbox[1]) for item in ordered]
    threshold = max(4.0, median(heights) * 1.65)
    groups: list[list[SourceSpanRef]] = []
    for ref in ordered:
        if not groups or _center(ref.bbox)[1] - _center(groups[-1][0].bbox)[1] > threshold:
            groups.append([ref])
        else:
            groups[-1].append(ref)
    while expected and len(groups) > expected:
        gaps = [
            (_center(groups[index + 1][0].bbox)[1] - _center(groups[index][-1].bbox)[1], index)
            for index in range(len(groups) - 1)
        ]
        _, index = min(gaps)
        groups[index].extend(groups.pop(index + 1))
    return groups


def _column_centers(refs: list[SourceSpanRef], expected: int) -> list[float]:
    if expected <= 0:
        return []
    values = sorted(_center(ref.bbox)[0] for ref in refs)
    if not values:
        return [float(index) for index in range(expected)]
    centers = [values[min(len(values) - 1, round(index * (len(values) - 1) / max(1, expected - 1)))] for index in range(expected)]
    for _ in range(12):
        buckets = [[] for _ in centers]
        for value in values:
            bucket = min(range(len(centers)), key=lambda index: (abs(value - centers[index]), index))
            buckets[bucket].append(value)
        changed = False
        for index, bucket in enumerate(buckets):
            if bucket:
                new_value = sum(bucket) / len(bucket)
                changed = changed or abs(new_value - centers[index]) > 0.01
                centers[index] = new_value
        if not changed:
            break
    return centers


def _raw_table_for_marker(
    marker_block: MarkerBlock,
    raw_page: Mapping[str, Any],
) -> tuple[int, Mapping[str, Any]] | None:
    target = _table_bbox(marker_block, raw_page)
    candidates: list[tuple[float, int, Mapping[str, Any]]] = []
    for table in raw_page.get("tables", []) or []:
        bbox = tuple(float(value) for value in table.get("bbox", (0, 0, 0, 0)))
        candidates.append((intersection_area(target, bbox), int(table.get("index", 0)), table))
    if not candidates:
        return None
    area, index, table = max(candidates, key=lambda item: (item[0], -item[1]))
    return (index, table) if area > 0 else None


def _raw_rows_from_spans(
    refs: list[SourceSpanRef],
    marker_rows: list[list[str | None]],
    table_bbox: BBox,
) -> list[list[tuple[str, tuple[SourceSpanRef, ...]]]]:
    expected_rows = len(marker_rows)
    expected_columns = max((len(row) for row in marker_rows), default=0)
    groups = _row_groups(refs, expected_rows)
    centers = _column_centers(refs, expected_columns)
    result: list[list[tuple[str, tuple[SourceSpanRef, ...]]]] = [
        [("", ()) for _ in range(expected_columns)] for _ in range(expected_rows)
    ]
    if not groups or not centers:
        return result
    for group_index, group in enumerate(groups):
        if group_index >= expected_rows:
            break
        by_column: list[list[SourceSpanRef]] = [[] for _ in centers]
        for ref in group:
            x = _center(ref.bbox)[0]
            column = min(range(len(centers)), key=lambda index: (abs(x - centers[index]), index))
            by_column[column].append(ref)
        for column, column_refs in enumerate(by_column):
            column_refs.sort(key=lambda item: (_center(item.bbox)[1], _center(item.bbox)[0], item.span_index))
            text = " ".join(item.text.strip() for item in column_refs if item.text.strip()).strip()
            result[group_index][column] = (text, tuple(column_refs))
    return result


def recover_marker_tables(
    marker: MarkerDocument,
    raw_document: Mapping[str, Any],
) -> TableRecoveryResult:
    raw_pages = {int(page.get("pdf_page_number")): page for page in raw_document.get("pages", [])}
    recovered: list[RecoveredTable] = []
    for page in marker.pages:
        raw_page = raw_pages.get(page.pdf_page_number)
        if raw_page is None:
            continue
        for marker_block in page.blocks:
            if not marker_block.is_table:
                continue
            marker_rows = parse_marker_table_html(marker_block.html)
            if not marker_rows:
                continue
            raw_match = _raw_table_for_marker(marker_block, raw_page)
            table_index = raw_match[0] if raw_match else len(recovered)
            target = _table_bbox(marker_block, raw_page)
            refs = [ref for ref in _raw_span_refs(raw_page) if intersection_area(target, ref.bbox) > 0]
            span_grid = _raw_rows_from_spans(refs, marker_rows, target)
            cells: list[RecoveredCell] = []
            merged_rows: list[tuple[str | None, ...]] = []
            raw_rows = list(raw_match[1].get("rows", []) or []) if raw_match else []
            for row_index, marker_row in enumerate(marker_rows):
                merged_row: list[str | None] = []
                for column_index, marker_value in enumerate(marker_row):
                    raw_value = None
                    if row_index < len(raw_rows) and column_index < len(raw_rows[row_index]):
                        value = raw_rows[row_index][column_index]
                        raw_value = str(value).strip() if value is not None and str(value).strip() else None
                    span_text, source_spans = (
                        span_grid[row_index][column_index]
                        if row_index < len(span_grid) and column_index < len(span_grid[row_index])
                        else ("", ())
                    )
                    observed = raw_value or span_text or None
                    marker_text = " ".join(str(marker_value or "").split()) or None
                    if raw_value:
                        status = "verified" if not marker_text or marker_text.casefold() == raw_value.casefold() else "needs_review"
                        value = raw_value
                    elif marker_text and span_text:
                        status = "verified" if marker_text.casefold() == span_text.casefold() else "needs_review"
                        value = marker_text
                    elif span_text:
                        status = "recovered"
                        value = span_text
                    elif marker_text:
                        status = "needs_review"
                        value = marker_text
                    else:
                        status = "missing"
                        value = None
                    merged_row.append(value)
                    cells.append(RecoveredCell(
                        page_number=page.pdf_page_number,
                        table_index=table_index,
                        row_index=row_index,
                        column_index=column_index,
                        text=value,
                        source_spans=source_spans,
                        marker_text=marker_text,
                        status=status,
                    ))
                merged_rows.append(tuple(merged_row))
            table_status = "recovered" if any(cell.status == "recovered" for cell in cells) else (
                "needs_review" if any(cell.status in {"missing", "needs_review"} for cell in cells) else "verified"
            )
            recovered.append(RecoveredTable(
                page_number=page.pdf_page_number,
                table_index=table_index,
                rows=tuple(merged_rows),
                cells=tuple(cells),
                status=table_status,
            ))
    return TableRecoveryResult(tables=tuple(recovered))


def apply_table_recovery(
    raw_document: Mapping[str, Any],
    recovery: TableRecoveryResult,
) -> dict[str, Any]:
    """Overlay recovered evidence while preserving every existing raw value."""
    output = deepcopy(dict(raw_document))
    by_key = {(table.page_number, table.table_index): table for table in recovery.tables}
    for page in output.get("pages", []) or []:
        page_number = int(page.get("pdf_page_number"))
        for table in page.get("tables", []) or []:
            key = (page_number, int(table.get("index", 0)))
            recovered = by_key.get(key)
            if recovered is None:
                continue
            current_rows = list(table.get("rows", []) or [])
            merged: list[list[str | None]] = []
            for row_index, row in enumerate(recovered.rows):
                current = list(current_rows[row_index]) if row_index < len(current_rows) else []
                cells: list[str | None] = []
                for column_index, value in enumerate(row):
                    existing = current[column_index] if column_index < len(current) else None
                    cells.append(existing if existing not in (None, "") else value)
                if len(current) > len(cells):
                    cells.extend(current[len(cells):])
                merged.append(cells)
            if len(current_rows) > len(merged):
                merged.extend(current_rows[len(merged):])
            table["rows"] = merged
    return output

