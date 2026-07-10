# -*- coding: utf-8 -*-
"""
competitor-scanner — конкурентный анализ премиального банкинга.

Запуск:
    python main.py --scan-all               # полный скан + Excel + HTML-витрины
    python main.py --scan-bank tbank        # точечный скан одного банка
    python main.py --scan-lifestyle         # только экосистемные подписки
    python main.py --build-sber-vs          # HTML-лендинг Сбер VS банки
    python main.py --build-premium-changes  # HTML-лендинг изменений с premiumbanking.info
    python main.py --build-premium-reviews  # HTML-отчёт отзывов о премиуме Сбера
    python main.py --list-sources           # показать все источники
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from scanner import sources
from scanner.curated import curated_for
from scanner.diff import (
    MAX_SERVICE_LOG,
    append_log,
    diff_results,
    load_history,
    merge_partial_scan,
    save_history,
    schema_changes,
)
from scanner.fetch import Fetcher
from scanner.merge import merge_tier_fields
from scanner.parse import parse_source
from scanner.scoring import score_tier
from report.excel_writer import write_report

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
HISTORY_PATH = DATA_DIR / "history.json"
SERVICE_LOG_PATH = DATA_DIR / "service_log.json"      # технический лог сервиса
OUTPUT_PATH = BASE_DIR / "output" / "competitor_analysis.xlsx"
SBER_VS_PATH = BASE_DIR / "output" / "sber_vs_banks.html"
PREMIUM_CHANGES_PATH = BASE_DIR / "output" / "premium_changes.html"
REVIEWS_STORE_PATH = DATA_DIR / "premium_reviews.json"

log = logging.getLogger("scanner")


def fetch_cbr_rates() -> dict:
    """Курсы ЦБ РФ на дату скана — справочно для пересчёта валютных порогов
    международных банков (см. лист «Методика оценки»)."""
    import requests
    try:
        resp = requests.get("https://www.cbr-xml-daily.ru/daily_json.js",
                            timeout=15)
        data = resp.json()
        wanted = ["USD", "EUR", "GBP", "SGD", "AED", "CHF"]
        rates = {code: round(data["Valute"][code]["Value"]
                             / data["Valute"][code]["Nominal"], 2)
                 for code in wanted if code in data.get("Valute", {})}
        rates["date"] = data.get("Date", "")[:10]
        return rates
    except Exception as exc:  # noqa: BLE001 — курсы справочные, скан не роняем
        log.warning("Курсы ЦБ получить не удалось: %s", exc)
        return {}


def scan_banks(banks: list, fetcher: Fetcher, scan_dt: str) -> tuple:
    """Сканирует список банков/подписок по всем источникам каждого тира.
    Возвращает (results, sources_ok, sources_failed)."""
    results, ok, failed = {}, [], {}
    for bank in banks:
        log.info("── %s", bank["name"])
        for tier in bank["tiers"]:
            parsed_sources = []
            ok_urls = []
            for src in sources.tier_sources(bank, tier):
                src_id = src["source_id"]
                raw_name = f"{tier['tier_id']}__{src_id}"
                fetch_result = fetcher.fetch(src["urls"], raw_name, scan_dt[:10])
                src_label = f"{bank['name']} / {tier['tier_name']} [{src_id}]"
                if fetch_result.status == "ok":
                    fields, quality = parse_source(
                        fetch_result.html, tier, bank, src_id, fetch_result.url)
                    found = sum(1 for v in fields.values()
                                if v != sources.NOT_FOUND)
                    log.info("  [ok] %s [%s] — %d полей (%s, via %s)",
                             tier["tier_name"], src_id, found, quality,
                             fetch_result.fetched_via)
                    parsed_sources.append({
                        "source_id": src_id,
                        "url": fetch_result.url,
                        "quality": quality,
                        "fields": fields,
                    })
                    ok.append(src_label)
                    ok_urls.append(fetch_result.url)
                else:
                    log.warning("  [fail] %s [%s] — %s (%s)", tier["tier_name"],
                                src_id, fetch_result.status, fetch_result.error)
                    failed[src_label] = (
                        f"{fetch_result.status}: {fetch_result.error}")

            field_ids = (list(sources.LIFESTYLE_FIELDS) + ["bank_overlap"]
                         if bank["type"] == "lifestyle"
                         else list(sources.BANK_FIELDS))
            merged = merge_tier_fields(parsed_sources, curated_for(tier["tier_id"]),
                                       field_ids, scan_dt)
            entry = {
                "bank": bank["name"],
                "tier": tier["tier_name"],
                "segment": tier.get("segment"),
                "fields": merged,
                "source_url": "; ".join(dict.fromkeys(ok_urls)),
                "status": "ok" if parsed_sources else "недоступен",
                "sources_ok": len(parsed_sources),
                "scan_date": scan_dt,
            }
            # Скоринг только для рублёвого рынка: международные банки не
            # оцениваются баллами — пороги/условия несопоставимы 1:1 (методика)
            if bank["type"] in ("our", "bank"):
                entry["score"] = score_tier(merged)
            results[tier["tier_id"]] = entry
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
    if mode == "all":
        new_scan["meta"]["cbr_rates"] = fetch_cbr_rates()
    if mode != "all":
        new_scan = merge_partial_scan(history, new_scan)

    changes = []
    if history["scans"]:
        prev = history["scans"][-1]
        changes = schema_changes(prev, new_scan, field_labels)
        changes += diff_results(prev, new_scan, field_labels)
        changes += _fill_stats_entries(changes, new_scan)
        history["changelog"].extend(changes)

    market_count = sum(1 for c in changes if c.get("kind") == "market")
    service_changes = [c for c in changes if c.get("kind") != "market"]
    # статусы источников этого скана — тоже в техлог
    service_changes += [
        {"scan_date": scan_dt, "bank": "— сервис —", "tier": name,
         "field": "источник", "old": "", "new": f"недоступен: {err}",
         "kind": "service", "source": "", "source_url": ""}
        for name, err in failed.items()
    ]
    append_log(SERVICE_LOG_PATH, service_changes, cap=MAX_SERVICE_LOG)

    fields_updated = sum(
        1 for entry in results.values()
        for v in entry["fields"].values()
        if (v.get("value") if isinstance(v, dict) else v) != sources.NOT_FOUND
    )
    new_scan["meta"]["fields_updated"] = fields_updated
    new_scan["meta"]["changes_found"] = len(changes)

    history["scans"].append(new_scan)
    save_history(history, HISTORY_PATH)
    write_report(history, OUTPUT_PATH)
    if mode == "all":
        build_full_scan_outputs()

    log.info("")
    log.info("═══ Сводка скана ═══")
    log.info("Источников успешно: %d, с ошибками: %d", len(ok), len(failed))
    log.info("Полей заполнено данными: %d", fields_updated)
    log.info("Изменений всего: %d (рыночных: %d, технических: %d)",
             len(changes), market_count, len(changes) - market_count)
    log.info("Отчёт: %s", OUTPUT_PATH)
    log.info("Техлог: %s", SERVICE_LOG_PATH)


def _fill_stats_entries(changes: list, new_scan: dict) -> list:
    """Системные записи changelog: итог целевого дозаполнения по банкам —
    сколько пустых полей закрыто, сколько осталось на ручную проверку."""
    closed = {}
    for c in changes:
        if (c.get("bank") != "— система —" and c.get("old") == sources.NOT_FOUND
                and c.get("new") != sources.NOT_FOUND):
            closed[c["bank"]] = closed.get(c["bank"], 0) + 1

    remaining = {}
    for entry in new_scan["results"].values():
        n = sum(1 for fid, f in entry["fields"].items()
                if fid not in sources.REFERENCE_FIELDS
                and (f.get("value") if isinstance(f, dict) else f) == sources.NOT_FOUND)
        if n:
            remaining[entry["bank"]] = remaining.get(entry["bank"], 0) + n

    stats = []
    for bank_name, n_closed in sorted(closed.items()):
        n_rest = remaining.get(bank_name, 0)
        stats.append({
            "scan_date": new_scan["date"],
            "prev_date": "",
            "bank": "— система —",
            "tier": bank_name,
            "field": "целевое дозаполнение пустых полей",
            "old": f"было пустых: {n_closed + n_rest}",
            "new": f"закрыто: {n_closed}; осталось на ручную проверку: {n_rest}",
            "source": "итог дозаполнения",
        })
    return stats


def list_sources():
    for bank in sources.BANKS:
        print(f"{bank['id']:14s} {bank['name']} ({bank['type']})")
        for tier in bank["tiers"]:
            print(f"    {tier['tier_id']:22s} {tier['tier_name']}")
    print("\nАгрегаторы:")
    for agg in sources.AGGREGATORS:
        print(f"    {agg['id']:22s} {agg['name']}")


def build_sber_vs_only():
    from landing.sber_vs import build_sber_vs_landing

    stats = build_sber_vs_landing(OUTPUT_PATH, SBER_VS_PATH)
    log.info("Лендинг Сбер VS банки собран: %s", stats["output"])
    log.info("Банков: %d; уровней пакетов: %d",
             stats["banks"], stats["levels"])
    return stats


def build_premium_changes_only():
    from landing.premium_changes import build_premium_changes_landing

    stats = build_premium_changes_landing(RAW_DIR, PREMIUM_CHANGES_PATH)
    log.info("Лендинг изменений премиальных программ собран: %s",
             stats["output"])
    log.info("Банков: %d; изменений: %d; ошибок: %d",
             stats["banks"], stats["changes"], stats["failed"])
    return stats


def build_full_scan_outputs():
    """Artifacts that must accompany a full market scan."""
    log.info("")
    log.info("═══ Сборка HTML-витрин полного скана ═══")
    sber_vs_stats = build_sber_vs_only()
    premium_stats = build_premium_changes_only()
    log.info("")
    log.info("═══ Артефакты полного скана ═══")
    log.info("Excel: %s", OUTPUT_PATH)
    log.info("Сравнение банков: %s", sber_vs_stats["output"])
    log.info("Новые изменения банков: %s", premium_stats["output"])


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
    group.add_argument("--build-sber-vs", action="store_true",
                       help="собрать HTML-лендинг Сбер VS банки из Excel-отчёта")
    group.add_argument("--build-premium-changes", action="store_true",
                       help="собрать HTML-лендинг изменений премиальных программ "
                            "с premiumbanking.info")
    group.add_argument("--build-premium-reviews", action="store_true",
                       help="собрать отзывы о премиальном обслуживании Сбера "
                            "(Sravni/Otzovik/ПБИ) и HTML-отчёт")
    group.add_argument("--list-sources", action="store_true",
                       help="список источников и id банков")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s",
                        stream=sys.stdout)

    if args.list_sources:
        list_sources()
    elif args.build_sber_vs:
        build_sber_vs_only()
    elif args.build_premium_changes:
        build_premium_changes_only()
    elif args.build_premium_reviews:
        from landing.premium_reviews import build_premium_reviews_landing
        stats = build_premium_reviews_landing(
            RAW_DIR, REVIEWS_STORE_PATH, BASE_DIR / "output", log)
        log.info("Отчёт по отзывам о премиуме собран: %s", stats["output"])
        log.info("Отзывов в базе: %d (новых: %d); источников со сбоями: %d",
                 stats["total"], stats["new"], stats["failed"])
    elif args.scan_bank:
        run_scan("bank", args.scan_bank)
    elif args.scan_lifestyle:
        run_scan("lifestyle")
    else:
        run_scan("all")


if __name__ == "__main__":
    main()
