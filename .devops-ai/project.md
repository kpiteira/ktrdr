# Project Configuration

This file is read by k* development commands (kdesign, kplan, kbuild, etc.)
to adapt workflows to this project's specific tooling and conventions.

## Project

- **Name:** ktrdr
- **Language:** Python
- **Runner:** uv — prefix for running commands

## Testing

- **Unit tests:** make test-unit
- **Quality checks:** make quality
- **Lint (fast):** uv run ruff check .
- **Integration tests:** make test-integration

## Infrastructure

- **Start:** uv run kinfra sandbox up
- **Stop:** uv run kinfra sandbox down
- **Logs:** docker compose logs -f
- **Health check:** curl -f http://localhost:${KTRDR_API_PORT:-8000}/api/v1/health

## E2E Testing

- **E2E tests:** ke2e-test-runner agent against running sandbox
- **Test catalog:** .claude/skills/ke2e/tests/

## Paths

- **Design documents:** docs/designs/
- **Implementation plans:** implementation/ subfolder within design
- **Handoff files:** Same directory as implementation plans

## Project-Specific Patterns

- Always use `uv run` for Python commands (project uses uv, not pip)
- Strategy files live in `strategies/*.yaml` (v3 format)
- Shared data directories: `~/.ktrdr/shared/` (data, models, strategies)
- Host services (training-host for GPU, ib-host for IB Gateway) run natively on macOS, not in Docker
- Never kill processes on port 8000 — the API runs in Docker; killing it destroys the container
- Use `runner` fixture from `tests/unit/cli/conftest.py` for CLI tests (CleanCliRunner strips ANSI codes)
- Docker hot-reload: code changes auto-reload in containers via volume mounts
