"""Packaging and public surface checks for the open-source project."""

from __future__ import annotations

import importlib
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_project_metadata_files_exist() -> None:
    """The root open-source files referenced by packaging should exist."""
    assert (ROOT / "README.md").exists()
    assert (ROOT / "CHANGELOG.md").exists()
    assert (ROOT / "LICENSE").exists()
    assert (ROOT / "CONTRIBUTING.md").exists()
    assert (ROOT / "CODE_OF_CONDUCT.md").exists()
    assert (ROOT / "SECURITY.md").exists()
    assert (ROOT / "docs" / "releasing.md").exists()


def test_console_script_targets_are_importable_callables() -> None:
    """Console script entrypoints should resolve to callable objects."""
    with (ROOT / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)

    scripts = data["project"]["scripts"]
    assert scripts

    for target in scripts.values():
        module_name, attr_name = target.split(":", 1)
        module = importlib.import_module(module_name)
        attr = getattr(module, attr_name)
        assert callable(attr), f"{target} must resolve to a callable"


def test_synthesis_public_imports_are_available() -> None:
    """The root package should expose the documented public API."""
    synthesis = importlib.import_module("synthesis")

    assert hasattr(synthesis, "SynthesisClient")
    assert hasattr(synthesis, "SynthesisMCPServer")
    assert hasattr(synthesis, "SkillAcquisitionResult")
    assert hasattr(synthesis, "CandidateBundleInspection")
    assert hasattr(synthesis, "CandidateBundlePublishability")
    assert hasattr(synthesis, "CandidateBundleBlockerQueue")
    assert hasattr(synthesis, "CandidateBundleReview")
    assert hasattr(synthesis, "CandidateBundleReviewQueue")
    assert hasattr(synthesis, "CandidateBundleSubmissionEnvelope")
    assert hasattr(synthesis, "SubmissionAutomationResult")
    assert hasattr(synthesis, "SkillInstallPolicy")
    assert hasattr(synthesis, "SkillLifecycleStage")


def test_project_urls_point_to_public_release_surfaces() -> None:
    """Public package metadata should point at the real repo and website."""
    with (ROOT / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)

    urls = data["project"]["urls"]

    assert urls["Homepage"] == "https://synthesis.making-minds.ai"
    assert urls["Repository"] == "https://github.com/anthony-maio/synthesis"
