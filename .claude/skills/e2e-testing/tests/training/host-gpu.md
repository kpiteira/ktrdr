# Test: training/host-gpu

**Purpose:** Verify GPU allocation in training responses
**Duration:** ~3 seconds
**Category:** Training (Host Service)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] Training host service running (port 5002)
- [ ] Run host-start test first (creates session data)

---

## Test Data

Uses session from host-start test (2.1).

---

## Execution Steps

### 1. Start Training and Check Start Response

**Command:**
```bash
STRATEGY_YAML=$(cat ~/.ktrdr/shared/strategies/test_e2e_local_pull.yaml)

RESPONSE=$(curl -s -X POST http://localhost:5002/training/start \
  -H "Content-Type: application/json" \
  -d "{
    \"strategy_yaml\": $(echo "$STRATEGY_YAML" | jq -Rs .),
    \"symbols\": [\"EURUSD\"],
    \"timeframes\": [\"1d\"],
    \"start_date\": \"2024-01-01\",
    \"end_date\": \"2024-12-31\"
  }")

echo "$RESPONSE" | jq '{gpu_allocated}'
SESSION_ID=$(echo "$RESPONSE" | jq -r '.session_id')
```

**Expected:**
- `gpu_allocated: true` (or false if no GPU)

### 2. Check GPU Usage in Status

**Command:**
```bash
sleep 3
curl -s "http://localhost:5002/training/status/$SESSION_ID" | jq '.gpu_usage'
```

**Expected:**
- `gpu_usage` object with memory info (if GPU allocated)
- Object present even if GPU not used

---

## Success Criteria

- [ ] Start response includes `gpu_allocated` field
- [ ] Status response includes `gpu_usage` object
- [ ] GPU properly allocated when available
- [ ] Graceful fallback when GPU unavailable

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Field present** — `gpu_allocated` is boolean (not null)
- [ ] **Consistent** — If `gpu_allocated: true`, then `gpu_usage` has details

---

## Troubleshooting

**If gpu_allocated is null:**
- **Cause:** Response schema changed
- **Cure:** Check host service API documentation

**If gpu_allocated: false unexpectedly:**
- **Cause:** No GPU available or CUDA not configured
- **Note:** This is not a failure — CPU fallback is expected behavior

---

## Evidence to Capture

- Start response: `{gpu_allocated: bool}`
- GPU usage: `{gpu_usage: {...}}`
- Host logs: GPU allocation messages
