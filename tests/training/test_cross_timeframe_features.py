"""Tests for cross-timeframe feature engineering."""

import pytest
import pandas as pd
import numpy as np
from typing import Dict

from ktrdr.training.cross_timeframe_features import (
    CrossTimeframeFeatureEngineer,
    CrossTimeframeFeature,
    FeatureExtractionResult
)


class TestCrossTimeframeFeatureEngineer:
    """Test cross-timeframe feature engineering."""
    
    @pytest.fixture
    def sample_config(self):
        """Create sample configuration."""
        return {
            'enabled_features': [
                'correlation', 'divergence', 'momentum_cascade', 
                'volatility_regime', 'trend_alignment', 'seasonality'
            ],
            'normalize_features': True,
            'correlation': {'window': 20},
            'divergence': {'momentum_period': 10},
            'volatility_regime': {'percentiles': [0.33, 0.67]}
        }
    
    @pytest.fixture
    def sample_multi_timeframe_data(self):
        """Create sample multi-timeframe data."""
        np.random.seed(42)
        
        indicator_data = {}
        fuzzy_data = {}
        price_data = {}
        
        # Create data for different timeframes
        for tf_mult, tf_name in [(1, '1h'), (4, '4h'), (24, '1d')]:
            n_points = 100 // tf_mult + 50  # Ensure enough data
            
            dates = pd.date_range(
                '2024-01-01', 
                periods=n_points, 
                freq='1h' if tf_name == '1h' else ('4h' if tf_name == '4h' else '1d')
            )
            
            # Generate realistic price data
            returns = np.random.normal(0, 0.02, n_points)
            prices = 100 * np.exp(np.cumsum(returns))
            
            # Price data with OHLC
            price_data[tf_name] = pd.DataFrame({
                'timestamp': dates,
                'open': prices * 0.999,
                'high': prices * 1.002,
                'low': prices * 0.998,
                'close': prices,
                'volume': np.random.lognormal(10, 0.5, n_points).astype(int)
            })
            
            # Indicator data
            indicator_df = price_data[tf_name].copy()
            indicator_df['rsi_14'] = np.random.uniform(20, 80, n_points)
            indicator_df['sma_20'] = prices + np.random.normal(0, 1, n_points)
            indicator_df['ema_12'] = prices + np.random.normal(0, 0.5, n_points)
            indicator_data[tf_name] = indicator_df
            
            # Fuzzy data
            fuzzy_df = price_data[tf_name].copy()
            fuzzy_df['rsi_membership'] = np.random.uniform(0, 1, n_points)
            fuzzy_df['trend_membership'] = np.random.uniform(0, 1, n_points)
            fuzzy_df['momentum_membership'] = np.random.uniform(0, 1, n_points)
            fuzzy_data[tf_name] = fuzzy_df
        
        return indicator_data, fuzzy_data, price_data
    
    @pytest.fixture
    def feature_engineer(self, sample_config):
        """Create feature engineer instance."""
        return CrossTimeframeFeatureEngineer(sample_config)
    
    def test_initialization(self, feature_engineer, sample_config):
        """Test feature engineer initialization."""
        assert feature_engineer.config == sample_config
        assert len(feature_engineer.feature_extractors) > 0
        assert 'correlation' in feature_engineer.feature_extractors
        assert 'momentum_cascade' in feature_engineer.feature_extractors
    
    def test_extract_cross_timeframe_features(self, feature_engineer, sample_multi_timeframe_data):
        """Test comprehensive cross-timeframe feature extraction."""
        indicator_data, fuzzy_data, price_data = sample_multi_timeframe_data
        
        result = feature_engineer.extract_cross_timeframe_features(
            indicator_data, fuzzy_data, price_data
        )
        
        # Verify result structure
        assert isinstance(result, FeatureExtractionResult)
        assert result.features.shape[0] == 1  # Single sample
        assert result.features.shape[1] > 0   # Has features
        assert len(result.feature_names) == result.features.shape[1]
        
        # Verify feature metadata
        assert isinstance(result.feature_metadata, dict)
        assert isinstance(result.extraction_stats, dict)
        
        # Check that enabled features were extracted
        enabled_features = feature_engineer.config['enabled_features']
        for feature_type in enabled_features:
            if feature_type != 'seasonality':  # Seasonality might not always work
                assert feature_type in result.extraction_stats
                assert result.extraction_stats[feature_type] > 0
    
    def test_correlation_features(self, feature_engineer, sample_multi_timeframe_data):
        """Test correlation feature extraction."""
        indicator_data, fuzzy_data, price_data = sample_multi_timeframe_data
        
        features, names, metadata = feature_engineer._extract_correlation_features(
            indicator_data, fuzzy_data, price_data
        )
        
        # Verify correlation features
        assert len(features) > 0
        assert len(names) == len(features)
        assert 'correlations' in metadata
        
        # Check feature naming
        correlation_features = [name for name in names if 'corr' in name]
        assert len(correlation_features) > 0
        
        # Verify correlation values are in valid range
        for feature in features:
            assert -1.0 <= feature <= 1.0
    
    def test_divergence_features(self, feature_engineer, sample_multi_timeframe_data):
        """Test divergence feature extraction."""
        indicator_data, fuzzy_data, price_data = sample_multi_timeframe_data
        
        features, names, metadata = feature_engineer._extract_divergence_features(
            indicator_data, fuzzy_data, price_data
        )
        
        # Verify divergence features
        assert len(features) > 0
        assert len(names) == len(features)
        assert 'divergences' in metadata
        
        # Check feature naming
        divergence_features = [name for name in names if 'divergence' in name]
        assert len(divergence_features) > 0
        
        # Verify divergence values are non-negative
        for feature in features:
            assert feature >= 0.0
    
    def test_momentum_cascade_features(self, feature_engineer, sample_multi_timeframe_data):
        """Test momentum cascade feature extraction."""
        indicator_data, fuzzy_data, price_data = sample_multi_timeframe_data
        
        features, names, metadata = feature_engineer._extract_momentum_cascade_features(
            indicator_data, fuzzy_data, price_data
        )
        
        # Verify momentum cascade features
        assert len(features) > 0
        assert len(names) == len(features)
        assert 'momentum_cascade' in metadata
        
        # Check for specific momentum features
        cascade_features = [name for name in names if 'momentum' in name or 'cascade' in name]
        assert len(cascade_features) > 0
        
        # Verify momentum values are in reasonable range
        for feature in features:
            assert -5.0 <= feature <= 5.0  # Reasonable range for normalized momentum
    
    def test_volatility_regime_features(self, feature_engineer, sample_multi_timeframe_data):
        """Test volatility regime feature extraction."""
        indicator_data, fuzzy_data, price_data = sample_multi_timeframe_data
        
        features, names, metadata = feature_engineer._extract_volatility_regime_features(
            indicator_data, fuzzy_data, price_data
        )
        
        # Verify volatility features
        assert len(features) > 0
        assert len(names) == len(features)
        assert 'volatility_regimes' in metadata
        
        # Check for volatility regime features
        vol_features = [name for name in names if 'vol' in name]
        assert len(vol_features) > 0
        
        # Check regime encoding (should have low/med/high for each timeframe)
        regime_features = [name for name in names if 'regime' in name]
        # Should have 3 features per timeframe (low, med, high)
        assert len(regime_features) % 3 == 0
    
    def test_trend_alignment_features(self, feature_engineer, sample_multi_timeframe_data):
        """Test trend alignment feature extraction."""
        indicator_data, fuzzy_data, price_data = sample_multi_timeframe_data
        
        features, names, metadata = feature_engineer._extract_trend_alignment_features(
            indicator_data, fuzzy_data, price_data
        )
        
        # Verify trend alignment features
        assert len(features) > 0
        assert len(names) == len(features)
        assert 'trend_alignment' in metadata
        
        # Check for trend features
        trend_features = [name for name in names if 'trend' in name]
        assert len(trend_features) > 0
        
        # Verify trend values are in reasonable range
        for feature in features:
            assert -2.0 <= feature <= 2.0  # Reasonable range for trend strength
    
    def test_support_resistance_features(self, feature_engineer, sample_multi_timeframe_data):
        """Test support/resistance feature extraction."""
        indicator_data, fuzzy_data, price_data = sample_multi_timeframe_data
        
        features, names, metadata = feature_engineer._extract_support_resistance_features(
            indicator_data, fuzzy_data, price_data
        )
        
        # Verify support/resistance features
        assert len(features) > 0
        assert len(names) == len(features)
        assert 'support_resistance' in metadata
        
        # Check for support/resistance features
        sr_features = [name for name in names if 'support' in name or 'resistance' in name or 'position' in name]
        assert len(sr_features) > 0
        
        # Verify position features are in [0, 1] range
        position_features = [features[i] for i, name in enumerate(names) if 'position' in name]
        for feature in position_features:
            assert 0.0 <= feature <= 1.0
    
    def test_seasonality_features(self, feature_engineer, sample_multi_timeframe_data):
        """Test seasonality feature extraction."""
        indicator_data, fuzzy_data, price_data = sample_multi_timeframe_data
        
        features, names, metadata = feature_engineer._extract_seasonality_features(
            indicator_data, fuzzy_data, price_data
        )
        
        # Verify seasonality features
        assert len(features) > 0
        assert len(names) == len(features)
        assert 'seasonality' in metadata
        
        # Check for time-based features
        time_features = [name for name in names if any(x in name for x in ['hour', 'day', 'month'])]
        assert len(time_features) > 0
        
        # Verify cyclical encoding values are in [-1, 1] range
        for feature in features:
            assert -1.0 <= feature <= 1.0
    
    def test_feature_normalization(self, feature_engineer, sample_multi_timeframe_data):
        """Test feature normalization."""
        indicator_data, fuzzy_data, price_data = sample_multi_timeframe_data
        
        # Create features with extreme values
        extreme_features = np.array([[1000, -1000, 0.5, 999999]])
        
        normalized = feature_engineer._normalize_features(extreme_features)
        
        # Verify normalization
        assert normalized.shape == extreme_features.shape
        assert np.all(normalized >= -3.0)  # Clipped values
        assert np.all(normalized <= 3.0)
    
    def test_helper_methods(self, feature_engineer):
        """Test helper methods."""
        
        # Test timeframe to minutes conversion
        assert feature_engineer._timeframe_to_minutes('1h') == 60
        assert feature_engineer._timeframe_to_minutes('4h') == 240
        assert feature_engineer._timeframe_to_minutes('1d') == 1440
        assert feature_engineer._timeframe_to_minutes('unknown') == 60  # Default
        
        # Test correlation calculation
        series1 = pd.Series([1, 2, 3, 4, 5])
        series2 = pd.Series([2, 4, 6, 8, 10])  # Perfect correlation
        corr = feature_engineer._calculate_aligned_correlation(series1, series2, '1h', '4h')
        assert abs(corr - 1.0) < 0.01  # Should be close to 1
        
        # Test momentum calculation
        price_series = pd.Series([100, 102, 101, 105, 103])
        momentum = feature_engineer._calculate_momentum(price_series)
        assert isinstance(momentum, float)
        assert -1.0 <= momentum <= 1.0  # Normalized
    
    def test_feature_definitions(self, feature_engineer):
        """Test feature definitions."""
        definitions = feature_engineer.get_feature_definitions()
        
        assert len(definitions) > 0
        assert all(isinstance(fd, CrossTimeframeFeature) for fd in definitions)
        
        # Check that all defined features have required attributes
        for fd in definitions:
            assert fd.name
            assert fd.description
            assert fd.feature_type
            assert isinstance(fd.timeframes, list)
            assert isinstance(fd.parameters, dict)
    
    def test_error_handling(self, feature_engineer):
        """Test error handling with invalid data."""
        
        # Test with empty data
        empty_data = {'1h': pd.DataFrame(), '4h': pd.DataFrame()}
        
        try:
            result = feature_engineer.extract_cross_timeframe_features(
                empty_data, empty_data, empty_data
            )
            # Should either succeed with zero features or raise ValueError
            if result.features.shape[1] == 0:
                assert len(result.feature_names) == 0
        except ValueError:
            pass  # Expected for empty data
        
        # Test with missing timeframes
        partial_data = {
            '1h': pd.DataFrame({
                'timestamp': pd.date_range('2024-01-01', periods=10, freq='1h'),
                'close': np.random.randn(10)
            })
        }
        
        # Should handle missing timeframes gracefully
        result = feature_engineer.extract_cross_timeframe_features(
            partial_data, partial_data, partial_data
        )
        assert isinstance(result, FeatureExtractionResult)
    
    def test_configuration_variations(self, sample_multi_timeframe_data):
        """Test different configuration options."""
        indicator_data, fuzzy_data, price_data = sample_multi_timeframe_data
        
        # Test with minimal features
        minimal_config = {
            'enabled_features': ['correlation'],
            'normalize_features': False
        }
        
        minimal_engineer = CrossTimeframeFeatureEngineer(minimal_config)
        result = minimal_engineer.extract_cross_timeframe_features(
            indicator_data, fuzzy_data, price_data
        )
        
        assert result.features.shape[1] > 0
        assert 'correlation' in result.extraction_stats
        
        # Test with all features disabled
        empty_config = {
            'enabled_features': [],
            'normalize_features': True
        }
        
        empty_engineer = CrossTimeframeFeatureEngineer(empty_config)
        
        # Should raise ValueError for no features
        with pytest.raises(ValueError, match="No features extracted"):
            empty_engineer.extract_cross_timeframe_features(
                indicator_data, fuzzy_data, price_data
            )


class TestFeatureExtractionEdgeCases:
    """Test edge cases in feature extraction."""
    
    def test_single_timeframe(self):
        """Test feature extraction with single timeframe."""
        config = {
            'enabled_features': ['correlation', 'momentum_cascade'],
            'normalize_features': True
        }
        
        engineer = CrossTimeframeFeatureEngineer(config)
        
        # Single timeframe data
        dates = pd.date_range('2024-01-01', periods=50, freq='1h')
        prices = 100 + np.cumsum(np.random.normal(0, 1, 50))
        
        single_tf_data = {
            '1h': pd.DataFrame({
                'timestamp': dates,
                'close': prices,
                'rsi_14': np.random.uniform(20, 80, 50)
            })
        }
        
        result = engineer.extract_cross_timeframe_features(
            single_tf_data, single_tf_data, single_tf_data
        )
        
        # Should extract features even with single timeframe
        assert isinstance(result, FeatureExtractionResult)
        # Some features may be zero or missing for single timeframe
    
    def test_insufficient_data(self):
        """Test feature extraction with insufficient data."""
        config = {
            'enabled_features': ['correlation', 'volatility_regime'],
            'normalize_features': True
        }
        
        engineer = CrossTimeframeFeatureEngineer(config)
        
        # Very small datasets
        small_data = {}
        for tf in ['1h', '4h']:
            dates = pd.date_range('2024-01-01', periods=5, freq='1h')
            small_data[tf] = pd.DataFrame({
                'timestamp': dates,
                'close': [100, 101, 99, 102, 98],
                'rsi_14': [50, 55, 45, 60, 40]
            })
        
        result = engineer.extract_cross_timeframe_features(
            small_data, small_data, small_data
        )
        
        # Should handle gracefully, possibly with zero/default features
        assert isinstance(result, FeatureExtractionResult)
    
    def test_data_quality_issues(self):
        """Test feature extraction with data quality issues."""
        config = {
            'enabled_features': ['correlation', 'trend_alignment'],
            'normalize_features': True
        }
        
        engineer = CrossTimeframeFeatureEngineer(config)
        
        # Data with NaN values and outliers
        dates = pd.date_range('2024-01-01', periods=50, freq='1h')
        prices = 100 + np.cumsum(np.random.normal(0, 1, 50))
        
        # Introduce data quality issues
        prices[10:15] = np.nan  # Missing values
        prices[20] = 10000      # Outlier
        
        quality_issue_data = {
            '1h': pd.DataFrame({
                'timestamp': dates,
                'close': prices,
                'rsi_14': np.random.uniform(20, 80, 50)
            }),
            '4h': pd.DataFrame({
                'timestamp': dates[::4],
                'close': prices[::4],
                'rsi_14': np.random.uniform(20, 80, len(dates[::4]))
            })
        }
        
        # Should handle data quality issues without crashing
        result = engineer.extract_cross_timeframe_features(
            quality_issue_data, quality_issue_data, quality_issue_data
        )
        
        assert isinstance(result, FeatureExtractionResult)
        # Features should be finite
        assert np.all(np.isfinite(result.features))


if __name__ == "__main__":
    pytest.main([__file__])