"""Feature engineering for neural network training."""

import pandas as pd
import numpy as np
import torch
from typing import Dict, List, Tuple, Optional, Any
from sklearn.preprocessing import StandardScaler, MinMaxScaler


class FeatureEngineer:
    """Convert fuzzy values and indicators into neural network features."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize feature engineer.
        
        Args:
            config: Feature engineering configuration
        """
        self.config = config
        self.scaler = None
        self.feature_names: List[str] = []
        self.feature_importance: Optional[Dict[str, float]] = None
        
    def prepare_features(self, 
                        fuzzy_data: pd.DataFrame,
                        indicators: pd.DataFrame,
                        price_data: pd.DataFrame) -> Tuple[torch.Tensor, List[str]]:
        """Prepare all features for neural network training.
        
        Args:
            fuzzy_data: DataFrame with fuzzy membership values
            indicators: DataFrame with technical indicators
            price_data: DataFrame with OHLCV data
            
        Returns:
            Tuple of (feature tensor, feature names)
        """
        features = []
        feature_names = []
        
        # 1. Core fuzzy membership features
        fuzzy_features, fuzzy_names = self._extract_fuzzy_features(fuzzy_data)
        features.append(fuzzy_features)
        feature_names.extend(fuzzy_names)
        
        # 2. Price context features
        if self.config.get('include_price_context', True):
            price_features, price_names = self._extract_price_features(
                price_data, indicators
            )
            features.append(price_features)
            feature_names.extend(price_names)
        
        # 3. Volume features
        if self.config.get('include_volume_context', True):
            volume_features, volume_names = self._extract_volume_features(
                price_data
            )
            features.append(volume_features)
            feature_names.extend(volume_names)
        
        # 4. Technical indicator features
        if self.config.get('include_raw_indicators', False):
            indicator_features, indicator_names = self._extract_indicator_features(
                indicators
            )
            features.append(indicator_features)
            feature_names.extend(indicator_names)
        
        # 5. Temporal features (lookback)
        lookback = self.config.get('lookback_periods', 1)
        if lookback > 1:
            temporal_features, temporal_names = self._extract_temporal_features(
                fuzzy_data, lookback
            )
            features.append(temporal_features)
            feature_names.extend(temporal_names)
        
        # Filter out empty arrays
        non_empty_features = [feat for feat in features if feat.size > 0]
        feature_names_filtered = []
        
        # Also filter feature names to match
        start_idx = 0
        for i, feat_array in enumerate(features):
            if feat_array.size > 0:
                if i == 0:  # fuzzy features
                    feature_names_filtered.extend(feature_names[start_idx:start_idx+feat_array.shape[1]])
                else:
                    # Calculate how many names belong to this feature group
                    feat_count = feat_array.shape[1] if len(feat_array.shape) > 1 else 1
                    feature_names_filtered.extend(feature_names[start_idx:start_idx+feat_count])
            
            # Update start index for next feature group
            if len(feat_array.shape) > 1:
                start_idx += feat_array.shape[1]
            else:
                start_idx += 1
        
        # Combine all non-empty features
        if not non_empty_features:
            raise ValueError("No valid features found")
        
        feature_matrix = np.column_stack(non_empty_features)
        feature_names = feature_names_filtered
        
        # Handle NaN values
        feature_matrix = np.nan_to_num(feature_matrix, nan=0.0)
        
        # Scale features
        if self.config.get('scale_features', True):
            feature_matrix = self._scale_features(feature_matrix)
        
        self.feature_names = feature_names
        return torch.FloatTensor(feature_matrix), feature_names
    
    def _extract_fuzzy_features(self, fuzzy_data: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """Extract fuzzy membership features.
        
        Args:
            fuzzy_data: DataFrame with fuzzy membership values
            
        Returns:
            Tuple of (features array, feature names)
        """
        features = []
        names = []
        
        # Include all fuzzy columns (they should all be membership values)
        # Fuzzy columns typically have format: indicator_fuzzyset (e.g., rsi_oversold, sma_above)
        for column in fuzzy_data.columns:
            # Skip any non-fuzzy columns that might be in the dataframe
            if '_' in column or 'membership' in column.lower():
                features.append(fuzzy_data[column].values)
                names.append(column)
        
        if not features:
            raise ValueError("No fuzzy membership features found")
        
        return np.column_stack(features), names
    
    def _extract_price_features(self, price_data: pd.DataFrame, 
                               indicators: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """Extract price-based features.
        
        Args:
            price_data: OHLCV data
            indicators: Technical indicators
            
        Returns:
            Tuple of (features array, feature names)
        """
        features = []
        names = []
        
        close = price_data['close']
        
        # Price relative to moving averages
        for ma_col in ['sma_20', 'sma_50', 'ema_20']:
            if ma_col in indicators.columns:
                price_ratio = close / indicators[ma_col]
                features.append(price_ratio.values)
                names.append(f'price_to_{ma_col}_ratio')
        
        # Price momentum (rate of change)
        for period in [5, 10, 20]:
            roc = close.pct_change(period).fillna(0)
            features.append(roc.values)
            names.append(f'roc_{period}')
        
        # Price position in daily range
        if all(col in price_data.columns for col in ['high', 'low']):
            daily_position = (close - price_data['low']) / (price_data['high'] - price_data['low'])
            daily_position = daily_position.fillna(0.5)
            features.append(daily_position.values)
            names.append('daily_price_position')
        
        # Volatility measure
        returns = close.pct_change().fillna(0)
        volatility = returns.rolling(20).std().fillna(returns.std())
        features.append(volatility.values)
        names.append('volatility_20')
        
        return np.column_stack(features), names
    
    def _extract_volume_features(self, price_data: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """Extract volume-based features.
        
        Args:
            price_data: OHLCV data
            
        Returns:
            Tuple of (features array, feature names)
        """
        features = []
        names = []
        
        if 'volume' not in price_data.columns:
            return np.array([]), []
        
        volume = price_data['volume']
        
        # Volume relative to average
        volume_sma = volume.rolling(20).mean().fillna(volume.mean())
        volume_ratio = volume / volume_sma
        features.append(volume_ratio.values)
        names.append('volume_ratio_20')
        
        # Volume trend
        volume_change = volume.pct_change(5).fillna(0)
        features.append(volume_change.values)
        names.append('volume_change_5')
        
        # On-balance volume indicator
        close = price_data['close']
        obv = (np.sign(close.diff()) * volume).cumsum()
        obv_normalized = (obv - obv.mean()) / obv.std()
        features.append(obv_normalized.values)
        names.append('obv_normalized')
        
        return np.column_stack(features), names
    
    def _extract_indicator_features(self, indicators: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """Extract raw indicator features.
        
        Args:
            indicators: Technical indicators
            
        Returns:
            Tuple of (features array, feature names)
        """
        features = []
        names = []
        
        # Normalize certain indicators
        for col in indicators.columns:
            if col in ['rsi', 'stochastic_k', 'stochastic_d']:
                # These are already 0-100, normalize to 0-1
                features.append(indicators[col].values / 100)
                names.append(f'{col}_normalized')
            elif col in ['macd', 'macd_signal', 'macd_histogram']:
                # Normalize MACD values
                values = indicators[col].values
                if values.std() > 0:
                    normalized = (values - values.mean()) / values.std()
                else:
                    normalized = values
                features.append(normalized)
                names.append(f'{col}_normalized')
        
        if features:
            return np.column_stack(features), names
        return np.array([]), []
    
    def _extract_temporal_features(self, fuzzy_data: pd.DataFrame, 
                                  lookback: int) -> Tuple[np.ndarray, List[str]]:
        """Extract temporal/lookback features.
        
        Args:
            fuzzy_data: Fuzzy membership values
            lookback: Number of periods to look back
            
        Returns:
            Tuple of (features array, feature names)
        """
        features = []
        names = []
        
        fuzzy_cols = [col for col in fuzzy_data.columns if 'membership' in col.lower()]
        
        for lag in range(1, lookback):
            for col in fuzzy_cols:
                shifted = fuzzy_data[col].shift(lag).fillna(0.5)
                features.append(shifted.values)
                names.append(f'{col}_lag{lag}')
        
        if features:
            return np.column_stack(features), names
        return np.array([]), []
    
    def _scale_features(self, features: np.ndarray) -> np.ndarray:
        """Scale features using configured method.
        
        Args:
            features: Raw feature matrix
            
        Returns:
            Scaled feature matrix
        """
        scaling_method = self.config.get('scaling_method', 'standard')
        
        if self.scaler is None:
            if scaling_method == 'standard':
                self.scaler = StandardScaler()
            elif scaling_method == 'minmax':
                self.scaler = MinMaxScaler()
            else:
                self.scaler = StandardScaler()
            
            return self.scaler.fit_transform(features)
        else:
            return self.scaler.transform(features)
    
    def calculate_feature_importance(self, model, X: torch.Tensor, y: torch.Tensor) -> Dict[str, float]:
        """Calculate feature importance using permutation.
        
        Args:
            model: Trained neural network model
            X: Feature tensor
            y: Label tensor
            
        Returns:
            Dictionary of feature importances
        """
        if not self.feature_names:
            raise ValueError("No feature names available")
        
        # Simple permutation importance
        model.eval()
        baseline_score = self._calculate_accuracy(model, X, y)
        
        importances = {}
        
        for i, feature_name in enumerate(self.feature_names):
            # Permute feature i
            X_permuted = X.clone()
            X_permuted[:, i] = X_permuted[torch.randperm(X.shape[0]), i]
            
            # Calculate new score
            permuted_score = self._calculate_accuracy(model, X_permuted, y)
            
            # Importance is drop in accuracy
            importance = baseline_score - permuted_score
            importances[feature_name] = float(importance)
        
        # Normalize importances
        total_importance = sum(abs(imp) for imp in importances.values())
        if total_importance > 0:
            importances = {k: v/total_importance for k, v in importances.items()}
        
        self.feature_importance = importances
        return importances
    
    def _calculate_accuracy(self, model, X: torch.Tensor, y: torch.Tensor) -> float:
        """Calculate model accuracy.
        
        Args:
            model: Neural network model
            X: Features
            y: Labels
            
        Returns:
            Accuracy score
        """
        with torch.no_grad():
            outputs = model(X)
            _, predicted = torch.max(outputs, 1)
            accuracy = (predicted == y).float().mean()
        return float(accuracy)