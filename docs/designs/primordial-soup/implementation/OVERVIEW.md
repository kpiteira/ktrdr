# Primordial Soup: Implementation Plan

## Milestone Summary

| # | Name | Tasks | Capability |
|---|------|-------|------------|
| M1 | Single Generation | 8 | Run 1 generation, collect results, score fitness |
| M2 | Evolution Loop | 6 | Multi-generation with selection, reproduction, resume |
| M3 | Full Fitness + Reporting | 5 | Multi-slice evaluation, gates, analysis report |

**Total: 19 tasks across 3 milestones**

## Dependency Graph

```
M1 (single generation) → M2 (evolution loop) → M3 (full fitness + reporting)
```

Strictly sequential — each milestone builds on the previous.

## User Capabilities (when complete)

1. Start an evolution run: `ktrdr evolve start --population 12 --generations 5`
2. Check run status: `ktrdr evolve status`
3. Resume a crashed run: `ktrdr evolve resume <run_id>`
4. View evolution report: `ktrdr evolve report <run_id>`

## Architecture Constraints

- All pipeline interaction via HTTP (existing APIs, no modifications)
- Genome expression solely through `brief` parameter
- State in YAML files only (no database)
- Operation IDs persisted immediately after trigger (crash safety)

## Reference Documents

- Design: `docs/designs/primordial-soup/DESIGN.md`
- Architecture: `docs/designs/primordial-soup/ARCHITECTURE.md`
- Intent: `docs/designs/primordial-soup/INTENT.md`
- Prior thinking: `docs/agentic/evolution/`
