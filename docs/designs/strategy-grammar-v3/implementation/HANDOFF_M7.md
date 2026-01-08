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

## Task 7.3 Complete: Update MCP Strategy Tools

### Implementation Notes

**Files created:**

1. `ktrdr/mcp/__init__.py` - Package init exposing `validate_strategy`
2. `ktrdr/mcp/strategy_service.py` - Business logic for MCP tools

**File modified:**

3. `mcp/src/tools/strategy_tools.py` - MCP tool wrapper updated

**Architecture decision:**
- Created a new `ktrdr/mcp/` package for MCP business logic
- This separates business logic from FastMCP dependencies
- Allows unit testing without needing MCP server
- The existing `strategy_tools.py` had broken imports from non-existent `research_agents` package

**`validate_strategy()` function:**
- Takes a file path, returns dict with validation results
- Detects v3 vs v2 format based on indicators structure
- For v3: returns `valid: True`, `format: "v3"`, resolved `features` list, `feature_count`
- For v2: returns `valid: False`, `format: "v2"`, `errors`, `suggestion` with migration command
- Handles file not found and YAML parse errors gracefully

### Gotchas

**MCP imports require FastMCP at import time**
- Can't directly test `mcp/src/tools/strategy_tools.py` in unit tests
- The `ktrdr/mcp/strategy_service.py` is the testable business logic layer
- Tests import from `ktrdr.mcp.strategy_service`, not from MCP tools

**The `research_agents` package doesn't exist**
- Was declared in `pyproject.toml` but never created
- Removed the broken `save_strategy_config` and `get_recent_strategies` tools
- They can be added back later when `research_agents` is implemented

### Files Created/Modified

- `ktrdr/mcp/__init__.py`: New package init
- `ktrdr/mcp/strategy_service.py`: New service with `validate_strategy()`
- `mcp/src/tools/strategy_tools.py`: Updated to use new service, removed broken tools
- `tests/unit/mcp/test_strategy_tools_v3.py`: New file with 7 tests

---

## M7 COMPLETE: Agent Integration

All 3 tasks completed. M7 E2E tests pass.

**Summary:**
- Task 7.1: Strategy generation prompt updated to v3 format
- Task 7.2: Strategy utilities added for v3 validation and feature extraction
- Task 7.3: MCP strategy tools updated to validate v3 format

**Next steps:**
- Merge to main when ready
- M8 can proceed with training pipeline integration
