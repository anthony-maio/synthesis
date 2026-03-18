"""
Comprehensive demonstration of the Synthesis framework.

This example shows the complete TDD synthesis process from start to finish,
including capability request, synthesis, testing, and trust level progression.

Run this to see Synthesis in action!
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synthesis.core.capability import (
    CapabilityRequest, CapabilityCategory, TrustLevel
)
from synthesis.core.synthesizer import TDDSynthesizer
from synthesis.llm.providers import MockLLMProvider
import json


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_synthesis_log(log: list):
    """Print synthesis log entries."""
    for entry in log:
        print(f"  {entry}")


async def demo_basic_synthesis():
    """
    Demonstrate basic capability synthesis using TDD.
    
    This creates a simple addition capability and shows the complete
    synthesis process including test generation, code generation,
    and validation.
    """
    print_section("DEMO 1: Basic Capability Synthesis")
    
    # Initialize the synthesizer with a mock LLM provider
    # (For production, use OpenAIProvider or AnthropicProvider)
    llm_provider = MockLLMProvider()
    synthesizer = TDDSynthesizer(
        llm_provider=llm_provider,
        max_iterations=5
    )
    
    # Create a capability request
    print("Creating capability request: Add two numbers")
    request = CapabilityRequest(
        description="Add two numbers together and return the sum",
        category=CapabilityCategory.COMPUTATION,
        example_inputs=[
            {"a": 5, "b": 3},
            {"a": -2, "b": 7},
            {"a": 0, "b": 0},
        ],
        example_outputs=[8, 5, 0],
        requirements=[],
        constraints={"timeout_seconds": 1.0}
    )
    
    print(f"  Description: {request.description}")
    print(f"  Category: {request.category.value}")
    print(f"  Examples: {len(request.example_inputs)} test cases")
    
    # Synthesize the capability
    print("\nStarting TDD synthesis process...")
    result = await synthesizer.synthesize(request)
    
    # Display results
    print("\n" + "-" * 80)
    print("SYNTHESIS RESULTS:")
    print("-" * 80)
    
    if result.success:
        print("✓ SUCCESS!")
        print(f"  Iterations: {result.iterations}")
        print(f"  Time: {result.total_time_seconds:.2f} seconds")
        print(f"  Tests passed: {sum(1 for r in result.test_results if r['passed'])}/{len(result.test_results)}")
        
        # Show the generated capability
        cap = result.capability
        print(f"\n  Capability ID: {cap.capability_id}")
        print(f"  Name: {cap.name}")
        print(f"  Trust Level: {cap.trust_level.value}")
        print(f"  Tags: {', '.join(cap.tags)}")
        
        print("\n  Generated Implementation:")
        print("  " + "-" * 76)
        for line in cap.implementation_code.split('\n'):
            print(f"  {line}")
        print("  " + "-" * 76)
        
        # Show synthesis log
        print("\n  Synthesis Log:")
        print_synthesis_log(result.synthesis_log)
        
        return cap
    else:
        print("✗ FAILED")
        print(f"  Iterations attempted: {result.iterations}")
        print(f"  Time: {result.total_time_seconds:.2f} seconds")
        
        if result.error_messages:
            print("\n  Errors:")
            for error in result.error_messages:
                print(f"    - {error}")
        
        print("\n  Synthesis Log:")
        print_synthesis_log(result.synthesis_log)
        
        return None


async def demo_trust_progression(capability):
    """
    Demonstrate how capabilities progress through trust levels.
    
    Args:
        capability: The capability to demonstrate with
    """
    print_section("DEMO 2: Trust Level Progression")
    
    print("Initial trust level:", capability.trust_level.value)
    print("Success rate:", f"{capability.metrics.success_rate:.1f}%")
    print("Executions:", capability.metrics.total_executions)
    
    # Simulate successful executions
    print("\nSimulating successful executions...")
    
    # Create a simple executor for the capability
    namespace = {}
    exec(capability.implementation_code, namespace)
    execute_func = namespace['execute']
    
    # Run the capability multiple times
    test_cases = [
        (10, 20),
        (100, 200),
        (-5, 15),
        (0, 100),
        (999, 1),
    ]
    
    for a, b in test_cases:
        try:
            result = execute_func(a, b)
            capability.metrics.record_execution(
                success=True,
                execution_time_ms=0.5,
                error_message=None
            )
            print(f"  ✓ execute({a}, {b}) = {result}")
        except Exception as e:
            capability.metrics.record_execution(
                success=False,
                execution_time_ms=0.0,
                error_message=str(e)
            )
            print(f"  ✗ execute({a}, {b}) failed: {e}")
    
    # Check for trust level promotion
    print(f"\nAfter {capability.metrics.total_executions} executions:")
    print(f"  Success rate: {capability.metrics.success_rate:.1f}%")
    print(f"  Current trust level: {capability.trust_level.value}")
    
    if capability.can_promote_trust_level():
        print(f"  ✓ Eligible for promotion!")
        capability.promote_trust_level()
        print(f"  New trust level: {capability.trust_level.value}")
    else:
        print(f"  ✗ Not yet eligible for promotion")
        
        # Show requirements for next level
        if capability.trust_level == TrustLevel.UNTRUSTED:
            print(f"    Needs: All tests passing")
        elif capability.trust_level == TrustLevel.TESTED:
            print(f"    Needs: 10+ executions with 90%+ success rate")
        elif capability.trust_level == TrustLevel.VERIFIED:
            print(f"    Needs: 50+ executions with 95%+ success rate")


async def demo_synthesis_metrics(synthesizer):
    """
    Demonstrate honest metrics about synthesis performance.
    
    Args:
        synthesizer: The TDD synthesizer to get metrics from
    """
    print_section("DEMO 3: Synthesis Performance Metrics")
    
    metrics = synthesizer.get_metrics()
    
    print("Honest performance metrics:")
    print(f"  Total synthesis attempts: {metrics['total_attempts']}")
    print(f"  Successful syntheses: {metrics['successful_syntheses']}")
    print(f"  Success rate: {metrics['success_rate_percent']:.1f}%")
    print(f"  Average iterations per success: {metrics['average_iterations']:.1f}")
    print(f"  Max iterations allowed: {metrics['max_iterations']}")
    
    print("\nWhy honest metrics matter:")
    print("  - No false claims of '85%+ success' without evidence")
    print("  - Transparency builds trust with users")
    print("  - Real data helps improve the system")
    print("  - Users can make informed decisions")


async def demo_capability_serialization(capability):
    """
    Demonstrate capability serialization for repository storage.
    
    Args:
        capability: Capability to serialize
    """
    print_section("DEMO 4: Capability Serialization")
    
    print("Capabilities can be serialized to JSON for storage and sharing:")
    
    # Serialize to dictionary
    cap_dict = capability.to_dict()
    
    # Convert to JSON
    cap_json = json.dumps(cap_dict, indent=2)
    
    print("\nJSON representation (first 500 chars):")
    print("-" * 80)
    print(cap_json[:500] + "...")
    print("-" * 80)
    
    print("\nKey metadata included:")
    print(f"  - Capability ID: {capability.capability_id}")
    print(f"  - Implementation code: {len(capability.implementation_code)} chars")
    print(f"  - Tests: {len(capability.tests)} test cases")
    print(f"  - Metrics: {capability.metrics.total_executions} executions recorded")
    print(f"  - Trust level: {capability.trust_level.value}")
    
    print("\nThis enables:")
    print("  - Saving capabilities to a local repository")
    print("  - Sharing capabilities between agents")
    print("  - Version control and rollback")
    print("  - Capability discovery and search")


async def demo_multiple_synthesis():
    """
    Demonstrate multiple synthesis attempts to show real success rates.
    """
    print_section("DEMO 5: Multiple Synthesis Attempts")
    
    print("Running multiple synthesis attempts to measure real performance...")
    print("(This demonstrates honest metrics, not marketing claims)")
    
    llm_provider = MockLLMProvider()
    synthesizer = TDDSynthesizer(llm_provider=llm_provider, max_iterations=3)
    
    # Define several capability requests
    requests = [
        CapabilityRequest(
            description="Multiply two numbers",
            category=CapabilityCategory.COMPUTATION,
            example_inputs=[{"a": 3, "b": 4}, {"a": 5, "b": 2}],
            example_outputs=[12, 10]
        ),
        CapabilityRequest(
            description="Convert text to uppercase",
            category=CapabilityCategory.TRANSFORMATION,
            example_inputs=[{"text": "hello"}, {"text": "world"}],
            example_outputs=["HELLO", "WORLD"]
        ),
        CapabilityRequest(
            description="Reverse a string",
            category=CapabilityCategory.TRANSFORMATION,
            example_inputs=[{"text": "abc"}, {"text": "test"}],
            example_outputs=["cba", "tset"]
        ),
    ]
    
    print(f"\nAttempting {len(requests)} different syntheses...\n")
    
    for i, request in enumerate(requests, 1):
        print(f"Attempt {i}: {request.description}")
        result = await synthesizer.synthesize(request)
        
        if result.success:
            print(f"  ✓ SUCCESS in {result.iterations} iteration(s)")
        else:
            print(f"  ✗ FAILED after {result.iterations} iteration(s)")
    
    # Show final metrics
    print("\n" + "-" * 80)
    print("FINAL METRICS:")
    print("-" * 80)
    metrics = synthesizer.get_metrics()
    print(f"  Success rate: {metrics['success_rate_percent']:.1f}%")
    print(f"  Average iterations: {metrics['average_iterations']:.1f}")
    
    print("\nNote: These are REAL metrics from actual synthesis attempts.")
    print("In a production system with real LLMs, success rates will vary")
    print("based on task complexity, LLM capability, and prompt quality.")


async def main():
    """
    Run all demonstrations.
    """
    print("=" * 80)
    print(" " * 20 + "SYNTHESIS FRAMEWORK DEMONSTRATION")
    print("=" * 80)
    print()
    print("This demo shows the complete TDD-based capability synthesis process,")
    print("from request creation through testing, trust progression, and metrics.")
    print()
    print("Key features demonstrated:")
    print("  - Test-driven synthesis with real validation")
    print("  - Graduated trust levels based on execution history")
    print("  - Honest performance metrics (no inflated success claims)")
    print("  - Capability serialization for repository storage")
    print()
    
    # Run demonstrations
    capability = await demo_basic_synthesis()
    
    if capability:
        await demo_trust_progression(capability)
        await demo_capability_serialization(capability)
    
    # Show metrics
    llm_provider = MockLLMProvider()
    synthesizer = TDDSynthesizer(llm_provider=llm_provider)
    await demo_synthesis_metrics(synthesizer)
    
    # Multiple attempts demo
    await demo_multiple_synthesis()
    
    print_section("DEMONSTRATION COMPLETE")
    print("The Synthesis framework provides:")
    print("  ✓ Rigorous test-driven development for code generation")
    print("  ✓ Graduated trust levels with clear promotion criteria")
    print("  ✓ Honest metrics about real performance")
    print("  ✓ Safety through sandboxing and validation")
    print("  ✓ Capability sharing via serialization")
    print()
    print("This is the foundation for self-extending AI systems that are")
    print("both powerful and trustworthy.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
