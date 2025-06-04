"""Strategy training orchestrator that coordinates the complete training pipeline."""

import yaml
import pandas as pd
import torch
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import numpy as np

from .zigzag_labeler import ZigZagLabeler
from .feature_engineering import FeatureEngineer
from .model_trainer import ModelTrainer
from .model_storage import ModelStorage
from ..neural.models.mlp import MLPTradingModel
from ..data.data_manager import DataManager
from ..indicators.indicator_engine import IndicatorEngine
from ..fuzzy.engine import FuzzyEngine


class StrategyTrainer:
    """Coordinate the complete training pipeline from data to trained model."""
    
    def __init__(self, models_dir: str = "models"):
        """Initialize the strategy trainer.
        
        Args:
            models_dir: Directory to store trained models
        """
        self.model_storage = ModelStorage(models_dir)
        self.data_manager = DataManager()
        self.indicator_engine = IndicatorEngine()
        self.fuzzy_engine = FuzzyEngine()
        
    def train_strategy(self,
                      strategy_config_path: str,
                      symbol: str,
                      timeframe: str,
                      start_date: str,
                      end_date: str,
                      validation_split: float = 0.2) -> Dict[str, Any]:
        """Train a complete neuro-fuzzy strategy.
        
        Args:
            strategy_config_path: Path to strategy YAML configuration
            symbol: Trading symbol to train on
            timeframe: Timeframe for training data
            start_date: Start date for training data
            end_date: End date for training data
            validation_split: Fraction of data to use for validation
            
        Returns:
            Dictionary with training results and model information
        """
        print(f"Starting training for {symbol} {timeframe} strategy...")
        
        # Load strategy configuration
        config = self._load_strategy_config(strategy_config_path)
        strategy_name = config['name']
        
        print(f"Strategy: {strategy_name}")
        print(f"Data range: {start_date} to {end_date}")
        
        # Step 1: Load and prepare data
        print("\n1. Loading market data...")
        price_data = self._load_price_data(symbol, timeframe, start_date, end_date)
        print(f"Loaded {len(price_data)} bars of data")
        
        # Step 2: Calculate indicators
        print("\n2. Calculating technical indicators...")
        indicators = self._calculate_indicators(price_data, config['indicators'])
        print(f"Calculated {len(config['indicators'])} indicators")
        
        # Step 3: Generate fuzzy memberships
        print("\n3. Generating fuzzy memberships...")
        fuzzy_data = self._generate_fuzzy_memberships(indicators, config['fuzzy_sets'])
        print(f"Generated fuzzy sets for {len(config['fuzzy_sets'])} indicators")
        
        # Step 4: Engineer features
        print("\n4. Engineering features...")
        features, feature_names = self._engineer_features(
            fuzzy_data, indicators, price_data, config.get('model', {}).get('features', {})
        )
        print(f"Created {features.shape[1]} features from {len(feature_names)} components")
        
        # Step 5: Generate training labels
        print("\n5. Generating training labels...")
        labels = self._generate_labels(price_data, config['training']['labels'])
        label_dist = self._get_label_distribution(labels)
        print(f"Label distribution: BUY={label_dist['buy_pct']:.1f}%, "
              f"HOLD={label_dist['hold_pct']:.1f}%, SELL={label_dist['sell_pct']:.1f}%")
        
        # Step 6: Prepare training datasets
        print("\n6. Preparing training datasets...")
        train_data, val_data, test_data = self._split_data(
            features, labels, validation_split, config['training']['data_split']
        )
        
        # Step 7: Create and train neural network
        print("\n7. Training neural network...")
        model = self._create_model(config['model'], features.shape[1])
        training_results = self._train_model(model, train_data, val_data, config['model']['training'])
        
        # Step 8: Evaluate model
        print("\n8. Evaluating model...")
        test_metrics = self._evaluate_model(model, test_data)
        training_results.update(test_metrics)
        
        # Step 9: Calculate feature importance
        print("\n9. Calculating feature importance...")
        feature_importance = self._calculate_feature_importance(
            model, val_data[0], val_data[1], feature_names
        )
        
        # Step 10: Save trained model
        print("\n10. Saving trained model...")
        model_path = self.model_storage.save_model(
            model=model,
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            config=config,
            training_metrics=training_results,
            feature_names=feature_names,
            feature_importance=feature_importance
        )
        
        print(f"\nTraining completed! Model saved to: {model_path}")
        
        return {
            "model_path": model_path,
            "training_metrics": training_results,
            "feature_importance": feature_importance,
            "label_distribution": label_dist,
            "data_summary": {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_date": start_date,
                "end_date": end_date,
                "total_samples": len(features),
                "feature_count": features.shape[1]
            }
        }
    
    def _load_strategy_config(self, config_path: str) -> Dict[str, Any]:
        """Load strategy configuration from YAML file.
        
        Args:
            config_path: Path to YAML configuration file
            
        Returns:
            Strategy configuration dictionary
        """
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Validate required sections
        required_sections = ['name', 'indicators', 'fuzzy_sets', 'model', 'training']
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required configuration section: {section}")
        
        return config
    
    def _load_price_data(self, symbol: str, timeframe: str, 
                        start_date: str, end_date: str) -> pd.DataFrame:
        """Load price data for training.
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start_date: Start date
            end_date: End date
            
        Returns:
            OHLCV DataFrame
        """
        # For now, use the existing data manager
        # In production, might want to implement date filtering
        data = self.data_manager.load_data(symbol, timeframe, mode="full")
        
        # Filter by date range if possible
        if hasattr(data.index, 'to_pydatetime'):
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            data = data.loc[start:end]
        
        return data
    
    def _calculate_indicators(self, price_data: pd.DataFrame, 
                            indicator_configs: List[Dict[str, Any]]) -> pd.DataFrame:
        """Calculate technical indicators.
        
        Args:
            price_data: OHLCV data
            indicator_configs: List of indicator configurations
            
        Returns:
            DataFrame with calculated indicators
        """
        return self.indicator_engine.calculate_multiple(price_data, indicator_configs)
    
    def _generate_fuzzy_memberships(self, indicators: pd.DataFrame,
                                   fuzzy_configs: Dict[str, Any]) -> pd.DataFrame:
        """Generate fuzzy membership values.
        
        Args:
            indicators: Technical indicators DataFrame
            fuzzy_configs: Fuzzy set configurations
            
        Returns:
            DataFrame with fuzzy membership values
        """
        return self.fuzzy_engine.evaluate_batch(indicators, fuzzy_configs)
    
    def _engineer_features(self, fuzzy_data: pd.DataFrame,
                          indicators: pd.DataFrame,
                          price_data: pd.DataFrame,
                          feature_config: Dict[str, Any]) -> Tuple[torch.Tensor, List[str]]:
        """Engineer features for neural network training.
        
        Args:
            fuzzy_data: Fuzzy membership values
            indicators: Technical indicators
            price_data: OHLCV data
            feature_config: Feature engineering configuration
            
        Returns:
            Tuple of (features tensor, feature names)
        """
        engineer = FeatureEngineer(feature_config)
        return engineer.prepare_features(fuzzy_data, indicators, price_data)
    
    def _generate_labels(self, price_data: pd.DataFrame,
                        label_config: Dict[str, Any]) -> torch.Tensor:
        """Generate training labels using ZigZag method.
        
        Args:
            price_data: OHLCV data
            label_config: Label generation configuration
            
        Returns:
            Tensor of labels
        """
        labeler = ZigZagLabeler(
            threshold=label_config['zigzag_threshold'],
            lookahead=label_config['label_lookahead']
        )
        
        labels = labeler.generate_labels(price_data)
        return torch.LongTensor(labels.values)
    
    def _get_label_distribution(self, labels: torch.Tensor) -> Dict[str, Any]:
        """Get label distribution statistics.
        
        Args:
            labels: Label tensor
            
        Returns:
            Distribution statistics
        """
        unique, counts = torch.unique(labels, return_counts=True)
        total = len(labels)
        
        dist = {f'class_{int(u)}': int(c) for u, c in zip(unique, counts)}
        
        return {
            'buy_count': dist.get('class_0', 0),
            'hold_count': dist.get('class_1', 0), 
            'sell_count': dist.get('class_2', 0),
            'buy_pct': dist.get('class_0', 0) / total * 100,
            'hold_pct': dist.get('class_1', 0) / total * 100,
            'sell_pct': dist.get('class_2', 0) / total * 100,
            'total': total
        }
    
    def _split_data(self, features: torch.Tensor, labels: torch.Tensor,
                   validation_split: float, split_config: Dict[str, float]) -> Tuple:
        """Split data into train/validation/test sets.
        
        Args:
            features: Feature tensor
            labels: Label tensor
            validation_split: Validation split ratio
            split_config: Split configuration from strategy
            
        Returns:
            Tuple of (train_data, val_data, test_data)
        """
        total_size = len(features)
        
        # Use strategy config if available, otherwise use validation_split
        if split_config:
            train_size = int(total_size * split_config['train'])
            val_size = int(total_size * split_config['validation'])
            test_size = total_size - train_size - val_size
        else:
            train_size = int(total_size * (1 - validation_split))
            val_size = total_size - train_size
            test_size = 0
        
        # Split data chronologically (important for time series)
        train_data = (features[:train_size], labels[:train_size])
        val_data = (features[train_size:train_size+val_size], 
                   labels[train_size:train_size+val_size])
        
        if test_size > 0:
            test_data = (features[train_size+val_size:], 
                        labels[train_size+val_size:])
        else:
            test_data = None
        
        return train_data, val_data, test_data
    
    def _create_model(self, model_config: Dict[str, Any], input_size: int) -> torch.nn.Module:
        """Create neural network model.
        
        Args:
            model_config: Model configuration
            input_size: Number of input features
            
        Returns:
            Neural network model
        """
        model_type = model_config.get('type', 'mlp').lower()
        
        if model_type == 'mlp':
            model = MLPTradingModel(model_config)
            model.model = model.build_model(input_size)
            return model.model
        else:
            raise ValueError(f"Unknown model type: {model_type}")
    
    def _train_model(self, model: torch.nn.Module, train_data: Tuple,
                    val_data: Tuple, training_config: Dict[str, Any]) -> Dict[str, Any]:
        """Train the neural network model.
        
        Args:
            model: Neural network model
            train_data: Training data tuple
            val_data: Validation data tuple
            training_config: Training configuration
            
        Returns:
            Training results
        """
        trainer = ModelTrainer(training_config)
        return trainer.train(model, train_data[0], train_data[1], val_data[0], val_data[1])
    
    def _evaluate_model(self, model: torch.nn.Module, test_data: Optional[Tuple]) -> Dict[str, Any]:
        """Evaluate model on test set.
        
        Args:
            model: Trained model
            test_data: Test data tuple
            
        Returns:
            Test metrics
        """
        if test_data is None:
            return {"test_accuracy": None, "test_loss": None}
        
        model.eval()
        with torch.no_grad():
            X_test, y_test = test_data
            outputs = model(X_test)
            
            # Calculate accuracy
            _, predicted = torch.max(outputs, 1)
            accuracy = (predicted == y_test).float().mean().item()
            
            # Calculate loss
            criterion = torch.nn.CrossEntropyLoss()
            loss = criterion(outputs, y_test).item()
        
        return {
            "test_accuracy": accuracy,
            "test_loss": loss
        }
    
    def _calculate_feature_importance(self, model: torch.nn.Module,
                                    X_val: torch.Tensor, y_val: torch.Tensor,
                                    feature_names: List[str]) -> Dict[str, float]:
        """Calculate feature importance scores.
        
        Args:
            model: Trained model
            X_val: Validation features
            y_val: Validation labels
            feature_names: List of feature names
            
        Returns:
            Feature importance dictionary
        """
        engineer = FeatureEngineer({})
        engineer.feature_names = feature_names
        return engineer.calculate_feature_importance(model, X_val, y_val)