# Multi-Timeframe & Multi-Symbol Implementation Plan

**Document Version**: 1.0  
**Date**: July 2, 2025  
**Status**: DRAFT  
**Timeline**: 3-4 weeks

---

## 🎯 **Executive Summary**

This document details the implementation plan for adding multi-timeframe and multi-symbol capabilities to the existing KTRDR neural network system. The implementation builds incrementally on the current architecture without major rewrites.

### **Core Concept Clarification**

**Multi-Timeframe Features**: Instead of having 27 features from a single timeframe, we'll have separate features for each timeframe, creating distinct "feature groups":

```
Current (single timeframe):
- rsi_oversold, rsi_neutral, rsi_overbought
- macd_bearish, macd_neutral, macd_bullish
- sma_below, sma_near, sma_above
Total: 9 indicators × 3 fuzzy sets = 27 features

Target (multi-timeframe):
15m timeframe:
- 15m_rsi_oversold, 15m_rsi_neutral, 15m_rsi_overbought
- 15m_macd_bearish, 15m_macd_neutral, 15m_macd_bullish
- 15m_sma_below, 15m_sma_near, 15m_sma_above

1h timeframe:
- 1h_rsi_oversold, 1h_rsi_neutral, 1h_rsi_overbought
- 1h_macd_bearish, 1h_macd_neutral, 1h_macd_bullish
- 1h_sma_below, 1h_sma_near, 1h_sma_above

4h timeframe:
- 4h_rsi_oversold, 4h_rsi_neutral, 4h_rsi_overbought
- 4h_macd_bearish, 4h_macd_neutral, 4h_macd_bullish
- 4h_sma_below, 4h_sma_near, 4h_sma_above

Total: 9 indicators × 3 fuzzy sets × 3 timeframes = 81 features
```

The neural network receives a single feature vector with all timeframes combined, allowing the attention mechanism to learn which timeframe patterns are most relevant for each market condition.

---

## 🏗️ **Phase 0: Strategy Grammar & Model Naming Evolution (Prerequisites)**

### **Problem Statement**

The current system has a fundamental architectural contradiction:

**Current State:**
```yaml
# Strategy YAML defines multi-symbols
data:
  symbols: ["AAPL", "MSFT", "GOOGL"]
  timeframes: ["1h", "4h", "1d"]

# But models are stored per symbol-timeframe
models/neuro_mean_reversion/AAPL_1h_v1/
models/neuro_mean_reversion/MSFT_1h_v1/
models/neuro_mean_reversion/GOOGL_1h_v1/
```

**Target State:**
```yaml
# Strategy defines training scope and deployment target
training:
  symbols: ["AAPL", "MSFT", "GOOGL"]  # Training ensemble
  timeframes: ["15m", "1h", "4h"]     # Multi-timeframe features

deployment:
  scope: "universal"  # Can trade any symbol with similar characteristics
  # OR scope: "symbol_specific"  # Trained for specific symbols only

# Models become strategy-versioned, not symbol-versioned
models/neuro_mean_reversion_multi/universal_v1/
models/neuro_mean_reversion_multi/universal_v2/
```

### **Strategy Grammar Evolution**

#### **New Strategy Schema Structure**
```yaml
# Meta information
name: "neuro_mean_reversion_multi"
description: "Multi-symbol, multi-timeframe adaptive mean reversion"
version: "2.0"
scope: "universal"  # "universal" | "symbol_group" | "symbol_specific"

# Training Data Configuration
training_data:
  # Symbol configuration
  symbols:
    mode: "multi_symbol"  # "single" | "multi_symbol" 
    list: ["EURUSD", "GBPUSD", "USDJPY"]  # Training symbols
    selection_criteria:  # Alternative to explicit list
      asset_class: "forex"
      volatility_range: [0.01, 0.05]
      liquidity_tier: "tier1"
  
  # Timeframe configuration  
  timeframes:
    mode: "multi_timeframe"  # "single" | "multi_timeframe"
    list: ["15m", "1h", "4h"]
    base_timeframe: "1h"  # Reference timeframe for alignment
    
  # Data requirements
  history_required: 500  # bars per timeframe
  start_date: "2020-01-01"  # Optional explicit date range
  end_date: "2024-01-01"

# Deployment Configuration
deployment:
  # Where this model can be used
  target_symbols:
    mode: "universal"  # "universal" | "group_restricted" | "training_only"
    restrictions:  # Only if mode != "universal"
      asset_classes: ["forex"]
      excluded_symbols: ["EXOTIC_PAIRS"]
      
  target_timeframes:
    mode: "multi_timeframe"  # Must match training
    supported: ["15m", "1h", "4h"]  # Must be subset of training timeframes
    
# Rest of config remains similar...
indicators: [...]
fuzzy_sets: [...]
model: [...]
```

#### **Backward Compatibility Strategy**
```yaml
# Legacy single-symbol, single-timeframe strategies
name: "legacy_mean_reversion"
scope: "symbol_specific"  # Explicit legacy mode

training_data:
  symbols:
    mode: "single"
    symbol: "AAPL"  # Single symbol (legacy)
  timeframes:
    mode: "single" 
    timeframe: "1h"  # Single timeframe (legacy)

deployment:
  target_symbols:
    mode: "training_only"  # Can only trade AAPL
  target_timeframes:
    mode: "single"
    timeframe: "1h"
```

### **Model Naming Convention Evolution**

#### **Current (Legacy) Model Paths**
```
models/{strategy_name}/{symbol}_{timeframe}_v{version}/
├── models/neuro_mean_reversion/AAPL_1h_v1/
├── models/neuro_mean_reversion/MSFT_1h_v1/
└── models/neuro_mean_reversion/GBPUSD_1h_v1/
```

#### **New Multi-Scope Model Paths**
```
models/{strategy_name}/{scope}_{identifier}_v{version}/

# Universal models (symbol-agnostic)
models/neuro_mean_reversion_multi/universal_v1/
models/neuro_mean_reversion_multi/universal_v2/

# Symbol-group models
models/neuro_mean_reversion_multi/forex_majors_v1/
models/neuro_mean_reversion_multi/us_stocks_v1/

# Legacy compatibility (symbol-specific)
models/neuro_mean_reversion/aapl_1h_v1/  # lowercase for legacy distinction
```

#### **Model Metadata Enhancement**
```json
// models/neuro_mean_reversion_multi/universal_v1/metadata.json
{
  "strategy_name": "neuro_mean_reversion_multi",
  "strategy_version": "2.0",
  "model_version": 1,
  "scope": "universal",
  
  "training_data": {
    "symbols": ["EURUSD", "GBPUSD", "USDJPY"],
    "timeframes": ["15m", "1h", "4h"],
    "base_timeframe": "1h",
    "date_range": ["2020-01-01", "2024-01-01"],
    "total_samples": 150000
  },
  
  "deployment_capabilities": {
    "symbol_restrictions": null,  // null = universal
    "timeframe_restrictions": ["15m", "1h", "4h"],
    "asset_class_compatibility": ["forex", "stocks", "crypto"],
    "min_liquidity_tier": "tier2"
  },
  
  "feature_architecture": {
    "input_size": 243,  // 3 timeframes × 81 features
    "timeframe_features": {
      "15m": 81,
      "1h": 81, 
      "4h": 81
    },
    "symbol_embedding_dim": 32,
    "attention_mechanism": true
  },
  
  "performance_metrics": {
    "cross_symbol_accuracy": 0.67,
    "per_symbol_accuracy": {
      "EURUSD": 0.65,
      "GBPUSD": 0.68,
      "USDJPY": 0.69
    },
    "generalization_score": 0.61  // Performance on unseen symbols
  }
}
```

### **CLI Command Evolution**

#### **Current Commands (Legacy)**
```bash
# Single symbol, single timeframe
ktrdr models train strategies/neuro_mean_reversion.yaml GBPUSD 1h

# Current multi-symbol attempt (broken)  
ktrdr models train strategies/neuro_mean_reversion.yaml EURUSD,GBPUSD 1h
```

#### **New Multi-Scope Commands**
```bash
# Multi-symbol, multi-timeframe training
ktrdr models train strategies/neuro_mean_reversion_multi.yaml

# Strategy-driven training (no CLI symbol/timeframe override)
# Symbols and timeframes come from strategy YAML only

# For testing/development: override strategy config
ktrdr models train strategies/neuro_mean_reversion_multi.yaml \
  --override-symbols EURUSD,GBPUSD \
  --override-timeframes 1h,4h

# Legacy single-symbol training (backward compatibility)
ktrdr models train strategies/legacy_mean_reversion.yaml \
  --symbol AAPL --timeframe 1h
```

#### **Model Deployment Commands**
```bash
# Universal model deployment (any compatible symbol)
ktrdr models deploy neuro_mean_reversion_multi/universal_v1 \
  --symbol GBPUSD --timeframe 1h

# Check deployment compatibility
ktrdr models check-compatibility neuro_mean_reversion_multi/universal_v1 \
  --symbol EURJPY --timeframe 15m

# List available models for symbol
ktrdr models list --compatible-with EURUSD --timeframe 1h
```

### **Implementation Requirements for Phase 0**

#### **Strategy Configuration Validation**
- [ ] **New Strategy Schema**: Define and implement new YAML schema with training/deployment sections
- [ ] **Backward Compatibility**: Automatically detect and handle legacy strategy configs
- [ ] **Schema Migration**: Tool to convert legacy strategies to new format

#### **Model Storage Refactoring**
- [ ] **New Model Paths**: Implement scope-based model directory structure
- [ ] **Metadata Enhancement**: Add comprehensive model metadata with training/deployment info
- [ ] **Legacy Model Support**: Maintain compatibility with existing symbol_timeframe_v models

#### **CLI Interface Updates**
- [ ] **Strategy-Driven Training**: Remove mandatory symbol/timeframe CLI arguments for multi-scope strategies
- [ ] **Deployment Commands**: Add model deployment and compatibility checking commands
- [ ] **Migration Tools**: Commands to migrate legacy models to new naming convention

#### **API Interface Updates**
- [ ] **Multi-Scope Training Endpoint**: Support strategy-driven training without explicit symbols
- [ ] **Model Compatibility API**: Check if model can trade specific symbol/timeframe combinations
- [ ] **Model Listing API**: List available models by compatibility criteria

---

## 📋 **Phase 1: Multi-Timeframe Implementation (Week 1)**

### **Backend Implementation**

#### **Step 1a: Extend DataManager for Multi-Timeframe Loading**

**What it does**: Add capability to load OHLCV data for multiple timeframes simultaneously with proper temporal alignment.

**Implementation approach**:
- Add new method `load_multi_timeframe_data()` to existing `DataManager` class
- Reuse existing `load_data()` method internally - call it once for each timeframe
- Handle temporal alignment by using the base timeframe (usually 1h) as the reference
- Align higher timeframes (4h, 1d) by forward-filling values
- Align lower timeframes (15m) by taking the most recent value at each base timeframe timestamp

**Temporal Alignment Strategy**:
```
Base timeframe: 1h (reference grid)
15m data: Take value at :00, :15, :30, :45 - use :00 value for 1h alignment
4h data: Forward-fill 4h values across 4 consecutive 1h periods
```

**Interface**:
```python
def load_multi_timeframe_data(
    self,
    symbol: str,
    timeframes: List[str],  # ["15m", "1h", "4h"]
    start_date: str,
    end_date: str,
    base_timeframe: str = "1h",
    mode: str = "local"
) -> Dict[str, pd.DataFrame]:
    """Returns: {timeframe: aligned_ohlcv_dataframe}"""
```

#### **Step 1b: Extend IndicatorEngine for Multi-Timeframe Processing**

**What it does**: Calculate the same set of indicators on each timeframe's OHLCV data.

**Implementation approach**:
- Add new method `apply_multi_timeframe()` to existing `IndicatorEngine` class
- For each timeframe, call the existing `apply()` method with that timeframe's data
- Use the same indicator configuration for all timeframes (RSI, MACD, SMA, etc.)

**Interface**:
```python
def apply_multi_timeframe(
    self,
    multi_timeframe_ohlcv: Dict[str, pd.DataFrame],
    indicator_configs: List[Dict]  # Same configs applied to all timeframes
) -> Dict[str, pd.DataFrame]:
    """Returns: {timeframe: indicators_dataframe}"""
```

#### **Step 1c: Extend FuzzyEngine for Multi-Timeframe Fuzzy Sets**

**What it does**: Generate fuzzy membership values for indicators on each timeframe.

**Implementation approach**:
- Add new method `generate_multi_timeframe_memberships()` to existing `FuzzyEngine` class
- For each timeframe, call existing fuzzy generation methods
- Use the same fuzzy set configurations across all timeframes

**Interface**:
```python
def generate_multi_timeframe_memberships(
    self,
    multi_timeframe_indicators: Dict[str, pd.DataFrame],
    fuzzy_sets_config: Dict[str, Dict]  # Same fuzzy sets for all timeframes
) -> Dict[str, pd.DataFrame]:
    """Returns: {timeframe: fuzzy_memberships_dataframe}"""
```

#### **Step 1d: Extend FuzzyNeuralProcessor for Feature Combination**

**What it does**: Take the separate timeframe fuzzy DataFrames and combine them into a single feature vector for the neural network.

**Feature combination process**:
1. Take fuzzy memberships from each timeframe
2. Add timeframe prefix to each feature name for clarity
3. Concatenate all features into a single vector in a consistent order
4. The neural network receives one long feature vector with all timeframes

**Example of feature combination**:
```
Input:
- 15m fuzzy: [rsi_low: 0.8, rsi_neutral: 0.2, rsi_high: 0.0, macd_bearish: 0.9, ...]
- 1h fuzzy:  [rsi_low: 0.3, rsi_neutral: 0.7, rsi_high: 0.0, macd_bearish: 0.2, ...]
- 4h fuzzy:  [rsi_low: 0.1, rsi_neutral: 0.6, rsi_high: 0.3, macd_bearish: 0.0, ...]

Output (single feature vector):
[15m_rsi_low: 0.8, 15m_rsi_neutral: 0.2, 15m_rsi_high: 0.0, 15m_macd_bearish: 0.9, ...,
 1h_rsi_low: 0.3, 1h_rsi_neutral: 0.7, 1h_rsi_high: 0.0, 1h_macd_bearish: 0.2, ...,
 4h_rsi_low: 0.1, 4h_rsi_neutral: 0.6, 4h_rsi_high: 0.3, 4h_macd_bearish: 0.0, ...]
```

**Interface**:
```python
def prepare_multi_timeframe_input(
    self,
    multi_timeframe_fuzzy: Dict[str, pd.DataFrame],
    timeframe_order: List[str] = ["15m", "1h", "4h"]
) -> Tuple[torch.Tensor, List[str]]:
    """Returns: (combined_feature_tensor, feature_names_list)"""
```

### **API & CLI Interface Specifications**

#### **CLI Interface Enhancement**

**Current command**:
```bash
ktrdr models train strategies/neuro_mean_reversion.yaml GBPUSD 1h --start-date 2005-01-01 --end-date 2010-01-01
```

**Enhanced command with multi-timeframe**:
```bash
ktrdr models train strategies/neuro_mean_reversion.yaml GBPUSD --timeframes 15m,1h,4h --start-date 2005-01-01 --end-date 2010-01-01
```

**New CLI parameters**:
- `--timeframes`: Comma-separated list of timeframes (defaults to single timeframe if not specified)
- `--base-timeframe`: Reference timeframe for alignment (defaults to "1h")

#### **API Interface Enhancement**

**Current API endpoint**:
```
POST /api/v1/trainings/start
{
    "symbol": "GBPUSD",
    "timeframe": "1h",
    "strategy_name": "neuro_mean_reversion",
    "start_date": "2005-01-01",
    "end_date": "2010-01-01"
}
```

**Enhanced API endpoint**:
```
POST /api/v1/trainings/start
{
    "symbol": "GBPUSD",
    "timeframes": ["15m", "1h", "4h"],  // New: array instead of single string
    "base_timeframe": "1h",             // New: reference timeframe
    "strategy_name": "neuro_mean_reversion",
    "start_date": "2005-01-01",
    "end_date": "2010-01-01"
}
```

**Backward compatibility**: If `timeframe` (singular) is provided, convert to `timeframes: [timeframe]` internally.

### **Success Metrics - Phase 1**

#### **Functional Success**
- [ ] Multi-timeframe data loading completes without errors
- [ ] Feature count increases from ~27 to 75-100 (3 timeframes × 25-33 features)
- [ ] All fuzzy features remain in [0,1] range
- [ ] Training pipeline processes multi-timeframe features without modification
- [ ] Model trains and converges (accuracy ≥ current baseline of ~52%)

#### **Technical Success**
- [ ] Memory usage increases by <3x (acceptable given 3x feature increase)
- [ ] Training time increases by <2x (features increase more than training time)
- [ ] Data temporal alignment produces no gaps or misaligned timestamps
- [ ] Feature names are clearly distinguishable by timeframe prefix

#### **Analytics Success**
- [ ] Training analytics capture multi-timeframe feature importance
- [ ] Feature utilization varies across timeframes (some features more important than others)
- [ ] Analytics show which timeframes contribute most to predictions

---

## 🌍 **Phase 2: Multi-Symbol Implementation (Week 2-3)**

### **Backend Implementation**

#### **Step 2a: Extend StrategyTrainer for Multi-Symbol Training**

**What it does**: Modify the training process to handle multiple symbols simultaneously instead of training on one symbol at a time.

**Implementation approach**:
- Add new method `train_multi_symbol_strategy()` to existing `StrategyTrainer` class
- Load data for all symbols using existing data loading methods
- Process indicators and fuzzy features for each symbol separately
- Combine all symbols' data for training

**Interface**:
```python
def train_multi_symbol_strategy(
    self,
    strategy_config_path: str,
    symbols: List[str],  # ["EURUSD", "GBPUSD", "USDJPY"]
    timeframes: List[str],  # Can combine with multi-timeframe
    start_date: str,
    end_date: str,
    validation_split: float = 0.2,
    data_mode: str = "local",
    progress_callback=None,
) -> Dict[str, Any]:
    """Returns: training_results_with_per_symbol_metrics"""
```

#### **Step 2b: Implement Balanced Multi-Symbol Data Loading**

**What it does**: Ensure that each training batch contains equal representation from all symbols to prevent the model from being biased toward symbols with more data.

**Why this matters**: If EURUSD has 10,000 data points and GBPUSD has 5,000 data points, random sampling would give EURUSD 67% representation in batches, making the model biased toward EURUSD patterns.

**Balanced sampling strategy**:
1. Divide batch size equally among symbols (batch_size=32, 3 symbols = ~10-11 samples per symbol per batch)
2. Randomly sample the allocated number from each symbol
3. Combine into balanced batches
4. Track per-symbol performance separately

**Implementation**: Create new `MultiSymbolDataLoader` class to handle balanced sampling.

#### **Step 2c: Add Symbol Embeddings to Neural Network**

**What it does**: Allow the neural network to learn symbol-specific patterns while still sharing universal patterns across symbols.

**Why embeddings**: Different currency pairs have different characteristics (EUR/USD vs USD/JPY behave differently), but they also share universal trading patterns. Symbol embeddings let the network learn both.

**Implementation approach**:
- Add symbol embedding layer to existing `MLPTradingModel`
- Embedding maps symbol index to small vector (e.g., 16-32 dimensions)
- Concatenate symbol embedding with fuzzy features before first hidden layer
- Network learns to associate certain patterns with certain symbols

### **API & CLI Interface Specifications**

#### **CLI Interface Enhancement**

**Multi-symbol training command**:
```bash
ktrdr models train strategies/neuro_mean_reversion.yaml --symbols EURUSD,GBPUSD,USDJPY --timeframes 15m,1h,4h --start-date 2005-01-01 --end-date 2010-01-01
```

**New CLI parameters**:
- `--symbols`: Comma-separated list of symbols for multi-symbol training
- Maintains backward compatibility: if no `--symbols`, uses positional symbol argument

#### **API Interface Enhancement**

**Multi-symbol API endpoint**:
```
POST /api/v1/trainings/start
{
    "symbols": ["EURUSD", "GBPUSD", "USDJPY"],  // New: array of symbols
    "timeframes": ["15m", "1h", "4h"],
    "strategy_name": "neuro_mean_reversion",
    "start_date": "2005-01-01",
    "end_date": "2010-01-01",
    "multi_symbol_config": {                     // New: multi-symbol specific settings
        "balance_strategy": "equal_representation",
        "symbol_embedding_dim": 32
    }
}
```

### **Success Metrics - Phase 2**

#### **Functional Success**
- [ ] Multi-symbol training completes successfully with 3 symbols
- [ ] Per-symbol accuracy tracked and reasonable (>45% for each symbol)
- [ ] Cross-symbol generalization: model trained on 2 symbols achieves >50% on 3rd symbol
- [ ] Symbol embeddings show meaningful differences between symbols

#### **Technical Success**
- [ ] Balanced sampling produces equal symbol representation in batches
- [ ] Training converges stably (no oscillations or divergence)
- [ ] Memory usage scales linearly with number of symbols
- [ ] Training time scales sub-linearly with number of symbols (some efficiency gains)

#### **Analytics Success**
- [ ] Per-symbol performance metrics tracked in analytics
- [ ] Symbol embedding visualization shows clustering by symbol characteristics
- [ ] Feature importance analysis shows both universal and symbol-specific patterns

---

## 📊 **Phase 3: Enhanced Analytics Implementation (Week 3-4)**

### **Multi-Timeframe Analytics**

**New analytics capabilities**:
- **Timeframe Feature Importance**: Which timeframes contribute most to predictions
- **Cross-Timeframe Correlation**: How different timeframes' features correlate
- **Temporal Pattern Analysis**: When each timeframe is most important

**Analytics enhancements**:
```python
def analyze_timeframe_importance(
    model, multi_timeframe_features
) -> Dict[str, float]:
    """Returns: {"15m": 0.25, "1h": 0.45, "4h": 0.30} - importance scores"""

def analyze_temporal_patterns(
    attention_weights, timestamps
) -> Dict[str, List[float]]:
    """Returns: timeframe importance over time"""
```

### **Multi-Symbol Analytics**

**New analytics capabilities**:
- **Per-Symbol Performance**: Accuracy, precision, recall for each symbol
- **Cross-Symbol Generalization**: How well model performs on unseen symbols
- **Symbol Embedding Analysis**: Clustering and relationships between symbols

### **Enhanced CSV Export Schema**

**Multi-timeframe CSV additions**:
```csv
epoch,train_loss,val_loss,train_acc,val_acc,15m_feature_importance,1h_feature_importance,4h_feature_importance,dominant_timeframe
```

**Multi-symbol CSV additions**:
```csv
epoch,train_loss,val_loss,EURUSD_acc,GBPUSD_acc,USDJPY_acc,cross_symbol_generalization,symbol_embedding_diversity
```

---

## ⚠️ **Risk Analysis & Mitigation**

### **Risk 1: Training Convergence with Multi-Symbol**

**Why this could happen**: Different symbols have different volatility patterns, correlations, and market behaviors. The network might struggle to find patterns that work across all symbols simultaneously.

**Specific scenarios**:
- EURUSD is range-bound while USDJPY is trending - conflicting signals
- Different symbols have different optimal indicator parameters
- Symbol-specific news events create contradictory patterns

**Mitigation strategies**:
1. **Start with similar symbols**: Begin with EURUSD and GBPUSD (both EUR/USD pairs)
2. **Gradual expansion**: Add one symbol at a time, validate convergence before adding more
3. **Symbol-specific validation**: Track per-symbol performance to identify problematic symbols
4. **Embedding regularization**: Prevent symbol embeddings from becoming too specialized
5. **Fallback capability**: Maintain ability to fall back to single-symbol training

### **Risk 2: Data Alignment Issues (Multi-Timeframe)**

**Root cause analysis**: Market hours, gaps, and data availability differ across timeframes.

**Specific scenarios**:
- Weekend gaps in 4h data but not in 1h data
- Different market open/close times affecting alignment
- Data quality issues in one timeframe corrupting others

**Mitigation strategies**:
1. **Least common denominator approach**: Use intersection of available timestamps across all timeframes
2. **Robust gap handling**: Extend existing gap classification to multi-timeframe scenarios
3. **Data quality validation**: Comprehensive checks before training
4. **Graceful degradation**: Continue with fewer timeframes if one fails

### **Risk 3: Feature Explosion and Overfitting**

**Why this could happen**: 27 features → 200+ features significantly increases model complexity and overfitting risk.

**Mitigation strategies**:
1. **Feature importance analysis**: Identify and remove consistently unimportant features
2. **Regularization**: Increase dropout, add L1/L2 regularization
3. **Early stopping**: More aggressive early stopping criteria
4. **Cross-validation**: Implement proper time-series cross-validation

---

## 📈 **Success Criteria & Exit Conditions**

### **Minimum Viable Success (Must Have)**
- [ ] **Functional**: Multi-timeframe and multi-symbol training both work independently
- [ ] **Performance**: Model accuracy ≥52% (maintains current baseline)
- [ ] **Stability**: Training converges consistently without manual intervention
- [ ] **Compatibility**: System maintains backward compatibility with single-symbol/single-timeframe

### **Target Success (Should Have)**
- [ ] **Performance**: Model accuracy >55% (meaningful improvement)
- [ ] **Generalization**: Cross-symbol accuracy >50% (learns transferable patterns)
- [ ] **Efficiency**: Training time increases <3x despite feature expansion
- [ ] **Analytics**: Clear insights into timeframe and symbol importance patterns

### **Stretch Success (Nice to Have)**
- [ ] **Performance**: Model accuracy >60% (significant improvement)
- [ ] **Scalability**: System handles 5+ symbols without degradation
- [ ] **Interpretability**: Attention patterns clearly correlate with market conditions
- [ ] **Production Ready**: Real-time inference capability maintained

---

## 🎯 **Implementation Timeline**

### **Week 0: Prerequisites (Strategy Grammar & Model Evolution)**
- **Days 1-2**: Design and implement new strategy schema with training/deployment sections
- **Days 3-4**: Create new model storage paths and metadata structure 
- **Day 5**: Update CLI and API interfaces for strategy-driven training

### **Week 1: Multi-Timeframe Foundation**
- **Days 1-2**: Extend DataManager and IndicatorEngine for multi-timeframe
- **Days 3-4**: Implement FuzzyEngine multi-timeframe support
- **Day 5**: Feature combination and integration testing

### **Week 2: Multi-Symbol Core**
- **Days 1-2**: Extend StrategyTrainer for multi-symbol support
- **Days 3-4**: Implement balanced data loading and symbol embeddings
- **Day 5**: Integration testing and validation

### **Week 3: Enhanced Analytics**
- **Days 1-2**: Implement multi-timeframe analytics
- **Days 3-4**: Implement multi-symbol analytics
- **Day 5**: Analytics integration and testing

### **Week 4: Integration & Validation**
- **Days 1-2**: End-to-end testing of combined multi-timeframe + multi-symbol
- **Days 3-4**: Performance optimization and bug fixes
- **Day 5**: Documentation and final validation

**Total Timeline: 4-5 weeks** (including prerequisite week)

---

## 🔄 **Backward Compatibility**

### **CLI Compatibility**
- All existing single-symbol, single-timeframe commands continue to work unchanged
- New multi-timeframe/multi-symbol features are opt-in via new flags
- Default behavior remains unchanged

### **API Compatibility**
- Existing API requests continue to work with same response format
- New multi-timeframe/multi-symbol capabilities available via enhanced request format
- Response format extended but maintains backward compatibility

### **Configuration Compatibility**
- Existing strategy configuration files work unchanged
- New multi-timeframe/multi-symbol configurations are optional extensions

---

**Document Status**: DRAFT - Ready for Review and Iteration  
**Next Review**: After Phase 1 completion  
**Owner**: KTRDR Development Team