# CLI Restructure Implementation Plan

## Reference Documents

- **Design:** [../DESIGN.md](../DESIGN.md)
- **Architecture:** [../ARCHITECTURE.md](../ARCHITECTURE.md)
- **Validation:** [../VALIDATION.md](../VALIDATION.md)

## Milestone Summary

| # | Name | Tasks | E2E Test | Status |
|---|------|-------|----------|--------|
| M1 | [Core Infrastructure + Train](M1_core_infrastructure.md) | 6 | `ktrdr train` starts operation | ⏳ |
| M2 | [Operation Commands](M2_operation_commands.md) | 8 | `ktrdr follow` shows progress | ⏳ |
| M3 | [Information Commands](M3_information_commands.md) | 5 | `ktrdr list strategies` works | ⏳ |
| M4 | [Performance](M4_performance.md) | 3 | `ktrdr --help` < 100ms | ⏳ |
| M5 | [Cleanup + Documentation](M5_cleanup.md) | 4 | Old commands removed cleanly | ⏳ |

**Total Tasks:** 26

## Dependency Graph

```
M1 → M2 → M3 → M4 → M5
```

All milestones are linear — each builds on the previous.

## Architecture Patterns

These patterns from ARCHITECTURE.md must be followed in all tasks:

| Pattern | Description | Verification |
|---------|-------------|--------------|
| **Lazy Imports** | Heavy deps imported inside functions | No pandas/OTEL at module top |
| **Unified Operation Runner** | Single code path for operations | Uses `OperationRunner.start()` |
| **Fire-and-Follow** | Default returns immediately | `--follow` triggers polling |
| **Global State via Callback** | `--json`, `--verbose` in root callback | `CLIState` passed to commands |
| **Strategy Names over Paths** | CLI sends names to API | No file path resolution in CLI |

## What We're NOT Doing

- No horizontal splitting (each command file is self-contained)
- No new polling logic (reuse `AsyncCLIClient.execute_operation()`)
- No CLI-side strategy parsing (backend handles resolution)
- No deprecation aliases (old commands removed completely)

## Key Implementation Notes

1. **Preserve existing UX** — The progress display code in `client/operations.py` and `agent_commands.py` works well. We're restructuring commands, not rewriting monitoring.

2. **Parallel development** — M1 creates new files alongside existing code. No modifications to existing commands until M5.

3. **Testing strategy** — Each command has unit tests for argument parsing and integration tests for API communication.
