"""
MACD indicator implementation for KTRDR.

This module provides the MACDIndicator class for calculating the Moving Average Convergence 
Divergence (MACD) indicator.
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple

from ktrdr import get_logger
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.errors import ConfigurationError

# Create module-level logger
logger = get_logger(__name__)


class MACDIndicator(BaseIndicator):
    """
    Moving Average Convergence Divergence (MACD) indicator.
    
    The MACD indicator calculates the difference between two exponential moving
    averages and provides a signal line, which is an EMA of the MACD line.
    
    Default parameters:
        - fast_period: 12 (12-day EMA)
        - slow_period: 26 (26-day EMA)
        - signal_period: 9 (9-day EMA of MACD line)
        - source: 'close' (use closing prices for calculation)
    
    Attributes:
        fast_period (int): The shorter EMA period
        slow_period (int): The longer EMA period
        signal_period (int): The signal line's EMA period
        source (str): The data column to use for calculations
    """
    
    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        source: str = 'close'
    ):
        """
        Initialize the MACD indicator.
        
        Args:
            fast_period: Period for the shorter EMA
            slow_period: Period for the longer EMA
            signal_period: Period for the signal line EMA
            source: Column name to use for calculations
        
        Raises:
            ConfigurationError: If the parameters are invalid
        """
        # Validate parameters
        if fast_period <= 0 or slow_period <= 0 or signal_period <= 0:
            raise ConfigurationError(
                "MACD periods must be positive integers",
                "CONFIG-InvalidParameter",
                {"fast_period": fast_period, "slow_period": slow_period, "signal_period": signal_period}
            )
            
        if fast_period >= slow_period:
            raise ConfigurationError(
                "MACD fast_period must be less than slow_period",
                "CONFIG-InvalidParameter",
                {"fast_period": fast_period, "slow_period": slow_period}
            )
        
        # Call parent constructor with display_as_overlay=False
        name = f"MACD_{fast_period}_{slow_period}_{signal_period}"
        super().__init__(name=name, display_as_overlay=False, 
                         fast_period=fast_period, slow_period=slow_period, 
                         signal_period=signal_period, source=source)
        
        # Store these for easy reference
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.source = source
        
        logger.debug(f"Initialized MACD indicator with fast_period={fast_period}, "
                     f"slow_period={slow_period}, signal_period={signal_period}, source={source}")
    
    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute the MACD indicator.
        
        Args:
            data: DataFrame containing the source column.
        
        Returns:
            DataFrame with MACD line, signal line, and histogram.
            
        Raises:
            ConfigurationError: If the source column is not in the data
        """
        # Check if source column exists
        if self.source not in data.columns:
            raise ConfigurationError(
                f"Source column '{self.source}' not found in data",
                "CONFIG-MissingColumn",
                {"column": self.source, "available_columns": list(data.columns)}
            )
            
        # Get the source data
        source_data = data[self.source]
        
        # Calculate fast and slow EMAs
        fast_ema = source_data.ewm(span=self.fast_period, adjust=False).mean()
        slow_ema = source_data.ewm(span=self.slow_period, adjust=False).mean()
        
        # Calculate MACD line
        macd_line = fast_ema - slow_ema
        
        # Calculate signal line (EMA of MACD line)
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
        
        # Calculate histogram (MACD line - signal line)
        histogram = macd_line - signal_line
        
        # Create result DataFrame with column names that include the parameters
        macd_col = f"MACD_{self.fast_period}_{self.slow_period}"
        signal_col = f"MACD_signal_{self.fast_period}_{self.slow_period}_{self.signal_period}"
        hist_col = f"MACD_hist_{self.fast_period}_{self.slow_period}_{self.signal_period}"
        
        result_df = pd.DataFrame({
            macd_col: macd_line,
            signal_col: signal_line,
            hist_col: histogram
        }, index=data.index)
        
        logger.debug(f"Computed MACD with parameters: fast={self.fast_period}, "
                     f"slow={self.slow_period}, signal={self.signal_period}")
        
        return result_df