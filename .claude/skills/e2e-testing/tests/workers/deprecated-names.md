# Test: workers/deprecated-names

**Purpose:** Validate that deprecated environment variable names (e.g., `WORKER_PORT` instead of `KTRDR_WORKER_PORT`) still work but emit deprecation warnings in the worker logs

**Duration:** ~20 seconds

**Category:** Workers (M4 Configuration)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) - Docker, sandbox detection

**Test-specific checks:**
- [ ] Docker daemon is running
- [ ] Can run one-off containers

---

## Test Data

```json
{
  "deprecated_env_vars": [
    {"old": "WORKER_PORT", "new": "KTRDR_WORKER_PORT", "test_value": "5050"},
    {"old": "WORKER_ID", "new": "KTRDR_WORKER_ID", "test_value": "test-deprecated-worker"},
    {"old": "CHECKPOINT_EPOCH_INTERVAL", "new": "KTRDR_CHECKPOINT_EPOCH_INTERVAL", "test_value": "5"},
    {"old": "ORPHAN_TIMEOUT_SECONDS", "new": "KTRDR_ORPHAN_TIMEOUT_SECONDS", "test_value": "120"}
  ],
  "expected_warning_pattern": "deprecated"
}
```

**Why this data:**
- Tests backward compatibility with old env var names
- Verifies deprecation warnings are emitted for migration guidance
- Uses M4 worker-specific deprecated names from DEPRECATED_NAMES mapping

---

## Execution Steps

| Step | Action | Expected Result | Evidence to Capture |
|------|--------|-----------------|---------------------|
| 1 | Run worker with deprecated WORKER_PORT | Worker starts, uses value, emits warning | warning_output |
| 2 | Verify deprecated value is used | Settings reflect deprecated value | settings_value |
| 3 | Check warning message content | Warning mentions old and new name | warning_text |
| 4 | Test multiple deprecated names | All emit appropriate warnings | all_warnings |

**Detailed Steps:**

### Step 1: Run Worker with Deprecated WORKER_PORT

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# Run Python with deprecated env var name
# Note: Using WORKER_PORT (old) instead of KTRDR_WORKER_PORT (new)
OUTPUT=$(docker compose run --rm \
  -e WORKER_PORT=5050 \
  --entrypoint python \
  training-worker-1 \
  -c "
import warnings
import os

# Capture deprecation warnings
warnings.simplefilter('always', DeprecationWarning)

# Import and call the deprecation checker
from ktrdr.config.deprecation import warn_deprecated_env_vars
found = warn_deprecated_env_vars()

print(f'DEPRECATED_VARS_FOUND={found}')

# Also verify the value is used
from ktrdr.config.settings import get_worker_settings, clear_settings_cache
clear_settings_cache()
settings = get_worker_settings()
print(f'PORT_VALUE={settings.port}')
print(f'PORT_SOURCE=WORKER_PORT (deprecated)')
" 2>&1)

echo "$OUTPUT"

# Check for deprecation warning
if echo "$OUTPUT" | grep -i "deprecated" > /dev/null; then
  echo ""
  echo "PASS: Deprecation warning emitted"
else
  echo ""
  echo "FAIL: No deprecation warning found"
fi
```

**Expected:**
- Output contains deprecation warning
- `DEPRECATED_VARS_FOUND=['WORKER_PORT']`
- `PORT_VALUE=5050` (deprecated value is used)

**Capture:** Full output including warnings

### Step 2: Verify Deprecated Value Is Actually Used

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# Verify that WorkerSettings actually uses the deprecated value
docker compose run --rm \
  -e WORKER_PORT=5050 \
  -e KTRDR_WORKER_PORT= \
  --entrypoint python \
  training-worker-1 \
  -c "
import os
from ktrdr.config.settings import get_worker_settings, clear_settings_cache

# Ensure new name is not set
if 'KTRDR_WORKER_PORT' in os.environ:
    del os.environ['KTRDR_WORKER_PORT']

clear_settings_cache()
settings = get_worker_settings()

print(f'Configured port: {settings.port}')
print(f'Expected from WORKER_PORT: 5050')
print(f'Match: {settings.port == 5050}')

if settings.port == 5050:
    print('PASS: Deprecated WORKER_PORT value is used')
else:
    print('FAIL: Deprecated value not used')
"
```

**Expected:**
- Configured port is 5050
- Value from deprecated WORKER_PORT is used

**Capture:** Port value from settings

### Step 3: Check Warning Message Content

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# Check that warning message includes both old and new name
OUTPUT=$(docker compose run --rm \
  -e WORKER_PORT=5050 \
  --entrypoint python \
  training-worker-1 \
  -c "
import warnings

# Capture warnings to list
captured_warnings = []

def capture_warning(message, category, filename, lineno, file=None, line=None):
    captured_warnings.append(str(message))

old_showwarning = warnings.showwarning
warnings.showwarning = capture_warning
warnings.simplefilter('always', DeprecationWarning)

from ktrdr.config.deprecation import warn_deprecated_env_vars
warn_deprecated_env_vars()

warnings.showwarning = old_showwarning

for w in captured_warnings:
    print(f'WARNING: {w}')

    # Check content
    has_old_name = 'WORKER_PORT' in w
    has_new_name = 'KTRDR_WORKER_PORT' in w
    has_deprecated_word = 'deprecated' in w.lower()

    print(f'  - Contains old name (WORKER_PORT): {has_old_name}')
    print(f'  - Contains new name (KTRDR_WORKER_PORT): {has_new_name}')
    print(f'  - Contains deprecated keyword: {has_deprecated_word}')
" 2>&1)

echo "$OUTPUT"

# Verify warning format
if echo "$OUTPUT" | grep -E "WORKER_PORT.*KTRDR_WORKER_PORT|KTRDR_WORKER_PORT.*WORKER_PORT" > /dev/null; then
  echo ""
  echo "PASS: Warning includes both old and new names"
else
  echo ""
  echo "FAIL: Warning missing old or new name"
fi
```

**Expected:**
- Warning contains "WORKER_PORT" (old name)
- Warning contains "KTRDR_WORKER_PORT" (new name)
- Warning contains "deprecated"

**Capture:** Full warning text

### Step 4: Test Multiple Deprecated Names

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

echo "=== Testing Multiple Deprecated Env Vars ==="

# Test with multiple deprecated names at once
OUTPUT=$(docker compose run --rm \
  -e WORKER_PORT=5050 \
  -e WORKER_ID=test-deprecated-id \
  -e CHECKPOINT_EPOCH_INTERVAL=5 \
  -e ORPHAN_TIMEOUT_SECONDS=120 \
  --entrypoint python \
  training-worker-1 \
  -c "
import warnings
warnings.simplefilter('always', DeprecationWarning)

from ktrdr.config.deprecation import warn_deprecated_env_vars
found = warn_deprecated_env_vars()

print(f'Found deprecated vars: {len(found)}')
for var in found:
    print(f'  - {var}')

# Verify each is in the found list
expected = ['WORKER_PORT', 'WORKER_ID', 'CHECKPOINT_EPOCH_INTERVAL', 'ORPHAN_TIMEOUT_SECONDS']
missing = [v for v in expected if v not in found]
extra = [v for v in found if v not in expected]

print(f'Expected: {expected}')
print(f'Missing: {missing}')
print(f'Extra: {extra}')

if not missing:
    print('PASS: All deprecated vars detected')
else:
    print(f'FAIL: Missing detection for: {missing}')
" 2>&1)

echo "$OUTPUT"
```

**Expected:**
- All 4 deprecated variables are detected
- Each emits a separate warning
- No missing or unexpected detections

**Capture:** List of all detected deprecated vars

### Step 5: Verify New Name Takes Precedence

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# When both old and new names are set, new name should take precedence
docker compose run --rm \
  -e WORKER_PORT=5050 \
  -e KTRDR_WORKER_PORT=5060 \
  --entrypoint python \
  training-worker-1 \
  -c "
from ktrdr.config.settings import get_worker_settings, clear_settings_cache

clear_settings_cache()
settings = get_worker_settings()

print(f'Port value: {settings.port}')
print(f'WORKER_PORT (deprecated): 5050')
print(f'KTRDR_WORKER_PORT (preferred): 5060')

if settings.port == 5060:
    print('PASS: New name takes precedence over deprecated name')
elif settings.port == 5050:
    print('FAIL: Deprecated name incorrectly takes precedence')
else:
    print(f'FAIL: Unexpected port value: {settings.port}')
"
```

**Expected:**
- Port value is 5060 (from KTRDR_WORKER_PORT)
- New name takes precedence over deprecated name

**Capture:** Port value when both names are set

---

## Success Criteria

All must pass for test to pass:

- [ ] WORKER_PORT (deprecated) is detected by warn_deprecated_env_vars()
- [ ] Deprecation warning is emitted for WORKER_PORT
- [ ] Warning message contains both old (WORKER_PORT) and new (KTRDR_WORKER_PORT) names
- [ ] Deprecated value (5050) is actually used by WorkerSettings
- [ ] Multiple deprecated vars are all detected (WORKER_ID, CHECKPOINT_*, etc.)
- [ ] When both names set, new name takes precedence over deprecated

---

## Sanity Checks

Catch false positives:

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Warning emitted | No warning fails | warn_deprecated_env_vars() not being called |
| Value used | Wrong value fails | AliasChoices not configured correctly |
| Both names in warning | Missing name fails | Warning message format incorrect |
| Precedence correct | Old takes precedence fails | AliasChoices order wrong |

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| No warning emitted | CODE_BUG | Check warn_deprecated_env_vars() is called in worker startup |
| Deprecated name not in DEPRECATED_NAMES | CODE_BUG | Add mapping to ktrdr/config/deprecation.py |
| Value not used | CODE_BUG | Check deprecated_field() in WorkerSettings uses AliasChoices |
| Wrong precedence | CODE_BUG | Verify AliasChoices has new name first: `AliasChoices(new, old)` |

---

## Cleanup

None required - test uses `--rm` flag for one-off containers.

---

## Troubleshooting

**If no deprecation warning:**
- **Cause:** warn_deprecated_env_vars() not called
- **Check:** Worker startup code calls warn_deprecated_env_vars() before validate_all()
- **File:** `ktrdr/backtesting/backtest_worker.py` line 39

**If deprecated value not used:**
- **Cause:** AliasChoices not configured in deprecated_field()
- **Check:** WorkerSettings.port uses deprecated_field() with correct params
- **File:** `ktrdr/config/settings.py` WorkerSettings class

**If wrong precedence:**
- **Cause:** AliasChoices has old name first instead of new name
- **Check:** deprecated_field() puts new name before old: `AliasChoices(new_env, old_env)`
- **Fix:** Ensure field is `deprecated_field(default, "KTRDR_*", "OLD_NAME", ...)`

---

## Evidence to Capture

- Deprecation warning output
- List of deprecated vars found
- Settings value using deprecated name
- Warning message text with both names
- Precedence test result

---

## Notes

**DEPRECATED_NAMES Mapping (M4):**
```python
DEPRECATED_NAMES = {
    # M4: Worker settings
    "WORKER_ID": "KTRDR_WORKER_ID",
    "WORKER_PORT": "KTRDR_WORKER_PORT",
    "WORKER_ENDPOINT_URL": "KTRDR_WORKER_ENDPOINT_URL",
    "WORKER_PUBLIC_BASE_URL": "KTRDR_WORKER_PUBLIC_BASE_URL",
    # M4: Checkpoint settings
    "CHECKPOINT_EPOCH_INTERVAL": "KTRDR_CHECKPOINT_EPOCH_INTERVAL",
    "CHECKPOINT_TIME_INTERVAL_SECONDS": "KTRDR_CHECKPOINT_TIME_INTERVAL_SECONDS",
    "CHECKPOINT_DIR": "KTRDR_CHECKPOINT_DIR",
    "CHECKPOINT_MAX_AGE_DAYS": "KTRDR_CHECKPOINT_MAX_AGE_DAYS",
    # M4: Orphan detector settings
    "ORPHAN_TIMEOUT_SECONDS": "KTRDR_ORPHAN_TIMEOUT_SECONDS",
    "ORPHAN_CHECK_INTERVAL_SECONDS": "KTRDR_ORPHAN_CHECK_INTERVAL_SECONDS",
    # M4: Operations settings
    "OPERATIONS_CACHE_TTL": "KTRDR_OPS_CACHE_TTL",
}
```

**deprecated_field() Helper:**
```python
def deprecated_field(default, new_env, old_env, **kwargs):
    """New name takes precedence (listed first in AliasChoices)."""
    return Field(
        default=default,
        validation_alias=AliasChoices(new_env, old_env),  # new first!
        **kwargs,
    )
```

**Warning Message Format:**
```
DeprecationWarning: Environment variable 'WORKER_PORT' is deprecated. Use 'KTRDR_WORKER_PORT' instead.
```
