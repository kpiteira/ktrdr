"""
Unit tests for strategy designer prompt.

Tests cover:
- System prompt structure and key elements
- User prompt variations by trigger reason
- Context injection (indicators, symbols, recent strategies)
- Prompt building with different contexts
"""

import pytest

from research_agents.prompts.strategy_designer import (
    PromptContext,
    StrategyDesignerPromptBuilder,
    TriggerReason,
)


class TestTriggerReason:
    """Tests for TriggerReason enum."""

    def test_trigger_reasons_exist(self):
        """All expected trigger reasons should exist."""
        assert TriggerReason.START_NEW_CYCLE == "start_new_cycle"
        assert TriggerReason.TRAINING_COMPLETED == "training_completed"
        assert TriggerReason.BACKTEST_COMPLETED == "backtest_completed"

    def test_trigger_reason_values(self):
        """Trigger reason values should be string compatible."""
        for reason in TriggerReason:
            assert isinstance(reason.value, str)


class TestPromptContext:
    """Tests for PromptContext dataclass."""

    def test_minimal_context(self):
        """Context can be created with just required fields."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="designing",
        )
        assert ctx.trigger_reason == TriggerReason.START_NEW_CYCLE
        assert ctx.session_id == 1
        assert ctx.phase == "designing"

    def test_context_with_optional_fields(self):
        """Context should support optional fields."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.TRAINING_COMPLETED,
            session_id=42,
            phase="training",
            training_results={"accuracy": 0.52, "loss": 0.42},
            strategy_config={"name": "test_strategy"},
        )
        assert ctx.training_results == {"accuracy": 0.52, "loss": 0.42}
        assert ctx.strategy_config == {"name": "test_strategy"}

    def test_context_defaults_to_empty_lists(self):
        """Optional list fields should default appropriately."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="designing",
        )
        assert ctx.recent_strategies == [] or ctx.recent_strategies is None
        assert ctx.available_indicators == [] or ctx.available_indicators is None
        assert ctx.available_symbols == [] or ctx.available_symbols is None


class TestStrategyDesignerPromptBuilder:
    """Tests for StrategyDesignerPromptBuilder."""

    @pytest.fixture
    def builder(self):
        """Create a prompt builder instance."""
        return StrategyDesignerPromptBuilder()

    @pytest.fixture
    def sample_indicators(self):
        """Sample indicator data for testing."""
        return [
            {
                "name": "rsi",
                "description": "Relative Strength Index",
                "parameters": [
                    {
                        "name": "period",
                        "type": "int",
                        "default": 14,
                        "min": 2,
                        "max": 100,
                    }
                ],
            },
            {
                "name": "macd",
                "description": "Moving Average Convergence Divergence",
                "parameters": [
                    {"name": "fast_period", "type": "int", "default": 12},
                    {"name": "slow_period", "type": "int", "default": 26},
                    {"name": "signal_period", "type": "int", "default": 9},
                ],
            },
            {
                "name": "ema",
                "description": "Exponential Moving Average",
                "parameters": [{"name": "period", "type": "int", "default": 20}],
            },
        ]

    @pytest.fixture
    def sample_symbols(self):
        """Sample symbol data for testing."""
        return [
            {
                "symbol": "EURUSD",
                "timeframes": ["1h", "4h", "1d"],
                "date_range": {"start": "2020-01-01", "end": "2024-12-01"},
            },
            {
                "symbol": "GBPUSD",
                "timeframes": ["1h", "1d"],
                "date_range": {"start": "2021-01-01", "end": "2024-12-01"},
            },
        ]

    @pytest.fixture
    def sample_recent_strategies(self):
        """Sample recent strategies for testing."""
        return [
            {
                "name": "momentum_ema_v1",
                "type": "momentum",
                "outcome": "success",
                "sharpe": 0.82,
                "created_at": "2024-01-15",
            },
            {
                "name": "mean_reversion_rsi",
                "type": "mean_reversion",
                "outcome": "failed_training",
                "created_at": "2024-01-14",
            },
        ]

    def test_builder_creates_valid_structure(self, builder):
        """Builder should return dict with system and user keys."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)

        assert isinstance(result, dict)
        assert "system" in result
        assert "user" in result
        assert isinstance(result["system"], str)
        assert isinstance(result["user"], str)

    def test_system_prompt_contains_role(self, builder):
        """System prompt should define the agent's role."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should mention being a strategy designer
        assert "strategy" in system.lower()
        # Should mention trading or KTRDR
        assert "trading" in system.lower() or "ktrdr" in system.lower()
        # Should mention autonomous or research
        assert "autonomous" in system.lower() or "research" in system.lower()

    def test_system_prompt_lists_available_tools(self, builder):
        """System prompt should list available MCP tools."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should mention key tools
        assert "get_agent_state" in system
        assert "update_agent_state" in system
        assert "save_strategy_config" in system
        assert "get_recent_strategies" in system

    def test_system_prompt_contains_yaml_template(self, builder):
        """System prompt should include strategy YAML template."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should have key YAML structure elements
        assert "training_data:" in system or "training_data" in system
        assert "indicators:" in system or "indicators" in system
        assert "fuzzy_sets:" in system or "fuzzy_sets" in system
        assert "model:" in system or "neural" in system.lower()

    def test_user_prompt_includes_trigger_reason(self, builder):
        """User prompt should include the trigger reason."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)
        user = result["user"]

        assert "start_new_cycle" in user

    def test_user_prompt_includes_session_context(self, builder):
        """User prompt should include session ID and phase."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=42,
            phase="designing",
        )
        result = builder.build(ctx)
        user = result["user"]

        assert "42" in user
        assert "designing" in user.lower()

    def test_start_new_cycle_includes_design_instructions(self, builder):
        """START_NEW_CYCLE trigger should include design instructions."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)
        user = result["user"]

        # Should mention design-related actions
        assert "design" in user.lower() or "create" in user.lower()
        assert "strategy" in user.lower()

    def test_training_completed_includes_results(self, builder):
        """TRAINING_COMPLETED trigger should include training results."""
        training_results = {
            "final_accuracy": 0.523,
            "final_loss": 0.42,
            "epochs_completed": 47,
        }
        ctx = PromptContext(
            trigger_reason=TriggerReason.TRAINING_COMPLETED,
            session_id=1,
            phase="training",
            training_results=training_results,
        )
        result = builder.build(ctx)
        user = result["user"]

        # Should include training results
        assert "0.523" in user or "52.3" in user or "accuracy" in user.lower()
        # Should mention backtesting next
        assert "backtest" in user.lower()

    def test_backtest_completed_includes_results(self, builder):
        """BACKTEST_COMPLETED trigger should include backtest results."""
        backtest_results = {
            "sharpe_ratio": 0.82,
            "win_rate": 0.542,
            "max_drawdown": 0.123,
        }
        ctx = PromptContext(
            trigger_reason=TriggerReason.BACKTEST_COMPLETED,
            session_id=1,
            phase="backtesting",
            backtest_results=backtest_results,
        )
        result = builder.build(ctx)
        user = result["user"]

        # Should include backtest results
        assert "sharpe" in user.lower() or "0.82" in user
        # Should mention assessment
        assert "assess" in user.lower() or "analyze" in user.lower()

    def test_context_injects_indicators(self, builder, sample_indicators):
        """Available indicators should be injected into context."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
            available_indicators=sample_indicators,
        )
        result = builder.build(ctx)

        # Indicators should appear in system or user prompt
        combined = result["system"] + result["user"]
        assert "rsi" in combined.lower()
        assert "macd" in combined.lower()

    def test_context_injects_symbols(self, builder, sample_symbols):
        """Available symbols should be injected into context."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
            available_symbols=sample_symbols,
        )
        result = builder.build(ctx)

        # Symbols should appear in system or user prompt
        combined = result["system"] + result["user"]
        assert "EURUSD" in combined

    def test_context_injects_recent_strategies(self, builder, sample_recent_strategies):
        """Recent strategies should be injected for novelty."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
            recent_strategies=sample_recent_strategies,
        )
        result = builder.build(ctx)

        # Recent strategies should appear
        combined = result["system"] + result["user"]
        assert "momentum_ema_v1" in combined or "momentum" in combined.lower()

    def test_output_format_section_exists(self, builder):
        """System prompt should include output format guidance."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should have output format section
        assert "status" in system.lower() or "output" in system.lower()

    def test_design_guidelines_exist(self, builder):
        """System prompt should include design guidelines."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should have guidelines or principles
        assert (
            "guideline" in system.lower()
            or "creative" in system.lower()
            or "hypothesis" in system.lower()
        )


class TestPromptEnumConstraints:
    """Tests for Task 1.14: Explicit enum constraints in prompts."""

    @pytest.fixture
    def builder(self):
        """Create a prompt builder instance."""
        return StrategyDesignerPromptBuilder()

    def test_system_prompt_contains_enum_constraints_section(self, builder):
        """System prompt should include explicit enum constraints section."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should have a section about valid enum values
        assert "valid enum" in system.lower() or "critical" in system.lower()
        # Should explicitly list training_data.symbols.mode values
        # Correct values: "single" and "multi_symbol"
        assert "multi_symbol" in system
        assert '"single"' in system  # The "single" legacy mode

    def test_system_prompt_contains_timeframe_mode_enums(self, builder):
        """System prompt should list timeframe mode enum values."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should list timeframe mode values
        # Correct values: "single" and "multi_timeframe"
        assert "multi_timeframe" in system
        assert '"single"' in system  # The "single" legacy mode

    def test_system_prompt_contains_deployment_mode_enums(self, builder):
        """System prompt should list deployment target mode enum values."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should list deployment mode values
        # Correct values: "universal", "group_restricted", "training_only"
        assert "universal" in system
        assert "training_only" in system or "group_restricted" in system

    def test_system_prompt_contains_fuzzy_type_enums(self, builder):
        """System prompt should list valid fuzzy membership types with param counts."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should list fuzzy types with parameter requirements
        assert "triangular" in system.lower()
        assert "trapezoidal" in system.lower() or "trapezoid" in system.lower()
        assert "gaussian" in system.lower()
        # Should mention parameter counts
        assert "3" in system or "three" in system.lower()

    def test_system_prompt_contains_model_type_enums(self, builder):
        """System prompt should list valid model types."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should list model type
        assert "mlp" in system.lower()

    def test_system_prompt_contains_activation_enums(self, builder):
        """System prompt should list valid activation functions."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should list activation functions
        assert "relu" in system.lower()
        assert "softmax" in system.lower()

    def test_system_prompt_contains_optimizer_enums(self, builder):
        """System prompt should list valid optimizers."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should list optimizer options
        assert "adam" in system.lower()


class TestPromptValidationErrorPrevention:
    """Tests for Task 1.14: Common validation errors section."""

    @pytest.fixture
    def builder(self):
        """Create a prompt builder instance."""
        return StrategyDesignerPromptBuilder()

    def test_system_prompt_contains_common_errors_section(self, builder):
        """System prompt should include common validation errors section."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should have a section about common errors
        assert "common" in system.lower() and "error" in system.lower()
        # Should warn about parameters vs params
        assert "parameters" in system.lower()

    def test_system_prompt_warns_about_feature_id_requirement(self, builder):
        """System prompt should emphasize feature_id is required."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should emphasize feature_id is required
        assert "feature_id" in system
        # Should mention it's required or mandatory
        assert "required" in system.lower() or "must" in system.lower()

    def test_system_prompt_warns_about_fuzzy_set_key_matching(self, builder):
        """System prompt should warn fuzzy_sets keys must match feature_id."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
        )
        result = builder.build(ctx)
        system = result["system"]

        # Should mention fuzzy_sets key matching
        assert "fuzzy_sets" in system or "fuzzy sets" in system.lower()
        assert "match" in system.lower() or "exact" in system.lower()


class TestPromptIndicatorFormatting:
    """Tests for Task 1.14: Case-sensitive indicator name formatting."""

    @pytest.fixture
    def builder(self):
        """Create a prompt builder instance."""
        return StrategyDesignerPromptBuilder()

    @pytest.fixture
    def sample_indicators_with_case(self):
        """Sample indicators with proper case-sensitive names."""
        return [
            {
                "name": "RSI",  # Proper case
                "description": "Relative Strength Index",
                "parameters": [{"name": "period", "type": "int", "default": 14}],
            },
            {
                "name": "WilliamsR",  # Proper PascalCase
                "description": "Williams %R",
                "parameters": [{"name": "period", "type": "int", "default": 14}],
            },
            {
                "name": "BollingerBands",  # Proper PascalCase
                "description": "Bollinger Bands",
                "parameters": [],
            },
        ]

    def test_indicator_formatting_preserves_exact_case(
        self, builder, sample_indicators_with_case
    ):
        """Indicator names should be displayed with exact case."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
            available_indicators=sample_indicators_with_case,
        )
        result = builder.build(ctx)
        combined = result["system"] + result["user"]

        # Should preserve exact case
        assert "RSI" in combined
        assert "WilliamsR" in combined
        assert "BollingerBands" in combined

    def test_indicator_formatting_warns_about_case_sensitivity(
        self, builder, sample_indicators_with_case
    ):
        """Indicator section should warn about case sensitivity."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
            available_indicators=sample_indicators_with_case,
        )
        result = builder.build(ctx)
        combined = result["system"] + result["user"]

        # Should mention case sensitivity
        assert (
            "case-sensitive" in combined.lower()
            or "exact" in combined.lower()
            or "must use" in combined.lower()
        )

    def test_indicator_formatting_uses_code_backticks(
        self, builder, sample_indicators_with_case
    ):
        """Indicator names should use backticks for code formatting."""
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="idle",
            available_indicators=sample_indicators_with_case,
        )
        result = builder.build(ctx)
        user = result["user"]

        # Should use backticks around indicator names for clarity
        assert "`RSI`" in user or "**RSI**" in user


class TestPromptBuilderIntegration:
    """Integration tests for prompt builder with full context."""

    def test_full_new_cycle_prompt(self):
        """Test complete prompt for starting a new design cycle."""
        builder = StrategyDesignerPromptBuilder()
        ctx = PromptContext(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=100,
            phase="idle",
            available_indicators=[
                {"name": "rsi", "description": "RSI indicator", "parameters": []},
                {"name": "macd", "description": "MACD indicator", "parameters": []},
            ],
            available_symbols=[
                {"symbol": "EURUSD", "timeframes": ["1h"], "date_range": {}},
            ],
            recent_strategies=[
                {"name": "old_strategy", "outcome": "failed_training"},
            ],
        )

        result = builder.build(ctx)

        # Verify structure
        assert "system" in result
        assert "user" in result

        # Verify system contains key elements
        system = result["system"]
        assert len(system) > 100  # Should be substantial

        # Verify user contains context
        user = result["user"]
        assert "100" in user  # Session ID
        assert "start_new_cycle" in user

    def test_full_training_completed_prompt(self):
        """Test complete prompt for training completion."""
        builder = StrategyDesignerPromptBuilder()
        ctx = PromptContext(
            trigger_reason=TriggerReason.TRAINING_COMPLETED,
            session_id=200,
            phase="training",
            training_results={
                "final_accuracy": 0.55,
                "final_loss": 0.38,
                "epochs_completed": 50,
            },
            strategy_config={"name": "test_strategy_v1"},
        )

        result = builder.build(ctx)

        # Should include training results in context
        user = result["user"]
        assert "training" in user.lower()

    def test_full_backtest_completed_prompt(self):
        """Test complete prompt for backtest completion."""
        builder = StrategyDesignerPromptBuilder()
        ctx = PromptContext(
            trigger_reason=TriggerReason.BACKTEST_COMPLETED,
            session_id=300,
            phase="backtesting",
            training_results={"final_accuracy": 0.55},
            backtest_results={
                "sharpe_ratio": 0.95,
                "win_rate": 0.58,
                "max_drawdown": 0.15,
                "total_trades": 200,
            },
            strategy_config={"name": "test_strategy_v2"},
        )

        result = builder.build(ctx)

        # Should include backtest results in context
        user = result["user"]
        assert "backtest" in user.lower() or "completed" in user.lower()
