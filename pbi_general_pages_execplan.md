# PremiumBanking.info General Pages Per-Tier Parsing

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document follows `PLANS.md` in the repository root.

## Purpose / Big Picture

The scanner already knows the PremiumBanking.info bank overview URLs, but only Sber uses its overview page as a real per-tier fact source. After this change, Alfa-Bank, VTB, Gazprombank, Ozon Bank, Raiffeisen Bank, and T-Bank will use their corresponding overview pages as the first PremiumBanking.info source while retaining level-specific pages as fallback. A user can verify the behavior by running a bank scan and seeing facts from `https://premiumbanking.info/<bank>` flow into `output/competitor_analysis.xlsx` and then into `output/sber_vs_banks.html` without mixing neighboring levels.

## Progress

- [x] (2026-07-13T00:00:00Z) Read the user request, `AGENTS.md`, `PLANS.md`, current source registry, PBI parser, merge logic, and report writer.
- [x] (2026-07-13T00:10:00Z) Checked the live PremiumBanking.info overview pages for Alfa-Bank, VTB, Gazprombank, Ozon Bank, Raiffeisen Bank, and T-Bank.
- [x] (2026-07-13T00:25:00Z) Added general overview URLs as first PBI source for all requested banks.
- [x] (2026-07-13T00:45:00Z) Generalized `PremiumBankingInfoParser` so overview blocks are selected by tier identity and entry-condition hints, not only by Sber level number.
- [x] (2026-07-13T01:05:00Z) Added regression tests for all requested banks, fallback source order, cross-tier separation, and overview registration.
- [x] (2026-07-13T01:25:00Z) Ran tests and safe scans, then rebuilt Excel and Sber VS HTML without publishing.
- [x] (2026-07-13T01:45:00Z) Split runtime PBI fetching into `pbi` overview and `pbi_level` fallback sources so fallback works per missing field, not only when the overview URL is unavailable.

## Surprises & Discoveries

- Observation: Alfa-Bank overview currently shows detailed blocks for Alfa Only at 3, 6, and 12 million rubles and A-Club, while the level table also mentions a paid Alfa Only level at 2990 rubles per month. The project has five Alfa tiers, so the paid tier must not borrow the 3 million block from the overview.
  Evidence: `https://premiumbanking.info/alfabank` shows the first detailed block as `Альфа-Банк – Alfa Only` with `за 3 млн ₽`, and separate table rows mention `Alfa Only за 2990 ₽ в мес`.
- Observation: T-Bank overview has seven blocks, including Private at 30, 55, and higher thresholds, while the project currently has four T-Bank tiers through Diamond. The parser must select only matching configured tiers and not collapse Private facts into Diamond.
  Evidence: `https://premiumbanking.info/tbank` shows Bronze, Silver, Gold, Diamond, and multiple Private blocks.
- Observation: VTB overview has a paid Privilege level in the summary table, but its detailed overview blocks start at the 2.5 million ruble Privilege level. Therefore `vtb_privilege_1` must not take the 2.5 million block.
  Evidence: live parsing returned `NOT_FOUND` for `vtb_privilege_1` and 9 structured fields for `vtb_privilege_2`.

## Decision Log

- Decision: Use the overview URL as the first `pbi` URL in `scanner/sources.py`, followed by the existing level-specific URL.
  Rationale: This preserves the requested priority order: official source first, PBI overview second, PBI level page third.
  Date/Author: 2026-07-13 / Codex.
- Decision: Match overview blocks by product words from `tier_name`, numeric threshold hints from `segment`, `tier_id`, and the tier's fallback URL order, rather than by DOM position alone.
  Rationale: Several pages repeat the same product heading across thresholds, and pure order would leak Alfa Only or Private data into the wrong configured tier when the overview has a different number of detailed blocks.
  Date/Author: 2026-07-13 / Codex.
- Decision: Leave `publisher.py` untouched and rebuild HTML through `landing.sber_vs.build_sber_vs_landing` directly.
  Rationale: The user explicitly asked not to publish, and the current CLI build path may invoke the existing publisher.
  Date/Author: 2026-07-13 / Codex.
- Decision: For tiers with explicit overview hints, do not fall back to fuzzy product matching if the hinted block is absent.
  Rationale: Alfa and VTB have paid levels mentioned in tables but not as full detailed blocks. Returning `NOT_FOUND` for the overview source lets the existing level-specific PBI URL serve as fallback without cross-tier leakage.
  Date/Author: 2026-07-13 / Codex.
- Decision: Keep the compact `_src("pbi", overview, fallback)` configuration, but expand it inside `tier_sources()` into two runtime sources: `pbi` and `pbi_level`.
  Rationale: `Fetcher.fetch()` returns the first reachable URL from a source, so a single source with two URLs cannot fallback per missing field. Separate runtime sources let merge choose overview facts first and use level pages only for fields missing from the overview.
  Date/Author: 2026-07-13 / Codex.

## Outcomes & Retrospective

Completed. The requested banks now use their PBI overview pages before level-specific fallback URLs, and runtime scanning expands those URLs into `pbi` and `pbi_level` so missing fields can be filled from level pages. The parser extracts per-tier overview blocks without cross-product leakage, tests pass, scans completed for all requested banks, and `output/competitor_analysis.xlsx` plus `output/sber_vs_banks.html` were rebuilt locally. `publisher.py` was not edited or invoked.

## Context and Orientation

`scanner/sources.py` defines banks, tiers, and sources. Each tier source created by `_src("pbi", ...)` is fetched and parsed by `scanner/parse.py`. `PremiumBankingInfoParser` already parses definition-list style PBI level pages and has Sber-specific fallback logic for overview blocks. `scanner/merge.py` attaches `bank_id`, `tier_id`, `field_id`, `source_url`, `source_type`, `date_checked`, and `raw_text` to every merged field. `report/excel_writer.py` writes those values to `output/competitor_analysis.xlsx`, and `landing/sber_vs.py` reads the workbook to produce HTML.

## Plan of Work

First, add constants for all PBI overview URLs and change the requested banks so every tier lists the overview URL before its existing level URL. Next, refactor the Sber-specific overview parser into a generic block parser that can identify headings such as `Альфа-Банк – Alfa Only`, `ВТБ – Привилегия`, `Газпромбанк – Private`, `Ozon банк – Ultra Bronze`, `Райффайзен – Premium`, and `Т-Банк – Diamond`. The parser will extract only lines inside the selected block and map labels like `Бизнес-залы`, `Рестораны`, `Такси`, `Трансфер`, `Страховка`, `Преференции`, `Доступно на выбор`, and `Другие привилегии` into project fields.

Finally, add fixture-based tests for the requested banks and source-order tests that inspect `BANKS`. Run unit tests, run targeted scan commands for the changed banks when practical, and rebuild local artifacts without publication.

## Concrete Steps

Run all commands from `/Users/ilyashmarov/Documents/analyst/bank_analyst`.

Use `apply_patch` for manual source edits. Use these validation commands:

    .venv/bin/python main.py --list-sources
    .venv/bin/python -m unittest
    .venv/bin/python main.py --scan-bank alfabank
    .venv/bin/python main.py --scan-bank vtb
    .venv/bin/python main.py --scan-bank gazprombank
    .venv/bin/python main.py --scan-bank ozonbank
    .venv/bin/python main.py --scan-bank raiffeisen
    .venv/bin/python main.py --scan-bank tbank
    .venv/bin/python -c 'from pathlib import Path; from landing.sber_vs import build_sber_vs_landing; print(build_sber_vs_landing(Path("output/competitor_analysis.xlsx"), Path("output/sber_vs_banks.html")))'

## Validation and Acceptance

Acceptance is behavioral. The tests must prove that Alfa Only and A-Club, VTB Privilege and Prime+, and T-Bank Premium/Diamond and Private are not mixed. A real scan must show the overview URLs being fetched as `pbi` sources before level-specific fallbacks. The workbook must include PBI overview source URLs in field provenance where those facts win, and the HTML must still be built from Excel.

## Idempotence and Recovery

All scan and build commands can be repeated. They overwrite generated artifacts from current source definitions and append scan history. No destructive git command is needed. If a live source is blocked, parser fixture tests remain the acceptance proof for code behavior.

## Artifacts and Notes

Key live source pages checked:

    https://premiumbanking.info/alfabank
    https://premiumbanking.info/vtb
    https://premiumbanking.info/gazprombank
    https://premiumbanking.info/ozon
    https://premiumbanking.info/raiffeisen
    https://premiumbanking.info/tbank

## Interfaces and Dependencies

No new dependency is required. The implementation uses `beautifulsoup4`, `re`, and existing project modules.
