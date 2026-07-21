# Make Excel the Single Source for the Sber VS Landing

This ExecPlan is a living document. It follows `PLANS.md` in this repository.

## Purpose / Big Picture

The user needs the Sber-vs-banks landing to show only facts that were normalized into `output/competitor_analysis.xlsx`. After this change, the HTML generator will not infer missing "Другие привилегии" from raw or service Excel fields. The scanner/report path will filter insurance risks out of "Другие привилегии" before Excel is written, and tests will catch the Sber level 1 leak that previously put visa, baggage, ski, and flight-delay insurance risks into additional benefits.

## Progress

- [x] (2026-07-13T13:02:47Z) Read the user request, `PLANS.md`, and `AGENTS.md`.
- [x] (2026-07-13T13:02:47Z) Identified that `landing/sber_vs.py` imports `scanner.benefits` and derives `other_benefits` when the Excel cell is missing.
- [x] (2026-07-13T13:02:47Z) Remove landing-side benefit derivation and make missing values display as `Не найдено в доступных источниках`.
- [x] (2026-07-13T13:02:47Z) Harden `scanner/benefits.py` so insurance risks and core categories cannot enter `other_benefits`.
- [x] (2026-07-13T13:02:47Z) Add Excel provenance/conflict sheets with per-field source URL, source type, raw text/value, date, and conflict status.
- [x] (2026-07-13T13:02:47Z) Add regression tests required by the user.
- [x] (2026-07-13T13:02:47Z) Run the project self-check commands and record the result.

## Surprises & Discoveries

- Observation: The landing already reads the workbook summary, but still has a fallback that derives `other_benefits` from other Excel fields when the summary cell is empty.
  Evidence: `landing/sber_vs.py` imports `other_benefits_text` and calls it in `load_summary_rows`.
- Observation: Regenerating Excel after adding PDF sources exposed illegal control characters from a malformed/binary PDF extraction path.
  Evidence: `openpyxl.utils.exceptions.IllegalCharacterError` occurred while writing a source-derived value; `report/excel_writer.py` now strips openpyxl-illegal characters before writing cells.
- Observation: Sber level 1 contained a non-benefit fragment `Включено исследование до 1 — тыс.` in "Другие привилегии".
  Evidence: Direct workbook inspection after regeneration showed that line; the normalizer now treats `включено исследование...` fragments as too generic and keeps the real `Здоровье` option.

## Decision Log

- Decision: Keep normalization before Excel in `main.py` and `report/excel_writer.py`, but remove all landing-side normalization.
  Rationale: The requested architecture allows parsing and normalization before `competitor_analysis.xlsx`; it forbids the HTML generator from creating user-facing values after Excel.
  Date/Author: 2026-07-13 / Codex
- Decision: Store per-cell provenance in new service sheets rather than expanding every public cell with raw text.
  Rationale: The summary remains readable for the landing and users, while `Провенанс значений` and `Конфликты источников` provide URL, source type, raw text/value, date, and conflict status for audit.
  Date/Author: 2026-07-13 / Codex

## Outcomes & Retrospective

Implemented. The landing now embeds JSON only from Excel summary cells and does not call the benefit normalizer. The Excel workbook has `Провенанс значений` and `Конфликты источников`. The Sber level 1 "Другие привилегии" output contains only Самокат, Здоровье, Питомцы, Авто, and СберПрайм, plus the selection rule. Tests pass and the published HTML was rebuilt successfully.

## Context and Orientation

`main.py` scans sources, merges fields, computes derived `other_benefits`, writes history, then calls `report/excel_writer.py` to produce `output/competitor_analysis.xlsx`. `landing/sber_vs.py` reads the `Сводная` sheet from that workbook and embeds JSON in `output/sber_vs_banks.html`. `scanner/benefits.py` converts normalized source fields such as `always_included_options`, `selectable_options`, `auto`, and `ecosystem` into a display list for "Другие привилегии".

## Plan of Work

First, edit `landing/sber_vs.py` so it only reads workbook cells. Remove the import of `scanner.benefits.other_benefits_text` and the fallback that fills `other_benefits` from `row["fields"]`. Use `NOT_FOUND_AVAILABLE` for missing display text.

Second, edit `scanner/benefits.py` so benefit IDs are stable English identifiers for the Sber regression set and so insurance-risk markers are rejected before an item is added. "Здоровье" remains allowed when it is a banking option with telemedicine, analyses, or studies; insurance context such as assistance, visa, baggage, flight delay, ski, and snowboard remains blocked.

Third, extend `report/excel_writer.py` with service sheets that expose provenance and conflicts per normalized cell without changing the public summary layout.

Fourth, add tests in `tests/test_premium_structured.py` for the required landing and Sber level 1 regressions.

## Concrete Steps

Run commands from `/Users/ilyashmarov/Documents/analyst/bank_analyst`.

After edits, run:

    .venv/bin/python main.py --list-sources
    .venv/bin/python -m unittest discover -s tests
    .venv/bin/python main.py --build-sber-vs

## Validation and Acceptance

The tests must pass. The new landing test must show that a missing `Другие привилегии` Excel cell stays missing in embedded JSON instead of being synthesized from other fields. The Sber level 1 tests must prove that the exact additional-benefit IDs are `sber_prime`, `samokat`, `health`, `pets`, and `auto`, and that insurance-risk IDs or text do not leak.

## Idempotence and Recovery

All edits are regular source changes inside the repository. Re-running the commands is safe. If HTML output changes, it is generated from the current Excel workbook and can be regenerated with `--build-sber-vs`.

## Artifacts and Notes

No validation output yet.

Validation output:

    .venv/bin/python -m unittest discover -s tests
    Ran 7 tests in 0.014s
    OK

    .venv/bin/python main.py --list-sources
    exited 0 and listed all banks plus the configured premiumbanking.info aggregators.

    .venv/bin/python main.py --build-sber-vs
    Лендинг Сбер VS банки собран: /Users/ilyashmarov/Documents/analyst/bank_analyst/output/sber_vs_banks.html
    Банков: 7; уровней пакетов: 34
    Publication completed successfully.

Revision note 2026-07-13 / Codex: Completed the plan and recorded the validation evidence so the next reader can verify the behavior without prior chat context.

## Interfaces and Dependencies

No new dependencies are needed. Existing modules used are `openpyxl`, `scanner.merge.field_value`, `scanner.sources.NOT_FOUND`, and `scanner.sources.NOT_FOUND_AVAILABLE`.
