# AGENTS.md

## Stack

- Python CLI
- `argparse` entrypoint in `main.py`
- `requests`, `beautifulsoup4`, `openpyxl`
- Optional: `playwright` for JS-rendered pages

## Commands

- `python3 -m venv .venv` - create virtualenv
- `.venv/bin/pip install -r requirements.txt` - install deps
- `.venv/bin/python main.py --list-sources` - list bank/source ids
- `.venv/bin/python main.py --scan-all` - full scan
- `.venv/bin/python main.py --scan-bank tbank` - scan one bank
- `.venv/bin/python main.py --scan-lifestyle` - scan lifestyle subscriptions
- `.venv/bin/python main.py --build-sber-vs` - rebuild Sber VS banks landing
- `.venv/bin/python main.py --build-premium-changes` - rebuild premium changes landing
- `.venv/bin/python main.py --build-premium-reviews` - collect Sber premium reviews and rebuild report

## Code Rules

- Start research by reading `PLANS.md`. Start implementation by reading `AGENTS.md`. Use an ExecPlan for complex features or significant refactors.
- Keep work inside `main.py`, `scanner/`, `landing/`, `report/`, `data/`, and `output/`.
- Do not invent banking data; use `sources.NOT_FOUND` when a fact is missing.
- Respect `robots.txt`, captchas, and antibot blocks; mark blocked sources unavailable.
- Add banks, tiers, subscriptions, and URLs in `scanner/sources.py` first.
- Add manually verified facts in `scanner/curated.py` with `source_url` and `date_checked`.
- Preserve provenance when changing merge, diff, scoring, or report logic.
- Keep service events in `data/service_log.json`.

## Source policy for bank data

- Banking facts must follow `SOURCE_POLICY.md`. This is a permanent project rule for parser, JSON, Excel, and landing changes.
- Never invent, infer, copy, or transfer banking conditions without direct confirmation from an allowed source.
- Every user-facing fact must be tied to a concrete `(bank_id, tier_id, field_id)` key and must preserve value, source URL, source type, check date, raw text, and reliability status.
- Source priority is strict: official bank documents and pages first, PremiumBanking.info second, other existing sources third. Official values win conflicts.
- PremiumBanking.info is fallback for missing or unavailable official data; do not replace a found official value with PBI.
- Do not transfer data between banks, between levels, or between Premium and Private products. Alfa Only data must not be used for A-Club unless the source explicitly says so.
- If a fact is missing, write `sources.NOT_FOUND` in data and display `sources.NOT_FOUND_AVAILABLE` (`Не найдено в доступных источниках`) to users.
- Conflicts between official sources and PremiumBanking.info must be preserved in provenance and in the `Конфликты источников` sheet.
- The Sber VS HTML landing must use `output/comparison_data.json` as its user-facing source and must not read Excel, re-fetch sites, parse PDFs, or invent missing values.
- Do not put insurance risks, assistance, insured sums, medical expenses, trip duration, baggage, flight delay/cancellation, skiing, or snowboarding into `Другие привилегии`.

## Self-Check

- Run `.venv/bin/python main.py --list-sources` after meaningful changes.
- Run `.venv/bin/python main.py --build-premium-changes` after premium changes landing edits.
- Run `.venv/bin/python main.py --build-sber-vs` after Sber VS landing edits.
- Run `.venv/bin/python main.py --build-premium-reviews` after premium review report edits.
- Prefer `.venv/bin/python main.py --scan-bank tbank` for scanner/report changes.
- Use `.venv/bin/python main.py --scan-all` only for full-pipeline changes.
- Check `git status --short` before finishing.
