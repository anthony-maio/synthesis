# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows semantic versioning once it moves past alpha release discipline.

## [Unreleased]

### Added
- Skill-first acquisition flow centered on local search, canonical registry search, composition, and synthesis fallback.
- Canonical GitHub registry integration targeting `anthony-maio/synthesis-skills`.
- Static project website source under `website/` plus a sync utility for the dedicated `synthesis-web` repo.

### Changed
- Trust defaults for unmanaged local skills now align with the skill-first governance model.
- Skill package install/load/submit paths now preserve binary assets instead of assuming UTF-8-only packages.
- Client construction is lazy with respect to provider creation and canonical repo bootstrap.

### Fixed
- Submission packaging no longer corrupts binary skill assets.
- Local unmanaged skill folders no longer default to trusted installed state.

## [0.3.0] - 2026-03-17

### Added
- Initial public alpha framing for the skill-first rewrite.
- MCP skill-management surface for acquisition, inspection, listing, and submission preparation.
- Public OSS project files and static website package.
