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
