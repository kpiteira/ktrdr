"""KTRDR MCP Server - Main entry point"""

import asyncio
import json
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP
import structlog

from .api_client import KTRDRAPIClient, get_api_client
from .storage_manager import get_storage

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
async def check_backend_health() -> Dict[str, Any]:
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
async def get_available_symbols() -> List[Dict[str, Any]]:
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
) -> Dict[str, Any]:
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
async def load_data_from_source(
    symbol: str,
    timeframe: str = "1h",
    mode: str = "tail",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Instruct backend to load data from external sources (e.g., Interactive Brokers)

    Args:
        symbol: Trading symbol (e.g., 'AAPL', 'TSLA')
        timeframe: Data timeframe ('1m', '5m', '1h', '1d')
        mode: Loading mode ('local', 'tail', 'backfill', 'full')
              - 'local': cached data only
              - 'tail': recent data gaps
              - 'backfill': historical data
              - 'full': both historical and recent
        start_date: Start date override (YYYY-MM-DD format, optional)
        end_date: End date override (YYYY-MM-DD format, optional)

    Returns operational metrics about what was loaded.
    """
    try:
        async with get_api_client() as client:
            result = await client.load_data_operation(
                symbol, timeframe, mode, start_date, end_date
            )
            logger.info("Data loading operation completed", symbol=symbol, mode=mode)
            return result
    except Exception as e:
        logger.error("Failed to load data from source", symbol=symbol, error=str(e))
        raise


@mcp.tool()
async def get_data_summary(symbol: str, timeframe: str = "1h") -> Dict[str, Any]:
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
async def create_experiment(
    name: str, description: str = "", config: Optional[Dict] = None
) -> Dict[str, Any]:
    """Create a new research experiment

    Args:
        name: Experiment name
        description: Experiment description
        config: Optional configuration dictionary
    """
    try:
        storage = await get_storage()
        experiment_id = await storage.create_experiment(name, description, config)

        logger.info("Experiment created", id=experiment_id, name=name)
        return {
            "experiment_id": experiment_id,
            "name": name,
            "description": description,
            "status": "created",
            "message": f"Experiment '{name}' created with ID {experiment_id}",
        }
    except Exception as e:
        logger.error("Failed to create experiment", name=name, error=str(e))
        raise


@mcp.tool()
async def list_experiments(status: Optional[str] = None, limit: int = 10) -> List[Dict]:
    """List research experiments

    Args:
        status: Filter by status ('running', 'completed', 'failed')
        limit: Maximum number of experiments to return
    """
    try:
        storage = await get_storage()
        experiments = await storage.list_experiments(status, limit)

        logger.info("Experiments listed", count=len(experiments), status=status)
        return experiments
    except Exception as e:
        logger.error("Failed to list experiments", error=str(e))
        raise


@mcp.tool()
async def save_strategy(
    name: str, config: Dict[str, Any], description: str = ""
) -> Dict[str, Any]:
    """Save a trading strategy configuration

    Args:
        name: Strategy name
        config: Strategy configuration dictionary
        description: Strategy description
    """
    try:
        storage = await get_storage()
        strategy_id = await storage.save_strategy(name, config, description)

        logger.info("Strategy saved", id=strategy_id, name=name)
        return {
            "strategy_id": strategy_id,
            "name": name,
            "description": description,
            "message": f"Strategy '{name}' saved with ID {strategy_id}",
        }
    except Exception as e:
        logger.error("Failed to save strategy", name=name, error=str(e))
        raise


@mcp.tool()
async def load_strategy(name: str) -> Dict[str, Any]:
    """Load a trading strategy configuration by name"""
    try:
        storage = await get_storage()
        strategy = await storage.get_strategy(name)

        if not strategy:
            return {"error": f"Strategy '{name}' not found"}

        logger.info("Strategy loaded", name=name)
        return strategy
    except Exception as e:
        logger.error("Failed to load strategy", name=name, error=str(e))
        raise


@mcp.tool()
async def list_strategies() -> List[Dict]:
    """List all saved trading strategies"""
    try:
        storage = await get_storage()
        strategies = await storage.list_strategies()

        logger.info("Strategies listed", count=len(strategies))
        return strategies
    except Exception as e:
        logger.error("Failed to list strategies", error=str(e))
        raise


@mcp.tool()
async def add_knowledge(
    topic: str,
    content: str,
    source_type: str = "manual",
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Add knowledge to the research knowledge base

    Args:
        topic: Knowledge topic/title
        content: Knowledge content/description
        source_type: Source type ('manual', 'experiment', 'backtest')
        tags: Optional list of tags
    """
    try:
        storage = await get_storage()
        knowledge_id = await storage.add_knowledge(
            topic, content, source_type, tags=tags
        )

        logger.info("Knowledge added", id=knowledge_id, topic=topic)
        return {
            "knowledge_id": knowledge_id,
            "topic": topic,
            "message": f"Knowledge '{topic}' added with ID {knowledge_id}",
        }
    except Exception as e:
        logger.error("Failed to add knowledge", topic=topic, error=str(e))
        raise


@mcp.tool()
async def search_knowledge(
    topic: Optional[str] = None, tags: Optional[List[str]] = None
) -> List[Dict]:
    """Search the knowledge base

    Args:
        topic: Search for topic (partial match)
        tags: Filter by tags
    """
    try:
        storage = await get_storage()
        knowledge = await storage.search_knowledge(topic, tags)

        logger.info("Knowledge searched", count=len(knowledge), topic=topic)
        return knowledge
    except Exception as e:
        logger.error("Failed to search knowledge", error=str(e))
        raise


@mcp.tool()
async def get_available_indicators() -> List[Dict[str, Any]]:
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
async def get_available_strategies() -> List[Dict[str, Any]]:
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
async def start_model_training(
    experiment_id: str,
    symbol: str,
    timeframe: str = "1h",
    training_config: Optional[Dict[str, Any]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Start neural network model training for a trading strategy

    This is a CORE capability that enables autonomous strategy discovery through
    machine learning. The training process creates neural networks that can
    learn complex patterns in market data and generate trading signals.

    Args:
        experiment_id: ID of experiment to track this training
        symbol: Trading symbol to train on (e.g., 'AAPL', 'TSLA')
        timeframe: Data timeframe ('1m', '5m', '1h', '1d')
        training_config: Training configuration (epochs, learning_rate, etc.)
        start_date: Training data start date (YYYY-MM-DD)
        end_date: Training data end date (YYYY-MM-DD)

    Returns:
        Training task status and progress information
    """
    try:
        # Default training configuration
        default_config = {
            "model_type": "mlp",
            "hidden_layers": [64, 32, 16],
            "epochs": 100,
            "learning_rate": 0.001,
            "batch_size": 32,
            "validation_split": 0.2,
            "early_stopping": {"patience": 10, "monitor": "val_accuracy"},
            "optimizer": "adam",
            "dropout_rate": 0.2,
        }

        # Merge with user config
        if training_config:
            default_config.update(training_config)

        # Store training task in experiment
        storage = await get_storage()
        task_id = await storage.create_training_task(
            experiment_id=experiment_id,
            symbol=symbol,
            timeframe=timeframe,
            config=default_config,
            start_date=start_date,
            end_date=end_date,
        )

        # Start training through backend API
        async with get_api_client() as client:
            training_result = await client.start_neural_training(
                symbol=symbol,
                timeframe=timeframe,
                config=default_config,
                start_date=start_date,
                end_date=end_date,
                task_id=task_id,
            )

        logger.info("Model training started", task_id=task_id, symbol=symbol)
        return {
            "task_id": task_id,
            "experiment_id": experiment_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "config": default_config,
            "status": "training_started",
            "backend_response": training_result,
            "message": f"Neural network training started for {symbol} with task ID {task_id}",
        }

    except Exception as e:
        logger.error("Failed to start model training", error=str(e))
        raise


@mcp.tool()
async def get_training_status(task_id: str) -> Dict[str, Any]:
    """Get the status and progress of a neural network training task

    Args:
        task_id: Training task ID returned from start_model_training

    Returns:
        Training status, progress, metrics, and current state
    """
    try:
        storage = await get_storage()
        task_info = await storage.get_training_task(task_id)

        if not task_info:
            return {"error": f"Training task {task_id} not found"}

        # Get live status from backend
        async with get_api_client() as client:
            backend_status = await client.get_training_status(task_id)

        # Combine storage info with live backend status
        result = {
            "task_id": task_id,
            "experiment_id": task_info.get("experiment_id"),
            "symbol": task_info.get("symbol"),
            "timeframe": task_info.get("timeframe"),
            "config": task_info.get("config", {}),
            "created_at": task_info.get("created_at"),
            "backend_status": backend_status,
            "status": backend_status.get("status", "unknown"),
        }

        logger.info(
            "Training status retrieved", task_id=task_id, status=result["status"]
        )
        return result

    except Exception as e:
        logger.error("Failed to get training status", task_id=task_id, error=str(e))
        raise


@mcp.tool()
async def list_training_tasks(
    experiment_id: Optional[str] = None, status: Optional[str] = None, limit: int = 10
) -> List[Dict[str, Any]]:
    """List neural network training tasks

    Args:
        experiment_id: Filter by experiment ID
        status: Filter by status ('pending', 'training', 'completed', 'failed')
        limit: Maximum number of tasks to return

    Returns:
        List of training tasks with their status and metrics
    """
    try:
        storage = await get_storage()
        tasks = await storage.list_training_tasks(experiment_id, status, limit)

        logger.info(
            "Training tasks listed", count=len(tasks), experiment_id=experiment_id
        )
        return tasks

    except Exception as e:
        logger.error("Failed to list training tasks", error=str(e))
        raise


@mcp.tool()
async def get_model_performance(task_id: str) -> Dict[str, Any]:
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
async def save_trained_model(
    task_id: str, model_name: str, description: str = ""
) -> Dict[str, Any]:
    """Save a trained neural network model for later use

    Args:
        task_id: Training task ID
        model_name: Name to save the model under
        description: Model description

    Returns:
        Model save confirmation and metadata
    """
    try:
        storage = await get_storage()

        # Get training task info
        task_info = await storage.get_training_task(task_id)
        if not task_info:
            return {"error": f"Training task {task_id} not found"}

        # Save model through backend
        async with get_api_client() as client:
            save_result = await client.save_trained_model(
                task_id, model_name, description
            )

        # Record in storage
        model_id = await storage.save_model_record(
            name=model_name,
            task_id=task_id,
            description=description,
            config=task_info.get("config", {}),
            symbol=task_info.get("symbol"),
            timeframe=task_info.get("timeframe"),
        )

        logger.info("Model saved", model_id=model_id, name=model_name)
        return {
            "model_id": model_id,
            "model_name": model_name,
            "task_id": task_id,
            "backend_response": save_result,
            "message": f"Model '{model_name}' saved successfully",
        }

    except Exception as e:
        logger.error("Failed to save trained model", task_id=task_id, error=str(e))
        raise


@mcp.tool()
async def load_trained_model(model_name: str) -> Dict[str, Any]:
    """Load a previously saved neural network model

    Args:
        model_name: Name of the model to load

    Returns:
        Model metadata and load confirmation
    """
    try:
        storage = await get_storage()
        model_info = await storage.get_model_record(model_name)

        if not model_info:
            return {"error": f"Model '{model_name}' not found"}

        # Load model through backend
        async with get_api_client() as client:
            load_result = await client.load_trained_model(model_name)

        logger.info("Model loaded", name=model_name)
        return {
            "model_name": model_name,
            "model_info": model_info,
            "backend_response": load_result,
            "message": f"Model '{model_name}' loaded successfully",
        }

    except Exception as e:
        logger.error("Failed to load trained model", name=model_name, error=str(e))
        raise


@mcp.tool()
async def test_model_prediction(
    model_name: str, symbol: str, timeframe: str = "1h", test_date: Optional[str] = None
) -> Dict[str, Any]:
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
async def run_strategy_backtest(
    experiment_id: str,
    strategy_name: str,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 10000.0,
    backtest_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a comprehensive backtest for a trading strategy

    This is a CORE capability that enables rigorous strategy evaluation through
    historical market simulation. Backtesting validates strategy performance
    across different market conditions and time periods.

    Args:
        experiment_id: ID of experiment to track this backtest
        strategy_name: Name of existing strategy to backtest
        symbol: Trading symbol to backtest on (e.g., 'AAPL', 'TSLA')
        timeframe: Data timeframe ('1m', '5m', '1h', '1d')
        start_date: Backtest start date (YYYY-MM-DD)
        end_date: Backtest end date (YYYY-MM-DD)
        initial_capital: Starting capital for the backtest
        backtest_name: Optional name for this backtest run

    Returns:
        Backtest task status and preliminary results
    """
    try:
        # Generate backtest name if not provided
        if not backtest_name:
            backtest_name = f"{strategy_name}_{symbol}_{start_date}_{end_date}"

        # Store backtest task in experiment
        storage = await get_storage()

        # Start backtest through backend API (CORRECTED API CALL)
        async with get_api_client() as client:
            backtest_result = await client.run_backtest(
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
            )

        logger.info("Backtest started", strategy_name=strategy_name, symbol=symbol)
        return {
            "experiment_id": experiment_id,
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "backend_response": backtest_result,
            "status": "started",
            "message": f"Backtest started for {strategy_name} on {symbol} from {start_date} to {end_date}",
        }

    except Exception as e:
        logger.error("Failed to run strategy backtest", error=str(e))
        raise


@mcp.tool()
async def get_backtest_results(backtest_id: int) -> Dict[str, Any]:
    """Get detailed results from a completed backtest

    Args:
        backtest_id: Backtest ID returned from run_strategy_backtest

    Returns:
        Comprehensive backtest results including trades, metrics, and analysis
    """
    try:
        storage = await get_storage()

        # Get backtest from storage
        backtests = await storage.get_backtest_history()
        backtest = None
        for bt in backtests:
            if bt["id"] == backtest_id:
                backtest = bt
                break

        if not backtest:
            return {"error": f"Backtest {backtest_id} not found"}

        # Parse stored results
        results = json.loads(backtest["results"]) if backtest["results"] else {}
        metrics = json.loads(backtest["metrics"]) if backtest["metrics"] else {}

        logger.info("Backtest results retrieved", backtest_id=backtest_id)
        return {
            "backtest_id": backtest_id,
            "symbol": backtest["symbol"],
            "start_date": backtest["start_date"],
            "end_date": backtest["end_date"],
            "results": results,
            "metrics": metrics,
            "created_at": backtest["created_at"],
        }

    except Exception as e:
        logger.error(
            "Failed to get backtest results", backtest_id=backtest_id, error=str(e)
        )
        raise


@mcp.tool()
async def compare_backtests(
    backtest_ids: List[int], metrics: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Compare performance metrics across multiple backtests

    Args:
        backtest_ids: List of backtest IDs to compare
        metrics: Specific metrics to compare (e.g., ['total_return', 'sharpe_ratio'])

    Returns:
        Comparative analysis showing relative performance across backtests
    """
    try:
        storage = await get_storage()

        # Default metrics to compare
        if not metrics:
            metrics = [
                "total_return",
                "annualized_return",
                "volatility",
                "sharpe_ratio",
                "max_drawdown",
                "win_rate",
                "profit_factor",
            ]

        # Get all backtests
        all_backtests = await storage.get_backtest_history()
        selected_backtests = []

        for backtest_id in backtest_ids:
            for bt in all_backtests:
                if bt["id"] == backtest_id:
                    # Parse metrics
                    bt_metrics = json.loads(bt["metrics"]) if bt["metrics"] else {}
                    selected_backtests.append(
                        {
                            "id": bt["id"],
                            "symbol": bt["symbol"],
                            "start_date": bt["start_date"],
                            "end_date": bt["end_date"],
                            "metrics": bt_metrics,
                        }
                    )
                    break

        if not selected_backtests:
            return {"error": "No valid backtests found for comparison"}

        # Build comparison table
        comparison = {
            "backtests": selected_backtests,
            "metric_comparison": {},
            "rankings": {},
        }

        # Compare each metric
        for metric in metrics:
            values = []
            for bt in selected_backtests:
                value = bt["metrics"].get(metric)
                if value is not None:
                    values.append({"backtest_id": bt["id"], "value": value})

            if values:
                # Sort by value (descending for most metrics)
                reverse_sort = metric not in [
                    "volatility",
                    "max_drawdown",
                ]  # Lower is better for these
                values.sort(key=lambda x: x["value"], reverse=reverse_sort)

                comparison["metric_comparison"][metric] = values
                comparison["rankings"][metric] = [v["backtest_id"] for v in values]

        logger.info("Backtest comparison completed", count=len(selected_backtests))
        return comparison

    except Exception as e:
        logger.error("Failed to compare backtests", error=str(e))
        raise


@mcp.tool()
async def run_walk_forward_analysis(
    experiment_id: str,
    strategy_config: Dict[str, Any],
    symbol: str,
    start_date: str,
    end_date: str,
    train_period_months: int = 12,
    test_period_months: int = 3,
) -> Dict[str, Any]:
    """Run walk-forward analysis to test strategy robustness over time

    Walk-forward analysis divides the data into multiple training and testing periods
    to evaluate how well a strategy adapts to changing market conditions.

    Args:
        experiment_id: ID of experiment to track this analysis
        strategy_config: Strategy configuration to test
        symbol: Trading symbol to analyze
        start_date: Analysis start date (YYYY-MM-DD)
        end_date: Analysis end date (YYYY-MM-DD)
        train_period_months: Months of data for training each iteration
        test_period_months: Months of data for testing each iteration

    Returns:
        Walk-forward analysis results with performance across time periods
    """
    try:
        # This would be implemented with multiple backtests across rolling windows
        # For now, return a structured response indicating the capability

        from datetime import datetime, timedelta
        import dateutil.relativedelta as rd

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        # Calculate periods
        periods = []
        current_start = start_dt

        while current_start < end_dt:
            train_end = current_start + rd.relativedelta(months=train_period_months)
            test_end = train_end + rd.relativedelta(months=test_period_months)

            if test_end > end_dt:
                test_end = end_dt

            periods.append(
                {
                    "train_start": current_start.strftime("%Y-%m-%d"),
                    "train_end": train_end.strftime("%Y-%m-%d"),
                    "test_start": train_end.strftime("%Y-%m-%d"),
                    "test_end": test_end.strftime("%Y-%m-%d"),
                }
            )

            # Move to next period (overlap by moving only test_period forward)
            current_start = train_end

            if current_start >= end_dt:
                break

        logger.info(
            "Walk-forward analysis planned", symbol=symbol, periods=len(periods)
        )
        return {
            "experiment_id": experiment_id,
            "symbol": symbol,
            "strategy_config": strategy_config,
            "periods_planned": len(periods),
            "periods": periods,
            "status": "analysis_framework_ready",
            "message": f"Walk-forward analysis framework prepared with {len(periods)} periods",
            "note": "Full implementation requires backend integration for iterative training/testing",
        }

    except Exception as e:
        logger.error("Failed to run walk-forward analysis", error=str(e))
        raise


@mcp.tool()
async def get_backtest_performance_summary(
    symbol: Optional[str] = None, strategy_name: Optional[str] = None, limit: int = 10
) -> Dict[str, Any]:
    """Get a performance summary of recent backtests

    Args:
        symbol: Filter by trading symbol
        strategy_name: Filter by strategy name
        limit: Maximum number of backtests to include

    Returns:
        Summary of backtest performance with key metrics and insights
    """
    try:
        storage = await get_storage()

        # Get backtest history
        backtests = await storage.get_backtest_history(symbol=symbol)

        if limit:
            backtests = backtests[:limit]

        if not backtests:
            return {"message": "No backtests found", "backtests": []}

        # Calculate summary statistics
        summary = {
            "total_backtests": len(backtests),
            "symbols_tested": list(set(bt["symbol"] for bt in backtests)),
            "date_range": {
                "earliest": min(bt["start_date"] for bt in backtests),
                "latest": max(bt["end_date"] for bt in backtests),
            },
            "backtests": [],
        }

        # Process each backtest
        for bt in backtests:
            metrics = json.loads(bt["metrics"]) if bt["metrics"] else {}

            backtest_summary = {
                "id": bt["id"],
                "symbol": bt["symbol"],
                "period": f"{bt['start_date']} to {bt['end_date']}",
                "key_metrics": {
                    "total_return": metrics.get("total_return"),
                    "sharpe_ratio": metrics.get("sharpe_ratio"),
                    "max_drawdown": metrics.get("max_drawdown"),
                    "win_rate": metrics.get("win_rate"),
                },
                "created_at": bt["created_at"],
            }
            summary["backtests"].append(backtest_summary)

        logger.info("Backtest performance summary generated", count=len(backtests))
        return summary

    except Exception as e:
        logger.error("Failed to get backtest performance summary", error=str(e))
        raise


class KTRDRMCPServer:
    """MCP Server for KTRDR trading strategy research"""

    def __init__(self):
        logger.info("KTRDR MCP Server initialized")

    def run(self):
        """Run the MCP server"""
        logger.info("Starting KTRDR MCP Server")
        mcp.run()
