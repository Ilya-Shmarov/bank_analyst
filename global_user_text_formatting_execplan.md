# Global User-Visible Text Formatting

This ExecPlan is a living document and follows `PLANS.md`.

## Purpose / Big Picture

Every user-visible string in the bank comparison Excel and HTML must be readable for every bank and current or future tier. Users should not see raw source separators, cut words, broken punctuation, `null`/`None`/`NaN`, unbalanced parentheses, or technical fragments. The observable result is that `output/competitor_analysis.xlsx` user-facing sheets and `output/sber_vs_banks.html` embedded JSON pass a global text-quality validator.

## Progress

- [x] (2026-07-13T14:11:03Z) Read the new request and reviewed current formatter, Excel writer, and landing generators.
- [x] (2026-07-13T14:23:00Z) Add global formatter aliases and validation functions.
- [x] (2026-07-13T14:36:00Z) Route all user-visible Excel/HTML strings through validation.
- [x] (2026-07-13T14:42:00Z) Fix benefit-list formatting so bullets remain separate after normalization.
- [x] (2026-07-13T14:55:00Z) Add global parameterized tests across all current banks and fields.
- [x] (2026-07-13T15:10:00Z) Regenerate Excel and HTML locally without publishing.
- [x] (2026-07-13T15:15:00Z) Record validation evidence and final outcomes.

## Surprises & Discoveries

- Observation: Previous formatting normalized the whole `Другие привилегии` multiline value before splitting lines, which merged bullets into one item in HTML.
  Evidence: Generated JSON showed one benefit description containing several `•` markers.
- Observation: Old changelog values are also user-visible and can contain historic raw separators.
  Evidence: `unittest` failed on `Изменения / row 16 / col 7: contains pipe separator`.
- Observation: Some raw parsed PDF fragments are binary-like and should not be shown as readable facts.
  Evidence: The validator caught replacement characters and unreadable glyph sequences in user-facing Excel cells.
- Observation: URLs can legitimately end with `/`.
  Evidence: `https://plus.yandex.ru/` was flagged by the generic terminal-character rule until URL endings were exempted.

## Decision Log

- Decision: Raw provenance text remains preserved in service fields, while user-facing summary cells, bank sheets, and HTML payload are formatted and validated.
  Rationale: The user requires readable output without losing full source text; provenance is the right place to preserve raw source material.
  Date/Author: 2026-07-13 / Codex
- Decision: Source conflicts no longer repeat raw alternative values in user-facing comments; they point to `Конфликты источников`.
  Rationale: Conflict comments are visible in Excel and were leaking low-quality raw PDF text.
  Date/Author: 2026-07-13 / Codex
- Decision: Premium changes and premium reviews use the same formatter at HTML escaping boundaries.
  Rationale: This keeps all project HTML output on the same display-text rules without changing scraping or data priority.
  Date/Author: 2026-07-13 / Codex

## Outcomes & Retrospective

Completed. `scanner/formatting.py` is now the shared display-text API and validator. `report/excel_writer.py` validates user-facing Excel sheets before save. `landing/sber_vs.py` validates every generated compare attribute and preserves full details through `Провенанс значений`. `landing/premium_changes.py` and `landing/premium_reviews.py` normalize user text before escaping; review excerpts use complete summaries instead of raw slicing.

Validation completed:

    .venv/bin/python -m unittest discover -s tests
    Ran 26 tests in 9.780s
    OK

    .venv/bin/python main.py --list-sources
    exit code 0

    .venv/bin/python -c '... write_report(...) ...'
    exit code 0

    .venv/bin/python -c '... build_sber_vs_landing(...) ...'
    {'output': 'output/sber_vs_banks.html', 'banks': 7, 'levels': 34}

    .venv/bin/python main.py --build-premium-changes
    Банков: 7; изменений: 39; ошибок: 0

    .venv/bin/python main.py --build-premium-reviews
    Отзывов в базе: 68 (новых: 0); источников со сбоями: 0

    Excel validation: excel_texts 14016; excel_problems 0
    Sber VS HTML validation: html_texts 1043; html_problems 0; payload_pipe False; bad_number False; word_ellipsis False; details_count 64

No publisher command was run. No push was run.

## Context and Orientation

`scanner/formatting.py` is the shared formatter. `report/excel_writer.py` writes `output/competitor_analysis.xlsx`. `landing/sber_vs.py` reads that workbook and writes `output/sber_vs_banks.html`. Tests live in `tests/test_premium_structured.py`.

## Plan of Work

Extend `scanner/formatting.py` with the requested names `normalize_user_text`, `normalize_list_separators`, `format_natural_list`, and `validate_user_visible_text`. Use the validator in Excel writer for user-facing sheets and in `landing/sber_vs.py` for embedded JSON attributes. Keep service raw text available in `Провенанс значений`.

## Concrete Steps

Run from `/Users/ilyashmarov/Documents/analyst/bank_analyst`:

    .venv/bin/python -m unittest discover -s tests
    .venv/bin/python -c 'from pathlib import Path; from scanner.diff import load_history; from report.excel_writer import write_report; write_report(load_history(Path("data/history.json")), Path("output/competitor_analysis.xlsx"))'
    .venv/bin/python -c 'from pathlib import Path; from landing.sber_vs import build_sber_vs_landing; print(build_sber_vs_landing(Path("output/competitor_analysis.xlsx"), Path("output/sber_vs_banks.html")))'

## Validation and Acceptance

Tests must pass. Additional scripts must confirm zero `|` in user-visible Excel sheets, zero `|` in HTML JSON payload, no word plus ellipsis patterns, no bad terminal characters, balanced parentheses, no null tokens, and no double spaces for all current banks.

## Idempotence and Recovery

All commands are safe to rerun. No publisher command is used in this plan.

## Artifacts and Notes

Generated artifacts:

- `output/competitor_analysis.xlsx`
- `output/sber_vs_banks.html`
- `output/premium_changes.html`
- `output/premium_reviews_report_2026-07-13.html`

## Interfaces and Dependencies

No new dependencies. The formatter API must expose:

    normalize_user_text(text: str) -> str
    normalize_list_separators(text: str) -> str
    cleanup_punctuation(text: str) -> str
    make_complete_summary(text: str, max_length: int = 240) -> str
    split_summary_and_details(text: str, max_length: int = 240) -> dict
    format_natural_list(items: list[str]) -> str
    validate_user_visible_text(text: str) -> list[str]
