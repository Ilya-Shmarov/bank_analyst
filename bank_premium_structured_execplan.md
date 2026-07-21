# Structured Premium Banking Data Pipeline

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document follows `PLANS.md` in the repository root.

## Purpose / Big Picture

The project already scans premium banking sources, merges them, writes `output/competitor_analysis.xlsx`, and generates `output/sber_vs_banks.html`. The current pipeline loses important source details because several distinct benefits are represented as one text field: taxi and restaurants are combined, selectable options are mixed with always-included benefits, and exact travel insurance terms are reduced during scoring and HTML display. After this change, the same daily CLI workflow will preserve more source detail end to end: sources to parser, merge, Excel, scoring, and HTML. A user can verify the result by rebuilding the Excel report and Sber comparison page, then checking that segment labels are gone from HTML cards while entry conditions remain, taxi and restaurants are separate, and exact insurance wording is retained.

## Progress

- [x] (2026-07-10T13:21:43Z) Read the user request, `AGENTS.md`, `PLANS.md`, and the core pipeline files that define fields, PBI parsing, merging, Excel generation, HTML generation, and scoring.
- [x] (2026-07-10T13:40:00Z) Inspected `main.py`, `scanner/fetch.py`, `scanner/curated.py`, existing output workbook, and source definitions. Confirmed daily CLI commands remain in `main.py` and publication is only triggered by the existing Sber VS build/full-scan path.
- [x] (2026-07-10T13:48:00Z) Extended `scanner/sources.py` with separate `taxi`, `restaurants`, `always_included_options`, `selectable_options`, and `selection_rules` fields while keeping `taxi_restaurants` as a compatibility scoring field.
- [x] (2026-07-10T13:58:00Z) Extended `scanner/parse.py` PBI parsing so transport text is split into taxi and restaurants, option snippets are classified as always-included or selectable, and exact insurance text is preserved.
- [x] (2026-07-10T14:03:00Z) Adjusted Excel display of missing values to "Не найдено в доступных источниках" while keeping the internal sentinel compatible with merge/diff logic.
- [x] (2026-07-10T14:08:00Z) Updated `scanner/scoring.py` to keep the old combined taxi/restaurants weight but derive it from split fields using the maximum monthly count instead of summing taxi rides and restaurant checks. Selectable auto now gets a conservative score.
- [x] (2026-07-10T14:12:00Z) Updated `report/excel_writer.py` so summary and bank sheets show separate taxi/restaurants and option rows, skip the compatibility row, preserve source/date annotations, and remove reference-only fields from manual checks.
- [x] (2026-07-10T14:20:00Z) Updated `landing/sber_vs.py` so embedded JSON and comparison UI hide segment labels in selected cards, keep entry conditions, show split taxi/restaurants, show exact insurance text, avoid technical empty values, and keep mobile `data-label` cells.
- [x] (2026-07-10T14:25:00Z) Added `tests/test_premium_structured.py` with parser, scoring, and generated HTML assertions.
- [x] (2026-07-10T14:35:00Z) Ran source listing, unit tests, Sber scan, Alfa scan, Sber VS HTML generation, and targeted workbook/HTML inspections.

## Surprises & Discoveries

- Observation: `PremiumBankingInfoParser` already exists and is selected for `source_id == "pbi"` or `premiumbanking.info` URLs. It currently maps restaurant, taxi, transfer, and cafe labels into one `taxi_restaurants` field.
  Evidence: `scanner/parse.py` has `LABEL_MAP` entry `(("ресторан", "такси", "трансфер", "кафе"), "taxi_restaurants")`.
- Observation: The current scorer contains a combined `taxi_restaurants` category with weight `0.10` and sums all text patterns matching "N в мес".
  Evidence: `scanner/scoring.py` defines `WEIGHTS["taxi_restaurants"] = 0.10` and `_score_taxi_rest` returns `sum(counts)`.
- Observation: Official Sber pages returned JS-required placeholders without Playwright, while PBI tier pages loaded and produced structured fields.
  Evidence: `main.py --scan-bank sber` logged Sber official sources as `js_required` and PBI as `[ok] ... structured`.
- Observation: Official Alfa Only returned HTTP 403, Banki.ru is blocked by robots.txt, and Bankiros produced zero relevant fields. PBI supplied insurance and transport details but did not expose cashback/deposit facts.
  Evidence: `main.py --scan-bank alfa` logged `alfabank.ru/everyday/alfa-only/` as HTTP 403, Banki.ru as `blocked_robots`, Bankiros as `0 полей`, and PBI as structured with 10 fields per Alfa Only level.
- Observation: PBI tier URLs are the safe source for per-level facts. The overview URLs without a numeric level are already used by the premium changes landing, but using them as direct tier sources would risk mixing conditions across levels unless a separate section selector is implemented.
  Evidence: raw archive contains `data/raw/2026-07-10/sber_first_4__pbi.html`, `alfa_only_1__pbi.html`, and other per-tier PBI snapshots; overview raw exists as `premiumbanking_info.html` for the aggregator path.

## Decision Log

- Decision: Keep `publisher.py` and the GitHub Pages publication mechanism untouched.
  Rationale: The user explicitly requested not to change publication, and the HTML generator already produces a standalone file suitable for Pages.
  Date/Author: 2026-07-10 / Codex.
- Decision: Preserve a backward-compatible `taxi_restaurants` field for scoring and older consumers, but introduce first-class `taxi` and `restaurants` fields for Excel and HTML display.
  Rationale: The existing score weight is product-defined as a combined category; splitting weights would invent a product decision. Separate display fields prevent false UI aggregation while the old score remains comparable.
  Date/Author: 2026-07-10 / Codex.
- Decision: Do not add overview PBI bank pages as direct tier sources in this change.
  Rationale: The existing tier URLs such as `/sber/4` and `/alfabank/2` preserve per-level boundaries. The overview URLs are present in the changes landing; parsing overview pages into tiers safely requires a dedicated selector for "Премиальные уровни", which is beyond this minimal safe change.
  Date/Author: 2026-07-10 / Codex.

## Outcomes & Retrospective

Implemented the structured split across parser, scoring, Excel, and HTML. Unit tests pass. `--scan-bank sber` and `--scan-bank alfa` regenerated `output/competitor_analysis.xlsx`; `--build-sber-vs` regenerated `output/sber_vs_banks.html`. The build command attempted the existing publication step and failed to copy to `../bank_cite/index.html` due to sandbox permissions, but the local HTML artifact was generated successfully and `publisher.py` was not changed.

## Context and Orientation

`scanner/sources.py` is the source registry and field model. `BANK_FIELDS` defines which bank fields are extracted and later written into Excel. Each bank tier has `sources`, and each source has `source_id` such as `official` or `pbi`. `SOURCE_META` defines source priorities.

`scanner/fetch.py` downloads pages. `scanner/parse.py` converts HTML to field dictionaries. `GenericParser` extracts snippets by keyword. `PremiumBankingInfoParser` is the structured parser for `premiumbanking.info`. It reads definition-list style label/value pairs and maps labels to field IDs.

`scanner/merge.py` merges parsed sources and curated facts. It chooses the best candidate by quality and source priority while keeping alternatives and divergence notes.

`scanner/scoring.py` computes the project-owned score. The current category weights sum to 1.0. The combined taxi/restaurants category has weight 0.10 and must remain compatible until a product decision changes the weights.

`report/excel_writer.py` writes the workbook. It uses `BANK_FIELDS` for summary and per-bank detail rows. `landing/sber_vs.py` reads the workbook summary and generates the static comparison HTML. `main.py` wires CLI commands.

## Plan of Work

First, inspect the remaining pipeline files and the current workbook to understand exact headers, source URLs, and any existing curated facts for Alfa cashback/deposits or insurance.

Next, extend the data model in `scanner/sources.py`. Add field IDs for `taxi`, `restaurants`, `always_included_options`, `selectable_options`, and `selection_rules`. Keep `taxi_restaurants` for compatibility but label it as a scoring compatibility field or populate it from the split fields.

Then, update `PremiumBankingInfoParser` in `scanner/parse.py`. It should still parse definition-list pages, but route taxi labels to `taxi`, restaurant labels to `restaurants`, option labels to `selectable_options`, always-included labels to `always_included_options`, and insurance labels to `insurance` without shortening exact `$150/35 тыс`, day count, or assistance names. It should also populate `taxi_restaurants` from taxi and restaurant raw texts for legacy scoring only.

After parser changes, update scoring so the old combined category derives from `taxi` and `restaurants` when present. For UI and Excel, never display that combined field as the user-facing row. For selectable auto text, avoid treating it as always included; leave the score conservative and document that the auto weight needs a product decision.

Then, update Excel and HTML generation to use the new fields, preserve sources/dates in Excel annotations, avoid adding reference-only gaps to manual checks, and hide segment labels in HTML headers while keeping entry conditions as a comparison row.

Finally, add tests that exercise parser fixtures, scoring compatibility, Excel headers, and generated HTML JSON/DOM string assertions. Run project commands and inspect generated artifacts.

## Concrete Steps

Run all commands from `/Users/ilyashmarov/Documents/analyst/bank_analyst`.

Use `rg --files`, `sed`, and targeted Python/openpyxl inspection for research. Use `apply_patch` for manual source edits.

Validation commands planned:

    .venv/bin/python main.py --list-sources
    .venv/bin/python -m pytest
    .venv/bin/python main.py --scan-bank sber
    .venv/bin/python main.py --build-sber-vs

If `pytest` is not installed, use the repository's available Python test runner or add tests that can run through `python -m unittest`.

## Validation and Acceptance

Acceptance is behavioral. The generated `output/sber_vs_banks.html` must not show segment labels under selected level names. It must still show the "Условия входа" row. It must contain separate "Такси" and "Рестораны" rows and valid embedded JSON.

The generated `output/competitor_analysis.xlsx` must keep the existing major sheets, include separate bank-sheet rows for "Такси" and "Рестораны", preserve source/date annotations, and not replace exact insurance terms with approximate coverage buckets in display cells.

Tests must cover at least parser separation for Sber-like and Alfa-like PBI snippets, selectable option status, segment removal in HTML, and workbook header/row structure.

## Idempotence and Recovery

All generation commands overwrite files from current `data/history.json` or scan output and can be repeated. No destructive git commands are needed. If a source fetch fails because of a remote block, tests based on local fixtures still prove parser and generator behavior. Do not edit `publisher.py`.

## Artifacts and Notes

Important current evidence:

    scanner/parse.py: PBI parser maps taxi/restaurants together.
    scanner/scoring.py: combined taxi/restaurants score uses one weight and sums monthly counts.
    landing/sber_vs.py: level payload includes `segment` and comparison fields include `taxi_restaurants`.

## Interfaces and Dependencies

The implementation uses the existing dependencies: `requests`, `beautifulsoup4`, `openpyxl`, and Python standard library. No new runtime dependency is planned.

The field IDs expected at completion are:

    taxi
    restaurants
    always_included_options
    selectable_options
    selection_rules
    taxi_restaurants

`taxi_restaurants` remains available for backward-compatible score calculation and historical consumers, but user-facing Excel and HTML should prefer `taxi` and `restaurants`.
