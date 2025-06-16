"""Predefined training configuration presets for different scenarios.

This module provides ready-to-use configuration presets for various
multi-timeframe neural network training scenarios.
"""

from typing import Dict, Any, List
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TrainingPreset:
    """A predefined training configuration preset."""
    name: str
    description: str
    config: Dict[str, Any]
    recommended_use_cases: List[str]
    estimated_training_time: str
    memory_requirements: str


class MultiTimeframeTrainingPresets:
    """Collection of predefined training configuration presets."""
    
    @staticmethod
    def get_quick_test_preset() -> TrainingPreset:
        """Quick test configuration for development and debugging."""
        
        config = {
            "data_spec": {
                "timeframes": ["1h", "4h"],
                "lookback_periods": {"1h": 100, "4h": 50}
            },
            "data_preparation": {
                "sequence_length": 20,
                "prediction_horizon": 3,
                "overlap_ratio": 0.5,
                "min_data_quality": 0.7
            },
            "neural_config": {
                "architecture": {
                    "hidden_layers": [32, 16],
                    "dropout": 0.3,
                    "activation": "relu"
                },
                "training": {
                    "learning_rate": 0.001,
                    "batch_size": 16,
                    "epochs": 20,
                    "early_stopping_patience": 5
                }
            },
            "feature_config": {
                "cross_timeframe_features": {
                    "enabled_features": ["correlation", "momentum_cascade"]
                }
            }
        }
        
        return TrainingPreset(
            name="quick_test",
            description="Fast configuration for testing and development",
            config=config,
            recommended_use_cases=["Development", "Testing", "Proof of concept"],
            estimated_training_time="5-10 minutes",
            memory_requirements="< 1GB"
        )
    
    @staticmethod
    def get_production_preset() -> TrainingPreset:
        """Production-ready configuration with comprehensive features."""
        
        config = {
            "data_spec": {
                "timeframes": ["1h", "4h", "1d"],
                "lookback_periods": {"1h": 1000, "4h": 500, "1d": 200}
            },
            "data_preparation": {
                "sequence_length": 100,
                "prediction_horizon": 5,
                "overlap_ratio": 0.3,
                "min_data_quality": 0.85,
                "timeframe_weights": {"1h": 1.0, "4h": 0.8, "1d": 0.6}
            },
            "indicator_config": {
                "timeframes": [
                    {
                        "timeframe": "1h",
                        "indicators": [
                            {"type": "RSI", "params": {"period": 14}},
                            {"type": "SimpleMovingAverage", "params": {"period": 20}},
                            {"type": "ExponentialMovingAverage", "params": {"period": 12}},
                            {"type": "MACD", "params": {"fast_period": 12, "slow_period": 26, "signal_period": 9}},
                            {"type": "BollingerBands", "params": {"period": 20, "std_dev": 2.0}}
                        ]
                    },
                    {
                        "timeframe": "4h",
                        "indicators": [
                            {"type": "RSI", "params": {"period": 14}},
                            {"type": "SimpleMovingAverage", "params": {"period": 50}},
                            {"type": "ExponentialMovingAverage", "params": {"period": 21}},
                            {"type": "ATR", "params": {"period": 14}}
                        ]
                    },
                    {
                        "timeframe": "1d",
                        "indicators": [
                            {"type": "RSI", "params": {"period": 14}},
                            {"type": "SimpleMovingAverage", "params": {"period": 200}},
                            {"type": "ExponentialMovingAverage", "params": {"period": 50}}
                        ]
                    }
                ]
            },
            "neural_config": {
                "architecture": {
                    "hidden_layers": [128, 64, 32, 16],
                    "dropout": 0.4,
                    "activation": "relu",
                    "batch_norm": True
                },
                "training": {
                    "learning_rate": 0.0005,
                    "batch_size": 64,
                    "epochs": 200,
                    "early_stopping_patience": 25,
                    "optimizer": "adamw",
                    "weight_decay": 0.01
                }
            },
            "feature_config": {
                "cross_timeframe_features": {
                    "enabled_features": [
                        "correlation", "divergence", "momentum_cascade",
                        "volatility_regime", "trend_alignment", "support_resistance", "seasonality"
                    ],
                    "normalize_features": True
                },
                "scaling": {
                    "enabled": True,
                    "type": "robust"
                }
            },
            "training_config": {
                "labeling": {
                    "min_change_percent": 0.025,
                    "min_bars": 5
                },
                "validation_split": 0.2,
                "test_split": 0.1,
                "random_seed": 42
            }
        }
        
        return TrainingPreset(
            name="production",
            description="Full-featured configuration for production deployment",
            config=config,
            recommended_use_cases=["Production deployment", "Live trading", "Final model training"],
            estimated_training_time="2-4 hours",
            memory_requirements="4-8GB"
        )
    
    @staticmethod
    def get_high_frequency_preset() -> TrainingPreset:
        """Configuration optimized for high-frequency trading patterns."""
        
        config = {
            "data_spec": {
                "timeframes": ["1m", "5m", "15m", "1h"],
                "lookback_periods": {"1m": 2000, "5m": 1000, "15m": 500, "1h": 200}
            },
            "data_preparation": {
                "sequence_length": 50,
                "prediction_horizon": 2,  # Shorter prediction horizon
                "overlap_ratio": 0.7,     # Higher overlap for more training data
                "min_data_quality": 0.9   # Higher quality requirement
            },
            "neural_config": {
                "architecture": {
                    "hidden_layers": [256, 128, 64, 32],  # Larger network
                    "dropout": 0.5,
                    "activation": "leaky_relu",
                    "batch_norm": True
                },
                "training": {
                    "learning_rate": 0.0001,  # Lower learning rate
                    "batch_size": 128,        # Larger batch size
                    "epochs": 300,
                    "early_stopping_patience": 30,
                    "optimizer": "adamw"
                }
            },
            "feature_config": {
                "cross_timeframe_features": {
                    "enabled_features": [
                        "correlation", "momentum_cascade", "volatility_regime", "seasonality"
                    ]
                }
            },
            "training_config": {
                "labeling": {
                    "min_change_percent": 0.01,  # Smaller movements
                    "min_bars": 3                # Faster signals
                }
            }
        }
        
        return TrainingPreset(
            name="high_frequency",
            description="Optimized for high-frequency trading with minute-level data",
            config=config,
            recommended_use_cases=["High-frequency trading", "Scalping strategies", "Market microstructure"],
            estimated_training_time="4-8 hours",
            memory_requirements="8-16GB"
        )
    
    @staticmethod
    def get_swing_trading_preset() -> TrainingPreset:
        """Configuration for swing trading with longer holding periods."""
        
        config = {
            "data_spec": {
                "timeframes": ["4h", "1d", "1w"],
                "lookback_periods": {"4h": 500, "1d": 365, "1w": 104}
            },
            "data_preparation": {
                "sequence_length": 150,    # Longer sequences
                "prediction_horizon": 10,  # Longer prediction horizon
                "overlap_ratio": 0.2,      # Less overlap
                "min_data_quality": 0.8
            },
            "neural_config": {
                "architecture": {
                    "hidden_layers": [64, 32, 16],
                    "dropout": 0.3,
                    "activation": "relu"
                },
                "training": {
                    "learning_rate": 0.001,
                    "batch_size": 32,
                    "epochs": 150,
                    "early_stopping_patience": 20
                }
            },
            "feature_config": {
                "cross_timeframe_features": {
                    "enabled_features": [
                        "trend_alignment", "support_resistance", "volatility_regime"
                    ]
                }
            },
            "training_config": {
                "labeling": {
                    "min_change_percent": 0.05,  # Larger movements
                    "min_bars": 10               # Longer confirmation
                }
            }
        }
        
        return TrainingPreset(
            name="swing_trading",
            description="Optimized for swing trading with daily/weekly patterns",
            config=config,
            recommended_use_cases=["Swing trading", "Position trading", "Weekly strategies"],
            estimated_training_time="1-2 hours",
            memory_requirements="2-4GB"
        )
    
    @staticmethod
    def get_research_preset() -> TrainingPreset:
        """Configuration for research and experimentation."""
        
        config = {
            "data_spec": {
                "timeframes": ["1h", "4h", "1d"],
                "lookback_periods": {"1h": 2000, "4h": 1000, "1d": 500}
            },
            "data_preparation": {
                "sequence_length": 200,    # Very long sequences
                "prediction_horizon": 1,   # Single step prediction
                "overlap_ratio": 0.1,      # Minimal overlap
                "min_data_quality": 0.95   # Highest quality
            },
            "neural_config": {
                "architecture": {
                    "hidden_layers": [512, 256, 128, 64, 32],  # Very deep
                    "dropout": 0.6,
                    "activation": "swish",
                    "batch_norm": True
                },
                "training": {
                    "learning_rate": 0.0001,
                    "batch_size": 16,         # Small batch for stability
                    "epochs": 500,            # Many epochs
                    "early_stopping_patience": 50,
                    "optimizer": "adamw",
                    "weight_decay": 0.1
                }
            },
            "feature_config": {
                "cross_timeframe_features": {
                    "enabled_features": [
                        "correlation", "divergence", "momentum_cascade",
                        "volatility_regime", "trend_alignment", "support_resistance", "seasonality"
                    ],
                    "normalize_features": True
                }
            },
            "advanced_features": {
                "hyperparameter_tuning": {
                    "enabled": True,
                    "method": "optuna",
                    "n_trials": 100
                }
            }
        }
        
        return TrainingPreset(
            name="research",
            description="Comprehensive configuration for research and deep analysis",
            config=config,
            recommended_use_cases=["Academic research", "Strategy development", "Deep analysis"],
            estimated_training_time="8-24 hours",
            memory_requirements="16-32GB"
        )
    
    @staticmethod
    def get_crypto_preset() -> TrainingPreset:
        """Configuration optimized for cryptocurrency trading."""
        
        config = {
            "data_spec": {
                "timeframes": ["15m", "1h", "4h", "1d"],
                "lookback_periods": {"15m": 1000, "1h": 500, "4h": 200, "1d": 100}
            },
            "data_preparation": {
                "sequence_length": 80,
                "prediction_horizon": 4,
                "overlap_ratio": 0.4,
                "min_data_quality": 0.8
            },
            "neural_config": {
                "architecture": {
                    "hidden_layers": [128, 64, 32],
                    "dropout": 0.5,          # Higher dropout for volatile markets
                    "activation": "relu"
                },
                "training": {
                    "learning_rate": 0.0005,
                    "batch_size": 64,
                    "epochs": 250,
                    "early_stopping_patience": 30,
                    "optimizer": "adamw"
                }
            },
            "feature_config": {
                "cross_timeframe_features": {
                    "enabled_features": [
                        "volatility_regime", "momentum_cascade", "seasonality", "correlation"
                    ]
                }
            },
            "training_config": {
                "labeling": {
                    "min_change_percent": 0.03,  # Higher threshold for crypto volatility
                    "min_bars": 4
                }
            }
        }
        
        return TrainingPreset(
            name="crypto",
            description="Optimized for cryptocurrency markets with high volatility",
            config=config,
            recommended_use_cases=["Cryptocurrency trading", "DeFi strategies", "Altcoin analysis"],
            estimated_training_time="2-3 hours",
            memory_requirements="4-6GB"
        )
    
    @staticmethod
    def get_forex_preset() -> TrainingPreset:
        """Configuration optimized for forex trading."""
        
        config = {
            "data_spec": {
                "timeframes": ["1h", "4h", "1d"],
                "lookback_periods": {"1h": 1000, "4h": 500, "1d": 200}
            },
            "data_preparation": {
                "sequence_length": 120,    # Longer sequences for trends
                "prediction_horizon": 6,
                "overlap_ratio": 0.3,
                "min_data_quality": 0.9    # High quality for forex precision
            },
            "neural_config": {
                "architecture": {
                    "hidden_layers": [96, 48, 24],
                    "dropout": 0.3,
                    "activation": "relu"
                },
                "training": {
                    "learning_rate": 0.0008,
                    "batch_size": 48,
                    "epochs": 180,
                    "early_stopping_patience": 25
                }
            },
            "feature_config": {
                "cross_timeframe_features": {
                    "enabled_features": [
                        "trend_alignment", "support_resistance", "correlation", "seasonality"
                    ]
                }
            },
            "training_config": {
                "labeling": {
                    "min_change_percent": 0.008,  # Smaller movements for forex
                    "min_bars": 6
                }
            }
        }
        
        return TrainingPreset(
            name="forex",
            description="Optimized for forex trading with currency pair analysis",
            config=config,
            recommended_use_cases=["Forex trading", "Currency analysis", "Central bank policy"],
            estimated_training_time="1.5-3 hours",
            memory_requirements="3-5GB"
        )
    
    @classmethod
    def get_all_presets(cls) -> Dict[str, TrainingPreset]:
        """Get all available training presets."""
        return {
            "quick_test": cls.get_quick_test_preset(),
            "production": cls.get_production_preset(),
            "high_frequency": cls.get_high_frequency_preset(),
            "swing_trading": cls.get_swing_trading_preset(),
            "research": cls.get_research_preset(),
            "crypto": cls.get_crypto_preset(),
            "forex": cls.get_forex_preset()
        }
    
    @classmethod
    def get_preset_names(cls) -> List[str]:
        """Get list of available preset names."""
        return list(cls.get_all_presets().keys())
    
    @classmethod
    def get_preset(cls, name: str) -> TrainingPreset:
        """Get a specific preset by name."""
        presets = cls.get_all_presets()
        if name not in presets:
            available = ", ".join(presets.keys())
            raise ValueError(f"Unknown preset '{name}'. Available presets: {available}")
        return presets[name]


def save_preset_to_yaml(preset: TrainingPreset, output_path: Path) -> None:
    """Save a training preset to YAML file."""
    import yaml
    
    # Add metadata to config
    full_config = {
        "metadata": {
            "preset_name": preset.name,
            "description": preset.description,
            "recommended_use_cases": preset.recommended_use_cases,
            "estimated_training_time": preset.estimated_training_time,
            "memory_requirements": preset.memory_requirements
        },
        **preset.config
    }
    
    with open(output_path, 'w') as f:
        yaml.dump(full_config, f, default_flow_style=False, indent=2)


def create_preset_configs(output_dir: Path) -> None:
    """Create YAML configuration files for all presets."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    presets = MultiTimeframeTrainingPresets.get_all_presets()
    
    for preset_name, preset in presets.items():
        output_path = output_dir / f"{preset_name}_config.yaml"
        save_preset_to_yaml(preset, output_path)
        print(f"Created {output_path}")


if __name__ == "__main__":
    # Create preset configuration files
    output_dir = Path(__file__).parent / "presets"
    create_preset_configs(output_dir)
    
    # Print preset summary
    presets = MultiTimeframeTrainingPresets.get_all_presets()
    
    print("\nAvailable Training Presets:")
    print("=" * 50)
    
    for name, preset in presets.items():
        print(f"\n{name.upper()}")
        print(f"Description: {preset.description}")
        print(f"Use cases: {', '.join(preset.recommended_use_cases)}")
        print(f"Training time: {preset.estimated_training_time}")
        print(f"Memory: {preset.memory_requirements}")