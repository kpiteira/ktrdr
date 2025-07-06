# Autonomous Research Agent Architecture Plan

## Executive Summary

The autonomous research agent will be built as an **evolutionary extension** of the existing KTRDR system, adding sophisticated research orchestration capabilities while leveraging established patterns for API design, async operations, and storage.

## Key Architectural Decision: MCP vs Direct Integration

### Original Spec Approach: Bypass MCP
The research specification proposed bypassing MCP entirely, with Claude directly orchestrating the research through a dedicated research orchestration layer.

### Proposed Alternative: Extend MCP Server
I initially proposed extending the existing MCP server because:
- ✅ Existing MCP patterns are well-established
- ✅ Clean interface for Claude interaction
- ✅ Handles authentication, error handling, etc.
- ✅ Consistent with current system architecture

**QUESTION FOR YOU**: Which approach do you prefer?
- **Option A**: Bypass MCP entirely - Claude directly calls research orchestration APIs
- **Option B**: Extend MCP server - Claude uses enhanced MCP tools for research
- **Option C**: Hybrid - MCP for simple operations, direct API for complex research workflows

## Multi-Agent Architecture Overview

This system implements a **collaborative multi-agent research infrastructure** with three key agents:

### 1. Autonomous Research Agent (LangGraph Orchestrator)
**Purpose**: Tireless 24/7 research execution
**Capabilities**: 
- Runs experiments continuously
- Manages async training/backtesting
- Reports progress and seeks guidance
- Adapts based on feedback

### 2. Research Advisor Agent (Claude Integration)
**Purpose**: Strategic guidance and re-evaluation
**Capabilities**:
- Receives regular status reports from autonomous agent
- Provides strategic direction changes
- Evaluates results and suggests pivots
- Generates new hypotheses based on learnings

### 3. Conversational Agent (Claude via MCP)
**Purpose**: Human-AI collaboration interface
**Capabilities**:
- Answers detailed questions about experiments
- Loads and analyzes historical data
- Receives human guidance and preferences
- Influences autonomous agent direction

## Agent Interaction Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Multi-Agent Research System                  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │         Autonomous Research Agent (LangGraph)          │   │
│  │  - Continuous experiment execution                     │   │
│  │  - Progress tracking and state management              │   │
│  │  - Regular advisor consultations                       │   │
│  └─────────────┬─────────────────────┬─────────────────────┘   │
│                │ Reports & Queries    │ Direction & Guidance    │
│                ▼                     ▲                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Research Advisor Agent (Claude)           │   │
│  │  - Evaluates progress and results                      │   │
│  │  - Provides strategic guidance                         │   │
│  │  - Suggests experiment modifications                   │   │
│  └─────────────┬───────────────────────────────────────────┘   │
│                │ Insights & Analysis                           │
│                ▼                                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │         Conversational Agent (Claude via MCP)          │   │
│  │  - Human interaction interface                         │   │
│  │  - Detailed experiment queries                         │   │
│  │  - Historical data analysis                            │   │
│  └─────────────┬───────────────────────────────────────────┘   │
│                │ Human Guidance                                │
│                ▼                                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                     Human (You)                        │   │
│  │  - Receives notifications                              │   │
│  │  - Provides strategic input                            │   │
│  │  - Reviews discoveries                                 │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Core Architecture Components

### 1. Autonomous Research Agent (LangGraph)
**Location**: `ktrdr/research/autonomous/` (new module)
**Purpose**: Continuous research execution and coordination

**Key Components**:
```
research/
├── autonomous/
│   ├── orchestrator.py      # Main LangGraph workflow
│   ├── experiment_executor.py # KTRDR integration
│   ├── progress_tracker.py  # Status and milestone tracking
│   ├── advisor_client.py    # Communication with Research Advisor
│   └── workflows/           # LangGraph workflow definitions
│       ├── overnight_cycle.py
│       ├── experiment_pipeline.py
│       └── advisor_consultation.py
├── advisor/
│   ├── strategy_evaluator.py # Claude-powered analysis
│   ├── direction_planner.py  # Strategic guidance
│   └── hypothesis_generator.py # New idea generation
└── conversational/
    ├── mcp_tools.py         # MCP tool definitions
    ├── query_engine.py     # Experiment data queries
    └── human_interface.py   # Conversation management
```

**Key Innovation**: Regular advisor consultations during execution

### 2. Enhanced API Layer
**Location**: `ktrdr/api/endpoints/research/` (new)
**Purpose**: Research-specific endpoints following existing patterns

**New Endpoint Structure**:
```
/v1/research/
├── sessions/              # Research session management
├── hypotheses/            # Hypothesis generation and tracking  
├── insights/              # Knowledge base queries and patterns
├── workflows/             # Research workflow management
└── notifications/         # Human attention system
```

**Maintains Existing Patterns**:
- Same response envelope: `{"success": true, "data": {...}}`
- Existing error handling and validation
- Integration with `OperationsService`
- Async/await patterns throughout

### 3. Enhanced Storage Layer
**Location**: Database migration to PostgreSQL
**Purpose**: Research-specific storage with advanced querying capabilities

**New PostgreSQL Schema**:
```sql
-- Research sessions tracking
CREATE TABLE research_sessions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    config JSONB,
    progress JSONB,
    insights_generated INTEGER DEFAULT 0,
    experiments_completed INTEGER DEFAULT 0
);

-- Hypothesis tracking and evolution
CREATE TABLE hypotheses (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES research_sessions(id),
    hypothesis TEXT NOT NULL,
    rationale TEXT,
    priority INTEGER DEFAULT 5,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    experiment_id INTEGER REFERENCES experiments(id),
    parent_hypothesis_id INTEGER REFERENCES hypotheses(id)
);

-- Research insights with vector search capability
CREATE TABLE research_insights (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES research_sessions(id),
    insight_type VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    source_experiments JSONB,
    confidence_score REAL DEFAULT 0.5,
    embedding VECTOR(1536), -- For semantic search
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Failure tracking and categorization
CREATE TABLE experiment_failures (
    id SERIAL PRIMARY KEY,
    experiment_id INTEGER NOT NULL REFERENCES experiments(id),
    failure_type VARCHAR(100) NOT NULL, -- 'partial', 'fatal', 'data', 'indicator'
    error_message TEXT,
    context JSONB,
    resolution_status VARCHAR(50) DEFAULT 'unresolved',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Migration Strategy**: 
- Existing SQLite data migrated to PostgreSQL
- Maintains all existing relationships
- Adds advanced querying capabilities for research

### 4. LLM Integration Layer
**Location**: `ktrdr/llm/` (new module)
**Purpose**: OpenAI-compatible LLM integration for maximum flexibility

**Architecture**:
```python
# Abstract LLM interface
class LLMProvider:
    async def generate_hypotheses(self, context: Dict) -> List[Hypothesis]
    async def analyze_experiment_results(self, results: Dict) -> Analysis
    async def synthesize_insights(self, experiments: List[Dict]) -> List[Insight]

# OpenAI-compatible implementation
class OpenAICompatibleProvider(LLMProvider):
    """Supports OpenRouter, Requesty, Anthropic API, etc."""
    
# Future: Multiple LLM coordination
class MultiLLMOrchestrator:
    """Coordinate multiple LLMs for research discussions"""
```

**Benefits**:
- Maximum flexibility for LLM providers
- Future-proof for multi-LLM scenarios
- Easy switching between providers/models

### 5. Notification System
**Location**: `ktrdr/notifications/` (new module)
**Purpose**: Human attention and communication system

**Architecture**:
```python
# Abstract notification interface
class NotificationProvider:
    async def send_attention_alert(self, message: str, urgency: str)
    async def send_research_update(self, summary: Dict)
    async def send_failure_alert(self, failure: ExperimentFailure)

# Initial implementations
class ConsoleNotificationProvider(NotificationProvider):
    """Simple console logging for development"""

class WebhookNotificationProvider(NotificationProvider):
    """Generic webhook for future Slack/Teams/etc integration"""
```

**Evolution Path**: Console → Webhook → Slack/Teams/SMS/Email

## Multi-Agent Workflow Architecture

### 1. Autonomous Research Cycle with Advisor Consultations
**Duration**: 8-12 hours autonomous operation with regular check-ins
**State Management**: LangGraph workflow with checkpointing and advisor integration

**Enhanced Workflow States**:
```
Initialize → Knowledge_Gap_Analysis → Advisor_Initial_Consultation → 
Hypothesis_Generation → Experiment_Scheduling → Execution_Start →
[Progress_Check → Advisor_Consultation → Direction_Update]* →
Results_Analysis → Insight_Synthesis → Advisor_Final_Review → 
Human_Notification → Await_Human_Input/Next_Cycle
```

**Key Innovation - Regular Advisor Consultations**:
- **20% Progress**: "Advisor, we've completed 6 experiments. Here are the early patterns. Should we continue this direction?"
- **50% Progress**: "Advisor, momentum strategies are showing promise, but mean reversion is failing. Pivot?"
- **Failure Patterns**: "Advisor, we're seeing repeated failures with X. Should we try Y instead?"
- **Resource Limits**: "Advisor, we're hitting GPU limits. Prioritize which experiments?"

### 2. Human Interaction Workflow
**Trigger**: Notification from autonomous agent
**Interface**: Conversational Claude via MCP

**Interaction Pattern**:
```
Notification → Human_Attention → Conversational_Query → 
Deep_Analysis → Strategic_Input → Autonomous_Agent_Update
```

**Example Conversations**:
- **Human**: "Give me details on the last 6 experiments"
- **Conversational Agent**: *Uses MCP tools to load experiment data* "Here's what we found..."
- **Human**: "The volume indicator approach looks promising. Focus more on that."
- **Conversational Agent**: *Updates autonomous agent priorities*

### 2. Failure Handling Architecture
**Failure Categories**:

**Partial Failures** (Continue Research):
- Missing indicators → Log for human attention, continue
- Insufficient data → Log data requirements, continue  
- Invalid parameters → Log parameter issues, continue
- Network timeouts → Retry with backoff, continue

**Fatal Failures** (Pause Research):
- System crashes → Immediate pause, human alert
- Database corruption → Immediate pause, human alert
- API quota exceeded → Pause with clear message
- Memory/resource exhaustion → Pause with resource alert

**Recovery Strategy**:
- Partial failures logged in `experiment_failures` table
- Clear categorization for human action
- Automatic retry for transient issues
- Human notification for attention-required failures

### 3. Knowledge Accumulation Architecture
**Pattern Recognition Pipeline**:
```
Experiment_Results → Feature_Extraction → Pattern_Detection → 
Insight_Generation → Confidence_Scoring → Knowledge_Storage → 
Future_Hypothesis_Influence
```

**Knowledge Types**:
- **Empirical**: Direct experiment results and metrics
- **Relational**: Patterns across experiments and conditions
- **Meta**: Higher-level insights about research process itself
- **Predictive**: Likelihood models for future experiment success

### 3. Notification and Interaction Patterns

**Autonomous Agent Notifications**:
- **Progress Milestones**: "Hey Karl, we're at 20% completion and already ran 6 experiments"
- **Completion**: "Karl, good news, all experiments completed, here is a brief summary <summary>"
- **Attention Required**: "Karl, we need your input on partial failures in indicator calculations"
- **Strategic Discoveries**: "Karl, we found something unexpected with volume patterns!"

**Conversational MCP Tools**:
```python
@mcp.tool()
async def get_experiment_details(session_id: str, experiment_ids: List[str]) -> Dict:
    """Get detailed information about specific experiments"""

@mcp.tool() 
async def get_research_session_summary(session_id: str) -> Dict:
    """Get comprehensive summary of research session progress"""

@mcp.tool()
async def update_research_priorities(session_id: str, priorities: Dict) -> Dict:
    """Update autonomous agent research priorities based on human input"""

@mcp.tool()
async def query_experiment_patterns(pattern_type: str, filters: Dict) -> List[Dict]:
    """Query experiments by patterns, indicators, performance, etc."""

@mcp.tool()
async def get_failure_analysis(session_id: str, failure_type: str) -> Dict:
    """Get detailed analysis of experiment failures needing attention"""
```

## Multi-Agent Communication Architecture

### 1. Autonomous Agent ↔ Research Advisor
**Protocol**: Direct API calls (internal)
**Frequency**: Regular check-ins + event-driven
**Data Exchange**: 
- Progress reports with experiment summaries
- Strategic questions and guidance requests
- Direction updates and priority changes

### 2. Autonomous Agent ↔ Human
**Protocol**: Webhook notifications
**Frequency**: Milestone-based + attention-required
**Data Exchange**:
- Progress notifications
- Completion summaries
- Failure alerts requiring attention

### 3. Human ↔ Conversational Agent
**Protocol**: Claude MCP interface
**Frequency**: Human-initiated after notifications
**Data Exchange**:
- Detailed experiment queries
- Historical analysis requests
- Strategic input and priority updates

### 4. Conversational Agent ↔ Autonomous Agent
**Protocol**: Research API calls
**Frequency**: When human provides guidance
**Data Exchange**:
- Priority updates
- Strategic direction changes
- Resource allocation adjustments

## Key Multi-Agent Architecture Questions

### C1. Advisor Consultation Frequency
**Question**: How often should the autonomous agent consult the research advisor?
- **Time-based**: Every 2 hours during overnight session?
- **Progress-based**: Every 20% completion?
- **Event-driven**: After failures, discoveries, resource issues?
- **Combination**: All of the above with different urgency levels?

### C2. Research Advisor Authority
**Question**: What level of authority should the research advisor have?
- **Suggestions Only**: Autonomous agent can ignore advisor recommendations
- **Strong Influence**: Autonomous agent heavily weights advisor input
- **Direct Control**: Research advisor can directly modify experiment queue
- **Human Override**: Only human input can override advisor decisions

### C3. State Synchronization
**Question**: How do we keep all agents synchronized on research state?
- **Shared Database**: All agents read/write to same research session state
- **Event Bus**: Agents publish/subscribe to state change events  
- **API Gateway**: Central API coordinates all agent interactions
- **Hybrid**: Database for persistence + events for real-time updates

### C4. Conflict Resolution
**Question**: What happens when agents disagree?
- **Autonomous Agent** wants to continue momentum strategies
- **Research Advisor** suggests pivoting to mean reversion  
- **Human** (via conversational agent) prefers volume-based approaches
- **Who wins?** Human > Research Advisor > Autonomous Agent?

### C5. Research Session Lifecycle
**Question**: How are research sessions managed?
- **Auto-start**: New session begins automatically after previous completion?
- **Human-triggered**: Human manually starts each research session?
- **Continuous**: One perpetual session with pause/resume capability?
- **Scheduled**: Predetermined schedule (e.g., every night at 8pm)?

## Implementation Priorities Based on Multi-Agent Architecture

### Phase 1: Core Infrastructure (Foundational)
1. **PostgreSQL Migration**: Migrate existing data + add research schema
2. **Research API Endpoints**: Basic session, experiment, and notification APIs
3. **Notification System**: Webhook-based notifications with configurable endpoints
4. **MCP Tool Extensions**: Add conversational research tools to existing MCP server

### Phase 2: Autonomous Agent (The Workhorse) 
1. **LangGraph Orchestrator**: Core autonomous workflow engine
2. **Experiment Executor**: Integration with existing KTRDR training/backtesting
3. **Progress Tracker**: Milestone detection and notification triggers
4. **Basic Resource Management**: Simple staggered experiment pipeline

### Phase 3: Research Advisor (The Intelligence)
1. **OpenAI-Compatible LLM Integration**: Flexible provider support
2. **Strategy Evaluator**: Claude-powered progress analysis
3. **Direction Planner**: Strategic guidance and pivot recommendations
4. **Advisor-Agent Communication**: Consultation protocol implementation

### Phase 4: Conversational Interface (The Collaborator)
1. **Enhanced MCP Tools**: Deep experiment querying and analysis
2. **Human Interface**: Conversation management and context preservation
3. **Agent Influence System**: Human guidance propagation to autonomous agent
4. **Cross-Session Analytics**: Historical research pattern analysis

### Architectural Decisions Made

**D1. Multi-Agent Coordination**: ✅ **DECIDED - Shared PostgreSQL Database**
- **Chosen**: Shared database for state synchronization (simplest approach)
- All agents read/write to same research session tables
- Uses existing database patterns, easy to debug and monitor
- No complex messaging or event systems needed

**D2. Authority Hierarchy**: ✅ **DECIDED - Human > Research Advisor > Autonomous Agent**
- Clear decision hierarchy for conflict resolution
- Human input (via conversational agent) has ultimate authority
- Research Advisor provides strategic guidance to Autonomous Agent
- Autonomous Agent executes unless overridden by higher authority

**D3. LangGraph Integration**: ✅ **DECIDED - LangGraph for Autonomous Agent**
- LangGraph is specifically designed for multi-agent coordination
- Perfect for managing advisor consultations, human input nodes, and async operations
- Can coordinate between local computation, external API calls, and database operations
- Handles complex workflows with state persistence and checkpointing

**D4. Research Session Model**: ✅ **DECIDED - Human-Triggered Sessions**
- Research sessions started manually by human when desired
- Provides control over when research happens and resource usage
- Sessions run until completion or human intervention
- Future: Could add scheduled option later if desired

## Summary of Multi-Agent Architecture

This ambitious system creates a **collaborative research ecosystem** where:

1. **Autonomous Agent** (LangGraph) works tirelessly 24/7, executing experiments and managing async operations
2. **Research Advisor** (Claude) provides strategic intelligence, evaluating progress and suggesting direction changes
3. **Conversational Agent** (Claude via MCP) enables deep human-AI collaboration through natural conversation
4. **Human** (You) receives intelligent notifications and can influence the research direction through conversation

### Key Innovations

- **Multi-Agent Collaboration**: Three AI agents working together with different specialized roles
- **Regular Strategy Consultations**: Autonomous agent seeks guidance from research advisor during execution
- **Conversational Research Interface**: Human can dive deep into experiment details through natural language
- **Intelligent Notifications**: Context-aware alerts that bring human attention when needed
- **Adaptive Research Direction**: System can pivot based on discoveries and human guidance

### Next Steps for Architecture Finalization

1. **Answer Critical Questions (D1-D4)**: Multi-agent coordination, authority hierarchy, LangGraph decision, session model
2. **Finalize Communication Protocols**: How agents exchange information and coordinate decisions
3. **Design Database Schema**: PostgreSQL tables that support multi-agent coordination
4. **Specify API Contracts**: Endpoints that enable agent communication and human interaction

This architecture enables your vision of an autonomous research system that can work independently while remaining collaborative and responsive to human guidance. The multi-agent approach provides both the autonomous capability you want and the conversational interaction you need.

---

**Note**: This is a living document that captures your ambitious multi-agent research vision. As we refine the details, the architecture will evolve to support the collaborative intelligence system you're building.