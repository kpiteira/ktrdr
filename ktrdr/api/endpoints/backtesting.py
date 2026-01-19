"""
Backtesting endpoints for the KTRDR API.

This module implements the API endpoints for running backtests following
the async operations architecture pattern (Phase 2 Task 2.4).

Key Design Principles:
- POST /backtests/start returns operation_id immediately
- All status tracking via existing /operations/* endpoints
- Uses BacktestingService from ktrdr.backtesting (not ktrdr.api.services)
- Follows same pattern as training endpoints
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ktrdr import get_logger
from ktrdr.api.endpoints.workers import get_worker_registry
from ktrdr.api.models.backtesting import BacktestStartRequest, BacktestStartResponse
from ktrdr.api.services.training import extract_symbols_timeframes_from_strategy
from ktrdr.backtesting.backtesting_service import BacktestingService
from ktrdr.errors import (
    ConfigurationError,
    DataError,
    ValidationError,
    WorkerUnavailableError,
)

logger = get_logger(__name__)

# Create router for backtesting endpoints
router = APIRouter(prefix="/backtests")

# Singleton backtesting service instance
_backtesting_service: Optional[BacktestingService] = None


# Dependency for backtesting service
async def get_backtesting_service() -> BacktestingService:
    """Get backtesting service instance (singleton - distributed-only mode)."""
    global _backtesting_service
    if _backtesting_service is None:
        # WorkerRegistry is required for distributed-only mode
        worker_registry = get_worker_registry()
        _backtesting_service = BacktestingService(worker_registry=worker_registry)
    return _backtesting_service


@router.post("/start", response_model=BacktestStartResponse)
async def start_backtest(
    request: BacktestStartRequest,
    service: BacktestingService = Depends(get_backtesting_service),
) -> BacktestStartResponse:
    """
    Start a new backtest operation.

    This endpoint initiates a backtest and returns immediately with an operation_id.
    The actual backtest runs asynchronously in the background (local or remote mode).

    Progress/status tracking:
      GET /api/v1/operations/{operation_id}

    Args:
        request: Backtest configuration
        service: BacktestingService dependency

    Returns:
        BacktestStartResponse with operation_id and status

    Raises:
        HTTPException: 400 for validation errors, 500 for internal errors
    """
    try:
        # Parse dates
        start_date = datetime.fromisoformat(request.start_date)
        end_date = datetime.fromisoformat(request.end_date)

        # Call ktrdr.backtesting.BacktestingService (not api.services!)
        strategy_config_path = f"strategies/{request.strategy_name}.yaml"

        # Resolve symbol/timeframe - use request values or extract from strategy config
        resolved_symbol = request.symbol
        resolved_timeframe = request.timeframe

        if resolved_symbol is None or resolved_timeframe is None:
            logger.info(
                f"Extracting symbol/timeframe from strategy config: {request.strategy_name}"
            )
            config_symbols, config_timeframes = (
                extract_symbols_timeframes_from_strategy(request.strategy_name)
            )

            if resolved_symbol is None:
                resolved_symbol = config_symbols[0] if config_symbols else None
                logger.info(f"Using symbol from strategy config: {resolved_symbol}")

            if resolved_timeframe is None:
                resolved_timeframe = config_timeframes[0] if config_timeframes else None
                logger.info(
                    f"Using timeframe from strategy config: {resolved_timeframe}"
                )

        # Validate we have both symbol and timeframe (either from request or strategy)
        if not resolved_symbol or not resolved_timeframe:
            raise ValidationError(
                "Symbol and timeframe must be provided or defined in strategy config"
            )

        # Use explicit model_path if provided (for v3 models), otherwise auto-discover
        model_path = request.model_path

        result = await service.run_backtest(
            symbol=resolved_symbol,
            timeframe=resolved_timeframe,
            strategy_config_path=strategy_config_path,
            model_path=model_path,
            start_date=start_date,
            end_date=end_date,
            initial_capital=request.initial_capital,
            commission=request.commission,
            slippage=request.slippage,
        )

        return BacktestStartResponse(
            success=result["success"],
            operation_id=result["operation_id"],
            status=result["status"],
            message=result["message"],
            symbol=result["symbol"],
            timeframe=result["timeframe"],
            mode=result.get("mode"),
        )

    except WorkerUnavailableError as e:
        # Return 503 with diagnostic context for worker unavailability
        logger.warning(f"No backtest workers available: {e.details}")
        raise HTTPException(status_code=503, detail=e.to_response_dict()) from e
    except ConfigurationError as e:
        logger.error(f"Configuration error starting backtest: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValidationError as e:
        logger.error(f"Validation error starting backtest: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DataError as e:
        logger.error(f"Data error starting backtest: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e
    except ValueError as e:
        logger.error(f"Value error starting backtest: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to start backtest: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start backtest") from e
