"""
On-Balance Volume (OBV) indicator implementation for KTRDR.

On-Balance Volume is a momentum indicator that uses volume flow to predict changes in stock price.
The theory behind OBV is that volume precedes price movement.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any

from ktrdr import get_logger
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.errors import DataError
from ktrdr.indicators.schemas import OBV_SCHEMA

# Create module-level logger
logger = get_logger(__name__)


class OBVIndicator(BaseIndicator):
    """
    On-Balance Volume (OBV) momentum indicator.

    OBV is calculated using the following logic:
    - If closing price is higher than previous close: OBV = Previous OBV + Current Volume
    - If closing price is lower than previous close: OBV = Previous OBV - Current Volume  
    - If closing price equals previous close: OBV = Previous OBV (no change)
    
    OBV is a cumulative indicator that starts from 0 and can be positive or negative.
    Rising OBV indicates buying pressure, while falling OBV indicates selling pressure.
    
    Unlike other indicators, OBV doesn't have configurable parameters - it uses all available data.
    However, it requires both price (close) and volume data.

    Attributes:
        No configurable parameters for OBV calculation
    """

    def __init__(self):
        """
        Initialize the OBV indicator.
        
        OBV doesn't have configurable parameters, but we maintain consistency with the base class.
        """
        # Call parent constructor with display_as_overlay=False (separate panel)
        super().__init__(
            name="OBV",
            display_as_overlay=False,
        )

        logger.debug("Initialized OBV indicator")

    def _validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate parameters for OBV indicator using schema-based validation.

        Args:
            params: Parameters to validate (OBV has no parameters, but we validate for consistency)

        Returns:
            Validated parameters (empty dict for OBV)

        Raises:
            DataError: If invalid parameters are provided
        """
        return OBV_SCHEMA.validate(params)

    def compute(self, data: pd.DataFrame) -> pd.Series:
        """
        Compute the On-Balance Volume (OBV) indicator.

        Args:
            data: DataFrame containing close and volume data

        Returns:
            Series with OBV values (cumulative volume flow)

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Check required columns
        required_columns = ["close", "volume"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise DataError(
                message=f"OBV requires columns: {', '.join(missing_columns)}",
                error_code="DATA-MissingColumn",
                details={
                    "missing_columns": missing_columns,
                    "required_columns": required_columns,
                    "available_columns": list(data.columns)
                },
            )

        # Check for sufficient data (need at least 2 data points for price comparison)
        if len(data) < 2:
            raise DataError(
                message="OBV requires at least 2 data points for price comparison",
                error_code="DATA-InsufficientData",
                details={
                    "required": 2,
                    "provided": len(data),
                },
            )

        # Get close prices and volume
        close = data["close"]
        volume = data["volume"]
        
        # Calculate price direction compared to previous close
        price_change = close.diff()
        
        # Initialize OBV series starting with 0
        obv = pd.Series(index=data.index, dtype=float)
        obv.iloc[0] = 0.0  # OBV starts at 0
        
        # Calculate OBV for each period
        for i in range(1, len(data)):
            prev_obv = obv.iloc[i-1]
            current_volume = volume.iloc[i]
            price_diff = price_change.iloc[i]
            
            if price_diff > 0:
                # Price increased: add volume
                obv.iloc[i] = prev_obv + current_volume
            elif price_diff < 0:
                # Price decreased: subtract volume
                obv.iloc[i] = prev_obv - current_volume
            else:
                # Price unchanged: OBV remains the same
                obv.iloc[i] = prev_obv

        # Create result Series with appropriate name
        result_series = pd.Series(
            obv,
            index=data.index,
            name="OBV",
        )

        logger.debug("Computed OBV indicator")

        return result_series