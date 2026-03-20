---
design: docs/designs/signal-model-evolution/DESIGN.md
---

# Signal Model Evolution — Implementation Plan

## Design Reference
- **Design:** `docs/designs/signal-model-evolution/DESIGN.md`
- **Branch:** `impl/signal-model-evolution` (create from `main`)

## Milestone Summary

| Milestone | Name | Tasks | Phase | Dependencies | JTBD |
|-----------|------|-------|-------|-------------|------|
| M1 | Triple Barrier Labeler | 5 | Phase 1 (Layer 1) | None | Train signal models on trade-outcome labels instead of noisy forward returns |
| M2 | Training Pipeline Upgrades | 5 | Phase 1 (Layer 3) | None | Train models that generalize instead of collapsing to predict the mean |
| M3 | Phase 1 Integration + Validation | 5 | Phase 1 | M1, M2 | Run a signal model trained with TB labels through the ensemble backtest and measure if it beats the forward-return baseline |
| M4 | Gaussian MFs + Hybrid Encoding | 5 | Phase 2 (Layer 2) | None | Eliminate dead-zone features so models receive non-zero input on every bar |
| M5 | Combined Validation + Experiments | 4 | Phase 1+2 | M3, M4 | Run the full evolved pipeline (TB + Gaussian + upgraded training) end-to-end and measure whether all three fixes compound into >55% accuracy and Sharpe >0.3 |
| M6 | Meta-Labeling Enhancement | 5 | Phase 3 | M5 (conditional) | Filter low-confidence trades and size positions by probability to improve Sharpe without increasing trade count |
| M7 | Learnable MFs / ANFIS | 5 | Phase 4 | M5 (conditional) | Let the model discover optimal market-structure boundaries instead of relying on expert-defined MF parameters |

**Total:** 34 tasks across 7 milestones

## Dependency Graph

```
M1 (TB Labeler)          M2 (Training Pipeline)     M4 (Gaussian MFs + Hybrid)
     │                         │                          │
     └────────┬────────────────┘                          │
              │                                           │
         M3 (Phase 1 Integration)                         │
              │                                           │
              └──────────────┬────────────────────────────┘
                             │
                    M5 (Combined Validation + Experiments)
                             │
              ┌──────────────┴──────────────┐
              │                             │
     M6 (Meta-Labeling)           M7 (ANFIS / Learnable MFs)
     (optional — if M5             (optional — if M5
      shows >55% accuracy)          shows feature impact)
```

**Parallelism:** M1, M2, and M4 are fully independent — can be worked simultaneously.

## Branch Strategy

Each milestone gets its own branch from `main`:
- M1: `impl/sme-M1-triple-barrier`
- M2: `impl/sme-M2-training-pipeline`
- M3: `impl/sme-M3-phase1-integration` (after M1+M2 merged)
- M4: `impl/sme-M4-gaussian-hybrid`
- M5: `impl/sme-M5-combined-validation` (after M3+M4 merged)
- M6: `impl/sme-M6-meta-labeling`
- M7: `impl/sme-M7-anfis`

## Go/No-Go Gates

**After M5 (Combined Validation):**
- If signal model val accuracy > 55% with TB labels + Gaussian MFs → proceed to M6/M7
- If val accuracy 50-55% → investigate further before M6/M7
- If val accuracy ~50% → pivot: different features, different model architecture, or tree-based approach

**After M6 (Meta-Labeling):**
- If meta-labeler improves Sharpe vs signal-model-only → keep both
- If meta-labeler adds no value → signal model alone is sufficient

## Key Files (Cross-Milestone Reference)

### New Files
- `ktrdr/training/triple_barrier_labeler.py` — M1
- `ktrdr/training/cusum_filter.py` — M1
- `ktrdr/training/sample_weights.py` — M1
- `ktrdr/neural/losses.py` — M2
- `ktrdr/backtesting/meta_labeler.py` — M6
- `ktrdr/backtesting/position_sizer.py` — M6
- `ktrdr/neural/layers/learnable_fuzzy.py` — M7

### Modified Files
- `ktrdr/neural/models/mlp.py` — M2 (mini-batch, early stopping, LR scheduling)
- `ktrdr/training/training_pipeline.py` — M1 (add TB branch), M2 (label purging)
- `ktrdr/config/models.py` — M4 (NNInputSpec for raw_indicator)
- `ktrdr/config/feature_resolver.py` — M4 (resolve raw indicators)
- `ktrdr/training/fuzzy_neural_processor.py` — M4 (hybrid encoding)
- `ktrdr/backtesting/ensemble_runner.py` — M6 (meta-label integration)
