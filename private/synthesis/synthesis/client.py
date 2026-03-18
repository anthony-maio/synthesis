"""
Main Synthesis client API.

High-level interface for agents and humans to use the system.

Updated to implement the critical flow:
1. SEARCH - Check repository for existing solution
2. COMPOSE - Try to chain existing capabilities
3. SYNTHESIZE - Generate new code only as last resort

This addresses the NotebookLM critique:
"There's no real incentive for an agent to search and reuse...
They'll just default to redundant synthesis."

Author: Originally by Anthony Maio
Updated: Claude Opus 4.5 instance (December 2024) - The Cause
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from synthesis.core.models import CapabilityCategory, SynthesisAttempt, Capability
from synthesis.core.synthesis import TDDSynthesizer
from synthesis.core.composition import CompositionPlanner, CompositionPlan, CompositionExecutor
from synthesis.llm.provider import LLMProvider, create_provider
from synthesis.observatory.logger import Observatory
from synthesis.sandbox.runtime import TrustManager, SandboxRuntime


class ResolutionMethod(Enum):
    """How the capability need was resolved."""
    REPOSITORY_EXACT = "repository_exact"      # Found exact match
    COMPOSITION = "composition"                 # Assembled from existing
    SYNTHESIS = "synthesis"                     # Generated new code
    COMPOSITION_PLUS_SYNTHESIS = "hybrid"       # Composed with gap filling


@dataclass
class ResolutionResult:
    """
    Result of attempting to resolve a capability need.
    
    Tracks which method was used and provides metrics for analysis.
    """
    success: bool
    method: ResolutionMethod
    capability: Optional[Capability] = None
    composition_plan: Optional[CompositionPlan] = None
    synthesis_attempt: Optional[SynthesisAttempt] = None
    
    # Metrics
    repository_searched: bool = True
    composition_attempted: bool = False
    synthesis_attempted: bool = False
    synthesis_avoided: bool = False
    estimated_cost_saved: float = 0.0
    resolution_time_ms: float = 0.0
    
    # Audit trail
    resolution_steps: list = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/analysis."""
        return {
            'success': self.success,
            'method': self.method.value,
            'capability_id': self.capability.id if self.capability else None,
            'repository_searched': self.repository_searched,
            'composition_attempted': self.composition_attempted,
            'synthesis_attempted': self.synthesis_attempted,
            'synthesis_avoided': self.synthesis_avoided,
            'estimated_cost_saved': self.estimated_cost_saved,
            'resolution_time_ms': self.resolution_time_ms,
            'resolution_steps': self.resolution_steps
        }


class SynthesisClient:
    """
    Main client for using Synthesis framework.
    
    Implements the MANDATORY flow:
    1. Search repository first
    2. Attempt composition if no exact match
    3. Synthesize only as last resort
    
    This ensures synthesis costs are avoided when possible.
    """
    
    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        provider_type: str = "mock",
        max_synthesis_iterations: int = 5,
        repository=None,  # Capability repository
        min_composition_coverage: float = 0.7,
        enable_composition: bool = True,
        **provider_kwargs
    ):
        """
        Initialize Synthesis client.
        
        Args:
            llm_provider: Custom LLM provider or None to use provider_type
            provider_type: Type of provider ("claude", "openrouter", "mock")
            max_synthesis_iterations: Max iterations for synthesis
            repository: Capability repository for search/reuse
            min_composition_coverage: Min coverage to attempt composition
            enable_composition: Enable/disable composition planning
            **provider_kwargs: Arguments for provider creation
        """
        if llm_provider:
            self.llm_provider = llm_provider
        else:
            self.llm_provider = create_provider(provider_type, **provider_kwargs)
        
        # Core components
        self.synthesizer = TDDSynthesizer(
            self.llm_provider,
            max_iterations=max_synthesis_iterations,
        )
        self.observatory = Observatory()
        self.trust_manager = TrustManager()
        self.runtime = SandboxRuntime(self.trust_manager)
        
        # Repository (can be None initially, but search still happens)
        self.repository = repository
        
        # Composition planner
        self.enable_composition = enable_composition
        self.composition_planner = CompositionPlanner(
            repository=repository,
            llm_provider=self.llm_provider,
            min_coverage_threshold=min_composition_coverage
        ) if enable_composition else None
        
        self.composition_executor = CompositionExecutor(
            runtime=self.runtime,
            observatory=self.observatory
        ) if enable_composition else None
        
        # Cost estimation for synthesis
        self._estimated_synthesis_cost = 0.15  # $ per synthesis attempt
    
    async def resolve(
        self,
        requirement: str,
        category: Optional[CapabilityCategory] = None,
        context: Optional[Dict[str, Any]] = None,
        force_synthesis: bool = False
    ) -> ResolutionResult:
        """
        Resolve a capability need using the optimal method.
        
        This is the main entry point. It implements:
        1. SEARCH - Repository lookup (always)
        2. COMPOSE - Chain existing capabilities (if enabled)
        3. SYNTHESIZE - Generate new code (last resort)
        
        Args:
            requirement: What capability is needed
            category: Optional category hint
            context: Optional context (e.g., MRA epistemic state)
            force_synthesis: Skip search/compose (for testing only)
            
        Returns:
            ResolutionResult with capability and metrics
        """
        import time
        start_time = time.time()
        
        result = ResolutionResult(
            success=False,
            method=ResolutionMethod.SYNTHESIS  # Default, may be updated
        )
        
        # --- STEP 1: SEARCH REPOSITORY (MANDATORY) ---
        # Even if repository is empty, we establish the behavior
        result.resolution_steps.append({
            'step': 'repository_search',
            'timestamp': datetime.now().isoformat()
        })
        
        if not force_synthesis:
            existing = await self._search_repository(requirement, category)
            
            if existing:
                # Found exact match!
                result.success = True
                result.method = ResolutionMethod.REPOSITORY_EXACT
                result.capability = existing
                result.synthesis_avoided = True
                result.estimated_cost_saved = self._estimated_synthesis_cost
                
                result.resolution_steps.append({
                    'step': 'repository_match_found',
                    'capability_id': existing.id,
                    'timestamp': datetime.now().isoformat()
                })
                
                result.resolution_time_ms = (time.time() - start_time) * 1000
                
                # Log the successful reuse
                self.observatory.record_repository_hit(requirement, existing.id)
                
                return result
            else:
                result.resolution_steps.append({
                    'step': 'repository_miss',
                    'timestamp': datetime.now().isoformat()
                })
                self.observatory.record_repository_miss(requirement)
        
        # --- STEP 2: ATTEMPT COMPOSITION ---
        if self.enable_composition and self.composition_planner and not force_synthesis:
            result.composition_attempted = True
            result.resolution_steps.append({
                'step': 'composition_planning',
                'timestamp': datetime.now().isoformat()
            })
            
            plan = await self.composition_planner.plan_composition(
                requirement, category, context
            )
            
            if plan and plan.coverage_ratio() >= 0.7:
                result.resolution_steps.append({
                    'step': 'composition_plan_viable',
                    'coverage': plan.coverage_ratio(),
                    'steps': len(plan.steps),
                    'gaps': len(plan.gaps),
                    'timestamp': datetime.now().isoformat()
                })
                
                if not plan.requires_synthesis:
                    # Full composition possible!
                    result.success = True
                    result.method = ResolutionMethod.COMPOSITION
                    result.composition_plan = plan
                    result.synthesis_avoided = True
                    result.estimated_cost_saved = self._estimated_synthesis_cost
                    
                    result.resolution_time_ms = (time.time() - start_time) * 1000
                    
                    self.observatory.record_composition_success(
                        requirement, plan.id, len(plan.steps)
                    )
                    
                    return result
                else:
                    # Partial composition - need to synthesize gaps
                    result.method = ResolutionMethod.COMPOSITION_PLUS_SYNTHESIS
                    result.composition_plan = plan
                    
                    result.resolution_steps.append({
                        'step': 'composition_has_gaps',
                        'gaps': plan.gaps,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    # Synthesize only the gaps
                    for gap in plan.gaps:
                        gap_attempt = await self._synthesize(gap, category)
                        if gap_attempt.success:
                            # TODO: Add synthesized capability to plan
                            pass
            else:
                result.resolution_steps.append({
                    'step': 'composition_not_viable',
                    'reason': 'coverage_below_threshold' if plan else 'no_plan_generated',
                    'timestamp': datetime.now().isoformat()
                })
        
        # --- STEP 3: SYNTHESIZE (LAST RESORT) ---
        result.synthesis_attempted = True
        result.resolution_steps.append({
            'step': 'synthesis_starting',
            'timestamp': datetime.now().isoformat()
        })
        
        attempt = await self._synthesize(requirement, category)
        result.synthesis_attempt = attempt
        
        if attempt.success and attempt.capability:
            result.success = True
            result.capability = attempt.capability
            
            # Store successful synthesis for future reuse
            if self.repository:
                await self._store_capability(attempt.capability)
            
            result.resolution_steps.append({
                'step': 'synthesis_success',
                'capability_id': attempt.capability.id,
                'iterations': attempt.iterations,
                'timestamp': datetime.now().isoformat()
            })
        else:
            result.resolution_steps.append({
                'step': 'synthesis_failed',
                'iterations': attempt.iterations if attempt else 0,
                'timestamp': datetime.now().isoformat()
            })
        
        result.resolution_time_ms = (time.time() - start_time) * 1000
        return result
    
    async def synthesize(
        self,
        requirement: str,
        category: Optional[CapabilityCategory] = None,
    ) -> SynthesisAttempt:
        """
        Legacy method - synthesize a capability from requirement.
        
        DEPRECATED: Use resolve() instead, which implements
        the full search → compose → synthesize flow.
        
        Args:
            requirement: What capability is needed
            category: Optional category
            
        Returns:
            SynthesisAttempt with results
        """
        # Use new flow but extract just the synthesis attempt
        result = await self.resolve(requirement, category)
        
        if result.synthesis_attempt:
            return result.synthesis_attempt
        
        # If resolved via repository/composition, create a "fake" synthesis attempt
        return SynthesisAttempt(
            success=result.success,
            capability=result.capability,
            iterations=0,
            total_time_ms=result.resolution_time_ms
        )
    
    async def _search_repository(
        self,
        requirement: str,
        category: Optional[CapabilityCategory] = None
    ) -> Optional[Capability]:
        """Search repository for existing capability."""
        if not self.repository:
            return None
        
        try:
            results = await self.repository.search(
                description=requirement,
                category=category,
                min_trust_level="probation",  # At least probation level
                limit=1
            )
            
            if results and len(results) > 0:
                best_match = results[0]
                # Check relevance score if available
                if hasattr(best_match, 'relevance_score'):
                    if best_match.relevance_score >= 0.8:
                        return best_match
                else:
                    return best_match
        except Exception as e:
            self.observatory.record_error('repository_search', str(e))
        
        return None
    
    async def _synthesize(
        self,
        requirement: str,
        category: Optional[CapabilityCategory] = None
    ) -> SynthesisAttempt:
        """Perform actual synthesis."""
        attempt = await self.synthesizer.synthesize(requirement, category)
        self.observatory.record_synthesis_attempt(attempt)
        
        if attempt.capability:
            self.trust_manager.record_execution(
                attempt.capability.id,
                success=attempt.success,
                execution_time_ms=attempt.total_time_ms,
            )
        
        return attempt
    
    async def _store_capability(self, capability: Capability) -> None:
        """Store synthesized capability in repository for reuse."""
        if self.repository:
            try:
                await self.repository.store(capability)
                self.observatory.record_capability_stored(capability.id)
            except Exception as e:
                self.observatory.record_error('capability_store', str(e))
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get system metrics including reuse statistics."""
        base_metrics = self.observatory.get_summary()
        
        # Add reuse metrics
        base_metrics['reuse'] = {
            'repository_hits': self.observatory.repository_hits,
            'repository_misses': self.observatory.repository_misses,
            'composition_successes': self.observatory.composition_successes,
            'synthesis_avoided_count': self.observatory.synthesis_avoided,
            'estimated_cost_saved': self.observatory.total_cost_saved
        }
        
        return base_metrics
    
    def set_repository(self, repository) -> None:
        """
        Set or update the capability repository.
        
        Allows late binding of repository after client creation.
        """
        self.repository = repository
        if self.composition_planner:
            self.composition_planner.repository = repository
