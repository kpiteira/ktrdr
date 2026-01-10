# Test: {category}/{name}

**Purpose:** [One sentence describing what this test validates]
**Duration:** [Expected time]
**Category:** [Training | Backtest | Data | Integration]

---

## Pre-Flight Checks

**Required modules:**
- [common](../preflight/common.md)
- [Add domain-specific if needed]

**Test-specific checks:**
- [ ] [Any checks unique to this test]

---

## Test Data

```json
{
  "REPLACE": "with actual request payload"
}
```

**Why this data:** [Explain parameter choices]

---

## Execution Steps

### 1. [Step Name]

**Command:**
```bash
# Command to execute
```

**Expected:**
- [What should happen]

### 2. [Next Step]
...

---

## Success Criteria

- [ ] [Observable outcome 1]
- [ ] [Observable outcome 2]

---

## Sanity Checks

**CRITICAL:** These catch false positives (e.g., 100% accuracy = model collapse)

- [ ] [Sanity check 1 with threshold]
- [ ] [Sanity check 2]

---

## Troubleshooting

**If [symptom]:**
- **Cause:** [Why this happens]
- **Cure:** [How to fix]

---

## Evidence to Capture

- Operation ID: `{operation_id}`
- Logs: `docker compose logs backend --since 5m | grep {pattern}`
- Response: [Key fields to save]
