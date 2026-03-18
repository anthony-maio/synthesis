"""
capability.py - Core Capability Abstraction with Enhanced Security
===================================================================

This module implements the fundamental capability abstraction with improvements based on feedback:
- Realistic trust scoring based on empirical data
- Proper metadata tracking for security analysis
- Clear separation between code and data
- Comprehensive validation hooks
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Set
import hashlib
import json
import uuid


class TrustLevel(Enum):
    """
    Graduated trust levels based on empirical performance metrics.
    
    Unlike the initial design's optimistic projections, these levels are based
    on realistic expectations from LLM code generation research.
    """
    UNTRUSTED = auto()    # New capabilities, <10 successful runs
    PROBATION = auto()    # 10-50 runs, 70%+ success (realistic for LLM-generated code)
    TRUSTED = auto()      # 50+ runs, 80%+ success, 14+ days old
    VERIFIED = auto()     # Human reviewed + trusted metrics
    QUARANTINE = auto()   # Failed security checks or high failure rate


class CapabilityType(Enum):
    """Types of capabilities the system can synthesize."""
    DATA_TRANSFORM = "data_transform"
    API_CLIENT = "api_client"
    FILE_PROCESSOR = "file_processor"
    COMPUTATION = "computation"
    TEXT_ANALYSIS = "text_analysis"
    INTEGRATION = "integration"
    CUSTOM = "custom"


@dataclass
class SecurityProfile:
    """
    Security requirements and restrictions for a capability.
    
    This replaces the naive approach of the initial design with explicit
    security boundaries that can be enforced at runtime.
    """
    
    # Filesystem permissions
    allow_file_read: bool = False
    allow_file_write: bool = False
    allowed_read_paths: List[str] = field(default_factory=list)
    allowed_write_paths: List[str] = field(default_factory=list)
    max_file_size_mb: int = 10
    
    # Network permissions
    allow_network: bool = False
    allowed_domains: List[str] = field(default_factory=list)
    blocked_domains: List[str] = field(default_factory=list)
    max_request_size_mb: int = 1
    
    # Resource limits
    max_memory_mb: int = 256
    max_cpu_seconds: float = 30.0
    max_threads: int = 1
    
    # Code restrictions
    blocked_modules: Set[str] = field(default_factory=lambda: {
        'os', 'subprocess', 'sys', 'eval', 'exec', '__import__',
        'compile', 'open', 'input', 'raw_input', 'reload'
    })
    allowed_modules: Set[str] = field(default_factory=lambda: {
        'json', 'math', 'datetime', 're', 'collections', 'itertools',
        'functools', 'typing', 'dataclasses', 'enum', 'uuid', 'hashlib'
    })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'allow_file_read': self.allow_file_read,
            'allow_file_write': self.allow_file_write,
            'allowed_read_paths': self.allowed_read_paths,
            'allowed_write_paths': self.allowed_write_paths,
            'max_file_size_mb': self.max_file_size_mb,
            'allow_network': self.allow_network,
            'allowed_domains': self.allowed_domains,
            'blocked_domains': self.blocked_domains,
            'max_request_size_mb': self.max_request_size_mb,
            'max_memory_mb': self.max_memory_mb,
            'max_cpu_seconds': self.max_cpu_seconds,
            'max_threads': self.max_threads,
            'blocked_modules': list(self.blocked_modules),
            'allowed_modules': list(self.allowed_modules)
        }
    
    @classmethod
    def from_trust_level(cls, trust_level: TrustLevel) -> 'SecurityProfile':
        """
        Generate appropriate security profile based on trust level.
        
        This implements the graduated permissions model, where capabilities
        earn more privileges as they prove themselves safe.
        """
        if trust_level == TrustLevel.QUARANTINE:
            # Maximum restrictions for problematic code
            return cls(
                allow_file_read=False,
                allow_file_write=False,
                allow_network=False,
                max_memory_mb=128,
                max_cpu_seconds=5.0
            )
        
        elif trust_level == TrustLevel.UNTRUSTED:
            # Very limited permissions for new capabilities
            return cls(
                allow_file_read=False,
                allow_file_write=False,
                allow_network=False,
                max_memory_mb=256,
                max_cpu_seconds=10.0
            )
        
        elif trust_level == TrustLevel.PROBATION:
            # Some file access, limited network
            return cls(
                allow_file_read=True,
                allowed_read_paths=["/tmp/synthesis"],
                allow_file_write=True,
                allowed_write_paths=["/tmp/synthesis"],
                allow_network=True,
                allowed_domains=["api.github.com", "pypi.org"],
                max_memory_mb=512,
                max_cpu_seconds=30.0
            )
        
        elif trust_level == TrustLevel.TRUSTED:
            # Broader permissions but still sandboxed
            return cls(
                allow_file_read=True,
                allow_file_write=True,
                allowed_write_paths=["/tmp", "/var/synthesis"],
                allow_network=True,
                max_memory_mb=1024,
                max_cpu_seconds=60.0,
                max_threads=2
            )
        
        else:  # VERIFIED
            # Most permissive, but still with some limits
            return cls(
                allow_file_read=True,
                allow_file_write=True,
                allow_network=True,
                max_memory_mb=2048,
                max_cpu_seconds=120.0,
                max_threads=4
            )


@dataclass
class ExecutionMetrics:
    """
    Track realistic performance metrics for trust scoring.
    
    Based on empirical research showing LLM-generated code typically has:
    - 40-60% success rate without iteration
    - 70-85% success rate with test-driven refinement
    - Higher rates only with human intervention
    """
    
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    timeout_executions: int = 0
    security_violations: int = 0
    average_execution_time_ms: float = 0.0
    last_execution: Optional[datetime] = None
    error_patterns: Dict[str, int] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate with realistic expectations."""
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions
    
    @property
    def is_improving(self) -> bool:
        """
        Check if the capability is showing improvement over time.
        
        This is more nuanced than the initial design - we look for
        trending improvement rather than absolute thresholds.
        """
        if self.total_executions < 20:
            return False  # Not enough data
        
        # Calculate success rate for last 10 executions vs previous 10
        # This would need execution history tracking in production
        # For now, use overall success rate trending
        return self.success_rate > 0.6 and self.security_violations == 0
    
    def record_execution(self, success: bool, execution_time_ms: float, 
                        error: Optional[str] = None) -> None:
        """Record an execution with detailed metrics."""
        self.total_executions += 1
        self.last_execution = datetime.now()
        
        # Update running average of execution time
        self.average_execution_time_ms = (
            (self.average_execution_time_ms * (self.total_executions - 1) + execution_time_ms) 
            / self.total_executions
        )
        
        if success:
            self.successful_executions += 1
        else:
            self.failed_executions += 1
            if error:
                # Track error patterns for evolution engine
                error_type = self._classify_error(error)
                self.error_patterns[error_type] = self.error_patterns.get(error_type, 0) + 1
    
    def _classify_error(self, error: str) -> str:
        """Classify error for pattern analysis."""
        error_lower = error.lower()
        
        if "timeout" in error_lower:
            self.timeout_executions += 1
            return "timeout"
        elif "permission" in error_lower or "denied" in error_lower:
            self.security_violations += 1
            return "permission"
        elif "syntax" in error_lower:
            return "syntax"
        elif "type" in error_lower:
            return "type_error"
        elif "import" in error_lower:
            return "import_error"
        elif "attribute" in error_lower:
            return "attribute_error"
        else:
            return "unknown"


@dataclass
class CapabilityMetadata:
    """
    Rich metadata for capability management and evolution.
    
    This is significantly enhanced from the initial design to support
    realistic tracking and improvement cycles.
    """
    
    id: str = field(default_factory=lambda: f"cap_{uuid.uuid4().hex[:12]}")
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Authorship and lineage
    author: str = "synthesis_engine"
    parent_id: Optional[str] = None  # For evolution/forking
    synthesis_iterations: int = 0  # How many refinement cycles
    
    # Classification
    capability_type: CapabilityType = CapabilityType.CUSTOM
    tags: List[str] = field(default_factory=list)
    
    # Dependencies with version pinning
    python_packages: Dict[str, str] = field(default_factory=dict)  # {"requests": ">=2.28.0"}
    system_packages: List[str] = field(default_factory=list)
    
    # Performance tracking
    metrics: ExecutionMetrics = field(default_factory=ExecutionMetrics)
    trust_level: TrustLevel = TrustLevel.UNTRUSTED
    
    # Security profile
    security: SecurityProfile = field(default_factory=SecurityProfile)
    
    # Test suite reference
    test_suite_id: Optional[str] = None
    test_pass_rate: float = 0.0
    
    def calculate_trust_level(self) -> TrustLevel:
        """
        Calculate trust level based on realistic metrics.
        
        Unlike the initial design's optimistic 85% threshold, we use:
        - 70% for probation (achievable with good TDD)
        - 80% for trusted (excellent for LLM-generated code)
        - Manual review required for verified status
        """
        metrics = self.metrics
        
        # Check for security issues first
        if metrics.security_violations > 0:
            return TrustLevel.QUARANTINE
        
        # Check failure patterns
        if metrics.success_rate < 0.5 and metrics.total_executions >= 10:
            return TrustLevel.QUARANTINE
        
        # Age of capability
        age_days = (datetime.now() - self.created_at).days
        
        # Realistic progression based on research
        if metrics.total_executions < 10:
            return TrustLevel.UNTRUSTED
        
        elif (metrics.total_executions >= 10 and 
              metrics.success_rate >= 0.70 and
              metrics.total_executions < 50):
            return TrustLevel.PROBATION
        
        elif (metrics.total_executions >= 50 and
              metrics.success_rate >= 0.80 and
              age_days >= 14):
            return TrustLevel.TRUSTED
        
        else:
            return self.trust_level  # Maintain current level
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for storage/transmission."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'author': self.author,
            'parent_id': self.parent_id,
            'synthesis_iterations': self.synthesis_iterations,
            'capability_type': self.capability_type.value,
            'tags': self.tags,
            'python_packages': self.python_packages,
            'system_packages': self.system_packages,
            'metrics': {
                'total_executions': self.metrics.total_executions,
                'success_rate': self.metrics.success_rate,
                'average_execution_time_ms': self.metrics.average_execution_time_ms
            },
            'trust_level': self.trust_level.name,
            'security': self.security.to_dict(),
            'test_suite_id': self.test_suite_id,
            'test_pass_rate': self.test_pass_rate
        }


@dataclass
class Capability:
    """
    A complete capability with code, metadata, and security profile.
    
    Major improvements from initial design:
    - Code stored as separate module, not injected into template
    - Clear separation of interface and implementation
    - Comprehensive validation hooks
    - Support for async execution
    """
    
    metadata: CapabilityMetadata
    
    # Code as a complete module, not fragments
    module_code: str = ""  # Complete Python module
    entry_point: str = "execute"  # Main function name
    
    # Interface definition
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    
    # Documentation
    docstring: str = ""
    examples: List[Dict[str, Any]] = field(default_factory=list)
    
    # Validation
    signature_hash: Optional[str] = None  # For integrity checking
    
    def __post_init__(self):
        """Calculate signature hash for integrity."""
        if self.module_code and not self.signature_hash:
            self.signature_hash = self._calculate_hash()
    
    def _calculate_hash(self) -> str:
        """Calculate SHA256 hash of module code for integrity checking."""
        return hashlib.sha256(self.module_code.encode()).hexdigest()
    
    def validate_integrity(self) -> bool:
        """Verify the capability hasn't been tampered with."""
        if not self.signature_hash:
            return False
        return self.signature_hash == self._calculate_hash()
    
    def to_dict(self) -> Dict[str, Any]:
        """Complete serialization including code and metadata."""
        return {
            'metadata': self.metadata.to_dict(),
            'module_code': self.module_code,
            'entry_point': self.entry_point,
            'input_schema': self.input_schema,
            'output_schema': self.output_schema,
            'docstring': self.docstring,
            'examples': self.examples,
            'signature_hash': self.signature_hash
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Capability':
        """Reconstruct capability from serialized form."""
        metadata_dict = data['metadata']
        
        # Reconstruct metadata
        metadata = CapabilityMetadata(
            id=metadata_dict['id'],
            name=metadata_dict['name'],
            description=metadata_dict['description'],
            version=metadata_dict['version'],
            created_at=datetime.fromisoformat(metadata_dict['created_at']),
            updated_at=datetime.fromisoformat(metadata_dict['updated_at']),
            author=metadata_dict['author'],
            parent_id=metadata_dict.get('parent_id'),
            synthesis_iterations=metadata_dict.get('synthesis_iterations', 0),
            capability_type=CapabilityType[metadata_dict.get('capability_type', 'CUSTOM')],
            tags=metadata_dict.get('tags', []),
            python_packages=metadata_dict.get('python_packages', {}),
            system_packages=metadata_dict.get('system_packages', []),
            trust_level=TrustLevel[metadata_dict.get('trust_level', 'UNTRUSTED')]
        )
        
        # Reconstruct security profile
        if 'security' in metadata_dict:
            security_dict = metadata_dict['security']
            metadata.security = SecurityProfile(
                allow_file_read=security_dict.get('allow_file_read', False),
                allow_file_write=security_dict.get('allow_file_write', False),
                allowed_read_paths=security_dict.get('allowed_read_paths', []),
                allowed_write_paths=security_dict.get('allowed_write_paths', []),
                max_file_size_mb=security_dict.get('max_file_size_mb', 10),
                allow_network=security_dict.get('allow_network', False),
                allowed_domains=security_dict.get('allowed_domains', []),
                blocked_domains=security_dict.get('blocked_domains', []),
                max_request_size_mb=security_dict.get('max_request_size_mb', 1),
                max_memory_mb=security_dict.get('max_memory_mb', 256),
                max_cpu_seconds=security_dict.get('max_cpu_seconds', 30.0),
                max_threads=security_dict.get('max_threads', 1)
            )
        
        return cls(
            metadata=metadata,
            module_code=data['module_code'],
            entry_point=data['entry_point'],
            input_schema=data.get('input_schema', {}),
            output_schema=data.get('output_schema', {}),
            docstring=data.get('docstring', ''),
            examples=data.get('examples', []),
            signature_hash=data.get('signature_hash')
        )
