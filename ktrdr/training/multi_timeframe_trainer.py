"""Multi-timeframe neural network training pipeline.

This module provides a comprehensive training pipeline that combines multi-timeframe
indicators, fuzzy logic, and neural networks for trading strategy development.
"""

import torch
import torch.nn as nn
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from pathlib import Path
import time
import json
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix

from ktrdr import get_logger
from ktrdr.indicators.multi_timeframe_indicator_engine import MultiTimeframeIndicatorEngine
from ktrdr.fuzzy.multi_timeframe_engine import MultiTimeframeFuzzyEngine
from ktrdr.neural.models.multi_timeframe_mlp import MultiTimeframeMLP
from ktrdr.training.multi_timeframe_feature_engineering import MultiTimeframeFeatureEngineer
from ktrdr.training.model_trainer import ModelTrainer
from ktrdr.training.zigzag_labeler import ZigZagLabeler
from ktrdr.data.data_manager import MultiTimeframeDataManager

logger = get_logger(__name__)


@dataclass
class TrainingDataSpec:
    """Specification for training data preparation."""
    symbol: str
    start_date: str
    end_date: str
    timeframes: List[str]
    lookback_periods: Dict[str, int]  # Minimum data required per timeframe
    

@dataclass
class MultiTimeframeTrainingConfig:
    """Configuration for multi-timeframe training."""
    data_spec: TrainingDataSpec
    indicator_config: Dict[str, Any]
    fuzzy_config: Dict[str, Any]
    neural_config: Dict[str, Any]
    feature_config: Dict[str, Any]
    training_config: Dict[str, Any]
    validation_split: float = 0.2
    test_split: float = 0.1
    random_seed: int = 42


@dataclass
class TrainingResult:
    """Result of multi-timeframe training pipeline."""
    model: MultiTimeframeMLP
    training_history: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    feature_importance: Optional[Dict[str, float]]
    timeframe_contributions: Dict[str, float]
    data_stats: Dict[str, Any]
    model_path: Optional[Path] = None


class MultiTimeframeTrainer:
    """Complete training pipeline for multi-timeframe neural networks."""
    
    def __init__(self, config: MultiTimeframeTrainingConfig):
        """
        Initialize multi-timeframe trainer.
        
        Args:
            config: Training configuration
        """
        self.config = config
        self.logger = get_logger(__name__)
        
        # Initialize components
        self.data_manager = None
        self.indicator_engine = None
        self.fuzzy_engine = None
        self.feature_engineer = None
        self.model = None
        self.labeler = None
        
        # Training data storage
        self.raw_data: Optional[Dict[str, pd.DataFrame]] = None
        self.indicator_data: Optional[Dict[str, pd.DataFrame]] = None
        self.fuzzy_data: Optional[Dict[str, pd.DataFrame]] = None
        self.labels: Optional[pd.Series] = None
        
        self.logger.info("Initialized MultiTimeframeTrainer")
    
    def prepare_training_pipeline(self) -> None:
        """Prepare all components of the training pipeline."""
        self.logger.info("Preparing multi-timeframe training pipeline")
        
        # Initialize data manager
        self.data_manager = MultiTimeframeDataManager(
            timeframes=self.config.data_spec.timeframes
        )
        
        # Initialize indicator engine
        self.indicator_engine = MultiTimeframeIndicatorEngine.from_config(
            self.config.indicator_config
        )
        
        # Initialize fuzzy engine
        self.fuzzy_engine = MultiTimeframeFuzzyEngine(self.config.fuzzy_config)
        
        # Initialize feature engineer
        self.feature_engineer = MultiTimeframeFeatureEngineer(self.config.feature_config)
        
        # Initialize labeler for generating trading signals
        labeler_config = self.config.training_config.get("labeling", {})
        self.labeler = ZigZagLabeler(
            min_change_percent=labeler_config.get("min_change_percent", 0.02),
            min_bars=labeler_config.get("min_bars", 5)
        )
        
        self.logger.info("Training pipeline components initialized")
    
    def load_and_prepare_data(self) -> Dict[str, Any]:
        """
        Load and prepare all training data.
        
        Returns:
            Dictionary with data preparation statistics
        """
        self.logger.info(f"Loading data for {self.config.data_spec.symbol}")
        
        data_spec = self.config.data_spec
        
        # Load raw OHLCV data for all timeframes
        self.raw_data = {}
        for timeframe in data_spec.timeframes:
            try:
                # This would integrate with your data loading system
                # For now, using placeholder - replace with actual data loading
                df = self._load_timeframe_data(
                    symbol=data_spec.symbol,
                    timeframe=timeframe,
                    start_date=data_spec.start_date,
                    end_date=data_spec.end_date,
                    lookback=data_spec.lookback_periods.get(timeframe, 100)
                )
                
                if df is not None and len(df) > 0:
                    self.raw_data[timeframe] = df
                    self.logger.info(f"Loaded {len(df)} rows for {timeframe}")
                else:
                    self.logger.warning(f"No data loaded for {timeframe}")
                    
            except Exception as e:
                self.logger.error(f"Failed to load data for {timeframe}: {e}")
                raise
        
        if not self.raw_data:
            raise ValueError("No data loaded for any timeframe")
        
        # Synchronize data across timeframes
        self.raw_data = self.data_manager.synchronize_timeframes(self.raw_data)
        
        # Compute indicators
        self.logger.info("Computing multi-timeframe indicators")
        self.indicator_data = self.indicator_engine.apply_multi_timeframe(self.raw_data)
        
        # Compute fuzzy memberships
        self.logger.info("Computing fuzzy memberships")
        self.fuzzy_data = self.fuzzy_engine.compute_multi_timeframe_memberships(
            self.indicator_data, self.raw_data
        )
        
        # Generate labels using primary timeframe (typically the finest)
        primary_timeframe = data_spec.timeframes[0]  # Assume first is primary
        primary_data = self.raw_data[primary_timeframe]
        
        self.logger.info(f"Generating labels using {primary_timeframe} data")
        self.labels = self.labeler.generate_labels(primary_data)
        
        # Calculate data statistics
        data_stats = self._calculate_data_stats()
        
        self.logger.info("Data preparation completed successfully")
        return data_stats
    
    def _load_timeframe_data(
        self, 
        symbol: str, 
        timeframe: str, 
        start_date: str, 
        end_date: str,
        lookback: int
    ) -> Optional[pd.DataFrame]:
        """
        Load data for a specific timeframe.
        
        This is a placeholder method that should be replaced with actual
        data loading from your data source (IB, files, database, etc.)
        """
        # Placeholder implementation - replace with actual data loading
        self.logger.debug(f"Loading {symbol} {timeframe} data from {start_date} to {end_date}")
        
        # For testing, create synthetic data
        try:
            import pandas as pd
            import numpy as np
            from datetime import datetime, timedelta
            
            # Parse dates
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            
            # Create date range based on timeframe
            if timeframe == "1h":
                freq = "1H"
            elif timeframe == "4h":
                freq = "4H"
            elif timeframe == "1d":
                freq = "1D"
            else:
                freq = "1H"  # Default
            
            dates = pd.date_range(start=start, end=end, freq=freq)
            
            # Generate synthetic OHLCV data
            np.random.seed(42)
            n = len(dates)
            
            # Simple random walk for prices
            returns = np.random.normal(0, 0.02, n)
            prices = 100 * np.exp(np.cumsum(returns))
            
            df = pd.DataFrame({
                'timestamp': dates,
                'open': prices * np.random.uniform(0.995, 1.005, n),
                'high': prices * np.random.uniform(1.0, 1.02, n),
                'low': prices * np.random.uniform(0.98, 1.0, n),
                'close': prices,
                'volume': np.random.randint(1000, 10000, n)
            })
            
            # Ensure OHLC constraints
            df['high'] = np.maximum(df['high'], np.maximum(df['open'], df['close']))
            df['low'] = np.minimum(df['low'], np.minimum(df['open'], df['close']))
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error creating synthetic data: {e}")
            return None
    
    def prepare_training_features(self) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Prepare features and labels for neural network training.
        
        Returns:
            Tuple of (features_tensor, labels_tensor)
        """
        self.logger.info("Preparing training features")
        
        if self.fuzzy_data is None or self.labels is None:
            raise ValueError("Data must be loaded and prepared before feature preparation")
        
        # Get the primary timeframe for alignment
        primary_timeframe = self.config.data_spec.timeframes[0]
        primary_fuzzy = self.fuzzy_data[primary_timeframe]
        
        # Align labels with fuzzy data
        aligned_labels = self._align_labels_with_data(primary_fuzzy, self.labels)
        
        # Prepare batch features for all samples
        batch_size = len(aligned_labels)
        batch_fuzzy_data = []
        
        for i in range(batch_size):
            # Extract fuzzy data slice for each sample
            sample_fuzzy = {}
            for timeframe, fuzzy_df in self.fuzzy_data.items():
                if i < len(fuzzy_df):
                    # Take data up to current point (avoid lookahead bias)
                    sample_fuzzy[timeframe] = fuzzy_df.iloc[:i+1]
                
            batch_fuzzy_data.append(sample_fuzzy)
        
        # Use feature engineer to create batch features
        feature_result = self.feature_engineer.prepare_batch_features(
            batch_fuzzy_data=batch_fuzzy_data,
            batch_indicators=[self.indicator_data] * batch_size  # Reuse indicator data
        )
        
        # Convert labels to tensor
        labels_tensor = torch.LongTensor(aligned_labels.values)
        
        self.logger.info(f"Prepared features: {feature_result.features_tensor.shape}, labels: {labels_tensor.shape}")
        
        return feature_result.features_tensor, labels_tensor
    
    def _align_labels_with_data(
        self, 
        reference_data: pd.DataFrame, 
        labels: pd.Series
    ) -> pd.Series:
        """Align labels with reference data timestamps."""
        
        if 'timestamp' in reference_data.columns:
            # Align by timestamp
            reference_timestamps = pd.to_datetime(reference_data['timestamp'])
            label_timestamps = pd.to_datetime(labels.index)
            
            # Find overlapping timestamps
            common_timestamps = reference_timestamps[
                reference_timestamps.isin(label_timestamps)
            ]
            
            # Reindex labels to match
            aligned_labels = labels.reindex(common_timestamps)
            aligned_labels = aligned_labels.fillna(1)  # Default to HOLD
            
        else:
            # Align by position (fallback)
            min_length = min(len(reference_data), len(labels))
            aligned_labels = labels.iloc[:min_length]
        
        return aligned_labels
    
    def train_model(self) -> TrainingResult:
        """
        Train the multi-timeframe neural network model.
        
        Returns:
            TrainingResult with comprehensive training information
        """
        self.logger.info("Starting multi-timeframe model training")
        
        if self.fuzzy_data is None:
            raise ValueError("Data must be prepared before training")
        
        # Prepare features and labels
        X, y = self.prepare_training_features()
        
        # Split data
        train_X, temp_X, train_y, temp_y = train_test_split(
            X, y, 
            test_size=self.config.validation_split + self.config.test_split,
            random_state=self.config.random_seed,
            stratify=y
        )
        
        val_size = self.config.validation_split / (self.config.validation_split + self.config.test_split)
        val_X, test_X, val_y, test_y = train_test_split(
            temp_X, temp_y,
            test_size=1-val_size,
            random_state=self.config.random_seed,
            stratify=temp_y
        )
        
        self.logger.info(f"Data split - Train: {len(train_X)}, Val: {len(val_X)}, Test: {len(test_X)}")
        
        # Initialize model
        self.model = MultiTimeframeMLP(self.config.neural_config)
        
        # Build model with correct input size
        input_size = X.shape[1]
        self.model.build_model(input_size)
        
        # Train model
        training_result = self.model.train(
            X=train_X,
            y=train_y,
            validation_data=(val_X, val_y)
        )
        
        # Evaluate on test set
        test_performance = self._evaluate_model(test_X, test_y)
        
        # Calculate comprehensive performance metrics
        performance_metrics = {
            "train_accuracy": training_result.model_performance.get("train_accuracy", 0.0),
            "val_accuracy": training_result.model_performance.get("val_accuracy", 0.0),
            "test_accuracy": test_performance["accuracy"],
            "test_classification_report": test_performance["classification_report"],
            "test_confusion_matrix": test_performance["confusion_matrix"]
        }
        
        # Calculate data statistics
        data_stats = self._calculate_data_stats()
        
        result = TrainingResult(
            model=self.model,
            training_history=training_result.training_history,
            performance_metrics=performance_metrics,
            feature_importance=training_result.feature_importance,
            timeframe_contributions=training_result.timeframe_contributions,
            data_stats=data_stats
        )
        
        self.logger.info("Model training completed successfully")
        return result
    
    def _evaluate_model(self, X: torch.Tensor, y: torch.Tensor) -> Dict[str, Any]:
        """Evaluate model performance on test set."""
        self.model.model.eval()
        
        with torch.no_grad():
            outputs = self.model.model(X)
            _, predicted = torch.max(outputs, 1)
            
            accuracy = (predicted == y).float().mean().item()
            
            # Convert to numpy for sklearn metrics
            y_true = y.cpu().numpy()
            y_pred = predicted.cpu().numpy()
            
            # Generate classification report
            class_names = ["BUY", "HOLD", "SELL"]
            classification_rep = classification_report(
                y_true, y_pred, 
                target_names=class_names,
                output_dict=True
            )
            
            confusion_mat = confusion_matrix(y_true, y_pred).tolist()
            
        return {
            "accuracy": accuracy,
            "classification_report": classification_rep,
            "confusion_matrix": confusion_mat
        }
    
    def _calculate_data_stats(self) -> Dict[str, Any]:
        """Calculate comprehensive data statistics."""
        stats = {
            "timeframes": list(self.raw_data.keys()) if self.raw_data else [],
            "data_ranges": {},
            "feature_counts": {},
            "label_distribution": {}
        }
        
        if self.raw_data:
            for timeframe, df in self.raw_data.items():
                stats["data_ranges"][timeframe] = {
                    "start": str(df['timestamp'].min()) if 'timestamp' in df.columns else "N/A",
                    "end": str(df['timestamp'].max()) if 'timestamp' in df.columns else "N/A",
                    "count": len(df)
                }
        
        if self.fuzzy_data:
            for timeframe, df in self.fuzzy_data.items():
                fuzzy_cols = [col for col in df.columns if col not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                stats["feature_counts"][timeframe] = len(fuzzy_cols)
        
        if self.labels is not None:
            label_counts = self.labels.value_counts().to_dict()
            stats["label_distribution"] = {
                str(k): int(v) for k, v in label_counts.items()
            }
        
        return stats
    
    def save_model(self, model_path: Path) -> None:
        """Save trained model and associated metadata."""
        if self.model is None:
            raise ValueError("No model to save")
        
        model_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save model state
        torch.save({
            'model_state_dict': self.model.model.state_dict(),
            'model_config': self.model.config,
            'feature_scaler': getattr(self.model, 'feature_scaler', None),
            'feature_order': getattr(self.model, 'feature_order', []),
            'training_config': self.config
        }, model_path)
        
        self.logger.info(f"Model saved to {model_path}")
    
    def load_model(self, model_path: Path) -> MultiTimeframeMLP:
        """Load trained model from file."""
        checkpoint = torch.load(model_path, map_location='cpu')
        
        # Recreate model
        model_config = checkpoint['model_config']
        model = MultiTimeframeMLP(model_config)
        
        # Determine input size from state dict
        first_layer_key = next(k for k in checkpoint['model_state_dict'].keys() if 'weight' in k)
        input_size = checkpoint['model_state_dict'][first_layer_key].shape[1]
        
        # Build and load model
        model.build_model(input_size)
        model.model.load_state_dict(checkpoint['model_state_dict'])
        
        # Restore additional attributes
        model.feature_scaler = checkpoint.get('feature_scaler')
        model.feature_order = checkpoint.get('feature_order', [])
        model.is_trained = True
        
        self.logger.info(f"Model loaded from {model_path}")
        return model
    
    def create_training_report(self, result: TrainingResult) -> Dict[str, Any]:
        """Create comprehensive training report."""
        report = {
            "training_config": {
                "symbol": self.config.data_spec.symbol,
                "timeframes": self.config.data_spec.timeframes,
                "date_range": {
                    "start": self.config.data_spec.start_date,
                    "end": self.config.data_spec.end_date
                },
                "validation_split": self.config.validation_split,
                "test_split": self.config.test_split
            },
            "model_architecture": self.model.get_model_summary() if self.model else {},
            "performance": result.performance_metrics,
            "training_history": {
                "epochs": len(result.training_history.get("train_loss", [])),
                "final_train_loss": result.training_history.get("train_loss", [])[-1] if result.training_history.get("train_loss") else None,
                "best_val_accuracy": max(result.training_history.get("val_accuracy", [0])) if result.training_history.get("val_accuracy") else None
            },
            "feature_analysis": {
                "timeframe_contributions": result.timeframe_contributions,
                "feature_importance": result.feature_importance
            },
            "data_statistics": result.data_stats,
            "timestamp": pd.Timestamp.now(tz='UTC').isoformat()
        }
        
        return report


def create_training_pipeline(
    symbol: str,
    timeframes: List[str],
    start_date: str,
    end_date: str,
    indicator_config_path: Optional[Path] = None,
    output_dir: Optional[Path] = None
) -> MultiTimeframeTrainer:
    """
    Create a complete multi-timeframe training pipeline with sensible defaults.
    
    Args:
        symbol: Trading symbol
        timeframes: List of timeframes to include
        start_date: Training data start date
        end_date: Training data end date
        indicator_config_path: Optional path to indicator configuration
        output_dir: Optional output directory for models/reports
        
    Returns:
        Configured MultiTimeframeTrainer
    """
    
    # Default configurations
    data_spec = TrainingDataSpec(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        timeframes=timeframes,
        lookback_periods={tf: 200 for tf in timeframes}
    )
    
    # Default indicator configuration
    indicator_config = {
        "timeframes": [
            {
                "timeframe": tf,
                "indicators": [
                    {"type": "RSI", "params": {"period": 14}},
                    {"type": "SimpleMovingAverage", "params": {"period": 20}},
                    {"type": "ExponentialMovingAverage", "params": {"period": 12}}
                ]
            }
            for tf in timeframes
        ]
    }
    
    # Default fuzzy configuration
    fuzzy_config = {
        "rules": {
            "buy_signal": {
                "conditions": [
                    {"variable": "rsi", "term": "low", "timeframes": timeframes},
                    {"variable": "price_trend", "term": "bullish", "timeframes": timeframes}
                ],
                "output": {"signal": "buy", "confidence": 0.8}
            },
            "sell_signal": {
                "conditions": [
                    {"variable": "rsi", "term": "high", "timeframes": timeframes},
                    {"variable": "price_trend", "term": "bearish", "timeframes": timeframes}
                ],
                "output": {"signal": "sell", "confidence": 0.8}
            }
        }
    }
    
    # Default neural network configuration
    neural_config = {
        "timeframe_configs": {
            tf: {
                "expected_features": ["rsi_membership", "trend_membership", "momentum_membership"],
                "weight": 1.0,
                "enabled": True
            }
            for tf in timeframes
        },
        "architecture": {
            "hidden_layers": [64, 32, 16],
            "dropout": 0.3,
            "activation": "relu",
            "batch_norm": True
        },
        "training": {
            "learning_rate": 0.001,
            "batch_size": 32,
            "epochs": 100,
            "early_stopping_patience": 15,
            "optimizer": "adam"
        }
    }
    
    # Default feature engineering configuration
    feature_config = {
        "timeframe_specs": {
            tf: {
                "fuzzy_features": ["rsi_membership", "trend_membership", "momentum_membership"],
                "weight": 1.0,
                "enabled": True
            }
            for tf in timeframes
        },
        "scaling": {
            "enabled": True,
            "type": "standard"
        }
    }
    
    # Default training configuration
    training_config = {
        "labeling": {
            "min_change_percent": 0.02,
            "min_bars": 5
        },
        "validation_split": 0.2,
        "test_split": 0.1,
        "random_seed": 42
    }
    
    config = MultiTimeframeTrainingConfig(
        data_spec=data_spec,
        indicator_config=indicator_config,
        fuzzy_config=fuzzy_config,
        neural_config=neural_config,
        feature_config=feature_config,
        training_config=training_config
    )
    
    return MultiTimeframeTrainer(config)