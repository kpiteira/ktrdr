# M6 Handoff - Docker Compose & CLI

**Branch:** `feature/config-m6-docker-cli`
**Started:** 2026-01-31

---

## Context

M6 updates all Docker Compose files and CLI commands to use the new `KTRDR_*` environment variable naming convention established in M1-M5. This is the infrastructure side of the config system migration.

**Key files affected:**
- `docker-compose.yml` - Main development compose
- `docker-compose.sandbox.yml` - Sandbox compose
- `.env.example` - Example environment file
- `ktrdr/cli/sandbox.py` - Sandbox CLI commands
- `ktrdr/cli/local_prod.py` - Local-prod CLI commands
- `ktrdr/cli/instance_core.py` - Shared instance management

**Env var mapping (from Settings classes in M1-M5):**

| Old Name | New Name | Settings Class |
|----------|----------|----------------|
| `ENVIRONMENT` | `KTRDR_API_ENVIRONMENT` | APISettings |
| `LOG_LEVEL` | `KTRDR_LOG_LEVEL` | LoggingSettings |
| `DB_HOST` | `KTRDR_DB_HOST` | DatabaseSettings |
| `DB_PORT` | `KTRDR_DB_PORT` | DatabaseSettings |
| `DB_NAME` | `KTRDR_DB_NAME` | DatabaseSettings |
| `DB_USER` | `KTRDR_DB_USER` | DatabaseSettings |
| `DB_PASSWORD` | `KTRDR_DB_PASSWORD` | DatabaseSettings |
| `OTLP_ENDPOINT` | `KTRDR_OTEL_OTLP_ENDPOINT` | ObservabilitySettings |
| `CHECKPOINT_DIR` | `KTRDR_CHECKPOINT_DIR` | CheckpointSettings |
| `JWT_SECRET` | `KTRDR_AUTH_JWT_SECRET` | AuthSettings |
| `USE_IB_HOST_SERVICE` | `KTRDR_IB_HOST_ENABLED` | IBHostServiceSettings |
| `IB_HOST_SERVICE_URL` | Computed from KTRDR_IB_HOST_HOST/PORT | IBHostServiceSettings |
| `WORKER_TYPE` | `WORKER_TYPE` (unchanged) | Not a Settings field, passthrough to worker |
| `WORKER_PORT` | `KTRDR_WORKER_PORT` | WorkerSettings |
| `WORKER_PUBLIC_BASE_URL` | `KTRDR_WORKER_PUBLIC_BASE_URL` | WorkerSettings |
| `AGENT_*` | `KTRDR_AGENT_*` | AgentSettings |

**Note:** Third-party env vars like `POSTGRES_*`, `GF_*`, `COLLECTOR_*` stay unchanged.

---

## Progress

### Task 6.1 Complete: Update `docker-compose.yml` with KTRDR_* Names

**Changes:**
- Updated all backend service environment variables to use `KTRDR_*` prefix
- Updated all worker service environment variables (backtest-worker-1/2, training-worker-1/2)
- Updated MCP services (mcp-local, mcp-preprod)
- Key mappings applied:
  - `ENVIRONMENT` → `KTRDR_API_ENVIRONMENT`
  - `LOG_LEVEL` → `KTRDR_LOG_LEVEL`
  - `DB_*` → `KTRDR_DB_*`
  - `OTLP_ENDPOINT` → `KTRDR_OTEL_OTLP_ENDPOINT`
  - `CHECKPOINT_DIR` → `KTRDR_CHECKPOINT_DIR`
  - `JWT_SECRET` → `KTRDR_AUTH_JWT_SECRET`
  - `USE_IB_HOST_SERVICE` → `KTRDR_IB_HOST_ENABLED`
  - `IB_HOST_SERVICE_URL` → `KTRDR_IB_HOST_HOST` + `KTRDR_IB_HOST_PORT`
  - `WORKER_PORT` → `KTRDR_WORKER_PORT`
  - `WORKER_PUBLIC_BASE_URL` → `KTRDR_WORKER_PUBLIC_BASE_URL`
  - `KTRDR_API_URL` → `KTRDR_API_CLIENT_BASE_URL`
  - `AGENT_*` → `KTRDR_AGENT_*`

**Kept unchanged (third-party):**
- `POSTGRES_*` (PostgreSQL)
- `GF_*` (Grafana)
- `LOG_LEVEL=info` in Jaeger service
- `PYTHONPATH`
- `ANTHROPIC_API_KEY`

---

### Task 6.2 Complete: Update `docker-compose.sandbox.yml` with KTRDR_* Names

**Changes:**
- Applied same mappings as 6.1 to all services
- Updated both active services and commented-out local-prod workers
- Validated compose file syntax

---

### Task 6.3 Complete: Update `.env.example` Templates

**Files updated:**
- `.env.example` - Complete rewrite with comprehensive documentation
- `.env.dev.example` - Updated all env vars to KTRDR_* names
- `.env.distributed.example` - Updated all env vars to KTRDR_* names

**Key improvements:**
- Added section headers explaining each settings group
- Documented the KTRDR_* naming convention
- Included all new env var names with descriptions
- Separated KTRDR settings from third-party settings (ANTHROPIC_*, GF_*)

---

### Task 6.4 Complete: Update CLI to Set `KTRDR_ENV`

**Changes to `ktrdr/cli/instance_core.py`:**
- Added `ktrdr_env` parameter to `start_instance()` function
- Sets `KTRDR_ENV` in compose environment before starting Docker
- Displays KTRDR_ENV value in startup output

**Changes to `ktrdr/cli/sandbox.py`:**
- Updated `up` command to set `KTRDR_ENV=development`
- Updated `SANDBOX_SECRETS_MAPPING` to use `KTRDR_DB_PASSWORD` and `KTRDR_AUTH_JWT_SECRET`

**Changes to `ktrdr/cli/local_prod.py`:**
- Updated `up` command to pass `ktrdr_env="production"` to `start_instance()`
- Updated `HOST_SERVICE_SECRETS_MAP` to use `KTRDR_DB_PASSWORD`
- Updated `_get_host_service_env()` to use `KTRDR_DB_*` and `KTRDR_*_DIR` names

**Behavior:**
- `ktrdr sandbox up` → Sets `KTRDR_ENV=development` (warnings on insecure defaults)
- `ktrdr local-prod up` → Sets `KTRDR_ENV=production` (hard failure on insecure defaults)

---

### Task 6.5 Complete: E2E Validation

**Test Execution:**

```bash
uv run ktrdr sandbox down
uv run ktrdr sandbox up --no-secrets
```

**Results:**

1. **Docker compose up with new names** ✅
   - All services started successfully
   - `KTRDR_ENV=development` displayed in output

2. **Sandbox startup works** ✅
   - Startability Gate: PASSED
   - All workers registered (4 workers: 2 backtest, 2 training)
   - API healthy at http://localhost:8001/api/v1/health

3. **No deprecation warnings** ✅
   - Logs show only insecure default warnings (expected with `--no-secrets`)
   - Workers using new names: `KTRDR_DB_PASSWORD`, `KTRDR_AUTH_JWT_SECRET`
   - No "deprecated" messages in backend or worker logs

4. **New env var names in use** ✅
   - Backend logs show KTRDR logging initialized
   - Workers show OTLP config using `http://jaeger:4317`
   - Database engine using `db:5432/ktrdr`

**Note:** Local-prod E2E test not run (requires 1Password secrets and production-ready credentials).

---

## Milestone Complete

All tasks (6.1-6.5) completed successfully:
- [x] Task 6.1: docker-compose.yml updated
- [x] Task 6.2: docker-compose.sandbox.yml updated
- [x] Task 6.3: .env.example templates updated
- [x] Task 6.4: CLI sets KTRDR_ENV
- [x] Task 6.5: E2E validation passed

Ready for PR creation.

