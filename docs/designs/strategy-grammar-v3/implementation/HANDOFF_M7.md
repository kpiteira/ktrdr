# M7 Handoff: Agent Integration

## Task 7.1 Complete: Update Strategy Generation Prompt

### Implementation Notes

**File modified:** `ktrdr/agents/prompts.py`

**Key changes to SYSTEM_PROMPT_TEMPLATE:**
- YAML template updated from v2 to v3 format
- `indicators` is now a dict keyed by indicator_id (e.g., `rsi_14: { type: rsi, period: 14 }`)
- Each fuzzy set has `indicator` field referencing an indicator_id
- Added `nn_inputs` section as a required list
- Removed all `feature_id` references from v2 format

### Gotchas

**Enum values are `single` not `single_timeframe`**
- `TimeframeMode` enum uses `single` and `multi_timeframe`
- The initial implementation used `single_timeframe` which failed Pydantic validation
- Check `ktrdr/config/models.py` for exact enum values when in doubt

**SYSTEM_PROMPT_TEMPLATE is the main constant**
- The prompt builder class uses `self._system_template = SYSTEM_PROMPT_TEMPLATE`
- Tests should import and check `SYSTEM_PROMPT_TEMPLATE` directly

### Files Created/Modified

- `ktrdr/agents/prompts.py`: Updated SYSTEM_PROMPT_TEMPLATE (~66 lines changed)
- `tests/unit/agents/test_prompts_v3.py`: New file with 9 tests

---

## Next Task Notes (7.2: Update Strategy Utilities)

**Files to modify:** `ktrdr/agents/strategy_utils.py`

**Key imports needed:**
- `from ktrdr.config.models import StrategyConfigurationV3`
- `from ktrdr.config.strategy_validator import validate_v3_strategy`
- `from ktrdr.config.feature_resolver import FeatureResolver`

**Functions to update:**
- `parse_strategy_response()` - Already handles YAML extraction, may need minor v3 adjustments
- `validate_agent_strategy()` - Should check for v3 markers (indicators dict, nn_inputs present)
- `extract_features()` - Use FeatureResolver to get resolved features

**Pattern from M6 handoff:** The validation should reject v2 format with clear error messages like "indicators must be a dict (v3 format)" and "nn_inputs section required (v3 format)"
