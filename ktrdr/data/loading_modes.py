"""
Data Loading Modes for KTRDR system.

Defines the different strategies for loading data:
- LOCAL: Use only existing cached data, no external requests
- TAIL: Focus on recent gaps from last data point to now  
- BACKFILL: Focus on historical gaps from start to first data point
- FULL: Comprehensive analysis combining tail + backfill strategies
"""

from enum import Enum


class DataLoadingMode(str, Enum):
    """Data loading strategy modes."""
    
    LOCAL = "local"
    TAIL = "tail" 
    BACKFILL = "backfill"
    FULL = "full"