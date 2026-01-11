# Handoff: Milestone 3 - Pre-Flight Cure System

## Task 3.1 Complete: Symptom→Cure Mappings

**File:** `.claude/skills/e2e-testing/preflight/common.md`

### Cure Structure

Each cure mapping follows this pattern:
- **Symptom** — What the error looks like
- **Cause** — Why it happens
- **Cure** — Copy-paste bash commands
- **Max Retries** — How many times to try
- **Wait After Cure** — How long to wait before retry

### Three Cures Added

| Symptom | Retries | Wait |
|---------|---------|------|
| Docker Not Running | 2 | 15s |
| Backend API Not Responding | 2 | 10s |
| Wrong Port (Sandbox Issue) | 1 | 0s |

### For Task 3.2

The e2e-tester agent needs to implement cure loop logic that:
1. Detects which symptom matches the pre-flight failure
2. Looks up the cure in preflight/common.md
3. Executes cure commands
4. Waits the specified time
5. Retries up to max attempts
6. Escalates if all attempts fail

Key patterns:
- Symptom text appears in pre-flight check fail messages
- Match "Docker containers not all running" → Docker Not Running cure
- Match "Backend API not responding" → Backend API Not Responding cure
- Match "connection refused" on port 8000 with sandbox → Wrong Port cure

---

## Task 3.2 Complete: Tester Agent Cure Logic

**File:** `.claude/agents/e2e-tester.md`

### Changes Made

1. **Pre-flight section (b)** — Replaced placeholder with full cure loop pseudocode
2. **New "Cure Application" section** — Added with:
   - When to apply cures
   - Cure reporting formats (success and failure templates)
   - Diagnostic gathering checklist

### Report Formats

Agent now reports cures in two formats:

**Success:** `**Pre-flight:** PASSED (after cure)` + `**Cures Applied:**` list
**Failure:** `**Pre-flight:** FAILED` + `**Cures Attempted:**` + `**Diagnostics:**` + `**Escalation:**`

### For Task 3.3

Task 3.3 is the integration test — manually verify the cure system works by:
1. Stopping backend (`docker compose stop backend`)
2. Invoking tester agent
3. Observing cure application and recovery

---

## Task 3.3 Complete: Cure Integration Test

### Test Results

| Test | Description | Result |
|------|-------------|--------|
| Test A | Docker Recovery | ✅ PASSED |
| Test B | Unrecoverable Failure | ✅ PASSED |

### Key Observations

1. **Sandbox port matters** — Must use `KTRDR_API_PORT` from `.env.sandbox` (8001), not default 8000
2. **`restart` vs `down`** — `docker compose restart backend` fails silently if container doesn't exist (after `down`)
3. **Port conflicts** — Multiple KTRDR instances can cause port conflicts; `ktrdr sandbox up` handles this better than raw `docker compose up`

### Gotcha for Future Tests

When testing cure behavior:
- Use `docker compose stop backend` for recoverable failures (container exists, just stopped)
- Use `docker compose down` for unrecoverable failures (containers removed)

---

## M3 Milestone Complete

All tasks completed:
- [x] Task 3.1: Symptom→cure mappings in preflight/common.md
- [x] Task 3.2: Cure loop logic in e2e-tester agent
- [x] Task 3.3: Integration test verified both recovery and escalation

### E2E Verification Results

- [x] Pre-flight failure detected correctly
- [x] Cure applied automatically
- [x] 10s wait observed
- [x] Retry succeeds
- [x] Unrecoverable failure → proper escalation with diagnostics
