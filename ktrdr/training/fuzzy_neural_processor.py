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

    def prepare_multi_timeframe_input(
        self,
        multi_timeframe_fuzzy: Dict[str, pd.DataFrame],
        timeframe_order: Optional[List[str]] = None
    ) -> Tuple[torch.Tensor, List[str]]:
        """Prepare multi-timeframe fuzzy features for neural network training.

        This method extends the single-timeframe approach to handle multiple timeframes
        by combining fuzzy membership values from each timeframe into a single feature vector.
        Single-timeframe processing becomes a special case of this multi-timeframe approach.

        Args:
            multi_timeframe_fuzzy: Dictionary mapping timeframes to fuzzy DataFrames
                                 Format: {timeframe: fuzzy_membership_dataframe}
            timeframe_order: Optional list specifying the order of timeframes for feature combination.
                           If None, uses sorted order of available timeframes for consistency.

        Returns:
            Tuple of (combined_feature_tensor, feature_names_list)
            
        Raises:
            ValueError: If no timeframe data provided or no valid features found

        Example:
            >>> processor = FuzzyNeuralProcessor(config)
            >>> multi_fuzzy = {
            ...     '15m': fuzzy_15m_df,  # columns: ['15m_rsi_low', '15m_rsi_high', ...]
            ...     '1h': fuzzy_1h_df,    # columns: ['1h_rsi_low', '1h_rsi_high', ...]
            ...     '4h': fuzzy_4h_df     # columns: ['4h_rsi_low', '4h_rsi_high', ...]
            ... }
            >>> features, names = processor.prepare_multi_timeframe_input(multi_fuzzy)
            >>> # features.shape: (batch_size, total_features_all_timeframes)
            >>> # names: ['15m_rsi_low', '15m_rsi_high', ..., '1h_rsi_low', ..., '4h_rsi_low', ...]
        """
        if not multi_timeframe_fuzzy:
            raise ValueError("No timeframe data provided for multi-timeframe processing")

        # Handle single timeframe case (special case of multi-timeframe)
        if len(multi_timeframe_fuzzy) == 1:
            timeframe, fuzzy_data = next(iter(multi_timeframe_fuzzy.items()))
            logger.debug(f"Single timeframe detected ({timeframe}), using standard processing")
            return self.prepare_input(fuzzy_data)

        # Determine timeframe processing order
        if timeframe_order is None:
            # Use sorted order for consistency when no order specified
            timeframe_order = sorted(multi_timeframe_fuzzy.keys())
            logger.debug(f"No timeframe order specified, using sorted order: {timeframe_order}")
        else:
            # Validate that all specified timeframes are available
            available_timeframes = set(multi_timeframe_fuzzy.keys())
            specified_timeframes = set(timeframe_order)
            
            missing_timeframes = specified_timeframes - available_timeframes
            if missing_timeframes:
                logger.warning(f"Specified timeframes not available: {missing_timeframes}")
                # Filter out missing timeframes
                timeframe_order = [tf for tf in timeframe_order if tf in available_timeframes]
            
            extra_timeframes = available_timeframes - specified_timeframes
            if extra_timeframes:
                logger.info(f"Additional timeframes available but not in order: {extra_timeframes}")
                # Add extra timeframes at the end in sorted order
                timeframe_order.extend(sorted(extra_timeframes))

        logger.info(f"Processing {len(timeframe_order)} timeframes in order: {timeframe_order}")

        # Process each timeframe separately and collect results
        all_features = []
        all_feature_names = []
        processing_errors = {}

        for timeframe in timeframe_order:
            try:
                # Get fuzzy data for this timeframe
                fuzzy_data = multi_timeframe_fuzzy[timeframe]
                
                if fuzzy_data is None or fuzzy_data.empty:
                    logger.warning(f"Empty fuzzy data for timeframe {timeframe}, skipping")
                    processing_errors[timeframe] = "Empty fuzzy data"
                    continue

                logger.debug(f"Processing timeframe {timeframe} with {len(fuzzy_data.columns)} fuzzy features")

                # Use existing single-timeframe processing for this timeframe
                tf_features, tf_names = self.prepare_input(fuzzy_data)
                
                # Features are already torch tensors, so we can collect them directly
                all_features.append(tf_features)
                all_feature_names.extend(tf_names)
                
                logger.debug(f"Successfully processed {tf_features.shape[1]} features for timeframe {timeframe}")

            except Exception as e:
                error_msg = f"Failed to process timeframe {timeframe}: {str(e)}"
                logger.error(error_msg)
                processing_errors[timeframe] = str(e)
                continue

        # Check if we got any valid results
        if not all_features:
            raise ValueError(
                f"Failed to process features for any timeframe. "
                f"Errors: {processing_errors}"
            )

        # Combine features from all timeframes
        # Each element in all_features is a torch tensor of shape (batch_size, timeframe_features)
        combined_features = torch.cat(all_features, dim=1)
        
        # Log summary
        total_features = combined_features.shape[1]
        successful_timeframes = len(all_features)
        failed_timeframes = len(processing_errors)
        
        if failed_timeframes > 0:
            logger.warning(
                f"Multi-timeframe processing completed with warnings: "
                f"{successful_timeframes}/{len(timeframe_order)} timeframes successful"
            )
            for tf, error in processing_errors.items():
                logger.warning(f"  {tf}: {error}")
        else:
            logger.info(f"Successfully processed all {successful_timeframes} timeframes")

        logger.info(
            f"Combined {total_features} features from {successful_timeframes} timeframes "
            f"for neural network input"
        )

        return combined_features, all_feature_names

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