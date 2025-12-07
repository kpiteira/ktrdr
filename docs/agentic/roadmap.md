# Autonomous Research Laboratory - Roadmap

## Document Purpose

This document provides the **high-level roadmap** for building the Autonomous Trading Research Laboratory. It defines the major milestones from MVP through full multi-agent operation.

**Related Documents**:
- `vision_north_star.md` - The dream we're building toward
- `architecture_north_star.md` - How the full system works
- `mvp/` - Detailed MVP implementation plans

---

## Roadmap Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AUTONOMOUS RESEARCH LABORATORY                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  MVP                    v2                  v3                 v4           │
│  ────                   ──                  ──                 ──           │
│  Single Agent           Learning            Knowledge          Multi-Agent  │
│  Strategy Loop          & Memory            Base               Laboratory   │
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ • Design    │    │ • Remember  │    │ • Facts     │    │ • Researcher│  │
│  │ • Train     │───▶│ • Learn     │───▶│ • Patterns  │───▶│ • Assistant │  │
│  │ • Backtest  │    │ • Improve   │    │ • Hypotheses│    │ • Director  │  │
│  │ • Assess    │    │             │    │             │    │ • Board     │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                             │
│  Proves: Loop works   Proves: Gets       Proves: Learns    Proves: Scales  │
│                       better over time   from history      with agents     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## MVP: Autonomous Strategy Design Loop

**Goal**: Prove a single AI agent can autonomously design, train, backtest, and assess neuro-fuzzy strategies.

**Key Capabilities**:
- Deterministic trigger layer (zero-cost polling)
- Quality gates (skip bad strategies early)
- Full observability and cost tracking
- Budget enforcement ($5/day)

**Success Criteria**:
- Cycle completion rate > 80%
- Valid strategy generation 100%
- Unattended operation for extended periods
- Daily cost < $5

**Duration**: ~10-14 days

**Details**: See `mvp/roadmap.md` and `mvp/PLAN_phase*.md`

---

## v2: Learning & Memory

**Goal**: Agent gets measurably better over time.

**Key Capabilities**:
- Simple memory: "Don't repeat strategies that failed"
- Query past results before designing new strategies
- Pattern detection across experiments
- Retry logic: Modify and retry failed strategies

**New Components**:
- Strategy history table with outcome tracking
- Pattern detection queries
- Agent context includes learned patterns

**Success Criteria**:
- Average Sharpe ratio improves week-over-week
- Fewer repeated failure patterns
- Agent explains why it chose specific approaches

**Prerequisites**: MVP complete and stable

---

## v3: Knowledge Base

**Goal**: Accumulated knowledge informs research direction.

**Key Capabilities**:
- **Facts**: Observations from experiments
  - "RSI-14 strategies achieved avg Sharpe 0.72 on EURUSD"
- **Patterns**: Synthesized insights across experiments
  - "Momentum indicators outperform in trending markets"
- **Hypotheses**: Testable ideas generated from patterns
  - "Adaptive RSI period based on volatility may improve further"
- **Contradictions**: Conflicting observations requiring investigation
  - "Strategy A worked on EURUSD but failed on GBPUSD"

**New Components**:
- `knowledge_facts` table
- `knowledge_patterns` table
- `knowledge_hypotheses` table
- `knowledge_contradictions` table
- Knowledge query MCP tools

**Success Criteria**:
- Novel strategies emerge from knowledge synthesis
- Contradictions trigger focused investigation
- Knowledge base grows meaningfully over time

**Prerequisites**: v2 complete (learning foundation)

---

## v4: Multi-Agent Research Laboratory

**Goal**: Specialized agents collaborate on research.

**Agent Roles**:

| Agent | Responsibility |
|-------|---------------|
| **Researcher** | Creative strategy generation, hypothesis formulation |
| **Assistant** | Execution, monitoring, detailed analysis |
| **Coordinator** | Workflow orchestration, quality gates, agent invocation |
| **Director** | Resource allocation, budget management, stream prioritization |
| **Board** | Strategic direction, human interface, discovery surfacing |

**Key Capabilities**:
- Parallel experiments across multiple Assistants
- Research streams with different focus areas
- Strategic resource allocation
- Natural language interaction via Board Agent

**New Components**:
- Multi-agent coordination layer
- Research stream management
- Agent communication protocol
- Board interface (Claude Desktop MCP)

**Success Criteria**:
- Parallel experiments run efficiently
- Faster discovery through specialization
- Human can interact naturally with system

**Prerequisites**: v3 complete (knowledge foundation)

---

## Future Considerations (v5+)

**Potential Enhancements**:
- **Message Queue**: Replace polling with Redis Streams for high-volume operation
- **Vector Database**: Semantic search over knowledge base (pgvector or dedicated)
- **Workflow Engine**: Temporal/Airflow for complex orchestration
- **Multi-Region**: Distributed agents for resilience
- **Paper Trading**: Connect to live market data for validation
- **Strategy Evolution**: Agents that modify their own approaches

These are not planned but architecture doesn't preclude them.

---

## Constraints

**Budget**: $5/day for LLM costs (adjustable based on ROI)

**Compute**: Leverage existing KTRDR workers for training/backtesting

**Data**: Focus on forex pairs with comprehensive historical data (2005-2025)

**Architecture**: Stay within neuro-fuzzy paradigm (interpretable strategies)

---

## Success Metrics by Phase

| Metric | MVP | v2 | v3 | v4 |
|--------|-----|----|----|-----|
| Strategies tested/week | 50+ | 100+ | 150+ | 300+ |
| Cycle completion rate | >80% | >85% | >90% | >90% |
| Avg Sharpe of passing | >0 | >0.3 | >0.5 | >0.7 |
| Unique insights discovered | - | - | 10+/week | 20+/week |
| Human intervention required | Daily check | Weekly check | Exception only | Exception only |

---

## Ultimate Goal

> "A research partner that works while you don't, accumulates knowledge, discovers strategies, and engages in meaningful discussion about what it's learned."

Not automation. **Augmentation**.

---

*Document Version: 1.0*
