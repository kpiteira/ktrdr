# Strategy Grammar v3: Implementation Plan

## Prerequisite Gate

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚠️  HARD PREREQUISITE: Indicator Standardization M1-M5        │
│                                                                 │
│  DO NOT BEGIN v3 implementation until:                         │
│  • All 29 indicators implement get_output_names()              │
│  • Multi-output indicators return semantic column names        │
│  • IndicatorEngine handles prefixing                           │
│  • Integration tests pass for all indicators                   │
│                                                                 │
│  Verification: Run indicator standardization E2E test suite    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Milestone Summary

| # | Name | Tasks | E2E Test | Status |
|---|------|-------|----------|--------|
| M1 | [Config Loading](M1_config_loading.md) | 6 | `ktrdr strategy validate` works | ✅ |
| M2 | [IndicatorEngine V3](M2_indicator_engine.md) | 3 | Dict-based indicator computation | ✅ |
| M3 | [FuzzyEngine V3](M3_fuzzy_engine.md) | 3 | fuzzy_set_id-based fuzzification | ✅ |
| M4 | [Training Pipeline](M4_training_pipeline.md) | 5 | Training produces correct features | ✅ |
| M5 | [Backtest Pipeline](M5_backtest_pipeline.md) | 4 | Backtest matches training features | ✅ |
| M6 | [CLI & Migration](M6_cli_migration.md) | 4 | `ktrdr strategy migrate` works | ✅ |
| M6.5 | [Integration Wiring](M6.5_integration_wiring.md) | 4 | V3 train → backtest E2E | ⏳ |
| M7 | [Agent Integration](M7_agent_integration.md) | 3 | Agent generates valid v3 | ⏳ |
| M8 | [Cleanup](M8_cleanup.md) | 4 | No v2 remnants | ⏳ |

**Total Tasks:** ~36
**Post-work:** Indicator Standardization M6 (cleanup) after v3 complete

---

## Dependency Graph

```
[Indicator Standardization M1-M5]  ← PREREQUISITE (separate plan)
              │
              ▼
       ┌──────────────┐
       │ M1: Config   │  Load & validate v3, resolve features
       └──────┬───────┘
              │
       ┌──────▼───────┐
       │ M2: Indicator│  Dict-based IndicatorEngine
       └──────┬───────┘
              │
       ┌──────▼───────┐
       │ M3: Fuzzy    │  fuzzy_set_id-based FuzzyEngine
       └──────┬───────┘
              │
       ┌──────▼───────┐
       │ M4: Training │  TrainingPipelineV3 class (isolated)
       └──────┬───────┘
              │
       ┌──────▼───────┐
       │ M5: Backtest │  FeatureCacheV3 class (isolated)
       └──────┬───────┘
              │
       ┌──────▼───────┐
       │ M6: CLI      │  migrate, features commands
       └──────┬───────┘
              │
       ┌──────▼───────┐
       │ M6.5: Wiring │  Wire v3 into execution flows
       └──────┬───────┘
              │
       ┌──────▼───────┐
       │ M7: Agents   │  v3 strategy generation
       └──────┬───────┘
              │
       ┌──────▼───────┐
       │ M8: Cleanup  │  Migrate strategies, remove v2 code
       └──────────────┘
              │
              ▼
[Indicator Standardization M6]  ← POST-WORK (after v3 verified)
```

---

## Reference Documents

- **Design:** [DESIGN.md](../DESIGN.md)
- **Architecture:** [ARCHITECTURE.md](../ARCHITECTURE.md)
- **Validation Scenarios:** [SCENARIOS.md](../SCENARIOS.md)
- **Prerequisite:** [Indicator Standardization](../../indicator-standardization/DESIGN.md)

---

## Architecture Alignment

### Core Patterns

| Pattern | Description | Implementation |
|---------|-------------|----------------|
| **Dict-based Config** | Indicators/fuzzy_sets keyed by ID | Pydantic models with `dict[str, Definition]` |
| **FeatureResolver** | Single source of truth for features | New class, used by training + backtest |
| **Explicit nn_inputs** | No implicit feature generation | Required section, validation fails if missing |
| **Clean Interface Break** | New IndicatorEngine/FuzzyEngine APIs | Complete replacement in M2/M3 |
| **Shorthand Expansion** | `[0,20,35]` → full form at parse time | `@model_validator` in Pydantic |
| **Dot Notation** | `bbands_20_2.upper` for multi-output | Requires `get_output_names()` from indicators |
| **Caller Adds Prefixes** | Engines return unprefixed columns | Pipelines add timeframe prefix |

### Key Decisions (from Design)

1. **No v2 backward compatibility** — Migration tooling instead
2. **Feature order is deterministic** — nn_inputs × timeframes × memberships
3. **Delete nothing, migrate useful** — v2 strategies migrated for testing
4. **API endpoints unchanged** — Pass paths, not contents
5. **Agent prompts are v3-aware** — Only place needing structure knowledge

### What We Will NOT Do

- ❌ Backward compatibility with v2 format
- ❌ Implicit feature generation
- ❌ Parameters in output column names
- ❌ Per-symbol fuzzy set variations
- ❌ Dynamic/runtime fuzzy set selection

---

## Risk Areas

| Milestone | Risk | Mitigation |
|-----------|------|------------|
| M1 | Pydantic shorthand expansion complexity | Thorough unit tests for all forms |
| M2 | Interface change breaks existing code | Clean break, M8 removes old paths |
| M4 | Training feature order mismatch | FeatureResolver is single source of truth |
| M5 | Backtest/training feature misalignment | Explicit order validation, stored in metadata |
| M7 | Agent generates invalid v3 | Validator runs on all agent output |

---

## Testing Strategy

Each milestone has an E2E test that must pass before proceeding:

| Milestone | E2E Verification |
|-----------|------------------|
| M1 | `ktrdr strategy validate` shows resolved features |
| M2 | Python script computes indicators with correct column names |
| M3 | Python script applies fuzzy sets with correct naming |
| M4 | `ktrdr train --dry-run` shows correct feature list |
| M5 | Backtest produces features matching training metadata |
| M6 | `ktrdr strategy migrate` converts v2 → v3 successfully |
| M7 | Agent-generated strategy passes validation |
| M8 | `grep -r "feature_id" ktrdr/` returns only migration code |

---

## Open Questions

None currently — all design decisions resolved in DESIGN.md and SCENARIOS.md.
