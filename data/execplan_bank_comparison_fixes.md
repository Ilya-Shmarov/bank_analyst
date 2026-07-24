# Correct bank comparison facts and traffic-light rankings

This ExecPlan is a living document maintained in accordance with `PLANS.md`. It covers the requested corrections for Sber, Alfa-Bank, VTB, Gazprombank, Ozon Bank, and Raiffeisenbank on the Sber-versus-banks landing page.

## Purpose / Big Picture

After this change, restaurant limits that matter for choosing a level are visible immediately, confirmed services such as Supreme and SimpleWine appear on every applicable Alfa level, and the traffic-light colors do not rank a richer level below a poorer level merely because its wording differs or because a benefit list could not be compared. The result is visible by rebuilding `output/sber_vs_banks.html` and selecting the named banks and levels.

## Progress

- [x] (2026-07-24 00:00 MSK) Read `PLANS.md` and located the display and comparison logic in `landing/sber_vs.py`.
- [x] (2026-07-24) Inspected saved records and verified current official or allowed fallback sources for every reported level.
- [x] (2026-07-24) Added presentation fixes for Sber and Alfa restaurant/Supreme/SimpleWine facts.
- [x] (2026-07-24) Corrected comparison semantics for deposits, concierge, and other-benefit sets without inventing missing data.
- [x] (2026-07-24) Added regression tests for the reported failures.
- [x] (2026-07-24) Rebuilt the landing and verified the selected levels in the rendered interface.

## Surprises & Discoveries

- Observation: The current “other privileges” evaluator refuses to compare a whole cell when even one parsed item has an unknown inclusion status.
  Evidence: `_benefits_evaluation()` returns `incomparable` as soon as `unknown` is non-empty.
- Observation: The fallback vector placed one selectable benefit ahead of a larger set of eight confirmed benefits.
  Evidence: Gazprombank Premium ranked above Private until confirmed benefit count was made the primary fallback dimension.
- Observation: Local generation succeeds, but publishing to the sibling `bank_cite` checkout requires filesystem access outside this workspace.
  Evidence: the build reported `Operation not permitted` while copying `index.html`.

## Decision Log

- Decision: Separate fact corrections from ranking corrections and preserve every source record in `output/comparison_data.json`.
  Rationale: The source policy prohibits manufacturing a value merely to obtain a desired traffic-light color.
  Date/Author: 2026-07-24 / Codex
- Decision: Rank other-benefit fallbacks by confirmed set size, then confirmed ruble value, then inclusion mode.
  Rationale: This keeps Ozon and Raiffeisen monetary differences visible while preventing a small selectable set from outranking a much richer confirmed set.
  Date/Author: 2026-07-24 / Codex

## Outcomes & Retrospective

The requested facts and traffic-light behaviors are corrected in the local landing. Browser verification confirmed: exact Sber and A-Club restaurant text is visible immediately; A-Club deposits rank above lower published rates; VTB concierge levels are equal and level 8 other benefits rank above levels 6 and 4; Gazprombank Private leads on deposits and other benefits; Ozon Bronze/Silver/Platinum rank weak/medium/strong; and Raiffeisen’s last level shows the 2,000 ₽ promo codes and ranks strongest. Publication remains a separate filesystem-permission step.

## Context and Orientation

`output/comparison_data.json` is the only user-facing data source for the landing. `landing/sber_vs.py` converts each field into a short display value and a structured evaluation. JavaScript embedded by the same module compares those structured evaluations and assigns strong, medium, or weak colors. `scanner/curated.py` contains manually verified facts with source URLs and check dates. Tests are in `tests/test_premium_structured.py`.

“Other privileges” is a set-valued category: it contains several named services rather than one numeric amount. A comparison is safe only when it uses confirmed service membership and confirmed inclusion status; absence of a service in one parsed list must not silently mean the bank does not offer it.

## Plan of Work

First inspect the exact records for the named tiers, including their source URLs, raw text, and reliability. Then add narrowly scoped display overrides only when the same fact is already confirmed in the landing source or an allowed official source. Adjust evaluation rules so richer and poorer levels are compared on common confirmed metrics, while genuinely incomparable facts remain uncolored. Add tests that reproduce the requested selections and assert both the visible summary and the structured order. Rebuild the HTML and exercise it in a browser.

## Concrete Steps

From `/Users/ilyashmarov/Documents/analyst/bank_analyst`, inspect records with `jq` and source code with `rg`. Edit only `landing/`, `scanner/curated.py`, `data/`, `output/`, and tests. Run targeted unit tests, then `.venv/bin/python main.py --list-sources` and `.venv/bin/python main.py --build-sber-vs`.

## Validation and Acceptance

The Sber level 6 restaurant cell must show the exact permanent-inclusion limit without opening details. Every applicable Alfa level must show Supreme; A-Club restaurant limits must be visible without details; confirmed SimpleWine text must appear in Alfa Only as well as A-Club. A-Club deposits must not rank below Alfa Only when its confirmed rate is higher on the same comparison basis. VTB Prime+ concierge and level 8 other benefits must not rank below poorer VTB levels due only to parsing. Gazprombank Private deposits and other benefits, Ozon other benefits, and the last Raiffeisen level must receive a color when a defensible common comparison exists. The new regression tests and the existing targeted suite must pass.

## Idempotence and Recovery

The build is deterministic and can be repeated. Generated output files may change, but source facts and provenance are not overwritten unless an explicitly verified curated record is added. No destructive commands are required.

## Artifacts and Notes

The primary deliverable is `output/sber_vs_banks.html`; `output/comparison_data.json` remains its fact source.

## Interfaces and Dependencies

Keep `_attr_metric(field, row) -> dict`, `_category_evaluation(field, raw_value, display_value, row) -> dict`, and the JavaScript comparison contract stable. New helper functions may be added inside `landing/sber_vs.py` but must return the existing evaluation shape: `status`, `method`, `metrics`, `directions`, `scope`, `summary`, and `reason`.

Revision note: created the initial plan after grouping the user’s reports into fact-display and ranking defects. Updated after implementation, tests, and rendered-browser verification.
