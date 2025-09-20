# System Architecture

## Architectural Overview

The Autonomous Trading Research Laboratory implements a **multi-agent orchestration pattern** where specialized AI agents collaborate to continuously discover and refine neuro-fuzzy trading strategies. The system uses an **event-driven coordination model** with **externalized state management** to ensure resilience and scalability.

## Core Architecture Patterns

### 1. Multi-Agent Orchestration
The system employs specialized agents that communicate through a coordinator, avoiding direct agent-to-agent coupling. Each agent has a focused responsibility and can be scaled independently.

### 2. Externalized Memory
Agents are stateless between sessions. All knowledge, state, and context live in PostgreSQL, loaded on-demand. This enables resilience, debugging, and cost control.

### 3. Event-Driven Coordination
Agents wake in response to state changes, not on fixed schedules. The existing KTRDR async operations system monitors long-running tasks and triggers agent actions when needed.

### 4. Knowledge Accumulation
A structured knowledge system transforms raw experimental results into facts, patterns, and hypotheses that inform future research directions.

## System Components

### Agent Hierarchy

```
┌─────────────────────────────────────────────────┐
│            Board Agent (Strategic)              │
│                                                 │
│         Research Director (Resources)           │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────┴────────────────────────────────┐
│       Research Coordinator (Orchestration)      │
└───────┬─────────────────────────┬───────────────┘
        │                         │
┌───────┴────────┐       ┌───────┴────────┐
│   Researcher   │       │    Assistant    │
│   (Creative)   │       │   (Execution)   │
└────────────────┘       └────────────────┘
        │                         │
        └────────────┬────────────┘
                     │
┌────────────────────┴────────────────────────────┐
│          Knowledge Base (PostgreSQL)            │
└──────────────────────────────────────────────────┘
```

**MVP Scope**: Start with Coordinator + Researcher + Assistant, add Board and Director as system matures.

### Integration Architecture

```
Claude Code Agents ←→ MCP Tools ←→ KTRDR System
        ↓                              ↑
    PostgreSQL ←→ Async Operations Monitor
```

## Technology Decisions

### Agent Runtime: Claude Code
- **Rationale**: Natural language reasoning, flexible tool use, sub-agent spawning
- **Trade-off**: No persistent memory, token costs

### Orchestration: KTRDR Async Operations
- **Rationale**: Reuse existing infrastructure, efficient database polling
- **Trade-off**: Not true event-driven, but avoids token waste

### Storage: PostgreSQL
- **Rationale**: ACID guarantees, JSON support, proven reliability
- **Trade-off**: Single point of failure (acceptable for MVP)

### Integration: MCP Tools
- **Rationale**: Clean interface to KTRDR, extensible capability model
- **Trade-off**: Requires MCP server implementation

## Architectural Principles

### Simplicity Over Sophistication
Start with the minimum viable orchestration. Add complexity only when proven necessary.

### Resilience Through Statelessness
Any agent can fail and restart without losing work. State lives in the database, not in memory.

### Unconstrained Creativity
The Researcher can request any capability. Resource constraints are managed by prioritization, not rejection.

### Learn From Contradictions
Conflicting observations trigger deeper investigation, not data cleaning.

## Scaling Strategy

### Phase 1: Sequential Processing
Single instance of each agent type, experiments run sequentially.

### Phase 2: Parallel Execution
Multiple Assistant Researchers enable parallel experiments. Single Researcher maintains strategy coherence.

### Phase 3: Distributed Research
Multiple specialized Researchers explore different strategy domains. Research Director coordinates focus areas.

## Critical Architectural Decisions

### Why Not Direct Agent Communication?
Agents communicate through the coordinator to maintain loose coupling and enable monitoring.

### Why Externalized State?
Enables agent restart, debugging, and cost control. Trade-off: context reload overhead.

### Why Not Real-Time Events?
KTRDR operations are slow (hours). Polling every few minutes is sufficient and simpler than webhooks.

### Why PostgreSQL for Everything?
Simplicity. One storage system for state, knowledge, and queues. Can specialize later if needed.

## Interfaces and Boundaries

### Agent ↔ Coordinator
- Coordinator spawns agents with focused context
- Agents return structured results
- No direct agent-to-agent communication

### Agents ↔ KTRDR
- Through MCP tools only
- No direct database access to KTRDR
- Clean separation of concerns

### Agents ↔ Knowledge Base
- Read: Query relevant facts and patterns
- Write: Store new insights and hypotheses
- Append-only for experiments (never delete history)

## Future Architecture Evolution

The architecture is designed to evolve:
1. **Message Queue**: Could replace database polling if volume increases
2. **Vector Database**: Could enhance knowledge retrieval as facts accumulate
3. **Workflow Engine**: Could replace coordinator if orchestration becomes complex
4. **Multi-Region**: Could distribute agents geographically for resilience

These are not needed for MVP but the architecture doesn't preclude them.