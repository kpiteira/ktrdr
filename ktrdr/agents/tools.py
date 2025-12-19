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
    {
        "name": "start_training",
        "description": (
            "Start training a strategy model. This initiates a training operation "
            "that runs in the background. Returns an operation_id that can be used "
            "to track progress. The training will use distributed workers if available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "strategy_name": {
                    "type": "string",
                    "description": (
                        "Name of the strategy to train (must exist in strategies/ folder). "
                        "This should match a previously saved strategy configuration."
                    ),
                },
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of symbols to train on (e.g., ['EURUSD', 'GBPUSD']). "
                        "If not provided, uses symbols from strategy config."
                    ),
                },
                "timeframes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of timeframes to use (e.g., ['1h', '4h']). "
                        "If not provided, uses timeframes from strategy config."
                    ),
                },
                "start_date": {
                    "type": "string",
                    "description": (
                        "Training data start date in YYYY-MM-DD format. "
                        "If not provided, uses default from strategy config."
                    ),
                },
                "end_date": {
                    "type": "string",
                    "description": (
                        "Training data end date in YYYY-MM-DD format. "
                        "If not provided, uses default from strategy config."
                    ),
                },
            },
            "required": ["strategy_name"],
        },
    },
    {
        "name": "start_backtest",
        "description": (
            "Start backtesting a trained model. This initiates a backtest operation "
            "that runs in the background. Returns an operation_id that can be used "
            "to track progress. The backtest will evaluate the strategy's performance "
            "on historical data using the specified trained model."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "strategy_name": {
                    "type": "string",
                    "description": (
                        "Name of the strategy to backtest (must exist in strategies/ folder). "
                        "This should match the strategy used during training."
                    ),
                },
                "model_path": {
                    "type": "string",
                    "description": (
                        "Path to the trained model file (e.g., 'models/momentum_v1/1d_v1/model.pt'). "
                        "This should be the model output from a successful training run."
                    ),
                },
                "symbol": {
                    "type": "string",
                    "description": (
                        "Symbol to backtest on (e.g., 'EURUSD', 'AAPL'). "
                        "If not provided, uses symbol from strategy config."
                    ),
                },
                "timeframe": {
                    "type": "string",
                    "description": (
                        "Timeframe to use (e.g., '1h', '4h', '1d'). "
                        "If not provided, uses timeframe from strategy config."
                    ),
                },
                "start_date": {
                    "type": "string",
                    "description": (
                        "Backtest start date in YYYY-MM-DD format. "
                        "Should typically be different from training period for out-of-sample testing."
                    ),
                },
                "end_date": {
                    "type": "string",
                    "description": (
                        "Backtest end date in YYYY-MM-DD format. "
                        "If not provided, uses current date."
                    ),
                },
                "initial_capital": {
                    "type": "number",
                    "description": (
                        "Initial capital for the backtest (default: 100000). "
                        "This is the starting account balance for simulation."
                    ),
                    "default": 100000,
                },
            },
            "required": ["strategy_name", "model_path"],
        },
    },
    {
        "name": "save_assessment",
        "description": (
            "Save your assessment of the strategy to disk. Call this after analyzing "
            "the training and backtest results. The assessment will be saved as JSON "
            "in the strategy's directory."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "verdict": {
                    "type": "string",
                    "enum": ["promising", "mediocre", "poor"],
                    "description": "Overall verdict on the strategy's potential.",
                },
                "strengths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of strategy strengths (2-4 items).",
                },
                "weaknesses": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of strategy weaknesses (2-4 items).",
                },
                "suggestions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of improvement suggestions (2-4 items).",
                },
            },
            "required": ["verdict", "strengths", "weaknesses", "suggestions"],
        },
    },
]


# Design phase tools - reduced subset for cost optimization (Task 8.2)
# Discovery tools (get_available_indicators, get_available_symbols, get_recent_strategies)
# are excluded because context is now pre-populated in the prompt (Task 8.1)
DESIGN_PHASE_TOOLS: list[dict[str, Any]] = [
    tool
    for tool in AGENT_TOOLS
    if tool["name"] in ["validate_strategy_config", "save_strategy_config"]
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
