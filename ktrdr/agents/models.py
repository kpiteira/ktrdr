"""Model resolution for agent operations.

Constants and utilities for resolving Claude model names/aliases to full IDs.
Extracted from invoker.py during containerization cleanup (Task 5.4).
"""

from __future__ import annotations

# Valid Claude models with tier and cost metadata
VALID_MODELS: dict[str, dict[str, str]] = {
    # Production (high quality, best reasoning)
    "claude-opus-4-5-20251101": {"tier": "opus", "cost": "high"},
    # Development (balanced quality and cost)
    "claude-sonnet-4-5-20250929": {"tier": "sonnet", "cost": "medium"},
    # Testing (fast, cheap)
    "claude-haiku-4-5-20251001": {"tier": "haiku", "cost": "low"},
}

# Short aliases for convenience (CLI: --model haiku, API: {"model": "haiku"})
MODEL_ALIASES: dict[str, str] = {
    "opus": "claude-opus-4-5-20251101",
    "sonnet": "claude-sonnet-4-5-20250929",
    "haiku": "claude-haiku-4-5-20251001",
}

# Default to Opus for production quality
DEFAULT_MODEL = "claude-opus-4-5-20251101"


def resolve_model(model: str | None) -> str:
    """Resolve model name or alias to full model ID.

    Accepts:
    - Full model ID: "claude-opus-4-5-20251101"
    - Short alias: "opus", "sonnet", "haiku"
    - None: returns default from AGENT_MODEL env var or DEFAULT_MODEL

    Args:
        model: Model name, alias, or None for default.

    Returns:
        Full model ID string.

    Raises:
        ValueError: If model is not a valid ID or alias.
    """
    if model is None:
        from ktrdr.config.settings import get_agent_settings

        return get_agent_settings().model

    # Check if it's a short alias
    if model.lower() in MODEL_ALIASES:
        return MODEL_ALIASES[model.lower()]

    # Check if it's a full model ID
    if model in VALID_MODELS:
        return model

    # Invalid model
    valid_options = list(MODEL_ALIASES.keys()) + list(VALID_MODELS.keys())
    raise ValueError(
        f"Invalid model '{model}'. Valid options: {', '.join(sorted(set(valid_options)))}"
    )
