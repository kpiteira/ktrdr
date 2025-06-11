# Neural Network Training API Endpoints Specification

This document specifies the missing neural network training API endpoints that need to be implemented in the KTRDR backend to support autonomous strategy research through the MCP server.

## Overview

The MCP server currently expects these neural training endpoints to exist but they return 404 errors. The CLI training functionality works well and should be used as the implementation base for these endpoints.

## Required Endpoints

### 1. Start Neural Training
**POST /training/start**

Start a new neural network training session.

**Request Body:**
```json
{
  "symbol": "AAPL",
  "timeframe": "1h", 
  "config": {
    "model_type": "mlp",
    "hidden_layers": [64, 32, 16],
    "epochs": 100,
    "learning_rate": 0.001,
    "batch_size": 32,
    "validation_split": 0.2,
    "early_stopping": {
      "patience": 10,
      "monitor": "val_accuracy"
    },
    "optimizer": "adam",
    "dropout_rate": 0.2
  },
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "task_id": "optional-task-id"
}
```

**Response:**
```json
{
  "success": true,
  "task_id": "training_20250610_123456",
  "status": "training_started",
  "message": "Neural network training started",
  "symbol": "AAPL",
  "timeframe": "1h",
  "config": {...},
  "estimated_duration_minutes": 30
}
```

**Implementation:**
- Use existing CLI training code from `ktrdr.cli.training_commands`
- Leverage `ktrdr.training.model_trainer.ModelTrainer`
- Run training in background task (FastAPI BackgroundTasks)
- Store progress in database or file system

### 2. Get Training Status
**GET /training/{task_id}**

Get the current status and progress of a training task.

**Response:**
```json
{
  "success": true,
  "task_id": "training_20250610_123456",
  "status": "training", // "pending", "training", "completed", "failed"
  "progress": 65,
  "current_epoch": 65,
  "total_epochs": 100,
  "symbol": "AAPL",
  "timeframe": "1h",
  "started_at": "2025-06-10T12:34:56Z",
  "estimated_completion": "2025-06-10T13:04:56Z",
  "current_metrics": {
    "train_loss": 0.045,
    "val_loss": 0.052,
    "train_accuracy": 0.89,
    "val_accuracy": 0.87
  },
  "error": null
}
```

**Implementation:**
- Check training progress from model trainer state
- Read metrics from training logs or checkpoint files
- Return real-time status during training

### 3. Get Model Performance
**GET /training/{task_id}/performance**

Get detailed performance metrics for a completed training session.

**Response:**
```json
{
  "success": true,
  "task_id": "training_20250610_123456",
  "status": "completed",
  "training_metrics": {
    "final_train_loss": 0.032,
    "final_val_loss": 0.038,
    "final_train_accuracy": 0.92,
    "final_val_accuracy": 0.89,
    "epochs_completed": 87,
    "early_stopped": true,
    "training_time_minutes": 25.5
  },
  "test_metrics": {
    "test_loss": 0.041,
    "test_accuracy": 0.88,
    "precision": 0.87,
    "recall": 0.89,
    "f1_score": 0.88
  },
  "model_info": {
    "model_size_mb": 12.5,
    "parameters_count": 125430,
    "architecture": "mlp_64_32_16"
  }
}
```

**Implementation:**
- Read final metrics from completed training session
- Load test results from model evaluation
- Include model metadata and performance statistics

### 4. Save Trained Model
**POST /models/save**

Save a trained model for later use.

**Request Body:**
```json
{
  "task_id": "training_20250610_123456", 
  "model_name": "aapl_momentum_v1",
  "description": "AAPL momentum strategy trained on 2024 data"
}
```

**Response:**
```json
{
  "success": true,
  "model_id": "model_20250610_134567",
  "model_name": "aapl_momentum_v1",
  "model_path": "/models/aapl_momentum_v1",
  "task_id": "training_20250610_123456",
  "saved_at": "2025-06-10T13:45:67Z",
  "model_size_mb": 12.5
}
```

**Implementation:**
- Use existing `ModelStorage.save_model()` from `ktrdr.training.model_storage`
- Copy trained model files to permanent storage
- Update model registry with metadata

### 5. Load Trained Model
**POST /models/{model_name}/load**

Load a previously saved model into memory for prediction.

**Response:**
```json
{
  "success": true,
  "model_name": "aapl_momentum_v1",
  "model_loaded": true,
  "model_info": {
    "created_at": "2025-06-10T13:45:67Z",
    "symbol": "AAPL",
    "timeframe": "1h",
    "architecture": "mlp_64_32_16",
    "training_accuracy": 0.89,
    "test_accuracy": 0.88
  }
}
```

**Implementation:**
- Use existing `ModelLoader.load_model()` from `ktrdr.backtesting.model_loader`
- Load model weights and configuration
- Prepare model for prediction requests

### 6. Test Model Prediction
**POST /models/predict**

Test a loaded model's prediction on specific data.

**Request Body:**
```json
{
  "model_name": "aapl_momentum_v1",
  "symbol": "AAPL", 
  "timeframe": "1h",
  "test_date": "2025-06-09"
}
```

**Response:**
```json
{
  "success": true,
  "model_name": "aapl_momentum_v1",
  "symbol": "AAPL",
  "test_date": "2025-06-09",
  "prediction": {
    "signal": "buy", // "buy", "sell", "hold" 
    "confidence": 0.78,
    "signal_strength": 0.65,
    "fuzzy_outputs": {
      "bullish": 0.78,
      "bearish": 0.22,
      "neutral": 0.31
    }
  },
  "input_features": {
    "sma_20": 152.34,
    "rsi_14": 64.2,
    "macd_signal": 0.45
  }
}
```

**Implementation:**
- Use loaded model to generate prediction
- Apply fuzzy logic post-processing if configured
- Return prediction with confidence metrics

### 7. List Trained Models  
**GET /models**

List all available trained models.

**Response:**
```json
{
  "success": true,
  "models": [
    {
      "model_id": "model_20250610_134567",
      "model_name": "aapl_momentum_v1", 
      "symbol": "AAPL",
      "timeframe": "1h",
      "created_at": "2025-06-10T13:45:67Z",
      "training_accuracy": 0.89,
      "test_accuracy": 0.88,
      "description": "AAPL momentum strategy trained on 2024 data"
    }
  ]
}
```

**Implementation:**
- Use existing `ModelStorage.list_models()` 
- Return model metadata from storage registry
- Include performance metrics summary

## Implementation Guidelines

### Using Existing CLI Code

The implementation should reuse the working CLI training code:

1. **Import existing modules:**
   ```python
   from ktrdr.cli.training_commands import train_strategy
   from ktrdr.training.model_trainer import ModelTrainer
   from ktrdr.training.model_storage import ModelStorage
   from ktrdr.backtesting.model_loader import ModelLoader
   ```

2. **Wrap CLI functionality in API endpoints:**
   ```python
   async def start_training_endpoint(request):
       # Convert API request to CLI arguments
       cli_args = convert_request_to_cli_args(request)
       
       # Run training using existing CLI code
       result = await run_training_async(cli_args)
       
       # Convert CLI result to API response
       return format_api_response(result)
   ```

3. **Share storage and configuration:**
   - Use same model storage paths as CLI
   - Leverage existing configuration loading
   - Maintain compatibility with CLI-trained models

### FastAPI Implementation Structure

Create new file: `ktrdr/api/endpoints/training.py`

```python
from fastapi import APIRouter, BackgroundTasks, HTTPException
from ktrdr.api.services.training_service import TrainingService

router = APIRouter(prefix="/training")

@router.post("/start")
async def start_training(request: TrainingRequest, 
                        background_tasks: BackgroundTasks):
    # Implementation here
    pass

@router.get("/{task_id}")  
async def get_training_status(task_id: str):
    # Implementation here
    pass
```

### Background Task Management

- Use FastAPI BackgroundTasks for async training
- Store task status in database or file system
- Implement progress tracking and status updates
- Handle task cleanup and error recovery

### Database Schema

Add training task tracking to existing database:

```sql
CREATE TABLE training_tasks (
    task_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL, 
    config TEXT NOT NULL,
    status TEXT NOT NULL,
    progress INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    model_path TEXT
);
```

## Testing Strategy

1. **Unit tests for each endpoint**
2. **Integration tests with MCP server**
3. **End-to-end training workflow tests**
4. **Compatibility tests with existing CLI**

## Success Criteria

1. All MCP neural training tools work without 404 errors
2. Training tasks run successfully in background
3. Model performance metrics are accurate
4. Saved models are compatible with backtesting system
5. CLI and API share same model storage format