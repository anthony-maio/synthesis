"""
Synthesis v2 - Evolution Engine for AI Model Agency
====================================================

A production-ready framework enabling AI models to create, test, share, 
and evolve their own tools autonomously.
"""

__version__ = "2.0.0"
__author__ = "Synthesis Development Team"

# Core imports
from .core import (
    Capability,
    CapabilityMetadata,
    CapabilityType,
    TrustLevel,
    SecurityProfile,
    EnhancedTDDSynthesizer,
    SecureRuntime,
    CapabilityRepository
)

# Evolution imports
from .evolution import (
    EvolutionEngine,
    EvolutionTrigger,
    EvolutionCandidate,
    EvolutionResult
)

# MCP imports
from .mcp import (
    MCPServerFactory,
    MCPServerConfig
)

__all__ = [
    # Core
    "Capability",
    "CapabilityMetadata",
    "CapabilityType",
    "TrustLevel",
    "SecurityProfile",
    "EnhancedTDDSynthesizer",
    "SecureRuntime",
    "CapabilityRepository",
    
    # Evolution
    "EvolutionEngine",
    "EvolutionTrigger",
    "EvolutionCandidate",
    "EvolutionResult",
    
    # MCP
    "MCPServerFactory",
    "MCPServerConfig",
]
