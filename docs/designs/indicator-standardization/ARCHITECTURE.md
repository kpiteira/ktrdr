# Indicator Standardization: Architecture

## Overview

This document describes the technical implementation of indicator output standardization. The goal is to make indicator outputs consistent and predictable, enabling Strategy Grammar v3's dot notation (`bbands_20_2.upper`) and simplifying downstream consumers.

**Core change:** Indicators no longer embed parameters in column names. They return semantic-only names (`upper`, `signal`, `k`), and the caller (IndicatorEngine) handles prefixing with `{indicator_id}.{output_name}`.

---

## Component Changes

### 1. BaseIndicator

**Location:** [ktrdr/indicators/base_indicator.py](../../../ktrdr/indicators/base_indicator.py)

**Changes:**
- Replace `get_primary_output_suffix()` with `get_output_names()`
- Add `get_primary_output()` convenience method
- Update docstrings to reflect new contract

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

        These names are:
        - Used as column names in compute() return value
        - Used for dot notation validation (bbands_20_2.upper)
        - Exposed to agents for strategy design
        """
        return []

    @classmethod
    def get_primary_output(cls) -> str | None:
        """
        Return the primary output name for multi-output indicators.

        Used when indicator is referenced without dot notation.
        Returns None for single-output indicators.
        """
        outputs = cls.get_output_names()
        return outputs[0] if outputs else None
```

**Methods to remove:**
- `get_primary_output_suffix()` — replaced by `get_output_names()` + `get_primary_output()`
- `get_column_name()` — indicators no longer responsible for naming
- `get_feature_id()` — caller provides indicator_id

**Note:** `get_column_name()` and `get_feature_id()` are heavily used. They'll be removed from BaseIndicator but the IndicatorEngine will take over naming responsibility.

---

### 2. Multi-Output Indicators

Each multi-output indicator needs:
1. `is_multi_output() -> True`
2. `get_output_names() -> list[str]`
3. `compute()` returns DataFrame with columns matching `get_output_names()`

**Example: BollingerBands**

```python
class BollingerBandsIndicator(BaseIndicator):

    @classmethod
    def is_multi_output(cls) -> bool:
        return True

    @classmethod
    def get_output_names(cls) -> list[str]:
        return ["upper", "middle", "lower"]

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        # ... calculation ...
        return pd.DataFrame({
            "upper": upper_band,
            "middle": middle_band,
            "lower": lower_band,
        }, index=data.index)
```

**All multi-output indicators and their outputs:**

| Indicator | File | Outputs |
|-----------|------|---------|
| BollingerBands | `bollinger_bands_indicator.py` | `upper`, `middle`, `lower` |
| MACD | `macd_indicator.py` | `line`, `signal`, `histogram` |
| Stochastic | `stochastic_indicator.py` | `k`, `d` |
| ADX | `adx_indicator.py` | `adx`, `plus_di`, `minus_di` |
| Aroon | `aroon_indicator.py` | `up`, `down`, `oscillator` |
| Ichimoku | `ichimoku_indicator.py` | `tenkan`, `kijun`, `senkou_a`, `senkou_b`, `chikou` |
| Supertrend | `supertrend_indicator.py` | `trend`, `direction` |
| Donchian | `donchian_channels.py` | `upper`, `middle`, `lower` |
| Keltner | `keltner_channels.py` | `upper`, `middle`, `lower` |
| Fisher | `fisher_transform.py` | `fisher`, `signal` |

---

### 3. Single-Output Indicators

Single-output indicators need minimal changes:
1. Remove `name` assignment from returned Series
2. Remove `get_column_name()` override if present

**Example: RSI**

```python
class RSIIndicator(BaseIndicator):

    # is_multi_output() returns False (default)
    # get_output_names() returns [] (default)

    def compute(self, data: pd.DataFrame) -> pd.Series:
        # ... calculation ...
        return rsi  # No name assignment
```

---

### 4. IndicatorEngine

**Location:** [ktrdr/indicators/indicator_engine.py](../../../ktrdr/indicators/indicator_engine.py)

The IndicatorEngine becomes responsible for column naming. It receives the `indicator_id` from the strategy config and prefixes columns appropriately.

**New signature:**

```python
class IndicatorEngine:

    def compute_indicator(
        self,
        data: pd.DataFrame,
        indicator: BaseIndicator,
        indicator_id: str,
    ) -> pd.DataFrame:
        """
        Compute an indicator and return properly named columns.

        Args:
            data: OHLCV data
            indicator: The indicator instance
            indicator_id: The ID from strategy config (e.g., "rsi_14", "bbands_20_2")

        Returns:
            DataFrame with columns:
            - Single-output: {indicator_id}
            - Multi-output: {indicator_id}.{output_name} for each output
        """
        result = indicator.compute(data)

        if indicator.is_multi_output():
            # Validate output names match expected
            expected = set(indicator.get_output_names())
            actual = set(result.columns)
            if expected != actual:
                raise ValueError(
                    f"Indicator {indicator_id} output mismatch: "
                    f"expected {expected}, got {actual}"
                )

            # Rename columns with indicator_id prefix
            return result.rename(columns={
                name: f"{indicator_id}.{name}"
                for name in result.columns
            })
        else:
            # Single output - name with indicator_id
            return pd.DataFrame({indicator_id: result}, index=data.index)
```

**Changes to `apply()` method:**

The current `apply()` method iterates over `self.indicators` without indicator IDs. This needs to change:

```python
def apply(
    self,
    data: pd.DataFrame,
    indicator_configs: dict[str, IndicatorConfig],  # New: {indicator_id: config}
) -> pd.DataFrame:
    """
    Apply all configured indicators to the input data.

    Args:
        data: OHLCV data
        indicator_configs: Dict mapping indicator_id to indicator config

    Returns:
        DataFrame with original data plus indicator columns
    """
    result_df = data.copy()

    for indicator_id, config in indicator_configs.items():
        indicator = self._create_indicator(config)
        computed = self.compute_indicator(data, indicator, indicator_id)
        result_df = pd.concat([result_df, computed], axis=1)

    return result_df
```

**Methods to remove:**
- `_build_feature_id_map()` — no longer needed
- `_create_feature_id_aliases()` — no longer needed
- `_get_technical_column_name()` — no longer needed
- `compute_rsi()`, `compute_sma()`, etc. — helper methods that hardcode naming

---

### 5. IndicatorFactory

**Location:** [ktrdr/indicators/indicator_factory.py](../../../ktrdr/indicators/indicator_factory.py)

The factory creates indicator instances but no longer handles naming. It receives config and returns indicator instances.

**Simplified interface:**

```python
class IndicatorFactory:

    def create(self, indicator_type: str, **params) -> BaseIndicator:
        """
        Create an indicator instance.

        Args:
            indicator_type: The indicator type (e.g., "rsi", "bbands")
            **params: Indicator parameters

        Returns:
            Configured indicator instance
        """
        indicator_class = self._get_indicator_class(indicator_type)
        return indicator_class(**params)
```

**Changes:**
- Remove `feature_id` handling
- Remove `_timeframe` assignment to indicators
- Simplify to pure construction

---

### 6. Files to Delete

**`column_standardization.py`**

This 463-line file contains `ColumnStandardizer` class that is never imported or used. It was designed to work around inconsistent naming — with standardized outputs, it's unnecessary.

**Verification:** `ColumnStandardizer` is only instantiated within its own file's helper function. No external imports exist.

---

## Data Flow

### Before (Current)

```
Strategy Config
    ↓
IndicatorFactory.build()
    → Sets _feature_id on each indicator
    → Sets _timeframe on each indicator
    ↓
IndicatorEngine.apply()
    → Calls indicator.compute()
    → indicator embeds params in column names
    → Engine creates feature_id aliases
    ↓
DataFrame with columns like:
    "upper_20_2.0", "MACD_12_26", "RSI_14"
    + aliases like "rsi_momentum"
```

### After (Proposed)

```
Strategy Config (v3 format)
    ↓
indicators:
  rsi_14: {type: rsi, period: 14}
  bbands_20_2: {type: bbands, period: 20, multiplier: 2.0}
    ↓
IndicatorFactory.create(type, **params)
    → Returns clean indicator instance
    ↓
IndicatorEngine.compute_indicator(data, indicator, indicator_id)
    → Calls indicator.compute()
    → indicator returns semantic names only
    → Engine prefixes with indicator_id
    ↓
DataFrame with columns like:
    "rsi_14", "bbands_20_2.upper", "bbands_20_2.middle", "bbands_20_2.lower"
```

---

## Consumer Updates

### FuzzyEngine

**Location:** `ktrdr/fuzzy/engine.py`

**Current behavior:** Expects column names like `RSI_14`, `upper_20_2.0`

**New behavior:** Expects column names like `rsi_14`, `bbands_20_2.upper`

**Changes needed:**
- Update column name expectations to match new format
- For multi-output, use dot notation: `indicator_id.output_name`
- Remove any case normalization logic

### FeatureCache

**Location:** `ktrdr/backtesting/feature_cache.py`

**Current behavior:** Contains gymnastics to map inconsistent names

**New behavior:** Names are consistent, mapping simplified

**Changes needed:**
- Remove fuzzy matching logic (exact match sufficient)
- Update expected column format
- Simplify caching key generation

### Training Pipeline

**Location:** `ktrdr/training/training_pipeline.py`, `ktrdr/training/fuzzy_neural_processor.py`

**Changes needed:**
- Update feature extraction to use new column names
- Ensure model metadata stores feature names in new format

---

## Multi-Timeframe Handling

Timeframe prefixing is **separate** from indicator standardization. It happens at a higher level (in v3 Strategy Grammar, features are named `{timeframe}_{fuzzy_set}_{membership}`).

For indicator columns within a single timeframe, no prefix is needed. When combining multiple timeframes, the IndicatorEngine's `_prefix_indicator_columns()` method adds the timeframe prefix.

**Example flow:**
1. Compute `bbands_20_2` on 1h data → columns: `bbands_20_2.upper`, etc.
2. Compute `bbands_20_2` on 5m data → columns: `bbands_20_2.upper`, etc.
3. When combining, prefix: `1h_bbands_20_2.upper`, `5m_bbands_20_2.upper`

This existing pattern remains unchanged.

---

## Backward Compatibility

This work is done **before** Strategy Grammar v3. v2 strategies must continue to work throughout the migration.

### Compatibility Constraint

**During indicator standardization:** v2 strategies must work at every milestone. The IndicatorEngine adapter layer (M2) is load-bearing for the entire v3 development period.

**After v3 is complete:** Cleanup milestone (M6) removes all v2 compatibility code.

### What stays the same

- v2 strategy YAML format parses correctly
- v2 `IndicatorConfig` with `name`, `feature_id`, `params` works
- Strategy execution flow unchanged
- Training pipeline produces valid models

### What changes

- Column names change format:
  - Single-output: `RSI_14` → `rsi_14` (uses `feature_id` directly)
  - Multi-output: `upper_20_2.0` → `bbands_20_2.upper` (uses `feature_id.output`)
- Consumers update to expect new format (coordinated change)
- Multi-output indicators get alias column for bare `indicator_id` references

### Key insight: `feature_id` = `indicator_id`

In v2, `feature_id` is the user-specified identifier (e.g., `rsi_14`).
In v3, `indicator_id` is the YAML dict key (e.g., `rsi_14: {type: rsi, ...}`).

**They serve the same role.** The IndicatorEngine uses this identifier to prefix column names.

```python
# v2 config
indicators:
  - name: rsi
    feature_id: rsi_14    # <-- This becomes the column prefix
    period: 14

# v3 config
indicators:
  rsi_14:                  # <-- This becomes the column prefix
    type: rsi
    period: 14
```

Both produce column: `rsi_14`

### v2 Smoke Test

At each milestone, verify v2 compatibility by running `strategies/rsi_mean_reversion.yaml` through the training pipeline. This strategy uses both single-output (RSI) and multi-output (MACD) indicators, providing good coverage.

### Cleanup Tracking

Code added for v2 compatibility should be marked:

```python
# CLEANUP(v3): Remove old-format detection after v3 migration complete
if expected_outputs != actual_columns:
    # Old format handling...
```

---

## Migration Strategy

### Progressive Milestones

Each milestone lands as a PR, leaves the system working, and has passing tests.

The key insight is that IndicatorEngine acts as an **adapter layer** — supporting both old and new indicator output formats during the transition. This adapter is load-bearing for the entire v3 development period.

---

### M1: Add Interface (No Behavior Change)

**Goal:** Add `get_output_names()` interface without changing runtime behavior.

**Changes:**

- Add `get_output_names()` and `get_primary_output()` to BaseIndicator
- Implement in all 29 indicators (return correct output names)
- `compute()` methods unchanged — still return old format

**Tests:**

- Unit tests for new interface methods on each indicator
- All existing tests pass (no behavior change)

**Acceptance:** v2 smoke test passes (no behavior change)

---

### M2: IndicatorEngine Adapter

**Goal:** Engine supports both old and new indicator output formats with v2 compatibility.

**Changes:**

- Add `compute_indicator(data, indicator, indicator_id)` method
- Detect output format: if columns match `get_output_names()` exactly → new format
- New format: prefix with `indicator_id` (e.g., `bbands_20_2.upper`)
- Old format: pass through unchanged + add alias for bare `indicator_id`
- Mark all compatibility code with `# CLEANUP(v3): ...` comments

**Format Detection Logic:**

```python
if indicator.is_multi_output():
    expected = set(indicator.get_output_names())
    actual = set(result.columns)

    if expected == actual:
        # NEW FORMAT: semantic names → prefix with indicator_id
        result = result.rename(columns={...})
    else:
        # OLD FORMAT: params in column names → pass through
        # Add alias from indicator_id to primary output
        pass
```

**Tests:**

- Unit tests for both code paths
- Integration test: old-format indicator produces expected columns
- Integration test: new-format indicator produces expected columns

**Acceptance:** v2 smoke test passes (uses old-format indicators through adapter)

---

### M3a: Migrate Single-Output Indicators

**Goal:** Single-output indicators return unnamed Series.

**Scope:** 15+ files

- RSI, ATR, CCI, CMF, MFI, OBV, ROC, Momentum
- Williams %R, RVI, VWAP, Volume Ratio, Distance from MA
- BB Width, Squeeze Intensity, Parabolic SAR, ZigZag, AD Line
- SMA, EMA (in ma_indicators.py)

**Changes per indicator:**

- Remove `.name` assignment from returned Series
- Verify `get_output_names()` returns `[]`

**Acceptance:** v2 smoke test passes, columns now use `feature_id` directly

---

### M3b: Migrate Multi-Output Indicators

**Goal:** Multi-output indicators return semantic column names only.

**Scope:** 10 files

- BollingerBands, MACD, Stochastic, ADX, Aroon
- Ichimoku, Supertrend, Donchian, Keltner, Fisher

**Changes per indicator:**

- `compute()` returns DataFrame with columns matching `get_output_names()`
- Remove param-embedding from column names
- Remove `get_column_name()` override

**Acceptance:** v2 smoke test passes, columns now use `indicator_id.output` format

---

### M4: Update Consumers

**Goal:** Consumers use new column format directly.

**Changes:**

- FeatureCache: simplify column lookup (exact match, not string gymnastics)
- FuzzyEngine: expect `feature_id` and `feature_id.output` format
- Training pipeline: update feature name expectations

**Tests:**

- Unit tests for each consumer with new format
- Integration tests: full pipeline from indicator → fuzzy → training
- E2E test: train a model with v2 strategy

**Acceptance:** v2 smoke test passes, full E2E training and backtesting works

---

### M5: v3 Ready (Checkpoint)

**Goal:** Indicator standardization complete, v3 Grammar can proceed.

**Deliverable:** This is a checkpoint, not implementation work. Verify:

- All indicators migrated to semantic output names
- All consumers updated to new format
- v2 strategies still work via adapter layer
- Ready for Strategy Grammar v3 implementation

**No cleanup yet** — v2 compatibility code remains until v3 is complete.

---

### M6: Cleanup (After v3 Complete) — DEFERRED

**Goal:** Remove v2 compatibility code.

**Trigger:** Only execute after v3 strategies are implemented and v2 strategies are deleted.

**Changes:**

- Remove old-format detection from IndicatorEngine adapter
- Delete `column_standardization.py` (463 lines, never used)
- Remove `get_column_name()` from BaseIndicator
- Remove `get_primary_output_suffix()` (replaced by `get_output_names()`)
- Remove all `# CLEANUP(v3): ...` code

**Acceptance:** All tests pass, no v2 compatibility code remains

---

## Verification Strategy

### Unit Tests

Each indicator needs tests verifying:
1. `is_multi_output()` returns correct value
2. `get_output_names()` returns expected list (empty for single-output)
3. `compute()` returns correct type (Series vs DataFrame)
4. Multi-output: column names match `get_output_names()` exactly

### Integration Test

```python
def test_all_indicators_follow_standard():
    """Verify all registered indicators follow the naming standard."""
    factory = IndicatorFactory()
    sample_data = create_sample_ohlcv()

    for indicator_type in factory.get_available_types():
        indicator = factory.create(indicator_type)

        if indicator.is_multi_output():
            outputs = indicator.get_output_names()
            assert len(outputs) > 0, f"{indicator_type} is multi-output but has no output names"

            result = indicator.compute(sample_data)
            assert isinstance(result, pd.DataFrame)
            assert set(result.columns) == set(outputs), \
                f"{indicator_type} columns {set(result.columns)} != expected {set(outputs)}"
        else:
            outputs = indicator.get_output_names()
            assert len(outputs) == 0, f"{indicator_type} is single-output but has output names"

            result = indicator.compute(sample_data)
            assert isinstance(result, pd.Series)
```

### IndicatorEngine Test

```python
def test_indicator_engine_naming():
    """Verify IndicatorEngine applies correct prefixes."""
    engine = IndicatorEngine()
    data = create_sample_ohlcv()

    # Single-output
    rsi = RSIIndicator(period=14)
    result = engine.compute_indicator(data, rsi, "rsi_14")
    assert "rsi_14" in result.columns

    # Multi-output
    bbands = BollingerBandsIndicator(period=20, multiplier=2.0)
    result = engine.compute_indicator(data, bbands, "bbands_20_2")
    assert "bbands_20_2.upper" in result.columns
    assert "bbands_20_2.middle" in result.columns
    assert "bbands_20_2.lower" in result.columns
```

---

## Resolved Questions

These questions were resolved during design validation (see [SCENARIOS.md](SCENARIOS.md)):

### 1. Primary output without dot notation

**Question:** When a fuzzy set references `macd_12_26_9` (no dot), which output is used?

**Decision:** Use `get_primary_output()` — the first item in `get_output_names()`. For MACD, that's `line`. IndicatorEngine also adds an alias column so `macd_12_26_9` can be looked up directly.

### 2. Indicator parameter validation

**Question:** Should the factory validate that `indicator_id` matches the params?

**Decision:** Warn but don't error. The ID is user-chosen and could be semantic ("rsi_fast" vs "rsi_14"). Let users name things as they prefer.

### 3. Format detection during transition

**Question:** How does IndicatorEngine distinguish old vs new indicator output format?

**Decision:** Check if `compute()` columns match `get_output_names()` exactly. Old-format indicators embed params in column names (e.g., `upper_20_2.0`), new-format use semantic names only (e.g., `upper`). This is a reliable distinguisher.

---

## Related Documents

- [DESIGN.md](DESIGN.md) — Problem statement, goals, and standard definition
- [SCENARIOS.md](SCENARIOS.md) — Validated scenarios and interface contracts
- [../strategy-grammar-v3/DESIGN.md](../strategy-grammar-v3/DESIGN.md) — v3 grammar that depends on this work
- [../strategy-grammar-v3/ARCHITECTURE.md](../strategy-grammar-v3/ARCHITECTURE.md) — v3 implementation details
