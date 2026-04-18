# Earnings Play Analyzer — Implementation Overview

## Milestone Map

```
M1: Data Foundation          M2: Analysis Engine         M3: Opus Reasoning
[data models, yfinance,      [edge calc, Kelly,          [Anthropic API,
 SQLite store, basic CLI]     structures, scoring]        prompts, E2E flow]
        │                           │                           │
        └───────────┬───────────────┘                           │
                    │                                           │
                    └──────────────────┬────────────────────────┘
                                       │
                              M4: ktrdr Integration      M5: IBKR Integration
                              [signal adapter,           [live data, paper
                               directional logic]         trading, full flow]
```

## Milestone Summary

| Milestone | Goal | Key Deliverable | Estimated Tasks |
|-----------|------|-----------------|-----------------|
| **M1** | Data pipeline works end-to-end | `epa analyze AAPL` prints raw earnings data + IV stats | 7 tasks |
| **M2** | Analysis engine produces structured recommendations | Edge estimate + Kelly sizing + structure selection (no LLM) | 6 tasks |
| **M3** | Full E2E with Opus reasoning | `epa analyze AAPL` → recommendation with natural language rationale | 5 tasks |
| **M4** | ktrdr signal integration | Directional signal modifies structure selection | 4 tasks |
| **M5** | IBKR live data + paper trading | Real-time options data, paper trade placement | 5 tasks |

**Total: 27 tasks across 5 milestones**

## Dependency Graph

- M1 has no dependencies (start here)
- M2 depends on M1 (needs data models and data layer)
- M3 depends on M2 (needs analysis outputs to feed to Opus)
- M4 depends on M2 (needs structure selector to modify)
- M5 depends on M1 (needs data provider interface to implement)
- M4 and M5 can be developed in parallel after M2/M3

## Conventions

- All tasks target 1-4 hours of implementation time
- Each task specifies: files to create/modify, behavior, and tests
- Every milestone ends with a VALIDATION task that proves E2E functionality
- Tests use pytest with fixtures in `epa/tests/fixtures/`
- Code style: ruff, type hints, dataclasses
