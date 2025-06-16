"""Advanced cross-timeframe feature engineering for neural networks.

This module provides sophisticated feature engineering techniques that capture
relationships and patterns across multiple timeframes.
"""

import pandas as pd
import numpy as np
import torch
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from scipy import stats
from sklearn.preprocessing import StandardScaler, RobustScaler

from ktrdr import get_logger

logger = get_logger(__name__)


@dataclass
class CrossTimeframeFeature:
    """Definition of a cross-timeframe feature."""
    name: str
    description: str
    timeframes: List[str]
    feature_type: str  # 'correlation', 'divergence', 'momentum_cascade', 'volatility_regime'
    parameters: Dict[str, Any]


@dataclass
class FeatureExtractionResult:
    """Result of cross-timeframe feature extraction."""
    features: np.ndarray
    feature_names: List[str]
    feature_metadata: Dict[str, Any]
    extraction_stats: Dict[str, Any]


class CrossTimeframeFeatureEngineer:
    """Advanced feature engineering for multi-timeframe analysis."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize cross-timeframe feature engineer.
        
        Args:
            config: Configuration containing feature engineering parameters
        """
        self.config = config
        self.logger = get_logger(__name__)
        
        # Feature extraction methods
        self.feature_extractors = {
            'correlation': self._extract_correlation_features,
            'divergence': self._extract_divergence_features,
            'momentum_cascade': self._extract_momentum_cascade_features,
            'volatility_regime': self._extract_volatility_regime_features,
            'trend_alignment': self._extract_trend_alignment_features,
            'support_resistance': self._extract_support_resistance_features,
            'seasonality': self._extract_seasonality_features
        }
        
        self.logger.info("Initialized CrossTimeframeFeatureEngineer")
    
    def extract_cross_timeframe_features(
        self,
        indicator_data: Dict[str, pd.DataFrame],
        fuzzy_data: Dict[str, pd.DataFrame],
        price_data: Dict[str, pd.DataFrame]
    ) -> FeatureExtractionResult:
        """
        Extract comprehensive cross-timeframe features.
        
        Args:
            indicator_data: Dict mapping timeframes to indicator DataFrames
            fuzzy_data: Dict mapping timeframes to fuzzy membership DataFrames
            price_data: Dict mapping timeframes to OHLCV DataFrames
            
        Returns:
            FeatureExtractionResult with extracted features
        """
        self.logger.info("Extracting cross-timeframe features")
        
        all_features = []
        all_feature_names = []
        feature_metadata = {}
        extraction_stats = {}
        
        # Get enabled feature types from config
        enabled_features = self.config.get("enabled_features", list(self.feature_extractors.keys()))
        
        for feature_type in enabled_features:
            if feature_type in self.feature_extractors:
                try:
                    features, names, metadata = self.feature_extractors[feature_type](
                        indicator_data, fuzzy_data, price_data
                    )
                    
                    if len(features) > 0:
                        all_features.extend(features)
                        all_feature_names.extend(names)
                        feature_metadata[feature_type] = metadata
                        extraction_stats[feature_type] = len(features)
                        
                        self.logger.debug(f"Extracted {len(features)} {feature_type} features")
                    
                except Exception as e:
                    self.logger.error(f"Failed to extract {feature_type} features: {e}")
                    extraction_stats[feature_type] = 0
            else:
                self.logger.warning(f"Unknown feature type: {feature_type}")
        
        if len(all_features) == 0:
            raise ValueError("No features extracted")
        
        # Convert to numpy array
        feature_array = np.array(all_features).reshape(1, -1)
        
        # Apply post-processing
        if self.config.get("normalize_features", True):
            feature_array = self._normalize_features(feature_array)
        
        self.logger.info(f"Extracted {len(all_features)} total cross-timeframe features")
        
        return FeatureExtractionResult(
            features=feature_array,
            feature_names=all_feature_names,
            feature_metadata=feature_metadata,
            extraction_stats=extraction_stats
        )
    
    def _extract_correlation_features(
        self,
        indicator_data: Dict[str, pd.DataFrame],
        fuzzy_data: Dict[str, pd.DataFrame],
        price_data: Dict[str, pd.DataFrame]
    ) -> Tuple[List[float], List[str], Dict[str, Any]]:
        """Extract correlation features between timeframes."""
        features = []
        feature_names = []
        metadata = {"correlations": {}}
        
        timeframes = list(price_data.keys())
        
        # Cross-timeframe price correlations
        for i, tf1 in enumerate(timeframes):
            for tf2 in timeframes[i+1:]:
                if tf1 in price_data and tf2 in price_data:
                    df1 = price_data[tf1]
                    df2 = price_data[tf2]
                    
                    # Align timeframes and calculate correlation
                    correlation = self._calculate_aligned_correlation(
                        df1['close'], df2['close'], tf1, tf2
                    )
                    
                    if not np.isnan(correlation):
                        features.append(correlation)
                        feature_names.append(f"price_corr_{tf1}_{tf2}")
                        metadata["correlations"][f"{tf1}_{tf2}"] = correlation
        
        # Cross-timeframe indicator correlations
        for indicator_name in self._get_common_indicators(indicator_data):
            for i, tf1 in enumerate(timeframes):
                for tf2 in timeframes[i+1:]:
                    if (tf1 in indicator_data and tf2 in indicator_data and
                        indicator_name in indicator_data[tf1].columns and
                        indicator_name in indicator_data[tf2].columns):
                        
                        correlation = self._calculate_aligned_correlation(
                            indicator_data[tf1][indicator_name],
                            indicator_data[tf2][indicator_name],
                            tf1, tf2
                        )
                        
                        if not np.isnan(correlation):
                            features.append(correlation)
                            feature_names.append(f"{indicator_name}_corr_{tf1}_{tf2}")
        
        return features, feature_names, metadata
    
    def _extract_divergence_features(
        self,
        indicator_data: Dict[str, pd.DataFrame],
        fuzzy_data: Dict[str, pd.DataFrame],
        price_data: Dict[str, pd.DataFrame]
    ) -> Tuple[List[float], List[str], Dict[str, Any]]:
        """Extract divergence features between timeframes."""
        features = []
        feature_names = []
        metadata = {"divergences": {}}
        
        timeframes = list(price_data.keys())
        
        # Price momentum divergences
        for i, tf1 in enumerate(timeframes):
            for tf2 in timeframes[i+1:]:
                if tf1 in price_data and tf2 in price_data:
                    # Calculate momentum for each timeframe
                    momentum1 = self._calculate_momentum(price_data[tf1]['close'])
                    momentum2 = self._calculate_momentum(price_data[tf2]['close'])
                    
                    # Calculate divergence (difference in normalized momentum)
                    divergence = abs(momentum1 - momentum2)
                    
                    features.append(divergence)
                    feature_names.append(f"momentum_divergence_{tf1}_{tf2}")
                    metadata["divergences"][f"{tf1}_{tf2}"] = divergence
        
        # RSI divergences
        for tf1 in timeframes:
            for tf2 in timeframes:
                if (tf1 != tf2 and tf1 in indicator_data and tf2 in indicator_data):
                    rsi_col1 = self._find_indicator_column(indicator_data[tf1], "rsi")
                    rsi_col2 = self._find_indicator_column(indicator_data[tf2], "rsi")
                    
                    if rsi_col1 and rsi_col2:
                        rsi1 = indicator_data[tf1][rsi_col1].iloc[-1]
                        rsi2 = indicator_data[tf2][rsi_col2].iloc[-1]
                        
                        if not (pd.isna(rsi1) or pd.isna(rsi2)):
                            rsi_divergence = abs(rsi1 - rsi2) / 100.0  # Normalize to 0-1
                            features.append(rsi_divergence)
                            feature_names.append(f"rsi_divergence_{tf1}_{tf2}")
        
        return features, feature_names, metadata
    
    def _extract_momentum_cascade_features(
        self,
        indicator_data: Dict[str, pd.DataFrame],
        fuzzy_data: Dict[str, pd.DataFrame],
        price_data: Dict[str, pd.DataFrame]
    ) -> Tuple[List[float], List[str], Dict[str, Any]]:
        """Extract momentum cascade features across timeframes."""
        features = []
        feature_names = []
        metadata = {"momentum_cascade": {}}
        
        timeframes = sorted(price_data.keys(), key=self._timeframe_to_minutes)
        
        # Calculate momentum for each timeframe
        momentum_values = {}
        for tf in timeframes:
            if tf in price_data:
                momentum = self._calculate_momentum(price_data[tf]['close'])
                momentum_values[tf] = momentum
        
        # Momentum cascade alignment
        cascade_alignment = self._calculate_cascade_alignment(momentum_values, timeframes)
        features.append(cascade_alignment)
        feature_names.append("momentum_cascade_alignment")
        metadata["momentum_cascade"]["alignment"] = cascade_alignment
        
        # Momentum acceleration (change in momentum across timeframes)
        if len(timeframes) >= 2:
            for i in range(len(timeframes) - 1):
                tf_short = timeframes[i]
                tf_long = timeframes[i + 1]
                
                if tf_short in momentum_values and tf_long in momentum_values:
                    acceleration = momentum_values[tf_short] - momentum_values[tf_long]
                    features.append(acceleration)
                    feature_names.append(f"momentum_acceleration_{tf_short}_to_{tf_long}")
        
        # Momentum strength consistency
        momentum_consistency = self._calculate_momentum_consistency(momentum_values)
        features.append(momentum_consistency)
        feature_names.append("momentum_consistency")
        
        return features, feature_names, metadata
    
    def _extract_volatility_regime_features(
        self,
        indicator_data: Dict[str, pd.DataFrame],
        fuzzy_data: Dict[str, pd.DataFrame],
        price_data: Dict[str, pd.DataFrame]
    ) -> Tuple[List[float], List[str], Dict[str, Any]]:
        """Extract volatility regime features across timeframes."""
        features = []
        feature_names = []
        metadata = {"volatility_regimes": {}}
        
        # Calculate volatility for each timeframe
        volatility_values = {}
        for tf, df in price_data.items():
            if 'close' in df.columns and len(df) > 1:
                returns = df['close'].pct_change().dropna()
                volatility = returns.std()
                volatility_values[tf] = volatility
        
        # Volatility regime classification
        for tf, vol in volatility_values.items():
            # Classify volatility regime (low/medium/high)
            vol_percentiles = [0.33, 0.67]  # Could be made configurable
            
            if vol < vol_percentiles[0]:
                regime_features = [1.0, 0.0, 0.0]  # Low volatility
            elif vol < vol_percentiles[1]:
                regime_features = [0.0, 1.0, 0.0]  # Medium volatility
            else:
                regime_features = [0.0, 0.0, 1.0]  # High volatility
            
            features.extend(regime_features)
            feature_names.extend([
                f"vol_regime_low_{tf}",
                f"vol_regime_med_{tf}",
                f"vol_regime_high_{tf}"
            ])
            
            metadata["volatility_regimes"][tf] = {
                "volatility": vol,
                "regime": "low" if regime_features[0] else ("medium" if regime_features[1] else "high")
            }
        
        # Cross-timeframe volatility ratios
        timeframes = list(volatility_values.keys())
        for i, tf1 in enumerate(timeframes):
            for tf2 in timeframes[i+1:]:
                if tf1 in volatility_values and tf2 in volatility_values:
                    vol_ratio = volatility_values[tf1] / (volatility_values[tf2] + 1e-8)
                    features.append(vol_ratio)
                    feature_names.append(f"vol_ratio_{tf1}_{tf2}")
        
        return features, feature_names, metadata
    
    def _extract_trend_alignment_features(
        self,
        indicator_data: Dict[str, pd.DataFrame],
        fuzzy_data: Dict[str, pd.DataFrame],
        price_data: Dict[str, pd.DataFrame]
    ) -> Tuple[List[float], List[str], Dict[str, Any]]:
        """Extract trend alignment features across timeframes."""
        features = []
        feature_names = []
        metadata = {"trend_alignment": {}}
        
        # Calculate trend direction for each timeframe
        trend_directions = {}
        for tf, df in price_data.items():
            if 'close' in df.columns and len(df) >= 20:
                # Use simple moving averages to determine trend
                sma_short = df['close'].rolling(window=10).mean().iloc[-1]
                sma_long = df['close'].rolling(window=20).mean().iloc[-1]
                current_price = df['close'].iloc[-1]
                
                # Trend strength and direction
                if current_price > sma_short > sma_long:
                    trend_direction = 1.0  # Strong uptrend
                elif current_price > sma_short:
                    trend_direction = 0.5  # Weak uptrend
                elif current_price < sma_short < sma_long:
                    trend_direction = -1.0  # Strong downtrend
                elif current_price < sma_short:
                    trend_direction = -0.5  # Weak downtrend
                else:
                    trend_direction = 0.0  # Sideways
                
                trend_directions[tf] = trend_direction
        
        # Trend alignment score
        if len(trend_directions) > 1:
            trend_values = list(trend_directions.values())
            alignment_score = self._calculate_trend_alignment_score(trend_values)
            features.append(alignment_score)
            feature_names.append("trend_alignment_score")
            metadata["trend_alignment"]["alignment_score"] = alignment_score
        
        # Individual timeframe trend features
        for tf, trend in trend_directions.items():
            features.append(trend)
            feature_names.append(f"trend_direction_{tf}")
            metadata["trend_alignment"][tf] = trend
        
        # Trend confirmation features
        if len(trend_directions) >= 2:
            timeframes = list(trend_directions.keys())
            for i in range(len(timeframes) - 1):
                tf1, tf2 = timeframes[i], timeframes[i + 1]
                trend_confirmation = 1.0 if (trend_directions[tf1] * trend_directions[tf2]) > 0 else 0.0
                features.append(trend_confirmation)
                feature_names.append(f"trend_confirmation_{tf1}_{tf2}")
        
        return features, feature_names, metadata
    
    def _extract_support_resistance_features(
        self,
        indicator_data: Dict[str, pd.DataFrame],
        fuzzy_data: Dict[str, pd.DataFrame],
        price_data: Dict[str, pd.DataFrame]
    ) -> Tuple[List[float], List[str], Dict[str, Any]]:
        """Extract support/resistance features across timeframes."""
        features = []
        feature_names = []
        metadata = {"support_resistance": {}}
        
        for tf, df in price_data.items():
            if 'close' in df.columns and len(df) >= 20:
                current_price = df['close'].iloc[-1]
                
                # Calculate support and resistance levels
                recent_data = df.tail(20)
                support = recent_data['low'].min()
                resistance = recent_data['high'].max()
                
                # Distance to support/resistance (normalized)
                support_distance = (current_price - support) / current_price
                resistance_distance = (resistance - current_price) / current_price
                
                # Position within range
                price_position = (current_price - support) / (resistance - support + 1e-8)
                
                features.extend([support_distance, resistance_distance, price_position])
                feature_names.extend([
                    f"support_distance_{tf}",
                    f"resistance_distance_{tf}",
                    f"price_position_{tf}"
                ])
                
                metadata["support_resistance"][tf] = {
                    "support": support,
                    "resistance": resistance,
                    "current_price": current_price,
                    "position": price_position
                }
        
        return features, feature_names, metadata
    
    def _extract_seasonality_features(
        self,
        indicator_data: Dict[str, pd.DataFrame],
        fuzzy_data: Dict[str, pd.DataFrame],
        price_data: Dict[str, pd.DataFrame]
    ) -> Tuple[List[float], List[str], Dict[str, Any]]:
        """Extract seasonality and time-based features."""
        features = []
        feature_names = []
        metadata = {"seasonality": {}}
        
        # Use the finest timeframe for time analysis
        primary_tf = min(price_data.keys(), key=self._timeframe_to_minutes)
        
        if primary_tf in price_data and 'timestamp' in price_data[primary_tf].columns:
            df = price_data[primary_tf]
            latest_timestamp = pd.to_datetime(df['timestamp'].iloc[-1])
            
            # Hour of day (cyclical encoding)
            hour = latest_timestamp.hour
            hour_sin = np.sin(2 * np.pi * hour / 24)
            hour_cos = np.cos(2 * np.pi * hour / 24)
            
            # Day of week (cyclical encoding)
            day_of_week = latest_timestamp.weekday()
            dow_sin = np.sin(2 * np.pi * day_of_week / 7)
            dow_cos = np.cos(2 * np.pi * day_of_week / 7)
            
            # Month (cyclical encoding)
            month = latest_timestamp.month
            month_sin = np.sin(2 * np.pi * month / 12)
            month_cos = np.cos(2 * np.pi * month / 12)
            
            features.extend([hour_sin, hour_cos, dow_sin, dow_cos, month_sin, month_cos])
            feature_names.extend([
                "hour_sin", "hour_cos",
                "day_of_week_sin", "day_of_week_cos",
                "month_sin", "month_cos"
            ])
            
            metadata["seasonality"] = {
                "hour": hour,
                "day_of_week": day_of_week,
                "month": month,
                "timestamp": latest_timestamp.isoformat()
            }
        
        return features, feature_names, metadata
    
    # Helper methods
    
    def _calculate_aligned_correlation(
        self, 
        series1: pd.Series, 
        series2: pd.Series,
        tf1: str,
        tf2: str,
        window: int = 20
    ) -> float:
        """Calculate correlation between two series with alignment."""
        try:
            # Take last window points for correlation
            s1 = series1.tail(window).dropna()
            s2 = series2.tail(window).dropna()
            
            if len(s1) < 5 or len(s2) < 5:
                return 0.0
            
            # Resample to common frequency if needed
            min_len = min(len(s1), len(s2))
            s1 = s1.tail(min_len)
            s2 = s2.tail(min_len)
            
            correlation = s1.corr(s2)
            return correlation if not pd.isna(correlation) else 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_momentum(self, price_series: pd.Series, period: int = 10) -> float:
        """Calculate normalized momentum."""
        if len(price_series) < period + 1:
            return 0.0
        
        current_price = price_series.iloc[-1]
        past_price = price_series.iloc[-(period + 1)]
        
        if past_price == 0:
            return 0.0
        
        momentum = (current_price - past_price) / past_price
        
        # Normalize to [-1, 1] using tanh
        return np.tanh(momentum * 10)  # Scale factor for sensitivity
    
    def _calculate_cascade_alignment(
        self, 
        momentum_values: Dict[str, float], 
        timeframes: List[str]
    ) -> float:
        """Calculate how well momentum aligns across timeframes."""
        if len(momentum_values) < 2:
            return 0.0
        
        momentum_list = [momentum_values.get(tf, 0.0) for tf in timeframes if tf in momentum_values]
        
        if len(momentum_list) < 2:
            return 0.0
        
        # Calculate alignment as correlation with ideal cascade
        # Ideal cascade: longer timeframes have smoother momentum
        ideal_cascade = np.linspace(momentum_list[0], momentum_list[-1], len(momentum_list))
        
        try:
            correlation = np.corrcoef(momentum_list, ideal_cascade)[0, 1]
            return correlation if not np.isnan(correlation) else 0.0
        except:
            return 0.0
    
    def _calculate_momentum_consistency(self, momentum_values: Dict[str, float]) -> float:
        """Calculate consistency of momentum across timeframes."""
        if len(momentum_values) < 2:
            return 0.0
        
        momentum_list = list(momentum_values.values())
        
        # Check if all momentum values have the same sign
        signs = [1 if m > 0 else (-1 if m < 0 else 0) for m in momentum_list]
        unique_signs = set(signs)
        
        if len(unique_signs) == 1 and 0 not in unique_signs:
            return 1.0  # Perfect consistency
        elif 0 in unique_signs:
            return 0.5  # Neutral momentum
        else:
            return 0.0  # Conflicting momentum
    
    def _calculate_trend_alignment_score(self, trend_values: List[float]) -> float:
        """Calculate overall trend alignment score."""
        if len(trend_values) < 2:
            return 0.0
        
        # Check for alignment (same direction)
        positive_trends = sum(1 for t in trend_values if t > 0)
        negative_trends = sum(1 for t in trend_values if t < 0)
        neutral_trends = sum(1 for t in trend_values if t == 0)
        
        total_trends = len(trend_values)
        
        # Alignment score based on consensus
        if positive_trends == total_trends:
            return 1.0  # All bullish
        elif negative_trends == total_trends:
            return -1.0  # All bearish
        elif positive_trends > negative_trends:
            return positive_trends / total_trends  # Bullish bias
        elif negative_trends > positive_trends:
            return -negative_trends / total_trends  # Bearish bias
        else:
            return 0.0  # No consensus
    
    def _get_common_indicators(self, indicator_data: Dict[str, pd.DataFrame]) -> List[str]:
        """Get list of indicators present in all timeframes."""
        if not indicator_data:
            return []
        
        # Find intersection of all columns
        common_indicators = set(indicator_data[list(indicator_data.keys())[0]].columns)
        for df in indicator_data.values():
            common_indicators &= set(df.columns)
        
        # Remove non-indicator columns
        exclude_cols = {'timestamp', 'open', 'high', 'low', 'close', 'volume'}
        common_indicators -= exclude_cols
        
        return list(common_indicators)
    
    def _find_indicator_column(self, df: pd.DataFrame, indicator_pattern: str) -> Optional[str]:
        """Find column matching indicator pattern."""
        pattern = indicator_pattern.lower()
        for col in df.columns:
            if pattern in col.lower():
                return col
        return None
    
    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """Convert timeframe string to minutes for sorting."""
        timeframe_map = {
            "1m": 1, "5m": 5, "15m": 15, "30m": 30,
            "1h": 60, "2h": 120, "4h": 240, "6h": 360, "8h": 480,
            "12h": 720, "1d": 1440, "3d": 4320, "1w": 10080, "1M": 43200
        }
        return timeframe_map.get(timeframe, 60)  # Default to 1 hour
    
    def _normalize_features(self, features: np.ndarray) -> np.ndarray:
        """Apply robust feature normalization."""
        # Use robust scaling to handle outliers
        scaler = RobustScaler()
        normalized = scaler.fit_transform(features)
        
        # Clip extreme values
        normalized = np.clip(normalized, -3, 3)
        
        return normalized
    
    def get_feature_definitions(self) -> List[CrossTimeframeFeature]:
        """Get definitions of all available cross-timeframe features."""
        features = [
            CrossTimeframeFeature(
                name="price_correlation",
                description="Correlation of price movements between timeframes",
                timeframes=["all"],
                feature_type="correlation",
                parameters={"window": 20}
            ),
            CrossTimeframeFeature(
                name="momentum_divergence",
                description="Difference in momentum between timeframes",
                timeframes=["all"],
                feature_type="divergence",
                parameters={"period": 10}
            ),
            CrossTimeframeFeature(
                name="momentum_cascade",
                description="Alignment of momentum across timeframe hierarchy",
                timeframes=["all"],
                feature_type="momentum_cascade",
                parameters={}
            ),
            CrossTimeframeFeature(
                name="volatility_regime",
                description="Volatility regime classification for each timeframe",
                timeframes=["all"],
                feature_type="volatility_regime",
                parameters={"percentiles": [0.33, 0.67]}
            ),
            CrossTimeframeFeature(
                name="trend_alignment",
                description="Alignment of trend direction across timeframes",
                timeframes=["all"],
                feature_type="trend_alignment",
                parameters={"short_window": 10, "long_window": 20}
            ),
            CrossTimeframeFeature(
                name="support_resistance",
                description="Distance to support/resistance levels",
                timeframes=["all"],
                feature_type="support_resistance",
                parameters={"lookback": 20}
            ),
            CrossTimeframeFeature(
                name="seasonality",
                description="Time-based seasonal patterns",
                timeframes=["primary"],
                feature_type="seasonality",
                parameters={}
            )
        ]
        
        return features