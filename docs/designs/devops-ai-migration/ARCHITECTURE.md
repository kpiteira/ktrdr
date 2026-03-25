# Architecture: Migrate ktrdr DevOps Tooling to DevOps AI

## Current State

```
ktrdr-prod/
├── .claude/
│   ├── skills/                          # 34 skills (7 devops + 27 domain)
│   │   ├── ktask/SKILL.md               # ← replaced by kbuild
│   │   ├── kmilestone/SKILL.md          # ← replaced by kbuild
│   │   ├── kdesign/SKILL.md             # ← replaced by devops-ai kdesign
│   │   ├── kdesign-validate/SKILL.md    # ← merged into kdesign
│   │   ├── kdesign-impl-plan/SKILL.md   # ← replaced by kplan
│   │   ├── address-review/SKILL.md      # ← replaced by kreview
│   │   ├── _execution-core/SKILL.md     # ← absorbed into kbuild
│   │   ├── kworktree/SKILL.md           # ← deferred to M5
│   │   ├── klandpr/SKILL.md             # stays (ktrdr-specific)
│   │   ├── e2e-testing/                 # ← replaced by ke2e
│   │   │   ├── SKILL.md                 #    71 recipes
│   │   │   ├── tests/                   #    organized by category
│   │   │   ├── preflight/               #    cure loop modules
│   │   │   └── troubleshooting/         #    symptom→fix guides
│   │   ├── ke2e/                        # 10 experiment-specific recipes
│   │   └── [27 domain skills]           # stay unchanged
│   ├── agents/
│   │   ├── e2e-test-designer.md         # ← replaced by ke2e-test-scout
│   │   ├── e2e-test-architect.md        # ← replaced by ke2e-test-designer
│   │   ├── e2e-tester.md               # ← replaced by ke2e-test-runner
│   │   ├── integration-test-specialist.md  # stays
│   │   └── unit-test-quality-checker.md    # stays
│   └── settings.local.json             # permissions for old skill names
│
├── ktrdr/cli/
│   ├── kinfra/                          # ← replaced in M5
│   │   ├── main.py                      #    ~800 lines embedded kinfra
│   │   ├── spec.py, impl.py, done.py
│   │   ├── sandbox.py, slots.py
│   │   ├── local_prod.py, deploy.py
│   │   ├── override.py
│   │   └── templates/
│   ├── sandbox_ports.py                 # ← replaced in M4
│   ├── sandbox_registry.py             # ← replaced in M4
│   ├── sandbox_detect.py               # ← replaced in M5
│   └── sandbox_gate.py                 # ← upstream as health cascade
│
├── docker-compose.sandbox.yml           # includes observability services
│
└── ~/.ktrdr/sandbox/instances.json      # ← replaced by global registry
```

## Target State

```
ktrdr-prod/
├── .devops-ai/
│   ├── project.md                       # NEW: project config for skills
│   └── infra.toml                       # NEW: sandbox/port config
│
├── .claude/
│   ├── skills/
│   │   ├── kworktree/SKILL.md           # devops-ai symlink (after M5)
│   │   ├── klandpr/SKILL.md             # stays (ktrdr-specific)
│   │   ├── ke2e/                        # project-local (shadows global)
│   │   │   ├── SKILL.md                 #   catalog table (81 recipes)
│   │   │   ├── tests/                   #   all recipes unified here
│   │   │   │   ├── training/            #   13 tests
│   │   │   │   ├── backtest/            #   13 tests
│   │   │   │   ├── cli/                 #   15 tests
│   │   │   │   ├── agent/               #   6 tests
│   │   │   │   ├── data/                #   6 tests
│   │   │   │   ├── workers/             #   4 tests
│   │   │   │   ├── integration/         #   3 tests
│   │   │   │   └── [others]/            #   remaining tests
│   │   │   ├── preflight/               #   ktrdr-specific modules
│   │   │   └── troubleshooting/         #   ktrdr-specific guides
│   │   └── [27 domain skills]           #   unchanged
│   ├── agents/
│   │   ├── ke2e-test-scout.md           # symlink → devops-ai
│   │   ├── ke2e-test-designer.md        # symlink → devops-ai
│   │   ├── ke2e-test-runner.md          # symlink → devops-ai
│   │   ├── integration-test-specialist.md  # stays
│   │   └── unit-test-quality-checker.md    # stays
│   ├── rules/                           # NEW: symlinks → devops-ai rules
│   │   ├── tdd.md
│   │   ├── handoffs.md
│   │   ├── quality-gates.md
│   │   ├── e2e-testing.md
│   │   ├── vertical-slicing.md
│   │   └── testing-taxonomy.md
│   └── settings.local.json             # updated permissions
│
├── ktrdr/cli/
│   └── deploy.py                        # kept (ktrdr-specific)
│   # kinfra/, sandbox_*.py all deleted
│
├── docker-compose.sandbox.yml           # observability services removed
│                                        # external network added
│
├── ~/.claude/skills/                    # global symlinks (from install.sh)
│   ├── kdesign/ → devops-ai
│   ├── kplan/ → devops-ai
│   ├── kbuild/ → devops-ai
│   ├── kreview/ → devops-ai
│   ├── kissue/ → devops-ai
│   ├── kworktree/ → devops-ai
│   ├── ke2e/ → devops-ai (framework)
│   └── kinfra-onboard/ → devops-ai
│
└── ~/.devops-ai/registry.json           # global registry (replaces ~/.ktrdr/sandbox/)
```

## Component Changes by Milestone

### M1: Skills Migration

**Files created:**

`.devops-ai/project.md`:
```markdown
# Project Configuration

## Project
- Name: ktrdr
- Language: Python
- Runner: uv

## Testing
- Unit tests: make test-unit
- Quality checks: make quality
- Lint (fast): uv run ruff check
- Integration tests: make test-integration

## Paths
- Design documents: docs/designs/
- Implementation plans: implementation/ subfolder of design
- Handoff files: Same directory as implementation plans

## Infrastructure
- Start: uv run kinfra sandbox up
- Stop: uv run kinfra sandbox down
- Logs: docker compose logs -f
- Health: curl http://localhost:${KTRDR_API_PORT:-8000}/api/v1/health

## E2E Testing
- Catalog: .claude/skills/ke2e/tests/
- Runner: ke2e-test-runner agent

## Project-Specific Patterns
- Always use `uv run` for Python commands
- Strategy files: strategies/*.yaml (v3 format)
- Shared data: ~/.ktrdr/shared/ (data, models, strategies)
- Host services: training-host (GPU), ib-host (IB Gateway) run natively
```

**Files deleted:**
- `.claude/skills/ktask/SKILL.md`
- `.claude/skills/kmilestone/SKILL.md`
- `.claude/skills/kdesign/SKILL.md`
- `.claude/skills/kdesign-validate/SKILL.md`
- `.claude/skills/kdesign-impl-plan/SKILL.md`
- `.claude/skills/address-review/SKILL.md`
- `.claude/skills/_execution-core/SKILL.md`

**Files modified:**

`.claude/settings.local.json` — permissions update:
```json
{
  "permissions": {
    "allow": [
      "Skill(kbuild)",
      "Skill(kdesign)",
      "Skill(kplan)",
      "Skill(kreview)",
      "Skill(kissue)",
      "Skill(kworktree)",
      "Skill(klandpr)"
    ]
  }
}
```
(Other existing permissions like Bash, Read, Edit, etc. preserved.)

**Files created (symlinks):**
- `.claude/rules/tdd.md` → `devops-ai/rules/tdd.md`
- `.claude/rules/handoffs.md` → `devops-ai/rules/handoffs.md`
- `.claude/rules/quality-gates.md` → `devops-ai/rules/quality-gates.md`
- `.claude/rules/e2e-testing.md` → `devops-ai/rules/e2e-testing.md`
- `.claude/rules/vertical-slicing.md` → `devops-ai/rules/vertical-slicing.md`
- `.claude/rules/testing-taxonomy.md` → `devops-ai/rules/testing-taxonomy.md`

**Validation:** Run `/kbuild` on a trivial task to confirm skill loading works.

---

### M2: E2E Consolidation

**Agent files — delete and symlink:**
```
DELETE  .claude/agents/e2e-test-designer.md
DELETE  .claude/agents/e2e-test-architect.md
DELETE  .claude/agents/e2e-tester.md
CREATE  .claude/agents/ke2e-test-scout.md    → devops-ai/agents/ke2e-test-scout.md
CREATE  .claude/agents/ke2e-test-designer.md → devops-ai/agents/ke2e-test-designer.md
CREATE  .claude/agents/ke2e-test-runner.md   → devops-ai/agents/ke2e-test-runner.md
```

**Recipe migration:**
```
MOVE  .claude/skills/e2e-testing/tests/*  →  .claude/skills/ke2e/tests/
MOVE  .claude/skills/e2e-testing/preflight/*  →  .claude/skills/ke2e/preflight/
MOVE  .claude/skills/e2e-testing/troubleshooting/*  →  .claude/skills/ke2e/troubleshooting/
MERGE .claude/skills/ke2e/tests/ (existing 10 recipes stay, 71 recipes added)
```

**SKILL.md rewrite:**
Create project-local `.claude/skills/ke2e/SKILL.md` with:
- Catalog table listing all 81 recipes
- References to preflight modules
- References to troubleshooting guides
- Framework docs reference global ke2e (TEMPLATE.md, FAILURE_CATEGORIES.md)

**Delete old skill:**
```
DELETE  .claude/skills/e2e-testing/  (entire directory)
```

**Validation:** Run ke2e-test-scout against a validation requirement. Confirm it finds recipes in new location. Run ke2e-test-runner on training/smoke against a running sandbox.

---

### M3: Shared Observability

**docker-compose.sandbox.yml modifications:**

Remove services:
```yaml
# DELETE these service blocks:
#   jaeger:
#   prometheus:
#   grafana:
```

Remove depends_on references:
```yaml
# In backend service, remove:
#   depends_on:
#     jaeger:
#       condition: service_healthy
# In grafana, remove entire depends_on block (service deleted)
```

Add external network:
```yaml
networks:
  devops-ai-observability:
    external: true
    name: devops-ai-observability

services:
  backend:
    networks:
      - default
      - devops-ai-observability
    environment:
      KTRDR_OTEL_OTLP_ENDPOINT: "http://devops-ai-jaeger:4317"
  backtest-worker:
    networks:
      - default
      - devops-ai-observability
    environment:
      KTRDR_OTEL_OTLP_ENDPOINT: "http://devops-ai-jaeger:4317"
  training-worker:
    networks:
      - default
      - devops-ai-observability
    environment:
      KTRDR_OTEL_OTLP_ENDPOINT: "http://devops-ai-jaeger:4317"
```

**sandbox_ports.py modifications:**

Remove port allocations for:
- `jaeger_ui`
- `jaeger_otlp_grpc`
- `jaeger_otlp_http`
- `prometheus`
- `grafana`

**Remaining ports per slot:** API, DB, 6 worker ports = 8 total (down from 11+).

**CLAUDE.md updates:**

Service URLs table:
```
- Jaeger UI: http://localhost:46686 (shared)
- Grafana: http://localhost:43000 (shared)
- Prometheus: http://localhost:49090 (shared)
```

**Validation:** Start sandbox, verify traces appear in shared Jaeger (port 46686). Run ke2e training/smoke, check trace correlation.

---

### M4: Port Allocation + infra.toml

**New file — `.devops-ai/infra.toml`:**

```toml
[project]
name = "ktrdr"

[sandbox]
compose_file = "docker-compose.sandbox.yml"

[sandbox.health]
endpoint = "/api/v1/health"
port_var = "KTRDR_API_PORT"
timeout = 120

[sandbox.ports]
KTRDR_API_PORT = 8000
KTRDR_DB_PORT = 5432
KTRDR_DESIGN_WORKER_PORT = 5003
KTRDR_BACKTEST_WORKER_PORT_1 = 5004
KTRDR_BACKTEST_WORKER_PORT_2 = 5005
KTRDR_TRAINING_WORKER_PORT_1 = 5006
KTRDR_TRAINING_WORKER_PORT_2 = 5007
KTRDR_ASSESSMENT_WORKER_PORT = 5008

[sandbox.mounts]
code = [
    "ktrdr/:/app/ktrdr",
    "research_agents/:/app/research_agents",
    "tests/:/app/tests",
    "config/:/app/config:ro",
]
code_targets = ["backend", "backtest-worker-1", "backtest-worker-2", "training-worker-1", "training-worker-2", "design-worker", "assessment-worker"]

shared = [
    "data/:/app/data",
    "models/:/app/models",
    "strategies/:/app/strategies:ro",
]
shared_targets = ["backend", "backtest-worker-1", "backtest-worker-2", "training-worker-1", "training-worker-2", "design-worker", "assessment-worker"]

[sandbox.otel]
endpoint_var = "KTRDR_OTEL_OTLP_ENDPOINT"

[sandbox.secrets]
KTRDR_DB_PASSWORD = "op://ktrdr-sandbox-dev/db_password"
KTRDR_AUTH_JWT_SECRET = "op://ktrdr-sandbox-dev/jwt_secret"
ANTHROPIC_API_KEY = "op://ktrdr-sandbox-dev/anthropic_api_key"
KTRDR_FRED_API_KEY = "op://ktrdr-sandbox-dev/fred_api_key"
```

**Port formula:** Uniform `base_port + slot_id` for all ports.

| Port Variable | Base | Slot 1 | Slot 2 | Slot 3 |
|---|---|---|---|---|
| KTRDR_API_PORT | 8000 | 8001 | 8002 | 8003 |
| KTRDR_DB_PORT | 5432 | 5433 | 5434 | 5435 |
| KTRDR_DESIGN_WORKER_PORT | 5003 | 5004 | 5005 | 5006 |
| KTRDR_BACKTEST_WORKER_PORT_1 | 5004 | 5005 | 5006 | 5007 |
| KTRDR_BACKTEST_WORKER_PORT_2 | 5005 | 5006 | 5007 | 5008 |
| KTRDR_TRAINING_WORKER_PORT_1 | 5006 | 5007 | 5008 | 5009 |
| KTRDR_TRAINING_WORKER_PORT_2 | 5007 | 5008 | 5009 | 5010 |
| KTRDR_ASSESSMENT_WORKER_PORT | 5008 | 5009 | 5010 | 5011 |

**Wait — I see a collision problem.** Slot 1's BACKTEST_WORKER_PORT_1 (5005) collides with Slot 0's TRAINING_WORKER_PORT_2 (5007 at base, but base is 5007... no, base+0=5007). Actually let me re-examine.

With `base + slot_id`:
- Slot 0: 5003, 5004, 5005, 5006, 5007, 5008
- Slot 1: 5004, 5005, 5006, 5007, 5008, 5009

**This collides.** Adjacent slots' worker ports overlap because the bases are sequential (5003-5008) but the offset is only +1 per slot.

**Fix: Use stride-based allocation.** Base ports must be spaced apart by at least `max_slots` to avoid collision. With devops-ai's registry supporting slots 1-100, we need:

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

Each base port is 100 apart. Slot N gets: 6100+N, 6200+N, etc. Even with 99 slots, no collision (6199 < 6200).

**Revised port table:**

| Port Variable | Base | Slot 1 | Slot 2 | Slot 3 |
|---|---|---|---|---|
| KTRDR_API_PORT | 8000 | 8001 | 8002 | 8003 |
| KTRDR_DB_PORT | 5432 | 5433 | 5434 | 5435 |
| KTRDR_DESIGN_WORKER_PORT | 6100 | 6101 | 6102 | 6103 |
| KTRDR_BACKTEST_WORKER_PORT_1 | 6200 | 6201 | 6202 | 6203 |
| KTRDR_BACKTEST_WORKER_PORT_2 | 6300 | 6301 | 6302 | 6303 |
| KTRDR_TRAINING_WORKER_PORT_1 | 6400 | 6401 | 6402 | 6403 |
| KTRDR_TRAINING_WORKER_PORT_2 | 6500 | 6501 | 6502 | 6503 |
| KTRDR_ASSESSMENT_WORKER_PORT | 6600 | 6601 | 6602 | 6603 |

No collisions possible. Clean formula.

**docker-compose.sandbox.yml updates:**
- Add design-worker and assessment-worker services
- Update all port references to use `${VAR}` syntax
- Worker port variables renamed from `KTRDR_WORKER_PORT_1..4` to semantic names

**Files to delete after validation:**
- `ktrdr/cli/sandbox_ports.py` (replaced by infra.toml + devops-ai compute_ports)
- `ktrdr/cli/sandbox_registry.py` (replaced by global registry)

**Registry migration:**
- Read existing `~/.ktrdr/sandbox/instances.json`
- Register any active instances in `~/.devops-ai/registry.json`
- Tear down all sandboxes and rebuild with new port allocation

**Validation:** Create sandbox slot 1 and slot 2 simultaneously. Verify no port conflicts. Run ke2e training/smoke on both.

---

### M5: kinfra CLI Migration

**Replace embedded kinfra with devops-ai's standalone CLI.**

The `ktrdr/cli/kinfra/` directory (~800 lines) is replaced by the `kinfra` CLI installed from devops-ai.

**Command mapping:**

| ktrdr (before) | devops-ai (after) |
|---|---|
| `uv run kinfra spec <feature>` | `kinfra spec <feature>` |
| `uv run kinfra impl <feature/milestone>` | `kinfra impl <feature/milestone>` |
| `uv run kinfra done <name>` | `kinfra done <name>` |
| `uv run kinfra worktrees` | `kinfra worktrees` |
| `uv run kinfra sandbox up` | `kinfra sandbox start` |
| `uv run kinfra sandbox down` | `kinfra sandbox stop` |
| `uv run kinfra sandbox up --build` | `kinfra sandbox rebuild` |
| `uv run kinfra sandbox status` | `kinfra status` |
| `uv run kinfra sandbox slots` | (via kinfra status) |
| `uv run kinfra local-prod init` | `kinfra local-prod init` (after devops-ai#17) |
| `uv run kinfra deploy <env>` | `ktrdr deploy <env>` (stays ktrdr-specific) |

**kworktree skill migrates here:**
- Delete `.claude/skills/kworktree/SKILL.md` (ktrdr variant)
- Global `~/.claude/skills/kworktree/` symlink (devops-ai) takes over
- Commands now use bare `kinfra` instead of `uv run kinfra`

**Deploy stays as ktrdr CLI command:**
- Extract deploy logic from `ktrdr/cli/kinfra/deploy.py`
- Move to `ktrdr/cli/commands/deploy.py` (standard CLI command location)
- Register on ktrdr's CLI app

**Files deleted (Phase 4 cleanup):**
- `ktrdr/cli/kinfra/` (entire directory)
- `ktrdr/cli/sandbox_detect.py`
- `ktrdr/cli/sandbox_gate.py`

**Blocked on:** devops-ai#17 P1 (health gate cascade) and P2 (local-prod pattern).

**Validation:** Full worktree lifecycle: `kinfra impl feature/test-M1` → sandbox starts → health checks pass → work → `kinfra done feature-test-M1` → slot released.

---

### M6: Cleanup

After all phases validated through at least one real milestone of dogfooding.

**Delete:**
- All files listed as "deleted" in M1-M5 that weren't already removed
- `~/.ktrdr/sandbox/` directory (old registry)
- Any remaining references to old skill names in CLAUDE.md, memory files
- Old compose templates in `ktrdr/cli/kinfra/templates/`

**Update:**
- CLAUDE.md — new command names, new port ranges, shared observability URLs
- Memory files — references to old skills/commands
- CI workflows — if any reference old kinfra commands

**Validation:** Full development cycle: design → plan → implement → test → PR → merge using only devops-ai tools.

## Integration Points

### devops-ai ← ktrdr (upstream contributions)

| Pattern | Source in ktrdr | Target in devops-ai | Tracked |
|---|---|---|---|
| Health gate cascade | `sandbox_gate.py` | kinfra health check | devops-ai#17 |
| Preflight cure loops | `e2e-testing/preflight/` | ke2e preflight | devops-ai#17 |
| Local-prod singleton | `kinfra/local_prod.py` | kinfra config option | devops-ai#17 |

### ktrdr ← devops-ai (downstream adoption)

| Feature | Source in devops-ai | Replaces in ktrdr |
|---|---|---|
| Shared observability | `observability.py` | Per-slot Jaeger/Grafana/Prometheus |
| Global registry | `registry.py` | `~/.ktrdr/sandbox/instances.json` |
| Port computation | `ports.py` + `infra.toml` | `sandbox_ports.py` |
| Compose parameterization | `compose.py` | `override.py` templates |
| Skill framework | `skills/` + `rules/` | 7 ktrdr-specific skill copies |
| E2E agents | `agents/ke2e-*` | 3 ktrdr-specific agent defs |

## Dependency Graph

```
M1 (Skills)
  │
  v
M2 (E2E) ──── dogfoods kbuild
  │
  v
M3 (Observability) ──── dogfoods kbuild + ke2e
  │
  v
M4 (Ports + infra.toml) ──── dogfoods kbuild + ke2e
  │
  ├── requires: devops-ai#17 P1 (health cascade)
  │   requires: devops-ai#17 P2 (local-prod)
  v
M5 (kinfra CLI) ──── dogfoods all
  │
  v
M6 (Cleanup) ──── dogfoods all, validates full cycle
```

M1 → M2 → M3 → M4 are linear.
M5 has an external dependency on devops-ai#17.
M6 is pure cleanup after validation.
