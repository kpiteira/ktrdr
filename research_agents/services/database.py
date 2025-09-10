"""
Database service layer for KTRDR Research Agents

Provides async database operations with connection pooling, error handling,
and performance optimization for the research laboratory system.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional, Union
from uuid import UUID, uuid4

import asyncpg
from asyncpg import Pool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DatabaseConfig(BaseModel):
    """Database configuration settings"""

    host: str = "localhost"
    port: int = 5433
    database: str = "research_agents"
    username: str = "research_admin"
    password: str = "research_dev_password"
    min_connections: int = 5
    max_connections: int = 20
    command_timeout: int = 60
    server_settings: dict[str, str] = Field(
        default_factory=lambda: {
            "application_name": "ktrdr_research_agents",
            "search_path": "research,public",
        }
    )


class DatabaseError(Exception):
    """Base exception for database operations"""

    pass


class ConnectionError(DatabaseError):
    """Connection-related database errors"""

    pass


class QueryError(DatabaseError):
    """Query execution errors"""

    pass


class ResearchDatabaseService:
    """
    Async database service for research agents system

    Provides high-level database operations with proper connection pooling,
    error handling, and performance optimization.
    """

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.pool: Optional[Pool] = None
        self._connection_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize database connection pool"""
        try:
            async with self._connection_lock:
                if self.pool is None:
                    self.pool = await asyncpg.create_pool(
                        host=self.config.host,
                        port=self.config.port,
                        database=self.config.database,
                        user=self.config.username,
                        password=self.config.password,
                        min_size=self.config.min_connections,
                        max_size=self.config.max_connections,
                        command_timeout=self.config.command_timeout,
                        server_settings=self.config.server_settings,
                    )
                    logger.info(
                        f"Database pool initialized with {self.config.min_connections}-{self.config.max_connections} connections"
                    )

        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise ConnectionError(f"Database initialization failed: {e}") from e

    async def close(self) -> None:
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database pool closed")

    @asynccontextmanager
    async def get_connection(self):
        """Get a database connection from the pool"""
        if not self.pool:
            await self.initialize()

        try:
            async with self.pool.acquire() as connection:
                yield connection
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise ConnectionError(f"Failed to acquire database connection: {e}") from e

    async def execute_query(
        self, query: str, *args, fetch: str = "none"
    ) -> Union[list[dict[str, Any]], dict[str, Any], None]:
        """
        Execute a database query with proper error handling

        Args:
            query: SQL query string
            *args: Query parameters
            fetch: "none", "one", "all", or "val"

        Returns:
            Query results based on fetch type
        """
        try:
            async with self.get_connection() as conn:
                if fetch == "all":
                    rows = await conn.fetch(query, *args)
                    return [dict(row) for row in rows]
                elif fetch == "one":
                    row = await conn.fetchrow(query, *args)
                    return dict(row) if row else None
                elif fetch == "val":
                    return await conn.fetchval(query, *args)
                else:  # fetch == "none"
                    await conn.execute(query, *args)
                    return None

        except Exception as e:
            logger.error(f"Query execution failed: {query[:100]}... Error: {e}")
            raise QueryError(f"Query failed: {e}") from e

    # ========================================================================
    # AGENT STATE OPERATIONS
    # ========================================================================

    async def get_agent_state(self, agent_id: str) -> Optional[dict[str, Any]]:
        """Get agent state by ID"""
        query = """
        SELECT id, agent_id, agent_type, status, current_activity,
               state_data, memory_context, last_heartbeat, created_at, updated_at
        FROM research.agent_states
        WHERE agent_id = $1
        """
        return await self.execute_query(query, agent_id, fetch="one")

    async def update_agent_heartbeat(self, agent_id: str) -> None:
        """Update agent's last heartbeat timestamp"""
        query = """
        UPDATE research.agent_states
        SET last_heartbeat = NOW()
        WHERE agent_id = $1
        """
        await self.execute_query(query, agent_id)

    async def create_agent_state(
        self,
        agent_id: str,
        agent_type: str,
        status: str,
        current_activity: str,
        state_data: dict[str, Any],
        memory_context: dict[str, Any],
    ) -> None:
        """Create new agent state record"""
        query = """
        INSERT INTO research.agent_states (
            agent_id, agent_type, status, current_activity,
            state_data, memory_context
        ) VALUES ($1, $2, $3, $4, $5, $6)
        """
        await self.execute_query(
            query,
            agent_id,
            agent_type,
            status,
            current_activity,
            json.dumps(state_data),
            json.dumps(memory_context),
        )

    async def update_agent_state(
        self,
        agent_id: str,
        status: str,
        current_activity: str,
        state_data: dict[str, Any],
        memory_context: dict[str, Any],
    ) -> None:
        """Update complete agent state"""
        query = """
        UPDATE research.agent_states
        SET status = $2, current_activity = $3, state_data = $4,
            memory_context = $5, last_heartbeat = NOW()
        WHERE agent_id = $1
        """
        await self.execute_query(
            query,
            agent_id,
            status,
            current_activity,
            json.dumps(state_data),
            json.dumps(memory_context),
        )

    async def update_agent_status(
        self, agent_id: str, status: str, activity: Optional[str] = None
    ) -> None:
        """Update agent status and current activity"""
        if activity is not None:
            query = """
            UPDATE research.agent_states
            SET status = $2, current_activity = $3, last_heartbeat = NOW()
            WHERE agent_id = $1
            """
            await self.execute_query(query, agent_id, status, activity)
        else:
            query = """
            UPDATE research.agent_states
            SET status = $2, last_heartbeat = NOW()
            WHERE agent_id = $1
            """
            await self.execute_query(query, agent_id, status)

    async def update_agent_state_data(
        self, agent_id: str, state_data: dict[str, Any]
    ) -> None:
        """Update agent's state data"""
        query = """
        UPDATE research.agent_states
        SET state_data = $2, last_heartbeat = NOW()
        WHERE agent_id = $1
        """
        await self.execute_query(query, agent_id, json.dumps(state_data))

    async def get_active_agents(self) -> list[dict[str, Any]]:
        """Get all active agents"""
        query = """
        SELECT agent_id, agent_type, status, current_activity, last_heartbeat
        FROM research.agent_states
        WHERE status IN ('idle', 'active', 'processing')
        ORDER BY agent_type, last_heartbeat DESC
        """
        return await self.execute_query(query, fetch="all")

    # ========================================================================
    # EXPERIMENT OPERATIONS
    # ========================================================================

    async def create_experiment(
        self,
        session_id: UUID,
        experiment_name: str,
        hypothesis: str,
        experiment_type: str,
        configuration: dict[str, Any],
        assigned_agent_id: Optional[UUID] = None,
    ) -> UUID:
        """Create a new experiment"""
        experiment_id = uuid4()
        query = """
        INSERT INTO research.experiments (
            id, session_id, experiment_name, hypothesis, experiment_type,
            configuration, assigned_agent_id, status
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'queued')
        RETURNING id
        """

        result = await self.execute_query(
            query,
            experiment_id,
            session_id,
            experiment_name,
            hypothesis,
            experiment_type,
            json.dumps(configuration),
            assigned_agent_id,
            fetch="val",
        )
        return result

    async def get_experiment(self, experiment_id: UUID) -> Optional[dict[str, Any]]:
        """Get experiment by ID"""
        query = """
        SELECT e.*, s.session_name, a.agent_id as assigned_agent_name
        FROM research.experiments e
        LEFT JOIN research.sessions s ON e.session_id = s.id
        LEFT JOIN research.agent_states a ON e.assigned_agent_id = a.id
        WHERE e.id = $1
        """
        return await self.execute_query(query, experiment_id, fetch="one")

    async def update_experiment_status(
        self,
        experiment_id: UUID,
        status: str,
        results: Optional[dict[str, Any]] = None,
        fitness_score: Optional[float] = None,
        error_details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Update experiment status and results"""

        # Build dynamic query based on provided parameters
        set_clauses = ["status = $2"]
        params = [experiment_id, status]
        param_count = 2

        if results is not None:
            param_count += 1
            set_clauses.append(f"results = ${param_count}")
            params.append(json.dumps(results))

        if fitness_score is not None:
            param_count += 1
            set_clauses.append(f"fitness_score = ${param_count}")
            params.append(fitness_score)

        if error_details is not None:
            param_count += 1
            set_clauses.append(f"error_details = ${param_count}")
            params.append(json.dumps(error_details))

        # Set appropriate timestamp based on status
        if status == "running":
            set_clauses.append("started_at = NOW()")
        elif status in ("completed", "failed", "aborted"):
            set_clauses.append("completed_at = NOW()")

        query = f"""
        UPDATE research.experiments
        SET {", ".join(set_clauses)}
        WHERE id = $1
        """

        await self.execute_query(query, *params)

    async def get_queued_experiments(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get queued experiments ready for processing"""
        query = """
        SELECT e.*, s.session_name
        FROM research.experiments e
        JOIN research.sessions s ON e.session_id = s.id
        WHERE e.status = 'queued' AND s.status = 'active'
        ORDER BY e.created_at ASC
        LIMIT $1
        """
        return await self.execute_query(query, limit, fetch="all")

    async def get_experiments_by_session(
        self, session_id: UUID, status_filter: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Get experiments for a specific session"""
        if status_filter:
            query = """
            SELECT e.*, a.agent_id as assigned_agent_name
            FROM research.experiments e
            LEFT JOIN research.agent_states a ON e.assigned_agent_id = a.id
            WHERE e.session_id = $1 AND e.status = $2
            ORDER BY e.created_at DESC
            """
            return await self.execute_query(
                query, session_id, status_filter, fetch="all"
            )
        else:
            query = """
            SELECT e.*, a.agent_id as assigned_agent_name
            FROM research.experiments e
            LEFT JOIN research.agent_states a ON e.assigned_agent_id = a.id
            WHERE e.session_id = $1
            ORDER BY e.created_at DESC
            """
            return await self.execute_query(query, session_id, fetch="all")

    # ========================================================================
    # KNOWLEDGE BASE OPERATIONS
    # ========================================================================

    async def add_knowledge_entry(
        self,
        content_type: str,
        title: str,
        content: str,
        summary: Optional[str] = None,
        keywords: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        source_experiment_id: Optional[UUID] = None,
        source_agent_id: Optional[UUID] = None,
        quality_score: Optional[float] = None,
        embedding: Optional[list[float]] = None,
    ) -> UUID:
        """Add new knowledge entry"""

        entry_id = uuid4()

        # Convert embedding to vector format if provided
        embedding_vector = None
        if embedding:
            embedding_vector = f"[{','.join(map(str, embedding))}]"

        query = """
        INSERT INTO research.knowledge_base (
            id, content_type, title, content, summary, keywords, tags,
            source_experiment_id, source_agent_id, quality_score, embedding
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING id
        """

        result = await self.execute_query(
            query,
            entry_id,
            content_type,
            title,
            content,
            summary,
            keywords or [],
            tags or [],
            source_experiment_id,
            source_agent_id,
            quality_score,
            embedding_vector,
            fetch="val",
        )
        return result

    async def search_knowledge_by_similarity(
        self,
        query_embedding: list[float],
        content_type_filter: Optional[str] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Search knowledge base using vector similarity"""

        embedding_vector = f"[{','.join(map(str, query_embedding))}]"

        if content_type_filter:
            query = """
            SELECT kb.*, (1 - (kb.embedding <=> $1::vector)) as similarity_score
            FROM research.knowledge_base kb
            WHERE kb.content_type = $2
              AND kb.embedding IS NOT NULL
              AND (1 - (kb.embedding <=> $1::vector)) >= $3
            ORDER BY kb.embedding <=> $1::vector
            LIMIT $4
            """
            return await self.execute_query(
                query,
                embedding_vector,
                content_type_filter,
                similarity_threshold,
                limit,
                fetch="all",
            )
        else:
            query = """
            SELECT kb.*, (1 - (kb.embedding <=> $1::vector)) as similarity_score
            FROM research.knowledge_base kb
            WHERE kb.embedding IS NOT NULL
              AND (1 - (kb.embedding <=> $1::vector)) >= $2
            ORDER BY kb.embedding <=> $1::vector
            LIMIT $3
            """
            return await self.execute_query(
                query, embedding_vector, similarity_threshold, limit, fetch="all"
            )

    async def search_knowledge_by_keywords(
        self,
        keywords: list[str],
        content_type_filter: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search knowledge base by keywords"""

        if content_type_filter:
            query = """
            SELECT * FROM research.knowledge_base
            WHERE content_type = $1 AND keywords && $2
            ORDER BY created_at DESC
            LIMIT $3
            """
            return await self.execute_query(
                query, content_type_filter, keywords, limit, fetch="all"
            )
        else:
            query = """
            SELECT * FROM research.knowledge_base
            WHERE keywords && $1
            ORDER BY created_at DESC
            LIMIT $2
            """
            return await self.execute_query(query, keywords, limit, fetch="all")

    async def search_knowledge_by_tags(
        self,
        tags: list[str],
        content_type_filter: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search knowledge base by tags (alias for search_knowledge_by_keywords)"""
        return await self.search_knowledge_by_keywords(tags, content_type_filter, limit)

    async def get_knowledge_by_source(
        self, source_experiment_id: UUID
    ) -> list[dict[str, Any]]:
        """Get knowledge entries generated from a specific experiment"""
        query = """
        SELECT * FROM research.knowledge_base
        WHERE source_experiment_id = $1
        ORDER BY created_at DESC
        """
        return await self.execute_query(query, source_experiment_id, fetch="all")

    # ========================================================================
    # SESSION OPERATIONS
    # ========================================================================

    async def get_active_session(self) -> Optional[dict[str, Any]]:
        """Get the currently active research session"""
        query = """
        SELECT s.*, a.agent_id as coordinator_name
        FROM research.sessions s
        LEFT JOIN research.agent_states a ON s.coordinator_id = a.id
        WHERE s.status = 'active'
        ORDER BY s.started_at DESC
        LIMIT 1
        """
        return await self.execute_query(query, fetch="one")

    async def create_session(
        self,
        session_name: str,
        description: Optional[str] = None,
        strategic_goals: Optional[list[str]] = None,
        priority_areas: Optional[list[str]] = None,
        coordinator_id: Optional[UUID] = None,
    ) -> UUID:
        """Create a new research session"""

        session_id = uuid4()
        query = """
        INSERT INTO research.sessions (
            id, session_name, description, strategic_goals,
            priority_areas, coordinator_id
        ) VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """

        result = await self.execute_query(
            query,
            session_id,
            session_name,
            description,
            json.dumps(strategic_goals or []),
            json.dumps(priority_areas or []),
            coordinator_id,
            fetch="val",
        )
        return result

    # ========================================================================
    # ANALYTICS AND REPORTING
    # ========================================================================

    async def get_experiment_statistics(
        self, session_id: Optional[UUID] = None
    ) -> dict[str, Any]:
        """Get experiment statistics for analytics"""

        base_query = """
        SELECT
            COUNT(*) as total_experiments,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
            COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
            COUNT(CASE WHEN status = 'running' THEN 1 END) as running,
            COUNT(CASE WHEN status = 'queued' THEN 1 END) as queued,
            AVG(CASE WHEN fitness_score IS NOT NULL THEN fitness_score END) as avg_fitness,
            MAX(fitness_score) as max_fitness,
            COUNT(CASE WHEN fitness_score > 0.6 THEN 1 END) as high_quality_results
        FROM research.experiments
        """

        if session_id:
            query = base_query + " WHERE session_id = $1"
            result = await self.execute_query(query, session_id, fetch="one")
        else:
            result = await self.execute_query(base_query, fetch="one")

        return result

    async def get_knowledge_base_statistics(self) -> dict[str, Any]:
        """Get knowledge base statistics"""
        query = """
        SELECT
            COUNT(*) as total_entries,
            COUNT(DISTINCT content_type) as content_types,
            AVG(quality_score) as avg_quality,
            COUNT(CASE WHEN validation_status = 'validated' THEN 1 END) as validated_entries,
            COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as entries_with_embeddings
        FROM research.knowledge_base
        """
        return await self.execute_query(query, fetch="one")

    async def health_check(self) -> dict[str, Any]:
        """Perform database health check"""
        try:
            # Test basic connectivity
            result = await self.execute_query(
                "SELECT NOW() as current_time", fetch="one"
            )

            # Test pool status
            pool_info = {
                "size": self.pool.get_size() if self.pool else 0,
                "idle": self.pool.get_idle_size() if self.pool else 0,
                "max_size": self.config.max_connections,
                "min_size": self.config.min_connections,
            }

            return {
                "status": "healthy",
                "current_time": result["current_time"],
                "pool_info": pool_info,
                "database": self.config.database,
                "host": self.config.host,
            }

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "database": self.config.database,
                "host": self.config.host,
            }


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================


def create_database_service(
    database_url: Optional[str] = None, **config_overrides
) -> ResearchDatabaseService:
    """
    Factory function to create a database service instance

    Args:
        database_url: PostgreSQL connection URL (optional)
        **config_overrides: Override default configuration
    """

    if database_url:
        # Parse database URL if provided
        # Format: postgresql://user:password@host:port/database
        import urllib.parse as urlparse

        parsed = urlparse.urlparse(database_url)

        config = DatabaseConfig(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5433,
            database=parsed.path.lstrip("/") if parsed.path else "research_agents",
            username=parsed.username or "research_admin",
            password=parsed.password or "research_dev_password",
            **config_overrides,
        )
    else:
        config = DatabaseConfig(**config_overrides)

    return ResearchDatabaseService(config)


# ============================================================================
# ASYNC CONTEXT MANAGER FOR EASY USAGE
# ============================================================================


@asynccontextmanager
async def get_database_service(database_url: Optional[str] = None, **config_overrides):
    """
    Async context manager for database service

    Usage:
        async with get_database_service() as db:
            result = await db.get_active_session()
    """

    db_service = create_database_service(database_url, **config_overrides)
    try:
        await db_service.initialize()
        yield db_service
    finally:
        await db_service.close()
