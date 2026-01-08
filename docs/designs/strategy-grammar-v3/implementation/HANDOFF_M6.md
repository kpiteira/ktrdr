# M6 Handoff: CLI & Migration Tools

## Task 6.1 Complete: Create Migration Logic

### Implementation Notes

**Module location:** `ktrdr/config/strategy_migration.py`

**Key functions:**
- `migrate_v2_to_v3(v2_config: dict) -> dict` - Converts v2 strategy to v3 format
- `validate_migration(original: dict, migrated: dict) -> list[str]` - Validates migration preserved data

**Migration rules implemented (per ARCHITECTURE.md lines 617-624):**
1. Convert `indicators` list to dict (key = feature_id, `type` = name)
2. Add `indicator` field to fuzzy_sets (defaults to fuzzy_set key)
3. Generate `nn_inputs` from fuzzy_sets (each gets `timeframes: "all"`)
4. Update version to "3.0"

### Gotchas

**Deep copy is critical**
- The function uses `copy.deepcopy()` to avoid modifying the original config
- Tests verify original config remains unchanged after migration

**feature_id fallback**
- If an indicator lacks `feature_id`, falls back to `name` as the key
- This handles edge cases in older configs

**Existing indicator field preserved**
- If a fuzzy_set already has `indicator` field, it's preserved (not overwritten)
- Allows partial migrations or manually-specified relationships

### Files Created

- `ktrdr/config/strategy_migration.py`: Migration logic (~75 lines)
- `tests/unit/config/test_strategy_migration.py`: 15 unit tests

### Next Task Notes

Task 6.2 adds the CLI `strategy migrate` command. It should:
- Import `migrate_v2_to_v3` and `validate_migration` from `ktrdr.config.strategy_migration`
- Use click for CLI arguments (path, --output, --backup, --dry-run)
- Use `StrategyConfigurationLoader` for validation after migration

---
