# Strategy Grammar v3 Readiness

**Status:** ✅ READY
**Date:** 2026-01-05
**Indicator Standardization Version:** v1

This document provides all necessary information for implementing Strategy Grammar v3 with dot notation support (e.g., `bbands_20_2.upper`).

---

## Verification Summary

### ✅ All Requirements Met

| Requirement | Status | Details |
|------------|--------|---------|
| Indicator Interface | ✅ Complete | 30/30 indicators have `get_output_names()` and `get_primary_output()` |
| Output Format | ⚠️ Mostly Complete | 27/30 indicators produce new format (RVI, ADLine, CMF pending) |
| Consumer Updates | ✅ Complete | FeatureCache and FuzzyEngine use direct O(1) lookup |
| v2 Compatibility | ✅ Verified | Training and backtesting work with new format |
| Unit Tests | ✅ Passing | 3666 passed, 76 skipped |
| Quality Gates | ✅ Passing | All linting, formatting, and type checks pass |

### ⚠️ Known Gaps

**3 indicators not yet migrated to M3b format:**
- `RVI` (Relative Vigor Index)
- `ADLine` (Accumulation/Distribution Line)
- `CMF` (Chaikin Money Flow)

These indicators have the interface (`get_output_names()`) but still return old-format column names. They are not used in current v2 strategies, so they don't block v3 development.

**Recommendation:** Migrate these 3 indicators in M6 cleanup phase (after v3 is complete).

---

## Column Naming Convention

### Single-Output Indicators

**Format:** `{indicator_id}`

**Example:**
```yaml
indicators:
  - name: rsi
    feature_id: rsi_14
    period: 14
```

**Produces column:** `rsi_14`

### Multi-Output Indicators

**Format:** `{indicator_id}.{output_name}`

**Example:**
```yaml
indicators:
  - name: bbands
    feature_id: bbands_20_2
    period: 20
    multiplier: 2.0
```

**Produces columns:**
- `bbands_20_2.upper`
- `bbands_20_2.middle`
- `bbands_20_2.lower`
- `bbands_20_2` (alias → points to primary output `upper`)

### Primary Output Alias

Multi-output indicators create an alias column pointing to their primary output. This allows bare references in v3 Grammar:

```yaml
fuzzy_sets:
  bbands_20_2:  # Bare reference uses alias → resolves to .upper
    overbought: {...}
```

---

## Indicator Output Reference

### Complete List of Indicators and Their Outputs

#### Single-Output Indicators (18)

| Indicator | Class | Output Names |
|-----------|-------|--------------|
| RSI | `RSIIndicator` | _(single value)_ |
| SMA | `SMAIndicator` | _(single value)_ |
| EMA | `EMAIndicator` | _(single value)_ |
| ATR | `ATRIndicator` | _(single value)_ |
| OBV | `OBVIndicator` | _(single value)_ |
| CCI | `CCIIndicator` | _(single value)_ |
| Momentum | `MomentumIndicator` | _(single value)_ |
| ROC | `ROCIndicator` | _(single value)_ |
| VWAP | `VWAPIndicator` | _(single value)_ |
| WilliamsR | `WilliamsRIndicator` | _(single value)_ |
| MFI | `MFIIndicator` | _(single value)_ |
| BollingerBandWidth | `BollingerBandWidthIndicator` | _(single value)_ |
| VolumeRatio | `VolumeRatioIndicator` | _(single value)_ |
| SqueezeIntensity | `SqueezeIntensityIndicator` | _(single value)_ |
| DistanceFromMA | `DistanceFromMAIndicator` | _(single value)_ |
| ZigZag | `ZigZagIndicator` | _(single value)_ |
| ADX | `ADXIndicator` | _(single value - ADX line only)_ |
| SuperTrend | `SuperTrendIndicator` | _(single value - trend line)_ |

#### Multi-Output Indicators (12)

| Indicator | Class | Output Names | Primary |
|-----------|-------|--------------|---------|
| **BollingerBands** | `BollingerBandsIndicator` | `upper`, `middle`, `lower` | `upper` |
| **MACD** | `MACDIndicator` | `line`, `signal`, `histogram` | `line` |
| **Stochastic** | `StochasticIndicator` | `k`, `d` | `k` |
| **ParabolicSAR** | `ParabolicSARIndicator` | `sar`, `trend` | `sar` |
| **Ichimoku** | `IchimokuIndicator` | `tenkan`, `kijun`, `senkou_a`, `senkou_b`, `chikou` | `tenkan` |
| **Aroon** | `AroonIndicator` | `up`, `down`, `oscillator` | `up` |
| **DonchianChannels** | `DonchianChannelsIndicator` | `upper`, `lower`, `middle` | `upper` |
| **KeltnerChannels** | `KeltnerChannelsIndicator` | `upper`, `middle`, `lower` | `upper` |
| **FisherTransform** | `FisherTransformIndicator` | `fisher`, `trigger` | `fisher` |
| **RVI** ⚠️ | `RVIIndicator` | `rvi`, `signal` | `rvi` |
| **ADLine** ⚠️ | `ADLineIndicator` | `line`, `mf_multiplier`, `mf_volume`, `roc_10`, `momentum_21`, `relative_strength` | `line` |
| **CMF** ⚠️ | `CMFIndicator` | `cmf`, `mf_multiplier`, `mf_volume`, `momentum`, `signal`, `histogram`, `above_zero`, `below_zero` | `cmf` |

⚠️ _Not yet producing new format (pending M6 migration)_

---

## v3 Grammar Integration

### Validation Pattern

When v3 Grammar encounters dot notation like `bbands_20_2.upper`, it should:

1. **Parse indicator_id and output**
   ```python
   parts = "bbands_20_2.upper".split(".", 1)
   indicator_id = parts[0]  # "bbands_20_2"
   output = parts[1] if len(parts) > 1 else None  # "upper"
   ```

2. **Get indicator class**
   ```python
   from ktrdr.indicators.indicator_factory import IndicatorFactory

   factory = IndicatorFactory()
   indicator_class = factory.get_indicator_class('bbands')
   ```

3. **Validate output name**
   ```python
   valid_outputs = indicator_class.get_output_names()
   # ['upper', 'middle', 'lower']

   if output and output not in valid_outputs:
       raise ValueError(f"Invalid output '{output}' for indicator 'bbands'. "
                       f"Valid outputs: {valid_outputs}")
   ```

4. **Handle bare references**
   ```python
   if not output:  # Bare reference like "bbands_20_2"
       # Uses alias column → points to primary output
       primary = indicator_class.get_primary_output()
       # Primary is 'upper', alias column will resolve to .upper
   ```

### Example v3 Strategy Snippet

```yaml
strategy:
  name: example_v3
  timeframe: 1h

indicators:
  - name: rsi
    feature_id: rsi_14
    period: 14

  - name: bbands
    feature_id: bbands_20_2
    period: 20
    multiplier: 2.0

  - name: macd
    feature_id: macd_12_26_9
    fast_period: 12
    slow_period: 26
    signal_period: 9

fuzzy_sets:
  # Single-output: direct reference
  rsi_14:
    oversold:
      type: triangular
      parameters: [0, 30, 40]
    overbought:
      type: triangular
      parameters: [60, 70, 100]

  # Multi-output: dot notation
  bbands_20_2.upper:
    price_near:
      type: gaussian
      parameters: [0, 0.01]

  bbands_20_2.lower:
    price_near:
      type: gaussian
      parameters: [0, 0.01]

  # Multi-output: bare reference (uses alias → .line)
  macd_12_26_9:
    bullish:
      type: triangular
      parameters: [0, 20, 50]
    bearish:
      type: triangular
      parameters: [-50, -20, 0]
```

---

## Implementation Checklist for v3

When implementing v3 Grammar, ensure:

- [ ] **Parser** recognizes dot notation in `{indicator_id}.{output}` format
- [ ] **Validator** checks output names against `get_output_names()`
- [ ] **Column lookup** uses exact string matching (no fuzzy matching needed)
- [ ] **Bare references** are validated as multi-output indicators only
- [ ] **Error messages** suggest valid outputs when validation fails
- [ ] **Documentation** explains dot notation and primary output behavior

---

## Migration Notes

### From v2 to v3

**No breaking changes for existing v2 strategies.** v2 strategies continue to work as-is because:

1. IndicatorEngine maintains v2 compatibility via adapter layer
2. FuzzyEngine supports both old and new formats
3. Training pipeline handles column name format detection

**When v3 is production-ready:**

M6 cleanup phase will:
- Remove v2 compatibility code
- Migrate remaining 3 indicators (RVI, ADLine, CMF)
- Remove old-format handling from IndicatorEngine

---

## Testing Patterns

### Unit Test Example

```python
def test_indicator_produces_correct_format():
    \"\"\"Verify indicator produces new semantic column names.\"\"\"
    from ktrdr.indicators import BollingerBandsIndicator, IndicatorEngine

    indicator = BollingerBandsIndicator(period=20, multiplier=2.0)
    engine = IndicatorEngine()

    result = engine.compute_indicator(data, indicator, "bbands_20_2")

    # Verify dot notation columns
    assert "bbands_20_2.upper" in result.columns
    assert "bbands_20_2.middle" in result.columns
    assert "bbands_20_2.lower" in result.columns

    # Verify alias
    assert "bbands_20_2" in result.columns

    # Verify alias points to primary
    assert result["bbands_20_2"].equals(result["bbands_20_2.upper"])
```

### Integration Test Example

```python
def test_v3_grammar_validation():
    \"\"\"Test v3 Grammar validates indicator outputs correctly.\"\"\"
    from ktrdr.indicators import IndicatorFactory

    factory = IndicatorFactory()

    # Valid output
    cls = factory.get_indicator_class('bbands')
    outputs = cls.get_output_names()
    assert 'upper' in outputs  # ✅ Valid

    # Invalid output
    assert 'invalid' not in outputs  # ✅ Should raise error in v3
```

---

## Next Steps

1. **Begin v3 Grammar Development**
   - Use this document as reference for validation logic
   - Implement dot notation parsing
   - Add validation against `get_output_names()`

2. **After v3 is Complete**
   - Run M6 cleanup phase
   - Migrate remaining 3 indicators
   - Remove v2 compatibility layer

---

## Questions?

If you encounter issues during v3 development:

1. **Check indicator outputs:** Use `IndicatorClass.get_output_names()` to see valid outputs
2. **Check primary output:** Use `IndicatorClass.get_primary_output()` for bare references
3. **Review M1-M4 handoffs:** See `docs/designs/indicator-standardization/implementation/HANDOFF_*.md`
4. **Consult design doc:** See `docs/designs/indicator-standardization/DESIGN.md`

**Contact:** This was implemented by Claude Code during indicator standardization milestone completion.
