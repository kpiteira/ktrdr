# Milestone 8: Polish + Admin

**Branch:** `feature/checkpoint-m8-polish`
**Depends On:** M1-M6 (core functionality)
**Estimated Tasks:** 7

---

## Capability

When M8 is complete:
- Concurrent resume requests handled safely
- Old checkpoints automatically cleaned up
- Orphan artifacts cleaned up
- CLI shows checkpoint availability in operations list
- CLI can view checkpoint details
- Documentation complete

---

## Tasks

### Task 8.1: Verify Concurrent Resume Protection

**File(s):**
- `tests/integration/test_concurrent_resume.py` (new)

**Type:** CODING

**Description:**
Verify that concurrent resume requests are handled correctly via optimistic locking.

**Test Scenario:**
```python
async def test_concurrent_resume():
    """Only one of multiple concurrent resume requests should succeed."""
    # Create cancelled operation with checkpoint
    op_id = await create_cancelled_operation_with_checkpoint()

    # Fire multiple resume requests concurrently
    results = await asyncio.gather(
        resume_operation(op_id),
        resume_operation(op_id),
        resume_operation(op_id),
        return_exceptions=True
    )

    # Exactly one should succeed
    successes = [r for r in results if not isinstance(r, Exception) and r.get("success")]
    failures = [r for r in results if isinstance(r, Exception) or not r.get("success")]

    assert len(successes) == 1
    assert len(failures) == 2
```

**Acceptance Criteria:**
- [ ] Test fires concurrent resume requests
- [ ] Exactly one succeeds
- [ ] Others get conflict error
- [ ] No race conditions or inconsistent state

---

### Task 8.2: Implement Automatic Checkpoint Cleanup

**File(s):**
- `ktrdr/checkpointing/cleanup_service.py` (new)
- `ktrdr/api/main.py` (modify)

**Type:** CODING

**Description:**
Background task that cleans up old checkpoints.

**Implementation:**
```python
class CheckpointCleanupService:
    def __init__(
        self,
        checkpoint_service: CheckpointService,
        max_age_days: int = 30,
        cleanup_interval_hours: int = 24,
    ):
        self._checkpoint_service = checkpoint_service
        self._max_age_days = max_age_days
        self._cleanup_interval = cleanup_interval_hours * 3600
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        self._task = asyncio.create_task(self._cleanup_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()

    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(self._cleanup_interval)
            await self._run_cleanup()

    async def _run_cleanup(self):
        logger.info("Starting checkpoint cleanup...")

        # Delete old checkpoints
        deleted = await self._checkpoint_service.cleanup_old_checkpoints(
            max_age_days=self._max_age_days
        )
        logger.info(f"Deleted {deleted} old checkpoints")

        # Clean orphan artifacts
        orphans = await self._checkpoint_service.cleanup_orphan_artifacts()
        logger.info(f"Cleaned {orphans} orphan artifact directories")
```

**Acceptance Criteria:**
- [ ] Runs daily (configurable)
- [ ] Deletes checkpoints older than 30 days (configurable)
- [ ] Cleans orphan artifact directories
- [ ] Logged cleanup results

---

### Task 8.3: Add Manual Cleanup Endpoints

**File(s):**
- `ktrdr/api/endpoints/checkpoints.py` (modify)

**Type:** CODING

**Description:**
Add admin endpoints for manual cleanup operations.

**Endpoints:**
```python
@router.post("/checkpoints/cleanup")
async def trigger_cleanup(
    max_age_days: int = 30,
) -> CleanupResponse:
    """Manually trigger checkpoint cleanup."""
    deleted = await checkpoint_service.cleanup_old_checkpoints(max_age_days)
    orphans = await checkpoint_service.cleanup_orphan_artifacts()
    return CleanupResponse(
        checkpoints_deleted=deleted,
        orphan_artifacts_cleaned=orphans
    )

@router.get("/checkpoints/stats")
async def get_checkpoint_stats() -> CheckpointStatsResponse:
    """Get checkpoint storage statistics."""
    checkpoints = await checkpoint_service.list_checkpoints()
    total_size = sum(cp.state_size_bytes + (cp.artifacts_size_bytes or 0) for cp in checkpoints)
    return CheckpointStatsResponse(
        total_checkpoints=len(checkpoints),
        total_size_bytes=total_size,
        oldest_checkpoint=min(cp.created_at for cp in checkpoints) if checkpoints else None,
    )
```

**Acceptance Criteria:**
- [ ] Manual cleanup endpoint works
- [ ] Stats endpoint shows storage usage
- [ ] Proper authorization (if applicable)

---

### Task 8.4: Enhance Operations List CLI

**File(s):**
- `ktrdr/cli/operations_commands.py` (modify)

**Type:** CODING

**Description:**
Add checkpoint information to operations list output.

**Output Format:**
```
$ ktrdr operations list --status cancelled

OPERATION_ID                              STATUS     PROGRESS   CHECKPOINT   AGE
op_training_20241213_143022_abc123        CANCELLED  29%        epoch 29     2d
op_training_20241210_091500_def456        CANCELLED  45%        epoch 45     5d
op_backtesting_20241212_100000_ghi789     CANCELLED  20%        bar 7000     3d

Total: 3 operations (3 resumable)
```

**Implementation:**
```python
@operations.command()
@click.option("--status", help="Filter by status")
@click.option("--resumable", is_flag=True, help="Only show resumable operations")
def list(status: Optional[str], resumable: bool):
    """List operations."""
    async def _list():
        async with AsyncCLIClient() as client:
            ops = await client.get("/operations", params={"status": status})

            # Fetch checkpoint info for each
            for op in ops["data"]:
                checkpoint = await client.get(f"/checkpoints/{op['operation_id']}")
                op["has_checkpoint"] = checkpoint.get("success", False)
                if op["has_checkpoint"]:
                    op["checkpoint_summary"] = checkpoint["data"]["state"]

            # Filter if --resumable
            if resumable:
                ops["data"] = [op for op in ops["data"] if op["has_checkpoint"]]

            # Display
            display_operations_table(ops["data"])

    asyncio.run(_list())
```

**Acceptance Criteria:**
- [ ] List shows checkpoint column
- [ ] --resumable flag filters to resumable only
- [ ] Summary line shows resumable count

---

### Task 8.5: Add Checkpoint Details CLI Command

**File(s):**
- `ktrdr/cli/operations_commands.py` (modify)

**Type:** CODING

**Description:**
Add command to view checkpoint details before resuming.

**Command:**
```
$ ktrdr checkpoints show op_training_20241213_143022_abc123

Checkpoint Details
==================
Operation ID:    op_training_20241213_143022_abc123
Checkpoint Type: cancellation
Created At:      2024-12-13 14:35:00 UTC
Age:             2 days

Training State:
  Epoch:         29 / 100
  Train Loss:    0.28
  Val Loss:      0.31
  Best Val Loss: 0.29
  Learning Rate: 0.001

Artifacts:
  model.pt       156.2 MB
  optimizer.pt   156.2 MB
  best_model.pt  156.2 MB

Total Size: 468.6 MB

To resume: ktrdr operations resume op_training_20241213_143022_abc123
```

**Acceptance Criteria:**
- [ ] Command shows checkpoint details
- [ ] Shows state summary
- [ ] Shows artifact sizes
- [ ] Shows resume command

---

### Task 8.6: Add Checkpoint Delete CLI Command

**File(s):**
- `ktrdr/cli/operations_commands.py` (modify)

**Type:** CODING

**Description:**
Add command to manually delete a checkpoint.

**Command:**
```
$ ktrdr checkpoints delete op_training_20241213_143022_abc123

Are you sure you want to delete checkpoint for op_training_20241213_143022_abc123?
This operation is CANCELLED and will not be resumable after deletion.
[y/N]: y

Checkpoint deleted.
```

**Acceptance Criteria:**
- [ ] Command deletes checkpoint
- [ ] Confirmation prompt
- [ ] Shows warning if operation is resumable
- [ ] Success/error messages

---

### Task 8.7: Documentation Updates

**File(s):**
- `docs/user-guides/checkpoint-resume.md` (new)
- `docs/architecture/checkpoint/README.md` (new)

**Type:** DOCUMENTATION

**Description:**
Write user and developer documentation for the checkpoint system.

**User Guide Contents:**
- How checkpoints work
- Resuming operations
- Viewing checkpoint status
- Managing checkpoints (cleanup, delete)
- Troubleshooting

**Architecture README Contents:**
- Overview of checkpoint system
- Links to design docs
- Component summary
- Configuration reference

**Acceptance Criteria:**
- [ ] User guide written
- [ ] Architecture README written
- [ ] Links from main docs
- [ ] Examples included

---

## Milestone 8 Verification Checklist

Before marking M8 complete:

- [ ] All 7 tasks complete
- [ ] Unit tests pass: `make test-unit`
- [ ] Integration tests pass: `make test-integration`
- [ ] All M1-M6 E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] Documentation reviewed

---

## Files Changed Summary

| File | Action | Task |
|------|--------|------|
| `ktrdr/checkpointing/cleanup_service.py` | Create | 8.2 |
| `ktrdr/api/main.py` | Modify | 8.2 |
| `ktrdr/api/endpoints/checkpoints.py` | Modify | 8.3 |
| `ktrdr/cli/operations_commands.py` | Modify | 8.4, 8.5, 8.6 |
| `docs/user-guides/checkpoint-resume.md` | Create | 8.7 |
| `docs/architecture/checkpoint/README.md` | Create | 8.7 |
| `tests/integration/test_concurrent_resume.py` | Create | 8.1 |
