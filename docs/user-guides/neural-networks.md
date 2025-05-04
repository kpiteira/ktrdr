# Neural Networks Guide

This guide explains how to work with neural networks in KTRDR, including creating, training, and deploying neural network models for market prediction and analysis.

## Overview

KTRDR provides a comprehensive neural network system that allows you to:

- Design and configure various neural network architectures
- Train models on historical market data
- Evaluate model performance with robust metrics
- Generate trading signals based on model predictions
- Visualize model predictions and performance

## Neural Network Types

KTRDR supports the following neural network architectures:

### Feed-Forward Neural Networks

Standard neural networks suitable for pattern recognition and classification tasks.

### Recurrent Neural Networks (RNN)

Specialized networks for sequential data with the ability to maintain internal state:

- LSTM (Long Short-Term Memory) networks
- GRU (Gated Recurrent Unit) networks

### Convolutional Neural Networks (CNN)

Networks that can identify patterns in multi-dimensional data, useful for finding patterns across multiple indicators or timeframes.

### Hybrid Models

KTRDR supports combining different network architectures to leverage their respective strengths.

## Creating Neural Network Models

You can create neural network models using either the Python API or the command-line interface.

### Using the Python API

```python
from ktrdr.neural import NeuralNetworkBuilder

# Initialize a neural network builder
builder = NeuralNetworkBuilder()

# Create a simple LSTM model
model = builder.create_model(
    type="lstm",
    input_features=["close", "volume", "rsi", "macd"],
    output_features=["price_direction"],
    layers=[64, 32],
    lookback_period=20
)

# Print model summary
print(model.summary())
```

### Using the CLI

```bash
# Create a new neural network model
ktrdr neural create --name my_price_predictor --type lstm --features close,volume,rsi,macd

# Create a model with custom configuration
ktrdr neural create --name trend_classifier --config models/my_config.yaml
```

## Training Models

### Using the Python API

```python
from ktrdr.data import DataManager
from ktrdr.neural import NeuralTrainer

# Load training data
data_manager = DataManager()
df = data_manager.load("AAPL", interval="1d", start="2018-01-01", end="2023-01-01")

# Initialize the trainer
trainer = NeuralTrainer(model)

# Train the model
history = trainer.train(
    data=df,
    target="price_direction",
    validation_split=0.2,
    epochs=100,
    batch_size=32
)

# Save the trained model
model.save("models/my_lstm_model")
```

### Using the CLI

```bash
# Train a model on AAPL data
ktrdr neural train --model my_price_predictor --symbol AAPL --timeframe 1d --start 2018-01-01 --end 2023-01-01

# Train with specific parameters
ktrdr neural train --model trend_classifier --epochs 200 --batch-size 64 --validation-split 0.3
```

## Evaluating Models

```python
from ktrdr.neural import NeuralEvaluator

# Load test data (different from training data)
test_df = data_manager.load("AAPL", interval="1d", start="2023-01-01")

# Initialize evaluator
evaluator = NeuralEvaluator(model)

# Evaluate the model
metrics = evaluator.evaluate(test_df)
print(f"Accuracy: {metrics['accuracy']:.2f}")
print(f"Precision: {metrics['precision']:.2f}")
print(f"Recall: {metrics['recall']:.2f}")
print(f"F1 Score: {metrics['f1']:.2f}")

# Generate performance visualization
evaluator.plot_performance()
```

## Generating Predictions

```python
from ktrdr.neural import NeuralPredictor

# Initialize predictor
predictor = NeuralPredictor(model)

# Generate predictions
predictions = predictor.predict(test_df)

# Get trading signals
signals = predictor.get_signals(threshold=0.7)

# Print the first few signals
print(signals.head())
```

## Visualization

KTRDR integrates neural network predictions with its visualization system:

```python
from ktrdr.visualization import Visualizer

# Create visualizer
visualizer = Visualizer()

# Add price data
visualizer.add_price_panel(test_df)

# Add neural network predictions
visualizer.add_prediction_panel(predictions, actual=test_df['close'])

# Add signals to the price chart
visualizer.add_signals(signals)

# Display the chart
visualizer.show()

# Save the chart
visualizer.save("output/neural_predictions.html")
```

## Model Management

KTRDR provides tools for managing your neural network models:

```python
from ktrdr.neural import ModelManager

# List all available models
manager = ModelManager()
models = manager.list_models()

# Load an existing model
loaded_model = manager.load("models/my_lstm_model")

# Compare model performances
comparison = manager.compare(["model1", "model2", "model3"], metric="accuracy")
manager.plot_comparison(comparison)

# Export a model for deployment
manager.export("my_lstm_model", format="onnx", destination="models/deployment/")
```

## Hyperparameter Optimization

KTRDR supports automated hyperparameter optimization to find the best model configuration:

```python
from ktrdr.neural import HyperparameterOptimizer

# Define parameter space
param_space = {
    'layers': [[32], [64], [128], [64, 32], [128, 64]],
    'dropout': [0.0, 0.2, 0.5],
    'learning_rate': [0.001, 0.01, 0.1],
    'optimizer': ['adam', 'rmsprop', 'sgd']
}

# Initialize optimizer
optimizer = HyperparameterOptimizer(
    model_type="lstm",
    param_space=param_space,
    max_trials=20
)

# Run optimization
best_params = optimizer.optimize(
    train_data=df,
    target="price_direction",
    validation_split=0.2
)

# Create model with best parameters
best_model = builder.create_model(
    type="lstm",
    input_features=["close", "volume", "rsi", "macd"],
    output_features=["price_direction"],
    **best_params
)
```

## Configuration

Neural network models are configured via YAML files:

```yaml
# Example neural network configuration
model:
  type: lstm
  input_features:
    - close
    - volume
    - rsi
    - macd
  output_features:
    - price_direction
  normalize: true
  lookback_period: 20
  layers:
    - units: 64
      activation: relu
      dropout: 0.2
    - units: 32
      activation: relu
  compile:
    optimizer: adam
    learning_rate: 0.001
    loss: binary_crossentropy
    metrics:
      - accuracy
```

## Integration with Strategies

Neural networks can be integrated into KTRDR trading strategies:

```python
from ktrdr.strategies import Strategy
from ktrdr.neural import NeuralPredictor

class NeuralStrategy(Strategy):
    def __init__(self, model_name):
        super().__init__()
        self.model = ModelManager().load(model_name)
        self.predictor = NeuralPredictor(self.model)
        
    def generate_signals(self, data):
        # Get neural network predictions
        predictions = self.predictor.predict(data)
        
        # Convert predictions to signals
        signals = self.predictor.get_signals(threshold=0.7)
        
        return signals
```

## Best Practices

1. **Data Preparation**: Ensure your data is clean and properly normalized before training.

2. **Prevent Overfitting**: Use validation sets, early stopping, and regularization techniques.

3. **Feature Selection**: Choose relevant features that have predictive power for your target.

4. **Model Complexity**: Start with simpler models and increase complexity only if needed.

5. **Ensemble Methods**: Consider combining predictions from multiple models for better results.

## Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Overfitting | Model learns noise in training data | Use regularization, dropout, early stopping; increase training data |
| Poor Generalization | Model doesn't work well on new data | Simplify model architecture, improve feature selection |
| Vanishing Gradients | Network too deep or improper activation | Use LSTM/GRU units, batch normalization, residual connections |
| Training Too Slow | Too much data or complex model | Reduce batch size, simplify model, use GPU acceleration |
| Inconsistent Results | Random initialization or stochastic training | Set random seed, use cross-validation, average multiple runs |

## Related Documentation

- [API Reference: Neural Network API](../api-reference/neural-api.md)
- [CLI Reference: Neural Network Commands](../cli/neural-commands.md)
- [Configuration: Neural Network Configuration](../configuration/neural-config.md)
- [Examples: Neural Network Examples](../examples/neural-examples.md)
- [Developer Guide: Neural Network Development](../developer/neural-development.md)