# Forward-Return Regression: Implementation Plan

## Milestones

| Milestone | Name | Tasks | Dependencies |
|---|---|---|---|
| M1 | Regression Substrate | 8 | None |
| M2 | Assessment + Agent Integration | 6 | M1 |
| M3 | Execution Realism | 4 | M1 |

M2 and M3 are independent of each other but both require M1.

## Branch Strategy

Each milestone gets its own impl worktree:
- `impl/forward-return-M1` — Regression substrate
- `impl/forward-return-M2` — Assessment integration
- `impl/forward-return-M3` — Execution realism

## Architecture Alignment

Every task traces to these design decisions:

| Decision | What It Means for Tasks |
|---|---|
| D1: Mode flag branching | Components check `output_format` and branch. No abstract interfaces, no strategy pattern. ~10 branch points. |
| D2: Dynamic cost threshold | `threshold = round_trip_cost * min_edge_multiplier`. Comes from strategy YAML `decisions.cost_model`. |
| D3: Huber loss default | `nn.HuberLoss(delta=huber_delta)` with configurable delta. MSE available as alternative. |
| D4: No separate confidence | Regression mode: `confidence = min(abs(predicted_return) / (3 * threshold), 1.0)` for cosmetic compat only. |
| D5: Minimal gates, rich assessment | Gates: directional accuracy > 50%, net return > 0, min trades. LLM assessment does the real evaluation. |
| D6: Next-bar execution | Decisions at bar t execute at bar t+1 open. Applies to both modes. |
| D7: Classification preserved | All classification code stays. Regression is parallel path via `output_format` flag. |

## What's Ruled Out

- Abstract model interface / strategy pattern for output formats
- Separate confidence metric for regression (magnitude IS signal)
- Removing classification code
- Multi-horizon prediction (future)
- Opportunity filter / regime classifier (future phases)

## Dependency Graph

```
M1.1 ForwardReturnLabeler ─────────────────────────────────┐
M1.2 MLPTradingModel regression ──────────────────────────┐│
M1.3 ModelTrainer regression ─────────────────────────────┐││
M1.4 TrainingPipeline integration ← M1.1, M1.2, M1.3 ───┤││
M1.5 DecisionFunction regression ─────────────────────────┤││
M1.6 Strategy validation + model metadata ────────────────┤││
M1.7 Example strategy + integration test ← M1.4-M1.6 ────┤││
M1.8 E2E validation ← M1.7 ──────────────────────────────┘┘┘
                                |
                    ┌───────────┴───────────┐
                    v                       v
            M2 Assessment              M3 Execution
            M2.1-M2.6                  M3.1-M3.4
```

Tasks M1.1, M1.2, M1.3, M1.5, M1.6 can be developed in parallel. M1.4 integrates them. M1.7 tests the integration. M1.8 validates E2E.
