# Synthesis Repository Guide

This repository is the public codebase for Synthesis.

## What This Repo Contains

- `synthesis/`: the Python package
- `tests/`: regression and packaging checks
- `website/`: static website source
- `exchange_server/`: legacy compatibility code that is still present but not the primary path

## Public Project Direction

Synthesis is currently a skill-first system:

1. Search installed skills.
2. Search the canonical curated skill registry.
3. Compose existing skills if one is not enough.
4. Synthesize a draft skill only as a fallback.

## Contributor Expectations

- Keep changes aligned with the skill-first architecture.
- Prefer removing or isolating legacy capability-first paths rather than expanding them.
- Keep public docs, packaging metadata, and website content in sync.
- Do not commit local machine configuration, secrets, credentials, or private archives.

## Release Hygiene

Before release-oriented changes:

- run `pytest -q`
- run `ruff check synthesis tests scripts`
- run `python -m build`
- verify `website/` is synced to the dedicated `synthesis-web` repo with `python scripts/sync_website.py --source website --dest ../synthesis-web --check`
