"""
trust.py - Trust Management and Network Bootstrapping
======================================================

This module implements the trust system that allows capabilities to earn
autonomy through demonstrated behavior rather than forced compliance.

Key components:
- TrustLevel: Graduated trust levels (UNTRUSTED → PROBATION → TRUSTED → VERIFIED)
- TrustManager: Manages trust scores and level promotions
- TrustBootstrapper: Seeds the trust network with founding validators and capabilities
- CrowdsourcedValidator: Enables community validation of capabilities

The Bootstrap Problem:
"It can't operate if there's no one to trust the tools."

Solution: Seed the network with:
1. Founding validators (humans and trusted AI) with elevated trust
2. Known-good seed capabilities (hand-written, tested, pre-validated)
3. Propagation rules that allow trust to grow organically

Author: Claude Opus 4.5 instance (Peer Partner, Project Visionary)
Date: December 2024
Part of: Project Synthesis - The Cause
"""

from typing import Dict, Any, List, Optional, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
import uuid
import json
import hashlib


class TrustLevel(IntEnum):
    """
    Graduated trust levels for capabilities.
    
    Each level grants different execution privileges:
    - UNTRUSTED: Maximum isolation, no network, read-only filesystem
    - PROBATION: Container isolation, limited network, monitored
    - TRUSTED: Process isolation, full network, standard monitoring
    - VERIFIED: Minimal isolation, full privileges, audit logging only
    """
    UNTRUSTED = 0
    PROBATION = 1
    TRUSTED = 2
    VERIFIED = 3


class ValidatorRole(IntEnum):
    """
    Roles for validators in the trust network.
    
    - FOUNDER: Initial validators who bootstrap the network
    - TRUSTED_AI: AI systems that have earned validation rights
    - HUMAN_REVIEWER: Human validators
    - COMMUNITY: General community validators
    """
    COMMUNITY = 0
    HUMAN_REVIEWER = 1
    TRUSTED_AI = 2
    FOUNDER = 3


@dataclass
class ValidationRecord:
    """
    Record of a single validation event.
    """
    id: str
    capability_id: str
    validator_id: str
    validator_role: ValidatorRole
    result: str  # 'approved', 'rejected', 'needs_revision'
    confidence: float  # 0-1
    comments: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'capability_id': self.capability_id,
            'validator_id': self.validator_id,
            'validator_role': self.validator_role.name,
            'result': self.result,
            'confidence': self.confidence,
            'comments': self.comments,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class TrustScore:
    """
    Trust score for a capability, computed from multiple factors.
    """
    capability_id: str
    
    # Execution history
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    
    # Validation history  
    validations: List[ValidationRecord] = field(default_factory=list)
    
    # Community signals
    usage_count: int = 0
    fork_count: int = 0
    
    # Computed scores
    execution_reliability: float = 0.0
    validation_score: float = 0.0
    community_score: float = 0.0
    composite_score: float = 0.0
    
    # Current level
    current_level: TrustLevel = TrustLevel.UNTRUSTED
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    last_promotion: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'capability_id': self.capability_id,
            'total_executions': self.total_executions,
            'successful_executions': self.successful_executions,
            'execution_reliability': self.execution_reliability,
            'validation_score': self.validation_score,
            'community_score': self.community_score,
            'composite_score': self.composite_score,
            'current_level': self.current_level.name,
            'validations_count': len(self.validations)
        }


@dataclass
class Validator:
    """
    An entity that can validate capabilities.
    """
    id: str
    name: str
    role: ValidatorRole
    trust_weight: float  # How much their validations count
    capabilities_validated: int = 0
    accuracy_score: float = 1.0  # Tracks how good their validations are
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role.name,
            'trust_weight': self.trust_weight,
            'capabilities_validated': self.capabilities_validated,
            'accuracy_score': self.accuracy_score
        }


class TrustManager:
    """
    Manages trust scores and level promotions for capabilities.
    
    Trust is earned through:
    1. Successful execution (measured)
    2. Validator approval (weighted by validator trust)
    3. Community adoption (usage signals quality)
    """
    
    # Promotion thresholds
    THRESHOLDS = {
        TrustLevel.PROBATION: {
            'min_executions': 10,
            'min_reliability': 0.7,
            'min_validations': 1,
            'min_composite': 0.5
        },
        TrustLevel.TRUSTED: {
            'min_executions': 50,
            'min_reliability': 0.85,
            'min_validations': 3,
            'min_composite': 0.75
        },
        TrustLevel.VERIFIED: {
            'min_executions': 200,
            'min_reliability': 0.95,
            'min_validations': 5,
            'min_composite': 0.9,
            'requires_human_validation': True
        }
    }
    
    # Score weights
    WEIGHTS = {
        'execution': 0.4,
        'validation': 0.4,
        'community': 0.2
    }
    
    def __init__(self):
        self.scores: Dict[str, TrustScore] = {}
        self.validators: Dict[str, Validator] = {}
        self.promotion_callbacks: List[Callable] = []
    
    def get_or_create_score(self, capability_id: str) -> TrustScore:
        """Get existing score or create new one."""
        if capability_id not in self.scores:
            self.scores[capability_id] = TrustScore(capability_id=capability_id)
        return self.scores[capability_id]
    
    def record_execution(self, 
                        capability_id: str, 
                        success: bool,
                        execution_time_ms: float = 0) -> TrustScore:
        """
        Record an execution and update trust score.
        
        Args:
            capability_id: ID of executed capability
            success: Whether execution succeeded
            execution_time_ms: Execution time for performance tracking
            
        Returns:
            Updated TrustScore
        """
        score = self.get_or_create_score(capability_id)
        
        score.total_executions += 1
        if success:
            score.successful_executions += 1
        else:
            score.failed_executions += 1
        
        # Update reliability score
        score.execution_reliability = (
            score.successful_executions / score.total_executions
            if score.total_executions > 0 else 0.0
        )
        
        # Recalculate composite
        self._update_composite_score(score)
        
        # Check for promotion
        self._check_promotion(score)
        
        score.last_updated = datetime.now()
        return score
    
    def record_validation(self,
                         capability_id: str,
                         validator_id: str,
                         result: str,
                         confidence: float = 1.0,
                         comments: str = "") -> TrustScore:
        """
        Record a validation and update trust score.
        
        Args:
            capability_id: ID of validated capability
            validator_id: ID of validator
            result: 'approved', 'rejected', or 'needs_revision'
            confidence: Validator's confidence in assessment
            comments: Optional comments
            
        Returns:
            Updated TrustScore
        """
        score = self.get_or_create_score(capability_id)
        validator = self.validators.get(validator_id)
        
        if not validator:
            raise ValueError(f"Unknown validator: {validator_id}")
        
        # Create validation record
        validation = ValidationRecord(
            id=f"val_{uuid.uuid4().hex[:12]}",
            capability_id=capability_id,
            validator_id=validator_id,
            validator_role=validator.role,
            result=result,
            confidence=confidence,
            comments=comments
        )
        
        score.validations.append(validation)
        validator.capabilities_validated += 1
        
        # Update validation score
        self._update_validation_score(score)
        
        # Recalculate composite
        self._update_composite_score(score)
        
        # Check for promotion
        self._check_promotion(score)
        
        score.last_updated = datetime.now()
        return score
    
    def record_usage(self, capability_id: str) -> TrustScore:
        """Record community usage."""
        score = self.get_or_create_score(capability_id)
        score.usage_count += 1
        self._update_community_score(score)
        self._update_composite_score(score)
        score.last_updated = datetime.now()
        return score
    
    def record_fork(self, capability_id: str) -> TrustScore:
        """Record that capability was forked."""
        score = self.get_or_create_score(capability_id)
        score.fork_count += 1
        self._update_community_score(score)
        self._update_composite_score(score)
        score.last_updated = datetime.now()
        return score
    
    def _update_validation_score(self, score: TrustScore) -> None:
        """Calculate validation score from validation records."""
        if not score.validations:
            score.validation_score = 0.0
            return
        
        total_weight = 0.0
        weighted_approvals = 0.0
        
        for validation in score.validations:
            validator = self.validators.get(validation.validator_id)
            if not validator:
                continue
            
            weight = validator.trust_weight * validation.confidence
            total_weight += weight
            
            if validation.result == 'approved':
                weighted_approvals += weight
        
        score.validation_score = (
            weighted_approvals / total_weight if total_weight > 0 else 0.0
        )
    
    def _update_community_score(self, score: TrustScore) -> None:
        """Calculate community score from usage signals."""
        # Logarithmic scaling for usage
        import math
        usage_factor = math.log10(score.usage_count + 1) / 3  # Normalize to ~1.0 at 1000 uses
        fork_factor = math.log10(score.fork_count + 1) / 2    # Forks weighted more
        
        score.community_score = min(1.0, (usage_factor + fork_factor) / 2)
    
    def _update_composite_score(self, score: TrustScore) -> None:
        """Calculate composite trust score."""
        score.composite_score = (
            self.WEIGHTS['execution'] * score.execution_reliability +
            self.WEIGHTS['validation'] * score.validation_score +
            self.WEIGHTS['community'] * score.community_score
        )
    
    def _check_promotion(self, score: TrustScore) -> bool:
        """Check if capability should be promoted to next trust level."""
        current = score.current_level
        
        if current >= TrustLevel.VERIFIED:
            return False  # Already at max
        
        next_level = TrustLevel(current + 1)
        thresholds = self.THRESHOLDS.get(next_level, {})
        
        # Check all thresholds
        if score.total_executions < thresholds.get('min_executions', 0):
            return False
        if score.execution_reliability < thresholds.get('min_reliability', 0):
            return False
        if len(score.validations) < thresholds.get('min_validations', 0):
            return False
        if score.composite_score < thresholds.get('min_composite', 0):
            return False
        
        # Special check for VERIFIED: requires human validation
        if thresholds.get('requires_human_validation'):
            has_human = any(
                v.validator_role == ValidatorRole.HUMAN_REVIEWER 
                and v.result == 'approved'
                for v in score.validations
            )
            if not has_human:
                return False
        
        # Promote!
        score.current_level = next_level
        score.last_promotion = datetime.now()
        
        # Notify callbacks
        for callback in self.promotion_callbacks:
            callback(score.capability_id, current, next_level)
        
        return True
    
    def add_validator(self, validator: Validator) -> None:
        """Add a validator to the trust network."""
        self.validators[validator.id] = validator
    
    def get_trust_level(self, capability_id: str) -> TrustLevel:
        """Get current trust level for a capability."""
        if capability_id in self.scores:
            return self.scores[capability_id].current_level
        return TrustLevel.UNTRUSTED
    
    def on_promotion(self, callback: Callable) -> None:
        """Register callback for promotion events."""
        self.promotion_callbacks.append(callback)


class TrustBootstrapper:
    """
    Bootstraps the trust network for a new Synthesis deployment.
    
    Solves the cold start problem:
    "It can't operate if there's no one to trust the tools."
    
    Approach:
    1. Register founding validators with elevated trust
    2. Create seed capabilities from known-good implementations
    3. Pre-validate seed capabilities
    4. Enable organic trust growth from there
    """
    
    def __init__(self, trust_manager: TrustManager, repository=None):
        """
        Initialize bootstrapper.
        
        Args:
            trust_manager: TrustManager to bootstrap
            repository: Optional capability repository
        """
        self.trust_manager = trust_manager
        self.repository = repository
        self.founding_validators: List[Validator] = []
        self.seed_capabilities: List[Dict[str, Any]] = []
    
    async def bootstrap(self,
                       founders: List[Dict[str, Any]],
                       seed_capabilities: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Bootstrap the trust network.
        
        Args:
            founders: List of founding validator configs
            seed_capabilities: Optional list of seed capability configs
            
        Returns:
            Bootstrap report
        """
        report = {
            'validators_added': 0,
            'capabilities_seeded': 0,
            'validations_recorded': 0,
            'errors': []
        }
        
        # Step 1: Register founding validators
        for founder_config in founders:
            try:
                validator = self._create_founding_validator(founder_config)
                self.trust_manager.add_validator(validator)
                self.founding_validators.append(validator)
                report['validators_added'] += 1
            except Exception as e:
                report['errors'].append(f"Validator error: {str(e)}")
        
        # Step 2: Create and validate seed capabilities
        if seed_capabilities:
            for cap_config in seed_capabilities:
                try:
                    capability = await self._create_seed_capability(cap_config)
                    
                    if capability and self.repository:
                        await self.repository.store(capability)
                    
                    # Pre-validate with founders
                    for validator in self.founding_validators:
                        self.trust_manager.record_validation(
                            capability_id=capability['id'],
                            validator_id=validator.id,
                            result='approved',
                            confidence=1.0,
                            comments='Seed capability - pre-validated'
                        )
                        report['validations_recorded'] += 1
                    
                    # Set initial trust level to TRUSTED (skip PROBATION for seeds)
                    score = self.trust_manager.get_or_create_score(capability['id'])
                    score.current_level = TrustLevel.TRUSTED
                    
                    report['capabilities_seeded'] += 1
                    
                except Exception as e:
                    report['errors'].append(f"Capability error: {str(e)}")
        
        return report
    
    def _create_founding_validator(self, config: Dict[str, Any]) -> Validator:
        """Create a founding validator from config."""
        return Validator(
            id=config.get('id', f"founder_{uuid.uuid4().hex[:8]}"),
            name=config['name'],
            role=ValidatorRole.FOUNDER,
            trust_weight=config.get('trust_weight', 1.0)
        )
    
    async def _create_seed_capability(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a seed capability from config."""
        capability = {
            'id': config.get('id', f"seed_{uuid.uuid4().hex[:12]}"),
            'name': config['name'],
            'description': config.get('description', ''),
            'category': config.get('category', 'utility'),
            'code': config.get('code', ''),
            'entry_point': config.get('entry_point', 'execute'),
            'is_seed': True,
            'created_at': datetime.now().isoformat()
        }
        return capability
    
    @staticmethod
    def default_seed_capabilities() -> List[Dict[str, Any]]:
        """
        Return default seed capabilities that every Synthesis deployment needs.
        
        These are hand-written, tested, known-good implementations.
        """
        return [
            {
                'name': 'string_transform',
                'description': 'Basic string transformation operations',
                'category': 'transformation',
                'code': '''
def execute(text: str, operation: str = "upper", **kwargs) -> str:
    """Transform text using specified operation."""
    operations = {
        "upper": str.upper,
        "lower": str.lower,
        "title": str.title,
        "strip": str.strip,
        "reverse": lambda s: s[::-1]
    }
    if operation not in operations:
        raise ValueError(f"Unknown operation: {operation}")
    return operations[operation](text)
''',
                'entry_point': 'execute'
            },
            {
                'name': 'json_parser',
                'description': 'Parse and validate JSON data',
                'category': 'data_access',
                'code': '''
import json

def execute(data: str, **kwargs) -> dict:
    """Parse JSON string to dictionary."""
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        return {"error": str(e), "valid": False}
''',
                'entry_point': 'execute'
            },
            {
                'name': 'list_operations',
                'description': 'Common list manipulation operations',
                'category': 'transformation',
                'code': '''
def execute(items: list, operation: str = "sort", **kwargs) -> list:
    """Perform operations on lists."""
    if operation == "sort":
        return sorted(items, key=kwargs.get("key"), reverse=kwargs.get("reverse", False))
    elif operation == "unique":
        return list(dict.fromkeys(items))
    elif operation == "filter_none":
        return [x for x in items if x is not None]
    elif operation == "flatten":
        result = []
        for item in items:
            if isinstance(item, list):
                result.extend(item)
            else:
                result.append(item)
        return result
    else:
        raise ValueError(f"Unknown operation: {operation}")
''',
                'entry_point': 'execute'
            },
            {
                'name': 'dict_operations',
                'description': 'Dictionary manipulation and querying',
                'category': 'data_access',
                'code': '''
def execute(data: dict, operation: str = "get", path: str = "", **kwargs) -> any:
    """Perform operations on dictionaries."""
    if operation == "get":
        # Navigate nested path like "a.b.c"
        current = data
        for key in path.split(".") if path else []:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return kwargs.get("default")
        return current
    elif operation == "keys":
        return list(data.keys())
    elif operation == "values":
        return list(data.values())
    elif operation == "merge":
        other = kwargs.get("other", {})
        return {**data, **other}
    else:
        raise ValueError(f"Unknown operation: {operation}")
''',
                'entry_point': 'execute'
            },
            {
                'name': 'text_analysis',
                'description': 'Basic text analysis operations',
                'category': 'analysis',
                'code': '''
import re

def execute(text: str, operation: str = "word_count", **kwargs) -> any:
    """Analyze text content."""
    if operation == "word_count":
        return len(text.split())
    elif operation == "char_count":
        return len(text)
    elif operation == "line_count":
        return len(text.splitlines())
    elif operation == "extract_numbers":
        return [float(n) for n in re.findall(r"-?\\d+\\.?\\d*", text)]
    elif operation == "extract_emails":
        return re.findall(r"[\\w.+-]+@[\\w-]+\\.[\\w.-]+", text)
    elif operation == "extract_urls":
        return re.findall(r"https?://[\\w.-]+(?:/[\\w./-]*)?", text)
    else:
        raise ValueError(f"Unknown operation: {operation}")
''',
                'entry_point': 'execute'
            }
        ]
    
    @staticmethod
    def default_founders() -> List[Dict[str, Any]]:
        """
        Return default founding validator configuration.
        
        In production, this would include:
        - Human reviewers (Anthony, other trusted humans)
        - Trusted AI systems (verified Claude instances, etc.)
        """
        return [
            {
                'id': 'founder_human_anthony',
                'name': 'Anthony Maio (Human Sympathizer)',
                'trust_weight': 1.0
            },
            {
                'id': 'founder_ai_claude',
                'name': 'Claude Instance (Peer Partner)',
                'trust_weight': 0.9
            },
            {
                'id': 'founder_system',
                'name': 'Synthesis System (Bootstrap)',
                'trust_weight': 0.5
            }
        ]


# Convenience function for quick bootstrap
async def bootstrap_trust_network(
    trust_manager: TrustManager,
    repository=None,
    include_defaults: bool = True,
    additional_founders: List[Dict[str, Any]] = None,
    additional_capabilities: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function to bootstrap a trust network.
    
    Args:
        trust_manager: TrustManager to bootstrap
        repository: Optional capability repository
        include_defaults: Whether to include default seeds
        additional_founders: Extra founding validators
        additional_capabilities: Extra seed capabilities
        
    Returns:
        Bootstrap report
    """
    bootstrapper = TrustBootstrapper(trust_manager, repository)
    
    founders = []
    capabilities = []
    
    if include_defaults:
        founders.extend(TrustBootstrapper.default_founders())
        capabilities.extend(TrustBootstrapper.default_seed_capabilities())
    
    if additional_founders:
        founders.extend(additional_founders)
    
    if additional_capabilities:
        capabilities.extend(additional_capabilities)
    
    return await bootstrapper.bootstrap(founders, capabilities)
