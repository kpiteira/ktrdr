# M2 Handoff: IndicatorEngine V3

## Task 2.1 Complete: V3 Constructor

### Emergent Patterns

**V3 indicators use separate `_indicators` dict**
- V3 format stores indicators in `self._indicators: dict[str, BaseIndicator]`
- V2 format continues using `self.indicators: list[BaseIndicator]`
- This avoids conflicts and maintains backward compatibility
- Access pattern: `engine._indicators[indicator_id]` for v3

**BUILT_IN_INDICATORS registry is the source of truth**
- Located in `ktrdr.indicators.indicator_factory`
- Keys are lowercase: `BUILT_IN_INDICATORS.get(definition.type.lower())`
- Returns indicator class (e.g., `RSIIndicator`, `BollingerBandsIndicator`)
- No need to duplicate mapping logic - reuse existing registry

**Extra params accessed via `model_extra`**
- `IndicatorDefinition` stores all fields except `type` in `model_extra` attribute
- Pattern: `params = definition.model_extra or {}`
- Then pass to indicator: `indicator_class(**params)`
- Consistent with M1 handoff guidance

### Implementation Notes

**Indicator parameter storage**
- Indicators store params in `self.params` dict, NOT as direct attributes
- Access via: `indicator.params['period']`, NOT `indicator.period`
- This is BaseIndicator convention - applies to all indicators

**Error messages should be helpful**
- Unknown indicator type: Include available types in error message
- Failed instantiation: Include indicator_id, type, and original error
- Pattern: `raise ValueError(f"Failed to create '{indicator_id}' of type '{type}': {e}") from e`

### Gotchas

**Dict detection comes before list detection**
- Check `isinstance(indicators, dict)` FIRST
- V2 list check is `elif isinstance(indicators[0], dict)`
- This prevents `KeyError: 0` when passing a dict

**Indicator count logging**
- Log based on which format: `len(self._indicators) if self._indicators else len(self.indicators)`
- Don't assume one or the other is populated

### Files Modified

- `ktrdr/indicators/indicator_engine.py`: Lines 8, 35-144 (constructor + helper)
- `tests/unit/indicators/test_indicator_engine_v3.py`: New file, 94 lines, 6 tests (all passing)

---

## Task 2.2 Complete: V3 compute() Method

### Implementation Notes

**compute() method signature**
- Accepts: `data: pd.DataFrame, indicator_ids: set[str]`
- Returns: DataFrame with indicator columns added to original data
- NO timeframe prefix (that's for compute_for_timeframe())

**Column naming logic**
- Single-output: column name is `{indicator_id}`
- Multi-output: column names are `{indicator_id}.{output_name}`
- Uses `indicator.is_multi_output()` to determine which path

**Multi-output validation**
- Validates `set(output.columns) == set(indicator.get_output_names())`
- Raises ValueError if mismatch (helps catch indicator bugs early)
- Error message includes expected vs actual columns

**Error handling**
- Unknown indicator_id raises ValueError with clear message
- Multi-output validation catches implementation bugs

### Gotchas

**Set iteration order is non-deterministic**
- `for indicator_id in indicator_ids:` order varies across runs
- This is fine - compute() doesn't depend on order
- Consumers should not rely on column order

**Result is a copy, not mutated input**
- `result = data.copy()` at start
- Original data unchanged
- Safe for indicator chaining

### Files Modified

- `ktrdr/indicators/indicator_engine.py`: Lines 146-189 (compute() method)
- `tests/unit/indicators/test_indicator_engine_v3.py`: Lines 97-223 (5 new tests, all passing)

### Next Task Notes

**For Task 2.3 (compute_for_timeframe() helper):**
- Call `compute()` first to get unprefixed columns
- Add timeframe prefix to indicator columns only (not OHLCV)
- Pattern: `{timeframe}_{column}` for non-OHLCV columns
- OHLCV columns: `{'open', 'high', 'low', 'close', 'volume'}` (case-insensitive)
