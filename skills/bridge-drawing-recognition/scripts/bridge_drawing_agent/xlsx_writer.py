"""Dependency-free XLSX writer for machine-generated review workbooks."""

from __future__ import annotations

import datetime as dt
import math
import zipfile
from pathlib import Path
from typing import Any, Iterable
from xml.sax.saxutils import escape

from .utils import ensure_dir
from .workbook import column_name

INVALID_SHEET_CHARS = set(r"[]:*?/\\")


def safe_sheet_name(name: str, used: set[str] | None = None) -> str:
    used = used or set()
    cleaned = "".join("_" if char in INVALID_SHEET_CHARS else char for char in name).strip() or "Sheet"
    cleaned = cleaned[:31]
    candidate = cleaned
    index = 2
    while candidate in used:
        suffix = f"_{index}"
        candidate = cleaned[: 31 - len(suffix)] + suffix
        index += 1
    used.add(candidate)
    return candidate


def _cell_xml(row: int, col: int, value: Any, style_id: int = 0) -> str:
    ref = f"{column_name(col)}{row}"
    style = f' s="{style_id}"' if style_id else ""
    if value is None:
        return ""
    if isinstance(value, bool):
        return f'<c r="{ref}"{style} t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            value = str(value)
        else:
            return f'<c r="{ref}"{style}><v>{value}</v></c>'
    if isinstance(value, (dt.date, dt.datetime)):
        value = value.isoformat()
    text = escape(str(value))
    return f'<c r="{ref}"{style} t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _column_widths(rows: Iterable[Iterable[Any]], max_cols: int) -> list[int]:
    widths = [10] * max_cols
    for row in rows:
        for index, value in enumerate(row):
            if index >= max_cols or value is None:
                continue
            text = str(value)
            display_width = sum(2 if ord(char) > 127 else 1 for char in text)
            widths[index] = max(widths[index], min(40, display_width + 2))
    return widths

def _sheet_xml(rows: list[list[Any]], freeze_header: bool) -> str:
    max_cols = max((len(row) for row in rows), default=1)
    max_rows = max(len(rows), 1)
    widths = _column_widths(rows, max_cols)
    cols_xml = "".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(widths, start=1)
    )
    rows_xml_parts: list[str] = []
    for row_index, row in enumerate(rows, start=1):
        cells = "".join(
            _cell_xml(row_index, col_index, value, 1 if freeze_header and row_index == 1 else 0)
            for col_index, value in enumerate(row, start=1)
        )
        rows_xml_parts.append(f'<row r="{row_index}">{cells}</row>')
    pane = (
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        if freeze_header and rows
        else ""
    )
    autofilter = (
        f'<autoFilter ref="A1:{column_name(max_cols)}{max_rows}"/>'
        if freeze_header and rows
        else ""
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="A1:{column_name(max_cols)}{max_rows}"/>'
        '<sheetViews><sheetView workbookViewId="0">'
        f'{pane}</sheetView></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f'<cols>{cols_xml}</cols><sheetData>{"".join(rows_xml_parts)}</sheetData>'
        f'{autofilter}</worksheet>'
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>'
    )

def write_xlsx(
    path: str | Path,
    sheets: dict[str, list[list[Any]]],
    *,
    freeze_header: bool = True,
) -> Path:
    output = Path(path)
    ensure_dir(output.parent)
    used_names: set[str] = set()
    normalized = [
        (safe_sheet_name(name, used_names), rows)
        for name, rows in sheets.items()
    ]
    if not normalized:
        normalized = [("Sheet", [[]])]

    content_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, len(normalized) + 1)
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f'{content_overrides}</Types>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    workbook_sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, (name, _) in enumerate(normalized, start=1)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{workbook_sheets}</sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
            for index in range(1, len(normalized) + 1)
        )
        + f'<Relationship Id="rId{len(normalized) + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/></Relationships>'
    )

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", _styles_xml())
        for index, (_, rows) in enumerate(normalized, start=1):
            archive.writestr(
                f"xl/worksheets/sheet{index}.xml",
                _sheet_xml([list(row) for row in rows], freeze_header),
            )
    return output
