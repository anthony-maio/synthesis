"""
Core data models for Synthesis framework.

Defines all the fundamental types and structures used throughout the system.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

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
    """Trust levels for capability execution"""
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
    id: str = Field(description="Unique attempt ID")
    requirement: str = Field(description="What was requested")
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
    
    @property
    def success(self) -> bool:
        """Whether synthesis was successful"""
        return self.status == SynthesisStatus.COMPLETE and self.total_tests > 0 and self.tests_passed == self.total_tests
    
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
    trust_level: TrustLevel = Field(description="Trust level at execution time")


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
