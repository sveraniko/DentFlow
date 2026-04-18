from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

XML_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def read_xlsx_workbook(path: str | Path) -> dict[str, list[dict[str, str]]]:
    with ZipFile(path) as archive:
        shared_strings = _load_shared_strings(archive)
        sheet_targets = _sheet_targets(archive)
        output: dict[str, list[dict[str, str]]] = {}
        for name, target in sheet_targets:
            rows = _load_sheet_rows(archive, target, shared_strings)
            if not rows:
                output[name] = []
                continue
            headers = [str(cell).strip() for cell in rows[0]]
            data_rows: list[dict[str, str]] = []
            for row in rows[1:]:
                mapped: dict[str, str] = {}
                for idx, header in enumerate(headers):
                    if not header:
                        continue
                    value = row[idx] if idx < len(row) else ""
                    mapped[header] = value
                if any((str(v).strip() for v in mapped.values())):
                    data_rows.append(mapped)
            output[name] = data_rows
        return output


def _load_shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.itertext()) for node in root.findall("main:si", XML_NS)]


def _sheet_targets(archive: ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_map: dict[str, str] = {}
    for rel in rels.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rel_id and target:
            rel_map[rel_id] = target

    sheets: list[tuple[str, str]] = []
    for sheet in workbook.findall("main:sheets/main:sheet", XML_NS):
        name = sheet.attrib.get("name", "")
        rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = rel_map.get(rel_id or "")
        if not target:
            continue
        sheets.append((name, f"xl/{target}"))
    return sheets


def _load_sheet_rows(archive: ZipFile, target: str, shared_strings: list[str]) -> list[list[str]]:
    root = ET.fromstring(archive.read(target))
    rows: list[list[str]] = []
    for row_node in root.findall("main:sheetData/main:row", XML_NS):
        row_values: list[str] = []
        current_col = 1
        for cell in row_node.findall("main:c", XML_NS):
            ref = cell.attrib.get("r", "A1")
            col = _column_to_index(ref)
            while current_col < col:
                row_values.append("")
                current_col += 1
            row_values.append(_cell_value(cell, shared_strings))
            current_col += 1
        rows.append(row_values)
    return rows


def _column_to_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    acc = 0
    for ch in letters:
        acc = acc * 26 + (ord(ch.upper()) - ord("A") + 1)
    return max(acc, 1)


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    value_node = cell.find("main:v", XML_NS)
    if value_node is None or value_node.text is None:
        inline = cell.find("main:is/main:t", XML_NS)
        return inline.text if inline is not None and inline.text is not None else ""
    value = value_node.text
    if cell.attrib.get("t") == "s":
        idx = int(value)
        return shared_strings[idx] if 0 <= idx < len(shared_strings) else ""
    return value
