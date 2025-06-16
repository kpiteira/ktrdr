"""Tests for multi-timeframe data preparation."""

import pytest
import pandas as pd
import numpy as np
import torch
from unittest.mock import Mock, patch

from ktrdr.training.data_preparation import (
    MultiTimeframeDataPreparator,
    DataPreparationConfig,
    TrainingSequence,
    DataQualityReport,
    create_default_preparation_config
)


class TestDataPreparationConfig:
    """Test data preparation configuration."""
    
    def test_default_config_creation(self):
        """Test default configuration creation."""
        config = create_default_preparation_config()
        
        assert isinstance(config, DataPreparationConfig)
        assert config.sequence_length > 0
        assert config.prediction_horizon > 0
        assert 0.0 <= config.overlap_ratio <= 1.0
        assert 0.0 <= config.min_data_quality <= 1.0
        assert isinstance(config.timeframe_weights, dict)
    
    def test_custom_config_creation(self):
        """Test custom configuration creation."""
        config = DataPreparationConfig(
            sequence_length=200,
            prediction_horizon=10,
            overlap_ratio=0.4,
            min_data_quality=0.9,
            timeframe_weights={"1h": 1.0, "4h": 0.7}
        )
        
        assert config.sequence_length == 200
        assert config.prediction_horizon == 10
        assert config.overlap_ratio == 0.4
        assert config.min_data_quality == 0.9
        assert config.timeframe_weights["1h"] == 1.0
        assert config.timeframe_weights["4h"] == 0.7


class TestMultiTimeframeDataPreparator:
    """Test multi-timeframe data preparator."""
    
    @pytest.fixture
    def sample_config(self):
        """Create sample configuration."""
        return DataPreparationConfig(
            sequence_length=50,
            prediction_horizon=5,
            overlap_ratio=0.3,
            min_data_quality=0.8,
            timeframe_weights={"1h": 1.0, "4h": 0.8, "1d": 0.6}
        )
    
    @pytest.fixture
    def preparator(self, sample_config):
        """Create data preparator instance."""
        return MultiTimeframeDataPreparator(sample_config)
    
    @pytest.fixture
    def sample_multi_timeframe_data(self):
        """Create comprehensive sample data."""
        np.random.seed(42)
        
        indicator_data = {}
        fuzzy_data = {}
        price_data = {}
        
        base_dates = pd.date_range('2024-01-01', periods=1000, freq='1h')
        base_prices = 100 + np.cumsum(np.random.normal(0, 1, 1000))
        
        for tf_mult, tf_name in [(1, '1h'), (4, '4h'), (24, '1d')]:
            # Subsample for different timeframes
            tf_dates = base_dates[::tf_mult]
            tf_prices = base_prices[::tf_mult]
            n_points = len(tf_dates)
            
            # Price data
            price_df = pd.DataFrame({
                'timestamp': tf_dates,
                'open': tf_prices * 0.999,
                'high': tf_prices * 1.002,
                'low': tf_prices * 0.998,
                'close': tf_prices,
                'volume': np.random.lognormal(10, 0.5, n_points).astype(int)
            })
            price_data[tf_name] = price_df
            
            # Indicator data
            indicator_df = price_df.copy()
            indicator_df['rsi_14'] = np.random.uniform(20, 80, n_points)
            indicator_df['sma_20'] = tf_prices + np.random.normal(0, 1, n_points)
            indicator_df['ema_12'] = tf_prices + np.random.normal(0, 0.5, n_points)
            indicator_data[tf_name] = indicator_df
            
            # Fuzzy data
            fuzzy_df = price_df.copy()
            fuzzy_df['rsi_membership'] = np.random.uniform(0, 1, n_points)
            fuzzy_df['trend_membership'] = np.random.uniform(0, 1, n_points)
            fuzzy_df['momentum_membership'] = np.random.uniform(0, 1, n_points)
            fuzzy_data[tf_name] = fuzzy_df
        
        return indicator_data, fuzzy_data, price_data
    
    def test_initialization(self, preparator, sample_config):
        """Test preparator initialization."""
        assert preparator.config == sample_config
        assert hasattr(preparator, 'quality_thresholds')
        assert preparator.quality_thresholds['completeness_min'] > 0
    
    def test_assess_data_quality(self, preparator, sample_multi_timeframe_data):
        """Test data quality assessment."""
        indicator_data, fuzzy_data, price_data = sample_multi_timeframe_data
        
        quality_report = preparator.assess_data_quality(indicator_data, fuzzy_data, price_data)
        
        # Verify report structure
        assert isinstance(quality_report, DataQualityReport)
        assert len(quality_report.timeframe_completeness) == 3
        assert 0.0 <= quality_report.overall_quality_score <= 1.0
        assert isinstance(quality_report.recommendations, list)
        
        # Verify timeframe assessments
        for tf in ['1h', '4h', '1d']:
            assert tf in quality_report.timeframe_completeness
            assert 0.0 <= quality_report.timeframe_completeness[tf] <= 1.0
            assert tf in quality_report.missing_data_summary
            assert tf in quality_report.outlier_detection
    
    def test_clean_and_align_data(self, preparator, sample_multi_timeframe_data):
        """Test data cleaning and alignment."""
        indicator_data, fuzzy_data, price_data = sample_multi_timeframe_data
        
        # Introduce some data quality issues
        price_data['1h'].loc[10:15, 'close'] = np.nan  # Missing values
        price_data['4h'].loc[5, 'close'] = 10000        # Outlier
        
        cleaned_indicator, cleaned_fuzzy, cleaned_price = preparator._clean_and_align_data(
            indicator_data, fuzzy_data, price_data
        )
        
        # Verify cleaning
        assert len(cleaned_indicator) <= len(indicator_data)
        assert len(cleaned_fuzzy) <= len(fuzzy_data)  
        assert len(cleaned_price) <= len(price_data)
        
        # Check that data is cleaned
        for tf, df in cleaned_price.items():
            if not df.empty:
                # Should have no NaN values in numeric columns
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                assert not df[numeric_cols].isna().any().any()
    
    def test_generate_training_labels(self, preparator, sample_multi_timeframe_data):
        """Test training label generation."""
        _, _, price_data = sample_multi_timeframe_data
        
        labels = preparator._generate_training_labels(price_data)
        
        # Verify labels
        assert isinstance(labels, pd.Series)
        assert len(labels) > 0
        assert labels.dtype in [np.int64, np.int32]  # Integer labels
        assert set(labels.unique()).issubset({0, 1, 2})  # Valid trading signals
    
    def test_create_temporal_alignment(self, preparator, sample_multi_timeframe_data):
        """Test temporal alignment creation."""
        indicator_data, fuzzy_data, price_data = sample_multi_timeframe_data
        
        # Create mock labels
        primary_timeframe = '1h'
        n_labels = len(price_data[primary_timeframe])
        labels = pd.Series(
            np.random.choice([0, 1, 2], n_labels),
            index=price_data[primary_timeframe]['timestamp']
        )
        
        aligned_data = preparator._create_temporal_alignment(
            indicator_data, fuzzy_data, price_data, labels
        )
        
        # Verify alignment
        assert 'timestamps' in aligned_data
        assert 'labels' in aligned_data
        assert 'indicator_data' in aligned_data
        assert 'fuzzy_data' in aligned_data
        assert 'price_data' in aligned_data
        
        # Check data consistency
        assert len(aligned_data['timestamps']) == len(aligned_data['labels'])
        
        # Verify all timeframes are represented
        for tf in price_data.keys():
            if tf in aligned_data['price_data']:
                aligned_df = aligned_data['price_data'][tf]
                assert 'timestamp' in aligned_df.columns
    
    def test_create_training_sequences(self, preparator):
        """Test training sequence creation."""
        # Create mock aligned data
        n_points = 200
        timestamps = pd.date_range('2024-01-01', periods=n_points, freq='1h')
        labels = pd.Series(np.random.choice([0, 1, 2], n_points), index=timestamps)
        
        # Mock data structure
        aligned_data = {
            'timestamps': timestamps,
            'labels': labels,
            'indicator_data': {
                '1h': pd.DataFrame({
                    'timestamp': timestamps,
                    'rsi_14': np.random.uniform(20, 80, n_points)
                })
            },
            'fuzzy_data': {
                '1h': pd.DataFrame({
                    'timestamp': timestamps,
                    'rsi_membership': np.random.uniform(0, 1, n_points)
                })
            },
            'price_data': {
                '1h': pd.DataFrame({
                    'timestamp': timestamps,
                    'close': 100 + np.cumsum(np.random.normal(0, 1, n_points))
                })
            }
        }
        
        sequences = preparator._create_training_sequences(aligned_data)
        
        # Verify sequences
        assert len(sequences) > 0
        assert all('features' in seq for seq in sequences)
        assert all('label' in seq for seq in sequences)
        assert all('timestamps' in seq for seq in sequences)
        
        # Check sequence properties
        for seq in sequences:
            assert len(seq['features']) > 0  # Has features
            assert seq['label'] in [0, 1, 2]  # Valid label
            assert len(seq['timestamps']) == preparator.config.sequence_length
    
    def test_prepare_training_data_full_pipeline(self, preparator, sample_multi_timeframe_data):
        """Test complete training data preparation pipeline."""
        indicator_data, fuzzy_data, price_data = sample_multi_timeframe_data
        
        train_seq, val_seq, quality_report = preparator.prepare_training_data(
            indicator_data, fuzzy_data, price_data, validation_split=0.2
        )
        
        # Verify training sequence
        assert isinstance(train_seq, TrainingSequence)
        assert train_seq.features.shape[0] > 0  # Has samples
        assert train_seq.features.shape[1] > 0  # Has features
        assert len(train_seq.labels) == train_seq.features.shape[0]
        assert train_seq.metadata['dataset_type'] == 'training'
        
        # Verify validation sequence
        assert isinstance(val_seq, TrainingSequence)
        assert val_seq.features.shape[0] > 0
        assert val_seq.features.shape[1] == train_seq.features.shape[1]  # Same features
        assert len(val_seq.labels) == val_seq.features.shape[0]
        assert val_seq.metadata['dataset_type'] == 'validation'
        
        # Verify quality report
        assert isinstance(quality_report, DataQualityReport)
        assert quality_report.overall_quality_score >= 0.0
        
        # Verify data split
        total_samples = train_seq.features.shape[0] + val_seq.features.shape[0]
        val_ratio = val_seq.features.shape[0] / total_samples
        assert 0.15 <= val_ratio <= 0.25  # Approximately 20% validation
    
    def test_edge_cases(self, preparator):
        """Test edge cases and error handling."""
        
        # Test with empty data
        empty_data = {'1h': pd.DataFrame(), '4h': pd.DataFrame()}
        
        quality_report = preparator.assess_data_quality(empty_data, empty_data, empty_data)
        assert quality_report.overall_quality_score >= 0.0
        
        # Test with single timeframe
        single_tf_data = {
            '1h': pd.DataFrame({
                'timestamp': pd.date_range('2024-01-01', periods=100, freq='1h'),
                'close': 100 + np.cumsum(np.random.normal(0, 1, 100)),
                'rsi_14': np.random.uniform(20, 80, 100)
            })
        }
        
        quality_report = preparator.assess_data_quality(
            single_tf_data, single_tf_data, single_tf_data
        )
        assert '1h' in quality_report.timeframe_completeness
    
    def test_insufficient_data_quality(self, sample_config):
        """Test handling of insufficient data quality."""
        # Create preparator with high quality threshold
        high_quality_config = DataPreparationConfig(
            sequence_length=50,
            prediction_horizon=5,
            overlap_ratio=0.3,
            min_data_quality=0.95  # Very high threshold
        )
        
        preparator = MultiTimeframeDataPreparator(high_quality_config)
        
        # Create low quality data (lots of missing values)
        low_quality_data = {
            '1h': pd.DataFrame({
                'timestamp': pd.date_range('2024-01-01', periods=100, freq='1h'),
                'close': [np.nan] * 50 + list(range(50))  # 50% missing
            })
        }
        
        quality_report = preparator.assess_data_quality(
            low_quality_data, low_quality_data, low_quality_data
        )
        
        # Should report low quality
        assert quality_report.overall_quality_score < 0.95
        assert len(quality_report.recommendations) > 0
    
    def test_timeframe_to_minutes_helper(self, preparator):
        """Test timeframe conversion helper."""
        assert preparator._timeframe_to_minutes('1m') == 1
        assert preparator._timeframe_to_minutes('1h') == 60
        assert preparator._timeframe_to_minutes('4h') == 240
        assert preparator._timeframe_to_minutes('1d') == 1440
        assert preparator._timeframe_to_minutes('1w') == 10080
        assert preparator._timeframe_to_minutes('unknown') == 60  # Default


class TestTrainingSequence:
    """Test TrainingSequence data structure."""
    
    def test_training_sequence_creation(self):
        """Test TrainingSequence creation and properties."""
        features = torch.randn(100, 20)  # 100 samples, 20 features
        labels = torch.randint(0, 3, (100,))  # 100 labels
        timestamps = pd.date_range('2024-01-01', periods=100, freq='1h')
        metadata = {'dataset_type': 'training', 'sequence_count': 100}
        
        sequence = TrainingSequence(
            features=features,
            labels=labels,
            timestamps=timestamps,
            metadata=metadata
        )
        
        assert torch.equal(sequence.features, features)
        assert torch.equal(sequence.labels, labels)
        assert sequence.timestamps.equals(timestamps)
        assert sequence.metadata == metadata
    
    def test_empty_training_sequence(self):
        """Test empty TrainingSequence creation."""
        empty_sequence = TrainingSequence(
            features=torch.empty(0, 0),
            labels=torch.empty(0, dtype=torch.long),
            timestamps=pd.DatetimeIndex([]),
            metadata={'dataset_type': 'empty', 'sequence_count': 0}
        )
        
        assert empty_sequence.features.shape == (0, 0)
        assert empty_sequence.labels.shape == (0,)
        assert len(empty_sequence.timestamps) == 0
        assert empty_sequence.metadata['sequence_count'] == 0


class TestDataQualityAssessment:
    """Test detailed data quality assessment."""
    
    @pytest.fixture
    def preparator(self):
        """Create preparator for quality tests."""
        config = DataPreparationConfig()
        return MultiTimeframeDataPreparator(config)
    
    def test_assess_timeframe_quality_perfect_data(self, preparator):
        """Test quality assessment with perfect data."""
        perfect_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=100, freq='1h'),
            'close': range(100),
            'rsi_14': range(100)
        })
        
        quality = preparator._assess_timeframe_quality('1h', perfect_df, None, perfect_df)
        
        assert quality['completeness'] == 1.0
        assert quality['outliers']['ratio'] == 0.0
        assert quality['temporal_consistency']['score'] == 1.0
    
    def test_assess_timeframe_quality_missing_data(self, preparator):
        """Test quality assessment with missing data."""
        missing_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=100, freq='1h'),
            'close': [np.nan] * 50 + list(range(50)),  # 50% missing
            'rsi_14': list(range(100))
        })
        
        quality = preparator._assess_timeframe_quality('1h', missing_df, None, missing_df)
        
        assert quality['completeness'] < 1.0
        assert quality['missing_data']['price']['missing_ratio'] > 0.0
    
    def test_assess_timeframe_quality_outliers(self, preparator):
        """Test quality assessment with outliers."""
        outlier_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=100, freq='1h'),
            'close': [100] * 95 + [10000] * 5,  # 5 extreme outliers
            'rsi_14': range(100)
        })
        
        quality = preparator._assess_timeframe_quality('1h', outlier_df, None, outlier_df)
        
        assert quality['outliers']['ratio'] > 0.0
        assert quality['outliers']['count'] > 0
    
    def test_assess_timeframe_quality_temporal_gaps(self, preparator):
        """Test quality assessment with temporal gaps."""
        # Create timestamps with gaps
        dates = list(pd.date_range('2024-01-01', periods=50, freq='1h'))
        dates.extend(list(pd.date_range('2024-01-03', periods=50, freq='1h')))  # 2-day gap
        
        gap_df = pd.DataFrame({
            'timestamp': dates,
            'close': range(100),
            'rsi_14': range(100)
        })
        
        quality = preparator._assess_timeframe_quality('1h', gap_df, None, gap_df)
        
        assert quality['temporal_consistency']['score'] < 1.0
        assert len(quality['temporal_consistency']['gaps']) > 0


class TestDataAlignment:
    """Test data alignment functionality."""
    
    @pytest.fixture
    def preparator(self):
        """Create preparator for alignment tests."""
        config = DataPreparationConfig()
        return MultiTimeframeDataPreparator(config)
    
    def test_filter_by_time_range(self, preparator):
        """Test time range filtering."""
        full_data = {
            '1h': pd.DataFrame({
                'timestamp': pd.date_range('2024-01-01', periods=240, freq='1h'),  # 10 days
                'close': range(240)
            })
        }
        
        min_time = pd.Timestamp('2024-01-02')
        max_time = pd.Timestamp('2024-01-05')
        
        filtered = preparator._filter_by_time_range(full_data, min_time, max_time)
        
        assert '1h' in filtered
        filtered_df = filtered['1h']
        assert all(filtered_df['timestamp'] >= min_time)
        assert all(filtered_df['timestamp'] <= max_time)
        assert len(filtered_df) < len(full_data['1h'])
    
    def test_align_to_timestamps(self, preparator):
        """Test timestamp alignment."""
        source_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=100, freq='1h'),
            'value': range(100)
        })
        
        target_timestamps = pd.date_range('2024-01-01 12:00:00', periods=24, freq='1h')
        
        aligned_df = preparator._align_to_timestamps(source_df, target_timestamps)
        
        assert len(aligned_df) == len(target_timestamps)
        assert 'timestamp' in aligned_df.columns
        assert aligned_df['timestamp'].equals(target_timestamps)
        # Values should be forward filled
        assert not aligned_df['value'].isna().any()


if __name__ == "__main__":
    pytest.main([__file__])