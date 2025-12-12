# Task: Session Recovery & Cancellation

**Priority:** High (system reliability)
**Effort:** 2-3 hours
**Branch:** `feature/agent-mvp`

---

## The Problem

Sessions can get into inconsistent states:

| Situation | Example | Impact |
|-----------|---------|--------|
| Operation disappeared | Session in TRAINING with `operation_id` that doesn't exist | Session stuck, no way forward |
| Test artifacts | Integration test left session pointing to mock operation | Blocks real cycles |
| Backend restart | Operations lost, session thinks work is ongoing | Manual DB fix needed |

**Common thread:** Session claims to have an operation, but the operation doesn't exist.

---

## Solution

### 1. Orphan Detection (Automatic)

On each trigger check, verify session's operation actually exists:

```python
# In TriggerService.check_and_trigger()
if session.operation_id:
    operation = await self.get_operation(session.operation_id)
    if not operation:
        # Orphan detected - operation disappeared
        await self.db.update_session(
            session_id=session.id,
            phase=SessionPhase.FAILED,
            is_active=False,
            completed_at=datetime.utcnow(),
            failure_reason="Operation disappeared"
        )
        logger.warning(
            f"Orphan session {session.id} detected: "
            f"operation {session.operation_id} not found. Marked as failed."
        )
        return {"triggered": False, "reason": "orphan_recovered"}
```

This handles the common case automatically - no manual intervention needed.

### 2. Manual Cancel (Backstop)

For anything else, add a CLI command:

```bash
ktrdr agent cancel <session_id>
```

Implementation:

```python
async def cancel_session(session_id: int) -> dict:
    """Cancel session - works regardless of state."""
    session = await db.get_session(session_id)
    if not session:
        return {"success": False, "error": "Session not found"}

    # Try to cancel operation if it exists (best effort)
    if session.operation_id:
        try:
            await operations_service.cancel(session.operation_id)
        except Exception:
            pass  # Operation might not exist, that's fine

    # Always update session
    await db.update_session(
        session_id=session_id,
        phase=SessionPhase.CANCELLED,
        is_active=False,
        completed_at=datetime.utcnow()
    )

    return {"success": True, "session_id": session_id}
```

---

## Acceptance Criteria

- [x] TriggerService detects orphan sessions (operation_id exists but operation doesn't)
- [x] Orphan sessions automatically marked as FAILED (FAILED_ORPHAN outcome)
- [x] `ktrdr agent cancel <session_id>` cancels any session
- [x] Cancel works even if operation doesn't exist
- [x] Orphan detection and cancellation logged

---

## Test Scenarios

1. **Orphan detection**
   - Create session with fake operation_id
   - Run trigger check
   - Verify session marked as FAILED

2. **Manual cancel - normal session**
   - Create active session
   - Run `ktrdr agent cancel`
   - Verify session marked as CANCELLED

3. **Manual cancel - orphan session**
   - Create session with non-existent operation_id
   - Run `ktrdr agent cancel`
   - Verify it works without error

---

## Future Work (Not This Task)

If we encounter other failure modes:

- **Stuck operations** (progress not advancing) - Add progress tracking
- **Retry logic** - Auto-retry failed phases
- **Checkpoints** - Resume from progress point instead of scratch

These can be added when/if we actually see those problems.
