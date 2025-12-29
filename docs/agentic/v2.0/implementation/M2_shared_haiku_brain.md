---
design: ../DESIGN.md
architecture: ../SCENARIOS.md
---

# Milestone 2: Shared HaikuBrain

**Branch:** `feature/v2-memory-m2`
**Builds on:** Milestone 1
**Goal:** Refactor HaikuBrain to shared location, add assessment parsing

---

## E2E Test Scenario

**Purpose:** Verify HaikuBrain works from both orchestrator and agent contexts
**Prerequisites:** M1 complete, Claude CLI available

```bash
# 1. Verify orchestrator still works with updated imports
uv run pytest orchestrator/tests/test_haiku_brain.py -v
# Expected: All existing tests pass

# 2. Test new parse_assessment method
uv run python -c "
from ktrdr.llm.haiku_brain import HaikuBrain

brain = HaikuBrain()

# Test with structured assessment
structured = '''
## Assessment

### Verdict
strong_signal

### Observations
- RSI + DI combination improved accuracy by 0.6pp
- Val-test gap of 1.7pp indicates good generalization

### Hypotheses Generated
- H: Multi-timeframe might break the plateau | Status: untested

### Limitations
- Only tested on 1h EURUSD
'''

result = brain.parse_assessment(structured, {})
print(f'Verdict: {result.verdict}')
print(f'Observations: {len(result.observations)}')
print(f'Hypotheses: {len(result.hypotheses)}')
assert result.verdict == 'strong_signal'
assert len(result.observations) >= 2
print('OK')
"

# 3. Test with prose assessment (Haiku extracts what it can)
uv run python -c "
from ktrdr.llm.haiku_brain import HaikuBrain

brain = HaikuBrain()

prose = '''
This strategy performed surprisingly well. The combination of RSI and DI
produced a test accuracy of 64.8%, which is significantly above random.
The validation-test gap was minimal, suggesting the model generalizes well.
I think this is a promising approach worth building on.
'''

result = brain.parse_assessment(prose, {})
print(f'Verdict: {result.verdict}')
assert result.verdict in ['strong_signal', 'weak_signal', 'promising']
print('OK')
"
```

**Success Criteria:**
- [ ] HaikuBrain moved to `ktrdr/llm/haiku_brain.py`
- [ ] All orchestrator tests still pass
- [ ] New `parse_assessment()` method works with structured input
- [ ] New `parse_assessment()` method works with prose input
- [ ] ParsedAssessment dataclass contains all required fields

---

## Task 2.1: Create ktrdr/llm Package

**File:** `ktrdr/llm/__init__.py` (NEW)
**Type:** CODING
**Estimated time:** 30 minutes

**Description:**
Create the new `ktrdr/llm` package that will house shared LLM utilities. Start with just the package init.

**Implementation Notes:**
- Simple package with re-exports from haiku_brain
- This becomes the import point for both orchestrator and agents

**Code:**
```python
"""Shared LLM utilities for KTRDR.

This package provides LLM-based utilities used across the codebase:
- HaikuBrain: Fast, cheap interpretation via Claude Haiku
"""

from ktrdr.llm.haiku_brain import (
    HaikuBrain,
    InterpretationResult,
    RetryDecision,
    ParsedAssessment,
    ExtractedTask,
)

__all__ = [
    "HaikuBrain",
    "InterpretationResult",
    "RetryDecision",
    "ParsedAssessment",
    "ExtractedTask",
]
```

**Tests:** None needed (just re-exports)

**Acceptance Criteria:**
- [ ] `ktrdr/llm/__init__.py` exists
- [ ] Package can be imported: `from ktrdr.llm import HaikuBrain`

---

## Task 2.2: Move HaikuBrain to Shared Location

**Files:**
- `orchestrator/haiku_brain.py` → `ktrdr/llm/haiku_brain.py` (MOVE)
- `orchestrator/runner.py` (MODIFY imports)
- `orchestrator/tests/test_haiku_brain.py` (MODIFY imports)

**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Move HaikuBrain from orchestrator to the shared ktrdr/llm location. Update all imports in orchestrator to use the new location.

**Implementation Notes:**
- Pure file move, no logic changes
- Update imports in runner.py: `from ktrdr.llm.haiku_brain import HaikuBrain, get_brain`
- Update test imports similarly
- Keep `get_brain()` and `configure_interpreter()` in runner.py (module-level state stays there)

**Changes:**

`orchestrator/runner.py`:
```python
# Before:
from orchestrator.haiku_brain import HaikuBrain

# After:
from ktrdr.llm.haiku_brain import HaikuBrain
```

`orchestrator/tests/test_haiku_brain.py`:
```python
# Before:
from orchestrator.haiku_brain import HaikuBrain, ...

# After:
from ktrdr.llm.haiku_brain import HaikuBrain, ...
```

**Tests:** Run existing orchestrator tests
```bash
uv run pytest orchestrator/tests/test_haiku_brain.py -v
uv run pytest orchestrator/tests/test_runner.py -v
```

**Acceptance Criteria:**
- [ ] `ktrdr/llm/haiku_brain.py` exists with full HaikuBrain class
- [ ] `orchestrator/haiku_brain.py` deleted
- [ ] All orchestrator tests pass with new imports
- [ ] No import errors when running orchestrator

---

## Task 2.3: Add ParsedAssessment Dataclass

**File:** `ktrdr/llm/haiku_brain.py` (MODIFY)
**Type:** CODING
**Estimated time:** 30 minutes

**Description:**
Add the ParsedAssessment dataclass that will be returned by the new parse_assessment method.

**Implementation Notes:**
- Matches the interface contract from SCENARIOS.md
- All fields have sensible defaults (for graceful degradation)
- `raw_text` preserves original for debugging

**Code:**
```python
@dataclass
class ParsedAssessment:
    """Structured data extracted from agent's assessment output."""

    verdict: str  # "strong_signal" | "weak_signal" | "no_signal" | "overfit"
    observations: list[str]
    hypotheses: list[dict]  # [{"text": "...", "status": "untested"}]
    limitations: list[str]
    capability_requests: list[str]
    tested_hypothesis_ids: list[str]  # H_001, H_002, etc. if mentioned
    raw_text: str  # Original output for reference

    @classmethod
    def empty(cls, raw_text: str) -> "ParsedAssessment":
        """Create empty result when parsing fails."""
        return cls(
            verdict="unknown",
            observations=[],
            hypotheses=[],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=[],
            raw_text=raw_text,
        )
```

**Tests:** `tests/unit/llm/test_haiku_brain.py` (NEW)
- [ ] `test_parsed_assessment_empty` — empty() creates valid object
- [ ] `test_parsed_assessment_fields` — all fields accessible

**Acceptance Criteria:**
- [ ] ParsedAssessment dataclass defined
- [ ] `empty()` classmethod works
- [ ] Exported from `ktrdr.llm`

---

## Task 2.4: Add parse_assessment Method

**File:** `ktrdr/llm/haiku_brain.py` (MODIFY)
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Add the `parse_assessment()` method to HaikuBrain. This uses Haiku to extract structured data from any assessment format (structured markdown, prose, or mixed).

**Implementation Notes:**
- Always uses Haiku (no regex fallback per design decision)
- Returns ParsedAssessment with all fields populated
- Graceful degradation: if Haiku fails, return ParsedAssessment.empty()
- Context parameter provides strategy_config for reference but may not be needed

**Prompt for Haiku:**
```python
PARSE_ASSESSMENT_PROMPT = """Extract structured assessment data from this agent output.

The output may be structured (with headers like "### Verdict") or prose.
Extract what you can, using reasonable defaults for missing fields.

Return a JSON object:
{{
  "verdict": "strong_signal" | "weak_signal" | "no_signal" | "overfit",
  "observations": ["observation 1", "observation 2", ...],
  "hypotheses": [{{"text": "hypothesis text", "status": "untested"}}, ...],
  "limitations": ["limitation 1", ...],
  "capability_requests": ["request 1", ...],
  "tested_hypothesis_ids": ["H_001", ...] // if existing hypotheses are mentioned
}}

Guidelines:
- verdict: Classify based on test accuracy and generalization
  - "strong_signal": test accuracy >= 60%, small val-test gap
  - "weak_signal": test accuracy 55-60%
  - "no_signal": test accuracy <= 55% or large val-test gap
  - "overfit": high validation, low test (gap > 10pp)
- observations: Key factual statements about results
- hypotheses: New ideas generated for future testing
- limitations: What wasn't tested, caveats
- capability_requests: Things the agent wishes it could try
- tested_hypothesis_ids: If agent mentions testing H_001 or similar

Return ONLY the JSON, no other text.

Agent output:
{output}
"""
```

**Code sketch:**
```python
def parse_assessment(
    self,
    output: str,
    context: dict[str, Any],
) -> ParsedAssessment:
    """Extract structured assessment from any format using Haiku."""
    prompt = PARSE_ASSESSMENT_PROMPT.format(output=output)

    try:
        response = self._invoke_haiku(prompt)
    except (RuntimeError, subprocess.TimeoutExpired):
        return ParsedAssessment.empty(output)

    return self._parse_assessment_response(response, output)


def _parse_assessment_response(self, response: str, raw_text: str) -> ParsedAssessment:
    """Parse Haiku response into ParsedAssessment."""
    data = self._extract_json_object(response)

    if data is None:
        return ParsedAssessment.empty(raw_text)

    return ParsedAssessment(
        verdict=data.get("verdict", "unknown"),
        observations=data.get("observations", []),
        hypotheses=data.get("hypotheses", []),
        limitations=data.get("limitations", []),
        capability_requests=data.get("capability_requests", []),
        tested_hypothesis_ids=data.get("tested_hypothesis_ids", []),
        raw_text=raw_text,
    )
```

**Tests:** `tests/unit/llm/test_haiku_brain.py`
- [ ] `test_parse_assessment_structured` — extracts from structured markdown
- [ ] `test_parse_assessment_prose` — extracts from prose (mocked Haiku)
- [ ] `test_parse_assessment_haiku_failure` — returns empty on failure
- [ ] `test_parse_assessment_partial` — handles missing fields gracefully

**Smoke Test:**
```bash
# Requires Claude CLI and ANTHROPIC_API_KEY
uv run python -c "
from ktrdr.llm.haiku_brain import HaikuBrain
brain = HaikuBrain()
result = brain.parse_assessment('This strategy achieved 64.8% test accuracy.', {})
print(result.verdict)
"
```

**Acceptance Criteria:**
- [ ] `parse_assessment()` method works with structured input
- [ ] Works with prose input (Haiku extracts meaning)
- [ ] Gracefully handles Haiku failures
- [ ] Returns ParsedAssessment with all fields
- [ ] All unit tests pass

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Orchestrator tests pass: `uv run pytest orchestrator/tests/ -v`
- [ ] New LLM tests pass: `uv run pytest tests/unit/llm/ -v`
- [ ] E2E test passes (both structured and prose parsing)
- [ ] Quality gates pass: `make quality`
- [ ] No regressions in orchestrator functionality
- [ ] HaikuBrain importable from both `ktrdr.llm` and used by orchestrator
