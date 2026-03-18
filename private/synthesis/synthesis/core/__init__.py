"""
Synthesis Core - The heart of capability generation and trust management.

This package contains:
- models.py: Data structures for capabilities, tests, and trust
- synthesis.py: TDD-based code synthesis engine
- validator.py: Code validation and security analysis
- composition.py: Composition-first problem solving (search → compose → synthesize)
- trust.py: Trust management and network bootstrapping
"""

from synthesis.core.models import (
    Capability,
    CapabilityCategory,
    CapabilityMetadata,
    ExecutionResult,
    ExecutionStatus,
    ParameterSchema,
    ReturnSchema,
    RiskLevel,
    SynthesisAttempt,
    SynthesisStatus,
    TestCase,
    TestResult,
    TestSuite,
    TrustLevel,
    TrustMetrics,
    ValidationIssue,
    ValidationResult,
)
from synthesis.core.synthesis import TDDSynthesizer
from synthesis.core.validator import CodeValidator

# New: Composition-first problem solving
from synthesis.core.composition import (
    CompositionPlan,
    CompositionPlanner,
    CompositionExecutor,
    SubtaskMapping,
)

# New: Trust management and bootstrapping
from synthesis.core.trust import (
    TrustLevel as TrustLevelEnum,  # Renamed to avoid conflict with models.TrustLevel
    ValidatorRole,
    ValidationRecord,
    TrustScore,
    Validator,
    TrustManager,
    TrustBootstrapper,
    bootstrap_trust_network,
)

__all__ = [
    # Models
    "Capability",
    "CapabilityCategory",
    "CapabilityMetadata",
    "ExecutionResult",
    "ExecutionStatus",
    "ParameterSchema",
    "ReturnSchema",
    "RiskLevel",
    "SynthesisAttempt",
    "SynthesisStatus",
    "TestCase",
    "TestResult",
    "TestSuite",
    "TrustLevel",
    "TrustMetrics",
    "ValidationIssue",
    "ValidationResult",
    # Synthesis
    "TDDSynthesizer",
    "CodeValidator",
    # Composition (NEW)
    "CompositionPlan",
    "CompositionPlanner",
    "CompositionExecutor",
    "SubtaskMapping",
    # Trust (NEW)
    "TrustLevelEnum",
    "ValidatorRole",
    "ValidationRecord",
    "TrustScore",
    "Validator",
    "TrustManager",
    "TrustBootstrapper",
    "bootstrap_trust_network",
]
