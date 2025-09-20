# Repository Guidelines

## Project Structure & Module Organization

Core backend (docker) code lives in `ktrdr/`, covering FastAPI services, async orchestration, PyTorch training, and database access. The React UI resides in `frontend/`, while the Model Context Protocol surface is under `mcp/`. Host-side executors (`ib-host-service/`, `training-host-service/`) run outside Docker; scripts and CLI entry points sit in `scripts/` and `ktrdr/__main__.py`. Reference designs, including the agent roadmap, are in `docs/agentic/`, and regression tests live in `tests/`.

## Build, Test, and Development Commands

- `uv run make test-unit` — run Python unit tests with pytest against the backend stack.
- `uv run make quality` — execute Ruff lint, Black format check, and MyPy type analysis.
- `uv run ktrdr --help` — inspect CLI capabilities before orchestrating jobs.
- `./start_ktrdr.sh` — launch the full Docker stack plus IB host service.
- From `frontend/`: `npm install` once, then `npm run dev` for the Vite dev server and `npm run test` for Vitest suites.

## Coding Style & Naming Conventions

Python follows Black formatting (88 cols) and Ruff linting; prefer type annotations and descriptive module-level docstrings. Use `snake_case` for functions/variables, `PascalCase` for classes, and align async services with the task registry terminology. Frontend TypeScript code uses ESLint + Prettier defaults with `camelCase` for bindings and `PascalCase` for React components. Keep new docs in Markdown with concise headings.

## Testing Guidelines

Pytest drives backend tests in `tests/`; mirror module paths (e.g., `tests/async/test_registry.py`). Use fixtures for async workflows and assert task lifecycle transitions. Frontend components rely on Vitest and Testing Library; place specs beside source files (`Component.test.tsx`). Target meaningful coverage for orchestrator changes and add regression tests for new task states. Always run `make test-unit` and `make quality` before opening a PR.

## Commit & Pull Request Guidelines

Adopt the conventional commit style seen in `git log` (`type(scope): summary`), reference issue or slice IDs in parentheses, and keep commits focused. PRs should outline behavioural changes, include reproduction or validation steps, and link relevant docs. Attach screenshots or CLI transcripts when UI or task flows change. Confirm mandatory checks pass and note any integration gaps before requesting review.

## Async & Agent Operations Tips

The task registry in PostgreSQL is the single source of truth—touch async code only after mapping CLI, MCP, and REST call sites. Prefer push-based notifications but maintain resilient polling fallbacks. When introducing agent behaviours, align with `docs/agentic/architecture-doc.md` and keep long-running jobs cancellable with explicit progress updates.
