# E2E Test: skills/m5-documentation-complete

**Purpose:** Validate M5 skill documentation reflects new patterns (registries, Params classes) and removes deprecated API references

**Duration:** <30s (static file analysis only, no runtime services)

**Category:** Skills / Documentation / Cleanup

---

## Pre-Flight Checks

**Required modules:**
- None (this test validates markdown file content, does not require running services)

**Test-specific checks:**
- [ ] Skill files exist: `.claude/skills/technical-indicators/SKILL.md`
- [ ] Skill files exist: `.claude/skills/fuzzy-logic-engine/SKILL.md`

**Note:** This test is purely static analysis of documentation files. No Docker, API, or Python environment required.

---

## Test Data

```python
# Files to validate
TARGET_FILES = {
    "technical-indicators": ".claude/skills/technical-indicators/SKILL.md",
    "fuzzy-logic-engine": ".claude/skills/fuzzy-logic-engine/SKILL.md",
}

# Patterns that MUST exist (positive validation)
REQUIRED_PATTERNS = {
    "technical-indicators": {
        "INDICATOR_REGISTRY": "Registry-based instantiation pattern",
        "class Params": "Pydantic Params pattern for validation",
    },
    "fuzzy-logic-engine": {
        "MEMBERSHIP_REGISTRY": "Registry-based membership function pattern",
    },
}

# Patterns that MUST NOT exist (negative validation)
FORBIDDEN_PATTERNS = {
    "technical-indicators": {
        "indicator_factory": "Deprecated factory pattern (replaced by INDICATOR_REGISTRY)",
    },
    "fuzzy-logic-engine": {
        # Case-insensitive patterns
        "v2": "Deprecated v2 references (all APIs are now v3-only)",
        "V2": "Deprecated V2 references (all APIs are now v3-only)",
    },
}
```

**Why this data:**
- M4/M5 migrated indicators and fuzzy to Type Registry pattern
- `INDICATOR_REGISTRY` and `MEMBERSHIP_REGISTRY` are the new canonical APIs
- `class Params` pattern replaced manual parameter validation
- `indicator_factory` is deprecated (replaced by registry)
- All `v2` references should be removed (codebase is v3-only now)

---

## Execution Steps

### Phase 1: File Existence Validation

#### 1.1 Verify technical-indicators SKILL.md Exists

**Command:**
```bash
if [ -f ".claude/skills/technical-indicators/SKILL.md" ]; then
    echo "OK: technical-indicators SKILL.md exists"
else
    echo "FAIL: technical-indicators SKILL.md not found"
    exit 1
fi
```

**Expected:**
- Output: "OK: technical-indicators SKILL.md exists"
- Exit code: 0

#### 1.2 Verify fuzzy-logic-engine SKILL.md Exists

**Command:**
```bash
if [ -f ".claude/skills/fuzzy-logic-engine/SKILL.md" ]; then
    echo "OK: fuzzy-logic-engine SKILL.md exists"
else
    echo "FAIL: fuzzy-logic-engine SKILL.md not found"
    exit 1
fi
```

**Expected:**
- Output: "OK: fuzzy-logic-engine SKILL.md exists"
- Exit code: 0

---

### Phase 2: Technical Indicators - Required Patterns

#### 2.1 Verify INDICATOR_REGISTRY is Documented

**Command:**
```bash
if grep -q "INDICATOR_REGISTRY" ".claude/skills/technical-indicators/SKILL.md"; then
    count=$(grep -c "INDICATOR_REGISTRY" ".claude/skills/technical-indicators/SKILL.md")
    echo "OK: INDICATOR_REGISTRY mentioned $count time(s) in technical-indicators SKILL.md"
else
    echo "FAIL: INDICATOR_REGISTRY not found in technical-indicators SKILL.md"
    echo "The skill documentation must describe the registry-based instantiation pattern"
    exit 1
fi
```

**Expected:**
- Output: "OK: INDICATOR_REGISTRY mentioned N time(s) in technical-indicators SKILL.md"
- Count should be >= 1
- Exit code: 0

#### 2.2 Verify Params Pattern is Documented

**Command:**
```bash
if grep -q "class Params" ".claude/skills/technical-indicators/SKILL.md"; then
    count=$(grep -c "class Params" ".claude/skills/technical-indicators/SKILL.md")
    echo "OK: 'class Params' pattern mentioned $count time(s) in technical-indicators SKILL.md"
else
    echo "FAIL: 'class Params' pattern not found in technical-indicators SKILL.md"
    echo "The skill documentation must describe the Pydantic Params validation pattern"
    exit 1
fi
```

**Expected:**
- Output: "OK: 'class Params' pattern mentioned N time(s) in technical-indicators SKILL.md"
- Count should be >= 1 (ideally >= 2 for definition and usage example)
- Exit code: 0

---

### Phase 3: Technical Indicators - Forbidden Patterns

#### 3.1 Verify No indicator_factory References

**Command:**
```bash
if grep -q "indicator_factory" ".claude/skills/technical-indicators/SKILL.md"; then
    echo "FAIL: Found deprecated 'indicator_factory' reference in technical-indicators SKILL.md"
    echo "Occurrences:"
    grep -n "indicator_factory" ".claude/skills/technical-indicators/SKILL.md"
    echo ""
    echo "indicator_factory was replaced by INDICATOR_REGISTRY in M4"
    exit 1
else
    echo "OK: No indicator_factory references in technical-indicators SKILL.md"
fi
```

**Expected:**
- Output: "OK: No indicator_factory references in technical-indicators SKILL.md"
- Exit code: 0

---

### Phase 4: Fuzzy Logic Engine - Required Patterns

#### 4.1 Verify MEMBERSHIP_REGISTRY is Documented

**Command:**
```bash
if grep -q "MEMBERSHIP_REGISTRY" ".claude/skills/fuzzy-logic-engine/SKILL.md"; then
    count=$(grep -c "MEMBERSHIP_REGISTRY" ".claude/skills/fuzzy-logic-engine/SKILL.md")
    echo "OK: MEMBERSHIP_REGISTRY mentioned $count time(s) in fuzzy-logic-engine SKILL.md"
else
    echo "FAIL: MEMBERSHIP_REGISTRY not found in fuzzy-logic-engine SKILL.md"
    echo "The skill documentation must describe the registry-based membership function pattern"
    exit 1
fi
```

**Expected:**
- Output: "OK: MEMBERSHIP_REGISTRY mentioned N time(s) in fuzzy-logic-engine SKILL.md"
- Count should be >= 1
- Exit code: 0

---

### Phase 5: Fuzzy Logic Engine - Forbidden Patterns

#### 5.1 Verify No v2 References (Case-Insensitive)

**Command:**
```bash
# Check for v2, V2, or v2-related patterns (case-insensitive)
# Must avoid false positives like "v2.0" in version numbers or "v2ray"
# Target patterns: "v2 format", "v2 API", "V2Strategy", etc.

if grep -iE '\bv2\b' ".claude/skills/fuzzy-logic-engine/SKILL.md" | grep -ivE '(version|v2\.[0-9])' > /tmp/v2_matches.txt; then
    if [ -s /tmp/v2_matches.txt ]; then
        echo "FAIL: Found deprecated v2 references in fuzzy-logic-engine SKILL.md"
        echo "Occurrences:"
        grep -inE '\bv2\b' ".claude/skills/fuzzy-logic-engine/SKILL.md" | grep -ivE '(version|v2\.[0-9])'
        echo ""
        echo "All v2 references should be removed - codebase is v3-only"
        exit 1
    fi
fi
echo "OK: No v2 references in fuzzy-logic-engine SKILL.md"
```

**Expected:**
- Output: "OK: No v2 references in fuzzy-logic-engine SKILL.md"
- Exit code: 0

**Note:** The regex `\bv2\b` matches word boundary to avoid false positives. Additional filter excludes version strings like "v2.0".

---

### Phase 6: Comprehensive Summary

#### 6.1 Generate Validation Report

**Command:**
```bash
echo "=== M5 Documentation Validation Report ==="
echo ""

# Count all patterns
ti_registry=$(grep -c "INDICATOR_REGISTRY" ".claude/skills/technical-indicators/SKILL.md" 2>/dev/null || echo 0)
ti_params=$(grep -c "class Params" ".claude/skills/technical-indicators/SKILL.md" 2>/dev/null || echo 0)
ti_factory=$(grep -c "indicator_factory" ".claude/skills/technical-indicators/SKILL.md" 2>/dev/null || echo 0)

fl_registry=$(grep -c "MEMBERSHIP_REGISTRY" ".claude/skills/fuzzy-logic-engine/SKILL.md" 2>/dev/null || echo 0)
fl_v2=$(grep -ciE '\bv2\b' ".claude/skills/fuzzy-logic-engine/SKILL.md" 2>/dev/null || echo 0)

echo "technical-indicators/SKILL.md:"
echo "  INDICATOR_REGISTRY mentions: $ti_registry (required >= 1)"
echo "  class Params mentions: $ti_params (required >= 1)"
echo "  indicator_factory mentions: $ti_factory (required = 0)"
echo ""
echo "fuzzy-logic-engine/SKILL.md:"
echo "  MEMBERSHIP_REGISTRY mentions: $fl_registry (required >= 1)"
echo "  v2 references: $fl_v2 (required = 0)"
echo ""

# Determine pass/fail
failures=0
if [ "$ti_registry" -lt 1 ]; then failures=$((failures + 1)); fi
if [ "$ti_params" -lt 1 ]; then failures=$((failures + 1)); fi
if [ "$ti_factory" -gt 0 ]; then failures=$((failures + 1)); fi
if [ "$fl_registry" -lt 1 ]; then failures=$((failures + 1)); fi
if [ "$fl_v2" -gt 0 ]; then failures=$((failures + 1)); fi

if [ "$failures" -eq 0 ]; then
    echo "RESULT: PASS - All M5 documentation requirements met"
else
    echo "RESULT: FAIL - $failures validation(s) failed"
    exit 1
fi
```

**Expected:**
- Output includes: "RESULT: PASS - All M5 documentation requirements met"
- All counts in expected ranges
- Exit code: 0

---

## Success Criteria

All must pass for test to pass:

- [ ] `.claude/skills/technical-indicators/SKILL.md` exists
- [ ] `.claude/skills/fuzzy-logic-engine/SKILL.md` exists
- [ ] technical-indicators SKILL.md mentions `INDICATOR_REGISTRY` >= 1 time
- [ ] technical-indicators SKILL.md mentions `class Params` >= 1 time
- [ ] technical-indicators SKILL.md has zero `indicator_factory` references
- [ ] fuzzy-logic-engine SKILL.md mentions `MEMBERSHIP_REGISTRY` >= 1 time
- [ ] fuzzy-logic-engine SKILL.md has zero `v2` references (case-insensitive)

---

## Sanity Checks

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| INDICATOR_REGISTRY >= 3 | < 3 warns | May need more examples in docs |
| MEMBERSHIP_REGISTRY >= 2 | < 2 warns | May need more examples in docs |
| class Params >= 2 | < 2 warns | Should show both definition and usage |
| File size > 1KB | <= 1KB fails | Documentation is incomplete |
| No TODO markers | Any TODO warns | Incomplete documentation |

**Note:** These are advisory checks. The primary success criteria are the required/forbidden pattern counts.

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| INDICATOR_REGISTRY not found | DOCUMENTATION | Add Registry API section with examples |
| class Params not found | DOCUMENTATION | Add Params pattern explanation to "Adding New Indicator" |
| indicator_factory found | DOCUMENTATION | Replace with INDICATOR_REGISTRY.get() pattern |
| MEMBERSHIP_REGISTRY not found | DOCUMENTATION | Add Registry API section to fuzzy docs |
| v2 reference found | DOCUMENTATION | Remove or update to v3 terminology |
| File not found | CONFIGURATION | Skill file may have been moved or renamed |

---

## Troubleshooting

**If INDICATOR_REGISTRY not found:**
- The technical-indicators SKILL.md should have a "Registry API" section
- Example content:
  ```python
  from ktrdr.indicators import INDICATOR_REGISTRY

  INDICATOR_REGISTRY.list_types()           # ['adx', 'atr', ...]
  INDICATOR_REGISTRY.get('rsi')             # RSIIndicator class
  ```

**If class Params not found:**
- The "Adding a New Indicator" section should demonstrate:
  ```python
  class AwesomeIndicator(BaseIndicator):
      class Params(BaseIndicator.Params):
          period: int = Field(default=14, ge=1)
  ```

**If indicator_factory found:**
- Search for: `indicator_factory`, `IndicatorFactory`, `factory.create`
- Replace with: `INDICATOR_REGISTRY.get(type_name)` pattern
- Example replacement:
  ```python
  # OLD (deprecated)
  from ktrdr.indicators.indicator_factory import create_indicator
  indicator = create_indicator("rsi", period=14)

  # NEW (registry pattern)
  from ktrdr.indicators import INDICATOR_REGISTRY
  RSIIndicator = INDICATOR_REGISTRY.get("rsi")
  indicator = RSIIndicator(period=14)
  ```

**If MEMBERSHIP_REGISTRY not found:**
- The fuzzy-logic-engine SKILL.md should have a "Registry API" section
- Example content:
  ```python
  from ktrdr.fuzzy import MEMBERSHIP_REGISTRY

  MEMBERSHIP_REGISTRY.list_types()  # ['gaussian', 'trapezoidal', 'triangular']
  MEMBERSHIP_REGISTRY.get('triangular')  # TriangularMF class
  ```

**If v2 reference found:**
- Common v2 patterns to remove:
  - "v2 config format" -> "V3 config format" or just remove version
  - "V2Strategy" -> update to current naming
  - "legacy v2" -> remove or update context
- Context: KTRDR is now v3-only; no v2 migration guidance needed in skills

---

## Evidence to Capture

For debugging failed tests:

1. **Pattern match context:** Use `grep -B2 -A2` to show lines around matches
2. **Full file if small:** Cat the entire SKILL.md for review
3. **Word counts:** Count key terms to verify documentation completeness

Example evidence collection:
```bash
# Capture context around any failures
grep -n -B2 -A2 "indicator_factory" ".claude/skills/technical-indicators/SKILL.md" || true
grep -in -B2 -A2 "\bv2\b" ".claude/skills/fuzzy-logic-engine/SKILL.md" || true

# Capture file sizes for sanity check
wc -l ".claude/skills/technical-indicators/SKILL.md"
wc -l ".claude/skills/fuzzy-logic-engine/SKILL.md"
```

---

## Notes for Implementation

- This test requires no Python runtime - pure shell/grep commands
- Pattern matching is case-sensitive except for v2 check
- The v2 check uses word boundaries (`\b`) to avoid false positives on things like "v20" or "v2.0.1"
- File paths are relative to repository root
- Test can run in CI without Docker or any services
- Consider adding this to pre-commit hooks for documentation PRs
