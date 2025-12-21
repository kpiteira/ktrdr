---
design: docs/architecture/autonomous-coding/DESIGN.md
architecture: docs/architecture/autonomous-coding/ARCHITECTURE.md
---

# Milestone: Orchestrator Health Check

**Branch:** `feature/orchestrator-health-check`

A simple 3-task milestone for validating the orchestrator.

---

## Task 1.1: Create health module

**File:** `orchestrator/health.py`
**Type:** CODING

**Description:**
Create a health module that returns system status.

**Implementation Notes:**
- Function `get_health() -> dict` returns {"status": "ok", "timestamp": ...}
- Check if sandbox container is running
- Return status info

**Acceptance Criteria:**
- [ ] File exists
- [ ] Function returns dict with "status" key
- [ ] Importable without errors

---

## Task 1.2: Add health CLI command

**File:** `orchestrator/cli.py`
**Type:** CODING

**Description:**
Add `orchestrator health` command that calls the health module.

**Acceptance Criteria:**
- [ ] `orchestrator health` command exists
- [ ] Outputs JSON health status
- [ ] Returns exit code 0 on healthy

---

## Task 1.3: Add health telemetry

**File:** `orchestrator/health.py`
**Type:** CODING

**Description:**
Emit a metric when health is checked.

**Acceptance Criteria:**
- [ ] `orchestrator_health_checks_total` counter increments
- [ ] Trace span created for health check

---

## E2E Test

```bash
# Run health check
orchestrator health

# Expected output (JSON):
# {"status": "ok", "timestamp": "2024-...", "sandbox": "running"}

# Verify in Jaeger:
# orchestrator.health_check span exists
```
