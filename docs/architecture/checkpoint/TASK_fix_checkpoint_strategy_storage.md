# Fix: Checkpoint Strategy Storage Causes Resume Failure

## Problem Summary

During M4 E2E testing, resume fails because the strategy YAML stored in the checkpoint state is **truncated**. The worker's `_execute_resumed_training` fails with:

```
ValidationError: Failed to parse strategy YAML: while scanning a quoted scalar
  in "/tmp/tmpp47d3ylr/resumed_training.yaml", line 3, column 14
found unexpected end of stream
```

The checkpoint state shows truncated content:
```json
"strategy_yaml": "# === STRATEGY IDENTITY ===\nname: \"test_e2e_local_pull\"\ndescription: \"Minimal strategy for E2E testi"
```

## Root Cause

The strategy YAML is being stored in the checkpoint's `state` field in the database. This is problematic because:

1. **Truncation**: The JSON state column likely has size limits, causing truncation
2. **Wrong location**: Large content should be in filesystem artifacts, not DB
3. **Unnecessary**: The strategy file already exists on disk at `strategies/xxx.yaml`

## Proposed Fix

**Don't store strategy YAML in checkpoint at all.** Instead:

1. Store only the **strategy path** in checkpoint metadata (e.g., `"strategy_path": "strategies/test_e2e_local_pull.yaml"`)
2. On resume, read the strategy from the original file path
3. If the strategy file was deleted/modified, resume fails with clear error message

This aligns with the existing architecture:
- **DB state**: Small metadata (epoch, losses, learning_rate, training_history)
- **Filesystem artifacts**: Large binary data (model.pt, optimizer.pt, scheduler.pt)
- **External files**: Strategy YAML (already on disk, no need to duplicate)

## Files to Modify

### 1. `ktrdr/training/training_worker.py`

In `_save_checkpoint_state()` around line 400-450:
- Change `original_request` to only store `strategy_path` instead of `strategy_yaml`
- Or remove `strategy_yaml` from `original_request` entirely

### 2. `ktrdr/training/training_worker.py`

In `_execute_resumed_training()` around line 600-650:
- Instead of reading strategy from `checkpoint.state["original_request"]["strategy_yaml"]`
- Read strategy from `checkpoint.state["original_request"]["strategy_path"]` (file on disk)
- Add error handling if strategy file doesn't exist

### 3. `ktrdr/checkpoint/schemas.py`

In `TrainingCheckpointState`:
- Consider adding `strategy_path: Optional[str]` field
- Remove or deprecate `strategy_yaml` from `original_request`

## Verification Steps

After fix:
1. Start training
2. Wait for checkpoint
3. Cancel training
4. Verify checkpoint state has `strategy_path` not `strategy_yaml`
5. Resume training
6. Verify training continues from correct epoch
7. Let training complete
8. Verify checkpoint deleted

## Other Large Data in DB?

Check these fields in checkpoint state for potential truncation issues:
- `training_history` - Could grow large with many epochs (but less likely to hit limits)
- `original_request` - Contains the problematic `strategy_yaml`

## Alternative Considered

Could store strategy YAML in filesystem artifacts alongside model.pt, but this adds complexity and duplicates data that already exists on disk.

---

**Priority**: HIGH - Blocks M4 E2E test completion
**Estimated Effort**: 1-2 hours
**Dependencies**: None
