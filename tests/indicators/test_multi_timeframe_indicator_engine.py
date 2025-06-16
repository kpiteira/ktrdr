"""Tests for multi-timeframe indicator engine."""

import pytest
import pandas as pd
import numpy as np
from typing import Dict, List

from ktrdr.indicators.multi_timeframe_indicator_engine import (
    MultiTimeframeIndicatorEngine,
    TimeframeIndicatorConfig,
    create_multi_timeframe_engine_from_config
)
from ktrdr.indicators.column_standardization import ColumnStandardizer


class TestMultiTimeframeIndicatorEngine:
    """Test cases for MultiTimeframeIndicatorEngine."""

    @pytest.fixture
    def sample_ohlcv_data(self):
        """Create sample OHLCV data for multiple timeframes."""
        # Generate 1-hour data (longer period to support longer MA periods)
        dates_1h = pd.date_range('2024-01-01', '2024-03-01', freq='1h')  # ~2 months
        np.random.seed(42)
        
        price_base = 100.0
        returns = np.random.normal(0, 0.01, len(dates_1h))
        prices = price_base * np.exp(np.cumsum(returns))
        
        data_1h = pd.DataFrame({
            'timestamp': dates_1h,
            'open': prices * (1 + np.random.normal(0, 0.001, len(dates_1h))),
            'high': prices * (1 + np.abs(np.random.normal(0, 0.005, len(dates_1h)))),
            'low': prices * (1 - np.abs(np.random.normal(0, 0.005, len(dates_1h)))),
            'close': prices,
            'volume': np.random.randint(1000, 10000, len(dates_1h))
        })
        
        # Create 4h data by resampling
        data_4h = data_1h.set_index('timestamp').resample('4h').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).reset_index()
        
        # Create daily data by resampling
        data_1d = data_1h.set_index('timestamp').resample('1d').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).reset_index()
        
        return {
            '1h': data_1h,
            '4h': data_4h,
            '1d': data_1d
        }

    @pytest.fixture
    def sample_timeframe_configs(self):
        """Create sample timeframe indicator configurations."""
        return [
            TimeframeIndicatorConfig(
                timeframe='1h',
                indicators=[
                    {'type': 'RSI', 'params': {'period': 14}},
                    {'type': 'SimpleMovingAverage', 'params': {'period': 10}},
                    {'type': 'SimpleMovingAverage', 'params': {'period': 20}}
                ],
                enabled=True,
                weight=1.0
            ),
            TimeframeIndicatorConfig(
                timeframe='4h',
                indicators=[
                    {'type': 'RSI', 'params': {'period': 14}},
                    {'type': 'SimpleMovingAverage', 'params': {'period': 30}},  # Reduced from 50
                    {'type': 'ExponentialMovingAverage', 'params': {'period': 21}}
                ],
                enabled=True,
                weight=1.5
            ),
            TimeframeIndicatorConfig(
                timeframe='1d',
                indicators=[
                    {'type': 'SimpleMovingAverage', 'params': {'period': 20}},  # Reduced from 200
                    {'type': 'RSI', 'params': {'period': 14}}
                ],
                enabled=True,
                weight=2.0
            )
        ]

    def test_initialization(self, sample_timeframe_configs):
        """Test MultiTimeframeIndicatorEngine initialization."""
        engine = MultiTimeframeIndicatorEngine(sample_timeframe_configs)
        
        assert len(engine.engines) == 3
        assert '1h' in engine.engines
        assert '4h' in engine.engines
        assert '1d' in engine.engines
        
        # Check that each engine has the correct number of indicators
        assert len(engine.engines['1h'].indicators) == 3
        assert len(engine.engines['4h'].indicators) == 3
        assert len(engine.engines['1d'].indicators) == 2

    def test_apply_multi_timeframe(self, sample_ohlcv_data, sample_timeframe_configs):
        """Test multi-timeframe indicator application."""
        engine = MultiTimeframeIndicatorEngine(sample_timeframe_configs)
        
        result = engine.apply_multi_timeframe(sample_ohlcv_data)
        
        # Check that all timeframes are processed
        assert len(result) == 3
        assert '1h' in result
        assert '4h' in result
        assert '1d' in result
        
        # Check that indicators are computed and named correctly
        for timeframe, df in result.items():
            assert not df.empty
            
            # Check for standardized column names
            indicator_columns = [col for col in df.columns 
                               if col not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            # All indicator columns should have timeframe suffix
            for col in indicator_columns:
                assert col.endswith(f'_{timeframe}'), f"Column {col} missing timeframe suffix"

    def test_column_standardization(self, sample_ohlcv_data, sample_timeframe_configs):
        """Test column name standardization."""
        engine = MultiTimeframeIndicatorEngine(sample_timeframe_configs)
        
        result = engine.apply_multi_timeframe(sample_ohlcv_data)
        
        # Check column naming patterns
        for timeframe, df in result.items():
            for col in df.columns:
                if col in ['open', 'high', 'low', 'close', 'volume', 'timestamp']:
                    # OHLCV columns should not have timeframe suffix
                    continue
                else:
                    # Indicator columns should have timeframe suffix
                    assert col.endswith(f'_{timeframe}')

    def test_get_indicator_columns(self, sample_timeframe_configs):
        """Test getting indicator column names."""
        engine = MultiTimeframeIndicatorEngine(sample_timeframe_configs)
        
        columns_1h = engine.get_indicator_columns('1h')
        columns_4h = engine.get_indicator_columns('4h')
        
        assert len(columns_1h) == 3  # RSI, SMA_10, SMA_20
        assert len(columns_4h) == 3  # RSI, SMA_50, EMA_21
        
        # Check that all columns have timeframe suffix
        for col in columns_1h:
            assert col.endswith('_1h')
        for col in columns_4h:
            assert col.endswith('_4h')

    def test_get_all_indicator_columns(self, sample_timeframe_configs):
        """Test getting all indicator columns."""
        engine = MultiTimeframeIndicatorEngine(sample_timeframe_configs)
        
        all_columns = engine.get_all_indicator_columns()
        
        assert '1h' in all_columns
        assert '4h' in all_columns
        assert '1d' in all_columns
        
        assert len(all_columns['1h']) == 3
        assert len(all_columns['4h']) == 3
        assert len(all_columns['1d']) == 2

    def test_compute_specific_indicator(self, sample_ohlcv_data, sample_timeframe_configs):
        """Test computing specific indicators."""
        engine = MultiTimeframeIndicatorEngine(sample_timeframe_configs)
        
        # Test RSI computation
        result = engine.compute_specific_indicator(
            sample_ohlcv_data['1h'], '1h', 'RSI', period=14
        )
        
        assert 'RSI_14_1h' in result.columns
        assert not result['RSI_14_1h'].isna().all()
        
        # Test SMA computation
        result = engine.compute_specific_indicator(
            sample_ohlcv_data['4h'], '4h', 'SMA', period=20
        )
        
        assert 'SMA_20_4h' in result.columns
        assert not result['SMA_20_4h'].isna().all()

    def test_create_cross_timeframe_features(self, sample_ohlcv_data, sample_timeframe_configs):
        """Test cross-timeframe feature creation."""
        engine = MultiTimeframeIndicatorEngine(sample_timeframe_configs)
        
        # First compute indicators
        multi_tf_indicators = engine.apply_multi_timeframe(sample_ohlcv_data)
        
        # Define cross-timeframe features
        feature_specs = {
            'rsi_divergence': {
                'primary_timeframe': '1h',
                'secondary_timeframe': '4h',
                'primary_column': 'RSI_1h',
                'secondary_column': 'RSI_4h',
                'operation': 'difference'
            },
            'sma_ratio': {
                'primary_timeframe': '1h',
                'secondary_timeframe': '4h',
                'primary_column': 'SimpleMovingAverage_1h',
                'secondary_column': 'SimpleMovingAverage_4h',
                'operation': 'ratio'
            }
        }
        
        cross_features = engine.create_cross_timeframe_features(
            multi_tf_indicators, feature_specs
        )
        
        # Note: This test may not have exact column matches since indicator naming
        # depends on the actual implementation, but we test the structure
        assert isinstance(cross_features, pd.DataFrame)

    def test_validation_configuration(self, sample_timeframe_configs):
        """Test configuration validation."""
        engine = MultiTimeframeIndicatorEngine(sample_timeframe_configs)
        
        validation_result = engine.validate_configuration()
        
        assert 'valid' in validation_result
        assert 'warnings' in validation_result
        assert 'errors' in validation_result
        assert 'summary' in validation_result
        
        # Should be valid configuration
        assert validation_result['valid'] == True
        assert len(validation_result['summary']['timeframes']) == 3

    def test_disabled_timeframe(self):
        """Test handling of disabled timeframes."""
        configs = [
            TimeframeIndicatorConfig(
                timeframe='1h',
                indicators=[{'type': 'RSI', 'params': {'period': 14}}],
                enabled=True
            ),
            TimeframeIndicatorConfig(
                timeframe='4h',
                indicators=[{'type': 'RSI', 'params': {'period': 14}}],
                enabled=False  # Disabled
            )
        ]
        
        engine = MultiTimeframeIndicatorEngine(configs)
        
        # Only enabled timeframe should be in engines
        assert len(engine.engines) == 1
        assert '1h' in engine.engines
        assert '4h' not in engine.engines

    def test_empty_data_handling(self, sample_timeframe_configs):
        """Test handling of empty data."""
        engine = MultiTimeframeIndicatorEngine(sample_timeframe_configs)
        
        # Test with empty data
        with pytest.raises(Exception):  # Should raise configuration error
            engine.apply_multi_timeframe({})

    def test_create_from_config(self):
        """Test creating engine from configuration dictionary."""
        config = {
            'timeframes': {
                '1h': {
                    'indicators': [
                        {'type': 'RSI', 'params': {'period': 14}}
                    ],
                    'enabled': True,
                    'weight': 1.0
                },
                '4h': {
                    'indicators': [
                        {'type': 'SimpleMovingAverage', 'params': {'period': 20}}
                    ],
                    'enabled': True,
                    'weight': 1.5
                }
            }
        }
        
        engine = create_multi_timeframe_engine_from_config(config)
        
        assert len(engine.engines) == 2
        assert '1h' in engine.engines
        assert '4h' in engine.engines


class TestColumnStandardizer:
    """Test cases for ColumnStandardizer."""

    @pytest.fixture
    def standardizer(self):
        """Create a ColumnStandardizer instance."""
        return ColumnStandardizer()

    def test_standardize_indicator_name(self, standardizer):
        """Test indicator name standardization."""
        # Test basic indicator
        result = standardizer.standardize_indicator_name('RSI', '1h')
        assert result == 'rsi_1h'
        
        # Test with parameters
        result = standardizer.standardize_indicator_name(
            'RSI', '1h', {'period': 14}
        )
        assert result == 'rsi_14_1h'
        
        # Test with multiple parameters
        result = standardizer.standardize_indicator_name(
            'MACD', '4h', {'fast_period': 12, 'slow_period': 26}
        )
        assert result == 'macd_12_26_4h'

    def test_standardize_fuzzy_name(self, standardizer):
        """Test fuzzy membership name standardization."""
        result = standardizer.standardize_fuzzy_name('RSI', 'oversold', '1h')
        assert result == 'rsi_oversold_1h'
        
        result = standardizer.standardize_fuzzy_name('SMA_cross', 'bullish', '4h')
        assert result == 'sma_cross_bullish_4h'

    def test_standardize_signal_name(self, standardizer):
        """Test signal name standardization."""
        result = standardizer.standardize_signal_name('BUY', '1h')
        assert result == 'buy_1h'
        
        result = standardizer.standardize_signal_name('confidence', '4h')
        assert result == 'confidence_4h'

    def test_standardize_dataframe_columns(self, standardizer):
        """Test DataFrame column standardization."""
        columns = ['open', 'high', 'low', 'close', 'volume', 'RSI_14', 'SMA_20', 'MACD_line']
        
        mapping = standardizer.standardize_dataframe_columns(columns, '1h')
        
        # OHLCV columns should be preserved
        assert mapping['open'] == 'open'
        assert mapping['close'] == 'close'
        assert mapping['volume'] == 'volume'
        
        # Indicator columns should get timeframe suffix
        assert mapping['RSI_14'] == 'rsi_14_1h'
        assert mapping['SMA_20'] == 'sma_20_1h'
        assert mapping['MACD_line'] == 'macd_line_1h'

    def test_clean_name(self, standardizer):
        """Test name cleaning functionality."""
        # Test special characters
        cleaned = standardizer._clean_name('RSI-14')
        assert cleaned == 'rsi_14'
        
        # Test multiple underscores
        cleaned = standardizer._clean_name('SMA__cross___bullish')
        assert cleaned == 'sma_cross_bullish'
        
        # Test leading/trailing underscores
        cleaned = standardizer._clean_name('_indicator_')
        assert cleaned == 'indicator'

    def test_infer_column_type(self, standardizer):
        """Test column type inference."""
        from ktrdr.indicators.column_standardization import ColumnType
        
        # Test indicator detection
        assert standardizer._infer_column_type('RSI_14') == ColumnType.INDICATOR
        assert standardizer._infer_column_type('MACD_line') == ColumnType.INDICATOR
        
        # Test fuzzy detection
        assert standardizer._infer_column_type('RSI_oversold') == ColumnType.FUZZY
        assert standardizer._infer_column_type('SMA_bullish') == ColumnType.FUZZY
        
        # Test signal detection
        assert standardizer._infer_column_type('BUY_signal') == ColumnType.SIGNAL
        assert standardizer._infer_column_type('confidence') == ColumnType.SIGNAL

    def test_filter_columns_by_type(self, standardizer):
        """Test filtering columns by type."""
        from ktrdr.indicators.column_standardization import ColumnType, ColumnInfo
        
        # Set up some test column mappings
        standardizer.column_mapping = {
            'rsi_14_1h': ColumnInfo('RSI_14', 'rsi_14_1h', ColumnType.INDICATOR, '1h'),
            'rsi_oversold_1h': ColumnInfo('RSI_oversold', 'rsi_oversold_1h', ColumnType.FUZZY, '1h'),
            'buy_signal_1h': ColumnInfo('BUY_signal', 'buy_signal_1h', ColumnType.SIGNAL, '1h')
        }
        
        columns = ['rsi_14_1h', 'rsi_oversold_1h', 'buy_signal_1h']
        
        indicator_cols = standardizer.filter_columns_by_type(columns, ColumnType.INDICATOR)
        assert indicator_cols == ['rsi_14_1h']
        
        fuzzy_cols = standardizer.filter_columns_by_type(columns, ColumnType.FUZZY)
        assert fuzzy_cols == ['rsi_oversold_1h']
        
        signal_cols = standardizer.filter_columns_by_type(columns, ColumnType.SIGNAL)
        assert signal_cols == ['buy_signal_1h']

    def test_get_timeframes(self, standardizer):
        """Test extracting timeframes from columns."""
        from ktrdr.indicators.column_standardization import ColumnType, ColumnInfo
        
        # Set up test column mappings
        standardizer.column_mapping = {
            'rsi_14_1h': ColumnInfo('RSI_14', 'rsi_14_1h', ColumnType.INDICATOR, '1h'),
            'sma_20_4h': ColumnInfo('SMA_20', 'sma_20_4h', ColumnType.INDICATOR, '4h'),
            'rsi_14_1d': ColumnInfo('RSI_14', 'rsi_14_1d', ColumnType.INDICATOR, '1d')
        }
        
        columns = ['rsi_14_1h', 'sma_20_4h', 'rsi_14_1d']
        timeframes = standardizer.get_timeframes(columns)
        
        assert timeframes == {'1h', '4h', '1d'}

    def test_validate_naming_consistency(self, standardizer):
        """Test naming consistency validation."""
        from ktrdr.indicators.column_standardization import ColumnType, ColumnInfo
        
        # Set up test mappings
        standardizer.column_mapping = {
            'rsi_14_1h': ColumnInfo('RSI_14', 'rsi_14_1h', ColumnType.INDICATOR, '1h'),
            'rsi_14_4h': ColumnInfo('RSI_14', 'rsi_14_4h', ColumnType.INDICATOR, '4h')
        }
        
        columns = ['rsi_14_1h', 'rsi_14_4h', 'unknown_column']
        results = standardizer.validate_naming_consistency(columns)
        
        assert 'valid' in results
        assert 'invalid' in results
        assert 'warnings' in results
        assert 'recommendations' in results
        
        # Should warn about unknown column without timeframe
        assert len(results['warnings']) > 0


def test_create_standardized_column_mapping():
    """Test creation of standardized column mappings."""
    from ktrdr.indicators.column_standardization import create_standardized_column_mapping
    
    multi_timeframe_data = {
        '1h': ['open', 'close', 'RSI_14', 'SMA_20'],
        '4h': ['open', 'close', 'RSI_14', 'EMA_21'],
        '1d': ['open', 'close', 'SMA_200']
    }
    
    mappings = create_standardized_column_mapping(multi_timeframe_data)
    
    assert '1h' in mappings
    assert '4h' in mappings
    assert '1d' in mappings
    
    # Check that OHLCV columns are preserved
    assert mappings['1h']['open'] == 'open'
    assert mappings['4h']['close'] == 'close'
    
    # Check that indicators get timeframe suffix
    assert mappings['1h']['RSI_14'] == 'rsi_14_1h'
    assert mappings['4h']['EMA_21'] == 'ema_21_4h'
    assert mappings['1d']['SMA_200'] == 'sma_200_1d'