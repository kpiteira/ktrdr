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

# Data models
from ktrdr.api.models.data import (
    DataLoadRequest,
    DataLoadResponse,
    OHLCVData,
    OHLCVPoint,
    SymbolInfo,
    TimeframeInfo,
    SymbolsResponse,
    TimeframesResponse,
    DataRangeRequest,
    DataRangeInfo,
    DataRangeResponse,
)

# Indicator models
from ktrdr.api.models.indicators import (
    IndicatorType,
    IndicatorParameter,
    IndicatorMetadata,
    IndicatorConfig,
    IndicatorResult,
    IndicatorCalculateRequest,
    IndicatorCalculateResponse,
    IndicatorsListResponse,
    IndicatorDetail,
    IndicatorDetailResponse,
)

# Fuzzy logic models
from ktrdr.api.models.fuzzy import (
    MembershipFunctionType,
    MembershipFunction,
    FuzzyVariable,
    FuzzyRule,
    FuzzySystem,
    FuzzyConfig,
    FuzzyInput,
    FuzzyOutput,
    FuzzyEvaluateRequest,
    FuzzyEvaluateResponse,
    FuzzyConfigResponse,
    FuzzyConfigsResponse,
)

# Extended error models
from ktrdr.api.models.errors import (
    ErrorCode,
    ValidationErrorItem,
    ValidationErrorDetail,
    DataErrorDetail,
    IndicatorErrorDetail,
    FuzzyErrorDetail,
    DetailedErrorResponse,
    DetailedApiResponse,
)

# Chart models
from ktrdr.api.models.charts import (
    ChartTheme,
    ChartGridOptions,
    ChartAxisOptions,
    ChartSeriesType,
    ChartSeriesStyle,
    ChartSeries,
    ChartPanel,
    ChartOptions,
    ChartRenderRequest,
    ChartData,
    ChartRenderResponse,
    ChartTemplateInfo,
    ChartTemplatesResponse,
    ChartExportRequest,
    ChartExportResponse,
)

# IB models
from ktrdr.api.models.ib import (
    ConnectionInfo,
    ConnectionMetrics,
    DataFetchMetrics,
    IbStatusResponse,
    IbHealthStatus,
    IbConfigInfo,
    IbStatusApiResponse,
    IbHealthApiResponse,
    IbConfigApiResponse,
)

__all__ = [
    # Base models
    'ApiResponse',
    'ErrorResponse',
    'PaginatedData',
    
    # Data models
    'DataLoadRequest',
    'DataLoadResponse',
    'OHLCVData',
    'OHLCVPoint',
    'SymbolInfo',
    'TimeframeInfo',
    'SymbolsResponse',
    'TimeframesResponse',
    'DataRangeRequest',
    'DataRangeInfo',
    'DataRangeResponse',
    
    # Indicator models
    'IndicatorType',
    'IndicatorParameter',
    'IndicatorMetadata',
    'IndicatorConfig',
    'IndicatorResult',
    'IndicatorCalculateRequest',
    'IndicatorCalculateResponse',
    'IndicatorsListResponse',
    'IndicatorDetail',
    'IndicatorDetailResponse',
    
    # Fuzzy logic models
    'MembershipFunctionType',
    'MembershipFunction',
    'FuzzyVariable',
    'FuzzyRule',
    'FuzzySystem',
    'FuzzyConfig',
    'FuzzyInput',
    'FuzzyOutput',
    'FuzzyEvaluateRequest',
    'FuzzyEvaluateResponse',
    'FuzzyConfigResponse',
    'FuzzyConfigsResponse',
    
    # Extended error models
    'ErrorCode',
    'ValidationErrorItem',
    'ValidationErrorDetail',
    'DataErrorDetail',
    'IndicatorErrorDetail',
    'FuzzyErrorDetail',
    'DetailedErrorResponse',
    'DetailedApiResponse',
    
    # Chart models
    'ChartTheme',
    'ChartGridOptions',
    'ChartAxisOptions',
    'ChartSeriesType',
    'ChartSeriesStyle',
    'ChartSeries',
    'ChartPanel',
    'ChartOptions',
    'ChartRenderRequest',
    'ChartData',
    'ChartRenderResponse',
    'ChartTemplateInfo',
    'ChartTemplatesResponse',
    'ChartExportRequest',
    'ChartExportResponse',
    
    # IB models
    'ConnectionInfo',
    'ConnectionMetrics',
    'DataFetchMetrics',
    'IbStatusResponse',
    'IbHealthStatus',
    'IbConfigInfo',
    'IbStatusApiResponse',
    'IbHealthApiResponse',
    'IbConfigApiResponse',
]