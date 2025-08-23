"""
Backtesting endpoints for the KTRDR API.

This module implements the API endpoints for running backtests and retrieving results.
"""

from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, field_validator

from ktrdr import get_logger
from ktrdr.api.services.backtesting_service import BacktestingService
from ktrdr.api.services.operations_service import get_operations_service
from ktrdr.errors import DataError, ValidationError

logger = get_logger(__name__)

# Create router for backtesting endpoints
router = APIRouter(prefix="/backtests")


# Request/Response models
class BacktestRequest(BaseModel):
    """Request model for starting a backtest."""

    strategy_name: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    commission: float = 0.001
    slippage: float = 0.0005
    data_mode: str = "local"

    @field_validator("strategy_name", "symbol", "timeframe", "start_date", "end_date")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Validate that required string fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class BacktestStartResponse(BaseModel):
    """Response model for backtest start."""

    success: bool
    backtest_id: str
    status: str
    message: str


class BacktestStatusResponse(BaseModel):
    """Response model for backtest status."""

    success: bool
    backtest_id: str
    strategy_name: str
    symbol: str
    timeframe: str
    status: str
    progress: int
    started_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


class BacktestMetrics(BaseModel):
    """Backtest performance metrics."""

    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int


class BacktestSummary(BaseModel):
    """Backtest summary information."""

    initial_capital: float
    final_value: float
    total_pnl: float
    winning_trades: int
    losing_trades: int


class BacktestResultsResponse(BaseModel):
    """Response model for backtest results."""

    success: bool
    backtest_id: str
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    metrics: BacktestMetrics
    summary: BacktestSummary


class TradeRecord(BaseModel):
    """Individual trade record."""

    trade_id: Optional[str] = None
    entry_time: str
    exit_time: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_percent: float
    entry_reason: Optional[str] = None
    exit_reason: Optional[str] = None


class BacktestTradesResponse(BaseModel):
    """Response model for backtest trades."""

    success: bool
    backtest_id: str
    trades: list[TradeRecord]


class EquityCurveResponse(BaseModel):
    """Response model for equity curve data."""

    success: bool
    backtest_id: str
    timestamps: list[str]
    values: list[float]
    drawdowns: list[float]


# Singleton backtesting service instance
_backtesting_service: Optional[BacktestingService] = None


# Dependency for backtesting service
async def get_backtesting_service() -> BacktestingService:
    """Get backtesting service instance (singleton)."""
    global _backtesting_service
    if _backtesting_service is None:
        _backtesting_service = BacktestingService(
            operations_service=get_operations_service()
        )
    return _backtesting_service


@router.post("/", response_model=BacktestStartResponse)
async def start_backtest(
    request: BacktestRequest,
    background_tasks: BackgroundTasks,
    service: BacktestingService = Depends(get_backtesting_service),
) -> BacktestStartResponse:
    """
    Start a new backtest run.

    This endpoint initiates a backtest for a specified strategy and returns
    immediately with a backtest ID. The actual backtest runs asynchronously
    in the background.
    """
    try:
        result = await service.start_backtest(
            strategy_name=request.strategy_name,
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
        )

        return BacktestStartResponse(
            success=True,
            backtest_id=result["backtest_id"],
            status=result["status"],
            message=result["message"],
        )

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start backtest: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start backtest")


@router.get("/{backtest_id}", response_model=BacktestStatusResponse)
async def get_backtest_status(
    backtest_id: str, service: BacktestingService = Depends(get_backtesting_service)
) -> BacktestStatusResponse:
    """
    Get the current status of a backtest.

    This endpoint returns the current status and progress of a running or
    completed backtest.
    """
    try:
        status = await service.get_backtest_status(backtest_id)

        return BacktestStatusResponse(
            success=True,
            backtest_id=status["backtest_id"],
            strategy_name=status["strategy_name"],
            symbol=status["symbol"],
            timeframe=status["timeframe"],
            status=status["status"],
            progress=status["progress"],
            started_at=status["started_at"],
            completed_at=status["completed_at"],
            error=status["error"],
        )

    except ValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get backtest status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get backtest status")


@router.get("/{backtest_id}/results", response_model=BacktestResultsResponse)
async def get_backtest_results(
    backtest_id: str, service: BacktestingService = Depends(get_backtesting_service)
) -> BacktestResultsResponse:
    """
    Get the full results of a completed backtest.

    This endpoint returns detailed performance metrics and summary statistics
    for a completed backtest.
    """
    try:
        results = await service.get_backtest_results(backtest_id)

        return BacktestResultsResponse(
            success=True,
            backtest_id=results["backtest_id"],
            strategy_name=results["strategy_name"],
            symbol=results["symbol"],
            timeframe=results["timeframe"],
            start_date=results["start_date"],
            end_date=results["end_date"],
            metrics=BacktestMetrics(**results["metrics"]),
            summary=BacktestSummary(**results["summary"]),
        )

    except ValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DataError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get backtest results: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get backtest results")


@router.get("/{backtest_id}/trades", response_model=BacktestTradesResponse)
async def get_backtest_trades(
    backtest_id: str, service: BacktestingService = Depends(get_backtesting_service)
) -> BacktestTradesResponse:
    """
    Get the list of trades from a backtest.

    This endpoint returns all trades executed during a backtest, including
    entry/exit times, prices, and P&L information.
    """
    try:
        trades = await service.get_backtest_trades(backtest_id)

        return BacktestTradesResponse(
            success=True,
            backtest_id=backtest_id,
            trades=[TradeRecord(**trade) for trade in trades],
        )

    except ValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get backtest trades: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get backtest trades")


@router.get("/{backtest_id}/equity_curve", response_model=EquityCurveResponse)
async def get_equity_curve(
    backtest_id: str, service: BacktestingService = Depends(get_backtesting_service)
) -> EquityCurveResponse:
    """
    Get the equity curve data from a backtest.

    This endpoint returns time series data showing the portfolio value
    and drawdowns over the course of the backtest.
    """
    try:
        equity_data = await service.get_equity_curve(backtest_id)

        return EquityCurveResponse(
            success=True,
            backtest_id=backtest_id,
            timestamps=equity_data["timestamps"],
            values=equity_data["values"],
            drawdowns=equity_data["drawdowns"],
        )

    except ValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DataError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get equity curve: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get equity curve")
