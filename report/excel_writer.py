# -*- coding: utf-8 -*-
"""
Генерация Excel-отчёта (openpyxl).

Файл каждый раз регенерируется из полной истории data/history.json,
поэтому changelog и данные прошлых сканов не теряются между запусками,
а форматирование остаётся консистентным.

Листы:
  1. Сводная            — тиры всех банков, сгруппированные по сегментам капитала
  2. <Банк>             — детализация по каждому банку (все тиры x все поля)
  3. Lifestyle          — экосистемные подписки
  4. Изменения          — changelog всех сканов (было/стало с датами)
  5. Метаданные         — дата запуска, статус источников
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from scanner.sources import (
    BANK_FIELDS,
    BANKS,
    LIFESTYLE_FIELDS,
    NOT_FOUND,
    SEGMENTS,
)

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
SEGMENT_FILL = PatternFill("solid", fgColor="D6E4F0")
OUR_FILL = PatternFill("solid", fgColor="E2EFDA")
NOT_FOUND_FONT = Font(color="999999", italic=True)
HEADER_FONT = Font(color="FFFFFF", bold=True)
WRAP = Alignment(wrap_text=True, vertical="top")
THIN_BORDER = Border(*[Side(style="thin", color="CCCCCC")] * 4)

LIFESTYLE_COLUMNS = dict(LIFESTYLE_FIELDS)
LIFESTYLE_EXTRA = {"bank_overlap": {"label": "Пересечения с банковскими привилегиями"}}


def write_report(history: dict, output_path: Path):
    wb = Workbook()
    wb.remove(wb.active)

    last_scan = history["scans"][-1] if history["scans"] else {"results": {}, "meta": {}, "date": ""}
    results = last_scan.get("results", {})

    _write_summary(wb, results, last_scan.get("date", ""))
    _write_bank_sheets(wb, results)
    _write_lifestyle(wb, results)
    _write_changelog(wb, history.get("changelog", []))
    _write_meta(wb, history)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)


# ---------- helpers ----------

def _style_header_row(ws, ncols, row=1):
    for col in range(1, ncols + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = WRAP
        cell.border = THIN_BORDER


def _set_widths(ws, widths):
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width


def _write_value_cell(ws, row, col, value):
    cell = ws.cell(row=row, column=col, value=value)
    cell.alignment = WRAP
    cell.border = THIN_BORDER
    if value == NOT_FOUND:
        cell.font = NOT_FOUND_FONT
    return cell


def _tier_entries(results, types):
    for bank in BANKS:
        if bank["type"] not in types:
            continue
        for tier in bank["tiers"]:
            entry = results.get(tier["tier_id"])
            if entry:
                yield bank, tier, entry


# ---------- листы ----------

def _write_summary(wb, results, scan_date):
    ws = wb.create_sheet("Сводная")
    headers = ["Сегмент капитала", "Банк", "Тир", "Дата скана", "Статус источника"] + [
        spec["label"] for spec in BANK_FIELDS.values()
    ] + ["Источник"]
    for col, header in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=header)
    _style_header_row(ws, len(headers))
    _set_widths(ws, [14, 16, 24, 12, 14] + [38] * len(BANK_FIELDS) + [40])
    ws.freeze_panes = "D2"

    row = 2
    for segment in SEGMENTS:
        segment_row_written = False
        for bank, tier, entry in _tier_entries(results, {"our", "bank"}):
            if tier["segment"] != segment:
                continue
            if not segment_row_written:
                cell = ws.cell(row=row, column=1, value=segment)
                for col in range(1, len(headers) + 1):
                    ws.cell(row=row, column=col).fill = SEGMENT_FILL
                cell.font = Font(bold=True)
                row += 1
                segment_row_written = True
            values = [
                "", bank["name"], tier["tier_name"],
                entry.get("scan_date", scan_date)[:10],
                entry.get("status", ""),
            ] + [
                entry["fields"].get(field_id, NOT_FOUND) for field_id in BANK_FIELDS
            ] + [entry.get("source_url", "")]
            for col, value in enumerate(values, start=1):
                cell = _write_value_cell(ws, row, col, value)
                if bank["type"] == "our" and col in (2, 3):
                    cell.fill = OUR_FILL
            row += 1


def _write_bank_sheets(wb, results):
    for bank in BANKS:
        if bank["type"] not in {"our", "bank"}:
            continue
        ws = wb.create_sheet(bank["name"][:31])
        headers = ["Поле"] + [t["tier_name"] for t in bank["tiers"]]
        for col, header in enumerate(headers, start=1):
            ws.cell(row=1, column=col, value=header)
        _style_header_row(ws, len(headers))
        _set_widths(ws, [36] + [55] * len(bank["tiers"]))
        ws.freeze_panes = "B2"

        meta_rows = [
            ("Сегмент капитала", lambda t, e: t["segment"] or ""),
            ("Дата скана", lambda t, e: e.get("scan_date", "")[:10]),
            ("Статус источника", lambda t, e: e.get("status", "")),
            ("Источник", lambda t, e: e.get("source_url", "")),
        ]
        row = 2
        for label, getter in meta_rows:
            ws.cell(row=row, column=1, value=label).font = Font(bold=True)
            ws.cell(row=row, column=1).border = THIN_BORDER
            for col, tier in enumerate(bank["tiers"], start=2):
                entry = results.get(tier["tier_id"], {})
                _write_value_cell(ws, row, col, getter(tier, entry) if entry else "")
            row += 1

        for field_id, spec in BANK_FIELDS.items():
            ws.cell(row=row, column=1, value=spec["label"]).font = Font(bold=True)
            ws.cell(row=row, column=1).alignment = WRAP
            ws.cell(row=row, column=1).border = THIN_BORDER
            for col, tier in enumerate(bank["tiers"], start=2):
                entry = results.get(tier["tier_id"])
                value = entry["fields"].get(field_id, NOT_FOUND) if entry else NOT_FOUND
                _write_value_cell(ws, row, col, value)
            row += 1


def _write_lifestyle(wb, results):
    ws = wb.create_sheet("Lifestyle-конкуренты")
    columns = {**LIFESTYLE_COLUMNS, **LIFESTYLE_EXTRA}
    headers = ["Подписка", "Дата скана", "Статус источника"] + [
        spec["label"] for spec in columns.values()
    ] + ["Источник"]
    for col, header in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=header)
    _style_header_row(ws, len(headers))
    _set_widths(ws, [22, 12, 14] + [42] * len(columns) + [40])
    ws.freeze_panes = "B2"

    row = 2
    for bank, tier, entry in _tier_entries(results, {"lifestyle"}):
        values = [
            tier["tier_name"],
            entry.get("scan_date", "")[:10],
            entry.get("status", ""),
        ] + [
            entry["fields"].get(field_id, NOT_FOUND) for field_id in columns
        ] + [entry.get("source_url", "")]
        for col, value in enumerate(values, start=1):
            _write_value_cell(ws, row, col, value)
        row += 1


def _write_changelog(wb, changelog):
    ws = wb.create_sheet("Изменения")
    headers = ["Дата скана", "Предыдущий скан", "Банк/подписка", "Тир",
               "Поле", "Было", "Стало"]
    for col, header in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=header)
    _style_header_row(ws, len(headers))
    _set_widths(ws, [17, 17, 20, 22, 30, 45, 45])
    ws.freeze_panes = "A2"

    if not changelog:
        ws.cell(row=2, column=1,
                value="Изменений пока нет — это первый скан или данные не менялись")
        return
    for row, change in enumerate(changelog, start=2):
        values = [change["scan_date"][:16], change["prev_date"][:16],
                  change["bank"], change["tier"], change["field"],
                  change["old"], change["new"]]
        for col, value in enumerate(values, start=1):
            _write_value_cell(ws, row, col, value)


def _write_meta(wb, history):
    ws = wb.create_sheet("Метаданные")
    _set_widths(ws, [30, 90])
    ws.cell(row=1, column=1, value="Параметр")
    ws.cell(row=1, column=2, value="Значение")
    _style_header_row(ws, 2)

    row = 2
    for scan in reversed(history.get("scans", [])):
        meta = scan.get("meta", {})
        rows = [
            ("Дата запуска", scan.get("date", "")),
            ("Режим", meta.get("mode", "")),
            ("Источники OK", "; ".join(meta.get("sources_ok", [])) or "—"),
            ("Источники с ошибками",
             "; ".join(f"{k}: {v}" for k, v in meta.get("sources_failed", {}).items()) or "—"),
            ("Полей обновлено", str(meta.get("fields_updated", ""))),
            ("Изменений найдено", str(meta.get("changes_found", ""))),
        ]
        for label, value in rows:
            ws.cell(row=row, column=1, value=label).font = Font(bold=True)
            _write_value_cell(ws, row, 2, value)
            row += 1
        row += 1  # пустая строка между сканами
