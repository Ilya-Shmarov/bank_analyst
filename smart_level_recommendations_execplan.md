# Add smart recommendations for comparable bank levels

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds. This document follows `PLANS.md` in the repository root.

## Purpose / Big Picture

Today a visitor can receive threshold-based recommendations, but the three-column picker still expands every level as a large button. Banks with seven or eight levels make the shared grid row so tall that the recommendations begin below the visible area. After this change, Bank 1 is selected in one full-width step, its levels use one compact native select, and the three strongest recommendations appear immediately underneath. A compact three-slot strip shows the comparison selection and provides an optional manual editor for Bank 2 and Bank 3.

The feature must not create or infer banking facts. It uses only the `entry_conditions` records already present in `output/comparison_data.json` and embedded by `landing/sber_vs.py` into the generated HTML.

## Progress

- [x] (2026-07-21) Inspected the existing payload builder, entry-condition evaluator, picker JavaScript, CSS, comparison behavior, current comparison JSON, and browser alignment tests.
- [x] (2026-07-21) Recorded the product decisions: recommendation cards, exact matches before nearest matches, regional ranges, and comparison only after three selected banks.
- [x] (2026-07-21) Added a conservative capital-threshold extraction contract and exposed it as `entry_match` on each embedded level.
- [x] (2026-07-21) Added the recommendation panel, interval ranking logic, and non-destructive click-to-fill behavior.
- [x] (2026-07-21) Added focused parser, payload, browser interaction, and mobile overflow tests.
- [x] (2026-07-21) Rebuilt the Sber VS landing, checked embedded JavaScript syntax, listed sources, ran focused tests, and ran the full suite.
- [x] (2026-07-21) Confirmed the visibility problem is caused by the shared grid row taking the height of VTB's eight rendered level buttons.
- [x] (2026-07-21) Chose the progressive layout, native level select, three visible recommendations with a show-more control, compact comparison slots, and automatic table reveal only after the third selection.
- [x] (2026-07-21) Implemented and validated the progressive picker experiment.
- [x] (2026-07-21) Reverted that experiment at the user's request, restoring the previous three-column picker while retaining smart recommendations.
- [x] (2026-07-21) Restored the matching tests, rebuilt the landing, and revalidated the generated JavaScript.

## Surprises & Discoveries

- Observation: The existing `entry_conditions` evaluation intentionally merges repeated metric keys by their minimum. That behavior is useful for dominance comparison but is unsafe for recommendations because a condition such as `3 млн ₽ или 1 млн ₽ и траты 200 тыс ₽` would expose `1 млн ₽` as the capital metric.
  Evidence: `_entry_evaluation` assigns `metrics[key] = min(...)` in `landing/sber_vs.py`.

- Observation: Regional conditions already use explicit Moscow and region markers in the current source text, so a conservative parser can preserve them as a confirmed range without external data.
  Evidence: current JSON contains forms such as `2.5 млн ₽ для Мск; 2 млн ₽ регионы`.

- Observation: Playwright is not installed in the project virtual environment, so the existing and new browser tests are skipped locally. The generated JavaScript still passed a Node syntax compilation check.
  Evidence: the final full-suite output reported three Playwright skips; `new Function(...)` printed `JavaScript syntax: OK` for the final embedded script.

- Observation: The build completes the tracked landing but its optional publication copy targets a sibling directory outside the writable workspace.
  Evidence: `main.py --build-sber-vs` built 7 banks and 38 levels, then reported an operation-permitted error for `../bank_cite/index.html` while exiting successfully.

- Observation: Gazprombank's current private-banking regional thresholds are joined with `и` rather than a semicolon.
  Evidence: the final parser safely produces `25–50 млн ₽ по региону` from the confirmed Moscow/regions clause while the compound `капитал и траты` regression test remains excluded.

## Decision Log

- Decision: Parse recommendation thresholds separately from the existing comparison evaluation.
  Rationale: Recommendation matching needs to preserve pure-capital alternatives and exclude combined spend, salary, shares, joint-capital, and monthly-fee routes; changing the existing evaluator would risk unrelated comparison behavior.
  Date/Author: 2026-07-21 / Codex.

- Decision: Store a small `entry_match` object in the embedded landing payload rather than parsing Russian banking text in browser JavaScript.
  Rationale: Python already owns normalization, is testable with the existing unittest suite, and keeps the browser algorithm limited to numeric interval matching.
  Date/Author: 2026-07-21 / Codex.

- Decision: Recommendation clicks fill the next empty slot in the order Bank 2, Bank 3 and never replace an occupied slot.
  Rationale: This is predictable, non-destructive, and matches the approved product behavior.
  Date/Author: 2026-07-21 / Codex.

- Decision: Replace expanded level chips with a native select and move recommendations directly below the full-width Bank 1 step.
  Rationale: The problem is structural, not merely scroll position. A compact control keeps recommendations visible for every bank and works consistently on mobile without an overlay or forced page jump.
  Date/Author: 2026-07-21 / Codex.

- Decision: Show three recommendations by default and keep manual selection in compact Bank 2 and Bank 3 slot editors.
  Rationale: Three results fit in one desktop row, while the show-more button preserves access to every bank and manual controls preserve user choice.
  Date/Author: 2026-07-21 / Codex.

## Outcomes & Retrospective

The progressive full-width picker was implemented and validated, then reverted at the user's request. The landing is back to the earlier three-column bank and level picker. The underlying interval-ranked smart recommendations remain: recommendation clicks fill the next free slot without replacing prior choices, changing Bank 1 preserves Bank 2 and Bank 3, and the comparison still requires all three banks.

Focused parser, payload, and static alignment tests pass. The full suite ran 120 tests with three Playwright skips and only the previously known `test_no_sber_status_hardcode_in_html` failure. The generated JavaScript passes Node syntax compilation. The tracked `output/sber_vs_banks.html` was rebuilt successfully; only the optional copy to the out-of-workspace sibling publication directory was unavailable.

## Context and Orientation

`landing/sber_vs.py` reads `output/comparison_data.json`, normalizes its rows, builds a compact banks-and-levels payload in `build_payload`, and emits a self-contained HTML page. Each embedded level currently carries its name, segment, date, `entry_hint`, and comparison attributes. The same file contains the page HTML, CSS, and JavaScript. Browser state consists of three slots named `a`, `b`, and `c`; the comparison table remains hidden until all three slots have a bank and level.

`tests/test_premium_structured.py` contains focused tests for payload and text normalization. `tests/test_sber_vs_alignment.py` generates a temporary landing and optionally uses Playwright to verify browser layout and interactions. The generated user-facing artifact is `output/sber_vs_banks.html` and must be rebuilt through `main.py --build-sber-vs`.

An `entry_match` is the recommendation-only numeric interval extracted from a confirmed entry condition. A scalar requirement such as 3 million rubles becomes an interval whose minimum and maximum are both 3,000,000. Moscow and regional values become a range from the lower confirmed value to the higher confirmed value. Text that only describes fees, spend, income, shares, joint capital, or compound capital-plus-spend conditions is ineligible.

## Plan of Work

Add a helper near the existing entry-hint code that splits entry-condition text into source-order clauses. Accept clauses containing a ruble amount only when they describe a standalone capital or balance route and do not mention a monthly fee, spending, turnover, income, salary, shares, special assets, or joint access. Group accepted Moscow and regional clauses into one interval. If generic standalone capital clauses exist, use the first one because source text lists the primary pure-capital route before alternate compound routes. Return an object with `eligible`, `min_amount`, `max_amount`, and `label`; return an ineligible object without amounts when no safe threshold exists.

Attach this object to each level in `build_payload`. Keep provenance and all existing attributes unchanged.

Replace the current `.pickers` grid with a full-width primary picker containing Bank 1 bank chips and a native level select. Place the recommendation section directly after it, then render a compact three-card selection strip. Slot 1 summarizes the primary choice and offers an edit action that returns focus to the primary picker. Slots 2 and 3 summarize recommended or manual choices and expose a manual editor with native bank and level selects; only one editor is open at a time.

Keep the current recommendation ranking. Render only the first three cards until the user activates `Показать ещё`; reset that expansion when Bank 1 changes. Recommendation clicks fill slot `b`, then `c`, and update the native controls. Preserve Bank 2 and Bank 3 when Bank 1 changes. Continue to reveal the table only when all three slots are complete, using smooth scrolling unless the user prefers reduced motion.

Add responsive CSS so the primary picker remains full-width, the three selection slots form a compact desktop row, and all controls become a single mobile column without horizontal overflow. Update browser tests to use selects instead of level chips and prove the collapsed recommendation count, show-more behavior, manual fallback, selection preservation, and table reveal.

## Concrete Steps

Work from `/Users/ilyashmarov/Documents/analyst/bank_analyst`.

1. Edit `landing/sber_vs.py` to replace the three expanding picker columns with the primary step, recommendation section, and comparison-slot strip while preserving `state.a/b/c` and `entry_match`.
2. Replace level-chip rendering with native select synchronization, add one-at-a-time manual slot editors, and add recommendation show-more state.
3. Edit `tests/test_sber_vs_alignment.py` to use the new controls and verify compact rendering, recommendation expansion, manual editing, state preservation, and mobile layout.
4. Run focused tests:

       .venv/bin/python -m unittest tests.test_premium_structured tests.test_sber_vs_alignment

5. Rebuild and verify the landing:

       .venv/bin/python main.py --build-sber-vs
       .venv/bin/python main.py --list-sources

6. Run the full suite:

       .venv/bin/python -m unittest discover -s tests -q

7. Check `git status --short` and inspect generated changes before reporting completion.

## Validation and Acceptance

With a generated fixture, selecting a bank with many levels must render one level select rather than a stack of level chips. Selecting a 3 million ruble level must show only the three strongest recommendations initially, with the remaining banks available through `Показать ещё`. Two recommendation clicks must fill Bank 2 and Bank 3 respectively; only then must the existing comparison table become visible. Manual editors must update one slot without clearing the others, and changing Bank 1 must recompute cards without clearing Bank 2 or Bank 3. At 390 pixels wide, the primary picker, recommendations, slots, and manual controls must have no horizontal overflow.

The focused test modules must pass. The full suite must not add failures beyond the already known `test_no_sber_status_hardcode_in_html` failure, which predates and is outside this feature.

## Idempotence and Recovery

Building the landing is idempotent: it overwrites `output/sber_vs_banks.html` from the tracked JSON. Tests use temporary directories. If implementation fails partway, rerun the focused unittest modules after the next edit; no migration or external service is involved.

## Artifacts and Notes

The main observable artifact is `output/sber_vs_banks.html`. The embedded payload remains private to this static page; `output/comparison_data.json` schema is not changed.

## Interfaces and Dependencies

In `landing/sber_vs.py`, define a recommendation parser with the interface:

    def _entry_match_from_text(value: str) -> dict:

It returns:

    {"eligible": True, "min_amount": 2000000.0,
     "max_amount": 2500000.0, "label": "2–2,5 млн ₽ по региону"}

or:

    {"eligible": False, "min_amount": None,
     "max_amount": None, "label": ""}

Each embedded level receives this object as `entry_match`. No new package or network dependency is required.

Revision note (2026-07-21): Initial plan created from the approved product plan and current repository inspection.

Revision note (2026-07-21): Marked the parser, payload, UI, and test implementation complete before validation.

Revision note (2026-07-21): Recorded final validation evidence, environment limitations, and completed outcomes.

Revision note (2026-07-21): Added the discovered conjunction-separated regional format and its validation result.

Revision note (2026-07-21): Extended the completed recommendation feature with the approved progressive-layout redesign that removes expanding level lists.

Revision note (2026-07-21): Completed the progressive layout and recorded final validation: 120 tests, one known unrelated failure, and three Playwright skips.

Revision note (2026-07-21): Reverted the progressive-layout experiment at the user's request and restored the prior three-column landing state without removing smart recommendation matching.
