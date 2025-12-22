# Repository Guidelines

## Collaboration & Working Style

- Karl provides long-term context and direction; the agent supplies focused analysis and honest pushback.
- Admit uncertainty instead of fabricating confidence; surface trade-offs and ask when context is missing.
- Call out disagreements respectfully; fix mistakes together without blame.

## Project Structure & Module Organization

Core backend (docker) code lives in `ktrdr/`, covering FastAPI services, async orchestration, PyTorch training, and database access. The React UI resides in `frontend/`, while the Model Context Protocol surface is under `mcp/`. Host-side executors (`ib-host-service/`, `training-host-service/`) run outside Docker; scripts and CLI entry points sit in `scripts/` and `ktrdr/__main__.py`. Reference designs, including the agent roadmap, are in `docs/agentic/`, and regression tests live in `tests/`.

## Architecture Snapshot

Distributed workers model: the backend orchestrates only; workers execute. Workers self-register on startup; GPU workers are preferred for training. Operations flow through `OperationsService`, and long-running jobs must stay cancellable. For full detail, see `docs/architecture-overviews/distributed-workers.md`.

## Think Before You Code

1. Understand the root cause and caller chain.
2. Consider architectural implications.
3. Propose the approach, confirm, then implement.

### When to Stop and Ask

- Changes touch core patterns or feel like a workaround.
- You need >3 files changed for a simple fix.
- Another try/except is needed to keep things running.
- Broader impact is unclear.

## Anti-Patterns to Avoid

- Never kill the API server with `lsof -ti:8000 | xargs kill`—it kills Docker containers.
- Avoid bandaid fixes: extra flags, copy/paste duplication, or swallowing errors instead of fixing roots.

## Build, Test, and Development Commands

- Always run Python via `uv run` (e.g., `uv run pytest`, `uv run ktrdr ...`).
- `uv run make test-unit` — run Python unit tests with pytest.
- `uv run make quality` — Ruff lint, Black format check, MyPy types.
- `uv run ktrdr --help` — inspect CLI capabilities.
- `./start_ktrdr.sh` — launch Docker stack plus IB host service.
- From `frontend/`: `npm install` once, then `npm run dev` and `npm run test`.
- Handy checks: `curl http://localhost:8000/api/v1/workers | jq` to see worker state.

## Coding Style & Naming Conventions

Python follows Black formatting (88 cols) and Ruff linting; prefer type annotations and descriptive module-level docstrings. Use `snake_case` for functions/variables, `PascalCase` for classes, and align async services with the task registry terminology. Frontend TypeScript code uses ESLint + Prettier defaults with `camelCase` for bindings and `PascalCase` for React components. Keep new docs in Markdown with concise headings.

## Testing Guidelines

Pytest drives backend tests in `tests/`; mirror module paths (e.g., `tests/async/test_registry.py`). Use fixtures for async workflows and assert task lifecycle transitions. Frontend components rely on Vitest and Testing Library; place specs beside source files (`Component.test.tsx`). Target meaningful coverage for orchestrator changes and add regression tests for new task states. Always run `make test-unit` and `make quality` before opening a PR.

## Commit & Pull Request Guidelines

Adopt the conventional commit style seen in `git log` (`type(scope): summary`), reference issue or slice IDs in parentheses, and keep commits focused. PRs should outline behavioural changes, include reproduction or validation steps, and link relevant docs. Attach screenshots or CLI transcripts when UI or task flows change. Confirm mandatory checks pass and note any integration gaps before requesting review.

## Before Making Changes

- Confirm module responsibilities and callers; trace data flow and side effects end-to-end.
- Check alignment with existing patterns, especially around async orchestration and task registry semantics.

## Debugging & Observability

- Start with Jaeger traces for operation IDs before diving into logs: `curl -s "http://localhost:16686/api/traces?tag=operation.id:$OPERATION_ID" | jq`.
- Prefer push notifications but ensure resilient polling fallbacks when diagnosing async flows.

## Service URLs (when running)

- Backend API: http://localhost:8000
- Swagger UI: http://localhost:8000/api/v1/docs
- Grafana: http://localhost:3000
- Jaeger UI: http://localhost:16686

## Skills & References

- Skill guides: distributed-workers, observability, deployment, api-development, debugging, integration-testing, memory-reflection.
- Async tips: the task registry in PostgreSQL is the single source of truth; align agent behaviours with `docs/agentic/architecture-doc.md` and keep long-running jobs cancellable with explicit progress updates.
