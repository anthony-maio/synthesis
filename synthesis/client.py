"""Skill-first Synthesis client."""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from synthesis.core.models import (
    CandidateBundleInspection,
    CandidateBundleReview,
    CandidateBundleReviewQueue,
    CandidateBundleReviewQueueItem,
    CandidateBundleSubmissionEnvelope,
    CandidateBundleValidation,
    CapabilityCategory,
    SkillCompositionBundle,
    SkillDraft,
    SkillInstallPolicy,
    SkillInstallState,
    SkillLifecycleStage,
    SkillRecord,
    SkillSourceType,
    SkillSubmission,
    SubmissionAutomationResult,
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
    load_candidate_bundle,
    render_provenance_metadata,
    render_registry_metadata,
    score_skill,
    tokenize,
)
from synthesis.skill_runtime import (
    inspect_candidate_bundle as inspect_candidate_bundle_payload,
)

ALLOWED_VARIANT_REASONS = {
    "host_runtime",
    "tool_surface",
    "security_model",
    "distinct_workflow",
}


def _render_candidate_pull_request_body(review: CandidateBundleReview) -> str:
    """Render a deterministic PR body for one candidate bundle submission."""
    sections = [
        "## Candidate",
        "",
        f"- Skill: `{review.skill_name}`",
        f"- Headline: {review.headline}",
        f"- Submission type: `{review.submission_type or 'unknown'}`",
        f"- Capability family: `{review.capability_family or 'unknown'}`",
    ]
    if review.nearest_canonical:
        sections.append(f"- Nearest canonical: `{review.nearest_canonical}`")
    if review.variant_reason:
        sections.append(f"- Variant reason: `{review.variant_reason}`")
    sections.extend(
        [
            "",
            "## Review Readiness",
            "",
            f"- Ready for review: `{str(review.ready_for_review).lower()}`",
            f"- License status: `{review.license_status or 'unknown'}`",
            f"- Packaging allowed: `{str(review.packaging_allowed).lower() if review.packaging_allowed is not None else 'unknown'}`",
            "",
            "## Why This Exists",
            "",
            review.evidence_summary or "No evidence summary provided.",
            "",
            "## Miner Report Excerpt",
            "",
            review.miner_report_excerpt or "No miner report excerpt available.",
        ]
    )
    if review.validation_errors:
        sections.extend(["", "## Validation Errors", ""])
        sections.extend(f"- {error}" for error in review.validation_errors)
    if review.validation_warnings:
        sections.extend(["", "## Validation Warnings", ""])
        sections.extend(f"- {warning}" for warning in review.validation_warnings)
    sections.append("")
    return "\n".join(sections)


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
            lifecycle_stage=SkillLifecycleStage.DRAFT,
            capability_family=draft.capability_family or draft.name,
            is_primary=False,
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

    def inspect_candidate_bundle(self, bundle_path: str) -> Optional[SkillRecord]:
        """Inspect a miner-produced challenger bundle without installing it."""
        try:
            record, _, _ = load_candidate_bundle(bundle_path, repo=self._canonical_repo_name())
        except FileNotFoundError:
            return None
        return record

    def inspect_candidate_bundle_detail(
        self,
        bundle_path: str,
    ) -> Optional[CandidateBundleInspection]:
        """Return a reviewer-facing inspection payload for a candidate bundle."""
        validation = self.validate_candidate_bundle(bundle_path)
        if validation.skill is None:
            return None
        try:
            record, governance, provenance, text_files, binary_files = inspect_candidate_bundle_payload(
                bundle_path,
                repo=self._canonical_repo_name(),
            )
        except FileNotFoundError:
            return None
        return CandidateBundleInspection(
            skill=record,
            validation=validation,
            governance=governance,
            provenance=provenance,
            miner_report=text_files.get("MINER_REPORT.md"),
            text_files=sorted(text_files.keys()),
            binary_files=sorted(binary_files.keys()),
        )

    def inspect_candidate_bundle_review(
        self,
        bundle_path: str,
    ) -> Optional[CandidateBundleReview]:
        """Return a compact curator-facing summary for a candidate bundle."""
        detail = self.inspect_candidate_bundle_detail(bundle_path)
        if not detail:
            return None

        skill = detail.skill
        report_excerpt = None
        if detail.miner_report:
            lines = [line.strip() for line in detail.miner_report.splitlines() if line.strip()]
            report_excerpt = " ".join(lines[1:3]) if len(lines) > 1 else lines[0]

        ready_for_review = detail.validation.valid and skill.packaging_allowed is True
        if ready_for_review:
            if skill.submission_type == "variant_candidate" and skill.capability_family:
                headline = f"Variant candidate for {skill.capability_family}"
            elif skill.submission_type == "canonical_improvement_candidate" and skill.nearest_canonical:
                headline = f"Improvement candidate for {skill.nearest_canonical}"
            elif skill.submission_type == "new_family_candidate" and skill.capability_family:
                headline = f"New family candidate for {skill.capability_family}"
            else:
                headline = f"Candidate ready for review: {skill.name}"
        else:
            headline = f"Blocked: {skill.name} is not ready for review"

        return CandidateBundleReview(
            skill_name=skill.name,
            headline=headline,
            ready_for_review=ready_for_review,
            submission_type=skill.submission_type,
            capability_family=skill.capability_family,
            nearest_canonical=skill.nearest_canonical,
            variant_reason=skill.variant_reason,
            license_status=skill.license_status,
            packaging_allowed=skill.packaging_allowed,
            validation_errors=detail.validation.errors,
            validation_warnings=detail.validation.warnings,
            evidence_summary=skill.evidence_summary,
            miner_report_excerpt=report_excerpt,
        )

    def inspect_candidate_bundle_directory(
        self,
        bundles_root: str,
    ) -> Optional[CandidateBundleReviewQueue]:
        """Build a curator-facing review queue from a directory of candidate bundles."""
        root = Path(bundles_root).expanduser()
        if not root.is_dir():
            return None

        items: List[CandidateBundleReviewQueueItem] = []
        for bundle_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            review = self.inspect_candidate_bundle_review(str(bundle_dir))
            if not review:
                continue
            items.append(
                CandidateBundleReviewQueueItem(
                    bundle_path=str(bundle_dir),
                    review=review,
                )
            )

        items.sort(key=lambda item: (not item.review.ready_for_review, item.review.skill_name))
        ready_candidates = sum(1 for item in items if item.review.ready_for_review)
        total_candidates = len(items)
        return CandidateBundleReviewQueue(
            root_path=str(root),
            total_candidates=total_candidates,
            ready_candidates=ready_candidates,
            blocked_candidates=total_candidates - ready_candidates,
            candidates=items,
        )

    def prepare_candidate_bundle_submission(
        self,
        bundle_path: str,
    ) -> Optional[CandidateBundleSubmissionEnvelope]:
        """Return a PR-ready submission envelope for a valid candidate bundle."""
        validation = self.validate_candidate_bundle(bundle_path)
        if not validation.valid:
            return None
        review = self.inspect_candidate_bundle_review(bundle_path)
        submission = self.submit_candidate_bundle(bundle_path)
        if not review or not submission:
            return None
        return CandidateBundleSubmissionEnvelope(
            bundle_path=str(bundle_path),
            submission=submission,
            validation=validation,
            review=review,
            pull_request_body=_render_candidate_pull_request_body(review),
        )

    def publish_candidate_bundle_submission(
        self,
        bundle_path: str,
        *,
        open_pull_request: bool = False,
        base_branch: str = "main",
        draft_pull_request: bool = False,
        labels: Optional[List[str]] = None,
        reviewers: Optional[List[str]] = None,
        use_temp_worktree: bool = False,
        worktree_root: Optional[str] = None,
        allow_existing_target: bool = False,
    ) -> Optional[SubmissionAutomationResult]:
        """Publish a prepared candidate envelope into the canonical registry checkout."""
        if not self.canonical_repository:
            return None

        envelope = self.prepare_candidate_bundle_submission(bundle_path)
        if not envelope:
            return None

        repo_root = self.canonical_repository.root
        if not (repo_root / ".git").exists():
            return None

        git_executable = shutil.which("git")
        if not git_executable:
            return None

        warnings: List[str] = []
        target_repo_root = repo_root
        temp_worktree_root: Optional[Path] = None

        if use_temp_worktree:
            worktree_parent = Path(worktree_root) if worktree_root else None
            if worktree_parent:
                worktree_parent.mkdir(parents=True, exist_ok=True)
            temp_worktree_root = Path(
                tempfile.mkdtemp(
                    prefix="synthesis-publish-",
                    dir=str(worktree_parent) if worktree_parent else None,
                )
            )
            self._run_command(
                [git_executable, "worktree", "add", str(temp_worktree_root), base_branch],
                cwd=repo_root,
            )
            target_repo_root = temp_worktree_root
        else:
            status = self._run_command(
                [git_executable, "status", "--porcelain"],
                cwd=repo_root,
            )
            if status.strip():
                return None

        try:
            self._run_command(
                [git_executable, "checkout", "-B", envelope.submission.branch],
                cwd=target_repo_root,
            )

            if not self._passes_publish_preflight(
                envelope,
                target_repo_root=target_repo_root,
                allow_existing_target=allow_existing_target,
            ):
                return None

            target_dir = target_repo_root / envelope.submission.target_path
            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)

            for relative_path, content in envelope.submission.files.items():
                destination = target_repo_root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(content, encoding="utf-8")
            for relative_path, payload in envelope.submission.binary_files.items():
                destination = target_repo_root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(base64.b64decode(payload.encode("ascii")))

            self._run_command(
                [git_executable, "add", envelope.submission.target_path],
                cwd=target_repo_root,
            )
            self._run_command(
                [
                    git_executable,
                    "commit",
                    "-m",
                    envelope.submission.title,
                    "-m",
                    envelope.pull_request_body,
                ],
                cwd=target_repo_root,
            )
            commit_sha = self._run_command(
                [git_executable, "rev-parse", "HEAD"],
                cwd=target_repo_root,
            ).strip()
            self._run_command(
                [git_executable, "push", "-u", "origin", envelope.submission.branch],
                cwd=target_repo_root,
            )

            pull_request_url: Optional[str] = None
            if open_pull_request:
                gh_executable = shutil.which("gh")
                if not gh_executable:
                    warnings.append("GitHub CLI not available; skipped pull request creation.")
                else:
                    pr_command = [
                        gh_executable,
                        "pr",
                        "create",
                        "--base",
                        base_branch,
                        "--head",
                        envelope.submission.branch,
                        "--title",
                        envelope.submission.title,
                        "--body",
                        envelope.pull_request_body,
                    ]
                    if draft_pull_request:
                        pr_command.append("--draft")
                    for label in labels or []:
                        pr_command.extend(["--label", label])
                    for reviewer in reviewers or []:
                        pr_command.extend(["--reviewer", reviewer])
                    pull_request_url = self._run_command(
                        pr_command,
                        cwd=target_repo_root,
                    ).strip() or None

            return SubmissionAutomationResult(
                success=True,
                branch=envelope.submission.branch,
                target_repo_root=str(target_repo_root),
                used_temp_worktree=use_temp_worktree,
                commit_sha=commit_sha or None,
                pull_request_url=pull_request_url,
                envelope=envelope,
                warnings=warnings,
            )
        finally:
            if temp_worktree_root is not None:
                try:
                    self._run_command(
                        [git_executable, "worktree", "remove", "--force", str(temp_worktree_root)],
                        cwd=repo_root,
                    )
                except subprocess.CalledProcessError:
                    warnings.append(
                        f"Failed to remove temporary worktree at {temp_worktree_root}."
                    )

    def validate_candidate_bundle(self, bundle_path: str) -> CandidateBundleValidation:
        """Validate a miner-produced challenger bundle before install or submission."""
        try:
            record, _, _ = load_candidate_bundle(bundle_path, repo=self._canonical_repo_name())
        except FileNotFoundError:
            return CandidateBundleValidation(
                valid=False,
                errors=["Candidate bundle must include SKILL.md, REGISTRY.json, and PROVENANCE.json."],
            )

        errors: List[str] = []
        warnings: List[str] = []

        if record.lifecycle_stage != SkillLifecycleStage.CHALLENGER:
            errors.append("Candidate bundles must use lifecycle_stage=challenger.")
        if record.trust_level != TrustLevel.PROBATION:
            errors.append("Candidate bundles must use trust_level=probation.")
        if not record.capability_family:
            errors.append("Candidate bundles must declare capability_family.")
        if not record.submission_type:
            errors.append("Candidate bundles must declare submission_type.")
        if record.submission_type != "new_family_candidate" and not record.nearest_canonical:
            errors.append(
                "Candidate bundles must declare nearest_canonical for non-new-family submissions."
            )
        if record.submission_type == "variant_candidate":
            if not record.variant_reason:
                errors.append("Variant candidates must declare variant_reason.")
            elif record.variant_reason not in ALLOWED_VARIANT_REASONS:
                errors.append(
                    "Variant candidates must use a supported variant_reason."
                )
        if record.packaging_allowed is not True:
            errors.append("Candidate bundles must be license-cleared with packaging_allowed=true.")
        if not record.license_status:
            warnings.append("Candidate bundle is missing explicit license_status metadata.")

        return CandidateBundleValidation(
            valid=not errors,
            errors=errors,
            warnings=warnings,
            skill=record,
        )

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

        capability_family = installed.capability_family or installed.name
        if installed.lifecycle_stage == SkillLifecycleStage.CANONICAL:
            submission_type = "canonical_improvement_candidate"
            nearest_canonical = installed.name
            evidence_summary = (
                installed.evidence_summary
                or f"Prepared a challenger update for the canonical skill {installed.name}."
            )
        else:
            submission_type = installed.submission_type or "new_family_candidate"
            nearest_canonical = installed.nearest_canonical
            evidence_summary = (
                installed.evidence_summary
                or f"Prepared from the local draft skill {installed.name} for curator review."
            )

        files.setdefault(
            "REGISTRY.json",
            render_registry_metadata(
                capability_family=capability_family,
                lifecycle_stage=SkillLifecycleStage.CHALLENGER,
                trust_level=TrustLevel.PROBATION,
                is_primary=False,
                variant_of=installed.variant_of,
                supersedes=installed.supersedes,
                submission_type=submission_type,
                nearest_canonical=nearest_canonical,
                evidence_summary=evidence_summary,
            ),
        )
        files.setdefault(
            "PROVENANCE.json",
            render_provenance_metadata(
                name=installed.name,
                source_type=installed.source.type,
                upstream=installed.source.upstream,
            ),
        )

        if binary_files:
            submission = SkillSubmission(
                repo=self._canonical_repo_name(),
                branch=f"synthesis/{name}",
                title=f"Add skill: {name}",
                status="prepared",
                target_path=f"skills/{name}",
                trust_level=TrustLevel.PROBATION,
                lifecycle_stage=SkillLifecycleStage.CHALLENGER,
                capability_family=capability_family,
                submission_type=submission_type,
                nearest_canonical=nearest_canonical,
                evidence_summary=evidence_summary,
                files={f"skills/{name}/{path}": content for path, content in files.items()},
                binary_files={
                    f"skills/{name}/{path}": content for path, content in binary_files.items()
                },
            )
            self.local_repository.update_metadata(
                name,
                trust_level=TrustLevel.PROBATION,
                install_state=SkillInstallState.SUBMITTED,
                lifecycle_stage=SkillLifecycleStage.CHALLENGER,
                capability_family=capability_family,
                is_primary=False,
                variant_of=installed.variant_of,
                supersedes=installed.supersedes,
                submission_type=submission_type,
                nearest_canonical=nearest_canonical,
                evidence_summary=evidence_summary,
            )
            return submission

        draft = SkillDraft(
            name=name,
            description=installed.description,
            keywords=installed.keywords,
            capability_family=capability_family,
            files=files,
            evaluation_scenarios=[],
        )
        submission = self.canonical_repository.prepare_submission(draft).model_copy(
            update={
                "submission_type": submission_type,
                "nearest_canonical": nearest_canonical,
                "evidence_summary": evidence_summary,
            }
        )
        self.local_repository.update_metadata(
            name,
            trust_level=TrustLevel.PROBATION,
            install_state=SkillInstallState.SUBMITTED,
            lifecycle_stage=SkillLifecycleStage.CHALLENGER,
            capability_family=capability_family,
            is_primary=False,
            variant_of=installed.variant_of,
            supersedes=installed.supersedes,
            submission_type=submission_type,
            nearest_canonical=nearest_canonical,
            evidence_summary=evidence_summary,
        )
        return submission

    def submit_candidate_bundle(self, bundle_path: str) -> Optional[SkillSubmission]:
        """Prepare a submission directly from a miner-produced challenger bundle."""
        if not self.canonical_repository:
            return None

        validation = self.validate_candidate_bundle(bundle_path)
        if not validation.valid or validation.skill is None:
            return None
        record, files, binary_files = load_candidate_bundle(
            bundle_path,
            repo=self._canonical_repo_name(),
        )

        return SkillSubmission(
            repo=self._canonical_repo_name(),
            branch=f"synthesis/{record.name}",
            title=f"Submit skill candidate: {record.name}",
            status="prepared",
            target_path=f"skills/{record.name}",
            trust_level=record.trust_level,
            lifecycle_stage=record.lifecycle_stage,
            capability_family=record.capability_family,
            submission_type=record.submission_type or "new_family_candidate",
            variant_reason=record.variant_reason,
            nearest_canonical=record.nearest_canonical,
            evidence_summary=record.evidence_summary,
            family_confidence=record.family_confidence,
            disposition_confidence=record.disposition_confidence,
            disposition_reason_codes=record.disposition_reason_codes,
            registry_snapshot_version=record.registry_snapshot_version,
            license_status=record.license_status,
            license_expression=record.license_expression,
            packaging_allowed=record.packaging_allowed,
            files={f"skills/{record.name}/{path}": content for path, content in files.items()},
            binary_files={
                f"skills/{record.name}/{path}": base64.b64encode(content).decode("ascii")
                for path, content in binary_files.items()
            },
        )

    def install_candidate_bundle(
        self,
        bundle_path: str,
        *,
        policy: Optional[SkillInstallPolicy] = None,
    ) -> Optional[SkillRecord]:
        """Install a validated candidate bundle into the local host root."""
        validation = self.validate_candidate_bundle(bundle_path)
        if not validation.valid or validation.skill is None:
            return None

        install_policy = policy or SkillInstallPolicy()
        record = validation.skill
        if record.lifecycle_stage == SkillLifecycleStage.CHALLENGER and not install_policy.allow_challengers:
            return None
        if record.lifecycle_stage == SkillLifecycleStage.DRAFT and not install_policy.allow_drafts:
            return None
        if record.lifecycle_stage == SkillLifecycleStage.CANONICAL and not install_policy.allow_canonical:
            return None
        if install_policy.require_packaging_allowed and record.packaging_allowed is not True:
            return None

        _, text_files, binary_files = load_candidate_bundle(
            bundle_path,
            repo=self._canonical_repo_name(),
        )
        files: Dict[str, str | bytes] = dict(text_files)
        files.update(binary_files)
        return self.host_adapter.install_skill_files(
            name=record.name,
            files=files,
            trust_level=record.trust_level,
            source_type=record.source.type,
            repo=record.source.repo,
            upstream=record.source.upstream,
            install_state=SkillInstallState.INSTALLED,
            lifecycle_stage=record.lifecycle_stage,
            capability_family=record.capability_family,
            is_primary=record.is_primary,
            variant_of=record.variant_of,
            variant_reason=record.variant_reason,
            supersedes=record.supersedes,
            submission_type=record.submission_type,
            nearest_canonical=record.nearest_canonical,
            evidence_summary=record.evidence_summary,
            family_confidence=record.family_confidence,
            disposition_confidence=record.disposition_confidence,
            disposition_reason_codes=record.disposition_reason_codes,
            registry_snapshot_version=record.registry_snapshot_version,
            license_status=record.license_status,
            license_expression=record.license_expression,
            packaging_allowed=record.packaging_allowed,
            source_commit=record.source.commit,
            source_fingerprint=record.source.fingerprint,
        )

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
            install_state=SkillInstallState.INSTALLED,
            lifecycle_stage=skill.lifecycle_stage,
            capability_family=skill.capability_family,
            is_primary=skill.is_primary,
            variant_of=skill.variant_of,
            supersedes=skill.supersedes,
            submission_type=skill.submission_type,
            nearest_canonical=skill.nearest_canonical,
            evidence_summary=skill.evidence_summary,
        )

    def _canonical_repo_name(self) -> str:
        """Return the canonical repo identifier used in submissions."""
        if self.canonical_repository:
            return self.canonical_repository.repo_slug
        return DEFAULT_CANONICAL_REPO_SLUG

    def _run_command(self, args: List[str], *, cwd: Path) -> str:
        """Run one subprocess command and return stdout."""
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    def _passes_publish_preflight(
        self,
        envelope: CandidateBundleSubmissionEnvelope,
        *,
        target_repo_root: Path,
        allow_existing_target: bool,
    ) -> bool:
        """Check live registry collisions and staleness before publishing."""
        submission = envelope.submission
        target_dir = target_repo_root / submission.target_path
        if target_dir.exists() and any(target_dir.iterdir()) and not allow_existing_target:
            return False

        live_snapshot = self._live_registry_snapshot_version()
        if (
            submission.registry_snapshot_version
            and live_snapshot
            and submission.registry_snapshot_version != live_snapshot
        ):
            return False

        live_skills = self._live_registry_skills()
        live_names = {skill.name for skill in live_skills}
        live_families = {skill.capability_family for skill in live_skills if skill.capability_family}

        if submission.submission_type == "new_family_candidate":
            if submission.capability_family in live_families:
                return False
        else:
            if not submission.nearest_canonical or submission.nearest_canonical not in live_names:
                return False

        return True

    def _live_registry_skills(self) -> List[SkillRecord]:
        """Return the current canonical registry catalog, if available."""
        if not self.canonical_repository:
            return []
        if not self.canonical_repository.is_available() and not self.canonical_repository.ensure_local_checkout():
            return []
        return self.canonical_repository.list_skills()

    def _live_registry_snapshot_version(self) -> Optional[str]:
        """Return the current catalog snapshot version when available."""
        if not self.canonical_repository or not self.canonical_repository.catalog_path.exists():
            return None
        try:
            payload = json.loads(
                self.canonical_repository.catalog_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        snapshot_version = payload.get("snapshot_version")
        if snapshot_version is None:
            return None
        text = str(snapshot_version).strip()
        return text or None

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
