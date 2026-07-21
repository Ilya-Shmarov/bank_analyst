# -*- coding: utf-8 -*-
"""
competitor-scanner — конкурентный анализ премиального банкинга.

Запуск:
    python main.py --scan-all               # полный скан + Excel + JSON + HTML-витрины
    python main.py --scan-bank tbank        # точечный скан одного банка
    python main.py --scan-lifestyle         # только экосистемные подписки
    python main.py --build-sber-vs          # HTML-лендинг Сбер VS банки
    python main.py --build-premium-changes  # HTML-лендинг изменений с premiumbanking.info
    python main.py --build-premium-reviews  # HTML-отчёт отзывов о премиуме Сбера
    python main.py --list-sources           # показать все источники
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from scanner import sources
from scanner.benefits import other_benefits_text
from scanner.contracts import validate_scan_contracts
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
from scanner.publication import apply_publication_gate, derivation_components, gate_field
from scanner.scoring import score_tier
from report.excel_writer import write_report
from report.json_writer import write_comparison_json
from config import COMPARISON_JSON, GENERATED_HTML
from publisher import publish_site

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
HISTORY_PATH = DATA_DIR / "history.json"
SERVICE_LOG_PATH = DATA_DIR / "service_log.json"      # технический лог сервиса
OUTPUT_PATH = BASE_DIR / "output" / "competitor_analysis.xlsx"
COMPARISON_JSON_PATH = BASE_DIR / "output" / COMPARISON_JSON
SBER_VS_PATH = BASE_DIR / "output" / GENERATED_HTML
PREMIUM_CHANGES_PATH = BASE_DIR / "output" / "premium_changes.html"
REVIEWS_STORE_PATH = DATA_DIR / "premium_reviews.json"
RUN_REPORT_JSON_PATH = BASE_DIR / "output" / "last_run_report.json"
RUN_REPORT_TEXT_PATH = BASE_DIR / "output" / "last_run_report.txt"

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
                        "source_section": tier.get("tier_name", ""),
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
            merged = merge_tier_fields(
                parsed_sources, curated_for(tier["tier_id"]), field_ids, scan_dt,
                bank_id=bank["id"], tier_id=tier["tier_id"],
            )
            merged = apply_publication_gate(merged)
            if bank["type"] != "lifestyle" and "other_benefits" in merged:
                derived_value = other_benefits_text(merged)
                component_ids = (
                    "always_included_options", "selectable_options",
                    "ecosystem", "auto", "concierge",
                )
                source_urls = [
                    merged[fid].get("source_url", "")
                    for fid in component_ids
                    if isinstance(merged.get(fid), dict)
                    and merged[fid].get("publication_status") == "published"
                    and merged[fid].get("source_url")
                ]
                merged["other_benefits"]["value"] = derived_value
                merged["other_benefits"]["source_id"] = "derived"
                merged["other_benefits"]["source_name"] = "Нормализация"
                merged["other_benefits"]["quality"] = "derived"
                merged["other_benefits"]["source_url"] = "; ".join(
                    dict.fromkeys(source_urls)
                )
                merged["other_benefits"]["raw_text"] = derived_value
                merged["other_benefits"]["derived_from"] = derivation_components(
                    merged, component_ids,
                )
                merged["other_benefits"] = gate_field(
                    merged["other_benefits"], "other_benefits",
                )
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
    quality_results = results
    if mode != "all":
        new_scan = merge_partial_scan(history, new_scan)
    else:
        quality_results = new_scan.get("results", {})

    quality_issues = validate_scan_contracts(quality_results)
    new_scan["meta"]["quality_issues"] = quality_issues
    new_scan["meta"]["quality_errors"] = sum(
        1 for issue in quality_issues if issue.get("severity") == "error")
    new_scan["meta"]["quality_warnings"] = sum(
        1 for issue in quality_issues if issue.get("severity") == "warning")

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
    service_changes += [
        {"scan_date": scan_dt, "bank": "— quality gate —",
         "tier": f"{issue.get('bank', '')} / {issue.get('tier', '')}",
         "field": issue.get("field_id", ""),
         "old": issue.get("code", ""),
         "new": issue.get("message", ""),
         "kind": "service",
         "source": issue.get("severity", ""),
         "source_url": ""}
        for issue in quality_issues
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
    write_comparison_json(history, COMPARISON_JSON_PATH)
    html_generated = False
    if mode == "all":
        build_full_scan_outputs()
        html_generated = True

    _write_run_reports(
        run_id=_run_id(scan_dt),
        started_at=scan_dt,
        finished_at=datetime.now().isoformat(timespec="seconds"),
        banks=banks,
        ok=ok,
        failed=failed,
        changes=changes,
        quality_issues=quality_issues,
        excel_updated=True,
        html_generated=html_generated,
        github_pages_published=html_generated,
    )

    log.info("")
    log.info("═══ Сводка скана ═══")
    log.info("Источников успешно: %d, с ошибками: %d", len(ok), len(failed))
    log.info("Полей заполнено данными: %d", fields_updated)
    log.info("Изменений всего: %d (рыночных: %d, технических: %d)",
             len(changes), market_count, len(changes) - market_count)
    log.info("Проверка качества: ошибок %d, предупреждений %d",
             new_scan["meta"]["quality_errors"],
             new_scan["meta"]["quality_warnings"])
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

    history = load_history(HISTORY_PATH)
    write_comparison_json(history, COMPARISON_JSON_PATH)
    stats = build_sber_vs_landing(COMPARISON_JSON_PATH, SBER_VS_PATH)
    log.info("Лендинг Сбер VS банки собран: %s", stats["output"])
    log.info("Банков: %d; уровней пакетов: %d",
             stats["banks"], stats["levels"])
    publish_site(Path(stats["output"]))
    return stats


def build_premium_changes_only():
    from landing.premium_changes import build_premium_changes_landing

    stats = build_premium_changes_landing(OUTPUT_PATH, PREMIUM_CHANGES_PATH)
    log.info("Лендинг изменений премиальных программ собран: %s",
             stats["output"])
    log.info("Банков: %d; изменений: %d; ошибок: %d",
             stats["banks"], stats["changes"], stats["failed"])
    return stats


def _run_id(scan_dt: str) -> str:
    return f"run_{scan_dt.replace('-', '').replace(':', '').replace('T', '_')}"


def _write_run_reports(run_id: str, started_at: str, finished_at: str,
                       banks: list, ok: list, failed: dict, changes: list,
                       quality_issues: list,
                       excel_updated: bool, html_generated: bool,
                       github_pages_published: bool):
    market_changes = [c for c in changes if c.get("kind") == "market"]
    confirmed = [c for c in market_changes if c.get("source_url")]
    requiring_review = [c for c in market_changes if not c.get("source_url")]
    report = {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "banks_checked": len([b for b in banks if b["type"] != "lifestyle"]),
        "sources_checked": len(ok) + len(failed),
        "documents_checked": 0,
        "new_changes_found": len(market_changes),
        "confirmed_changes": len(confirmed),
        "changes_requiring_review": len(requiring_review),
        "duplicate_changes_skipped": 0,
        "errors": len(failed),
        "quality_errors": sum(1 for i in quality_issues if i.get("severity") == "error"),
        "quality_warnings": sum(1 for i in quality_issues if i.get("severity") == "warning"),
        "quality_issues": quality_issues[:200],
        "excel_updated": excel_updated,
        "html_generated": html_generated,
        "github_pages_published": github_pages_published,
    }
    RUN_REPORT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUN_REPORT_JSON_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    changed_banks = sorted({c.get("bank", "") for c in market_changes if c.get("bank")})
    text = "\n".join([
        f"run_id: {run_id}",
        f"Проверены банки: {', '.join(b['name'] for b in banks) or 'нет'}",
        f"Банки с изменениями: {', '.join(changed_banks) or 'нет'}",
        f"Подтвержденные изменения: {len(confirmed)}",
        f"Требуют ручной проверки: {len(requiring_review)}",
        f"Недоступные источники: {len(failed)}",
        f"Ошибки качества данных: {report['quality_errors']}",
        f"Предупреждения качества данных: {report['quality_warnings']}",
        f"Excel обновлен: {'да' if excel_updated else 'нет'}",
        f"HTML пересоздан: {'да' if html_generated else 'нет'}",
        f"GitHub Pages публикация: {'да' if github_pages_published else 'нет'}",
    ])
    RUN_REPORT_TEXT_PATH.write_text(text + "\n", encoding="utf-8")


def build_full_scan_outputs():
    """Artifacts that must accompany a full market scan."""
    log.info("")
    log.info("═══ Сборка HTML-витрин полного скана ═══")
    sber_vs_stats = build_sber_vs_only()
    premium_stats = build_premium_changes_only()
    log.info("")
    log.info("═══ Артефакты полного скана ═══")
    log.info("Excel: %s", OUTPUT_PATH)
    log.info("JSON сравнения: %s", COMPARISON_JSON_PATH)
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
                       help="собрать HTML-лендинг Сбер VS банки из JSON-экспорта")
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
