# -*- coding: utf-8 -*-
"""Publish generated HTML output to the GitHub Pages repository."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from config import (
    BASE_DIR,
    GENERATED_HTML,
    OUTPUT_DIR,
    PUBLISHED_HTML,
    PUBLISH_EXTRA_ASSETS,
    SITE_REPOSITORY,
)

COMMIT_MESSAGE = "Daily site update"
GIT = "git"

log = logging.getLogger("scanner")


def publish_site(html_path: Optional[Path] = None) -> bool:
    """Copy generated site files and push them from the publication repo.

    Args:
        html_path: Path to the HTML file produced by the generator. If omitted,
            the configured default ``output/<GENERATED_HTML>`` is used.

    Returns:
        True when publication completed or there was nothing to commit. False
        when a required path is missing or a git command fails.
    """
    log.info("Starting publication...")

    source_html = _resolve_generated_html(html_path)
    site_repo = _resolve_path(SITE_REPOSITORY, BASE_DIR)
    if not _validate_paths(source_html, site_repo):
        return False

    log.info("Copying generated HTML...")
    try:
        _copy_file(source_html, site_repo / PUBLISHED_HTML)
        if not _copy_extra_assets(site_repo):
            return False
    except OSError as exc:
        log.error("Failed to copy publication files: %s", exc)
        return False
    log.info("Copied successfully.")

    log.info("Running git add...")
    published_paths = _published_git_paths()
    if not _run_git(["add", "--", *published_paths], site_repo):
        return False

    if not _has_staged_changes(site_repo, published_paths):
        log.info("Nothing changed.")
        return True

    log.info("Running git commit...")
    if not _run_git(["commit", "-m", COMMIT_MESSAGE, "--", *published_paths], site_repo):
        return False

    log.info("Running git pull --rebase...")
    if not _run_git(["pull", "--rebase"], site_repo):
        return False

    log.info("Running git push...")
    push_result = _run_git(["push"], site_repo)
    if not push_result:
        log.error("Git push failed; publication files were committed locally.")
        return False

    log.info("Publication completed successfully.")
    return True


def _resolve_generated_html(html_path: Optional[Path]) -> Path:
    """Return the generated HTML path from the caller or configuration."""
    if html_path is not None:
        return _resolve_path(Path(html_path), BASE_DIR)
    return OUTPUT_DIR / GENERATED_HTML


def _resolve_path(path: Path, base_dir: Path) -> Path:
    """Resolve relative paths against the project root."""
    return path if path.is_absolute() else base_dir / path


def _validate_paths(source_html: Path, site_repo: Path) -> bool:
    """Validate required source and destination paths before publishing."""
    if not source_html.exists():
        log.error("Generated HTML not found: %s", source_html)
        return False
    if not source_html.is_file():
        log.error("Generated HTML path is not a file: %s", source_html)
        return False
    if not site_repo.exists():
        log.error("Publication repository not found: %s", site_repo)
        return False
    if not (site_repo / ".git").exists():
        log.error("Publication path is not a git repository: %s", site_repo)
        return False
    return True


def _copy_file(source: Path, destination: Path) -> None:
    """Copy one file preserving metadata."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _copy_extra_assets(site_repo: Path) -> bool:
    """Copy configured additional site assets."""
    for source, destination in PUBLISH_EXTRA_ASSETS:
        source_path = _resolve_path(source, BASE_DIR)
        destination_path = _resolve_path(destination, site_repo)
        if not source_path.exists():
            log.error("Configured publication asset not found: %s", source_path)
            return False
        _copy_file(source_path, destination_path)
    return True


def _published_git_paths() -> list[str]:
    """Return paths that publication is allowed to add and commit."""
    paths = [PUBLISHED_HTML]
    paths.extend(str(destination) for _, destination in PUBLISH_EXTRA_ASSETS)
    return paths


def _has_staged_changes(repo_path: Path, paths: list[str]) -> bool:
    """Return True when git has staged changes ready to commit."""
    result = subprocess.run(
        [GIT, "diff", "--cached", "--quiet", "--", *paths],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return False
    if result.returncode == 1:
        return True
    _log_git_error(result)
    return False


def _run_git(args: list[str], repo_path: Path) -> bool:
    """Run a git command in the publication repository."""
    result = subprocess.run(
        [GIT, *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        _log_git_error(result)
        return False
    return True


def _log_git_error(result: subprocess.CompletedProcess[str]) -> None:
    """Log stderr from a failed git command."""
    stderr = result.stderr.strip() or result.stdout.strip()
    log.error("Git command failed with exit code %s.", result.returncode)
    if stderr:
        log.error(stderr)
