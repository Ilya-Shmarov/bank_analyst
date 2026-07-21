# Отсеять переформулировки из истории изменений

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds. This plan follows `PLANS.md` in the repository root.

## Purpose / Big Picture

Users should see only real bank condition changes in the "Последние изменения" section. Today the system publishes many wording-only edits, such as "безлимит" becoming "Бизнес-залы — безлимит" or a long parenthetical note being removed. After this work, the diff layer will classify those wording edits as service events, the public Excel `Changes` sheet and both HTML landings will be rebuilt from cleaned history, and source links in change cards will remain absolute URLs.

## Progress

- [x] (2026-07-14 23:35 MSK) Read repository instructions in `AGENTS.md` and plan requirements in `PLANS.md`.
- [x] (2026-07-14 23:37 MSK) Located the current market/service classifier in `scanner/diff.py` and the public `Changes` writer in `report/excel_writer.py`.
- [x] (2026-07-14 23:45 MSK) Add semantic diff rules and tests for the wording-only and real-change examples from the user.
- [x] (2026-07-14 23:47 MSK) Fix URL preservation in the `Changes` contract and change-card rendering.
- [x] (2026-07-14 23:50 MSK) Recompute `data/history.json` changelog from retained scans using the stricter classifier; market events dropped from 421 to 123.
- [x] (2026-07-14 23:55 MSK) Rebuild Excel, premium changes landing, Sber comparison landing, run tests and required self-checks.
- [x] (2026-07-14 23:56 MSK) Publish the rebuilt comparison/news page to `bank_cite` because the user explicitly allowed pushes for these changes.

## Surprises & Discoveries

- Observation: Source URLs in the public change cards can be corrupted by text normalization.
  Evidence: The user showed links rendered as `https://ilya-shmarov.github.io/bank_cite/%20//premiumbanking.info/...`, which happens when `https://` is normalized into text containing a space before `//`.

## Decision Log

- Decision: Treat changes as market events only when the condition signature changes, not merely when the display text changes.
  Rationale: The user's requirement is strict: identical numbers, limits, dates, service brands, and availability states must not be published as condition changes even if wording changes.
  Date/Author: 2026-07-14 / Codex.

- Decision: Recompute the retained changelog rather than hiding entries only in HTML.
  Rationale: The Excel `Changes` sheet is the single source for both the standalone changes landing and the Sber comparison landing. Cleaning the data source prevents duplicate filtering logic in the UI and keeps the contract consistent.
  Date/Author: 2026-07-14 / Codex.

## Outcomes & Retrospective

No final outcome yet. This section will be updated after validation and publishing.

Completed on 2026-07-14. The stricter semantic classifier reduced retained market events from 421 to 123 in `data/history.json`; the generated premium changes page publishes 115 visible, source-backed events. The user examples that were wording-only are absent from the rebuilt `Changes` sheet, and source URLs are preserved as absolute links. The main landing was published to `bank_cite` on branch `main` at commit `92600f2 Daily site update`.

## Context and Orientation

`scanner/diff.py` compares consecutive scans stored in `data/history.json`. Its function `change_kind(field_id, old_value, new_value)` labels each difference as `market` or `service`. Only `market` changes are written to the Excel `Changes` sheet by `report/excel_writer.py`. `landing/premium_changes.py` reads the Excel `Changes` sheet and renders the standalone changes page. `landing/sber_vs.py` embeds the same changes component into the Sber comparison page and uses the same data for row-level badges.

A "service" event means a parser, source, schema, or wording changed, but the bank's customer-facing condition did not. A "market" event means the bank condition changed: numbers, limits, dates, availability, or named service/provider changed.

## Plan of Work

Update `scanner/diff.py` with helper functions that extract a semantic signature from condition text. The signature will normalize numeric formats such as `5000` and `5 000`, ignore explanatory parentheticals that clearly describe old context rather than the current condition, recognize unlimited versus limited access, recognize absence phrases such as "нет" or "не предоставляется", and track named service/provider tokens such as `prime` and `aspire`. `change_kind` will keep the existing source-policy behavior for missing values and reference fields, then use semantic equivalence before returning `market`.

Add unit tests in `tests/test_source_policy.py` or a focused new test file. The tests will assert that the user's examples classify correctly: wording-only lounge, entry-threshold, concierge, and taxi changes are service events; unlimited to two lounge visits and PRIME to Aspire are market events.

Update `report/excel_writer.py` so URL fields in the `Changes` contract are not passed through human text normalization. Update `landing/premium_changes.py` to defensively repair any already-normalized `http: //` or `https: //` value when rendering links.

Regenerate `data/history.json` changelog from the retained scan snapshots with the stricter classifier, write `output/competitor_analysis.xlsx`, rebuild `output/premium_changes.html`, rebuild and publish `output/sber_vs_banks.html`, then run repository tests and self-check commands.

## Concrete Steps

All commands run from `/Users/ilyashmarov/Documents/analyst/bank_analyst`.

First, edit `scanner/diff.py`, `report/excel_writer.py`, `landing/premium_changes.py`, and tests with `apply_patch`.

Then run:

    .venv/bin/python -m unittest discover -s tests
    .venv/bin/python main.py --list-sources
    .venv/bin/python main.py --build-premium-changes
    .venv/bin/python main.py --build-sber-vs
    git status --short

Before rebuilding the public pages, recompute `data/history.json` changelog from existing retained scans with the updated classifier. The command will use `scanner.diff.diff_results` and `scanner.diff.schema_changes`, preserving scan snapshots and only replacing derived changelog entries.

## Validation and Acceptance

The new semantic tests must pass. The rebuilt `Changes` sheet should no longer include the examples where only wording changed, while still including real changes such as a changed lounge limit or a changed concierge provider. The generated HTML should show fewer public events than before and source links should start with `https://premiumbanking.info/...` or another absolute URL rather than a GitHub Pages-relative `%20//...` URL.

## Idempotence and Recovery

The changelog recomputation is deterministic from retained scans in `data/history.json`, so it can be rerun after classifier edits. If a rebuild fails, rerun the same command after fixing the failing code. No scan snapshots are deleted manually.

## Artifacts and Notes

Key user examples to preserve in tests:

    безлимит -> Бизнес-залы — безлимит = service
    3 посещения в месяц, до 15 в год (по 5000 ₽) -> Такси — 3 раза в месяц, 15 раз в год, до 5 000 ₽ = service
    Есть — консьерж-сервис PRIME (...) -> Есть — консьерж-сервис PRIME = service
    Бизнес-залы — безлимит -> Бизнес-залы — 2 посещения в месяц = market
    консьерж PRIME -> консьерж Aspire = market

## Interfaces and Dependencies

The public interface remains `scanner.diff.change_kind(field_id: str, old_value: str, new_value: str) -> str`, returning exactly `"market"` or `"service"`. The Excel and landing builders continue reading and writing the same sheet names and HTML entry points.
