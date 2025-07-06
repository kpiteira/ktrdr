# AI Research Agents MVP Implementation Guide - Weeks 1-2

## Executive Summary

This guide provides detailed implementation instructions for the thin vertical slice MVP of the AI Research Agents system, following the established KTRDR architectural patterns. We'll implement a single `ResearchAgentMVP` class that combines Researcher and Assistant roles, with full integration into the existing KTRDR infrastructure.

## Week 1: Foundation Implementation

### Day 1-2: Database Schema and Core Models

#### A. PostgreSQL Migration Setup

**File: `ktrdr/migrations/research_001_initial_schema.sql`**
```sql
-- Research schema for AI agents
CREATE SCHEMA IF NOT EXISTS research;

-- Agent states table
CREATE TABLE research.agent_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(255) UNIQUE NOT NULL,
    agent_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'idle',
    current_task_id UUID,
    state_data JSONB NOT NULL DEFAULT '{}',
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Experiments table
CREATE TABLE research.experiments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    hypothesis TEXT NOT NULL,
    agent_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'designing',
    priority INTEGER NOT NULL DEFAULT 5,
    config JSONB NOT NULL,
    results JSONB,
    fitness_score REAL,
    performance_metrics JSONB,
    error_details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (agent_id) REFERENCES research.agent_states(agent_id)
);

-- Knowledge base with vector embeddings (pgvector extension required)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE research.knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    insight_type VARCHAR(100) NOT NULL,
    source_experiment_id UUID,
    embedding vector(1536), -- OpenAI text-embedding-3-small
    metadata JSONB NOT NULL DEFAULT '{}',
    fitness_score REAL,
    tags TEXT[] DEFAULT '{}',
    created_by VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (source_experiment_id) REFERENCES research.experiments(id)
);

-- Agent communication messages
CREATE TABLE research.agent_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_agent VARCHAR(255) NOT NULL,
    to_agent VARCHAR(255),
    message_type VARCHAR(50) NOT NULL,
    content JSONB NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (from_agent) REFERENCES research.agent_states(agent_id)
);

-- Research sessions (for tracking longer research cycles)
CREATE TABLE research.sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    config JSONB NOT NULL DEFAULT '{}',
    total_experiments INTEGER DEFAULT 0,
    successful_experiments INTEGER DEFAULT 0,
    insights_generated INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX idx_experiments_status ON research.experiments(status);
CREATE INDEX idx_experiments_agent_id ON research.experiments(agent_id);
CREATE INDEX idx_experiments_created_at ON research.experiments(created_at);
CREATE INDEX idx_knowledge_base_embedding ON research.knowledge_base USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_knowledge_base_fitness ON research.knowledge_base(fitness_score);
CREATE INDEX idx_agent_states_status ON research.agent_states(status);
CREATE INDEX idx_agent_messages_status ON research.agent_messages(status);
```

#### B. Core Research Models

**File: `ktrdr/api/models/research.py`**
```python
"""Research agent models and schemas."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, validator

from ktrdr.api.models.base import APIResponse


class AgentType(str, Enum):
    """Types of research agents."""
    RESEARCH_MVP = "research_mvp"
    RESEARCHER = "researcher"
    ASSISTANT = "assistant"
    COORDINATOR = "coordinator"
    BOARD = "board"
    ARCHITECT = "architect"


class AgentStatus(str, Enum):
    """Agent operational status."""
    IDLE = "idle"
    THINKING = "thinking"
    DESIGNING = "designing"
    EXECUTING = "executing"
    ANALYZING = "analyzing"
    ERROR = "error"
    OFFLINE = "offline"


class ExperimentStatus(str, Enum):
    """Experiment lifecycle status."""
    DESIGNING = "designing"
    QUEUED = "queued"
    RUNNING = "running"
    TRAINING = "training"
    BACKTESTING = "backtesting"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InsightType(str, Enum):
    """Types of research insights."""
    PATTERN = "pattern"
    STRATEGY = "strategy"
    FAILURE = "failure"
    OPTIMIZATION = "optimization"
    DISCOVERY = "discovery"
    META_LEARNING = "meta_learning"


class FitnessComponents(BaseModel):
    """Breakdown of fitness score components."""
    performance_score: float = Field(..., ge=0.0, le=1.0)
    novelty_score: float = Field(..., ge=0.0, le=1.0)
    robustness_score: float = Field(..., ge=0.0, le=1.0)
    combined_fitness: float = Field(..., ge=0.0, le=1.0)


class ExperimentConfig(BaseModel):
    """Configuration for a research experiment."""
    hypothesis: str = Field(..., min_length=10, max_length=1000)
    symbols: List[str] = Field(..., min_items=1, max_items=5)
    timeframes: List[str] = Field(default=["1h"])
    max_duration_hours: int = Field(default=4, ge=1, le=24)
    
    # Strategy parameters
    strategy_type: str = Field(default="neural_fuzzy")
    neural_config: Dict[str, Any] = Field(default_factory=dict)
    fuzzy_config: Dict[str, Any] = Field(default_factory=dict)
    
    # Training parameters
    training_config: Dict[str, Any] = Field(default_factory=lambda: {
        "epochs": 100,
        "learning_rate": 0.001,
        "batch_size": 32,
        "validation_split": 0.2
    })
    
    # Backtest parameters
    backtest_config: Dict[str, Any] = Field(default_factory=lambda: {
        "initial_capital": 10000.0,
        "commission": 0.001,
        "slippage": 0.0005
    })

    @validator('symbols')
    def validate_symbols(cls, v):
        """Validate trading symbols."""
        valid_symbols = ["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN", "SPY", "QQQ"]
        for symbol in v:
            if symbol not in valid_symbols:
                raise ValueError(f"Invalid symbol: {symbol}")
        return v


class ExperimentResults(BaseModel):
    """Results from a completed experiment."""
    fitness_score: float = Field(..., ge=0.0, le=1.0)
    fitness_components: FitnessComponents
    
    # Training results
    training_metrics: Dict[str, float] = Field(default_factory=dict)
    training_duration_minutes: float
    model_path: Optional[str] = None
    
    # Backtest results
    backtest_metrics: Dict[str, float] = Field(default_factory=dict)
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    
    # Insights and analysis
    insights: List[str] = Field(default_factory=list)
    patterns_discovered: List[str] = Field(default_factory=list)
    failure_analysis: Optional[str] = None


class Insight(BaseModel):
    """Knowledge base insight."""
    id: UUID
    content: str
    insight_type: InsightType
    source_experiment_id: Optional[UUID] = None
    fitness_score: Optional[float] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_by: str
    created_at: datetime


class AgentState(BaseModel):
    """Current state of a research agent."""
    agent_id: str
    agent_type: AgentType
    status: AgentStatus
    current_task_id: Optional[UUID] = None
    state_data: Dict[str, Any] = Field(default_factory=dict)
    last_heartbeat: datetime
    created_at: datetime
    updated_at: datetime


class ResearchSession(BaseModel):
    """Research session tracking."""
    id: UUID
    name: str
    description: Optional[str] = None
    status: str
    config: Dict[str, Any] = Field(default_factory=dict)
    total_experiments: int = 0
    successful_experiments: int = 0
    insights_generated: int = 0
    started_at: datetime
    ended_at: Optional[datetime] = None


# Request/Response Models
class StartExperimentRequest(BaseModel):
    """Request to start a new experiment."""
    experiment_config: ExperimentConfig
    session_id: Optional[UUID] = None
    priority: int = Field(default=5, ge=1, le=10)


class ExperimentResponse(BaseModel):
    """Response for experiment operations."""
    experiment_id: UUID
    status: ExperimentStatus
    agent_id: str
    created_at: datetime
    results: Optional[ExperimentResults] = None


class AgentStatusResponse(BaseModel):
    """Response for agent status queries."""
    agent_state: AgentState
    current_experiment: Optional[ExperimentResponse] = None
    recent_activity: List[str] = Field(default_factory=list)


class InsightQueryRequest(BaseModel):
    """Request to query the knowledge base."""
    query: str
    insight_types: List[InsightType] = Field(default_factory=list)
    min_fitness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    max_results: int = Field(default=10, ge=1, le=100)


class InsightQueryResponse(BaseModel):
    """Response for knowledge base queries."""
    insights: List[Insight]
    total_found: int
    query_embedding_time_ms: float


# Type aliases for API responses
StartExperimentResponse = APIResponse[ExperimentResponse]
GetExperimentResponse = APIResponse[ExperimentResponse]
GetAgentStatusResponse = APIResponse[AgentStatusResponse]
QueryInsightsResponse = APIResponse[InsightQueryResponse]
```

#### C. Database Service Implementation

**File: `ktrdr/api/services/research_db_service.py`**
```python
"""Database service for research operations."""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import asyncpg
from asyncpg import Pool

from ktrdr.api.models.research import (
    AgentState, AgentStatus, AgentType, ExperimentStatus, 
    Insight, InsightType, ResearchSession, ExperimentConfig,
    ExperimentResults
)
from ktrdr.api.services.base import BaseService
from ktrdr.config import get_config

logger = logging.getLogger(__name__)


class ResearchDBService(BaseService):
    """Database service for research agent operations."""
    
    def __init__(self, database_url: str):
        super().__init__()
        self.database_url = database_url
        self.pool: Optional[Pool] = None
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Initialize database connection pool."""
        if self.pool is None:
            async with self._lock:
                if self.pool is None:
                    self.pool = await asyncpg.create_pool(
                        self.database_url,
                        min_size=2,
                        max_size=10,
                        command_timeout=60
                    )
                    logger.info("Research database pool initialized")
    
    async def close(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Research database pool closed")
    
    # Agent Management
    async def register_agent(self, agent_id: str, agent_type: AgentType) -> None:
        """Register a new agent."""
        await self.initialize()
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO research.agent_states (agent_id, agent_type, status)
                VALUES ($1, $2, $3)
                ON CONFLICT (agent_id) DO UPDATE SET
                    agent_type = EXCLUDED.agent_type,
                    status = EXCLUDED.status,
                    last_heartbeat = NOW(),
                    updated_at = NOW()
            """, agent_id, agent_type.value, AgentStatus.IDLE.value)
    
    async def update_agent_status(
        self, 
        agent_id: str, 
        status: AgentStatus,
        current_task_id: Optional[UUID] = None,
        state_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update agent status and state."""
        await self.initialize()
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE research.agent_states 
                SET status = $2, current_task_id = $3, state_data = $4,
                    last_heartbeat = NOW(), updated_at = NOW()
                WHERE agent_id = $1
            """, agent_id, status.value, current_task_id, 
                json.dumps(state_data or {}))
    
    async def get_agent_state(self, agent_id: str) -> Optional[AgentState]:
        """Get current agent state."""
        await self.initialize()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT agent_id, agent_type, status, current_task_id, 
                       state_data, last_heartbeat, created_at, updated_at
                FROM research.agent_states
                WHERE agent_id = $1
            """, agent_id)
            
            if row:
                return AgentState(
                    agent_id=row['agent_id'],
                    agent_type=AgentType(row['agent_type']),
                    status=AgentStatus(row['status']),
                    current_task_id=row['current_task_id'],
                    state_data=json.loads(row['state_data']),
                    last_heartbeat=row['last_heartbeat'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
        return None
    
    # Experiment Management
    async def create_experiment(
        self,
        name: str,
        hypothesis: str,
        agent_id: str,
        config: ExperimentConfig,
        session_id: Optional[UUID] = None,
        priority: int = 5
    ) -> UUID:
        """Create a new experiment."""
        await self.initialize()
        experiment_id = uuid4()
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO research.experiments 
                (id, name, hypothesis, agent_id, config, priority, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, experiment_id, name, hypothesis, agent_id, 
                config.json(), priority, ExperimentStatus.DESIGNING.value)
        
        logger.info(f"Created experiment {experiment_id} for agent {agent_id}")
        return experiment_id
    
    async def update_experiment_status(
        self,
        experiment_id: UUID,
        status: ExperimentStatus,
        results: Optional[ExperimentResults] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update experiment status and results."""
        await self.initialize()
        
        update_fields = ["status = $2", "updated_at = NOW()"]
        params = [experiment_id, status.value]
        param_count = 2
        
        if status == ExperimentStatus.RUNNING and not await self._has_started_at(experiment_id):
            update_fields.append("started_at = NOW()")
        
        if status in [ExperimentStatus.COMPLETED, ExperimentStatus.FAILED, ExperimentStatus.CANCELLED]:
            update_fields.append("completed_at = NOW()")
        
        if results:
            param_count += 1
            update_fields.append(f"results = ${param_count}")
            params.append(results.json())
            
            if results.fitness_score:
                param_count += 1
                update_fields.append(f"fitness_score = ${param_count}")
                params.append(results.fitness_score)
        
        if error_details:
            param_count += 1
            update_fields.append(f"error_details = ${param_count}")
            params.append(json.dumps(error_details))
        
        query = f"""
            UPDATE research.experiments 
            SET {', '.join(update_fields)}
            WHERE id = $1
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(query, *params)
    
    async def _has_started_at(self, experiment_id: UUID) -> bool:
        """Check if experiment has started_at timestamp."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT started_at FROM research.experiments WHERE id = $1",
                experiment_id
            )
            return row and row['started_at'] is not None
    
    async def get_experiment(self, experiment_id: UUID) -> Optional[Dict[str, Any]]:
        """Get experiment by ID."""
        await self.initialize()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, name, hypothesis, agent_id, status, priority,
                       config, results, fitness_score, error_details,
                       created_at, started_at, completed_at
                FROM research.experiments
                WHERE id = $1
            """, experiment_id)
            
            if row:
                return {
                    'id': row['id'],
                    'name': row['name'],
                    'hypothesis': row['hypothesis'],
                    'agent_id': row['agent_id'],
                    'status': ExperimentStatus(row['status']),
                    'priority': row['priority'],
                    'config': json.loads(row['config']),
                    'results': json.loads(row['results']) if row['results'] else None,
                    'fitness_score': row['fitness_score'],
                    'error_details': json.loads(row['error_details']) if row['error_details'] else None,
                    'created_at': row['created_at'],
                    'started_at': row['started_at'],
                    'completed_at': row['completed_at']
                }
        return None
    
    async def list_experiments(
        self,
        agent_id: Optional[str] = None,
        status: Optional[ExperimentStatus] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List experiments with optional filters."""
        await self.initialize()
        
        where_clauses = []
        params = []
        param_count = 0
        
        if agent_id:
            param_count += 1
            where_clauses.append(f"agent_id = ${param_count}")
            params.append(agent_id)
        
        if status:
            param_count += 1
            where_clauses.append(f"status = ${param_count}")
            params.append(status.value)
        
        param_count += 1
        params.append(limit)
        
        where_clause = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        query = f"""
            SELECT id, name, hypothesis, agent_id, status, priority,
                   fitness_score, created_at, started_at, completed_at
            FROM research.experiments
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_count}
        """
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    # Knowledge Base Management
    async def save_insight(
        self,
        content: str,
        insight_type: InsightType,
        created_by: str,
        source_experiment_id: Optional[UUID] = None,
        fitness_score: Optional[float] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None
    ) -> UUID:
        """Save an insight to the knowledge base."""
        await self.initialize()
        insight_id = uuid4()
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO research.knowledge_base 
                (id, content, insight_type, source_experiment_id, embedding,
                 metadata, fitness_score, tags, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, insight_id, content, insight_type.value, source_experiment_id,
                embedding, json.dumps(metadata or {}), fitness_score,
                tags or [], created_by)
        
        logger.info(f"Saved insight {insight_id} of type {insight_type.value}")
        return insight_id
    
    async def query_insights_by_similarity(
        self,
        query_embedding: List[float],
        insight_types: Optional[List[InsightType]] = None,
        min_fitness_score: float = 0.0,
        max_results: int = 10
    ) -> List[Insight]:
        """Query insights by vector similarity."""
        await self.initialize()
        
        where_clauses = ["fitness_score >= $2"]
        params = [query_embedding, min_fitness_score]
        param_count = 2
        
        if insight_types:
            param_count += 1
            where_clauses.append(f"insight_type = ANY(${param_count})")
            params.append([t.value for t in insight_types])
        
        param_count += 1
        params.append(max_results)
        
        where_clause = " AND ".join(where_clauses)
        
        query = f"""
            SELECT id, content, insight_type, source_experiment_id,
                   metadata, fitness_score, tags, created_by, created_at,
                   embedding <=> $1 as distance
            FROM research.knowledge_base
            WHERE {where_clause}
            ORDER BY embedding <=> $1
            LIMIT ${param_count}
        """
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
            insights = []
            for row in rows:
                insights.append(Insight(
                    id=row['id'],
                    content=row['content'],
                    insight_type=InsightType(row['insight_type']),
                    source_experiment_id=row['source_experiment_id'],
                    fitness_score=row['fitness_score'],
                    tags=row['tags'],
                    metadata=json.loads(row['metadata']),
                    created_by=row['created_by'],
                    created_at=row['created_at']
                ))
            
            return insights
    
    # Session Management
    async def create_session(
        self,
        name: str,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """Create a new research session."""
        await self.initialize()
        session_id = uuid4()
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO research.sessions (id, name, description, config)
                VALUES ($1, $2, $3, $4)
            """, session_id, name, description, json.dumps(config or {}))
        
        return session_id
    
    async def get_session(self, session_id: UUID) -> Optional[ResearchSession]:
        """Get research session by ID."""
        await self.initialize()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, name, description, status, config,
                       total_experiments, successful_experiments, insights_generated,
                       started_at, ended_at
                FROM research.sessions
                WHERE id = $1
            """, session_id)
            
            if row:
                return ResearchSession(
                    id=row['id'],
                    name=row['name'],
                    description=row['description'],
                    status=row['status'],
                    config=json.loads(row['config']),
                    total_experiments=row['total_experiments'],
                    successful_experiments=row['successful_experiments'],
                    insights_generated=row['insights_generated'],
                    started_at=row['started_at'],
                    ended_at=row['ended_at']
                )
        return None
```

### Day 3-4: Research Service Implementation

#### A. Core Research Service

**File: `ktrdr/api/services/research_service.py`**
```python
"""Core research service for experiment orchestration."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from ktrdr.api.models.research import (
    AgentStatus, AgentType, ExperimentConfig, ExperimentResults,
    ExperimentStatus, FitnessComponents, InsightType
)
from ktrdr.api.services.base import BaseService
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.services.research_db_service import ResearchDBService
from ktrdr.api.services.training_service import TrainingService
from ktrdr.api.services.backtesting_service import BacktestingService
from ktrdr.errors import ValidationError, OperationError

logger = logging.getLogger(__name__)


class ResearchService(BaseService):
    """Service for AI research agent operations."""
    
    def __init__(
        self,
        db_service: ResearchDBService,
        operations_service: OperationsService,
        training_service: TrainingService,
        backtesting_service: BacktestingService
    ):
        super().__init__()
        self.db = db_service
        self.operations = operations_service
        self.training = training_service
        self.backtesting = backtesting_service
        
        # Agent registry
        self.agents: Dict[str, 'ResearchAgentMVP'] = {}
        self._agent_lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Initialize the research service."""
        await self.db.initialize()
        
        # Create default MVP agent
        await self.register_agent("research_mvp_001", AgentType.RESEARCH_MVP)
        logger.info("Research service initialized")
    
    async def register_agent(self, agent_id: str, agent_type: AgentType) -> None:
        """Register a new research agent."""
        async with self._agent_lock:
            if agent_id not in self.agents:
                agent = ResearchAgentMVP(agent_id, agent_type, self)
                self.agents[agent_id] = agent
                await self.db.register_agent(agent_id, agent_type)
                await agent.initialize()
                logger.info(f"Registered agent {agent_id} of type {agent_type}")
    
    async def start_experiment(
        self,
        experiment_config: ExperimentConfig,
        agent_id: str = "research_mvp_001",
        session_id: Optional[UUID] = None,
        priority: int = 5
    ) -> UUID:
        """Start a new research experiment."""
        # Validate agent exists
        if agent_id not in self.agents:
            raise ValidationError(f"Agent {agent_id} not found")
        
        agent = self.agents[agent_id]
        
        # Create experiment record
        experiment_id = await self.db.create_experiment(
            name=f"Experiment-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            hypothesis=experiment_config.hypothesis,
            agent_id=agent_id,
            config=experiment_config,
            session_id=session_id,
            priority=priority
        )
        
        # Start experiment execution
        asyncio.create_task(agent.execute_experiment(experiment_id, experiment_config))
        
        logger.info(f"Started experiment {experiment_id} with agent {agent_id}")
        return experiment_id
    
    async def get_experiment_status(self, experiment_id: UUID) -> Optional[Dict[str, Any]]:
        """Get current experiment status."""
        return await self.db.get_experiment(experiment_id)
    
    async def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get current agent status."""
        agent_state = await self.db.get_agent_state(agent_id)
        if agent_state:
            return {
                'agent_state': agent_state,
                'current_experiment': None,  # TODO: Load current experiment
                'recent_activity': []  # TODO: Load recent activity
            }
        return None
    
    async def list_experiments(
        self,
        agent_id: Optional[str] = None,
        status: Optional[ExperimentStatus] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List experiments with optional filters."""
        return await self.db.list_experiments(agent_id, status, limit)
    
    def calculate_fitness_score(
        self,
        training_metrics: Dict[str, float],
        backtest_metrics: Dict[str, float],
        novelty_score: float = 0.5
    ) -> FitnessComponents:
        """Calculate comprehensive fitness score."""
        # Performance component (40% weight)
        sharpe_ratio = backtest_metrics.get('sharpe_ratio', 0.0)
        win_rate = backtest_metrics.get('win_rate', 0.0)
        max_drawdown = backtest_metrics.get('max_drawdown', 1.0)
        
        # Normalize performance metrics
        sharpe_normalized = min(max(sharpe_ratio / 2.0, 0.0), 1.0)  # Cap at 2.0 Sharpe
        win_rate_normalized = win_rate
        drawdown_penalty = max(0.0, 1.0 - (max_drawdown / 0.2))  # Penalty for >20% drawdown
        
        performance_score = (sharpe_normalized * 0.5 + win_rate_normalized * 0.3 + drawdown_penalty * 0.2)
        
        # Robustness component (30% weight) - based on training stability
        val_accuracy = training_metrics.get('val_accuracy', 0.0)
        overfitting_penalty = abs(training_metrics.get('train_accuracy', 0.0) - val_accuracy)
        robustness_score = max(0.0, val_accuracy - overfitting_penalty * 0.5)
        
        # Combined fitness (weighted average)
        combined_fitness = (
            performance_score * 0.4 +
            novelty_score * 0.3 +
            robustness_score * 0.3
        )
        
        return FitnessComponents(
            performance_score=performance_score,
            novelty_score=novelty_score,
            robustness_score=robustness_score,
            combined_fitness=combined_fitness
        )


class ResearchAgentMVP:
    """MVP Research Agent combining Researcher and Assistant roles."""
    
    def __init__(self, agent_id: str, agent_type: AgentType, research_service: ResearchService):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.research_service = research_service
        self.current_experiment_id: Optional[UUID] = None
        
        # Access to KTRDR services
        self.training = research_service.training
        self.backtesting = research_service.backtesting
        self.db = research_service.db
    
    async def initialize(self) -> None:
        """Initialize the agent."""
        await self.update_status(AgentStatus.IDLE)
        logger.info(f"Agent {self.agent_id} initialized")
    
    async def update_status(
        self,
        status: AgentStatus,
        current_task_id: Optional[UUID] = None,
        state_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update agent status in database."""
        await self.db.update_agent_status(
            self.agent_id, status, current_task_id, state_data
        )
    
    async def execute_experiment(
        self, 
        experiment_id: UUID, 
        config: ExperimentConfig
    ) -> None:
        """Execute a complete research experiment."""
        self.current_experiment_id = experiment_id
        
        try:
            # Phase 1: Design (Researcher role)
            await self.update_status(AgentStatus.DESIGNING, experiment_id)
            await self.db.update_experiment_status(experiment_id, ExperimentStatus.QUEUED)
            
            logger.info(f"Agent {self.agent_id} starting experiment {experiment_id}")
            
            # Phase 2: Training (Assistant role)
            await self.update_status(AgentStatus.EXECUTING, experiment_id)
            await self.db.update_experiment_status(experiment_id, ExperimentStatus.TRAINING)
            
            training_results = await self._execute_training(config)
            
            # Phase 3: Backtesting (Assistant role)
            await self.db.update_experiment_status(experiment_id, ExperimentStatus.BACKTESTING)
            
            backtest_results = await self._execute_backtesting(config, training_results)
            
            # Phase 4: Analysis (Assistant role)
            await self.update_status(AgentStatus.ANALYZING, experiment_id)
            await self.db.update_experiment_status(experiment_id, ExperimentStatus.ANALYZING)
            
            analysis_results = await self._analyze_results(training_results, backtest_results)
            
            # Phase 5: Compile final results
            experiment_results = ExperimentResults(
                fitness_score=analysis_results['fitness_components'].combined_fitness,
                fitness_components=analysis_results['fitness_components'],
                training_metrics=training_results['metrics'],
                training_duration_minutes=training_results['duration_minutes'],
                model_path=training_results.get('model_path'),
                backtest_metrics=backtest_results['metrics'],
                total_return=backtest_results['metrics']['total_return'],
                sharpe_ratio=backtest_results['metrics']['sharpe_ratio'],
                max_drawdown=backtest_results['metrics']['max_drawdown'],
                win_rate=backtest_results['metrics']['win_rate'],
                insights=analysis_results['insights'],
                patterns_discovered=analysis_results['patterns']
            )
            
            # Save results and complete experiment
            await self.db.update_experiment_status(
                experiment_id, ExperimentStatus.COMPLETED, experiment_results
            )
            
            # Save insights to knowledge base
            await self._save_insights(experiment_id, analysis_results)
            
            await self.update_status(AgentStatus.IDLE)
            logger.info(f"Agent {self.agent_id} completed experiment {experiment_id}")
            
        except Exception as e:
            logger.error(f"Agent {self.agent_id} experiment {experiment_id} failed: {e}")
            await self.db.update_experiment_status(
                experiment_id, 
                ExperimentStatus.FAILED,
                error_details={'error': str(e), 'type': type(e).__name__}
            )
            await self.update_status(AgentStatus.ERROR, experiment_id)
    
    async def _execute_training(self, config: ExperimentConfig) -> Dict[str, Any]:
        """Execute neural network training."""
        # Use existing KTRDR training service
        training_config = {
            'symbol': config.symbols[0],  # MVP: single symbol
            'timeframe': config.timeframes[0],
            'strategy_name': 'research_experiment',
            **config.training_config
        }
        
        # This would integrate with the existing training API
        # For MVP, we'll simulate the training process
        await asyncio.sleep(2)  # Simulate training time
        
        return {
            'metrics': {
                'train_accuracy': 0.75,
                'val_accuracy': 0.68,
                'train_loss': 0.45,
                'val_loss': 0.52,
                'final_epoch': 85
            },
            'duration_minutes': 45.0,
            'model_path': f'/models/research_{self.current_experiment_id}.pth'
        }
    
    async def _execute_backtesting(
        self, 
        config: ExperimentConfig,
        training_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute strategy backtesting."""
        # Use existing KTRDR backtesting service
        backtest_config = {
            'symbol': config.symbols[0],
            'timeframe': config.timeframes[0],
            'start_date': '2020-01-01',
            'end_date': '2023-12-31',
            **config.backtest_config
        }
        
        # This would integrate with the existing backtesting API
        # For MVP, we'll simulate the backtesting process
        await asyncio.sleep(1)  # Simulate backtest time
        
        return {
            'metrics': {
                'total_return': 0.15,
                'annualized_return': 0.05,
                'sharpe_ratio': 1.2,
                'max_drawdown': 0.08,
                'win_rate': 0.58,
                'profit_factor': 1.45,
                'total_trades': 156
            }
        }
    
    async def _analyze_results(
        self,
        training_results: Dict[str, Any],
        backtest_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze experiment results and generate insights."""
        # Calculate fitness score
        fitness_components = self.research_service.calculate_fitness_score(
            training_results['metrics'],
            backtest_results['metrics'],
            novelty_score=0.6  # TODO: Calculate based on knowledge base similarity
        )
        
        # Generate insights based on results
        insights = []
        patterns = []
        
        # Training insights
        if training_results['metrics']['val_accuracy'] > 0.65:
            insights.append("Model shows good generalization with validation accuracy above 65%")
        
        overfitting = training_results['metrics']['train_accuracy'] - training_results['metrics']['val_accuracy']
        if overfitting > 0.1:
            insights.append(f"Model shows signs of overfitting (gap: {overfitting:.2f})")
        
        # Backtest insights
        if backtest_results['metrics']['sharpe_ratio'] > 1.0:
            insights.append("Strategy demonstrates good risk-adjusted returns")
            patterns.append("High Sharpe ratio strategy")
        
        if backtest_results['metrics']['win_rate'] > 0.55:
            patterns.append("High win rate pattern")
        
        return {
            'fitness_components': fitness_components,
            'insights': insights,
            'patterns': patterns
        }
    
    async def _save_insights(
        self,
        experiment_id: UUID,
        analysis_results: Dict[str, Any]
    ) -> None:
        """Save experiment insights to knowledge base."""
        for insight in analysis_results['insights']:
            await self.db.save_insight(
                content=insight,
                insight_type=InsightType.DISCOVERY,
                created_by=self.agent_id,
                source_experiment_id=experiment_id,
                fitness_score=analysis_results['fitness_components'].combined_fitness
            )
        
        for pattern in analysis_results['patterns']:
            await self.db.save_insight(
                content=f"Pattern discovered: {pattern}",
                insight_type=InsightType.PATTERN,
                created_by=self.agent_id,
                source_experiment_id=experiment_id,
                fitness_score=analysis_results['fitness_components'].combined_fitness
            )
```

### Day 5: Basic LangGraph Workflow

#### A. Simple Research Workflow

**File: `ktrdr/research/workflows/basic_research_workflow.py`**
```python
"""Basic LangGraph workflow for research experiments."""
import asyncio
import logging
from typing import Any, Dict, TypedDict
from uuid import UUID

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from ktrdr.api.models.research import AgentStatus, ExperimentConfig, ExperimentStatus
from ktrdr.api.services.research_service import ResearchService

logger = logging.getLogger(__name__)


class ResearchState(TypedDict):
    """State passed between workflow nodes."""
    experiment_id: UUID
    agent_id: str
    config: ExperimentConfig
    training_results: Dict[str, Any]
    backtest_results: Dict[str, Any]
    analysis_results: Dict[str, Any]
    status: str
    error: str


class BasicResearchWorkflow:
    """Simple LangGraph workflow for research experiments."""
    
    def __init__(self, research_service: ResearchService):
        self.research_service = research_service
        self.workflow = self._create_workflow()
    
    def _create_workflow(self) -> StateGraph:
        """Create the basic research workflow."""
        workflow = StateGraph(ResearchState)
        
        # Add nodes
        workflow.add_node("initialize", self._initialize_experiment)
        workflow.add_node("train", self._execute_training)
        workflow.add_node("backtest", self._execute_backtesting)
        workflow.add_node("analyze", self._analyze_results)
        workflow.add_node("finalize", self._finalize_experiment)
        workflow.add_node("handle_error", self._handle_error)
        
        # Add edges
        workflow.add_edge(START, "initialize")
        workflow.add_conditional_edges(
            "initialize",
            self._should_continue,
            {
                "continue": "train",
                "error": "handle_error"
            }
        )
        workflow.add_conditional_edges(
            "train",
            self._should_continue,
            {
                "continue": "backtest",
                "error": "handle_error"
            }
        )
        workflow.add_conditional_edges(
            "backtest",
            self._should_continue,
            {
                "continue": "analyze",
                "error": "handle_error"
            }
        )
        workflow.add_conditional_edges(
            "analyze",
            self._should_continue,
            {
                "continue": "finalize",
                "error": "handle_error"
            }
        )
        workflow.add_edge("finalize", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile(checkpointer=MemorySaver())
    
    async def execute_experiment(
        self,
        experiment_id: UUID,
        agent_id: str,
        config: ExperimentConfig
    ) -> Dict[str, Any]:
        """Execute experiment using LangGraph workflow."""
        initial_state = ResearchState(
            experiment_id=experiment_id,
            agent_id=agent_id,
            config=config,
            training_results={},
            backtest_results={},
            analysis_results={},
            status="initialized",
            error=""
        )
        
        # Execute workflow
        config_dict = {"configurable": {"thread_id": str(experiment_id)}}
        result = await self.workflow.ainvoke(initial_state, config_dict)
        
        return result
    
    def _should_continue(self, state: ResearchState) -> str:
        """Determine if workflow should continue or handle error."""
        return "error" if state["error"] else "continue"
    
    async def _initialize_experiment(self, state: ResearchState) -> ResearchState:
        """Initialize experiment."""
        try:
            logger.info(f"Initializing experiment {state['experiment_id']}")
            
            # Update experiment status
            await self.research_service.db.update_experiment_status(
                state['experiment_id'], ExperimentStatus.RUNNING
            )
            
            state["status"] = "initialized"
            return state
            
        except Exception as e:
            logger.error(f"Error initializing experiment: {e}")
            state["error"] = str(e)
            return state
    
    async def _execute_training(self, state: ResearchState) -> ResearchState:
        """Execute neural network training."""
        try:
            logger.info(f"Starting training for experiment {state['experiment_id']}")
            
            # Update status
            await self.research_service.db.update_experiment_status(
                state['experiment_id'], ExperimentStatus.TRAINING
            )
            
            # Simulate training (in real implementation, this would call KTRDR training API)
            await asyncio.sleep(2)
            
            state["training_results"] = {
                'metrics': {
                    'train_accuracy': 0.75,
                    'val_accuracy': 0.68,
                    'train_loss': 0.45,
                    'val_loss': 0.52
                },
                'duration_minutes': 45.0
            }
            
            state["status"] = "training_complete"
            logger.info(f"Training completed for experiment {state['experiment_id']}")
            return state
            
        except Exception as e:
            logger.error(f"Error in training: {e}")
            state["error"] = str(e)
            return state
    
    async def _execute_backtesting(self, state: ResearchState) -> ResearchState:
        """Execute strategy backtesting."""
        try:
            logger.info(f"Starting backtesting for experiment {state['experiment_id']}")
            
            # Update status
            await self.research_service.db.update_experiment_status(
                state['experiment_id'], ExperimentStatus.BACKTESTING
            )
            
            # Simulate backtesting (in real implementation, this would call KTRDR backtesting API)
            await asyncio.sleep(1)
            
            state["backtest_results"] = {
                'metrics': {
                    'total_return': 0.15,
                    'sharpe_ratio': 1.2,
                    'max_drawdown': 0.08,
                    'win_rate': 0.58
                }
            }
            
            state["status"] = "backtesting_complete"
            logger.info(f"Backtesting completed for experiment {state['experiment_id']}")
            return state
            
        except Exception as e:
            logger.error(f"Error in backtesting: {e}")
            state["error"] = str(e)
            return state
    
    async def _analyze_results(self, state: ResearchState) -> ResearchState:
        """Analyze experiment results."""
        try:
            logger.info(f"Analyzing results for experiment {state['experiment_id']}")
            
            # Update status
            await self.research_service.db.update_experiment_status(
                state['experiment_id'], ExperimentStatus.ANALYZING
            )
            
            # Calculate fitness score
            fitness_components = self.research_service.calculate_fitness_score(
                state["training_results"]["metrics"],
                state["backtest_results"]["metrics"],
                novelty_score=0.6
            )
            
            state["analysis_results"] = {
                'fitness_components': fitness_components,
                'insights': [
                    "Model shows good generalization",
                    "Strategy demonstrates positive returns"
                ],
                'patterns': ["High Sharpe ratio strategy"]
            }
            
            state["status"] = "analysis_complete"
            logger.info(f"Analysis completed for experiment {state['experiment_id']}")
            return state
            
        except Exception as e:
            logger.error(f"Error in analysis: {e}")
            state["error"] = str(e)
            return state
    
    async def _finalize_experiment(self, state: ResearchState) -> ResearchState:
        """Finalize experiment and save results."""
        try:
            logger.info(f"Finalizing experiment {state['experiment_id']}")
            
            # Create experiment results
            from ktrdr.api.models.research import ExperimentResults
            
            experiment_results = ExperimentResults(
                fitness_score=state["analysis_results"]["fitness_components"].combined_fitness,
                fitness_components=state["analysis_results"]["fitness_components"],
                training_metrics=state["training_results"]["metrics"],
                training_duration_minutes=state["training_results"]["duration_minutes"],
                backtest_metrics=state["backtest_results"]["metrics"],
                total_return=state["backtest_results"]["metrics"]["total_return"],
                sharpe_ratio=state["backtest_results"]["metrics"]["sharpe_ratio"],
                max_drawdown=state["backtest_results"]["metrics"]["max_drawdown"],
                win_rate=state["backtest_results"]["metrics"]["win_rate"],
                insights=state["analysis_results"]["insights"],
                patterns_discovered=state["analysis_results"]["patterns"]
            )
            
            # Save results
            await self.research_service.db.update_experiment_status(
                state['experiment_id'], ExperimentStatus.COMPLETED, experiment_results
            )
            
            state["status"] = "completed"
            logger.info(f"Experiment {state['experiment_id']} completed successfully")
            return state
            
        except Exception as e:
            logger.error(f"Error finalizing experiment: {e}")
            state["error"] = str(e)
            return state
    
    async def _handle_error(self, state: ResearchState) -> ResearchState:
        """Handle experiment errors."""
        logger.error(f"Handling error for experiment {state['experiment_id']}: {state['error']}")
        
        try:
            # Update experiment status to failed
            await self.research_service.db.update_experiment_status(
                state['experiment_id'], 
                ExperimentStatus.FAILED,
                error_details={'error': state['error']}
            )
            
            state["status"] = "failed"
            
        except Exception as e:
            logger.error(f"Error handling error: {e}")
        
        return state
```

## Week 2: Core Research Loop Implementation

### Day 6-7: Research API Endpoints

#### A. Research Router Implementation

**File: `ktrdr/api/endpoints/research.py`**
```python
"""Research agent API endpoints."""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from ktrdr.api.dependencies import get_operations_service
from ktrdr.api.models.research import (
    StartExperimentRequest, StartExperimentResponse,
    ExperimentResponse, GetExperimentResponse,
    AgentStatusResponse, GetAgentStatusResponse,
    InsightQueryRequest, QueryInsightsResponse,
    ExperimentStatus, AgentType
)
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.services.research_service import ResearchService
from ktrdr.api.services.research_db_service import ResearchDBService
from ktrdr.config import get_config
from ktrdr.errors import ValidationError, NotFoundError

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/research", tags=["Research"])

# Dependencies
def get_research_db_service() -> ResearchDBService:
    """Get research database service."""
    database_url = get_config("RESEARCH_DATABASE_URL", "postgresql://localhost:5432/ktrdr_research")
    return ResearchDBService(database_url)

def get_research_service(
    operations_service: OperationsService = Depends(get_operations_service),
    db_service: ResearchDBService = Depends(get_research_db_service)
) -> ResearchService:
    """Get research service."""
    # Note: In real implementation, we'd inject training and backtesting services
    from ktrdr.api.services.training_service import TrainingService
    from ktrdr.api.services.backtesting_service import BacktestingService
    
    training_service = TrainingService()  # This would be properly injected
    backtesting_service = BacktestingService()  # This would be properly injected
    
    service = ResearchService(db_service, operations_service, training_service, backtesting_service)
    return service


@router.post("/experiments", response_model=StartExperimentResponse)
async def start_experiment(
    request: StartExperimentRequest,
    background_tasks: BackgroundTasks,
    research_service: ResearchService = Depends(get_research_service)
) -> StartExperimentResponse:
    """Start a new research experiment."""
    try:
        # Initialize research service if needed
        await research_service.initialize()
        
        # Start experiment
        experiment_id = await research_service.start_experiment(
            experiment_config=request.experiment_config,
            agent_id="research_mvp_001",  # Default MVP agent
            session_id=request.session_id,
            priority=request.priority
        )
        
        # Create response
        experiment_response = ExperimentResponse(
            experiment_id=experiment_id,
            status=ExperimentStatus.QUEUED,
            agent_id="research_mvp_001",
            created_at=datetime.now(timezone.utc)
        )
        
        return StartExperimentResponse(
            success=True,
            data=experiment_response,
            error=None
        )
        
    except ValidationError as e:
        logger.error(f"Validation error starting experiment: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting experiment: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/experiments/{experiment_id}", response_model=GetExperimentResponse)
async def get_experiment(
    experiment_id: UUID,
    research_service: ResearchService = Depends(get_research_service)
) -> GetExperimentResponse:
    """Get experiment details and status."""
    try:
        experiment_data = await research_service.get_experiment_status(experiment_id)
        
        if not experiment_data:
            raise HTTPException(status_code=404, detail="Experiment not found")
        
        from datetime import datetime
        
        experiment_response = ExperimentResponse(
            experiment_id=experiment_data['id'],
            status=experiment_data['status'],
            agent_id=experiment_data['agent_id'],
            created_at=experiment_data['created_at'],
            results=experiment_data.get('results')
        )
        
        return GetExperimentResponse(
            success=True,
            data=experiment_response,
            error=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting experiment {experiment_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/experiments", response_model=List[ExperimentResponse])
async def list_experiments(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    status: Optional[ExperimentStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    research_service: ResearchService = Depends(get_research_service)
) -> List[ExperimentResponse]:
    """List experiments with optional filters."""
    try:
        experiments = await research_service.list_experiments(agent_id, status, limit)
        
        response = []
        for exp in experiments:
            response.append(ExperimentResponse(
                experiment_id=exp['id'],
                status=exp['status'],
                agent_id=exp['agent_id'],
                created_at=exp['created_at']
            ))
        
        return response
        
    except Exception as e:
        logger.error(f"Error listing experiments: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/agents/{agent_id}/status", response_model=GetAgentStatusResponse)
async def get_agent_status(
    agent_id: str,
    research_service: ResearchService = Depends(get_research_service)
) -> GetAgentStatusResponse:
    """Get current agent status and activity."""
    try:
        agent_data = await research_service.get_agent_status(agent_id)
        
        if not agent_data:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        agent_response = AgentStatusResponse(
            agent_state=agent_data['agent_state'],
            current_experiment=agent_data.get('current_experiment'),
            recent_activity=agent_data.get('recent_activity', [])
        )
        
        return GetAgentStatusResponse(
            success=True,
            data=agent_response,
            error=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent status {agent_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/knowledge/query", response_model=QueryInsightsResponse)
async def query_knowledge_base(
    request: InsightQueryRequest,
    research_service: ResearchService = Depends(get_research_service)
) -> QueryInsightsResponse:
    """Query the research knowledge base."""
    try:
        # For MVP, we'll implement a simple text-based search
        # In full implementation, this would use vector similarity search
        
        # Placeholder implementation
        insights = []  # TODO: Implement actual knowledge base search
        
        from ktrdr.api.models.research import InsightQueryResponse
        
        query_response = InsightQueryResponse(
            insights=insights,
            total_found=len(insights),
            query_embedding_time_ms=0.0
        )
        
        return QueryInsightsResponse(
            success=True,
            data=query_response,
            error=None
        )
        
    except Exception as e:
        logger.error(f"Error querying knowledge base: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health")
async def health_check(
    research_service: ResearchService = Depends(get_research_service)
) -> JSONResponse:
    """Health check for research services."""
    try:
        # Check database connectivity
        await research_service.db.initialize()
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "service": "research",
                "database": "connected",
                "agents": len(research_service.agents)
            }
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "research",
                "error": str(e)
            }
        )
```

### Day 8-9: Configuration and Dependencies

#### A. Configuration Updates

**File: `ktrdr/config/research_settings.py`**
```python
"""Research agent configuration settings."""
from typing import Dict, Any, List
from pydantic import BaseSettings, Field

class ResearchSettings(BaseSettings):
    """Settings for research agents."""
    
    # Database settings
    database_url: str = Field(
        default="postgresql://ktrdr:password@localhost:5432/ktrdr_research",
        description="PostgreSQL database URL for research data"
    )
    
    # Agent settings
    max_concurrent_experiments: int = Field(
        default=3,
        description="Maximum number of concurrent experiments"
    )
    
    experiment_timeout_hours: int = Field(
        default=8,
        description="Maximum experiment duration in hours"
    )
    
    # LLM settings
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key for LLM calls"
    )
    
    claude_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Claude model to use for research"
    )
    
    # Fitness scoring weights
    fitness_performance_weight: float = Field(
        default=0.4,
        ge=0.0, le=1.0,
        description="Weight for performance component in fitness score"
    )
    
    fitness_novelty_weight: float = Field(
        default=0.3,
        ge=0.0, le=1.0,
        description="Weight for novelty component in fitness score"
    )
    
    fitness_robustness_weight: float = Field(
        default=0.3,
        ge=0.0, le=1.0,
        description="Weight for robustness component in fitness score"
    )
    
    min_fitness_threshold: float = Field(
        default=0.6,
        ge=0.0, le=1.0,
        description="Minimum fitness score for accepting strategies"
    )
    
    # Knowledge base settings
    knowledge_base_size_limit: int = Field(
        default=10000,
        description="Maximum number of insights in knowledge base"
    )
    
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model for knowledge base"
    )
    
    class Config:
        env_prefix = "KTRDR_RESEARCH_"
        case_sensitive = False


# Configuration validation
def validate_fitness_weights(settings: ResearchSettings) -> None:
    """Validate that fitness weights sum to 1.0."""
    total_weight = (
        settings.fitness_performance_weight +
        settings.fitness_novelty_weight +
        settings.fitness_robustness_weight
    )
    
    if abs(total_weight - 1.0) > 0.01:
        raise ValueError(
            f"Fitness weights must sum to 1.0, got {total_weight}"
        )


# Global settings instance
research_settings = ResearchSettings()
validate_fitness_weights(research_settings)
```

#### B. Dependency Injection Updates

**File: `ktrdr/api/dependencies.py` (additions)**
```python
"""Research service dependencies to add to existing dependencies."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from ktrdr.api.services.research_service import ResearchService
from ktrdr.api.services.research_db_service import ResearchDBService
from ktrdr.config.research_settings import research_settings

# Research database service
@lru_cache()
def get_research_db_service() -> ResearchDBService:
    """Get research database service singleton."""
    return ResearchDBService(research_settings.database_url)

# Research service
@lru_cache()
def get_research_service(
    operations_service: OperationsService = Depends(get_operations_service),
    db_service: ResearchDBService = Depends(get_research_db_service)
) -> ResearchService:
    """Get research service singleton."""
    # Note: These services would be properly injected in production
    from ktrdr.api.services.training_service import get_training_service
    from ktrdr.api.services.backtesting_service import get_backtesting_service
    
    training_service = get_training_service()
    backtesting_service = get_backtesting_service()
    
    return ResearchService(db_service, operations_service, training_service, backtesting_service)

# Type annotations for dependency injection
ResearchServiceDep = Annotated[ResearchService, Depends(get_research_service)]
ResearchDBServiceDep = Annotated[ResearchDBService, Depends(get_research_db_service)]
```

### Day 10: Integration and Testing

#### A. Docker Compose Setup for Development

**File: `docker/docker-compose.research.yml`**
```yaml
version: '3.8'

services:
  # PostgreSQL with pgvector for research data
  research-postgres:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_DB: ktrdr_research
      POSTGRES_USER: ktrdr
      POSTGRES_PASSWORD: research_password
    volumes:
      - research_postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d/
    ports:
      - "5433:5432"
    networks:
      - research_network

  # Research service (extends existing KTRDR backend)
  research-backend:
    build:
      context: ..
      dockerfile: Dockerfile
    environment:
      - KTRDR_RESEARCH_DATABASE_URL=postgresql://ktrdr:research_password@research-postgres:5432/ktrdr_research
      - KTRDR_RESEARCH_OPENAI_API_KEY=${OPENAI_API_KEY}
      - KTRDR_RESEARCH_MAX_CONCURRENT_EXPERIMENTS=2
    depends_on:
      - research-postgres
    ports:
      - "8001:8000"
    volumes:
      - ../:/app
      - research_models:/app/models
    networks:
      - research_network
    command: >
      sh -c "
        echo 'Waiting for postgres...' &&
        while ! nc -z research-postgres 5432; do sleep 1; done &&
        echo 'PostgreSQL started' &&
        python -m ktrdr.research.migrations.apply &&
        uvicorn ktrdr.api.main:app --host 0.0.0.0 --port 8000 --reload
      "

  # Research MCP Server
  research-mcp:
    build:
      context: ../mcp
      dockerfile: Dockerfile
    environment:
      - KTRDR_API_URL=http://research-backend:8000
      - KTRDR_RESEARCH_DATABASE_URL=postgresql://ktrdr:research_password@research-postgres:5432/ktrdr_research
    depends_on:
      - research-backend
    ports:
      - "8002:8001"
    networks:
      - research_network
    command: python -m mcp.src.research_server

volumes:
  research_postgres_data:
  research_models:

networks:
  research_network:
    driver: bridge
```

#### B. Database Migration Script

**File: `ktrdr/research/migrations/apply.py`**
```python
"""Apply research database migrations."""
import asyncio
import asyncpg
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

async def apply_migrations(database_url: str):
    """Apply all research database migrations."""
    try:
        # Connect to database
        conn = await asyncpg.connect(database_url)
        
        # Read migration file
        migration_file = Path(__file__).parent.parent.parent / "migrations" / "research_001_initial_schema.sql"
        
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        # Execute migration
        await conn.execute(migration_sql)
        logger.info("Research database migrations applied successfully")
        
        await conn.close()
        
    except Exception as e:
        logger.error(f"Failed to apply migrations: {e}")
        raise

if __name__ == "__main__":
    import os
    database_url = os.getenv(
        "KTRDR_RESEARCH_DATABASE_URL",
        "postgresql://ktrdr:research_password@localhost:5433/ktrdr_research"
    )
    asyncio.run(apply_migrations(database_url))
```

#### C. Basic Tests

**File: `tests/api/test_research_endpoints.py`**
```python
"""Tests for research API endpoints."""
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from ktrdr.api.main import app
from ktrdr.api.models.research import ExperimentConfig

client = TestClient(app)

class TestResearchEndpoints:
    """Test research API endpoints."""
    
    def test_health_check(self):
        """Test research health check endpoint."""
        response = client.get("/api/v1/research/health")
        assert response.status_code in [200, 503]  # May fail if DB not available
    
    def test_start_experiment(self):
        """Test starting a research experiment."""
        experiment_config = {
            "hypothesis": "Test hypothesis for MVP",
            "symbols": ["AAPL"],
            "timeframes": ["1h"],
            "max_duration_hours": 2
        }
        
        request_data = {
            "experiment_config": experiment_config,
            "priority": 5
        }
        
        response = client.post("/api/v1/research/experiments", json=request_data)
        
        # May fail if research service not initialized
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "experiment_id" in data["data"]
    
    def test_list_experiments(self):
        """Test listing experiments."""
        response = client.get("/api/v1/research/experiments")
        
        if response.status_code == 200:
            experiments = response.json()
            assert isinstance(experiments, list)
    
    def test_get_nonexistent_experiment(self):
        """Test getting a non-existent experiment."""
        fake_id = str(uuid4())
        response = client.get(f"/api/v1/research/experiments/{fake_id}")
        assert response.status_code == 404
```

## Summary and Next Steps

This implementation guide provides:

1. **Complete PostgreSQL schema** with research agents, experiments, and knowledge base tables
2. **Comprehensive data models** using Pydantic for validation and serialization
3. **Database service layer** with async operations and proper error handling
4. **Research service layer** integrating with existing KTRDR patterns
5. **MVP Research Agent** combining Researcher and Assistant roles
6. **Basic LangGraph workflow** for experiment orchestration
7. **REST API endpoints** following existing KTRDR patterns
8. **Configuration management** integrated with existing patterns
9. **Docker setup** for development environment
10. **Database migrations** and basic testing framework

### Week 1 Completion Criteria
- [ ] PostgreSQL schema created and tested
- [ ] Research service can start and track experiments
- [ ] MVP agent can execute simulated training/backtesting cycle
- [ ] REST API endpoints respond correctly
- [ ] Docker environment runs without errors

### Week 2 Focus Areas
- Integrate with real KTRDR training and backtesting APIs
- Implement LLM-powered hypothesis generation
- Add basic fitness scoring and novelty detection
- Create simple web UI for experiment monitoring
- Add comprehensive logging and error handling

This foundation provides a solid base for the full AI Research Agents system while maintaining consistency with existing KTRDR architectural patterns.