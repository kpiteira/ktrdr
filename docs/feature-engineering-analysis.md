# KTRDR Feature Engineering Deep Analysis

## Executive Summary

**CRITICAL FINDING: The neural network receives BOTH fuzzy memberships AND raw engineered features, creating a mixed input that violates the neuro-fuzzy architecture principle.**

## 1. Feature Engineering Module Analysis

### Location: `ktrdr/training/feature_engineering.py`

The `FeatureEngineer.prepare_features()` method creates **5 distinct types of features**:

### 1.1 Core Fuzzy Membership Features (Lines 43-46)
**Source:** `_extract_fuzzy_features(fuzzy_data)`
**Content:** Direct fuzzy membership values (0.0 to 1.0)
**Example Features:**
- `rsi_oversold` (0.8 = strong oversold membership)
- `rsi_neutral` (0.1 = weak neutral membership) 
- `rsi_overbought` (0.0 = no overbought membership)
- `macd_negative` (0.6 = moderate negative momentum)
- `sma_above` (0.9 = price strongly above SMA)

### 1.2 Price Context Features (Lines 49-54) - **RAW ENGINEERED VALUES**
**Source:** `_extract_price_features(price_data, indicators)`
**Content:** Raw mathematical ratios and calculations
**Hardcoded Parameters:**
- MA periods: `["sma_20", "sma_50", "ema_20"]` (Line 167)
- Momentum periods: `[5, 10, 20]` (Line 174)
- Volatility window: `20` periods (Line 190)

**Example Features:**
- `price_to_sma_20_ratio`: 1.05 (price 5% above SMA)
- `price_to_sma_50_ratio`: 1.12 (price 12% above SMA)
- `roc_5`: 0.023 (2.3% price change in 5 periods)
- `roc_10`: 0.045 (4.5% price change in 10 periods)
- `roc_20`: 0.087 (8.7% price change in 20 periods)
- `daily_price_position`: 0.8 (price at 80% of daily range)
- `volatility_20`: 0.025 (2.5% volatility)

### 1.3 Volume Features (Lines 57-60) - **RAW ENGINEERED VALUES**
**Source:** `_extract_volume_features(price_data)`
**Content:** Raw volume calculations
**Hardcoded Parameters:**
- Volume SMA period: `20` (Line 231)
- Volume change period: `5` (Line 239)

**Example Features:**
- `volume_ratio_20`: 1.5 (volume 50% above 20-period average)
- `volume_change_5`: 0.25 (25% volume increase over 5 periods)
- `obv_normalized`: 0.6 (normalized On-Balance Volume)

### 1.4 Raw Indicator Features (Lines 63-68) - **DISABLED BY DEFAULT**
**Source:** `_extract_indicator_features(indicators)`
**Config:** `include_raw_indicators: false` (Line 91 in strategy config)
**Content:** Normalized raw indicator values (if enabled)

### 1.5 Temporal Features (Lines 71-77) - **LAG OF FUZZY VALUES**
**Source:** `_extract_temporal_features(fuzzy_data, lookback)`
**Config:** `lookback_periods: 3` (Line 92 in strategy config)
**Content:** Historical fuzzy memberships

**Example Features:**
- `rsi_oversold_lag1`: 0.6 (RSI oversold membership 1 period ago)
- `rsi_oversold_lag2`: 0.4 (RSI oversold membership 2 periods ago)
- `macd_negative_lag1`: 0.8 (MACD negative membership 1 period ago)

## 2. Complete Data Flow Analysis

### ACTUAL DATA FLOW:
```
Raw OHLCV Data
    ↓
1. Technical Indicators (IndicatorEngine.apply)
   → RSI: 25.0, MACD: -0.08, SMA_20: 150.5, etc.
    ↓
2. Fuzzy Memberships (FuzzyEngine.fuzzify) 
   → rsi_oversold: 0.8, macd_negative: 0.6, sma_below: 0.3
    ↓
3. Feature Engineering (FeatureEngineer.prepare_features)
   → COMBINES: Fuzzy (0-1) + Raw ratios (any value) + Volume ratios
    ↓
4. Feature Scaling (StandardScaler/MinMaxScaler)
   → All features normalized to similar ranges
    ↓
5. Neural Network (MLPTradingModel.forward)
   → Mixed input tensor of fuzzy + raw features
```

### Key Transformation Locations:

**Step 1:** `train_strategy.py:77`
```python
indicators = self._calculate_indicators(price_data, config["indicators"])
```

**Step 2:** `train_strategy.py:88`
```python
fuzzy_data = self._generate_fuzzy_memberships(indicators, config["fuzzy_sets"])
```

**Step 3:** `train_strategy.py:99-104`
```python
features, feature_names, feature_scaler = self._engineer_features(
    fuzzy_data, indicators, price_data, config.get("model", {}).get("features", {})
)
```

**Step 4:** `feature_engineering.py:108-116`
```python
feature_matrix = np.column_stack(non_empty_features)
if self.config.get("scale_features", True):
    feature_matrix = self._scale_features(feature_matrix)
return torch.FloatTensor(feature_matrix), feature_names
```

## 3. Neural Network Input Analysis

### Location: `ktrdr/neural/models/mlp.py`

**Input Expectation:** `build_model(input_size: int)` (Line 16)
- The neural network expects a flat tensor of features
- **No distinction** between fuzzy vs raw features
- Input size auto-calculated from feature matrix shape

**Critical Issue in MLPTradingModel.prepare_features():**
```python
# Lines 80-92: DUPLICATES the same FeatureEngineer logic!
from ...training.feature_engineering import FeatureEngineer
engineer = FeatureEngineer(feature_config)
features_tensor, feature_names = engineer.prepare_features(
    fuzzy_data=fuzzy_data, indicators=indicators, price_data=price_data
)
```

**This means the model uses the SAME mixed features during inference!**

## 4. Configuration Analysis

### Strategy Config: `strategies/neuro_mean_reversion.yaml`

**Feature Configuration (Lines 88-94):**
```yaml
features:
  include_price_context: true      # ENABLES raw price ratios
  include_volume_context: true     # ENABLES raw volume ratios  
  include_raw_indicators: false    # DISABLED (good)
  lookback_periods: 3              # ENABLES fuzzy lags
  scale_features: true             # NORMALIZES everything together
```

**Default Behavior:**
- Fuzzy memberships: ✅ **ENABLED** (always included)
- Price context: ✅ **ENABLED** by default 
- Volume context: ✅ **ENABLED** by default
- Raw indicators: ❌ **DISABLED** by default

## 5. Evidence Collection

### 5.1 Mixed Feature Evidence

**File:** `feature_engineering.py:108`
```python
feature_matrix = np.column_stack(non_empty_features)
```
**Evidence:** All feature types concatenated into single matrix

**File:** `feature_engineering.py:167-171`
```python
for ma_col in ["sma_20", "sma_50", "ema_20"]:
    if ma_col in indicators.columns:
        price_ratio = close / indicators[ma_col]  # RAW RATIO, NOT FUZZY!
        features.append(price_ratio.values)
        names.append(f"price_to_{ma_col}_ratio")
```
**Evidence:** Raw mathematical ratios mixed with fuzzy values

### 5.2 Scaling Evidence

**File:** `feature_engineering.py:115-116`
```python
if self.config.get("scale_features", True):
    feature_matrix = self._scale_features(feature_matrix)
```
**Evidence:** All features scaled together, masking the fuzzy vs raw distinction

### 5.3 Neural Network Coupling Evidence

**File:** `mlp.py:80-81`
```python
from ...training.feature_engineering import FeatureEngineer
```
**Evidence:** Model directly imports training module, creating circular dependency

## 6. Key Questions Answered

### Q1: Does the neural network receive fuzzy memberships only, raw features only, or both?
**A: BOTH** - The network receives a mixed input of:
- Fuzzy memberships (0-1 values)  
- Raw price ratios (any positive value)
- Raw volume ratios (any positive value)
- Fuzzy membership lags (0-1 values)

### Q2: What's the ratio of fuzzy vs non-fuzzy inputs?
**A: Approximately 40% fuzzy, 60% raw** (for default config):
- **Fuzzy features:** ~9 (3 indicators × 3 fuzzy sets each)
- **Raw price features:** ~7 (3 ratios + 3 momentum + 1 position + 1 volatility)
- **Raw volume features:** ~3 (ratio + change + OBV)
- **Fuzzy lags:** ~18 (9 fuzzy × 2 lags)
- **Total:** ~37 features (9+18=27 fuzzy, 7+3=10 raw)

### Q3: Are engineered features fuzzified before going to the NN?
**A: NO** - Raw engineered features bypass fuzzy logic entirely and go directly to the neural network.

### Q4: Could we remove feature engineering entirely and only use fuzzy memberships?
**A: YES, but with modifications:**
- Remove `include_price_context: true`
- Remove `include_volume_context: true` 
- Keep only fuzzy memberships and their lags
- Would require retraining all models

### Q5: What would break if we deleted the feature engineering step?
**A: Everything** - Feature engineering is mandatory because:
1. `MLPTradingModel.prepare_features()` imports and uses `FeatureEngineer`
2. Model storage expects feature names and scaler from feature engineering
3. All trained models expect the specific feature dimensions

## 7. Current Data Flow Diagram

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   OHLCV Data    │───▶│  IndicatorEngine │───▶│   Raw Indicators    │
│                 │    │                  │    │  RSI: 25.0          │
└─────────────────┘    └──────────────────┘    │  MACD: -0.08        │
                                               │  SMA_20: 150.5      │
                                               └─────────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│ Fuzzy Features  │◄───│   FuzzyEngine    │◄───│                     │
│ rsi_oversold:0.8│    │                  │    │                     │
│ macd_neg: 0.6   │    └──────────────────┘    │                     │
│ sma_below: 0.3  │                             │                     │
└─────────────────┘                             │                     │
         │                                      │                     │
         │              ┌─────────────────────┐ │                     │
         │              │ Raw Price Features  │ │                     │
         │              │ price/sma20: 1.05   │◄┘                     │
         │              │ roc_5: 0.023        │                       │
         │              │ volatility: 0.025   │                       │
         │              └─────────────────────┘                       │
         │                       │                                    │
         │                       │                                    │
         │              ┌─────────────────────┐                       │
         │              │ Raw Volume Features │                       │
         │              │ vol_ratio: 1.5      │                       │
         │              │ vol_change: 0.25    │                       │
         │              │ obv_norm: 0.6       │                       │
         │              └─────────────────────┘                       │
         │                       │                                    │
         ▼                       ▼                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                    FeatureEngineer.prepare_features()               │
│                                                                     │
│  1. Fuzzy Features (9)     │  4. Fuzzy Lags (18)                   │
│  2. Price Features (7)     │  5. Volume Features (3)               │
│  3. np.column_stack() → Mixed Feature Matrix                       │
│  4. StandardScaler() → Normalized Mixed Features                   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                        ┌─────────────────────┐
                        │  Neural Network     │
                        │  Input Tensor       │
                        │  Shape: [N, 37]     │
                        │                     │
                        │  MIXED INPUT:       │
                        │  - Fuzzy: 0.8       │
                        │  - Raw: 1.05        │
                        │  - Fuzzy: 0.6       │
                        │  - Raw: 0.025       │
                        │  - etc...           │
                        └─────────────────────┘
```

## 8. Assessment and Recommendations

### 8.1 Current Architecture Assessment

**PROBLEM: Architectural Inconsistency**
The system is marketed as "neuro-fuzzy" but actually implements a "neural network with mixed fuzzy and raw inputs." This violates the neuro-fuzzy principle where fuzzy logic should be the primary feature representation.

**EVIDENCE:**
1. Raw price ratios (`price/sma_20: 1.05`) are NOT fuzzified
2. Raw volume calculations bypass fuzzy logic entirely  
3. Feature scaling masks the conceptual difference between fuzzy and raw
4. The neural network has no awareness of input types

### 8.2 Feature Engineering Necessity Analysis

**VERDICT: Feature Engineering is CURRENTLY NECESSARY but ARCHITECTURALLY WRONG**

**Why it's necessary:**
1. All models expect the specific 37-feature input dimension
2. `MLPTradingModel.prepare_features()` hardcodes the FeatureEngineer dependency
3. Model storage assumes feature names and scaler objects exist
4. Removing it would break all existing trained models

**Why it's architecturally wrong:**
1. Mixes paradigms: fuzzy logic (semantic) with raw math (statistical)
2. Creates inconsistent scaling (0-1 fuzzy values with unbounded ratios)
3. Violates single responsibility principle (doing both fuzzy AND feature engineering)
4. Makes the system harder to understand and debug

### 8.3 Specific Recommendations

#### Recommendation 1: Pure Neuro-Fuzzy Architecture
**Goal:** Remove raw feature engineering, use only fuzzy memberships

**Changes needed:**
1. Set `include_price_context: false` in strategy configs
2. Set `include_volume_context: false` in strategy configs  
3. Create volume and momentum fuzzy sets instead of raw ratios
4. Retrain all models with fuzzy-only features

**Benefits:**
- Conceptually cleaner neuro-fuzzy architecture
- All inputs have semantic meaning (memberships)
- Easier to interpret model behavior
- Consistent 0-1 input ranges

**Risks:**
- May reduce model performance (fewer features)
- Requires retraining all existing models
- Need to design appropriate fuzzy sets for volume/momentum

#### Recommendation 2: Hybrid Architecture (Status Quo Fix)
**Goal:** Keep mixed approach but make it explicit and organized

**Changes needed:**
1. Separate fuzzy and raw features in model architecture
2. Use different scaling for fuzzy (none) vs raw (standard) features  
3. Document the hybrid approach clearly
4. Add feature type metadata to model storage

**Benefits:**
- Preserves existing model performance
- Makes mixed approach explicit
- Easier to maintain current system

**Risks:**
- Perpetuates architectural confusion
- Still violates neuro-fuzzy principles

#### Recommendation 3: Parallel Feature Engineering (Future-Proof)
**Goal:** Support both pure fuzzy and hybrid modes

**Changes needed:**
1. Create `FuzzyFeatureEngineer` (fuzzy only) vs `HybridFeatureEngineer` (mixed)
2. Add feature mode configuration to strategy files
3. Support both architectures in model loading
4. Migrate strategies gradually

**Benefits:**
- Supports both paradigms
- Enables gradual migration
- Future-proof architecture

**Risks:**
- Increases complexity
- Requires significant refactoring

### 8.4 Multi-Symbol Training Impact

**CRITICAL ISSUE:** The current mixed feature engineering makes multi-symbol training MORE complex because:

1. **Symbol-specific parameters:** Different assets need different ratio calculations
2. **Asset class differences:** Forex doesn't have volume, crypto has different patterns
3. **Scaling conflicts:** Mixing fuzzy (0-1) with raw (unbounded) creates scaling issues
4. **Feature alignment:** Hard to align features across symbols with different characteristics

**For multi-symbol training, I recommend pursuing Recommendation 1 (Pure Neuro-Fuzzy) because:**
- Fuzzy memberships are asset-agnostic (RSI oversold means the same thing for any symbol)
- Easier to align features across symbols
- Conceptually cleaner for universal model training
- Avoids symbol-specific parameter tuning

## 9. Conclusion

The KTRDR training pipeline currently creates a **mixed feature set** combining fuzzy memberships with raw engineered features. While this may provide performance benefits, it violates the neuro-fuzzy architecture principle and creates unnecessary complexity for multi-symbol training.

**The neural network receives approximately 37 features:**
- 27 fuzzy-based features (73%)
- 10 raw engineered features (27%) 

**For multi-symbol training success, I recommend prioritizing a pure neuro-fuzzy approach to eliminate symbol-specific parameter dependencies and create a truly universal feature representation.**

---

**Document Version:** 1.0  
**Analysis Date:** 2025-06-24  
**Files Analyzed:** 
- `ktrdr/training/feature_engineering.py`
- `ktrdr/neural/models/mlp.py` 
- `ktrdr/training/train_strategy.py`
- `strategies/neuro_mean_reversion.yaml`