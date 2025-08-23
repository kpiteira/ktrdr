"""Pure fuzzy neural processing for feature engineering removal."""

from typing import Any, Optional

import numpy as np
import pandas as pd
import torch

from ktrdr import get_logger

logger = get_logger(__name__)


class FuzzyNeuralProcessor:
    """Convert pure fuzzy membership values into neural network inputs.

    This class replaces FeatureEngineer for pure neuro-fuzzy architecture.
    It handles ONLY fuzzy membership values (0-1 range) with optional
    temporal context, eliminating all raw feature engineering.
    """

    def __init__(self, config: dict[str, Any], disable_temporal: bool = False):
        """Initialize fuzzy neural processor.

        Args:
            config: Fuzzy processing configuration
            disable_temporal: If True, disable temporal feature generation
                             (used in backtesting when FeatureCache handles lag features)
        """
        self.config = config
        self.feature_names: list[str] = []
        self.disable_temporal = disable_temporal

    def prepare_input(
        self,
        fuzzy_data: pd.DataFrame,
    ) -> tuple[torch.Tensor, list[str]]:
        """Prepare pure fuzzy features for neural network training.

        Args:
            fuzzy_data: DataFrame with fuzzy membership values (0-1 range)

        Returns:
            Tuple of (feature tensor, feature names)
        """
        logger.debug(
            f"Processing fuzzy data with {len(fuzzy_data.columns)} fuzzy features"
        )

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
            logger.debug(
                "Temporal feature generation disabled - assuming FeatureCache provides lag features"
            )

        # Combine all features
        if not features:
            raise ValueError("No fuzzy features found in input data")

        feature_matrix = np.column_stack(features) if len(features) > 1 else features[0]

        # Validate fuzzy range (should be 0-1)
        self._validate_fuzzy_range(feature_matrix, feature_names)

        # Handle any remaining NaN values (rare for fuzzy outputs)
        feature_matrix = np.nan_to_num(feature_matrix, nan=0.0)

        self.feature_names = feature_names

        logger.info(
            f"Prepared {feature_matrix.shape[1]} pure fuzzy features for neural network"
        )
        return torch.FloatTensor(feature_matrix), feature_names

    def prepare_multi_timeframe_input(
        self,
        multi_timeframe_fuzzy: dict[str, pd.DataFrame],
        timeframe_order: Optional[list[str]] = None,
    ) -> tuple[torch.Tensor, list[str]]:
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
            raise ValueError(
                "No timeframe data provided for multi-timeframe processing"
            )

        # Handle single timeframe case (special case of multi-timeframe)
        if len(multi_timeframe_fuzzy) == 1:
            timeframe, fuzzy_data = next(iter(multi_timeframe_fuzzy.items()))
            logger.debug(
                f"Single timeframe detected ({timeframe}), using standard processing"
            )
            return self.prepare_input(fuzzy_data)

        # Determine timeframe processing order
        if timeframe_order is None:
            # Use frequency-based order (highest frequency first) for proper temporal alignment
            timeframe_order = self._sort_timeframes_by_frequency(
                list(multi_timeframe_fuzzy.keys())
            )
            logger.debug(
                f"No timeframe order specified, using frequency order: {timeframe_order}"
            )
        else:
            # Validate that all specified timeframes are available
            available_timeframes = set(multi_timeframe_fuzzy.keys())
            specified_timeframes = set(timeframe_order)

            missing_timeframes = specified_timeframes - available_timeframes
            if missing_timeframes:
                logger.warning(
                    f"Specified timeframes not available: {missing_timeframes}"
                )
                # Filter out missing timeframes
                timeframe_order = [
                    tf for tf in timeframe_order if tf in available_timeframes
                ]

            extra_timeframes = available_timeframes - specified_timeframes
            if extra_timeframes:
                logger.info(
                    f"Additional timeframes available but not in order: {extra_timeframes}"
                )
                # Add extra timeframes at the end in sorted order
                timeframe_order.extend(sorted(extra_timeframes))

        logger.info(
            f"Processing {len(timeframe_order)} timeframes in order: {timeframe_order}"
        )

        # Process each timeframe separately to extract fuzzy features
        timeframe_features = {}
        timeframe_feature_names = {}
        processing_errors = {}

        for timeframe in timeframe_order:
            try:
                # Get fuzzy data for this timeframe
                fuzzy_data = multi_timeframe_fuzzy[timeframe]

                if fuzzy_data is None or fuzzy_data.empty:
                    logger.warning(
                        f"Empty fuzzy data for timeframe {timeframe}, skipping"
                    )
                    processing_errors[timeframe] = "Empty fuzzy data"
                    continue

                logger.debug(
                    f"Processing timeframe {timeframe} with {len(fuzzy_data.columns)} fuzzy features"
                )

                # Extract fuzzy features while preserving DataFrame structure for temporal alignment
                tf_features, tf_names = self._extract_fuzzy_features(fuzzy_data)

                # Store as DataFrame with original index for temporal alignment
                timeframe_features[timeframe] = pd.DataFrame(
                    tf_features, index=fuzzy_data.index, columns=tf_names
                )
                timeframe_feature_names[timeframe] = tf_names

                logger.debug(
                    f"Successfully processed {len(tf_names)} features for timeframe {timeframe} ({len(fuzzy_data)} timestamps)"
                )

            except Exception as e:
                error_msg = f"Failed to process timeframe {timeframe}: {str(e)}"
                logger.error(error_msg)
                processing_errors[timeframe] = str(e)
                continue

        # Check if we got any valid results
        if not timeframe_features:
            raise ValueError(
                f"Failed to process features for any timeframe. "
                f"Errors: {processing_errors}"
            )

        # Perform temporal alignment for multi-timeframe neural network input
        combined_features, all_feature_names = self._align_multi_timeframe_features(
            timeframe_features, timeframe_feature_names, timeframe_order
        )

        # Log summary
        total_features = combined_features.shape[1]
        successful_timeframes = len(timeframe_features)
        failed_timeframes = len(processing_errors)

        if failed_timeframes > 0:
            logger.warning(
                f"Multi-timeframe processing completed with warnings: "
                f"{successful_timeframes}/{len(timeframe_order)} timeframes successful"
            )
            for tf, error in processing_errors.items():
                logger.warning(f"  {tf}: {error}")
        else:
            logger.info(
                f"Successfully processed all {successful_timeframes} timeframes"
            )

        logger.info(
            f"Combined {total_features} features from {successful_timeframes} timeframes "
            f"for neural network input"
        )

        return combined_features, all_feature_names

    def _align_multi_timeframe_features(
        self,
        timeframe_features: dict[str, pd.DataFrame],
        timeframe_feature_names: dict[str, list[str]],
        timeframe_order: list[str],
    ) -> tuple[torch.Tensor, list[str]]:
        """
        Align multi-timeframe fuzzy features for neural network input.

        This method implements proper temporal alignment where each neural network
        input row contains features from all timeframes at the corresponding time.
        Higher frequency timeframes drive the temporal resolution.

        Example for 1h + 1d alignment:
        - 1h timestamp 2024-01-02 09:00 → uses 1d features from 2024-01-02
        - 1h timestamp 2024-01-02 10:00 → uses SAME 1d features from 2024-01-02
        - 1h timestamp 2024-01-03 09:00 → uses NEW 1d features from 2024-01-03

        Args:
            timeframe_features: Dict mapping timeframes to feature DataFrames
            timeframe_feature_names: Dict mapping timeframes to feature name lists
            timeframe_order: Ordered list of timeframes for feature combination

        Returns:
            Tuple of (aligned_features_tensor, combined_feature_names)
        """
        # Find the highest frequency (most granular) timeframe to use as base
        # Assume first timeframe in order is highest frequency (shortest period)
        base_timeframe = timeframe_order[0]
        base_features = timeframe_features[base_timeframe]

        logger.info(
            f"Using {base_timeframe} as base timeframe for temporal alignment ({len(base_features)} timestamps)"
        )

        # Create aligned feature matrix
        aligned_features_list = []
        combined_feature_names = []

        # Start with base timeframe features
        aligned_features_list.append(base_features.values)
        combined_feature_names.extend(
            [
                f"{base_timeframe}_{name}"
                for name in timeframe_feature_names[base_timeframe]
            ]
        )

        # Align other timeframes to base timeframe timestamps
        for timeframe in timeframe_order[1:]:
            tf_features = timeframe_features[timeframe]
            tf_names = timeframe_feature_names[timeframe]

            logger.debug(
                f"Aligning {timeframe} ({len(tf_features)} bars) to {base_timeframe} ({len(base_features)} bars)"
            )

            # Align using forward-fill to match base timeframe timestamps
            # This correctly maps daily features to each hour within that day
            aligned_tf_features = tf_features.reindex(
                base_features.index, method="ffill"
            )

            # Check for NaN values and provide detailed logging
            nan_count = aligned_tf_features.isnull().sum().sum()
            if nan_count > 0:
                logger.warning(
                    f"Temporal alignment of {timeframe} created {nan_count} NaN values. "
                    f"This indicates gaps between {timeframe} and {base_timeframe} coverage."
                )
                logger.debug(
                    f"Original {timeframe} coverage: {tf_features.index[0]} to {tf_features.index[-1]}"
                )
                logger.debug(
                    f"Base {base_timeframe} coverage: {base_features.index[0]} to {base_features.index[-1]}"
                )

            # Handle any remaining NaN values using multiple strategies
            if nan_count > 0:
                # First try backward fill for gaps at the beginning
                aligned_tf_features = aligned_tf_features.bfill()

                # Then forward fill for any remaining gaps
                aligned_tf_features = aligned_tf_features.ffill()

                # Finally, fill any remaining NaN with 0.0 (neutral fuzzy values)
                aligned_tf_features = aligned_tf_features.fillna(0.0)

                # Verify all NaN values are resolved
                remaining_nans = aligned_tf_features.isnull().sum().sum()
                if remaining_nans > 0:
                    logger.error(
                        f"Failed to resolve {remaining_nans} NaN values in {timeframe} alignment"
                    )
                else:
                    logger.debug(
                        f"Successfully resolved all NaN values in {timeframe} alignment"
                    )

            aligned_features_list.append(aligned_tf_features.values)
            combined_feature_names.extend([f"{timeframe}_{name}" for name in tf_names])

            logger.debug(
                f"Aligned {timeframe}: {aligned_tf_features.shape[1]} features → {len(aligned_tf_features)} timestamps"
            )

        # Combine all aligned features horizontally
        combined_features_matrix = np.concatenate(aligned_features_list, axis=1)

        # Check for NaN values after alignment but before temporal features
        pre_temporal_nans = np.isnan(combined_features_matrix).sum()
        if pre_temporal_nans > 0:
            logger.warning(
                f"Found {pre_temporal_nans} NaN values after alignment, before temporal features"
            )
            # Fill any remaining NaN values before temporal processing
            combined_features_matrix = np.nan_to_num(combined_features_matrix, nan=0.0)
            logger.debug(
                "Filled NaN values with 0.0 before temporal feature extraction"
            )

        # Apply temporal features if configured
        if self.config.get("lookback_periods", 0) > 0:
            lookback = self.config["lookback_periods"]
            temporal_features, temporal_names = self._extract_temporal_features(
                pd.DataFrame(combined_features_matrix, columns=combined_feature_names),
                lookback,
            )

            if temporal_features.size > 0:
                # Check for NaN values in temporal features
                temporal_nans = np.isnan(temporal_features).sum()
                if temporal_nans > 0:
                    logger.warning(
                        f"Temporal features introduced {temporal_nans} NaN values (likely at beginning due to lookback)"
                    )
                    # Fill temporal NaN values with 0.0
                    temporal_features = np.nan_to_num(temporal_features, nan=0.0)
                    logger.debug("Filled temporal feature NaN values with 0.0")

                # Combine current + temporal features
                combined_features_matrix = np.concatenate(
                    [combined_features_matrix, temporal_features], axis=1
                )
                combined_feature_names.extend(temporal_names)
                logger.debug(
                    f"Added {len(temporal_names)} temporal features (lookback={lookback})"
                )

        # Convert to tensor
        features_tensor = torch.FloatTensor(combined_features_matrix)

        logger.info(
            f"Multi-timeframe alignment complete: {features_tensor.shape[0]} samples, "
            f"{features_tensor.shape[1]} total features from {len(timeframe_order)} timeframes"
        )

        return features_tensor, combined_feature_names

    def _sort_timeframes_by_frequency(self, timeframes: list[str]) -> list[str]:
        """
        Sort timeframes by frequency (highest frequency first).

        This ensures proper temporal alignment where the highest frequency
        timeframe drives the neural network input resolution.

        Args:
            timeframes: List of timeframe strings (e.g., ['1h', '1d', '4h'])

        Returns:
            List of timeframes sorted by frequency (highest first)

        Example:
            ['1h', '1d'] → ['1h', '1d']  # 1h is higher frequency
            ['1d', '4h', '1h'] → ['1h', '4h', '1d']  # 1h > 4h > 1d
        """

        def timeframe_to_minutes(tf: str) -> int:
            """Convert timeframe string to minutes for comparison."""
            tf = tf.lower().strip()
            if tf.endswith("m"):
                return int(tf[:-1])
            elif tf.endswith("h"):
                return int(tf[:-1]) * 60
            elif tf.endswith("d"):
                return int(tf[:-1]) * 60 * 24
            elif tf.endswith("w"):
                return int(tf[:-1]) * 60 * 24 * 7
            else:
                # Default to hours if no suffix
                return int(tf) * 60

        # Sort by minutes (ascending = highest frequency first)
        sorted_timeframes = sorted(timeframes, key=timeframe_to_minutes)

        logger.debug(f"Sorted timeframes by frequency: {sorted_timeframes}")
        return sorted_timeframes

    def _extract_fuzzy_features(
        self, fuzzy_data: pd.DataFrame
    ) -> tuple[np.ndarray, list[str]]:
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
            elif any(
                keyword in column.lower()
                for keyword in [
                    "oversold",
                    "overbought",
                    "above",
                    "below",
                    "strong",
                    "weak",
                    "buying",
                    "selling",
                    "up",
                    "down",
                    "high",
                    "low",
                    "neutral",
                ]
            ):
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
    ) -> tuple[np.ndarray, list[str]]:
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

    def _validate_fuzzy_range(
        self, feature_matrix: np.ndarray, feature_names: list[str]
    ) -> None:
        """Validate that fuzzy features are in expected 0-1 range.

        Args:
            feature_matrix: Matrix of features to validate
            feature_names: Names of features for error reporting
        """
        # Check for values outside 0-1 range (allowing small numerical errors)
        # Suppress warnings for all-NaN slices (handled separately below)
        with np.errstate(invalid="ignore"):
            min_vals = np.nanmin(feature_matrix, axis=0)
            max_vals = np.nanmax(feature_matrix, axis=0)

        tolerance = 1e-6
        out_of_range_features = []

        for i, name in enumerate(feature_names):
            if min_vals[i] < -tolerance or max_vals[i] > 1 + tolerance:
                out_of_range_features.append(
                    {"feature": name, "min": min_vals[i], "max": max_vals[i]}
                )

        if out_of_range_features:
            logger.warning(
                f"Found {len(out_of_range_features)} features outside fuzzy range [0,1]: "
                f"{out_of_range_features[:3]}..."
            )
            # Don't fail - just warn, as some indicators might have slight overflows

        # Check for completely invalid data (NaN only - zero values are valid fuzzy memberships)
        invalid_features = []
        for i, name in enumerate(feature_names):
            col_data = feature_matrix[:, i]
            if np.all(np.isnan(col_data)):
                invalid_features.append(name)

        if invalid_features:
            logger.warning(
                f"Found {len(invalid_features)} features with all NaN values: {invalid_features[:5]}..."
            )
            logger.warning(
                "This may indicate missing indicators or fuzzy configuration issues."
            )

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

    def get_config_summary(self) -> dict[str, Any]:
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
