# -*- coding: utf-8 -*-
"""
competitor-scanner — конкурентный анализ премиального банкинга.

Запуск:
    python main.py --scan-all               # полный скан всех источников
    python main.py --scan-bank tbank        # точечный скан одного банка
    python main.py --scan-lifestyle         # только экосистемные подписки
    python main.py --list-sources           # показать все источники
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from scanner import sources
from scanner.diff import (
    diff_results,
    load_history,
    merge_partial_scan,
    save_history,
)
from scanner.fetch import Fetcher
from scanner.parse import empty_result, parse_tier
from report.excel_writer import write_report

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
HISTORY_PATH = DATA_DIR / "history.json"
OUTPUT_PATH = BASE_DIR / "output" / "competitor_analysis.xlsx"

log = logging.getLogger("scanner")


def scan_banks(banks: list, fetcher: Fetcher, scan_dt: str) -> tuple:
    """Сканирует список банков/подписок. Возвращает (results, sources_ok, sources_failed)."""
    results, ok, failed = {}, [], {}
    for bank in banks:
        log.info("── %s", bank["name"])
        for tier in bank["tiers"]:
            source_id = tier["tier_id"]
            fetch_result = fetcher.fetch(tier["urls"], source_id, scan_dt[:10])
            if fetch_result.status == "ok":
                fields = parse_tier(fetch_result.html, tier, bank,
                                    fetch_result.url)
                found = sum(1 for v in fields.values() if v != sources.NOT_FOUND)
                log.info("  [ok] %s — %s (%d/%d полей, via %s)",
                         tier["tier_name"], fetch_result.url, found,
                         len(fields), fetch_result.fetched_via)
                ok.append(f"{bank['name']} / {tier['tier_name']}")
                status = "ok"
            else:
                fields = empty_result(bank)
                log.warning("  [fail] %s — %s (%s)", tier["tier_name"],
                            fetch_result.status, fetch_result.error)
                failed[f"{bank['name']} / {tier['tier_name']}"] = (
                    f"{fetch_result.status}: {fetch_result.error}"
                )
                status = f"недоступен ({fetch_result.error})"
            results[tier["tier_id"]] = {
                "bank": bank["name"],
                "tier": tier["tier_name"],
                "segment": tier.get("segment"),
                "fields": fields,
                "source_url": fetch_result.url,
                "status": status,
                "scan_date": scan_dt,
            }
    return results, ok, failed


def scan_aggregators(fetcher: Fetcher, scan_dt: str, ok: list, failed: dict):
    """Агрегаторы: сохраняем raw-снимки для аудита и фиксируем доступность."""
    for agg in sources.AGGREGATORS:
        log.info("── %s", agg["name"])
        result = fetcher.fetch(agg["urls"], agg["id"], scan_dt[:10])
        if result.status == "ok":
            log.info("  [ok] снимок сохранён в data/raw/%s/%s.html",
                     scan_dt[:10], agg["id"])
            ok.append(agg["name"])
        else:
            log.warning("  [fail] %s (%s)", result.status, result.error)
            failed[agg["name"]] = f"{result.status}: {result.error}"


def run_scan(mode: str, bank_id: str = None):
    scan_dt = datetime.now().isoformat(timespec="seconds")
    log.info("Старт скана: %s (режим: %s)", scan_dt, mode)

    if mode == "bank":
        bank = sources.get_bank(bank_id)
        if bank is None:
            log.error("Банк '%s' не найден. Доступные: %s",
                      bank_id, ", ".join(sources.bank_ids()))
            sys.exit(1)
        banks = [bank]
    elif mode == "lifestyle":
        banks = [b for b in sources.BANKS if b["type"] == "lifestyle"]
    else:
        banks = sources.BANKS

    fetcher = Fetcher(RAW_DIR)
    results, ok, failed = scan_banks(banks, fetcher, scan_dt)
    if mode == "all":
        scan_aggregators(fetcher, scan_dt, ok, failed)

    history = load_history(HISTORY_PATH)
    field_labels = {
        **{k: v["label"] for k, v in sources.BANK_FIELDS.items()},
        **{k: v["label"] for k, v in sources.LIFESTYLE_FIELDS.items()},
        "bank_overlap": "Пересечения с банковскими привилегиями",
    }

    new_scan = {
        "date": scan_dt,
        "results": results,
        "meta": {"mode": mode, "sources_ok": ok, "sources_failed": failed},
    }
    if mode != "all":
        new_scan = merge_partial_scan(history, new_scan)

    changes = []
    if history["scans"]:
        changes = diff_results(history["scans"][-1], new_scan, field_labels)
        history["changelog"].extend(changes)

    fields_updated = sum(
        1 for entry in results.values()
        for v in entry["fields"].values() if v != sources.NOT_FOUND
    )
    new_scan["meta"]["fields_updated"] = fields_updated
    new_scan["meta"]["changes_found"] = len(changes)

    history["scans"].append(new_scan)
    save_history(history, HISTORY_PATH)
    write_report(history, OUTPUT_PATH)

    log.info("")
    log.info("═══ Сводка скана ═══")
    log.info("Источников успешно: %d, с ошибками: %d", len(ok), len(failed))
    log.info("Полей заполнено данными: %d", fields_updated)
    log.info("Изменений с прошлого скана: %d", len(changes))
    log.info("Отчёт: %s", OUTPUT_PATH)
    log.info("История: %s", HISTORY_PATH)


def list_sources():
    for bank in sources.BANKS:
        print(f"{bank['id']:14s} {bank['name']} ({bank['type']})")
        for tier in bank["tiers"]:
            print(f"    {tier['tier_id']:22s} {tier['tier_name']}")
    print("\nАгрегаторы:")
    for agg in sources.AGGREGATORS:
        print(f"    {agg['id']:22s} {agg['name']}")


def main():
    parser = argparse.ArgumentParser(
        description="Сканер конкурентного анализа премиум-банкинга")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scan-all", action="store_true",
                       help="полный скан всех банков, подписок и агрегаторов")
    group.add_argument("--scan-bank", metavar="BANK_ID",
                       help="скан одного банка (id из --list-sources)")
    group.add_argument("--scan-lifestyle", action="store_true",
                       help="скан только экосистемных подписок")
    group.add_argument("--list-sources", action="store_true",
                       help="список источников и id банков")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s",
                        stream=sys.stdout)

    if args.list_sources:
        list_sources()
    elif args.scan_bank:
        run_scan("bank", args.scan_bank)
    elif args.scan_lifestyle:
        run_scan("lifestyle")
    else:
        run_scan("all")


if __name__ == "__main__":
    main()
