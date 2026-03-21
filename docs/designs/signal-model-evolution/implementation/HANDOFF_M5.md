# Handoff — M5: Combined Validation + Experiments

## Task 5.1 Complete: Ensemble Config with TB Signal Models

**Files created:** 4 ensemble YAML configs in `configs/`

**What was done:**
- Created `ensemble_tb_regime_only.yaml` and `ensemble_tb_context_gated.yaml` (+ container variants)
- Signal models use `output_type: classification` (not regression) — context gate adjusts `confidence_threshold` which is the classification code path
- Trend signal → `models/trend_tb_gaussian_signal_v1/1h_latest` (Gaussian MFs + hybrid from M4)
- Range signal → `models/range_tb_signal_v1/1h_latest` (triangular MFs from M3, no Gaussian range strategy was created in M4)

**Gotchas:**
- M4 only created a Gaussian strategy for trend (`trend_tb_gaussian_signal_v1`), not range. Range uses `range_tb_signal_v1` with triangular MFs. This means the range model won't have hybrid encoding or dead-zone elimination — only the trend model benefits from M4 improvements.
- Context gate description notes it works with classification models (adjusts `confidence_threshold`), unlike the regression path (which uses `trade_threshold` and was the M8 bug).

**Next task notes (5.2):**
- Train using CLI: `uv run ktrdr models train trend_tb_gaussian_signal_v1.yaml EURUSD 1h --start-date 2020-01-01 --end-date 2023-12-31`
- Range model: `uv run ktrdr models train range_tb_signal_v1.yaml EURUSD 1h --start-date 2020-01-01 --end-date 2023-12-31`
- Model paths in ensemble configs expect exact directory names matching strategy names
