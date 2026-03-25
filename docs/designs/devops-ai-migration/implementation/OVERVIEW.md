# Implementation Plan: ktrdr → DevOps AI Migration

## Summary

Migrate ktrdr's devops tooling to DevOps AI in 6 milestones, each dogfooding the previous. Linear dependency chain M1→M2→M3→M4, with M5 blocked on upstream devops-ai work, and M6 as final cleanup.

## Milestones

| # | Name | Phase | Tasks | Dogfoods | Key Risk |
|---|---|---|---|---|---|
| M1 | Skills Migration | Phase 1 | 4 | — | Low — mostly file ops |
| M2 | E2E Consolidation | Phase 2 | 5 | kbuild | Medium — recipe path refs |
| M3 | Shared Observability | Phase 3a | 5 | kbuild, ke2e | Medium — compose changes |
| M4 | Port Allocation | Phase 3b | 6 | kbuild, ke2e | High — port formula change |
| M5 | kinfra CLI Migration | Phase 3c | 5 | All | High — blocked on devops-ai#17 |
| M6 | Cleanup | Phase 4 | 4 | All | Low — delete dead code |

## Dependency Graph

```
M1 (Skills) ────────────────────────────── no dependencies
  │
  v
M2 (E2E) ──────────────────────────────── dogfoods kbuild from M1
  │
  v
M3 (Shared Observability) ─────────────── dogfoods kbuild + ke2e
  │
  v
M4 (Port Allocation + infra.toml) ─────── dogfoods kbuild + ke2e
  │
  ├── blocked: devops-ai#17 P1 (health cascade)
  ├── blocked: devops-ai#17 P2 (local-prod)
  v
M5 (kinfra CLI Migration) ─────────────── dogfoods all, external dep
  │
  v
M6 (Cleanup) ──────────────────────────── validates full cycle
```

## Branch Strategy

Each milestone gets its own branch from main:
- `devops-migration/M1-skills`
- `devops-migration/M2-e2e`
- `devops-migration/M3-observability`
- `devops-migration/M4-ports`
- `devops-migration/M5-kinfra`
- `devops-migration/M6-cleanup`

Each milestone is merged to main before starting the next (dogfooding constraint).

## Current State (as verified)

**Skills:** Global symlinks already exist (kbuild, kdesign, kplan, kreview, kissue, kworktree, ke2e, kinfra-onboard). Only `address-review` remains as a local old skill. No `.devops-ai/` dir. No `.claude/rules/` dir. Settings has no Skill permissions.

**E2E:** 71 recipes in `e2e-testing/tests/`, 12 in `ke2e/tests/`. Old agents are local files (not symlinks). Preflight modules only in `e2e-testing/`.

**Compose:** `docker-compose.sandbox.yml` has jaeger, prometheus, grafana services inline. 2 backtest workers + 2 training workers. No design or assessment workers.

**Infrastructure:** Embedded kinfra at `ktrdr/cli/kinfra/`. Hardcoded ports in `sandbox_ports.py`. Per-project registry at `~/.ktrdr/sandbox/instances.json`.
