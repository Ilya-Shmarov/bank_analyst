# -*- coding: utf-8 -*-
"""Project-level settings for generated site publication."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

# Sibling Git repository used by GitHub Pages.
SITE_REPOSITORY = BASE_DIR / "../bank_cite"

# Current generated landing file. Change this if the generator output is renamed.
GENERATED_HTML = "sber_vs_banks.html"

# Structured comparison data consumed by the Sber VS landing.
COMPARISON_JSON = "comparison_data.json"

# GitHub Pages entrypoint in the publication repository.
PUBLISHED_HTML = "index.html"

# Additional generated site assets can be added later as (source, destination)
# path pairs relative to BASE_DIR and SITE_REPOSITORY.
PUBLISH_EXTRA_ASSETS: tuple[tuple[Path, Path], ...] = ()
