"""Gap Analysis API Models."""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, field_validator
from datetime import datetime


class GapAnalysisError(Exception):
    """Gap analysis specific error."""

    pass


class GapAnalysisMode(str, Enum):
    """Gap analysis mode."""

    QUICK = "quick"
    NORMAL = "normal"
    DETAILED = "detailed"
    COMPREHENSIVE = "comprehensive"


class GapInfoModel(BaseModel):
    """Gap information model."""

    start_time: str
    end_time: str
    duration_hours: float
    gap_type: str
    severity: str
    market_hours: bool
    trading_session: Optional[str] = None
    volume_impact: Optional[float] = None
    price_impact: Optional[float] = None


class GapAnalysisSummary(BaseModel):
    """Gap analysis summary."""

    total_gaps: int
    critical_gaps: int
    major_gaps: int
    minor_gaps: int
    total_missing_hours: float
    coverage_percentage: float
    data_quality_score: float


class GapAnalysisRequest(BaseModel):
    """Request for gap analysis."""

    symbol: str
    timeframe: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    mode: GapAnalysisMode = GapAnalysisMode.QUICK
    include_market_hours_only: bool = True

    @field_validator("symbol", "timeframe")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class GapAnalysisResponse(BaseModel):
    """Response for gap analysis."""

    success: bool = True
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    summary: GapAnalysisSummary
    gaps: List[GapInfoModel]
    analysis_mode: GapAnalysisMode
    generated_at: str


class BatchGapAnalysisRequest(BaseModel):
    """Request for batch gap analysis."""

    symbols: List[str]
    timeframe: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    mode: GapAnalysisMode = GapAnalysisMode.QUICK

    @field_validator("symbols")
    @classmethod
    def validate_symbols_list(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("Symbols list cannot be empty")
        return [s.strip() for s in v if s.strip()]


class BatchGapAnalysisResponse(BaseModel):
    """Response for batch gap analysis."""

    success: bool = True
    timeframe: str
    start_date: str
    end_date: str
    results: Dict[str, GapAnalysisResponse]
    overall_summary: Dict[str, Any]
    generated_at: str
