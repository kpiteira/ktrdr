# Strategy Audit - M8 Cleanup

**Date:** 2026-01-08
**Branch:** `feature/strategy-grammar-v3-m8`

## Summary

- **Total strategies:** 74
- **V3 format:** 1 (`v3_test_example.yaml`)
- **V2 format:** 73

## Strategy Categories

### Category 1: V3 Test Examples (KEEP - Already V3)

| Strategy | Status | Action | Notes |
|----------|--------|--------|-------|
| v3_test_example.yaml | V3 | KEEP | Minimal v3 example for E2E testing |

### Category 2: V1.5 Experiment Suite (MIGRATE)

These 24 strategies are part of a controlled experiment suite with fixed parameters. They're used by unit tests (`tests/unit/test_v15_template.py`) and represent a systematic indicator combination study.

| Strategy | Status | Action | Notes |
|----------|--------|--------|-------|
| v15_template.yaml | V2 | MIGRATE | Template file, referenced by tests |
| v15_rsi_only.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_stochastic_only.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_williams_only.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_mfi_only.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_adx_only.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_aroon_only.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_cmf_only.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_rvi_only.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_di_only.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_rsi_adx.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_rsi_stochastic.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_rsi_williams.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_rsi_mfi.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_adx_aroon.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_adx_di.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_stochastic_williams.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_mfi_cmf.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_rsi_cmf.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_adx_rsi.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_aroon_rvi.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_rsi_adx_stochastic.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_mfi_adx_aroon.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_williams_stochastic_cmf.yaml | V2 | MIGRATE | Part of v1.5 experiment |
| v15_test_analytics.yaml | V2 | DELETE | Not in v1.5 spec, appears to be one-off |

### Category 3: Featured/Example Strategies (MIGRATE)

These are well-documented strategies that serve as useful examples:

| Strategy | Status | Action | Notes |
|----------|--------|--------|-------|
| neuro_mean_reversion.yaml | V2 | MIGRATE | Multi-symbol/timeframe example with hypothesis |
| bollinger_squeeze.yaml | V2 | MIGRATE | Large/complex, good for advanced example |
| crypto_scalping.yaml | V2 | MIGRATE | Asset-specific example |
| rsi_mean_reversion.yaml | V2 | MIGRATE | Simple RSI strategy, good tutorial example |
| trend_momentum.yaml | V2 | MIGRATE | Multi-indicator example |
| volume_surge_momentum.yaml | V2 | MIGRATE | Volume-focused strategy |

### Category 4: Test Infrastructure Strategies (MIGRATE)

| Strategy | Status | Action | Notes |
|----------|--------|--------|-------|
| test_e2e_local_pull.yaml | V2 | MIGRATE | Minimal for fast E2E testing |

### Category 5: Universal/Generalization Models (MIGRATE)

| Strategy | Status | Action | Notes |
|----------|--------|--------|-------|
| universal_generalization_model.yaml | V2 | MIGRATE | Research into universal models |
| universal_zero_shot_model.yaml | V2 | MIGRATE | Research into zero-shot capability |

### Category 6: Complex Multi-Timeframe (MIGRATE OR DELETE)

| Strategy | Status | Action | Notes |
|----------|--------|--------|-------|
| mtf_forex_neural.yaml | V2 | DELETE | 30KB, overly complex, likely one-off experiment |
| multidim_squeeze_breakout.yaml | V2 | MIGRATE | Demonstrates multi-dimensional approach |

### Category 7: Timestamped Experiments (DELETE)

These appear to be one-off experiments with timestamps in names:

| Strategy | Status | Action | Notes |
|----------|--------|--------|-------|
| volatility_breakout_1765518026.yaml | V2 | DELETE | Timestamped experiment |
| volatility_breakout_v1_1734842466.yaml | V2 | DELETE | Timestamped experiment |
| volatility_breakout_multi_20241221.yaml | V2 | DELETE | Dated experiment |
| volatility_breakout_multi_v1_20241227.yaml | V2 | DELETE | Dated experiment |
| volatility_expansion_capture_20241218.yaml | V2 | DELETE | Dated experiment |
| volatility_momentum_confluence_20241211.yaml | V2 | DELETE | Dated experiment |
| volatility_momentum_confluence_20241213.yaml | V2 | DELETE | Dated experiment |
| volatility_momentum_confluence_20241220.yaml | V2 | DELETE | Dated experiment |
| volatility_momentum_confluence_20241224.yaml | V2 | DELETE | Dated experiment |
| volatility_momentum_fusion_20251213_013903.yaml | V2 | DELETE | Timestamped experiment |
| volume_momentum_breakout_20251211.yaml | V2 | DELETE | Dated experiment |
| volume_momentum_divergence_1765518926.yaml | V2 | DELETE | Timestamped experiment |

### Category 8: Named Strategy Variants (CONSOLIDATE)

Keep one representative from each family, delete duplicates:

**Volatility Breakout Family (keep volatility_breakout_v1.yaml):**

| Strategy | Status | Action | Notes |
|----------|--------|--------|-------|
| volatility_breakout_v1.yaml | V2 | MIGRATE | Primary volatility breakout |
| volatility_breakout_fisher_v1.yaml | V2 | DELETE | Fisher variant, duplicate concept |
| volatility_breakout_hunter_v1.yaml | V2 | DELETE | Hunter variant, duplicate concept |
| volatility_breakout_momentum_v1.yaml | V2 | DELETE | Momentum variant, duplicate concept |
| volatility_breakout_multi_v1.yaml | V2 | DELETE | Multi variant, duplicate concept |
| volatility_breakout_multidim_v1.yaml | V2 | DELETE | Multidim variant, duplicate concept |
| volatility_breakout_regime_v1.yaml | V2 | DELETE | Regime variant, duplicate concept |

**Mean Reversion Family (keep mean_reversion_momentum_v1.yaml):**

| Strategy | Status | Action | Notes |
|----------|--------|--------|-------|
| mean_reversion_momentum_v1.yaml | V2 | MIGRATE | Primary mean reversion |
| mean_reversion_momentum_v2.yaml | V2 | DELETE | Likely iteration, keep v1 |
| mean_reversion_confluence_v1.yaml | V2 | DELETE | Confluence variant |
| adaptive_volatility_breakout_v1.yaml | V2 | DELETE | Crossover concept |
| momentum_acceleration_v1.yaml | V2 | DELETE | Momentum-focused variant |

**Volatility/Volume Family (keep representative samples):**

| Strategy | Status | Action | Notes |
|----------|--------|--------|-------|
| volatility_squeeze_breakout_v1.yaml | V2 | MIGRATE | Distinct squeeze concept |
| volatility_squeeze_fisher_v1.yaml | V2 | DELETE | Fisher variant |
| volatility_trend_fusion_v1.yaml | V2 | DELETE | Trend fusion variant |
| volatility_volume_breakout_v1.yaml | V2 | DELETE | Volume crossover |
| volatility_volume_convergence_v1.yaml | V2 | DELETE | Volume convergence |
| volatility_momentum_confluence_v1.yaml | V2 | MIGRATE | Distinct confluence concept |
| volatility_momentum_conv_v1.yaml | V2 | DELETE | Conv variant |
| volatility_momentum_fusion_v1.yaml | V2 | DELETE | Fusion variant |
| volume_volatility_breakout_v1.yaml | V2 | DELETE | Reverse naming, duplicate |

**Volume Family (keep volume_momentum_breakout_v1.yaml):**

| Strategy | Status | Action | Notes |
|----------|--------|--------|-------|
| volume_momentum_breakout_v1.yaml | V2 | MIGRATE | Primary volume-momentum |
| volume_momentum_confluence_v1.yaml | V2 | DELETE | Confluence variant |
| volume_momentum_divergence_v1.yaml | V2 | MIGRATE | Distinct divergence concept |

**Trend Family:**

| Strategy | Status | Action | Notes |
|----------|--------|--------|-------|
| trend_momentum_divergence_v1.yaml | V2 | MIGRATE | Distinct trend-divergence |

---

## Final Summary

### Strategies to KEEP/MIGRATE (31 total)

1. **Already V3 (1):** v3_test_example.yaml
2. **V1.5 Experiment Suite (23):** v15_*.yaml (except v15_test_analytics.yaml)
3. **Featured Examples (6):** neuro_mean_reversion, bollinger_squeeze, crypto_scalping, rsi_mean_reversion, trend_momentum, volume_surge_momentum
4. **Test Infrastructure (1):** test_e2e_local_pull.yaml
5. **Universal Models (2):** universal_generalization_model, universal_zero_shot_model
6. **Multi-dimensional (1):** multidim_squeeze_breakout.yaml
7. **Representative Strategies (7):**
   - volatility_breakout_v1.yaml
   - mean_reversion_momentum_v1.yaml
   - volatility_squeeze_breakout_v1.yaml
   - volatility_momentum_confluence_v1.yaml
   - volume_momentum_breakout_v1.yaml
   - volume_momentum_divergence_v1.yaml
   - trend_momentum_divergence_v1.yaml

### Strategies to DELETE (43 total)

1. **Timestamped Experiments (12):** All *_YYYYMMDD*.yaml and *_timestamp.yaml
2. **Duplicate Variants (29):** Various *_v1.yaml that duplicate concepts
3. **Overly Complex (1):** mtf_forex_neural.yaml (30KB)
4. **One-off Experiment (1):** v15_test_analytics.yaml

---

## Test Impact Analysis

### Unit Tests (`tests/unit/test_v15_template.py`)

- **Dependencies:** v15_template.yaml + 23 v1.5 strategies
- **Impact:** All must be migrated to V3
- **Note:** Tests check fixed parameters - migration must preserve these

### E2E Tests (`tests/e2e/test_v3_train_backtest.py`)

- **Dependencies:** Creates inline test strategy, uses first v2 strategy found
- **Impact:** After cleanup, backward compatibility test will need adjustment
- **Action:** Update `TestV2BackwardCompatibility` to explicitly skip or test migration path

### Other Test References

Most test files reference generic paths like `strategies/test.yaml` or create inline fixtures - these don't depend on specific strategy files.

---

## Migration Order

1. **Task 8.2:** Migrate the 31 strategies to V3 format
2. **Task 8.3:** Delete the 43 obsolete strategies
3. **Task 8.4:** Update test fixtures (especially `test_v15_template.py`)
