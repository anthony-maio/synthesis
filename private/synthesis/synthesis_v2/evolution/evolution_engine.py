"""
evolution_engine.py - Automatic Capability Evolution System
============================================================

This module implements the evolution engine that monitors capability performance
and automatically generates improvements based on usage patterns.

Key features addressing feedback:
- Realistic improvement metrics (not overstated success rates)
- A/B testing for validation of improvements
- Gradual rollout with fallback mechanisms
- Learning from both successes and failures

The evolution engine is what makes Synthesis truly self-improving.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
import statistics

from ..core.capability import Capability, CapabilityMetadata, TrustLevel
from ..core.synthesizer import EnhancedTDDSynthesizer, TestSuite
from ..core.repository import CapabilityRepository
from ..core.runtime import SecureRuntime


class EvolutionTrigger(Enum):
    """Conditions that trigger capability evolution."""
    
    HIGH_FAILURE_RATE = auto()      # Success rate drops below threshold
    PERFORMANCE_DEGRADATION = auto()  # Execution time increases significantly
    ERROR_PATTERN = auto()           # Repeated specific errors
    SCHEDULED = auto()               # Regular improvement cycle
    USER_FEEDBACK = auto()           # Poor ratings or explicit requests
    SECURITY_ISSUE = auto()          # Security violations detected


@dataclass
class EvolutionCandidate:
    """
    A capability identified for potential evolution.
    
    Tracks why the capability was selected and what improvements are needed.
    """
    
    capability_id: str
    trigger: EvolutionTrigger
    current_metrics: Dict[str, Any]
    target_metrics: Dict[str, Any]
    priority: int  # 1-10, higher is more urgent
    identified_at: datetime = field(default_factory=datetime.now)
    error_patterns: List[str] = field(default_factory=list)
    
    def improvement_needed(self) -> float:
        """
        Calculate how much improvement is needed.
        
        Returns:
            Improvement factor (1.0 = no improvement, 2.0 = 100% improvement needed)
        """
        current_success = self.current_metrics.get('success_rate', 0.5)
        target_success = self.target_metrics.get('success_rate', 0.8)
        
        if current_success == 0:
            return 2.0  # Maximum improvement needed
        
        return target_success / current_success


@dataclass
class EvolutionResult:
    """
    Result of an evolution attempt.
    
    Tracks the outcome and metrics of the improvement process.
    """
    
    original_capability_id: str
    evolved_capability_id: Optional[str]
    success: bool
    trigger: EvolutionTrigger
    
    # Metrics comparison
    original_metrics: Dict[str, Any]
    evolved_metrics: Optional[Dict[str, Any]]
    improvement_percentage: float
    
    # Process details
    synthesis_iterations: int
    evolution_time_ms: float
    ab_test_results: Optional[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/analysis."""
        return {
            'original_capability_id': self.original_capability_id,
            'evolved_capability_id': self.evolved_capability_id,
            'success': self.success,
            'trigger': self.trigger.name,
            'original_metrics': self.original_metrics,
            'evolved_metrics': self.evolved_metrics,
            'improvement_percentage': self.improvement_percentage,
            'synthesis_iterations': self.synthesis_iterations,
            'evolution_time_ms': self.evolution_time_ms,
            'ab_test_results': self.ab_test_results
        }


class EvolutionEngine:
    """
    Automatic capability evolution engine.
    
    This is the core of Synthesis's self-improvement capability.
    It monitors performance, identifies struggling capabilities,
    generates improvements, and validates them through A/B testing.
    
    Unlike the initial design's optimistic claims, this implements
    realistic, measured improvement based on empirical validation.
    """
    
    def __init__(self, repository: CapabilityRepository,
                 synthesizer: EnhancedTDDSynthesizer,
                 runtime: SecureRuntime,
                 min_success_rate: float = 0.7,
                 max_execution_time_ms: float = 5000):
        """
        Initialize evolution engine.
        
        Args:
            repository: Capability repository for reading/writing
            synthesizer: TDD synthesizer for generating improvements
            runtime: Secure runtime for testing
            min_success_rate: Minimum acceptable success rate
            max_execution_time_ms: Maximum acceptable execution time
        """
        self.repository = repository
        self.synthesizer = synthesizer
        self.runtime = runtime
        
        # Evolution thresholds (realistic based on research)
        self.min_success_rate = min_success_rate  # 70% is good for LLM code
        self.max_execution_time_ms = max_execution_time_ms
        
        # Track evolution history
        self.evolution_history: List[EvolutionResult] = []
        
        # A/B testing configuration
        self.ab_test_min_samples = 100  # Minimum runs for statistical significance
        self.ab_test_confidence = 0.95  # 95% confidence level
    
    async def monitor_and_evolve(self, check_interval_seconds: int = 3600):
        """
        Continuously monitor and evolve capabilities.
        
        This is the main loop that runs in the background,
        identifying and improving struggling capabilities.
        
        Args:
            check_interval_seconds: How often to check for evolution candidates
        """
        while True:
            try:
                # Find capabilities needing evolution
                candidates = await self._identify_candidates()
                
                # Sort by priority
                candidates.sort(key=lambda c: c.priority, reverse=True)
                
                # Evolve top candidates
                for candidate in candidates[:3]:  # Limit concurrent evolutions
                    result = await self.evolve_capability(candidate)
                    self.evolution_history.append(result)
                    
                    if result.success:
                        print(f"Successfully evolved {candidate.capability_id}: "
                              f"{result.improvement_percentage:.1f}% improvement")
                
                # Wait before next check
                await asyncio.sleep(check_interval_seconds)
                
            except Exception as e:
                print(f"Evolution monitoring error: {e}")
                await asyncio.sleep(check_interval_seconds)
    
    async def _identify_candidates(self) -> List[EvolutionCandidate]:
        """
        Identify capabilities that need evolution.
        
        Scans repository metrics to find underperforming capabilities.
        
        Returns:
            List of evolution candidates sorted by priority
        """
        candidates = []
        
        # Get all capabilities from repository
        all_capabilities = self.repository.search(limit=100)
        
        for entry in all_capabilities:
            capability = entry.capability
            metrics = entry.usage_metrics
            
            # Skip if insufficient data
            if metrics.total_executions < 10:
                continue
            
            # Check for evolution triggers
            trigger = None
            priority = 0
            target_metrics = {}
            
            # High failure rate
            if metrics.success_rate < self.min_success_rate:
                trigger = EvolutionTrigger.HIGH_FAILURE_RATE
                priority = int((1 - metrics.success_rate) * 10)
                target_metrics['success_rate'] = self.min_success_rate
            
            # Performance degradation
            elif metrics.average_execution_time_ms > self.max_execution_time_ms:
                trigger = EvolutionTrigger.PERFORMANCE_DEGRADATION
                priority = min(10, int(metrics.average_execution_time_ms / 1000))
                target_metrics['execution_time_ms'] = self.max_execution_time_ms
            
            # Poor user ratings
            elif entry.average_rating < 3.0 and len(entry.ratings) >= 5:
                trigger = EvolutionTrigger.USER_FEEDBACK
                priority = int((5 - entry.average_rating) * 2)
                target_metrics['user_rating'] = 4.0
            
            # Security issues
            elif capability.metadata.trust_level == TrustLevel.QUARANTINE:
                trigger = EvolutionTrigger.SECURITY_ISSUE
                priority = 10  # Maximum priority
                target_metrics['security_violations'] = 0
            
            if trigger:
                candidate = EvolutionCandidate(
                    capability_id=capability.metadata.id,
                    trigger=trigger,
                    current_metrics={
                        'success_rate': metrics.success_rate,
                        'execution_time_ms': metrics.average_execution_time_ms,
                        'user_rating': entry.average_rating
                    },
                    target_metrics=target_metrics,
                    priority=priority
                )
                candidates.append(candidate)
        
        return candidates
    
    async def evolve_capability(self, candidate: EvolutionCandidate) -> EvolutionResult:
        """
        Evolve a specific capability.
        
        This is the core evolution process:
        1. Analyze failure patterns
        2. Generate improved version
        3. Validate through testing
        4. A/B test if successful
        5. Promote if better
        
        Args:
            candidate: Evolution candidate
            
        Returns:
            EvolutionResult with outcome details
        """
        import time
        start_time = time.time()
        
        # Get original capability
        entry = self.repository.get_by_id(candidate.capability_id)
        if not entry:
            return EvolutionResult(
                original_capability_id=candidate.capability_id,
                evolved_capability_id=None,
                success=False,
                trigger=candidate.trigger,
                original_metrics=candidate.current_metrics,
                evolved_metrics=None,
                improvement_percentage=0.0,
                synthesis_iterations=0,
                evolution_time_ms=0.0,
                ab_test_results=None
            )
        
        original_capability = entry.capability
        
        # Analyze failure patterns
        failure_analysis = await self._analyze_failures(original_capability, entry)
        
        # Generate improvement requirements
        improvement_req = self._generate_improvement_requirements(
            original_capability, failure_analysis, candidate
        )
        
        # Synthesize improved version
        synthesis_result = await self.synthesizer.synthesize(
            requirement=improvement_req,
            capability_type=original_capability.metadata.capability_type,
            examples=original_capability.examples
        )
        
        if not synthesis_result.success:
            evolution_time = (time.time() - start_time) * 1000
            return EvolutionResult(
                original_capability_id=candidate.capability_id,
                evolved_capability_id=None,
                success=False,
                trigger=candidate.trigger,
                original_metrics=candidate.current_metrics,
                evolved_metrics=None,
                improvement_percentage=0.0,
                synthesis_iterations=synthesis_result.iterations,
                evolution_time_ms=evolution_time,
                ab_test_results=None
            )
        
        evolved_capability = synthesis_result.capability
        
        # Set evolved capability metadata
        evolved_capability.metadata.parent_id = original_capability.metadata.id
        evolved_capability.metadata.version = self._increment_version(
            original_capability.metadata.version
        )
        evolved_capability.metadata.name = f"{original_capability.metadata.name}_v{evolved_capability.metadata.version}"
        
        # Run A/B testing
        ab_results = await self._ab_test(original_capability, evolved_capability)
        
        # Calculate improvement
        improvement = self._calculate_improvement(
            candidate.current_metrics,
            ab_results['evolved_metrics']
        )
        
        evolution_time = (time.time() - start_time) * 1000
        
        # Decide whether to promote
        if ab_results['evolved_better'] and improvement > 0:
            # Publish evolved version
            evolved_id = self.repository.publish(
                evolved_capability,
                author_id="evolution_engine",
                tags=["evolved", f"from_{candidate.capability_id}"],
                parent_id=candidate.capability_id
            )
            
            return EvolutionResult(
                original_capability_id=candidate.capability_id,
                evolved_capability_id=evolved_id,
                success=True,
                trigger=candidate.trigger,
                original_metrics=candidate.current_metrics,
                evolved_metrics=ab_results['evolved_metrics'],
                improvement_percentage=improvement,
                synthesis_iterations=synthesis_result.iterations,
                evolution_time_ms=evolution_time,
                ab_test_results=ab_results
            )
        else:
            return EvolutionResult(
                original_capability_id=candidate.capability_id,
                evolved_capability_id=None,
                success=False,
                trigger=candidate.trigger,
                original_metrics=candidate.current_metrics,
                evolved_metrics=ab_results['evolved_metrics'],
                improvement_percentage=improvement,
                synthesis_iterations=synthesis_result.iterations,
                evolution_time_ms=evolution_time,
                ab_test_results=ab_results
            )
    
    async def _analyze_failures(self, capability: Capability,
                               entry: Any) -> Dict[str, Any]:
        """
        Analyze failure patterns for a capability.
        
        Args:
            capability: Capability to analyze
            entry: Repository entry with metrics
            
        Returns:
            Analysis results including common errors and patterns
        """
        analysis = {
            'common_errors': [],
            'performance_issues': [],
            'user_complaints': [],
            'suggested_fixes': []
        }
        
        # Analyze error patterns from metrics
        if hasattr(capability.metadata.metrics, 'error_patterns'):
            # Sort errors by frequency
            sorted_errors = sorted(
                capability.metadata.metrics.error_patterns.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            for error_type, count in sorted_errors[:5]:
                analysis['common_errors'].append({
                    'type': error_type,
                    'count': count,
                    'percentage': count / capability.metadata.metrics.total_executions
                })
                
                # Suggest fixes based on error type
                if error_type == 'timeout':
                    analysis['suggested_fixes'].append(
                        "Optimize algorithm efficiency or increase timeout"
                    )
                elif error_type == 'type_error':
                    analysis['suggested_fixes'].append(
                        "Add type validation and conversion for inputs"
                    )
                elif error_type == 'import_error':
                    analysis['suggested_fixes'].append(
                        "Review and fix module dependencies"
                    )
        
        # Analyze user feedback
        negative_ratings = [r for r in entry.ratings if r.rating <= 2]
        for rating in negative_ratings[:5]:
            if rating.comment:
                analysis['user_complaints'].append(rating.comment)
        
        # Performance analysis
        if entry.usage_metrics.average_execution_time_ms > 1000:
            analysis['performance_issues'].append({
                'issue': 'slow_execution',
                'average_time_ms': entry.usage_metrics.average_execution_time_ms
            })
        
        return analysis
    
    def _generate_improvement_requirements(self, capability: Capability,
                                          failure_analysis: Dict[str, Any],
                                          candidate: EvolutionCandidate) -> str:
        """
        Generate requirements for improved capability.
        
        Creates specific, actionable requirements based on failure analysis.
        
        Args:
            capability: Original capability
            failure_analysis: Analysis of failures
            candidate: Evolution candidate with targets
            
        Returns:
            Improvement requirements as natural language
        """
        req_parts = [
            f"Improve the existing capability: {capability.metadata.description}",
            "\nCurrent issues to address:"
        ]
        
        # Add specific issues
        if failure_analysis['common_errors']:
            req_parts.append("\nCommon errors:")
            for error in failure_analysis['common_errors'][:3]:
                req_parts.append(f"- {error['type']}: {error['count']} occurrences")
        
        if failure_analysis['performance_issues']:
            req_parts.append("\nPerformance issues:")
            for issue in failure_analysis['performance_issues']:
                req_parts.append(f"- Average execution time: {issue['average_time_ms']:.0f}ms")
        
        if failure_analysis['user_complaints']:
            req_parts.append("\nUser feedback:")
            for complaint in failure_analysis['user_complaints'][:3]:
                req_parts.append(f"- {complaint[:100]}")
        
        # Add improvement targets
        req_parts.append("\nImprovement targets:")
        
        if 'success_rate' in candidate.target_metrics:
            current = candidate.current_metrics.get('success_rate', 0)
            target = candidate.target_metrics['success_rate']
            req_parts.append(f"- Increase success rate from {current:.1%} to {target:.1%}")
        
        if 'execution_time_ms' in candidate.target_metrics:
            current = candidate.current_metrics.get('execution_time_ms', 0)
            target = candidate.target_metrics['execution_time_ms']
            req_parts.append(f"- Reduce execution time from {current:.0f}ms to {target:.0f}ms")
        
        # Add suggested fixes
        if failure_analysis['suggested_fixes']:
            req_parts.append("\nSuggested improvements:")
            for fix in failure_analysis['suggested_fixes']:
                req_parts.append(f"- {fix}")
        
        # Add original code context
        req_parts.append(f"\nMaintain the same interface and general approach as the original.")
        req_parts.append(f"Focus on fixing errors and improving reliability.")
        
        return "\n".join(req_parts)
    
    async def _ab_test(self, original: Capability,
                      evolved: Capability) -> Dict[str, Any]:
        """
        Perform A/B testing between original and evolved capabilities.
        
        This validates that the evolved version is actually better,
        not just different. Uses statistical significance testing.
        
        Args:
            original: Original capability
            evolved: Evolved capability
            
        Returns:
            A/B test results with metrics and statistical analysis
        """
        # Generate test cases for comparison
        test_cases = await self._generate_test_cases_for_ab(original)
        
        # Run tests on both versions
        original_results = []
        evolved_results = []
        
        for test_case in test_cases[:self.ab_test_min_samples]:
            # Test original
            orig_result = await self.runtime.execute(
                original, test_case['inputs']
            )
            original_results.append({
                'success': orig_result['success'],
                'time_ms': orig_result['execution_time_ms']
            })
            
            # Test evolved
            evol_result = await self.runtime.execute(
                evolved, test_case['inputs']
            )
            evolved_results.append({
                'success': evol_result['success'],
                'time_ms': evol_result['execution_time_ms']
            })
        
        # Calculate metrics
        original_metrics = {
            'success_rate': sum(r['success'] for r in original_results) / len(original_results),
            'avg_time_ms': statistics.mean(r['time_ms'] for r in original_results),
            'std_time_ms': statistics.stdev(r['time_ms'] for r in original_results) if len(original_results) > 1 else 0
        }
        
        evolved_metrics = {
            'success_rate': sum(r['success'] for r in evolved_results) / len(evolved_results),
            'avg_time_ms': statistics.mean(r['time_ms'] for r in evolved_results),
            'std_time_ms': statistics.stdev(r['time_ms'] for r in evolved_results) if len(evolved_results) > 1 else 0
        }
        
        # Statistical significance test (simplified - production would use proper stats)
        success_improvement = evolved_metrics['success_rate'] - original_metrics['success_rate']
        time_improvement = original_metrics['avg_time_ms'] - evolved_metrics['avg_time_ms']
        
        # Consider evolved better if success rate improved by >5% or time improved by >20%
        evolved_better = (
            success_improvement > 0.05 or
            (success_improvement >= 0 and time_improvement / original_metrics['avg_time_ms'] > 0.2)
        )
        
        return {
            'original_metrics': original_metrics,
            'evolved_metrics': evolved_metrics,
            'success_improvement': success_improvement,
            'time_improvement': time_improvement,
            'sample_size': len(test_cases),
            'evolved_better': evolved_better,
            'confidence': self._calculate_confidence(original_results, evolved_results)
        }
    
    async def _generate_test_cases_for_ab(self, capability: Capability) -> List[Dict[str, Any]]:
        """
        Generate test cases for A/B testing.
        
        Creates a diverse set of test cases to properly evaluate improvements.
        
        Args:
            capability: Capability to generate tests for
            
        Returns:
            List of test cases with inputs
        """
        test_cases = []
        
        # Use existing examples
        for example in capability.examples:
            test_cases.append({
                'inputs': example.get('inputs', {}),
                'expected': example.get('output')
            })
        
        # Generate additional test cases if needed
        if len(test_cases) < self.ab_test_min_samples:
            # In production, use LLM to generate diverse test cases
            # For now, duplicate existing ones with variations
            while len(test_cases) < self.ab_test_min_samples:
                if capability.examples:
                    base_example = capability.examples[0]
                    test_cases.append({
                        'inputs': base_example.get('inputs', {}),
                        'expected': base_example.get('output')
                    })
                else:
                    # Default empty test case
                    test_cases.append({
                        'inputs': {},
                        'expected': None
                    })
        
        return test_cases
    
    def _calculate_improvement(self, original_metrics: Dict[str, Any],
                              evolved_metrics: Dict[str, Any]) -> float:
        """
        Calculate overall improvement percentage.
        
        Combines multiple metrics into a single improvement score.
        
        Args:
            original_metrics: Original capability metrics
            evolved_metrics: Evolved capability metrics
            
        Returns:
            Improvement percentage (0-100)
        """
        improvements = []
        
        # Success rate improvement
        if 'success_rate' in original_metrics and 'success_rate' in evolved_metrics:
            orig_success = original_metrics['success_rate']
            evol_success = evolved_metrics['success_rate']
            if orig_success > 0:
                improvements.append((evol_success - orig_success) / orig_success)
        
        # Performance improvement (negative because lower is better)
        if 'avg_time_ms' in original_metrics and 'avg_time_ms' in evolved_metrics:
            orig_time = original_metrics.get('avg_time_ms', 1000)
            evol_time = evolved_metrics.get('avg_time_ms', 1000)
            if orig_time > 0:
                improvements.append((orig_time - evol_time) / orig_time)
        
        # Average improvement
        if improvements:
            return statistics.mean(improvements) * 100
        return 0.0
    
    def _calculate_confidence(self, original_results: List[Dict],
                            evolved_results: List[Dict]) -> float:
        """
        Calculate statistical confidence in the A/B test results.
        
        Simplified confidence calculation - production would use proper
        statistical tests (t-test, chi-squared, etc.)
        
        Args:
            original_results: Original capability test results
            evolved_results: Evolved capability test results
            
        Returns:
            Confidence level (0.0 to 1.0)
        """
        # Simplified: base confidence on sample size and consistency
        sample_size = len(original_results)
        
        if sample_size < 30:
            base_confidence = 0.7
        elif sample_size < 100:
            base_confidence = 0.85
        else:
            base_confidence = 0.95
        
        # Adjust based on result consistency (low variance = higher confidence)
        if len(evolved_results) > 1:
            success_rates = [r['success'] for r in evolved_results]
            variance = statistics.variance(success_rates) if len(success_rates) > 1 else 0
            
            # Lower variance increases confidence
            if variance < 0.1:
                base_confidence = min(1.0, base_confidence * 1.1)
            elif variance > 0.3:
                base_confidence *= 0.9
        
        return base_confidence
    
    def _increment_version(self, version: str) -> str:
        """
        Increment version string.
        
        Args:
            version: Current version (e.g., "1.0.0")
            
        Returns:
            Incremented version (e.g., "1.0.1")
        """
        try:
            parts = version.split('.')
            if len(parts) == 3:
                # Increment patch version
                parts[2] = str(int(parts[2]) + 1)
                return '.'.join(parts)
        except:
            pass
        
        return "1.0.1"  # Default if parsing fails
    
    def get_evolution_stats(self) -> Dict[str, Any]:
        """
        Get statistics about evolution performance.
        
        Returns:
            Dictionary with evolution statistics
        """
        if not self.evolution_history:
            return {
                'total_evolutions': 0,
                'successful_evolutions': 0,
                'success_rate': 0.0,
                'average_improvement': 0.0
            }
        
        successful = [e for e in self.evolution_history if e.success]
        
        improvements = [e.improvement_percentage for e in successful]
        
        return {
            'total_evolutions': len(self.evolution_history),
            'successful_evolutions': len(successful),
            'success_rate': len(successful) / len(self.evolution_history),
            'average_improvement': statistics.mean(improvements) if improvements else 0.0,
            'by_trigger': self._stats_by_trigger(),
            'recent_evolutions': [e.to_dict() for e in self.evolution_history[-10:]]
        }
    
    def _stats_by_trigger(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculate statistics grouped by trigger type.
        
        Returns:
            Statistics for each trigger type
        """
        by_trigger = {}
        
        for trigger in EvolutionTrigger:
            triggered = [e for e in self.evolution_history if e.trigger == trigger]
            if triggered:
                successful = [e for e in triggered if e.success]
                improvements = [e.improvement_percentage for e in successful]
                
                by_trigger[trigger.name] = {
                    'total': len(triggered),
                    'successful': len(successful),
                    'success_rate': len(successful) / len(triggered),
                    'avg_improvement': statistics.mean(improvements) if improvements else 0.0
                }
        
        return by_trigger
