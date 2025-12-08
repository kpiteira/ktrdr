"""KTRDR MCP Server - Main entry point"""

from typing import Any, Optional

import structlog

from mcp.server.fastmcp import FastMCP

from .api_client import get_api_client
from .telemetry import trace_mcp_tool
from .tools.agent_tools import register_agent_tools
from .tools.strategy_tools import register_strategy_tools

logger = structlog.get_logger()

# Create the MCP server instance
mcp = FastMCP("KTRDR-Trading-Research")


# Phase 0: Hello World Tool
@trace_mcp_tool("hello_ktrdr")
@mcp.tool()
def hello_ktrdr(name: str = "World") -> str:
    """Test tool to verify MCP server is working"""
    logger.info("Hello tool called", name=name)
    return f"Hello {name}! KTRDR MCP Server is working. Version: 0.1.0"


# Phase 1: Core Research Tools


@trace_mcp_tool("check_backend_health")
@mcp.tool()
async def check_backend_health() -> dict[str, Any]:
    """
    Check if KTRDR backend API is healthy and accessible.

    Verifies backend connectivity, database status, and service health.
    Use this before starting any operations to ensure system readiness.

    Returns:
        Dict with structure:
        {
            "status": str,  # "healthy" or "unhealthy"
            "health": {
                "database": bool,
                "services": dict,
                "version": str
            },
            "message": str,
            "error": Optional[str]
        }

    Examples:
        # Check system health before operations
        health = await check_backend_health()
        if health["status"] == "healthy":
            print("System ready")

    Notes:
        - Fast check (<100ms)
        - No authentication required
        - Use before critical operations
    """
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


@trace_mcp_tool("get_available_symbols")
@mcp.tool()
async def get_available_symbols() -> list[dict[str, Any]]:
    """
    Get list of available trading symbols with metadata.

    Returns all symbols configured in the system with their instrument types,
    exchange information, and data availability status.

    Returns:
        List of dicts with structure:
        [
            {
                "symbol": str,          # "AAPL", "EURUSD", etc.
                "instrument_type": str, # "stock", "forex", "futures"
                "exchange": str,        # "NASDAQ", "FOREX", etc.
                "currency": str,        # "USD", "EUR", etc.
                "data_available": bool
            },
            ...
        ]

    Examples:
        # Get all available symbols
        symbols = await get_available_symbols()
        stocks = [s for s in symbols if s["instrument_type"] == "stock"]

    See Also:
        - trigger_data_loading(): Load data for symbols
        - get_market_data(): Get cached data for symbols

    Notes:
        - Returns configured symbols (not all possible symbols)
        - Check data_available before requesting data
        - New symbols can be added via configuration
    """
    try:
        async with get_api_client() as client:
            symbols = await client.get_symbols()
            logger.info("Retrieved symbols", count=len(symbols))
            return symbols
    except Exception as e:
        logger.error("Failed to get symbols", error=str(e))
        raise


@trace_mcp_tool("get_market_data")
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
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                trading_hours_only=trading_hours_only,
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


@trace_mcp_tool("get_data_summary")
@mcp.tool()
async def get_data_summary(symbol: str, timeframe: str = "1h") -> dict[str, Any]:
    """
    Get summary information about available data for a symbol.

    Provides metadata about available data ranges without returning the actual
    data. Use this to check data availability and size before requesting large datasets.

    Args:
        symbol: Trading symbol (e.g., "AAPL", "TSLA", "EURUSD")
        timeframe: Data timeframe to check
            - Valid values: "1m", "5m", "15m", "30m", "1h", "4h", "1d"
            - Default: "1h"

    Returns:
        Dict with structure:
        {
            "success": bool,
            "data": {
                "symbol": str,
                "timeframe": str,
                "data_available": bool,
                "metadata": {
                    "points": int,        # Total data points available
                    "start_date": str,    # Earliest date
                    "end_date": str,      # Latest date
                    "trading_days": int,
                    "gaps": int          # Missing data gaps
                }
            }
        }

    Examples:
        # Check if data exists before loading
        summary = await get_data_summary("AAPL", "1h")
        if summary["data"]["data_available"]:
            print(f"Data available: {summary['data']['metadata']['points']} points")

    See Also:
        - get_market_data(): Get actual OHLCV data
        - trigger_data_loading(): Load new data if unavailable

    Notes:
        - Fast metadata-only query (<50ms)
        - Use before requesting large datasets
        - Shows data gaps that may need filling
    """
    try:
        async with get_api_client() as client:
            # Get a minimal data sample to extract metadata
            data = await client.get_cached_data(
                symbol=symbol, timeframe=timeframe, limit=1
            )

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


@trace_mcp_tool("get_available_indicators")
@mcp.tool()
async def get_available_indicators() -> list[dict[str, Any]]:
    """
    Get list of available technical indicators for strategies.

    Returns all technical indicators that can be used in strategy configurations,
    including their parameters, default values, and descriptions.

    Returns:
        List of dicts with structure:
        [
            {
                "name": str,           # "RSI", "MACD", "BollingerBands"
                "category": str,       # "momentum", "trend", "volatility"
                "description": str,
                "parameters": [
                    {
                        "name": str,
                        "type": str,   # "int", "float", "string"
                        "default": Any,
                        "min": Optional[float],
                        "max": Optional[float]
                    }
                ],
                "outputs": list[str]   # Output columns produced
            },
            ...
        ]

    Examples:
        # Find all momentum indicators
        indicators = await get_available_indicators()
        momentum = [i for i in indicators if i["category"] == "momentum"]

    See Also:
        - get_available_strategies(): See how indicators are used in strategies

    Notes:
        - 30+ indicators available
        - Each indicator has configurable parameters
        - Custom indicators can be added
    """
    try:
        async with get_api_client() as client:
            indicators = await client.get_indicators()
            logger.info("Retrieved indicators", count=len(indicators))
            return indicators
    except Exception as e:
        logger.error("Failed to get available indicators", error=str(e))
        raise


@trace_mcp_tool("get_available_strategies")
@mcp.tool()
async def get_available_strategies() -> list[dict[str, Any]]:
    """
    Get list of available trading strategies.

    Returns all configured trading strategies with their settings, indicators,
    fuzzy rules, and neural network architectures.

    Returns:
        List of dicts with structure:
        [
            {
                "name": str,              # "neuro_mean_reversion"
                "description": str,
                "indicators": list[str],  # Required indicators
                "fuzzy_rules": int,       # Number of fuzzy rules
                "neural_architecture": {
                    "layers": list[int],
                    "activation": str
                },
                "trained_models": int,    # Number of trained instances
                "last_trained": Optional[str]  # ISO timestamp
            },
            ...
        ]

    Examples:
        # List all strategies
        strategies = await get_available_strategies()
        for s in strategies:
            print(f"{s['name']}: {s['description']}")

    See Also:
        - start_training(): Train a strategy on data
        - get_available_indicators(): See available indicators

    Notes:
        - Strategies defined in config/strategies/
        - Each combines indicators + fuzzy logic + neural nets
        - Custom strategies can be created
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


@trace_mcp_tool("get_training_status")
@mcp.tool()
async def get_training_status(task_id: str) -> dict[str, Any]:
    """
    Get status and progress of a neural network training task.

    DEPRECATED: Use get_operation_status() instead for unified operation tracking.
    This tool remains for backward compatibility.

    Args:
        task_id: Training task ID (same as operation_id)

    Returns:
        Dict with training status, progress, and current metrics

    See Also:
        - get_operation_status(): Preferred method for checking training progress
        - start_training(): Start new training operations

    Notes:
        - This is a legacy endpoint
        - Use get_operation_status() for new code
        - Will be removed in future version
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


@trace_mcp_tool("get_model_performance")
@mcp.tool()
async def get_model_performance(task_id: str) -> dict[str, Any]:
    """
    Get detailed performance metrics for a trained model.

    Retrieves comprehensive performance metrics including accuracy, loss curves,
    validation results, and training history for analysis.

    Args:
        task_id: Training task/operation ID from completed training

    Returns:
        Dict with structure:
        {
            "success": bool,
            "data": {
                "task_id": str,
                "model_name": str,
                "metrics": {
                    "accuracy": float,        # Overall accuracy
                    "precision": float,
                    "recall": float,
                    "f1_score": float
                },
                "loss_history": {
                    "train": list[float],     # Loss per epoch
                    "validation": list[float]
                },
                "validation_results": {
                    "confusion_matrix": list[list[int]],
                    "classification_report": dict
                },
                "training_time": float,       # Seconds
                "epochs_completed": int
            }
        }

    Examples:
        # Get performance after training completes
        perf = await get_model_performance("op_training_123")
        print(f"Model accuracy: {perf['data']['metrics']['accuracy']:.2%}")

    See Also:
        - get_operation_results(): Alternative method for results
        - start_training(): Start training operations

    Notes:
        - Only available after training completion
        - Includes full training history and metrics
        - Use for detailed model analysis
    """
    try:
        async with get_api_client() as client:
            performance = await client.get_model_performance(task_id)

        logger.info("Model performance retrieved", task_id=task_id)
        return performance

    except Exception as e:
        logger.error("Failed to get model performance", task_id=task_id, error=str(e))
        raise


@trace_mcp_tool("test_model_prediction")
@mcp.tool()
async def test_model_prediction(
    model_name: str, symbol: str, timeframe: str = "1h", test_date: Optional[str] = None
) -> dict[str, Any]:
    """
    Test a trained model's prediction on specific data.

    Run a trained model on specific market data to see its predictions and
    confidence scores. Useful for validating model performance on new data.

    Args:
        model_name: Name of trained model to test
            - Format: "strategy_name_YYYYMMDD_HHMMSS"
            - Get from list_trained_models() or training results
        symbol: Trading symbol to test on
            - Should match or be similar to training symbols
        timeframe: Data timeframe
            - Valid values: "1m", "5m", "15m", "30m", "1h", "4h", "1d"
            - Should match training timeframe
        test_date: Specific date for testing (YYYY-MM-DD)
            - Default: Latest available data
            - Use out-of-sample dates for validation

    Returns:
        Dict with structure:
        {
            "success": bool,
            "data": {
                "model_name": str,
                "symbol": str,
                "test_date": str,
                "prediction": {
                    "signal": str,        # "BUY", "SELL", "HOLD"
                    "confidence": float,  # 0.0-1.0
                    "probabilities": {
                        "buy": float,
                        "sell": float,
                        "hold": float
                    }
                },
                "features": dict,         # Input features used
                "timestamp": str
            }
        }

    Examples:
        # Test model on latest data
        result = await test_model_prediction(
            model_name="neuro_mean_reversion_20241201_120000",
            symbol="AAPL",
            timeframe="1h"
        )
        print(f"Signal: {result['data']['prediction']['signal']}")

        # Test on specific historical date
        result = await test_model_prediction(
            model_name="neuro_mean_reversion_20241201_120000",
            symbol="AAPL",
            timeframe="1h",
            test_date="2024-12-15"
        )

    See Also:
        - get_model_performance(): Get overall model metrics
        - start_training(): Train new models

    Notes:
        - Model must be trained and saved first
        - Data must be available for test_date
        - Use out-of-sample data for true validation
        - Confidence indicates model certainty
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


@trace_mcp_tool("list_operations")
@mcp.tool()
async def list_operations(
    operation_type: Optional[str] = None,
    status: Optional[str] = None,
    active_only: bool = False,
    limit: int = 10,
) -> dict[str, Any]:
    """
    List operations with optional filters.

    Discover operations without prior knowledge. Filter by type, status,
    or show only active operations. Returns most recent operations first.

    Args:
        operation_type: Filter by type. Valid values:
            - "data_load": Data loading operations
            - "training": Neural network training
            - "backtesting": Strategy backtesting
            - None: All types
        status: Filter by status. Valid values:
            - "pending": Queued, not started
            - "running": Currently executing
            - "completed": Finished successfully
            - "failed": Finished with errors
            - "cancelled": Manually cancelled
            - None: All statuses
        active_only: Only show pending + running operations
        limit: Maximum operations to return (default 10, max 100)

    Returns:
        Dict with structure:
        {
            "success": bool,
            "data": [
                {
                    "operation_id": str,
                    "operation_type": str,
                    "status": str,
                    "created_at": str,  # ISO timestamp
                    "progress_percentage": float,
                    "current_step": str,
                    "symbol": Optional[str],
                    "duration_seconds": float
                },
                ...
            ],
            "total_count": int,      # Total matching operations
            "active_count": int,     # Currently running operations
            "returned_count": int    # Number in this response
        }

    Examples:
        # Get all active operations
        result = await list_operations(active_only=True)

        # Get recent training operations
        result = await list_operations(
            operation_type="training",
            status="completed",
            limit=5
        )

    See Also:
        - get_operation_status(): Get detailed progress for specific operation
        - cancel_operation(): Cancel running operation
        - get_operation_results(): Get results after completion

    Notes:
        - Operations sorted by created_at DESC (most recent first)
        - Default limit is 10 to minimize token usage
        - Use active_only=True to find currently running operations
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


@trace_mcp_tool("get_operation_status")
@mcp.tool()
async def get_operation_status(operation_id: str) -> dict[str, Any]:
    """
    Get detailed status and progress of a specific operation.

    Poll for real-time progress updates on data loading, training, or other async
    operations. Returns current status, progress percentage, ETA, and any errors.

    Args:
        operation_id: Unique operation identifier from list_operations() or operation start
            - Format: "op_{type}_{timestamp}" (e.g., "op_training_20241201_123456")

    Returns:
        Dict with structure:
        {
            "success": bool,
            "data": {
                "operation_id": str,
                "operation_type": str,
                "status": str,           # pending/running/completed/failed/cancelled
                "progress_percentage": float,  # 0-100
                "current_step": str,     # Human-readable current activity
                "created_at": str,       # ISO timestamp
                "started_at": Optional[str],
                "completed_at": Optional[str],
                "duration_seconds": float,
                "estimated_completion": Optional[str],  # ETA
                "error": Optional[str],  # Error message if failed
                "metadata": dict         # Operation-specific details
            }
        }

    Raises:
        KTRDRAPIError: If operation_id not found or backend communication fails

    Examples:
        # Poll for training progress
        status = await get_operation_status("op_training_123")
        if status["data"]["status"] == "running":
            print(f"Progress: {status['data']['progress_percentage']}%")

    See Also:
        - list_operations(): Find operation IDs
        - cancel_operation(): Stop running operations
        - get_operation_results(): Get final results after completion

    Notes:
        - Poll every 2-5 seconds for smooth progress tracking
        - Status persists for 24 hours after completion
        - Use metadata field for operation-specific details
    """
    try:
        async with get_api_client() as client:
            result = await client.operations.get_operation_status(operation_id)
            logger.info("Got operation status", operation_id=operation_id)
            return result
    except Exception as e:
        logger.error("Failed to get operation status", error=str(e))
        raise


@trace_mcp_tool("cancel_operation")
@mcp.tool()
async def cancel_operation(
    operation_id: str, reason: Optional[str] = None
) -> dict[str, Any]:
    """
    Cancel a running or pending async operation.

    Stop a long-running data load or training operation. Cancellation is
    graceful - the operation will stop at the next safe checkpoint.

    Args:
        operation_id: Unique operation identifier to cancel
        reason: Optional reason for cancellation (stored in audit trail)
            - Helps debugging and tracking why operations were stopped

    Returns:
        Dict with structure:
        {
            "success": bool,
            "data": {
                "operation_id": str,
                "status": str,       # Should be "cancelled"
                "cancelled_at": str, # ISO timestamp
                "reason": Optional[str]
            }
        }

    Raises:
        KTRDRAPIError: If operation not found, already completed, or cannot be cancelled

    Examples:
        # Cancel a long-running training
        result = await cancel_operation(
            "op_training_123",
            reason="Training taking too long"
        )

    See Also:
        - list_operations(): Find operations to cancel
        - get_operation_status(): Check if cancellation succeeded

    Notes:
        - Only works for 'running' or 'pending' status
        - Cancelled operations cannot be resumed
        - Partial results may be available via get_operation_results()
    """
    try:
        async with get_api_client() as client:
            result = await client.operations.cancel_operation(operation_id, reason)
            logger.info("Cancelled operation", operation_id=operation_id, reason=reason)
            return result
    except Exception as e:
        logger.error("Failed to cancel operation", error=str(e))
        raise


@trace_mcp_tool("get_operation_results")
@mcp.tool()
async def get_operation_results(operation_id: str) -> dict[str, Any]:
    """
    Get results and artifacts from a completed operation.

    Retrieve summary metrics, performance data, and artifact paths from finished
    operations. Useful for analyzing training results or data load statistics.

    Args:
        operation_id: Unique operation identifier from completed operation

    Returns:
        Dict with structure:
        {
            "success": bool,
            "data": {
                "operation_id": str,
                "operation_type": str,
                "status": str,       # completed or failed
                "summary": {
                    "duration_seconds": float,
                    "items_processed": int,
                    "success_rate": float
                },
                "metrics": dict,     # Operation-specific metrics
                "artifacts": {       # Paths to detailed results
                    "model_path": Optional[str],
                    "logs_path": Optional[str],
                    "charts_path": Optional[str]
                },
                "error": Optional[str]  # If status is failed
            }
        }

    Raises:
        KTRDRAPIError: If operation not found or not yet completed

    Examples:
        # Get training results
        results = await get_operation_results("op_training_123")
        print(f"Training accuracy: {results['data']['metrics']['accuracy']}")

    See Also:
        - get_operation_status(): Check if operation is completed
        - list_operations(): Find completed operations

    Notes:
        - Only available for 'completed' or 'failed' status
        - Results persist for 7 days after completion
        - Partial results may be available for cancelled operations
    """
    try:
        async with get_api_client() as client:
            result = await client.operations.get_operation_results(operation_id)
            logger.info("Got operation results", operation_id=operation_id)
            return result
    except Exception as e:
        logger.error("Failed to get operation results", error=str(e))
        raise


@trace_mcp_tool("get_operation_metrics")
@mcp.tool()
async def get_operation_metrics(operation_id: str) -> dict[str, Any]:
    """
    Get detailed training metrics for an operation (M1: API Contract).

    Retrieve real-time training metrics including epoch history, loss curves,
    overfitting indicators, and training health metrics. Useful for monitoring
    training progress and making intelligent decisions about early stopping.

    Args:
        operation_id: Unique operation identifier for training operation

    Returns:
        Dict with structure:
        {
            "success": bool,
            "data": {
                "operation_id": str,
                "operation_type": str,
                "metrics": {
                    "epochs": [              # Epoch-by-epoch history
                        {
                            "epoch": int,
                            "train_loss": float,
                            "train_accuracy": float,
                            "val_loss": float,
                            "val_accuracy": float,
                            "learning_rate": float,
                            "duration": float,
                            "timestamp": str
                        },
                        ...
                    ],
                    "best_epoch": int,               # Epoch with best val_loss
                    "best_val_loss": float,
                    "epochs_since_improvement": int,
                    "is_overfitting": bool,          # Train↓ Val↑ detected
                    "is_plateaued": bool,            # No improvement in N epochs
                    "total_epochs_planned": int,
                    "total_epochs_completed": int
                }
            }
        }

    Raises:
        KTRDRAPIError: If operation not found or not a training operation

    Examples:
        # Monitor training progress
        metrics = await get_operation_metrics("op_training_123")
        if metrics["data"]["metrics"]["is_overfitting"]:
            print("⚠️ Overfitting detected!")
            await cancel_operation("op_training_123", "Overfitting detected")

        # Check training health
        metrics = await get_operation_metrics("op_training_123")
        epochs = metrics["data"]["metrics"]["epochs"]
        if len(epochs) > 0:
            latest = epochs[-1]
            print(f"Epoch {latest['epoch']}: "
                  f"train_loss={latest['train_loss']:.4f}, "
                  f"val_loss={latest['val_loss']:.4f}")

    See Also:
        - get_operation_status(): Get overall progress percentage
        - start_training(): Start training operations
        - cancel_operation(): Stop training if issues detected

    Notes:
        - M1: Returns empty metrics (interface only)
        - M2: Will return populated metrics with real-time updates
        - Only available for training operations
        - Metrics update after each epoch completes
        - Use for intelligent early stopping decisions
    """
    try:
        async with get_api_client() as client:
            result = await client.operations.get_operation_metrics(operation_id)
            logger.info("Got operation metrics", operation_id=operation_id)
            return result
    except Exception as e:
        logger.error("Failed to get operation metrics", error=str(e))
        raise


@trace_mcp_tool("trigger_data_loading")
@mcp.tool()
async def trigger_data_loading(
    symbol: str,
    timeframe: str = "1h",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    mode: str = "local",
) -> dict[str, Any]:
    """
    Load market data from external sources or local cache (async).

    Triggers background data loading and returns immediately with operation_id
    for progress tracking. Use get_operation_status() to monitor the load.

    Args:
        symbol: Trading symbol. Valid formats:
            - Stocks: "AAPL", "MSFT", "TSLA"
            - Forex: "EURUSD", "GBPUSD"
            - Futures: "ES" (requires specific contract month)
        timeframe: Data timeframe. Valid values:
            - "1m": 1 minute bars
            - "5m": 5 minute bars
            - "15m": 15 minute bars
            - "30m": 30 minute bars
            - "1h": 1 hour bars (default)
            - "4h": 4 hour bars
            - "1d": Daily bars
        start_date: Start date in YYYY-MM-DD format
            - Default: 30 days ago
        end_date: End date in YYYY-MM-DD format
            - Default: today
        mode: Loading mode. Valid values:
            - "local": Load from local cache only (fast)
            - "ib": Load from Interactive Brokers (requires IB Gateway)
            - "hybrid": Try local first, fallback to IB

    Returns:
        Dict with structure:
        {
            "success": bool,
            "data": {
                "operation_id": str,  # Use with get_operation_status()
                "symbol": str,
                "timeframe": str,
                "estimated_duration": float  # Seconds
            }
        }

    Raises:
        KTRDRAPIError: If symbol invalid, IB Gateway unavailable (mode=ib), or backend error

    Examples:
        # Load recent AAPL data from local cache
        result = await trigger_data_loading(
            symbol="AAPL",
            timeframe="1h",
            mode="local"
        )
        operation_id = result["data"]["operation_id"]

        # Load historical data from IB Gateway
        result = await trigger_data_loading(
            symbol="EURUSD",
            timeframe="5m",
            start_date="2024-01-01",
            end_date="2024-03-31",
            mode="ib"
        )

    See Also:
        - get_operation_status(): Monitor loading progress
        - get_market_data(): Get cached data immediately (synchronous)
        - get_available_symbols(): Check valid symbol names

    Notes:
        - Local mode is fastest (milliseconds)
        - IB mode requires IB Gateway running and connected
        - Hybrid mode recommended for reliability
        - Data is cached after first load
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


@trace_mcp_tool("start_training")
@mcp.tool()
async def start_training(
    symbols: list[str],
    timeframes: list[str],
    strategy_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    """
    Train a neural network model on market data (async).

    Trains a neural network to predict trading signals using historical market
    data. Training runs in background (can take minutes to hours). Returns
    immediately with operation_id for tracking progress.

    Args:
        symbols: List of trading symbols to train on
            - Example: ["AAPL", "MSFT", "GOOGL"]
            - Multi-symbol training improves generalization
            - Data must be available (use trigger_data_loading first)
        timeframes: List of timeframes to use for features
            - Example: ["1h", "4h", "1d"]
            - Multiple timeframes provide better context
            - Valid values: 1m, 5m, 15m, 30m, 1h, 4h, 1d
        strategy_name: Strategy configuration name
            - Example: "neuro_mean_reversion"
            - Must exist in config/strategies/ directory
            - Defines indicators, fuzzy rules, and neural architecture
        start_date: Training data start date (YYYY-MM-DD)
            - Default: 6 months ago
            - More data = better model (but slower training)
        end_date: Training data end date (YYYY-MM-DD)
            - Default: yesterday
            - Leave gap from today for out-of-sample testing

    Returns:
        Dict with structure:
        {
            "success": bool,
            "data": {
                "operation_id": str,     # Use with get_operation_status()
                "strategy_name": str,
                "symbols": list[str],
                "estimated_duration": float,  # Estimated minutes
                "model_name": str        # Name of model being trained
            }
        }

    Raises:
        KTRDRAPIError: If data unavailable, strategy not found, or backend error

    Examples:
        # Train simple mean reversion model
        result = await start_training(
            symbols=["AAPL"],
            timeframes=["1h"],
            strategy_name="neuro_mean_reversion",
            start_date="2024-01-01",
            end_date="2024-03-01"
        )
        operation_id = result["data"]["operation_id"]

        # Multi-symbol, multi-timeframe training
        result = await start_training(
            symbols=["AAPL", "MSFT", "GOOGL"],
            timeframes=["1h", "4h", "1d"],
            strategy_name="advanced_momentum",
            start_date="2023-01-01",
            end_date="2024-12-31"
        )

    See Also:
        - get_operation_status(): Monitor training progress
        - get_operation_results(): Get model metrics after completion
        - get_available_strategies(): List valid strategy names
        - trigger_data_loading(): Ensure data is available first

    Notes:
        - Training duration: 5-60+ minutes depending on data size
        - GPU acceleration used if available (10x faster)
        - Progress updates every 30 seconds
        - Model saved automatically on completion
        - Can be cancelled mid-training (partial model saved)
    """
    try:
        async with get_api_client() as client:
            result = await client.training.start_neural_training(
                symbols=symbols,
                timeframes=timeframes,
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
            )
            logger.info(
                "Training started",
                symbols=symbols,
                strategy_name=strategy_name,
                operation_id=result.get("operation_id"),
            )
            return result
    except Exception as e:
        logger.error("Failed to start training", error=str(e))
        raise


@trace_mcp_tool("start_backtest")
@mcp.tool()
async def start_backtest(
    strategy_name: str,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    model_path: Optional[str] = None,
    initial_capital: float = 100000.0,
    commission: float = 0.001,
    slippage: float = 0.001,
) -> dict[str, Any]:
    """
    Run a backtest on a trading strategy (async).

    Simulates trading a strategy on historical data. Backtest runs in
    background (can take seconds to minutes). Returns immediately with
    operation_id for tracking progress.

    Args:
        strategy_name: Strategy configuration name
            - Example: "neuro_mean_reversion"
            - Must exist in config/strategies/ directory
            - Defines indicators, fuzzy rules, and neural architecture
        symbol: Trading symbol to backtest
            - Example: "AAPL", "EURUSD"
            - Data must be available (use trigger_data_loading first)
        timeframe: Timeframe for backtest data
            - Example: "1h", "4h", "1d"
            - Valid values: 1m, 5m, 15m, 30m, 1h, 4h, 1d
        start_date: Backtest start date (YYYY-MM-DD)
            - Example: "2024-01-01"
        end_date: Backtest end date (YYYY-MM-DD)
            - Example: "2024-12-31"
        model_path: Optional path to trained model file
            - Example: "models/neuro_mean_reversion/1d_v2/model.pt"
            - If not provided, backend will use latest model for strategy
            - Use this to test specific model versions
            - Relative to project root directory
        initial_capital: Starting capital for simulation
            - Default: 100000.0
            - In strategy's base currency
        commission: Commission rate per trade
            - Default: 0.001 (0.1%)
            - Applied to each buy/sell
        slippage: Slippage rate per trade
            - Default: 0.001 (0.1%)
            - Simulates price impact

    Returns:
        Dict with structure:
        {
            "success": bool,
            "operation_id": str,     # Use with get_operation_status()
            "status": str,           # "started"
            "message": str,
            "symbol": str,
            "timeframe": str,
            "mode": str              # "local" or "remote"
        }

    Raises:
        KTRDRAPIError: If data unavailable, strategy not found, or backend error

    Examples:
        # Basic backtest (uses latest model for strategy)
        result = await start_backtest(
            strategy_name="neuro_mean_reversion",
            symbol="EURUSD",
            timeframe="1d",
            start_date="2024-01-01",
            end_date="2024-12-31"
        )
        operation_id = result["operation_id"]

        # Backtest with specific model version
        result = await start_backtest(
            strategy_name="neuro_mean_reversion",
            symbol="EURUSD",
            timeframe="1d",
            start_date="2024-01-01",
            end_date="2024-12-31",
            model_path="models/neuro_mean_reversion/1d_v2/model.pt"
        )

        # Check progress
        status = await get_operation_status(operation_id)

        # Wait for completion
        while status["data"]["status"] == "running":
            await asyncio.sleep(2)
            status = await get_operation_status(operation_id)

        # Get results
        results = status["data"]["results"]
        print(f"Total return: {results['total_return']:.2%}")
        print(f"Sharpe ratio: {results['sharpe_ratio']:.2f}")
        print(f"Max drawdown: {results['max_drawdown']:.2%}")

    See Also:
        - get_operation_status(): Monitor backtest progress
        - get_operation_results(): Get detailed metrics after completion
        - get_available_strategies(): List valid strategy names
        - trigger_data_loading(): Ensure data is available first

    Notes:
        - Backtest duration: 5 seconds - 5 minutes depending on data size
        - Progress updates every 50 bars
        - Results saved automatically on completion
        - Can be cancelled mid-backtest
        - Local or remote execution based on backend configuration
    """
    try:
        async with get_api_client() as client:
            result = await client.backtesting.start_backtest(
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                model_path=model_path,
                initial_capital=initial_capital,
                commission=commission,
                slippage=slippage,
            )
            logger.info(
                "Backtest started",
                symbol=symbol,
                strategy_name=strategy_name,
                operation_id=result.get("operation_id"),
            )
            return result
    except Exception as e:
        logger.error("Failed to start backtest", error=str(e))
        raise


# Register Agent State Management Tools
register_agent_tools(mcp)

# Register Strategy Management Tools (Task 1.3)
register_strategy_tools(mcp)


class KTRDRMCPServer:
    """MCP Server for KTRDR trading strategy research"""

    def __init__(self):
        logger.info("KTRDR MCP Server initialized")

    def run(self):
        """Run the MCP server"""
        logger.info("Starting KTRDR MCP Server")
        mcp.run()
