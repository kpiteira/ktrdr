"""Agent API Pydantic models."""

from typing import Optional

from pydantic import BaseModel, field_validator, model_validator


class AgentTriggerRequest(BaseModel):
    """Request model for POST /agent/trigger.

    Allows specifying model at trigger time for easy switching between
    opus/sonnet/haiku without restarting Docker.
    """

    model: Optional[str] = None
    """Model to use: 'opus', 'sonnet', 'haiku', or full model ID.
    If None, uses AGENT_MODEL env var or defaults to opus."""

    brief: Optional[str] = None
    """Natural language guidance for the strategy designer.
    Injected into the agent's prompt to guide design decisions.
    Example: 'Design a simple RSI strategy for EURUSD 1h only.'"""

    bypass_gates: bool = False
    """If True, skip quality gates between phases (for testing)."""

    strategy: Optional[str] = None
    """Name of an existing v3 strategy to train directly (skips design phase).
    Mutually exclusive with 'brief'. Example: 'v3_minimal' or 'momentum_rsi_v2'."""

    @model_validator(mode="after")
    def check_brief_strategy_mutual_exclusivity(self) -> "AgentTriggerRequest":
        """Ensure brief and strategy are mutually exclusive."""
        if self.brief is not None and self.strategy is not None:
            raise ValueError(
                "Cannot specify both 'brief' and 'strategy'. "
                "Use 'brief' to design a new strategy, or 'strategy' to train an existing one."
            )
        return self

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: Optional[str]) -> Optional[str]:
        """Validate model is a known alias or model ID."""
        if v is None:
            return None
        # Import here to avoid circular dependency
        from ktrdr.agents.invoker import MODEL_ALIASES, VALID_MODELS

        v_lower = v.lower()
        if v_lower in MODEL_ALIASES or v in VALID_MODELS:
            return v
        valid_options = list(MODEL_ALIASES.keys()) + list(VALID_MODELS.keys())
        raise ValueError(
            f"Invalid model '{v}'. Valid options: {', '.join(sorted(set(valid_options)))}"
        )


class LastCycleInfo(BaseModel):
    """Information about the last completed research cycle."""

    operation_id: str
    outcome: str
    strategy_name: Optional[str] = None
    completed_at: Optional[str] = None


class ActiveResearchInfo(BaseModel):
    """Information about an active research operation."""

    operation_id: str
    phase: str
    strategy_name: Optional[str] = None
    duration_seconds: int
    child_operation_id: Optional[str] = None


class WorkerUtilization(BaseModel):
    """Worker utilization counts."""

    busy: int
    total: int


class WorkersStatus(BaseModel):
    """Worker status by type."""

    training: WorkerUtilization
    backtesting: WorkerUtilization


class BudgetStatus(BaseModel):
    """Budget tracking status."""

    remaining: float
    daily_limit: float


class CapacityStatus(BaseModel):
    """Concurrency capacity status."""

    active: int
    limit: int


class AgentStatusResponse(BaseModel):
    """Response model for GET /agent/status.

    Returns multi-research status with worker utilization, budget, and capacity.
    """

    status: str  # "active" or "idle"
    active_researches: list[ActiveResearchInfo] = []
    last_cycle: Optional[LastCycleInfo] = None
    workers: Optional[WorkersStatus] = None
    budget: Optional[BudgetStatus] = None
    capacity: Optional[CapacityStatus] = None


class AgentTriggerResponse(BaseModel):
    """Response model for POST /agent/trigger."""

    triggered: bool
    operation_id: Optional[str] = None
    reason: Optional[str] = None
    message: Optional[str] = None
