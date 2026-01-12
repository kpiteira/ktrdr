# Pre-Flight: Data

**Used by:** Data E2E tests
**Purpose:** Verify data-specific prerequisites before test execution

---

## Checks

### 1. Data Directory Accessible

**Command:**
```bash
test -d data && test -r data && echo "OK" || echo "FAIL"
```

**Pass if:** Output is `OK`

**Fail message:** "Data directory not accessible"

---

### 2. Data Directory Mounted in Docker

**Command:**
```bash
docker compose exec backend test -d /app/data && echo "OK" || echo "FAIL"
```

**Pass if:** Output is `OK`

**Fail message:** "Data directory not mounted in Docker"

---

### 3. At Least One Data File Exists

**Command:**
```bash
ls data/*.csv data/*.pkl 2>/dev/null | head -1 && echo "OK" || echo "EMPTY"
```

**Pass if:** At least one file found

**Fail message:** "No data files in cache (tests may fail)"

---

## Quick Check Script

```bash
#!/bin/bash

echo "=== Pre-Flight: Data ==="

# Check 1: Directory exists
if ! test -d data; then
  echo "FAIL: Data directory does not exist"
  exit 1
fi
echo "OK: Data directory exists"

# Check 2: Readable
if ! test -r data; then
  echo "FAIL: Data directory not readable"
  exit 1
fi
echo "OK: Data directory readable"

# Check 3: Docker mount
if ! docker compose exec backend test -d /app/data 2>/dev/null; then
  echo "WARN: Cannot verify Docker mount (backend may not be running)"
fi

# Check 4: Has files
FILE_COUNT=$(ls data/*.csv data/*.pkl 2>/dev/null | wc -l)
if [ "$FILE_COUNT" -eq 0 ]; then
  echo "WARN: No data files in cache"
else
  echo "OK: $FILE_COUNT data files found"
fi

echo "=== Data pre-flight passed ==="
```

---

## Symptom→Cure Mappings

### Data Directory Missing

**Symptom:** "Data directory does not exist"

**Cause:** Directory not created

**Cure:**
```bash
mkdir -p data
chmod 755 data
```

**Max Retries:** 1
**Wait After Cure:** 0 seconds

---

### Directory Not Readable

**Symptom:** "Data directory not readable"

**Cause:** Permission issue

**Cure:**
```bash
chmod -R u+r data
```

**Max Retries:** 1
**Wait After Cure:** 0 seconds

---

### Docker Mount Missing

**Symptom:** "Data directory not mounted in Docker"

**Cause:** Docker compose volume not configured

**Cure:**
```bash
# Verify docker-compose.yml has data volume
grep -A5 "volumes:" docker-compose.yml | grep "data"

# Restart to apply mounts
docker compose down && docker compose up -d
```

**Max Retries:** 1
**Wait After Cure:** 15 seconds

---

### No Data Files

**Symptom:** "No data files in cache"

**Cause:** Cache is empty, need to download data

**Cure:**
```bash
# Copy from shared location if available
cp ~/.ktrdr/shared/data/*.csv data/ 2>/dev/null || echo "No shared data available"
```

**Note:** This is a warning, not a failure. Some tests may create their own data.

**Max Retries:** 0
**Wait After Cure:** 0 seconds
