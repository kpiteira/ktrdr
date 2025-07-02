# Training Analytics Implementation Plan - KTRDR

**Version**: 1.0  
**Date**: December 2024  
**Status**: READY FOR DEVELOPMENT  
**Related Documents**: 
- [Requirements Plan](training-analytics-plan.md)
- [Multi-Symbol Design](multi-symbol-design.md)

---

## 🎯 **Implementation Objective**

Implement comprehensive training analytics with **LLM-friendly CSV export** and **JSON backup** to understand why neural network training stops early (3-13 epochs). Focus on actionable data collection with built-in alerts for immediate insights.

---

## 📊 **1. Data Export Architecture**

### 1.1 Primary Export: LLM-Friendly CSV

**File**: `training_analytics/runs/{run_id}/metrics.csv`

**Schema** (1 row per epoch):
```csv
epoch,train_loss,val_loss,train_acc,val_acc,learning_rate,
gradient_norm_avg,gradient_norm_max,param_change_magnitude,
buy_precision,hold_precision,sell_precision,
buy_recall,hold_recall,sell_recall,
prediction_confidence_avg,prediction_entropy,
learning_signal_strength,early_stopping_triggered,
overfitting_score,class_balance_score,batch_count,
total_samples_processed,epoch_duration_seconds
```

**Estimated Size**: 50 epochs × 23 columns = ~8KB (perfect for LLM context)

### 1.2 Backup Export: Detailed JSON

**File**: `training_analytics/runs/{run_id}/detailed_metrics.json`

**Structure**:
```json
{
  "run_metadata": {
    "run_id": "single_symbol_debug_001",
    "symbol": "EURUSD",
    "strategy": "neuro_mean_reversion", 
    "start_time": "2024-12-XX 10:30:00",
    "end_time": "2024-12-XX 10:45:00",
    "total_epochs": 13,
    "stopping_reason": "early_stopping_triggered",
    "config_hash": "abc123..."
  },
  "training_config": {
    "learning_rate": 0.001,
    "batch_size": 32,
    "architecture": [50, 25, 12],
    "early_stopping_patience": 15,
    "optimizer": "adam"
  },
  "epoch_metrics": [
    {
      "epoch": 1,
      "train_loss": 1.045,
      "val_loss": 1.089,
      "train_accuracy": 0.334,
      "val_accuracy": 0.329,
      "learning_rate": 0.001,
      "gradient_norms": {
        "average": 0.45,
        "maximum": 1.23,
        "by_layer": {"layer_1": 0.34, "layer_2": 0.56, "output": 0.67}
      },
      "parameter_stats": {
        "total_change_magnitude": 0.023,
        "by_layer": {
          "layer_1": {"mean_change": 0.002, "std_change": 0.45},
          "layer_2": {"mean_change": -0.001, "std_change": 0.33}
        }
      },
      "class_metrics": {
        "BUY": {"precision": 0.31, "recall": 0.45, "f1": 0.36, "support": 1205},
        "HOLD": {"precision": 0.28, "recall": 0.12, "f1": 0.17, "support": 2341},
        "SELL": {"precision": 0.41, "recall": 0.67, "f1": 0.51, "support": 1189}
      },
      "prediction_stats": {
        "mean_confidence": 0.45,
        "confidence_distribution": [0.12, 0.23, 0.34, 0.21, 0.10],
        "prediction_entropy": 0.89,
        "high_confidence_predictions": 0.23
      },
      "learning_indicators": {
        "signal_strength": "strong",
        "overfitting_score": 0.12,
        "class_balance_score": 0.85,
        "convergence_indicator": "improving"
      },
      "timing": {
        "epoch_duration": 12.4,
        "batch_count": 156,
        "samples_processed": 4992
      }
    }
  ],
  "alerts": [
    {
      "epoch": 3,
      "severity": "warning", 
      "category": "gradient_flow",
      "message": "Gradient norms dropped significantly - possible vanishing gradients",
      "details": {"prev_norm": 0.45, "current_norm": 0.08, "drop_ratio": 0.18}
    }
  ],
  "final_analysis": {
    "total_epochs_completed": 13,
    "best_val_accuracy": 0.487,
    "best_epoch": 8,
    "stopping_trigger": "early_stopping_patience_exceeded",
    "final_gradient_norm": 0.023,
    "learning_progression": "plateau_after_epoch_5"
  }
}
```

### 1.3 Built-in Alerts System

**File**: `training_analytics/runs/{run_id}/alerts.txt`

**Alert Categories**:
```python
ALERT_PATTERNS = {
    'vanishing_gradients': {
        'condition': 'gradient_norm_avg < 0.01 and epoch > 5',
        'message': '⚠️ Vanishing gradients detected - learning may have stopped',
        'severity': 'warning'
    },
    'exploding_gradients': {
        'condition': 'gradient_norm_max > 10.0',
        'message': '🚨 Exploding gradients - reduce learning rate immediately', 
        'severity': 'critical'
    },
    'severe_overfitting': {
        'condition': 'val_loss > train_loss + 0.3',
        'message': '🚨 Severe overfitting - validation much worse than training',
        'severity': 'critical'
    },
    'learning_plateau': {
        'condition': 'learning_signal_strength == "weak" for 5+ consecutive epochs',
        'message': '📉 Learning plateau detected - consider reducing learning rate',
        'severity': 'warning'
    },
    'class_imbalance': {
        'condition': 'class_balance_score < 0.5',
        'message': '⚖️ Severe class imbalance affecting learning',
        'severity': 'warning'
    },
    'poor_convergence': {
        'condition': 'val_accuracy < 0.4 and epoch > 10',
        'message': '📊 Poor accuracy after 10 epochs - check architecture or features',
        'severity': 'warning'
    }
}
```

---

## 🏗️ **2. Code Architecture & Integration**

### 2.1 File Structure
```
ktrdr/training/
├── model_trainer.py          # MODIFY: Enhanced metrics collection
├── training_analyzer.py      # NEW: Analytics collection and export
├── training_alerts.py        # NEW: Built-in alert system
└── analytics/                # NEW: Analytics utilities
    ├── __init__.py
    ├── csv_exporter.py        # CSV export functionality
    ├── json_exporter.py       # JSON export functionality
    └── metrics_collector.py   # Core metrics collection

training_analytics/           # NEW: Analytics data storage
├── runs/
│   └── {run_id}/
│       ├── metrics.csv
│       ├── detailed_metrics.json
│       ├── config.yaml
│       └── alerts.txt
└── experiments/
    └── {experiment_name}/
        ├── run_1/, run_2/, run_3/
        └── summary.csv
```

### 2.2 Core Classes Design

#### 2.2.1 Enhanced TrainingMetrics
```python
@dataclass
class DetailedTrainingMetrics:
    """Extended training metrics for comprehensive analysis."""
    
    # Basic metrics (existing)
    epoch: int
    train_loss: float
    train_accuracy: float
    val_loss: Optional[float] = None
    val_accuracy: Optional[float] = None
    learning_rate: float = 0.001
    duration: float = 0.0
    
    # New gradient metrics
    gradient_norm_avg: float = 0.0
    gradient_norm_max: float = 0.0
    gradient_norms_by_layer: Dict[str, float] = field(default_factory=dict)
    
    # New parameter metrics
    param_change_magnitude: float = 0.0
    param_stats_by_layer: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # New class-wise metrics
    class_precisions: Dict[str, float] = field(default_factory=dict)
    class_recalls: Dict[str, float] = field(default_factory=dict)
    class_f1_scores: Dict[str, float] = field(default_factory=dict)
    class_supports: Dict[str, int] = field(default_factory=dict)
    
    # New prediction metrics
    prediction_confidence_avg: float = 0.0
    prediction_entropy: float = 0.0
    high_confidence_predictions: float = 0.0
    confidence_distribution: List[float] = field(default_factory=list)
    
    # New learning indicators
    learning_signal_strength: str = "unknown"  # strong, medium, weak
    overfitting_score: float = 0.0
    class_balance_score: float = 0.0
    convergence_indicator: str = "unknown"  # improving, plateauing, diverging
    
    # New timing metrics
    batch_count: int = 0
    total_samples_processed: int = 0
    early_stopping_triggered: bool = False
```

#### 2.2.2 TrainingAnalyzer Class
```python
class TrainingAnalyzer:
    """Main analytics collection and export system."""
    
    def __init__(self, run_id: str, output_dir: Path, config: Dict[str, Any]):
        self.run_id = run_id
        self.output_dir = output_dir
        self.config = config
        self.metrics_history: List[DetailedTrainingMetrics] = []
        self.alerts: List[Dict[str, Any]] = []
        self.previous_params: Optional[Dict[str, torch.Tensor]] = None
        
    def collect_epoch_metrics(
        self, 
        epoch: int,
        model: nn.Module,
        train_metrics: Dict[str, float],
        val_metrics: Dict[str, float],
        optimizer: torch.optim.Optimizer,
        y_pred: torch.Tensor,
        y_true: torch.Tensor
    ) -> DetailedTrainingMetrics:
        """Collect comprehensive metrics for one epoch."""
        
    def export_csv(self) -> Path:
        """Export LLM-friendly CSV file."""
        
    def export_json(self) -> Path:
        """Export detailed JSON file."""
        
    def export_alerts(self) -> Path:
        """Export human-readable alerts."""
        
    def check_alerts(self, metrics: DetailedTrainingMetrics) -> List[Dict[str, Any]]:
        """Check for training issues and generate alerts."""
```

### 2.3 ModelTrainer Integration

#### 2.3.1 Configuration Integration
```yaml
# strategies/neuro_mean_reversion.yaml
model:
  training:
    # ... existing config ...
    analytics:
      enabled: false  # Default off
      export_csv: true
      export_json: true
      export_alerts: true
      batch_sampling_rate: 10  # Sample every 10th batch for batch-level metrics
```

#### 2.3.2 ModelTrainer Modifications
```python
class ModelTrainer:
    def __init__(self, config: Dict[str, Any], progress_callback=None):
        # ... existing init ...
        
        # Analytics setup
        self.analytics_enabled = config.get("analytics", {}).get("enabled", False)
        if self.analytics_enabled:
            run_id = f"{config.get('symbol', 'unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            analytics_dir = Path("training_analytics/runs") / run_id
            analytics_dir.mkdir(parents=True, exist_ok=True)
            self.analyzer = TrainingAnalyzer(run_id, analytics_dir, config)
        else:
            self.analyzer = None
    
    def train(self, model, X_train, y_train, X_val=None, y_val=None):
        # ... existing training loop ...
        
        for epoch in range(epochs):
            # ... existing training code ...
            
            # Analytics collection (new)
            if self.analyzer:
                detailed_metrics = self.analyzer.collect_epoch_metrics(
                    epoch=epoch,
                    model=model,
                    train_metrics={"loss": avg_train_loss, "accuracy": train_accuracy},
                    val_metrics={"loss": val_loss, "accuracy": val_accuracy},
                    optimizer=optimizer,
                    y_pred=val_predicted if X_val is not None else train_predicted,
                    y_true=y_val if X_val is not None else y_train
                )
                
                # Check for alerts
                alerts = self.analyzer.check_alerts(detailed_metrics)
                if alerts:
                    for alert in alerts:
                        logger.warning(f"Training Alert: {alert['message']}")
        
        # Export analytics at end of training
        if self.analyzer:
            csv_path = self.analyzer.export_csv()
            json_path = self.analyzer.export_json()
            alerts_path = self.analyzer.export_alerts()
            logger.info(f"Analytics exported: CSV={csv_path}, JSON={json_path}")
            
            return {
                **existing_return_dict,
                "analytics": {
                    "csv_path": str(csv_path),
                    "json_path": str(json_path),
                    "alerts_path": str(alerts_path)
                }
            }
```

### 2.4 CLI Integration

#### 2.4.1 Training Commands Enhancement
```python
# ktrdr/cli/training_commands.py

@click.command()
@click.option("--symbol", required=True)
@click.option("--strategy", required=True)
@click.option("--detailed-analytics", is_flag=True, default=False, 
              help="Enable detailed training analytics with CSV/JSON export")
def train(symbol: str, strategy: str, detailed_analytics: bool):
    """Train neural network with optional detailed analytics."""
    
    # Load strategy config
    config = load_strategy_config(strategy)
    
    # Override analytics setting from CLI
    if detailed_analytics:
        if "model" not in config:
            config["model"] = {}
        if "training" not in config["model"]:
            config["model"]["training"] = {}
        if "analytics" not in config["model"]["training"]:
            config["model"]["training"]["analytics"] = {}
        
        config["model"]["training"]["analytics"]["enabled"] = True
        print("🔍 Detailed analytics enabled - will export CSV and JSON")
    
    # ... rest of training logic ...
```

### 2.5 API Integration

#### 2.5.1 Training Service Enhancement
```python
# ktrdr/api/services/training_service.py

async def start_training(
    self,
    symbol: str,
    timeframe: str, 
    strategy_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    detailed_analytics: bool = False,  # New parameter
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Start neural network training with optional analytics."""
    
    # ... existing validation ...
    
    # Override analytics in config if requested
    if detailed_analytics:
        training_config["analytics"] = {
            "enabled": True,
            "export_csv": True,
            "export_json": True,
            "export_alerts": True
        }
    
    # ... rest of training logic ...
```

#### 2.5.2 API Endpoint Enhancement
```python
# ktrdr/api/endpoints/training.py

@router.post("/training/start", response_model=StartTrainingResponse)
async def start_training_endpoint(
    request: StartTrainingRequest,
    detailed_analytics: bool = Query(False, description="Enable detailed training analytics"),
    training_service: TrainingService = Depends(get_training_service)
):
    """Start neural network training with optional detailed analytics."""
    
    result = await training_service.start_training(
        symbol=request.symbol,
        timeframe=request.timeframe,
        strategy_name=request.strategy_name,
        start_date=request.start_date,
        end_date=request.end_date,
        detailed_analytics=detailed_analytics  # Pass through
    )
    
    return StartTrainingResponse(**result)
```

---

## 🧪 **3. Systematic Testing Framework**

### 3.1 Experiment Runner Implementation

#### 3.1.1 ExperimentRunner Class
```python
class ExperimentRunner:
    """Automated experiment execution for systematic parameter testing."""
    
    def __init__(self, base_config: Dict[str, Any], output_dir: Path):
        self.base_config = base_config
        self.output_dir = output_dir
        self.results: List[Dict[str, Any]] = []
    
    def run_learning_rate_experiment(
        self, 
        lr_values: List[float] = [0.01, 0.001, 0.0001, 0.00001],
        seeds: List[int] = [42, 123, 456]
    ) -> Path:
        """Run systematic learning rate experiments."""
        
        experiment_dir = self.output_dir / "lr_experiment"
        experiment_dir.mkdir(exist_ok=True)
        
        for lr in lr_values:
            for seed in seeds:
                run_id = f"lr_{lr}_seed_{seed}"
                print(f"🧪 Running experiment: {run_id}")
                
                # Modify config
                config = self.base_config.copy()
                config["model"]["training"]["learning_rate"] = lr
                config["random_seed"] = seed
                config["model"]["training"]["analytics"]["enabled"] = True
                
                # Run training
                try:
                    result = self._run_single_training(config, run_id, experiment_dir)
                    self.results.append({
                        "experiment_type": "learning_rate",
                        "learning_rate": lr,
                        "seed": seed,
                        "run_id": run_id,
                        **result
                    })
                except Exception as e:
                    logger.error(f"Experiment {run_id} failed: {e}")
                    self.results.append({
                        "experiment_type": "learning_rate", 
                        "learning_rate": lr,
                        "seed": seed,
                        "run_id": run_id,
                        "status": "failed",
                        "error": str(e)
                    })
        
        # Export experiment summary
        summary_path = experiment_dir / "summary.csv"
        pd.DataFrame(self.results).to_csv(summary_path, index=False)
        return summary_path
    
    def run_patience_experiment(
        self,
        patience_values: List[int] = [10, 20, 30, 50],
        seeds: List[int] = [42, 123, 456]
    ) -> Path:
        """Run early stopping patience experiments."""
        # Similar structure to learning rate experiment
        
    def run_architecture_experiment(
        self,
        architectures: List[List[int]] = [[32, 16], [64, 32, 16], [128, 64, 32], [256, 128, 64]],
        seeds: List[int] = [42, 123, 456]
    ) -> Path:
        """Run model architecture experiments."""
        # Similar structure to learning rate experiment
```

### 3.2 LLM Analysis Integration

#### 3.2.1 LLM Prompt Templates
```python
LLM_ANALYSIS_PROMPTS = {
    "single_run_analysis": """
Analyze this neural network training run that stopped early. The CSV shows metrics for each epoch.

CONTEXT:
- This is a 3-class classification problem (BUY/HOLD/SELL)
- Model uses fuzzy logic features as input
- Training stopped at epoch {final_epoch} (max was {max_epochs})
- Random accuracy would be ~33%

CSV DATA:
{csv_content}

QUESTIONS:
1. Why did training stop early?
2. Was the model learning effectively?
3. What specific changes would improve training?
4. Rate the overall training quality (Poor/Fair/Good/Excellent)

Focus on actionable insights, not just descriptions of the data.
""",
    
    "experiment_comparison": """
Compare these training experiments to determine optimal hyperparameters.

EXPERIMENT: {experiment_type}
SUMMARY DATA:
{summary_csv}

For each configuration, I need:
1. Average epochs reached
2. Average final accuracy  
3. Training stability (consistent across seeds?)
4. Overall ranking (best to worst)

Recommend the optimal {experiment_type} value and explain why.
""",
    
    "failure_diagnosis": """
This training run failed or performed very poorly. Help diagnose the issue.

TRAINING DATA:
{csv_content}

FAILURE SYMPTOMS:
- Final accuracy: {final_accuracy}
- Epochs completed: {epochs_completed}
- Alerts generated: {alerts}

What went wrong and how to fix it?
"""
}
```

#### 3.2.2 LLM Analysis Helper
```python
class LLMAnalysisHelper:
    """Helper for generating LLM-ready analysis prompts."""
    
    @staticmethod
    def prepare_single_run_analysis(csv_path: Path, config: Dict[str, Any]) -> str:
        """Prepare prompt for analyzing a single training run."""
        
        df = pd.read_csv(csv_path)
        csv_content = df.to_string(index=False)
        
        return LLM_ANALYSIS_PROMPTS["single_run_analysis"].format(
            final_epoch=len(df),
            max_epochs=config.get("epochs", 100),
            csv_content=csv_content
        )
    
    @staticmethod
    def prepare_experiment_comparison(summary_csv_path: Path, experiment_type: str) -> str:
        """Prepare prompt for comparing experimental results."""
        
        df = pd.read_csv(summary_csv_path)
        summary_content = df.to_string(index=False)
        
        return LLM_ANALYSIS_PROMPTS["experiment_comparison"].format(
            experiment_type=experiment_type,
            summary_csv=summary_content
        )
```

---

## 🚀 **4. Implementation Schedule**

### 4.1 Week 1: Core Analytics Infrastructure

**Days 1-2: Metrics Collection**
- [ ] Create `DetailedTrainingMetrics` dataclass
- [ ] Implement `TrainingAnalyzer` class with core metric collection
- [ ] Add gradient norm calculation using `torch.nn.utils.clip_grad_norm_`
- [ ] Add parameter change tracking between epochs
- [ ] Implement class-wise metrics using sklearn

**Days 3-4: Export System**
- [ ] Implement CSV export with LLM-friendly schema
- [ ] Implement JSON export for detailed backup
- [ ] Create alerts system with pattern detection
- [ ] Add file structure and directory management

**Days 5-7: ModelTrainer Integration**
- [ ] Modify `ModelTrainer` to integrate `TrainingAnalyzer`
- [ ] Add configuration options for analytics
- [ ] Test with small dataset (1000 samples, 10 epochs)
- [ ] Verify CSV and JSON exports work correctly

### 4.2 Week 2: CLI/API Integration & Testing

**Days 1-2: CLI Integration**
- [ ] Add `--detailed-analytics` flag to training commands
- [ ] Update help text and documentation
- [ ] Test CLI integration with analytics

**Days 3-4: API Integration**
- [ ] Add `detailed_analytics` parameter to training endpoints
- [ ] Update API documentation and response models
- [ ] Test API integration with analytics

**Days 5-7: System Validation**
- [ ] Run full training with analytics on EURUSD
- [ ] Validate metric accuracy and completeness
- [ ] Test alert system with known problematic configs
- [ ] Performance testing (ensure <20% slowdown)

### 4.3 Week 3: Systematic Experiments

**Days 1-2: Experiment Framework**
- [ ] Implement `ExperimentRunner` class
- [ ] Create experiment configuration management
- [ ] Test with small-scale experiments

**Days 3-4: Learning Rate Experiments**
- [ ] Run learning rate grid: [0.01, 0.001, 0.0001, 0.00001]
- [ ] 3 seeds per configuration = 12 total runs
- [ ] Export experiment summary CSV

**Days 5-7: Additional Experiments**
- [ ] Early stopping patience experiments
- [ ] Model architecture experiments
- [ ] Generate LLM analysis prompts for results

### 4.4 Week 4: Analysis & Optimization

**Days 1-3: Results Analysis**
- [ ] Manual analysis of experiment results
- [ ] LLM-assisted analysis using generated prompts
- [ ] Identify optimal hyperparameters

**Days 4-5: Configuration Optimization**
- [ ] Update strategy configs with optimal parameters
- [ ] Validate improved configurations
- [ ] Document findings and recommendations

**Days 6-7: Documentation & Finalization**
- [ ] Update documentation with analytics usage
- [ ] Create user guide for interpreting results
- [ ] Prepare for multi-symbol training phase

---

## 📋 **5. Technical Implementation Details**

### 5.1 Key Metrics Calculation Methods

#### 5.1.1 Gradient Norms
```python
def calculate_gradient_norms(model: nn.Module) -> Dict[str, float]:
    """Calculate gradient norms by layer and overall."""
    
    total_norm = 0.0
    layer_norms = {}
    
    for name, param in model.named_parameters():
        if param.grad is not None:
            param_norm = param.grad.data.norm(2)
            total_norm += param_norm.item() ** 2
            layer_norms[name] = param_norm.item()
    
    total_norm = total_norm ** (1. / 2)
    
    return {
        "total": total_norm,
        "average": total_norm / len(layer_norms) if layer_norms else 0.0,
        "maximum": max(layer_norms.values()) if layer_norms else 0.0,
        "by_layer": layer_norms
    }
```

#### 5.1.2 Parameter Change Tracking
```python
def calculate_parameter_changes(
    current_params: Dict[str, torch.Tensor],
    previous_params: Dict[str, torch.Tensor]
) -> Dict[str, float]:
    """Calculate magnitude of parameter changes between epochs."""
    
    if previous_params is None:
        return {"total_magnitude": 0.0, "by_layer": {}}
    
    total_change = 0.0
    layer_changes = {}
    
    for name, current in current_params.items():
        if name in previous_params:
            change = (current - previous_params[name]).norm().item()
            total_change += change ** 2
            layer_changes[name] = change
    
    return {
        "total_magnitude": total_change ** 0.5,
        "by_layer": layer_changes
    }
```

#### 5.1.3 Learning Signal Strength
```python
def calculate_learning_signal_strength(
    current_metrics: DetailedTrainingMetrics,
    previous_metrics: Optional[DetailedTrainingMetrics]
) -> str:
    """Determine learning signal strength based on multiple indicators."""
    
    if previous_metrics is None:
        return "unknown"
    
    # Check loss improvement
    loss_improvement = previous_metrics.train_loss - current_metrics.train_loss
    relative_improvement = loss_improvement / previous_metrics.train_loss
    
    # Check gradient magnitude
    gradient_strength = current_metrics.gradient_norm_avg
    
    # Check parameter change magnitude
    param_change_strength = current_metrics.param_change_magnitude
    
    # Scoring logic
    score = 0
    if relative_improvement > 0.05:  # >5% loss improvement
        score += 2
    elif relative_improvement > 0.01:  # >1% loss improvement
        score += 1
    
    if gradient_strength > 0.1:
        score += 2
    elif gradient_strength > 0.01:
        score += 1
    
    if param_change_strength > 0.01:
        score += 1
    
    # Classify strength
    if score >= 4:
        return "strong"
    elif score >= 2:
        return "medium"
    else:
        return "weak"
```

#### 5.1.4 Class-wise Metrics
```python
def calculate_class_metrics(y_true: torch.Tensor, y_pred: torch.Tensor) -> Dict[str, Dict[str, float]]:
    """Calculate precision, recall, F1 for each class."""
    
    from sklearn.metrics import precision_recall_fscore_support, classification_report
    
    # Convert to numpy
    y_true_np = y_true.cpu().numpy()
    y_pred_np = y_pred.cpu().numpy()
    
    # Calculate metrics
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true_np, y_pred_np, average=None, zero_division=0
    )
    
    class_names = ["BUY", "HOLD", "SELL"]
    class_metrics = {}
    
    for i, class_name in enumerate(class_names):
        class_metrics[class_name] = {
            "precision": float(precision[i]) if i < len(precision) else 0.0,
            "recall": float(recall[i]) if i < len(recall) else 0.0,
            "f1": float(f1[i]) if i < len(f1) else 0.0,
            "support": int(support[i]) if i < len(support) else 0
        }
    
    return class_metrics
```

### 5.2 Error Handling & Edge Cases

#### 5.2.1 Graceful Degradation
```python
class TrainingAnalyzer:
    def collect_epoch_metrics(self, **kwargs) -> DetailedTrainingMetrics:
        """Collect metrics with graceful error handling."""
        
        try:
            # Attempt full metrics collection
            return self._collect_all_metrics(**kwargs)
        except Exception as e:
            logger.warning(f"Full metrics collection failed: {e}")
            try:
                # Fallback to basic metrics
                return self._collect_basic_metrics(**kwargs)
            except Exception as e2:
                logger.error(f"Basic metrics collection failed: {e2}")
                # Return minimal metrics to keep training running
                return DetailedTrainingMetrics(
                    epoch=kwargs.get('epoch', 0),
                    train_loss=kwargs.get('train_metrics', {}).get('loss', 0.0),
                    train_accuracy=kwargs.get('train_metrics', {}).get('accuracy', 0.0)
                )
```

#### 5.2.2 Resource Management
```python
def cleanup_old_analytics(max_runs: int = 100):
    """Clean up old analytics files to prevent disk space issues."""
    
    analytics_dir = Path("training_analytics/runs")
    if not analytics_dir.exists():
        return
    
    # Get all run directories sorted by creation time
    run_dirs = sorted(
        [d for d in analytics_dir.iterdir() if d.is_dir()],
        key=lambda x: x.stat().st_ctime,
        reverse=True
    )
    
    # Remove old runs beyond limit
    for old_dir in run_dirs[max_runs:]:
        shutil.rmtree(old_dir)
        logger.info(f"Cleaned up old analytics: {old_dir.name}")
```

---

## ✅ **6. Success Criteria & Validation**

### 6.1 Implementation Success Metrics

**Technical Validation:**
- [ ] Analytics collection adds <20% training time overhead
- [ ] CSV exports are <50KB and LLM-readable
- [ ] JSON exports preserve all collected data
- [ ] Alerts correctly identify known issues (test with high LR)
- [ ] System handles training failures gracefully

**Functional Validation:**
- [ ] Can identify why training stops early in known scenarios
- [ ] LLM analysis provides actionable recommendations
- [ ] Systematic experiments complete successfully
- [ ] Results lead to improved training configurations

### 6.2 User Acceptance Criteria

**Ease of Use:**
- [ ] Single CLI flag enables analytics (`--detailed-analytics`)
- [ ] API parameter works correctly
- [ ] CSV files open correctly in Excel/Google Sheets
- [ ] Alerts are clear and actionable

**Value Delivery:**
- [ ] Answers "why does training stop early?"
- [ ] Provides concrete hyperparameter recommendations
- [ ] Enables data-driven training optimization
- [ ] Supports transition to multi-symbol training

---

## 🔄 **7. Next Phase Integration**

Upon completion of this implementation:

1. **Immediate Benefits**: Understanding of single-symbol training behavior
2. **Multi-Symbol Preparation**: Validated hyperparameters for scaling experiments  
3. **Ongoing Analytics**: Continuous training optimization capability
4. **Tool Foundation**: Base for future automated training optimization

**Integration with Multi-Symbol Design**: Use optimized configuration from analytics as baseline for multi-symbol experiments in [Multi-Symbol Design Document](multi-symbol-design.md).

---

**Status**: Ready for development - comprehensive implementation plan with clear deliverables and success criteria.