"""Prometheus metrics for agent research cycles.

This module defines custom business metrics for agent research cycle visibility.

Metrics:
- agent_cycles_total: Total research cycles by outcome
- agent_cycle_duration_seconds: Research cycle duration distribution
- agent_phase_duration_seconds: Phase duration within cycles
- agent_gate_results_total: Gate evaluation results
- agent_tokens_total: Token usage by phase
- agent_budget_spend_total: Total budget spent
"""

import logging

from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)


# Histogram buckets for cycle duration (in seconds)
# Research cycles typically take 5-60 minutes
CYCLE_DURATION_BUCKETS = [60, 300, 600, 900, 1200, 1800, 3600]

# Histogram buckets for phase duration (in seconds)
# Individual phases: design ~30s, training ~10min, backtest ~5min, assess ~30s
PHASE_DURATION_BUCKETS = [10, 30, 60, 120, 300, 600]


# Cycle metrics
agent_cycles_total = Counter(
    "agent_cycles_total",
    "Total research cycles",
    ["outcome"],  # completed, failed, cancelled
)

agent_cycle_duration_seconds = Histogram(
    "agent_cycle_duration_seconds",
    "Research cycle duration",
    buckets=CYCLE_DURATION_BUCKETS,
)

# Phase metrics
agent_phase_duration_seconds = Histogram(
    "agent_phase_duration_seconds",
    "Phase duration within cycle",
    ["phase"],  # designing, training, backtesting, assessing
    buckets=PHASE_DURATION_BUCKETS,
)

# Gate metrics
agent_gate_results_total = Counter(
    "agent_gate_results_total",
    "Gate evaluation results",
    ["gate", "result"],  # gate: training/backtest, result: pass/fail
)

# Token metrics
agent_tokens_total = Counter(
    "agent_tokens_total",
    "Token usage by phase",
    ["phase"],  # design, assessment
)

# Budget metrics
agent_budget_spend_total = Counter(
    "agent_budget_spend_total",
    "Total budget spent (dollars)",
)


def record_cycle_outcome(outcome: str) -> None:
    """Record cycle outcome.

    Args:
        outcome: Cycle outcome (completed, failed, cancelled)
    """
    agent_cycles_total.labels(outcome=outcome).inc()
    logger.debug(f"Recorded cycle outcome: {outcome}")


def record_cycle_duration(duration_seconds: float) -> None:
    """Record cycle duration.

    Args:
        duration_seconds: Duration in seconds
    """
    agent_cycle_duration_seconds.observe(duration_seconds)
    logger.debug(f"Recorded cycle duration: {duration_seconds:.2f}s")


def record_phase_duration(phase: str, duration_seconds: float) -> None:
    """Record phase duration.

    Args:
        phase: Phase name (designing, training, backtesting, assessing)
        duration_seconds: Duration in seconds
    """
    agent_phase_duration_seconds.labels(phase=phase).observe(duration_seconds)
    logger.debug(f"Recorded phase duration: {phase}={duration_seconds:.2f}s")


def record_gate_result(gate: str, passed: bool) -> None:
    """Record gate result.

    Args:
        gate: Gate name (training, backtest)
        passed: Whether the gate passed
    """
    result = "pass" if passed else "fail"
    agent_gate_results_total.labels(gate=gate, result=result).inc()
    logger.debug(f"Recorded gate result: {gate}={result}")


def record_tokens(phase: str, count: int) -> None:
    """Record token usage.

    Args:
        phase: Phase name (design, assessment)
        count: Number of tokens used
    """
    agent_tokens_total.labels(phase=phase).inc(count)
    logger.debug(f"Recorded tokens: {phase}={count}")


def record_budget_spend(amount: float) -> None:
    """Record budget spend.

    Args:
        amount: Amount spent in dollars
    """
    agent_budget_spend_total.inc(amount)
    logger.debug(f"Recorded budget spend: ${amount:.4f}")
