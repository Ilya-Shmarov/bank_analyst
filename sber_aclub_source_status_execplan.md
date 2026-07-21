# Fix Sber Availability and A-Club Source Coverage

This ExecPlan is a living document. It follows `PLANS.md` in the repository root.

## Purpose / Big Picture

The user-visible Excel report and Sber VS banks landing should show whether Sber privileges are permanently included or selectable based on source sections, not on the word "option". The A-Club tier should use the official A-Club URL as the first-priority source, fall back to PremiumBanking.info when the official site is blocked, and avoid leaking Alfa Only facts into A-Club. A human can verify the result by running the parser tests, rebuilding the Excel report and landing, and checking that Sber levels 4-6 no longer show lounge, taxi, or restaurants with the wrong selectable status.

## Progress

- [x] (2026-07-13 22:25 MSK) Read the attached task, `AGENTS.md`, `PLANS.md`, and the relevant parser, source, curated, Excel, and landing modules.
- [x] (2026-07-13 22:30 MSK) Fetched current PBI Sber and Alfa pages. PBI is accessible and contains the requested Sber and A-Club facts. `https://alfabank.ru/a-club/` returns HTTP 403 with an anti-bot message.
- [x] (2026-07-13 22:36 MSK) Fixed parser normalization so always-included options cannot survive in `selectable_options`.
- [x] (2026-07-13 22:37 MSK) Registered the official A-Club URL and adjusted A-Club curated facts to use A-Club/PBI facts only.
- [x] (2026-07-13 22:39 MSK) Added regression tests for Sber availability, SberPrime, A-Club source registration and structured fields, no A-Club/Alfa Only merge, and no HTML hardcode.
- [x] (2026-07-13 22:49 MSK) Ran targeted tests, rebuilt required outputs, and checked local HTML payload for Sber and A-Club acceptance conditions.

## Surprises & Discoveries

- Observation: The PBI Sber overview already places level 4 lounge and restaurants, and level 5-6 lounge/taxi/restaurants, under `Всегда включено`. The parser then re-adds some of them to `selectable_options` through a generic embedded regex that matches any text beginning with `опция`.
  Evidence: Parsing `https://premiumbanking.info/sber` showed `sber_first_5` with `always_included_options` containing taxi and restaurants while `selectable_options` also contained `опция «Такси»` and `опция «Рестораны»`.
- Observation: `https://alfabank.ru/a-club/` is the correct official URL to register, but direct HTTP fetch returns 403 anti-bot content in this environment.
  Evidence: `requests.get("https://alfabank.ru/a-club/")` returned status 403 and an HTML body headed `Forbidden`.

## Decision Log

- Decision: Fix Sber statuses in `scanner/parse.py` by preserving the source section classification and reconciling duplicate option names after embedded extraction.
  Rationale: This keeps the chain source section -> normalized availability -> Excel -> HTML and avoids special-casing bank/tier names in the landing.
  Date/Author: 2026-07-13 / Codex.
- Decision: Register `/a-club/` as the first official A-Club source but rely on PBI fallback for structured A-Club facts when the official page is blocked.
  Rationale: The project source policy requires official sources first, while anti-bot blocks must be respected and unavailable official data must not be invented.
  Date/Author: 2026-07-13 / Codex.

## Outcomes & Retrospective

Completed. Sber levels 4-6 now preserve source-section availability through parsing, Excel, and HTML. A-Club has the official `/a-club/` source registered first, falls back to PBI when the official page is blocked, and no longer uses Alfa Only curated facts as A-Club tariff facts. Excel list fields are preserved as multiline lists so the HTML landing can consume them as separate benefits.

## Context and Orientation

`scanner/sources.py` defines banks, tiers, and source URLs. `scanner/parse.py` extracts structured fields from PremiumBanking.info pages. `scanner/merge.py` chooses the final value by source priority and quality. `scanner/benefits.py` converts normalized always/selectable/ecosystem fields into the displayed `Другие привилегии` list. `report/excel_writer.py` writes `output/competitor_analysis.xlsx`, including provenance and conflict sheets. `landing/sber_vs.py` reads only the Excel workbook to build `output/sber_vs_banks.html`.

In this repository, an "option" is just source wording such as `опция «Такси»`. Availability must come from source structure. Text under `Всегда включено` means `always_included`; text under `Дополнительно на выбор` or `Доступно на выбор` means `selectable`; ambiguous text remains `unknown`.

## Plan of Work

First, edit `scanner/parse.py` so `_assign_level_options` annotates option text from the always-included section with an explicit marker and a new reconciliation step removes any option already found in `always_included_options` from `selectable_options`. This directly addresses the parser bug without HTML special cases.

Second, edit `scanner/sources.py` to add `https://alfabank.ru/a-club/` to priority official URLs and make the A-Club tier use it before legacy A-Club URLs. Edit `scanner/curated.py` so A-Club curated facts do not cite Alfa Only facts as A-Club tariff facts, and use PBI for confirmed fallback values and confirmed not-found states where PBI has no permanent field.

Third, extend tests in `tests/test_premium_structured.py` and `tests/test_source_policy.py` to cover the requested regressions. The tests should use source-shaped HTML fixtures and registered source configuration, not live network calls.

Finally, run `.venv/bin/python -m pytest tests`, `.venv/bin/python main.py --list-sources`, and rebuild the Sber VS landing. If scanner data changes are needed in the workbook, run the narrow bank scan where practical and then rebuild.

## Concrete Steps

Work from `/Users/ilyashmarov/Documents/analyst/bank_analyst`.

Run:

    .venv/bin/python -m unittest discover -s tests
    .venv/bin/python main.py --list-sources
    .venv/bin/python main.py --scan-bank sber
    .venv/bin/python main.py --scan-bank alfa
    .venv/bin/python main.py --build-sber-vs

## Validation and Acceptance

The tests should show that parsing a Sber PBI-shaped overview produces:

Level 4: lounge and restaurants in `always_included_options`, taxi in `selectable_options`, and no lounge/restaurants in `selectable_options`.

Level 5 and 6: lounge, taxi, and restaurants in `always_included_options`, and none of those three in `selectable_options`.

The source tests should show that A-Club registers `https://alfabank.ru/a-club/`, that Alfa Only URLs are not used as A-Club tariff fact sources, and that missing A-Club cashback/deposit facts remain `не найдено` rather than being filled from promotions or general Alfa products.

The rebuilt HTML should be generated from the Excel workbook only and contain no Sber tier hardcode for hiding badges.

## Idempotence and Recovery

All edits are code and test changes. Re-running the tests and report builders is safe. If an external source is blocked during a scan, the fetcher records the unavailable source and the merge layer uses lower-priority sources without inventing facts.

## Artifacts and Notes

Current live source checks:

    https://premiumbanking.info/sber -> HTTP 200, contains Sber levels and SberPrime.
    https://premiumbanking.info/alfabank -> HTTP 200, contains A-Club fields.
    https://premiumbanking.info/alfabank/5 -> HTTP 200, A-Club level page.
    https://alfabank.ru/a-club/ -> HTTP 403 Forbidden anti-bot response.

Validation transcript:

    .venv/bin/python -m unittest discover -s tests
    Ran 63 tests in 15.298s
    OK

    .venv/bin/python main.py --list-sources
    listed Sber and Alfa-Bank tiers including alfa_aclub.

    .venv/bin/python main.py --scan-bank sber
    Источников успешно: 30, с ошибками: 12; Полей заполнено данными: 114.

    .venv/bin/python main.py --scan-bank alfa
    Источников успешно: 19, с ошибками: 10; Полей заполнено данными: 72.

    .venv/bin/python main.py --build-sber-vs
    Локальный HTML собран. Existing publication copy attempted by the CLI failed with Operation not permitted for ../bank_cite/index.html; no GitHub push was performed.

## Interfaces and Dependencies

No CLI interface changes. No publisher or GitHub Pages changes. The parser continues to return the existing `BANK_FIELDS` keys. The landing continues to consume only the Excel summary and provenance sheets through `openpyxl`.
