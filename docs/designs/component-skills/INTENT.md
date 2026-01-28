# Component Skills: Intent

## Problem

Claude starts every session with zero knowledge of KTRDR's internal systems. CLAUDE.md provides high-level guidance, but when working on a specific component (configuration, sandbox, training pipeline, etc.), Claude must rediscover how that component works by reading code, git history, and design docs. This leads to:

1. **Wasted time**: Repeated exploration of the same systems across sessions
2. **Wrong assumptions**: Claude finds a file that looks like the answer (e.g., a `config.yaml`) and acts on it without understanding the full picture
3. **Lost institutional knowledge**: Design decisions, migration history, and gotchas live only in git history and Karl's memory

## Solution

Create **on-demand skills** for each major component of the system. Skills are markdown files in `.claude/skills/<name>/SKILL.md` that are loaded only when relevant work is happening. They provide:

- **How the component works** (architecture, key files, patterns)
- **How to modify it** (where to add things, what patterns to follow)
- **What to avoid** (known pitfalls, deprecated patterns, things that look right but isn't)
- **Key decisions and their rationale** (why it works this way, not some other way)

## How Skills Work

Skills are defined with a YAML frontmatter containing a `name` and `description`. The description is what Claude uses to decide whether to load the skill — it matches against the current task context.

```yaml
---
name: sandbox
description: Use when working with sandbox environments, port mappings, docker compose in sandboxes, .env.sandbox files, or sandbox CLI commands.
---

# Sandbox System

[comprehensive documentation of the component]
```

Skills are loaded on demand, so they don't clutter the context window. Claude sees the skill descriptions at all times (they're lightweight) and loads the full skill content only when the work calls for it.

## Skill Invocation Visibility

**Problem:** Karl can't tell when skills are being loaded. This makes it impossible to build trust in the system or diagnose issues (bad descriptions, missing skills, etc.).

**Solution:** Every component skill MUST include this as its very first instruction after the frontmatter header:

```markdown
**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL <skill-name> loaded!`
```

This creates a visible signal whenever a skill fires. Once we've built confidence that skills load at the right times, we'll remove the announcement.

## Design Principles

1. **Document what exists today** — Skills describe the current implementation, not aspirational designs
2. **Exhaustive over concise** — When Claude loads a skill, it should find everything it needs. The cost of loading a large skill is much less than the cost of Claude going down the wrong path.
3. **Actionable, not academic** — Focus on "here's how to do X" rather than "here's the theory behind X"
4. **Include gotchas** — The most valuable content is often what NOT to do, or what looks right but isn't
5. **Keep current** — When a component changes, the skill should be updated in the same PR

## Prioritized Skill Roadmap

Full inventory of components, prioritized by value (how much pain Claude rediscovering this causes) and frequency (how often Claude needs this context).

### Tier 1: High Value, High Frequency

| Priority | Component | Status | Why | Notes |
|----------|-----------|--------|-----|-------|
| 1 | **Configuration** | Blocked | Multiple overlapping patterns (YAML, Pydantic, dataclass), redesign pending | Blocked by `doc/config-system-design` branch work in `ktrdr2-spec-work`. Create skill for current state once redesign lands. |
| 2 | **Training Pipeline** | Done | 20+ modules, GPU/CPU paths, error handling, checkpoint flow. Hardest subsystem to reason about cold | `.claude/skills/training-pipeline/SKILL.md` |
| 3 | **Strategy Grammar (V3)** | Done | Pydantic models, feature resolver, validation, fuzzy set shorthand — very specific patterns Claude must follow exactly | `.claude/skills/strategy-grammar-v3/SKILL.md` |
| 4 | **Sandbox** | Done | Port mappings, compose project names, env files, local-prod — easy to get wrong | `.claude/skills/sandbox/SKILL.md` |
| 5 | **Agent System** | Done | Prompts, tool execution, assessment parsing, multi-research coordinator, memory — actively evolving | `.claude/skills/agent-system/SKILL.md` |

### Tier 2: High Value, Moderate Frequency

| Priority | Component | Status | Why |
|----------|-----------|--------|-----|
| 6 | **Data Acquisition / IB** | Done | IB rate limiting, chunking, gap analysis, host service proxy, trading hours — many edge cases |
| 7 | **CLI Architecture** | Done | Lazy loading, sandbox detection, async client, operation runner, progress display — non-obvious patterns |
| 8 | **Backtesting Engine** | Done | Position management, performance metrics, worker integration, checkpoint flow |

### Tier 3: Moderate Value

| Priority | Component | Status | Why |
|----------|-----------|--------|-----|
| 9 | **Async Infrastructure** | Done | ServiceOrchestrator, progress tracking, cancellation — foundational but rarely changed |
| 10 | **Checkpoint System** | Done | Persistence, restore logic, policies — cross-cuts training and backtesting |
| 11 | **Fuzzy Logic Engine** | Done | Membership functions, configuration-driven — moderate complexity |
| 12 | **Technical Indicators** | Done | 70+ indicators, but `docs/adding_new_indicators.md` already exists |
| 13 | **Error Handling** | Done | Exception hierarchy, retry logic — moderate complexity, standard patterns |

### Tier 4: Low Value (Simple, Rarely Touched, or Already Documented)

| Priority | Component | Status | Why |
|----------|-----------|--------|-----|
| 14 | **Decision Engine** | Done | Small, stable, rarely modified |
| 15 | **Neural Networks** | Done | Standard PyTorch, small surface area |
| 16 | **Visualization** | Done | TradingView lightweight-charts, rarely touched |
| 17 | **Monitoring / Observability** | Exists | Already covered by `observability` skill |
| 18 | **Logging** | Done | Standard patterns, stable |
| 19 | **MCP Server** | Done | Thin wrappers, separate concern |
| 20 | **Frontend** | Skip | Has its own `CLAUDE.md`, separate concern |
| 21 | **Utilities** | Skip | Too simple to warrant a skill |

### Already Covered by Existing Skills

These cross-cutting skills already exist and don't need component equivalents:

- `distributed-workers` — Worker architecture and patterns
- `deployment` — Starting and deploying the system
- `debugging` — Troubleshooting workflows
- `observability` — Jaeger and Grafana queries
- `api-development` — Creating API endpoints
- `e2e-testing` — E2E test design and execution
- `integration-testing` — Integration test patterns

## Future Consideration: Tiered Loading

Skills are currently loaded in full when triggered. As the number of component skills grows, the combined token cost could become meaningful — especially in complex sessions where multiple skills load alongside large code reads.

A possible future optimization is **tiered loading**: a lightweight summary (~500 tokens) loaded automatically, with the full skill (~4,000+ tokens) loaded on demand when deeper context is needed.

Possible approaches:
- **Two files**: `SKILL.md` (summary) + `SKILL_FULL.md` (everything)
- **Structured sections**: One file with a quick-reference header and detailed sections below
- **Split skills**: e.g., `sandbox` (core concepts, ports, gotchas) + `sandbox-internals` (registry, gate, secrets)

**We are NOT doing this now.** We have one component skill (sandbox, ~4K tokens), which is ~2% of a 200K context window. The cost is negligible. We need real usage data before optimizing — specifically, evidence that multiple skills loading in one session causes context pressure. Premature splitting risks fragmenting knowledge that's more useful as a single coherent document.

Revisit when:
- We have 15+ component skills and sessions regularly load several
- A single skill grows very large (e.g., training pipeline might be 2-3x the sandbox skill)
- We observe context pressure in sessions with multiple skill loads

## Process

For each new component skill:

1. Research the component thoroughly (git history, design docs, actual code)
2. Write the skill with all relevant information
3. Add the visibility announcement as the first instruction
4. Test by simulating a task that would require the skill
5. Iterate based on real usage across sessions
