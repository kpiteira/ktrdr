"""
Multi-timeframe decision endpoints for the KTRDR API.

This module implements API endpoints for multi-timeframe trading decision making,
providing comprehensive analysis across multiple timeframes with consensus building.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator
import pandas as pd
from datetime import datetime

from ktrdr import get_logger
from ktrdr.decision.multi_timeframe_orchestrator import (
    MultiTimeframeDecisionOrchestrator,
    MultiTimeframeConsensus,
    TimeframeDecision,
    create_multi_timeframe_decision_orchestrator,
)
from ktrdr.decision.base import Signal, Position
from ktrdr.data.data_manager import DataManager

# Note: dependencies removed for simplicity

logger = get_logger(__name__)

# Create router for multi-timeframe decision endpoints
router = APIRouter(prefix="/multi-timeframe-decisions")


# Request models
class MultiTimeframeDecisionRequest(BaseModel):
    """Request model for multi-timeframe trading decision."""

    symbol: str = Field(..., description="Trading symbol (e.g., 'AAPL')")
    strategy_config_path: str = Field(
        ..., description="Path to strategy configuration file"
    )
    timeframes: List[str] = Field(
        default=["1h", "4h", "1d"], description="List of timeframes to analyze"
    )
    mode: str = Field(
        default="backtest", description="Operating mode: backtest, paper, or live"
    )
    model_path: Optional[str] = Field(
        None, description="Path to multi-timeframe model (optional)"
    )
    portfolio_state: Optional[Dict[str, Any]] = Field(
        default={"total_value": 100000, "available_capital": 50000},
        description="Current portfolio state",
    )

    @field_validator("timeframes")
    @classmethod
    def validate_timeframes(cls, v):
        valid_timeframes = [
            "1m",
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "4h",
            "1d",
            "1w",
            "1M",
        ]
        for tf in v:
            if tf not in valid_timeframes:
                raise ValueError(
                    f"Invalid timeframe: {tf}. Must be one of {valid_timeframes}"
                )
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v):
        valid_modes = ["backtest", "paper", "live"]
        if v not in valid_modes:
            raise ValueError(f"Invalid mode: {v}. Must be one of {valid_modes}")
        return v


class TimeframeAnalysisRequest(BaseModel):
    """Request model for timeframe analysis."""

    symbol: str = Field(..., description="Trading symbol")
    strategy_config_path: str = Field(..., description="Path to strategy configuration")
    timeframes: List[str] = Field(default=["1h", "4h", "1d"])
    lookback_periods: int = Field(
        default=100, description="Number of periods to analyze"
    )


# Response models
class TimeframeDecisionResponse(BaseModel):
    """Response model for individual timeframe decision."""

    timeframe: str
    signal: str
    confidence: float
    weight: float
    data_quality: float
    reasoning: Dict[str, Any]


class MultiTimeframeConsensusResponse(BaseModel):
    """Response model for multi-timeframe consensus."""

    final_signal: str
    consensus_confidence: float
    agreement_score: float
    conflicting_timeframes: List[str]
    primary_timeframe_influence: float
    consensus_method: str
    timeframe_decisions: Dict[str, TimeframeDecisionResponse]
    reasoning: Dict[str, Any]


class MultiTimeframeDecisionResponse(BaseModel):
    """Response model for complete multi-timeframe decision."""

    success: bool = True
    symbol: str
    timestamp: str
    decision: Dict[str, Any]
    consensus: MultiTimeframeConsensusResponse
    metadata: Dict[str, Any]


class TimeframeAnalysisResponse(BaseModel):
    """Response model for timeframe analysis."""

    success: bool = True
    symbol: str
    timeframes: List[str]
    primary_timeframe: str
    timeframe_weights: Dict[str, float]
    latest_consensus: Optional[MultiTimeframeConsensusResponse] = None
    timeframe_breakdown: Optional[Dict[str, Dict[str, Any]]] = None
    recent_decisions_count: int
    analysis_timestamp: str


class TimeframeDataStatus(BaseModel):
    """Status of timeframe data availability."""

    timeframe: str
    available: bool
    last_update: Optional[str] = None
    record_count: int
    data_quality_score: float
    freshness_score: float


class MultiTimeframeDataStatusResponse(BaseModel):
    """Response model for multi-timeframe data status."""

    success: bool = True
    symbol: str
    timeframe_status: List[TimeframeDataStatus]
    overall_data_quality: float
    ready_for_analysis: bool


class MultiTimeframeStrategyListResponse(BaseModel):
    """Response model for multi-timeframe strategy listing."""

    success: bool = True
    strategies: List[Dict[str, Any]]


# Service function to create orchestrator
def create_orchestrator(
    strategy_config_path: str,
    timeframes: List[str],
    mode: str = "backtest",
    model_path: Optional[str] = None,
) -> MultiTimeframeDecisionOrchestrator:
    """Create multi-timeframe decision orchestrator."""
    try:
        config_path = Path(strategy_config_path)
        if not config_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Strategy configuration not found: {strategy_config_path}",
            )

        orchestrator = create_multi_timeframe_decision_orchestrator(
            strategy_config_path=str(config_path),
            model_path=model_path,
            mode=mode,
            timeframes=timeframes,
        )

        return orchestrator

    except Exception as e:
        logger.error(f"Failed to create multi-timeframe orchestrator: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize multi-timeframe orchestrator: {str(e)}",
        )


def prepare_timeframe_data(
    symbol: str, timeframes: List[str], lookback_periods: int = 100
) -> Dict[str, pd.DataFrame]:
    """Prepare data for all requested timeframes."""
    try:
        data_manager = DataManager()
        timeframe_data = {}

        for timeframe in timeframes:
            try:
                # Get data for this timeframe
                data = data_manager.get_data(
                    symbol=symbol, timeframe=timeframe, rows=lookback_periods
                )

                if data is not None and not data.empty:
                    timeframe_data[timeframe] = data
                else:
                    logger.warning(f"No data available for {symbol} {timeframe}")

            except Exception as e:
                logger.error(f"Failed to load data for {symbol} {timeframe}: {e}")
                continue

        return timeframe_data

    except Exception as e:
        logger.error(f"Failed to prepare timeframe data: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to load timeframe data: {str(e)}"
        )


# Endpoints
@router.post("/decide", response_model=MultiTimeframeDecisionResponse)
async def make_multi_timeframe_decision(request: MultiTimeframeDecisionRequest):
    """
    Generate a trading decision using multi-timeframe analysis.

    This endpoint coordinates decision making across multiple timeframes,
    builds consensus, and returns a comprehensive trading decision with
    detailed reasoning and metadata.
    """
    logger.info(f"Making multi-timeframe decision for {request.symbol}")

    try:
        # Create orchestrator
        orchestrator = create_orchestrator(
            strategy_config_path=request.strategy_config_path,
            timeframes=request.timeframes,
            mode=request.mode,
            model_path=request.model_path,
        )

        # Prepare timeframe data
        timeframe_data = prepare_timeframe_data(
            symbol=request.symbol, timeframes=request.timeframes
        )

        if not timeframe_data:
            raise HTTPException(
                status_code=404,
                detail=f"No data available for {request.symbol} in any requested timeframes",
            )

        # Generate multi-timeframe decision
        decision = orchestrator.make_multi_timeframe_decision(
            symbol=request.symbol,
            timeframe_data=timeframe_data,
            portfolio_state=request.portfolio_state,
        )

        # Get consensus history for response
        consensus_history = orchestrator.get_consensus_history(limit=1)
        latest_consensus = consensus_history[0] if consensus_history else None

        # Convert consensus to response format
        consensus_response = None
        if latest_consensus:
            timeframe_decisions_response = {}
            for tf, tf_decision in latest_consensus.timeframe_decisions.items():
                timeframe_decisions_response[tf] = TimeframeDecisionResponse(
                    timeframe=tf_decision.timeframe,
                    signal=tf_decision.signal.value,
                    confidence=tf_decision.confidence,
                    weight=tf_decision.weight,
                    data_quality=tf_decision.data_quality,
                    reasoning=tf_decision.reasoning,
                )

            consensus_response = MultiTimeframeConsensusResponse(
                final_signal=latest_consensus.final_signal.value,
                consensus_confidence=latest_consensus.consensus_confidence,
                agreement_score=latest_consensus.agreement_score,
                conflicting_timeframes=latest_consensus.conflicting_timeframes,
                primary_timeframe_influence=latest_consensus.primary_timeframe_influence,
                consensus_method=latest_consensus.consensus_method,
                timeframe_decisions=timeframe_decisions_response,
                reasoning=latest_consensus.reasoning,
            )

        return MultiTimeframeDecisionResponse(
            symbol=request.symbol,
            timestamp=decision.timestamp.isoformat(),
            decision={
                "signal": decision.signal.value,
                "confidence": decision.confidence,
                "current_position": decision.current_position.value,
                "reasoning": decision.reasoning,
            },
            consensus=consensus_response,
            metadata={
                "timeframes": request.timeframes,
                "mode": request.mode,
                "model_path": request.model_path,
                "portfolio_state": request.portfolio_state,
                "orchestrator_type": "multi_timeframe",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to make multi-timeframe decision: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate multi-timeframe decision: {str(e)}",
        )


@router.get("/analyze/{symbol}", response_model=TimeframeAnalysisResponse)
async def analyze_timeframe_performance(
    symbol: str,
    strategy_config_path: str = Query(
        ..., description="Path to strategy configuration"
    ),
    timeframes: List[str] = Query(default=["1h", "4h", "1d"]),
    mode: str = Query(default="backtest"),
):
    """
    Analyze timeframe performance and consensus patterns for a symbol.

    Provides detailed analysis of how different timeframes contribute to
    decision making, including agreement patterns and performance metrics.
    """
    logger.info(f"Analyzing timeframe performance for {symbol}")

    try:
        # Create orchestrator
        orchestrator = create_orchestrator(
            strategy_config_path=strategy_config_path, timeframes=timeframes, mode=mode
        )

        # Get timeframe analysis
        analysis = orchestrator.get_timeframe_analysis(symbol)

        # Convert latest consensus if available
        latest_consensus_response = None
        if "latest_consensus" in analysis:
            consensus_data = analysis["latest_consensus"]

            # Get recent consensus for detailed breakdown
            consensus_history = orchestrator.get_consensus_history(
                symbol=symbol, limit=1
            )
            if consensus_history:
                latest_consensus = consensus_history[0]

                timeframe_decisions_response = {}
                for tf, tf_decision in latest_consensus.timeframe_decisions.items():
                    timeframe_decisions_response[tf] = TimeframeDecisionResponse(
                        timeframe=tf_decision.timeframe,
                        signal=tf_decision.signal.value,
                        confidence=tf_decision.confidence,
                        weight=tf_decision.weight,
                        data_quality=tf_decision.data_quality,
                        reasoning=tf_decision.reasoning,
                    )

                latest_consensus_response = MultiTimeframeConsensusResponse(
                    final_signal=consensus_data["final_signal"],
                    consensus_confidence=consensus_data["consensus_confidence"],
                    agreement_score=consensus_data["agreement_score"],
                    conflicting_timeframes=consensus_data["conflicting_timeframes"],
                    primary_timeframe_influence=0.0,  # Not stored in analysis
                    consensus_method=consensus_data["consensus_method"],
                    timeframe_decisions=timeframe_decisions_response,
                    reasoning=latest_consensus.reasoning,
                )

        return TimeframeAnalysisResponse(
            symbol=symbol,
            timeframes=analysis["timeframes"],
            primary_timeframe=analysis["primary_timeframe"],
            timeframe_weights=analysis["timeframe_weights"],
            latest_consensus=latest_consensus_response,
            timeframe_breakdown=analysis.get("timeframe_breakdown"),
            recent_decisions_count=analysis["recent_decisions_count"],
            analysis_timestamp=datetime.now().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze timeframe performance: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze timeframe performance: {str(e)}"
        )


@router.get("/data-status/{symbol}", response_model=MultiTimeframeDataStatusResponse)
async def check_multi_timeframe_data_status(
    symbol: str,
    timeframes: List[str] = Query(default=["1h", "4h", "1d"]),
    lookback_periods: int = Query(default=100),
):
    """
    Check data availability and quality across multiple timeframes.

    Verifies that sufficient data is available for multi-timeframe analysis
    and provides quality metrics for each timeframe.
    """
    logger.info(f"Checking multi-timeframe data status for {symbol}")

    try:
        data_manager = DataManager()
        timeframe_status = []
        quality_scores = []

        for timeframe in timeframes:
            try:
                # Get data for this timeframe
                data = data_manager.get_data(
                    symbol=symbol, timeframe=timeframe, rows=lookback_periods
                )

                if data is not None and not data.empty:
                    # Calculate data quality metrics
                    completeness = 1.0 - data.isnull().sum().sum() / (
                        len(data) * len(data.columns)
                    )

                    # Simple freshness score based on last timestamp
                    last_timestamp = data.index[-1]
                    current_time = pd.Timestamp.now(tz="UTC")
                    if last_timestamp.tz is None:
                        last_timestamp = last_timestamp.tz_localize("UTC")

                    hours_since_last = (
                        current_time - last_timestamp
                    ).total_seconds() / 3600

                    # Freshness score decreases with time
                    if hours_since_last <= 1:
                        freshness = 1.0
                    elif hours_since_last <= 24:
                        freshness = 0.8
                    elif hours_since_last <= 168:  # 1 week
                        freshness = 0.5
                    else:
                        freshness = 0.2

                    data_quality = completeness * 0.7 + freshness * 0.3
                    quality_scores.append(data_quality)

                    timeframe_status.append(
                        TimeframeDataStatus(
                            timeframe=timeframe,
                            available=True,
                            last_update=last_timestamp.isoformat(),
                            record_count=len(data),
                            data_quality_score=completeness,
                            freshness_score=freshness,
                        )
                    )
                else:
                    timeframe_status.append(
                        TimeframeDataStatus(
                            timeframe=timeframe,
                            available=False,
                            record_count=0,
                            data_quality_score=0.0,
                            freshness_score=0.0,
                        )
                    )

            except Exception as e:
                logger.error(f"Failed to check data for {symbol} {timeframe}: {e}")
                timeframe_status.append(
                    TimeframeDataStatus(
                        timeframe=timeframe,
                        available=False,
                        record_count=0,
                        data_quality_score=0.0,
                        freshness_score=0.0,
                    )
                )

        # Calculate overall metrics
        overall_quality = (
            sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        )
        ready_for_analysis = (
            len(quality_scores) >= len(timeframes) / 2 and overall_quality > 0.6
        )

        return MultiTimeframeDataStatusResponse(
            symbol=symbol,
            timeframe_status=timeframe_status,
            overall_data_quality=overall_quality,
            ready_for_analysis=ready_for_analysis,
        )

    except Exception as e:
        logger.error(f"Failed to check multi-timeframe data status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to check data status: {str(e)}"
        )


@router.get("/strategies", response_model=MultiTimeframeStrategyListResponse)
async def list_multi_timeframe_strategies():
    """
    List strategies that support multi-timeframe analysis.

    Scans strategy configurations to identify those with multi-timeframe
    support and returns their configurations and capabilities.
    """
    logger.info("Listing multi-timeframe strategies")

    try:
        strategies = []
        strategy_dir = Path("strategies")

        if not strategy_dir.exists():
            return MultiTimeframeStrategyListResponse(strategies=[])

        for yaml_file in strategy_dir.glob("*.yaml"):
            try:
                import yaml

                with open(yaml_file, "r") as f:
                    config = yaml.safe_load(f)

                # Check if strategy supports multi-timeframe
                timeframe_configs = config.get("timeframe_configs", {})
                multi_timeframe_config = config.get("multi_timeframe", {})

                if timeframe_configs or multi_timeframe_config:
                    strategy_info = {
                        "name": config.get("name", yaml_file.stem),
                        "description": config.get("description", ""),
                        "config_path": str(yaml_file),
                        "supports_multi_timeframe": True,
                        "timeframes": (
                            list(timeframe_configs.keys()) if timeframe_configs else []
                        ),
                        "primary_timeframe": None,
                        "consensus_method": multi_timeframe_config.get(
                            "consensus_method", "weighted_majority"
                        ),
                        "min_agreement_threshold": multi_timeframe_config.get(
                            "min_agreement_threshold", 0.6
                        ),
                        "indicators": config.get("indicators", []),
                        "fuzzy_sets": list(config.get("fuzzy_sets", {}).keys()),
                    }

                    # Find primary timeframe
                    for tf, tf_config in timeframe_configs.items():
                        if tf_config.get("primary", False):
                            strategy_info["primary_timeframe"] = tf
                            break

                    strategies.append(strategy_info)

            except Exception as e:
                logger.warning(f"Failed to parse strategy {yaml_file}: {e}")
                continue

        return MultiTimeframeStrategyListResponse(strategies=strategies)

    except Exception as e:
        logger.error(f"Failed to list multi-timeframe strategies: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list strategies: {str(e)}"
        )


@router.post("/batch-decisions")
async def make_batch_multi_timeframe_decisions(
    requests: List[MultiTimeframeDecisionRequest],
):
    """
    Generate multiple multi-timeframe decisions in batch.

    Efficiently processes multiple decision requests, useful for
    portfolio-wide analysis or strategy comparison.
    """
    logger.info(f"Processing batch of {len(requests)} multi-timeframe decisions")

    if len(requests) > 10:  # Limit batch size
        raise HTTPException(status_code=400, detail="Batch size limited to 10 requests")

    results = []
    errors = []

    for i, request in enumerate(requests):
        try:
            # Use the existing single decision endpoint logic
            result = await make_multi_timeframe_decision(request)
            results.append({"index": i, "symbol": request.symbol, "result": result})
        except Exception as e:
            errors.append({"index": i, "symbol": request.symbol, "error": str(e)})

    return {
        "success": len(errors) == 0,
        "processed": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }


# Backwards compatibility endpoints
@router.post("/legacy/decide", response_model=MultiTimeframeDecisionResponse)
async def legacy_multi_timeframe_decision(
    symbol: str,
    strategy_config_path: str,
    timeframes: str = "1h,4h,1d",  # Comma-separated string for legacy support
    mode: str = "backtest",
):
    """
    Legacy endpoint for multi-timeframe decisions (backwards compatibility).

    Provides the same functionality as the main decision endpoint but with
    a simplified parameter interface for backwards compatibility.
    """
    # Convert comma-separated timeframes to list
    timeframes_list = [tf.strip() for tf in timeframes.split(",")]

    # Create request object
    request = MultiTimeframeDecisionRequest(
        symbol=symbol,
        strategy_config_path=strategy_config_path,
        timeframes=timeframes_list,
        mode=mode,
    )

    # Use main decision endpoint
    return await make_multi_timeframe_decision(request)
