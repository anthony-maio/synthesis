"""
Synthesis: Test-Driven Capability Synthesis for AI Agents

A framework for enabling AI agents to dynamically create, test, and validate
new capabilities through rigorous test-driven development.

Key Features:
- TDD-based synthesis ensures generated code actually works
- Graduated trust levels provide safety through progressive validation
- Honest performance metrics (no inflated success claims)
- LLM-provider agnostic architecture
- Capability repository for sharing and reuse
- Comprehensive observability and debugging

Example usage:
    >>> from synthesis import TDDSynthesizer, CapabilityRequest, CapabilityCategory
    >>> from synthesis.llm import MockLLMProvider
    >>> 
    >>> # Create synthesizer
    >>> synthesizer = TDDSynthesizer(MockLLMProvider())
    >>> 
    >>> # Request a new capability
    >>> request = CapabilityRequest(
    ...     description="Add two numbers",
    ...     category=CapabilityCategory.COMPUTATION,
    ...     example_inputs=[{"a": 5, "b": 3}],
    ...     example_outputs=[8]
    ... )
    >>> 
    >>> # Synthesize and validate
    >>> result = await synthesizer.synthesize(request)
    >>> if result.success:
    ...     capability = result.capability
    ...     print(f"Created: {capability.name}")

Version: 0.1.0
Author: Anthony Maio & Claude
License: MIT
"""

from .core.capability import (
    Capability,
    CapabilityRequest,
    CapabilityTest,
    CapabilityCategory,
    TrustLevel,
    ExecutionMetrics
)

from .core.synthesizer import (
    TDDSynthesizer,
    SynthesisResult
)

__version__ = "0.1.0"
__author__ = "Anthony Maio & Claude"
__all__ = [
    # Core abstractions
    "Capability",
    "CapabilityRequest",
    "CapabilityTest",
    "CapabilityCategory",
    "TrustLevel",
    "ExecutionMetrics",
    
    # Synthesis engine
    "TDDSynthesizer",
    "SynthesisResult",
]
