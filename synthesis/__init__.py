"""
Synthesis: A skill-first self-extension ecosystem.

This package provides:
- Search-first skill acquisition
- Skill composition before synthesis
- Draft skill synthesis as a fallback
- Canonical-repo submission preparation
- MCP management tooling for installed skills

Usage:
    from synthesis import SynthesisClient

    client = SynthesisClient()
    result = await client.acquire_skill("Parse CSV files and return as dictionaries")

    if result.success:
        # Inspect result.primary_skill
        pass
"""

__version__ = "0.3.0"
__author__ = "Anthony Maio & Codex"

from synthesis.client import (
    ResolutionMethod,
    ResolutionResult,
    SkillAcquisitionResult,
    SynthesisClient,
)
from synthesis.core.models import (
    CandidateBundleBlockerQueue,
    CandidateBundleInspection,
    CandidateBundlePublishability,
    CandidateBundleReview,
    CandidateBundleReviewQueue,
    CandidateBundleReviewQueueItem,
    CandidateBundleSubmissionEnvelope,
    CandidateBundleValidation,
    Capability,
    CapabilityCategory,
    ExecutionResult,
    RiskLevel,
    SkillCompositionBundle,
    SkillDraft,
    SkillInstallPolicy,
    SkillInstallState,
    SkillLifecycleStage,
    SkillRecord,
    SkillSource,
    SkillSourceType,
    SkillSubmission,
    SubmissionAutomationResult,
    SynthesisAttempt,
    TestCase,
    TestSuite,
    TrustLevel,
)
from synthesis.mcp.server import SynthesisMCPServer

__all__ = [
    "SynthesisClient",
    "SkillAcquisitionResult",
    "ResolutionResult",
    "ResolutionMethod",
    "SynthesisMCPServer",
    "Capability",
    "CapabilityCategory",
    "CandidateBundleBlockerQueue",
    "CandidateBundleInspection",
    "CandidateBundlePublishability",
    "CandidateBundleReview",
    "CandidateBundleReviewQueue",
    "CandidateBundleReviewQueueItem",
    "CandidateBundleSubmissionEnvelope",
    "CandidateBundleValidation",
    "TrustLevel",
    "RiskLevel",
    "TestCase",
    "TestSuite",
    "SynthesisAttempt",
    "ExecutionResult",
    "SkillSourceType",
    "SkillInstallState",
    "SkillInstallPolicy",
    "SkillLifecycleStage",
    "SkillSource",
    "SkillRecord",
    "SkillCompositionBundle",
    "SkillSubmission",
    "SkillDraft",
    "SubmissionAutomationResult",
]
