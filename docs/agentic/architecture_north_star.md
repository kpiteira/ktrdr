# Architecture: Autonomous Trading Research Laboratory

## Architectural Vision

A **multi-agent AI system** that operates as a virtual research organization, coordinating specialized agents to continuously discover neuro-fuzzy trading strategies. The architecture prioritizes **resilience**, **cost control**, and **knowledge accumulation** while integrating seamlessly with KTRDR's existing infrastructure.

---

## Core Architecture Principles

### 1. Stateless Agents, Externalized Memory
Agents hold no persistent state. All knowledge, context, and state live in PostgreSQL. Benefits:
- Any agent can fail and restart without data loss
- Context is explicitly managed and debuggable
- Cost control through selective context loading
- Audit trail of all decisions

### 2. Event-Driven Coordination
Agents wake in response to state changes, not fixed schedules:
- Training completes → wake Assistant for analysis
- Quality gate passes → wake Researcher for next hypothesis
- Budget available → wake Director to allocate
- Eliminates wasteful polling by agents

### 3. Deterministic Gates, Creative Agents
Separate deterministic logic from LLM reasoning:
- Quality gates: Pure code, no tokens, fast
- Agents: LLM-powered, creative, expensive
- Coordinator: Hybrid—deterministic state machine, agents for judgment calls

### 4. Knowledge as First-Class Citizen
The knowledge base isn't just storage—it's the system's memory:
- Facts accumulate from experiments
- Patterns emerge from analysis
- Hypotheses guide future research
- Contradictions trigger investigation

### 5. Cost-Aware Everything
Every component considers budget:
- Agents only invoked when work justifies cost
- Context trimmed to essential information
- Deterministic operations preferred over LLM calls
- Daily budget enforced at system level

---

## System Architecture

### Component Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              HUMAN INTERFACE                              │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   CLI       │  │   Board     │  │  Grafana    │  │   Alerts    │    │
│  │  Commands   │  │   Agent     │  │  Dashboard  │  │   (Email/   │    │
│  │             │  │   (MCP)     │  │             │  │   Slack)    │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
┌────────────────────────────────────┴─────────────────────────────────────┐
│                           ORCHESTRATION LAYER                             │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                     Research Coordinator                            │  │
│  │                                                                    │  │
│  │  • State Machine (IDLE → DESIGNING → TRAINING → ...)              │  │
│  │  • Quality Gates (Training, Backtest)                              │  │
│  │  • Agent Invocation (when state change requires reasoning)         │  │
│  │  • Budget Checking (before any agent call)                         │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │ Research Director│  │    Researcher    │  │ Assistant Researcher │  │
│  │                  │  │                  │  │                      │  │
│  │ Budget allocation│  │ Strategy design  │  │ Training analysis    │  │
│  │ Stream priority  │  │ Hypothesis gen   │  │ Backtest analysis    │  │
│  │ ROI tracking     │  │ Creative choices │  │ Deep interpretation  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘  │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
┌────────────────────────────────────┴─────────────────────────────────────┐
│                            INTEGRATION LAYER                              │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                          MCP Tools                                   │ │
│  │                                                                     │ │
│  │  Agent State    Strategy    Training    Backtest    Knowledge      │ │
│  │  Management     Config      Operations  Operations  Base Queries   │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
┌────────────────────────────────────┴─────────────────────────────────────┐
│                             KTRDR SYSTEM                                  │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │  Indicators  │  │    Fuzzy     │  │   Training   │  │  Backtest   │  │
│  │   Engine     │  │    Engine    │  │   Pipeline   │  │   Engine    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘  │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │    Data      │  │    Async     │  │  Checkpoint  │  │    API      │  │
│  │  Management  │  │  Operations  │  │    System    │  │   Layer     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘  │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
┌────────────────────────────────────┴─────────────────────────────────────┐
│                            PERSISTENCE LAYER                              │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                         PostgreSQL                                   │ │
│  │                                                                     │ │
│  │  Agent State │ Sessions │ Actions │ Knowledge │ Budget │ Metrics   │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                      Observability Stack                             │ │
│  │                                                                     │ │
│  │      OTEL Traces (Jaeger)  │  Prometheus Metrics  │  Grafana       │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Agent Architecture

### Agent Design Pattern

All agents follow a consistent pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│                          AGENT                                   │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │     Prompt      │  │    Context      │  │     Tools       │ │
│  │                 │  │    Injection    │  │                 │ │
│  │  Role + Goal    │  │                 │  │  MCP interface  │ │
│  │  Constraints    │  │  Session state  │  │  to KTRDR and   │ │
│  │  Output format  │  │  Recent history │  │  knowledge base │ │
│  │                 │  │  Knowledge      │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│           │                    │                    │          │
│           └────────────────────┼────────────────────┘          │
│                                │                               │
│                                ▼                               │
│                    ┌─────────────────────┐                     │
│                    │     LLM Call        │                     │
│                    │                     │                     │
│                    │  Claude Opus 4.5    │                     │
│                    │  via Claude Code    │                     │
│                    └─────────────────────┘                     │
│                                │                               │
│                                ▼                               │
│                    ┌─────────────────────┐                     │
│                    │   Tool Execution    │                     │
│                    │                     │                     │
│                    │  Save strategy      │                     │
│                    │  Start training     │                     │
│                    │  Query knowledge    │                     │
│                    │  Update state       │                     │
│                    └─────────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Specifications

#### Research Coordinator
**Purpose**: Orchestrate the research workflow
**Invocation**: Periodic (every 5 minutes) or on state change
**Mode**: Hybrid—deterministic state machine + LLM for edge cases

**Responsibilities**:
- Check experiment state and determine next action
- Apply quality gates (deterministic)
- Invoke appropriate agent when reasoning needed
- Handle errors and recovery
- Enforce budget limits

**Does NOT**:
- Design strategies (Researcher's job)
- Analyze results (Assistant's job)
- Allocate resources (Director's job)

#### Researcher Agent
**Purpose**: Generate novel strategy hypotheses
**Invocation**: When new experiment needed
**Mode**: Full LLM—creativity is the value

**Responsibilities**:
- Design new strategy configurations
- Draw on knowledge base patterns
- Explain design rationale
- Vary approaches based on what's worked/failed

**Tools**:
- `get_available_indicators()` - What indicators exist
- `get_available_symbols()` - What data is available
- `get_recent_strategies(n)` - Avoid repetition
- `query_knowledge_base(query)` - Learn from history
- `save_strategy_config(config)` - Store design

**Context Injection**:
- Last 5 strategies (avoid repetition)
- Relevant knowledge base entries
- Current research priorities
- Budget remaining

#### Assistant Researcher Agent
**Purpose**: Analyze training and backtest results
**Invocation**: When training or backtest completes
**Mode**: Full LLM—interpretation is the value

**Responsibilities**:
- Interpret training metrics
- Analyze backtest performance
- Identify why strategies succeed/fail
- Write detailed assessments
- Propose follow-up experiments

**Tools**:
- `get_training_results(operation_id)` - Metrics, loss curves
- `get_backtest_results(operation_id)` - Returns, drawdown, trades
- `save_assessment(assessment)` - Store analysis
- `add_knowledge_entry(entry)` - Record insights

**Context Injection**:
- Strategy configuration
- Training/backtest results
- Similar past experiments
- Relevant knowledge entries

#### Research Director Agent
**Purpose**: Allocate resources across research streams
**Invocation**: Daily or when major decisions needed
**Mode**: LLM for judgment calls

**Responsibilities**:
- Review research stream performance
- Allocate daily budget across streams
- Decide when to pivot vs. persist
- Track ROI of different approaches

**Tools**:
- `get_stream_metrics()` - Performance by research area
- `get_budget_status()` - Spending and remaining
- `set_stream_priority(stream, weight)` - Allocate resources
- `query_knowledge_base(query)` - Review learnings

#### Board Agent
**Purpose**: Human interface for strategic oversight
**Invocation**: On-demand via MCP (Claude Desktop, etc.)
**Mode**: Conversational LLM

**Responsibilities**:
- Answer questions about research progress
- Summarize discoveries and patterns
- Accept strategic direction
- Surface important findings

**Tools**:
- `get_research_summary()` - Overall status
- `get_discoveries(filters)` - Notable findings
- `get_experiment_details(id)` - Deep dive
- `set_research_priority(area, weight)` - Strategic direction

---

## State Machine

### Experiment Lifecycle

```
                                    ┌─────────────┐
                                    │    IDLE     │
                                    │             │
                                    │ No active   │
                                    │ experiment  │
                                    └──────┬──────┘
                                           │
                            Coordinator invokes Researcher
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │  DESIGNING  │
                                    │             │
                                    │ Researcher  │
                                    │ working     │
                                    └──────┬──────┘
                                           │
                              Researcher saves strategy
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │   QUEUED    │
                                    │             │
                                    │ Waiting for │
                                    │ training    │
                                    └──────┬──────┘
                                           │
                            Coordinator starts training
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │  TRAINING   │◀──────────────────┐
                                    │             │                   │
                                    │ KTRDR       │                   │
                                    │ working     │                   │
                                    └──────┬──────┘                   │
                                           │                          │
                              Training completes                      │
                                           │                          │
                                           ▼                          │
                                    ┌─────────────┐                   │
                                    │  TRAINING   │                   │
                                    │   GATE      │                   │
                                    │             │                   │
                                    │ Deterministic                   │
                                    │ pass/fail   │                   │
                                    └──────┬──────┘                   │
                                           │                          │
                          ┌────────────────┼────────────────┐         │
                          │                │                │         │
                       FAIL             MARGINAL          PASS        │
                          │                │                │         │
                          ▼                ▼                ▼         │
                   ┌───────────┐   ┌───────────┐    ┌───────────┐    │
                   │  FAILED   │   │ ANALYZING │    │  QUEUED   │    │
                   │           │   │ (training)│    │ (backtest)│    │
                   │ Record    │   │           │    │           │    │
                   │ failure   │   │ Assistant │    │ Waiting   │    │
                   └─────┬─────┘   │ reviews   │    └─────┬─────┘    │
                         │         └─────┬─────┘          │          │
                         │               │                │          │
                         │               │ (may retry)────┘          │
                         │               │                           │
                         ▼               ▼                           │
                   ┌─────────────────────────────────────────────────┤
                   │                    IDLE                         │
                   └─────────────────────────────────────────────────┘
                                           │
                            Coordinator starts backtest
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │ BACKTESTING │
                                    │             │
                                    │ KTRDR       │
                                    │ working     │
                                    └──────┬──────┘
                                           │
                               Backtest completes
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │  BACKTEST   │
                                    │   GATE      │
                                    │             │
                                    │ Deterministic
                                    │ pass/fail   │
                                    └──────┬──────┘
                                           │
                          ┌────────────────┼────────────────┐
                          │                │                │
                       FAIL             MARGINAL          PASS
                          │                │                │
                          ▼                ▼                ▼
                   ┌───────────┐   ┌───────────┐    ┌───────────┐
                   │  FAILED   │   │ ASSESSING │    │ ASSESSING │
                   │           │   │           │    │           │
                   │ Record    │   │ Assistant │    │ Assistant │
                   │ failure   │   │ analyzes  │    │ analyzes  │
                   └─────┬─────┘   └─────┬─────┘    └─────┬─────┘
                         │               │                │
                         │               │                ▼
                         │               │         ┌───────────┐
                         │               │         │ PROMISING │
                         │               │         │           │
                         │               │         │ Flagged   │
                         │               │         │ for review│
                         │               │         └─────┬─────┘
                         │               │               │
                         ▼               ▼               ▼
                   ┌─────────────────────────────────────────────────┐
                   │                    IDLE                         │
                   │                                                 │
                   │            Ready for next experiment            │
                   └─────────────────────────────────────────────────┘
```

### State Transitions

| From | Event | To | Actor |
|------|-------|-----|-------|
| IDLE | Time to design | DESIGNING | Coordinator |
| DESIGNING | Strategy saved | QUEUED_TRAINING | Researcher |
| QUEUED_TRAINING | Resources available | TRAINING | Coordinator |
| TRAINING | Training complete | TRAINING_GATE | KTRDR |
| TRAINING_GATE | Gate pass | QUEUED_BACKTEST | Coordinator |
| TRAINING_GATE | Gate fail | FAILED | Coordinator |
| TRAINING_GATE | Gate marginal | ANALYZING_TRAINING | Coordinator |
| ANALYZING_TRAINING | Analysis complete | IDLE or RETRY | Assistant |
| QUEUED_BACKTEST | Resources available | BACKTESTING | Coordinator |
| BACKTESTING | Backtest complete | BACKTEST_GATE | KTRDR |
| BACKTEST_GATE | Gate pass | ASSESSING | Coordinator |
| BACKTEST_GATE | Gate fail | FAILED | Coordinator |
| ASSESSING | Assessment complete | IDLE or PROMISING | Assistant |

---

## Knowledge Base Architecture

### Schema Design

```
┌────────────────────────────────────────────────────────────────────────┐
│                           KNOWLEDGE SCHEMA                              │
└────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐       ┌─────────────────────┐
│   knowledge_facts   │       │  knowledge_patterns │
├─────────────────────┤       ├─────────────────────┤
│ id                  │       │ id                  │
│ category            │       │ pattern_type        │
│ statement           │       │ description         │
│ confidence          │       │ supporting_facts[]  │
│ source_experiments[]│       │ confidence          │
│ created_at          │       │ created_at          │
│ validated           │       │ validated           │
└─────────────────────┘       └─────────────────────┘
         │                              │
         │         ┌────────────────────┘
         │         │
         ▼         ▼
┌─────────────────────────────────────────┐
│         knowledge_hypotheses            │
├─────────────────────────────────────────┤
│ id                                      │
│ hypothesis                              │
│ rationale                               │
│ source_patterns[]                       │
│ status (untested/testing/validated/     │
│         refuted)                        │
│ test_experiments[]                      │
│ created_at                              │
└─────────────────────────────────────────┘
         │
         │
         ▼
┌─────────────────────────────────────────┐
│       knowledge_contradictions          │
├─────────────────────────────────────────┤
│ id                                      │
│ fact_a_id                               │
│ fact_b_id                               │
│ description                             │
│ resolution_status                       │
│ resolution_notes                        │
│ investigating_experiments[]             │
└─────────────────────────────────────────┘
```

### Knowledge Flow

```
Experiment Completes
        │
        ▼
┌───────────────────┐
│ Assistant writes  │
│ assessment with   │
│ observations      │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐     ┌───────────────────┐
│ Extract FACTS     │────▶│ Check for         │
│                   │     │ CONTRADICTIONS    │
│ "RSI-14 with      │     │ with existing     │
│  triangular fuzzy │     │ facts             │
│  achieved Sharpe  │     └─────────┬─────────┘
│  0.72 on EURUSD"  │               │
└───────────────────┘               │
                                    ▼
                          ┌───────────────────┐
                          │ Log contradiction │
                          │ for investigation │
                          └───────────────────┘
          │
          ▼
┌───────────────────┐
│ Periodically      │
│ analyze facts for │
│ PATTERNS          │
│                   │
│ "RSI strategies   │
│  show 15% higher  │
│  Sharpe in high   │
│  volatility"      │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Generate          │
│ HYPOTHESES from   │
│ patterns          │
│                   │
│ "Adaptive RSI     │
│  period based on  │
│  volatility may   │
│  improve further" │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Researcher uses   │
│ hypotheses to     │
│ design next       │
│ experiments       │
└───────────────────┘
```

---

## Integration with KTRDR

### MCP Tool Categories

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            MCP TOOLS                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  AGENT STATE TOOLS                                                      │
│  ├── get_session_state()         - Current experiment state             │
│  ├── update_session_state()      - Transition state                     │
│  ├── get_session_history()       - Recent sessions                      │
│  └── record_action()             - Log agent action                     │
│                                                                         │
│  STRATEGY TOOLS                                                         │
│  ├── save_strategy_config()      - Store strategy YAML                  │
│  ├── get_recent_strategies()     - Avoid repetition                     │
│  ├── validate_strategy()         - Check validity                       │
│  └── get_strategy_details()      - Load existing strategy               │
│                                                                         │
│  TRAINING TOOLS (likely exist in KTRDR)                                │
│  ├── start_training()            - Begin training operation             │
│  ├── get_training_status()       - Check progress                       │
│  └── get_training_results()      - Metrics after completion             │
│                                                                         │
│  BACKTEST TOOLS (likely exist in KTRDR)                                │
│  ├── start_backtest()            - Begin backtest operation             │
│  ├── get_backtest_status()       - Check progress                       │
│  └── get_backtest_results()      - Performance after completion         │
│                                                                         │
│  KNOWLEDGE TOOLS                                                        │
│  ├── query_knowledge()           - Search facts/patterns/hypotheses     │
│  ├── add_fact()                  - Record observation                   │
│  ├── add_hypothesis()            - Record testable idea                 │
│  └── get_contradictions()        - Find conflicts to resolve            │
│                                                                         │
│  DISCOVERY TOOLS (for indicators, symbols)                             │
│  ├── get_available_indicators()  - What indicators exist                │
│  ├── get_available_symbols()     - What data is available               │
│  └── get_symbol_date_range()     - Data coverage                        │
│                                                                         │
│  BUDGET TOOLS                                                           │
│  ├── get_budget_status()         - Remaining budget                     │
│  ├── record_cost()               - Log spending                         │
│  └── check_budget()              - Can we afford this call?             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### KTRDR Integration Points

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    KTRDR INTEGRATION POINTS                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  REUSE (existing infrastructure)                                        │
│  ├── Async Operations System     - Track training/backtest progress     │
│  ├── Indicator Engine            - 26+ technical indicators             │
│  ├── Fuzzy Engine               - Membership functions                  │
│  ├── Training Pipeline          - Neural network training               │
│  ├── Backtest Engine            - Strategy evaluation                   │
│  ├── Checkpoint System          - Recovery from failures                │
│  ├── Data Management            - Historical market data                │
│  ├── Validation Framework       - Strategy config validation            │
│  └── Observability Stack        - OTEL, Prometheus, Grafana             │
│                                                                         │
│  EXTEND (add capabilities)                                              │
│  ├── MCP Tools                  - Agent interface to KTRDR              │
│  ├── Agent State Tables         - PostgreSQL schema for agents          │
│  ├── Knowledge Tables           - PostgreSQL schema for knowledge       │
│  └── Agent CLI Commands         - Visibility into agent system          │
│                                                                         │
│  INTEGRATE (connect systems)                                            │
│  ├── Training Completion Hook   - Trigger when training done            │
│  ├── Backtest Completion Hook   - Trigger when backtest done            │
│  ├── Quality Gate Integration   - Use KTRDR metrics                     │
│  └── Strategy Storage           - Save to strategies/ folder            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Observability Architecture

### Telemetry Stack

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         OBSERVABILITY                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  TRACES (Jaeger via OTEL)                                              │
│  ├── agent.session              - Full experiment lifecycle             │
│  ├── agent.invocation           - Single agent call                     │
│  ├── agent.tool_call            - MCP tool execution                    │
│  ├── coordinator.cycle          - Coordinator check cycle               │
│  └── gate.evaluation            - Quality gate check                    │
│                                                                         │
│  METRICS (Prometheus)                                                   │
│  ├── ktrdr_agent_invocations_total        - Count by agent type         │
│  ├── ktrdr_agent_tokens_total             - Token usage                 │
│  ├── ktrdr_agent_cost_dollars_total       - Money spent                 │
│  ├── ktrdr_agent_budget_remaining_dollars - Budget left                 │
│  ├── ktrdr_agent_experiments_total        - Experiments by outcome      │
│  ├── ktrdr_agent_gate_evaluations_total   - Gate results                │
│  ├── ktrdr_agent_knowledge_entries_total  - Knowledge growth            │
│  └── ktrdr_agent_session_duration_seconds - Time per experiment         │
│                                                                         │
│  DASHBOARDS (Grafana)                                                   │
│  ├── Agent Overview             - Health, costs, experiments            │
│  ├── Research Progress          - Discoveries, patterns, hypotheses     │
│  ├── Budget Status              - Spending, remaining, projections      │
│  └── System Health              - Errors, latency, availability         │
│                                                                         │
│  ALERTS                                                                 │
│  ├── budget_exhausted           - Daily budget depleted                 │
│  ├── agent_error_rate_high      - >50% failures in 1 hour              │
│  ├── experiment_stuck           - No progress for 30 minutes            │
│  └── promising_discovery        - Strategy passed all gates             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Scaling Architecture

### Phase 1: Sequential (MVP)
```
┌─────────────────┐
│   Coordinator   │───▶ One experiment at a time
│   (1 instance)  │
└─────────────────┘
        │
        ▼
┌─────────────────┐
│    Researcher   │───▶ Designs strategies sequentially
│   (1 instance)  │
└─────────────────┘
        │
        ▼
┌─────────────────┐
│    Assistant    │───▶ Analyzes results sequentially
│   (1 instance)  │
└─────────────────┘
```

### Phase 2: Parallel Execution
```
┌─────────────────┐
│   Coordinator   │───▶ Manages multiple experiments
│   (1 instance)  │
└─────────────────┘
        │
        ├──────────────────┬──────────────────┐
        ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   Assistant 1   │ │   Assistant 2   │ │   Assistant 3   │
│                 │ │                 │ │                 │
│  Experiment A   │ │  Experiment B   │ │  Experiment C   │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Phase 3: Research Streams
```
┌─────────────────┐
│    Director     │───▶ Allocates budget across streams
│   (1 instance)  │
└─────────────────┘
        │
        ├──────────────────┬──────────────────┐
        ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Momentum       │ │  Mean Reversion │ │  Volatility     │
│  Stream         │ │  Stream         │ │  Stream         │
│                 │ │                 │ │                 │
│  Researcher +   │ │  Researcher +   │ │  Researcher +   │
│  Assistants     │ │  Assistants     │ │  Assistants     │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

---

## Security and Safety

### Budget Controls
- Hard daily limit ($5/day default)
- Per-invocation cost tracking
- Budget check before every agent call
- Automatic pause when exhausted

### Experiment Safety
- All operations through KTRDR (validated, sandboxed)
- No direct market access
- No code execution outside MCP tools
- Audit log of all actions

### Data Safety
- All state in PostgreSQL (backed up)
- Append-only experiment history
- Checkpoint-based recovery
- No destructive operations

### Human Override
- CLI commands for pause/resume/stop
- Emergency stop via database flag
- Board Agent for strategic intervention
- All actions logged and reversible

---

## Future Architecture Evolution

### Potential Enhancements

**Message Queue** (if polling becomes limiting)
- Replace database polling with Redis Streams
- Event-driven agent wake-up
- Better for high-volume operation

**Vector Database** (if knowledge search becomes slow)
- Embed facts/patterns for semantic search
- pgvector extension or dedicated vector DB
- Enable "find similar experiments"

**Workflow Engine** (if coordination becomes complex)
- Temporal, Airflow, or similar
- Visual workflow definition
- Built-in retry and recovery

**Multi-Region** (if resilience becomes critical)
- Distributed PostgreSQL
- Regional agent deployment
- Global coordinator

These are not needed for MVP but architecture doesn't preclude them.

---

*Document Version: 1.0*
*Last Updated: November 2024*
