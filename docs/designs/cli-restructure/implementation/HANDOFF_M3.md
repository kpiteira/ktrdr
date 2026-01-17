# Milestone 3 Handoff

Running notes for M3 CLI restructure implementation.

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
- **Feature resolution is local-only:** The `/strategies/{name}/features` API endpoint doesn't exist. Features command uses local file loading via `StrategyConfigurationLoader().load_v3_strategy()` and `FeatureResolver().resolve()`.

### Next Task Notes

- Task 3.3 (validate command) supports both API validation (by name) and local file validation (paths starting with `./` or `/`). The local validation path is intentional for pre-deployment testing.
- Task 3.5 wires up show_app with `app.add_typer(show_app)`, same pattern as list_app.
