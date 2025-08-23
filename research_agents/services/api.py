"""
FastAPI service for KTRDR Research Agents

Provides REST API endpoints for managing research sessions, experiments,
and agent coordination in the autonomous research laboratory.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .database import ResearchDatabaseService, create_database_service, DatabaseConfig

logger = logging.getLogger(__name__)


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class HealthResponse(BaseModel):
    """Health check response model"""

    status: str
    timestamp: datetime
    database: Dict[str, Any]
    version: str = "0.1.0"


class AgentStatus(BaseModel):
    """Agent status model"""

    agent_id: str
    agent_type: str
    status: str
    current_activity: Optional[str] = None
    last_heartbeat: datetime


class ExperimentRequest(BaseModel):
    """Request model for creating experiments"""

    experiment_name: str = Field(..., description="Name of the experiment")
    hypothesis: str = Field(..., description="Research hypothesis to test")
    experiment_type: str = Field(..., description="Type of experiment")
    configuration: Dict[str, Any] = Field(
        default_factory=dict, description="Experiment configuration"
    )
    session_id: Optional[UUID] = Field(
        None, description="Session ID (uses active session if not provided)"
    )


class ExperimentResponse(BaseModel):
    """Response model for experiments"""

    id: UUID = Field(alias="experiment_id")
    experiment_name: str
    hypothesis: str
    experiment_type: str
    status: str
    configuration: Dict[str, Any]
    results: Optional[Dict[str, Any]] = None
    fitness_score: Optional[float] = None
    assigned_agent_name: Optional[str] = None
    session_name: Optional[str] = None
    session_id: Optional[UUID] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class KnowledgeEntry(BaseModel):
    """Knowledge base entry model"""

    id: UUID
    content_type: str
    title: str
    content: str
    summary: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    quality_score: Optional[float] = None
    relevance_score: Optional[float] = None
    created_at: datetime


class KnowledgeSearchRequest(BaseModel):
    """Request model for knowledge search"""

    query: str
    content_type_filter: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=50)
    search_type: str = Field(default="keywords", description="'keywords' or 'semantic'")


class SessionStatistics(BaseModel):
    """Session statistics model"""

    total_experiments: int
    completed_experiments: int
    pending_experiments: int
    failed: int
    running: int
    queued: int
    avg_fitness: Optional[float] = None
    max_fitness: Optional[float] = None
    high_quality_results: int


class SessionRequest(BaseModel):
    """Request model for creating sessions"""

    session_name: str = Field(..., min_length=1, description="Name of the session")
    description: Optional[str] = Field(None, description="Session description")
    strategic_goals: List[str] = Field(
        default_factory=list, description="Strategic goals for the session"
    )
    priority_areas: List[str] = Field(
        default_factory=list, description="Priority research areas"
    )


class SessionResponse(BaseModel):
    """Response model for sessions"""

    session_id: UUID
    session_name: str
    description: Optional[str] = None
    status: str
    started_at: datetime
    strategic_goals: List[str] = Field(default_factory=list)
    priority_areas: List[str] = Field(default_factory=list)


class KnowledgeRequest(BaseModel):
    """Request model for creating knowledge entries"""

    content_type: str = Field(..., description="Type of knowledge content")
    title: str = Field(..., min_length=1, description="Title of the entry")
    content: str = Field(..., min_length=1, description="Main content")
    summary: Optional[str] = Field(None, description="Summary of the content")
    keywords: List[str] = Field(
        default_factory=list, description="Keywords for searchability"
    )
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    quality_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Quality score between 0 and 1"
    )


class StatusUpdateRequest(BaseModel):
    """Request model for status updates"""

    status: str = Field(..., description="New status")


class CompletionRequest(BaseModel):
    """Request model for experiment completion"""

    status: str = Field(default="completed", description="Completion status")
    results: Dict[str, Any] = Field(..., description="Experiment results")
    fitness_score: Optional[float] = Field(None, description="Calculated fitness score")


# ============================================================================
# FASTAPI APPLICATION SETUP
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    import os

    # Check if we're in testing mode
    if os.getenv("TESTING") == "1":
        # Skip database initialization in tests
        app.state.background_tasks = set()
        yield
        return

    # Startup
    logger.info("Starting Research Agents API...")

    # Initialize database service
    app.state.db = create_database_service()
    await app.state.db.initialize()

    # Start background tasks
    app.state.background_tasks = set()

    yield

    # Shutdown
    logger.info("Shutting down Research Agents API...")

    # Cancel background tasks
    for task in app.state.background_tasks:
        task.cancel()

    # Close database connections
    if hasattr(app.state, "db"):
        await app.state.db.close()


# Create the global app instance first
app = FastAPI(
    title="KTRDR Research Agents API",
    description="REST API for autonomous AI research laboratory",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    # Return the global app instance which has all routes attached
    return app


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================


async def get_database() -> ResearchDatabaseService:
    """Get database service dependency"""
    return app.state.db


# ============================================================================
# HEALTH AND STATUS ENDPOINTS
# ============================================================================


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "KTRDR Research Agents API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check(db: ResearchDatabaseService = Depends(get_database)):
    """Health check endpoint"""
    try:
        db_health = await db.health_check()

        return HealthResponse(
            status="healthy", timestamp=datetime.now(timezone.utc), database=db_health
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {e}",
        )


@app.get("/agents/status")
async def get_agents_status(db: ResearchDatabaseService = Depends(get_database)):
    """Get status of all agents"""
    try:
        agents = await db.get_active_agents()
        agent_details = [
            AgentStatus(
                agent_id=agent["agent_id"],
                agent_type=agent["agent_type"],
                status=agent["status"],
                current_activity=agent["current_activity"],
                last_heartbeat=agent["last_heartbeat"],
            )
            for agent in agents
        ]

        return {
            "active_agents": len(
                [a for a in agents if a["status"] in ["active", "processing"]]
            ),
            "total_agents": len(agents),
            "agent_details": agent_details,
        }
    except Exception as e:
        logger.error(f"Failed to get agent status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve agent status: {e}",
        )


# ============================================================================
# EXPERIMENT ENDPOINTS
# ============================================================================


@app.post(
    "/experiments",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_experiment(
    experiment: ExperimentRequest,
    background_tasks: BackgroundTasks,
    db: ResearchDatabaseService = Depends(get_database),
):
    """Create a new experiment"""
    try:
        # Get active session if session_id not provided
        session_id = experiment.session_id
        if not session_id:
            active_session = await db.get_active_session()
            if not active_session:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No active session found. Please provide session_id or start a session.",
                )
            session_id = active_session["id"]

        # Create experiment
        experiment_id = await db.create_experiment(
            session_id=session_id,
            experiment_name=experiment.experiment_name,
            hypothesis=experiment.hypothesis,
            experiment_type=experiment.experiment_type,
            configuration=experiment.configuration,
        )

        # Get created experiment details
        experiment_data = await db.get_experiment(experiment_id)

        # Add background task to notify coordinator (if implemented)
        background_tasks.add_task(notify_coordinator_new_experiment, experiment_id)

        # Create response with correct field mapping
        return {
            "experiment_id": str(experiment_data["id"]),
            "experiment_name": experiment_data["experiment_name"],
            "hypothesis": experiment_data["hypothesis"],
            "experiment_type": experiment_data["experiment_type"],
            "status": experiment_data["status"],
            "configuration": experiment_data["configuration"],
            "session_id": (
                str(experiment_data["session_id"])
                if experiment_data.get("session_id")
                else None
            ),
            "created_at": experiment_data["created_at"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create experiment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create experiment: {e}",
        )


@app.get("/experiments/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: UUID, db: ResearchDatabaseService = Depends(get_database)
):
    """Get experiment by ID"""
    try:
        experiment = await db.get_experiment(experiment_id)
        if not experiment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Experiment {experiment_id} not found",
            )

        return ExperimentResponse(**experiment)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get experiment {experiment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve experiment: {e}",
        )


@app.get("/experiments", response_model=List[ExperimentResponse])
async def list_experiments(
    session_id: Optional[UUID] = None,
    status_filter: Optional[str] = None,
    limit: int = 20,
    db: ResearchDatabaseService = Depends(get_database),
):
    """List experiments with optional filtering"""
    try:
        if session_id:
            experiments = await db.get_experiments_by_session(session_id, status_filter)
        else:
            # Get active session experiments if no session specified
            active_session = await db.get_active_session()
            if active_session:
                experiments = await db.get_experiments_by_session(
                    active_session["id"], status_filter
                )
            else:
                experiments = []

        # Apply limit
        experiments = experiments[:limit]

        return [ExperimentResponse(**exp) for exp in experiments]

    except Exception as e:
        logger.error(f"Failed to list experiments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list experiments: {e}",
        )


@app.patch("/experiments/{experiment_id}/status")
async def update_experiment_status(
    experiment_id: UUID,
    status_update: StatusUpdateRequest,
    db: ResearchDatabaseService = Depends(get_database),
):
    """Update experiment status"""
    try:
        await db.update_experiment_status(experiment_id, status_update.status)

        return {
            "message": f"Experiment {experiment_id} status updated to {status_update.status}"
        }

    except Exception as e:
        logger.error(f"Failed to update experiment status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update experiment status: {e}",
        )


@app.patch("/experiments/{experiment_id}/complete")
async def complete_experiment(
    experiment_id: UUID,
    completion: CompletionRequest,
    db: ResearchDatabaseService = Depends(get_database),
):
    """Complete an experiment with results"""
    try:
        await db.update_experiment_status(
            experiment_id,
            completion.status,
            results=completion.results,
            fitness_score=completion.fitness_score,
        )

        return {"message": f"Experiment {experiment_id} completed successfully"}

    except Exception as e:
        logger.error(f"Failed to complete experiment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete experiment: {e}",
        )


@app.get("/experiments/queue", response_model=List[ExperimentResponse])
async def get_experiment_queue(
    limit: int = 10, db: ResearchDatabaseService = Depends(get_database)
):
    """Get queued experiments ready for processing"""
    try:
        experiments = await db.get_queued_experiments(limit)
        return [ExperimentResponse(**exp) for exp in experiments]

    except Exception as e:
        logger.error(f"Failed to get experiment queue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve experiment queue: {e}",
        )


# ============================================================================
# KNOWLEDGE BASE ENDPOINTS
# ============================================================================


@app.post(
    "/knowledge", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED
)
async def create_knowledge_entry(
    knowledge: KnowledgeRequest, db: ResearchDatabaseService = Depends(get_database)
):
    """Create a new knowledge base entry"""
    try:
        entry_id = await db.add_knowledge_entry(
            content_type=knowledge.content_type,
            title=knowledge.title,
            content=knowledge.content,
            summary=knowledge.summary,
            keywords=knowledge.keywords,
            tags=knowledge.tags,
            quality_score=knowledge.quality_score,
        )

        return {
            "entry_id": str(entry_id),
            "title": knowledge.title,
            "message": "Knowledge entry created successfully",
        }

    except Exception as e:
        logger.error(f"Failed to create knowledge entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create knowledge entry: {e}",
        )


@app.get("/knowledge/{entry_id}", response_model=KnowledgeEntry)
async def get_knowledge_entry(
    entry_id: UUID, db: ResearchDatabaseService = Depends(get_database)
):
    """Get knowledge entry by ID"""
    try:
        entry = await db.execute_query(
            "SELECT * FROM research.knowledge_base WHERE id = $1", entry_id, fetch="one"
        )

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Knowledge entry {entry_id} not found",
            )

        # Parse JSON fields
        keywords = entry.get("keywords") or []
        if isinstance(keywords, str):
            import json

            keywords = json.loads(keywords)

        tags = entry.get("tags") or []
        if isinstance(tags, str):
            import json

            tags = json.loads(tags)

        return KnowledgeEntry(
            id=entry["id"],
            content_type=entry["content_type"],
            title=entry["title"],
            content=entry["content"],
            summary=entry["summary"],
            keywords=keywords,
            tags=tags,
            quality_score=entry["quality_score"],
            created_at=entry["created_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get knowledge entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve knowledge entry: {e}",
        )


@app.get("/knowledge/search", response_model=List[KnowledgeEntry])
async def search_knowledge_by_query(
    tags: Optional[str] = None,
    content_type: Optional[str] = None,
    limit: int = 10,
    db: ResearchDatabaseService = Depends(get_database),
):
    """Search knowledge base by tags or content type"""
    try:
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",")]
            results = await db.search_knowledge_by_tags(
                tags=tag_list, content_type_filter=content_type, limit=limit
            )
        else:
            # Return recent entries if no search criteria
            results = await db.execute_query(
                "SELECT * FROM research.knowledge_base ORDER BY created_at DESC LIMIT $1",
                limit,
                fetch="all",
            )

        # Parse JSON fields for each result
        processed_results = []
        for entry in results:
            keywords = entry.get("keywords") or []
            if isinstance(keywords, str):
                import json

                keywords = json.loads(keywords)

            tags_data = entry.get("tags") or []
            if isinstance(tags_data, str):
                import json

                tags_data = json.loads(tags_data)

            processed_results.append(
                KnowledgeEntry(
                    id=entry["id"],
                    content_type=entry["content_type"],
                    title=entry["title"],
                    content=entry["content"],
                    summary=entry["summary"],
                    keywords=keywords,
                    tags=tags_data,
                    quality_score=entry["quality_score"],
                    created_at=entry["created_at"],
                )
            )

        return processed_results

    except Exception as e:
        logger.error(f"Failed to search knowledge: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Knowledge search failed: {e}",
        )


@app.post("/knowledge/search", response_model=List[KnowledgeEntry])
async def search_knowledge(
    search_request: KnowledgeSearchRequest,
    db: ResearchDatabaseService = Depends(get_database),
):
    """Search knowledge base"""
    try:
        if search_request.search_type == "semantic":
            # TODO: Implement semantic search with embeddings
            # For now, fall back to keyword search
            logger.warning("Semantic search not yet implemented, using keyword search")

        # Use keyword search
        keywords = search_request.query.split()
        results = await db.search_knowledge_by_keywords(
            keywords=keywords,
            content_type_filter=search_request.content_type_filter,
            limit=search_request.limit,
        )

        return [KnowledgeEntry(**entry) for entry in results]

    except Exception as e:
        logger.error(f"Failed to search knowledge base: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Knowledge search failed: {e}",
        )


@app.get("/knowledge/experiment/{experiment_id}", response_model=List[KnowledgeEntry])
async def get_experiment_knowledge(
    experiment_id: UUID, db: ResearchDatabaseService = Depends(get_database)
):
    """Get knowledge entries generated from a specific experiment"""
    try:
        entries = await db.get_knowledge_by_source(experiment_id)
        return [KnowledgeEntry(**entry) for entry in entries]

    except Exception as e:
        logger.error(f"Failed to get experiment knowledge: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve experiment knowledge: {e}",
        )


# ============================================================================
# SESSION ENDPOINTS
# ============================================================================


@app.post(
    "/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED
)
async def create_session(
    session: SessionRequest, db: ResearchDatabaseService = Depends(get_database)
):
    """Create a new research session"""
    try:
        # Check if session name already exists
        existing_sessions = await db.execute_query(
            "SELECT id FROM research.sessions WHERE session_name = $1",
            session.session_name,
            fetch="all",
        )

        if existing_sessions:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Session with name '{session.session_name}' already exists",
            )

        session_id = await db.create_session(
            session_name=session.session_name,
            description=session.description,
            strategic_goals=session.strategic_goals,
            priority_areas=session.priority_areas,
        )

        # Get created session details
        created_session = await db.execute_query(
            "SELECT id, session_name, description, status, started_at, strategic_goals, priority_areas FROM research.sessions WHERE id = $1",
            session_id,
            fetch="one",
        )

        return SessionResponse(
            session_id=created_session["id"],
            session_name=created_session["session_name"],
            description=created_session["description"],
            status=created_session["status"],
            started_at=created_session["started_at"],
            strategic_goals=created_session.get("strategic_goals", []) or [],
            priority_areas=created_session.get("priority_areas", []) or [],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {e}",
        )


@app.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID, db: ResearchDatabaseService = Depends(get_database)
):
    """Get session by ID"""
    try:
        session = await db.execute_query(
            "SELECT id, session_name, description, status, started_at, strategic_goals, priority_areas FROM research.sessions WHERE id = $1",
            session_id,
            fetch="one",
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )

        return SessionResponse(
            session_id=session["id"],
            session_name=session["session_name"],
            description=session["description"],
            status=session["status"],
            started_at=session["started_at"],
            strategic_goals=session.get("strategic_goals", []) or [],
            priority_areas=session.get("priority_areas", []) or [],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve session: {e}",
        )


@app.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    limit: int = 20, db: ResearchDatabaseService = Depends(get_database)
):
    """List all sessions"""
    try:
        sessions = await db.execute_query(
            "SELECT id, session_name, description, status, started_at, strategic_goals, priority_areas FROM research.sessions ORDER BY started_at DESC LIMIT $1",
            limit,
            fetch="all",
        )

        return [
            SessionResponse(
                session_id=session["id"],
                session_name=session["session_name"],
                description=session["description"],
                status=session["status"],
                started_at=session["started_at"],
                strategic_goals=session.get("strategic_goals", []) or [],
                priority_areas=session.get("priority_areas", []) or [],
            )
            for session in sessions
        ]

    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sessions: {e}",
        )


@app.get("/sessions/{session_id}/experiments", response_model=List[ExperimentResponse])
async def list_experiments_by_session(
    session_id: UUID,
    status_filter: Optional[str] = None,
    limit: int = 20,
    db: ResearchDatabaseService = Depends(get_database),
):
    """List experiments by session"""
    try:
        experiments = await db.get_experiments_by_session(session_id, status_filter)
        experiments = experiments[:limit]

        return [ExperimentResponse(**exp) for exp in experiments]

    except Exception as e:
        logger.error(f"Failed to list experiments for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list experiments: {e}",
        )


@app.get("/sessions/{session_id}/statistics", response_model=SessionStatistics)
async def get_session_statistics(
    session_id: UUID, db: ResearchDatabaseService = Depends(get_database)
):
    """Get session statistics"""
    try:
        stats = await db.get_experiment_statistics(session_id)

        # Map the database response to the expected response format
        return SessionStatistics(
            total_experiments=stats["total_experiments"],
            completed_experiments=stats.get(
                "completed", stats.get("completed_experiments", 0)
            ),
            pending_experiments=stats.get(
                "queued", stats.get("pending_experiments", 0)
            ),
            failed=stats["failed"],
            running=stats["running"],
            queued=stats.get("queued", stats.get("pending_experiments", 0)),
            avg_fitness=stats["avg_fitness"],
            max_fitness=stats["max_fitness"],
            high_quality_results=stats["high_quality_results"],
        )

    except Exception as e:
        logger.error(f"Failed to get session statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve statistics: {e}",
        )


@app.get("/session/active")
async def get_active_session(db: ResearchDatabaseService = Depends(get_database)):
    """Get currently active research session"""
    try:
        session = await db.get_active_session()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No active session found"
            )

        return session

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get active session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve active session: {e}",
        )


@app.get("/analytics/experiments", response_model=SessionStatistics)
async def get_experiment_analytics(
    session_id: Optional[UUID] = None,
    db: ResearchDatabaseService = Depends(get_database),
):
    """Get experiment analytics and statistics"""
    try:
        stats = await db.get_experiment_statistics(session_id)
        return SessionStatistics(**stats)

    except Exception as e:
        logger.error(f"Failed to get experiment analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve analytics: {e}",
        )


@app.get("/analytics/knowledge")
async def get_knowledge_analytics(db: ResearchDatabaseService = Depends(get_database)):
    """Get knowledge base analytics"""
    try:
        stats = await db.get_knowledge_base_statistics()
        return stats

    except Exception as e:
        logger.error(f"Failed to get knowledge analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve knowledge analytics: {e}",
        )


# ============================================================================
# BACKGROUND TASKS
# ============================================================================


async def notify_coordinator_new_experiment(experiment_id: UUID):
    """Background task to notify coordinator of new experiment"""
    try:
        # TODO: Implement coordinator notification
        # This could be via Redis pub/sub, HTTP call, or message queue
        logger.info(f"New experiment created: {experiment_id}")

    except Exception as e:
        logger.error(f"Failed to notify coordinator of experiment {experiment_id}: {e}")


# ============================================================================
# ERROR HANDLERS
# ============================================================================


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ============================================================================
# DEVELOPMENT SERVER
# ============================================================================


def run_dev_server():
    """Run development server"""
    uvicorn.run(
        "research_agents.services.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    run_dev_server()
