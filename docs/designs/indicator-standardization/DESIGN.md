# Indicator Standardization: Design

## Problem Statement

Our 29 indicators use inconsistent naming conventions:

| Indicator | Current Output | Issue |
|-----------|---------------|-------|
| RSI | `RSI_14` | Uppercase, params in name |
| MACD | `MACD_12_26`, `MACD_signal_12_26_9` | Mixed case, inconsistent param inclusion |
| BollingerBands | `upper_20_2.0`, `middle_20_2.0` | Lowercase, output first, float params |
| Stochastic | `%K_14_3`, `%D_14_3` | Special chars, params vary |
| ADX | `ADX_14`, `+DI_14`, `-DI_14` | Special chars, mixed outputs |

This causes:
- Gymnastics in `FeatureCache` and `FuzzyEngine` to map names
- Confusion about which column corresponds to which indicator
- Bugs when indicator output format changes slightly
- Agents can't reliably discover available outputs

## Goals

1. **Consistent naming**: All indicators follow the same convention
2. **Discoverable outputs**: Multi-output indicators expose their output names via `get_output_names()`
3. **Semantic names**: Output names are meaningful (`upper`, `signal`) not computed (`MACD_signal_12_26_9`)
4. **Clean separation**: Parameters live in indicator_id, not in output column names
5. **v3 ready**: Enables dot notation (`bbands_20_2.upper`) for Strategy Grammar v3

## Non-Goals

- Preserving existing model checkpoints (they'll be retrained anyway)

## Compatibility Approach

**During development:** v2 strategies must continue to work while we migrate indicators. The IndicatorEngine acts as an adapter layer, supporting both old and new indicator output formats.

**After v3 is complete:** A cleanup milestone removes all v2 compatibility code. This happens only after v3 strategies are implemented and validated.

This approach avoids the "break everything, fix it later" anti-pattern that leads to half-migrated states.

---

## The Standard

### Naming Convention

**Single-output indicators:**
- `compute()` returns `pd.Series`
- Column naming is caller's responsibility
- Caller uses `{indicator_id}` (e.g., `rsi_14`)

**Multi-output indicators:**
- `compute()` returns `pd.DataFrame`
- Column names are semantic output names only: `upper`, `signal`, `k`
- Caller prefixes with indicator_id: `bbands_20_2.upper`

### Standard Output Names

| Indicator | Type | Outputs |
|-----------|------|---------|
| `rsi` | single | (value) |
| `sma` | single | (value) |
| `ema` | single | (value) |
| `atr` | single | (value) |
| `cci` | single | (value) |
| `cmf` | single | (value) |
| `mfi` | single | (value) |
| `obv` | single | (value) |
| `roc` | single | (value) |
| `momentum` | single | (value) |
| `williams_r` | single | (value) |
| `rvi` | single | (value) |
| `vwap` | single | (value) |
| `volume_ratio` | single | (value) |
| `distance_from_ma` | single | (value) |
| `bbands` | multi | `upper`, `middle`, `lower` |
| `bbands_width` | single | (value) |
| `macd` | multi | `line`, `signal`, `histogram` |
| `stochastic` | multi | `k`, `d` |
| `adx` | multi | `adx`, `plus_di`, `minus_di` |
| `aroon` | multi | `up`, `down`, `oscillator` |
| `ichimoku` | multi | `tenkan`, `kijun`, `senkou_a`, `senkou_b`, `chikou` |
| `supertrend` | multi | `trend`, `direction` |
| `parabolic_sar` | single | (value) |
| `squeeze_intensity` | single | (value) |
| `donchian` | multi | `upper`, `middle`, `lower` |
| `keltner` | multi | `upper`, `middle`, `lower` |
| `fisher` | multi | `fisher`, `signal` |
| `zigzag` | single | (value) |
| `ad_line` | single | (value) |

### BaseIndicator Interface

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

    @abstractmethod
    def compute(self, data: pd.DataFrame) -> pd.Series | pd.DataFrame:
        """
        Compute indicator values.

        Returns:
            - Single-output: pd.Series (unnamed, caller names it)
            - Multi-output: pd.DataFrame with columns matching get_output_names()
        """
        pass
```

### Example: BollingerBands

**Before:**
```python
def compute(self, data: pd.DataFrame) -> pd.DataFrame:
    # ... calculation ...
    suffix = f"{period}_{multiplier}"
    return pd.DataFrame({
        f"upper_{suffix}": upper_band,
        f"middle_{suffix}": middle_band,
        f"lower_{suffix}": lower_band,
    }, index=data.index)
```

**After:**
```python
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

### Example: RSI

**Before:**
```python
def compute(self, data: pd.DataFrame) -> pd.Series:
    # ... calculation ...
    rsi.name = f"RSI_{period}"
    return rsi
```

**After:**
```python
@classmethod
def is_multi_output(cls) -> bool:
    return False  # Default

@classmethod
def get_output_names(cls) -> list[str]:
    return []  # Single output

def compute(self, data: pd.DataFrame) -> pd.Series:
    # ... calculation ...
    return rsi  # No name - caller handles naming
```

---

## IndicatorEngine Changes

The `IndicatorEngine` becomes responsible for naming:

```python
class IndicatorEngine:
    def compute(
        self,
        data: pd.DataFrame,
        indicator_id: str,
    ) -> pd.DataFrame:
        """
        Compute an indicator and return properly named columns.

        Returns:
            DataFrame with columns:
            - Single-output: {indicator_id}
            - Multi-output: {indicator_id}.{output_name} for each output
        """
        indicator = self._indicators[indicator_id]
        result = indicator.compute(data)

        if indicator.is_multi_output():
            # Validate output names match expected
            expected = set(indicator.get_output_names())
            actual = set(result.columns)
            if expected != actual:
                raise ValueError(f"Output mismatch: expected {expected}, got {actual}")

            # Rename columns with indicator_id prefix
            return result.rename(columns={
                name: f"{indicator_id}.{name}"
                for name in result.columns
            })
        else:
            # Single output - name with indicator_id
            return pd.DataFrame({indicator_id: result}, index=data.index)
```

---

## Migration Checklist

### Single-Output Indicators (15)

- [ ] `rsi_indicator.py`
- [ ] `atr_indicator.py`
- [ ] `cci_indicator.py`
- [ ] `cmf_indicator.py`
- [ ] `mfi_indicator.py`
- [ ] `obv_indicator.py`
- [ ] `roc_indicator.py`
- [ ] `momentum_indicator.py`
- [ ] `williams_r_indicator.py`
- [ ] `rvi_indicator.py`
- [ ] `vwap_indicator.py`
- [ ] `volume_ratio_indicator.py`
- [ ] `distance_from_ma_indicator.py`
- [ ] `bollinger_band_width_indicator.py`
- [ ] `squeeze_intensity_indicator.py`
- [ ] `parabolic_sar_indicator.py`
- [ ] `zigzag_indicator.py`
- [ ] `ad_line.py`

### Multi-Output Indicators (11)

- [ ] `bollinger_bands_indicator.py` → `upper`, `middle`, `lower`
- [ ] `macd_indicator.py` → `line`, `signal`, `histogram`
- [ ] `stochastic_indicator.py` → `k`, `d`
- [ ] `adx_indicator.py` → `adx`, `plus_di`, `minus_di`
- [ ] `aroon_indicator.py` → `up`, `down`, `oscillator`
- [ ] `ichimoku_indicator.py` → `tenkan`, `kijun`, `senkou_a`, `senkou_b`, `chikou`
- [ ] `supertrend_indicator.py` → `trend`, `direction`
- [ ] `donchian_channels.py` → `upper`, `middle`, `lower`
- [ ] `keltner_channels.py` → `upper`, `middle`, `lower`
- [ ] `fisher_transform.py` → `fisher`, `signal`

### MA Indicators (`ma_indicators.py`)

- [ ] `SMAIndicator`
- [ ] `EMAIndicator`
- [ ] `WMAIndicator` (if exists)

### Infrastructure Updates

- [ ] `base_indicator.py` — Add interface methods
- [ ] `indicator_engine.py` — Handle naming
- [ ] `indicator_factory.py` — No changes needed
- [ ] `column_standardization.py` — Can be simplified or removed

### Consumers to Update

- [ ] `ktrdr/fuzzy/engine.py` — Expect new format
- [ ] `ktrdr/backtesting/feature_cache.py` — Remove gymnastics
- [ ] `ktrdr/training/training_pipeline.py` — Use new format
- [ ] `ktrdr/training/fuzzy_neural_processor.py` — Expect clean names

---

## Verification

### Unit Tests

Each indicator gets a test verifying:
1. `is_multi_output()` returns correct value
2. `get_output_names()` returns expected list
3. `compute()` returns correct type (Series vs DataFrame)
4. Multi-output: column names match `get_output_names()` exactly

### Integration Test

```python
def test_all_indicators_follow_standard():
    """Verify all registered indicators follow the naming standard."""
    factory = IndicatorFactory()

    for indicator_type in factory.get_available_types():
        indicator = factory.create(indicator_type)

        if indicator.is_multi_output():
            outputs = indicator.get_output_names()
            assert len(outputs) > 0, f"{indicator_type} is multi-output but has no output names"

            # Compute and verify
            result = indicator.compute(sample_data)
            assert isinstance(result, pd.DataFrame)
            assert set(result.columns) == set(outputs)
        else:
            outputs = indicator.get_output_names()
            assert len(outputs) == 0, f"{indicator_type} is single-output but has output names"

            result = indicator.compute(sample_data)
            assert isinstance(result, pd.Series)
```

---

## Decisions

1. **Lowercase everything** — `upper` not `Upper` or `UPPER`

2. **Semantic names only** — `line` not `macd_line`, `upper` not `upper_band`

3. **No parameters in output names** — Parameters belong in indicator_id

4. **Primary output is first** — `get_output_names()[0]` is the primary

5. **Caller handles prefixes** — Indicators don't know their indicator_id

---

## Related Documents

This work is a **strict prerequisite** for Strategy Grammar v3:

- [ARCHITECTURE.md](ARCHITECTURE.md) — Technical implementation details
- [SCENARIOS.md](SCENARIOS.md) — Validated scenarios and interface contracts
- [../strategy-grammar-v3/DESIGN.md](../strategy-grammar-v3/DESIGN.md) — v3 grammar spec (depends on this work)
- [../strategy-grammar-v3/ARCHITECTURE.md](../strategy-grammar-v3/ARCHITECTURE.md) — v3 implementation architecture

**Why v3 depends on this:**

- v3 dot notation (`bbands_20_2.upper`) requires `get_output_names()` for validation
- v3 feature naming assumes consistent indicator output format
- v3 IndicatorEngine changes build on the standardized interface

---

## M5 Completion Status

**Status:** ✅ COMPLETE  
**Completion Date:** 2026-01-05  
**Version:** indicator-std-v1

### Verification Results

All M1-M4 milestones completed successfully:

#### ✅ M1: Interface Compliance
- **30/30 indicators** have `get_output_names()` and `get_primary_output()` interface
- All single-output indicators correctly return empty list from `get_output_names()`
- All multi-output indicators correctly return semantic output names

#### ⚠️ M2-M3: Output Format Migration
- **27/30 indicators** produce new semantic column format
- **3 indicators pending** (RVI, ADLine, CMF) - deferred to M6 cleanup
- All indicators used in v2 strategies are fully migrated

#### ✅ M4: Consumer Updates
- FeatureCache uses O(1) direct column lookup
- FuzzyEngine supports dot notation and alias references
- Training pipeline produces models with new format feature names

#### ✅ v2 Compatibility
- Training and backtesting work with new format
- Existing v2 strategies run unchanged
- Model features use semantic names (`1h_rsi_21_oversold`, `1h_macd_12_bullish`)

#### ✅ Quality Gates
- **Unit Tests:** 3666 passed, 76 skipped
- **Integration Tests:** Full pipeline validation passed
- **Code Quality:** All linting, formatting, type checks passed

### Known Gaps

**3 indicators not yet migrated:** RVI, ADLine, CMF
- Have correct interface (`get_output_names()`)
- Still return old-format column names
- Not used in current v2 strategies
- **Action:** Migrate during M6 cleanup (after v3 is complete)

### v3 Readiness

✅ **Ready for Strategy Grammar v3 development**

See [V3_READINESS.md](V3_READINESS.md) for:
- Complete indicator output reference
- Column naming conventions
- v3 Grammar integration patterns
- Validation examples
- Migration notes

### Next Steps

1. **Begin v3 Grammar Development** — Use standardized interface
2. **After v3 Complete** — Run M6 cleanup phase to:
   - Migrate remaining 3 indicators
   - Remove v2 compatibility layer
   - Simplify IndicatorEngine

---

**Implementation Notes:** This design was completed across 5 milestones (M1-M5) with comprehensive handoff documentation for each phase. All verification checks passed, confirming the system is ready for v3 Grammar development.
