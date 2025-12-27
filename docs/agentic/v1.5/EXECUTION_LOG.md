# v1.5 Experiment Execution Log

**Started:** [Not yet started]
**Last Updated:** [Auto-update on each run]

---

## Status Summary

| Status | Count |
|--------|-------|
| Completed | 0 |
| Running | 0 |
| Failed | 0 |
| Pending | 27 |

---

## Execution Log

### Single Indicator Strategies (9)

| Strategy | Started | Operation ID | Status | Duration | Notes |
|----------|---------|--------------|--------|----------|-------|
| v15_rsi_only | - | - | pending | - | - |
| v15_stochastic_only | - | - | pending | - | - |
| v15_williams_only | - | - | pending | - | - |
| v15_mfi_only | - | - | pending | - | - |
| v15_adx_only | - | - | pending | - | - |
| v15_aroon_only | - | - | pending | - | - |
| v15_cmf_only | - | - | pending | - | - |
| v15_rvi_only | - | - | pending | - | - |
| v15_di_only | - | - | pending | - | - |

### Two Indicator Combinations (11)

| Strategy | Started | Operation ID | Status | Duration | Notes |
|----------|---------|--------------|--------|----------|-------|
| v15_rsi_adx | - | - | pending | - | - |
| v15_rsi_stochastic | - | - | pending | - | - |
| v15_rsi_williams | - | - | pending | - | - |
| v15_rsi_mfi | - | - | pending | - | - |
| v15_rsi_cmf | - | - | pending | - | - |
| v15_adx_aroon | - | - | pending | - | - |
| v15_adx_di | - | - | pending | - | - |
| v15_adx_rsi | - | - | pending | - | - |
| v15_stochastic_williams | - | - | pending | - | - |
| v15_mfi_cmf | - | - | pending | - | - |
| v15_aroon_rvi | - | - | pending | - | - |

### Three Indicator Combinations (3)

| Strategy | Started | Operation ID | Status | Duration | Notes |
|----------|---------|--------------|--------|----------|-------|
| v15_rsi_adx_stochastic | - | - | pending | - | - |
| v15_mfi_adx_aroon | - | - | pending | - | - |
| v15_williams_stochastic_cmf | - | - | pending | - | - |

### Zigzag Threshold Variations (4)

| Strategy | Started | Operation ID | Status | Duration | Notes |
|----------|---------|--------------|--------|----------|-------|
| v15_rsi_zigzag_1.5 | - | - | pending | - | - |
| v15_rsi_zigzag_2.0 | - | - | pending | - | - |
| v15_rsi_zigzag_3.0 | - | - | pending | - | - |
| v15_rsi_zigzag_3.5 | - | - | pending | - | - |

---

## Failures (if any)

_No failures recorded yet._

<!--
Template for recording failures:

### [Strategy Name]
- **Error:** [error message]
- **Logs:** [relevant log snippet]
- **Action:** [retry / skip / investigate]
- **Resolution:** [what was done]
-->

---

## Execution Notes

### Prerequisites Verified
- [ ] Strategies copied to ktrdr2: `cp strategies/v15_*.yaml ../ktrdr2/strategies/`
- [ ] Docker environment running: `docker compose up -d`
- [ ] Backend healthy: `curl http://localhost:8000/api/v1/health`

### Training Configuration
| Parameter | Value |
|-----------|-------|
| Symbol | EURUSD |
| Timeframe | 1h |
| Date range | 2015-01-01 to 2023-12-31 |
| Split | 70% train / 15% val / 15% test |
| Epochs | 100 (early stopping, patience 15) |
| Analytics | Enabled |

---

## Post-Execution Summary

_To be filled after all experiments complete._

| Metric | Value |
|--------|-------|
| Total Strategies | 27 |
| Completed | - |
| Failed | - |
| Completion Rate | - |
| Total Runtime | - |
| Average Runtime | - |
