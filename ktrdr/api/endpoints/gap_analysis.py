"""
Gap Analysis API Endpoints

Provides comprehensive gap analysis functionality with trading hours awareness.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ktrdr.api.models.base import ApiResponse
from ktrdr.api.models.gap_analysis import (
    BatchGapAnalysisRequest,
    BatchGapAnalysisResponse,
    GapAnalysisMode,
    GapAnalysisRequest,
    GapAnalysisResponse,
)
from ktrdr.api.services.gap_analysis_service import GapAnalysisService
from ktrdr.logging import get_logger

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/gap-analysis", tags=["gap-analysis"])


def get_gap_analysis_service() -> GapAnalysisService:
    """Dependency to get gap analysis service instance."""
    return GapAnalysisService()


@router.get(
    "/data/{symbol}/{timeframe}/gaps",
    response_model=ApiResponse[GapAnalysisResponse],
    summary="Analyze data gaps for symbol/timeframe",
    description="""
    Perform comprehensive gap analysis for a specific symbol and timeframe.

    The analysis classifies gaps as expected (weekends, holidays, non-trading hours)
    or unexpected (requiring investigation) based on trading hours metadata.

    **Analysis Modes:**
    - `normal`: Summary statistics only
    - `extended`: Summary + unexpected gaps only
    - `verbose`: Summary + all gaps (expected and unexpected)

    **Examples:**
    - `/gap-analysis/data/AAPL/1d/gaps?start_date=2024-01-01&end_date=2024-12-31`
    - `/gap-analysis/data/EURUSD/1h/gaps?start_date=2024-01-01&end_date=2024-02-01&mode=extended`
    """,
)
async def analyze_symbol_gaps(
    symbol: str,
    timeframe: str,
    start_date: str = Query(..., description="Analysis start date (ISO format)"),
    end_date: str = Query(..., description="Analysis end date (ISO format)"),
    mode: GapAnalysisMode = Query(
        GapAnalysisMode.NORMAL, description="Analysis detail level"
    ),
    include_expected: bool = Query(
        False, description="Include expected gaps in results"
    ),
    service: GapAnalysisService = Depends(get_gap_analysis_service),
) -> ApiResponse[GapAnalysisResponse]:
    """
    Analyze data gaps for a specific symbol and timeframe.

    Args:
        symbol: Trading symbol (e.g., "AAPL", "EURUSD")
        timeframe: Data timeframe (e.g., "1d", "1h", "5m")
        start_date: Analysis start date in ISO format
        end_date: Analysis end date in ISO format
        mode: Analysis detail level (normal/extended/verbose)
        include_expected: Whether to include expected gaps in results
        service: Gap analysis service dependency

    Returns:
        Gap analysis response with statistics and recommendations
    """
    try:
        # Create request object
        request = GapAnalysisRequest(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            mode=mode,
        )

        logger.info(
            f"Gap analysis requested for {symbol}_{timeframe} ({start_date} to {end_date})"
        )

        # Perform analysis
        result = await service.analyze_gaps(request)

        logger.info(
            f"Gap analysis completed for {symbol}_{timeframe}: "
            f"{result.summary.data_completeness_pct:.1f}% complete, "
            f"{result.summary.total_missing} missing bars"
        )

        return ApiResponse(success=True, data=result, error=None)

    except ValueError as e:
        logger.warning(f"Invalid gap analysis request: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e

    except FileNotFoundError as e:
        logger.warning(f"Data not found for gap analysis: {e}")
        raise HTTPException(
            status_code=404, detail=f"No data found for {symbol}_{timeframe}"
        ) from e

    except Exception as e:
        logger.error(f"Gap analysis failed for {symbol}_{timeframe}: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error during gap analysis"
        ) from e


@router.post(
    "/data/batch",
    response_model=ApiResponse[BatchGapAnalysisResponse],
    summary="Batch gap analysis for multiple symbols",
    description="""
    Perform gap analysis for multiple symbols in a single request.

    Useful for analyzing data quality across multiple instruments with the same timeframe.
    Results include individual symbol analysis plus aggregated statistics.

    **Request Body Example:**
    ```json
    {
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "timeframe": "1d",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "mode": "normal",
        "include_expected": false
    }
    ```
    """,
)
async def analyze_batch_gaps(
    request: BatchGapAnalysisRequest,
    service: GapAnalysisService = Depends(get_gap_analysis_service),
) -> ApiResponse[BatchGapAnalysisResponse]:
    """
    Perform batch gap analysis for multiple symbols.

    Args:
        request: Batch gap analysis request
        service: Gap analysis service dependency

    Returns:
        Batch analysis response with individual and aggregated results
    """
    try:
        logger.info(
            f"Batch gap analysis requested for {len(request.symbols)} symbols "
            f"({request.timeframe}, {request.start_date} to {request.end_date})"
        )

        # Perform batch analysis
        result = await service.analyze_gaps_batch(request)

        success_count = result.request_summary["symbols_successful"]
        error_count = result.request_summary["symbols_failed"]

        logger.info(
            f"Batch gap analysis completed: {success_count} successful, {error_count} failed"
        )

        return ApiResponse(success=True, data=result, error=None)

    except ValueError as e:
        logger.warning(f"Invalid batch gap analysis request: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e

    except Exception as e:
        logger.error(f"Batch gap analysis failed: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error during batch analysis"
        ) from e


@router.get(
    "/data/{symbol}/{timeframe}/summary",
    response_model=ApiResponse[dict[str, Any]],
    summary="Get gap analysis summary only",
    description="""
    Get a quick summary of data completeness for a symbol/timeframe without detailed gap analysis.

    Useful for dashboards and data quality monitoring where only high-level statistics are needed.
    """,
)
async def get_gap_summary(
    symbol: str,
    timeframe: str,
    start_date: str = Query(..., description="Analysis start date (ISO format)"),
    end_date: str = Query(..., description="Analysis end date (ISO format)"),
    service: GapAnalysisService = Depends(get_gap_analysis_service),
) -> ApiResponse[dict[str, Any]]:
    """
    Get gap analysis summary without detailed gap information.

    Args:
        symbol: Trading symbol
        timeframe: Data timeframe
        start_date: Analysis start date
        end_date: Analysis end date
        service: Gap analysis service dependency

    Returns:
        Summary statistics only
    """
    try:
        # Create request with normal mode (summary only)
        request = GapAnalysisRequest(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            mode=GapAnalysisMode.NORMAL,
        )

        # Perform analysis
        result = await service.analyze_gaps(request)

        # Return just the summary and recommendations
        summary_data = {
            "symbol": result.symbol,
            "timeframe": result.timeframe,
            "analysis_period": result.analysis_period,
            "summary": result.summary.dict(),
            "recommendations": result.recommendations,
        }

        return ApiResponse(success=True, data=summary_data, error=None)

    except Exception as e:
        logger.error(f"Gap summary failed for {symbol}_{timeframe}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get(
    "/health",
    response_model=ApiResponse[dict[str, Any]],
    summary="Gap analysis service health check",
    description="Check if gap analysis service is operational and return system information.",
)
async def health_check(
    service: GapAnalysisService = Depends(get_gap_analysis_service),
) -> ApiResponse[dict[str, Any]]:
    """
    Health check for gap analysis service.

    Args:
        service: Gap analysis service dependency

    Returns:
        Health status and system information
    """
    try:
        # Basic health checks
        health_data = {
            "status": "healthy",
            "service": "gap_analysis",
            "data_directory": service.data_dir,
            "gap_classifier_symbols": len(service.gap_classifier.symbol_metadata),
            "supported_timeframes": list(service.timeframe_minutes.keys()),
            "version": "1.0.0",
        }

        return ApiResponse(success=True, data=health_data)

    except Exception as e:
        logger.error(f"Gap analysis health check failed: {e}")
        raise HTTPException(
            status_code=500, detail="Service health check failed"
        ) from e
