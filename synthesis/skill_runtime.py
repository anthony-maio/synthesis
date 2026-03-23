"""Skill-first repositories, synthesis, and host installation helpers."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from synthesis.core.models import (
    SkillCompositionBundle,
    SkillDraft,
    SkillInstallState,
    SkillLifecycleStage,
    SkillRecord,
    SkillSource,
    SkillSourceType,
    SkillSubmission,
    TrustLevel,
)
from synthesis.llm.provider import LLMProvider

STOP_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "for",
    "from",
    "into",
    "of",
    "or",
    "the",
    "this",
    "to",
    "with",
}

SYNONYM_MAP = {
    "repository": "repo",
    "repos": "repo",
    "files": "file",
    "parsing": "parse",
    "formatted": "format",
    "formatting": "format",
}

DEFAULT_CANONICAL_REPO_SLUG = "anthony-maio/synthesis-skills"
DEFAULT_CANONICAL_REPO_URL = f"https://github.com/{DEFAULT_CANONICAL_REPO_SLUG}.git"
DEFAULT_CANONICAL_REPO_DIRNAME = "synthesis-skills"


def default_canonical_repo_path() -> Path:
    """Return the default local checkout path for the canonical registry."""
    configured = os.getenv("SYNTHESIS_CANONICAL_REPO_PATH")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".synthesis" / "canonical" / DEFAULT_CANONICAL_REPO_DIRNAME


def default_canonical_repo_slug() -> str:
    """Return the configured canonical registry slug."""
    return os.getenv("SYNTHESIS_CANONICAL_REPO_SLUG", DEFAULT_CANONICAL_REPO_SLUG)


def default_canonical_repo_url() -> str:
    """Return the configured canonical registry clone URL."""
    return os.getenv("SYNTHESIS_CANONICAL_REPO_URL", DEFAULT_CANONICAL_REPO_URL)


def slugify(text: str) -> str:
    """Create a filesystem-safe skill name from free text."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "generated-skill"


def normalize_token(token: str) -> str:
    """Normalize one token for matching."""
    token = token.lower().strip()
    return SYNONYM_MAP.get(token, token)


def tokenize(text: str) -> List[str]:
    """Extract normalized tokens from search text."""
    tokens = [normalize_token(token) for token in re.findall(r"[a-z0-9]+", text.lower())]
    return [token for token in tokens if token and token not in STOP_WORDS]


def parse_front_matter(text: str) -> Dict[str, object]:
    """Parse the small YAML subset used by skill front matter."""
    if not text.startswith("---"):
        return {}

    lines = text.splitlines()
    if len(lines) < 3:
        return {}

    payload: Dict[str, object] = {}
    current_list_key: Optional[str] = None
    for line in lines[1:]:
        if line.strip() == "---":
            break

        if not line.strip():
            continue

        if re.match(r"^[A-Za-z0-9_-]+:\s*", line):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                payload[key] = value
                current_list_key = None
            else:
                payload[key] = []
                current_list_key = key
            continue

        if current_list_key and line.strip().startswith("- "):
            items = payload.setdefault(current_list_key, [])
            if isinstance(items, list):
                items.append(line.strip()[2:].strip())

    return payload


def render_skill_markdown(name: str, description: str, keywords: List[str], intent: str) -> str:
    """Create a minimal compatible skill file."""
    header = [
        "---",
        f"name: {name}",
        f"description: {description}",
        "keywords:",
        *[f"  - {keyword}" for keyword in keywords],
        "---",
        "",
        f"# {name}",
        "",
        "## Overview",
        "",
        description,
        "",
        "## Workflow",
        "",
        "1. Restate the user's goal and constraints.",
        "2. Inspect the relevant repository state before making changes.",
        "3. Prefer composition of existing tools or skills before creating new assets.",
        f"4. Execute the work needed for: {intent}.",
        "",
        "## Notes",
        "",
        "Keep outputs concise, practical, and grounded in the current workspace.",
    ]
    return "\n".join(header)


def render_registry_metadata(
    *,
    capability_family: str,
    lifecycle_stage: SkillLifecycleStage,
    trust_level: TrustLevel,
    is_primary: bool,
    variant_of: Optional[str] = None,
    supersedes: Optional[List[str]] = None,
    submission_type: Optional[str] = None,
    nearest_canonical: Optional[str] = None,
    evidence_summary: Optional[str] = None,
) -> str:
    """Render canonical registry governance metadata as JSON."""
    payload = {
        "capability_family": capability_family,
        "lifecycle_stage": lifecycle_stage.value,
        "trust_level": trust_level.value,
        "is_primary": is_primary,
        "variant_of": variant_of,
        "supersedes": supersedes or [],
        "submission_type": submission_type,
        "nearest_canonical": nearest_canonical,
        "evidence_summary": evidence_summary,
    }
    return json.dumps(payload, indent=2) + "\n"


def render_provenance_metadata(
    *,
    name: str,
    source_type: SkillSourceType,
    upstream: Optional[str] = None,
) -> str:
    """Render provenance metadata for synthesized or curated skill submissions."""
    if source_type == SkillSourceType.CANONICAL and upstream:
        payload = {
            "kind": "mirrored_external",
            "author": "Synthesis",
            "source": upstream,
            "upstream": upstream,
            "source_license": "unknown",
            "notes": f"Submitted from a canonical skill snapshot for {name}.",
        }
    else:
        payload = {
            "kind": "first_party",
            "author": "Synthesis",
            "source": f"synthesis://local-draft/{name}",
            "notes": "Synthesized locally from a live task and prepared for registry review.",
        }
    return json.dumps(payload, indent=2) + "\n"


def build_skill_record(
    *,
    name: str,
    description: str,
    keywords: Iterable[str],
    trust_level: TrustLevel,
    source_type: SkillSourceType,
    repo: Optional[str],
    relative_path: Optional[str],
    install_root: Optional[str] = None,
    upstream: Optional[str] = None,
    install_state: SkillInstallState = SkillInstallState.DISCOVERED,
    lifecycle_stage: SkillLifecycleStage = SkillLifecycleStage.DRAFT,
    capability_family: Optional[str] = None,
    is_primary: bool = False,
    variant_of: Optional[str] = None,
    variant_reason: Optional[str] = None,
    supersedes: Optional[List[str]] = None,
    submission_type: Optional[str] = None,
    nearest_canonical: Optional[str] = None,
    evidence_summary: Optional[str] = None,
    family_confidence: Optional[float] = None,
    disposition_confidence: Optional[float] = None,
    disposition_reason_codes: Optional[List[str]] = None,
    registry_snapshot_version: Optional[str] = None,
    license_status: Optional[str] = None,
    license_expression: Optional[str] = None,
    packaging_allowed: Optional[bool] = None,
    source_commit: Optional[str] = None,
    source_fingerprint: Optional[str] = None,
    score: float = 0.0,
) -> SkillRecord:
    """Construct a skill record with normalized values."""
    normalized_keywords = sorted({normalize_token(token) for token in keywords if token})
    return SkillRecord(
        name=name,
        description=description,
        keywords=normalized_keywords,
        trust_level=trust_level,
        source=SkillSource(
            type=source_type,
            repo=repo,
            relative_path=relative_path,
            install_root=install_root,
            upstream=upstream,
            commit=source_commit,
            fingerprint=source_fingerprint,
        ),
        install_state=install_state,
        lifecycle_stage=lifecycle_stage,
        capability_family=capability_family or name,
        is_primary=is_primary,
        variant_of=variant_of,
        variant_reason=variant_reason,
        supersedes=supersedes or [],
        submission_type=submission_type,
        nearest_canonical=nearest_canonical,
        evidence_summary=evidence_summary,
        family_confidence=family_confidence,
        disposition_confidence=disposition_confidence,
        disposition_reason_codes=disposition_reason_codes or [],
        registry_snapshot_version=registry_snapshot_version,
        license_status=license_status,
        license_expression=license_expression,
        packaging_allowed=packaging_allowed,
        relative_path=relative_path,
        install_path=str(Path(install_root) / name) if install_root else None,
        score=score,
    )


def _coerce_text_content(content: str | bytes) -> str:
    """Decode UTF-8 skill text payloads."""
    if isinstance(content, bytes):
        return content.decode("utf-8")
    return content


def _coerce_binary_content(content: str | bytes) -> bytes:
    """Encode text payloads for binary-safe package writes."""
    if isinstance(content, bytes):
        return content
    return content.encode("utf-8")


class LocalSkillRepository:
    """Discovers and reads installed skills from the host root."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)

    def list_skills(self) -> List[SkillRecord]:
        """Return all installed skills."""
        skills: List[SkillRecord] = []
        for skill_dir in sorted(self.root.iterdir()):
            skill_file = skill_dir / "SKILL.md"
            if not skill_dir.is_dir() or not skill_file.exists():
                continue

            metadata = parse_front_matter(skill_file.read_text(encoding="utf-8"))
            install_metadata = self._read_install_metadata(skill_dir)
            skills.append(
                build_skill_record(
                    name=str(metadata.get("name", skill_dir.name)),
                    description=str(metadata.get("description", "")),
                    keywords=_coerce_keywords(metadata.get("keywords")),
                    trust_level=TrustLevel(
                        install_metadata.get("trust_level", TrustLevel.UNTRUSTED.value)
                    ),
                    source_type=SkillSourceType(
                        install_metadata.get("source_type", SkillSourceType.LOCAL.value)
                    ),
                    repo=_coerce_optional(install_metadata.get("repo")),
                    relative_path=skill_dir.name,
                    install_root=str(self.root),
                    upstream=_coerce_optional(install_metadata.get("upstream")),
                    install_state=SkillInstallState(
                        install_metadata.get("install_state", SkillInstallState.DRAFT.value)
                    ),
                    lifecycle_stage=SkillLifecycleStage(
                        install_metadata.get(
                            "lifecycle_stage", SkillLifecycleStage.DRAFT.value
                        )
                    ),
                    capability_family=_coerce_optional(
                        install_metadata.get("capability_family")
                    )
                    or skill_dir.name,
                    is_primary=bool(install_metadata.get("is_primary", False)),
                    variant_of=_coerce_optional(install_metadata.get("variant_of")),
                    variant_reason=_coerce_optional(install_metadata.get("variant_reason")),
                    supersedes=_coerce_keywords(install_metadata.get("supersedes")),
                    submission_type=_coerce_optional(install_metadata.get("submission_type")),
                    nearest_canonical=_coerce_optional(
                        install_metadata.get("nearest_canonical")
                    ),
                    evidence_summary=_coerce_optional(
                        install_metadata.get("evidence_summary")
                    ),
                    family_confidence=_coerce_float(
                        install_metadata.get("family_confidence")
                    ),
                    disposition_confidence=_coerce_float(
                        install_metadata.get("disposition_confidence")
                    ),
                    disposition_reason_codes=_coerce_keywords(
                        install_metadata.get("disposition_reason_codes")
                    ),
                    registry_snapshot_version=_coerce_optional(
                        install_metadata.get("registry_snapshot_version")
                    ),
                    license_status=_coerce_optional(install_metadata.get("license_status")),
                    license_expression=_coerce_optional(
                        install_metadata.get("license_expression")
                    ),
                    packaging_allowed=_coerce_optional_bool(
                        install_metadata.get("packaging_allowed")
                    ),
                    source_commit=_coerce_optional(install_metadata.get("source_commit")),
                    source_fingerprint=_coerce_optional(
                        install_metadata.get("source_fingerprint")
                    ),
                )
            )
        return skills

    def get(self, name: str) -> Optional[SkillRecord]:
        """Get an installed skill by name."""
        for skill in self.list_skills():
            if skill.name == name:
                return skill
        return None

    def install_files(
        self,
        *,
        name: str,
        files: Dict[str, str | bytes],
        trust_level: TrustLevel,
        source_type: SkillSourceType,
        repo: Optional[str],
        upstream: Optional[str] = None,
        install_state: SkillInstallState = SkillInstallState.INSTALLED,
        lifecycle_stage: SkillLifecycleStage = SkillLifecycleStage.DRAFT,
        capability_family: Optional[str] = None,
        is_primary: bool = False,
        variant_of: Optional[str] = None,
        variant_reason: Optional[str] = None,
        supersedes: Optional[List[str]] = None,
        submission_type: Optional[str] = None,
        nearest_canonical: Optional[str] = None,
        evidence_summary: Optional[str] = None,
        family_confidence: Optional[float] = None,
        disposition_confidence: Optional[float] = None,
        disposition_reason_codes: Optional[List[str]] = None,
        registry_snapshot_version: Optional[str] = None,
        license_status: Optional[str] = None,
        license_expression: Optional[str] = None,
        packaging_allowed: Optional[bool] = None,
        source_commit: Optional[str] = None,
        source_fingerprint: Optional[str] = None,
    ) -> SkillRecord:
        """Install a synthesized or copied skill into the host root."""
        target_dir = self.root / name
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        for relative_path, content in files.items():
            file_path = target_dir / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(_coerce_binary_content(content))

        metadata_path = target_dir / ".synthesis.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "trust_level": trust_level.value,
                    "source_type": source_type.value,
                    "repo": repo,
                    "upstream": upstream,
                    "install_state": install_state.value,
                    "lifecycle_stage": lifecycle_stage.value,
                    "capability_family": capability_family or name,
                    "is_primary": is_primary,
                    "variant_of": variant_of,
                    "variant_reason": variant_reason,
                    "supersedes": supersedes or [],
                    "submission_type": submission_type,
                    "nearest_canonical": nearest_canonical,
                    "evidence_summary": evidence_summary,
                    "family_confidence": family_confidence,
                    "disposition_confidence": disposition_confidence,
                    "disposition_reason_codes": disposition_reason_codes or [],
                    "registry_snapshot_version": registry_snapshot_version,
                    "license_status": license_status,
                    "license_expression": license_expression,
                    "packaging_allowed": packaging_allowed,
                    "source_commit": source_commit,
                    "source_fingerprint": source_fingerprint,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        metadata = parse_front_matter(_coerce_text_content(files.get("SKILL.md", "")))
        return build_skill_record(
            name=str(metadata.get("name", name)),
            description=str(metadata.get("description", "")),
            keywords=_coerce_keywords(metadata.get("keywords")),
            trust_level=trust_level,
            source_type=source_type,
            repo=repo,
            relative_path=name,
            install_root=str(self.root),
            upstream=upstream,
            install_state=install_state,
            lifecycle_stage=lifecycle_stage,
            capability_family=capability_family or name,
            is_primary=is_primary,
            variant_of=variant_of,
            variant_reason=variant_reason,
            supersedes=supersedes,
            submission_type=submission_type,
            nearest_canonical=nearest_canonical,
            evidence_summary=evidence_summary,
            family_confidence=family_confidence,
            disposition_confidence=disposition_confidence,
            disposition_reason_codes=disposition_reason_codes,
            registry_snapshot_version=registry_snapshot_version,
            license_status=license_status,
            license_expression=license_expression,
            packaging_allowed=packaging_allowed,
            source_commit=source_commit,
            source_fingerprint=source_fingerprint,
        )

    def update_metadata(
        self,
        name: str,
        *,
        trust_level: Optional[TrustLevel] = None,
        install_state: Optional[SkillInstallState] = None,
        lifecycle_stage: Optional[SkillLifecycleStage] = None,
        capability_family: Optional[str] = None,
        is_primary: Optional[bool] = None,
        variant_of: Optional[str] = None,
        variant_reason: Optional[str] = None,
        supersedes: Optional[List[str]] = None,
        submission_type: Optional[str] = None,
        nearest_canonical: Optional[str] = None,
        evidence_summary: Optional[str] = None,
        family_confidence: Optional[float] = None,
        disposition_confidence: Optional[float] = None,
        disposition_reason_codes: Optional[List[str]] = None,
        registry_snapshot_version: Optional[str] = None,
        license_status: Optional[str] = None,
        license_expression: Optional[str] = None,
        packaging_allowed: Optional[bool] = None,
        source_commit: Optional[str] = None,
        source_fingerprint: Optional[str] = None,
    ) -> Optional[SkillRecord]:
        """Update the local sidecar metadata for one installed skill."""
        skill_dir = self.root / name
        skill_file = skill_dir / "SKILL.md"
        metadata_path = skill_dir / ".synthesis.json"
        if not skill_file.exists():
            return None

        existing = self._read_install_metadata(skill_dir)
        if trust_level is not None:
            existing["trust_level"] = trust_level.value
        if install_state is not None:
            existing["install_state"] = install_state.value
        if lifecycle_stage is not None:
            existing["lifecycle_stage"] = lifecycle_stage.value
        if capability_family is not None:
            existing["capability_family"] = capability_family
        if is_primary is not None:
            existing["is_primary"] = is_primary
        if variant_of is not None:
            existing["variant_of"] = variant_of
        if variant_reason is not None:
            existing["variant_reason"] = variant_reason
        if supersedes is not None:
            existing["supersedes"] = supersedes
        if submission_type is not None:
            existing["submission_type"] = submission_type
        if nearest_canonical is not None:
            existing["nearest_canonical"] = nearest_canonical
        if evidence_summary is not None:
            existing["evidence_summary"] = evidence_summary
        if family_confidence is not None:
            existing["family_confidence"] = family_confidence
        if disposition_confidence is not None:
            existing["disposition_confidence"] = disposition_confidence
        if disposition_reason_codes is not None:
            existing["disposition_reason_codes"] = disposition_reason_codes
        if registry_snapshot_version is not None:
            existing["registry_snapshot_version"] = registry_snapshot_version
        if license_status is not None:
            existing["license_status"] = license_status
        if license_expression is not None:
            existing["license_expression"] = license_expression
        if packaging_allowed is not None:
            existing["packaging_allowed"] = packaging_allowed
        if source_commit is not None:
            existing["source_commit"] = source_commit
        if source_fingerprint is not None:
            existing["source_fingerprint"] = source_fingerprint

        metadata_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        return self.get(name)

    def _read_install_metadata(self, skill_dir: Path) -> Dict[str, object]:
        """Read the local Synthesis metadata sidecar if it exists."""
        metadata_path = skill_dir / ".synthesis.json"
        if not metadata_path.exists():
            return {}
        try:
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}


class CanonicalSkillRepository:
    """Searchable canonical skill registry rooted in a Git repo checkout."""

    def __init__(
        self,
        root: str | Path | None = None,
        repo_slug: Optional[str] = None,
        remote_url: Optional[str] = None,
        auto_bootstrap: bool = True,
    ):
        self.root = Path(root).expanduser() if root else default_canonical_repo_path()
        self.repo_slug = repo_slug or default_canonical_repo_slug()
        self.remote_url = remote_url or default_canonical_repo_url()
        self.catalog_path = self.root / "catalog" / "skills.json"
        if auto_bootstrap:
            self.ensure_local_checkout()

    def is_available(self) -> bool:
        """Whether the canonical repo exists locally."""
        return self.catalog_path.exists() or (self.root / "skills").exists()

    def ensure_local_checkout(self) -> bool:
        """Clone the canonical repo on first use when it is missing."""
        if self.is_available():
            return True

        if self.root.exists():
            return False

        git_executable = shutil.which("git")
        if not git_executable:
            return False

        self.root.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                [git_executable, "clone", "--depth", "1", self.remote_url, str(self.root)],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return False

        return self.is_available()

    def list_skills(self) -> List[SkillRecord]:
        """Load the generated catalog if it exists."""
        if self.catalog_path.exists():
            data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            entries = data.get("skills", [])
            return [self._record_from_catalog(entry) for entry in entries]

        skills: List[SkillRecord] = []
        skills_root = self.root / "skills"
        if not skills_root.exists():
            return skills

        for skill_dir in sorted(skills_root.iterdir()):
            skill_file = skill_dir / "SKILL.md"
            if not skill_dir.is_dir() or not skill_file.exists():
                continue
            metadata = parse_front_matter(skill_file.read_text(encoding="utf-8"))
            skills.append(
                build_skill_record(
                    name=str(metadata.get("name", skill_dir.name)),
                    description=str(metadata.get("description", "")),
                    keywords=_coerce_keywords(metadata.get("keywords")),
                    trust_level=TrustLevel.TRUSTED,
                    source_type=SkillSourceType.CANONICAL,
                    repo=self.repo_slug,
                    relative_path=str(Path("skills") / skill_dir.name),
                    lifecycle_stage=SkillLifecycleStage.CANONICAL,
                    capability_family=skill_dir.name,
                    is_primary=True,
                )
            )
        return skills

    def search(self, intent: str) -> List[SkillRecord]:
        """Return ranked canonical skills for an intent."""
        query_tokens = set(tokenize(intent))
        ranked = []
        for skill in self.list_skills():
            score = score_skill(skill, query_tokens)
            if score > 0:
                ranked.append(skill.model_copy(update={"score": score}))
        ranked.sort(key=lambda record: record.score, reverse=True)
        return ranked

    def load_files(self, skill: SkillRecord) -> Dict[str, bytes]:
        """Read all files for a skill package from the canonical repo."""
        if not skill.relative_path:
            raise ValueError("Skill has no relative path")

        source_dir = self.root / skill.relative_path
        files: Dict[str, bytes] = {}
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                files[str(file_path.relative_to(source_dir)).replace("\\", "/")] = file_path.read_bytes()
        return files

    def prepare_submission(self, draft: SkillDraft) -> SkillSubmission:
        """Create a PR-ready submission object for a draft skill."""
        capability_family = draft.capability_family or draft.name
        evidence_summary = (
            draft.evaluation_scenarios[0] if draft.evaluation_scenarios else None
        )
        files = {
            f"skills/{draft.name}/{path}": content
            for path, content in draft.files.items()
        }
        files.setdefault(
            f"skills/{draft.name}/REGISTRY.json",
            render_registry_metadata(
                capability_family=capability_family,
                lifecycle_stage=SkillLifecycleStage.CHALLENGER,
                trust_level=TrustLevel.PROBATION,
                is_primary=False,
                submission_type="new_family_candidate",
                nearest_canonical=None,
                evidence_summary=evidence_summary,
            ),
        )
        files.setdefault(
            f"skills/{draft.name}/PROVENANCE.json",
            render_provenance_metadata(name=draft.name, source_type=SkillSourceType.SYNTHESIZED),
        )
        return SkillSubmission(
            repo=self.repo_slug,
            branch=f"synthesis/{draft.name}",
            title=f"Add skill: {draft.name}",
            status="prepared",
            target_path=f"skills/{draft.name}",
            trust_level=TrustLevel.PROBATION,
            lifecycle_stage=SkillLifecycleStage.CHALLENGER,
            capability_family=capability_family,
            submission_type="new_family_candidate",
            evidence_summary=evidence_summary,
            files=files,
            binary_files={},
        )

    def _record_from_catalog(self, entry: Dict[str, object]) -> SkillRecord:
        """Convert a catalog row into a skill record."""
        relative_path = str(entry.get("relative_path", ""))
        trust_level = TrustLevel(str(entry.get("trust_level", TrustLevel.TRUSTED.value)))
        source_type = SkillSourceType(str(entry.get("source_type", SkillSourceType.CANONICAL.value)))
        governance = entry.get("governance", {}) if isinstance(entry.get("governance"), dict) else {}
        return build_skill_record(
            name=str(entry["name"]),
            description=str(entry.get("description", "")),
            keywords=_coerce_keywords(entry.get("keywords")),
            trust_level=trust_level,
            source_type=source_type,
            repo=str(entry.get("repo", self.repo_slug)),
            relative_path=relative_path,
            upstream=_coerce_optional(entry.get("upstream")),
            lifecycle_stage=SkillLifecycleStage(
                str(governance.get("lifecycle_stage", SkillLifecycleStage.CANONICAL.value))
            ),
            capability_family=_coerce_optional(governance.get("capability_family"))
            or str(entry["name"]),
            is_primary=bool(governance.get("is_primary", source_type == SkillSourceType.CANONICAL)),
            variant_of=_coerce_optional(governance.get("variant_of")),
            variant_reason=_coerce_optional(governance.get("variant_reason")),
            supersedes=_coerce_keywords(governance.get("supersedes")),
            submission_type=_coerce_optional(governance.get("submission_type")),
            nearest_canonical=_coerce_optional(governance.get("nearest_canonical")),
            evidence_summary=_coerce_optional(governance.get("evidence_summary")),
            family_confidence=_coerce_float(governance.get("family_confidence")),
            disposition_confidence=_coerce_float(governance.get("disposition_confidence")),
            disposition_reason_codes=_coerce_keywords(
                governance.get("disposition_reason_codes")
            ),
            registry_snapshot_version=_coerce_optional(
                governance.get("registry_snapshot_version")
            ),
            license_status=_coerce_optional(entry.get("license_status")),
            license_expression=_coerce_optional(entry.get("license_expression")),
            packaging_allowed=_coerce_optional_bool(entry.get("packaging_allowed")),
            source_commit=_coerce_optional(entry.get("source_commit")),
            source_fingerprint=_coerce_optional(entry.get("source_fingerprint")),
        )


class CodexHostAdapter:
    """Install skills into a Codex-compatible skill root."""

    def __init__(self, root: str | Path):
        self.repository = LocalSkillRepository(root)

    @property
    def root(self) -> Path:
        """Host install root."""
        return self.repository.root

    def list_installed_skills(self) -> List[SkillRecord]:
        """Return installed skills."""
        return self.repository.list_skills()

    def install_skill_files(
        self,
        *,
        name: str,
        files: Dict[str, str | bytes],
        trust_level: TrustLevel,
        source_type: SkillSourceType,
        repo: Optional[str],
        upstream: Optional[str] = None,
        install_state: SkillInstallState = SkillInstallState.INSTALLED,
        lifecycle_stage: SkillLifecycleStage = SkillLifecycleStage.DRAFT,
        capability_family: Optional[str] = None,
        is_primary: bool = False,
        variant_of: Optional[str] = None,
        variant_reason: Optional[str] = None,
        supersedes: Optional[List[str]] = None,
        submission_type: Optional[str] = None,
        nearest_canonical: Optional[str] = None,
        evidence_summary: Optional[str] = None,
        family_confidence: Optional[float] = None,
        disposition_confidence: Optional[float] = None,
        disposition_reason_codes: Optional[List[str]] = None,
        registry_snapshot_version: Optional[str] = None,
        license_status: Optional[str] = None,
        license_expression: Optional[str] = None,
        packaging_allowed: Optional[bool] = None,
        source_commit: Optional[str] = None,
        source_fingerprint: Optional[str] = None,
    ) -> SkillRecord:
        """Install files into the host root."""
        return self.repository.install_files(
            name=name,
            files=files,
            trust_level=trust_level,
            source_type=source_type,
            repo=repo,
            upstream=upstream,
            install_state=install_state,
            lifecycle_stage=lifecycle_stage,
            capability_family=capability_family,
            is_primary=is_primary,
            variant_of=variant_of,
            variant_reason=variant_reason,
            supersedes=supersedes,
            submission_type=submission_type,
            nearest_canonical=nearest_canonical,
            evidence_summary=evidence_summary,
            family_confidence=family_confidence,
            disposition_confidence=disposition_confidence,
            disposition_reason_codes=disposition_reason_codes,
            registry_snapshot_version=registry_snapshot_version,
            license_status=license_status,
            license_expression=license_expression,
            packaging_allowed=packaging_allowed,
            source_commit=source_commit,
            source_fingerprint=source_fingerprint,
        )

    def activation_message(self) -> str:
        """Instruction for the host agent."""
        return "Restart Codex to pick up newly installed skills."


class SkillSynthesizer:
    """Create compatible draft skill packages from free-text intent."""

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm_provider = llm_provider

    async def synthesize(self, intent: str, requirements: str = "") -> SkillDraft:
        """Generate a deterministic draft skill package."""
        keywords = _keywords_from_intent(intent)
        name = slugify(intent)
        description = f"Use when the user asks to {intent.strip().lower().rstrip('.')}."
        if requirements:
            description = f"{description} Requirements: {requirements.strip()}."

        scenarios = [
            f"Use the skill when the user asks to {intent.strip().lower()}.",
            "Inspect the local repository before proposing changes.",
            "Prefer existing tools and installed skills before creating new assets.",
        ]
        skill_markdown = render_skill_markdown(name, description, keywords, intent)
        return SkillDraft(
            name=name,
            description=description,
            keywords=keywords,
            capability_family=name,
            files={"SKILL.md": skill_markdown},
            evaluation_scenarios=scenarios,
        )


def score_skill(skill: SkillRecord, query_tokens: set[str]) -> float:
    """Rank a skill against a query using keyword overlap."""
    if not query_tokens:
        return 0.0

    skill_tokens = set(tokenize(skill.name))
    skill_tokens.update(tokenize(skill.description))
    skill_tokens.update(skill.keywords)

    overlap = skill_tokens & query_tokens
    return len(overlap) / len(query_tokens)


def compose_skills(intent: str, candidates: List[SkillRecord], minimum_coverage: float) -> Optional[SkillCompositionBundle]:
    """Greedily build a bundle whose combined coverage satisfies the intent."""
    query_tokens = set(tokenize(intent))
    if not query_tokens:
        return None

    bundle: List[SkillRecord] = []
    covered: set[str] = set()
    remaining = sorted(candidates, key=lambda record: record.score, reverse=True)

    while remaining and len(bundle) < 3:
        best_skill = None
        best_new_tokens: set[str] = set()
        for candidate in remaining:
            candidate_tokens = set(tokenize(candidate.name))
            candidate_tokens.update(tokenize(candidate.description))
            candidate_tokens.update(candidate.keywords)
            new_tokens = (candidate_tokens & query_tokens) - covered
            if len(new_tokens) > len(best_new_tokens):
                best_skill = candidate
                best_new_tokens = new_tokens

        if not best_skill or not best_new_tokens:
            break

        bundle.append(best_skill)
        covered.update(best_new_tokens)
        remaining = [candidate for candidate in remaining if candidate.name != best_skill.name]

        coverage = len(covered) / len(query_tokens)
        if coverage >= minimum_coverage and len(bundle) > 1:
            missing = sorted(query_tokens - covered)
            return SkillCompositionBundle(
                intent=intent,
                skills=bundle,
                coverage_ratio=coverage,
                missing_tokens=missing,
            )

    return None


def _coerce_keywords(value: object) -> List[str]:
    """Normalize keyword sources into a list."""
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value:
        return [value]
    return []


def _coerce_optional(value: object) -> Optional[str]:
    """Return a string or None."""
    if value is None:
        return None
    text = str(value)
    return text or None


def _coerce_float(value: object) -> Optional[float]:
    """Return a float or None."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_bool(value: object) -> Optional[bool]:
    """Return a bool or None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def _read_json_file(path: Path) -> Dict[str, object]:
    """Read one JSON file, returning an empty object on failure."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _bundle_source_type(provenance: Dict[str, object]) -> SkillSourceType:
    """Map provenance kind to a best-effort source type."""
    kind = _coerce_optional(provenance.get("kind"))
    if kind in {"mirrored_external", "adapted_external"}:
        return SkillSourceType.CURATED
    if kind == "first_party":
        return SkillSourceType.SYNTHESIZED
    return SkillSourceType.LOCAL


def load_candidate_bundle(
    bundle_path: str | Path,
    *,
    repo: Optional[str] = None,
) -> tuple[SkillRecord, Dict[str, str], Dict[str, bytes]]:
    """Load a miner-produced challenger bundle from disk."""
    root = Path(bundle_path).expanduser()
    skill_file = root / "SKILL.md"
    registry_file = root / "REGISTRY.json"
    provenance_file = root / "PROVENANCE.json"
    if not root.is_dir() or not skill_file.exists() or not registry_file.exists() or not provenance_file.exists():
        raise FileNotFoundError("Candidate bundle must include SKILL.md, REGISTRY.json, and PROVENANCE.json")

    front_matter = parse_front_matter(skill_file.read_text(encoding="utf-8"))
    governance = _read_json_file(registry_file)
    provenance = _read_json_file(provenance_file)

    text_files: Dict[str, str] = {}
    binary_files: Dict[str, bytes] = {}
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        relative_path = str(file_path.relative_to(root)).replace("\\", "/")
        payload = file_path.read_bytes()
        if b"\x00" in payload:
            binary_files[relative_path] = payload
            continue
        try:
            text_files[relative_path] = payload.decode("utf-8")
        except UnicodeDecodeError:
            binary_files[relative_path] = payload

    record = build_skill_record(
        name=str(front_matter.get("name", root.name)),
        description=str(front_matter.get("description", "")),
        keywords=_coerce_keywords(front_matter.get("keywords")),
        trust_level=TrustLevel(str(governance.get("trust_level", TrustLevel.PROBATION.value))),
        source_type=_bundle_source_type(provenance),
        repo=repo,
        relative_path=root.name,
        upstream=_coerce_optional(provenance.get("upstream"))
        or _coerce_optional(provenance.get("source")),
        install_state=SkillInstallState.SUBMITTED,
        lifecycle_stage=SkillLifecycleStage(
            str(governance.get("lifecycle_stage", SkillLifecycleStage.CHALLENGER.value))
        ),
        capability_family=_coerce_optional(governance.get("capability_family")) or root.name,
        is_primary=bool(governance.get("is_primary", False)),
        variant_of=_coerce_optional(governance.get("variant_of")),
        variant_reason=_coerce_optional(governance.get("variant_reason")),
        supersedes=_coerce_keywords(governance.get("supersedes")),
        submission_type=_coerce_optional(governance.get("submission_type")),
        nearest_canonical=_coerce_optional(governance.get("nearest_canonical")),
        evidence_summary=_coerce_optional(governance.get("evidence_summary")),
        family_confidence=_coerce_float(governance.get("family_confidence")),
        disposition_confidence=_coerce_float(governance.get("disposition_confidence")),
        disposition_reason_codes=_coerce_keywords(governance.get("disposition_reason_codes")),
        registry_snapshot_version=_coerce_optional(
            governance.get("registry_snapshot_version")
        ),
        license_status=_coerce_optional(provenance.get("license_status")),
        license_expression=_coerce_optional(provenance.get("license_expression")),
        packaging_allowed=_coerce_optional_bool(provenance.get("packaging_allowed")),
        source_commit=_coerce_optional(provenance.get("source_commit")),
        source_fingerprint=_coerce_optional(provenance.get("source_fingerprint")),
    )
    return record, text_files, binary_files


def inspect_candidate_bundle(
    bundle_path: str | Path,
    *,
    repo: Optional[str] = None,
) -> tuple[SkillRecord, Dict[str, object], Dict[str, object], Dict[str, str], Dict[str, bytes]]:
    """Load a candidate bundle plus raw metadata for reviewer-facing inspection."""
    root = Path(bundle_path).expanduser()
    governance = _read_json_file(root / "REGISTRY.json")
    provenance = _read_json_file(root / "PROVENANCE.json")
    record, text_files, binary_files = load_candidate_bundle(root, repo=repo)
    return record, governance, provenance, text_files, binary_files


def _keywords_from_intent(intent: str) -> List[str]:
    """Derive stable keywords from the intent."""
    seen = []
    for token in tokenize(intent):
        if token not in seen:
            seen.append(token)
    return seen[:6] if seen else ["skill"]
