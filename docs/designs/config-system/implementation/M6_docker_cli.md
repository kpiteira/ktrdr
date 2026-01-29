---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 6: Docker Compose & CLI

**Goal:** Full stack runs with only `KTRDR_*` env var names in docker-compose files. CLI commands set `KTRDR_ENV` appropriately.

**Why M6:** Infrastructure files need updating to use the new naming convention. Should be done after all Settings classes are defined (M1-M5) so we know all the env var names.

**Branch:** `feature/config-m6-docker-cli`

**Depends on:** M5 (Agent & Data) — requires all Settings classes to be defined so docker-compose can use final `KTRDR_*` names

---

## Task 6.1: Update `docker-compose.yml` with KTRDR_* Names

**Files:** `docker-compose.yml` (symlink to `deploy/environments/local/docker-compose.yml`)
**Type:** CODING

**Task Categories:** Configuration, Wiring/DI

**Description:**
Update all environment variable references in the main docker-compose file to use `KTRDR_*` names.

**Implementation Notes:**
- Find all `DB_*` env vars → change to `KTRDR_DB_*`
- Find all `API_*` env vars → change to `KTRDR_API_*`
- Find all other env vars → change to `KTRDR_*` equivalents
- Deprecated names still work (via `deprecated_field()`), but compose files should use new names
- Test that services still start correctly

**Acceptance Criteria:**
- [ ] Zero non-`KTRDR_*` prefixed env vars in `docker-compose.yml` (except third-party like `POSTGRES_*`)
- [ ] All services start correctly
- [ ] Backend connects to DB
- [ ] Workers register with backend

---

## Task 6.2: Update `docker-compose.sandbox.yml` with KTRDR_* Names

**Files:** `docker-compose.sandbox.yml`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Update all environment variable references in the sandbox docker-compose file to use `KTRDR_*` names.

**Implementation Notes:**
- Same pattern as Task 6.1
- Sandbox compose uses `${VAR:-default}` syntax for parameterization
- Ensure parameterized variables also use KTRDR_* names

**Acceptance Criteria:**
- [ ] Zero non-`KTRDR_*` prefixed env vars in `docker-compose.sandbox.yml`
- [ ] Sandbox startup still works: `uv run ktrdr sandbox up`

---

## Task 6.3: Update `.env.example` and `.env.sandbox` Templates

**Files:** `.env.example`, `deploy/environments/local/.env.example`, `.env.sandbox` (if exists)
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Update example env files to use `KTRDR_*` names and document the new naming convention.

**Implementation Notes:**
- Replace all old env var names with new ones
- Add comments explaining the naming convention
- Include example values

**Acceptance Criteria:**
- [ ] All example env files use `KTRDR_*` names
- [ ] Comments explain naming convention
- [ ] Examples are valid and helpful

---

## Task 6.4: Update CLI to Set `KTRDR_ENV`

**Files:** `ktrdr/cli/commands/*.py`
**Type:** CODING

**Task Categories:** Wiring/DI

**Description:**
Ensure CLI commands set `KTRDR_ENV` appropriately when starting services.

**Implementation Notes:**
- `ktrdr local-prod up` should set `KTRDR_ENV=production` in the compose environment
- `ktrdr sandbox up` should set `KTRDR_ENV=development`
- The env var is passed to docker-compose, not set in the current shell

**Key code pattern:**
```python
# In sandbox/local-prod command
compose_env["KTRDR_ENV"] = "development"  # or "production"
subprocess.run(cmd, env=compose_env)
```

**Acceptance Criteria:**
- [ ] `ktrdr local-prod up` sets `KTRDR_ENV=production`
- [ ] `ktrdr sandbox up` sets `KTRDR_ENV=development`
- [ ] Backend validates correctly based on `KTRDR_ENV`

---

## Task 6.5: Execute E2E Test

**Type:** VALIDATION

**Description:**
Validate M6 is complete with E2E scenarios.

**E2E Test Scenarios:**

### Scenario 1: Docker compose up with new names
```bash
docker compose up -d
# Verify all services running
docker compose ps | grep -E "running|Up"
# Expected: all services running
curl http://localhost:8000/health
# Expected: 200 OK
docker compose down
```

### Scenario 2: Sandbox startup with new names
```bash
uv run ktrdr sandbox up
uv run ktrdr sandbox status
# Expected: sandbox running
curl http://localhost:8001/health  # or appropriate sandbox port
# Expected: 200 OK
uv run ktrdr sandbox down
```

### Scenario 3: Local-prod sets production mode
```bash
uv run ktrdr local-prod up
# Check backend is in production mode
docker compose logs backend 2>&1 | head -20
# Expected: should see production-mode validation (stricter)
# If using insecure defaults, should fail
uv run ktrdr local-prod down
```

### Scenario 4: No deprecated names in compose logs at startup
```bash
docker compose up -d backend
docker compose logs backend 2>&1 | grep -i "deprecated"
# Expected: no deprecation warnings (compose uses new names)
docker compose down
```

**Success Criteria:**
- [ ] All scenarios pass
- [ ] Full stack runs with only `KTRDR_*` names
- [ ] `KTRDR_ENV` is set correctly by CLI commands
- [ ] No deprecation warnings when using new compose files

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Docker compose files use only `KTRDR_*` names
- [ ] CLI sets `KTRDR_ENV` correctly
- [ ] Example env files updated
- [ ] E2E tests pass
- [ ] Quality gates pass: `make quality`
- [ ] Branch merged to main
