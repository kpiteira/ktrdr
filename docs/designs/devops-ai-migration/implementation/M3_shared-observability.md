---
design: docs/designs/devops-ai-migration/DESIGN.md
architecture: docs/designs/devops-ai-migration/ARCHITECTURE.md
---

# M3: Shared Observability

Remove per-slot Jaeger/Grafana/Prometheus from ktrdr's compose file. Connect to devops-ai's shared observability stack instead. This milestone dogfoods kbuild + ke2e from M1/M2.

## Context

**Current state:**
- `docker-compose.sandbox.yml` includes jaeger, prometheus, grafana services (3 containers per slot)
- Each slot allocates 5 observability ports: Jaeger UI, OTLP gRPC, OTLP HTTP, Prometheus, Grafana
- `sandbox_ports.py` computes observability ports with mixed-offset formulas
- OTEL endpoint hardcoded as `http://jaeger:4317` in all service environment blocks

**Target state:**
- Observability services removed from compose file
- External `devops-ai-observability` Docker network connects services to shared stack
- OTEL endpoint set to `http://devops-ai-jaeger:4317`
- 5 ports freed per slot
- Fixed shared ports: Jaeger UI 46686, Grafana 43000, Prometheus 49090

---

## Task 3.1: Remove observability services from compose

**File(s):** `docker-compose.sandbox.yml`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Remove the jaeger, prometheus, and grafana service definitions from `docker-compose.sandbox.yml`. Remove their named volumes. Remove `depends_on` references to these services from other services.

**Implementation Notes:**
- Services to remove: `jaeger` (lines ~144-162), `prometheus` (lines ~164-186), `grafana` (lines ~188-215)
- Named volumes to remove from `volumes:` section: `prometheus_data`, `grafana_data`
- Remove `depends_on` references:
  - `backend` depends_on `jaeger: condition: service_healthy` — remove this entry (keep `db` dependency)
  - `grafana` depends_on `prometheus` and `jaeger` — entire service is deleted
- Remove comment block at top referencing `GF_ADMIN_PASSWORD` (grafana secret no longer needed)
- Remove `KTRDR_GRAFANA_PORT`, `KTRDR_JAEGER_UI_PORT`, `KTRDR_JAEGER_OTLP_GRPC_PORT`, `KTRDR_JAEGER_OTLP_HTTP_PORT`, `KTRDR_PROMETHEUS_PORT` from the PORT VARIABLES comment block
- Keep the `ktrdr-network` — it's still used by remaining services

**Testing Requirements:**
- [ ] `docker compose -f docker-compose.sandbox.yml config` validates without errors
- [ ] No references to jaeger, prometheus, or grafana as services
- [ ] No dangling depends_on references
- [ ] No dangling volume references (prometheus_data, grafana_data)
- [ ] Remaining services (db, backend, workers) still have valid config

**Acceptance Criteria:**
- [ ] Compose file validates cleanly
- [ ] Only application services remain (db, backend, 4 workers, mcp-local)
- [ ] No observability service definitions

---

## Task 3.2: Add shared observability network

**File(s):** `docker-compose.sandbox.yml`
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Add the `devops-ai-observability` external Docker network to the compose file and connect all services that emit traces (backend, workers) to it. Update OTEL endpoint environment variables.

**Implementation Notes:**
- Add top-level network definition:
  ```yaml
  networks:
    ktrdr-network:
      driver: bridge
    devops-ai-observability:
      external: true
      name: devops-ai-observability
  ```
- Add `devops-ai-observability` to `networks:` for: backend, backtest-worker-1, backtest-worker-2, training-worker-1, training-worker-2 (all services that have OTEL endpoint)
- Each service keeps `ktrdr-network` (internal) AND gets `devops-ai-observability` (external)
- Update all `KTRDR_OTEL_OTLP_ENDPOINT` values from `http://jaeger:4317` to `http://devops-ai-jaeger:4317`
- This includes both active services AND commented-out services (extra workers, agents)
- The MCP server doesn't emit traces — no network change needed for it

**Testing Requirements:**
- [ ] `docker compose -f docker-compose.sandbox.yml config` validates
- [ ] All OTEL endpoints reference `devops-ai-jaeger` not `jaeger`
- [ ] Backend and all workers have both networks listed
- [ ] `devops-ai-observability` is declared as external

**Acceptance Criteria:**
- [ ] Compose validates with external network declaration
- [ ] All trace-emitting services connected to shared observability network
- [ ] OTEL endpoint updated in all service environment blocks

---

## Task 3.3: Remove observability ports from allocation

**File(s):** `ktrdr/cli/sandbox_ports.py`
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Remove observability port allocations from `sandbox_ports.py`. These ports are no longer needed since observability runs on fixed shared ports (46686, 44317, 43000, 49090).

**Implementation Notes:**
- Remove from `PortAllocation` dataclass (or equivalent): `jaeger_ui`, `jaeger_otlp_grpc`, `jaeger_otlp_http`, `prometheus`, `grafana`
- Remove from `get_ports()` function: the allocation lines for these 5 ports
- Remove from `to_env_dict()`: the env var entries for `KTRDR_JAEGER_UI_PORT`, `KTRDR_JAEGER_OTLP_GRPC_PORT`, `KTRDR_JAEGER_OTLP_HTTP_PORT`, `KTRDR_PROMETHEUS_PORT`, `KTRDR_GRAFANA_PORT`
- Update `check_ports_available()` to not check these ports
- The remaining ports should be: API, DB, and 4 worker ports (6 total per slot)
- Note: This file will be fully replaced in M4 — this is an incremental fix for M3

**Testing Requirements:**
- [ ] `sandbox_ports.py` still computes valid ports for remaining services
- [ ] No references to removed port variables
- [ ] Existing unit tests updated or removed for observability ports
- [ ] Port allocation for API, DB, workers unchanged

**Acceptance Criteria:**
- [ ] Only 6 ports allocated per slot (API, DB, 4 workers)
- [ ] `make quality` passes (no type errors from removed fields)
- [ ] `make test-unit` passes

---

## Task 3.4: Update documentation

**File(s):** `CLAUDE.md`, `.claude/skills/observability/SKILL.md`, `.claude/skills/debugging/SKILL.md`
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Update all documentation referencing per-slot observability ports to reflect the shared stack.

**Implementation Notes:**
- `CLAUDE.md` Service URLs section: Update Jaeger, Grafana, Prometheus URLs to shared ports (46686, 43000, 49090)
- `CLAUDE.md` Sandbox Awareness table: Remove Grafana, Jaeger, DB columns or update to show shared ports
- `.claude/skills/observability/SKILL.md`: Update Jaeger query URLs to port 46686
- `.claude/skills/debugging/SKILL.md`: Update any Jaeger curl examples to port 46686
- Any other skills referencing Jaeger/Grafana ports (search for `16686`, `3000`, `4317`)
- Add note: "Shared observability must be running: `kinfra observability up`"

**Testing Requirements:**
- [ ] No references to per-slot observability ports (16686+N, 3000+N, 9090+N) in docs
- [ ] Shared ports (46686, 43000, 49090) documented correctly
- [ ] Prerequisite documented: `kinfra observability up` needed before sandbox use

**Acceptance Criteria:**
- [ ] All documentation reflects shared observability architecture
- [ ] No stale port references

---

## Task 3.5: Validation — traces in shared Jaeger

**File(s):** (none — validation only)
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Validate that ktrdr sandbox services emit traces to the shared observability stack and that traces are visible in Jaeger UI.

**Implementation Notes:**
- Requires: shared observability running (`kinfra observability up`), ktrdr sandbox running
- This tests the full chain: service → OTEL SDK → devops-ai-jaeger:4317 → Jaeger UI on 46686

**Validation Steps:**
1. Load the `ke2e` skill
2. Invoke ke2e-test-scout with requirement: "Validate observability — traces from sandbox services appear in shared Jaeger"
3. If no existing test matches, design a lightweight validation:
   - Ensure shared observability is running: `curl -s http://localhost:46686` returns Jaeger UI
   - Start/rebuild ktrdr sandbox with updated compose
   - Make an API call: `curl http://localhost:${KTRDR_API_PORT}/api/v1/health`
   - Wait 5 seconds for trace propagation
   - Query Jaeger for ktrdr traces: `curl -s "http://localhost:46686/api/traces?service=ktrdr&limit=1"`
   - Verify at least one trace exists
4. Verify Grafana accessible at shared port: `curl -s http://localhost:43000/api/health`
5. Verify no observability containers running as part of sandbox: `docker compose ps` should NOT show jaeger, prometheus, or grafana

**Acceptance Criteria:**
- [ ] Sandbox starts without observability containers
- [ ] Traces appear in shared Jaeger (port 46686)
- [ ] No per-slot observability containers running
- [ ] Grafana accessible on shared port (43000)
- [ ] HANDOFF document updated
