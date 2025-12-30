"""Tests for compact prompt formatting.

Task 8.1: Verify compact formatting reduces token usage while preserving information.

Tests cover:
- Compact indicator format produces valid string
- Compact symbol format includes timeframes
- Design prompt includes context data (indicators, symbols, recent strategies)
- Format is human-readable but token-efficient
"""

from ktrdr.agents.prompts import (
    PromptContext,
    TriggerReason,
    format_indicators_compact,
    format_symbols_compact,
    get_strategy_designer_prompt,
)


class TestCompactIndicatorFormat:
    """Tests for format_indicators_compact function."""

    def test_produces_valid_string(self):
        """Compact indicator format produces a valid string."""
        indicators = [
            {
                "name": "RSI",
                "type": "momentum",
                "parameters": [
                    {"name": "period", "default": 14},
                    {"name": "source", "default": "close"},
                ],
            },
            {
                "name": "MACD",
                "type": "trend",
                "parameters": [
                    {"name": "fast", "default": 12},
                    {"name": "slow", "default": 26},
                    {"name": "signal", "default": 9},
                ],
            },
        ]

        result = format_indicators_compact(indicators)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "RSI" in result
        assert "MACD" in result

    def test_includes_parameters_in_compact_format(self):
        """Parameters are included in compact format (name:default)."""
        indicators = [
            {
                "name": "RSI",
                "type": "momentum",
                "parameters": [
                    {"name": "period", "default": 14},
                ],
            },
        ]

        result = format_indicators_compact(indicators)

        # Should have compact parameter format like "period:14"
        assert "period:14" in result

    def test_includes_indicator_type(self):
        """Indicator type is included."""
        indicators = [
            {
                "name": "RSI",
                "type": "momentum",
                "parameters": [],
            },
        ]

        result = format_indicators_compact(indicators)

        assert "momentum" in result

    def test_handles_empty_list(self):
        """Returns appropriate string for empty list."""
        result = format_indicators_compact([])

        assert isinstance(result, str)
        # Should indicate no indicators available
        assert "no" in result.lower() or len(result) == 0

    def test_handles_missing_fields(self):
        """Handles indicators with missing optional fields gracefully."""
        indicators = [
            {"name": "SMA"},  # No type, no parameters
        ]

        result = format_indicators_compact(indicators)

        assert "SMA" in result
        # Should not crash

    def test_compact_format_is_shorter_than_verbose(self):
        """Compact format uses fewer tokens than verbose JSON format."""
        indicators = [
            {
                "name": "RSI",
                "type": "momentum",
                "description": "Relative Strength Index measures momentum",
                "parameters": [
                    {"name": "period", "default": 14, "min": 2, "max": 100},
                    {
                        "name": "source",
                        "default": "close",
                        "options": ["open", "high", "low", "close"],
                    },
                ],
            },
        ]

        compact = format_indicators_compact(indicators)
        import json

        verbose = json.dumps(indicators, indent=2)

        # Compact should be significantly shorter
        assert len(compact) < len(verbose) * 0.5


class TestCompactSymbolFormat:
    """Tests for format_symbols_compact function."""

    def test_produces_valid_string(self):
        """Compact symbol format produces a valid string."""
        symbols = [
            {
                "symbol": "AAPL",
                "timeframes": ["1m", "5m", "15m", "1h", "4h", "1d"],
                "start_date": "2020-01-01",
                "end_date": "2024-12-01",
            },
        ]

        result = format_symbols_compact(symbols)

        assert isinstance(result, str)
        assert "AAPL" in result

    def test_includes_timeframes(self):
        """Timeframes are included in the format."""
        symbols = [
            {
                "symbol": "AAPL",
                "timeframes": ["1h", "4h", "1d"],
                "start_date": "2020-01-01",
                "end_date": "2024-12-01",
            },
        ]

        result = format_symbols_compact(symbols)

        # Should contain timeframes
        assert "1h" in result
        assert "4h" in result
        assert "1d" in result

    def test_includes_date_range(self):
        """Date range is included."""
        symbols = [
            {
                "symbol": "EURUSD",
                "timeframes": ["1d"],
                "start_date": "2015-01-01",
                "end_date": "2024-12-01",
            },
        ]

        result = format_symbols_compact(symbols)

        assert "2015-01-01" in result
        assert "2024-12-01" in result

    def test_handles_empty_list(self):
        """Returns appropriate string for empty list."""
        result = format_symbols_compact([])

        assert isinstance(result, str)

    def test_handles_missing_fields(self):
        """Handles symbols with missing optional fields gracefully."""
        symbols = [
            {"symbol": "BTC"},  # No timeframes, no dates
        ]

        result = format_symbols_compact(symbols)

        assert "BTC" in result

    def test_compact_format_uses_concise_notation(self):
        """Format uses concise notation (comma-separated timeframes)."""
        symbols = [
            {
                "symbol": "AAPL",
                "timeframes": ["1m", "5m", "1h"],
                "start_date": "2020-01-01",
                "end_date": "2024-12-01",
            },
        ]

        result = format_symbols_compact(symbols)

        # Should have comma-separated timeframes like "1m,5m,1h"
        assert "1m,5m,1h" in result or "1m, 5m, 1h" in result


class TestDesignPromptIncludesContext:
    """Tests that design prompt includes all context data."""

    def test_prompt_includes_indicators(self):
        """Design prompt includes available indicators."""
        indicators = [
            {"name": "RSI", "type": "momentum", "parameters": []},
            {"name": "MACD", "type": "trend", "parameters": []},
        ]

        prompt = get_strategy_designer_prompt(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            operation_id="op_test_123",
            phase="designing",
            available_indicators=indicators,
        )

        user_prompt = prompt["user"]
        assert "RSI" in user_prompt
        assert "MACD" in user_prompt

    def test_prompt_includes_symbols_with_timeframes(self):
        """Design prompt includes available symbols with their timeframes."""
        symbols = [
            {
                "symbol": "AAPL",
                "timeframes": ["1h", "4h", "1d"],
                "date_range": {"start": "2020-01-01", "end": "2024-12-01"},
            },
        ]

        prompt = get_strategy_designer_prompt(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            operation_id="op_test_123",
            phase="designing",
            available_symbols=symbols,
        )

        user_prompt = prompt["user"]
        assert "AAPL" in user_prompt
        assert "1h" in user_prompt or "1h," in user_prompt

    def test_prompt_includes_recent_strategies(self):
        """Design prompt includes recent strategies for novelty."""
        recent_strategies = [
            {
                "name": "momentum_v1",
                "type": "momentum",
                "outcome": "promising",
                "sharpe": 1.2,
            },
            {
                "name": "trend_v2",
                "type": "trend",
                "outcome": "mediocre",
                "sharpe": 0.5,
            },
        ]

        prompt = get_strategy_designer_prompt(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            operation_id="op_test_123",
            phase="designing",
            recent_strategies=recent_strategies,
        )

        user_prompt = prompt["user"]
        assert "momentum_v1" in user_prompt
        assert "trend_v2" in user_prompt

    def test_prompt_includes_all_context_together(self):
        """Design prompt includes all context data when provided together."""
        indicators = [{"name": "RSI", "type": "momentum", "parameters": []}]
        symbols = [
            {
                "symbol": "AAPL",
                "timeframes": ["1d"],
                "date_range": {"start": "2020-01-01", "end": "2024-12-01"},
            }
        ]
        recent_strategies = [
            {"name": "test_strat", "type": "test", "outcome": "pending"}
        ]

        prompt = get_strategy_designer_prompt(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            operation_id="op_test_123",
            phase="designing",
            available_indicators=indicators,
            available_symbols=symbols,
            recent_strategies=recent_strategies,
        )

        user_prompt = prompt["user"]
        # All context should be present
        assert "RSI" in user_prompt
        assert "AAPL" in user_prompt
        assert "test_strat" in user_prompt


class TestPromptContextWithMemory:
    """Tests for PromptContext memory fields (Task 3.1).

    These tests verify that PromptContext can hold experiment_history
    and open_hypotheses fields for memory integration.
    """

    def test_prompt_context_with_memory(self):
        """Can create PromptContext with memory fields populated."""
        experiments = [
            {
                "id": "exp_v15_rsi_only",
                "timestamp": "2025-12-27T00:00:00Z",
                "context": {"indicators": ["RSI"], "timeframe": "1h"},
                "results": {"test_accuracy": 0.642},
                "assessment": {"verdict": "strong_signal"},
            }
        ]
        hypotheses = [
            {
                "id": "H_001",
                "text": "Multi-timeframe might break the plateau",
                "status": "untested",
            }
        ]

        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            operation_id="op_test_123",
            phase="designing",
            experiment_history=experiments,
            open_hypotheses=hypotheses,
        )

        assert ctx.experiment_history == experiments
        assert ctx.open_hypotheses == hypotheses
        assert len(ctx.experiment_history) == 1
        assert len(ctx.open_hypotheses) == 1
        assert ctx.experiment_history[0]["id"] == "exp_v15_rsi_only"
        assert ctx.open_hypotheses[0]["id"] == "H_001"

    def test_prompt_context_without_memory(self):
        """PromptContext works without memory fields (defaults to None)."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            operation_id="op_test_123",
            phase="designing",
        )

        assert ctx.experiment_history is None
        assert ctx.open_hypotheses is None
        # Other fields still work
        assert ctx.trigger_reason == TriggerReason.START_NEW_CYCLE
        assert ctx.operation_id == "op_test_123"
        assert ctx.phase == "designing"

    def test_prompt_context_memory_fields_default_to_none(self):
        """Memory fields default to None when not specified."""
        # Create with only required fields
        ctx = PromptContext(
            trigger_reason=TriggerReason.TRAINING_COMPLETED,
            operation_id="op_other_456",
            phase="training",
            training_results={"accuracy": 0.65},  # Non-memory optional field
        )

        # Memory fields should be None
        assert ctx.experiment_history is None
        assert ctx.open_hypotheses is None
        # But training_results is set
        assert ctx.training_results is not None

    def test_prompt_context_with_empty_memory_lists(self):
        """PromptContext accepts empty lists for memory fields."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            operation_id="op_test_789",
            phase="designing",
            experiment_history=[],
            open_hypotheses=[],
        )

        # Empty lists are valid (not None)
        assert ctx.experiment_history == []
        assert ctx.open_hypotheses == []
        assert ctx.experiment_history is not None
        assert ctx.open_hypotheses is not None
