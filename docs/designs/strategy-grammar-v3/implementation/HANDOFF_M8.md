# Handoff: Milestone 8 - Cleanup & Migration

## Task 8.1 Complete: Audit Existing Strategies

**Key findings:**
- 74 total strategies: 1 v3, 73 v2
- 31 to migrate, 43 to delete
- v1.5 experiment suite (23 strategies) is critical - used by `tests/unit/test_v15_template.py`

**Gotchas:**
- V3 detection: Look for `nn_inputs:` key (v2 strategies don't have it)
- V2 detection: Look for `feature_id:` in indicators list format

**Next Task Notes (8.2):**
- Audit document at `STRATEGY_AUDIT_M8.md` has full inventory
- Migration tool: `ktrdr strategy migrate strategies/ --backup`
- Test after migration: `ktrdr strategy validate <file>`
- v1.5 strategies have fixed parameters that tests validate - ensure migration preserves them
