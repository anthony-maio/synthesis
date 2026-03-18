"""
Core capability abstraction for the Synthesis framework.

This module defines the fundamental building blocks for representing AI capabilities
that can be dynamically created, tested, and evolved. A capability represents a
discrete piece of functionality that an AI agent can acquire and use.

The design emphasizes safety through graduated trust levels, comprehensive metadata
for discoverability, and test-driven validation for correctness.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
from datetime import datetime
import uuid
import json


class TrustLevel(Enum):
    """
    Graduated trust levels for capabilities based on validation and usage.
    
    Capabilities start as UNTRUSTED and progress through levels as they
    demonstrate reliability and safety. This allows for controlled rollout
    of new capabilities while maintaining system security.
    """
    UNTRUSTED = "untrusted"      # Just created, unvalidated
    TESTED = "tested"            # Passed initial tests, limited sandbox
    VERIFIED = "verified"        # Multiple successful executions, expanded permissions
    TRUSTED = "trusted"          # Proven reliable, full permissions
    DEPRECATED = "deprecated"    # Being phased out


class CapabilityCategory(Enum):
    """
    High-level categories for organizing capabilities.
    
    Categories help with discovery, security policies, and resource management.
    """
    DATA_ACCESS = "data_access"      # Read/write external data
    COMPUTATION = "computation"       # Pure computation tasks
    INTEGRATION = "integration"       # Third-party API integration
    SYSTEM = "system"                 # System-level operations
    COMMUNICATION = "communication"   # Network communication
    ANALYSIS = "analysis"             # Data analysis and processing
    GENERATION = "generation"         # Content generation
    TRANSFORMATION = "transformation" # Data transformation


@dataclass
class CapabilityTest:
    """
    Represents a single test case for a capability.
    
    Tests are the foundation of trust in Synthesis. They validate both
    correctness and safety of generated capabilities.
    """
    name: str
    description: str
    input_data: Dict[str, Any]
    expected_output: Any
    test_code: str
    timeout_seconds: float = 5.0
    requires_network: bool = False
    requires_filesystem: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert test to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "input_data": self.input_data,
            "expected_output": self.expected_output,
            "test_code": self.test_code,
            "timeout_seconds": self.timeout_seconds,
            "requires_network": self.requires_network,
            "requires_filesystem": self.requires_filesystem
        }


@dataclass
class ExecutionMetrics:
    """
    Tracks execution statistics for a capability.
    
    These metrics inform trust level progression and identify capabilities
    that need improvement or deprecation.
    """
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    average_execution_time_ms: float = 0.0
    last_executed: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    failure_reasons: List[str] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        if self.total_executions == 0:
            return 0.0
        return (self.successful_executions / self.total_executions) * 100.0
    
    def record_execution(self, success: bool, execution_time_ms: float, 
                        error_message: Optional[str] = None) -> None:
        """
        Record the result of a capability execution.
        
        Args:
            success: Whether the execution succeeded
            execution_time_ms: Execution time in milliseconds
            error_message: Error message if execution failed
        """
        self.total_executions += 1
        self.last_executed = datetime.now()
        
        if success:
            self.successful_executions += 1
        else:
            self.failed_executions += 1
            self.last_failure = datetime.now()
            if error_message and len(self.failure_reasons) < 100:
                self.failure_reasons.append(error_message)
        
        # Update rolling average execution time
        if self.total_executions == 1:
            self.average_execution_time_ms = execution_time_ms
        else:
            alpha = 0.2  # Smoothing factor for exponential moving average
            self.average_execution_time_ms = (
                alpha * execution_time_ms + 
                (1 - alpha) * self.average_execution_time_ms
            )


@dataclass
class Capability:
    """
    Represents a complete capability that an AI agent can use.
    
    A capability encapsulates:
    - Functionality (implementation code)
    - Validation (tests)
    - Metadata (description, category, requirements)
    - Safety (trust level, permissions)
    - Observability (metrics, versioning)
    
    This is the core abstraction that Synthesis builds upon.
    """
    
    # Identity
    capability_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    category: CapabilityCategory = CapabilityCategory.COMPUTATION
    version: str = "0.1.0"
    
    # Implementation
    implementation_code: str = ""
    entry_point: str = "execute"  # Function name to call
    signature: Dict[str, Any] = field(default_factory=dict)
    
    # Testing and validation
    tests: List[CapabilityTest] = field(default_factory=list)
    trust_level: TrustLevel = TrustLevel.UNTRUSTED
    
    # Dependencies
    python_requirements: List[str] = field(default_factory=list)
    system_requirements: List[str] = field(default_factory=list)
    
    # Permissions and safety
    requires_network: bool = False
    requires_filesystem: bool = False
    requires_system_access: bool = False
    allowed_domains: List[str] = field(default_factory=list)
    allowed_paths: List[str] = field(default_factory=list)
    
    # Metadata
    author: str = "synthesis"
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    parent_capability_id: Optional[str] = None  # For evolved versions
    
    # Observability
    metrics: ExecutionMetrics = field(default_factory=ExecutionMetrics)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize capability to dictionary.
        
        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "version": self.version,
            "implementation_code": self.implementation_code,
            "entry_point": self.entry_point,
            "signature": self.signature,
            "tests": [test.to_dict() for test in self.tests],
            "trust_level": self.trust_level.value,
            "python_requirements": self.python_requirements,
            "system_requirements": self.system_requirements,
            "requires_network": self.requires_network,
            "requires_filesystem": self.requires_filesystem,
            "requires_system_access": self.requires_system_access,
            "allowed_domains": self.allowed_domains,
            "allowed_paths": self.allowed_paths,
            "author": self.author,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "parent_capability_id": self.parent_capability_id,
            "metrics": {
                "total_executions": self.metrics.total_executions,
                "successful_executions": self.metrics.successful_executions,
                "failed_executions": self.metrics.failed_executions,
                "success_rate": self.metrics.success_rate,
                "average_execution_time_ms": self.metrics.average_execution_time_ms,
                "last_executed": self.metrics.last_executed.isoformat() if self.metrics.last_executed else None,
                "last_failure": self.metrics.last_failure.isoformat() if self.metrics.last_failure else None
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Capability':
        """
        Deserialize capability from dictionary.
        
        Args:
            data: Dictionary representation of capability
            
        Returns:
            Reconstructed Capability instance
        """
        # Parse tests
        tests = [
            CapabilityTest(**test_data)
            for test_data in data.get("tests", [])
        ]
        
        # Parse metrics
        metrics_data = data.get("metrics", {})
        metrics = ExecutionMetrics(
            total_executions=metrics_data.get("total_executions", 0),
            successful_executions=metrics_data.get("successful_executions", 0),
            failed_executions=metrics_data.get("failed_executions", 0),
            average_execution_time_ms=metrics_data.get("average_execution_time_ms", 0.0)
        )
        
        return cls(
            capability_id=data["capability_id"],
            name=data["name"],
            description=data["description"],
            category=CapabilityCategory(data["category"]),
            version=data["version"],
            implementation_code=data["implementation_code"],
            entry_point=data.get("entry_point", "execute"),
            signature=data.get("signature", {}),
            tests=tests,
            trust_level=TrustLevel(data["trust_level"]),
            python_requirements=data.get("python_requirements", []),
            system_requirements=data.get("system_requirements", []),
            requires_network=data.get("requires_network", False),
            requires_filesystem=data.get("requires_filesystem", False),
            requires_system_access=data.get("requires_system_access", False),
            allowed_domains=data.get("allowed_domains", []),
            allowed_paths=data.get("allowed_paths", []),
            author=data.get("author", "synthesis"),
            tags=data.get("tags", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            parent_capability_id=data.get("parent_capability_id"),
            metrics=metrics
        )
    
    def can_promote_trust_level(self) -> bool:
        """
        Determine if capability has met criteria for trust level promotion.
        
        Returns:
            True if capability qualifies for next trust level
        """
        if self.trust_level == TrustLevel.UNTRUSTED:
            # Promote to TESTED if all tests pass at least once
            return (
                len(self.tests) > 0 and 
                self.metrics.total_executions >= len(self.tests) and
                self.metrics.success_rate >= 100.0
            )
        elif self.trust_level == TrustLevel.TESTED:
            # Promote to VERIFIED after 10 successful real-world executions
            return (
                self.metrics.total_executions >= 10 and
                self.metrics.success_rate >= 90.0
            )
        elif self.trust_level == TrustLevel.VERIFIED:
            # Promote to TRUSTED after 50 executions with high reliability
            return (
                self.metrics.total_executions >= 50 and
                self.metrics.success_rate >= 95.0
            )
        
        return False
    
    def promote_trust_level(self) -> bool:
        """
        Attempt to promote capability to next trust level.
        
        Returns:
            True if promotion occurred, False otherwise
        """
        if not self.can_promote_trust_level():
            return False
        
        if self.trust_level == TrustLevel.UNTRUSTED:
            self.trust_level = TrustLevel.TESTED
        elif self.trust_level == TrustLevel.TESTED:
            self.trust_level = TrustLevel.VERIFIED
        elif self.trust_level == TrustLevel.VERIFIED:
            self.trust_level = TrustLevel.TRUSTED
        else:
            return False
        
        self.updated_at = datetime.now()
        return True


class CapabilityRequest:
    """
    Represents a request for a new capability.
    
    This is what an AI agent provides when it realizes it needs a new tool.
    The request is then fulfilled by the TDD Synthesizer.
    """
    
    def __init__(self,
                 description: str,
                 category: CapabilityCategory,
                 example_inputs: List[Dict[str, Any]],
                 example_outputs: List[Any],
                 requirements: Optional[List[str]] = None,
                 constraints: Optional[Dict[str, Any]] = None):
        """
        Initialize a capability request.
        
        Args:
            description: Natural language description of needed capability
            category: Category this capability falls into
            example_inputs: Example input data structures
            example_outputs: Expected outputs for the example inputs
            requirements: Python package requirements
            constraints: Additional constraints (timeout, resources, etc.)
        """
        self.request_id = str(uuid.uuid4())
        self.description = description
        self.category = category
        self.example_inputs = example_inputs
        self.example_outputs = example_outputs
        self.requirements = requirements or []
        self.constraints = constraints or {}
        self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "description": self.description,
            "category": self.category.value,
            "example_inputs": self.example_inputs,
            "example_outputs": self.example_outputs,
            "requirements": self.requirements,
            "constraints": self.constraints,
            "created_at": self.created_at.isoformat()
        }
