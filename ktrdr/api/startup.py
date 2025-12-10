"""
API Startup Configuration - UPDATED FOR NEW IB ARCHITECTURE

Simplified startup for new IB architecture:
- No complex background services
- IB connections created on-demand via DataManager
- Clean separation of concerns

Task 1.10 additions:
- Background trigger loop for research agents
- Conditional on AGENT_ENABLED environment variable
- Graceful shutdown handling
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from ktrdr.logging import get_logger

if TYPE_CHECKING:
    from research_agents.services.trigger import TriggerService

logger = get_logger(__name__)

# Global reference for background tasks (for graceful shutdown)
_agent_trigger_task: asyncio.Task | None = None
_agent_trigger_service: TriggerService | None = None


async def start_agent_trigger_loop() -> None:
    """Start the background agent trigger loop.

    This function creates and starts the TriggerService which runs every
    AGENT_TRIGGER_INTERVAL_SECONDS (default: 300 = 5 minutes) to check
    if a new research cycle should be started.

    The loop runs until the service is stopped via stop_agent_trigger_loop().

    Environment variables:
        AGENT_ENABLED: Must be "true" for this to do anything
        AGENT_TRIGGER_INTERVAL_SECONDS: Interval between checks (default: 300)
        AGENT_MODEL: Claude model to use (default: claude-sonnet-4-20250514)
        ANTHROPIC_API_KEY: Required for Anthropic API access
        DATABASE_URL: Required for agent session database
    """
    global _agent_trigger_service

    # Import here to avoid circular imports and heavy dependencies at module load
    from ktrdr.agents.invoker import AnthropicAgentInvoker, AnthropicInvokerConfig
    from ktrdr.api.services.agent_context import AgentMCPContextProvider
    from research_agents.database.queries import get_agent_db
    from research_agents.services.trigger import TriggerConfig, TriggerService

    # Load configuration
    config = TriggerConfig.from_env()

    if not config.enabled:
        logger.info("Agent trigger loop disabled (AGENT_ENABLED != true)")
        return

    logger.info(f"Starting agent trigger loop (interval={config.interval_seconds}s)")

    try:
        # Initialize components
        invoker_config = AnthropicInvokerConfig.from_env()
        invoker = AnthropicAgentInvoker(config=invoker_config)
        db = await get_agent_db()
        context_provider = AgentMCPContextProvider()

        # Create tool executor (Task 1.11)
        # The ToolExecutor routes tool calls to appropriate handlers:
        # - save_strategy_config → strategy service
        # - get_available_indicators → API call
        # - get_available_symbols → API call
        # - get_recent_strategies → strategy service
        from ktrdr.agents.executor import ToolExecutor

        tool_executor = ToolExecutor()

        # Create and start the trigger service
        _agent_trigger_service = TriggerService(
            config=config,
            db=db,
            invoker=invoker,
            context_provider=context_provider,
            tool_executor=tool_executor,
        )

        # Run the service loop
        await _agent_trigger_service.start()

    except Exception as e:
        logger.error(f"Agent trigger loop failed: {e}", exc_info=True)
        raise


async def stop_agent_trigger_loop() -> None:
    """Stop the background agent trigger loop gracefully.

    This signals the TriggerService to stop and waits for the background
    task to complete.
    """
    global _agent_trigger_task, _agent_trigger_service

    if _agent_trigger_service is not None:
        logger.info("Stopping agent trigger service...")
        _agent_trigger_service.stop()
        _agent_trigger_service = None

    if _agent_trigger_task is not None:
        try:
            # Wait for the task to complete with timeout
            await asyncio.wait_for(_agent_trigger_task, timeout=5.0)
            logger.info("Agent trigger task completed")
        except asyncio.TimeoutError:
            logger.warning("Agent trigger task did not complete in time, cancelling")
            _agent_trigger_task.cancel()
            try:
                await _agent_trigger_task
            except asyncio.CancelledError:
                pass
        except asyncio.CancelledError:
            pass
        finally:
            _agent_trigger_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown.

    With the new simplified IB architecture:
    - No persistent background connection pools
    - Connections created on-demand via IbConnectionPool
    - DataManager uses IbDataAdapter when needed

    Task 1.10 additions:
    - Background trigger loop for research agents (when AGENT_ENABLED=true)
    - Graceful shutdown of agent trigger loop
    """
    global _agent_trigger_task

    # Startup
    logger.info("🚀 Starting KTRDR API with new IB architecture...")

    # New architecture doesn't require complex startup
    # IB connections are created on-demand when needed
    logger.info("✅ New IB architecture: connections created on-demand")
    logger.info("✅ DataManager uses IbDataAdapter when enable_ib=True")

    # Initialize training service to log training mode at startup
    from ktrdr.api.endpoints.training import get_training_service

    _ = await get_training_service()  # Initialize service (logs training mode)
    logger.info("✅ TrainingService initialized")

    # Start worker registry background health checks
    from ktrdr.api.endpoints.workers import get_worker_registry

    registry = get_worker_registry()
    await registry.start()
    logger.info("✅ Worker registry started with background health checks")

    # Start agent trigger loop if enabled (Task 1.10)
    agent_enabled = os.getenv("AGENT_ENABLED", "false").lower() in ("true", "1", "yes")
    if agent_enabled:
        logger.info("🤖 Starting agent trigger loop (AGENT_ENABLED=true)...")
        _agent_trigger_task = asyncio.create_task(start_agent_trigger_loop())
        logger.info("✅ Agent trigger loop started in background")
    else:
        logger.info("ℹ️ Agent trigger loop disabled (AGENT_ENABLED != true)")

    logger.info("🎉 API startup completed")

    yield

    # Shutdown
    logger.info("🛑 Shutting down KTRDR API...")

    # Stop agent trigger loop if running (Task 1.10)
    if _agent_trigger_task is not None:
        logger.info("🤖 Stopping agent trigger loop...")
        await stop_agent_trigger_loop()
        logger.info("✅ Agent trigger loop stopped")

    # Stop worker registry background health checks
    await registry.stop()
    logger.info("✅ Worker registry stopped")

    # New architecture: connections are cleaned up automatically
    # via context managers and dedicated threads
    logger.info("✅ IB connections cleaned up automatically")

    logger.info("👋 API shutdown completed")


def init_background_services():
    """
    DEPRECATED: Background services not needed in new IB architecture.

    The new architecture creates IB connections on-demand via:
    - DataManager with IbDataAdapter when enable_ib=True
    - IbConnectionPool for dedicated thread connections

    No persistent background services required.
    """
    logger.info("New IB architecture: no background services needed")
    logger.info("IB connections created on-demand when required")
    return True


def stop_background_services():
    """
    DEPRECATED: Background services not used in new IB architecture.

    Connections are cleaned up automatically via context managers.
    """
    logger.info("New IB architecture: no background services to stop")
    logger.info("IB connections cleaned up automatically")
