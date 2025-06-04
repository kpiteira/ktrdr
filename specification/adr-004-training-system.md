# ADR-004: Training System Design

## Status
**Draft** - December 2024

## Context
KTRDR has established a neuro-fuzzy strategy framework (ADR-003) that combines fuzzy logic processing of technical indicators with neural network decision-making. Before we can backtest strategies, we need a robust system for training neural networks using historical market data with supervised learning labels.

This training system must integrate with existing KTRDR infrastructure (data management, indicators, fuzzy logic) while providing a clear path from raw market data to trained models ready for backtesting and eventual live trading.

## Decision

### Training System Architecture

The training system follows a pipeline architecture that leverages existing KTRDR modules:

```
Historical Data → Indicators → Fuzzy Logic → Feature Engineering → Neural Network Training
      ↓              ↓            ↓              ↓                    ↓
    OHLCV      RSI, MACD,    Membership    Feature Vector      Trained Model
              SMA, etc.      Values         + ZigZag Labels    (.pt file)
```

### Core Components

#### 1. Training Pipeline Orchestrator
**Module**: `ktrdr/training/train_strategy.py`
**Purpose**: Coordinate the end-to-end training process

```python
# ktrdr/training/train_strategy.py
from typing import Dict, Any, Optional
import pandas as pd
from pathlib import Path
import yaml
import torch

class StrategyTrainer:
    """Orchestrates the complete training pipeline for a neuro-fuzzy strategy"""
    
    def __init__(self, strategy_config_path: str):
        self.config = self._load_strategy_config(strategy_config_path)
        self.strategy_name = self.config['name']
        
        # Initialize existing KTRDR components
        self.data_manager = DataManager()
        self.indicator_engine = IndicatorEngine()
        self.fuzzy_engine = FuzzyEngine()
        
        # Initialize training-specific components
        self.zigzag_labeler = ZigZagLabeler(
            threshold=self.config['training']['labels']['zigzag_threshold'],
            lookahead=self.config['training']['labels']['label_lookahead']
        )
        self.neural_model = self._create_neural_model()
        
    def train(self, symbol: str, timeframe: str, 
              start_date: Optional[str] = None,
              end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the complete training pipeline for a single instrument
        
        Returns training metrics and model save path
        """
        # Step 1: Load historical data
        print(f"Loading data for {symbol} {timeframe}...")
        data = self.data_manager.load_data(
            symbol=symbol, 
            timeframe=timeframe, 
            mode="full",
            start_date=start_date,
            end_date=end_date
        )
        
        # Step 2: Calculate indicators
        print("Calculating technical indicators...")
        indicators = self.indicator_engine.calculate_multiple(
            data=data,
            configs=self.config['indicators']
        )
        
        # Step 3: Generate fuzzy memberships
        print("Computing fuzzy memberships...")
        fuzzy_values = self.fuzzy_engine.evaluate_batch(
            indicators=indicators,
            fuzzy_config=self.config['fuzzy_sets']
        )
        
        # Step 4: Generate training labels
        print("Generating ZigZag labels...")
        labels = self.zigzag_labeler.generate_labels(data)
        
        # Step 5: Prepare features
        print("Preparing feature matrix...")
        X, y = self._prepare_training_data(data, indicators, fuzzy_values, labels)
        
        # Step 6: Split data
        X_train, X_val, X_test, y_train, y_val, y_test = self._split_data(X, y)
        
        # Step 7: Train model
        print("Training neural network...")
        training_history = self._train_neural_network(
            X_train, y_train, X_val, y_val
        )
        
        # Step 8: Evaluate and save
        print("Evaluating model...")
        test_metrics = self._evaluate_model(X_test, y_test)
        
        # Step 9: Calculate feature importance
        feature_importance = self._calculate_feature_importance(
            X_train, y_train, X_val, y_val
        )
        
        # Step 10: Save model and results
        model_path = self._save_model_and_results(
            symbol, timeframe, test_metrics, feature_importance
        )
        
        return {
            'model_path': model_path,
            'training_history': training_history,
            'test_metrics': test_metrics,
            'feature_importance': feature_importance,
            'data_stats': {
                'total_samples': len(data),
                'training_samples': len(X_train),
                'validation_samples': len(X_val),
                'test_samples': len(X_test)
            }
        }
```

#### 2. Feature Engineering Module
**Module**: `ktrdr/training/feature_engineering.py`
**Purpose**: Convert fuzzy memberships and market data into neural network features

```python
# ktrdr/training/feature_engineering.py
import numpy as np
import pandas as pd
from typing import List, Tuple

class FeatureEngineer:
    """Transforms market data and fuzzy values into neural network features"""
    
    def __init__(self, feature_config: Dict[str, Any]):
        self.config = feature_config
        self.feature_names: List[str] = []
        
    def prepare_features(self, 
                        data: pd.DataFrame,
                        indicators: pd.DataFrame,
                        fuzzy_values: pd.DataFrame) -> pd.DataFrame:
        """
        Create feature matrix from multiple data sources
        
        Features include:
        - Fuzzy membership values (primary features)
        - Price context (if enabled)
        - Volume context (if enabled)
        - Temporal features (lookback)
        """
        features = pd.DataFrame(index=data.index)
        
        # Core fuzzy features
        fuzzy_columns = [col for col in fuzzy_values.columns if 'membership' in col]
        for col in fuzzy_columns:
            features[col] = fuzzy_values[col]
            self.feature_names.append(col)
        
        # Price context features
        if self.config.get('include_price_context', False):
            # Price relative to SMA
            if 'sma_20' in indicators.columns:
                features['price_to_sma'] = data['close'] / indicators['sma_20']
                self.feature_names.append('price_to_sma')
            
            # Price momentum
            features['price_change_1'] = data['close'].pct_change(1)
            features['price_change_5'] = data['close'].pct_change(5)
            self.feature_names.extend(['price_change_1', 'price_change_5'])
        
        # Volume context features
        if self.config.get('include_volume_context', False):
            volume_sma = data['volume'].rolling(20).mean()
            features['volume_ratio'] = data['volume'] / volume_sma
            features['volume_change'] = data['volume'].pct_change(1)
            self.feature_names.extend(['volume_ratio', 'volume_change'])
        
        # Temporal features (lookback)
        lookback = self.config.get('lookback_periods', 1)
        if lookback > 1:
            for i in range(1, lookback):
                for col in fuzzy_columns:
                    shifted_name = f"{col}_lag_{i}"
                    features[shifted_name] = fuzzy_values[col].shift(i)
                    self.feature_names.append(shifted_name)
        
        # Handle NaN values
        features = features.fillna(0)
        
        return features
    
    def get_feature_names(self) -> List[str]:
        """Return names of all features for interpretability"""
        return self.feature_names
```

#### 3. Model Training Logic
**Module**: `ktrdr/training/model_trainer.py`
**Purpose**: Neural network training with early stopping and validation

```python
# ktrdr/training/model_trainer.py
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from typing import Dict, Any, Tuple
import numpy as np

class ModelTrainer:
    """Handles the neural network training process"""
    
    def __init__(self, model: nn.Module, training_config: Dict[str, Any]):
        self.model = model
        self.config = training_config
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        
        # Setup optimizer
        self.optimizer = self._create_optimizer()
        self.criterion = nn.CrossEntropyLoss()
        
        # Training history
        self.history = {
            'train_loss': [],
            'train_accuracy': [],
            'val_loss': [],
            'val_accuracy': []
        }
        
    def train(self, 
              X_train: np.ndarray, 
              y_train: np.ndarray,
              X_val: np.ndarray, 
              y_val: np.ndarray) -> Dict[str, List[float]]:
        """
        Train the model with early stopping
        """
        # Convert to PyTorch tensors
        X_train_t = torch.FloatTensor(X_train).to(self.device)
        y_train_t = torch.LongTensor(y_train).to(self.device)
        X_val_t = torch.FloatTensor(X_val).to(self.device)
        y_val_t = torch.LongTensor(y_val).to(self.device)
        
        # Create data loaders
        train_dataset = TensorDataset(X_train_t, y_train_t)
        train_loader = DataLoader(
            train_dataset, 
            batch_size=self.config['batch_size'],
            shuffle=True
        )
        
        # Early stopping setup
        best_val_loss = float('inf')
        patience_counter = 0
        patience = self.config['early_stopping']['patience']
        
        # Training loop
        for epoch in range(self.config['epochs']):
            # Training phase
            self.model.train()
            train_loss = 0
            train_correct = 0
            
            for batch_X, batch_y in train_loader:
                self.optimizer.zero_grad()
                outputs = self.model(batch_X)
                loss = self.criterion(outputs, batch_y)
                loss.backward()
                self.optimizer.step()
                
                train_loss += loss.item()
                _, predicted = torch.max(outputs.data, 1)
                train_correct += (predicted == batch_y).sum().item()
            
            # Validation phase
            self.model.eval()
            with torch.no_grad():
                val_outputs = self.model(X_val_t)
                val_loss = self.criterion(val_outputs, y_val_t)
                _, val_predicted = torch.max(val_outputs.data, 1)
                val_correct = (val_predicted == y_val_t).sum().item()
            
            # Calculate metrics
            train_accuracy = train_correct / len(X_train)
            val_accuracy = val_correct / len(X_val)
            avg_train_loss = train_loss / len(train_loader)
            
            # Store history
            self.history['train_loss'].append(avg_train_loss)
            self.history['train_accuracy'].append(train_accuracy)
            self.history['val_loss'].append(val_loss.item())
            self.history['val_accuracy'].append(val_accuracy)
            
            # Print progress
            if epoch % 10 == 0:
                print(f"Epoch {epoch}: Train Loss={avg_train_loss:.4f}, "
                      f"Train Acc={train_accuracy:.4f}, "
                      f"Val Loss={val_loss:.4f}, Val Acc={val_accuracy:.4f}")
            
            # Early stopping check
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                # Save best model state
                self.best_model_state = self.model.state_dict().copy()
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    print(f"Early stopping at epoch {epoch}")
                    break
        
        # Restore best model
        self.model.load_state_dict(self.best_model_state)
        
        return self.history
```

#### 4. Feature Importance Analysis
**Module**: `ktrdr/training/feature_importance.py`
**Purpose**: Understand which features drive model decisions

```python
# ktrdr/training/feature_importance.py
import numpy as np
import torch
from typing import Dict, List

class FeatureImportanceAnalyzer:
    """Calculate feature importance using permutation importance"""
    
    def __init__(self, model: nn.Module, feature_names: List[str]):
        self.model = model
        self.feature_names = feature_names
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
    def calculate_importance(self, 
                           X: np.ndarray, 
                           y: np.ndarray,
                           n_iterations: int = 10) -> Dict[str, float]:
        """
        Calculate feature importance using permutation method
        
        For each feature:
        1. Randomly shuffle the feature values
        2. Measure decrease in model accuracy
        3. Average over multiple iterations
        """
        self.model.eval()
        X_tensor = torch.FloatTensor(X).to(self.device)
        y_tensor = torch.LongTensor(y).to(self.device)
        
        # Baseline accuracy
        with torch.no_grad():
            outputs = self.model(X_tensor)
            _, predicted = torch.max(outputs.data, 1)
            baseline_accuracy = (predicted == y_tensor).float().mean().item()
        
        importance_scores = {}
        
        for idx, feature_name in enumerate(self.feature_names):
            accuracy_drops = []
            
            for _ in range(n_iterations):
                # Create a copy and shuffle one feature
                X_permuted = X.copy()
                np.random.shuffle(X_permuted[:, idx])
                
                # Measure accuracy with permuted feature
                X_perm_tensor = torch.FloatTensor(X_permuted).to(self.device)
                with torch.no_grad():
                    outputs = self.model(X_perm_tensor)
                    _, predicted = torch.max(outputs.data, 1)
                    perm_accuracy = (predicted == y_tensor).float().mean().item()
                
                accuracy_drops.append(baseline_accuracy - perm_accuracy)
            
            # Average importance over iterations
            importance_scores[feature_name] = np.mean(accuracy_drops)
        
        # Normalize scores
        total_importance = sum(importance_scores.values())
        if total_importance > 0:
            importance_scores = {
                k: v/total_importance for k, v in importance_scores.items()
            }
        
        return importance_scores
```

#### 5. Model Storage and Versioning
**Module**: `ktrdr/training/model_storage.py`
**Purpose**: Save trained models with metadata and versioning

```python
# ktrdr/training/model_storage.py
from pathlib import Path
import torch
import json
import yaml
from datetime import datetime
from typing import Dict, Any

class ModelStorage:
    """Handles saving and loading of trained models with metadata"""
    
    def __init__(self, base_path: str = "models"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        
    def save_model(self, 
                   model: nn.Module,
                   strategy_name: str,
                   symbol: str,
                   timeframe: str,
                   metrics: Dict[str, float],
                   feature_importance: Dict[str, float],
                   config: Dict[str, Any]) -> Path:
        """
        Save model with organized directory structure:
        models/
        └── strategy_name/
            └── symbol_timeframe_version/
                ├── model.pt
                ├── metrics.json
                ├── feature_importance.json
                └── config.yaml
        """
        # Create versioned directory
        version = self._get_next_version(strategy_name, symbol, timeframe)
        model_dir = self.base_path / strategy_name / f"{symbol}_{timeframe}_v{version}"
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Save model weights
        model_path = model_dir / "model.pt"
        torch.save({
            'model_state_dict': model.state_dict(),
            'model_config': config['model'],
            'feature_config': config['features'],
            'timestamp': datetime.now().isoformat()
        }, model_path)
        
        # Save metrics
        metrics_path = model_dir / "metrics.json"
        with open(metrics_path, 'w') as f:
            json.dump({
                'test_metrics': metrics,
                'symbol': symbol,
                'timeframe': timeframe,
                'version': version
            }, f, indent=2)
        
        # Save feature importance
        importance_path = model_dir / "feature_importance.json"
        with open(importance_path, 'w') as f:
            json.dump(feature_importance, f, indent=2)
        
        # Save full config
        config_path = model_dir / "config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        print(f"Model saved to: {model_dir}")
        return model_dir
    
    def _get_next_version(self, strategy_name: str, symbol: str, timeframe: str) -> int:
        """Find the next available version number"""
        strategy_dir = self.base_path / strategy_name
        if not strategy_dir.exists():
            return 1
        
        # Find existing versions
        pattern = f"{symbol}_{timeframe}_v*"
        existing = list(strategy_dir.glob(pattern))
        
        if not existing:
            return 1
        
        # Extract version numbers
        versions = []
        for path in existing:
            try:
                version = int(path.name.split('_v')[-1])
                versions.append(version)
            except:
                continue
        
        return max(versions) + 1 if versions else 1
```

### Training Configuration Integration

The training system uses the strategy YAML configuration from ADR-003, specifically the `training` section:

```yaml
# strategies/neuro_mean_reversion.yaml
training:
  method: "supervised"
  labels:
    source: "zigzag"
    zigzag_threshold: 0.05  # 5% price movement
    label_lookahead: 20     # bars to look ahead
  
  data_split:
    train: 0.7
    validation: 0.15
    test: 0.15
    
  fitness_metrics:
    primary: "accuracy"
    secondary: ["precision", "recall", "f1_score"]
```

### CLI Interface

```python
# ktrdr/training/cli.py
import click
from pathlib import Path

@click.command()
@click.option('--strategy', '-s', required=True, help='Path to strategy YAML file')
@click.option('--symbol', required=True, help='Trading symbol (e.g., AAPL)')
@click.option('--timeframe', '-t', default='1h', help='Timeframe (e.g., 1h, 1d)')
@click.option('--start-date', help='Training start date (YYYY-MM-DD)')
@click.option('--end-date', help='Training end date (YYYY-MM-DD)')
def train_strategy(strategy, symbol, timeframe, start_date, end_date):
    """Train a neuro-fuzzy strategy on historical data"""
    
    # Validate strategy file exists
    strategy_path = Path(strategy)
    if not strategy_path.exists():
        click.echo(f"Error: Strategy file {strategy} not found")
        return
    
    # Initialize trainer
    trainer = StrategyTrainer(strategy_path)
    
    # Run training
    click.echo(f"Training {trainer.strategy_name} on {symbol} {timeframe}")
    results = trainer.train(symbol, timeframe, start_date, end_date)
    
    # Display results
    click.echo("\nTraining Complete!")
    click.echo(f"Model saved to: {results['model_path']}")
    click.echo(f"\nTest Metrics:")
    for metric, value in results['test_metrics'].items():
        click.echo(f"  {metric}: {value:.4f}")
    
    click.echo(f"\nTop 5 Important Features:")
    sorted_features = sorted(
        results['feature_importance'].items(), 
        key=lambda x: x[1], 
        reverse=True
    )[:5]
    for feature, importance in sorted_features:
        click.echo(f"  {feature}: {importance:.3f}")

# Usage example:
# python -m ktrdr.training.cli --strategy strategies/neuro_mean_reversion.yaml --symbol AAPL --timeframe 1h
```

## Integration with Existing Systems

### Data Flow Integration
The training system seamlessly integrates with existing KTRDR modules:

```python
# Training uses existing modules
data = DataManager().load_data(symbol, timeframe)  # Existing
indicators = IndicatorEngine().calculate_multiple(data, configs)  # Existing
fuzzy_values = FuzzyEngine().evaluate_batch(indicators, fuzzy_config)  # Existing

# Training adds new capabilities
labels = ZigZagLabeler().generate_labels(data)  # New
features = FeatureEngineer().prepare_features(data, indicators, fuzzy_values)  # New
model = ModelTrainer().train(features, labels)  # New
```

### API Extensions
While the MVP focuses on CLI usage, the training system is designed to support future API endpoints:

```python
# Future API endpoints (post-MVP)
POST /api/v1/training/start
GET /api/v1/training/{job_id}/status
GET /api/v1/training/{job_id}/results
GET /api/v1/models/
GET /api/v1/models/{model_id}/metrics
```

## Consequences

### Positive Consequences
- **Leverages existing infrastructure**: Uses current data management, indicators, and fuzzy logic
- **Clear separation of concerns**: Training is independent from backtesting and live trading
- **Reproducible results**: Versioned models with saved configurations
- **Interpretable models**: Feature importance helps understand decisions
- **Simple MVP path**: Single instrument training with clear CLI interface

### Negative Consequences
- **Single instrument limitation**: MVP doesn't support multi-symbol training
- **No online learning**: Models must be retrained from scratch
- **Limited model types**: Only supports neural networks defined in config
- **No hyperparameter optimization**: Manual parameter tuning required

### Mitigation Strategies
- Design allows easy extension to multi-instrument training
- Model versioning enables A/B testing of different approaches
- Modular architecture supports adding new model types
- Clear integration points for future AutoML capabilities

## Future Evolution Ideas

### 1. Multi-Instrument Training
**Rationale**: Training on multiple instruments can create more robust models
**Benefits**: 
- Better generalization across different market conditions
- Shared learning from correlated assets
- Portfolio-level strategy development

**Implementation approach**:
```python
# Future: Multi-instrument training
trainer.train_multi(
    symbols=['AAPL', 'MSFT', 'GOOGL'],
    timeframe='1h',
    mode='concatenate'  # or 'ensemble' or 'transfer_learning'
)
```

### 2. Advanced Model Architectures
**Rationale**: Different architectures may capture different market patterns
**Options**:
- **LSTM/GRU**: For temporal dependencies beyond simple lookback
- **Transformer**: For attention-based pattern recognition
- **Ensemble**: Combining multiple models for robustness

### 3. Automated Hyperparameter Optimization
**Rationale**: Manual tuning is time-consuming and may miss optimal parameters
**Approaches**:
- **Grid Search**: Systematic parameter exploration
- **Bayesian Optimization**: Efficient parameter search
- **Genetic Algorithms**: Evolution-based optimization

### 4. Online Learning Capabilities
**Rationale**: Markets evolve, and models should adapt
**Features**:
- Incremental learning from new data
- Concept drift detection
- Automatic retraining triggers

### 5. Advanced Labeling Strategies
**Beyond ZigZag**:
- **Risk-adjusted labels**: Incorporate volatility in label generation
- **Multi-class labels**: More nuanced than BUY/HOLD/SELL
- **Reinforcement learning**: Learn from actual trading outcomes

### 6. Feature Engineering Enhancements
**Rationale**: Better features lead to better predictions
**Ideas**:
- **Market microstructure features**: Bid-ask spread, order flow
- **Cross-asset features**: Correlations, sector movements
- **Alternative data**: Sentiment, news events

### 7. Distributed Training
**Rationale**: Scale to larger datasets and faster iteration
**Benefits**:
- Parallel training across multiple instruments
- Faster hyperparameter search
- GPU cluster utilization

## Implementation Notes

### MVP Checklist
- [ ] Implement ZigZag labeler (building on ADR-003 design)
- [ ] Create feature engineering pipeline
- [ ] Implement model training with early stopping
- [ ] Add feature importance calculation
- [ ] Create model storage system with versioning
- [ ] Build CLI interface for training
- [ ] Add comprehensive logging throughout
- [ ] Write unit tests for each component
- [ ] Create example strategy configuration
- [ ] Document training workflow in README

### Dependencies
- Existing: `pandas`, `numpy`, `torch`, `pyyaml`
- New: `click` (for CLI), potentially `scikit-learn` (for metrics)

### Performance Considerations
- Feature matrix can be large: implement chunking if needed
- Model training can be GPU-intensive: support both CPU and GPU
- Feature importance calculation can be slow: make it optional

## Conclusion

The Training System provides a **clear path** from historical market data to trained neural network models, leveraging all existing KTRDR infrastructure while maintaining simplicity for the MVP. The modular design allows for significant future enhancements without disrupting the core training workflow.

**Key design principles**:
- **Full pipeline integration**: Leverages all existing modules
- **Clear separation**: Training is independent from inference
- **Reproducibility**: Versioned models with complete metadata
- **Interpretability**: Feature importance for understanding
- **Extensibility**: Ready for multi-instrument and advanced features

This design ensures that the MVP can quickly produce trained models for backtesting while providing a solid foundation for future sophistication.