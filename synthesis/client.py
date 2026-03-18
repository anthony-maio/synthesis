"""Skill-first Synthesis client."""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from synthesis.core.models import (
    CapabilityCategory,
    SkillCompositionBundle,
    SkillDraft,
    SkillInstallState,
    SkillRecord,
    SkillSourceType,
    SkillSubmission,
    TrustLevel,
)
from synthesis.llm.provider import LLMProvider, create_provider
from synthesis.observatory.logger import Observatory
from synthesis.skill_runtime import (
    DEFAULT_CANONICAL_REPO_SLUG,
    CanonicalSkillRepository,
    CodexHostAdapter,
    LocalSkillRepository,
    SkillSynthesizer,
    compose_skills,
    default_canonical_repo_path,
    score_skill,
    tokenize,
)


class ResolutionMethod(Enum):
    """How skill acquisition was resolved."""

    LOCAL_SKILL = "local_skill"
    CANONICAL_SKILL = "canonical_skill"
    COMPOSITION = "composition"
    SYNTHESIZED = "synthesized"

    # Legacy aliases
    REPOSITORY_EXACT = "local_skill"
    EXCHANGE_HIT = "canonical_skill"
    SYNTHESIS = "synthesized"


@dataclass
class SkillAcquisitionResult:
    """Result of acquiring or synthesizing a skill."""

    success: bool
    method: ResolutionMethod
    primary_skill: Optional[SkillRecord] = None
    installed_skills: List[SkillRecord] = field(default_factory=list)
    composition_bundle: Optional[SkillCompositionBundle] = None
    synthesized_skill: Optional[SkillDraft] = None
    submission: Optional[SkillSubmission] = None

    repository_searched: bool = False
    composition_attempted: bool = False
    synthesis_attempted: bool = False
    synthesis_avoided: bool = False
    resolution_time_ms: float = 0.0
    activation_message: Optional[str] = None
    resolution_steps: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for MCP responses and logging."""
        return {
            "success": self.success,
            "method": self.method.value,
            "primary_skill": self.primary_skill.model_dump() if self.primary_skill else None,
            "installed_skills": [skill.model_dump() for skill in self.installed_skills],
            "composition_bundle": (
                self.composition_bundle.model_dump() if self.composition_bundle else None
            ),
            "synthesized_skill": (
                self.synthesized_skill.model_dump() if self.synthesized_skill else None
            ),
            "submission": self.submission.model_dump() if self.submission else None,
            "repository_searched": self.repository_searched,
            "composition_attempted": self.composition_attempted,
            "synthesis_attempted": self.synthesis_attempted,
            "synthesis_avoided": self.synthesis_avoided,
            "resolution_time_ms": self.resolution_time_ms,
            "activation_message": self.activation_message,
            "resolution_steps": self.resolution_steps,
        }


ResolutionResult = SkillAcquisitionResult


class SynthesisClient:
    """Main client for search-first, skill-first self-extension."""

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        provider_type: str = "mock",
        repository=None,
        exchange_url: Optional[str] = None,
        canonical_repo_path: Optional[str] = None,
        host_root: Optional[str] = None,
        min_composition_coverage: float = 0.7,
        enable_composition: bool = True,
        **provider_kwargs: Any,
    ):
        self.llm_provider = llm_provider
        self._provider_type = provider_type
        self._provider_kwargs = provider_kwargs
        self.skill_synthesizer: Optional[SkillSynthesizer] = None

        self.observatory = Observatory()
        self.enable_composition = enable_composition
        self.min_composition_coverage = min_composition_coverage

        default_root = host_root or str(Path.home() / ".codex" / "skills")
        canonical_root = canonical_repo_path or str(default_canonical_repo_path())
        self.host_adapter = CodexHostAdapter(default_root)
        self.local_repository = LocalSkillRepository(default_root)
        self.canonical_repository = CanonicalSkillRepository(canonical_root, auto_bootstrap=False)

        # Legacy compatibility only.
        self.repository = repository
        self.exchange_url = exchange_url

    async def acquire_skill(
        self,
        intent: str,
        requirements: str = "",
        host: Optional[str] = None,
        force_synthesis: bool = False,
    ) -> SkillAcquisitionResult:
        """Acquire a skill by search, composition, or synthesis."""
        del host

        start_time = time.time()
        result = SkillAcquisitionResult(success=False, method=ResolutionMethod.SYNTHESIZED)

        if not force_synthesis:
            result.repository_searched = True

            local_match = self._find_best_local_skill(intent)
            if local_match:
                result.success = True
                result.method = ResolutionMethod.LOCAL_SKILL
                result.primary_skill = local_match
                result.installed_skills = [local_match]
                result.synthesis_avoided = True
                result.activation_message = self.host_adapter.activation_message()
                result.resolution_steps.append(
                    {
                        "step": "local_skill_hit",
                        "skill": local_match.name,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                result.resolution_time_ms = (time.time() - start_time) * 1000
                self.observatory.record_repository_hit(intent, local_match.name)
                return result

            result.resolution_steps.append(
                {"step": "local_skill_miss", "timestamp": datetime.now().isoformat()}
            )
            self.observatory.record_repository_miss(intent)

            canonical_ranked = self._search_canonical_skills(intent)
            exact_match = self._select_exact_match(canonical_ranked)
            if exact_match:
                installed = self._install_existing_skill(exact_match)
                result.success = True
                result.method = ResolutionMethod.CANONICAL_SKILL
                result.primary_skill = installed
                result.installed_skills = [installed]
                result.synthesis_avoided = True
                result.activation_message = self.host_adapter.activation_message()
                result.resolution_steps.append(
                    {
                        "step": "canonical_skill_installed",
                        "skill": installed.name,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                result.resolution_time_ms = (time.time() - start_time) * 1000
                self.observatory.record_repository_hit(intent, installed.name)
                return result

            if self.enable_composition and canonical_ranked:
                result.composition_attempted = True
                bundle = compose_skills(intent, canonical_ranked, self.min_composition_coverage)
                if bundle:
                    installed_skills = [self._install_existing_skill(skill) for skill in bundle.skills]
                    result.success = True
                    result.method = ResolutionMethod.COMPOSITION
                    result.primary_skill = installed_skills[0]
                    result.installed_skills = installed_skills
                    result.composition_bundle = SkillCompositionBundle(
                        intent=bundle.intent,
                        skills=installed_skills,
                        coverage_ratio=bundle.coverage_ratio,
                        missing_tokens=bundle.missing_tokens,
                    )
                    result.synthesis_avoided = True
                    result.activation_message = self.host_adapter.activation_message()
                    result.resolution_steps.append(
                        {
                            "step": "composition_bundle_installed",
                            "skills": [skill.name for skill in installed_skills],
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    result.resolution_time_ms = (time.time() - start_time) * 1000
                    self.observatory.record_composition_success(
                        intent,
                        ",".join(skill.name for skill in installed_skills),
                        len(installed_skills),
                    )
                    return result

        draft = await self._get_skill_synthesizer().synthesize(intent, requirements)
        installed = self.host_adapter.install_skill_files(
            name=draft.name,
            files={path: content.encode("utf-8") for path, content in draft.files.items()},
            trust_level=TrustLevel.UNTRUSTED,
            source_type=SkillSourceType.SYNTHESIZED,
            repo=self._canonical_repo_name(),
            install_state=SkillInstallState.DRAFT,
        )

        result.success = True
        result.method = ResolutionMethod.SYNTHESIZED
        result.primary_skill = installed
        result.installed_skills = [installed]
        result.synthesized_skill = draft
        result.synthesis_attempted = True
        result.activation_message = self.host_adapter.activation_message()
        result.resolution_steps.append(
            {
                "step": "skill_synthesized",
                "skill": installed.name,
                "timestamp": datetime.now().isoformat(),
            }
        )
        if self.canonical_repository:
            result.submission = self.canonical_repository.prepare_submission(draft)
            result.resolution_steps.append(
                {
                    "step": "submission_prepared",
                    "branch": result.submission.branch,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        result.resolution_time_ms = (time.time() - start_time) * 1000
        return result

    async def resolve(
        self,
        requirement: str,
        category: Optional[CapabilityCategory] = None,
        context: Optional[Dict[str, Any]] = None,
        force_synthesis: bool = False,
    ) -> SkillAcquisitionResult:
        """Legacy alias for skill acquisition."""
        del category, context
        return await self.acquire_skill(requirement, force_synthesis=force_synthesis)

    async def synthesize(self, requirement: str, category: Optional[CapabilityCategory] = None) -> SkillDraft:
        """Legacy compatibility wrapper for direct synthesis."""
        del category
        return await self._get_skill_synthesizer().synthesize(requirement)

    def list_installed_skills(self) -> List[SkillRecord]:
        """Return installed skills from the host root."""
        return self.host_adapter.list_installed_skills()

    def inspect_skill(self, name: str) -> Optional[SkillRecord]:
        """Inspect an installed or canonical skill by name."""
        local = self.local_repository.get(name)
        if local:
            return local
        for skill in self._search_canonical_skills(name):
            if skill.name == name:
                return skill
        return None

    def submit_skill(self, name: str) -> Optional[SkillSubmission]:
        """Prepare a submission for an installed skill."""
        installed = self.local_repository.get(name)
        if not installed or not self.canonical_repository:
            return None

        skill_dir = self.host_adapter.root / name
        files: Dict[str, str] = {}
        binary_files: Dict[str, str] = {}
        for path in skill_dir.rglob("*"):
            if path.is_file():
                relative_path = str(path.relative_to(skill_dir)).replace("\\", "/")
                if relative_path == ".synthesis.json":
                    continue
                payload = path.read_bytes()
                try:
                    files[relative_path] = payload.decode("utf-8")
                except UnicodeDecodeError:
                    binary_files[relative_path] = base64.b64encode(payload).decode("ascii")

        if binary_files:
            return SkillSubmission(
                repo=self._canonical_repo_name(),
                branch=f"synthesis/{name}",
                title=f"Add skill: {name}",
                status="prepared",
                target_path=f"skills/{name}",
                files={f"skills/{name}/{path}": content for path, content in files.items()},
                binary_files={
                    f"skills/{name}/{path}": content for path, content in binary_files.items()
                },
            )

        draft = SkillDraft(
            name=name,
            description=installed.description,
            keywords=installed.keywords,
            files=files,
            evaluation_scenarios=[],
        )
        return self.canonical_repository.prepare_submission(draft)

    def get_metrics(self) -> Dict[str, Any]:
        """Return summary metrics and current skill inventory."""
        summary = self.observatory.get_summary()
        summary["skills"] = {"installed": len(self.list_installed_skills())}
        return summary

    def set_repository(self, repository) -> None:
        """Legacy compatibility hook."""
        self.repository = repository

    def set_exchange_url(self, url: str) -> None:
        """Legacy compatibility hook."""
        self.exchange_url = url

    def _find_best_local_skill(self, intent: str) -> Optional[SkillRecord]:
        """Search installed skills for a high-confidence match."""
        query_tokens = set(tokenize(intent))
        best: Optional[SkillRecord] = None
        for skill in self.list_installed_skills():
            score = score_skill(skill, query_tokens)
            if score >= 0.8 and (best is None or score > best.score):
                best = skill.model_copy(update={"score": score})
        return best

    def _search_canonical_skills(self, intent: str) -> List[SkillRecord]:
        """Search the canonical catalog if configured."""
        if not self.canonical_repository:
            return []
        if not self.canonical_repository.is_available() and not self.canonical_repository.ensure_local_checkout():
            return []
        return self.canonical_repository.search(intent)

    def _select_exact_match(self, ranked: List[SkillRecord]) -> Optional[SkillRecord]:
        """Return a single-skill solution when the match is strong enough."""
        if not ranked:
            return None
        top = ranked[0]
        if top.score >= 0.8:
            return top
        return None

    def _install_existing_skill(self, skill: SkillRecord) -> SkillRecord:
        """Install a skill from the canonical repo into the host root."""
        if not self.canonical_repository:
            raise ValueError("Canonical repository is not configured")
        files = self.canonical_repository.load_files(skill)
        return self.host_adapter.install_skill_files(
            name=skill.name,
            files=files,
            trust_level=skill.trust_level,
            source_type=skill.source.type,
            repo=skill.source.repo,
            upstream=skill.source.upstream,
        )

    def _canonical_repo_name(self) -> str:
        """Return the canonical repo identifier used in submissions."""
        if self.canonical_repository:
            return self.canonical_repository.repo_slug
        return DEFAULT_CANONICAL_REPO_SLUG

    def _get_llm_provider(self) -> LLMProvider:
        """Create the provider only when synthesis needs it."""
        if self.llm_provider is None:
            self.llm_provider = create_provider(self._provider_type, **self._provider_kwargs)
        return self.llm_provider

    def _get_skill_synthesizer(self) -> SkillSynthesizer:
        """Create the synthesizer only when synthesis needs it."""
        if self.skill_synthesizer is None:
            self.skill_synthesizer = SkillSynthesizer(self._get_llm_provider())
        return self.skill_synthesizer
