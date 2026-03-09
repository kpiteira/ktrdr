"""Context data providers for external data sources.

This package provides the abstraction layer for fetching, caching, and
aligning external data (FRED yields, CFTC positioning, cross-pair prices)
to the primary trading instrument's timeframe.
"""

from .base import ContextDataAligner, ContextDataProvider, ContextDataResult
from .registry import ContextDataProviderRegistry

__all__ = [
    "ContextDataAligner",
    "ContextDataProvider",
    "ContextDataProviderRegistry",
    "ContextDataResult",
]
