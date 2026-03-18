# Releasing Synthesis

This document is the release-prep checklist for the public Synthesis repository.

## Scope

Use this before:
- tagging a public alpha or beta release
- publishing a package build
- announcing a release on the website or GitHub

## Repository Checks

1. Confirm public metadata is current.
   - `README.md`
   - `pyproject.toml`
   - `CHANGELOG.md`
   - `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`
2. Confirm the canonical registry link still points at `anthony-maio/synthesis-skills`.
3. Confirm the website link still points at `https://synthesis.making-minds.ai`.

## Code Verification

Run:

```bash
pytest -q
ruff check synthesis/client.py synthesis/skill_runtime.py synthesis/core/models.py tests
python -m build
```

Expected outcome:
- tests pass
- lint passes
- `dist/` contains both sdist and wheel artifacts

## Website Sync

The source of truth for the site content in this repo is `website/`.

To verify or sync the dedicated site repo:

```bash
python scripts/sync_website.py --source website --dest ../synthesis-web --check
python scripts/sync_website.py --source website --dest ../synthesis-web
```

After sync:
- commit and push `D:\Development\synthesis-web`
- verify GitHub Pages deployment
- verify the custom domain and TLS edge configuration

## Registry Checks

1. Confirm `anthony-maio/synthesis-skills` validation is green.
2. Confirm seeded skills and provenance are current.
3. Confirm mirrored external skills that leak upstream assumptions are either:
   - still intentionally mirrored, or
   - adapted into Synthesis-native variants

## Pre-Announcement Sanity Check

Before publishing or announcing:
- install from a clean environment
- run the quick start from `README.md`
- confirm the website is reachable
- confirm the release notes match actual shipped behavior
