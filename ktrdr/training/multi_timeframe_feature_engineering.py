"""Multi-timeframe feature engineering for neural network training."""

import pandas as pd
import numpy as np
import torch
from typing import Dict, List, Tuple, Optional, Any
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from dataclasses import dataclass

from ktrdr import get_logger
from .feature_engineering import FeatureEngineer

# Set up module-level logger
logger = get_logger(__name__)


@dataclass
class TimeframeFeatureSpec:
    """Specification for features from a specific timeframe."""
    timeframe: str
    fuzzy_features: List[str]
    indicator_features: List[str] = None
    weight: float = 1.0
    enabled: bool = True


@dataclass
class MultiTimeframeFeatureResult:
    """Result of multi-timeframe feature engineering."""
    features_tensor: torch.Tensor
    feature_names: List[str]
    timeframe_feature_map: Dict[str, List[str]]
    feature_stats: Dict[str, Any]
    scaler: Optional[Any] = None


class MultiTimeframeFeatureEngineer:
    """Enhanced feature engineer for multi-timeframe data processing."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize multi-timeframe feature engineer.
        
        Args:
            config: Configuration containing:
                - timeframe_specs: Dict mapping timeframes to feature specifications
                - feature_processing: Feature processing parameters
                - scaling: Scaling configuration
        """
        self.config = config
        self.timeframe_specs = self._build_timeframe_specs()
        self.scaler = None
        self.feature_names: List[str] = []
        self.timeframe_feature_map: Dict[str, List[str]] = {}
        
        logger.info(f"Initialized MultiTimeframeFeatureEngineer with {len(self.timeframe_specs)} timeframes")

    def _build_timeframe_specs(self) -> Dict[str, TimeframeFeatureSpec]:
        """Build timeframe feature specifications from config."""
        specs = {}
        timeframe_configs = self.config.get("timeframe_specs", {})
        
        for tf_name, tf_config in timeframe_configs.items():
            specs[tf_name] = TimeframeFeatureSpec(
                timeframe=tf_name,
                fuzzy_features=tf_config.get("fuzzy_features", []),
                indicator_features=tf_config.get("indicator_features", []),
                weight=tf_config.get("weight", 1.0),
                enabled=tf_config.get("enabled", True)
            )
        
        return specs

    def prepare_multi_timeframe_features(
        self,
        fuzzy_data: Dict[str, pd.DataFrame],
        indicators: Optional[Dict[str, pd.DataFrame]] = None,
        price_data: Optional[Dict[str, pd.DataFrame]] = None,
        saved_scaler: Optional[Any] = None
    ) -> MultiTimeframeFeatureResult:
        """
        Prepare features from multiple timeframes for neural network training.
        
        Args:
            fuzzy_data: Dict mapping timeframes to fuzzy membership DataFrames
            indicators: Optional dict mapping timeframes to indicator DataFrames
            price_data: Optional dict mapping timeframes to OHLCV DataFrames
            saved_scaler: Optional pre-trained scaler for consistent scaling
            
        Returns:
            MultiTimeframeFeatureResult with processed features
        """
        logger.debug("Preparing multi-timeframe features")
        
        all_features = []
        all_feature_names = []
        timeframe_feature_map = {}
        
        # Process each timeframe in consistent order
        timeframe_order = self._get_timeframe_order()
        
        for timeframe in timeframe_order:
            if timeframe not in self.timeframe_specs:
                continue
                
            tf_spec = self.timeframe_specs[timeframe]
            if not tf_spec.enabled:
                logger.debug(f"Skipping disabled timeframe: {timeframe}")
                continue
            
            # Extract features for this timeframe
            tf_features, tf_names = self._extract_timeframe_features(
                timeframe=timeframe,
                fuzzy_data=fuzzy_data.get(timeframe),
                indicators=indicators.get(timeframe) if indicators else None,
                price_data=price_data.get(timeframe) if price_data else None,
                feature_spec=tf_spec
            )
            
            if len(tf_features) > 0:
                all_features.extend(tf_features)
                all_feature_names.extend(tf_names)
                timeframe_feature_map[timeframe] = tf_names
                
                logger.debug(f"Extracted {len(tf_features)} features from {timeframe}")

        if len(all_features) == 0:
            raise ValueError("No features extracted from any timeframe")

        # Convert to numpy array
        feature_array = np.array(all_features).reshape(1, -1)
        
        # Apply feature scaling
        scaled_features, scaler = self._apply_feature_scaling(feature_array, saved_scaler)
        
        # Convert to tensor
        features_tensor = torch.FloatTensor(scaled_features)
        
        # Calculate feature statistics
        feature_stats = self._calculate_feature_stats(feature_array, all_feature_names, timeframe_feature_map)
        
        logger.info(f"Prepared {features_tensor.shape[1]} total features from {len(timeframe_feature_map)} timeframes")
        
        return MultiTimeframeFeatureResult(
            features_tensor=features_tensor,
            feature_names=all_feature_names,
            timeframe_feature_map=timeframe_feature_map,
            feature_stats=feature_stats,
            scaler=scaler
        )

    def _get_timeframe_order(self) -> List[str]:
        """Get consistent timeframe ordering (shortest to longest)."""
        timeframe_priority = {
            "1m": 1, "5m": 2, "15m": 3, "30m": 4,
            "1h": 5, "2h": 6, "4h": 7, "6h": 8, "8h": 9,
            "12h": 10, "1d": 11, "3d": 12, "1w": 13, "1M": 14
        }
        
        available_timeframes = list(self.timeframe_specs.keys())
        return sorted(available_timeframes, key=lambda tf: timeframe_priority.get(tf, 999))

    def _extract_timeframe_features(
        self,
        timeframe: str,
        fuzzy_data: Optional[pd.DataFrame],
        indicators: Optional[pd.DataFrame],
        price_data: Optional[pd.DataFrame],
        feature_spec: TimeframeFeatureSpec
    ) -> Tuple[List[float], List[str]]:
        """
        Extract features for a specific timeframe.
        
        Args:
            timeframe: Timeframe identifier
            fuzzy_data: Fuzzy membership DataFrame for this timeframe
            indicators: Indicator DataFrame for this timeframe
            price_data: OHLCV DataFrame for this timeframe
            feature_spec: Feature specification for this timeframe
            
        Returns:
            Tuple of (feature values, feature names)
        """
        features = []
        feature_names = []
        
        # Extract fuzzy features
        if fuzzy_data is not None and len(fuzzy_data) > 0:
            fuzzy_features, fuzzy_names = self._extract_fuzzy_features(
                fuzzy_data, timeframe, feature_spec.fuzzy_features
            )
            features.extend(fuzzy_features)
            feature_names.extend(fuzzy_names)
        else:
            # Create zero features for missing fuzzy data
            logger.warning(f"Missing or empty fuzzy data for timeframe {timeframe}")
            zero_features = [0.0] * len(feature_spec.fuzzy_features)
            zero_names = [f"{feat}_{timeframe}" for feat in feature_spec.fuzzy_features]
            features.extend(zero_features)
            feature_names.extend(zero_names)
        
        # Extract indicator features (if enabled)
        if feature_spec.indicator_features and indicators is not None and len(indicators) > 0:
            indicator_features, indicator_names = self._extract_indicator_features(
                indicators, timeframe, feature_spec.indicator_features
            )
            features.extend(indicator_features)
            feature_names.extend(indicator_names)
        
        # Apply timeframe weight
        if feature_spec.weight != 1.0:
            features = [f * feature_spec.weight for f in features]
        
        return features, feature_names

    def _extract_fuzzy_features(
        self,
        fuzzy_data: pd.DataFrame,
        timeframe: str,
        expected_features: List[str]
    ) -> Tuple[List[float], List[str]]:
        """
        Extract fuzzy membership features for a timeframe.
        
        Args:
            fuzzy_data: Fuzzy membership DataFrame
            timeframe: Timeframe identifier
            expected_features: List of expected fuzzy feature names
            
        Returns:
            Tuple of (feature values, feature names)
        """
        features = []
        feature_names = []
        
        # Get the latest row (most recent data)
        latest_row = fuzzy_data.iloc[-1]
        
        for expected_feature in expected_features:
            feature_name = f"{expected_feature}_{timeframe}"
            
            if expected_feature in latest_row:
                value = float(latest_row[expected_feature])
                # Ensure value is in valid range [0, 1] for fuzzy membership
                value = max(0.0, min(1.0, value))
            else:
                logger.warning(f"Missing fuzzy feature {expected_feature} for timeframe {timeframe}")
                value = 0.0
            
            features.append(value)
            feature_names.append(feature_name)
        
        return features, feature_names

    def _extract_indicator_features(
        self,
        indicators: pd.DataFrame,
        timeframe: str,
        expected_features: List[str]
    ) -> Tuple[List[float], List[str]]:
        """
        Extract raw indicator features for a timeframe.
        
        Args:
            indicators: Indicator DataFrame
            timeframe: Timeframe identifier
            expected_features: List of expected indicator names
            
        Returns:
            Tuple of (feature values, feature names)
        """
        features = []
        feature_names = []
        
        # Get the latest row (most recent data)
        latest_row = indicators.iloc[-1]
        
        for expected_feature in expected_features:
            feature_name = f"{expected_feature}_raw_{timeframe}"
            
            if expected_feature in latest_row:
                value = float(latest_row[expected_feature])
                # Handle NaN values
                if pd.isna(value):
                    value = 0.0
            else:
                logger.warning(f"Missing indicator {expected_feature} for timeframe {timeframe}")
                value = 0.0
            
            features.append(value)
            feature_names.append(feature_name)
        
        return features, feature_names

    def _apply_feature_scaling(
        self,
        features: np.ndarray,
        saved_scaler: Optional[Any] = None
    ) -> Tuple[np.ndarray, Optional[Any]]:
        """
        Apply feature scaling with scaler persistence.
        
        Args:
            features: Feature array to scale
            saved_scaler: Optional pre-trained scaler
            
        Returns:
            Tuple of (scaled features, scaler)
        """
        scaling_config = self.config.get("scaling", {})
        
        if not scaling_config.get("enabled", True):
            return features, None
        
        if saved_scaler is not None:
            # Use existing scaler for consistent scaling
            scaled_features = saved_scaler.transform(features)
            return scaled_features, saved_scaler
        
        # Create new scaler
        scaler_type = scaling_config.get("type", "standard")
        
        if scaler_type == "standard":
            scaler = StandardScaler()
        elif scaler_type == "minmax":
            scaler = MinMaxScaler()
        else:
            logger.warning(f"Unknown scaler type: {scaler_type}, using standard")
            scaler = StandardScaler()
        
        scaled_features = scaler.fit_transform(features)
        self.scaler = scaler
        
        logger.debug(f"Applied {scaler_type} scaling to features")
        return scaled_features, scaler

    def _calculate_feature_stats(
        self,
        features: np.ndarray,
        feature_names: List[str],
        timeframe_feature_map: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """Calculate comprehensive feature statistics."""
        stats = {
            "total_features": len(feature_names),
            "feature_count_by_timeframe": {
                tf: len(names) for tf, names in timeframe_feature_map.items()
            },
            "feature_range": {
                "min": float(np.min(features)),
                "max": float(np.max(features)),
                "mean": float(np.mean(features)),
                "std": float(np.std(features))
            },
            "missing_features": []
        }
        
        # Check for zero features (potential missing data indicators)
        zero_features = [
            feature_names[i] for i in range(len(feature_names))
            if features[0, i] == 0.0
        ]
        stats["zero_features"] = zero_features
        
        return stats

    def prepare_batch_features(
        self,
        batch_fuzzy_data: List[Dict[str, pd.DataFrame]],
        batch_indicators: Optional[List[Dict[str, pd.DataFrame]]] = None,
        batch_price_data: Optional[List[Dict[str, pd.DataFrame]]] = None,
        saved_scaler: Optional[Any] = None
    ) -> MultiTimeframeFeatureResult:
        """
        Prepare features for a batch of samples.
        
        Args:
            batch_fuzzy_data: List of fuzzy data dicts for each sample
            batch_indicators: Optional list of indicator data dicts
            batch_price_data: Optional list of price data dicts
            saved_scaler: Optional pre-trained scaler
            
        Returns:
            MultiTimeframeFeatureResult with batch features
        """
        batch_size = len(batch_fuzzy_data)
        logger.debug(f"Preparing batch features for {batch_size} samples")
        
        all_batch_features = []
        feature_names = None
        timeframe_feature_map = None
        
        for i in range(batch_size):
            # Prepare features for this sample
            sample_indicators = batch_indicators[i] if batch_indicators else None
            sample_price_data = batch_price_data[i] if batch_price_data else None
            
            result = self.prepare_multi_timeframe_features(
                fuzzy_data=batch_fuzzy_data[i],
                indicators=sample_indicators,
                price_data=sample_price_data,
                saved_scaler=saved_scaler
            )
            
            # Store feature tensor for this sample
            all_batch_features.append(result.features_tensor.squeeze(0))  # Remove batch dimension
            
            # Use feature names and mapping from first sample
            if feature_names is None:
                feature_names = result.feature_names
                timeframe_feature_map = result.timeframe_feature_map
        
        # Stack all features into batch tensor
        batch_features_tensor = torch.stack(all_batch_features, dim=0)
        
        # Calculate batch statistics
        batch_stats = {
            "batch_size": batch_size,
            "feature_count": len(feature_names),
            "timeframe_count": len(timeframe_feature_map)
        }
        
        logger.info(f"Prepared batch features: {batch_features_tensor.shape}")
        
        return MultiTimeframeFeatureResult(
            features_tensor=batch_features_tensor,
            feature_names=feature_names,
            timeframe_feature_map=timeframe_feature_map,
            feature_stats=batch_stats,
            scaler=self.scaler
        )

    def get_feature_template(self) -> Dict[str, Any]:
        """Get template showing expected feature structure."""
        template = {
            "timeframes": {},
            "total_expected_features": 0
        }
        
        for timeframe, spec in self.timeframe_specs.items():
            if spec.enabled:
                tf_template = {
                    "fuzzy_features": spec.fuzzy_features,
                    "indicator_features": spec.indicator_features or [],
                    "weight": spec.weight,
                    "expected_count": len(spec.fuzzy_features) + len(spec.indicator_features or [])
                }
                template["timeframes"][timeframe] = tf_template
                template["total_expected_features"] += tf_template["expected_count"]
        
        return template

    def validate_input_data(
        self,
        fuzzy_data: Dict[str, pd.DataFrame],
        indicators: Optional[Dict[str, pd.DataFrame]] = None
    ) -> Dict[str, Any]:
        """
        Validate input data against expected structure.
        
        Args:
            fuzzy_data: Dict mapping timeframes to fuzzy DataFrames
            indicators: Optional dict mapping timeframes to indicator DataFrames
            
        Returns:
            Validation report
        """
        validation_report = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "timeframe_status": {}
        }
        
        for timeframe, spec in self.timeframe_specs.items():
            if not spec.enabled:
                continue
                
            tf_status = {"has_fuzzy": False, "has_indicators": False, "missing_features": []}
            
            # Check fuzzy data
            if timeframe in fuzzy_data and len(fuzzy_data[timeframe]) > 0:
                tf_status["has_fuzzy"] = True
                fuzzy_df = fuzzy_data[timeframe]
                
                # Check for missing fuzzy features
                for feature in spec.fuzzy_features:
                    if feature not in fuzzy_df.columns:
                        tf_status["missing_features"].append(f"fuzzy:{feature}")
                        validation_report["warnings"].append(
                            f"Missing fuzzy feature '{feature}' for timeframe '{timeframe}'"
                        )
            else:
                validation_report["errors"].append(f"Missing fuzzy data for timeframe '{timeframe}'")
                validation_report["valid"] = False
            
            # Check indicator data (if required)
            if spec.indicator_features and indicators:
                if timeframe in indicators and len(indicators[timeframe]) > 0:
                    tf_status["has_indicators"] = True
                    indicator_df = indicators[timeframe]
                    
                    # Check for missing indicator features
                    for feature in spec.indicator_features:
                        if feature not in indicator_df.columns:
                            tf_status["missing_features"].append(f"indicator:{feature}")
                            validation_report["warnings"].append(
                                f"Missing indicator '{feature}' for timeframe '{timeframe}'"
                            )
                else:
                    validation_report["warnings"].append(
                        f"Missing indicator data for timeframe '{timeframe}'"
                    )
            
            validation_report["timeframe_status"][timeframe] = tf_status
        
        return validation_report