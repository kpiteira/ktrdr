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

## Files Modified in Task 5.2
- `ktrdr/agents/workers/assessment_worker.py` - Added `_update_tested_hypotheses()` and `_infer_hypothesis_status()` methods
- `tests/unit/agent_tests/test_assessment_worker.py` - Added TestUpdateTestedHypotheses class (8 tests)

## Status Inference Logic (Task 5.2)
`_infer_hypothesis_status()` checks in this order:
1. **Explicit statements in raw_text** (case-insensitive):
   - "H_001 validated" or "H_001 confirmed" → "validated"
   - "H_001 refuted" or "H_001 disproved" → "refuted"
   - "H_001 inconclusive" or "H_001 unclear" → "inconclusive"
2. **Fallback to verdict**:
   - strong_signal → "validated"
   - no_signal → "refuted"
   - anything else → "inconclusive"

## Files Modified in Task 5.3
- `ktrdr/llm/haiku_brain.py` - Enhanced `PARSE_ASSESSMENT_PROMPT` with detailed H_XXX extraction instructions
- `tests/unit/llm/test_haiku_brain.py` - Added 5 new tests: 3 for hypothesis ID extraction, 2 for prompt validation

## Prompt Enhancement (Task 5.3)
The `PARSE_ASSESSMENT_PROMPT` now includes explicit examples for extracting hypothesis references:
- "Testing hypothesis H_001" → include "H_001"
- "H_002 was validated by this experiment" → include "H_002"
- "This refutes H_003" → include "H_003"
- "H_004 inconclusive" → include "H_004"

Key distinction: `tested_hypothesis_ids` is for EXISTING hypotheses being referenced, not new hypotheses being generated.

## Milestone Complete
All M5 tasks (5.1, 5.2, 5.3) are complete. The hypothesis lifecycle is now fully implemented:
1. New hypotheses extracted from assessments → saved with status="untested"
2. Existing hypotheses detected when referenced in assessment text
3. Hypothesis status updated (validated/refuted/inconclusive) based on context
4. `tested_by` list tracks which experiments tested each hypothesis
