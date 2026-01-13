# CLI Testing Guidelines

## The `runner` Fixture (CRITICAL)

**ALWAYS use the `runner` fixture** when testing CLI commands that check output:

```python
# ✅ CORRECT
def test_help_shows_flags(self, runner) -> None:
    result = runner.invoke(app, ["--help"])
    assert "--json" in result.output

# ❌ WRONG - will fail in CI
def test_help_shows_flags(self) -> None:
    runner = CliRunner()  # Don't create your own!
    result = runner.invoke(app, ["--help"])
    assert "--json" in result.output
```

### Why This Matters

Rich/Typer outputs ANSI color codes differently in CI vs local:
- **Local:** Terminal renders or strips codes, assertions pass
- **CI:** Raw codes appear in output (`\x1b[1;36m--json\x1b[0m`), assertions fail

The `runner` fixture provides `CleanCliRunner` which:
1. Sets `NO_COLOR=1` environment variable
2. Strips any remaining ANSI escape codes from `result.output`

### When to Use the Fixture

| Test Type | Use `runner` fixture? |
|-----------|----------------------|
| Checking help text output | ✅ YES |
| Checking command output | ✅ YES |
| Testing state capture via dynamic commands | Create own CliRunner |
| Testing exit codes only | Either works |

## Dynamic Command Registration Pattern

When tests need to capture internal state, they register temporary commands:

```python
def test_state_captured(self) -> None:
    from ktrdr.cli.app import app

    runner = CliRunner()  # OK here - not checking output text
    captured_state = None

    @app.command()
    def test_cmd(ctx: typer.Context) -> None:
        nonlocal captured_state
        captured_state = ctx.obj

    try:
        result = runner.invoke(app, ["test-cmd"])
        assert result.exit_code == 0
        assert captured_state is not None
    finally:
        # ALWAYS clean up registered commands
        app.registered_commands = [
            cmd for cmd in app.registered_commands if cmd.name != "test-cmd"
        ]
```

**Important:** Always clean up in a `finally` block to avoid polluting other tests.

## Common Patterns

### Testing Global Flags

```python
def test_json_flag_sets_state(self, runner) -> None:
    # Use runner fixture for output checks
    result = runner.invoke(app, ["--json", "some-command"])
    assert result.exit_code == 0
```

### Testing Command Registration

```python
def test_train_command_exists(self, runner) -> None:
    result = runner.invoke(app, ["--help"])
    assert "train" in result.output.lower()
```

### Testing Command Help

```python
def test_train_help(self, runner) -> None:
    result = runner.invoke(app, ["train", "--help"])
    assert "--start" in result.output
    assert "--end" in result.output
```

## Files Reference

- `conftest.py` - Contains `runner` fixture, `CleanCliRunner`, `CleanResult`
- `test_app.py` - Tests for main app entry point
- `commands/test_train.py` - Tests for train command
