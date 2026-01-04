# Handoff: M1 Compose File + Shared Data Setup

## Gotchas

### Shared Data Mount Pattern
**Problem:** The architecture doc's bash expansion pattern `${KTRDR_SHARED_DIR:+${KTRDR_SHARED_DIR}/models}${KTRDR_SHARED_DIR:-./models}` produces doubled paths like `/path/models/path` when the variable is set.

**Symptom:** Volume mounts fail or point to wrong directories.

**Solution:** Use separate variables for each directory instead:
```yaml
- ${KTRDR_DATA_DIR:-./data}:/app/data
- ${KTRDR_MODELS_DIR:-./models}:/app/models
- ${KTRDR_STRATEGIES_DIR:-./strategies}:/app/strategies
```

The `.env.sandbox` should set:
```bash
KTRDR_DATA_DIR=~/.ktrdr/shared/data
KTRDR_MODELS_DIR=~/.ktrdr/shared/models
KTRDR_STRATEGIES_DIR=~/.ktrdr/shared/strategies
```

### Worker Port Parameterization
**Problem:** Workers register with their port number. If internal and external ports don't match, registration fails.

**Solution:** Parameterize both sides of the port mapping AND set the WORKER_PORT env var:
```yaml
ports:
  - "${KTRDR_WORKER_PORT_1:-5003}:${KTRDR_WORKER_PORT_1:-5003}"
environment:
  - WORKER_PORT=${KTRDR_WORKER_PORT_1:-5003}
command: ... --port ${KTRDR_WORKER_PORT_1:-5003}
```

## Patterns Established

### Port Variable Naming
All port variables follow `KTRDR_<SERVICE>_PORT` pattern:
- `KTRDR_API_PORT`, `KTRDR_DB_PORT`, `KTRDR_GRAFANA_PORT`
- `KTRDR_JAEGER_UI_PORT`, `KTRDR_JAEGER_OTLP_GRPC_PORT`, `KTRDR_JAEGER_OTLP_HTTP_PORT`
- `KTRDR_PROMETHEUS_PORT`
- `KTRDR_WORKER_PORT_1` through `KTRDR_WORKER_PORT_4`

### MCP Services Excluded
MCP services are dev tooling for Claude Code integration. They don't expose ports and aren't needed in sandbox instances. Keep them out of `docker-compose.sandbox.yml`.

## For Next Tasks

- ~~Task 1.2 creates `scripts/init-shared-data-dir.sh`~~ — ✅ Complete
- Task 1.3 documents the manual multi-instance process — use the variable names established here
- Task 1.4 verifies main compose unchanged — run `docker compose up` from `../ktrdr2` to confirm
