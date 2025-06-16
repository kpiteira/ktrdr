"""Advanced data preparation for multi-timeframe neural network training.

This module handles the complex task of preparing, aligning, and synchronizing
data across multiple timeframes for neural network training.
"""

import pandas as pd
import numpy as np
import torch
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import warnings

from ktrdr import get_logger
from ktrdr.training.zigzag_labeler import ZigZagLabeler

logger = get_logger(__name__)


@dataclass
class TrainingSequence:
    """A training sequence with features and labels."""
    features: torch.Tensor
    labels: torch.Tensor
    timestamps: pd.DatetimeIndex
    metadata: Dict[str, Any]


@dataclass
class DataPreparationConfig:
    """Configuration for data preparation."""
    sequence_length: int = 100  # Number of time steps in sequence
    prediction_horizon: int = 5  # Steps ahead to predict
    overlap_ratio: float = 0.5  # Overlap between sequences
    min_data_quality: float = 0.8  # Minimum data quality threshold
    timeframe_weights: Dict[str, float] = None  # Weights for different timeframes
    

@dataclass
class DataQualityReport:
    """Report on data quality across timeframes."""
    timeframe_completeness: Dict[str, float]
    missing_data_summary: Dict[str, Any]
    outlier_detection: Dict[str, Any]
    temporal_consistency: Dict[str, Any]
    overall_quality_score: float
    recommendations: List[str]


class MultiTimeframeDataPreparator:
    """Advanced data preparation for multi-timeframe neural network training."""
    
    def __init__(self, config: DataPreparationConfig):
        """
        Initialize data preparator.
        
        Args:
            config: Data preparation configuration
        """
        self.config = config
        self.logger = get_logger(__name__)
        
        # Initialize quality thresholds
        self.quality_thresholds = {
            'completeness_min': 0.85,
            'outlier_max_ratio': 0.05,
            'temporal_gap_max': 0.1
        }
        
        self.logger.info("Initialized MultiTimeframeDataPreparator")
    
    def prepare_training_data(
        self,
        indicator_data: Dict[str, pd.DataFrame],
        fuzzy_data: Dict[str, pd.DataFrame],
        price_data: Dict[str, pd.DataFrame],
        labels: Optional[pd.Series] = None,
        validation_split: float = 0.2
    ) -> Tuple[TrainingSequence, TrainingSequence, DataQualityReport]:
        """
        Prepare complete training and validation datasets.
        
        Args:
            indicator_data: Dict mapping timeframes to indicator DataFrames
            fuzzy_data: Dict mapping timeframes to fuzzy membership DataFrames
            price_data: Dict mapping timeframes to OHLCV DataFrames
            labels: Optional pre-computed labels
            validation_split: Fraction of data for validation
            
        Returns:
            Tuple of (training_sequence, validation_sequence, quality_report)
        """
        self.logger.info("Preparing multi-timeframe training data")
        
        # Step 1: Quality assessment and cleaning
        quality_report = self.assess_data_quality(indicator_data, fuzzy_data, price_data)
        
        if quality_report.overall_quality_score < self.config.min_data_quality:
            self.logger.warning(f"Data quality score {quality_report.overall_quality_score:.3f} "
                              f"below threshold {self.config.min_data_quality}")
        
        # Step 2: Clean and align data
        cleaned_indicator_data, cleaned_fuzzy_data, cleaned_price_data = self._clean_and_align_data(
            indicator_data, fuzzy_data, price_data
        )
        
        # Step 3: Generate labels if not provided
        if labels is None:
            labels = self._generate_training_labels(cleaned_price_data)
        
        # Step 4: Create temporal alignment
        aligned_data = self._create_temporal_alignment(
            cleaned_indicator_data, cleaned_fuzzy_data, cleaned_price_data, labels
        )
        
        # Step 5: Create training sequences
        all_sequences = self._create_training_sequences(aligned_data)
        
        # Step 6: Split into training and validation
        split_index = int(len(all_sequences) * (1 - validation_split))
        
        train_sequences = all_sequences[:split_index]
        val_sequences = all_sequences[split_index:]
        
        # Step 7: Convert to TrainingSequence objects
        training_sequence = self._combine_sequences(train_sequences, "training")
        validation_sequence = self._combine_sequences(val_sequences, "validation")
        
        self.logger.info(f"Prepared {len(train_sequences)} training and {len(val_sequences)} validation sequences")
        
        return training_sequence, validation_sequence, quality_report
    
    def assess_data_quality(
        self,
        indicator_data: Dict[str, pd.DataFrame],
        fuzzy_data: Dict[str, pd.DataFrame],
        price_data: Dict[str, pd.DataFrame]
    ) -> DataQualityReport:
        """
        Assess data quality across all timeframes.
        
        Args:
            indicator_data: Indicator data by timeframe
            fuzzy_data: Fuzzy data by timeframe
            price_data: Price data by timeframe
            
        Returns:
            Comprehensive data quality report
        """
        self.logger.debug("Assessing data quality")
        
        timeframe_completeness = {}
        missing_data_summary = {}
        outlier_detection = {}
        temporal_consistency = {}
        recommendations = []
        
        all_timeframes = set(indicator_data.keys()) | set(fuzzy_data.keys()) | set(price_data.keys())
        
        for timeframe in all_timeframes:
            tf_quality = self._assess_timeframe_quality(
                timeframe,
                indicator_data.get(timeframe),
                fuzzy_data.get(timeframe),
                price_data.get(timeframe)
            )
            
            timeframe_completeness[timeframe] = tf_quality['completeness']
            missing_data_summary[timeframe] = tf_quality['missing_data']
            outlier_detection[timeframe] = tf_quality['outliers']
            temporal_consistency[timeframe] = tf_quality['temporal_consistency']
            
            # Add recommendations based on quality issues
            if tf_quality['completeness'] < self.quality_thresholds['completeness_min']:
                recommendations.append(f"Timeframe {timeframe}: Low data completeness ({tf_quality['completeness']:.2f})")
            
            if tf_quality['outliers']['ratio'] > self.quality_thresholds['outlier_max_ratio']:
                recommendations.append(f"Timeframe {timeframe}: High outlier ratio ({tf_quality['outliers']['ratio']:.2f})")
        
        # Calculate overall quality score
        quality_scores = [
            np.mean(list(timeframe_completeness.values())),
            1.0 - np.mean([od['ratio'] for od in outlier_detection.values()]),
            np.mean([tc['score'] for tc in temporal_consistency.values()])
        ]
        overall_quality_score = np.mean(quality_scores)
        
        return DataQualityReport(
            timeframe_completeness=timeframe_completeness,
            missing_data_summary=missing_data_summary,
            outlier_detection=outlier_detection,
            temporal_consistency=temporal_consistency,
            overall_quality_score=overall_quality_score,
            recommendations=recommendations
        )
    
    def _assess_timeframe_quality(
        self,
        timeframe: str,
        indicator_df: Optional[pd.DataFrame],
        fuzzy_df: Optional[pd.DataFrame],
        price_df: Optional[pd.DataFrame]
    ) -> Dict[str, Any]:
        """Assess quality for a single timeframe."""
        
        quality_assessment = {
            'completeness': 0.0,
            'missing_data': {},
            'outliers': {'count': 0, 'ratio': 0.0},
            'temporal_consistency': {'score': 0.0, 'gaps': []}
        }
        
        # Combine all dataframes for this timeframe
        all_dfs = [df for df in [indicator_df, fuzzy_df, price_df] if df is not None]
        
        if not all_dfs:
            return quality_assessment
        
        # Use the largest dataframe as reference
        reference_df = max(all_dfs, key=len)
        
        # Completeness assessment
        total_possible_data = len(reference_df) * len(reference_df.columns)
        actual_data = total_possible_data - reference_df.isna().sum().sum()
        completeness = actual_data / total_possible_data if total_possible_data > 0 else 0.0
        
        quality_assessment['completeness'] = completeness
        
        # Missing data summary
        missing_summary = {}
        for df_name, df in zip(['indicators', 'fuzzy', 'price'], [indicator_df, fuzzy_df, price_df]):
            if df is not None:
                missing_count = df.isna().sum().sum()
                total_values = len(df) * len(df.columns)
                missing_summary[df_name] = {
                    'missing_count': int(missing_count),
                    'total_values': int(total_values),
                    'missing_ratio': float(missing_count / total_values) if total_values > 0 else 0.0
                }
        
        quality_assessment['missing_data'] = missing_summary
        
        # Outlier detection (using IQR method on numeric columns)
        numeric_columns = reference_df.select_dtypes(include=[np.number]).columns
        outlier_count = 0
        
        for col in numeric_columns:
            Q1 = reference_df[col].quantile(0.25)
            Q3 = reference_df[col].quantile(0.75)
            IQR = Q3 - Q1
            
            if IQR > 0:
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                outliers = ((reference_df[col] < lower_bound) | (reference_df[col] > upper_bound)).sum()
                outlier_count += outliers
        
        total_numeric_values = len(reference_df) * len(numeric_columns)
        outlier_ratio = outlier_count / total_numeric_values if total_numeric_values > 0 else 0.0
        
        quality_assessment['outliers'] = {
            'count': int(outlier_count),
            'ratio': float(outlier_ratio)
        }
        
        # Temporal consistency (check for gaps in timestamps if available)
        temporal_score = 1.0
        temporal_gaps = []
        
        if 'timestamp' in reference_df.columns:
            timestamps = pd.to_datetime(reference_df['timestamp'])
            time_diffs = timestamps.diff().dropna()
            
            if len(time_diffs) > 0:
                expected_interval = time_diffs.mode().iloc[0] if len(time_diffs.mode()) > 0 else time_diffs.median()
                
                # Find significant gaps (more than 2x expected interval)
                large_gaps = time_diffs[time_diffs > 2 * expected_interval]
                
                if len(large_gaps) > 0:
                    gap_ratio = len(large_gaps) / len(time_diffs)
                    temporal_score = max(0.0, 1.0 - gap_ratio)
                    temporal_gaps = large_gaps.tolist()
        
        quality_assessment['temporal_consistency'] = {
            'score': float(temporal_score),
            'gaps': [str(gap) for gap in temporal_gaps[:10]]  # Limit to first 10 gaps
        }
        
        return quality_assessment
    
    def _clean_and_align_data(
        self,
        indicator_data: Dict[str, pd.DataFrame],
        fuzzy_data: Dict[str, pd.DataFrame],
        price_data: Dict[str, pd.DataFrame]
    ) -> Tuple[Dict[str, pd.DataFrame], Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]]:
        """Clean and temporally align data across timeframes."""
        
        self.logger.debug("Cleaning and aligning data")
        
        cleaned_indicator = {}
        cleaned_fuzzy = {}
        cleaned_price = {}
        
        # Get common timeframes
        all_timeframes = set(indicator_data.keys()) | set(fuzzy_data.keys()) | set(price_data.keys())
        
        for timeframe in all_timeframes:
            # Clean individual dataframes
            if timeframe in indicator_data:
                cleaned_indicator[timeframe] = self._clean_dataframe(
                    indicator_data[timeframe], f"indicator_{timeframe}"
                )
            
            if timeframe in fuzzy_data:
                cleaned_fuzzy[timeframe] = self._clean_dataframe(
                    fuzzy_data[timeframe], f"fuzzy_{timeframe}"
                )
            
            if timeframe in price_data:
                cleaned_price[timeframe] = self._clean_dataframe(
                    price_data[timeframe], f"price_{timeframe}"
                )
        
        # Align timestamps across timeframes
        aligned_indicator, aligned_fuzzy, aligned_price = self._align_timeframes(
            cleaned_indicator, cleaned_fuzzy, cleaned_price
        )
        
        return aligned_indicator, aligned_fuzzy, aligned_price
    
    def _clean_dataframe(self, df: pd.DataFrame, name: str) -> pd.DataFrame:
        """Clean a single dataframe."""
        if df is None or df.empty:
            return df
        
        cleaned_df = df.copy()
        
        # Remove duplicate timestamps
        if 'timestamp' in cleaned_df.columns:
            initial_len = len(cleaned_df)
            cleaned_df = cleaned_df.drop_duplicates(subset=['timestamp'], keep='last')
            if len(cleaned_df) < initial_len:
                self.logger.debug(f"Removed {initial_len - len(cleaned_df)} duplicate timestamps from {name}")
        
        # Handle missing values
        numeric_columns = cleaned_df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_columns:
            # Forward fill then backward fill
            cleaned_df[col] = cleaned_df[col].ffill().bfill()
            
            # If still NaN, fill with median
            if cleaned_df[col].isna().any():
                median_value = cleaned_df[col].median()
                cleaned_df[col] = cleaned_df[col].fillna(median_value)
        
        # Handle outliers (cap at 99th percentile)
        for col in numeric_columns:
            if col not in ['timestamp', 'volume']:  # Don't cap volume or timestamp
                upper_cap = cleaned_df[col].quantile(0.99)
                lower_cap = cleaned_df[col].quantile(0.01)
                
                cleaned_df[col] = cleaned_df[col].clip(lower=lower_cap, upper=upper_cap)
        
        # Ensure timestamp is datetime
        if 'timestamp' in cleaned_df.columns:
            cleaned_df['timestamp'] = pd.to_datetime(cleaned_df['timestamp'])
            cleaned_df = cleaned_df.sort_values('timestamp').reset_index(drop=True)
        
        return cleaned_df
    
    def _align_timeframes(
        self,
        indicator_data: Dict[str, pd.DataFrame],
        fuzzy_data: Dict[str, pd.DataFrame],
        price_data: Dict[str, pd.DataFrame]
    ) -> Tuple[Dict[str, pd.DataFrame], Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]]:
        """Align timestamps across all timeframes."""
        
        # Find common time range across all data
        min_timestamp = None
        max_timestamp = None
        
        for data_dict in [indicator_data, fuzzy_data, price_data]:
            for df in data_dict.values():
                if df is not None and 'timestamp' in df.columns and len(df) > 0:
                    df_min = df['timestamp'].min()
                    df_max = df['timestamp'].max()
                    
                    if min_timestamp is None or df_min > min_timestamp:
                        min_timestamp = df_min
                    if max_timestamp is None or df_max < max_timestamp:
                        max_timestamp = df_max
        
        if min_timestamp is None or max_timestamp is None:
            self.logger.warning("Could not determine common time range")
            return indicator_data, fuzzy_data, price_data
        
        self.logger.debug(f"Aligning data to time range: {min_timestamp} to {max_timestamp}")
        
        # Filter all dataframes to common time range
        aligned_indicator = self._filter_by_time_range(indicator_data, min_timestamp, max_timestamp)
        aligned_fuzzy = self._filter_by_time_range(fuzzy_data, min_timestamp, max_timestamp)
        aligned_price = self._filter_by_time_range(price_data, min_timestamp, max_timestamp)
        
        return aligned_indicator, aligned_fuzzy, aligned_price
    
    def _filter_by_time_range(
        self,
        data_dict: Dict[str, pd.DataFrame],
        min_timestamp: pd.Timestamp,
        max_timestamp: pd.Timestamp
    ) -> Dict[str, pd.DataFrame]:
        """Filter dataframes by time range."""
        filtered_dict = {}
        
        for timeframe, df in data_dict.items():
            if df is not None and 'timestamp' in df.columns:
                mask = (df['timestamp'] >= min_timestamp) & (df['timestamp'] <= max_timestamp)
                filtered_df = df[mask].reset_index(drop=True)
                
                if len(filtered_df) > 0:
                    filtered_dict[timeframe] = filtered_df
                else:
                    self.logger.warning(f"No data remaining for {timeframe} after time filtering")
            else:
                filtered_dict[timeframe] = df
        
        return filtered_dict
    
    def _generate_training_labels(self, price_data: Dict[str, pd.DataFrame]) -> pd.Series:
        """Generate training labels using price data."""
        
        # Use the finest timeframe for label generation
        timeframes = list(price_data.keys())
        primary_timeframe = min(timeframes, key=self._timeframe_to_minutes)
        
        if primary_timeframe not in price_data:
            raise ValueError(f"Primary timeframe {primary_timeframe} not found in price data")
        
        primary_df = price_data[primary_timeframe]
        
        # Use ZigZag labeler for generating trading signals
        labeler = ZigZagLabeler(
            min_change_pct=0.02,  # 2% minimum price change
            min_bars=5  # Minimum 5 bars for signal
        )
        
        labels = labeler.generate_labels(primary_df)
        
        self.logger.info(f"Generated {len(labels)} labels using {primary_timeframe} data")
        
        return labels
    
    def _create_temporal_alignment(
        self,
        indicator_data: Dict[str, pd.DataFrame],
        fuzzy_data: Dict[str, pd.DataFrame],
        price_data: Dict[str, pd.DataFrame],
        labels: pd.Series
    ) -> Dict[str, Any]:
        """Create temporally aligned dataset."""
        
        # Use primary timeframe timestamps as reference
        timeframes = list(price_data.keys())
        primary_timeframe = min(timeframes, key=self._timeframe_to_minutes)
        
        if primary_timeframe not in price_data:
            raise ValueError(f"Primary timeframe {primary_timeframe} not found")
        
        reference_timestamps = price_data[primary_timeframe]['timestamp']
        
        # Align labels with reference timestamps
        if hasattr(labels.index, 'tz_localize'):
            # Handle timezone-aware timestamps
            label_timestamps = pd.to_datetime(labels.index)
        else:
            label_timestamps = labels.index
        
        # Find common timestamps between reference and labels
        common_timestamps = reference_timestamps[
            reference_timestamps.isin(label_timestamps)
        ]
        
        # Create aligned dataset
        aligned_data = {
            'timestamps': common_timestamps,
            'labels': labels.reindex(common_timestamps).fillna(1),  # Default to HOLD
            'indicator_data': {},
            'fuzzy_data': {},
            'price_data': {}
        }
        
        # Align all dataframes to common timestamps
        for timeframe in timeframes:
            if timeframe in indicator_data:
                aligned_data['indicator_data'][timeframe] = self._align_to_timestamps(
                    indicator_data[timeframe], common_timestamps
                )
            
            if timeframe in fuzzy_data:
                aligned_data['fuzzy_data'][timeframe] = self._align_to_timestamps(
                    fuzzy_data[timeframe], common_timestamps
                )
            
            if timeframe in price_data:
                aligned_data['price_data'][timeframe] = self._align_to_timestamps(
                    price_data[timeframe], common_timestamps
                )
        
        self.logger.info(f"Created aligned dataset with {len(common_timestamps)} timestamps")
        
        return aligned_data
    
    def _align_to_timestamps(
        self, 
        df: pd.DataFrame, 
        target_timestamps: pd.DatetimeIndex
    ) -> pd.DataFrame:
        """Align dataframe to target timestamps."""
        if df is None or 'timestamp' not in df.columns:
            return df
        
        # Set timestamp as index for alignment
        df_indexed = df.set_index('timestamp')
        
        # Reindex to target timestamps with forward fill
        aligned_df = df_indexed.reindex(target_timestamps, method='ffill')
        
        # Reset index to restore timestamp column
        aligned_df = aligned_df.reset_index()
        aligned_df = aligned_df.rename(columns={'index': 'timestamp'})
        
        return aligned_df
    
    def _create_training_sequences(self, aligned_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create training sequences from aligned data."""
        
        timestamps = aligned_data['timestamps']
        labels = aligned_data['labels']
        
        sequence_length = self.config.sequence_length
        prediction_horizon = self.config.prediction_horizon
        overlap_ratio = self.config.overlap_ratio
        
        # Calculate step size based on overlap
        step_size = max(1, int(sequence_length * (1 - overlap_ratio)))
        
        sequences = []
        
        # Create sequences with sliding window
        for start_idx in range(0, len(timestamps) - sequence_length - prediction_horizon, step_size):
            end_idx = start_idx + sequence_length
            label_idx = end_idx + prediction_horizon - 1
            
            if label_idx >= len(labels):
                break
            
            # Extract sequence data
            sequence_timestamps = timestamps.iloc[start_idx:end_idx]
            sequence_features = self._extract_sequence_features(
                aligned_data, start_idx, end_idx
            )
            sequence_label = labels.iloc[label_idx]
            
            sequences.append({
                'features': sequence_features,
                'label': sequence_label,
                'timestamps': sequence_timestamps,
                'start_idx': start_idx,
                'end_idx': end_idx,
                'label_idx': label_idx
            })
        
        self.logger.info(f"Created {len(sequences)} training sequences")
        
        return sequences
    
    def _extract_sequence_features(
        self, 
        aligned_data: Dict[str, Any], 
        start_idx: int, 
        end_idx: int
    ) -> np.ndarray:
        """Extract features for a sequence."""
        
        all_features = []
        
        # Extract features from each timeframe
        for timeframe in aligned_data['indicator_data']:
            # Indicator features
            if timeframe in aligned_data['indicator_data']:
                indicator_df = aligned_data['indicator_data'][timeframe]
                indicator_features = self._extract_dataframe_features(
                    indicator_df, start_idx, end_idx, exclude_cols=['timestamp']
                )
                all_features.extend(indicator_features)
            
            # Fuzzy features  
            if timeframe in aligned_data['fuzzy_data']:
                fuzzy_df = aligned_data['fuzzy_data'][timeframe]
                fuzzy_features = self._extract_dataframe_features(
                    fuzzy_df, start_idx, end_idx, exclude_cols=['timestamp']
                )
                all_features.extend(fuzzy_features)
        
        return np.array(all_features)
    
    def _extract_dataframe_features(
        self, 
        df: pd.DataFrame, 
        start_idx: int, 
        end_idx: int,
        exclude_cols: List[str] = None
    ) -> List[float]:
        """Extract features from dataframe slice."""
        if df is None or len(df) == 0:
            return []
        
        exclude_cols = exclude_cols or []
        
        # Get numeric columns (excluding specified columns)
        numeric_cols = [col for col in df.select_dtypes(include=[np.number]).columns 
                       if col not in exclude_cols]
        
        if not numeric_cols:
            return []
        
        # Extract slice
        slice_df = df.iloc[start_idx:end_idx]
        
        # Take last value from each numeric column
        features = []
        for col in numeric_cols:
            if len(slice_df) > 0:
                last_value = slice_df[col].iloc[-1]
                features.append(float(last_value) if not pd.isna(last_value) else 0.0)
            else:
                features.append(0.0)
        
        return features
    
    def _combine_sequences(self, sequences: List[Dict[str, Any]], dataset_type: str) -> TrainingSequence:
        """Combine individual sequences into training dataset."""
        
        if not sequences:
            # Return empty sequence
            return TrainingSequence(
                features=torch.empty(0, 0),
                labels=torch.empty(0, dtype=torch.long),
                timestamps=pd.DatetimeIndex([]),
                metadata={'dataset_type': dataset_type, 'sequence_count': 0}
            )
        
        # Stack features and labels
        all_features = [seq['features'] for seq in sequences]
        all_labels = [seq['label'] for seq in sequences]
        all_timestamps = [seq['timestamps'].iloc[-1] for seq in sequences]  # Use last timestamp of each sequence
        
        # Convert to tensors
        features_tensor = torch.FloatTensor(np.stack(all_features))
        labels_tensor = torch.LongTensor(all_labels)
        timestamps_index = pd.DatetimeIndex(all_timestamps)
        
        metadata = {
            'dataset_type': dataset_type,
            'sequence_count': len(sequences),
            'sequence_length': self.config.sequence_length,
            'prediction_horizon': self.config.prediction_horizon,
            'feature_count': features_tensor.shape[1] if len(features_tensor.shape) > 1 else 0
        }
        
        return TrainingSequence(
            features=features_tensor,
            labels=labels_tensor,
            timestamps=timestamps_index,
            metadata=metadata
        )
    
    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """Convert timeframe string to minutes for sorting."""
        timeframe_map = {
            "1m": 1, "5m": 5, "15m": 15, "30m": 30,
            "1h": 60, "2h": 120, "4h": 240, "6h": 360, "8h": 480,
            "12h": 720, "1d": 1440, "3d": 4320, "1w": 10080, "1M": 43200
        }
        return timeframe_map.get(timeframe, 60)  # Default to 1 hour


def create_default_preparation_config() -> DataPreparationConfig:
    """Create default data preparation configuration."""
    return DataPreparationConfig(
        sequence_length=50,  # 50 time steps
        prediction_horizon=5,  # Predict 5 steps ahead
        overlap_ratio=0.3,  # 30% overlap between sequences
        min_data_quality=0.8,  # 80% minimum quality
        timeframe_weights={
            "1h": 1.0,
            "4h": 0.8,
            "1d": 0.6
        }
    )