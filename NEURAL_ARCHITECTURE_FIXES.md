# Neural Network Architecture Issues - Future Fixes

## Root Problem Identified
Double-softmax bug exposed fundamental architectural issues where strategy configs control low-level PyTorch implementation details.

## Current Band-Aid Fix (2025-06-21)
- Removed softmax layer from MLP model (forces raw logits output)
- Fixed bollinger-squeeze-strategy.yaml config
- Added comments preventing future output_activation configs

## Deep Architectural Problems to Fix Later

### 1. Dangerous Configuration Coupling
**Problem**: Strategy YAML files control neural network implementation details
- `output_activation: "softmax"` in strategy configs
- Model and trainer separated but have hidden dependencies
- Strategy authors need PyTorch knowledge

**Solution**: Strategy configs should only control business logic:
```yaml
# GOOD - business decisions only
model:
  type: "mlp" 
  architecture:
    hidden_layers: [40, 20, 10]
    dropout: 0.25
  training:
    learning_rate: 0.0008

# BAD - technical implementation
model:
  architecture:
    output_activation: "softmax"  # Should be hardcoded based on task type
```

### 2. Violated Separation of Concerns
**Problem**: Model (mlp.py) and trainer (model_trainer.py) are loosely coupled but must work together
- Model outputs format must match loss function expectations
- Currently allows dangerous mismatches

**Solution**: Tight coupling for model+trainer, clean interfaces elsewhere
- ModelTrainer should own both model architecture AND loss function
- Classification models ALWAYS output raw logits (no configuration)
- Enforce PyTorch conventions strictly

### 3. Missing Contracts
**Problem**: Components assume things about each other without enforcement
- Inference code has to detect if softmax was applied
- No validation that model output matches expected format

**Solution**: Explicit contracts and validation
- Model.forward() output format is guaranteed
- Training/inference consistency checks
- Clear interfaces between components

## Implementation Plan (Future)
1. Create ModelTask enum (CLASSIFICATION, REGRESSION) 
2. ModelTrainer owns both model building AND loss selection based on task
3. Remove all output_activation configs from strategies
4. Add interface validation between components
5. Enforce PyTorch conventions throughout

## Current Status
- Immediate double-softmax bug fixed
- Model will now output raw logits
- Need to retrain and verify backtesting works
- Document this pattern to prevent regression