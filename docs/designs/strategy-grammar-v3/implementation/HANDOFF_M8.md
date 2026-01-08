# Handoff: Milestone 8 - Cleanup & Migration

## Task 8.1 Complete: Audit Existing Strategies

**Key findings:**
- 74 total strategies: 1 v3, 73 v2
- 31 to migrate, 43 to delete
- v1.5 experiment suite (23 strategies) is critical - used by `tests/unit/test_v15_template.py`

**Gotchas:**
- V3 detection: Look for `nn_inputs:` key (v2 strategies don't have it)
- V2 detection: Look for `feature_id:` in indicators list format

---

## Task 8.2 Complete: Migrate Useful Strategies

**What was done:**
- Migrated all 73 v2 strategies to v3 format using `ktrdr strategies migrate strategies/ --backup`
- Fixed mode values: `single_symbol` → `single`, `single_timeframe` → `single`
- Fixed fuzzy_set `indicator` references for ADX/Aroon (must reference indicator ID, not output column)

**Gotchas:**
- Migration tool converts indicators from list to dict, but doesn't fix mode values
- fuzzy_set `indicator` field must match indicator ID (lowercase), not column names
- For multi-output indicators (ADX, Aroon), use base indicator ID: `adx_14` not `ADX_14`
- Backup files created as `.bak` in strategies/ directory

**Test updates required:**
- `tests/unit/test_v15_template.py` needed updates for v3 dict-based indicators
- Changed `isinstance(indicators, list)` → `isinstance(indicators, dict)`
- Changed iteration from `for ind in indicators` → `for ind_key, ind_config in indicators.items()`

**Next Task Notes (8.3):**
- All 74 strategies are now v3 format (including ones marked for deletion)
- Delete obsolete strategies per audit document `STRATEGY_AUDIT_M8.md`
- Backup files (.bak) can be deleted after verification
