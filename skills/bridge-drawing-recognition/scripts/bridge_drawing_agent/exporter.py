"""Export normalized bridge records to an auditable Excel workbook."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import read_json
from .workbook import column_name
from .xlsx_writer import write_xlsx


def _code_sort_key(code: str) -> tuple[int, str]:
    index = 0
    for char in code.upper():
        index = index * 26 + ord(char) - 64
    return index, code


def build_export_sheets(payload: dict[str, Any]) -> dict[str, list[list[Any]]]:
    headers: dict[str, str] = payload.get("headers", {})
    records: list[dict[str, Any]] = payload.get("records", [])
    scalar_codes = sorted(
        (code for code in headers if code != "A" and _code_sort_key(code) <= (27, "AA")),
        key=_code_sort_key,
    )
    result_rows: list[list[Any]] = [[headers.get(code) or code for code in scalar_codes]]
    evidence_rows: list[list[Any]] = [
        ["record_id", "field_code", "field_label", "value", "source_cell", "source_row", "source_column"]
    ]
    pier_rows: list[list[Any]] = [[
        "record_id", "source_cell", "source_row", "column", "value", "required_in_v1"
    ]]
    issue_rows: list[list[Any]] = [["record_id_or_scope", "issue"]]
    for issue in payload.get("issues", []):
        issue_rows.append(["", issue])

    for record in records:
        record_id = record.get("record_id", "")
        result_rows.append(
            [
                record.get("scalar", {}).get(code, {}).get("value")
                for code in scalar_codes
            ]
        )
        for code in scalar_codes:
            source = record.get("scalar", {}).get(code)
            if not source:
                continue
            evidence_rows.append([
                record_id,
                code,
                headers.get(code, ""),
                source.get("value"),
                source.get("cell", ""),
                source.get("row", ""),
                source.get("column", ""),
            ])
        for item in record.get("span_entries", []):
            evidence_rows.append([
                record_id,
                "F",
                headers.get("F", "跨径"),
                item.get("value"),
                item.get("cell", ""),
                item.get("row", ""),
                item.get("column", ""),
            ])
        for item in record.get("pier_height_cells", []):
            pier_rows.append([
                record_id,
                item.get("cell", ""),
                item.get("row", ""),
                item.get("column", ""),
                item.get("value"),
                False,
            ])

    metadata_rows = [
        ["key", "value"],
        ["source_file", payload.get("source_file", "")],
        ["generated_at", payload.get("generated_at", "")],
        ["ignored_columns", ", ".join(payload.get("ignored_columns", []))],
        ["record_count", payload.get("summary", {}).get("record_count", len(records))],
    ]
    return {
        "筛选结果": result_rows,
        "字段证据": evidence_rows,
        "可选墩高": pier_rows,
        "问题": issue_rows,
        "元数据": metadata_rows,
    }


def export_normalized_workbook(input_path: str | Path, output_path: str | Path) -> Path:
    payload = read_json(Path(input_path))
    return write_xlsx(output_path, build_export_sheets(payload))
