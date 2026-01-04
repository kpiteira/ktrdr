# Indicator Standardization: Validation Scenarios

**Date:** 2026-01-04
**Documents Validated:**
- [DESIGN.md](DESIGN.md) — Problem statement, goals, standard definition
- [ARCHITECTURE.md](ARCHITECTURE.md) — Technical implementation details

---

## Validation Summary

**Scenarios Validated:** 8/8 traced
**Critical Gaps Found:** 3 (all resolved)
**Interface Contracts:** Defined for BaseIndicator, IndicatorEngine

---

## Key Decisions Made

These decisions came from the validation conversation and inform implementation:

### 1. Format Detection via Column Matching

**Context:** During M2-M3 transition, IndicatorEngine needs to detect old vs new indicator output format.

**Decision:** If `compute()` columns match `get_output_names()` exactly, it's new format; otherwise old format. Old-format indicators embed params in column names (e.g., `upper_20_2.0`), new-format use semantic names only (e.g., `upper`).

**Trade-off:** Implicit detection vs explicit `uses_semantic_names()` flag. Chose implicit because it's reliable and requires no indicator-side changes during transition.

### 2. Alias for Bare indicator_id References

**Context:** When fuzzy sets reference `macd_12_26_9` without `.line` suffix, but DataFrame has `macd_12_26_9.line`, who resolves this?

**Decision:** IndicatorEngine adds `{indicator_id}` as alias column pointing to `{indicator_id}.{primary_output}`. This keeps consumers simple — they can reference either form.

**Trade-off:** Slight memory overhead for alias columns vs complexity in every consumer. Chose aliases for simplicity.

### 3. v2 Compatibility Throughout Development

**Context:** Design initially said "no backward compatibility" but this was clarified.

**Decision:** v2 strategies must work throughout indicator standardization. The adapter layer (M2) is load-bearing for the entire v3 development period. Cleanup happens only after v3 is complete (M6).

**Trade-off:** Carrying compatibility code during development vs "break everything, fix later" approach. Chose compatibility for safety.

### 4. M3 Split: Single-Output First

**Context:** 29 indicators to migrate — should we do all at once or in batches?

**Decision:** M3a migrates single-output indicators (15 files, simpler), M3b migrates multi-output (10 files, more complex). Each batch has its own acceptance criteria.

**Trade-off:** More milestones vs larger atomic changes. Chose smaller batches for safer incremental progress.

### 5. Smoke Test Strategy

**Decision:** Use `strategies/rsi_mean_reversion.yaml` as v2 smoke test. It uses both single-output (RSI) and multi-output (MACD) indicators, providing good coverage.

---

## Scenarios

### Happy Paths

#### Scenario 1: Single-output indicator computation

**Trigger:** Strategy with `rsi_14: {type: rsi, period: 14}` is processed

**Expected Outcome:** DataFrame contains column `rsi_14`

| Step | Component | Action | Output |
|------|-----------|--------|--------|
| 1 | IndicatorFactory | Create RSIIndicator | Instance with period=14 |
| 2 | IndicatorEngine | Call `compute()` | pd.Series (unnamed) |
| 3 | IndicatorEngine | Check `is_multi_output()` | `False` |
| 4 | IndicatorEngine | Wrap in DataFrame | `{"rsi_14": series}` |

**Verification:** Column exists and contains valid RSI values (0-100 range).

---

#### Scenario 2: Multi-output indicator computation

**Trigger:** Strategy with `bbands_20_2: {type: bbands, period: 20, multiplier: 2.0}` is processed

**Expected Outcome:** DataFrame contains `bbands_20_2.upper`, `bbands_20_2.middle`, `bbands_20_2.lower`, plus `bbands_20_2` alias

| Step | Component | Action | Output |
|------|-----------|--------|--------|
| 1 | IndicatorFactory | Create BollingerBandsIndicator | Instance |
| 2 | IndicatorEngine | Call `compute()` | DataFrame with `upper`, `middle`, `lower` |
| 3 | IndicatorEngine | Check `is_multi_output()` | `True` |
| 4 | IndicatorEngine | Get `get_output_names()` | `["upper", "middle", "lower"]` |
| 5 | IndicatorEngine | Validate columns match | Pass |
| 6 | IndicatorEngine | Rename with prefix | `bbands_20_2.upper`, etc. |
| 7 | IndicatorEngine | Add alias | `bbands_20_2` → copy of `bbands_20_2.upper` |

**Verification:** All four columns exist; alias equals primary output.

---

#### Scenario 3: v2 strategy full pipeline

**Trigger:** `rsi_mean_reversion.yaml` processed through training pipeline

**Expected Outcome:** Training completes successfully

| Step | Component | Action | Verification |
|------|-----------|--------|--------------|
| 1 | StrategyLoader | Parse YAML | Config object created |
| 2 | IndicatorEngine | Compute all indicators | DataFrame with indicator columns |
| 3 | FeatureCache | Map columns to feature_ids | Mapping successful |
| 4 | FuzzyEngine | Fuzzify indicators | Membership values computed |
| 5 | TrainingPipeline | Train model | Model file saved |

**This is the v2 smoke test.** Must pass at every milestone.

---

### Error Paths

#### Scenario 4: Output mismatch detection

**Trigger:** Multi-output indicator's `compute()` returns columns that don't match `get_output_names()`

**Expected Outcome:** Clear error with diagnostic information

| Step | Component | Action | Output |
|------|-----------|--------|--------|
| 1 | IndicatorEngine | Call `compute()` | DataFrame with wrong columns |
| 2 | IndicatorEngine | Get `get_output_names()` | Expected column list |
| 3 | IndicatorEngine | Compare sets | Mismatch detected |
| 4 | IndicatorEngine | Raise ValueError | "Indicator {id} output mismatch: expected {X}, got {Y}" |

**Verification:** Error message includes indicator_id, expected columns, actual columns.

---

#### Scenario 5: Missing get_output_names() implementation

**Trigger:** Multi-output indicator returns `is_multi_output() = True` but `get_output_names()` returns `[]`

**Expected Outcome:** Error at validation time (not runtime)

**Verification:** Integration test catches this: "multi-output indicator has no output names"

---

### Edge Cases

#### Scenario 6: Primary output resolution

**Trigger:** Fuzzy set references `macd_12_26_9` without dot notation

**Expected Outcome:** System uses primary output (`line`)

| Step | Component | Action | Output |
|------|-----------|--------|--------|
| 1 | IndicatorEngine | Compute MACD | `macd_12_26_9.line`, `.signal`, `.histogram` |
| 2 | IndicatorEngine | Add alias | `macd_12_26_9` = copy of `macd_12_26_9.line` |
| 3 | FeatureCache | Lookup `macd_12_26_9` | Finds alias column |
| 4 | FuzzyEngine | Fuzzify | Uses primary output value |

**Verification:** Bare reference works; returns same value as explicit `.line` reference.

---

#### Scenario 7: Multi-timeframe column prefixing

**Trigger:** Same indicator computed on 1h and 5m data, then combined

**Expected Outcome:** Columns prefixed with timeframe

| Step | Component | Action | Output |
|------|-----------|--------|--------|
| 1 | IndicatorEngine | Compute on 1h data | `rsi_14` |
| 2 | IndicatorEngine | Compute on 5m data | `rsi_14` |
| 3 | IndicatorEngine | Prefix 1h columns | `1h_rsi_14` |
| 4 | IndicatorEngine | Prefix 5m columns | `5m_rsi_14` |
| 5 | Combine | Merge DataFrames | No collision |

**Verification:** Both columns exist with distinct prefixes.

---

### Integration Boundaries

#### Scenario 8: FuzzyEngine consumption

**Trigger:** FuzzyEngine receives indicator values after standardization

**Expected Outcome:** Fuzzification works with new column format

| Step | Component | Action | Verification |
|------|-----------|--------|--------------|
| 1 | FeatureCache | Get indicator value | Direct lookup by feature_id |
| 2 | FeatureCache | Pass to FuzzyEngine | Value is float, not column name |
| 3 | FuzzyEngine | Lookup fuzzy set config | Config keyed by feature_id |
| 4 | FuzzyEngine | Apply membership functions | Returns membership dict |

**Key insight:** FuzzyEngine receives values, not column names. The integration point is FeatureCache's column lookup logic.

---

#### Scenario 9: FeatureCache lookup (new format)

**Trigger:** FeatureCache looks up columns after standardization

**Current behavior (gymnastics):**
```python
for col in self.indicators_df.columns:
    if col.upper().startswith(indicator_type):
        # Special case handling for MACD, etc.
```

**New behavior (simplified):**
```python
if feature_id in self.indicators_df.columns:
    # Direct lookup (works for single-output and aliases)
    value = self.indicators_df[feature_id].iloc[idx]
```

**Verification:** Lookup is O(1) dict access, not O(n) string matching.

---

## Interface Contracts

### BaseIndicator (New Methods)

```python
class BaseIndicator(ABC):

    @classmethod
    def is_multi_output(cls) -> bool:
        """Returns True if compute() returns DataFrame, False if Series."""
        return False  # Default: single output

    @classmethod
    def get_output_names(cls) -> list[str]:
        """
        Return semantic output names for multi-output indicators.

        Single-output indicators return empty list.
        Multi-output indicators return ordered list of output names.
        First item is the primary output (used for bare indicator_id references).

        Examples:
            RSI: []
            BollingerBands: ["upper", "middle", "lower"]
            MACD: ["line", "signal", "histogram"]
        """
        return []

    @classmethod
    def get_primary_output(cls) -> str | None:
        """
        Return the primary output name for multi-output indicators.
        Convenience method - returns get_output_names()[0] or None.
        """
        outputs = cls.get_output_names()
        return outputs[0] if outputs else None
```

### IndicatorEngine.compute_indicator (New Method)

```python
def compute_indicator(
    self,
    data: pd.DataFrame,
    indicator: BaseIndicator,
    indicator_id: str,
) -> pd.DataFrame:
    """
    Compute an indicator and return properly named columns.

    Handles both old-format and new-format indicator outputs:
    - Old format: columns include params (e.g., "upper_20_2.0") -> pass through
    - New format: semantic names only (e.g., "upper") -> prefix with indicator_id

    For multi-output indicators, adds alias column for bare indicator_id
    pointing to primary output.

    Args:
        data: OHLCV DataFrame
        indicator: The indicator instance
        indicator_id: The ID from strategy config (e.g., "rsi_14", "bbands_20_2")

    Returns:
        DataFrame with columns:
        - Single-output: {indicator_id}
        - Multi-output (new): {indicator_id}.{output_name} + {indicator_id} alias
        - Multi-output (old): original columns + {indicator_id} alias
    """
```

### Multi-Output Indicator Standard Outputs

| Indicator | `get_output_names()` | Primary Output |
|-----------|---------------------|----------------|
| BollingerBands | `["upper", "middle", "lower"]` | `upper` |
| MACD | `["line", "signal", "histogram"]` | `line` |
| Stochastic | `["k", "d"]` | `k` |
| ADX | `["adx", "plus_di", "minus_di"]` | `adx` |
| Aroon | `["up", "down", "oscillator"]` | `up` |
| Ichimoku | `["tenkan", "kijun", "senkou_a", "senkou_b", "chikou"]` | `tenkan` |
| Supertrend | `["trend", "direction"]` | `trend` |
| Donchian | `["upper", "middle", "lower"]` | `upper` |
| Keltner | `["upper", "middle", "lower"]` | `upper` |
| Fisher | `["fisher", "signal"]` | `fisher` |

---

## Milestone Structure

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed milestone definitions.

| Milestone | Goal | E2E Test |
|-----------|------|----------|
| M1 | Add `get_output_names()` interface | v2 smoke test passes (no behavior change) |
| M2 | IndicatorEngine adapter (both formats) | v2 smoke test passes |
| M3a | Migrate single-output indicators | v2 smoke test passes |
| M3b | Migrate multi-output indicators | v2 smoke test passes |
| M4 | Update consumers (FeatureCache, etc.) | v2 smoke test passes |
| M5 | v3 Ready checkpoint | All tests pass, ready for v3 Grammar |
| M6 | Cleanup (after v3 complete) | No v2 code remains |

**v2 Smoke Test:** `strategies/rsi_mean_reversion.yaml` through full training pipeline.

---

## Cleanup Tracking

Code added for v2 compatibility should be marked for future cleanup:

```python
# CLEANUP(v3): Remove old-format detection after v3 migration complete
if expected_outputs != actual_columns:
    # Old format handling...
```

Items to remove in M6:
- Old-format detection in IndicatorEngine adapter
- `get_column_name()` method in BaseIndicator
- `get_primary_output_suffix()` method
- Alias creation for bare indicator_id references
- `column_standardization.py` (463 lines, never used)
