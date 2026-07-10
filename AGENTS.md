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

## Self-Check

- Run `.venv/bin/python main.py --list-sources` after meaningful changes.
- Run `.venv/bin/python main.py --build-premium-changes` after premium changes landing edits.
- Run `.venv/bin/python main.py --build-sber-vs` after Sber VS landing edits.
- Run `.venv/bin/python main.py --build-premium-reviews` after premium review report edits.
- Prefer `.venv/bin/python main.py --scan-bank tbank` for scanner/report changes.
- Use `.venv/bin/python main.py --scan-all` only for full-pipeline changes.
- Check `git status --short` before finishing.
