---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 5: Documentation

**Branch:** `feature/type-registry-m5`
**Builds on:** M2, M3
**Goal:** Skills updated to reflect new patterns

## E2E Validation

**Success Criteria:**
- [ ] technical-indicators skill mentions INDICATOR_REGISTRY
- [ ] technical-indicators skill documents Params pattern
- [ ] technical-indicators skill has no indicator_factory references
- [ ] fuzzy-logic-engine skill mentions MEMBERSHIP_REGISTRY
- [ ] fuzzy-logic-engine skill has no v2 references

---

## Task 5.1: Update technical-indicators skill

**File:** `.claude/skills/technical-indicators/SKILL.md`
**Type:** CODING
**Estimated time:** 30 min

**Changes:**
- Remove references to indicator_factory.py
- Add "Adding a New Indicator" section with Params pattern
- Document INDICATOR_REGISTRY for lookups

**New content to add:**
```markdown
## Adding a New Indicator

Create one file:

\`\`\`python
# ktrdr/indicators/awesome_indicator.py
from pydantic import Field
from ktrdr.indicators.base_indicator import BaseIndicator

class AwesomeIndicator(BaseIndicator):
    class Params(BaseIndicator.Params):
        fast_period: int = Field(default=5, ge=1)
        slow_period: int = Field(default=34, ge=1)

    # No __init__ needed - BaseIndicator handles validation

    def compute(self, df):
        # Use self.fast_period, self.slow_period
        ...
\`\`\`

That's it. The indicator auto-registers as 'awesome', 'awesomeindicator', etc.

## Registry API

\`\`\`python
from ktrdr.indicators import INDICATOR_REGISTRY

INDICATOR_REGISTRY.list_types()           # ['adx', 'atr', ...]
INDICATOR_REGISTRY.get('rsi')             # RSIIndicator class
INDICATOR_REGISTRY.get_params_schema('rsi')  # Params model
\`\`\`
```

**Acceptance Criteria:**
- [ ] No indicator_factory reference
- [ ] Params pattern documented
- [ ] INDICATOR_REGISTRY documented

---

## Task 5.2: Update fuzzy-logic-engine skill

**File:** `.claude/skills/fuzzy-logic-engine/SKILL.md`
**Type:** CODING
**Estimated time:** 30 min

**Changes:**
- Remove all v2 config references
- Add "Adding a New Membership Function" section
- Document MEMBERSHIP_REGISTRY

**New content to add:**
```markdown
## Adding a New Membership Function

Create one file:

\`\`\`python
# ktrdr/fuzzy/sigmoid_mf.py
from pydantic import field_validator
from ktrdr.fuzzy.membership import MembershipFunction

class SigmoidMF(MembershipFunction):
    class Params(MembershipFunction.Params):
        @field_validator("parameters")
        @classmethod
        def validate_parameters(cls, v):
            if len(v) != 2:
                raise ValueError("Sigmoid requires [center, slope]")
            return v

    def _init_from_params(self, parameters):
        self.center, self.slope = parameters

    def evaluate(self, x):
        ...
\`\`\`

Auto-registers as 'sigmoid', 'sigmoidmf', etc.

## Registry API

\`\`\`python
from ktrdr.fuzzy import MEMBERSHIP_REGISTRY

MEMBERSHIP_REGISTRY.list_types()  # ['gaussian', 'trapezoidal', 'triangular']
MEMBERSHIP_REGISTRY.get('triangular')  # TriangularMF class
\`\`\`

## V3 Format Only

FuzzyEngine only accepts v3 format (dict[str, FuzzySetDefinition]).
V2 FuzzyConfig format is no longer supported.
```

**Acceptance Criteria:**
- [ ] No v2 references
- [ ] MEMBERSHIP_REGISTRY documented
- [ ] New MF pattern documented

---

## Task 5.3: Execute M5 E2E Test

**Type:** VALIDATION

**E2E Test:**
```bash
# technical-indicators skill
grep -q "INDICATOR_REGISTRY" .claude/skills/technical-indicators/SKILL.md && echo "OK: INDICATOR_REGISTRY" || echo "FAIL"
grep -q "class Params" .claude/skills/technical-indicators/SKILL.md && echo "OK: Params pattern" || echo "FAIL"
grep -q "indicator_factory" .claude/skills/technical-indicators/SKILL.md && echo "FAIL: still has indicator_factory" || echo "OK: no indicator_factory"

# fuzzy-logic-engine skill
grep -q "MEMBERSHIP_REGISTRY" .claude/skills/fuzzy-logic-engine/SKILL.md && echo "OK: MEMBERSHIP_REGISTRY" || echo "FAIL"
grep -qi "v2" .claude/skills/fuzzy-logic-engine/SKILL.md && echo "FAIL: still has v2" || echo "OK: no v2"

echo "M5 E2E complete"
```

**Acceptance Criteria:**
- [ ] All checks pass
- [ ] Skills are accurate
