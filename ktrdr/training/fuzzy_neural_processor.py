"""Pure fuzzy neural processing for feature engineering removal."""

import pandas as pd
import numpy as np
import torch
from typing import Dict, List, Tuple, Optional, Any

from ktrdr import get_logger

logger = get_logger(__name__)


class FuzzyNeuralProcessor:
    """Convert pure fuzzy membership values into neural network inputs.
    
    This class replaces FeatureEngineer for pure neuro-fuzzy architecture.
    It handles ONLY fuzzy membership values (0-1 range) with optional
    temporal context, eliminating all raw feature engineering.
    """

    def __init__(self, config: Dict[str, Any], disable_temporal: bool = False):
        """Initialize fuzzy neural processor.

        Args:
            config: Fuzzy processing configuration
            disable_temporal: If True, disable temporal feature generation 
                             (used in backtesting when FeatureCache handles lag features)
        """
        self.config = config
        self.feature_names: List[str] = []
        self.disable_temporal = disable_temporal

    def prepare_input(
        self,
        fuzzy_data: pd.DataFrame,
    ) -> Tuple[torch.Tensor, List[str]]:
        """Prepare pure fuzzy features for neural network training.

        Args:
            fuzzy_data: DataFrame with fuzzy membership values (0-1 range)

        Returns:
            Tuple of (feature tensor, feature names)
        """
        logger.debug(f"Processing fuzzy data with {len(fuzzy_data.columns)} fuzzy features")
        
        features = []
        feature_names = []

        # 1. Core fuzzy membership features (primary)
        fuzzy_features, fuzzy_names = self._extract_fuzzy_features(fuzzy_data)
        features.append(fuzzy_features)
        feature_names.extend(fuzzy_names)

        # 2. Temporal features (optional - lagged fuzzy values)
        # Skip temporal feature generation if disabled (e.g., in backtesting when FeatureCache handles this)
        lookback = self.config.get("lookback_periods", 0)
        if lookback > 0 and not self.disable_temporal:
            temporal_features, temporal_names = self._extract_temporal_features(
                fuzzy_data, lookback
            )
            if temporal_features.size > 0:
                features.append(temporal_features)
                feature_names.extend(temporal_names)
        elif self.disable_temporal and lookback > 0:
            logger.debug(f"Temporal feature generation disabled - assuming FeatureCache provides lag features")

        # Combine all features
        if not features:
            raise ValueError("No fuzzy features found in input data")

        feature_matrix = np.column_stack(features) if len(features) > 1 else features[0]
        
        # Validate fuzzy range (should be 0-1)
        self._validate_fuzzy_range(feature_matrix, feature_names)

        # Handle any remaining NaN values (rare for fuzzy outputs)
        feature_matrix = np.nan_to_num(feature_matrix, nan=0.0)

        self.feature_names = feature_names
        
        logger.info(f"Prepared {feature_matrix.shape[1]} pure fuzzy features for neural network")
        return torch.FloatTensor(feature_matrix), feature_names

    def _extract_fuzzy_features(
        self, fuzzy_data: pd.DataFrame
    ) -> Tuple[np.ndarray, List[str]]:
        """Extract fuzzy membership features.

        Args:
            fuzzy_data: DataFrame with fuzzy membership values

        Returns:
            Tuple of (features array, feature names)
        """
        features = []
        names = []

        # Include all fuzzy columns (they should all be membership values 0-1)
        # Fuzzy columns have format: indicator_fuzzyset (e.g., rsi_oversold, sma_above)
        fuzzy_columns = []
        
        for column in fuzzy_data.columns:
            # Include columns that look like fuzzy membership outputs
            if "_" in column:  # Standard format: indicator_fuzzyset
                fuzzy_columns.append(column)
            elif "membership" in column.lower():  # Alternative format
                fuzzy_columns.append(column)
            elif any(keyword in column.lower() for keyword in 
                    ["oversold", "overbought", "above", "below", "strong", "weak", 
                     "buying", "selling", "up", "down", "high", "low", "neutral"]):
                fuzzy_columns.append(column)
        
        if not fuzzy_columns:
            raise ValueError("No fuzzy membership columns found in input data")
        
        # Sort columns for consistent ordering
        fuzzy_columns.sort()
        
        for column in fuzzy_columns:
            values = fuzzy_data[column].values
            features.append(values)
            names.append(column)

        if not features:
            raise ValueError("No valid fuzzy features found")

        # Stack as column matrix
        feature_matrix = np.column_stack(features)
        
        logger.debug(f"Extracted {len(names)} fuzzy features: {names[:5]}...")
        return feature_matrix, names

    def _extract_temporal_features(
        self, fuzzy_data: pd.DataFrame, lookback: int
    ) -> Tuple[np.ndarray, List[str]]:
        """Extract temporal fuzzy features (lagged values).

        Args:
            fuzzy_data: DataFrame with fuzzy membership values
            lookback: Number of historical periods to include

        Returns:
            Tuple of (temporal features array, feature names)
        """
        if lookback < 1:
            return np.array([]), []

        temporal_features = []
        temporal_names = []

        # Get base fuzzy columns
        fuzzy_columns = [col for col in fuzzy_data.columns if "_" in col]
        
        for lag in range(1, lookback + 1):
            for column in fuzzy_columns:
                # Create lagged values
                lagged_values = fuzzy_data[column].shift(lag).values
                temporal_features.append(lagged_values)
                temporal_names.append(f"{column}_lag_{lag}")

        if not temporal_features:
            return np.array([]), []

        # Stack temporal features
        temporal_matrix = np.column_stack(temporal_features)
        
        logger.debug(f"Added {len(temporal_names)} temporal fuzzy features")
        return temporal_matrix, temporal_names

    def _validate_fuzzy_range(self, feature_matrix: np.ndarray, feature_names: List[str]) -> None:
        """Validate that fuzzy features are in expected 0-1 range.

        Args:
            feature_matrix: Matrix of features to validate
            feature_names: Names of features for error reporting
        """
        # Check for values outside 0-1 range (allowing small numerical errors)
        # Suppress warnings for all-NaN slices (handled separately below)
        with np.errstate(invalid='ignore'):
            min_vals = np.nanmin(feature_matrix, axis=0)
            max_vals = np.nanmax(feature_matrix, axis=0)
        
        tolerance = 1e-6
        out_of_range_features = []
        
        for i, name in enumerate(feature_names):
            if min_vals[i] < -tolerance or max_vals[i] > 1 + tolerance:
                out_of_range_features.append({
                    'feature': name,
                    'min': min_vals[i],
                    'max': max_vals[i]
                })
        
        if out_of_range_features:
            logger.warning(f"Found {len(out_of_range_features)} features outside fuzzy range [0,1]: "
                         f"{out_of_range_features[:3]}...")
            # Don't fail - just warn, as some indicators might have slight overflows
        
        # Check for completely invalid data (NaN only - zero values are valid fuzzy memberships)
        invalid_features = []
        for i, name in enumerate(feature_names):
            col_data = feature_matrix[:, i]
            if np.all(np.isnan(col_data)):
                invalid_features.append(name)
        
        if invalid_features:
            logger.warning(f"Found {len(invalid_features)} features with all NaN values: {invalid_features[:5]}...")
            logger.warning("This may indicate missing indicators or fuzzy configuration issues.")

    def get_feature_count(self) -> int:
        """Get total number of features that will be generated.
        
        Returns:
            Expected number of neural network input features
        """
        base_features = len(self.feature_names) if self.feature_names else 0
        lookback = self.config.get("lookback_periods", 0)
        
        if lookback > 0 and base_features > 0:
            # Base features + (base features * lookback periods)
            return base_features + (base_features * lookback)
        
        return base_features

    def get_config_summary(self) -> Dict[str, Any]:
        """Get summary of processing configuration.
        
        Returns:
            Dictionary with configuration details
        """
        return {
            "type": "FuzzyNeuralProcessor",
            "lookback_periods": self.config.get("lookback_periods", 0),
            "feature_count": self.get_feature_count(),
            "pure_fuzzy": True,
            "scaling": False,  # Fuzzy values already 0-1
            "raw_features": False,  # No raw feature engineering
        }