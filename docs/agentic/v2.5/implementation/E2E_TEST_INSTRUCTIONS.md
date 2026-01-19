# E2E Test Instructions: Multi-Symbol and Multi-Timeframe Validation

**Created:** 2026-01-19
**Purpose:** Validate that v3 grammar works for multi-symbol and multi-timeframe strategies
**Context:** This is the core validation for M4/M5 of v2.5 agentic work

## Background

The v3 strategy grammar and indicator standardization work is complete. We need to validate:
1. **Multi-timeframe** (H_001 hypothesis) - Different fuzzy interpretations per timeframe
2. **Multi-symbol** (H_004 hypothesis) - Training across multiple symbols
3. **Both combined** - Multi-symbol + multi-timeframe

## Prerequisites

- Sandbox running on port 8001 (`uv run ktrdr sandbox status`)
- Set env var: `export KTRDR_API_CLIENT_BASE_URL="http://localhost:8001/api/v1"`
- Data available for test symbols (EURUSD, GBPUSD at minimum)

## Test Approach

Use the proper E2E test infrastructure:
1. **e2e-test-designer** agent to find existing test specifications in the catalog
2. **e2e-test-architect** agent if new tests need to be designed
3. **e2e-tester** agent to execute tests

**IMPORTANT:** If e2e-test-architect creates new tests, they MUST be added to the standard test catalog so e2e-test-designer can find them in future sessions.

Do NOT write ad-hoc Python scripts.

## Test Cases Needed

### Test 1: Multi-Timeframe Strategy (H_001)

**Goal:** Validate that a strategy with multiple timeframes (e.g., 1h + 4h) can:
- Train successfully with v3 grammar
- Create metadata_v3.json with correct resolved_features
- Backtest without feature mismatch errors

**Strategy should have:**
- Single symbol (EURUSD)
- Multiple timeframes (1h, 4h)
- Same indicator (RSI) with different fuzzy interpretations per timeframe
- nn_inputs specifying which fuzzy_set applies to which timeframe

### Test 2: Multi-Symbol Strategy (H_004)

**Goal:** Validate that a strategy with multiple symbols can:
- Train successfully combining data from all symbols
- Create valid model
- Backtest on individual symbols

**Strategy should have:**
- Multiple symbols (EURUSD, GBPUSD)
- Single timeframe (1h)
- Same indicators and fuzzy sets applied to all

### Test 3: Combined Multi-Symbol + Multi-Timeframe

**Goal:** The full test - validate both dimensions work together

**Strategy should have:**
- Multiple symbols (EURUSD, GBPUSD)
- Multiple timeframes (1h, 4h)
- Different fuzzy interpretations per timeframe

## Success Criteria

For each test:
- [ ] Strategy validates as v3 format
- [ ] Training completes without errors
- [ ] `metadata_v3.json` created with correct `resolved_features`
- [ ] Features have correct prefixes (e.g., `1h_rsi_fast_oversold`, `4h_rsi_slow_oversold`)
- [ ] Backtest completes without "feature mismatch" errors
- [ ] No column collision errors

## Known Issues (Work Around)

1. **CLI sandbox detection bug** (Issue #252): Use `export KTRDR_API_CLIENT_BASE_URL="http://localhost:8001/api/v1"`
2. **Agent token consumption** (Issue #253): Don't use agent-driven research for now; use direct CLI commands

## How to Run

```bash
# Use e2e-test-designer to find appropriate tests
# Then use e2e-tester to execute

# If tests don't exist, use e2e-test-architect to design them

# For manual validation (if needed):
uv run ktrdr validate <strategy.yaml>
uv run ktrdr train <strategy> --start 2024-01-01 --end 2024-06-01 --follow
uv run ktrdr backtest <strategy> --start 2024-06-01 --end 2024-07-01 --follow
```

## Related Documents

- Validation Plan: `docs/agentic/v2.5/implementation/VALIDATION_PLAN_v3_ready.md`
- Strategy Grammar v3 Design: `docs/designs/strategy-grammar-v3/DESIGN.md`
- v2.5 Agentic Design: `docs/agentic/v2.5/DESIGN.md`

## GitHub Issues

- #252: CLI sandbox auto-detection broken
- #253: Agent token consumption due to missing v3 prompt example
