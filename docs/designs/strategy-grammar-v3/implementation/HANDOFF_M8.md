# Handoff: Milestone 8 - Cleanup & Migration

## Task 8.1 Complete: Audit Existing Strategies

**Key findings:**
- 74 total strategies in project root `strategies/` (legacy, gitignored)
- 125 strategies in `~/.ktrdr/shared/strategies/` (actual user strategies)
- v1.5 experiment suite (23 strategies) is critical - used by `tests/unit/test_v15_template.py`

**Gotchas:**
- V3 detection: Look for `nn_inputs:` key (v2 strategies don't have it)
- V2 detection: Look for `feature_id:` in indicators list format
- **Important**: User strategies are in `~/.ktrdr/shared/strategies/`, not project root

---

## Task 8.2 Complete: Migrate Useful Strategies

**Location:** `~/.ktrdr/shared/strategies/` (125 strategies)

**What was done:**
- Migrated 121 v2 strategies to v3 format using `ktrdr strategies migrate ~/.ktrdr/shared/strategies/ --backup`
- Fixed mode values: `single_symbol` → `single`, `single_timeframe` → `single` (34 files)
- Fixed fuzzy_set `indicator` references for ADX/Aroon (12 files)
- Fixed MTF-prefixed indicator references like `DI_Plus_1h_14` → `adx_1h_14` (3 files)

**Gotchas:**
- Migration tool converts indicators from list to dict, but doesn't fix mode values
- fuzzy_set `indicator` field must match indicator ID (lowercase), not column names
- For multi-output indicators (ADX, Aroon), use base indicator ID: `adx_14` not `ADX_14`
- MTF strategies may have timeframe-prefixed IDs: `adx_1h_14`, `DI_Plus_1h_14` etc.
- Backup files created as `.bak` in strategies/ directory

**Test updates (for project root strategies/):**
- `tests/unit/test_v15_template.py` needed updates for v3 dict-based indicators
- Changed `isinstance(indicators, list)` → `isinstance(indicators, dict)`
- Changed iteration from `for ind in indicators` → `for ind_key, ind_config in indicators.items()`

**Final validation:** All 125 strategies in `~/.ktrdr/shared/strategies/` pass validation

**Next Task Notes (8.3):**
- Delete obsolete strategies from shared directory
- Note: Project root `strategies/` directory is legacy and should be removed eventually
- Backup files (.bak) can be deleted after verification
