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
