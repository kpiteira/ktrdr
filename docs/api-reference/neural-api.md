# Neural Network API Reference

This document provides a comprehensive reference for the KTRDR Neural Network API.

## NeuralNetworkBuilder

The `NeuralNetworkBuilder` class is responsible for creating neural network models with various architectures.

```python
from ktrdr.neural import NeuralNetworkBuilder
```

### Methods

#### `create_model()`

Creates a new neural network model with the specified architecture and parameters.

```python
def create_model(
    type: str,
    input_features: List[str],
    output_features: List[str],
    layers: List[Union[int, Dict]] = None,
    lookback_period: int = 10,
    **kwargs
) -> NeuralModel:
    """
    Create a new neural network model.
    
    Args:
        type: Type of neural network to create ("ffn", "lstm", "gru", "cnn", "hybrid")
        input_features: List of input feature names
        output_features: List of output feature names
        layers: List of layer specifications (integers for layer sizes or dicts for detailed config)
        lookback_period: Number of previous time periods to consider (for sequence models)
        **kwargs: Additional model configuration parameters
        
    Returns:
        A configured NeuralModel instance
    """
```

#### `create_from_config()`

Creates a model from a YAML configuration file.

```python
def create_from_config(
    config_path: str
) -> NeuralModel:
    """
    Create a neural network model from a YAML configuration file.
    
    Args:
        config_path: Path to the YAML configuration file
        
    Returns:
        A configured NeuralModel instance
    """
```

## NeuralModel

The `NeuralModel` class represents a neural network model and provides methods for training, evaluation, and prediction.

```python
from ktrdr.neural import NeuralModel
```

### Methods

#### `summary()`

Returns a summary of the model architecture.

```python
def summary() -> str:
    """
    Get a string representation of the model architecture.
    
    Returns:
        A string describing the model's layers and parameters
    """
```

#### `save()`

Saves the model to disk.

```python
def save(
    path: str,
    include_weights: bool = True,
    include_optimizer: bool = False
) -> None:
    """
    Save the model to the specified path.
    
    Args:
        path: Directory or file path to save the model
        include_weights: Whether to save model weights
        include_optimizer: Whether to save optimizer state
    """
```

#### `load()`

Static method to load a model from disk.

```python
@staticmethod
def load(
    path: str
) -> NeuralModel:
    """
    Load a model from the specified path.
    
    Args:
        path: Path to the saved model
        
    Returns:
        A loaded NeuralModel instance
    """
```

#### `compile()`

Configures the model for training.

```python
def compile(
    optimizer: str = "adam",
    learning_rate: float = 0.001,
    loss: str = "mse",
    metrics: List[str] = None
) -> None:
    """
    Configure the model for training.
    
    Args:
        optimizer: Name of the optimizer to use
        learning_rate: Learning rate for the optimizer
        loss: Loss function to use
        metrics: List of metrics to track during training
    """
```

## NeuralTrainer

The `NeuralTrainer` class handles the training of neural network models.

```python
from ktrdr.neural import NeuralTrainer
```

### Methods

#### `__init__()`

```python
def __init__(
    model: NeuralModel,
    callbacks: List[Any] = None
):
    """
    Initialize a trainer for a neural network model.
    
    Args:
        model: The model to train
        callbacks: List of training callbacks
    """
```

#### `train()`

Trains the model on the provided data.

```python
def train(
    data: pd.DataFrame,
    target: Union[str, List[str]],
    validation_split: float = 0.2,
    epochs: int = 100,
    batch_size: int = 32,
    early_stopping: bool = True,
    patience: int = 10,
    verbose: int = 1
) -> Dict:
    """
    Train the model on the provided data.
    
    Args:
        data: DataFrame containing training data
        target: Target column(s) to predict
        validation_split: Fraction of data to use for validation
        epochs: Number of training epochs
        batch_size: Batch size for training
        early_stopping: Whether to use early stopping
        patience: Number of epochs with no improvement after which training will stop
        verbose: Verbosity mode (0, 1, or 2)
        
    Returns:
        Dictionary containing training history
    """
```

#### `train_with_generator()`

Trains the model using a data generator for handling large datasets.

```python
def train_with_generator(
    data_generator: Any,
    steps_per_epoch: int,
    validation_data: Any = None,
    validation_steps: int = None,
    epochs: int = 100,
    callbacks: List[Any] = None,
    verbose: int = 1
) -> Dict:
    """
    Train the model using a data generator.
    
    Args:
        data_generator: Generator that yields batches of data
        steps_per_epoch: Number of batches per epoch
        validation_data: Generator for validation data
        validation_steps: Number of validation batches
        epochs: Number of training epochs
        callbacks: List of callbacks for training
        verbose: Verbosity mode
        
    Returns:
        Dictionary containing training history
    """
```

#### `cross_validate()`

Performs k-fold cross-validation.

```python
def cross_validate(
    data: pd.DataFrame,
    target: Union[str, List[str]],
    n_splits: int = 5,
    epochs: int = 100,
    batch_size: int = 32
) -> Dict:
    """
    Perform k-fold cross-validation.
    
    Args:
        data: DataFrame containing training data
        target: Target column(s) to predict
        n_splits: Number of folds
        epochs: Number of training epochs per fold
        batch_size: Batch size for training
        
    Returns:
        Dictionary with cross-validation results
    """
```

## NeuralEvaluator

The `NeuralEvaluator` class provides methods for evaluating neural network models.

```python
from ktrdr.neural import NeuralEvaluator
```

### Methods

#### `__init__()`

```python
def __init__(
    model: NeuralModel
):
    """
    Initialize an evaluator for a neural network model.
    
    Args:
        model: The model to evaluate
    """
```

#### `evaluate()`

Evaluates the model on test data.

```python
def evaluate(
    data: pd.DataFrame,
    actual: Union[str, List[str]] = None,
    metrics: List[str] = None
) -> Dict:
    """
    Evaluate the model on test data.
    
    Args:
        data: DataFrame containing test data
        actual: Column name(s) containing actual values
        metrics: List of metrics to compute
        
    Returns:
        Dictionary of evaluation metrics
    """
```

#### `evaluate_with_generator()`

Evaluates the model using a data generator.

```python
def evaluate_with_generator(
    data_generator: Any,
    steps: int,
    metrics: List[str] = None
) -> Dict:
    """
    Evaluate the model using a data generator.
    
    Args:
        data_generator: Generator that yields batches of data
        steps: Number of batches to evaluate
        metrics: List of metrics to compute
        
    Returns:
        Dictionary of evaluation metrics
    """
```

#### `plot_performance()`

Generates visualizations of model performance.

```python
def plot_performance(
    data: pd.DataFrame = None,
    actual: str = None,
    predicted: pd.DataFrame = None,
    metrics: List[str] = None,
    output_path: str = None
) -> None:
    """
    Generate visualizations of model performance.
    
    Args:
        data: DataFrame containing test data
        actual: Column name containing actual values
        predicted: DataFrame containing predicted values
        metrics: List of metrics to visualize
        output_path: Path to save visualizations
    """
```

## NeuralPredictor

The `NeuralPredictor` class handles generating predictions from trained models.

```python
from ktrdr.neural import NeuralPredictor
```

### Methods

#### `__init__()`

```python
def __init__(
    model: NeuralModel
):
    """
    Initialize a predictor for a neural network model.
    
    Args:
        model: The trained model for predictions
    """
```

#### `predict()`

Generates predictions from the model.

```python
def predict(
    data: pd.DataFrame,
    batch_size: int = 32
) -> Union[pd.DataFrame, pd.Series]:
    """
    Generate predictions using the model.
    
    Args:
        data: DataFrame containing input data
        batch_size: Batch size for prediction
        
    Returns:
        DataFrame or Series containing predictions
    """
```

#### `predict_proba()`

Generates probability predictions for classification models.

```python
def predict_proba(
    data: pd.DataFrame,
    batch_size: int = 32
) -> pd.DataFrame:
    """
    Generate probability predictions for classification models.
    
    Args:
        data: DataFrame containing input data
        batch_size: Batch size for prediction
        
    Returns:
        DataFrame containing class probabilities
    """
```

#### `get_signals()`

Converts predictions to trading signals.

```python
def get_signals(
    predictions: pd.DataFrame = None,
    threshold: float = 0.5,
    signal_type: str = "binary"
) -> pd.DataFrame:
    """
    Convert predictions to trading signals.
    
    Args:
        predictions: DataFrame containing predictions (uses last prediction if None)
        threshold: Threshold for generating signals
        signal_type: Type of signals to generate ("binary", "continuous", "categorical")
        
    Returns:
        DataFrame containing trading signals
    """
```

## ModelManager

The `ModelManager` class provides utilities for managing neural network models.

```python
from ktrdr.neural import ModelManager
```

### Methods

#### `list_models()`

Lists all available models.

```python
def list_models(
    filter_type: str = None
) -> List[str]:
    """
    List all available models.
    
    Args:
        filter_type: Filter models by type
        
    Returns:
        List of model names
    """
```

#### `load()`

Loads a model by name.

```python
def load(
    model_name: str
) -> NeuralModel:
    """
    Load a model by name.
    
    Args:
        model_name: Name or path of the model to load
        
    Returns:
        Loaded NeuralModel instance
    """
```

#### `delete()`

Deletes a model.

```python
def delete(
    model_name: str
) -> bool:
    """
    Delete a model.
    
    Args:
        model_name: Name of the model to delete
        
    Returns:
        True if deletion was successful
    """
```

#### `compare()`

Compares multiple models.

```python
def compare(
    model_names: List[str],
    data: pd.DataFrame = None,
    metric: str = "accuracy"
) -> Dict:
    """
    Compare multiple models.
    
    Args:
        model_names: List of model names to compare
        data: DataFrame containing test data
        metric: Metric to use for comparison
        
    Returns:
        Dictionary of comparison results
    """
```

#### `plot_comparison()`

Generates visualization of model comparison.

```python
def plot_comparison(
    comparison_results: Dict,
    output_path: str = None
) -> None:
    """
    Generate visualization of model comparison.
    
    Args:
        comparison_results: Results from compare() method
        output_path: Path to save visualization
    """
```

#### `export()`

Exports a model for deployment.

```python
def export(
    model_name: str,
    format: str = "onnx",
    destination: str = None
) -> str:
    """
    Export a model for deployment.
    
    Args:
        model_name: Name of the model to export
        format: Export format ("onnx", "tensorflow", "pytorch", "torchscript")
        destination: Directory to save exported model
        
    Returns:
        Path to exported model
    """
```

## HyperparameterOptimizer

The `HyperparameterOptimizer` class provides tools for finding optimal hyperparameters.

```python
from ktrdr.neural import HyperparameterOptimizer
```

### Methods

#### `__init__()`

```python
def __init__(
    model_type: str,
    param_space: Dict,
    max_trials: int = 10,
    objective: str = "val_loss",
    minimize: bool = True
):
    """
    Initialize a hyperparameter optimizer.
    
    Args:
        model_type: Type of model to optimize
        param_space: Dictionary defining parameter search space
        max_trials: Maximum number of optimization trials
        objective: Metric to optimize
        minimize: Whether to minimize (True) or maximize (False) the objective
    """
```

#### `optimize()`

Runs hyperparameter optimization.

```python
def optimize(
    train_data: pd.DataFrame,
    target: Union[str, List[str]],
    validation_split: float = 0.2,
    epochs: int = 50,
    batch_size: int = 32,
    verbose: int = 1
) -> Dict:
    """
    Run hyperparameter optimization.
    
    Args:
        train_data: DataFrame containing training data
        target: Target column(s) to predict
        validation_split: Fraction of data for validation
        epochs: Maximum epochs per trial
        batch_size: Batch size for training
        verbose: Verbosity level
        
    Returns:
        Dictionary of best hyperparameters
    """
```

#### `get_best_model()`

Creates a model with the best found hyperparameters.

```python
def get_best_model(
    input_features: List[str],
    output_features: List[str]
) -> NeuralModel:
    """
    Create a model with the best found hyperparameters.
    
    Args:
        input_features: List of input feature names
        output_features: List of output feature names
        
    Returns:
        NeuralModel with optimal hyperparameters
    """
```

## DataProcessor

The `DataProcessor` class prepares data for neural network training.

```python
from ktrdr.neural import DataProcessor
```

### Methods

#### `__init__()`

```python
def __init__(
    sequence_length: int = 10,
    normalize: bool = True,
    normalization_method: str = "minmax",
    target_encoding: str = "raw"
):
    """
    Initialize a data processor.
    
    Args:
        sequence_length: Length of input sequences for sequential models
        normalize: Whether to normalize input features
        normalization_method: Method for normalization ("minmax", "standard", "robust")
        target_encoding: Method for encoding target values ("raw", "binary", "categorical")
    """
```

#### `prepare_data()`

Prepares data for model training or inference.

```python
def prepare_data(
    data: pd.DataFrame,
    features: List[str],
    target: Union[str, List[str]] = None,
    for_training: bool = True,
    shuffle: bool = True
) -> Tuple:
    """
    Prepare data for model training or inference.
    
    Args:
        data: DataFrame containing data
        features: List of feature columns
        target: Target column(s) for prediction
        for_training: Whether data is for training (True) or inference (False)
        shuffle: Whether to shuffle training data
        
    Returns:
        Tuple of (X, y) arrays for training or X array for inference
    """
```

#### `create_sequences()`

Creates sequences from time series data.

```python
def create_sequences(
    data: pd.DataFrame,
    sequence_length: int = None
) -> np.ndarray:
    """
    Create sequences from time series data.
    
    Args:
        data: DataFrame containing time series data
        sequence_length: Length of sequences to create
        
    Returns:
        Array of sequences
    """
```

#### `train_test_split()`

Splits data into training and testing sets, respecting time order.

```python
def train_test_split(
    data: pd.DataFrame,
    test_size: float = 0.2,
    validation_size: float = 0.0
) -> Tuple:
    """
    Split data into training and testing sets.
    
    Args:
        data: DataFrame containing data
        test_size: Fraction of data for testing
        validation_size: Fraction of data for validation
        
    Returns:
        Tuple of DataFrames (train, test) or (train, validation, test)
    """
```

## Error Handling

The neural module provides custom exceptions for handling errors:

```python
# Model creation errors
from ktrdr.neural.errors import ModelCreationError

# Training errors
from ktrdr.neural.errors import TrainingError

# Data processing errors
from ktrdr.neural.errors import DataProcessingError

# Prediction errors
from ktrdr.neural.errors import PredictionError
```

## Constants

```python
from ktrdr.neural import constants

# Available model types
constants.MODEL_TYPES  # ["ffn", "lstm", "gru", "cnn", "hybrid"]

# Available optimizers
constants.OPTIMIZERS  # ["adam", "sgd", "rmsprop", "adagrad"]

# Available loss functions
constants.LOSS_FUNCTIONS  # ["mse", "mae", "binary_crossentropy", "categorical_crossentropy"]

# Available metrics
constants.METRICS  # ["accuracy", "precision", "recall", "f1", "mse", "mae"]

# Available activation functions
constants.ACTIVATIONS  # ["relu", "sigmoid", "tanh", "softmax", "linear"]
```