# KTRDR Multi-Symbol Training Implementation Plan

## Executive Summary

This document outlines the comprehensive planning for implementing multi-symbol training capability in KTRDR to address the current data scarcity issue (15 years per symbol) and enable more robust model training across multiple instruments.

## 1. Current State Analysis

### 1.1 Current Training Pipeline Flow

The existing training pipeline follows this single-symbol oriented flow:

```
StrategyTrainer.train_strategy(symbol="AAPL", timeframe="1h") 
    ↓
1. Load Strategy Config (YAML)
    ↓
2. Load Market Data → DataManager.load_data(symbol, timeframe)
    ↓
3. Calculate Indicators → IndicatorEngine.apply(price_data)
    ↓
4. Generate Fuzzy Memberships → FuzzyEngine.fuzzify(indicators)
    ↓
5. Engineer Features → FeatureEngineer.prepare_features(fuzzy_data, indicators, price_data)
    ↓
6. Generate Labels → ZigZagLabeler.generate_segment_labels(price_data)
    ↓
7. Train Neural Network → ModelTrainer.train(model, train_data, val_data)
    ↓
8. Save Model → ModelStorage.save_model(model, "strategy", "AAPL", "1h")
```

### 1.2 Current Model Storage Structure

**Current Pattern:**
```
models/
├── neuro_mean_reversion/
│   ├── AAPL_1h_v1/
│   ├── AAPL_1h_v2/
│   ├── AAPL_1h_latest → AAPL_1h_v2/
│   ├── MSFT_1h_v1/
│   └── MSFT_1h_v8/
└── mean_reversion_strategy/
    ├── AAPL_1h_v1/
    └── MSFT_1h_v1/
```

**Key Observations:**
- Symbol-specific models only (`AAPL_1h_v1`, `MSFT_1h_v1`)
- No universal or multi-symbol models exist
- Each symbol trained independently
- Model loading assumes single symbol: `load_model(strategy, symbol, timeframe)`

### 1.3 Backtesting Integration

**Current Backtesting Model Loading:**
```python
# ktrdr/backtesting/backtest_engine.py (inferred pattern)
model = model_storage.load_model(strategy_name, symbol, timeframe)
```

**Assumptions:**
- One model per symbol-timeframe combination
- Direct symbol-based model lookup
- No fallback to universal models

## 2. Coupling Assessment

### 2.1 Critical Coupling Issues (High Severity)

#### 2.1.1 Direct Component Instantiation Pattern
**Location:** `ktrdr/training/train_strategy.py:30-33`
```python
self.model_storage = ModelStorage(models_dir)
self.data_manager = DataManager()
self.indicator_engine = IndicatorEngine()
```
**Impact:** Each StrategyTrainer creates its own components, preventing resource sharing across symbols.
**Effort:** **High** - Requires dependency injection refactoring

#### 2.1.2 Hardcoded Feature Engineering Parameters
**Location:** `ktrdr/training/feature_engineering.py:167-177`
```python
for ma_col in ["sma_20", "sma_50", "ema_20"]:  # Hardcoded periods
for period in [5, 10, 20]:  # Hardcoded momentum periods
```
**Impact:** One-size-fits-all parameters fail for different asset classes (stocks vs forex vs crypto).
**Effort:** **High** - Requires symbol-specific configuration system

#### 2.1.3 Single-Symbol Method Signatures
**Location:** `ktrdr/training/train_strategy.py:35-45`
```python
def train_strategy(self, symbol: str, timeframe: str, ...):
```
**Impact:** Fundamental design limitation - cannot process multiple symbols in batch.
**Effort:** **High** - Core API redesign required

### 2.2 Medium Coupling Issues (Medium Severity)

#### 2.2.1 Fixed Model Architecture
**Location:** `ktrdr/training/train_strategy.py:538-539`
```python
model = MLPTradingModel(model_config)
```
**Impact:** Cannot use different model architectures per symbol or strategy.
**Effort:** **Medium** - Requires model factory pattern

#### 2.2.2 Fixed Device Selection
**Location:** `ktrdr/training/model_trainer.py:98-106`
```python
if torch.cuda.is_available():
    self.device = torch.device("cuda")
```
**Impact:** Cannot distribute training across multiple GPUs for parallel symbol training.
**Effort:** **Medium** - Device allocation strategy needed

### 2.3 Low Coupling Issues (Low Severity)

#### 2.3.1 Configurable Components
**Location:** `ktrdr/training/model_trainer.py:367-389`
```python
optimizer_name = self.config.get("optimizer", "adam").lower()
```
**Impact:** Already has good extensibility patterns.
**Effort:** **Low** - Minimal changes needed

## 3. Multi-Symbol Design Options

### 3.1 Option A: Minimal Changes (Batch Processing)

**Approach:** Work within existing coupling, add batch processing layer

**Architecture:**
```python
class MultiSymbolTrainer:
    def __init__(self):
        self.strategy_trainer = StrategyTrainer()
    
    def train_multi_symbol(self, symbols: List[str], strategy_config: str):
        for symbol in symbols:
            self.strategy_trainer.train_strategy(symbol, ...)
```

**Pros:**
- Minimal disruption to existing code
- Quick implementation (1-2 weeks)
- Preserves current API compatibility
- No dependency injection needed

**Cons:**
- No resource sharing or optimization
- Cannot combine data across symbols
- Still creates separate models per symbol
- Misses core benefit of multi-symbol training

**Storage Strategy:**
```
models/
├── neuro_mean_reversion/
│   ├── AAPL_1h_v1/
│   ├── MSFT_1h_v1/
│   └── GOOGL_1h_v1/
```

**Effort Estimate:** **5-7 days**

### 3.2 Option B: Moderate Refactoring (Universal + Symbol-Specific)

**Approach:** Add universal model capability while maintaining symbol-specific fallbacks

**Architecture:**
```python
class UniversalTrainer:
    def __init__(self, components: TrainingComponents):
        self.components = components  # Injected dependencies
    
    def train_universal_model(self, symbols: List[str], strategy_config: str):
        # 1. Load and combine data from all symbols
        combined_data = self._load_combined_data(symbols)
        
        # 2. Apply symbol-specific feature engineering
        symbol_features = {}
        for symbol in symbols:
            features = self._engineer_symbol_features(combined_data[symbol], symbol)
            symbol_features[symbol] = features
        
        # 3. Combine features with temporal alignment
        aligned_features = self._align_temporal_features(symbol_features)
        
        # 4. Train universal model
        universal_model = self._train_model(aligned_features)
        
        # 5. Save with universal identifier
        self._save_universal_model(universal_model, symbols, strategy_config)
```

**Key Changes:**
1. **Dependency Injection:** Replace direct instantiation with injected components
2. **Symbol-Specific Config:** Parameters vary by symbol (e.g., different MA periods for stocks vs forex)
3. **Temporal Alignment:** Handle different trading hours across symbols
4. **Universal Model Storage:** New storage pattern for multi-symbol models

**Storage Strategy:**
```
models/
├── neuro_mean_reversion/
│   ├── universal_v1/                    # Multi-symbol model
│   │   ├── model.pt
│   │   ├── symbols.json                 # ["AAPL", "MSFT", "GOOGL"]
│   │   ├── symbol_configs.json          # Symbol-specific parameters
│   │   └── metadata.json
│   ├── AAPL_1h_v1/                      # Fallback single-symbol models
│   └── MSFT_1h_v1/
```

**Backtesting Integration:**
```python
# Enhanced model loading with fallback
model = model_storage.load_model_with_fallback(strategy_name, symbol, timeframe)
# 1. Try universal model first
# 2. Fallback to symbol-specific model
# 3. Fallback to similar symbol model (e.g., AAPL → MSFT for stocks)
```

**Pros:**
- Addresses core multi-symbol training goal
- Maintains backward compatibility
- Allows symbol-specific optimizations
- Enables model reuse across similar symbols

**Cons:**
- Requires significant refactoring
- More complex model storage and loading
- Temporal alignment complexity
- Higher implementation risk

**Effort Estimate:** **15-20 days**

### 3.3 Option C: Clean Architecture (Full Dependency Injection)

**Approach:** Complete architectural refactoring with proper dependency injection

**Architecture:**
```python
# Core training interface
class TrainingOrchestrator:
    def __init__(self, 
                 data_loader: DataLoader,
                 feature_engineer: FeatureEngineer,
                 model_trainer: ModelTrainer,
                 model_storage: ModelStorage):
        self.data_loader = data_loader
        self.feature_engineer = feature_engineer
        self.model_trainer = model_trainer
        self.model_storage = model_storage
    
    def train(self, request: TrainingRequest) -> TrainingResult:
        # Universal interface for single/multi-symbol training
        pass

# Flexible training request
@dataclass
class TrainingRequest:
    strategy_config: StrategyConfig
    symbols: List[str]
    timeframe: str
    training_mode: TrainingMode  # SINGLE_SYMBOL, MULTI_SYMBOL, UNIVERSAL
    
# Repository pattern for data access
class DataRepository:
    def load_multi_symbol_data(self, symbols: List[str], timeframe: str) -> Dict[str, pd.DataFrame]:
        pass
    
    def get_symbol_characteristics(self, symbol: str) -> SymbolCharacteristics:
        # Return asset class, trading hours, volatility profile, etc.
        pass
```

**Pros:**
- Clean, testable architecture
- Maximum flexibility for future extensions
- Proper separation of concerns
- Optimal resource sharing

**Cons:**
- Major breaking changes
- Requires extensive testing
- Long implementation timeline
- Risk of introducing bugs

**Effort Estimate:** **25-30 days**

## 4. Key Technical Decisions

### 4.1 Temporal Alignment Strategy

**Challenge:** Different symbols have different trading hours
- **Stocks:** 9:30 AM - 4:00 PM EST
- **Forex:** 24/5 trading
- **Crypto:** 24/7 trading

**Solution Options:**

**Option 1: Common Trading Hours Only**
```python
def align_to_common_hours(symbol_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    # Use only overlapping trading hours (e.g., 9:30-4:00 EST)
    common_hours = get_common_trading_hours(symbol_data.keys())
    aligned_data = {}
    for symbol, data in symbol_data.items():
        aligned_data[symbol] = filter_by_trading_hours(data, common_hours)
    return aligned_data
```

**Option 2: Time-of-Day Features**
```python
def add_temporal_features(data: pd.DataFrame, symbol: str) -> pd.DataFrame:
    # Add features: hour_of_day, day_of_week, market_session
    data['hour_of_day'] = data.index.hour
    data['is_market_open'] = get_market_session(data.index, symbol)
    return data
```

**Recommendation:** Use **Option 2** - preserves maximum data while handling timing differences through features.

### 4.2 Model Storage Strategy

**Current Single-Symbol Pattern:**
```
models/{strategy}/{symbol}_{timeframe}_v{version}/
```

**Multi-Symbol Pattern Options:**

**Option A: Universal Models Only**
```
models/{strategy}/universal_v{version}/
├── model.pt
├── symbols.json           # ["AAPL", "MSFT", "GOOGL"]
├── symbol_configs.json    # Symbol-specific parameters
└── metadata.json
```

**Option B: Hybrid Pattern (Recommended)**
```
models/{strategy}/
├── universal_v1/          # Multi-symbol models
│   ├── model.pt
│   ├── symbols.json
│   └── symbol_configs.json
├── AAPL_1h_v1/           # Single-symbol fallbacks
└── MSFT_1h_v1/
```

**Recommendation:** Use **Option B** - maintains backward compatibility while enabling universal models.

### 4.3 Backtesting Integration

**Enhanced Model Loading Logic:**
```python
def load_model_with_fallback(self, strategy: str, symbol: str, timeframe: str):
    # 1. Try universal model first
    universal_model = self._try_load_universal_model(strategy, symbol, timeframe)
    if universal_model:
        return universal_model
    
    # 2. Try symbol-specific model
    symbol_model = self._try_load_symbol_model(strategy, symbol, timeframe)
    if symbol_model:
        return symbol_model
    
    # 3. Try similar symbol model (stocks → stocks, forex → forex)
    similar_model = self._try_load_similar_symbol_model(strategy, symbol, timeframe)
    if similar_model:
        return similar_model
    
    raise ModelNotFoundError(f"No model found for {strategy}/{symbol}_{timeframe}")
```

### 4.4 Data Combination Strategy

**Challenge:** How to combine data from multiple symbols for training

**Option 1: Simple Concatenation**
```python
def combine_simple(symbol_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    # Concatenate all symbol data chronologically
    combined = pd.concat(symbol_data.values(), keys=symbol_data.keys())
    return combined.reset_index(level=0)  # Symbol as column
```

**Option 2: Interleaved Sampling**
```python
def combine_interleaved(symbol_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    # Interleave samples to ensure balanced representation
    # AAPL[0], MSFT[0], GOOGL[0], AAPL[1], MSFT[1], GOOGL[1], ...
    return interleave_dataframes(symbol_data)
```

**Option 3: Balanced Sampling**
```python
def combine_balanced(symbol_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    # Ensure equal representation by sampling
    min_samples = min(len(df) for df in symbol_data.values())
    balanced_data = {}
    for symbol, df in symbol_data.items():
        balanced_data[symbol] = df.sample(n=min_samples, random_state=42)
    return pd.concat(balanced_data.values())
```

**Recommendation:** Use **Option 3** - balanced sampling ensures no symbol dominates training.

## 5. Branch Strategy

### 5.1 Recommended Branch Structure

```
feature/multi-symbol-training
├── feature/dependency-injection
├── feature/universal-models
├── feature/temporal-alignment
├── feature/enhanced-model-storage
└── feature/backtesting-integration
```

### 5.2 Implementation Phases

**Phase 1: Foundation (Week 1-2)**
- Branch: `feature/dependency-injection`
- Refactor StrategyTrainer to use dependency injection
- Create TrainingComponents interface
- Implement component factories

**Phase 2: Core Multi-Symbol (Week 3-4)**
- Branch: `feature/universal-models`
- Implement UniversalTrainer
- Add symbol-specific configuration support
- Create temporal alignment utilities

**Phase 3: Storage & Loading (Week 5)**
- Branch: `feature/enhanced-model-storage`
- Extend ModelStorage for universal models
- Implement model loading with fallback
- Add backward compatibility layer

**Phase 4: Integration (Week 6)**
- Branch: `feature/backtesting-integration`
- Update backtesting engine for universal models
- Add integration tests
- Performance optimization

### 5.3 Rollback Strategy

**Safe Rollback Points:**
1. **After Phase 1:** Dependency injection can be reverted without breaking existing functionality
2. **After Phase 2:** Universal training can be disabled via feature flag
3. **After Phase 3:** Model storage maintains backward compatibility

**Rollback Procedure:**
```bash
# Disable universal training
git checkout feature/multi-symbol-training
git revert --no-commit HEAD~10..HEAD  # Revert specific commits
# Test single-symbol training still works
git commit -m "Rollback: Disable universal training"
```

## 6. Risk Analysis

### 6.1 High Risk Items

**1. Temporal Alignment Complexity**
- **Risk:** Different market hours cause training data misalignment
- **Mitigation:** Start with common hours only, add time-of-day features
- **Testing:** Verify alignment with synthetic data first

**2. Model Performance Degradation**
- **Risk:** Universal models may underperform symbol-specific models
- **Mitigation:** Maintain symbol-specific fallbacks, compare performance extensively
- **Testing:** A/B test universal vs symbol-specific models

**3. Memory Usage Explosion**
- **Risk:** Loading multiple symbols simultaneously causes OOM
- **Mitigation:** Implement batch processing, memory-efficient data loading
- **Testing:** Load test with 10+ symbols

### 6.2 Medium Risk Items

**4. Backward Compatibility Breaks**
- **Risk:** Existing model loading code breaks
- **Mitigation:** Maintain compatibility layer, extensive regression testing
- **Testing:** Full integration test suite

**5. Training Time Increases**
- **Risk:** Multi-symbol training takes too long
- **Mitigation:** Implement parallel processing, GPU optimization
- **Testing:** Benchmark training times

### 6.3 Low Risk Items

**6. Configuration Complexity**
- **Risk:** Symbol-specific configs become unwieldy
- **Mitigation:** Use hierarchical configuration with defaults
- **Testing:** Validate configs for edge cases

## 7. Recommendation

### 7.1 Recommended Approach: **Option B (Moderate Refactoring)**

**Rationale:**
1. **Addresses Core Goal:** Enables true multi-symbol training to address data scarcity
2. **Balanced Risk:** Significant improvement without complete architectural overhaul
3. **Backward Compatible:** Maintains existing single-symbol workflows
4. **Reasonable Timeline:** 15-20 days vs 25-30 days for full refactoring

### 7.2 Implementation Priorities

**Phase 1 (High Priority):**
1. Implement dependency injection in StrategyTrainer
2. Create symbol-specific configuration system
3. Build temporal alignment utilities
4. Implement universal model storage

**Phase 2 (Medium Priority):**
5. Add multi-symbol data loading
6. Implement balanced sampling strategy
7. Create universal training pipeline
8. Add fallback model loading

**Phase 3 (Low Priority):**
9. Optimize memory usage
10. Add parallel processing
11. Implement performance monitoring
12. Create comprehensive testing suite

### 7.3 Success Metrics

**Technical Metrics:**
- Universal models train successfully on 5+ symbols
- Training time per symbol decreases (due to shared computation)
- Memory usage stays within acceptable limits
- Backward compatibility maintained (100% of existing tests pass)

**Business Metrics:**
- Model accuracy improves due to increased training data
- Reduced time to deploy models for new symbols
- Ability to train on symbol combinations (e.g., sector ETFs)

### 7.4 Estimated Timeline

**Total Effort:** **18-22 days**

**Breakdown:**
- Dependency injection refactoring: 5-6 days
- Universal training pipeline: 6-8 days
- Model storage enhancements: 3-4 days
- Backtesting integration: 2-3 days
- Testing and optimization: 2-3 days

**Critical Path:** Dependency injection → Universal training → Model storage → Integration testing

## 8. Prerequisites and Preparation

### 8.1 Technical Prerequisites

1. **Code Review:** Complete audit of existing coupling issues
2. **Test Coverage:** Ensure comprehensive test coverage for refactored components
3. **Performance Baseline:** Benchmark current single-symbol training performance
4. **Configuration Design:** Design symbol-specific configuration schema

### 8.2 Development Environment Setup

```bash
# Create feature branch
git checkout -b feature/multi-symbol-training

# Set up isolated testing environment
python -m venv venv-multi-symbol
source venv-multi-symbol/bin/activate
pip install -r requirements.txt

# Create test data for multiple symbols
python scripts/generate_test_data.py --symbols AAPL,MSFT,GOOGL --timeframe 1h
```

### 8.3 Success Criteria

**Definition of Done:**
- [ ] Universal models can be trained on 5+ symbols simultaneously
- [ ] Model storage supports both universal and symbol-specific models
- [ ] Backtesting engine loads appropriate model (universal → symbol-specific fallback)
- [ ] All existing single-symbol tests pass
- [ ] Performance benchmarks meet or exceed baseline
- [ ] Documentation updated for new multi-symbol capabilities

---

**Document Version:** 1.0  
**Last Updated:** 2025-06-24  
**Next Review:** After Phase 1 completion