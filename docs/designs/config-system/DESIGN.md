# Configuration System Redesign: Design

> **Status:** Validated. Ready for implementation planning.
> **Dependency:** M6/M7 (sandbox → local-prod) landed on main. Blocker resolved.
> See `SCENARIOS.md` for validation results and `VALIDATION_NOTES.md` for earlier session notes.

## Problem Statement

KTRDR's configuration system has grown organically and now suffers from multiple overlapping patterns, unclear precedence, and scattered settings.

**Quantified (from codebase audit, 2026-01-27):**
- **5 config patterns**: Pydantic BaseSettings, dataclasses with `os.getenv()` lambdas, direct `os.getenv()` calls, YAML via metadata.py, YAML via ConfigLoader
- **~90 unique environment variable names** across production code
- **14 YAML files** providing configuration (10 to delete)
- **6 major duplications** (e.g., `APIConfig` vs `APISettings` — two classes, same prefix, overlapping fields)
- **3 names for "environment"**: `KTRDR_ENVIRONMENT`, `ENVIRONMENT`, `KTRDR_API_ENVIRONMENT`
- **~30 scattered reads** where the same env var is read via `os.getenv()` in 3+ separate files
- **1 bug**: `WORKER_PORT` defaults to 5002 in `training_worker.py` but 5004 in `training/worker_registration.py`
- **No startup validation** — invalid config silently fails at runtime

See `ARCHITECTURE.md` → Complete Migration Map for the full audit.

## Goals

What we're trying to achieve:

1. **Single pattern for all configuration** — One way to define, load, and access config (Pydantic Settings)
2. **Clear precedence** — Explicit order: Python defaults → environment variables (no YAML layer)
3. **Consistent naming** — All env vars use `KTRDR_` prefix with logical grouping
4. **Fail-fast validation** — Invalid or missing required config crashes immediately at startup with clear errors
5. **Discoverable** — Open one file, see all available settings with types and defaults
6. **Secrets never in files** — 1Password injection at deploy time, no encrypted files or committed secrets

## Non-Goals (Out of Scope)

What we're explicitly not doing:

1. **Runtime config changes** — No hot-reload of settings without restart (not needed, restarts are cheap)
2. **Config UI/dashboard** — No web interface for viewing/editing config
3. **Multi-tenant config** — No per-user or per-tenant configuration overrides
4. **Config versioning/history** — No tracking of config changes over time
5. **Feature flags system** — This is config, not feature management
6. **Strategy configuration** — Strategy YAML files are domain data, not system config (excluded from this redesign)

### YAML Files Explicitly Out of Scope

These YAML files are **domain data** or **deployment artifacts**, not application configuration:

| File | Purpose | Status |
|------|---------|--------|
| `config/strategies/*.yaml` | Trading strategy definitions | Domain data, unchanged |
| `config/fuzzy.yaml` | Fuzzy set membership definitions | Domain data, unchanged |
| `config/workers.*.yaml` | Deployment fleet definitions | Infrastructure tooling, unchanged |
| `config/indicators.yaml` | Unused relic | **Delete** |

## User Experience

How developers and operators interact with the new system:

### Scenario 1: Developer wants to know what config exists

```python
# Open ktrdr/config/settings.py, see all settings grouped by concern:

class DatabaseSettings(BaseSettings):
    """Database connection settings."""
    host: str = "localhost"
    port: int = 5432
    name: str = "ktrdr"
    user: str = "ktrdr"
    password: str = "localdev"  # Insecure default — triggers startup warning
    echo: bool = False

    model_config = SettingsConfigDict(env_prefix="KTRDR_DB_")

# Clear: DB password defaults to "localdev" for zero-config local dev
# Clear: All DB settings use KTRDR_DB_ prefix
# Clear: Types and defaults are visible
# Clear: Insecure defaults emit BIG WARNING at startup (see Decision 3)
```

### Scenario 2: Developer wants to override a setting locally

```bash
# In .env.local (gitignored):
KTRDR_DB_HOST=localhost
KTRDR_DB_PASSWORD=localdev
KTRDR_API_LOG_LEVEL=DEBUG

# Or inline:
KTRDR_API_LOG_LEVEL=DEBUG docker compose up
```

No YAML files to hunt through. One mechanism: environment variables.

### Scenario 3: Operator deploys to production

```bash
# 1Password items contain secrets:
#   - ktrdr-prod-db: db_password
#   - ktrdr-prod-api: jwt_secret, anthropic_api_key

# Deploy script fetches and injects:
ktrdr deploy up --env production
# Internally: op inject → sets env vars → starts containers
```

Secrets never touch disk. Fetched from 1Password, injected as env vars, containers start.

### How Secrets Flow (Detail)

Understanding the actual mechanism, since the design depends on it:

```
1Password item ("ktrdr-local-prod")
    │
    ▼
ktrdr local-prod up / ktrdr sandbox up
    │  calls fetch_sandbox_secrets() → op CLI → 1Password
    │  returns dict of secret env vars
    ▼
compose_env = os.environ.copy()
compose_env.update(sandbox_env)    # ports, metadata from .env.sandbox
compose_env.update(secrets_env)    # 1Password secrets (highest priority)
    │
    ▼
subprocess.run(["docker", "compose", "up", ...], env=compose_env)
    │
    ▼
Container inherits env vars → Pydantic Settings reads them
```

**Key points:**
- Secrets are injected at CLI invocation time, not at container runtime
- Hot reload (uvicorn `--reload`) restarts the Python process, NOT the container — secrets persist
- 1Password CLI caches sessions in `~/.op/sessions` — no re-prompting on hot reload
- Secrets only re-fetched on full `docker compose down` + `up` cycle
- If 1Password is not authenticated, `local-prod up` falls back to insecure defaults with warnings

### Scenario 4: New developer onboards

```bash
# Clone repo and set up local-prod (see scripts/setup-local-prod.sh)
git clone https://github.com/kpiteira/ktrdr.git ~/Documents/dev/ktrdr-prod
cd ~/Documents/dev/ktrdr-prod
uv sync
uv run ktrdr local-prod init
uv run ktrdr local-prod up

# Backend starts with insecure defaults + BIG WARNING:
# ========================================
# WARNING: INSECURE DEFAULT CONFIGURATION
# ========================================
# The following settings are using insecure defaults:
#   - KTRDR_DB_PASSWORD: Using default "localdev"
#   - KTRDR_AUTH_JWT_SECRET: Using default "local-dev-secret-..."
# ========================================
```

Zero config for basic local development. Insecure state is loud, not silent.
With 1Password configured, `local-prod up` injects real secrets and no warning appears.

### Scenario 5: Config validation fails at startup

**Type errors and truly invalid config always fail, regardless of environment:**

```
$ docker compose up
backend-1  | CONFIGURATION ERROR
backend-1  | ====================
backend-1  | Invalid settings:
backend-1  |   - KTRDR_API_PORT: 'abc' is not a valid integer
backend-1  |   - KTRDR_DB_PORT: '-1' is not a valid port number
backend-1  |
backend-1  | See: docs/configuration.md for all available settings
backend-1  | ====================
backend-1 exited with code 1
```

**In production mode, insecure defaults also fail:**

```
$ KTRDR_ENV=production docker compose up
backend-1  | CONFIGURATION ERROR
backend-1  | ====================
backend-1  | Insecure defaults not allowed in production:
backend-1  |   - KTRDR_DB_PASSWORD: Must be explicitly set (not "localdev")
backend-1  |   - KTRDR_AUTH_JWT_SECRET: Must be explicitly set
backend-1  |
backend-1  | See: docs/configuration.md for all available settings
backend-1  | ====================
backend-1 exited with code 1
```

Fail fast, fail clearly. Dev mode warns loudly; production mode rejects insecure defaults entirely.

### Scenario 6: Worker needs config

```python
# Workers import only what they need:
from ktrdr.config import (
    DatabaseSettings,
    LoggingSettings,
    ObservabilitySettings,
    WorkerSettings,
)

# They don't import APISettings, AuthSettings, etc.
# Validation only fails for settings they actually use
```

Workers share core settings but don't need API-specific config.

## Key Decisions

### Decision 1: Pure Pydantic Settings, no YAML layer

**Choice:** All configuration via Pydantic BaseSettings classes with environment variable overrides. Remove the metadata.py YAML loading system.

**Alternatives considered:**
- Keep YAML + env var layering (current approach)
- Use dynaconf for multi-layer config
- Use Hydra for complex config composition

**Rationale:**
- YAML layer adds complexity without demonstrated value (env YAML files are ~10 lines each)
- Pydantic gives us type validation, IDE support, and clear defaults in one place
- Docker/Kubernetes world is env-var native
- We already use Pydantic Settings partially; this just makes it the only pattern
- One fewer thing to debug when config behaves unexpectedly

### Decision 2: Standardize all env vars to KTRDR_ prefix

**Choice:** All environment variables use `KTRDR_` prefix with logical grouping:
- `KTRDR_ENV` — Environment mode (production/development/test)
- `KTRDR_DB_*` — Database
- `KTRDR_API_*` — API server + API client
- `KTRDR_AUTH_*` — Authentication and secrets
- `KTRDR_IB_*` — Interactive Brokers connection
- `KTRDR_IB_HOST_*` — IB host service proxy
- `KTRDR_TRAINING_HOST_*` — Training host service proxy
- `KTRDR_WORKER_*` — Worker process settings
- `KTRDR_LOG_*` — Logging
- `KTRDR_OTEL_*` — Observability/telemetry
- `KTRDR_ORPHAN_*` — Orphan operation detection
- `KTRDR_CHECKPOINT_*` — Operation checkpoints
- `KTRDR_AGENT_*` — AI agent settings
- `KTRDR_GATE_*` — Agent quality gate thresholds
- `KTRDR_DATA_*` — Data storage and acquisition
- `KTRDR_OPS_*` — Operations service

**Alternatives considered:**
- Keep current mixed naming (DB_HOST, IB_PORT, KTRDR_API_PORT, ORPHAN_TIMEOUT_SECONDS)
- Use flat naming without grouping

**Rationale:**
- Namespacing prevents collisions with system/other app env vars
- Grouping makes it obvious what category a setting belongs to
- Consistent pattern is easier to document and remember
- Migration can be gradual (accept old names with deprecation warnings)

### Decision 3: Secrets have insecure defaults with loud warnings

**Choice:** Secrets have insecure defaults that work for local dev, but emit prominent warnings at startup.

**Defaults for local dev convenience:**
```python
class DatabaseSettings(BaseSettings):
    host: str = "localhost"      # Default: local dev
    port: int = 5432             # Default: standard postgres
    password: str = "localdev"   # Insecure default, triggers warning
```

**Precedence for secrets (highest to lowest):**
1. 1Password injection via `ktrdr sandbox up` (recommended)
2. `.env.local` file (gitignored, manual setup)
3. Python defaults with **BIG WARNINGS**

**Alternatives considered:**
- No defaults at all (original proposal) — rejected: breaks "zero config local dev"
- Silent defaults — rejected: too easy to deploy insecurely

**Rationale:**
- Local dev must "just work" with minimal setup
- Warnings make insecure state obvious without blocking development
- 1Password integration (via sandbox system) provides secure path
- Production deployments use 1Password injection, never see defaults

**Warning mechanism:**
- Validation module detects when insecure defaults are active
- Emits prominent boxed warning at startup (not a failure in dev mode)
- `KTRDR_ENV=production` converts these warnings to hard failures
- Warning appears once at startup, not on every request

**Insecure default detection:**
```python
# Each secret field declares its insecure default explicitly:
INSECURE_DEFAULTS = {
    "KTRDR_DB_PASSWORD": "localdev",
    "KTRDR_AUTH_JWT_SECRET": "local-dev-secret-do-not-use-in-production",
}

# At startup, check if current values match insecure defaults
# If KTRDR_ENV=production and any match → ConfigurationError
# Otherwise → prominent warning to stderr
```

**Suppression:** `KTRDR_ACKNOWLEDGE_INSECURE_DEFAULTS=true` suppresses the warning
for CI/test environments that intentionally use defaults.

### Decision 4: Project metadata stays in pyproject.toml

**Choice:** Project identity (name, version, description) comes from `pyproject.toml`, not a separate metadata.yaml.

**Rationale:**
- `pyproject.toml` already has version, name, description
- Single source of truth (PEP 621 standard)
- No need for a separate metadata file
- Runtime can read from `importlib.metadata` if needed

### Decision 5: Settings grouped by concern, not by component

**Choice:** Organize settings by what they configure, not who uses them:

```python
# By concern (chosen):
DatabaseSettings    # All DB config
APISettings         # All API server config
WorkerSettings      # All worker config

# NOT by component:
BackendSettings     # Would duplicate DB settings
WorkerSettings      # Would duplicate DB settings
```

**Rationale:**
- Avoids duplication (workers and backend both need DB settings)
- Each settings class is cohesive (one responsibility)
- Components import the settings classes they need
- Clear ownership: "who owns DatabaseSettings?" → whoever changes DB config

### Decision 6: Deprecation path for old env var names

**Choice:** Accept old env var names with deprecation warnings during migration period.

```python
class DatabaseSettings(BaseSettings):
    host: str = Field(default="localhost", validation_alias=AliasChoices(
        "KTRDR_DB_HOST",  # New name (preferred)
        "DB_HOST",         # Old name (deprecated)
    ))
```

**Rationale:**
- Allows gradual migration without breaking existing deployments
- Clear warning at startup: "DB_HOST is deprecated, use KTRDR_DB_HOST"
- Can remove old aliases after migration period (1-2 releases)

### Decision 7: Validation runs at explicit startup call (not import time)

**Choice:** Settings are validated via an explicit `validate_all()` call in each entrypoint, NOT at module import time.

```python
# ktrdr/api/main.py (backend entrypoint)
from ktrdr.config import validate_all, warn_deprecated_env_vars
warn_deprecated_env_vars()
validate_all("backend")

# ktrdr/training/training_worker.py (worker entrypoint)
warn_deprecated_env_vars()
validate_all("worker")

# ktrdr/cli/__init__.py (CLI entrypoint)
# NO validate_all() call — CLI is a client, doesn't need DB/auth config
```

**Why not import time:** Import-time validation would break the CLI. When a user runs `ktrdr data show AAPL 1d`, the CLI imports `ktrdr` modules but doesn't have database credentials. If validation ran at import, `ktrdr --help` would fail.

**Rationale:**
- Fail fast: backend/worker entrypoints validate before serving traffic
- CLI not blocked: clients don't need server config
- Explicit is better than implicit
- Testable: tests don't trigger validation on import

### Decision 8: `KTRDR_ENV` controls validation strictness; local-prod is production

**Choice:** `KTRDR_ENV` is a standalone env var (not in any Settings class) read by the validation module.

- `KTRDR_ENV=production` — Insecure defaults are hard failures. Set by `ktrdr local-prod up` and production deploys.
- `KTRDR_ENV=development` — Insecure defaults are loud warnings. Set by `ktrdr sandbox up`. Default if not set.
- `KTRDR_ENV=test` — Reserved for CI. Same behavior as development.

**Key decision: local-prod IS production.** It runs IB Gateway, GPU training, real money decisions. It must not silently use insecure defaults.

```python
# ktrdr/cli/local_prod.py
compose_env["KTRDR_ENV"] = "production"

# ktrdr/cli/sandbox.py
compose_env["KTRDR_ENV"] = "development"
```

### Decision 9: `deprecated_field()` helper prevents AliasChoices gotcha

**Choice:** A helper function enforces correct usage of `validation_alias` with `AliasChoices`.

**The gotcha:** When `validation_alias` is set on a Pydantic Settings field, `env_prefix` is completely ignored for that field. The prefixed env var name must be explicitly listed in `AliasChoices`. Forgetting this causes the `KTRDR_*` name to silently not work.

```python
def deprecated_field(default, new_env: str, old_env: str, **kwargs) -> Field:
    """Create a field with both new and deprecated env var names.

    CRITICAL: validation_alias OVERRIDES env_prefix for that field.
    new_env MUST match what env_prefix would produce.
    """
    return Field(
        default=default,
        validation_alias=AliasChoices(new_env, old_env),
        **kwargs,
    )

# Usage:
class DatabaseSettings(BaseSettings):
    host: str = deprecated_field("localhost", "KTRDR_DB_HOST", "DB_HOST")
    port: int = 5432  # No deprecated name → env_prefix works normally
    model_config = SettingsConfigDict(env_prefix="KTRDR_DB_")
```

**Rule:** Fields WITHOUT deprecated names use `env_prefix` normally (no `validation_alias`). Fields WITH deprecated names use `deprecated_field()` (which sets `validation_alias`).

## Resolved Questions

Questions from the design process, now answered:

### Q1: Where do indicator/fuzzy configs live?

**Answer:** These are domain data, not system config.

- **indicators.yaml** — Not used by any runtime code. Relic from earlier development. **Delete it.**
- **fuzzy.yaml** — Actively used by `FuzzyService` to define fuzzy set membership functions. This is domain data (like strategies). **Stays as YAML**, excluded from this redesign.

### Q2: What about workers.*.yaml files?

**Answer:** These are deployment artifacts, not application config.

- `config/workers.dev.yaml` and `config/workers.prod.yaml` are templates for deployment scripts
- Tests validate their structure exists, but no Python runtime code loads them
- They define which physical/virtual machines run which worker types
- **Keep as-is** — they're infrastructure tooling in `config/deploy/`, not application config

### Q3: What about training-host-service?

**Answer:** Separate project, separate config.

- It's a standalone deployable with its own `config/settings.yaml`
- Should follow the same *pattern* (Pydantic Settings) but have its own settings module
- No shared code — just consistent approach

### Q4: Documentation generation?

**Answer:** Yes, auto-generate.

- Use Pydantic's schema export or a simple script to generate `docs/configuration.md`
- Triggered on release or manually via `make docs-config`
- Shows all settings, types, defaults, and env var names

## Open Questions

Issues to resolve during implementation:

1. **Testing config** — How do tests override settings? Options:
   - Set env vars in pytest fixtures (simple, explicit)
   - A `TestSettings` class that overrides defaults
   - `monkeypatch.setenv()` in conftest.py

   Leaning toward env vars in fixtures for explicitness.

---

## Summary

| Aspect | Current State | New State |
|--------|--------------|-----------|
| Config mechanism | 5 patterns (YAML, Pydantic, dataclass, raw env, metadata.py) | 1 pattern (Pydantic Settings) |
| Env var naming | ~90 vars with mixed naming (DB_\*, IB_\*, KTRDR_\*, ORPHAN_\*, AGENT_\*, etc.) | Consistent (KTRDR_\*) across ~90 vars in 16 Settings classes |
| Settings location | 14 YAML files + 5 Python modules + scattered `os.getenv()` in ~30 files | One `settings.py` module |
| Duplications | 6 major (APIConfig vs APISettings, 3 names for "environment", etc.) | Zero — single source of truth per concept |
| Secrets handling | Mix of .env files, compose defaults, and 1Password | 1Password only; insecure defaults with loud warnings |
| Startup validation | None — invalid config fails at runtime | Complete, fail-fast at startup |
| Discoverability | Hunt through 14+ files | Open settings.py, see everything |

---

## Scope of Migration (From Codebase Audit)

Full audit performed 2026-01-27. See `ARCHITECTURE.md` → Complete Migration Map for every env var.

**By the numbers:**
- **~90 env vars** to standardize into **16 Settings classes**
- **~50 deprecated name mappings** (old → new)
- **10 YAML files** to delete
- **5 Python modules** to delete (`metadata.py`, `api/config.py`, `ib_config.py`, `host_services.py`, `credentials.py`)
- **~30 scattered reads** to consolidate into single cached getters
- **6 duplications** to resolve
- **1 bug to fix** (`WORKER_PORT` inconsistency between training worker and registration)

## Next Steps

1. ~~**Architecture doc**~~ — Done. See `ARCHITECTURE.md`.
2. ~~**Validation**~~ — Done. See `SCENARIOS.md`.
3. **Define implementation milestones** — Vertical slices, one settings group at a time
4. **Implement** — Following the phased migration plan in `ARCHITECTURE.md`
