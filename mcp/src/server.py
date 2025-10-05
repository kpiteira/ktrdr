"""KTRDR MCP Server - Main entry point"""

from typing import Any, Optional

import structlog

from mcp.server.fastmcp import FastMCP

from .api_client import get_api_client

logger = structlog.get_logger()

# Create the MCP server instance
mcp = FastMCP("KTRDR-Trading-Research")


# Phase 0: Hello World Tool
@mcp.tool()
def hello_ktrdr(name: str = "World") -> str:
    """Test tool to verify MCP server is working"""
    logger.info("Hello tool called", name=name)
    return f"Hello {name}! KTRDR MCP Server is working. Version: 0.1.0"


# Phase 1: Core Research Tools


@mcp.tool()
async def check_backend_health() -> dict[str, Any]:
    """Check if KTRDR backend is healthy and accessible"""
    try:
        async with get_api_client() as client:
            health_data = await client.health_check()

            logger.info("Backend health check completed", status="healthy")
            return {
                "status": "healthy",
                "health": health_data,
                "message": "KTRDR backend is accessible and healthy",
            }
    except Exception as e:
        logger.error("Backend health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
            "message": "Cannot connect to KTRDR backend",
        }


@mcp.tool()
async def get_available_symbols() -> list[dict[str, Any]]:
    """Get list of available trading symbols with metadata from KTRDR backend"""
    try:
        async with get_api_client() as client:
            symbols = await client.get_symbols()
            logger.info("Retrieved symbols", count=len(symbols))
            return symbols
    except Exception as e:
        logger.error("Failed to get symbols", error=str(e))
        raise


@mcp.tool()
async def get_market_data(
    symbol: str,
    timeframe: str = "1h",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    trading_hours_only: bool = False,
    limit_bars: int = 50,
) -> dict[str, Any]:
    """Get cached market data for analysis (fast, local data only)

    ⚠️ RESPONSE SIZE LIMITS: This tool can return large datasets. For best results:
    - Use start_date/end_date to limit data range (e.g., single trading day)
    - Set limit_bars to reasonable size (50-200 bars max recommended)
    - For "last trading day": set both start_date and end_date to same recent date

    COMMON PATTERNS:
    - Last trading day: start_date="2025-06-07", end_date="2025-06-07"
    - Recent week: start_date="2025-06-01", end_date="2025-06-07"
    - Small sample: limit_bars=20

    Args:
        symbol: Trading symbol (e.g., 'AAPL', 'TSLA')
        timeframe: Data timeframe ('1m', '5m', '1h', '1d')
        start_date: Start date (YYYY-MM-DD format) - RECOMMENDED for size control
        end_date: End date (YYYY-MM-DD format) - RECOMMENDED for size control
        trading_hours_only: Filter to trading hours only
        limit_bars: Maximum number of data points to return (default 50, max 200)

    Returns OHLCV data ready for analysis. Perfect for research and visualization.
    """
    try:
        async with get_api_client() as client:
            # Apply client-side limiting (max 200 bars to prevent Claude overload)
            effective_limit = min(limit_bars, 200) if limit_bars else 50
            data = await client.get_cached_data(
                symbol,
                timeframe,
                start_date,
                end_date,
                trading_hours_only,
                limit=effective_limit,
            )
            logger.info(
                "Cached market data retrieved",
                symbol=symbol,
                timeframe=timeframe,
                limit=effective_limit,
            )
            return data
    except Exception as e:
        logger.error("Failed to get market data", symbol=symbol, error=str(e))
        raise


@mcp.tool()
async def get_data_summary(symbol: str, timeframe: str = "1h") -> dict[str, Any]:
    """Get summary information about available data for a symbol

    NOTE: This tool provides metadata about available data ranges without
    returning the actual data. Use this to check data availability before
    requesting large datasets.

    Args:
        symbol: Trading symbol (e.g., 'AAPL', 'TSLA')
        timeframe: Data timeframe to check ('1m', '5m', '1h', '1d')

    Returns metadata about date ranges, point counts, etc.
    """
    try:
        async with get_api_client() as client:
            # Get a minimal data sample to extract metadata
            data = await client.get_cached_data(symbol, timeframe, limit=1)

            # Extract useful summary info
            metadata = data.get("data", {}).get("metadata", {})
            summary = {
                "symbol": symbol,
                "timeframe": timeframe,
                "data_available": len(data.get("data", {}).get("dates", [])) > 0,
                "metadata": metadata,
            }

            logger.info("Data summary retrieved", symbol=symbol, timeframe=timeframe)
            return {"success": True, "data": summary, "error": None}
    except Exception as e:
        logger.error("Failed to get data summary", symbol=symbol, error=str(e))
        raise


@mcp.tool()
async def get_available_indicators() -> list[dict[str, Any]]:
    """Get list of available indicators that can be used in strategies

    Returns:
        List of available indicators with their parameters and descriptions
    """
    try:
        async with get_api_client() as client:
            indicators = await client.get_indicators()
            logger.info("Retrieved indicators", count=len(indicators))
            return indicators
    except Exception as e:
        logger.error("Failed to get available indicators", error=str(e))
        raise


@mcp.tool()
async def get_available_strategies() -> list[dict[str, Any]]:
    """Get list of available trading strategies

    Returns:
        List of strategies with their configuration and training status
    """
    try:
        async with get_api_client() as client:
            response = await client.get_strategies()
            strategies = response.get("strategies", [])
            logger.info("Retrieved strategies", count=len(strategies))
            return strategies
    except Exception as e:
        logger.error("Failed to get available strategies", error=str(e))
        raise


# Neural Network Training Tools


@mcp.tool()
async def get_training_status(task_id: str) -> dict[str, Any]:
    """Get the status and progress of a neural network training task

    Args:
        task_id: Training task ID from backend operations

    Returns:
        Training status, progress, metrics, and current state
    """
    try:
        # Get status directly from backend
        async with get_api_client() as client:
            status = await client.get_training_status(task_id)

        logger.info(
            "Training status retrieved", task_id=task_id, status=status.get("status")
        )
        return status

    except Exception as e:
        logger.error("Failed to get training status", task_id=task_id, error=str(e))
        raise


@mcp.tool()
async def get_model_performance(task_id: str) -> dict[str, Any]:
    """Get detailed performance metrics for a trained model

    Args:
        task_id: Training task ID

    Returns:
        Model performance metrics, validation results, and training history
    """
    try:
        async with get_api_client() as client:
            performance = await client.get_model_performance(task_id)

        logger.info("Model performance retrieved", task_id=task_id)
        return performance

    except Exception as e:
        logger.error("Failed to get model performance", task_id=task_id, error=str(e))
        raise


@mcp.tool()
async def test_model_prediction(
    model_name: str, symbol: str, timeframe: str = "1h", test_date: Optional[str] = None
) -> dict[str, Any]:
    """Test a trained model's prediction capability on specific data

    Args:
        model_name: Name of the model to test
        symbol: Trading symbol to test on
        timeframe: Data timeframe
        test_date: Specific date to test (YYYY-MM-DD), uses latest if not specified

    Returns:
        Model prediction results with confidence scores and signal
    """
    try:
        async with get_api_client() as client:
            prediction = await client.test_model_prediction(
                model_name=model_name,
                symbol=symbol,
                timeframe=timeframe,
                test_date=test_date,
            )

        logger.info("Model prediction tested", model=model_name, symbol=symbol)
        return prediction

    except Exception as e:
        logger.error("Failed to test model prediction", model=model_name, error=str(e))
        raise


# Backtesting Tools


@mcp.tool()
async def list_operations(
    operation_type: Optional[str] = None,
    status: Optional[str] = None,
    active_only: bool = False,
    limit: int = 10,
) -> dict[str, Any]:
    """List all operations with optional filtering

    Get a list of data loading, training, or other async operations.
    Filter by status (running, completed, failed) or type (data_load, training).

    Args:
        operation_type: Filter by type (data_load, training, backtest)
        status: Filter by status (running, completed, failed, cancelled, pending)
        active_only: Show only active operations (running/pending)
        limit: Maximum number of operations to return (default 10, max 100)

    Returns:
        dict with operation list and counts
    """
    try:
        async with get_api_client() as client:
            result = await client.operations.list_operations(
                operation_type=operation_type,
                status=status,
                active_only=active_only,
                limit=min(limit, 100),
                offset=0,
            )
            logger.info("Listed operations", count=len(result.get("data", [])))
            return result
    except Exception as e:
        logger.error("Failed to list operations", error=str(e))
        raise


@mcp.tool()
async def get_operation_status(operation_id: str) -> dict[str, Any]:
    """Get detailed status of a specific operation

    Poll for progress updates on data loading, training, or other async operations.
    Returns current status, progress percentage, ETA, and any errors.

    Args:
        operation_id: Unique operation identifier (e.g., "op_training_20241201_123456")

    Returns:
        dict with detailed operation status, progress, and metadata
    """
    try:
        async with get_api_client() as client:
            result = await client.operations.get_operation_status(operation_id)
            logger.info("Got operation status", operation_id=operation_id)
            return result
    except Exception as e:
        logger.error("Failed to get operation status", error=str(e))
        raise


@mcp.tool()
async def cancel_operation(
    operation_id: str, reason: Optional[str] = None
) -> dict[str, Any]:
    """Cancel a running async operation

    Stop a long-running data load or training operation.
    Only works for operations in 'running' or 'pending' status.

    Args:
        operation_id: Unique operation identifier to cancel
        reason: Optional reason for cancellation (for audit trail)

    Returns:
        dict confirming cancellation
    """
    try:
        async with get_api_client() as client:
            result = await client.operations.cancel_operation(operation_id, reason)
            logger.info("Cancelled operation", operation_id=operation_id, reason=reason)
            return result
    except Exception as e:
        logger.error("Failed to cancel operation", error=str(e))
        raise


@mcp.tool()
async def get_operation_results(operation_id: str) -> dict[str, Any]:
    """Get results from a completed operation

    Retrieve summary metrics and artifact paths from finished operations.
    Only works for operations in 'completed' or 'failed' status.

    Args:
        operation_id: Unique operation identifier

    Returns:
        dict with result summary, metrics, and paths to detailed data
    """
    try:
        async with get_api_client() as client:
            result = await client.operations.get_operation_results(operation_id)
            logger.info("Got operation results", operation_id=operation_id)
            return result
    except Exception as e:
        logger.error("Failed to get operation results", error=str(e))
        raise


@mcp.tool()
async def trigger_data_loading(
    symbol: str,
    timeframe: str = "1h",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    mode: str = "local",
) -> dict[str, Any]:
    """Load market data from external sources (IB Gateway) or local cache

    Triggers data loading in the background. Returns immediately with operation_id
    for tracking progress. Use get_operation_status() to monitor the data load.

    Args:
        symbol: Trading symbol (e.g., "AAPL", "EURUSD")
        timeframe: Data timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d)
        start_date: Start date (YYYY-MM-DD, optional)
        end_date: End date (YYYY-MM-DD, optional)
        mode: Loading mode (local, ib, hybrid)

    Returns:
        dict with operation_id for tracking the data loading operation
    """
    try:
        async with get_api_client() as client:
            result = await client.data.load_data_operation(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                mode=mode,
            )
            logger.info(
                "Data loading triggered",
                symbol=symbol,
                operation_id=result.get("operation_id"),
            )
            return result
    except Exception as e:
        logger.error("Failed to trigger data loading", error=str(e))
        raise


@mcp.tool()
async def start_training(
    symbols: list[str],
    timeframe: str = "1h",
    config: Optional[dict[str, Any]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    """Train a neural network model on market data

    Trains a neural network to predict trading signals using historical market data.
    Training runs in the background. Returns immediately with operation_id for
    tracking progress. Use get_operation_status() to monitor training progress.

    Args:
        symbols: List of trading symbols to train on (e.g., ["AAPL", "MSFT"])
        timeframe: Data timeframe (1h, 4h, 1d)
        config: Optional training configuration dict (epochs, batch_size, learning_rate)
        start_date: Training data start date (YYYY-MM-DD, optional)
        end_date: Training data end date (YYYY-MM-DD, optional)

    Returns:
        dict with operation_id for tracking the training operation
    """
    try:
        async with get_api_client() as client:
            training_config = config or {
                "epochs": 100,
                "batch_size": 32,
                "learning_rate": 0.001,
            }

            result = await client.training.start_neural_training(
                symbols=symbols,
                timeframe=timeframe,
                config=training_config,
                start_date=start_date,
                end_date=end_date,
            )
            logger.info(
                "Training started",
                symbols=symbols,
                operation_id=result.get("operation_id"),
            )
            return result
    except Exception as e:
        logger.error("Failed to start training", error=str(e))
        raise


class KTRDRMCPServer:
    """MCP Server for KTRDR trading strategy research"""

    def __init__(self):
        logger.info("KTRDR MCP Server initialized")

    def run(self):
        """Run the MCP server"""
        logger.info("Starting KTRDR MCP Server")
        mcp.run()
