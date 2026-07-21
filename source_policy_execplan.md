# Source Policy Enforcement

This ExecPlan is a living document. It follows `PLANS.md` in the repository root and must be kept current while the source policy is implemented.

## Purpose / Big Picture

The project must have a permanent, written, and test-backed policy for bank data sources. After this change, future parser, Excel, and landing changes can be checked against one rule: official bank documents are first, PremiumBanking.info is second, other sources are third, and missing facts stay missing instead of being invented. A user can see this working by reading `AGENTS.md` and `SOURCE_POLICY.md`, running tests, and inspecting `output/competitor_analysis.xlsx` where every fact carries source provenance and source conflicts are logged.

## Progress

- [x] (2026-07-13 15:35Z) Read the attached policy request, `AGENTS.md`, and `PLANS.md`.
- [x] (2026-07-13 15:42Z) Inspected current source registry, parser dispatch, merge logic, Excel conflict sheets, and HTML generator.
- [x] (2026-07-13 15:50Z) Add permanent policy text to `AGENTS.md` and create `SOURCE_POLICY.md`.
- [x] (2026-07-13 15:57Z) Centralize priority URLs in `scanner/sources.py`.
- [x] (2026-07-13 16:05Z) Enforce source priority order in `scanner/merge.py` and preserve `(bank_id, tier_id, field_id)` provenance.
- [x] (2026-07-13 16:14Z) Add policy regression tests.
- [x] (2026-07-13 16:24Z) Regenerate Excel and HTML locally without publishing.
- [x] (2026-07-13 16:28Z) Record validation evidence and final outcomes.

## Surprises & Discoveries

- Observation: The existing merge sorted by parser quality before source priority.
  Evidence: `scanner/merge.py` used `candidates.sort(key=lambda c: (QUALITY_RANK[c["quality"]], _source_priority(c["source_id"])))`, which lets structured PremiumBanking.info beat an official snippet.
- Observation: `landing/sber_vs.py` already reads from `competitor_analysis.xlsx` and does not fetch sites.
  Evidence: `build_sber_vs_landing(workbook_path, output_path)` calls `load_summary_rows(workbook_path)` and builds the HTML payload from workbook rows.
- Observation: Old history contained an official-source field whose raw parsed text was binary garbage and normalized to `sources.NOT_FOUND`.
  Evidence: the VTB Prime+ deposits field normalized to `не найдено` while keeping old `source_id=official`; Excel display was adjusted so normalized not-found values become `Не найдено в доступных источниках` and status `not_found`.

## Decision Log

- Decision: Make source priority outrank parser quality in merge sorting.
  Rationale: The requested policy says official documents win over PremiumBanking.info even when PBI has more structured text.
  Date/Author: 2026-07-13 / Codex
- Decision: Keep `curated` as priority 0 only when it contains a manually verified source URL and date.
  Rationale: Existing curated facts are project-maintained verified facts; they still must carry provenance and should not become anonymous invented data.
  Date/Author: 2026-07-13 / Codex
- Decision: Store `source_type` in merged fields and map old `source_id` values through `SOURCE_META` when writing Excel.
  Rationale: Existing history does not always have `source_type`, but the policy requires a user-visible source type.
  Date/Author: 2026-07-13 / Codex
- Decision: Update the `Конфликты источников` sheet to explicit official and PremiumBanking.info columns.
  Rationale: The policy requires conflicts to show official value/URL, PBI value/URL, selected value, reason, and check date.
  Date/Author: 2026-07-13 / Codex

## Outcomes & Retrospective

Completed. The policy is now durable in `AGENTS.md` and `SOURCE_POLICY.md`, priority URLs are centralized in `scanner/sources.py`, merge source ordering now prefers source priority over parser quality, merged facts carry `bank_id`, `tier_id`, `field_id`, and `source_type`, Excel conflict/provenance output exposes policy fields, and regression tests cover the requested source-policy cases.

Validation:

    .venv/bin/python -m unittest discover -s tests
    Ran 41 tests in 13.536s
    OK

    .venv/bin/python main.py --list-sources
    exit code 0

    .venv/bin/python -c 'from pathlib import Path; from scanner.diff import load_history; from report.excel_writer import write_report; write_report(load_history(Path("data/history.json")), Path("output/competitor_analysis.xlsx"))'
    exit code 0

    .venv/bin/python -c 'from pathlib import Path; from landing.sber_vs import build_sber_vs_landing; print(build_sber_vs_landing(Path("output/competitor_analysis.xlsx"), Path("output/sber_vs_banks.html")))'
    {'output': 'output/sber_vs_banks.html', 'banks': 7, 'levels': 34}

No publisher command was run. No git push was run. `publisher.py` was not edited.

## Context and Orientation

The source registry is `scanner/sources.py`. It defines `SOURCE_META`, constants for official PDF URLs, `BANKS`, `AGGREGATORS`, and `tier_sources(bank, tier)`. The parser dispatcher is `scanner/parse.py`, where PremiumBanking.info receives the structured parser and other pages use keyword snippets. The merge layer is `scanner/merge.py`; it chooses the final field value from parsed sources and curated facts. Excel output is `report/excel_writer.py`, including the `Провенанс значений` and `Конфликты источников` sheets. The Sber VS landing is `landing/sber_vs.py` and should continue to read user-facing data from Excel only.

## Plan of Work

First, write the source policy into durable project files: append a `## Source policy for bank data` section to `AGENTS.md` and create `SOURCE_POLICY.md` with the full source hierarchy, fallback rules, conflict rules, strict tier binding, Excel-to-HTML rule, category rules, and test requirements.

Second, centralize the priority source URLs in `scanner/sources.py` as named dictionaries/lists that tests can inspect. The existing tier sources already contain these URLs, so the change is additive and does not rewrite every tier by hand.

Third, update `scanner/merge.py` so source priority is evaluated before parser quality. Add `bank_id`, `tier_id`, and `field_id` to merged fields and empty fields. This makes the required minimal provenance key explicit in each fact.

Fourth, add regression tests with the requested names. The tests will use small synthetic parsed-source inputs so they prove the policy without depending on live network or PDF parsing.

Finally, run the test suite, `main.py --list-sources`, regenerate local Excel and Sber VS HTML, and inspect `git status --short`. Do not touch `publisher.py` and do not push.

## Concrete Steps

Run commands from `/Users/ilyashmarov/Documents/analyst/bank_analyst`:

    .venv/bin/python -m unittest discover -s tests
    .venv/bin/python main.py --list-sources
    .venv/bin/python -c 'from pathlib import Path; from scanner.diff import load_history; from report.excel_writer import write_report; write_report(load_history(Path("data/history.json")), Path("output/competitor_analysis.xlsx"))'
    .venv/bin/python -c 'from pathlib import Path; from landing.sber_vs import build_sber_vs_landing; print(build_sber_vs_landing(Path("output/competitor_analysis.xlsx"), Path("output/sber_vs_banks.html")))'

## Validation and Acceptance

Acceptance requires the policy section to exist in `AGENTS.md`, `SOURCE_POLICY.md` to exist, all priority URLs from the request to be registered in `scanner/sources.py`, merge tests to show official over PBI and PBI over other sources, no invented value when all sources are empty, explicit provenance on merged facts, conflict logging, and Sber VS HTML generation from Excel only. The full unittest suite must pass.

## Idempotence and Recovery

All edits are additive or localized. The generation commands overwrite local `output/` artifacts and are safe to rerun. No publisher command is used. If a test fails, inspect the failing assertion and adjust the policy enforcement code rather than weakening the policy text.

## Artifacts and Notes

Key generated artifacts:

- `output/competitor_analysis.xlsx`
- `output/sber_vs_banks.html`

Example official fact from workbook: Газпромбанк / Премиум — уровень 1 / cashback, source_type `official`, source_url `https://www.gazprombank.ru/premium/`.

Example PBI fallback from workbook: Сбер / СберПремьер — уровень 1 / positioning, source_type `premiumbanking.info`, source_url `https://premiumbanking.info/sber/1`.

Example missing value from workbook: Сбер / СберПремьер — уровень 1 / addons, value `Не найдено в доступных источниках`, status `not_found`.

Example conflict from workbook: Сбер / СберПремьер — уровень 1 / deposits, conflict_status `conflict`.

## Interfaces and Dependencies

`scanner/sources.py` must expose `SOURCE_PRIORITY_ORDER`, `PRIORITY_SOURCE_URLS`, `REQUIRED_PRIORITY_URLS`, `registered_source_urls()`, and `source_priority_rank(source_id)`. `scanner/merge.py` must keep `merge_tier_fields(parsed_sources, curated, field_ids, scan_date, bank_id="", tier_id="")` backward compatible while adding provenance keys to returned field dictionaries.
