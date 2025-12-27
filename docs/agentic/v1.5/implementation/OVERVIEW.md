# v1.5 Implementation Plan: Prove the NN Can Learn

## Goal

Determine if the neuro-fuzzy architecture can learn anything at all when mechanical errors (wrong fuzzy ranges) are eliminated.

**Success Criteria:** >30% of strategies achieve >55% validation accuracy = NN works

## Milestone Summary

| # | Name | Tasks | E2E Test | Status |
|---|------|-------|----------|--------|
| M1 | Validate Analytics & Diagnostics | 6 | Training produces readable analytics | ⏳ |
| M2 | Create Experimental Strategies | 4 | 27 validated strategy files | ⏳ |
| M3 | Run Experiments | 3 | All strategies trained with results | ⏳ |
| M4 | Analyze and Conclude | 3 | Summary report with conclusion | ⏳ |

## Dependency Graph

```
M1 (Validate Analytics)
    │
    ▼
M2 (Create Strategies)
    │
    ▼
M3 (Run Experiments)
    │
    ▼
M4 (Analyze & Conclude)
```

All milestones are sequential. Each depends on the previous.

## Reference Documents

- **Design:** [../DESIGN.md](../DESIGN.md) — Problem statement, indicator classification, success criteria
- **Plan:** [../PLAN.md](../PLAN.md) — Strategy matrix, training configuration
- **Architecture:** [../ARCHITECTURE.md](../ARCHITECTURE.md) — Superseded, but fuzzy set references remain valid

## Key Context

### This is an Experiment, Not a Feature

We're not building new infrastructure. We're:
1. Creating YAML strategy files with correct configurations
2. Running existing training via API
3. Reading existing TrainingAnalyzer output
4. Producing a summary report

### The Core Question

> "Can the neuro-fuzzy architecture learn predictive patterns from bounded indicators when fuzzy ranges are correct?"

### Why This Matters

Previous strategies failed because of mechanical errors (wrong fuzzy ranges). Before building learning systems (v2), we must know if the architecture can learn at all when given correct inputs.

## Risk Mitigation

| Risk | Mitigation | Milestone |
|------|------------|-----------|
| Training/NN not working | Validate analytics output in M1 | M1 |
| Indicators not working | Check feature variance in M1.6 | M1 |
| Fuzzy sets not working | Verify transforms produce non-zero values | M1 |
| Labeling not working | Check label distribution (~50/1/49) | M1 |
| 3-state not useful | If all fail, becomes hypothesis in M4 | M4 |

## Estimated Timeline

- **M1:** 2-4 hours (includes potential debugging)
- **M2:** 2-3 hours (strategy creation + validation)
- **M3:** 4-8 hours (mostly training runtime)
- **M4:** 1-2 hours (analysis + report)

**Total:** ~1-2 days (mostly waiting for training)

---

*Created: December 2025*
*Approach: Lean experimentation over infrastructure*
