# Integrate premium changes into the Sber comparison landing

This ExecPlan is a living document. It follows `PLANS.md` in this repository.

## Purpose / Big Picture

The user wants one main HTML landing, `output/sber_vs_banks.html`, to contain both the bank comparison workflow and the existing premium changes workflow. After this change, the top of the comparison page will include a collapsed “Последние изменения” panel that reuses the same changes data, filters, cards, CSS, and JavaScript behavior currently used by `premium_changes.html`. When a selected comparison level has matching changes, the relevant comparison row will show a badge, highlight, and a “Показать изменение” button that opens the same change card format.

## Progress

- [x] (2026-07-14T00:00:00Z) Read `AGENTS.md`, `PLANS.md`, `landing/sber_vs.py`, `landing/premium_changes.py`, and inspected the generated HTML structure for both pages.
- [x] (2026-07-14T00:00:00Z) Refactor `landing/premium_changes.py` into a reusable component without changing the underlying change data source.
- [x] (2026-07-14T00:00:00Z) Embed the changes component into `landing/sber_vs.py` after the hero stats as a collapsed panel.
- [x] (2026-07-14T00:00:00Z) Use one JSON payload in `sber_vs_banks.html` containing both comparison data and changes data.
- [x] (2026-07-14T00:00:00Z) Add row-level change indicators, highlighting, and “Показать изменение” using existing change cards.
- [x] (2026-07-14T00:00:00Z) Rebuild HTML and run tests/self-check commands.

## Surprises & Discoveries

- Observation: Both generated pages use generic names such as `id="data"`, `.stats`, `.banks`, and `.bank`.
  Evidence: `output/sber_vs_banks.html` uses `.banks` for bank picker chip rows, while `output/premium_changes.html` uses `.banks` and `.bank` for the change history layout. Directly concatenating the HTML/CSS/JS would make the changes filter hide comparison bank picker blocks.
- Observation: Browser automation could not launch Chromium in this sandbox because Playwright browsers are not installed.
  Evidence: Playwright reported `Executable doesn't exist at /Users/ilyashmarov/Library/Caches/ms-playwright/.../chrome-headless-shell`. JavaScript syntax was still checked with `node --check`.

## Decision Log

- Decision: Keep a single `id="data"` JSON payload in `sber_vs_banks.html`, shaped as `{comparison, changes}`.
  Rationale: This satisfies the “one source of data” requirement and avoids duplicating the changes array in a second script tag.
  Date/Author: 2026-07-14 / Codex
- Decision: Scope the reusable changes UI under `.changes-app` and make the existing filter functions operate on that root.
  Rationale: It preserves the existing changes interface while preventing class and DOM selector collisions with the comparison picker.
  Date/Author: 2026-07-14 / Codex

## Outcomes & Retrospective

Completed. `sber_vs_banks.html` now contains a collapsed “Последние изменения” panel after the hero statistics, reusing the Excel-backed change data and card/filter implementation from `premium_changes.py`. The page emits one JSON payload with `comparison` and `changes`. Comparison rows now detect matching changes by bank, product, and category, then show a badge, highlight, inline “Было ↓ Стало” summary, and a “Показать изменение” button that clones the existing change card from the embedded history panel.

## Context and Orientation

`landing/premium_changes.py` currently owns the Excel-backed changes workflow: `load_changes`, `group_by_bank`, `_render_bank`, `_render_change`, `_CSS`, and `_JS`. `landing/sber_vs.py` owns the Excel-backed comparison workflow and currently embeds only a JSON list of comparison banks in `<script id="data">`. Both modules generate standalone HTML. The integration should be made in the Python generators, not by manually editing generated output, because `main.py --build-sber-vs` rewrites `output/sber_vs_banks.html`.

## Plan of Work

First, refactor `landing/premium_changes.py` to expose reusable functions that render the changes header, filters, bank sections, card markup, CSS, and JavaScript as a component. The standalone `premium_changes.html` will call the same functions, so there is one implementation.

Second, update `landing/sber_vs.py` so it loads changes from the same workbook, groups them through `premium_changes.group_by_bank`, renders the collapsed panel after hero stats, and emits one JSON object with `comparison` and `changes`.

Third, extend the comparison JavaScript to build an index from the shared `changes` payload. For each selected level and attribute, it will match changes by bank, product name, and category, then add the visual badge, row highlight, and “Показать изменение” button. The button will reuse the same client-side change-card renderer as the panel.

Fourth, merge CSS by including comparison styles plus the reusable, scoped changes styles in one style tag. Merge JavaScript by including comparison logic plus the reusable changes functions in one script tag.

## Concrete Steps

Run commands from `/Users/ilyashmarov/Documents/analyst/bank_analyst`.

After edits:

    .venv/bin/python main.py --build-premium-changes
    .venv/bin/python main.py --build-sber-vs
    .venv/bin/python -m unittest discover -s tests

If a local browser check is needed, serve the output directory:

    python3 -m http.server 8765 -d output

Then open `http://localhost:8765/sber_vs_banks.html` and verify the collapsed changes panel, the comparison picker, and row-level change indicators.

## Validation and Acceptance

The generated `sber_vs_banks.html` must contain one `<script id="data">` with both comparison and changes. The changes panel must be collapsed by default and must expose bank/category/period filters that operate only on the changes panel. Existing bank and level pickers must still select levels and render comparison rows. Rows with matching changes must have a visible badge, highlight, and a “Показать изменение” button that inserts the existing change card format.

## Idempotence and Recovery

All output HTML files are generated artifacts and can be rebuilt. The source changes are limited to `landing/premium_changes.py`, `landing/sber_vs.py`, tests, and this ExecPlan. Re-running the build commands should produce the same structure from the current Excel workbook.

## Artifacts and Notes

Validation output:

    .venv/bin/python main.py --build-premium-changes
    Лендинг изменений премиальных программ собран: /Users/ilyashmarov/Documents/analyst/bank_analyst/output/premium_changes.html
    Банков: 7; изменений: 311; ошибок: 0

    .venv/bin/python main.py --build-sber-vs
    Лендинг Сбер VS банки собран: /Users/ilyashmarov/Documents/analyst/bank_analyst/output/sber_vs_banks.html
    Банков: 7; уровней пакетов: 34
    Publication failed because the sandbox cannot write to ../bank_cite/index.html.

    .venv/bin/python -m unittest discover -s tests
    Ran 65 tests in 23.635s
    OK

    Static HTML checks:
    data_scripts 1
    comparison 7 levels 34
    changes 7 311
    panel True
    old_filter_ids False
    scoped_filters True
    row_integration True
    matched_attr_rows 337

    node --check output/_sber_vs_inline_check.js
    exited 0

Revision note 2026-07-14 / Codex: Completed integration, recorded sandbox publication/browser limitations, and documented validation evidence.

## Interfaces and Dependencies

No new Python dependencies are required. Existing `openpyxl` reads `output/competitor_analysis.xlsx`. Existing JavaScript remains vanilla browser JavaScript.
