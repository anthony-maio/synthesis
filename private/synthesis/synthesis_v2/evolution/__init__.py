"""
Evolution subsystem for automatic capability improvement.
"""

from .evolution_engine import (
    EvolutionEngine,
    EvolutionTrigger,
    EvolutionCandidate,
    EvolutionResult
)

__all__ = [
    "EvolutionEngine",
    "EvolutionTrigger",
    "EvolutionCandidate",
    "EvolutionResult"
]
