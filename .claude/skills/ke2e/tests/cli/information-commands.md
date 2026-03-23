# Test: cli/information-commands

**Purpose:** Validate CLI information commands: list, show, validate, migrate
**Duration:** ~30 seconds
**Category:** CLI / Restructure

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) — Docker, sandbox, API health

**Test-specific checks:**
- [ ] At least one strategy file exists
- [ ] Some market data available (EURUSD 1d)

---

## Test Data

```yaml
symbol: EURUSD
timeframe: 1d
strategy: test_e2e_local_pull
local_strategy_path: strategies/v3_minimal.yaml
```

---

## Execution Steps

### 1. List Strategies

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

uv run ktrdr list strategies 2>&1
echo "Exit: $?"
```

**Expected:**
- Exit 0
- Table output with columns (Name, Version, Symbols, Timeframes)
- At least one strategy listed

### 2. List Strategies (JSON)

**Command:**
```bash
uv run ktrdr list strategies --json 2>&1 | head -20
```

**Expected:**
- Valid JSON array
- Parseable by jq

### 3. List Models

**Command:**
```bash
uv run ktrdr list models 2>&1
echo "Exit: $?"
```

**Expected:**
- Exit 0
- Table output (may be empty)

### 4. List Checkpoints

**Command:**
```bash
uv run ktrdr list checkpoints 2>&1
echo "Exit: $?"
```

**Expected:**
- Exit 0
- Table output (may be empty)

### 5. Show Market Data

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

uv run ktrdr show EURUSD 1d 2>&1
echo "Exit: $?"
```

**Expected:**
- Exit 0
- OHLCV table displayed
- Columns: Date, Open, High, Low, Close, Volume

### 6. Show Features

**Command:**
```bash
uv run ktrdr show features test_e2e_local_pull 2>&1
echo "Exit: $?"
```

**Expected:**
- Exit 0
- Features table displayed
- Columns: Name, Type, Parameters

### 7. Validate Strategy (API)

**Command:**
```bash
uv run ktrdr validate test_e2e_local_pull 2>&1
echo "Exit: $?"
```

**Expected:**
- Exit 0
- Message: "Strategy is valid" or similar
- Shows features count

### 8. Validate Strategy (Local)

**Command:**
```bash
uv run ktrdr validate ./strategies/v3_minimal.yaml 2>&1
echo "Exit: $?"
```

**Expected:**
- Exit 0
- Message: "Strategy is valid (v3 format)"

---

## Success Criteria

- [ ] `ktrdr list strategies` displays table
- [ ] `ktrdr list strategies --json` produces valid JSON
- [ ] `ktrdr list models` displays table (may be empty)
- [ ] `ktrdr list checkpoints` displays table (may be empty)
- [ ] `ktrdr show EURUSD 1d` displays OHLCV data
- [ ] `ktrdr show features <strategy>` displays feature list
- [ ] `ktrdr validate <name>` validates via API
- [ ] `ktrdr validate ./path` validates locally
- [ ] All commands exit 0

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Tables have headers** — Not just raw data
- [ ] **JSON parseable** — `jq` succeeds
- [ ] **At least one strategy** — List not empty
- [ ] **Data has rows** — Show returns actual OHLCV

---

## Troubleshooting

**If list returns empty:**
- **Cause:** No strategies/models deployed
- **Cure:** Deploy test strategy first

**If show returns no data:**
- **Cause:** Data not cached
- **Cure:** Run data load first or use different symbol

**If validate fails for local file:**
- **Cause:** File not found or invalid YAML
- **Cure:** Check path and file format

---

## Evidence to Capture

- List output (table format)
- List output (JSON format)
- Show data output
- Show features output
- Validate outputs
