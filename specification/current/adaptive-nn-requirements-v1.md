# KTRDR Adaptive Neural Network Requirements - Phase 1

**Document Version**: 1.0  
**Date**: January 2025  
**Status**: DRAFT  
**Timeline**: 3-4 weeks

---

## 1. Executive Summary

This document defines requirements for evolving KTRDR's neural network from a single-strategy system to an adaptive multi-market trading system that naturally learns to activate different internal pathways based on market conditions. The approach uses attention mechanisms and multi-symbol training without explicit regime detection.

### Key Principles
- **Simplicity**: Build on existing working MLP architecture
- **Focus**: Add only what's necessary for adaptive behavior
- **MVP Mindset**: Prove the concept before adding complexity

---

## 2. Vision & Goals

### 2.1 Current State
- Single neural network (MLP) trained on individual symbols
- ~25 technical indicators with fuzzy logic preprocessing
- 42-52% classification accuracy
- Working backtesting and paper trading infrastructure

### 2.2 Target State (Phase 1)
- Neural network with attention mechanism for dynamic feature selection
- Multi-symbol training for generalization
- Natural adaptation to different market conditions through learned attention patterns
- Improved accuracy through better feature utilization

### 2.3 Success Criteria
- [ ] Model achieves >55% accuracy on validation set
- [ ] Attention patterns show meaningful variation across market conditions
- [ ] Model generalizes to unseen symbols (>50% accuracy)
- [ ] Training remains stable with multi-symbol data
- [ ] Inference time increases by <2x

---

## 3. Functional Requirements

### 3.1 Feature Engineering

#### 3.1.1 Multi-Timeframe Support
**Requirement**: Expand feature generation to multiple timeframes

**Specification**:
```yaml
timeframes:
  - 15m   # Short-term noise and momentum
  - 1h    # Intraday patterns
  - 4h    # Session-based movements
  - 1d    # Daily trends (optional for Phase 1)

# Expected feature count
# 25 indicators × 3 fuzzy sets × 3-4 timeframes = 225-300 features
```

**Implementation Notes**:
- Reuse existing indicator calculation code
- Ensure temporal alignment across timeframes
- Handle missing data gracefully (markets closed, gaps)

#### 3.1.2 Feature Organization
**Requirement**: Structure features for attention mechanism

**Specification**:
- Features must be organized consistently across timeframes
- Group features by indicator type and timeframe
- Maintain feature name mapping for interpretability

**Example Structure**:
```python
# Features organized as: [timeframe][indicator][fuzzy_set]
features = {
    '15m': {
        'rsi': ['low', 'neutral', 'high'],
        'macd': ['bearish', 'neutral', 'bullish'],
        # ...
    },
    '1h': {
        # Same structure
    }
}
```

### 3.2 Neural Network Architecture

#### 3.2.1 Attention Mechanism
**Requirement**: Add simple attention layer to enable dynamic feature selection

**Specification**:
```python
class AttentionLayer:
    """
    Input: Feature vector of size N (225-300)
    Output: Attention weights [0,1] of size N
    
    Properties:
    - Weights sum to approximately 1.0 (soft constraint)
    - Smooth transitions (no sudden jumps)
    - Interpretable (which features are important when)
    """
```

**Implementation Requirements**:
- Single hidden layer with ReLU activation
- Sigmoid output for [0,1] range
- Optional: L1 regularization for sparsity
- Must be differentiable for backpropagation

#### 3.2.2 Enhanced MLP Architecture
**Requirement**: Modify existing MLP to incorporate attention

**Specification**:
```python
class AdaptiveNeuralNetwork:
    """
    Architecture:
    1. Input Layer: 225-300 features
    2. Attention Layer: Learn feature importance
    3. Feature Multiplication: element-wise attention application
    4. Hidden Layer 1: 256 neurons (wide for implicit specialization)
    5. Dropout: 0.3
    6. Hidden Layer 2: 128 neurons  
    7. Dropout: 0.3
    8. Hidden Layer 3: 64 neurons
    9. Output Layer: 3 classes (BUY, HOLD, SELL)
    """
```

**Constraints**:
- Must be compatible with existing training pipeline
- PyTorch implementation
- Support both training and inference modes

### 3.3 Multi-Symbol Training

#### 3.3.1 Symbol Selection
**Requirement**: Train on multiple forex pairs simultaneously

**Initial Symbol Set**:
```python
primary_symbols = [
    "EURUSD",  # Major pair, most liquid
    "GBPUSD",  # Major pair, correlated but different
    "USDJPY",  # Major pair, different dynamics
]

# Phase 1.5 additions (optional)
extended_symbols = [
    "AUDUSD",  # Commodity currency
    "USDCAD",  # Oil correlation
]
```

#### 3.3.2 Data Loading Strategy
**Requirement**: Balanced sampling across symbols

**Specification**:
- Equal representation from each symbol per epoch
- Temporal alignment (same date ranges)
- Shuffle within batches but maintain symbol balance
- Support for weighted sampling (future enhancement)

**Implementation**:
```python
class MultiSymbolDataLoader:
    def __init__(self, symbols, start_date, end_date, batch_size=32):
        """
        Parameters:
        - symbols: List of currency pairs
        - start_date/end_date: Training period
        - batch_size: Must be divisible by len(symbols)
        """
    
    def get_batch(self):
        """
        Returns balanced batch with equal samples per symbol
        """
```

### 3.4 Training Process

#### 3.4.1 Training Configuration
**Requirement**: Adapt training process for multi-symbol attention-based model

**Specifications**:
```yaml
training:
  # Existing parameters (keep what works)
  batch_size: 32
  learning_rate: 0.001
  optimizer: Adam
  loss_function: CrossEntropyLoss
  
  # New parameters
  attention_regularization: 0.0001  # L1 penalty on attention
  gradient_clipping: 1.0            # Prevent explosion
  warmup_epochs: 5                  # Gradual learning rate increase
  
  # Multi-symbol specific
  symbols_per_batch: 3              # All symbols in each batch
  temporal_gap: 100                 # Bars between train/val samples
```

#### 3.4.2 Validation Strategy
**Requirement**: Proper validation for multi-symbol model

**Specifications**:
- Time-based split (no future leakage)
- Validate on all training symbols
- Additional test on held-out symbol
- Track per-symbol performance

### 3.5 Monitoring & Analytics

#### 3.5.1 Attention Analysis
**Requirement**: Tools to understand what the model learns

**Specifications**:
```python
def analyze_attention_patterns(model, data_loader):
    """
    Returns:
    - Average attention weights per feature
    - Attention variance (does it change?)
    - Correlation with market conditions
    - Top-K most attended features
    """

def visualize_attention_heatmap(model, sample_data):
    """
    Creates heatmap showing:
    - Features on Y-axis (grouped by indicator/timeframe)
    - Time on X-axis
    - Attention weight as color intensity
    """
```

#### 3.5.2 Performance Metrics
**Requirement**: Extended metrics for adaptive behavior

**New Metrics**:
- Per-symbol accuracy
- Cross-symbol generalization score
- Attention stability (how much weights vary)
- Feature utilization (% features with >0.1 attention)
- Inference time comparison

---

## 4. Non-Functional Requirements

### 4.1 Performance
- Training time should increase by <3x
- Inference latency should increase by <2x
- Memory usage should stay under 8GB
- Must support CPU-only training (until GPU enabled)

### 4.2 Compatibility
- Integrate with existing data pipeline
- Work with current fuzzy logic preprocessing
- Compatible with existing backtesting system
- Maintain same API interface for predictions

### 4.3 Maintainability
- Clear separation between attention and MLP components
- Extensive logging for debugging
- Model versioning for A/B testing
- Configuration-driven architecture

---

## 5. Implementation Plan

### Week 1: Foundation
**Day 1-2: Multi-timeframe Data Pipeline**
- [ ] Extend DataManager for multiple timeframes
- [ ] Test temporal alignment
- [ ] Verify fuzzy feature generation

**Day 3-4: Multi-Symbol Data Loader**
- [ ] Implement balanced sampling
- [ ] Test with 2 symbols first
- [ ] Performance optimization

**Day 5: Integration Testing**
- [ ] Verify data pipeline end-to-end
- [ ] Check memory usage
- [ ] Document any issues

### Week 2: Neural Architecture
**Day 1-2: Attention Layer Implementation**
- [ ] Create AttentionLayer class
- [ ] Unit tests for attention mechanism
- [ ] Gradient flow verification

**Day 3-4: Integrated Model**
- [ ] Combine attention with existing MLP
- [ ] Maintain backward compatibility
- [ ] Test on single symbol first

**Day 5: Training Pipeline Updates**
- [ ] Add attention regularization
- [ ] Implement gradient clipping
- [ ] Update metrics tracking

### Week 3: Multi-Symbol Training
**Day 1-2: Initial Training**
- [ ] Train on 2 symbols (EURUSD, GBPUSD)
- [ ] Monitor convergence
- [ ] Debug any instabilities

**Day 3-4: Expand Training**
- [ ] Add third symbol (USDJPY)
- [ ] Implement cross-symbol validation
- [ ] Performance analysis

**Day 5: Analysis Tools**
- [ ] Implement attention visualization
- [ ] Create performance dashboards
- [ ] Document findings

### Week 4: Validation & Refinement
**Day 1-2: Comprehensive Testing**
- [ ] Test on held-out symbol
- [ ] Backtesting integration
- [ ] Performance benchmarking

**Day 3-4: Optimization**
- [ ] Hyperparameter tuning
- [ ] Architecture refinements
- [ ] Documentation

**Day 5: Release Preparation**
- [ ] Code review
- [ ] Final testing
- [ ] Deployment plan

---

## 6. Risks & Mitigations

### 6.1 Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|---------|-------------|------------|
| Attention mechanism doesn't learn meaningful patterns | High | Medium | Start with simple attention, add complexity gradually |
| Multi-symbol training destabilizes | High | Low | Begin with 2 similar symbols, expand slowly |
| Performance degrades vs. single-symbol | Medium | Medium | Maintain single-symbol baseline for comparison |
| Training time becomes prohibitive | Medium | High | Implement checkpointing, consider cloud GPU |

### 6.2 Data Risks

| Risk | Impact | Probability | Mitigation |
|------|---------|-------------|------------|
| Timeframe alignment issues | High | Low | Thorough testing, clear data pipeline |
| Insufficient data diversity | Medium | Medium | Can add more symbols in Phase 2 |
| Feature explosion (too many) | Low | Medium | Feature importance analysis, pruning |

---

## 7. Success Metrics & Exit Criteria

### 7.1 Minimum Success (Must Have)
- [ ] Attention model trains successfully
- [ ] Achieves ≥52% accuracy (matches current)
- [ ] Works on at least 2 symbols
- [ ] Attention patterns are non-uniform

### 7.2 Target Success (Should Have)
- [ ] Achieves >55% accuracy
- [ ] Successfully trains on 3+ symbols
- [ ] Shows clear attention pattern differences
- [ ] Generalizes to unseen symbol (>50%)

### 7.3 Stretch Goals (Nice to Have)
- [ ] 60%+ accuracy achieved
- [ ] Interpretable attention patterns
- [ ] 5+ symbols training
- [ ] Real-time inference ready

---

## 8. Future Phases Preview

### Phase 2 (Months 2-3)
- Transformer architecture exploration
- 10+ symbol training
- Advanced attention mechanisms
- Real-time inference optimization

### Phase 3 (Months 4-6)
- Mixture of experts investigation
- Cross-asset training (FX + commodities)
- Production deployment
- Continuous learning pipeline

---

## 9. Dependencies

### 9.1 Technical Dependencies
- PyTorch (existing)
- Current fuzzy logic engine
- IB data pipeline
- Backtesting framework

### 9.2 Data Dependencies
- Historical data for selected symbols
- Consistent data quality
- No major gaps in training period

### 9.3 Knowledge Dependencies
- Understanding of attention mechanisms
- Multi-task learning concepts
- Time series alignment

---

## 10. Acceptance Criteria

The Phase 1 implementation will be considered complete when:

1. **Multi-timeframe pipeline** generates 200+ fuzzy features successfully
2. **Attention-based model** trains without convergence issues
3. **Multi-symbol training** works with at least 3 forex pairs
4. **Performance metrics** meet minimum success criteria
5. **Analysis tools** provide clear visibility into model behavior
6. **Documentation** is complete and accurate
7. **All tests** pass in CI/CD pipeline
8. **Backtesting** confirms no regression in strategy performance

---

## Appendix A: Technical Specifications

### A.1 Attention Layer Detailed Design
```python
class AttentionLayer(nn.Module):
    def __init__(self, input_dim, hidden_dim=None, sparsity_penalty=0.0001):
        super().__init__()
        hidden_dim = hidden_dim or input_dim // 2
        
        self.attention_network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, input_dim),
            nn.Sigmoid()
        )
        
        self.sparsity_penalty = sparsity_penalty
    
    def forward(self, x):
        attention_weights = self.attention_network(x)
        
        # Optional: Add sparsity penalty during training
        if self.training and self.sparsity_penalty > 0:
            self.sparsity_loss = self.sparsity_penalty * attention_weights.mean()
        
        return x * attention_weights
```

### A.2 Data Structure Specifications
```python
@dataclass
class MultiTimeframeFeatures:
    """Container for multi-timeframe fuzzy features"""
    symbol: str
    timestamp: datetime
    features: Dict[str, Dict[str, List[float]]]  # timeframe -> indicator -> values
    label: int  # 0: SELL, 1: HOLD, 2: BUY
    
    def to_tensor(self) -> torch.Tensor:
        """Flatten to 1D tensor maintaining consistent order"""
        pass

@dataclass
class AttentionAnalysis:
    """Results from attention pattern analysis"""
    mean_attention: np.ndarray
    std_attention: np.ndarray
    top_k_features: List[Tuple[str, float]]
    temporal_stability: float
    market_condition_correlation: Dict[str, float]
```

---

**Document Status**: DRAFT - Ready for Review  
**Next Review Date**: Week 1 completion  
**Owner**: KTRDR Development Team