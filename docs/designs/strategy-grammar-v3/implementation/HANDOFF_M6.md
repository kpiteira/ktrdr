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

---

## Task 6.3 Complete: Add CLI `strategy features` Command

### Implementation Notes

**Command location:** `ktrdr/cli/strategy_commands.py`

**Command usage:**
```bash
ktrdr strategies features <path> [--group-by none|timeframe|fuzzy_set]
```

**Features implemented:**
- Loads v3 strategy with `StrategyConfigurationLoader.load_v3_strategy()`
- Resolves features with `FeatureResolver.resolve(config)`
- Three display modes via `--group-by`:
  - `none` (default): Flat list of all features
  - `timeframe`: Groups features by timeframe with `[5m]`, `[1h]` headers
  - `fuzzy_set`: Groups by fuzzy set showing indicator reference
- Shows strategy name and total feature count
- Proper error handling for v2 strategies (suggests migration)

### Gotchas

**Rich markup escaping**
- Fuzzy set names in `[brackets]` need escaping for Rich console
- Used `\\[{fs_id}]` to display literal brackets

**v2 strategy detection**
- Catches `ValueError` from loader when format detection fails
- Shows helpful message suggesting `strategies migrate` command

### Files Modified

- `ktrdr/cli/strategy_commands.py`: Added `features` command (~75 lines)
- `tests/unit/cli/test_strategy_features.py`: New file, 9 tests

---

## Task 6.4 Complete: Update Strategy Commands Help Text

### Implementation Notes

**Files modified:**
- `ktrdr/cli/strategy_commands.py`: Updated module docstring and `strategies_app` help
- `ktrdr/cli/__init__.py`: Updated help text in `add_typer()` call

**Changes made:**
- Module docstring now lists all 6 commands including migrate and features
- `strategies_app` help includes v3 format mention and usage examples
- Main CLI registration updated to show "Manage trading strategies (v3 format)"

### Gotchas

**Help text override in main CLI**
- The `add_typer()` call in `__init__.py` overrides `strategies_app.help`
- Need to update both locations for changes to take effect

---

## Milestone 6 Complete: E2E Test Results

All E2E tests passed:

| Test | Description | Result |
|------|-------------|--------|
| Test 1 | Dry-run migration shows preview | ✅ PASS |
| Test 2 | Migration creates valid v3 file with nn_inputs | ✅ PASS |
| Test 3 | Validation passes on migrated strategy | ✅ PASS |
| Test 4 | Features listed correctly | ✅ PASS |
| Test 5 | Features grouped by timeframe | ✅ PASS |

**Note:** v2 strategies with `single_symbol` mode need `single` for v3 compatibility.
The migration does not auto-convert enum values, so source v2 files may need
manual adjustment if they use deprecated enum names.

---
