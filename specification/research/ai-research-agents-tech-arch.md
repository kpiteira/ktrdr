# AI Research Agents Technical Architecture

## 1. Executive Summary

### Technical Vision
We are implementing a multi-agent research system using **LangGraph** as the orchestration engine, **PostgreSQL** for persistent state management, and **OpenAI-compatible LLMs** for agent reasoning. Each agent runs as an independent process with well-defined APIs, communicating through a combination of direct HTTP calls and PostgreSQL-backed event queuing.

### Core Technology Stack
- **Orchestration**: LangGraph for workflow management and agent coordination
- **State Management**: PostgreSQL with SQLAlchemy ORM for all persistent data
- **Agent Framework**: LangGraph nodes with explicit tool calls (LangChain agents only where dynamic tool selection is essential)
- **Communication**: FastAPI endpoints + Redis Streams for async messaging
- **LLM Integration**: OpenAI API (with support for compatible providers)
- **Existing Integration**: Direct access to KTRDR's FastAPI endpoints
- **Observability**: Structured logging + Prometheus metrics from day one

### Architectural Principles
- **Stateless Agents**: All state in PostgreSQL, agents can restart anytime
- **Event-Driven**: Asynchronous communication through database-backed queues
- **Tool-Based**: Each agent has specialized tools, not general code execution
- **Observable**: All actions logged and traceable through the database
- **Resilient**: Failures don't lose work, everything is resumable

### Expected Technical Outcomes
- Sub-second agent response times for most operations
- Automatic recovery from failures without data loss
- Complete audit trail of all research activities
- Horizontal scalability through additional agent instances
- Clean integration with existing KTRDR system

---

## 2. System Technical Architecture

### 2.1 High-Level Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        PostgreSQL Database                       │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐  │
│  │ Agent State │  │ Experiments │  │   Knowledge Base     │  │
│  │   Tables    │  │   Results   │  │      Tables          │  │
│  └─────────────┘  └─────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                ↑
                                │
┌─────────────────────────────────────────────────────────────────┐
│                         Redis Layer                              │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐  │
│  │   Message   │  │   Event     │  │    Metrics          │  │
│  │   Streams   │  │   Streams   │  │    Cache            │  │
│  └─────────────┘  └─────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                ↑
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph Orchestration Layer                 │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐  │
│  │  Workflow   │  │   Message   │  │    State Machine     │  │
│  │  Executor   │  │   Router    │  │     Manager          │  │
│  └─────────────┘  └─────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                ↑
                                │
┌─────────────────────────────────────────────────────────────────┐
│                         Agent Processes                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │Assistant │  │Researcher│  │  Board   │  │ Coordinator  │  │
│  │   API    │  │   API    │  │   MCP    │  │    API       │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                ↑
                                │
┌─────────────────────────────────────────────────────────────────┐
│                      External Integrations                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  KTRDR   │  │  OpenAI  │  │ Prometheus│  │   Grafana    │  │
│  │   API    │  │   API    │  │  Metrics  │  │  Dashboards  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Distributed Deployment Architecture

The system is designed for distributed deployment across multiple machines using Docker Swarm for orchestration:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Machine 1: Core Infrastructure               │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐  │
│  │ PostgreSQL  │  │ Coordinator │  │    Board Agent       │  │
│  │  (Primary)  │  │   Service   │  │      Service         │  │
│  └─────────────┘  └─────────────┘  └──────────────────────┘  │
│                     Docker Swarm Manager Node                    │
└─────────────────────────────────────────────────────────────────┘
                                ↓
               ┌────────────────┴────────────────┐
               ↓                                 ↓
┌──────────────────────────────┐  ┌──────────────────────────────┐
│   Machine 2: Compute Node     │  │   Machine 3: Creative Node    │
│  ┌────────────────────────┐  │  │  ┌────────────────────────┐  │
│  │ Assistant Researcher   │  │  │  │     Researcher         │  │
│  │    (2 instances)       │  │  │  │    (1 instance)        │  │
│  └────────────────────────┘  │  │  └────────────────────────┘  │
│  ┌────────────────────────┐  │  │  ┌────────────────────────┐  │
│  │    KTRDR Service       │  │  │  │ Knowledge Base Engine  │  │
│  │   (if separated)       │  │  │  │    (1 instance)        │  │
│  └────────────────────────┘  │  │  └────────────────────────┘  │
│      Docker Swarm Worker      │  │      Docker Swarm Worker      │
└──────────────────────────────┘  └──────────────────────────────┘
```

#### Distribution Strategy
- **Core Infrastructure**: Stateful services on dedicated machine
- **Compute Nodes**: CPU/memory intensive agent operations
- **Creative Nodes**: LLM-heavy operations with different resource profiles
- **Horizontal Scaling**: Add more worker nodes as needed

#### Network Design
- **Overlay Network**: Encrypted Docker Swarm overlay for inter-container communication
- **Service Discovery**: Automatic DNS-based service discovery
- **Load Balancing**: Built-in round-robin for scaled services
- **External Access**: Traefik reverse proxy for API gateway

### 2.2 Agent Technical Design

Each agent follows a consistent technical pattern:

#### Agent Core Components
1. **FastAPI Service**: RESTful API for external communication
2. **LangGraph Node**: Explicit tool execution with deterministic flow (LangChain agent wrapper only when dynamic tool selection is required)
3. **Custom Tools**: Specialized functions the agent can invoke
4. **Memory Manager**: PostgreSQL-backed context management
5. **Event Handler**: Processes messages from Redis Streams

#### Agent Lifecycle
- **Initialization**: Load configuration, connect to PostgreSQL/Redis, register with coordinator
- **Message Processing**: Consume from Redis streams, execute tools, publish results
- **State Updates**: All state changes persisted to PostgreSQL
- **Health Monitoring**: Regular heartbeat to coordinator with metrics emission

### 2.3 Communication Architecture

#### Synchronous Communication (HTTP)
- Direct agent-to-agent API calls for immediate responses
- RESTful endpoints with JSON payloads
- JWT-based authentication between agents
- Circuit breakers for resilience

#### Asynchronous Communication (Redis Streams)
- Redis Streams for high-performance message passing
- Agents publish to streams, consumers process with acknowledgment
- Automatic retry with exponential backoff via consumer groups
- Dead letter handling for failed messages
- Message persistence with configurable retention

#### Event Notification System
- Event types: experiment_started, training_update, results_ready
- Publishers write to specific Redis streams
- Subscribers use consumer groups for guaranteed delivery
- Optional PostgreSQL backup for critical events

### 2.4 Data Architecture

#### Core Schema Design
```
agents                  → Agent registry and status
experiments            → Experiment specifications and state
training_runs          → Training execution records
backtest_results       → Backtest performance data
messages              → Inter-agent communication
knowledge_entries     → Accumulated insights
agent_memories        → Per-agent context storage
```

#### Knowledge Base Structure
- **Experiments**: Full specifications, parameters, results
- **Insights**: Patterns discovered, tagged by agent and type
- **Relationships**: Graph structure linking related insights
- **Versioning**: All changes tracked with timestamps

### 2.5 LLM Integration Strategy

#### Agent-Specific Prompts
- System prompts tailored to each agent's role
- Few-shot examples for consistent behavior
- Temperature and parameter tuning per agent type

#### Context Management
- Sliding window of recent activities
- Relevant knowledge base entries
- Current experiment state
- Tool descriptions and examples

#### Token Optimization
- Chunking strategies for large contexts
- Selective memory loading based on relevance
- Summary generation for historical data

---

## 3. Component Specifications

### 3.1 PostgreSQL Database Layer

#### Purpose
Central persistent storage for all system state, enabling stateless agents and full system observability.

#### Technical Implementation
- **Version**: PostgreSQL 15+ with JSONB support
- **ORM**: SQLAlchemy 2.0 with async support
- **Migrations**: Alembic for schema versioning
- **Connection Pooling**: PgBouncer for high concurrency

#### Key Tables

**agents**
- `id`: UUID primary key
- `name`: Agent identifier
- `type`: Agent class (assistant, researcher, etc.)
- `status`: active, idle, error
- `last_heartbeat`: Timestamp
- `config`: JSONB configuration
- `api_endpoint`: Service URL

**experiments**
- `id`: UUID primary key
- `name`: Human-readable identifier
- `specification`: JSONB full experiment details
- `status`: designing, queued, running, completed, failed
- `created_by`: Agent ID
- `assigned_to`: Agent ID
- `priority`: Integer for queue ordering
- `results`: JSONB outcomes

**messages** (Redis-backed events only)
- `id`: UUID primary key
- `stream_key`: Redis stream identifier
- `message_id`: Redis message ID
- `timestamp`: Event timestamp
- `status`: processed, failed, dead_letter
- `retry_count`: Number of retries
- `error_log`: JSONB error details

**knowledge_entries**
- `id`: UUID primary key
- `type`: insight, pattern, failure, success
- `content`: JSONB structured knowledge
- `tags`: Array of categorization tags
- `source_experiment`: Link to experiment
- `created_by`: Agent that generated insight
- `embeddings`: Vector for similarity search

#### Performance Optimizations
- Indexes on status fields for queue polling
- Partial indexes for active records
- JSONB GIN indexes for content searching
- Partitioning for time-series data

### 3.2 LangGraph Orchestration Engine

#### Purpose
Manages complex multi-agent workflows with state persistence and error recovery.

#### Technical Implementation
- **Core**: LangGraph 0.2+ with PostgreSQL checkpointing
- **Workflow Definition**: Python-based DAGs
- **State Management**: PostgreSQL-backed state machines
- **Execution**: Async Python with asyncio

#### Key Workflows

**Experiment Lifecycle with Human Approval**
```python
# Workflow nodes (not actual code, just structure)
START → Design → Review → Approve* → Queue → Assign → Execute → Analyze → Approve* → Store → END
         ↓                    ↓                              ↓         ↓        ↓
       Reject              Reject                          Fail    Timeout   Reject

* Human approval checkpoints (can be automated once confidence is high)
```

**Knowledge Integration**
```python
# Triggered by new insights
NEW_INSIGHT → Validate → Score → Embed → Link → Notify → Update_Agents
                         ↓
                    Below_Threshold → Archive
```

#### Workflow Components
- **Nodes**: Individual agent actions
- **Edges**: Conditional transitions based on outcomes
- **State**: Shared context passed between nodes
- **Checkpoints**: Automatic saving at each node

#### Error Handling
- Automatic retry with exponential backoff
- Dead letter queue for persistent failures
- Human intervention triggers
- Rollback capabilities

### 3.3 Assistant Researcher Implementation

#### Technical Stack
- **Service**: FastAPI with uvicorn
- **Orchestration**: LangGraph node with explicit tool execution
- **LLM Integration**: OpenAI for analysis and decision-making (only when needed)
- **Tools**: Custom Python functions for KTRDR interaction
- **Memory**: PostgreSQL-backed conversation memory

#### Implementation Note
The Assistant Researcher primarily operates as a LangGraph node executing predefined tools in sequence. LangChain agent capabilities are invoked only for complex analysis tasks requiring dynamic reasoning.

#### API Endpoints
- `POST /execute_experiment`: Start experiment execution
- `GET /training_status/{id}`: Real-time training metrics
- `POST /analyze_results`: Deep dive into results
- `GET /health`: Service health check with metrics

#### Custom Tools

**KTRDRTrainingTool**
- Interfaces with KTRDR training API
- Streams training metrics to PostgreSQL
- Handles interruption and resumption

**BacktestAnalysisTool**
- Executes backtests via KTRDR API
- Statistical analysis of results
- Pattern detection in performance

**KnowledgeBaseTool**
- Queries relevant past experiments
- Writes new insights
- Links related findings

#### Agent Memory Design
- Short-term: Current experiment context
- Long-term: Successful strategies and patterns
- Episodic: Specific experiment histories

### 3.4 Researcher Implementation

#### Technical Stack
- **Service**: FastAPI with creative sampling
- **Orchestration**: Hybrid LangGraph/LangChain approach
- **Tools**: Research databases, pattern analyzers
- **Memory**: Inspiration tracking system

#### Implementation Strategy
The Researcher uses LangChain agents for creative tasks (hypothesis generation, cross-domain inspiration) where dynamic tool selection adds value. Structured tasks like experiment design use explicit LangGraph nodes.

#### Creative Tools

**HypothesisGenerator**
- Cross-domain inspiration engine
- Academic paper integration
- Pattern combination algorithms

**ExperimentDesigner**
- Template-based experiment creation
- Parameter space exploration
- Constraint satisfaction

**KnowledgeMiner**
- Graph-based insight navigation
- Similarity search in embeddings
- Trend detection algorithms

#### Creativity Engine
- Multiple LLM calls with different temperatures
- Ensemble approach for idea generation
- Fitness scoring for hypothesis quality

### 3.5 Research Coordinator Implementation

#### Technical Stack
- **Service**: LangGraph-native coordinator with metrics emission
- **Scheduler**: Priority queue with resource tracking
- **Monitor**: Real-time workflow status with observability
- **Router**: Redis Streams message distribution hub

#### Core Components

**WorkflowEngine**
- LangGraph workflow executor with instrumentation
- State machine management with checkpoint persistence
- Checkpoint and recovery with metrics
- Human approval gate management

**ResourceManager**
- Track available compute with real-time updates
- Queue management with Redis-backed persistence
- Priority scheduling with fairness guarantees
- Cost tracking and budget enforcement

**MessageRouter**
- Redis Streams publishing and consumption
- Event broadcasting with fan-out patterns
- Delivery guarantees via consumer groups
- Dead letter queue management

**ObservabilityHub**
- Prometheus metrics for all operations
- Structured logging with correlation IDs
- Workflow tracing and timing
- SLA monitoring and alerting

#### Coordination Patterns
- Round-robin work distribution
- Priority-based scheduling
- Resource-aware assignment
- Deadlock detection

### 3.6 Board Agent Implementation (MCP Server)

#### Technical Stack
- **Service**: MCP Server implementation (Python)
- **Protocol**: JSON-RPC over stdio/SSE
- **Database**: Direct PostgreSQL access for queries
- **Compatibility**: Works with Claude Desktop, GitHub Copilot, Cline, etc.

#### MCP Server Architecture
```python
# MCP server structure (conceptual)
class ResearchBoardMCP:
    """MCP server for research system interaction"""
    
    tools = [
        # Research Overview Tools
        "get_research_summary",
        "list_active_experiments", 
        "show_experiment_details",
        "get_performance_metrics",
        
        # Strategic Analysis Tools
        "analyze_strategy_performance",
        "compare_strategies",
        "get_roi_analysis",
        "identify_top_patterns",
        
        # Research Control Tools
        "set_research_priority",
        "pause_experiment",
        "approve_strategy",
        "allocate_resources",
        
        # Knowledge Base Tools
        "search_insights",
        "get_related_findings",
        "export_report"
    ]
```

#### MCP Tools Specification

**Research Overview Tools**
- `get_research_summary()`: High-level dashboard of all research
- `list_active_experiments(status?, agent?)`: Current experiments
- `show_experiment_details(experiment_id)`: Deep dive into specific experiment
- `get_performance_metrics(timeframe)`: System and strategy metrics

**Strategic Analysis Tools**
- `analyze_strategy_performance(strategy_name)`: Detailed strategy analysis
- `compare_strategies(strategy_ids[])`: Side-by-side comparison
- `get_roi_analysis()`: Resource usage vs discoveries
- `identify_top_patterns()`: Most successful patterns found

**Research Control Tools**
- `set_research_priority(area, weight)`: Adjust focus areas
- `pause_experiment(experiment_id, reason)`: Interrupt running experiment
- `approve_strategy(strategy_id)`: Mark strategy for production
- `allocate_resources(distribution)`: Rebalance compute allocation

**Knowledge Base Tools**
- `search_insights(query, filters?)`: Natural language knowledge search
- `get_related_findings(insight_id)`: Find connected insights
- `export_report(format, filters)`: Generate formatted reports

#### Integration Points
```yaml
# MCP server configuration
name: "research-board"
version: "1.0.0"
description: "AI Research Laboratory Board Interface"

transport:
  type: "stdio"  # Works with all MCP clients

tools:
  - name: "get_research_summary"
    description: "Get high-level overview of all research activities"
    parameters: 
      type: "object"
      properties:
        include_metrics:
          type: "boolean"
          description: "Include performance metrics"
        
  - name: "set_research_priority"
    description: "Adjust research focus and resource allocation"
    parameters:
      type: "object"
      required: ["area", "priority"]
      properties:
        area:
          type: "string"
          enum: ["momentum", "mean_reversion", "volatility", "ml_architectures"]
        priority:
          type: "number"
          minimum: 0
          maximum: 1
```

#### Deployment as MCP Server
```dockerfile
# Dockerfile for MCP server
FROM python:3.11-slim

# Install MCP SDK and dependencies
RUN pip install mcp-sdk sqlalchemy asyncpg pandas

COPY ./board_mcp /app
WORKDIR /app

# MCP servers typically run via stdio
CMD ["python", "server.py"]
```

#### Usage Examples
- **Claude Desktop**: Add to config, discuss research naturally
- **GitHub Copilot**: Code + research insights in IDE
- **Cline**: Autonomous research discussions
- **Custom CLI**: `mcp-client research-board get_research_summary`

#### Benefits of MCP Approach
- No UI development needed
- Works with existing tools developers use
- Natural language interface via Claude/Copilot
- Extensible through standard MCP protocol
- Easy integration with future MCP clients

### 3.7 Knowledge Base Engine

#### Technical Stack
- **Storage**: PostgreSQL with pgvector extension
- **Embeddings**: OpenAI embeddings API
- **Search**: Hybrid keyword + vector similarity
- **Graph**: NetworkX for relationship modeling

#### Core Capabilities

**Semantic Search**
- Vector similarity for finding related insights
- Keyword search for specific terms
- Hybrid ranking algorithm

**Relationship Mapping**
- Graph structure for insight connections
- Causality tracking
- Pattern evolution over time

**Knowledge Synthesis**
- Automated summarization
- Trend detection
- Anomaly identification

#### Access Patterns
- Agent-specific views
- Time-based filtering
- Experiment genealogy
- Success pattern extraction

---

### 3.8 GitOps Deployment Architecture

#### Purpose
Enable declarative, version-controlled deployment of the multi-agent system using Git as the single source of truth for all configuration and deployment state.

#### Technical Architecture
The GitOps layer provides automated deployment pipelines that monitor Git repositories and ensure the running system matches the desired state defined in Git.

#### Core Components

**Git Repository Structure**
- **Deployment Configurations**: Docker Compose files for each environment
- **Agent Configurations**: YAML files defining agent parameters
- **Secret References**: Encrypted references to sensitive data
- **Environment Definitions**: Development, staging, production specs

**GitOps Controller**
- **Repository Monitoring**: Watches for changes in Git
- **State Reconciliation**: Ensures running state matches Git
- **Deployment Automation**: Applies changes to Docker Swarm
- **Rollback Capability**: Reverts to previous known-good states

**CI/CD Pipeline**
- **Build Automation**: Triggered by code changes
- **Image Registry**: Stores versioned Docker images
- **Deployment Triggers**: Activates on configuration changes
- **Health Validation**: Ensures successful deployments

#### Deployment Flow

1. **Developer Push**: Changes committed to Git repository
2. **CI Pipeline**: Builds and tests new Docker images
3. **Image Push**: Validated images pushed to registry
4. **GitOps Sync**: Controller detects configuration changes
5. **Swarm Update**: Docker stack updated with new definitions
6. **Health Check**: Services validated as healthy
7. **Notification**: Team alerted of deployment status

#### Tool Integration Options

**Portainer Business**
- Native Git integration for Docker Swarm
- Web UI for stack management
- Webhook-triggered deployments
- Built-in rollback functionality

**Custom GitHub Actions**
- Direct integration with repository
- Flexible deployment workflows
- Secret management via GitHub
- Matrix builds for multiple environments

**Swarmpit**
- Docker Swarm-native UI
- Git repository integration
- Stack versioning support
- Visual deployment tracking

**Shepherd**
- Automatic image updates
- Watches Docker registries
- Rolling update orchestration
- Zero-downtime deployments

#### Security Considerations

**Secret Management**
- Secrets never stored in Git
- References to external secret stores
- Docker Swarm secret integration
- Encrypted environment variables

**Access Control**
- Git branch protection rules
- Deployment approval workflows
- Audit logging of all changes
- Role-based access to environments

#### Benefits

**Declarative Infrastructure**
- Entire system state in Git
- Self-documenting deployment
- Easy disaster recovery
- Environment consistency

**Automated Operations**
- Hands-off deployments
- Consistent rollout process
- Reduced human error
- Faster deployment cycles

**Version Control**
- Complete deployment history
- Easy rollback to any version
- Diff-based change review
- Collaborative deployment process

### 3.9 Research Quality Measurement (Fitness Functions)

#### Purpose
Define and calculate objective metrics to evaluate the quality and novelty of discovered trading strategies and insights.

#### Technical Architecture
The fitness evaluation system runs as part of the analysis pipeline, scoring each strategy and insight against multiple criteria.

#### Core Metrics

**Strategy Performance Metrics**
- **Sharpe Ratio**: Risk-adjusted returns (threshold > 0.5 for consideration)
- **Maximum Drawdown**: Worst peak-to-trough decline (threshold < 20%)
- **Win Rate**: Percentage of profitable trades (threshold > 45%)
- **Profit Factor**: Gross profits / gross losses (threshold > 1.2)
- **Recovery Factor**: Net profit / maximum drawdown

**Novelty Metrics**
- **Similarity Score**: Vector distance to existing strategies in knowledge base
- **Feature Uniqueness**: Novel feature combinations or parameters
- **Market Condition Coverage**: Performance across different regimes
- **Insight Overlap**: Percentage of new vs. known patterns

**Robustness Metrics**
- **Out-of-Sample Performance**: Forward-testing degradation
- **Parameter Stability**: Performance sensitivity to parameter changes
- **Multi-Symbol Generalization**: Cross-asset performance
- **Time Period Consistency**: Performance across different time windows

#### Scoring Algorithm

```python
# Conceptual fitness calculation
fitness_score = weighted_sum(
    performance_score * 0.4,    # How well does it perform?
    novelty_score * 0.3,        # How different is it?
    robustness_score * 0.3      # How reliable is it?
)

# Thresholds
ACCEPT_THRESHOLD = 0.7      # Auto-accept high-quality strategies
REVIEW_THRESHOLD = 0.5      # Human review required
REJECT_THRESHOLD = 0.5      # Auto-reject poor strategies
```

#### Integration Points
- **Analyzer Node**: Calculates fitness after each backtest
- **Knowledge Base**: Stores fitness scores with insights
- **Human Review**: Triggered for scores in review range
- **Research Director**: Uses fitness trends for resource allocation

#### Continuous Improvement
- Track human override patterns to refine scoring
- A/B test different fitness weights
- Monitor real-world performance vs. fitness predictions
- Adjust thresholds based on false positive/negative rates

### 3.10 Observability and Monitoring

#### Purpose
Provide comprehensive visibility into system behavior, performance, and research quality through structured logging and metrics.

#### Technical Stack
- **Metrics**: Prometheus for time-series metrics
- **Logging**: Structured JSON logs to stdout, collected by Fluentd/Loki
- **Tracing**: OpenTelemetry for distributed tracing (optional for MVP)
- **Dashboards**: Grafana for visualization
- **Alerting**: Prometheus AlertManager for critical issues

#### Key Metrics

**System Health Metrics**
- Agent heartbeat status and uptime
- API response times (p50, p95, p99)
- Redis stream lag and throughput
- PostgreSQL connection pool utilization
- LLM API call success rates and latencies

**Research Process Metrics**
- Experiments per hour/day
- Average experiment duration
- Success/failure/timeout rates
- Human approval rates and timing
- Knowledge base growth rate

**Quality Metrics**
- Fitness score distribution
- Strategy discovery rate
- Novelty scores over time
- Human override frequency
- Real vs. predicted performance correlation

**Resource Utilization**
- LLM token usage by agent
- Computational cost per experiment
- Storage growth rates
- Network bandwidth usage

#### Logging Standards

```python
# Structured log format
{
    "timestamp": "2024-01-15T10:30:45Z",
    "level": "INFO",
    "agent": "assistant_researcher",
    "workflow_id": "exp_123",
    "event": "tool_execution",
    "tool": "ktrdr_training",
    "duration_ms": 1234,
    "metadata": {
        "symbol": "AAPL",
        "timeframe": "1h",
        "model_version": "v3"
    }
}
```

#### Critical Alerts
- Agent down for > 5 minutes
- Experiment failure rate > 50% (1-hour window)
- LLM API errors > 10% (5-minute window)
- PostgreSQL replication lag > 60 seconds
- Disk usage > 85%

#### Dashboard Organization
- **System Overview**: Agent status, experiment flow, error rates
- **Research Analytics**: Discovery rates, fitness scores, strategy performance
- **Resource Usage**: Costs, API limits, storage trends
- **Agent Deep Dive**: Per-agent metrics, tool usage, performance

---

### 4.1 Development Phases

**Phase 1: Foundation (Week 1)**
```python
# Database schema
from sqlalchemy import create_engine, Column, String, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID

Base = declarative_base()

class Agent(Base):
    __tablename__ = 'agents'
    id = Column(UUID, primary_key=True)
    name = Column(String, unique=True)
    type = Column(String)
    status = Column(String)
    config = Column(JSON)
```

**Phase 2: Basic Agents (Week 2)**
```python
# LangGraph node example (preferred approach)
from langgraph.graph import Node

class AssistantResearcherNode(Node):
    def __init__(self, db_url: str, redis_url: str):
        self.tools = {
            'train_model': KTRDRTrainingTool(),
            'run_backtest': BacktestTool(),
            'analyze_results': AnalysisTool()
        }
        self.redis = Redis.from_url(redis_url)
        
    async def process(self, state: dict) -> dict:
        """Explicit tool execution - no hidden loops"""
        experiment = state['experiment']
        
        # Execute training
        training_result = await self.tools['train_model'].run(
            experiment['config']
        )
        
        # Emit metrics
        await self.emit_metrics({
            'event': 'training_complete',
            'duration': training_result['duration'],
            'accuracy': training_result['accuracy']
        })
        
        # Only use LLM for complex analysis
        if training_result['requires_analysis']:
            analysis = await self.analyze_with_llm(training_result)
            state['analysis'] = analysis
            
        return state
```

**Phase 3: Orchestration (Week 3)**
```python
# LangGraph workflow example
from langgraph.graph import StateGraph

def create_experiment_workflow():
    workflow = StateGraph()
    
    # Add nodes
    workflow.add_node("design", design_experiment)
    workflow.add_node("execute", execute_experiment)
    workflow.add_node("analyze", analyze_results)
    
    # Add edges
    workflow.add_edge("design", "execute")
    workflow.add_edge("execute", "analyze")
    
    return workflow.compile()
```

### 4.2 Configuration Structure

```yaml
# config/agents.yaml
agents:
  assistant_researcher:
    type: "langgraph_node"  # Explicit execution flow
    llm:
      model: "gpt-4-turbo-preview"
      temperature: 0.2
      max_tokens: 2000
    tools:
      - ktrdr_training
      - backtest_analysis
      - knowledge_query
    memory:
      type: "postgresql"
      retention_days: 30
    observability:
      metrics_enabled: true
      log_level: "INFO"
      
  researcher:
    type: "hybrid"  # LangGraph + LangChain for creative tasks
    llm:
      model: "gpt-4-turbo-preview"
      temperature: 0.8
      max_tokens: 3000
    tools:
      - hypothesis_generator
      - experiment_designer
      - pattern_analyzer
    langchain_enabled_for:
      - creative_hypothesis
      - cross_domain_inspiration
      
  coordinator:
    type: "langgraph_workflow"
    redis:
      streams:
        - "experiments"
        - "results" 
        - "insights"
    human_approval:
      required_for:
        - "new_experiments"
        - "production_strategies"
      timeout_minutes: 60
```

### 4.3 Deployment Considerations

**Container Architecture**
Each agent runs in its own Docker container with proper resource allocation, monitoring, and network isolation.

**Redis Deployment**
```yaml
# Redis with persistence for message reliability
services:
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --appendfsync everysec
    volumes:
      - redis_data:/data
    deploy:
      placement:
        constraints: [node.labels.type == core]
```

**Docker Images Structure**
```dockerfile
# Base image for all agents
FROM python:3.11-slim as base
RUN pip install langchain langraph sqlalchemy fastapi

# Assistant Researcher image
FROM base as assistant
COPY ./agents/assistant /app
RUN pip install -r requirements.txt
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]

# Researcher image with additional ML libraries
FROM base as researcher  
COPY ./agents/researcher /app
RUN pip install -r requirements.txt
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]
```

**Service Mesh Configuration**
```yaml
# traefik.yml for API gateway
providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    swarmMode: true

entryPoints:
  web:
    address: ":80"
  websecure:
    address: ":443"

# Automatic HTTPS and load balancing
certificatesResolvers:
  letsencrypt:
    acme:
      email: admin@research.ai
      storage: /certificates/acme.json
      httpChallenge:
        entryPoint: web
```

**Resource Allocation**
```yaml
# Resource constraints per service type
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 8G
    reservations:
      cpus: '2'
      memory: 4G
```

**Persistent Storage**
- PostgreSQL data: Docker volumes with backup strategies
- Model artifacts: Shared NFS/GlusterFS mount
- Logs: Centralized logging with Loki/Promtail

**Security Hardening**
- Non-root containers
- Read-only root filesystems where possible
- Secrets management via Docker secrets
- Network policies for service isolation

**Monitoring Stack**
```yaml
# monitoring/docker-compose.yml
services:
  prometheus:
    image: prom/prometheus
    configs:
      - prometheus.yml
    deploy:
      placement:
        constraints: [node.labels.type == core]
  
  grafana:
    image: grafana/grafana
    depends_on:
      - prometheus
    deploy:
      placement:
        constraints: [node.labels.type == core]
  
  loki:
    image: grafana/loki
    deploy:
      placement:
        constraints: [node.labels.type == core]
```

### 4.4 Deployment Architecture

**Distributed Container Design**
```yaml
# docker-compose.yml structure for multi-machine deployment
services:
  # Core Infrastructure (Machine 1)
  postgres:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    networks:
      - research_net
  
  coordinator:
    build: ./agents/coordinator
    environment:
      - DATABASE_URL=postgresql://postgres:5432/research
    depends_on:
      - postgres
    networks:
      - research_net
    deploy:
      placement:
        constraints: [node.labels.type == core]
  
  # Compute-Heavy Agents (Machine 2)
  assistant_researcher:
    build: ./agents/assistant
    environment:
      - DATABASE_URL=postgresql://machine1:5432/research
      - KTRDR_API_URL=http://ktrdr:8000
    networks:
      - research_net
    deploy:
      placement:
        constraints: [node.labels.type == compute]
      resources:
        reservations:
          memory: 8G
  
  # Creative Agents (Machine 3)
  researcher:
    build: ./agents/researcher
    environment:
      - DATABASE_URL=postgresql://machine1:5432/research
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    networks:
      - research_net
    deploy:
      placement:
        constraints: [node.labels.type == creative]
```

**Multi-Machine Setup**
```bash
# Machine 1: Core Infrastructure
docker swarm init --advertise-addr <MACHINE_1_IP>
docker node update --label-add type=core <NODE_ID>

# Machine 2: Compute Node
docker swarm join --token <SWARM_TOKEN> <MACHINE_1_IP>:2377
docker node update --label-add type=compute <NODE_ID>

# Machine 3: Creative Node  
docker swarm join --token <SWARM_TOKEN> <MACHINE_1_IP>:2377
docker node update --label-add type=creative <NODE_ID>
```

**Network Architecture**
- Docker Swarm overlay network for secure inter-container communication
- Encrypted connections between nodes
- Service discovery through Docker DNS
- External access through Traefik reverse proxy

**Service Distribution Strategy**
- **Core Services** (Machine 1): PostgreSQL, Coordinator, Board Agent
- **Compute Services** (Machine 2+): Assistant Researcher, KTRDR
- **Creative Services** (Machine 3+): Researcher, Knowledge Base Engine
- **Scaling**: Add more compute/creative nodes as needed

**Data Persistence**
- PostgreSQL data on Machine 1 with regular backups
- Shared volumes for experiment artifacts
- Optional: GlusterFS or NFS for distributed file access

### 4.5 Performance Guidelines

**Database Optimization**
- Connection pooling for high concurrency
- Read replicas for knowledge queries
- Materialized views for common aggregations
- Vacuum scheduling for PostgreSQL

**LLM Optimization**
- Response caching for common queries
- Batch processing where possible
- Token budget management
- Fallback to smaller models

**Scalability Patterns**
- Horizontal scaling of agent instances
- Queue partitioning by experiment type
- Sharded knowledge base (future)
- Load balancing for API endpoints

### 4.6 Alternative: Kubernetes Deployment (Future)

While Docker Swarm provides sufficient orchestration for MVP, the architecture supports future migration to Kubernetes:

```yaml
# Example Kubernetes deployment structure
apiVersion: apps/v1
kind: Deployment
metadata:
  name: assistant-researcher
spec:
  replicas: 2
  selector:
    matchLabels:
      app: assistant-researcher
  template:
    spec:
      containers:
      - name: assistant
        image: research/assistant:latest
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
          limits:
            memory: "8Gi"
            cpu: "4"
      nodeSelector:
        workload-type: compute
```

### 4.7 GitOps Implementation Details

#### Portainer with Git Integration
```yaml
# portainer-agent-stack.yml
version: '3.8'

services:
  agent:
    image: portainer/agent:latest
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /var/lib/docker/volumes:/var/lib/docker/volumes
    networks:
      - agent_network
    deploy:
      mode: global
      placement:
        constraints: [node.platform.os == linux]

  portainer:
    image: portainer/portainer-ce:latest
    command: -H tcp://tasks.agent:9001 --tlsskipverify
    ports:
      - "9443:9443"
    volumes:
      - portainer_data:/data
    networks:
      - agent_network
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints: [node.role == manager]
```

**Portainer GitOps Setup:**
1. Install Portainer stack on Swarm manager
2. Configure Git repository in Portainer UI
3. Set webhook URL in GitHub/GitLab
4. Define auto-sync intervals
5. Configure environment variables

#### GitHub Actions Workflow
```yaml
# .github/workflows/deploy.yml
name: Deploy to Docker Swarm

on:
  push:
    branches: [main]
    paths:
      - 'deploy/**.yml'
      - 'agents/**/Dockerfile'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      
      - name: Login to Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ secrets.REGISTRY_URL }}
          username: ${{ secrets.REGISTRY_USER }}
          password: ${{ secrets.REGISTRY_PASS }}
      
      - name: Build and Push Images
        run: |
          docker build -t ${{ secrets.REGISTRY_URL }}/assistant:${{ github.sha }} ./agents/assistant
          docker push ${{ secrets.REGISTRY_URL }}/assistant:${{ github.sha }}
          
          docker build -t ${{ secrets.REGISTRY_URL }}/researcher:${{ github.sha }} ./agents/researcher
          docker push ${{ secrets.REGISTRY_URL }}/researcher:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to Swarm
        uses: appleboy/ssh-action@v0.1.5
        with:
          host: ${{ secrets.SWARM_HOST }}
          username: ${{ secrets.SWARM_USER }}
          key: ${{ secrets.SWARM_SSH_KEY }}
          script: |
            cd /opt/research-agents
            git pull
            export ASSISTANT_IMAGE=${{ secrets.REGISTRY_URL }}/assistant:${{ github.sha }}
            export RESEARCHER_IMAGE=${{ secrets.REGISTRY_URL }}/researcher:${{ github.sha }}
            docker stack deploy -c docker-compose.prod.yml research_agents
```

#### Swarmpit Configuration
```yaml
# swarmpit-stack.yml
version: '3.8'

services:
  app:
    image: swarmpit/swarmpit:latest
    environment:
      - SWARMPIT_DB=http://db:5984
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    ports:
      - 888:8080
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 1024M
      placement:
        constraints:
          - node.role == manager

  db:
    image: couchdb:2.3.0
    volumes:
      - db-data:/opt/couchdb/data
    deploy:
      resources:
        limits:
          cpus: '0.30'
          memory: 512M
      placement:
        constraints:
          - node.role == manager

  agent:
    image: swarmpit/agent:latest
    environment:
      - DOCKER_API_VERSION=1.35
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - net
    deploy:
      mode: global
      resources:
        limits:
          cpus: '0.10'
          memory: 64M

volumes:
  db-data:
    driver: local

networks:
  net:
    driver: overlay
    attachable: true
```

#### Shepherd Auto-Update Service
```yaml
# shepherd-stack.yml
version: '3.8'

services:
  shepherd:
    image: mazzolino/shepherd
    environment:
      - SLEEP_TIME=5m
      - BLACKLIST_SERVICES=shepherd postgres
      - WITH_REGISTRY_AUTH=true
      - FILTER_SERVICES=label=auto-update=true
      - TZ=UTC
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    deploy:
      placement:
        constraints:
          - node.role == manager
      resources:
        limits:
          cpus: '0.20'
          memory: 128M
```

#### GitOps Repository Structure
```
research-agents-gitops/
├── environments/
│   ├── development/
│   │   ├── docker-compose.yml
│   │   ├── config/
│   │   │   ├── agents.yaml
│   │   │   └── research-priorities.yaml
│   │   └── .env
│   ├── staging/
│   │   ├── docker-compose.yml
│   │   ├── config/
│   │   └── .env
│   └── production/
│       ├── docker-compose.yml
│       ├── config/
│       └── .env.encrypted
├── scripts/
│   ├── deploy.sh
│   ├── rollback.sh
│   ├── health-check.sh
│   └── backup-db.sh
├── .github/
│   └── workflows/
│       ├── deploy.yml
│       ├── test.yml
│       └── backup.yml
└── README.md
```

#### Deployment Script
```bash
#!/bin/bash
# scripts/deploy.sh - GitOps deployment with validation

set -euo pipefail

# Configuration
ENVIRONMENT="${1:-staging}"
STACK_NAME="research_agents"
COMPOSE_FILE="environments/${ENVIRONMENT}/docker-compose.yml"
ENV_FILE="environments/${ENVIRONMENT}/.env"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Validation
if [[ ! -f "${COMPOSE_FILE}" ]]; then
    log_error "Compose file not found: ${COMPOSE_FILE}"
    exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
    log_error "Environment file not found: ${ENV_FILE}"
    exit 1
fi

# Load environment
log_info "Loading environment: ${ENVIRONMENT}"
source "${ENV_FILE}"

# Validate Docker Swarm
if ! docker info | grep -q "Swarm: active"; then
    log_error "Docker Swarm is not active"
    exit 1
fi

# Deploy stack
log_info "Deploying stack: ${STACK_NAME}"
docker stack deploy \
    -c "${COMPOSE_FILE}" \
    --with-registry-auth \
    --prune \
    "${STACK_NAME}"

# Wait for services
log_info "Waiting for services to be ready..."
sleep 10

# Health check
./scripts/health-check.sh "${STACK_NAME}"

log_info "Deployment complete!"
```

#### Health Check Script
```bash
#!/bin/bash
# scripts/health-check.sh - Verify deployment health

STACK_NAME="${1:-research_agents}"
MAX_ATTEMPTS=30
SLEEP_TIME=5

check_service() {
    local service=$1
    local replicas_running=$(docker service ls \
        --filter "name=${STACK_NAME}_${service}" \
        --format "{{.Replicas}}" | cut -d'/' -f1)
    local replicas_desired=$(docker service ls \
        --filter "name=${STACK_NAME}_${service}" \
        --format "{{.Replicas}}" | cut -d'/' -f2)
    
    if [[ "${replicas_running}" == "${replicas_desired}" ]]; then
        return 0
    else
        return 1
    fi
}

# Check all services
services=("postgres" "coordinator" "assistant" "researcher" "board_mcp")
attempt=0

while [[ $attempt -lt $MAX_ATTEMPTS ]]; do
    all_healthy=true
    
    for service in "${services[@]}"; do
        if ! check_service "$service"; then
            all_healthy=false
            break
        fi
    done
    
    if $all_healthy; then
        echo "All services are healthy!"
        exit 0
    fi
    
    attempt=$((attempt + 1))
    echo "Waiting for services... (${attempt}/${MAX_ATTEMPTS})"
    sleep $SLEEP_TIME
done

echo "Services failed to become healthy"
exit 1
```

#### Environment Configuration
```bash
# environments/production/.env
# PostgreSQL
POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
POSTGRES_DB=research_agents
POSTGRES_USER=research_admin

# Agent Configuration
OPENAI_API_KEY_FILE=/run/secrets/openai_key
KTRDR_API_URL=http://ktrdr:8000
LOG_LEVEL=INFO

# Resource Limits
ASSISTANT_MEMORY_LIMIT=8G
RESEARCHER_MEMORY_LIMIT=4G
COORDINATOR_MEMORY_LIMIT=2G

# Feature Flags
ENABLE_MONITORING=true
ENABLE_BACKUPS=true
```

#### MVP GitOps Setup Instructions

1. **Initialize Git Repository**
   ```bash
   git init research-agents-gitops
   cd research-agents-gitops
   mkdir -p environments/{development,staging,production}
   ```

2. **Install Portainer**
   ```bash
   docker stack deploy -c portainer-agent-stack.yml portainer
   ```

3. **Configure GitHub Actions**
   - Add secrets: SWARM_HOST, REGISTRY_URL, etc.
   - Enable Actions in repository
   - Push to trigger first deployment

4. **Monitor Deployments**
   - Portainer UI: https://swarm-manager:9443
   - GitHub Actions: Check workflow runs
   - Swarm status: `docker service ls`

5. **Rollback if Needed**
   ```bash
   ./scripts/rollback.sh production v1.2.3
   ```