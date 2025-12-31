# Handoff: M5 Hypothesis Lifecycle

## Gotchas

### Test Isolation for Memory Files
**Problem:** Tests calling `_save_to_memory` were modifying the real `memory/hypotheses.yaml` because only `EXPERIMENTS_DIR` was patched, not `HYPOTHESES_FILE`.

**Symptom:** Running tests added spurious entries to `memory/hypotheses.yaml`.

**Solution:** Always patch BOTH paths when testing `_save_to_memory`:
```python
with (
    patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path / "experiments"),
    patch("ktrdr.agents.memory.HYPOTHESES_FILE", tmp_path / "hypotheses.yaml"),
):
    await worker._save_to_memory(...)
```

### String Matching: "hypothesis" vs "hypotheses"
**Problem:** "hypothesis" is NOT a substring of "hypotheses" (different suffixes: -sis vs -ses).

**Symptom:** Assertion `"hypothesis" in "hypotheses"` returns False.

**Solution:** Use exact word in assertions, or check for both forms.

## Patterns Established

### Graceful Degradation for Memory Operations
All memory operations follow this pattern:
```python
try:
    # Memory operation
except Exception as e:
    logger.warning(f"Failed to X: {e}")
    # Don't raise - memory is enhancement, not requirement
```

### Hypothesis ID Generation
Sequential IDs: H_001, H_002, etc. Generated via `generate_hypothesis_id()` which reads existing hypotheses to find the next number.

### ParsedAssessment.hypotheses Structure
Each hypothesis dict has:
- `text`: The hypothesis text (required, skip if empty)
- `status`: Usually "untested"
- `rationale`: Optional, defaults to "Generated during assessment"

## Files Modified in Task 5.1
- `ktrdr/agents/workers/assessment_worker.py` - Added `_save_hypotheses()` method
- `tests/unit/agent_tests/test_assessment_worker.py` - Added TestSaveHypotheses class, fixed test isolation

## Next Tasks (5.2, 5.3)
Task 5.2 will need to detect and update tested hypotheses - uses `ParsedAssessment.tested_hypothesis_ids` which is already populated by HaikuBrain.

Task 5.3 will enhance HaikuBrain prompt to better extract H_XXX patterns from assessment text.
