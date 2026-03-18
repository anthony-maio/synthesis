"""
Synthesis v2 - Evolution Engine for AI Model Agency
====================================================

A production-ready framework for AI models to create, test, and evolve their own tools.
This implementation addresses all critical feedback from the initial design:
- Realistic success rate expectations based on empirical research
- Proper code isolation and sandboxing
- Secure dependency management
- Graduated trust model with real metrics

Author: Developed collaboratively with human partner
License: MIT
"""

__version__ = "2.0.0"

from .capability import Capability, CapabilityMetadata, TrustLevel
from .synthesizer import EnhancedTDDSynthesizer
from .runtime import SecureRuntime
from .repository import CapabilityRepository

__all__ = [
    "Capability",
    "CapabilityMetadata", 
    "TrustLevel",
    "EnhancedTDDSynthesizer",
    "SecureRuntime",
    "CapabilityRepository"
]
