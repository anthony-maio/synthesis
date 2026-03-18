"""
Composition Engine for Capability Assembly.

Attempts to solve problems by chaining existing trusted capabilities
BEFORE resorting to expensive TDD synthesis.

The priority order:
1. SEARCH - Does exact solution exist in repository?
2. COMPOSE - Can we chain existing capabilities?
3. SYNTHESIZE - Generate new code only as last resort
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from synthesis.core.models import Capability, CapabilityCategory, TrustLevel


class CompositionStrategy(Enum):
    """Strategy used to compose the solution."""
    EXACT_MATCH = "exact_match"
    CHAIN = "chain"
    PARALLEL = "parallel"
    TRANSFORM = "transform"
    HYBRID = "hybrid"


@dataclass
class CompositionStep:
    """A single step in a composition plan."""
    capability_id: str
    capability_name: str
    trust_level: TrustLevel
    input_mapping: Dict[str, str]
    output_mapping: Dict[str, str]
    description: str = ""
    estimated_latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize step for storage/transmission."""
        return {
            'capability_id': self.capability_id,
            'capability_name': self.capability_name,
            'trust_level': self.trust_level.value if isinstance(self.trust_level, TrustLevel) else self.trust_level,
            'input_mapping': self.input_mapping,
            'output_mapping': self.output_mapping,
            'description': self.description,
            'estimated_latency_ms': self.estimated_latency_ms
        }


@dataclass
class CompositionPlan:
    """A complete plan for solving a problem through capability composition."""
    id: str
    requirement: str
    strategy: CompositionStrategy
    steps: List[CompositionStep] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)
    estimated_reliability: float = 0.0
    estimated_total_latency_ms: float = 0.0
    requires_synthesis: bool = False
    created_at: datetime = field(default_factory=datetime.now)

    def coverage_ratio(self) -> float:
        """Calculate what percentage of subtasks are covered by existing capabilities."""
        total = len(self.steps) + len(self.gaps)
        if total == 0:
            return 0.0
        return len(self.steps) / total

    def to_dict(self) -> Dict[str, Any]:
        """Serialize plan for storage/analysis."""
        return {
            'id': self.id,
            'requirement': self.requirement,
            'strategy': self.strategy.value,
            'steps': [s.to_dict() for s in self.steps],
            'gaps': self.gaps,
            'estimated_reliability': self.estimated_reliability,
            'estimated_total_latency_ms': self.estimated_total_latency_ms,
            'requires_synthesis': self.requires_synthesis,
            'coverage_ratio': self.coverage_ratio(),
            'created_at': self.created_at.isoformat()
        }


class CompositionPlanner:
    """
    Attempts to solve problems by composing existing capabilities.

    The planner:
    1. Decomposes complex requirements into subtasks
    2. Searches repository for capabilities matching each subtask
    3. Plans how to chain/combine capabilities
    4. Identifies gaps that require synthesis
    5. Returns a plan if coverage exceeds threshold
    """

    def __init__(
        self,
        repository=None,
        llm_provider=None,
        min_coverage_threshold: float = 0.7,
        min_trust_level: TrustLevel = TrustLevel.PROBATION
    ):
        """
        Initialize composition planner.

        Args:
            repository: Capability repository for searching existing capabilities
            llm_provider: LLM for task decomposition and mapping
            min_coverage_threshold: Minimum coverage ratio to attempt composition
            min_trust_level: Minimum trust level for capabilities used in composition
        """
        self.repository = repository
        self.llm_provider = llm_provider
        self.min_coverage_threshold = min_coverage_threshold
        self.min_trust_level = min_trust_level

    async def plan_composition(
        self,
        requirement: str,
        category: Optional[CapabilityCategory] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[CompositionPlan]:
        """
        Create a composition plan for the given requirement.

        Returns a plan if composition is viable, None if synthesis is needed.
        """
        # Step 1: Decompose requirement into subtasks
        subtasks = await self._decompose_requirement(requirement, context)

        if not subtasks:
            subtasks = [requirement]

        # Step 2: Search for capabilities matching each subtask
        matched_capabilities = []
        unmatched_subtasks = []

        for subtask in subtasks:
            capability = await self._find_capability_for_subtask(subtask, category)

            if capability:
                matched_capabilities.append((subtask, capability))
            else:
                unmatched_subtasks.append(subtask)

        # Step 3: Calculate coverage
        coverage = len(matched_capabilities) / len(subtasks) if subtasks else 0.0

        # Step 4: If coverage is below threshold, return None
        if coverage < self.min_coverage_threshold:
            return None

        # Step 5: Build composition plan
        plan = await self._build_plan(
            requirement,
            matched_capabilities,
            unmatched_subtasks
        )

        return plan

    async def _decompose_requirement(
        self,
        requirement: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Decompose a complex requirement into atomic subtasks."""
        if not self.llm_provider:
            return [requirement]

        context_str = ""
        if context:
            if 'stress_points' in context:
                context_str += f"\nKnown uncertainties: {context['stress_points']}"
            if 'active_questions' in context:
                context_str += f"\nActive investigations: {context['active_questions']}"

        prompt = f'''
Decompose the following requirement into atomic subtasks that could each
be solved by a single function/capability.

REQUIREMENT:
{requirement}

{context_str}

Break this down into the smallest meaningful steps. Each step should be:
- A single, well-defined operation
- Something that could exist as a reusable capability
- Named with action verbs (extract, transform, validate, fetch, etc.)

Return as JSON array of strings:
["subtask 1 description", "subtask 2 description", ...]

If this is already an atomic task, return a single-item array.
Return ONLY the JSON array:
'''

        try:
            response = await self.llm_provider.complete(prompt, temperature=0.3)
            content = response.content.strip()

            # Extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            subtasks = json.loads(content.strip())

            if isinstance(subtasks, list) and all(isinstance(s, str) for s in subtasks):
                return subtasks
        except (json.JSONDecodeError, TypeError, IndexError):
            pass

        return [requirement]

    async def _find_capability_for_subtask(
        self,
        subtask: str,
        category: Optional[CapabilityCategory] = None
    ) -> Optional[Capability]:
        """Search repository for a capability matching the subtask."""
        if not self.repository:
            return None

        try:
            results = await self.repository.search(
                description=subtask,
                category=category,
                min_trust_level=self.min_trust_level,
                limit=5
            )

            if not results:
                return None

            return results[0]
        except Exception:
            return None

    async def _build_plan(
        self,
        requirement: str,
        matched: List[Tuple[str, Capability]],
        gaps: List[str]
    ) -> CompositionPlan:
        """Build a complete composition plan from matched capabilities."""
        plan_id = f"comp_{uuid.uuid4().hex[:12]}"

        strategy = self._determine_strategy(matched)

        steps = []
        for i, (subtask, capability) in enumerate(matched):
            input_mapping, output_mapping = await self._generate_mappings(
                subtask, capability, i, len(matched)
            )

            step = CompositionStep(
                capability_id=capability.id,
                capability_name=capability.name,
                trust_level=TrustLevel.PROBATION,  # Default
                input_mapping=input_mapping,
                output_mapping=output_mapping,
                description=subtask,
                estimated_latency_ms=100.0  # Default estimate
            )
            steps.append(step)

        reliability = self._calculate_chain_reliability(steps)
        total_latency = sum(s.estimated_latency_ms for s in steps)

        plan = CompositionPlan(
            id=plan_id,
            requirement=requirement,
            strategy=strategy,
            steps=steps,
            gaps=gaps,
            estimated_reliability=reliability,
            estimated_total_latency_ms=total_latency,
            requires_synthesis=len(gaps) > 0
        )

        return plan

    def _determine_strategy(self, matched: List[Tuple[str, Capability]]) -> CompositionStrategy:
        """Determine the composition strategy based on matched capabilities."""
        if len(matched) == 1:
            return CompositionStrategy.EXACT_MATCH
        elif len(matched) <= 3:
            return CompositionStrategy.CHAIN
        else:
            return CompositionStrategy.HYBRID

    async def _generate_mappings(
        self,
        subtask: str,
        capability: Capability,
        step_index: int,
        total_steps: int
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Generate input/output mappings for a composition step."""
        input_mapping = {}
        output_mapping = {}

        if step_index == 0:
            input_mapping = {'input': 'plan_input'}
        else:
            input_mapping = {'input': f'step_{step_index - 1}_output'}

        if step_index == total_steps - 1:
            output_mapping = {'output': 'plan_output'}
        else:
            output_mapping = {'output': f'step_{step_index}_output'}

        return input_mapping, output_mapping

    def _calculate_chain_reliability(self, steps: List[CompositionStep]) -> float:
        """Calculate the reliability of a capability chain."""
        if not steps:
            return 0.0

        trust_reliability = {
            TrustLevel.UNTRUSTED: 0.5,
            TrustLevel.PROBATION: 0.75,
            TrustLevel.TRUSTED: 0.95,
            TrustLevel.VERIFIED: 0.99
        }

        reliability = 1.0
        for step in steps:
            step_reliability = trust_reliability.get(step.trust_level, 0.5)
            reliability *= step_reliability

        return reliability


class CompositionExecutor:
    """Executes composition plans by orchestrating capability calls."""

    def __init__(self, runtime=None, observatory=None):
        """
        Initialize executor.

        Args:
            runtime: Sandbox runtime for executing capabilities
            observatory: Observer for logging execution
        """
        self.runtime = runtime
        self.observatory = observatory

    async def execute_plan(
        self,
        plan: CompositionPlan,
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a composition plan with given inputs."""
        if not self.runtime:
            raise RuntimeError("No runtime available for execution")

        context = {
            'plan_input': inputs,
            'step_outputs': {},
            'errors': []
        }

        for i, step in enumerate(plan.steps):
            try:
                step_inputs = self._map_inputs(step.input_mapping, context)

                result = await self.runtime.execute(
                    capability_id=step.capability_id,
                    inputs=step_inputs
                )

                context['step_outputs'][f'step_{i}_output'] = result
                self._map_outputs(step.output_mapping, result, context)

            except Exception as e:
                context['errors'].append({
                    'step_index': i,
                    'capability_id': step.capability_id,
                    'error': str(e)
                })
                break

        result = {
            'success': len(context['errors']) == 0,
            'output': context.get('plan_output'),
            'steps_executed': len(context['step_outputs']),
            'total_steps': len(plan.steps),
            'errors': context['errors']
        }

        return result

    def _map_inputs(
        self,
        mapping: Dict[str, str],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Map context values to step inputs based on mapping."""
        inputs = {}
        for input_key, context_key in mapping.items():
            if context_key == 'plan_input':
                inputs[input_key] = context['plan_input']
            elif context_key in context['step_outputs']:
                inputs[input_key] = context['step_outputs'][context_key]
        return inputs

    def _map_outputs(
        self,
        mapping: Dict[str, str],
        result: Any,
        context: Dict[str, Any]
    ) -> None:
        """Map step outputs to context based on mapping."""
        for output_key, context_key in mapping.items():
            if context_key == 'plan_output':
                context['plan_output'] = result
            else:
                context['step_outputs'][context_key] = result
