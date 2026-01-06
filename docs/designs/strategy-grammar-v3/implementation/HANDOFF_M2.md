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

### Next Task Notes

**For Task 2.2 (compute() method):**
- Use `self._indicators` dict for v3 code path
- Remember to check for unknown indicator_id
- Multi-output indicators need dot notation: `{indicator_id}.{output_name}`
- Single-output indicators: just `{indicator_id}`
- NO timeframe prefix in compute() - that's for compute_for_timeframe()
