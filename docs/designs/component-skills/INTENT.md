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
- **What to avoid** (known pitfalls, deprecated patterns, things that look right but aren't)
- **Key decisions and their rationale** (why it works this way, not some other way)

## How Skills Work

Skills are defined with a YAML frontmatter containing a `name` and `description`. The description is what Claude uses to decide whether to load the skill - it matches against the current task context.

```yaml
---
name: sandbox
description: Use when working with sandbox environments, port mappings, docker compose in sandboxes, .env.sandbox files, or sandbox CLI commands.
---

# Sandbox System

[comprehensive documentation of the component]
```

Skills are loaded on demand, so they don't clutter the context window. Claude sees the skill descriptions at all times (they're lightweight) and loads the full skill content only when the work calls for it.

## Design Principles

1. **Document what exists today** - Skills describe the current implementation, not aspirational designs
2. **Exhaustive over concise** - When Claude loads a skill, it should find everything it needs. The cost of loading a large skill is much less than the cost of Claude going down the wrong path.
3. **Actionable, not academic** - Focus on "here's how to do X" rather than "here's the theory behind X"
4. **Include gotchas** - The most valuable content is often what NOT to do, or what looks right but isn't
5. **Keep current** - When a component changes, the skill should be updated in the same PR

## Candidate Components

Rough priority based on how often Claude needs to rediscover these:

| Component | Why It Needs a Skill |
|-----------|---------------------|
| **Sandbox** | Port mappings, compose project names, env files - easy to get wrong |
| **Configuration** | Multiple overlapping patterns (YAML, Pydantic, dataclass) - redesign pending |
| **Training Pipeline** | Complex multi-step flow across workers and host services |
| **Strategy Grammar (V3)** | Pydantic models, feature resolver, validation - specific patterns to follow |
| **IB Data System** | Connection management, rate limiting, chunking - many edge cases |
| **CLI Architecture** | Command structure, async patterns, progress display |
| **Testing Patterns** | Test categories, fixtures, what to mock, sandbox-aware testing |

## Existing Skills

We already have skills for cross-cutting concerns:

- `distributed-workers` - Worker architecture and patterns
- `deployment` - Starting and deploying the system
- `debugging` - Troubleshooting workflows
- `observability` - Jaeger and Grafana queries
- `api-development` - Creating API endpoints
- `e2e-testing` - E2E test design and execution
- `integration-testing` - Integration test patterns

The component skills proposed here complement these by documenting **specific subsystems** rather than **cross-cutting activities**.

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
3. Test by simulating a task that would require the skill
4. Iterate based on real usage across sessions
