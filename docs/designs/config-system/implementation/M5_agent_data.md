---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 5: Agent & Data Settings

**Goal:** Agent reads config correctly. Data paths work. CLI uses proper API client settings.

**Why M5:** Agent and data are the application layer built on top of the infrastructure. After M4 completes worker config, M5 handles the final application-level settings.

**Branch:** `feature/config-m5-agent-data`

**Depends on:** M4 (Workers)

---

## Task 5.1: Create `AgentSettings` Class

**Files:** `ktrdr/config/settings.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Add `AgentSettings` class for agent process configuration.

**Implementation Notes:**
- Include: agent_id, strategy_path, max_positions, risk_limit, etc.
- Reference any existing agent-related env vars in the codebase

**Key signatures:**
```python
class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KTRDR_AGENT_", env_file=".env.local")
    # Fields: agent_id, strategy_path, max_positions, risk_limit, ...

@lru_cache
def get_agent_settings() -> AgentSettings: ...
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `AgentSettings` loads defaults correctly
- [ ] Agent-specific env vars work

**Acceptance Criteria:**
- [ ] `AgentSettings` class exists
- [ ] `get_agent_settings()` cached getter exists

---

## Task 5.2: Create `AgentGateSettings` Class

**Files:** `ktrdr/config/settings.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Add `AgentGateSettings` class for agent gate (simulation/live trading gate) configuration.

**Implementation Notes:**
- Include: mode (simulation/live), dry_run, confirmation_required, etc.
- These settings control whether agent can actually execute trades

**Key signatures:**
```python
class AgentGateSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KTRDR_GATE_", env_file=".env.local")
    # Fields: mode, dry_run, confirmation_required, ...

@lru_cache
def get_agent_gate_settings() -> AgentGateSettings: ...
```

**Acceptance Criteria:**
- [ ] `AgentGateSettings` class exists
- [ ] `get_agent_gate_settings()` cached getter exists

---

## Task 5.3: Create `DataSettings` Class

**Files:** `ktrdr/config/settings.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Add `DataSettings` class for data storage paths and configuration.

**Implementation Notes:**
- Include: data_dir, cache_dir, models_dir, etc.
- Reference any existing `DATA_*` or `CACHE_*` env vars

**Key signatures:**
```python
class DataSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KTRDR_DATA_", env_file=".env.local")
    # Fields: data_dir, cache_dir, models_dir, ...

@lru_cache
def get_data_settings() -> DataSettings: ...
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `DataSettings` loads defaults correctly
- [ ] Paths resolve correctly

**Acceptance Criteria:**
- [ ] `DataSettings` class exists
- [ ] `get_data_settings()` cached getter exists
- [ ] Default paths make sense for local dev

---

## Task 5.4: Create `APIClientSettings` Class

**Files:** `ktrdr/config/settings.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Add `APIClientSettings` class for CLI and other clients that need to connect to the backend API. This resolves duplication #5 from audit (multiple env vars for the same backend URL concept).

**Implementation Notes:**
- Include: base_url, timeout, retry_count, etc.
- Use `deprecated_field()` for `KTRDR_API_URL` → `KTRDR_API_CLIENT_BASE_URL`
- This is the single source of truth for "how to connect to backend"

**Key signatures:**
```python
class APIClientSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KTRDR_API_CLIENT_", env_file=".env.local")
    # Fields: base_url, timeout, retry_count, ...

@lru_cache
def get_api_client_settings() -> APIClientSettings: ...
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `APIClientSettings` loads defaults correctly
- [ ] `KTRDR_API_URL` (deprecated) works with warning

**Acceptance Criteria:**
- [ ] `APIClientSettings` class exists
- [ ] Single source of truth for backend URL (resolves duplication #5)
- [ ] Deprecated name support

---

## Task 5.5: Migrate Agent Consumers

**Files:** `ktrdr/agent/*.py`
**Type:** CODING

**Task Categories:** Wiring/DI

**Description:**
Replace all agent-related `os.getenv()` calls with settings getters.

**Implementation Notes:**
- Find all `os.getenv("AGENT_*")` and similar calls
- Replace with `get_agent_settings().field` or `get_agent_gate_settings().field`

**Acceptance Criteria:**
- [ ] Zero direct agent env var reads
- [ ] Agent functionality unchanged

---

## Task 5.6: Migrate Data/Path Consumers

**Files:** Various modules that read data paths
**Type:** CODING

**Task Categories:** Wiring/DI

**Description:**
Replace all data path `os.getenv()` calls with `get_data_settings()`.

**Implementation Notes:**
- Find all `os.getenv("DATA_DIR")`, `os.getenv("CACHE_DIR")`, etc.
- Replace with `get_data_settings().data_dir`, etc.

**Acceptance Criteria:**
- [ ] Zero direct data path env var reads
- [ ] Data paths work correctly

---

## Task 5.7: Migrate CLI/API Client Consumers

**Files:** `ktrdr/cli/*.py`
**Type:** CODING

**Task Categories:** Wiring/DI

**Description:**
Replace all CLI API client configuration with `get_api_client_settings()`.

**Implementation Notes:**
- Find all `os.getenv("KTRDR_API_URL")` and similar
- Replace with `get_api_client_settings().base_url`

**Acceptance Criteria:**
- [ ] Zero direct API URL env var reads in CLI
- [ ] CLI connects to backend correctly

---

## Task 5.8: Update Validation and Deprecation Modules

**Files:** `ktrdr/config/validation.py`, `ktrdr/config/deprecation.py`
**Type:** CODING

**Task Categories:** Configuration

**Description:**
Update validation and deprecation modules for M5 Settings classes.

**Acceptance Criteria:**
- [ ] All M5 settings validated appropriately
- [ ] All M5 deprecated names in `DEPRECATED_NAMES`

---

## Task 5.9: Write Unit Tests

**Files:** `tests/unit/config/test_agent_settings.py`, `tests/unit/config/test_data_settings.py`, etc.
**Type:** CODING

**Description:**
Write unit tests for all M5 Settings classes.

**Acceptance Criteria:**
- [ ] All M5 Settings classes have unit tests
- [ ] `make test-unit` passes

---

## Task 5.10: Execute E2E Test

**Type:** VALIDATION

**Description:**
Validate M5 is complete with E2E scenarios.

**E2E Test Scenarios:**

### Scenario 1: Agent reads config
```bash
docker compose up -d backend
# Run agent with specific settings (dry_run is in AgentGateSettings)
KTRDR_GATE_DRY_RUN=true uv run ktrdr agent run --strategy test
# Expected: agent runs in dry run mode
docker compose down
```

### Scenario 2: Data paths work
```bash
# Set custom data dir
KTRDR_DATA_DIR=/tmp/ktrdr-test uv run python -c "from ktrdr.config import get_data_settings; print(get_data_settings().data_dir)"
# Expected: /tmp/ktrdr-test
```

### Scenario 3: CLI uses correct API URL
```bash
docker compose up -d backend
# CLI should connect using settings
uv run ktrdr ops list
# Expected: success (proves CLI connected to backend)
docker compose down
```

### Scenario 4: Deprecated KTRDR_API_URL works
```bash
KTRDR_API_URL=http://localhost:8000 uv run python -c "from ktrdr.config import get_api_client_settings; print(get_api_client_settings().base_url)"
# Expected: prints URL and emits deprecation warning
```

**Success Criteria:**
- [ ] All scenarios pass
- [ ] Agent configuration works
- [ ] Data paths work
- [ ] CLI/API client settings work
- [ ] Duplication #5 (multiple backend URL env vars) resolved

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E tests pass
- [ ] Quality gates pass: `make quality`
- [ ] Duplication #5 (backend URL inconsistency) resolved
- [ ] Branch merged to main
