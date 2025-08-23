"""
API models package for KTRDR.

This package provides Pydantic models for request validation,
response formatting, and data structure definitions throughout the API.
"""

# Base models
from ktrdr.api.models.base import (
    ApiResponse,
    ErrorResponse,
    PaginatedData,
)

# Chart models
from ktrdr.api.models.charts import (
    ChartAxisOptions,
    ChartData,
    ChartExportRequest,
    ChartExportResponse,
    ChartGridOptions,
    ChartOptions,
    ChartPanel,
    ChartRenderRequest,
    ChartRenderResponse,
    ChartSeries,
    ChartSeriesStyle,
    ChartSeriesType,
    ChartTemplateInfo,
    ChartTemplatesResponse,
    ChartTheme,
)

# Data models
from ktrdr.api.models.data import (
    DataLoadRequest,
    DataLoadResponse,
    DataRangeInfo,
    DataRangeRequest,
    DataRangeResponse,
    OHLCVData,
    OHLCVPoint,
    SymbolInfo,
    SymbolsResponse,
    TimeframeInfo,
    TimeframesResponse,
)

# Extended error models
from ktrdr.api.models.errors import (
    DataErrorDetail,
    DetailedApiResponse,
    DetailedErrorResponse,
    ErrorCode,
    FuzzyErrorDetail,
    IndicatorErrorDetail,
    ValidationErrorDetail,
    ValidationErrorItem,
)

# Fuzzy logic models
from ktrdr.api.models.fuzzy import (
    FuzzyConfig,
    FuzzyConfigResponse,
    FuzzyConfigsResponse,
    FuzzyEvaluateRequest,
    FuzzyEvaluateResponse,
    FuzzyInput,
    FuzzyOutput,
    FuzzyRule,
    FuzzySystem,
    FuzzyVariable,
    MembershipFunction,
    MembershipFunctionType,
)

# IB models
from ktrdr.api.models.ib import (
    ConnectionInfo,
    ConnectionMetrics,
    DataFetchMetrics,
    IbConfigApiResponse,
    IbConfigInfo,
    IbHealthApiResponse,
    IbHealthStatus,
    IbStatusApiResponse,
    IbStatusResponse,
)

# Indicator models
from ktrdr.api.models.indicators import (
    IndicatorCalculateRequest,
    IndicatorCalculateResponse,
    IndicatorConfig,
    IndicatorDetail,
    IndicatorDetailResponse,
    IndicatorMetadata,
    IndicatorParameter,
    IndicatorResult,
    IndicatorsListResponse,
    IndicatorType,
)

# Operations models
from ktrdr.api.models.operations import (
    CancelOperationRequest,
    OperationCancelResponse,
    OperationInfo,
    OperationListResponse,
    OperationMetadata,
    OperationProgress,
    OperationStartResponse,
    OperationStatus,
    OperationStatusResponse,
    OperationSummary,
    OperationType,
)

__all__ = [
    # Base models
    "ApiResponse",
    "ErrorResponse",
    "PaginatedData",
    # Data models
    "DataLoadRequest",
    "DataLoadResponse",
    "OHLCVData",
    "OHLCVPoint",
    "SymbolInfo",
    "TimeframeInfo",
    "SymbolsResponse",
    "TimeframesResponse",
    "DataRangeRequest",
    "DataRangeInfo",
    "DataRangeResponse",
    # Indicator models
    "IndicatorType",
    "IndicatorParameter",
    "IndicatorMetadata",
    "IndicatorConfig",
    "IndicatorResult",
    "IndicatorCalculateRequest",
    "IndicatorCalculateResponse",
    "IndicatorsListResponse",
    "IndicatorDetail",
    "IndicatorDetailResponse",
    # Fuzzy logic models
    "MembershipFunctionType",
    "MembershipFunction",
    "FuzzyVariable",
    "FuzzyRule",
    "FuzzySystem",
    "FuzzyConfig",
    "FuzzyInput",
    "FuzzyOutput",
    "FuzzyEvaluateRequest",
    "FuzzyEvaluateResponse",
    "FuzzyConfigResponse",
    "FuzzyConfigsResponse",
    # Extended error models
    "ErrorCode",
    "ValidationErrorItem",
    "ValidationErrorDetail",
    "DataErrorDetail",
    "IndicatorErrorDetail",
    "FuzzyErrorDetail",
    "DetailedErrorResponse",
    "DetailedApiResponse",
    # Chart models
    "ChartTheme",
    "ChartGridOptions",
    "ChartAxisOptions",
    "ChartSeriesType",
    "ChartSeriesStyle",
    "ChartSeries",
    "ChartPanel",
    "ChartOptions",
    "ChartRenderRequest",
    "ChartData",
    "ChartRenderResponse",
    "ChartTemplateInfo",
    "ChartTemplatesResponse",
    "ChartExportRequest",
    "ChartExportResponse",
    # IB models
    "ConnectionInfo",
    "ConnectionMetrics",
    "DataFetchMetrics",
    "IbStatusResponse",
    "IbHealthStatus",
    "IbConfigInfo",
    "IbStatusApiResponse",
    "IbHealthApiResponse",
    "IbConfigApiResponse",
    # Operations models
    "OperationStatus",
    "OperationType",
    "OperationProgress",
    "OperationMetadata",
    "OperationInfo",
    "OperationSummary",
    "CancelOperationRequest",
    "OperationListResponse",
    "OperationStatusResponse",
    "OperationCancelResponse",
    "OperationStartResponse",
]
