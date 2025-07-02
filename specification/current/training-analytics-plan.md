# Training Analytics & Debugging Plan - KTRDR

**Version**: 1.0  
**Date**: December 2024  
**Status**: ACTIVE PLAN - Ready for Implementation  
**Related**: [Multi-Symbol Design Document](multi-symbol-design.md)

---

## 🎯 **Objective**

Understand and fix why neural network training stops early (3-13 epochs) before attempting multi-symbol training. Focus on **data collection and analysis** rather than complex tooling to identify root causes and optimize single-symbol training.

---

## 🔍 **Phase 1: Deep Understanding of Current Training Behavior**

### 1.1 Enhanced Data Collection (No Visualization Code)

**Current Gaps in Understanding:**
- Why does validation loss plateau so quickly?
- Are gradients vanishing/exploding?
- Is the model actually learning meaningful patterns?
- What happens to fuzzy feature distributions during training?

**Data to Collect:**
- **Per-Epoch Detailed Metrics**:
  - Gradient norms by layer (detect vanishing/exploding)
  - Parameter value statistics (mean, std, min, max per layer)
  - Learning rate at each epoch
  - Class-wise precision/recall/F1 scores
  - Prediction confidence distributions
  - Loss breakdown (if possible to separate fuzzy sets)

- **Per-Batch Diagnostics** (sample every 10th batch):
  - Input feature statistics (mean, std, outliers)
  - Model output distributions before softmax
  - Gradient flow indicators
  - Memory usage patterns

### 1.2 Training Behavior Analysis Framework

**JSON Export Structure:**
```json
{
  "run_metadata": {
    "run_id": "single_symbol_debug_001",
    "symbol": "EURUSD", 
    "config": {...},
    "start_time": "...",
    "end_time": "..."
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
        "layer_1": 0.45,
        "layer_2": 0.23,
        "output": 0.67
      },
      "parameter_stats": {
        "layer_1": {"mean": 0.002, "std": 0.45, "max": 2.1},
        "layer_2": {"mean": -0.001, "std": 0.33, "max": 1.8}
      },
      "class_metrics": {
        "BUY": {"precision": 0.31, "recall": 0.45, "f1": 0.36},
        "HOLD": {"precision": 0.28, "recall": 0.12, "f1": 0.17},
        "SELL": {"precision": 0.41, "recall": 0.67, "f1": 0.51}
      },
      "confidence_stats": {
        "mean_confidence": 0.45,
        "high_confidence_predictions": 0.23,
        "prediction_entropy": 0.89
      }
    }
  ],
  "batch_samples": [...],
  "final_analysis": {
    "stopping_reason": "early_stopping_triggered",
    "best_epoch": 8,
    "best_val_accuracy": 0.487,
    "total_epochs": 13
  }
}
```

### 1.3 Critical Questions to Answer Through Data

**Learning Dynamics:**
1. **Is the model actually learning?** 
   - Compare epoch 1 vs epoch 13 parameter distributions
   - Track gradient magnitudes - are they getting smaller over time?
   - Analyze prediction confidence evolution

2. **Why does validation loss plateau?**
   - Does training loss continue decreasing while val loss stays flat?
   - Are gradients still flowing or have they diminished?
   - Is the model memorizing training data (overfitting)?

3. **Are fuzzy features appropriate for this architecture?**
   - What's the distribution of fuzzy membership values?
   - Are they all clustered around 0.5 (uninformative)?
   - Do different fuzzy sets contribute differently to learning?

4. **Is early stopping too aggressive?**
   - How much does val loss actually vary epoch-to-epoch?
   - Is min_delta=0.0001 realistic for this problem?
   - What would happen with different patience values?

---

## 🧪 **Phase 2: Systematic Parameter Testing Strategy**

### 2.1 How Systematic Testing Would Work

**Single-Variable Testing (One at a time):**

**Learning Rate Experiment:**
- **Control**: Current config (LR=0.001, patience=15)
- **Test**: [0.01, 0.001, 0.0001, 0.00001] keeping everything else identical
- **Measure**: Epochs reached, final accuracy, learning curves
- **Data Export**: Full JSON for each run
- **Analysis**: Compare learning dynamics across LR values

**Early Stopping Patience Experiment:**
- **Control**: Current config 
- **Test**: Patience [10, 20, 30, 50] with same LR
- **Measure**: When does training actually stop improving vs when early stopping triggers?
- **Analysis**: Find optimal patience that doesn't cut off real learning

**Architecture Size Experiment:**
- **Control**: [50, 25, 12]
- **Test**: [32, 16], [64, 32, 16], [128, 64, 32], [256, 128, 64]
- **Measure**: Does larger architecture learn longer and better?
- **Analysis**: Parameter count vs performance relationship

### 2.2 Experimental Design Principles

**Controlled Variables:**
- Same dataset (single symbol, same date range)
- Same random seed for reproducibility
- Same fuzzy set configurations
- Same validation split

**Measured Outcomes:**
- **Primary**: Epochs reached before stopping
- **Secondary**: Best validation accuracy achieved
- **Tertiary**: Learning curve shape (gradual vs rapid plateau)

**Sample Size:**
- 3 runs per configuration (different random seeds)
- Focus on consistent patterns across runs
- Export all raw data for manual analysis

---

## 📊 **Phase 3: Data Analysis Strategy (Manual, Not Automated)**

### 3.1 Data Export and Analysis Workflow

**Export Strategy:**
- Each training run exports comprehensive JSON
- Store in structured directory: `training_data/{run_id}/metrics.json`
- Include configuration file alongside metrics
- Export to formats suitable for external analysis (pandas, R, Excel)

**Manual Analysis Questions:**
1. **Pattern Recognition**: 
   - What do "good" vs "bad" training runs look like in the data?
   - Are there consistent patterns in gradient norms before early stopping?
   - How do class metrics evolve - is the model learning all classes equally?

2. **Parameter Sensitivity**:
   - Which hyperparameters have the biggest impact on epochs reached?
   - Is there a clear learning rate threshold where behavior changes?
   - Does architecture size correlate with learning stability?

3. **Feature Quality Assessment**:
   - Are fuzzy membership values providing useful signal?
   - Which fuzzy sets seem most/least informative for learning?
   - Are input features well-distributed or clustered?

### 3.2 Decision Framework Based on Analysis

**If Analysis Shows:**
- **High learning rate causes oscillation**: Reduce LR and test warmup schedules
- **Model underfitting**: Increase architecture size
- **Poor fuzzy feature quality**: Review fuzzy set parameters
- **Class imbalance issues**: Adjust loss function or sampling strategy
- **Genuine convergence**: Current early stopping is appropriate

---

## 🎯 **Success Criteria for Understanding Phase**

### Before Moving to Multi-Symbol:

1. **Training Stability**: Can consistently get >30 epochs on single-symbol
2. **Performance Baseline**: Know what "good" single-symbol performance looks like
3. **Root Cause Clarity**: Understand exactly why training was stopping early
4. **Optimal Configuration**: Have data-driven hyperparameter choices
5. **Feature Validation**: Confirmed fuzzy features are learnable

### Key Questions Answered:
- "Why was training stopping at epoch 3-13?" → Clear, data-backed answer
- "What's the optimal learning rate for this problem?" → Tested answer
- "Is early stopping patience appropriate?" → Evidence-based setting
- "Are fuzzy features providing useful signal?" → Quantified assessment

---

## 🛠 **Implementation Priorities**

### **Week 1: Enhanced Data Collection**
1. **Modify ModelTrainer** to collect detailed metrics
2. **Export System**: JSON output with comprehensive training data
3. **Baseline Run**: Execute detailed training run on EURUSD with current config

### **Week 2: Systematic Testing**
4. **Learning Rate Grid**: Test [0.01, 0.001, 0.0001, 0.00001]
5. **Patience Grid**: Test [10, 20, 30, 50]
6. **Architecture Grid**: Test different model sizes

### **Week 3: Analysis & Optimization**
7. **Data Analysis**: Manual review of collected metrics
8. **Root Cause Identification**: Determine why training stops early
9. **Optimal Configuration**: Data-driven hyperparameter selection

### **Week 4: Validation**
10. **Stability Testing**: Confirm optimized config reaches >30 epochs consistently
11. **Performance Validation**: Verify improved accuracy on validation sets
12. **Documentation**: Record findings and optimal configurations

---

## 📝 **Expected Outcomes**

- **Immediate**: Understanding of why training stops at 3-13 epochs
- **Short-term**: Optimized single-symbol training reaching 30-50 epochs
- **Long-term**: Solid foundation for multi-symbol training experiments
- **Documentation**: Clear hyperparameter guidelines for future strategies

---

## 🔗 **Next Steps After This Phase**

Once single-symbol training is optimized and understood:
1. Return to [Multi-Symbol Design Document](multi-symbol-design.md)
2. Apply learned optimizations to multi-symbol training
3. Proceed with 2-symbol proof of concept using validated configuration

---

**Status**: Ready for implementation - focus on data collection and understanding before building complex tooling or attempting multi-symbol training.