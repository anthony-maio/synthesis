# Synthesis

Synthesis is a skill-first self-extension system for coding agents.

[![Status](https://img.shields.io/badge/status-alpha-b86b2b)](https://github.com/anthony-maio/synthesis)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://github.com/anthony-maio/synthesis/blob/main/pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-1f6feb)](https://github.com/anthony-maio/synthesis/blob/main/LICENSE)
[![Website](https://img.shields.io/badge/website-live-0a7f5a)](https://synthesis.making-minds.ai)
[![Registry](https://img.shields.io/badge/registry-synthesis--skills-6f42c1)](https://github.com/anthony-maio/synthesis-skills)

Search first. Compose second. Synthesize last.

Instead of defaulting to generated code for every new task, Synthesis pushes a stricter loop:

1. Search existing skills.
2. Compose a small bundle of skills if one skill is not enough.
3. Synthesize a new skill package only as a fallback.
4. Prepare that skill for curation in a canonical GitHub skill repository.

The current codebase is an alpha Python package centered on a `SynthesisClient` that can acquire, install, compose, and synthesize agent skills. The long-term project direction is a federated capability ecosystem where skills earn trust through review, validation, and repeated use.

Website: [synthesis.making-minds.ai](https://synthesis.making-minds.ai)  
Canonical registry: [anthony-maio/synthesis-skills](https://github.com/anthony-maio/synthesis-skills)

## At a Glance

- Skill-first acquisition flow for coding agents
- Canonical GitHub skill registry with curated provenance
- Composition before synthesis
- Draft skills stay local and untrusted until review
- Lifecycle-aware flow for draft, challenger, and canonical skills
- Miner-produced challenger bundles can be inspected and submitted directly
- Static website source lives in `website/` and is synced to `synthesis-web`

## Status

This project is in active rewrite.

- The primary path is now skill-first.
- Legacy capability, sandbox, and exchange code still exists in the repo as compatibility infrastructure.
- The canonical distribution model is GitHub-based curation rather than a REST marketplace.

## Why Synthesis Exists

Most agent frameworks still treat self-extension as “write more code.” That is expensive, slow, and often unnecessary.

Synthesis is built around a different default:

- reuse verified skill packages first
- keep skill packages compatible with existing agent ecosystems
- synthesize only when search and composition fail
- move new skills into a reviewable, open GitHub workflow

That makes self-extension more observable, more composable, and easier to govern in the open.

## Core Ideas

### Search Before Synthesis

Synthesis looks for installed skills first, then a canonical curated repo. New generation is a fallback, not the first move.

### Composition Over Reinvention

If one skill does not fully cover an intent, Synthesis tries to assemble a small skill bundle before creating anything new.

### Skill Packages, Not Raw Functions

The artifact is a real skill package centered on `SKILL.md`, with optional `scripts/`, `assets/`, `references/`, and `agents/` directories when the task requires them.

### Governance Through GitHub

Draft skills are local and untrusted. Promotion happens through pull requests, automated checks, and human review in the canonical repo.

## Project Layout

```text
synthesis/
├── synthesis/          # Python package
├── tests/              # Test suite
├── exchange_server/    # Legacy marketplace prototype
└── website/            # Static project website
```

## Installation

```bash
pip install -e ".[dev]"
```

## Quick Start

```python
import asyncio

from synthesis import SynthesisClient


async def main() -> None:
    client = SynthesisClient(
        provider_type="mock",
        host_root="./installed-skills",
    )
    result = await client.acquire_skill("parse csv files")
    print(result.to_dict())


asyncio.run(main())
```

By default, Synthesis targets the canonical public registry at `anthony-maio/synthesis-skills` and bootstraps a local checkout under `~/.synthesis/canonical/synthesis-skills` when `git` is available. Use `SYNTHESIS_CANONICAL_REPO_PATH` or `--canonical-repo` to override that checkout path.

## CLI

```bash
synthesis acquire-skill "parse csv files"
synthesis list-installed-skills
synthesis inspect-candidate-bundle ./candidate-bundle
synthesis inspect-candidate-bundle-detail ./candidate-bundle
synthesis inspect-candidate-bundle-review ./candidate-bundle
synthesis prepare-candidate-bundle-submission ./candidate-bundle
synthesis publish-candidate-bundle-submission ./candidate-bundle --open-pull-request
synthesis validate-candidate-bundle ./candidate-bundle
synthesis submit-candidate-bundle ./candidate-bundle
synthesis install-candidate-bundle ./candidate-bundle --allow-challengers
```

## Development

Run tests:

```bash
pytest -q
```

Run focused lint checks on the active skill-first path:

```bash
ruff check synthesis/__init__.py synthesis/client.py synthesis/mcp/server.py synthesis/skill_runtime.py tests/test_client.py
```

Preview the website locally:

```bash
cd website
python -m http.server 8000
```

## Website

The static project site lives in [`website/`](./website). It follows the same no-build deployment model used by sibling projects like `mnemos-web` and `slipstream-web`, so it can be published directly to GitHub Pages, Cloudflare Pages, or any static host.

## Open Source

- [Contributing](./CONTRIBUTING.md)
- [Code of Conduct](./CODE_OF_CONDUCT.md)
- [Security Policy](./SECURITY.md)
- [License](./LICENSE)
- [Changelog](./CHANGELOG.md)
- [Release Guide](./docs/releasing.md)

## Near-Term Cleanup

- remove or isolate more of the legacy capability-first path
- harden the GitHub-backed canonical skill registry flow
- improve validation for synthesized skill packages
- publish the project website and documentation
