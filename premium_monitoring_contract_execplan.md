# Add the premium monitoring Excel contract

This ExecPlan is a living document. It follows `PLANS.md` in this repository.

## Purpose / Big Picture

The user needs the premium banking monitor to keep the Excel workbook as the only data source for public HTML. After this change, `output/competitor_analysis.xlsx` will contain explicit contract sheets named `Banks`, `Products`, `Changes`, `Sources`, and `Monitoring_Log`; `output/premium_changes.html` will be generated from the workbook instead of fetching PremiumBanking.info directly; and each scan will leave machine-readable and text run reports in `output/`.

## Progress

- [x] (2026-07-14T00:00:00Z) Read the attached monitoring requirements, `AGENTS.md`, `PLANS.md`, and `SOURCE_POLICY.md`.
- [x] (2026-07-14T00:00:00Z) Confirmed that `landing/sber_vs.py` already reads `competitor_analysis.xlsx`, while `landing/premium_changes.py` still fetches PremiumBanking.info directly.
- [x] (2026-07-14T00:00:00Z) Add Excel contract sheets without removing the existing Russian analytical sheets.
- [x] (2026-07-14T00:00:00Z) Change `premium_changes.html` generation to read the Excel `Changes` sheet only.
- [x] (2026-07-14T00:00:00Z) Add per-run JSON and text summaries after scans.
- [x] (2026-07-14T00:00:00Z) Add regression tests for the Excel contract and premium changes landing source boundary.
- [x] (2026-07-14T00:00:00Z) Run project self-checks and record results.

## Surprises & Discoveries

- Observation: The repository already contains provenance sheets `Провенанс значений` and `Конфликты источников`, so the new `Products` sheet can point to normalized fields without duplicating all raw provenance columns.
  Evidence: `report/excel_writer.py` writes both sheets before the methodology sheet.

## Decision Log

- Decision: Keep existing workbook sheets and add the requested English-named sheets as compatibility/contract sheets.
  Rationale: Existing code and tests depend on the Russian analytical sheets; adding sheets is safer than renaming or replacing them.
  Date/Author: 2026-07-14 / Codex
- Decision: Generate `premium_changes.html` from `output/competitor_analysis.xlsx` and the `Changes` sheet, with no network fetcher in that module.
  Rationale: The request explicitly forbids passing found changes directly into HTML and requires HTML to read Excel.
  Date/Author: 2026-07-14 / Codex

## Outcomes & Retrospective

Completed. `output/competitor_analysis.xlsx` now contains the requested contract sheets alongside the existing analytical sheets. `output/premium_changes.html` is rebuilt from the Excel `Changes` sheet and no longer fetches PremiumBanking.info directly. Scans now write `output/last_run_report.json` and `output/last_run_report.txt` with the requested run summary structure.

## Context and Orientation

`main.py` runs scans, stores history in `data/history.json`, writes `output/competitor_analysis.xlsx` through `report/excel_writer.py`, and builds HTML files under `output/`. `landing/sber_vs.py` already reads the Excel workbook. `landing/premium_changes.py` currently fetches PremiumBanking.info directly, which violates the new requirement. The existing `Изменения` sheet is a legacy changelog; the new `Changes` sheet will expose the user-requested normalized columns.

## Plan of Work

First, extend `report/excel_writer.py` so `write_report` adds `Banks`, `Products`, `Changes`, `Sources`, and `Monitoring_Log`. These sheets will be built from `scanner/sources.py` and `data/history.json` data already passed into `write_report`; missing facts will use `sources.NOT_FOUND`.

Second, rewrite `landing/premium_changes.py` so `build_premium_changes_landing` accepts a workbook path and reads only the `Changes` sheet. It will filter records by `html_visible`, `verification_status`, required bank/description/source fields, and group visible changes by bank.

Third, update `main.py` so `--build-premium-changes` passes `OUTPUT_PATH`, and scans emit `output/last_run_report.json` plus `output/last_run_report.txt`.

Fourth, add focused tests proving that the workbook has the requested contract sheets and that `landing/premium_changes.py` contains no fetch/network path.

## Concrete Steps

Run commands from `/Users/ilyashmarov/Documents/analyst/bank_analyst`.

After edits, run:

    .venv/bin/python main.py --list-sources
    .venv/bin/python -m unittest discover -s tests
    .venv/bin/python main.py --build-premium-changes

## Validation and Acceptance

The tests must pass. `--build-premium-changes` must complete without fetching external websites and produce `output/premium_changes.html` from `output/competitor_analysis.xlsx`. The workbook must contain sheets named `Banks`, `Products`, `Changes`, `Sources`, and `Monitoring_Log`.

## Idempotence and Recovery

All generated files can be rebuilt. Re-running `write_report` replaces the workbook with sheets generated from current history. Re-running `--build-premium-changes` rewrites only `output/premium_changes.html`.

## Artifacts and Notes

Validation output:

    .venv/bin/python main.py --list-sources
    exited 0 and listed all configured banks, tiers, and aggregators.

    .venv/bin/python -m unittest discover -s tests
    Ran 65 tests in 22.958s
    OK

    .venv/bin/python main.py --build-premium-changes
    Лендинг изменений премиальных программ собран: /Users/ilyashmarov/Documents/analyst/bank_analyst/output/premium_changes.html
    Банков: 7; изменений: 311; ошибок: 0

    Workbook contract sheet check after regeneration:
    Banks 12 9
    Products 44 24
    Changes 340 28
    Sources 173 12
    Monitoring_Log 21 10

Revision note 2026-07-14 / Codex: Implemented the Excel contract sheets, switched the premium changes landing to Excel-only generation, added scan run reports, and recorded validation evidence.

## Interfaces and Dependencies

No new dependencies are needed. The implementation uses existing `openpyxl`, `scanner.sources`, and `scanner.merge.field_value`.
