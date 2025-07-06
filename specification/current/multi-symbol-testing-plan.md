# Multi-Symbol Testing Plan

## 🧪 **Incremental Multi-Symbol Testing Strategy**

### **Test Plan Philosophy**
- **Start with single symbol, gradually add symbols**
- **Test data loading, feature engineering, and training at each layer**
- **Use real market data with proper symbol selection**
- **Verify balanced sampling and symbol embedding functionality**
- **Test cross-symbol generalization capabilities**
- **Validate memory and performance scaling**

### **Available Data Analysis**
Based on `/Users/karl/Documents/dev/ktrdr2/data/`:

**Forex Pairs** (Excellent for multi-symbol testing):
- **EURUSD**: `5m`, `1h`, `1d` (major pair, high liquidity)
- **GBPUSD**: `1h`, `1d` (major pair, different characteristics)
- **USDJPY**: `1h`, `1d` (major pair, different base currency)

**US Stocks** (Good for diverse symbol testing):
- **AAPL**: `1h`, `1d` (tech stock, 2020-2025 coverage)
- **MSFT**: `1h`, `1d` (tech stock, similar sector)
- **TSLA**: `15m`, `30m`, `1h`, `1d` (volatile, different characteristics)

**Strategy**: Use **forex majors** (EURUSD, GBPUSD, USDJPY) for primary testing as they have similar timeframes but different market characteristics.

---

## **🚨 CRITICAL REQUIREMENTS FOR MULTI-SYMBOL TESTING**

### **Data Requirements**
- **Minimum 2 months date range** - Multi-symbol needs more data for proper label distribution across symbols
- **Overlapping timeframes** - All symbols must have data for the same timeframes
- **Sufficient sample size** - Each symbol needs adequate representation in training

### **Memory Considerations**
- **3 symbols = 3x memory usage** minimum
- **Combined features** = (symbol_count × features_per_symbol) + embedding_dimensions
- **Balanced sampling** = equal representation requires adequate data per symbol

### **Expected Behavior Changes**
- **Training time**: 2-3x longer due to balanced sampling and larger datasets
- **Model size**: Larger due to symbol embeddings (16-32 additional parameters per symbol)
- **Feature count**: Same per symbol, but with symbol context
- **Convergence**: May be slower initially as model learns symbol-specific patterns

---

## **Phase 1: Single Symbol Baseline (Multi-Symbol Infrastructure)**
**Goal**: Verify multi-symbol training works with 1 symbol (should match single-symbol results)

### Setup
```bash
# Create a test strategy for single symbol multi-symbol training
cp strategies/neuro_mean_reversion.yaml strategies/test_multi_single_eurusd.yaml
```

**Edit `strategies/test_multi_single_eurusd.yaml`**:
```yaml
name: "test_multi_single_eurusd"
description: "Single symbol test using multi-symbol infrastructure"

training_data:
  symbols:
    mode: "multi_symbol"
    list: ["EURUSD"]  # Single symbol via multi-symbol path
  timeframes:
    mode: "single" 
    timeframe: "1h"

# Add symbol embedding configuration
model:
  type: "mlp"
  symbol_embedding_dim: 16  # Small embedding for testing
  architecture:
    hidden_layers: [32, 16]  # Smaller network for faster testing
    dropout: 0.2
  training:
    epochs: 20  # Reduced for faster testing
    batch_size: 16
    learning_rate: 0.001
```

### Test Command
```bash
# Use 2 month minimum for multi-symbol (more than 1 month for single-symbol)
ktrdr models train strategies/test_multi_single_eurusd.yaml --start-date 2024-01-01 --end-date 2024-03-01 --verbose
```

### Manual Verification Steps
1. **Check multi-symbol detection**: Look for "Multi-symbol training enabled: EURUSD"
2. **Check API endpoint**: Should use `/trainings/start-multi-symbol` endpoint
3. **Check data loading**: Look for "Loading market data for all symbols: EURUSD"
4. **Check symbol embedding**: Model should include embedding layer with 16 dimensions
5. **Check balanced sampling**: Should mention balanced sampling even with 1 symbol

### Expected Outputs
- **Features**: Same count as regular single-symbol (~6-10 features)
- **Model architecture**: Should mention "multi_symbol_mlp_1symbols"
- **Training time**: Slightly longer due to multi-symbol infrastructure overhead
- **Memory usage**: Slightly higher due to symbol embeddings

### What to Watch For
- Multi-symbol infrastructure shouldn't break single-symbol functionality
- Performance should be comparable to regular single-symbol training
- No errors about symbol indices or embedding lookups
- Balanced sampling should work correctly (even with 1 symbol)

---

## **Phase 2: Simple Two Symbol Test**
**Goal**: Test basic multi-symbol functionality with two similar symbols

### Setup
```bash
cp strategies/test_multi_single_eurusd.yaml strategies/test_multi_dual_forex.yaml
```

**Edit `strategies/test_multi_dual_forex.yaml`**:
```yaml
name: "test_multi_dual_forex"
training_data:
  symbols:
    mode: "multi_symbol"
    list: ["EURUSD", "GBPUSD"]  # Two major forex pairs
  timeframes:
    mode: "single" 
    timeframe: "1h"

model:
  symbol_embedding_dim: 16
  architecture:
    hidden_layers: [64, 32]  # Slightly larger for 2 symbols
  training:
    epochs: 25
```

### Test Command
```bash
ktrdr models train strategies/test_multi_dual_forex.yaml --start-date 2024-01-01 --end-date 2024-03-01 --verbose
```

### Manual Verification Steps
1. **Check data loading**: "Loading market data for all symbols..." should list both symbols
2. **Check balanced sampling**: Should mention equal representation between symbols
3. **Check symbol distribution**: Look for percentage distribution (should be ~50%/50%)
4. **Check per-symbol metrics**: Should report accuracy for EURUSD and GBPUSD separately

### Expected Outputs
- **Combined dataset**: Should combine data from both symbols
- **Symbol distribution**: Approximately equal (45-55% each symbol)
- **Per-symbol metrics**: Separate accuracy/loss for each symbol
- **Model architecture**: "multi_symbol_mlp_2symbols"
- **Training time**: ~2x longer than single symbol

### How to Verify Balanced Sampling
Look for output like:
```
Combined dataset: 5000 total samples
  EURUSD: 2500 samples (50.0%)
  GBPUSD: 2500 samples (50.0%)
```

### What to Watch For
- Balanced sampling should prevent one symbol from dominating
- Per-symbol accuracy should be reasonable (>40% for each)
- No symbol should have 0 samples in validation set
- Symbol embeddings should learn different representations

---

## **Phase 3: Three Symbol Test (Core Multi-Symbol)**
**Goal**: Test full multi-symbol capability with three diverse symbols

### Setup
```bash
cp strategies/test_multi_dual_forex.yaml strategies/test_multi_triple_forex.yaml
```

**Edit `strategies/test_multi_triple_forex.yaml`**:
```yaml
name: "test_multi_triple_forex"
training_data:
  symbols:
    mode: "multi_symbol"
    list: ["EURUSD", "GBPUSD", "USDJPY"]  # Three major pairs with different characteristics
  timeframes:
    mode: "single" 
    timeframe: "1h"

model:
  symbol_embedding_dim: 32  # Larger embedding for 3 symbols
  architecture:
    hidden_layers: [128, 64, 32]  # Larger network for 3 symbols
  training:
    epochs: 30
    batch_size: 32
```

### Test Command
```bash
ktrdr models train strategies/test_multi_triple_forex.yaml --start-date 2024-01-01 --end-date 2024-03-01 --verbose
```

### Manual Verification Steps
1. **Check symbol distribution**: Should be ~33% each (30-37% acceptable)
2. **Check per-symbol performance**: Each symbol should achieve >35% accuracy
3. **Check cross-symbol generalization**: Model should work on all three symbols
4. **Check memory usage**: Should be manageable (3x single symbol)

### Expected Symbol Characteristics
- **EURUSD**: European market hours, EUR base currency
- **GBPUSD**: British market characteristics, GBP volatility
- **USDJPY**: Asian market influence, carry trade effects

### What to Watch For
- Symbol embeddings should capture these different characteristics
- No single symbol should dominate the loss function
- Training should converge despite increased complexity
- Memory usage should scale approximately linearly

---

## **Phase 4: Multi-Symbol + Multi-Timeframe Combined**
**Goal**: Test the full Phase 1 + Phase 2 combination

### Setup
```bash
cp strategies/test_multi_triple_forex.yaml strategies/test_multi_full_3tf.yaml
```

**Edit `strategies/test_multi_full_3tf.yaml`**:
```yaml
name: "test_multi_full_3tf"
training_data:
  symbols:
    mode: "multi_symbol"
    list: ["EURUSD", "GBPUSD", "USDJPY"]
  timeframes:
    mode: "multi_timeframe"
    list: ["1h", "1d"]  # Only use timeframes all symbols have
    base_timeframe: "1h"

model:
  symbol_embedding_dim: 32
  architecture:
    hidden_layers: [256, 128, 64]  # Larger for combined complexity
  training:
    epochs: 40
    batch_size: 64  # Larger batches for stability
```

### Test Command
```bash
ktrdr models train strategies/test_multi_full_3tf.yaml --start-date 2024-01-01 --end-date 2024-04-01 --verbose
```

### Manual Verification Steps
1. **Check feature explosion**: Features should be timeframes × base_features (e.g., 12 base → 24 features)
2. **Check symbol + timeframe combination**: Should handle both dimensions properly
3. **Check memory scaling**: Memory should be (symbols × timeframes × base_memory)
4. **Check training stability**: Should converge despite high complexity

### Expected Complexity
- **Input size**: (base_features × timeframes) + symbol_embedding_dim
- **Total complexity**: 3 symbols × 2 timeframes × base features + embeddings
- **Training time**: 4-6x baseline single symbol/timeframe

### What to Watch For
- Feature explosion leading to overfitting
- Memory pressure from large combined datasets
- Training instability from high-dimensional inputs
- Convergence taking significantly longer

---

## **Phase 5: Cross-Symbol Generalization Test**
**Goal**: Test if models trained on some symbols can trade others

### Setup - Training Set
```bash
cp strategies/test_multi_triple_forex.yaml strategies/test_generalization_train.yaml
```

**Edit `strategies/test_generalization_train.yaml`**:
```yaml
name: "test_generalization_train"
training_data:
  symbols:
    mode: "multi_symbol"
    list: ["EURUSD", "GBPUSD"]  # Train on only 2 symbols
```

### Setup - Test Set
```bash
cp strategies/test_multi_single_eurusd.yaml strategies/test_generalization_test.yaml
```

**Edit `strategies/test_generalization_test.yaml`**:
```yaml
name: "test_generalization_test"
training_data:
  symbols:
    mode: "multi_symbol"
    list: ["USDJPY"]  # Test on unseen symbol
```

### Test Commands
```bash
# Step 1: Train on EURUSD + GBPUSD
ktrdr models train strategies/test_generalization_train.yaml --start-date 2024-01-01 --end-date 2024-03-01 --verbose

# Step 2: Note the model path from output
# Step 3: Test generalization (this would require backtesting infrastructure)
# For now, just verify the model can handle different symbols in training
ktrdr models train strategies/test_generalization_test.yaml --start-date 2024-01-01 --end-date 2024-03-01 --verbose
```

### Manual Verification
1. **Compare symbol-specific accuracy**: EURUSD/GBPUSD vs USDJPY performance
2. **Check feature importance**: Should show universal vs symbol-specific patterns
3. **Check embedding similarity**: Similar symbols should have similar embeddings

### What to Look For
- **Universal patterns**: Features that work across all symbols
- **Symbol-specific patterns**: Features that only work for specific symbols
- **Embedding clustering**: Similar symbols should have similar embedding vectors
- **Generalization gap**: Performance difference between trained and unseen symbols

---

## **Phase 6: Memory and Performance Scaling**
**Goal**: Test system limits and performance characteristics

### Test 1 - Memory Scaling
```bash
cp strategies/test_multi_triple_forex.yaml strategies/test_memory_scaling.yaml
```

**Edit for large dataset**:
```yaml
training_data:
  symbols:
    mode: "multi_symbol"
    list: ["EURUSD", "GBPUSD", "USDJPY"]
  timeframes:
    mode: "multi_timeframe"
    list: ["1h", "1d"]

model:
  training:
    epochs: 50
    batch_size: 128  # Large batches
```

### Test Command - Large Dataset
```bash
# 6 month dataset for memory testing
ktrdr models train strategies/test_memory_scaling.yaml --start-date 2023-06-01 --end-date 2023-12-01 --verbose
```

### Test 2 - Symbol Count Scaling
Create configurations for:
- **2 symbols**: EURUSD, GBPUSD
- **3 symbols**: EURUSD, GBPUSD, USDJPY
- **Stock symbols**: AAPL, MSFT, TSLA (if data permits)

### Performance Metrics to Track
1. **Memory usage**: Peak memory during training
2. **Training time**: Time per epoch scaling
3. **Convergence**: Epochs needed to reach stable accuracy
4. **Model size**: Final model file size

### Expected Scaling
- **Memory**: Should scale approximately linearly with (symbols × timeframes)
- **Training time**: Should scale sub-linearly due to vectorization
- **Convergence**: May require more epochs with more symbols
- **Model size**: Should increase with symbol count (embeddings)

---

## **Phase 7: Edge Cases and Error Handling**
**Goal**: Test failure scenarios and boundary conditions

### Test 1 - Imbalanced Symbol Data
```bash
cp strategies/test_multi_triple_forex.yaml strategies/test_imbalanced_data.yaml
```

**Test with date ranges where symbols have different data availability**:
```bash
# Use a range where one symbol might have less data
ktrdr models train strategies/test_imbalanced_data.yaml --start-date 2023-01-01 --end-date 2023-02-01 --verbose
```

### Test 2 - Symbol Embedding Dimensions
Test different embedding sizes:
- `symbol_embedding_dim: 4` (very small)
- `symbol_embedding_dim: 64` (large)
- `symbol_embedding_dim: 0` (should fail gracefully)

### Test 3 - Invalid Symbol Combinations
```yaml
symbols:
  mode: "multi_symbol"
  list: ["EURUSD", "NONEXISTENT"]  # One valid, one invalid symbol
```

### What to Watch For
- **Graceful degradation**: System should handle missing data appropriately
- **Error messages**: Should be clear about what failed and why
- **Memory leaks**: No memory accumulation during failed training
- **Resource cleanup**: Proper cleanup on training failure

---

## **Success Criteria Summary**

### Phase 1 (Single Symbol Multi-Symbol Infrastructure)
- [ ] **Functional**: Training completes using multi-symbol API endpoints
- [ ] **Performance**: Comparable to single-symbol baseline (within 5% accuracy)
- [ ] **Architecture**: Model includes symbol embeddings
- [ ] **API**: Uses `/trainings/start-multi-symbol` endpoint

### Phase 2 (Two Symbol)
- [ ] **Balanced Sampling**: Approximately equal symbol representation (45-55% each)
- [ ] **Per-Symbol Metrics**: Separate accuracy tracking for each symbol
- [ ] **Performance**: Each symbol achieves >40% accuracy
- [ ] **Training**: Converges within 2x baseline time

### Phase 3 (Three Symbol)
- [ ] **Symbol Distribution**: ~33% per symbol (30-37% acceptable)
- [ ] **Cross-Symbol Learning**: Model performs reasonably on all symbols
- [ ] **Memory**: Manageable memory usage (<8GB)
- [ ] **Stability**: Training converges consistently

### Phase 4 (Multi-Symbol + Multi-Timeframe)
- [ ] **Feature Integration**: Handles both symbol and timeframe dimensions
- [ ] **Complexity Management**: Trains successfully despite high dimensionality
- [ ] **Performance**: Achieves reasonable accuracy (>45%) on combined task
- [ ] **Resource Usage**: Memory and time scale appropriately

### Phase 5 (Generalization)
- [ ] **Cross-Symbol Performance**: Model works on unseen symbols (>35% accuracy)
- [ ] **Universal Patterns**: Identifies features that work across symbols
- [ ] **Symbol Specificity**: Learns symbol-specific characteristics
- [ ] **Embedding Quality**: Similar symbols have similar embeddings

### Phase 6 (Scaling)
- [ ] **Linear Memory Scaling**: Memory increases predictably with symbols
- [ ] **Training Time**: Scales sub-linearly with symbol count
- [ ] **Large Dataset Handling**: Processes 6+ month datasets successfully
- [ ] **Model Size**: Reasonable file size increases

### Phase 7 (Edge Cases)
- [ ] **Error Handling**: Graceful failure with clear error messages
- [ ] **Data Imbalance**: Handles unequal symbol data appropriately
- [ ] **Resource Cleanup**: No memory leaks or resource accumulation
- [ ] **Boundary Conditions**: Stable behavior at system limits

---

## **Quick Action Items**

1. **Start with Phase 1** - Verify multi-symbol infrastructure with single symbol
2. **Progress incrementally** - Don't skip phases if earlier ones fail
3. **Monitor memory usage** - Multi-symbol uses significantly more memory
4. **Check balanced sampling** - Key differentiator from single-symbol training
5. **Validate per-symbol metrics** - Ensure each symbol contributes to learning
6. **Test cross-symbol patterns** - Look for universal vs symbol-specific features

## **Emergency Stop Criteria**

**Stop testing and investigate if you see**:
- Memory usage >16GB during training (multi-symbol needs more memory)
- Training time >30 minutes for 2-month datasets
- Any symbol consistently getting 0% accuracy
- Symbol distribution severely imbalanced (e.g., 90%/10% for 2 symbols)
- Python crashes or out-of-memory errors
- Model size >100MB (embeddings shouldn't cause excessive growth)
- Validation accuracy decreasing over time (overfitting to symbol artifacts)

---

## **Data Quality Checklist**

Before running any multi-symbol tests:

### Symbol Data Verification
```bash
# Check that all symbols have data for the same time periods
ls -la data/ | grep EURUSD
ls -la data/ | grep GBPUSD  
ls -la data/ | grep USDJPY

# Verify timeframe overlap
head -5 data/EURUSD_1h.csv
head -5 data/GBPUSD_1h.csv
head -5 data/USDJPY_1h.csv
```

### Date Range Validation
- **Minimum 2 months** for multi-symbol training
- **Verify overlap**: All symbols must have data for the same dates
- **Check market hours**: Forex vs stocks have different trading hours
- **Weekend handling**: Ensure consistent weekend gap handling

### Symbol Characteristics
- **EURUSD**: Major pair, high liquidity, European hours
- **GBPUSD**: British pound volatility, Brexit impacts
- **USDJPY**: Asian market influence, carry trade dynamics
- **US Stocks**: Different market hours, earnings impacts

**Remember**: Multi-symbol training is fundamentally different from single-symbol. The goal is to learn patterns that work across multiple instruments while respecting their individual characteristics. Take time to understand the balanced sampling and per-symbol metrics!