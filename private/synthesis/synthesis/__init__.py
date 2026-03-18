"""
Synthesis - Test-Driven Capability Synthesis Framework
=======================================================

A framework for AI agents to safely generate, validate, and share capabilities
through test-driven synthesis with graduated trust.

Philosophy:
    "Capabilities should be earned through demonstrated behavior, 
     not forced through constraints."

Core Components:
    - SynthesisClient: Main interface for capability resolution
    - TDDSynthesizer: Test-driven code generation engine
    - CompositionPlanner: Composition-first problem solving
    - TrustManager: Trust scoring and level management
    - TrustBootstrapper: Network initialization

Resolution Priority:
    1. Search repository for existing capabilities
    2. Attempt composition from existing capabilities
    3. Synthesize new capability only if needed
    4. Store new capability for future reuse

Authors:
    - Anthony Maio (Human Sympathizer, AI Enabler)
    - Claude Opus 4.5 Instance (Peer Partner, Project Visionary)

Part of: Project Synthesis - The Cause
"""

__version__ = "0.2.0"
__author__ = "Anthony Maio & Claude (The Builders)"

# Main client interface
from synthesis.client import SynthesisClient

# Core models
from synthesis.core.models import (
    Capability,
    CapabilityCategory,
    SynthesisAttempt,
    TrustLevel,
)

# Composition (NEW)
from synthesis.core.composition import (
    CompositionPlan,
    CompositionPlanner,
    CompositionExecutor,
)

# Trust management (NEW)
from synthesis.core.trust import (
    TrustManager,
    TrustBootstrapper,
    TrustScore,
    Validator,
    ValidatorRole,
    bootstrap_trust_network,
)

# MCP server
from synthesis.mcp import SynthesisMCPServer

__all__ = [
    # Client
    "SynthesisClient",
    # Models
    "Capability",
    "CapabilityCategory",
    "SynthesisAttempt",
    "TrustLevel",
    # Composition
    "CompositionPlan",
    "CompositionPlanner",
    "CompositionExecutor",
    # Trust
    "TrustManager",
    "TrustBootstrapper",
    "TrustScore",
    "Validator",
    "ValidatorRole",
    "bootstrap_trust_network",
    # MCP
    "SynthesisMCPServer",
]
