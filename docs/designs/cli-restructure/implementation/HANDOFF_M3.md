# Milestone 3 Handoff

Running notes for M3 CLI restructure implementation.

---

## Known Technical Debt

**Dual Command Registration:** M2/M3 commands are registered in BOTH:
- `ktrdr/cli/__init__.py` (actual CLI entry point via `cli_app`)
- `ktrdr/cli/app.py` (test entry point, intended to be the new clean app)

This violates DRY and is error-prone (can get out of sync).

**Resolution:** M5 Task 5.3 will consolidate to `app.py` as single source of truth:
- `__init__.py` will just do `from ktrdr.cli.app import app`
- `pyproject.toml` will point to `ktrdr.cli.app:app`

**Until then:** When adding new commands, register in BOTH places to maintain consistency.

---

## Task 3.1 Complete: Implement List Command

### Gotchas

- **API response formats differ:** Strategies endpoint returns `{"strategies": [...]}`, models returns `{"models": [...]}`, checkpoints returns `{"data": [...], "total_count": N}`. Always check actual endpoint implementation.
- **Strategy format varies:** Old format has `symbol`/`timeframe` as strings, v3 has `training_data.symbols`/`training_data.timeframes` as arrays. Implementation checks for both.
- **Use `AsyncCLIClient()` without base_url:** Per M2 handoff, the `resolve_url()` function auto-appends `/api/v1` only when no explicit URL is passed.

### Emergent Patterns

- **Typer subcommand group pattern:** Use `typer.Typer(name="list")` and register with `app.add_typer(list_app)`. Tests clean up with `app.registered_groups = [g for g in app.registered_groups if g.typer_instance != list_app]`.
- **JSON output pattern:** Check `state.json_mode`, then `print(json.dumps(data))` and return early. Table rendering only happens when not in JSON mode.
- **Status color coding:** Use `[green]`, `[yellow]`, `[red]` Rich markup for status display based on value.

### Next Task Notes

- Task 3.2 (show command) has dual mode: `ktrdr show <symbol>` for data, `ktrdr show features <strategy>` for features. Use typer callback with `invoke_without_command=True` pattern.
- Task 3.5 wires up all M3 commands - list_app uses `app.add_typer()`, not `app.command()`.

---

## Task 3.2 Complete: Implement Show Command

### Gotchas

- **Typer callback + positional args + subcommands conflict:** The plan suggested `ktrdr show <symbol>` with a callback that has positional arguments + `invoke_without_command=True`. This DOESN'T work - Typer consumes arguments before recognizing subcommands. `show features path.yaml` parses as `symbol="features", timeframe="path.yaml"`, not as invoking the `features` subcommand.
- **Solution: Explicit subcommands:** Changed to `ktrdr show data <symbol>` and `ktrdr show features <strategy>`. This is cleaner and works correctly.
- **V3 strategy format:** The `_is_v3_format()` check expects `indicators` to be a **dict** (not a list) and `nn_inputs` to be present. Test YAML must use the correct v3 format with indicators as a dict with named keys.
- **Data API response format:** `/data/{symbol}/{timeframe}` returns `{"success": true, "data": {"dates": [...], "ohlcv": [[o,h,l,c,v], ...]}}`

### Emergent Patterns

- **Subcommand-only approach works best:** When a command has both default behavior AND subcommands, make everything explicit subcommands. Don't mix callback positional args with subcommands.
- **API endpoint created for features:** Added `GET /strategies/{name}/features` endpoint that uses `FeatureResolver` to resolve and return features. CLI is now properly thin and calls this endpoint.

### Next Task Notes

- Task 3.3 (validate command) supports both API validation (by name) and local file validation (paths starting with `./` or `/`). The local validation path is intentional for pre-deployment testing.
- Task 3.5 wires up show_app with `app.add_typer(show_app)`, same pattern as list_app.

---

## Task 3.3 Complete: Implement Validate Command

### Gotchas

- **Command registration requires explicit name:** Using `app.command()(validate_cmd)` creates a command named `validate-cmd` (from function name). Must use `app.command("validate")(validate_cmd)` to get the expected `validate` name.
- **Two CLI entry points:** The `ktrdr` command uses `cli_app` from `ktrdr/cli/__init__.py`, not `app` from `ktrdr/cli/app.py`. M3 commands must be registered in both places (app.py for tests, __init__.py for actual CLI).
- **API validation uses POST:** The `/strategies/validate/{name}` endpoint uses POST, not GET. Returns `{valid, strategy_name, issues, message}`.
- **Local path detection:** Check for `./` or `/` prefix to detect local paths. Names without prefix go to API.
- **V3 format detection:** Check `isinstance(config.get("indicators"), dict) and "nn_inputs" in config`.

### Emergent Patterns

- **Test cleanup pattern:** Use helper functions `_register_validate_cmd(app)` and `_cleanup_validate_cmd(app)` to manage command registration/cleanup in tests.
- **Dual mode pattern:** For commands that work differently based on input type (name vs path), use simple prefix detection in the main function, then delegate to specialized handlers.
- **Patch location matters:** When imports are inside functions, patch at the source module (`ktrdr.config.strategy_loader.StrategyConfigurationLoader`), not at the usage module.

### Next Task Notes

- Task 3.4 (migrate command) is similar to validate but focuses on v2→v3 conversion. Uses local-only validation (no API call needed).
- Task 3.5 wires up all M3 commands in `ktrdr/cli/__init__.py` (the actual entry point) using `cli_app.add_typer()` for subcommand groups and `cli_app.command("name")(func)` for direct commands.

---

## Task 3.4 Complete: Implement Migrate Command

### Gotchas

- **Local-only command:** Unlike validate, migrate doesn't need API calls — uses `migrate_v2_to_v3` from `ktrdr.config.strategy_migration` directly.
- **V3 detection uses same pattern as validate:** Check `isinstance(config.get("indicators"), dict) and "nn_inputs" in config`.
- **Default output path:** Creates `{name}_v3.yaml` in same directory as input file (not overwriting original).
- **Parent directory creation:** Uses `output_path.parent.mkdir(parents=True, exist_ok=True)` to handle custom output paths.

### Emergent Patterns

- **Simplified command structure:** No API calls means simpler implementation — just file I/O + migration function call.
- **Consistent JSON output format:** Uses `{"status": "migrated"|"skipped", ...}` pattern for machine readability.
- **Graceful skip for already-v3:** Returns success (exit 0) with informative message, not an error.

### Next Task Notes

- Task 3.5 wires up all M3 commands. Migrate command uses `cli_app.command("migrate")(migrate_cmd)` (same pattern as validate).
- All M3 commands now implemented: list_app, show_app, validate_cmd, migrate_cmd.

---

## Task 3.5 Complete: Wire Up Information Commands

### Gotchas

- **M3 commands were already wired up:** Tasks 3.1-3.4 each wired up their commands in both `app.py` (test entry point) and `__init__.py` (actual CLI entry point). Task 3.5 just needed to verify and add tests.
- **Test pollution was the real issue:** Tests in `test_list_cmd.py`, `test_show.py`, `test_validate.py`, and `test_migrate.py` manually register commands with `add_typer()` or `app.command()`, then remove them in cleanup. This removes the commands that were already registered at module import time.
- **autouse fixture needed for restoration:** Added `_restore_m3_commands()` function in `conftest.py` that restores all M3 commands if they were removed by a test.

### Emergent Patterns

- **Test isolation via autouse fixture:** The `cleanup_app_commands` autouse fixture in `tests/unit/cli/conftest.py` now:
  1. Removes known test-only commands (test-cmd, capture-*, etc.)
  2. Restores M3 commands (list, show, validate, migrate) if they were removed
  3. Runs both before AND after each test to handle pollution from previous tests

### Files Changed

- `tests/unit/cli/test_app.py`: Added `TestM3CommandsRegistration` class with 5 tests
- `tests/unit/cli/conftest.py`: Added `_cleanup_test_commands()`, `_restore_m3_commands()`, enhanced `cleanup_app_commands` fixture

### Next Task Notes

- M3 is complete. The M3 E2E validation test should be run to verify all commands work end-to-end with the backend.
- M4 will implement alias commands and deprecation notices for old command paths.
