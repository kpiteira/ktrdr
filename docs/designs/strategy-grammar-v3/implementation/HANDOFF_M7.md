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

## Task 7.2 Complete: Update Strategy Utilities

### Implementation Notes

**File modified:** `ktrdr/agents/strategy_utils.py`

**Three new functions added:**

1. `parse_strategy_response(response: str) -> dict`
   - Extracts YAML from markdown code blocks (`yaml` or generic ```)
   - Falls back to raw YAML parsing if no code blocks
   - Returns empty dict on parse failure

2. `validate_agent_strategy(config: dict) -> tuple[bool, list[str]]`
   - Quick v3 format checks first (indicators dict, nn_inputs present)
   - Full Pydantic validation if basic checks pass
   - Returns `(is_valid, messages)` tuple

3. `extract_features(config: dict) -> list[str]`
   - Uses `FeatureResolver` to resolve nn_inputs
   - Returns list of feature IDs like `['1h_rsi_momentum_oversold', ...]`
   - Raises `ValidationError` for invalid configs

### Gotchas

**Functions are synchronous (not async)**
- Unlike existing functions in the file (`validate_strategy_config`, `save_strategy_config`)
- These are simple utility functions that don't need async

**Imports are inside functions**
- Heavy imports like `StrategyConfigurationV3` are inside function bodies
- Avoids circular import issues and speeds up module load

### Files Created/Modified

- `ktrdr/agents/strategy_utils.py`: Added 3 functions (~116 lines)
- `tests/unit/agents/test_strategy_utils_v3.py`: New file with 11 tests

---

## Next Task Notes (7.3: Update MCP Strategy Tools)

**Files to check:** `mcp/src/tools/strategy_tools.py`

**Note:** This task may need investigation - the milestone plan mentions MCP tools but check if they exist. If not present, may need to skip or adapt.

**Expected functionality:**
- `validate_strategy()` - Should use v3 loader and return format info
- Return `format: "v3"` or `format: "v2"` with migration suggestion
- Include resolved feature count for v3 strategies
