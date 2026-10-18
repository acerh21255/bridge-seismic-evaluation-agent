"""Minimal, dependency-free XLSX reader and bridge-record normalizer.

The project input is a small workbook with merged cells and one bridge spanning
several physical rows.  This module deliberately does not write into the source
workbook and ignores column A because it has no business meaning.
"""

from __future__ import annotations

import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator
import xml.etree.ElementTree as ET

from .utils import (
    atomic_write_json,
    first_nonempty,
    normalize_text,
    parse_number,
    stable_digest,
    utc_now_iso,
)

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CELL_RE = re.compile(r"^([A-Z]+)(\d+)$")

def column_name(index: int) -> str:
    if index < 1:
        raise ValueError("Column index must be >= 1")
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def column_index(name: str) -> int:
    result = 0
    for char in name.upper():
        if not ("A" <= char <= "Z"):
            raise ValueError(f"Invalid column name: {name}")
        result = result * 26 + (ord(char) - 64)
    return result


def cell_to_row_col(ref: str) -> tuple[int, int]:
    match = CELL_RE.fullmatch(ref.upper())
    if not match:
        raise ValueError(f"Invalid cell reference: {ref}")
    return int(match.group(2)), column_index(match.group(1))


def row_col_to_cell(row: int, col: int) -> str:
    return f"{column_name(col)}{row}"


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _element_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext())


@dataclass(frozen=True)
class MergedRange:
    min_row: int
    min_col: int
    max_row: int
    max_col: int
    ref: str

    def contains(self, row: int, col: int) -> bool:
        return self.min_row <= row <= self.max_row and self.min_col <= col <= self.max_col

    @classmethod
    def from_ref(cls, ref: str) -> "MergedRange":
        start, end = ref.split(":", 1)
        min_row, min_col = cell_to_row_col(start)
        max_row, max_col = cell_to_row_col(end)
        return cls(min_row, min_col, max_row, max_col, ref)


@dataclass
class Sheet:
    name: str
    cells: dict[tuple[int, int], Any]
    formulas: dict[tuple[int, int], str] = field(default_factory=dict)
    merges: list[MergedRange] = field(default_factory=list)
    dimension: str = ""
    max_row: int = 0
    max_col: int = 0

    def value(self, row: int, col: int) -> Any:
        return self.cells.get((row, col))

    def expanded_value(self, row: int, col: int) -> Any:
        for merged in self.merges:
            if merged.contains(row, col):
                return self.cells.get((merged.min_row, merged.min_col))
        return self.cells.get((row, col))

    def row_values(self, row: int, max_col: int | None = None) -> dict[int, Any]:
        limit = max_col or self.max_col
        return {col: self.expanded_value(row, col) for col in range(1, limit + 1)}

    def iter_rows(self, min_row: int = 1, max_row: int | None = None) -> Iterator[tuple[int, dict[int, Any]]]:
        for row in range(min_row, (max_row or self.max_row) + 1):
            yield row, self.row_values(row)

    def headers(self) -> dict[int, str]:
        return {col: normalize_text(self.value(1, col)) for col in range(1, self.max_col + 1)}


class WorkbookReader:
    """Read basic XLSX structures using only the Python standard library."""

    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        self._zip = zipfile.ZipFile(self.path)
        self.shared_strings = self._read_shared_strings()
        self._sheet_paths = self._read_sheet_paths()
        self._sheet_cache: dict[str, Sheet] = {}

    def close(self) -> None:
        self._zip.close()

    def __enter__(self) -> "WorkbookReader":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    @property
    def sheet_names(self) -> list[str]:
        return list(self._sheet_paths)

    def _read_shared_strings(self) -> list[str]:
        if "xl/sharedStrings.xml" not in self._zip.namelist():
            return []
        root = ET.fromstring(self._zip.read("xl/sharedStrings.xml"))
        values: list[str] = []
        for item in root:
            if local_name(item.tag) != "si":
                continue
            values.append("".join(node.text or "" for node in item.iter() if local_name(node.tag) == "t"))
        return values

    def _read_sheet_paths(self) -> dict[str, str]:
        workbook = ET.fromstring(self._zip.read("xl/workbook.xml"))
        rels = ET.fromstring(self._zip.read("xl/_rels/workbook.xml.rels"))
        rel_targets: dict[str, str] = {}
        for relation in rels:
            if local_name(relation.tag) != "Relationship":
                continue
            rel_id = relation.attrib.get("Id")
            target = relation.attrib.get("Target")
            if rel_id and target:
                rel_targets[rel_id] = target

        paths: dict[str, str] = {}
        for sheet in workbook.iter():
            if local_name(sheet.tag) != "sheet":
                continue
            name = sheet.attrib.get("name", "")
            rel_id = sheet.attrib.get(f"{{{REL_NS}}}id", "")
            target = rel_targets.get(rel_id)
            if not target:
                continue
            if target.startswith("/"):
                path = target.lstrip("/")
            else:
                path = posixpath.normpath(posixpath.join("xl", target))
            paths[name] = path
        return paths

    def sheet(self, name: str | None = None) -> Sheet:
        selected = name or (self.sheet_names[0] if self.sheet_names else "")
        if not selected:
            raise ValueError("Workbook contains no sheets")
        if selected in self._sheet_cache:
            return self._sheet_cache[selected]
        path = self._sheet_paths.get(selected)
        if not path:
            raise KeyError(f"Unknown sheet: {selected}")

        root = ET.fromstring(self._zip.read(path))
        cells: dict[tuple[int, int], Any] = {}
        formulas: dict[tuple[int, int], str] = {}
        max_row = 0
        max_col = 0
        for cell in root.iter():
            if local_name(cell.tag) != "c":
                continue
            ref = cell.attrib.get("r")
            if not ref:
                continue
            row, col = cell_to_row_col(ref)
            cell_type = cell.attrib.get("t", "")
            value_node = next((node for node in cell if local_name(node.tag) == "v"), None)
            formula_node = next((node for node in cell if local_name(node.tag) == "f"), None)
            inline = next((node for node in cell if local_name(node.tag) == "is"), None)
            value: Any = None
            if cell_type == "s" and value_node is not None and value_node.text is not None:
                try:
                    value = self.shared_strings[int(value_node.text)]
                except (ValueError, IndexError):
                    value = value_node.text
            elif cell_type == "inlineStr" and inline is not None:
                value = _element_text(inline)
            elif cell_type == "b" and value_node is not None:
                value = value_node.text == "1"
            elif cell_type in {"str", "e"} and value_node is not None:
                value = value_node.text
            elif value_node is not None and value_node.text is not None:
                number = parse_number(value_node.text)
                value = number if number is not None else value_node.text
            if formula_node is not None:
                formulas[(row, col)] = formula_node.text or ""
            if value is not None and normalize_text(value) != "":
                cells[(row, col)] = value
                max_row = max(max_row, row)
                max_col = max(max_col, col)

        merges: list[MergedRange] = []
        for node in root.iter():
            if local_name(node.tag) != "mergeCell":
                continue
            ref = node.attrib.get("ref")
            if ref:
                merges.append(MergedRange.from_ref(ref))
        dimension_node = next((node for node in root.iter() if local_name(node.tag) == "dimension"), None)
        sheet = Sheet(
            name=selected,
            cells=cells,
            formulas=formulas,
            merges=merges,
            dimension=dimension_node.attrib.get("ref", "") if dimension_node is not None else "",
            max_row=max_row,
            max_col=max_col,
        )
        self._sheet_cache[selected] = sheet
        return sheet


def _json_value(value: Any) -> Any:
    return value


def _source_ref(sheet: Sheet, row: int, col: int, value: Any) -> dict[str, Any]:
    return {
        "cell": row_col_to_cell(row, col),
        "row": row,
        "column": column_name(col),
        "value": _json_value(value),
    }


def normalize_sheet(sheet: Sheet) -> dict[str, Any]:
    """Normalize merged, multi-row bridge records from the G8511 workbook."""
    if sheet.max_row < 1:
        return {"sheet": sheet.name, "headers": {}, "records": [], "issues": ["工作表为空"]}

    headers = sheet.headers()
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for row in range(2, sheet.max_row + 1):
        values = sheet.row_values(row, sheet.max_col)
        nonempty = {
            col: value
            for col, value in values.items()
            if value is not None and normalize_text(value) != ""
        }
        if not nonempty:
            continue

        series_key = normalize_text(sheet.expanded_value(row, 2))
        if current is None or (series_key and series_key != current["series_key"]):
            current = {
                "record_id": f"g8511-{series_key or row}",
                "series_key": series_key or f"row-{row}",
                "source_rows": [],
                "scalar": {},
                "span_entries": [],
                "pier_height_cells": [],
                "merged_value_refs": [],
            }
            records.append(current)

        current["source_rows"].append(row)
        for col in range(1, sheet.max_col + 1):
            value = sheet.expanded_value(row, col)
            if value is None or normalize_text(value) == "":
                continue
            code = column_name(col)
            if col == 1:
                # Column A is explicitly ignored.
                continue
            if col == 6:  # Repeated span values in F.
                current["span_entries"].append(_source_ref(sheet, row, col, value))
            if 2 <= col <= 27 and code not in current["scalar"]:
                current["scalar"][code] = _source_ref(sheet, row, col, value)
            if col >= 28:
                number = parse_number(value)
                if number is not None:
                    current["pier_height_cells"].append(
                        {
                            "cell": row_col_to_cell(row, col),
                            "row": row,
                            "column": code,
                            "value": number,
                        }
                    )

    issue_list: list[str] = []
    for record in records:
        if not record["scalar"].get("B"):
            issue_list.append(f"{record['record_id']}: 缺少序号 B")
        if not record["scalar"].get("D"):
            issue_list.append(f"{record['record_id']}: 缺少设计桩号 D")
        if not record["scalar"].get("G"):
            issue_list.append(f"{record['record_id']}: 缺少桥跨组合 G")

    return {
        "source_file": str(sheet.name),
        "generated_at": utc_now_iso(),
        "ignored_columns": ["A"],
        "headers": {column_name(col): headers.get(col, "") for col in range(1, sheet.max_col + 1)},
        "records": records,
        "issues": issue_list,
        "summary": {
            "record_count": len(records),
            "row_count": sheet.max_row,
            "max_column": column_name(sheet.max_col),
            "merge_count": len(sheet.merges),
        },
    }


def inspect_workbook(path: Path, sheet_name: str | None = None) -> dict[str, Any]:
    with WorkbookReader(path) as reader:
        sheet = reader.sheet(sheet_name)
        normalized = normalize_sheet(sheet)
        coverage: dict[str, int] = {}
        for col in range(2, sheet.max_col + 1):
            code = column_name(col)
            coverage[code] = sum(
                1
                for record in normalized["records"]
                if record["scalar"].get(code)
                or any(entry["column"] == code for entry in record["span_entries"])
                or any(entry["column"] == code for entry in record["pier_height_cells"])
            )
        return {
            **normalized,
            "sheets": reader.sheet_names,
            "sheet_names": reader.sheet_names,
            "coverage": coverage,
        }


def normalize_workbook(path: Path, sheet_name: str | None = None) -> dict[str, Any]:
    with WorkbookReader(path) as reader:
        sheet = reader.sheet(sheet_name)
        result = normalize_sheet(sheet)
        result["source_file"] = str(Path(path).resolve())
        return result


def write_normalized_workbook(path: Path, output: Path, sheet_name: str | None = None) -> dict[str, Any]:
    result = normalize_workbook(path, sheet_name)
    atomic_write_json(output, result)
    return result
