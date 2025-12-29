---
design: ../DESIGN.md
architecture: ../SCENARIOS.md
---

# Milestone 5: Hypothesis Lifecycle

**Branch:** `feature/v2-memory-m5`
**Builds on:** Milestone 3, Milestone 4
**Goal:** Hypotheses are tracked across experiments - new ones added, tested ones updated

---

## E2E Test Scenario

**Purpose:** Verify hypotheses are extracted from assessments and updated when tested
**Prerequisites:** M1-M4 complete, memory populated

```bash
# 1. Check initial hypothesis state
cat memory/hypotheses.yaml
# Note the count and status of hypotheses

# 2. Run assessment that generates new hypothesis
# (Via API trigger or unit test)

# 3. Check new hypothesis was added
cat memory/hypotheses.yaml
# Should have one more hypothesis with status="untested"

# 4. Run assessment that references existing hypothesis
# Agent output includes "Testing H_001" or "H_001 validated"

# 5. Check hypothesis status updated
cat memory/hypotheses.yaml
# H_001 should now have status="validated" or "refuted"
# H_001.tested_by should include the new experiment ID

# 6. Verify via Python
uv run python -c "
from ktrdr.agents.memory import get_all_hypotheses

hyps = get_all_hypotheses()
print(f'Total hypotheses: {len(hyps)}')

# Check for updated hypothesis
for h in hyps:
    if h.get('tested_by'):
        print(f'{h[\"id\"]}: status={h[\"status\"]}, tested_by={h[\"tested_by\"]}')

print('OK')
"
```

**Success Criteria:**
- [ ] New hypotheses extracted from assessments
- [ ] New hypotheses saved with status="untested"
- [ ] Existing hypotheses detected when referenced
- [ ] Hypothesis status updated when tested
- [ ] tested_by list includes experiment ID

---

## Task 5.1: Extract New Hypotheses from Assessment

**File:** `ktrdr/agents/workers/assessment_worker.py` (MODIFY)
**Type:** CODING
**Estimated time:** 1.5 hours

**Description:**
After parsing the assessment, extract any new hypotheses and save them to the hypothesis registry.

**Implementation Notes:**
- ParsedAssessment.hypotheses contains new hypothesis dicts
- Each has `text` and `status` (should be "untested")
- Generate hypothesis ID
- Link to source experiment
- Infer rationale from context if not provided

**Code sketch:**
```python
from ktrdr.agents.memory import (
    Hypothesis,
    save_hypothesis,
    generate_hypothesis_id,
)


async def _save_to_memory(self, ...):
    # ... existing experiment save code ...

    # NEW: Extract and save hypotheses
    await self._save_hypotheses(
        parsed_assessment=parsed_assessment,
        experiment_id=record.id,
    )


async def _save_hypotheses(
    self,
    parsed_assessment,
    experiment_id: str,
) -> None:
    """Extract and save new hypotheses from assessment."""
    try:
        for hyp_data in parsed_assessment.hypotheses:
            text = hyp_data.get("text", "")
            if not text:
                continue

            hypothesis = Hypothesis(
                id=generate_hypothesis_id(),
                text=text,
                source_experiment=experiment_id,
                rationale=hyp_data.get("rationale", "Generated during assessment"),
                status="untested",
            )

            save_hypothesis(hypothesis)
            logger.info(f"Saved new hypothesis: {hypothesis.id}")

    except Exception as e:
        logger.warning(f"Failed to save hypotheses: {e}")
```

**Tests:** `tests/unit/agents/test_assessment_worker.py`
- [ ] `test_save_hypotheses_extracts_new` — new hypotheses saved
- [ ] `test_save_hypotheses_generates_id` — unique IDs assigned
- [ ] `test_save_hypotheses_links_experiment` — source_experiment set
- [ ] `test_save_hypotheses_empty_list` — no error when no hypotheses
- [ ] `test_save_hypotheses_failure_continues` — assessment still succeeds

**Acceptance Criteria:**
- [ ] New hypotheses extracted from ParsedAssessment
- [ ] Each hypothesis gets unique ID
- [ ] Source experiment linked
- [ ] Saved to hypotheses.yaml
- [ ] Failures don't break assessment

---

## Task 5.2: Detect and Update Tested Hypotheses

**File:** `ktrdr/agents/workers/assessment_worker.py` (MODIFY)
**Type:** CODING
**Estimated time:** 1.5 hours

**Description:**
When the agent references existing hypotheses (e.g., "H_001 validated"), detect this and update the hypothesis status.

**Implementation Notes:**
- ParsedAssessment.tested_hypothesis_ids contains IDs like ["H_001"]
- HaikuBrain extracts these when parsing
- Determine status from context (validated, refuted, inconclusive)
- Call update_hypothesis_status()

**Code sketch:**
```python
from ktrdr.agents.memory import update_hypothesis_status


async def _save_to_memory(self, ...):
    # ... existing code ...

    # NEW: Update tested hypotheses
    await self._update_tested_hypotheses(
        parsed_assessment=parsed_assessment,
        experiment_id=record.id,
    )


async def _update_tested_hypotheses(
    self,
    parsed_assessment,
    experiment_id: str,
) -> None:
    """Update status of hypotheses that were tested in this experiment."""
    try:
        for hyp_id in parsed_assessment.tested_hypothesis_ids:
            # Determine status from verdict and observations
            status = self._infer_hypothesis_status(parsed_assessment, hyp_id)

            update_hypothesis_status(
                hypothesis_id=hyp_id,
                status=status,
                tested_by_experiment=experiment_id,
            )
            logger.info(f"Updated hypothesis {hyp_id}: status={status}")

    except Exception as e:
        logger.warning(f"Failed to update hypotheses: {e}")


def _infer_hypothesis_status(self, parsed_assessment, hyp_id: str) -> str:
    """Infer hypothesis status from assessment."""
    # Check observations for explicit statements
    raw_text = parsed_assessment.raw_text.lower()
    hyp_id_lower = hyp_id.lower()

    if f"{hyp_id_lower} validated" in raw_text or f"{hyp_id_lower} confirmed" in raw_text:
        return "validated"
    elif f"{hyp_id_lower} refuted" in raw_text or f"{hyp_id_lower} disproved" in raw_text:
        return "refuted"
    elif f"{hyp_id_lower} inconclusive" in raw_text or f"{hyp_id_lower} unclear" in raw_text:
        return "inconclusive"
    else:
        # Default based on overall verdict
        if parsed_assessment.verdict == "strong_signal":
            return "validated"
        elif parsed_assessment.verdict == "no_signal":
            return "refuted"
        else:
            return "inconclusive"
```

**Tests:** `tests/unit/agents/test_assessment_worker.py`
- [ ] `test_update_tested_hypotheses_validated` — status set to validated
- [ ] `test_update_tested_hypotheses_refuted` — status set to refuted
- [ ] `test_update_tested_hypotheses_inconclusive` — status set to inconclusive
- [ ] `test_update_tested_hypotheses_adds_experiment` — experiment in tested_by
- [ ] `test_update_tested_hypotheses_no_ids` — no error when empty

**Acceptance Criteria:**
- [ ] Tested hypothesis IDs detected from ParsedAssessment
- [ ] Status correctly inferred from assessment
- [ ] update_hypothesis_status called with correct args
- [ ] tested_by list updated
- [ ] Failures don't break assessment

---

## Task 5.3: Enhance HaikuBrain to Extract Hypothesis References

**File:** `ktrdr/llm/haiku_brain.py` (MODIFY)
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Update the parse_assessment prompt to better extract references to existing hypotheses (like "H_001", "H_002").

**Implementation Notes:**
- Update PARSE_ASSESSMENT_PROMPT to look for H_XXX patterns
- Haiku should identify when agent mentions testing specific hypotheses
- Return in tested_hypothesis_ids field

**Updated prompt section:**
```python
PARSE_ASSESSMENT_PROMPT = """...

- tested_hypothesis_ids: Look for references to existing hypotheses like "H_001",
  "H_002", etc. If the agent mentions testing or validating a specific hypothesis
  ID, include it here. Examples:
  - "Testing hypothesis H_001" → include "H_001"
  - "H_002 was validated by this experiment" → include "H_002"
  - "This refutes H_003" → include "H_003"
  Only include IDs explicitly mentioned, not hypotheses from new ideas.

...
"""
```

**Tests:** `tests/unit/llm/test_haiku_brain.py`
- [ ] `test_parse_assessment_extracts_hypothesis_ids` — H_XXX patterns found
- [ ] `test_parse_assessment_no_hypothesis_ids` — empty list when none mentioned
- [ ] `test_parse_assessment_multiple_hypothesis_ids` — all IDs extracted

**Acceptance Criteria:**
- [ ] Prompt updated to look for hypothesis references
- [ ] tested_hypothesis_ids populated correctly
- [ ] Works with various phrasings ("testing H_001", "H_001 validated", etc.)

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `uv run pytest tests/unit/agents/test_assessment_worker.py -v`
- [ ] HaikuBrain tests pass: `uv run pytest tests/unit/llm/test_haiku_brain.py -v`
- [ ] E2E test passes (hypothesis lifecycle complete)
- [ ] Quality gates pass: `make quality`
- [ ] No regressions in assessment flow
- [ ] New hypotheses saved to registry
- [ ] Tested hypotheses have status updated
- [ ] tested_by list includes experiment IDs

---

## Full Memory Loop Verification

After M5 is complete, the full memory loop should work:

```bash
# 1. Start with bootstrapped memory
ls memory/experiments/ | wc -l  # 24 from v1.5
cat memory/hypotheses.yaml | grep "status: untested" | wc -l  # 5+ open

# 2. Trigger research cycle
# (Agent sees experiments + hypotheses in prompt)

# 3. After assessment:
ls memory/experiments/ | wc -l  # 25 (one new)
cat memory/hypotheses.yaml  # New hypothesis added if generated
                            # Tested hypothesis updated if referenced

# 4. Next cycle sees the new experiment
# Memory loop complete!
```

This milestone completes the v2.0 Memory Foundation. The agent now has persistent memory that accumulates across sessions.
