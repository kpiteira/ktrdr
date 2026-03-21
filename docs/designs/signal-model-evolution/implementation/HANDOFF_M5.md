# Handoff — M5: Combined Validation + Experiments

## Task 5.1 Complete: Ensemble Config with TB Signal Models

**Files created:** 4 ensemble YAML configs in `configs/`

**What was done:**
- Created `ensemble_tb_regime_only.yaml` and `ensemble_tb_context_gated.yaml` (+ container variants)
- Signal models use `output_type: classification` (not regression) — context gate adjusts `confidence_threshold` which is the classification code path
- Trend signal → `models/trend_tb_gaussian_signal_v1/5m_latest` (Gaussian MFs + hybrid from M4)
- Range signal → `models/range_tb_signal_v1/1h_latest` (triangular MFs from M3)

**Gotchas:**
- M4 only created a Gaussian strategy for trend (`trend_tb_gaussian_signal_v1`), not range. Range uses `range_tb_signal_v1` with triangular MFs. This means the range model won't have hybrid encoding or dead-zone elimination — only the trend model benefits from M4 improvements.
- Context gate description notes it works with classification models (adjusts `confidence_threshold`), unlike the regression path (which uses `trade_threshold` and was the M8 bug).

**Next task notes (5.2):**
- Train using CLI: `uv run ktrdr models train trend_tb_gaussian_signal_v1.yaml EURUSD 1h --start-date 2020-01-01 --end-date 2023-12-31`
- Range model: `uv run ktrdr models train range_tb_signal_v1.yaml EURUSD 1h --start-date 2020-01-01 --end-date 2023-12-31`
- Model paths in ensemble configs expect exact directory names matching strategy names

## Task 5.2 Complete: Train Signal Models with Full Pipeline

**Training results:**
- Trend (Gaussian+hybrid): 100 epochs, val accuracy 55.1%, val loss 0.807, saved `5m_latest`
- Range (triangular): 200 epochs, val accuracy 52.4%, val loss 0.180, saved `1h_latest`
- Neither triggered early stopping

**Gotchas:**
- Multi-TF strategies (trend) save under `5m_latest` not `1h_latest` — updated ensemble configs
- Strategies must be in `~/.ktrdr/shared/strategies/` for sandbox containers to find them
- Sandbox slot 3 used (slot 1 had port conflicts with prod agents on 5010/5020)
- Alembic migrations don't auto-run on fresh sandbox — must `docker exec <backend> alembic upgrade head`
- `.env.sandbox` needs `KTRDR_JAEGER_OTLP_GRPC_PORT` (compose var name) in addition to `KTRDR_OTLP_GRPC_PORT` (sandbox_ports var name)

**Next task notes (5.3):**
- Sandbox on slot 3, port 8003 — already running with trained models
- Existing regression models: `models/trend_regression_signal/1h_latest`, `models/range_regression_signal/1h_latest`
- Run ensemble backtests via CLI: `uv run ktrdr backtest run <ensemble_config> EURUSD 1h --start 2024-01-01 --end 2024-12-31`
