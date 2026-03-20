"""Tests for the skill-first Synthesis client."""

import base64
import json
from pathlib import Path

import pytest

from synthesis import (
    ResolutionMethod,
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


def _write_catalog(repo_root: Path, entries: list[dict]) -> None:
    catalog_dir = repo_root / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    (catalog_dir / "skills.json").write_text(
        json.dumps({"skills": entries}, indent=2),
        encoding="utf-8",
    )


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
            }
        ],
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
        "list_installed_skills",
        "submit_skill",
    }

    response = await server.call_tool("acquire_skill", {"intent": "draft release notes"})
    payload = json.loads(response)

    assert payload["success"] is True
    assert payload["primary_skill"]["name"] == "release-notes"


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
