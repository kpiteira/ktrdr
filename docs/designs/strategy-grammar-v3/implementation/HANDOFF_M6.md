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

---

## Task 6.2 Complete: Add CLI `strategy migrate` Command

### Implementation Notes

**Command location:** `ktrdr/cli/strategy_commands.py`

**Command usage:**
```bash
ktrdr strategies migrate <path> [--output PATH] [--backup] [--dry-run]
```

**Note:** The CLI uses `strategies` (plural) as the command group, not `strategy` (singular).

**Features implemented:**
- Single file migration with `--output` for alternate destination
- Directory migration (processes all *.yaml and *.yml files)
- `--backup` creates .bak file before overwriting in place
- `--dry-run` shows what would change without writing
- Automatic v3 format detection (skips already-migrated files)
- Post-migration validation with `StrategyConfigurationLoader`

### Gotchas

**Uses typer, not click**
- The CLI uses `typer` (not `click` as mentioned in design doc)
- Typer is built on click but has different API

**Parent directories created automatically**
- `out_path.parent.mkdir(parents=True, exist_ok=True)` ensures output directory exists

**Validation is non-blocking**
- Migration completes even if validation fails
- Shows warning instead of error (allows manual fixing)

### Files Modified

- `ktrdr/cli/strategy_commands.py`: Added `migrate` command (~80 lines)
- `tests/unit/cli/test_strategy_migrate.py`: New file, 9 tests

### Next Task Notes

Task 6.3 adds the CLI `strategy features` command. It should:
- Use `FeatureResolver.resolve(config)` to get resolved features
- Support `--group-by` option (none, timeframe, fuzzy_set)
- Display feature list in readable format

---
