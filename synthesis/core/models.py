"""
Core data models for Synthesis framework.

Defines all the fundamental types and structures used throughout the system.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CapabilityCategory(str, Enum):
    """Categories of capabilities"""
    DATA_PROCESSING = "data_processing"
    COMPUTATION = "computation"
    INTEGRATION = "integration"
    ANALYSIS = "analysis"
    TRANSFORMATION = "transformation"
    VALIDATION = "validation"
    IO = "io"
    OTHER = "other"


class TrustLevel(str, Enum):
    """Trust levels for synthesized artifacts and curated skills."""
    UNTRUSTED = "untrusted"
    PROBATION = "probation"
    TRUSTED = "trusted"
    VERIFIED = "verified"


class RiskLevel(str, Enum):
    """Risk assessment for capabilities"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SynthesisStatus(str, Enum):
    """Status of a synthesis attempt"""
    PENDING = "pending"
    GENERATING_TESTS = "generating_tests"
    GENERATING_CODE = "generating_code"
    RUNNING_TESTS = "running_tests"
    REFINING = "refining"
    COMPLETE = "complete"
    FAILED = "failed"


class ExecutionStatus(str, Enum):
    """Status of capability execution"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"


class SkillSourceType(str, Enum):
    """Origin of a skill package."""

    LOCAL = "local"
    CANONICAL = "canonical"
    CURATED = "curated"
    SYNTHESIZED = "synthesized"


class SkillInstallState(str, Enum):
    """Installation state of a skill package."""

    DISCOVERED = "discovered"
    INSTALLED = "installed"
    DRAFT = "draft"
    SUBMITTED = "submitted"


class SkillLifecycleStage(str, Enum):
    """Lifecycle stage of a skill package in the curation flow."""

    DRAFT = "draft"
    CHALLENGER = "challenger"
    CANONICAL = "canonical"
    DEPRECATED = "deprecated"


class SkillSource(BaseModel):
    """Where a skill package came from."""

    type: SkillSourceType
    repo: Optional[str] = None
    relative_path: Optional[str] = None
    install_root: Optional[str] = None
    upstream: Optional[str] = None
    version: Optional[str] = None
    commit: Optional[str] = None
    fingerprint: Optional[str] = None


class SkillRecord(BaseModel):
    """Machine-readable representation of a skill package."""

    name: str
    description: str
    keywords: List[str] = Field(default_factory=list)
    trust_level: TrustLevel = Field(default=TrustLevel.UNTRUSTED)
    source: SkillSource
    install_state: SkillInstallState = Field(default=SkillInstallState.DISCOVERED)
    lifecycle_stage: SkillLifecycleStage = Field(default=SkillLifecycleStage.DRAFT)
    capability_family: Optional[str] = None
    is_primary: bool = False
    variant_of: Optional[str] = None
    variant_reason: Optional[str] = None
    supersedes: List[str] = Field(default_factory=list)
    submission_type: Optional[str] = None
    nearest_canonical: Optional[str] = None
    evidence_summary: Optional[str] = None
    family_confidence: Optional[float] = None
    disposition_confidence: Optional[float] = None
    disposition_reason_codes: List[str] = Field(default_factory=list)
    registry_snapshot_version: Optional[str] = None
    license_status: Optional[str] = None
    license_expression: Optional[str] = None
    packaging_allowed: Optional[bool] = None
    relative_path: Optional[str] = None
    install_path: Optional[str] = None
    score: float = 0.0


class SkillCompositionBundle(BaseModel):
    """A composed bundle of skills that satisfy one intent together."""

    intent: str
    skills: List[SkillRecord] = Field(default_factory=list)
    coverage_ratio: float = 0.0
    missing_tokens: List[str] = Field(default_factory=list)


class SkillInstallPolicy(BaseModel):
    """Local acceptance rules for installing a skill package."""

    allow_drafts: bool = False
    allow_challengers: bool = False
    allow_canonical: bool = True
    require_packaging_allowed: bool = True


class CandidateBundleValidation(BaseModel):
    """Validation result for a miner-produced challenger bundle."""

    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    skill: Optional["SkillRecord"] = None


class CandidateBundleInspection(BaseModel):
    """Reviewer-facing inspection payload for a candidate bundle."""

    skill: SkillRecord
    validation: CandidateBundleValidation
    governance: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    miner_report: Optional[str] = None
    text_files: List[str] = Field(default_factory=list)
    binary_files: List[str] = Field(default_factory=list)


class CandidateBundleReview(BaseModel):
    """High-signal curator summary for a candidate bundle."""

    skill_name: str
    headline: str
    ready_for_review: bool
    submission_type: Optional[str] = None
    capability_family: Optional[str] = None
    nearest_canonical: Optional[str] = None
    variant_reason: Optional[str] = None
    license_status: Optional[str] = None
    packaging_allowed: Optional[bool] = None
    validation_errors: List[str] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)
    evidence_summary: Optional[str] = None
    miner_report_excerpt: Optional[str] = None


class CandidateBundleReviewQueueItem(BaseModel):
    """One harvested candidate bundle in a reviewer queue."""

    bundle_path: str
    review: CandidateBundleReview

    @property
    def ready_for_review(self) -> bool:
        """Expose review readiness directly for queue sorting and display."""
        return self.review.ready_for_review

    @property
    def validation_errors(self) -> List[str]:
        """Expose validation errors directly for queue display."""
        return self.review.validation_errors


class CandidateBundleReviewQueue(BaseModel):
    """Reviewer queue for a directory of harvested candidate bundles."""

    root_path: str
    total_candidates: int
    ready_candidates: int
    blocked_candidates: int
    candidates: List[CandidateBundleReviewQueueItem] = Field(default_factory=list)


class SkillSubmission(BaseModel):
    """PR-ready submission metadata for a synthesized or curated skill."""

    repo: str
    branch: str
    title: str
    status: str
    target_path: str
    trust_level: TrustLevel = Field(default=TrustLevel.PROBATION)
    lifecycle_stage: SkillLifecycleStage = Field(default=SkillLifecycleStage.CHALLENGER)
    capability_family: Optional[str] = None
    submission_type: str = "new_family_candidate"
    variant_reason: Optional[str] = None
    nearest_canonical: Optional[str] = None
    evidence_summary: Optional[str] = None
    family_confidence: Optional[float] = None
    disposition_confidence: Optional[float] = None
    disposition_reason_codes: List[str] = Field(default_factory=list)
    registry_snapshot_version: Optional[str] = None
    license_status: Optional[str] = None
    license_expression: Optional[str] = None
    packaging_allowed: Optional[bool] = None
    files: Dict[str, str] = Field(default_factory=dict)
    binary_files: Dict[str, str] = Field(default_factory=dict)


class CandidateBundleSubmissionEnvelope(BaseModel):
    """PR-ready candidate handoff bundle for registry submission."""

    bundle_path: str
    submission: SkillSubmission
    validation: CandidateBundleValidation
    review: CandidateBundleReview
    pull_request_body: str


class SubmissionAutomationResult(BaseModel):
    """Result of publishing a candidate submission envelope into the registry workflow."""

    success: bool
    branch: Optional[str] = None
    target_repo_root: Optional[str] = None
    used_temp_worktree: bool = False
    commit_sha: Optional[str] = None
    pull_request_url: Optional[str] = None
    envelope: Optional[CandidateBundleSubmissionEnvelope] = None
    failure_reason: Optional[str] = None
    failure_details: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class SkillDraft(BaseModel):
    """Draft skill package produced by synthesis."""

    name: str
    description: str
    keywords: List[str] = Field(default_factory=list)
    capability_family: Optional[str] = None
    files: Dict[str, str] = Field(default_factory=dict)
    evaluation_scenarios: List[str] = Field(default_factory=list)


class ParameterSchema(BaseModel):
    """Schema for capability parameters"""
    type: str = Field(default="object", description="JSON schema type")
    properties: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)


class ReturnSchema(BaseModel):
    """Schema for capability return value"""
    type: str = Field(description="Expected return type")
    description: Optional[str] = Field(default=None)


class TestCase(BaseModel):
    """A single test case"""
    name: str = Field(description="Test name")
    description: Optional[str] = Field(default=None)
    inputs: Dict[str, Any] = Field(description="Input arguments")
    expected_output: Any = Field(description="Expected output")
    should_raise: Optional[str] = Field(default=None, description="Expected exception type")


class TestResult(BaseModel):
    """Result of running a test"""
    test_case: TestCase
    passed: bool
    actual_output: Optional[Any] = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0


class TestSuite(BaseModel):
    """Collection of test cases"""
    name: str
    tests: List[TestCase]
    description: Optional[str] = None


class CapabilityMetadata(BaseModel):
    """Metadata about a capability"""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = Field(description="Author or system that created this")
    version: str = Field(default="0.1.0")
    synthesis_reasoning: Optional[str] = None


class Capability(BaseModel):
    """A synthesized or manually created capability"""
    id: str = Field(description="Unique identifier")
    name: str = Field(description="Capability name")
    description: str = Field(description="What this capability does")
    category: CapabilityCategory

    # Specification
    parameters: ParameterSchema
    returns: ReturnSchema

    # Implementation
    implementation_code: str = Field(description="The actual Python code")
    dependencies: List[str] = Field(default_factory=list)

    # Metadata
    metadata: CapabilityMetadata
    risk_level: RiskLevel = Field(default=RiskLevel.MEDIUM)

    # Associated tests
    test_suite: Optional[TestSuite] = None

    def model_post_init(self, __context: Any) -> None:
        """Validation after model creation"""
        if not self.id:
            import uuid
            self.id = f"cap-{uuid.uuid4().hex[:8]}"


class SynthesisAttempt(BaseModel):
    """Record of a single synthesis attempt"""
    id: str = Field(default="", description="Unique attempt ID")
    requirement: str = Field(default="", description="What was requested")
    category: Optional[CapabilityCategory] = None
    status: SynthesisStatus = Field(default=SynthesisStatus.PENDING)

    # Generated artifacts
    test_suite: Optional[TestSuite] = None
    generated_code: Optional[str] = None
    capability: Optional[Capability] = None

    # Metrics
    tests_generated: int = 0
    tests_passed: int = 0
    total_tests: int = 0
    iterations: int = 0
    total_time_ms: float = 0.0

    # Results
    test_results: List[TestResult] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Allow extra fields for backward compatibility
    success: Optional[bool] = None

    @property
    def is_success(self) -> bool:
        """Whether synthesis was successful"""
        if self.success is not None:
            return self.success
        return (
            self.status == SynthesisStatus.COMPLETE
            and self.total_tests > 0
            and self.tests_passed == self.total_tests
        )

    @property
    def test_pass_rate(self) -> float:
        """Percentage of tests passed"""
        if self.total_tests == 0:
            return 0.0
        return self.tests_passed / self.total_tests


class ExecutionResult(BaseModel):
    """Result of executing a capability"""
    capability_id: str
    status: ExecutionStatus
    output: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    memory_used_mb: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    trust_level: TrustLevel = Field(default=TrustLevel.UNTRUSTED)


class ValidationIssue(BaseModel):
    """A validation issue found in code"""
    severity: str = Field(description="critical, high, medium, low")
    category: str = Field(description="Type of issue (e.g., safety, style, performance)")
    message: str = Field(description="Human-readable description")
    location: Optional[str] = Field(default=None, description="Code location if applicable")
    suggestion: Optional[str] = Field(default=None, description="How to fix it")


class ValidationResult(BaseModel):
    """Result of code validation"""
    is_valid: bool
    issues: List[ValidationIssue] = Field(default_factory=list)
    risk_level: RiskLevel = Field(default=RiskLevel.LOW)
    warnings: List[str] = Field(default_factory=list)


class TrustMetrics(BaseModel):
    """Metrics for trust scoring"""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    timeout_executions: int = 0
    average_execution_time_ms: float = 0.0
    days_active: int = 0

    @property
    def success_rate(self) -> float:
        """Percentage of successful executions"""
        if self.total_executions == 0:
            return 1.0
        return self.successful_executions / self.total_executions

    @property
    def timeout_rate(self) -> float:
        """Percentage of timeouts"""
        if self.total_executions == 0:
            return 0.0
        return self.timeout_executions / self.total_executions


class SynthesisMetrics(BaseModel):
    """Overall synthesis metrics"""
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    average_iterations: float = 0.0
    average_time_ms: float = 0.0
    by_category: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Overall synthesis success rate"""
        if self.total_attempts == 0:
            return 0.0
        return self.successful_attempts / self.total_attempts
