"""core/agent/pipeline — UnderstandingStrategy seam and default implementation."""

from core.agent.pipeline.strategy import (
    DecomposedStrategy,
    FastThenDecomposeStrategy,
    NativeToolCallStrategy,
    StrategyResult,
    UnderstandingStrategy,
)
from core.agent.pipeline.assembler import (
    AssembleResult,
    Unresolved,
    assemble,
)

__all__ = [
    "DecomposedStrategy",
    "FastThenDecomposeStrategy",
    "NativeToolCallStrategy",
    "StrategyResult",
    "UnderstandingStrategy",
    "AssembleResult",
    "Unresolved",
    "assemble",
]
