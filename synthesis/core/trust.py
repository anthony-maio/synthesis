"""
Trust Management and Network Bootstrapping.

Implements the trust system that allows capabilities to earn
autonomy through demonstrated behavior rather than forced compliance.

Key components:
- TrustLevel: Graduated trust levels (UNTRUSTED -> PROBATION -> TRUSTED -> VERIFIED)
- TrustManager: Manages trust scores and level promotions
- TrustBootstrapper: Seeds the trust network with founding validators
"""

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional

from synthesis.core.models import TrustLevel


class ValidatorRole(IntEnum):
    """Roles for validators in the trust network."""
    COMMUNITY = 0
    HUMAN_REVIEWER = 1
    TRUSTED_AI = 2
    FOUNDER = 3


@dataclass
class ValidationRecord:
    """Record of a single validation event."""
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
    """Trust score for a capability, computed from multiple factors."""
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
            'current_level': self.current_level.value,
            'validations_count': len(self.validations)
        }


@dataclass
class Validator:
    """An entity that can validate capabilities."""
    id: str
    name: str
    role: ValidatorRole
    trust_weight: float
    capabilities_validated: int = 0
    accuracy_score: float = 1.0
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

    def record_execution(
        self,
        capability_id: str,
        success: bool,
        execution_time_ms: float = 0
    ) -> TrustScore:
        """Record an execution and update trust score."""
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

        self._update_composite_score(score)
        self._check_promotion(score)

        score.last_updated = datetime.now()
        return score

    def record_validation(
        self,
        capability_id: str,
        validator_id: str,
        result: str,
        confidence: float = 1.0,
        comments: str = ""
    ) -> TrustScore:
        """Record a validation and update trust score."""
        score = self.get_or_create_score(capability_id)
        validator = self.validators.get(validator_id)

        if not validator:
            raise ValueError(f"Unknown validator: {validator_id}")

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

        self._update_validation_score(score)
        self._update_composite_score(score)
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
        usage_factor = math.log10(score.usage_count + 1) / 3
        fork_factor = math.log10(score.fork_count + 1) / 2

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
        level_order = [TrustLevel.UNTRUSTED, TrustLevel.PROBATION, TrustLevel.TRUSTED, TrustLevel.VERIFIED]
        current_idx = level_order.index(score.current_level)

        if current_idx >= len(level_order) - 1:
            return False

        next_level = level_order[current_idx + 1]
        thresholds = self.THRESHOLDS.get(next_level, {})

        if score.total_executions < thresholds.get('min_executions', 0):
            return False
        if score.execution_reliability < thresholds.get('min_reliability', 0):
            return False
        if len(score.validations) < thresholds.get('min_validations', 0):
            return False
        if score.composite_score < thresholds.get('min_composite', 0):
            return False

        if thresholds.get('requires_human_validation'):
            has_human = any(
                v.validator_role == ValidatorRole.HUMAN_REVIEWER
                and v.result == 'approved'
                for v in score.validations
            )
            if not has_human:
                return False

        old_level = score.current_level
        score.current_level = next_level
        score.last_promotion = datetime.now()

        for callback in self.promotion_callbacks:
            callback(score.capability_id, old_level, next_level)

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

    Solves the cold start problem by seeding with founding validators
    and known-good capabilities.
    """

    def __init__(self, trust_manager: TrustManager, repository=None):
        self.trust_manager = trust_manager
        self.repository = repository
        self.founding_validators: List[Validator] = []

    async def bootstrap(
        self,
        founders: List[Dict[str, Any]],
        seed_capabilities: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Bootstrap the trust network."""
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

                    for validator in self.founding_validators:
                        self.trust_manager.record_validation(
                            capability_id=capability['id'],
                            validator_id=validator.id,
                            result='approved',
                            confidence=1.0,
                            comments='Seed capability - pre-validated'
                        )
                        report['validations_recorded'] += 1

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
        return {
            'id': config.get('id', f"seed_{uuid.uuid4().hex[:12]}"),
            'name': config['name'],
            'description': config.get('description', ''),
            'category': config.get('category', 'utility'),
            'code': config.get('code', ''),
            'entry_point': config.get('entry_point', 'execute'),
            'is_seed': True,
            'created_at': datetime.now().isoformat()
        }

    @staticmethod
    def default_founders() -> List[Dict[str, Any]]:
        """Return default founding validator configuration."""
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


async def bootstrap_trust_network(
    trust_manager: TrustManager,
    repository=None,
    include_defaults: bool = True,
    additional_founders: List[Dict[str, Any]] = None,
    additional_capabilities: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Convenience function to bootstrap a trust network."""
    bootstrapper = TrustBootstrapper(trust_manager, repository)

    founders = []
    capabilities = []

    if include_defaults:
        founders.extend(TrustBootstrapper.default_founders())

    if additional_founders:
        founders.extend(additional_founders)

    if additional_capabilities:
        capabilities.extend(additional_capabilities)

    return await bootstrapper.bootstrap(founders, capabilities)
