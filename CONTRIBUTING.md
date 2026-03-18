# Contributing to Synthesis

Thanks for contributing.

## What To Expect

Synthesis is still in an alpha rewrite. The public direction is stable:

- skill-first acquisition
- composition before synthesis
- GitHub-based curation and governance

The implementation is still being cleaned up, so small, focused changes are easier to review than large refactors.

## Before You Start

1. Open an issue or start a discussion if the change is large.
2. Check whether the work touches the skill-first path or legacy capability code.
3. Keep changes narrow and easy to review.

## Development Setup

```bash
pip install -e ".[dev]"
pytest -q
```

## Pull Request Expectations

- explain the user-facing or architecture-facing reason for the change
- add or update tests for behavior changes
- avoid unrelated cleanup in the same PR
- document any legacy areas left intentionally untouched

## Code Style

- prefer explicit, readable Python over clever abstractions
- keep public surfaces small
- preserve compatibility only when it clearly reduces migration pain
- do not add synthesis-by-default behavior back into the main path

## Documentation

If you change the public story of the project, update the relevant docs:

- `README.md`
- `website/`
- any architecture or migration notes you touched

## Security

Please do not file public issues for security-sensitive problems. Follow the process in `SECURITY.md`.
