# -*- coding: utf-8 -*-
"""
Генерация Excel-отчёта (openpyxl).

Файл каждый раз регенерируется из полной истории data/history.json,
поэтому changelog и данные прошлых сканов не теряются между запусками.

Листы:
  1. Сводная            — тиры по сегментам капитала + итоговый балл + расхождения
  2. <Банк>             — детализация: значение + источник + дата проверки
  3. Lifestyle          — экосистемные подписки
  4. Изменения          — changelog (было/стало, источник, ручные уточнения)
  5. Методика оценки    — формула, веса, пороги, разбивка балла по тирам
  6. Метаданные         — дата запуска, статус источников
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from scanner.merge import field_value
from scanner.scoring import METHODOLOGY_TEXT, THRESHOLDS, WEIGHTS
from scanner.sources import (
    BANK_FIELDS,
    BANKS,
    LIFESTYLE_FIELDS,
    NOT_FOUND,
    REFERENCE_FIELDS,
    SEGMENTS,
)

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
SEGMENT_FILL = PatternFill("solid", fgColor="D6E4F0")
OUR_FILL = PatternFill("solid", fgColor="E2EFDA")
DIVERGENT_FILL = PatternFill("solid", fgColor="FCE4D6")
NOT_FOUND_FONT = Font(color="999999", italic=True)
HEADER_FONT = Font(color="FFFFFF", bold=True)
WRAP = Alignment(wrap_text=True, vertical="top")
THIN_BORDER = Border(*[Side(style="thin", color="CCCCCC")] * 4)

LIFESTYLE_COLUMNS = dict(LIFESTYLE_FIELDS)
LIFESTYLE_EXTRA = {"bank_overlap": {"label": "Пересечения с банковскими привилегиями"}}


def write_report(history: dict, output_path: Path):
    wb = Workbook()
    wb.remove(wb.active)

    last_scan = history["scans"][-1] if history["scans"] else {
        "results": {}, "meta": {}, "date": ""}
    results = last_scan.get("results", {})

    _write_summary(wb, results, last_scan.get("date", ""))
    _write_bank_sheets(wb, results)
    _write_lifestyle(wb, results)
    _write_changelog(wb, history.get("changelog", []))
    _write_manual_check(wb, results)
    _write_methodology(wb, results)
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


def _annotated(field) -> str:
    """Значение поля + провенанс: источник, дата проверки, примечание."""
    if not isinstance(field, dict):
        return field if field is not None else NOT_FOUND
    value = field.get("value", NOT_FOUND)
    if value == NOT_FOUND:
        return NOT_FOUND
    parts = [value]
    src = field.get("source_name", "")
    if src:
        parts.append(f"[источник: {src}, проверено: {field.get('date_checked', '')}]")
    if field.get("note"):
        parts.append(f"[прим.: {field['note']}]")
    return "\n".join(parts)


def _divergence_info(fields: dict) -> tuple:
    """(да/нет, комментарий по полям с расхождениями источников)."""
    comments = []
    for fid, field in fields.items():
        if isinstance(field, dict) and field.get("divergent"):
            label = BANK_FIELDS.get(fid, {}).get("label", fid)
            alts = "; ".join(
                f"{a['source_name']}: {a['value'][:80]}"
                for a in field.get("alternatives", []))
            comments.append(f"{label} — основное: {field['value'][:80]} | {alts}")
    return ("да" if comments else "нет"), "\n".join(comments)


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
    headers = (["Сегмент капитала", "Банк", "Тир", "Дата скана",
                "Источников OK", "Итоговый балл (0–5)",
                "Расхождение источников", "Комментарий по расхождениям"]
               + [spec["label"] for spec in BANK_FIELDS.values()])
    for col, header in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=header)
    _style_header_row(ws, len(headers))
    _set_widths(ws, [14, 14, 24, 11, 11, 11, 13, 45] + [40] * len(BANK_FIELDS))
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
            divergent, div_comment = _divergence_info(entry["fields"])
            score = entry.get("score", {}).get("total", "")
            values = [
                "", bank["name"], tier["tier_name"],
                entry.get("scan_date", scan_date)[:10],
                entry.get("sources_ok", ""),
                score, divergent, div_comment,
            ] + [
                _annotated(entry["fields"].get(fid)) for fid in BANK_FIELDS
            ]
            for col, value in enumerate(values, start=1):
                cell = _write_value_cell(ws, row, col, value)
                if bank["type"] == "our" and col in (2, 3):
                    cell.fill = OUR_FILL
                if col == 7 and divergent == "да":
                    cell.fill = DIVERGENT_FILL
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
            ("Источников OK", lambda t, e: str(e.get("sources_ok", ""))),
            ("Итоговый балл (0–5)",
             lambda t, e: str(e.get("score", {}).get("total", ""))),
            ("Источники (URL)", lambda t, e: e.get("source_url", "")),
        ]
        row = 2
        for label, getter in meta_rows:
            ws.cell(row=row, column=1, value=label).font = Font(bold=True)
            ws.cell(row=row, column=1).border = THIN_BORDER
            for col, tier in enumerate(bank["tiers"], start=2):
                entry = results.get(tier["tier_id"], {})
                _write_value_cell(ws, row, col, getter(tier, entry) if entry else "")
            row += 1

        for fid, spec in BANK_FIELDS.items():
            ws.cell(row=row, column=1, value=spec["label"]).font = Font(bold=True)
            ws.cell(row=row, column=1).alignment = WRAP
            ws.cell(row=row, column=1).border = THIN_BORDER
            for col, tier in enumerate(bank["tiers"], start=2):
                entry = results.get(tier["tier_id"])
                field = entry["fields"].get(fid) if entry else None
                cell = _write_value_cell(ws, row, col, _annotated(field))
                if isinstance(field, dict) and field.get("divergent"):
                    cell.fill = DIVERGENT_FILL
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
            _annotated(entry["fields"].get(fid)) for fid in columns
        ] + [entry.get("source_url", "")]
        for col, value in enumerate(values, start=1):
            _write_value_cell(ws, row, col, value)
        row += 1


def _write_changelog(wb, changelog):
    ws = wb.create_sheet("Изменения")
    headers = ["Дата скана", "Предыдущий скан", "Банк/подписка", "Тир",
               "Поле", "Было", "Стало", "Источник нового значения"]
    for col, header in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=header)
    _style_header_row(ws, len(headers))
    _set_widths(ws, [17, 17, 20, 22, 30, 42, 42, 30])
    ws.freeze_panes = "A2"

    if not changelog:
        ws.cell(row=2, column=1,
                value="Изменений пока нет — это первый скан или данные не менялись")
        return
    for row, change in enumerate(changelog, start=2):
        values = [change["scan_date"][:16], change["prev_date"][:16],
                  change["bank"], change["tier"], change["field"],
                  change["old"], change["new"], change.get("source", "")]
        for col, value in enumerate(values, start=1):
            cell = _write_value_cell(ws, row, col, value)
            if "ручное уточнение" in str(change.get("source", "")) and col == 8:
                cell.fill = DIVERGENT_FILL


def _write_manual_check(wb, results):
    """Все поля со статусом «не найдено» — чтобы пробелы не терялись молча.
    Значения «—» (подтверждённое отсутствие услуги) сюда не попадают."""
    ws = wb.create_sheet("Требует ручной проверки")
    headers = ["Банк/подписка", "Тир", "Поле", "Причина / что делать"]
    for col, header in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=header)
    _style_header_row(ws, len(headers))
    _set_widths(ws, [24, 26, 38, 70])
    ws.freeze_panes = "A2"

    all_labels = {**{k: v["label"] for k, v in BANK_FIELDS.items()},
                  **{k: v["label"] for k, v in LIFESTYLE_FIELDS.items()},
                  "bank_overlap": "Пересечения с банковскими привилегиями"}
    row = 2
    for bank in BANKS:
        for tier in bank["tiers"]:
            entry = results.get(tier["tier_id"])
            if not entry:
                continue
            for fid, field in entry["fields"].items():
                if field_value(field) != NOT_FOUND:
                    continue
                if entry.get("sources_ok", 0) == 0:
                    reason = ("все источники недоступны (антибот/блокировка) — "
                              "проверить вручную или найти зеркальный источник")
                elif fid in REFERENCE_FIELDS:
                    reason = "справочное поле — заполняется при появлении данных"
                else:
                    reason = ("целевой поиск публичных данных результата не дал — "
                              "проверить тарифные PDF банка / запросить у банка")
                values = [entry["bank"], entry["tier"], all_labels.get(fid, fid),
                          reason]
                for col, value in enumerate(values, start=1):
                    _write_value_cell(ws, row, col, value)
                row += 1
    if row == 2:
        ws.cell(row=2, column=1, value="Пробелов нет — все поля заполнены "
                                       "или помечены как отсутствующие")


def _write_methodology(wb, results):
    ws = wb.create_sheet("Методика оценки")
    _set_widths(ws, [26, 22, 34, 10, 9, 13])

    row = 1
    ws.cell(row=row, column=1, value="Методика собственной оценки пакетов")
    ws.cell(row=row, column=1).font = Font(bold=True, size=13)
    row += 2
    for line in METHODOLOGY_TEXT:
        cell = ws.cell(row=row, column=1, value=line)
        cell.alignment = WRAP
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        row += 1
    row += 1

    ws.cell(row=row, column=1, value="Веса категорий (сумма = 1.0)").font = Font(bold=True)
    row += 1
    for category, weight in WEIGHTS.items():
        label = BANK_FIELDS.get(category, {}).get("label", category)
        ws.cell(row=row, column=1, value=label)
        ws.cell(row=row, column=2, value=weight)
        row += 1
    row += 1

    ws.cell(row=row, column=1, value="Пороговые таблицы (метрика ≥ порога → балл)").font = Font(bold=True)
    row += 1
    for table_key, table in THRESHOLDS.items():
        ws.cell(row=row, column=1, value=table_key)
        ws.cell(row=row, column=2,
                value="; ".join(f"≥{minimum} → {score}" for minimum, score in table))
        row += 1
    ws.cell(row=row, column=1, value="особые правила")
    ws.cell(row=row, column=2,
            value="безлимит → 5; консьерж есть/нет → 5/0; страховка по покрытию "
                  "(≈1 млн → 5 … 30–90 тыс → 2); авто: 3 базово +1 помощь на "
                  "дорогах +1 кэшбэк дороги/парковки; «не найдено» → 0")
    ws.cell(row=row, column=2).alignment = WRAP
    row += 2

    ws.cell(row=row, column=1, value="Разбивка балла по тирам").font = Font(bold=True)
    row += 1
    headers = ["Банк / тир", "Категория", "Извлечённая метрика", "Балл 0–5",
               "Вес", "Вклад в итог"]
    for col, header in enumerate(headers, start=1):
        ws.cell(row=row, column=col, value=header)
    _style_header_row(ws, len(headers), row=row)
    row += 1

    for bank, tier, entry in _tier_entries(results, {"our", "bank"}):
        score = entry.get("score")
        if not score:
            continue
        first_row = row
        for category, detail in score["breakdown"].items():
            label = BANK_FIELDS.get(category, {}).get("label", category)
            values = ["", label, detail["metric"], detail["score"],
                      detail["weight"], detail["contribution"]]
            for col, value in enumerate(values, start=1):
                _write_value_cell(ws, row, col, value)
            row += 1
        name_cell = ws.cell(row=first_row, column=1,
                            value=f"{bank['name']} / {tier['tier_name']}")
        name_cell.font = Font(bold=True)
        name_cell.alignment = WRAP
        total_cell = ws.cell(row=row, column=1, value="ИТОГО")
        total_cell.font = Font(bold=True)
        ws.cell(row=row, column=6, value=score["total"]).font = Font(bold=True)
        row += 2


def _write_meta(wb, history):
    ws = wb.create_sheet("Метаданные")
    _set_widths(ws, [30, 110])
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
