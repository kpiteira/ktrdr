"""Brief translator — converts genome + config into a design brief string.

This is the genome-to-phenotype mechanism. The brief is injected into the
LLM's design prompt as a "Research Brief" section, framing the researcher's
approach to strategy design.
"""

from __future__ import annotations

from ktrdr.evolution.config import EvolutionConfig
from ktrdr.evolution.genome import Genome, TraitLevel

# Trait-level text mappings.
# Each trait level maps to a paragraph of instructions (1-3 sentences).

_NOVELTY_TEXT = {
    TraitLevel.OFF: (
        "Build on proven, systematic patterns. Use well-understood indicator "
        "combinations and vary only one parameter from what has worked before."
    ),
    TraitLevel.LOW: (
        "Prefer indicators not heavily used in recent strategies, but keep "
        "the overall architecture conservative."
    ),
    TraitLevel.HIGH: (
        "Actively seek creative, experimental approaches. Try unusual indicator "
        "combinations and unconventional parameter choices. Avoid anything that "
        "looks similar to what has been tried before."
    ),
}

_SKEPTICISM_TEXT = {
    TraitLevel.OFF: (
        "Accept results as-is. Do not over-constrain your design with "
        "conservative parameters."
    ),
    TraitLevel.LOW: (
        "Prefer simpler strategies with fewer indicators. Use conservative "
        "zigzag thresholds (0.01-0.02) and small-to-medium networks "
        "([16, 8] or [32, 16])."
    ),
    TraitLevel.HIGH: (
        "Be extremely conservative: use maximum 2 indicators, start with the "
        "smallest viable network ([8, 4]), and prefer strategies that show "
        "consistency over raw performance."
    ),
}

_MEMORY_TEXT = {
    TraitLevel.OFF: (
        "Ignore any experiment history shown below. Design as if starting "
        "completely fresh."
    ),
    TraitLevel.LOW: (
        "Consider only the most recent 2-3 experiments when designing. "
        "Focus on what worked or failed recently."
    ),
    TraitLevel.HIGH: (
        "Carefully synthesize all experiment history before designing. "
        "Explicitly reference what has and hasn't worked across all "
        "previous experiments."
    ),
}


class BriefTranslator:
    """Translates a genome + config into a design brief string."""

    def translate(self, genome: Genome, config: EvolutionConfig) -> str:
        """Convert genome traits + config into a natural language brief.

        The brief includes trait-derived personality instructions followed
        by date windows, symbol, and timeframe.
        """
        paragraphs = [
            _NOVELTY_TEXT[genome.novelty_seeking],
            _SKEPTICISM_TEXT[genome.skepticism],
            _MEMORY_TEXT[genome.memory_depth],
        ]

        # Date window section (always same format per ARCHITECTURE.md)
        tw = config.training_window
        # Use the first fitness slice as the backtest window
        bw = config.fitness_slices[0]
        date_section = (
            f"Training window: {tw.start} to {tw.end}. "
            f"Backtest window: {bw.start} to {bw.end}. "
            f"Symbol: {config.symbol}, Timeframe: {config.timeframe}."
        )

        return " ".join(paragraphs) + "\n\n" + date_section
