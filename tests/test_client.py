"""Tests for the skill-first Synthesis client."""

import base64
import json
from pathlib import Path

import pytest

from synthesis import (
    ResolutionMethod,
    SkillInstallPolicy,
    SkillInstallState,
    SkillLifecycleStage,
    SynthesisClient,
    SynthesisMCPServer,
    TrustLevel,
)
from synthesis.skill_runtime import DEFAULT_CANONICAL_REPO_SLUG


def _write_skill(repo_root: Path, name: str, description: str, keywords: list[str]) -> None:
    skill_dir = repo_root / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_text = "\n".join(
        [
            "---",
            f"name: {name}",
            f"description: {description}",
            "keywords:",
            *[f"  - {keyword}" for keyword in keywords],
            "---",
            "",
            f"# {name}",
            "",
            description,
        ]
    )
    (skill_dir / "SKILL.md").write_text(skill_text, encoding="utf-8")


def _write_catalog(
    repo_root: Path,
    entries: list[dict],
    *,
    snapshot_version: str | None = None,
) -> None:
    catalog_dir = repo_root / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"skills": entries}
    if snapshot_version is not None:
        payload["snapshot_version"] = snapshot_version
    (catalog_dir / "skills.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_local_skill(install_root: Path, name: str, description: str) -> None:
    skill_dir = install_root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                f"description: {description}",
                "---",
                "",
                f"# {name}",
                "",
                description,
            ]
        ),
        encoding="utf-8",
    )


def _write_candidate_bundle(
    bundle_root: Path,
    name: str,
    description: str,
    *,
    registry_overrides: dict[str, object] | None = None,
) -> Path:
    bundle_dir = bundle_root / name
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                f"description: {description}",
                "keywords:",
                "  - review",
                "  - workflow",
                "---",
                "",
                f"# {name}",
                "",
                description,
            ]
        ),
        encoding="utf-8",
    )
    registry_payload = {
        "schema_version": "1",
        "capability_family": "repo-surveyor",
        "lifecycle_stage": "challenger",
        "trust_level": "probation",
        "is_primary": False,
        "variant_of": None,
        "supersedes": [],
        "submission_type": "variant_candidate",
        "nearest_canonical": "repo-surveyor",
        "evidence_summary": "Preserves hidden-directory analysis from a mined workflow.",
        "variant_reason": "distinct_workflow",
        "family_confidence": 0.93,
        "disposition_confidence": 0.84,
        "disposition_reason_codes": [
            "family_match_strong",
            "variant_distinct_workflow",
        ],
        "registry_snapshot_version": "snapshot-2026-03-23",
    }
    if registry_overrides:
        registry_payload.update(registry_overrides)
    (bundle_dir / "REGISTRY.json").write_text(
        json.dumps(registry_payload, indent=2),
        encoding="utf-8",
    )
    (bundle_dir / "PROVENANCE.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "kind": "adapted_external",
                "author": "Synthesis Skill Miner",
                "source": "https://github.com/example/skill-source",
                "upstream": "https://github.com/example/skill-source",
                "source_commit": "abc123def",
                "source_fingerprint": "repo-fingerprint-1",
                "license_status": "permissive",
                "license_expression": "MIT",
                "packaging_allowed": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (bundle_dir / "MINER_REPORT.md").write_text(
        "\n".join(
            [
                "# Miner Report",
                "",
                "Nearest canonical: repo-surveyor",
                "",
                "Why better or different: stronger hidden-directory inventory and workflow grouping.",
            ]
        ),
        encoding="utf-8",
    )
    asset = bundle_dir / "assets" / "example.bin"
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes(b"\x00candidate-binary")
    return bundle_dir


def _repo_surveyor_catalog_entry() -> dict:
    return {
        "name": "repo-surveyor",
        "description": "Canonical repo survey skill.",
        "keywords": ["repo", "survey"],
        "relative_path": "skills/repo-surveyor",
        "trust_level": "trusted",
        "source_type": "canonical",
        "repo": DEFAULT_CANONICAL_REPO_SLUG,
        "governance": {
            "capability_family": "repo-surveyor",
            "lifecycle_stage": "canonical",
            "trust_level": "trusted",
            "is_primary": True,
        },
    }


@pytest.fixture
def skill_roots(tmp_path: Path) -> tuple[Path, Path]:
    canonical_root = tmp_path / "canonical"
    install_root = tmp_path / "installed"
    canonical_root.mkdir()
    install_root.mkdir()
    return canonical_root, install_root


@pytest.mark.asyncio
async def test_acquire_skill_installs_canonical_match(skill_roots: tuple[Path, Path]) -> None:
    canonical_root, install_root = skill_roots
    _write_skill(
        canonical_root,
        name="csv-parser",
        description="Parse CSV files into Python dictionaries.",
        keywords=["csv", "parse", "files"],
    )
    _write_catalog(
        canonical_root,
        [
            {
                "name": "csv-parser",
                "description": "Parse CSV files into Python dictionaries.",
                "keywords": ["csv", "parse", "files"],
                "relative_path": "skills/csv-parser",
                "trust_level": "trusted",
                "source_type": "canonical",
                "repo": "github.com/synthesis-ai/skills",
                "governance": {
                    "capability_family": "csv-parser",
                    "lifecycle_stage": "canonical",
                    "trust_level": "trusted",
                    "is_primary": True,
                    "variant_of": None,
                    "supersedes": [],
                    "submission_type": None,
                    "nearest_canonical": None,
                    "evidence_summary": None,
                },
            }
        ],
    )

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    result = await client.acquire_skill("parse csv files")

    assert result.success is True
    assert result.method == ResolutionMethod.CANONICAL_SKILL
    assert result.primary_skill is not None
    assert result.primary_skill.name == "csv-parser"
    assert result.primary_skill.trust_level == TrustLevel.TRUSTED
    assert result.primary_skill.lifecycle_stage == SkillLifecycleStage.CANONICAL
    assert result.primary_skill.capability_family == "csv-parser"
    assert (install_root / "csv-parser" / "SKILL.md").exists()


@pytest.mark.asyncio
async def test_resolve_is_legacy_alias_for_skill_acquisition(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_skill(
        canonical_root,
        name="lint-repo",
        description="Lint a Python repository with Ruff.",
        keywords=["lint", "python", "ruff"],
    )
    _write_catalog(
        canonical_root,
        [
            {
                "name": "lint-repo",
                "description": "Lint a Python repository with Ruff.",
                "keywords": ["lint", "python", "ruff"],
                "relative_path": "skills/lint-repo",
                "trust_level": "verified",
                "source_type": "canonical",
                "repo": "github.com/synthesis-ai/skills",
            }
        ],
    )

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    result = await client.resolve("lint this python repo")

    assert result.success is True
    assert result.method == ResolutionMethod.CANONICAL_SKILL
    assert result.primary_skill is not None
    assert result.primary_skill.name == "lint-repo"


@pytest.mark.asyncio
async def test_acquire_skill_uses_composition_bundle_before_synthesis(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_skill(
        canonical_root,
        name="fetch-data",
        description="Fetch structured data from remote APIs.",
        keywords=["fetch", "data", "api"],
    )
    _write_skill(
        canonical_root,
        name="format-report",
        description="Format structured data into a readable report.",
        keywords=["format", "report", "data"],
    )
    _write_catalog(
        canonical_root,
        [
            {
                "name": "fetch-data",
                "description": "Fetch structured data from remote APIs.",
                "keywords": ["fetch", "data", "api"],
                "relative_path": "skills/fetch-data",
                "trust_level": "trusted",
                "source_type": "canonical",
                "repo": "github.com/synthesis-ai/skills",
            },
            {
                "name": "format-report",
                "description": "Format structured data into a readable report.",
                "keywords": ["format", "report", "data"],
                "relative_path": "skills/format-report",
                "trust_level": "trusted",
                "source_type": "canonical",
                "repo": "github.com/synthesis-ai/skills",
            },
        ],
    )

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    result = await client.acquire_skill("fetch data and format report")

    assert result.success is True
    assert result.method == ResolutionMethod.COMPOSITION
    assert result.composition_bundle is not None
    assert {skill.name for skill in result.installed_skills} == {
        "fetch-data",
        "format-report",
    }


@pytest.mark.asyncio
async def test_acquire_skill_synthesizes_draft_and_prepares_submission(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_catalog(canonical_root, [])

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    result = await client.acquire_skill("triage support tickets", requirements="Use skill packages")

    assert result.success is True
    assert result.method == ResolutionMethod.SYNTHESIZED
    assert result.primary_skill is not None
    assert result.primary_skill.trust_level == TrustLevel.UNTRUSTED
    assert result.primary_skill.lifecycle_stage == SkillLifecycleStage.DRAFT
    assert result.submission is not None
    assert result.submission.repo == DEFAULT_CANONICAL_REPO_SLUG
    assert result.submission.status == "prepared"
    assert result.submission.lifecycle_stage == SkillLifecycleStage.CHALLENGER
    assert result.submission.capability_family == result.primary_skill.name
    assert f"skills/{result.primary_skill.name}/REGISTRY.json" in result.submission.files
    assert f"skills/{result.primary_skill.name}/PROVENANCE.json" in result.submission.files
    assert (install_root / result.primary_skill.name / "SKILL.md").exists()


@pytest.mark.asyncio
async def test_client_uses_default_canonical_registry_from_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_root = tmp_path / "canonical"
    install_root = tmp_path / "installed"
    canonical_root.mkdir()
    install_root.mkdir()

    _write_skill(
        canonical_root,
        name="csv-parser",
        description="Parse CSV files into Python dictionaries.",
        keywords=["csv", "parse", "files"],
    )
    _write_catalog(
        canonical_root,
        [
            {
                "name": "csv-parser",
                "description": "Parse CSV files into Python dictionaries.",
                "keywords": ["csv", "parse", "files"],
                "relative_path": "skills/csv-parser",
                "trust_level": "trusted",
                "source_type": "canonical",
                "repo": DEFAULT_CANONICAL_REPO_SLUG,
            }
        ],
    )
    monkeypatch.setenv("SYNTHESIS_CANONICAL_REPO_PATH", str(canonical_root))

    client = SynthesisClient(provider_type="mock", host_root=str(install_root))

    result = await client.acquire_skill("parse csv files")

    assert result.success is True
    assert result.method == ResolutionMethod.CANONICAL_SKILL
    assert result.primary_skill is not None
    assert result.primary_skill.name == "csv-parser"


@pytest.mark.asyncio
async def test_mcp_server_exposes_skill_management_tools(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_skill(
        canonical_root,
        name="release-notes",
        description="Draft release notes from recent code changes.",
        keywords=["release", "notes", "changes"],
    )
    _write_skill(
        canonical_root,
        name="repo-surveyor",
        description="Canonical repo survey skill.",
        keywords=["repo", "survey"],
    )
    _write_catalog(
        canonical_root,
        [
            {
                "name": "release-notes",
                "description": "Draft release notes from recent code changes.",
                "keywords": ["release", "notes", "changes"],
                "relative_path": "skills/release-notes",
                "trust_level": "trusted",
                    "source_type": "canonical",
                    "repo": "github.com/synthesis-ai/skills",
                },
                _repo_surveyor_catalog_entry(),
            ],
            snapshot_version="snapshot-2026-03-23",
        )

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )
    server = SynthesisMCPServer(client)

    tools = await server.list_tools()

    assert {tool["name"] for tool in tools} == {
        "acquire_skill",
        "inspect_skill",
        "inspect_candidate_bundle",
        "inspect_candidate_bundle_detail",
        "inspect_candidate_bundle_directory",
        "inspect_candidate_bundle_blockers",
        "inspect_candidate_bundle_review",
        "install_candidate_bundle",
        "list_installed_skills",
        "prepare_candidate_bundle_submission",
        "publish_candidate_bundle_submission",
        "validate_candidate_bundle",
        "submit_candidate_bundle",
        "submit_skill",
    }

    response = await server.call_tool("acquire_skill", {"intent": "draft release notes"})
    payload = json.loads(response)

    assert payload["success"] is True
    assert payload["primary_skill"]["name"] == "release-notes"

    inspect_bundle = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="review-bundle",
        description="Use when reviewing miner-produced challenger bundles.",
    )
    detail_response = await server.call_tool(
        "inspect_candidate_bundle_detail",
        {"path": str(inspect_bundle)},
    )
    detail_payload = json.loads(detail_response)

    assert detail_payload["skill"]["name"] == "review-bundle"
    assert detail_payload["validation"]["valid"] is True
    assert detail_payload["publishability"]["publishable"] is True
    assert detail_payload["recommended_next_action"] == "ready_to_publish"
    assert "Nearest canonical: repo-surveyor" in detail_payload["miner_report"]

    review_response = await server.call_tool(
        "inspect_candidate_bundle_review",
        {"path": str(inspect_bundle)},
    )
    review_payload = json.loads(review_response)

    assert review_payload["skill_name"] == "review-bundle"
    assert review_payload["ready_for_review"] is True
    assert review_payload["publishability"]["publishable"] is True
    assert review_payload["recommended_next_action"] == "ready_to_publish"
    assert review_payload["submission_type"] == "variant_candidate"
    assert review_payload["headline"] == "Variant candidate for repo-surveyor"

    directory_response = await server.call_tool(
        "inspect_candidate_bundle_directory",
        {"path": str(canonical_root / "candidate-bundles")},
    )
    directory_payload = json.loads(directory_response)

    assert directory_payload["total_candidates"] == 1
    assert directory_payload["scanned_candidates"] == 1
    assert directory_payload["ready_candidates"] == 1
    assert directory_payload["action_counts"]["ready_to_publish"] == 1
    assert directory_payload["action_filter"] is None

    blockers_response = await server.call_tool(
        "inspect_candidate_bundle_blockers",
        {"path": str(canonical_root / "candidate-bundles")},
    )
    blockers_payload = json.loads(blockers_response)

    assert blockers_payload["scanned_candidates"] == 1
    assert blockers_payload["blocked_candidates"] == 0
    assert blockers_payload["action_counts"] == {}
    assert blockers_payload["action_filter"] is None
    assert blockers_payload["candidates"] == []

    envelope_response = await server.call_tool(
        "prepare_candidate_bundle_submission",
        {"path": str(inspect_bundle)},
    )
    envelope_payload = json.loads(envelope_response)

    assert envelope_payload["submission"]["target_path"] == "skills/review-bundle"
    assert envelope_payload["review"]["headline"] == "Variant candidate for repo-surveyor"
    assert "## Why This Exists" in envelope_payload["pull_request_body"]


def test_inspect_candidate_bundle_returns_structured_metadata(skill_roots: tuple[Path, Path]) -> None:
    canonical_root, install_root = skill_roots
    _write_catalog(canonical_root, [])
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="hidden-repo-surveyor",
        description="Use when inspecting hidden directories and orchestration files in a repository.",
    )

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    record = client.inspect_candidate_bundle(str(bundle_dir))

    assert record is not None
    assert record.name == "hidden-repo-surveyor"
    assert record.lifecycle_stage == SkillLifecycleStage.CHALLENGER
    assert record.capability_family == "repo-surveyor"
    assert record.submission_type == "variant_candidate"
    assert record.variant_reason == "distinct_workflow"
    assert record.family_confidence == pytest.approx(0.93)
    assert record.disposition_confidence == pytest.approx(0.84)
    assert record.disposition_reason_codes == [
        "family_match_strong",
        "variant_distinct_workflow",
    ]
    assert record.registry_snapshot_version == "snapshot-2026-03-23"
    assert record.license_status == "permissive"
    assert record.license_expression == "MIT"
    assert record.packaging_allowed is True
    assert record.source.commit == "abc123def"
    assert record.source.fingerprint == "repo-fingerprint-1"


def test_inspect_candidate_bundle_detail_includes_validation_and_report(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_catalog(canonical_root, [])
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="hidden-repo-surveyor",
        description="Use when inspecting hidden directories and orchestration files in a repository.",
    )

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    detail = client.inspect_candidate_bundle_detail(str(bundle_dir))

    assert detail is not None
    assert detail.skill.name == "hidden-repo-surveyor"
    assert detail.validation.valid is True
    assert detail.publishability.publishable is False
    assert detail.publishability.blocked_reason == "missing_nearest_canonical"
    assert detail.recommended_next_action == "reclassify_against_live_canon"
    assert detail.miner_report is not None
    assert "Nearest canonical: repo-surveyor" in detail.miner_report
    assert detail.provenance["source_commit"] == "abc123def"
    assert detail.governance["submission_type"] == "variant_candidate"
    assert detail.binary_files == ["assets/example.bin"]
    assert "MINER_REPORT.md" in detail.text_files


def test_inspect_candidate_bundle_review_summarizes_curator_decision_surface(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_skill(
        canonical_root,
        name="repo-surveyor",
        description="Canonical repo survey skill.",
        keywords=["repo", "survey"],
    )
    _write_catalog(
        canonical_root,
        [_repo_surveyor_catalog_entry()],
        snapshot_version="snapshot-2026-03-23",
    )
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="hidden-repo-surveyor",
        description="Use when inspecting hidden directories and orchestration files in a repository.",
    )

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    review = client.inspect_candidate_bundle_review(str(bundle_dir))

    assert review is not None
    assert review.skill_name == "hidden-repo-surveyor"
    assert review.ready_for_review is True
    assert review.publishability.publishable is True
    assert review.publishability.blocked_reason is None
    assert review.recommended_next_action == "ready_to_publish"
    assert review.headline == "Variant candidate for repo-surveyor"
    assert review.validation_errors == []
    assert review.license_status == "permissive"
    assert review.nearest_canonical == "repo-surveyor"
    assert review.variant_reason == "distinct_workflow"
    assert "stronger hidden-directory inventory" in review.miner_report_excerpt


def test_inspect_candidate_bundle_review_surfaces_blockers(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_catalog(canonical_root, [])
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="blocked-bundle",
        description="Use when the candidate should be blocked for review.",
    )
    registry_path = bundle_dir / "REGISTRY.json"
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    payload["nearest_canonical"] = None
    registry_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    review = client.inspect_candidate_bundle_review(str(bundle_dir))

    assert review is not None
    assert review.ready_for_review is False
    assert review.publishability.publishable is False
    assert review.publishability.blocked_reason == "invalid_candidate_bundle"
    assert review.recommended_next_action == "fix_validation_errors"
    assert any("nearest_canonical" in error for error in review.validation_errors)
    assert "Blocked" in review.headline


def test_inspect_candidate_bundle_review_surfaces_publishability_blocker(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_skill(
        canonical_root,
        name="repo-surveyor",
        description="Canonical repo survey skill.",
        keywords=["repo", "survey"],
    )
    _write_catalog(
        canonical_root,
        [_repo_surveyor_catalog_entry()],
        snapshot_version="snapshot-2026-03-24",
    )
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="stale-bundle",
        description="Use when a stale bundle should still be reviewable but not publishable.",
    )

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    review = client.inspect_candidate_bundle_review(str(bundle_dir))

    assert review is not None
    assert review.ready_for_review is True
    assert review.publishability.publishable is False
    assert review.publishability.blocked_reason == "stale_registry_snapshot"
    assert review.recommended_next_action == "refresh_against_live_canon"


def test_submit_candidate_bundle_prepares_submission_with_metadata(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_catalog(canonical_root, [])
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="hidden-repo-surveyor",
        description="Use when inspecting hidden directories and orchestration files in a repository.",
    )

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    submission = client.submit_candidate_bundle(str(bundle_dir))

    assert submission is not None
    assert submission.lifecycle_stage == SkillLifecycleStage.CHALLENGER
    assert submission.trust_level == TrustLevel.PROBATION
    assert submission.capability_family == "repo-surveyor"
    assert submission.submission_type == "variant_candidate"
    assert submission.variant_reason == "distinct_workflow"
    assert submission.family_confidence == pytest.approx(0.93)
    assert submission.disposition_confidence == pytest.approx(0.84)
    assert submission.disposition_reason_codes == [
        "family_match_strong",
        "variant_distinct_workflow",
    ]
    assert submission.registry_snapshot_version == "snapshot-2026-03-23"
    assert submission.license_status == "permissive"
    assert submission.license_expression == "MIT"
    assert submission.packaging_allowed is True
    assert submission.files["skills/hidden-repo-surveyor/MINER_REPORT.md"].startswith("# Miner Report")
    assert submission.binary_files["skills/hidden-repo-surveyor/assets/example.bin"] == base64.b64encode(
        b"\x00candidate-binary"
    ).decode("ascii")


def test_prepare_candidate_bundle_submission_returns_pr_ready_envelope(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_catalog(canonical_root, [])
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="hidden-repo-surveyor",
        description="Use when inspecting hidden directories and orchestration files in a repository.",
    )

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    envelope = client.prepare_candidate_bundle_submission(str(bundle_dir))

    assert envelope is not None
    assert envelope.submission.target_path == "skills/hidden-repo-surveyor"
    assert envelope.validation.valid is True
    assert envelope.review.ready_for_review is True
    assert envelope.bundle_path == str(bundle_dir)
    assert "## Candidate" in envelope.pull_request_body
    assert "## Why This Exists" in envelope.pull_request_body
    assert "distinct_workflow" in envelope.pull_request_body
    assert "repo-surveyor" in envelope.pull_request_body


def test_prepare_candidate_bundle_submission_blocks_invalid_bundle(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_catalog(canonical_root, [])
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="blocked-bundle",
        description="Use when the candidate should be blocked for review.",
    )
    registry_path = bundle_dir / "REGISTRY.json"
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    payload["nearest_canonical"] = None
    registry_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    assert client.prepare_candidate_bundle_submission(str(bundle_dir)) is None


def test_publish_candidate_bundle_submission_writes_files_and_runs_git(
    skill_roots: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_root, install_root = skill_roots
    _write_skill(
        canonical_root,
        name="repo-surveyor",
        description="Canonical repo survey skill.",
        keywords=["repo", "survey"],
    )
    _write_catalog(
        canonical_root,
        [_repo_surveyor_catalog_entry()],
        snapshot_version="snapshot-2026-03-23",
    )
    (canonical_root / ".git").mkdir()
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="publish-bundle",
        description="Use when publishing a candidate bundle into the registry checkout.",
    )

    commands: list[list[str]] = []

    def fake_run(self: object, args: list[str], cwd: Path) -> str:
        commands.append(args)
        if args[-2:] == ["rev-parse", "HEAD"]:
            return "deadbeef"
        return ""

    monkeypatch.setattr("shutil.which", lambda name: name)

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )
    monkeypatch.setattr(client, "_run_command", fake_run.__get__(client, SynthesisClient))

    result = client.publish_candidate_bundle_submission(str(bundle_dir))

    assert result is not None
    assert result.success is True
    assert result.pull_request_url is None
    assert result.branch == "synthesis/publish-bundle"
    assert (canonical_root / "skills" / "publish-bundle" / "SKILL.md").exists()
    assert any(command[:3] == ["git", "checkout", "-B"] for command in commands)
    assert any(command[:2] == ["git", "add"] for command in commands)
    assert any(command[:2] == ["git", "commit"] for command in commands)
    assert any(command[:2] == ["git", "push"] for command in commands)


def test_publish_candidate_bundle_submission_can_open_pull_request(
    skill_roots: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_root, install_root = skill_roots
    _write_skill(
        canonical_root,
        name="repo-surveyor",
        description="Canonical repo survey skill.",
        keywords=["repo", "survey"],
    )
    _write_catalog(
        canonical_root,
        [_repo_surveyor_catalog_entry()],
        snapshot_version="snapshot-2026-03-23",
    )
    (canonical_root / ".git").mkdir()
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="pr-bundle",
        description="Use when opening a pull request for a candidate bundle.",
    )

    commands: list[list[str]] = []

    def fake_run(self: object, args: list[str], cwd: Path) -> str:
        commands.append(args)
        if args[:3] == ["gh", "pr", "create"]:
            return "https://github.com/anthony-maio/synthesis-skills/pull/123"
        return ""

    monkeypatch.setattr("shutil.which", lambda name: name)

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )
    monkeypatch.setattr(client, "_run_command", fake_run.__get__(client, SynthesisClient))

    result = client.publish_candidate_bundle_submission(
        str(bundle_dir),
        open_pull_request=True,
    )

    assert result is not None
    assert result.success is True
    assert result.pull_request_url == "https://github.com/anthony-maio/synthesis-skills/pull/123"
    assert any(command[:3] == ["gh", "pr", "create"] for command in commands)


def test_publish_candidate_bundle_submission_blocks_dirty_checkout(
    skill_roots: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_root, install_root = skill_roots
    _write_catalog(canonical_root, [])
    (canonical_root / ".git").mkdir()
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="dirty-bundle",
        description="Use when a dirty checkout should block publication.",
    )

    commands: list[list[str]] = []

    def fake_run(self: object, args: list[str], cwd: Path) -> str:
        commands.append(args)
        if args[-2:] == ["status", "--porcelain"]:
            return " M README.md"
        return ""

    monkeypatch.setattr("shutil.which", lambda name: name)

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )
    monkeypatch.setattr(client, "_run_command", fake_run.__get__(client, SynthesisClient))

    result = client.publish_candidate_bundle_submission(str(bundle_dir))

    assert result is not None
    assert result.success is False
    assert result.failure_reason == "dirty_checkout"
    assert any(command[-2:] == ["status", "--porcelain"] for command in commands)
    assert not any(command[:2] == ["git", "commit"] for command in commands)


def test_publish_candidate_bundle_submission_can_use_temp_worktree(
    skill_roots: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_root, install_root = skill_roots
    _write_skill(
        canonical_root,
        name="repo-surveyor",
        description="Canonical repo survey skill.",
        keywords=["repo", "survey"],
    )
    _write_catalog(
        canonical_root,
        [_repo_surveyor_catalog_entry()],
        snapshot_version="snapshot-2026-03-23",
    )
    (canonical_root / ".git").mkdir()
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="worktree-bundle",
        description="Use when publishing from a temporary worktree.",
    )
    worktree_root = canonical_root / "temp-worktrees"

    commands: list[list[str]] = []

    def fake_run(self: object, args: list[str], cwd: Path) -> str:
        commands.append(args)
        if args[-2:] == ["status", "--porcelain"]:
            return " M README.md"
        if args[:3] == ["git", "worktree", "add"]:
            Path(args[3]).mkdir(parents=True, exist_ok=True)
            return ""
        if args[:3] == ["git", "worktree", "remove"]:
            return ""
        if args[-2:] == ["rev-parse", "HEAD"]:
            return "cafebabe"
        return ""

    monkeypatch.setattr("shutil.which", lambda name: name)

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )
    monkeypatch.setattr(client, "_run_command", fake_run.__get__(client, SynthesisClient))

    result = client.publish_candidate_bundle_submission(
        str(bundle_dir),
        use_temp_worktree=True,
        worktree_root=str(worktree_root),
    )

    assert result is not None
    assert result.success is True
    assert result.used_temp_worktree is True
    assert result.target_repo_root is not None
    assert Path(result.target_repo_root).parent == worktree_root
    assert any(command[:3] == ["git", "worktree", "add"] for command in commands)
    assert any(command[:3] == ["git", "worktree", "remove"] for command in commands)


def test_publish_candidate_bundle_submission_can_set_pr_metadata(
    skill_roots: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_root, install_root = skill_roots
    _write_skill(
        canonical_root,
        name="repo-surveyor",
        description="Canonical repo survey skill.",
        keywords=["repo", "survey"],
    )
    _write_catalog(
        canonical_root,
        [_repo_surveyor_catalog_entry()],
        snapshot_version="snapshot-2026-03-23",
    )
    (canonical_root / ".git").mkdir()
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="metadata-bundle",
        description="Use when opening a richly configured pull request for a candidate bundle.",
    )

    commands: list[list[str]] = []

    def fake_run(self: object, args: list[str], cwd: Path) -> str:
        commands.append(args)
        if args[:3] == ["gh", "pr", "create"]:
            return "https://github.com/anthony-maio/synthesis-skills/pull/456"
        return ""

    monkeypatch.setattr("shutil.which", lambda name: name)

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )
    monkeypatch.setattr(client, "_run_command", fake_run.__get__(client, SynthesisClient))

    result = client.publish_candidate_bundle_submission(
        str(bundle_dir),
        open_pull_request=True,
        draft_pull_request=True,
        labels=["challenger", "miner"],
        reviewers=["anthony-maio"],
    )

    assert result is not None
    assert result.pull_request_url == "https://github.com/anthony-maio/synthesis-skills/pull/456"

    pr_command = next(command for command in commands if command[:3] == ["gh", "pr", "create"])
    assert "--draft" in pr_command
    assert pr_command.count("--label") == 2
    assert "--reviewer" in pr_command


def test_publish_candidate_bundle_submission_blocks_existing_target_without_override(
    skill_roots: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_root, install_root = skill_roots
    _write_catalog(canonical_root, [])
    (canonical_root / ".git").mkdir()
    existing_dir = canonical_root / "skills" / "publish-bundle"
    existing_dir.mkdir(parents=True, exist_ok=True)
    (existing_dir / "SKILL.md").write_text("# existing", encoding="utf-8")
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="publish-bundle",
        description="Use when a colliding target should be blocked before publish.",
    )

    monkeypatch.setattr("shutil.which", lambda name: name)

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )
    monkeypatch.setattr(client, "_run_command", lambda *args, **kwargs: "")

    result = client.publish_candidate_bundle_submission(str(bundle_dir))

    assert result is not None
    assert result.success is False
    assert result.failure_reason == "existing_target"


def test_publish_candidate_bundle_submission_blocks_stale_registry_snapshot(
    skill_roots: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_root, install_root = skill_roots
    _write_catalog(canonical_root, [], snapshot_version="snapshot-2026-03-24")
    (canonical_root / ".git").mkdir()
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="stale-bundle",
        description="Use when stale canon judgments should block publication.",
    )

    monkeypatch.setattr("shutil.which", lambda name: name)

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )
    monkeypatch.setattr(client, "_run_command", lambda *args, **kwargs: "")

    result = client.publish_candidate_bundle_submission(str(bundle_dir))

    assert result is not None
    assert result.success is False
    assert result.failure_reason == "stale_registry_snapshot"


def test_publish_candidate_bundle_submission_blocks_new_family_conflict(
    skill_roots: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_root, install_root = skill_roots
    _write_skill(
        canonical_root,
        name="repo-surveyor",
        description="Canonical repo survey skill.",
        keywords=["repo", "survey"],
    )
    _write_catalog(
        canonical_root,
        [
                _repo_surveyor_catalog_entry()
            ],
            snapshot_version="snapshot-2026-03-23",
        )
    (canonical_root / ".git").mkdir()
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="new-repo-surveyor",
        description="Use when pretending a known family is brand new.",
    )
    registry_path = bundle_dir / "REGISTRY.json"
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    payload["submission_type"] = "new_family_candidate"
    payload["nearest_canonical"] = None
    registry_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    monkeypatch.setattr("shutil.which", lambda name: name)

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )
    monkeypatch.setattr(client, "_run_command", lambda *args, **kwargs: "")

    result = client.publish_candidate_bundle_submission(str(bundle_dir))

    assert result is not None
    assert result.success is False
    assert result.failure_reason == "capability_family_conflict"


def test_publish_candidate_bundle_submission_reports_missing_nearest_canonical(
    skill_roots: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_root, install_root = skill_roots
    _write_catalog(canonical_root, [], snapshot_version="snapshot-2026-03-23")
    (canonical_root / ".git").mkdir()
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="missing-nearest",
        description="Use when nearest canonical should be enforced against the live registry.",
    )

    monkeypatch.setattr("shutil.which", lambda name: name)

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )
    monkeypatch.setattr(client, "_run_command", lambda *args, **kwargs: "")

    result = client.publish_candidate_bundle_submission(str(bundle_dir))

    assert result is not None
    assert result.success is False
    assert result.failure_reason == "missing_nearest_canonical"


def test_inspect_candidate_bundle_directory_builds_review_queue(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_skill(
        canonical_root,
        name="repo-surveyor",
        description="Canonical repo survey skill.",
        keywords=["repo", "survey"],
    )
    _write_catalog(
        canonical_root,
        [_repo_surveyor_catalog_entry()],
        snapshot_version="snapshot-2026-03-23",
    )
    bundles_root = canonical_root / "candidate-bundles"
    _write_candidate_bundle(
        bundles_root,
        name="ready-bundle",
        description="Use when the bundle should be review-ready.",
    )
    blocked_bundle = _write_candidate_bundle(
        bundles_root,
        name="blocked-bundle",
        description="Use when the bundle should be blocked.",
    )
    registry_path = blocked_bundle / "REGISTRY.json"
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    payload["nearest_canonical"] = None
    registry_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    queue = client.inspect_candidate_bundle_directory(str(bundles_root))

    assert queue is not None
    assert queue.total_candidates == 2
    assert queue.scanned_candidates == 2
    assert queue.ready_candidates == 1
    assert queue.blocked_candidates == 1
    assert queue.action_counts == {
        "ready_to_publish": 1,
        "fix_validation_errors": 1,
    }
    assert queue.action_filter is None
    assert queue.candidates[0].ready_for_review is True
    assert queue.candidates[0].publishable is True
    assert queue.candidates[0].blocked_reason is None
    assert queue.candidates[0].recommended_next_action == "ready_to_publish"
    assert queue.candidates[1].ready_for_review is False
    assert queue.candidates[1].publishable is False
    assert queue.candidates[1].blocked_reason == "invalid_candidate_bundle"
    assert queue.candidates[1].recommended_next_action == "fix_validation_errors"
    assert queue.candidates[1].validation_errors


def test_inspect_candidate_bundle_directory_surfaces_publishability_blockers(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_skill(
        canonical_root,
        name="repo-surveyor",
        description="Canonical repo survey skill.",
        keywords=["repo", "survey"],
    )
    _write_catalog(
        canonical_root,
        [_repo_surveyor_catalog_entry()],
        snapshot_version="snapshot-2026-03-24",
    )
    bundles_root = canonical_root / "candidate-bundles"
    _write_candidate_bundle(
        bundles_root,
        name="stale-bundle",
        description="Use when a stale snapshot should block publishability in the queue.",
    )

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    queue = client.inspect_candidate_bundle_directory(str(bundles_root))

    assert queue is not None
    assert queue.total_candidates == 1
    assert queue.scanned_candidates == 1
    assert queue.ready_candidates == 0
    assert queue.blocked_candidates == 1
    assert queue.action_counts == {"refresh_against_live_canon": 1}
    assert queue.action_filter is None
    assert queue.candidates[0].ready_for_review is True
    assert queue.candidates[0].publishable is False
    assert queue.candidates[0].blocked_reason == "stale_registry_snapshot"
    assert queue.candidates[0].recommended_next_action == "refresh_against_live_canon"


def test_inspect_candidate_bundle_blockers_returns_only_blocked_candidates(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_skill(
        canonical_root,
        name="repo-surveyor",
        description="Canonical repo survey skill.",
        keywords=["repo", "survey"],
    )
    _write_catalog(
        canonical_root,
        [_repo_surveyor_catalog_entry()],
        snapshot_version="snapshot-2026-03-24",
    )
    bundles_root = canonical_root / "candidate-bundles"
    _write_candidate_bundle(
        bundles_root,
        name="ready-bundle",
        description="Use when a ready bundle should stay out of the blockers queue.",
        registry_overrides={"registry_snapshot_version": "snapshot-2026-03-24"},
    )
    _write_candidate_bundle(
        bundles_root,
        name="stale-bundle",
        description="Use when a stale bundle should appear in the blockers queue.",
    )

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    blockers = client.inspect_candidate_bundle_blockers(str(bundles_root))

    assert blockers is not None
    assert blockers.scanned_candidates == 2
    assert blockers.blocked_candidates == 1
    assert blockers.action_counts == {"refresh_against_live_canon": 1}
    assert blockers.action_filter is None
    assert len(blockers.candidates) == 1
    assert blockers.candidates[0].review.skill_name == "stale-bundle"
    assert blockers.candidates[0].publishable is False
    assert blockers.candidates[0].blocked_reason == "stale_registry_snapshot"
    assert blockers.candidates[0].recommended_next_action == "refresh_against_live_canon"


def test_inspect_candidate_bundle_directory_filters_by_action(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_skill(
        canonical_root,
        name="repo-surveyor",
        description="Canonical repo survey skill.",
        keywords=["repo", "survey"],
    )
    _write_catalog(
        canonical_root,
        [_repo_surveyor_catalog_entry()],
        snapshot_version="snapshot-2026-03-24",
    )
    bundles_root = canonical_root / "candidate-bundles"
    _write_candidate_bundle(
        bundles_root,
        name="ready-bundle",
        description="Use when a ready bundle should remain publishable.",
        registry_overrides={"registry_snapshot_version": "snapshot-2026-03-24"},
    )
    _write_candidate_bundle(
        bundles_root,
        name="stale-bundle",
        description="Use when a stale bundle should require a canon refresh.",
    )

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    queue = client.inspect_candidate_bundle_directory(
        str(bundles_root),
        action="refresh_against_live_canon",
    )

    assert queue is not None
    assert queue.scanned_candidates == 2
    assert queue.total_candidates == 1
    assert queue.blocked_candidates == 1
    assert queue.ready_candidates == 0
    assert queue.action_counts == {
        "ready_to_publish": 1,
        "refresh_against_live_canon": 1,
    }
    assert queue.action_filter == "refresh_against_live_canon"
    assert len(queue.candidates) == 1
    assert queue.candidates[0].review.skill_name == "stale-bundle"


def test_inspect_candidate_bundle_blockers_filters_by_action(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_skill(
        canonical_root,
        name="repo-surveyor",
        description="Canonical repo survey skill.",
        keywords=["repo", "survey"],
    )
    _write_catalog(
        canonical_root,
        [_repo_surveyor_catalog_entry()],
        snapshot_version="snapshot-2026-03-24",
    )
    bundles_root = canonical_root / "candidate-bundles"
    _write_candidate_bundle(
        bundles_root,
        name="stale-bundle",
        description="Use when a stale bundle should require a canon refresh.",
    )
    invalid_bundle = _write_candidate_bundle(
        bundles_root,
        name="invalid-bundle",
        description="Use when a bundle should fail validation.",
    )
    registry_path = invalid_bundle / "REGISTRY.json"
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    payload["nearest_canonical"] = None
    registry_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    blockers = client.inspect_candidate_bundle_blockers(
        str(bundles_root),
        action="refresh_against_live_canon",
    )

    assert blockers is not None
    assert blockers.scanned_candidates == 2
    assert blockers.blocked_candidates == 1
    assert blockers.action_counts == {
        "fix_validation_errors": 1,
        "refresh_against_live_canon": 1,
    }
    assert blockers.action_filter == "refresh_against_live_canon"
    assert len(blockers.candidates) == 1
    assert blockers.candidates[0].review.skill_name == "stale-bundle"


def test_validate_candidate_bundle_rejects_missing_variant_context(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_catalog(canonical_root, [])
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="hidden-repo-surveyor",
        description="Use when inspecting hidden directories and orchestration files in a repository.",
    )
    registry_path = bundle_dir / "REGISTRY.json"
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    payload["nearest_canonical"] = None
    registry_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    validation = client.validate_candidate_bundle(str(bundle_dir))

    assert validation.valid is False
    assert any("nearest_canonical" in error for error in validation.errors)
    assert client.submit_candidate_bundle(str(bundle_dir)) is None


def test_install_candidate_bundle_requires_explicit_policy_for_challengers(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_catalog(canonical_root, [])
    bundle_dir = _write_candidate_bundle(
        canonical_root / "candidate-bundles",
        name="hidden-repo-surveyor",
        description="Use when inspecting hidden directories and orchestration files in a repository.",
    )

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    assert client.install_candidate_bundle(str(bundle_dir)) is None

    installed = client.install_candidate_bundle(
        str(bundle_dir),
        policy=SkillInstallPolicy(allow_challengers=True),
    )

    assert installed is not None
    assert installed.name == "hidden-repo-surveyor"
    assert installed.lifecycle_stage == SkillLifecycleStage.CHALLENGER
    assert installed.trust_level == TrustLevel.PROBATION
    assert installed.packaging_allowed is True
    assert (install_root / "hidden-repo-surveyor" / "MINER_REPORT.md").exists()


def test_local_skill_without_metadata_defaults_to_untrusted_draft(tmp_path: Path) -> None:
    install_root = tmp_path / "installed"
    install_root.mkdir()
    _write_local_skill(
        install_root,
        name="ad-hoc-skill",
        description="Use when trying an unmanaged local draft skill.",
    )

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(tmp_path / "canonical"),
        host_root=str(install_root),
    )

    installed = client.list_installed_skills()

    assert len(installed) == 1
    assert installed[0].name == "ad-hoc-skill"
    assert installed[0].trust_level == TrustLevel.UNTRUSTED
    assert installed[0].install_state == SkillInstallState.DRAFT
    assert installed[0].lifecycle_stage == SkillLifecycleStage.DRAFT


@pytest.mark.asyncio
async def test_canonical_install_and_submission_preserve_binary_files(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_skill(
        canonical_root,
        name="diagram-skill",
        description="Use when packaging diagram assets alongside skill instructions.",
        keywords=["diagram", "asset", "image"],
    )
    binary_payload = b"\x89PNG\r\n\x1a\nbinary-skill-asset"
    asset_path = canonical_root / "skills" / "diagram-skill" / "assets" / "icon.png"
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(binary_payload)
    _write_catalog(
        canonical_root,
        [
            {
                "name": "diagram-skill",
                "description": "Use when packaging diagram assets alongside skill instructions.",
                "keywords": ["diagram", "asset", "image"],
                "relative_path": "skills/diagram-skill",
                "trust_level": "trusted",
                "source_type": "canonical",
                "repo": DEFAULT_CANONICAL_REPO_SLUG,
            }
        ],
    )

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    result = await client.acquire_skill("diagram asset image")

    assert result.success is True
    installed_asset = install_root / "diagram-skill" / "assets" / "icon.png"
    assert installed_asset.read_bytes() == binary_payload

    submission = client.submit_skill("diagram-skill")

    assert submission is not None
    assert submission.files["skills/diagram-skill/SKILL.md"].startswith("---")
    assert submission.binary_files["skills/diagram-skill/assets/icon.png"] == base64.b64encode(
        binary_payload
    ).decode("ascii")


def test_client_construction_is_lazy_for_provider_and_canonical_bootstrap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_root = tmp_path / "installed"
    install_root.mkdir()
    canonical_root = tmp_path / "canonical"

    provider_created = False
    checkout_attempted = False

    def fail_provider(*args: object, **kwargs: object) -> object:
        nonlocal provider_created
        provider_created = True
        raise AssertionError("provider should not be created during client construction")

    def fail_checkout(self: object) -> bool:
        nonlocal checkout_attempted
        checkout_attempted = True
        raise AssertionError("canonical checkout should not happen during client construction")

    monkeypatch.setattr("synthesis.client.create_provider", fail_provider)
    monkeypatch.setattr("synthesis.skill_runtime.CanonicalSkillRepository.ensure_local_checkout", fail_checkout)

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    assert client.list_installed_skills() == []
    assert provider_created is False
    assert checkout_attempted is False


@pytest.mark.asyncio
async def test_submit_skill_marks_local_draft_as_submitted_challenger(
    skill_roots: tuple[Path, Path],
) -> None:
    canonical_root, install_root = skill_roots
    _write_catalog(canonical_root, [])

    client = SynthesisClient(
        provider_type="mock",
        canonical_repo_path=str(canonical_root),
        host_root=str(install_root),
    )

    result = await client.acquire_skill("triage support tickets", requirements="Use skill packages")

    assert result.primary_skill is not None
    submission = client.submit_skill(result.primary_skill.name)

    assert submission is not None
    assert submission.lifecycle_stage == SkillLifecycleStage.CHALLENGER
    assert submission.capability_family == result.primary_skill.name
    assert submission.trust_level == TrustLevel.PROBATION

    installed = client.inspect_skill(result.primary_skill.name)

    assert installed is not None
    assert installed.install_state == SkillInstallState.SUBMITTED
    assert installed.trust_level == TrustLevel.PROBATION
    assert installed.lifecycle_stage == SkillLifecycleStage.CHALLENGER
