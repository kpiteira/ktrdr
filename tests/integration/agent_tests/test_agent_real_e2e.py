"""
Real End-to-End Integration Tests for the Research Agent System.

These tests invoke the REAL Anthropic API to verify the complete agent flow:
    CLI → API → TriggerService → AnthropicAgentInvoker → Anthropic API → ToolExecutor → Strategy

IMPORTANT: These tests are EXPENSIVE and SLOW. They:
- Call the real Anthropic API (costs money)
- Require ANTHROPIC_API_KEY to be set
- Take 30-120 seconds per invocation
- Create real files in the strategies/ directory

Prerequisites:
- PostgreSQL database running and DATABASE_URL set
- ANTHROPIC_API_KEY set
- Set AGENT_E2E_REAL_INVOKE=true to enable these tests

Run with:
    AGENT_E2E_REAL_INVOKE=true DATABASE_URL="postgresql://ktrdr:localdev@localhost:5432/ktrdr" \
        uv run pytest tests/integration/agent_tests/test_agent_real_e2e.py -v -s

For detailed output with token tracking:
    AGENT_E2E_REAL_INVOKE=true DATABASE_URL="postgresql://..." \
        uv run pytest tests/integration/agent_tests/test_agent_real_e2e.py::TestAgentRealE2E::test_full_design_cycle_with_real_anthropic -v -s
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

from research_agents.database.queries import AgentDatabase
from research_agents.database.schema import SessionPhase

# Skip all tests in this module unless both conditions are met
pytestmark = [
    pytest.mark.skipif(
        not os.getenv("DATABASE_URL"),
        reason="DATABASE_URL not set - skipping real E2E tests",
    ),
    pytest.mark.skipif(
        not os.getenv("AGENT_E2E_REAL_INVOKE"),
        reason="Set AGENT_E2E_REAL_INVOKE=true to run real Anthropic API tests",
    ),
    pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set - cannot call Anthropic API",
    ),
]


@pytest_asyncio.fixture
async def agent_db():
    """Create and connect to the agent database.

    Yields the database instance, then disconnects.
    Skips tests if database connection fails.
    """
    db = AgentDatabase()
    try:
        await db.connect(os.getenv("DATABASE_URL"))
    except Exception as e:
        pytest.skip(f"Could not connect to database: {e}")

    yield db

    await db.disconnect()


@pytest_asyncio.fixture
async def clean_db(agent_db: AgentDatabase):
    """Ensure database is clean before each test.

    Deletes all existing sessions and actions to ensure a clean state.
    """
    async with agent_db.pool.acquire() as conn:
        await conn.execute("DELETE FROM agent_actions")
        await conn.execute("DELETE FROM agent_sessions")

    return agent_db


@pytest.fixture
def test_strategies_dir(tmp_path):
    """Create a temporary directory for test strategies.

    This prevents pollution of the real strategies/ directory.
    """
    strategies_dir = tmp_path / "test_strategies"
    strategies_dir.mkdir()
    return str(strategies_dir)


class TestAgentRealE2E:
    """Real E2E tests that invoke the actual Anthropic API.

    These tests verify the complete flow:
    1. TriggerService creates session
    2. AnthropicAgentInvoker calls Anthropic API
    3. Claude calls tools (save_strategy_config, get_available_indicators, etc.)
    4. ToolExecutor executes tools locally
    5. Strategy saved to disk
    6. Session updated to DESIGNED state

    WARNING: These tests are EXPENSIVE. Each invocation costs real money
    (approximately $0.05-0.20 depending on model and response length).
    """

    @pytest.mark.asyncio
    async def test_full_design_cycle_with_real_anthropic(
        self,
        clean_db: AgentDatabase,
        test_strategies_dir: str,
    ):
        """Test complete design cycle with real Anthropic API.

        This is the main E2E test that verifies:
        1. TriggerService creates session and invokes agent
        2. Real Claude API is called
        3. Claude calls tools and they execute correctly
        4. Strategy YAML is saved to disk
        5. Session is updated to DESIGNED state
        6. Token counts are captured

        Test takes 30-120 seconds depending on API latency.
        """
        # Arrange - Import here to avoid issues when anthropic not installed
        from ktrdr.agents.executor import ToolExecutor
        from ktrdr.agents.invoker import AnthropicAgentInvoker, AnthropicInvokerConfig
        from ktrdr.agents.tools import AGENT_TOOLS
        from research_agents.services.trigger import TriggerConfig, TriggerService

        # Create mock context provider for controlled test data
        context_provider = MockContextProviderForRealTest()

        # Create real components
        invoker_config = AnthropicInvokerConfig.from_env()
        invoker = AnthropicAgentInvoker(config=invoker_config)
        tool_executor = ToolExecutor()

        # Override the strategies directory in the tool executor
        # to use our test directory instead of the real one
        async def test_save_strategy_config(
            name: str, config: dict[str, Any], description: str = ""
        ) -> dict[str, Any]:
            """Wrapper that saves to test directory."""
            from research_agents.services.strategy_service import save_strategy_config

            return await save_strategy_config(
                name=name,
                config=config,
                description=description,
                strategies_dir=test_strategies_dir,
            )

        tool_executor._handle_save_strategy_config = test_save_strategy_config

        config = TriggerConfig(interval_seconds=0.1, enabled=True)

        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=invoker,
            context_provider=context_provider,
            tool_executor=tool_executor,
            tools=AGENT_TOOLS,  # Pass the tool definitions
        )

        # Act - Trigger the agent (this calls real Anthropic API!)
        print("\n" + "=" * 60)
        print("STARTING REAL ANTHROPIC API INVOCATION")
        print(f"Model: {invoker_config.model}")
        print(f"Max tokens: {invoker_config.max_tokens}")
        print("This will take 30-120 seconds...")
        print("=" * 60 + "\n")

        start_time = time.time()
        result = await service.check_and_trigger()
        elapsed = time.time() - start_time

        print("\n" + "=" * 60)
        print(f"INVOCATION COMPLETE ({elapsed:.1f}s)")
        print(f"Result: {result}")
        print("=" * 60 + "\n")

        # Assert - Trigger was successful
        assert result["triggered"] is True, f"Trigger failed: {result}"
        assert result["session_id"] is not None

        session_id = result["session_id"]

        # Assert - Session exists and is in DESIGNED state
        session = await clean_db.get_session(session_id)
        assert session is not None, "Session not found in database"
        assert (
            session.phase == SessionPhase.DESIGNED
        ), f"Session phase is {session.phase}, expected DESIGNED"
        assert session.strategy_name is not None, "Strategy name not set on session"

        print(f"✅ Session {session_id} in DESIGNED state")
        print(f"   Strategy name: {session.strategy_name}")

        # Assert - Strategy file was created
        strategy_files = list(Path(test_strategies_dir).glob("*.yaml"))
        assert (
            len(strategy_files) >= 1
        ), f"No strategy files created in {test_strategies_dir}"

        strategy_file = strategy_files[0]
        print(f"✅ Strategy file created: {strategy_file.name}")

        # Assert - Strategy file validates
        import yaml

        from ktrdr.config.strategy_validator import StrategyValidator

        with open(strategy_file) as f:
            loaded_config = yaml.safe_load(f)

        validator = StrategyValidator()
        validation_result = validator.validate_strategy_config(loaded_config)

        assert (
            validation_result.is_valid
        ), f"Strategy validation failed: {validation_result.errors}"

        print("✅ Strategy file validates successfully")
        print(
            f"   Strategy type: {loaded_config.get('model', {}).get('type', 'unknown')}"
        )
        print(
            f"   Indicators: {[i.get('name') for i in loaded_config.get('indicators', [])]}"
        )

        # Log token usage from the result
        if "input_tokens" in result and "output_tokens" in result:
            print("✅ Token usage captured:")
            print(f"   Input tokens: {result['input_tokens']}")
            print(f"   Output tokens: {result['output_tokens']}")

    @pytest.mark.asyncio
    async def test_real_api_via_service_trigger(
        self,
        clean_db: AgentDatabase,
        test_strategies_dir: str,
    ):
        """Test triggering via AgentService (simulates API endpoint).

        This test verifies the API endpoint path works correctly:
        AgentService.trigger() → TriggerService → Anthropic API

        Important: This test exposes the bug if ToolExecutor is not
        properly passed through AgentService.
        """
        # This test requires the real backend to be running
        # It tests the API layer integration
        from ktrdr.api.services.agent_service import AgentService

        service = AgentService()

        # Override the config to enable the agent
        service._config.enabled = True

        print("\n" + "=" * 60)
        print("TESTING API SERVICE TRIGGER PATH")
        print("This calls AgentService.trigger() which uses TriggerService")
        print("=" * 60 + "\n")

        start_time = time.time()

        # Act - Trigger via the service (API path)
        result = await service.trigger(dry_run=False)

        elapsed = time.time() - start_time

        print("\n" + "=" * 60)
        print(f"API SERVICE TRIGGER COMPLETE ({elapsed:.1f}s)")
        print(f"Result: {result}")
        print("=" * 60 + "\n")

        # Assert - The trigger should succeed
        # If tool_executor is None, the agent will fail to execute tools
        assert result["success"] is True, f"Trigger failed: {result.get('error')}"
        assert (
            result["triggered"] is True
        ), f"Trigger not triggered: {result.get('reason')}"

        # Get the session to verify state
        db = await service._get_db()
        session_id = result.get("session_id")

        if session_id:
            session = await db.get_session(session_id)
            print(f"✅ Session {session_id}: phase={session.phase.value}")

            # The session should be in DESIGNED state if tools worked
            # If it's still in DESIGNING, tools likely failed
            if session.phase != SessionPhase.DESIGNED:
                print("⚠️  Session not in DESIGNED state - tools may have failed")

    @pytest.mark.asyncio
    async def test_token_tracking_accuracy(
        self,
        clean_db: AgentDatabase,
        test_strategies_dir: str,
    ):
        """Test that token counts are accurately tracked.

        Verifies that input_tokens and output_tokens are captured
        from the Anthropic API response and accumulated correctly
        across multiple API calls (for tool use loops).
        """
        from ktrdr.agents.executor import ToolExecutor
        from ktrdr.agents.invoker import AnthropicAgentInvoker, AnthropicInvokerConfig
        from ktrdr.agents.tools import AGENT_TOOLS
        from research_agents.prompts.strategy_designer import (
            get_strategy_designer_prompt,
        )
        from research_agents.services.trigger import TriggerReason

        # Create invoker
        invoker_config = AnthropicInvokerConfig.from_env()
        invoker = AnthropicAgentInvoker(config=invoker_config)

        # Create context for prompt
        context_provider = MockContextProviderForRealTest()
        indicators = await context_provider.get_available_indicators()
        symbols = await context_provider.get_available_symbols()

        # Build prompt
        prompts = get_strategy_designer_prompt(
            trigger_reason=TriggerReason.START_NEW_CYCLE,
            session_id=1,
            phase="designing",
            available_indicators=indicators,
            available_symbols=symbols,
            recent_strategies=[],
        )

        # Create tool executor that saves to test directory
        tool_executor = ToolExecutor()

        async def test_save(name: str, config: dict, description: str = ""):
            from research_agents.services.strategy_service import save_strategy_config

            return await save_strategy_config(
                name=name,
                config=config,
                description=description,
                strategies_dir=test_strategies_dir,
            )

        tool_executor._handle_save_strategy_config = test_save

        print("\n" + "=" * 60)
        print("TESTING TOKEN TRACKING")
        print("=" * 60 + "\n")

        # Act - Run the invoker directly
        result = await invoker.run(
            prompt=prompts["user"],
            tools=AGENT_TOOLS,
            system_prompt=prompts["system"],
            tool_executor=tool_executor,
        )

        print("\n✅ Invocation complete")
        print(f"   Success: {result.success}")
        print(f"   Input tokens: {result.input_tokens}")
        print(f"   Output tokens: {result.output_tokens}")

        # Assert - Token counts should be positive
        assert result.success is True, f"Invocation failed: {result.error}"
        assert result.input_tokens > 0, "Input tokens should be > 0"
        assert result.output_tokens > 0, "Output tokens should be > 0"

        # Strategy design typically uses 3000-5000 input tokens
        # and 500-2000 output tokens
        assert (
            result.input_tokens > 1000
        ), f"Input tokens suspiciously low: {result.input_tokens}"


class MockContextProviderForRealTest:
    """Context provider for real E2E tests.

    Provides a small set of real indicators and symbols that exist
    in the KTRDR system, so the agent can design valid strategies.
    """

    async def get_available_indicators(self) -> list[dict[str, Any]]:
        """Return real indicators available in KTRDR."""
        return [
            {
                "name": "RSI",
                "type": "momentum",
                "description": "Relative Strength Index - momentum oscillator",
                "parameters": [
                    {
                        "name": "period",
                        "type": "int",
                        "default": 14,
                        "min": 2,
                        "max": 100,
                    },
                    {"name": "source", "type": "str", "default": "close"},
                ],
            },
            {
                "name": "SMA",
                "type": "trend",
                "description": "Simple Moving Average",
                "parameters": [
                    {
                        "name": "period",
                        "type": "int",
                        "default": 20,
                        "min": 1,
                        "max": 500,
                    },
                    {"name": "source", "type": "str", "default": "close"},
                ],
            },
            {
                "name": "MACD",
                "type": "momentum",
                "description": "Moving Average Convergence Divergence",
                "parameters": [
                    {"name": "fast_period", "type": "int", "default": 12},
                    {"name": "slow_period", "type": "int", "default": 26},
                    {"name": "signal_period", "type": "int", "default": 9},
                    {"name": "source", "type": "str", "default": "close"},
                ],
            },
            {
                "name": "BB",
                "type": "volatility",
                "description": "Bollinger Bands - volatility indicator",
                "parameters": [
                    {"name": "period", "type": "int", "default": 20},
                    {"name": "std_dev", "type": "float", "default": 2.0},
                    {"name": "source", "type": "str", "default": "close"},
                ],
            },
            {
                "name": "ATR",
                "type": "volatility",
                "description": "Average True Range",
                "parameters": [
                    {"name": "period", "type": "int", "default": 14},
                ],
            },
        ]

    async def get_available_symbols(self) -> list[dict[str, Any]]:
        """Return real symbols available in KTRDR."""
        return [
            {
                "symbol": "EURUSD",
                "name": "EUR/USD",
                "type": "forex",
                "available_timeframes": ["1m", "5m", "15m", "1h", "4h", "1d"],
                "data_start": "2020-01-01",
                "data_end": "2024-12-31",
            },
            {
                "symbol": "GBPUSD",
                "name": "GBP/USD",
                "type": "forex",
                "available_timeframes": ["1h", "4h", "1d"],
                "data_start": "2020-01-01",
                "data_end": "2024-12-31",
            },
            {
                "symbol": "AAPL",
                "name": "Apple Inc",
                "type": "stock",
                "available_timeframes": ["1d"],
                "data_start": "2020-01-01",
                "data_end": "2024-12-31",
            },
        ]


class TestAgentToolExecution:
    """Tests specifically for tool execution in the E2E context.

    These tests verify that tools execute correctly when called
    by the real Anthropic API.
    """

    @pytest.mark.asyncio
    async def test_tool_executor_integrates_with_invoker(
        self,
        clean_db: AgentDatabase,
        test_strategies_dir: str,
    ):
        """Test that ToolExecutor works correctly with AnthropicAgentInvoker.

        This test verifies that:
        1. Invoker can call ToolExecutor
        2. Tools return correct results
        3. Tool results are sent back to Claude
        4. The conversation loop completes
        """
        from ktrdr.agents.executor import ToolExecutor
        from ktrdr.agents.invoker import AnthropicAgentInvoker, AnthropicInvokerConfig
        from ktrdr.agents.tools import AGENT_TOOLS

        # Create executor with test directory
        tool_executor = ToolExecutor()

        async def test_save(name: str, config: dict, description: str = ""):
            from research_agents.services.strategy_service import save_strategy_config

            return await save_strategy_config(
                name=name,
                config=config,
                description=description,
                strategies_dir=test_strategies_dir,
            )

        tool_executor._handle_save_strategy_config = test_save

        # Create invoker
        invoker_config = AnthropicInvokerConfig.from_env()
        invoker = AnthropicAgentInvoker(config=invoker_config)

        # Simple prompt that should trigger tool use
        prompt = """You are a trading strategy designer.

Your task is simple: Call the get_available_indicators tool to see what indicators are available,
then design a minimal valid strategy and save it using save_strategy_config.

Create a simple RSI-based strategy called "test_rsi_simple" with these minimal requirements:
- Single indicator: RSI with period 14
- Single symbol: EURUSD
- Single timeframe: 1h
- Basic fuzzy sets for oversold/neutral/overbought
- Simple MLP model

Save the strategy when complete."""

        system_prompt = "You are a helpful assistant that designs trading strategies. Always save your strategy using the save_strategy_config tool."

        print("\n" + "=" * 60)
        print("TESTING TOOL EXECUTION INTEGRATION")
        print("=" * 60 + "\n")

        # Act
        result = await invoker.run(
            prompt=prompt,
            tools=AGENT_TOOLS,
            system_prompt=system_prompt,
            tool_executor=tool_executor,
        )

        print("\n✅ Tool integration test complete")
        print(f"   Success: {result.success}")
        print(f"   Output: {result.output[:200] if result.output else 'None'}...")

        # Assert
        assert result.success is True, f"Invocation failed: {result.error}"

        # Check that a strategy file was created
        strategy_files = list(Path(test_strategies_dir).glob("*.yaml"))
        assert (
            len(strategy_files) >= 1
        ), "No strategy file created - tool execution may have failed"

        print(f"   Strategy file: {strategy_files[0].name}")
