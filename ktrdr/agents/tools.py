"""
Agent tool schema definitions for Anthropic API.

This module defines the tool schemas that are passed to the Anthropic API
for function calling. These schemas follow the Anthropic tool format:
https://docs.anthropic.com/en/docs/tool-use

The tools defined here are:
- save_strategy_config: Save a validated strategy to disk
- get_available_indicators: Get list of available technical indicators
- get_available_symbols: Get list of available trading symbols
- get_recent_strategies: Get recently designed strategies for context

These replace the MCP tools for the agent - tools execute in-process
rather than via MCP protocol.
"""

from typing import Any

# Tool schema definitions for Anthropic API
AGENT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "validate_strategy_config",
        "description": (
            "Validate a strategy configuration before saving. Returns validation "
            "results including any errors, warnings, and suggestions. Use this to "
            "check your strategy config is valid BEFORE calling save_strategy_config. "
            "This helps catch issues early and reduces save failures."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config": {
                    "type": "object",
                    "description": (
                        "Complete strategy configuration dictionary to validate. "
                        "Must include: scope, training_data, deployment, indicators, "
                        "fuzzy_sets, model, decisions, and training sections."
                    ),
                },
            },
            "required": ["config"],
        },
    },
    {
        "name": "save_strategy_config",
        "description": (
            "Save a strategy configuration to the strategies directory. "
            "Validates the strategy against KTRDR requirements before saving. "
            "Use this after designing a complete strategy configuration."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": (
                        "Strategy name (file saved as strategies/{name}.yaml). "
                        "Use lowercase with underscores, e.g., 'momentum_rsi_v1'."
                    ),
                },
                "config": {
                    "type": "object",
                    "description": (
                        "Complete strategy configuration dictionary. Must include: "
                        "scope, training_data, deployment, indicators, fuzzy_sets, "
                        "model, decisions, and training sections."
                    ),
                },
                "description": {
                    "type": "string",
                    "description": (
                        "Human-readable description explaining the strategy's "
                        "purpose and approach."
                    ),
                },
            },
            "required": ["name", "config", "description"],
        },
    },
    {
        "name": "get_available_indicators",
        "description": (
            "Get list of available technical indicators with their parameters. "
            "Returns indicator names, categories, descriptions, and configurable "
            "parameters with their types and default values. Use this to see "
            "what indicators can be used in strategy configurations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_available_symbols",
        "description": (
            "Get list of available trading symbols with their timeframes and "
            "data availability. Returns symbols like EURUSD, AAPL, etc., with "
            "available timeframes (1m, 5m, 1h, 1d) and data status. Use this "
            "to see what symbols can be used for training and backtesting."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_recent_strategies",
        "description": (
            "Get the N most recent strategies designed by the agent. "
            "Returns strategy names, model types, indicators used, outcomes, "
            "and creation dates. Use this to avoid repeating similar strategies "
            "and to understand what has been tried before."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {
                    "type": "integer",
                    "description": (
                        "Number of recent strategies to return (default 5, max 20)."
                    ),
                    "default": 5,
                },
            },
        },
    },
]


def get_tool_by_name(name: str) -> dict[str, Any] | None:
    """Get a tool definition by name.

    Args:
        name: The tool name to look up.

    Returns:
        Tool definition dict, or None if not found.
    """
    for tool in AGENT_TOOLS:
        if tool["name"] == name:
            return tool
    return None


def get_tool_names() -> list[str]:
    """Get list of all tool names.

    Returns:
        List of tool name strings.
    """
    return [tool["name"] for tool in AGENT_TOOLS]
