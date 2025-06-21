# Training Pipeline Architecture

## Overview

The KTRDR training pipeline is designed as an **indicator-agnostic orchestrator** that coordinates the complete neural network training process while maintaining strict separation of concerns. This document outlines the architectural principles, responsibilities, and data flow.

## Core Principle: Indicator Agnosticism

**The training pipeline MUST NOT contain any indicator calculations or mathematical transformations.**

All technical analysis calculations belong in dedicated indicator classes that are orchestrated by the training pipeline but not implemented within it.

## Architecture Diagram

```
Strategy Config → Training Pipeline → Trained Model
                      ↓
              ┌─────────────────┐
              │  Data Loading   │
              └─────────────────┘
                      ↓
              ┌─────────────────┐
              │ Indicator Engine│ ← Indicator Classes
              └─────────────────┘
                      ↓
              ┌─────────────────┐
              │  Fuzzy Engine   │ ← Fuzzy Logic Rules
              └─────────────────┘
                      ↓
              ┌─────────────────┐
              │Feature Engineer │ ← Scaling & Selection
              └─────────────────┘
                      ↓
              ┌─────────────────┐
              │Label Generation │ ← ZigZag Labeling
              └─────────────────┘
                      ↓
              ┌─────────────────┐
              │ Neural Training │ ← PyTorch Models
              └─────────────────┘
```

## Training Pipeline Responsibilities

### ✅ What Training Pipeline SHOULD Do:

1. **Configuration Management**
   - Load and validate strategy YAML files
   - Extract training parameters and model configuration
   - Validate required sections exist

2. **Data Orchestration**
   - Load price data using DataManager
   - Filter by date ranges
   - Validate data quality and completeness

3. **Indicator Engine Orchestration**
   - Initialize IndicatorEngine with strategy-declared indicators
   - Apply indicator calculations to price data
   - Handle indicator registration and configuration

4. **Fuzzy Engine Orchestration**
   - Initialize FuzzyEngine with fuzzy set configurations
   - Generate fuzzy membership values from indicators
   - Handle fuzzy rule processing

5. **Feature Engineering Coordination**
   - Initialize FeatureEngineer with feature configuration
   - Coordinate feature scaling and selection
   - Prepare final feature tensors for training

6. **Label Generation Coordination**
   - Initialize ZigZagLabeler with labeling configuration
   - Generate training labels from price data
   - Handle label distribution analysis

7. **Neural Network Training**
   - Create and configure neural network models
   - Execute training loops with progress tracking
   - Handle model evaluation and metrics collection

8. **Model Storage**
   - Save trained models with metadata
   - Store feature importance and training metrics
   - Handle model versioning and paths

### ❌ What Training Pipeline MUST NOT Do:

1. **Direct Indicator Calculations**
   ```python
   # ❌ WRONG - Don't calculate indicators in training
   rsi = ta.RSI(price_data["close"], period=14)
   bb_width = (bb_upper - bb_lower) / bb_middle
   ```

2. **Mathematical Transformations**
   ```python
   # ❌ WRONG - Don't transform indicator data
   volume_ratio = price_data["volume"] / volume_sma
   squeeze_intensity = calculate_squeeze(bb, kc)
   ```

3. **Hard-coded Derived Metrics**
   ```python
   # ❌ WRONG - Don't assume indicators exist
   mapped_results["bb_width"] = some_calculation()
   ```

4. **Indicator-Specific Logic**
   ```python
   # ❌ WRONG - Don't handle specific indicators
   if "bollinger_bands" in indicators:
       # Special handling
   ```

## Data Flow Architecture

### 1. Configuration Phase
```python
# Load strategy configuration
config = self._load_strategy_config(config_path)

# Extract components
indicators_config = config["indicators"]
fuzzy_config = config["fuzzy_sets"] 
model_config = config["model"]
training_config = config["training"]
```

### 2. Data Loading Phase
```python
# Load raw market data
price_data = self._load_price_data(symbol, timeframe, start_date, end_date)

# Data is passed unchanged to indicator engine
```

### 3. Indicator Calculation Phase
```python
# Initialize indicator engine with strategy configuration
self.indicator_engine = IndicatorEngine(indicators_config)

# Apply all configured indicators
indicator_results = self.indicator_engine.apply(price_data)

# Training pipeline receives calculated indicators
```

### 4. Fuzzy Processing Phase
```python
# Initialize fuzzy engine
self.fuzzy_engine = FuzzyEngine(fuzzy_config)

# Generate fuzzy memberships from indicators
fuzzy_data = self._generate_fuzzy_memberships(indicator_results, fuzzy_config)
```

### 5. Feature Engineering Phase
```python
# Prepare features for neural network
features, feature_names, scaler = self._engineer_features(
    fuzzy_data, indicator_results, price_data, feature_config
)
```

### 6. Training Phase
```python
# Generate labels and train model
labels = self._generate_labels(price_data, label_config)
model = self._train_model(model, train_data, val_data, training_config)
```

## Component Interaction Patterns

### 1. Strategy-Driven Processing

The training pipeline only processes what's declared in the strategy configuration:

```yaml
# Strategy declares requirements
indicators:
  - name: rsi
    type: RSI
    period: 14
  - name: bb_width
    type: BollingerBandWidth
    bb_period: 20
```

```python
# Training pipeline honors the declaration
for indicator_config in strategy_config["indicators"]:
    # Only these indicators will be calculated
    # No assumptions about other indicators
```

### 2. Error Propagation

Errors are caught and re-raised with context:

```python
try:
    indicators = self.indicator_engine.apply(price_data)
except DataError as e:
    raise DataError(
        f"Indicator calculation failed during training: {e.message}",
        error_code="TRAIN-IndicatorError",
        details={"strategy": strategy_name, "original_error": str(e)}
    )
```

### 3. Progress Tracking

Training pipeline provides progress callbacks to external systems:

```python
def train_strategy(self, ..., progress_callback=None):
    if progress_callback:
        progress_callback("Loading data...", 0)
    
    # ... data loading
    
    if progress_callback:
        progress_callback("Calculating indicators...", 20)
    
    # ... indicator calculation
```

## Validation and Safety

### 1. Configuration Validation

```python
def _load_strategy_config(self, config_path: str) -> Dict[str, Any]:
    """Load and validate strategy configuration."""
    
    # Required sections check
    required_sections = ["name", "indicators", "fuzzy_sets", "model", "training"]
    for section in required_sections:
        if section not in config:
            raise ConfigError(f"Missing required section: {section}")
    
    return config
```

### 2. Data Quality Validation

```python
def _validate_training_data(self, features: torch.Tensor, labels: torch.Tensor):
    """Validate data quality before training."""
    
    # Check for NaN values
    if torch.isnan(features).any():
        raise DataError("Features contain NaN values")
    
    # Check for infinite values  
    if torch.isinf(features).any():
        raise DataError("Features contain infinite values")
```

### 3. Component Availability

```python
def _ensure_components_available(self, config: Dict[str, Any]):
    """Ensure all required components are available."""
    
    # Validate indicator types exist
    for indicator_config in config["indicators"]:
        indicator_type = indicator_config["type"]
        if not self.indicator_engine.is_indicator_available(indicator_type):
            raise ConfigError(f"Unknown indicator type: {indicator_type}")
```

## Historical Context: June 21 Incident

### What Went Wrong

On June 21, 2025, commit `1efe5ab` introduced architectural violations:

```python
# ❌ WRONG - Added to training pipeline
mapped_results["bb_width"] = np.where(
    np.abs(middle_vals) > 1e-10,
    (upper_vals - lower_vals) / middle_vals,
    0.0
)

mapped_results["volume_ratio"] = np.where(
    np.abs(volume_sma_vals) > 1e-10,
    volume_vals / volume_sma_vals,
    1.0
)
```

### Root Cause

1. **Architectural Coupling**: Training pipeline directly calculated derived metrics
2. **Hard-coded Assumptions**: Assumed indicators existed regardless of strategy config
3. **Separation Violation**: Mathematical calculations in wrong layer

### Impact

- Training failures with "NaN loss on first batch"
- Strategy-agnostic principle violated  
- Tight coupling between training and indicator logic

### Resolution

1. **Extracted Calculations**: Moved to proper indicator classes
2. **Restored Agnosticism**: Training pipeline only processes declared indicators
3. **Architectural Documentation**: Created guidelines to prevent recurrence

## Best Practices

### 1. Configuration-First Design

Always start with strategy configuration:

```python
# ✅ Good - Honor configuration
strategy_indicators = config["indicators"]
self.indicator_engine = IndicatorEngine(strategy_indicators)

# ❌ Bad - Hard-code assumptions
self.indicator_engine = IndicatorEngine([
    {"type": "RSI", "period": 14},  # Assumes RSI needed
    {"type": "MACD", "fast": 12}    # Assumes MACD needed
])
```

### 2. Defensive Programming

Validate at each stage:

```python
# Check data exists before processing
if len(price_data) == 0:
    raise DataError("No price data available for training")

# Validate indicator results
if len(indicator_results.columns) == 0:
    raise DataError("No indicators calculated - check strategy configuration")
```

### 3. Clear Error Messages

Provide actionable error context:

```python
raise DataError(
    f"Training failed: insufficient data for {symbol} {timeframe}",
    error_code="TRAIN-InsufficientData",
    details={
        "symbol": symbol,
        "timeframe": timeframe,
        "required_bars": min_required,
        "available_bars": len(price_data),
        "suggestion": "Extend date range or use different symbol"
    }
)
```

### 4. Modular Testing

Test each responsibility separately:

```python
def test_indicator_orchestration():
    """Test that training pipeline correctly orchestrates indicator engine."""
    # Mock indicator engine
    # Verify correct configuration passed
    # Check results are used properly

def test_data_validation():
    """Test that training pipeline validates data quality."""
    # Test with NaN data
    # Test with insufficient data
    # Verify appropriate errors raised
```

## Integration Points

### 1. API Integration

Training pipeline integrates with API for async operations:

```python
# API starts training asynchronously
operation_id = await training_api.start_training(
    strategy_config=config,
    symbol=symbol,
    timeframe=timeframe,
    progress_callback=api_progress_callback
)
```

### 2. CLI Integration

CLI provides synchronous interface:

```python
# CLI runs training with user feedback
result = trainer.train_strategy(
    strategy_config_path="strategy.yaml",
    symbol="AAPL",
    timeframe="1h",
    progress_callback=cli_progress_callback
)
```

### 3. Model Storage Integration

Training pipeline saves complete model packages:

```python
model_path = self.model_storage.save_model(
    model=trained_model,
    strategy_name=strategy_name,
    symbol=symbol,
    timeframe=timeframe,
    config=complete_config,
    training_metrics=results,
    feature_names=feature_names,
    scaler=feature_scaler
)
```

## Monitoring and Debugging

### 1. Progress Tracking

```python
# Report progress at each major stage
progress_callback("Loading market data...", 10)
progress_callback("Calculating indicators...", 30) 
progress_callback("Generating fuzzy memberships...", 50)
progress_callback("Training neural network...", 70)
progress_callback("Evaluating model...", 90)
progress_callback("Saving model...", 100)
```

### 2. Metrics Collection

```python
# Collect timing and quality metrics
training_metrics = {
    "data_loading_time": data_time,
    "indicator_calculation_time": indicator_time,
    "training_time": train_time,
    "final_accuracy": accuracy,
    "feature_count": len(feature_names),
    "label_distribution": label_stats
}
```

### 3. Debug Information

```python
# Provide debug context for troubleshooting
logger.debug(
    "Training pipeline state",
    extra={
        "strategy": strategy_name,
        "indicators_calculated": len(indicator_results.columns),
        "fuzzy_features": len(fuzzy_data.columns),
        "final_features": features.shape[1],
        "training_samples": len(train_data[0])
    }
)
```

## Future Considerations

### 1. Multi-Timeframe Support

Training pipeline can be extended for multi-timeframe strategies:

```python
# Load data for multiple timeframes
price_data_1h = self._load_price_data(symbol, "1h", start, end)
price_data_4h = self._load_price_data(symbol, "4h", start, end)

# Apply indicators to each timeframe
indicators_1h = self.indicator_engine.apply(price_data_1h)
indicators_4h = self.indicator_engine.apply(price_data_4h)
```

### 2. Distributed Training

Training pipeline can be adapted for distributed training:

```python
# Partition data across workers
train_partitions = self._partition_data(train_data, num_workers)

# Coordinate distributed training
model = self._train_distributed(model, train_partitions)
```

### 3. Model Ensemble

Training pipeline can support ensemble methods:

```python
# Train multiple models
models = []
for config in ensemble_configs:
    model = self._train_single_model(config, train_data)
    models.append(model)

# Create ensemble
ensemble_model = self._create_ensemble(models)
```

## Conclusion

The training pipeline serves as a clean orchestrator that coordinates complex machine learning workflows while maintaining strict architectural boundaries. By adhering to the indicator-agnostic principle and proper separation of concerns, the training pipeline remains maintainable, testable, and extensible.

Key takeaways:
- **Orchestrate, don't calculate** - Training pipeline coordinates but doesn't implement
- **Honor configuration** - Only process what's declared in strategy files
- **Validate extensively** - Check data quality and component availability
- **Fail fast** - Provide clear error messages with actionable context
- **Maintain separation** - Keep mathematical calculations in indicator classes

This architecture ensures robust, reliable neural network training while preventing architectural violations like the June 21 incident.