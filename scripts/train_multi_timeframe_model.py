#!/usr/bin/env python3
"""
Training script for multi-timeframe neuro-fuzzy models.

This script demonstrates training multi-timeframe models with the new
MultiTimeframeLabelGenerator and compares performance against single-timeframe baselines.
"""

import sys
import os
import numpy as np
import pandas as pd
import torch
from pathlib import Path
from typing import Dict, Any, List, Optional
import argparse
import json
from datetime import datetime
import warnings

# Add the project root to the path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from ktrdr import get_logger
from ktrdr.data import DataManager
from ktrdr.indicators import IndicatorEngine
from ktrdr.fuzzy import FuzzyEngine
from ktrdr.neural.models.multi_timeframe_mlp import MultiTimeframeMLP
from ktrdr.neural.training.multi_timeframe_trainer import (
    MultiTimeframeTrainer,
    MultiTimeframeTrainingConfig,
    CrossTimeframeValidationConfig,
    EarlyStoppingConfig
)
from ktrdr.neural.feature_engineering import MultiTimeframeFeatureEngineer
from ktrdr.training.multi_timeframe_label_generator import (
    MultiTimeframeLabelGenerator,
    MultiTimeframeLabelConfig,
    TimeframeLabelConfig,
    create_multi_timeframe_label_generator
)

# Set up logging
logger = get_logger(__name__)

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)


class MultiTimeframeModelTrainer:
    """Training pipeline for multi-timeframe models with baseline comparison."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the training pipeline.
        
        Args:
            config: Training configuration containing data, model, and training parameters
        """
        self.config = config
        self.data_manager = DataManager()
        self.indicator_engine = IndicatorEngine()
        # Skip fuzzy engine for now - we'll compute fuzzy features manually
        
        # Initialize results storage
        self.results = {
            "multi_timeframe": {},
            "single_timeframe_baselines": {},
            "comparison_metrics": {},
            "training_metadata": {}
        }
        
        logger.info("Initialized MultiTimeframeModelTrainer")
    
    def prepare_sample_data(self) -> Dict[str, pd.DataFrame]:
        """
        Prepare sample multi-timeframe data for training.
        
        Returns:
            Dictionary mapping timeframes to price data
        """
        logger.info("Preparing sample multi-timeframe data")
        
        # Generate realistic sample data
        np.random.seed(42)
        
        # Create base time series with trends
        base_dates = pd.date_range('2024-01-01', periods=1000, freq='1h')
        base_price = 100.0
        
        # Generate price series with regime changes
        prices = []
        current_price = base_price
        regime_length = 100  # Change regime every 100 hours
        
        for i in range(1000):
            # Change volatility regime periodically
            if i % regime_length == 0:
                volatility = np.random.choice([0.5, 1.0, 2.0])  # Low, medium, high vol
                trend = np.random.choice([-0.01, 0.0, 0.01])   # Down, sideways, up trend
            else:
                volatility = volatility  # Keep current regime
                trend = trend
            
            # Generate price change
            change = np.random.normal(trend, volatility/100)
            current_price *= (1 + change)
            prices.append(current_price)
        
        # Create multi-timeframe data
        data = {}
        
        # 1h data (base resolution)
        data["1h"] = pd.DataFrame({
            'open': prices,
            'high': [p * (1 + abs(np.random.normal(0, 0.1)/100)) for p in prices],
            'low': [p * (1 - abs(np.random.normal(0, 0.1)/100)) for p in prices],
            'close': prices,
            'volume': np.random.randint(1000, 50000, 1000)
        }, index=base_dates)
        
        # 4h data (aggregated)
        h4_data = []
        h4_dates = base_dates[::4]  # Every 4 hours
        for i in range(0, len(prices), 4):
            chunk = prices[i:i+4]
            if len(chunk) > 0:
                h4_data.append({
                    'open': chunk[0],
                    'high': max(chunk),
                    'low': min(chunk),
                    'close': chunk[-1],
                    'volume': sum([1000] * len(chunk))
                })
        
        data["4h"] = pd.DataFrame(h4_data, index=h4_dates[:len(h4_data)])
        
        # 1d data (aggregated)
        d1_data = []
        d1_dates = base_dates[::24]  # Every 24 hours
        for i in range(0, len(prices), 24):
            chunk = prices[i:i+24]
            if len(chunk) > 0:
                d1_data.append({
                    'open': chunk[0],
                    'high': max(chunk),
                    'low': min(chunk),
                    'close': chunk[-1],
                    'volume': sum([1000] * len(chunk))
                })
        
        data["1d"] = pd.DataFrame(d1_data, index=d1_dates[:len(d1_data)])
        
        logger.info(f"Generated sample data: 1h({len(data['1h'])}), 4h({len(data['4h'])}), 1d({len(data['1d'])})")
        
        return data
    
    def compute_multi_timeframe_features(
        self, 
        price_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, Dict[str, np.ndarray]]:
        """
        Compute indicators and fuzzy features for each timeframe.
        
        Args:
            price_data: Multi-timeframe price data
            
        Returns:
            Dictionary mapping timeframes to feature dictionaries
        """
        logger.info("Computing multi-timeframe features")
        
        features_by_timeframe = {}
        
        for timeframe, data in price_data.items():
            try:
                logger.debug(f"Computing features for {timeframe}")
                
                # Compute basic indicators manually (simplified approach)
                close = data['close']
                high = data['high']
                low = data['low']
                
                # Simple RSI calculation
                delta = close.diff()
                gain = delta.where(delta > 0, 0).rolling(window=14).mean()
                loss = (-delta).where(delta < 0, 0).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                
                # Simple MACD calculation
                ema12 = close.ewm(span=12).mean()
                ema26 = close.ewm(span=26).mean()
                macd_line = ema12 - ema26
                macd_signal = macd_line.ewm(span=9).mean()
                macd_histogram = macd_line - macd_signal
                
                # Simple moving averages
                sma = close.rolling(window=20).mean()
                ema = close.ewm(span=12).mean()
                
                # Simple Bollinger Bands
                bb_middle = close.rolling(window=20).mean()
                bb_std = close.rolling(window=20).std()
                bb_upper = bb_middle + (bb_std * 2)
                bb_lower = bb_middle - (bb_std * 2)
                
                # Create indicator dataframe
                indicators_df = pd.DataFrame({
                    'rsi': rsi,
                    'macd_line': macd_line,
                    'macd_signal': macd_signal,
                    'macd_histogram': macd_histogram,
                    'sma': sma,
                    'ema': ema,
                    'bb_upper': bb_upper,
                    'bb_middle': bb_middle,
                    'bb_lower': bb_lower,
                    'close': data['close']
                }, index=data.index)
                
                # Remove NaN values
                indicators_df = indicators_df.dropna()
                
                if len(indicators_df) == 0:
                    logger.warning(f"No valid indicators for {timeframe}")
                    continue
                
                # Compute fuzzy features
                fuzzy_features = {}
                
                # RSI fuzzy sets
                rsi_values = indicators_df['rsi'].values
                fuzzy_features['rsi_oversold'] = self._triangular_membership(rsi_values, 0, 30, 50)
                fuzzy_features['rsi_neutral'] = self._triangular_membership(rsi_values, 30, 50, 70)
                fuzzy_features['rsi_overbought'] = self._triangular_membership(rsi_values, 50, 70, 100)
                
                # MACD fuzzy sets
                macd_values = indicators_df['macd_histogram'].values
                macd_std = np.std(macd_values)
                fuzzy_features['macd_negative'] = self._triangular_membership(macd_values, -3*macd_std, -macd_std, 0)
                fuzzy_features['macd_neutral'] = self._triangular_membership(macd_values, -macd_std, 0, macd_std)
                fuzzy_features['macd_positive'] = self._triangular_membership(macd_values, 0, macd_std, 3*macd_std)
                
                # Price position relative to Bollinger Bands
                close_values = indicators_df['close'].values
                bb_upper = indicators_df['bb_upper'].values
                bb_lower = indicators_df['bb_lower'].values
                bb_position = (close_values - bb_lower) / (bb_upper - bb_lower)
                bb_position = np.clip(bb_position, 0, 1)  # Ensure [0,1] range
                
                fuzzy_features['bb_low'] = self._triangular_membership(bb_position, 0, 0, 0.5)
                fuzzy_features['bb_middle'] = self._triangular_membership(bb_position, 0, 0.5, 1)
                fuzzy_features['bb_high'] = self._triangular_membership(bb_position, 0.5, 1, 1)
                
                # Convert to arrays and ensure same length
                min_length = min(len(arr) for arr in fuzzy_features.values())
                for key in fuzzy_features:
                    fuzzy_features[key] = fuzzy_features[key][:min_length]
                
                # Stack fuzzy features
                fuzzy_array = np.column_stack(list(fuzzy_features.values()))
                
                # Create raw indicator features (normalized)
                raw_indicators = indicators_df[['rsi', 'macd_histogram', 'bb_upper', 'bb_lower', 'close']].values[:min_length]
                
                # Normalize raw indicators
                from sklearn.preprocessing import StandardScaler
                scaler = StandardScaler()
                raw_indicators_normalized = scaler.fit_transform(raw_indicators)
                
                features_by_timeframe[timeframe] = {
                    'fuzzy_features': fuzzy_array,
                    'indicator_features': raw_indicators_normalized
                }
                
                logger.debug(f"Generated {fuzzy_array.shape[1]} fuzzy + {raw_indicators_normalized.shape[1]} indicator features for {timeframe}")
                
            except Exception as e:
                logger.error(f"Failed to compute features for {timeframe}: {e}")
                continue
        
        return features_by_timeframe
    
    def _triangular_membership(self, x: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
        """Compute triangular membership function."""
        return np.maximum(0, np.minimum((x - a) / (b - a), (c - x) / (c - b)))
    
    def generate_multi_timeframe_labels(
        self, 
        price_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """
        Generate multi-timeframe labels using the new label generator.
        
        Args:
            price_data: Multi-timeframe price data
            
        Returns:
            Dictionary containing labels and metadata
        """
        logger.info("Generating multi-timeframe labels")
        
        # Create label generator configuration
        label_config = MultiTimeframeLabelConfig(
            timeframe_configs={
                "1h": TimeframeLabelConfig(threshold=0.02, lookahead=8, weight=0.5),
                "4h": TimeframeLabelConfig(threshold=0.03, lookahead=6, weight=0.3),
                "1d": TimeframeLabelConfig(threshold=0.05, lookahead=3, weight=0.2)
            },
            consensus_method="weighted_majority",
            consistency_threshold=0.6,
            min_confidence_score=0.5,
            label_smoothing=True
        )
        
        # Generate labels
        label_generator = MultiTimeframeLabelGenerator(label_config)
        label_result = label_generator.generate_labels(price_data, method="weighted")
        
        # Analyze label quality
        quality_analysis = label_generator.analyze_label_quality(label_result)
        
        logger.info(f"Generated {len(label_result.labels)} multi-timeframe labels")
        logger.info(f"Label quality: {quality_analysis['average_confidence']:.3f} confidence, "
                   f"{quality_analysis['class_balance']['balance_score']:.3f} balance")
        
        return {
            "label_result": label_result,
            "quality_analysis": quality_analysis
        }
    
    def train_multi_timeframe_model(
        self,
        features: Dict[str, Dict[str, np.ndarray]],
        labels: pd.Series
    ) -> Dict[str, Any]:
        """
        Train multi-timeframe neural network model.
        
        Args:
            features: Multi-timeframe features
            labels: Target labels
            
        Returns:
            Training results and model performance metrics
        """
        logger.info("Training multi-timeframe model")
        
        # Create model configuration
        model_config = {
            "timeframe_configs": {
                "1h": {"expected_features": ["rsi", "macd"], "weight": 0.5},
                "4h": {"expected_features": ["rsi", "macd"], "weight": 0.3},
                "1d": {"expected_features": ["rsi", "macd"], "weight": 0.2}
            },
            "architecture": {
                "hidden_layers": [64, 32, 16],
                "dropout": 0.3,
                "activation": "relu"
            },
            "training": {
                "epochs": 100,
                "learning_rate": 0.001,
                "batch_size": 32
            }
        }
        
        # Create training configuration
        training_config = MultiTimeframeTrainingConfig(
            model_config=model_config,
            feature_engineering_config={
                "scaling": {"method": "standard"},
                "selection": {"method": "none"},
                "dimensionality_reduction": {"method": "none"}
            },
            validation_config=CrossTimeframeValidationConfig(
                method="temporal_split",
                test_size=0.2
            ),
            early_stopping_config=EarlyStoppingConfig(
                patience=15,
                monitor="val_loss"
            ),
            training_params={"epochs": 100},
            save_checkpoints=False
        )
        
        # Create trainer and train
        trainer = MultiTimeframeTrainer(training_config)
        
        try:
            # Convert labels to numpy array
            labels_array = labels.values
            
            # Train the model
            training_result = trainer.train(features, labels_array)
            
            # Extract performance metrics
            performance_metrics = {
                "final_train_loss": training_result.training_history.get("train_loss", [])[-1] if training_result.training_history.get("train_loss") else None,
                "final_val_loss": training_result.training_history.get("val_loss", [])[-1] if training_result.training_history.get("val_loss") else None,
                "convergence_epoch": training_result.convergence_metrics.get("final_epoch", 0),
                "timeframe_contributions": training_result.timeframe_contributions,
                "feature_importance": training_result.feature_importance
            }
            
            logger.info(f"Multi-timeframe model training completed")
            logger.info(f"Final validation loss: {performance_metrics['final_val_loss']:.4f}")
            
            return {
                "training_result": training_result,
                "performance_metrics": performance_metrics,
                "model": trainer.model
            }
            
        except Exception as e:
            logger.error(f"Multi-timeframe model training failed: {e}")
            return {
                "error": str(e),
                "performance_metrics": {}
            }
    
    def train_single_timeframe_baselines(
        self,
        features: Dict[str, Dict[str, np.ndarray]],
        labels_by_timeframe: Dict[str, pd.Series]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Train single-timeframe baseline models for comparison.
        
        Args:
            features: Multi-timeframe features
            labels_by_timeframe: Labels for each timeframe
            
        Returns:
            Dictionary mapping timeframes to training results
        """
        logger.info("Training single-timeframe baseline models")
        
        baseline_results = {}
        
        for timeframe in ["1h", "4h", "1d"]:
            if timeframe not in features or timeframe not in labels_by_timeframe:
                logger.warning(f"Missing data for {timeframe} baseline")
                continue
            
            try:
                logger.info(f"Training {timeframe} baseline model")
                
                # Get single timeframe features and labels
                tf_features = features[timeframe]
                tf_labels = labels_by_timeframe[timeframe]
                
                # Combine fuzzy and indicator features
                combined_features = np.concatenate([
                    tf_features['fuzzy_features'],
                    tf_features['indicator_features']
                ], axis=1)
                
                # Find common indices between features and labels
                feature_indices = range(len(combined_features))
                label_indices = tf_labels.index
                
                # Take minimum length
                min_length = min(len(combined_features), len(tf_labels))
                features_aligned = combined_features[:min_length]
                labels_aligned = tf_labels.values[:min_length]
                
                # Create simple single-timeframe configuration
                single_tf_config = MultiTimeframeTrainingConfig(
                    model_config={
                        "timeframe_configs": {
                            timeframe: {"expected_features": ["combined"], "weight": 1.0}
                        },
                        "architecture": {
                            "hidden_layers": [32, 16],
                            "dropout": 0.2
                        },
                        "training": {
                            "epochs": 50,
                            "learning_rate": 0.001
                        }
                    },
                    feature_engineering_config={
                        "scaling": {"method": "standard"},
                        "selection": {"method": "none"}
                    },
                    validation_config=CrossTimeframeValidationConfig(
                        method="temporal_split",
                        test_size=0.2
                    ),
                    early_stopping_config=EarlyStoppingConfig(patience=10),
                    training_params={"epochs": 50}
                )
                
                # Create trainer
                trainer = MultiTimeframeTrainer(single_tf_config)
                
                # Prepare single-timeframe data
                single_tf_data = {timeframe: {"combined": features_aligned}}
                
                # Train
                result = trainer.train(single_tf_data, labels_aligned)
                
                baseline_results[timeframe] = {
                    "training_result": result,
                    "final_val_loss": result.training_history.get("val_loss", [])[-1] if result.training_history.get("val_loss") else None,
                    "convergence_epoch": result.convergence_metrics.get("final_epoch", 0)
                }
                
                logger.info(f"{timeframe} baseline completed: val_loss={baseline_results[timeframe]['final_val_loss']:.4f}")
                
            except Exception as e:
                logger.error(f"Failed to train {timeframe} baseline: {e}")
                baseline_results[timeframe] = {"error": str(e)}
        
        return baseline_results
    
    def compare_model_performance(
        self,
        multi_tf_results: Dict[str, Any],
        baseline_results: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compare multi-timeframe model against single-timeframe baselines.
        
        Args:
            multi_tf_results: Multi-timeframe model results
            baseline_results: Single-timeframe baseline results
            
        Returns:
            Comparison metrics and analysis
        """
        logger.info("Comparing model performance")
        
        comparison = {
            "multi_timeframe_performance": {},
            "baseline_performance": {},
            "improvement_metrics": {},
            "summary": {}
        }
        
        # Extract multi-timeframe performance
        if "performance_metrics" in multi_tf_results:
            mt_metrics = multi_tf_results["performance_metrics"]
            comparison["multi_timeframe_performance"] = {
                "validation_loss": mt_metrics.get("final_val_loss"),
                "convergence_epoch": mt_metrics.get("convergence_epoch"),
                "timeframe_contributions": mt_metrics.get("timeframe_contributions", {})
            }
        
        # Extract baseline performance
        for timeframe, results in baseline_results.items():
            if "error" not in results:
                comparison["baseline_performance"][timeframe] = {
                    "validation_loss": results.get("final_val_loss"),
                    "convergence_epoch": results.get("convergence_epoch")
                }
        
        # Calculate improvements
        mt_val_loss = comparison["multi_timeframe_performance"].get("validation_loss")
        
        if mt_val_loss is not None:
            improvements = {}
            
            for timeframe, baseline in comparison["baseline_performance"].items():
                baseline_loss = baseline.get("validation_loss")
                if baseline_loss is not None:
                    improvement = (baseline_loss - mt_val_loss) / baseline_loss * 100
                    improvements[f"{timeframe}_improvement_pct"] = improvement
            
            comparison["improvement_metrics"] = improvements
            
            # Summary statistics
            if improvements:
                avg_improvement = np.mean(list(improvements.values()))
                best_improvement = max(improvements.values())
                comparison["summary"] = {
                    "average_improvement_pct": avg_improvement,
                    "best_improvement_pct": best_improvement,
                    "improved_over_all_baselines": all(imp > 0 for imp in improvements.values())
                }
        
        # Log results
        logger.info("=== Model Performance Comparison ===")
        logger.info(f"Multi-timeframe val_loss: {mt_val_loss:.4f}" if mt_val_loss else "Multi-timeframe: Failed")
        
        for tf, baseline in comparison["baseline_performance"].items():
            bl_loss = baseline.get("validation_loss")
            logger.info(f"{tf} baseline val_loss: {bl_loss:.4f}" if bl_loss else f"{tf} baseline: Failed")
        
        if "summary" in comparison:
            summary = comparison["summary"]
            logger.info(f"Average improvement: {summary['average_improvement_pct']:.2f}%")
            logger.info(f"Best improvement: {summary['best_improvement_pct']:.2f}%")
            logger.info(f"Improved over all baselines: {summary['improved_over_all_baselines']}")
        
        return comparison
    
    def run_training_pipeline(self) -> Dict[str, Any]:
        """
        Run the complete training pipeline.
        
        Returns:
            Complete results including models, metrics, and comparisons
        """
        logger.info("Starting multi-timeframe training pipeline")
        
        try:
            # 1. Prepare data
            price_data = self.prepare_sample_data()
            
            # 2. Compute features
            features = self.compute_multi_timeframe_features(price_data)
            
            # 3. Generate labels
            label_data = self.generate_multi_timeframe_labels(price_data)
            label_result = label_data["label_result"]
            
            # 4. Train multi-timeframe model
            multi_tf_results = self.train_multi_timeframe_model(
                features, label_result.labels
            )
            
            # 5. Train single-timeframe baselines
            baseline_results = self.train_single_timeframe_baselines(
                features, label_result.timeframe_labels
            )
            
            # 6. Compare performance
            comparison = self.compare_model_performance(
                multi_tf_results, baseline_results
            )
            
            # 7. Compile final results
            final_results = {
                "data_info": {
                    "timeframes": list(price_data.keys()),
                    "data_lengths": {tf: len(data) for tf, data in price_data.items()},
                    "feature_counts": {tf: {k: v.shape for k, v in feat.items()} for tf, feat in features.items()}
                },
                "label_info": {
                    "total_labels": len(label_result.labels),
                    "label_distribution": label_result.label_distribution,
                    "quality_analysis": label_data["quality_analysis"]
                },
                "multi_timeframe_model": multi_tf_results,
                "baseline_models": baseline_results,
                "performance_comparison": comparison,
                "training_metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "config": self.config
                }
            }
            
            logger.info("Multi-timeframe training pipeline completed successfully")
            return final_results
            
        except Exception as e:
            logger.error(f"Training pipeline failed: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


def main():
    """Main training script entry point."""
    parser = argparse.ArgumentParser(description="Train multi-timeframe neuro-fuzzy models")
    parser.add_argument("--config", type=str, help="Path to training configuration file")
    parser.add_argument("--output", type=str, default="training_results.json", help="Output file for results")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load configuration
    if args.config and Path(args.config).exists():
        with open(args.config) as f:
            config = json.load(f)
    else:
        # Default configuration
        config = {
            "data": {
                "symbol": "SAMPLE",
                "timeframes": ["1h", "4h", "1d"]
            },
            "training": {
                "epochs": 100,
                "validation_split": 0.2
            },
            "fuzzy": {
                "membership_functions": "triangular"
            }
        }
    
    # Run training pipeline
    trainer = MultiTimeframeModelTrainer(config)
    results = trainer.run_training_pipeline()
    
    # Save results
    output_path = Path(args.output)
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info(f"Training results saved to {output_path}")
    
    # Print summary
    if "error" not in results:
        print("\n=== TRAINING SUMMARY ===")
        
        if "performance_comparison" in results:
            comparison = results["performance_comparison"]
            if "summary" in comparison:
                summary = comparison["summary"]
                print(f"Average improvement over baselines: {summary.get('average_improvement_pct', 0):.2f}%")
                print(f"Best improvement: {summary.get('best_improvement_pct', 0):.2f}%")
                print(f"Improved over all baselines: {summary.get('improved_over_all_baselines', False)}")
        
        if "label_info" in results:
            label_info = results["label_info"]
            print(f"Generated {label_info['total_labels']} labels")
            
            quality = label_info.get("quality_analysis", {})
            print(f"Label quality: {quality.get('average_confidence', 0):.3f} confidence")
        
        print("Training completed successfully!")
    else:
        print(f"Training failed: {results['error']}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())