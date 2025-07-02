# Multi-Symbol Training Design Document - KTRDR

**Version**: 1.0  
**Date**: December 2024  
**Status**: DRAFT - In Active Development

---

## Training Analytics & Interpretation System

### The Problem
Raw training metrics are difficult to interpret without deep ML experience. We need automated analysis that provides actionable insights.

### Proposed Solution: Automated Interpretation Layer

The system should generate both:
1. **Raw metrics** (JSON/CSV for records)
2. **Natural language analysis** (what it means and what to do)

### Example Output

```
=== Training Run Analysis: forex_multi_v1_2symbols ===

SUMMARY: ⚠️ Training stopped too early - potential learning rate issue

WHAT HAPPENED:
- Model improved rapidly for 3 epochs (loss: 1.05 → 0.72)
- Then plateaued completely (loss stuck at 0.72 for 10 epochs)
- Early stopping triggered at epoch 13

DIAGNOSIS:
- Learning rate likely too high (0.001)
- Model jumped over better solutions
- Current architecture may be too small for the data

RECOMMENDATIONS:
1. Try learning rate = 0.0001 (10x smaller)
2. Or implement learning rate warmup
3. If still plateaus, increase model size to [256, 128, 64]

COMPARISON TO BASELINE:
- Single-symbol baseline: 52% accuracy at epoch 45
- This run: 48% accuracy at epoch 13
- Verdict: Worse, but stopped too early to be conclusive
```

### Implementation Options

**Option 1: Built-in Analysis** (Recommended for MVP)
- Python code that analyzes metrics and generates reports
- Template-based natural language output
- Rules-based interpretation (if loss plateaus early → suggest lower LR)

**Option 2: LLM Integration**
- Send metrics to Claude/ChatGPT API for interpretation
- More flexible analysis but requires API setup
- Better for complex pattern recognition

**Option 3: Hybrid Approach**
- Basic automated analysis built-in
- Export detailed metrics for LLM analysis when needed
- Best of both worlds

### Key Interpretations Needed

1. **Early Stopping Diagnosis**
   - Why did training stop?
   - Was it too aggressive?
   - Should we adjust patience?

2. **Learning Dynamics**
   - Is model learning or memorizing?
   - Are gradients healthy?
   - Is architecture appropriate?

3. **Comparative Analysis**
   - How does multi-symbol compare to single-symbol?
   - Which configuration works best?
   - Are we making progress?

### MVP Analytics Code Structure

```python
class TrainingAnalyzer:
    def analyze_run(self, metrics):
        report = {
            "summary": self._get_summary(metrics),
            "diagnosis": self._diagnose_issues(metrics),
            "recommendations": self._suggest_next_steps(metrics),
            "comparison": self._compare_to_baseline(metrics)
        }
        return self._format_human_readable(report)
    
    def _diagnose_issues(self, metrics):
        issues = []
        if metrics['final_epoch'] < 20:
            issues.append("Early stopping - possible LR too high")
        if metrics['val_loss'] - metrics['train_loss'] > 0.2:
            issues.append("Overfitting detected")
        # ... more rules
        return issues
```

This gives you immediate, actionable feedback without needing to understand the raw metrics.

---

## Executive Summary

This document outlines the design and implementation plan for extending KTRDR's neural network training from single-symbol to multi-symbol datasets. The goal is to increase training data from 15 years (single symbol) to 150+ years (10 symbols) to improve model generalization and discover universal forex trading patterns.

---

## Problem Statement

### Current Limitations
- **Limited training data**: Only 15 years per symbol
- **Poor generalization**: Models overfit to single symbols
- **Mediocre accuracy**: 42-52% on 3-class classification
- **Early training termination**: Models stop improving after 3-13 epochs

### Opportunity
By training on multiple forex pairs simultaneously, we can:
- Learn patterns that transcend individual currency pairs
- Reduce overfitting through diverse examples
- Create models that work on previously unseen symbols
- Leverage 10x more historical data

---

## Design Principles

1. **Market-Specific Focus**: Train separate models for forex (not universal across all asset classes)
2. **Progressive Implementation**: Start with 2 symbols, validate, then scale to 10
3. **Simplicity First**: Use straightforward concatenation, avoid complex schemes
4. **Data-Driven Decisions**: Build analytics before scaling

---

## Technical Approach

### Data Combination Strategy

**Selected Approach**: Simple Concatenation
```
[EURUSD: 2005-2020] → [GBPUSD: 2005-2020] → [USDJPY: 2005-2020] → ...
```

**Why This Works**:
- Preserves temporal patterns within each symbol
- Minimal artificial transitions (only at symbol boundaries)
- Simple to implement and debug
- Network sees variety of patterns in single training run

**Rejected Alternatives**:
- ❌ Interleaving: Breaks multi-day patterns
- ❌ Random sampling: Destroys temporal patterns
- ❌ Synchronized only: Loses too much data

### Symbol Selection

**Phase 1 (Weeks 1-2)**: Core Pairs
- EURUSD + GBPUSD (similar dynamics)

**Phase 2 (Week 3)**: Expand Major Pairs
- Add: USDJPY + AUDUSD

**Phase 3 (Week 4)**: Complete Set
- Add: USDCAD, NZDUSD, EURGBP, EURJPY, USDCHF, GBPJPY

**Validation Symbol** (never in training):
- AUDNZD or EURCHF

### Neural Network Adjustments

```yaml
# Current (Single-Symbol)
model:
  architecture:
    hidden_layers: [64, 32, 16]
    dropout_rate: 0.2
  training:
    batch_size: 32
    early_stopping_patience: 10
    epochs: 100

# Proposed (Multi-Symbol)
model:
  architecture:
    hidden_layers: [128, 64, 32]  # 2x capacity
    dropout_rate: 0.2              # unchanged
  training:
    batch_size: 64                 # larger batches
    early_stopping_patience: 25    # more patience
    epochs: 200                    # more available
    # New additions:
    reduce_lr_patience: 10         # adaptive learning
    reduce_lr_factor: 0.5
```

### Feature Configuration

Features depend on the strategy configuration:
- Each strategy defines which indicators and fuzzy sets to use
- Example: `neuro_mean_reversion.yaml` might use RSI, MACD, ATR
- Different strategies = different input dimensions
- For multi-symbol training, we must use the SAME strategy across all symbols
- Universal membership functions (same parameters for all symbols)
- No symbol-specific inputs (network is symbol-blind)

---

## Success Metrics

### Primary Metrics
1. **Generalization**: Performance on unseen symbol (AUDNZD)
2. **Consistency**: Sharpe ratio variance across all symbols < 0.3
3. **Stability**: No early stopping before epoch 30

### Secondary Metrics
1. **Training efficiency**: Time per epoch within 2x of single-symbol
2. **Memory usage**: Fits in available RAM/GPU memory
3. **Backtest improvement**: Any symbol shows improved Sharpe vs single-symbol model

### Diagnostic Metrics
- Training/validation loss curves
- Per-class accuracy evolution
- Gradient norms per epoch
- Feature importance rankings

---

## Implementation Plan

### Week 0: Fix Foundation Issues
- [ ] Diagnose why training stops at epoch 3-13
- [ ] Build training analytics system
- [ ] Establish single-symbol baseline metrics
- [ ] Verify data shuffling and label distribution

### Week 1: Two-Symbol Proof of Concept
- [ ] Modify data loader for multiple symbols
- [ ] Implement simple concatenation
- [ ] Train on EURUSD + GBPUSD
- [ ] Compare metrics vs single-symbol
- [ ] Document learnings

### Week 2: Validation & Analytics
- [ ] Test two-symbol model on USDJPY (unseen)
- [ ] Build comparative analysis tools
- [ ] Generate LLM-readable training reports
- [ ] Adjust architecture based on findings

### Week 3: Scale to Four Symbols
- [ ] Add USDJPY + AUDUSD to training
- [ ] Monitor training stability
- [ ] Validate on NZDUSD
- [ ] Compare 2-symbol vs 4-symbol results

### Week 4: Full Implementation
- [ ] Scale to all 10 forex pairs
- [ ] Run comprehensive backtests
- [ ] Document final architecture
- [ ] Create deployment pipeline

---

## Critical Issues to Resolve

### Issue 1: Early Training Termination
**Problem**: Models stop improving after 3 epochs (with patience 10)  
**Impact**: Only 3 epochs of actual learning  
**Solutions to Test**:
1. Reduce learning rate (0.001 → 0.0001)
2. Implement learning rate warmup
3. Check class imbalance in labels
4. Verify data shuffling

### Issue 2: Lack of Training Visibility
**Problem**: No systematic way to analyze training outcomes  
**Impact**: Can't diagnose issues or compare approaches  
**Solution**: Build automated metrics collection and reporting

### Issue 3: Unknown Optimal Architecture
**Problem**: Current architecture may be too small for 10x data  
**Impact**: Underfitting on larger dataset  
**Solution**: Progressive testing with metrics-driven decisions

---

## Risk Mitigation

### Risk 1: Overfitting to Training Symbols
**Mitigation**: Always validate on completely unseen pairs

### Risk 2: Training Time Explosion
**Mitigation**: GPU optimization, larger batches, early stopping

### Risk 3: Memory Constraints
**Mitigation**: Streaming data loader, gradient accumulation

### Risk 4: No Improvement Over Single-Symbol
**Mitigation**: Clear rollback plan, keep single-symbol option

---

## Open Questions

1. **Label Strategy**: Should we keep 5% ZigZag or move to ATR-based labels?
2. **Temporal Alignment**: How to handle different trading hours (though forex is 24/5)?
3. **Validation Split**: Time-based or random split for multi-symbol?
4. **Symbol Weighting**: Equal representation or weighted by liquidity?
5. **Architecture Search**: Should we try different architectures per symbol count?

---

## Next Steps

1. **Immediate**: Fix early stopping issue in single-symbol training
2. **This Week**: Implement training analytics system
3. **Next Week**: Begin two-symbol experiments
4. **Decision Point**: Week 2 - Continue scaling or pivot approach?

---

## Appendix: Training Analytics Specification

### Required Metrics per Training Run
```json
{
  "run_id": "forex_multi_v1_2symbols",
  "timestamp": "2024-12-XX",
  "configuration": {
    "symbols": ["EURUSD", "GBPUSD"],
    "date_range": "2005-2020",
    "architecture": [128, 64, 32],
    "total_samples": 150000
  },
  "results": {
    "final_epoch": 45,
    "best_val_loss": 0.485,
    "final_train_accuracy": 0.68,
    "final_val_accuracy": 0.64,
    "training_time_minutes": 12.5
  },
  "patterns": {
    "overfitting": false,
    "early_plateau": false,
    "unstable_gradients": false,
    "class_imbalance": "slight_hold_bias"
  },
  "per_epoch_data": [
    {"epoch": 1, "train_loss": 1.05, "val_loss": 1.08, "lr": 0.001},
    // ... all epochs
  ]
}
```

### Comparative Analysis Output
- Side-by-side loss curves
- Performance matrix (symbols × metrics)
- Recommendations for next experiment
- Anomaly detection (unusual patterns)

---

**End of Document**