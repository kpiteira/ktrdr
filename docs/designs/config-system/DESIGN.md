# Configuration System Redesign: Design

> **Status:** Design complete, validation paused.
> **Dependency:** Requires M6/M7 (sandbox merge) before implementation.
> See `VALIDATION_NOTES.md` for detailed session notes.

## Problem Statement

KTRDR's configuration system has grown organically and now suffers from multiple overlapping patterns, unclear precedence, and scattered settings. There are 4+ different ways to define configuration (metadata.py with YAML, Pydantic BaseSettings, dataclasses with env lambdas, direct os.getenv calls), 14+ YAML files, 60+ environment variables with inconsistent naming, and no startup validation. This makes it difficult to understand where any given setting is configured, leads to subtle bugs when precedence is unclear, and creates maintenance burden.

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
    password: str  # Required, no default
    echo: bool = False

    model_config = SettingsConfigDict(env_prefix="KTRDR_DB_")

# Clear: DB password is required, set via KTRDR_DB_PASSWORD
# Clear: All DB settings use KTRDR_DB_ prefix
# Clear: Types and defaults are visible
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

### Scenario 4: New developer onboards

```bash
# Clone repo
git clone ...

# Start with defaults (insecure but works for local dev)
docker compose up

# Backend starts with:
# - DB: localhost:5432/ktrdr/ktrdr/localdev (defaults)
# - API: 0.0.0.0:8000 (defaults)
# - No secrets required for basic local dev
```

Zero config for basic local development. Secure defaults are overridden only when needed.

### Scenario 5: Config validation fails at startup

```
$ docker compose up
backend-1  | CONFIGURATION ERROR
backend-1  | ====================
backend-1  | Missing required settings:
backend-1  |   - KTRDR_DB_PASSWORD: Database password (no default, must be set)
backend-1  |   - KTRDR_AUTH_JWT_SECRET: JWT signing secret (no default, must be set)
backend-1  |
backend-1  | Invalid settings:
backend-1  |   - KTRDR_API_PORT: 'abc' is not a valid integer
backend-1  |
backend-1  | See: docs/configuration.md for all available settings
backend-1  | ====================
backend-1 exited with code 1
```

Fail fast, fail clearly. No silent fallbacks to wrong values.

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
- `KTRDR_DB_*` — Database
- `KTRDR_API_*` — API server
- `KTRDR_AUTH_*` — Authentication
- `KTRDR_IB_*` — Interactive Brokers
- `KTRDR_WORKER_*` — Worker settings
- `KTRDR_LOG_*` — Logging
- `KTRDR_OTEL_*` — Observability/telemetry

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

**Warning mechanism (to be implemented):**
- Validation module detects when insecure defaults are active
- Emits prominent warning at startup (not a failure)
- Consider `KTRDR_ENV=production` flag that converts warnings to failures

> **Note:** This decision was revised during validation session (2025-01-18).
> See `VALIDATION_NOTES.md` for full context.

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

### Decision 7: Validation runs at import time

**Choice:** Settings are validated when the settings module is imported, before the application starts serving requests.

**Rationale:**
- Fail fast: broken config never serves traffic
- Clear errors: all validation errors reported together
- Testable: can test config loading in isolation
- Current behavior for Pydantic Settings (keep it)

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
| Config mechanism | 4+ patterns (YAML, Pydantic, dataclass, raw env) | 1 pattern (Pydantic Settings) |
| Env var naming | Mixed (DB_*, IB_*, KTRDR_*, ORPHAN_*) | Consistent (KTRDR_*) |
| Settings location | 14+ YAML files + scattered Python | One settings.py module |
| Secrets handling | Mix of .env files and 1Password | 1Password only, injected at deploy |
| Startup validation | Partial/none | Complete, fail-fast |
| Discoverability | Hunt through multiple files | Open settings.py, see everything |

---

## Next Steps

1. **Architecture doc** — Define the specific classes, modules, and migration approach
2. **Validation via /kdesign-validate** — Trace scenarios through proposed architecture
3. **Implementation milestones** — Incremental migration, one settings group at a time
