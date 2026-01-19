# Validation Plan: Agent Research Cycle with v3 Grammar

**Date:** 2026-01-18
**Status:** Ready for execution
**Context:** All foundational work complete (v3 grammar, indicator standardization, M6.5 wiring)

---

## Purpose

Validate that the full agent research cycle works end-to-end with the v3 strategy grammar. This is the final validation before closing out the v2.5/v3 work streams.

---

## Prerequisites Verified

| Component | Status | Evidence |
|-----------|--------|----------|
| Test collection | ✅ Fixed | 5100 tests collected, 0 errors |
| Strategy validation | ✅ Working | `ktrdr validate` detects v3 format |
| V3 training | ✅ Working | Creates `metadata_v3.json` |
| V3 backtest | ✅ Working | No feature mismatch errors |
| Agent prompts | ✅ Updated | Contains v3 structure, `nn_inputs`, no `feature_id` |
| Agent utilities | ✅ Updated | Uses `StrategyConfigurationV3` |
| Brief mechanism | ✅ Working | Flows to design worker per M3 handoff |

---

## Validation Phases

### Phase 1: Agent Strategy Generation (Isolated)

**Goal:** Verify agent generates valid v3 strategies.

**Test:**
```bash
# Trigger research with a simple brief
uv run ktrdr research "Design a simple RSI-based momentum strategy for EURUSD on 1h timeframe. Use single symbol, single timeframe, single indicator. This is a validation run." --model haiku --follow
```

**Success Criteria:**
- [ ] Agent generates YAML with `indicators` dict (not list)
- [ ] Agent includes `nn_inputs` section
- [ ] Agent does NOT use `feature_id` terminology
- [ ] Generated strategy passes `ktrdr validate`

**Verification:**
```bash
# After research completes, check the generated strategy
cat ~/.ktrdr/shared/strategies/[generated_strategy_name].yaml | grep -E "nn_inputs|indicators:|fuzzy_sets:"
```

---

### Phase 2: Full Research Cycle (Integration)

**Goal:** Verify complete design → training → backtest → assessment flow.

**Test:**
```bash
# Trigger research and follow through all phases
uv run ktrdr research "Design a simple RSI-based strategy for EURUSD 1h. Use a single indicator with 3 fuzzy membership functions (oversold, neutral, overbought). This is an E2E validation." --model haiku --follow
```

**Success Criteria:**
- [ ] Design phase completes (valid v3 strategy created)
- [ ] Training phase starts and completes
- [ ] Training creates `metadata_v3.json` in model directory
- [ ] Training gate passes (Baby mode: accuracy > 10%)
- [ ] Backtest phase starts and completes
- [ ] No "feature mismatch" errors in backtest
- [ ] Assessment phase completes
- [ ] Experiment recorded in database

**Verification:**
```bash
# Check operation status
uv run ktrdr ops

# Check experiment was recorded
curl -s "http://localhost:8001/api/v1/experiments" | python3 -m json.tool | head -50
```

---

### Phase 3: Multi-Timeframe Validation (H_001)

**Goal:** Verify multi-timeframe strategies work with v3 grammar.

**Test:**
```bash
uv run ktrdr research "Design a multi-timeframe RSI strategy for EURUSD using 1h and 4h timeframes. Use different fuzzy interpretations for each timeframe (rsi_fast for 1h, rsi_slow for 4h). This tests hypothesis H_001." --model haiku --follow
```

**Success Criteria:**
- [ ] Strategy correctly defines `nn_inputs` with timeframe-specific fuzzy sets
- [ ] Training produces features with timeframe prefixes (e.g., `1h_rsi_fast_oversold`)
- [ ] Backtest uses correct feature order from `resolved_features`
- [ ] No column collision errors

**Verification:**
```bash
# Check model metadata
MODEL_PATH=$(ls -td ~/.ktrdr/shared/models/*/1h_* | head -1)
cat "$MODEL_PATH/metadata_v3.json" | python3 -m json.tool | grep -A 20 "resolved_features"
```

---

### Phase 4: Multi-Symbol Validation (H_004)

**Goal:** Verify multi-symbol strategies work with v3 grammar.

**Test:**
```bash
uv run ktrdr research "Design a multi-symbol RSI strategy for EURUSD, GBPUSD, and USDJPY on 1h timeframe. Use the same fuzzy interpretation across all symbols. This tests hypothesis H_004." --model haiku --follow
```

**Success Criteria:**
- [ ] Strategy correctly defines symbols in `training_data`
- [ ] Training combines data from all symbols
- [ ] Training produces valid model
- [ ] Backtest runs without errors

---

### Phase 5: Gate Validation (Baby Mode)

**Goal:** Verify quality gates are working in Baby mode.

**Sub-test 5a: Catastrophic Failure Detection**
```bash
# This should fail at training gate (0% accuracy = catastrophic)
# No direct test possible without forcing a failure, but check gate config:
uv run python -c "
from ktrdr.agents.gates import GateConfig
config = GateConfig()
print(f'Baby mode thresholds:')
print(f'  min_accuracy: {config.min_accuracy} (should be 0.10)')
print(f'  min_loss_decrease: {config.min_loss_decrease} (should be -0.50)')
print(f'  min_win_rate: {config.min_win_rate} (should be 0.10)')
"
```

**Success Criteria:**
- [ ] `min_accuracy` is 0.10 (Baby mode)
- [ ] `min_loss_decrease` is -0.50 (allows exploration)
- [ ] `min_win_rate` is 0.10 (only catches catastrophic)

---

## Execution Summary

| Phase | Test | Expected Duration | Status |
|-------|------|-------------------|--------|
| 1 | Agent v3 generation | 1-2 minutes | ⬜ Pending |
| 2 | Full research cycle | 5-10 minutes | ⬜ Pending |
| 3 | Multi-timeframe (H_001) | 5-10 minutes | ⬜ Pending |
| 4 | Multi-symbol (H_004) | 5-10 minutes | ⬜ Pending |
| 5 | Gate configuration | 30 seconds | ⬜ Pending |

---

## Failure Recovery

If any phase fails:

1. **Check operation status:**
   ```bash
   uv run ktrdr ops
   curl -s "http://localhost:8001/api/v1/operations/[OP_ID]" | python3 -m json.tool
   ```

2. **Check Jaeger traces:**
   ```bash
   open http://localhost:16687
   # Search for operation ID or "research" service
   ```

3. **Check worker logs:**
   ```bash
   docker compose logs -f training-worker-1 2>&1 | grep -i "error\|warning"
   ```

4. **Common issues:**
   - "feature mismatch" → Check `metadata_v3.json` vs backtest feature generation
   - "0 trades" → Check confidence threshold, may need more training epochs
   - "gate failed" → Check thresholds match Baby mode

---

## Post-Validation

After all phases pass:

1. **Update documentation:**
   - Mark M6.5, M7, M8 as complete in OVERVIEW.md
   - Update v2.5 status

2. **Clean up:**
   - Delete test strategies created during validation
   - Remove `/tmp/v3_e2e_test.yaml`

3. **Next steps:**
   - Consider designing v3 Agentic System (maturity progression, automated gate tightening)
   - Run longer research cycles to gather experiment data

---

*Created: 2026-01-18*
*Last Updated: 2026-01-18*
