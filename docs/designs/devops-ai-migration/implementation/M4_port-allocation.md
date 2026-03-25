---
design: docs/designs/devops-ai-migration/DESIGN.md
architecture: docs/designs/devops-ai-migration/ARCHITECTURE.md
---

# M4: Port Allocation + infra.toml

Replace hardcoded Python port allocation with declarative infra.toml config. Add design and assessment worker services. Migrate from per-project registry to devops-ai's global registry. Use stride-based port spacing to eliminate collisions.

## Context

**Current state:**
- `sandbox_ports.py` hardcodes port allocation with mixed-offset formulas
- 4 workers (2 backtest, 2 training) — no design or assessment workers
- Per-project registry at `~/.ktrdr/sandbox/instances.json`
- Port variables: `KTRDR_WORKER_PORT_1..4` (non-semantic names)

**Target state:**
- `.devops-ai/infra.toml` declares ports with stride-based bases (100 apart for workers)
- 6 workers (1 design, 2 backtest, 2 training, 1 assessment)
- Global registry at `~/.devops-ai/registry.json`
- Semantic port variable names: `KTRDR_DESIGN_WORKER_PORT`, `KTRDR_BACKTEST_WORKER_PORT_1`, etc.

**Critical: All existing sandboxes must be torn down before this milestone.** The port formula changes produce different ports for worker services.

---

## Task 4.1: Create infra.toml

**File(s):** `.devops-ai/infra.toml`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Create the infra.toml configuration file that devops-ai's kinfra reads for sandbox configuration. Define project metadata, compose file reference, health check config, stride-based port allocation, volume mounts, OTEL config, and 1Password secret references.

**Implementation Notes:**
- Port bases must be spaced 100 apart to prevent cross-slot collisions with `base + slot_id` formula:
  ```toml
  [sandbox.ports]
  KTRDR_API_PORT = 8000
  KTRDR_DB_PORT = 5432
  KTRDR_DESIGN_WORKER_PORT = 6100
  KTRDR_BACKTEST_WORKER_PORT_1 = 6200
  KTRDR_BACKTEST_WORKER_PORT_2 = 6300
  KTRDR_TRAINING_WORKER_PORT_1 = 6400
  KTRDR_TRAINING_WORKER_PORT_2 = 6500
  KTRDR_ASSESSMENT_WORKER_PORT = 6600
  ```
- Health endpoint: `/api/v1/health` on `KTRDR_API_PORT`, timeout 120s
- Mounts: code dirs to all 7 service targets, shared dirs (data/models/strategies)
- OTEL: `endpoint_var = "KTRDR_OTEL_OTLP_ENDPOINT"` (already using shared stack from M3)
- Secrets: 1Password references using `op://` syntax for ktrdr-sandbox-dev item
- Verify infra.toml validates with devops-ai's config parser: `kinfra status` should parse it

**Testing Requirements:**
- [ ] infra.toml is valid TOML (parse with Python `tomllib`)
- [ ] All port bases are at least 100 apart (no collision possible)
- [ ] Port formula produces correct values: slot 1 → 8001, 5433, 6101, 6201, 6301, 6401, 6501, 6601
- [ ] Health endpoint matches actual backend health path
- [ ] Secret references use valid `op://` format

**Acceptance Criteria:**
- [ ] `.devops-ai/infra.toml` exists and parses correctly
- [ ] `kinfra status` reads the config (or fails gracefully if kinfra not yet global)
- [ ] Port allocation documented with slot example table

---

## Task 4.2: Add design and assessment workers to compose

**File(s):** `docker-compose.sandbox.yml`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Add design-worker and assessment-worker service definitions to the compose file. Update port variable names from `KTRDR_WORKER_PORT_1..4` to semantic names for all workers.

**Implementation Notes:**
- Design worker: modeled after existing workers but with `WORKER_TYPE=design`
  - Port: `${KTRDR_DESIGN_WORKER_PORT:-6100}:6100`
  - Internal port: 6100 (matches new allocation)
  - Command: uvicorn for design worker app (check existing worker entry points)
  - `KTRDR_WORKER_PORT=6100`
  - `KTRDR_WORKER_PUBLIC_BASE_URL=http://design-worker:6100`
- Assessment worker: similar with `WORKER_TYPE=assessment`
  - Port: `${KTRDR_ASSESSMENT_WORKER_PORT:-6600}:6600`
  - Internal port: 6600
- Rename existing worker ports:
  - backtest-worker-1: `${KTRDR_BACKTEST_WORKER_PORT_1:-6200}:6200` (was `KTRDR_WORKER_PORT_1:-5003}:5003`)
  - backtest-worker-2: `${KTRDR_BACKTEST_WORKER_PORT_2:-6300}:6300` (was `KTRDR_WORKER_PORT_2:-5004}:5004`)
  - training-worker-1: `${KTRDR_TRAINING_WORKER_PORT_1:-6400}:6400` (was `KTRDR_WORKER_PORT_3:-5005}:5005`)
  - training-worker-2: `${KTRDR_TRAINING_WORKER_PORT_2:-6500}:6500` (was `KTRDR_WORKER_PORT_4:-5006}:5006`)
- Update internal ports in `KTRDR_WORKER_PORT` env var and uvicorn command for each worker
- Update health check ports to match new internal ports
- All workers connect to both `ktrdr-network` and `devops-ai-observability`
- IMPORTANT: Update `KTRDR_WORKER_PUBLIC_BASE_URL` for each worker to use new port

**Testing Requirements:**
- [ ] `docker compose -f docker-compose.sandbox.yml config` validates
- [ ] All 6 workers defined with correct ports
- [ ] Each worker has correct WORKER_TYPE
- [ ] Health checks reference correct internal ports
- [ ] PUBLIC_BASE_URL matches service name and port

**Acceptance Criteria:**
- [ ] Compose file has 6 worker services (1D + 2B + 2T + 1A)
- [ ] Port variable names are semantic (not numbered)
- [ ] Compose validates without errors

---

## Task 4.3: Update sandbox_ports.py for new allocation

**File(s):** `ktrdr/cli/sandbox_ports.py`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Update the port allocation to use stride-based bases matching infra.toml. This is an interim step — sandbox_ports.py will be fully replaced when kinfra migrates (M5), but the embedded kinfra still reads it for now.

**Implementation Notes:**
- Replace the `get_ports()` function to return ports matching infra.toml:
  - API: 8000 + slot
  - DB: 5432 + slot
  - Design worker: 6100 + slot
  - Backtest worker 1: 6200 + slot
  - Backtest worker 2: 6300 + slot
  - Training worker 1: 6400 + slot
  - Training worker 2: 6500 + slot
  - Assessment worker: 6600 + slot
- Update `PortAllocation` dataclass fields to use semantic names
- Update `to_env_dict()` to emit new variable names
- Update any references to old `KTRDR_WORKER_PORT_1..4` in the codebase
- Search for hardcoded old port numbers (5003-5006) in Python code and update
- Slot 0 (local-prod) gets base ports directly

**Testing Requirements:**
- [ ] Unit tests for `get_ports()` updated to verify new formula
- [ ] Slot 0: API=8000, DB=5432, workers at base ports
- [ ] Slot 1: API=8001, DB=5433, design=6101, backtest1=6201, etc.
- [ ] Slot 2: API=8002, DB=5434, design=6102, backtest1=6202, etc.
- [ ] No port collision between any two slots (0-10)
- [ ] `make quality` passes
- [ ] `make test-unit` passes

**Acceptance Criteria:**
- [ ] Port formula matches infra.toml exactly
- [ ] All old port variable names removed from code
- [ ] No collision possible between slots

---

## Task 4.4: Update .env.sandbox generation

**File(s):** `ktrdr/cli/kinfra/sandbox.py`, `ktrdr/cli/sandbox_detect.py`
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Update .env.sandbox file generation to emit new port variable names and remove observability port variables.

**Implementation Notes:**
- The `generate_env_file()` function in `sandbox.py` calls `PortAllocation.to_env_dict()`
- After task 4.3, `to_env_dict()` returns new variable names — verify the generated .env.sandbox has correct content
- Remove any remaining observability port variables from template/generation
- `sandbox_detect.py` reads .env.sandbox to resolve API URL — verify it still works with new variable names (it reads `KTRDR_API_PORT` which is unchanged)
- Override template in `override.py` may reference old `KTRDR_WORKER_PORT_*` variables — update to new names

**Testing Requirements:**
- [ ] Generated .env.sandbox contains all 8 new port variables
- [ ] No observability port variables in generated file
- [ ] `sandbox_detect.py::resolve_api_url()` still finds correct port
- [ ] Override template uses new variable names

**Acceptance Criteria:**
- [ ] .env.sandbox generation produces correct variables
- [ ] API URL resolution works with new ports
- [ ] Override file references correct new variable names

---

## Task 4.5: Tear down and rebuild sandboxes

**File(s):** (infrastructure — no code files)
**Type:** MIXED
**Estimated time:** 1 hour

**Description:**
Tear down all existing sandboxes and rebuild with new port allocation. This is a "break the world" step — all existing sandbox instances must be destroyed because port assignments change.

**Implementation Notes:**
- List active sandboxes: `uv run kinfra worktrees` or check `~/.ktrdr/sandbox/instances.json`
- For each active sandbox: `uv run kinfra sandbox down` (in the worktree)
- For local-prod: `uv run kinfra local-prod down` (if running)
- After tear down, rebuild local-prod with new ports: `uv run kinfra local-prod up`
- Any active worktree sandboxes: recreate with `uv run kinfra sandbox up`
- Verify workers register on new ports: `curl http://localhost:${API_PORT}/api/v1/workers`
- Check for 6 workers (1D + 2B + 2T + 1A) vs previous 4

**Testing Requirements:**
- [ ] No containers running on old ports (5003-5006)
- [ ] Workers running on new ports (6100, 6200, 6300, 6400, 6500, 6600 + slot offset)
- [ ] All 6 workers register with backend
- [ ] Health endpoints respond on new ports

**Acceptance Criteria:**
- [ ] All sandboxes rebuilt with new port allocation
- [ ] 6 workers per sandbox (up from 4)
- [ ] No old port references in running containers

---

## Task 4.6: Validation — multi-slot port isolation

**File(s):** (none — validation only)
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Validate that two concurrent sandbox slots have completely isolated ports. Run E2E tests against both to prove no collisions.

**Implementation Notes:**
- Requires two worktrees with sandbox slots or local-prod + one sandbox
- This is the highest-risk validation in the entire migration

**Validation Steps:**
1. Load the `ke2e` skill
2. Invoke ke2e-test-scout with requirement: "Validate port isolation between concurrent sandbox slots — two sandboxes run simultaneously without port conflicts"
3. If no existing test matches, design validation:
   - Start sandbox slot 1 (or local-prod slot 0)
   - Start sandbox slot 2 (from a worktree)
   - Verify each has its own API port: `curl http://localhost:8001/api/v1/health` and `curl http://localhost:8002/api/v1/health`
   - Verify worker ports don't collide: `lsof -i :6101` vs `lsof -i :6102` (design workers)
   - Run training/smoke on slot 1
   - Run training/smoke on slot 2
   - Both should pass independently
4. Verify shared observability receives traces from both: query Jaeger for service namespaces

**Acceptance Criteria:**
- [ ] Two concurrent slots run without port conflicts
- [ ] Each slot's workers register on their own ports
- [ ] E2E tests pass on both slots
- [ ] Traces from both visible in shared Jaeger
- [ ] HANDOFF document updated
