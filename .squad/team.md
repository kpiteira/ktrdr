# Research Squad

A collaborative multi-agent team for trading architecture discovery. Each agent brings a distinct perspective; the Coordinator orchestrates their interaction. The squad compounds knowledge across experiments — experiment #100 should leverage synthesized insights from #1-99.

## Members

| Role | Focus | Charter |
|------|-------|---------|
| Director | Strategic research leadership, frontier prioritization | [charter](agents/director/charter.md) |
| Inventor | Novel architectures, divergent thinking, cross-domain insight | [charter](agents/inventor/charter.md) |
| Quant | Trading reality — costs, slippage, market microstructure | [charter](agents/quant/charter.md) |
| Engineer | ktrdr codebase expertise, v3 strategy YAML, experiment specs | [charter](agents/engineer/charter.md) |
| Critic | Experimental rigor, statistical validity, tiered evaluation | [charter](agents/critic/charter.md) |
| Architect | Capability gap analysis, infrastructure specifications | [charter](agents/architect/charter.md) |
| Scout | External research — papers, techniques, data sources | [charter](agents/scout/charter.md) |
| Scribe | Knowledge synthesis, experiment recording, pattern detection | [charter](agents/scribe/charter.md) |

## Coordination

Agents never talk to each other directly. The Coordinator spawns each agent with targeted context and routes responses between them. Each agent sees only what it needs (see architecture doc for context routing table).

## Model

All agents use the best available model (Claude Opus). These are deep thinking tasks — no downgrades.
