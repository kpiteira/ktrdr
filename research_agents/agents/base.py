"""
Base agent class for KTRDR Research Agents

Provides common functionality for all AI agents in the research laboratory.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from ktrdr import get_logger
from ktrdr.errors import (
    ProcessingError,
    DataError,
    retry_with_backoff,
    RetryConfig
)
from ..services.database import ResearchDatabaseService, create_database_service
from ..config import ResearchAgentConfig

logger = get_logger(__name__)


# Use KTRDR's error hierarchy instead of custom exceptions
# AgentError -> ProcessingError
# AgentInitializationError -> ProcessingError with specific error code
# AgentExecutionError -> ProcessingError with specific error code


class BaseResearchAgent(ABC):
    """
    Base class for all research agents
    
    Provides common functionality including:
    - Database connectivity
    - Heartbeat management
    - State persistence
    - Error handling
    - Logging
    """
    
    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        database_url: Optional[str] = None,
        agent_config: Optional[ResearchAgentConfig] = None,
        **config
    ):
        # Configuration with defaults
        self.agent_config = agent_config or ResearchAgentConfig()
        
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.config = config
        
        # Initialize state
        self.is_running = False
        self._stop_requested = False
        self._status = "idle"
        self.current_activity = "Initializing"
        self.state_data: Dict[str, Any] = {}
        self.memory_context: Dict[str, Any] = {}
        self._error_count = 0
        self._max_errors = self.agent_config.max_consecutive_errors
        
        # Database service
        self.db: Optional[ResearchDatabaseService] = None
        self.database_url = database_url
        
        # Async tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._background_tasks: set = set()
        
        # Configure logging
        self.logger = get_logger(f"{__name__}.{agent_type}.{agent_id}")
    
    @property
    def db_service(self) -> Optional[ResearchDatabaseService]:
        """Alias for db to maintain compatibility with tests"""
        return self.db
    
    @db_service.setter
    def db_service(self, value: Optional[ResearchDatabaseService]) -> None:
        """Setter for db_service alias"""
        self.db = value
    
    def _ensure_db_available(self) -> None:
        """Ensure database service is available"""
        if not self.db:
            raise ProcessingError("Database service not initialized", error_code="DB_NOT_INITIALIZED")
    
    @property
    def status(self) -> str:
        """Get current agent status"""
        return getattr(self, '_status', 'idle')
    
    @status.setter
    def status(self, value: str) -> None:
        """Set current agent status"""
        self._status = value
    
    async def initialize(self) -> None:
        """Initialize the agent"""
        try:
            self.logger.info(f"Initializing {self.agent_type} agent: {self.agent_id}")
            
            # Initialize database connection
            if self.db is None:
                self.db = create_database_service(self.database_url)
                await self.db.initialize()
            
            # Register agent in database
            loaded_existing = await self._register_agent()
            
            # Start heartbeat
            await self._start_heartbeat()
            
            # Agent-specific initialization
            await self._initialize_agent()
            
            self.is_running = True
            
            # Only update status if we didn't load existing state
            if not loaded_existing:
                self.current_activity = "Ready"
                await self._update_status("idle", "Agent initialized and ready")
            
            self.logger.info(f"Agent {self.agent_id} initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Agent initialization failed: {e}")
            raise ProcessingError(
                "Agent initialization failed",
                error_code="AGENT_INIT_FAILED",
                details={"agent_id": self.agent_id, "agent_type": self.agent_type, "original_error": str(e)}
            ) from e
    
    async def shutdown(self) -> None:
        """Shutdown the agent gracefully"""
        try:
            self.logger.info(f"Shutting down agent: {self.agent_id}")
            
            self.is_running = False
            await self._update_status("shutdown", "Agent shutting down")
            
            # Cancel background tasks
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
            
            for task in self._background_tasks:
                task.cancel()
            
            # Agent-specific cleanup
            await self._cleanup_agent()
            
            # Close database connection
            if self.db:
                await self.db.close()
            
            self.logger.info(f"Agent {self.agent_id} shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Agent shutdown error: {e}")
    
    async def run(self) -> None:
        """Main agent execution loop"""
        try:
            if not self.is_running:
                await self.initialize()
            
            self.logger.info(f"Starting main execution loop for agent: {self.agent_id}")
            
            while self.is_running and not self._stop_requested:
                try:
                    # Execute agent-specific logic
                    await self._execute_cycle()
                    
                    # Brief pause between cycles (configurable)
                    await asyncio.sleep(self.agent_config.state_save_interval_seconds // 120)  # 1 second by default
                    
                except Exception as e:
                    self._error_count += 1
                    self.logger.error(f"Error in agent execution cycle: {e} (error {self._error_count}/{self._max_errors})")
                    await self._update_status("error", f"Execution error: {e}")
                    
                    # Stop if too many errors
                    if self._error_count >= self._max_errors:
                        self.logger.error(f"Agent stopping due to too many errors ({self._max_errors})")
                        self.is_running = False
                        raise ProcessingError(
                            f"Agent failed after {self._max_errors} consecutive errors",
                            error_code="AGENT_MAX_ERRORS_EXCEEDED",
                            details={"agent_id": self.agent_id, "error_count": self._error_count, "max_errors": self._max_errors, "last_error": str(e)}
                        ) from e
                    
                    # Brief pause before retrying (configurable)
                    await asyncio.sleep(self.agent_config.error_backoff_multiplier * 2.5)  # ~5 seconds by default
            
        except Exception as e:
            self.logger.error(f"Fatal error in agent run loop: {e}")
            raise ProcessingError(
                "Agent execution failed",
                error_code="AGENT_EXECUTION_FAILED",
                details={"agent_id": self.agent_id, "original_error": str(e)}
            ) from e
        finally:
            await self.shutdown()
    
    async def _register_agent(self) -> bool:
        """Register agent in the database"""
        """Returns True if existing state was loaded, False if new state was created"""
        try:
            self._ensure_db_available()
            
            # Check if agent already exists
            if self.db is None:
                raise ProcessingError("Database service not initialized", error_code="NO_DB")
            existing_agent = await self.db.get_agent_state(self.agent_id)
            
            if existing_agent:
                # Load existing agent state
                self._status = existing_agent["status"]
                self.current_activity = existing_agent["current_activity"]
                self.state_data = existing_agent["state_data"] or {}
                self.memory_context = existing_agent["memory_context"] or {}
                
                self.logger.info(f"Loaded existing agent state: {self.agent_id}")
                return True
            else:
                # Create new agent registration
                if self.db is None:
                    raise ProcessingError("Database service not initialized", error_code="NO_DB")
                await self.db.create_agent_state(
                    self.agent_id, self.agent_type, "idle",
                    "Agent registered", self.state_data, self.memory_context
                )
                self.logger.info(f"Registered new agent: {self.agent_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to register agent: {e}")
            raise
    
    async def _start_heartbeat(self) -> None:
        """Start the heartbeat task"""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._background_tasks.add(self._heartbeat_task)
    
    async def _heartbeat_loop(self) -> None:
        """Heartbeat loop to update agent status"""
        while self.is_running:
            try:
                if self.db is None:
                    raise ProcessingError("Database service not initialized", error_code="NO_DB")
                await self.db.update_agent_heartbeat(self.agent_id)
                await asyncio.sleep(self.agent_config.memory_cleanup_interval_seconds // 10)  # Use config-based heartbeat interval
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(self.agent_config.memory_cleanup_interval_seconds // 10)  # Use same interval on error
    
    async def _update_status(self, status: str, activity: Optional[str] = None) -> None:
        """Update agent status and activity"""
        try:
            self._ensure_db_available()
            
            if activity:
                self.current_activity = activity
            
            if self.db is None:
                raise ProcessingError("Database service not initialized", error_code="NO_DB")
            await self.db.update_agent_status(self.agent_id, status, activity)
            
        except Exception as e:
            self.logger.error(f"Failed to update agent status: {e}")
    
    async def _update_state_data(self, state_data: Dict[str, Any]) -> None:
        """Update agent state data"""
        try:
            self.state_data.update(state_data)
            if self.db is None:
                raise ProcessingError("Database service not initialized", error_code="NO_DB")
            await self.db.update_agent_state_data(self.agent_id, self.state_data)
            
        except Exception as e:
            self.logger.error(f"Failed to update agent state data: {e}")
    
    async def _add_to_memory(self, key: str, value: Any, max_size: int = 50) -> None:
        """Add item to agent memory with size limit"""
        self.memory_context[key] = value
        
        # Implement simple memory management
        if len(self.memory_context) > max_size:
            # Remove oldest entries (simple FIFO)
            oldest_key = next(iter(self.memory_context))
            del self.memory_context[oldest_key]
        
        # Update in database
        await self._update_state_data({"memory_context": self.memory_context})
    
    async def _persist_state(self) -> None:
        """Persist current agent state to database"""
        try:
            if self.db is None:
                raise ProcessingError("Database service not initialized", error_code="NO_DB")
            await self.db.update_agent_state(
                self.agent_id, self.status, self.current_activity,
                self.state_data, self.memory_context
            )
        except Exception as e:
            self.logger.error(f"Failed to persist agent state: {e}")
    
    def add_memory(self, key: str, value: Any) -> None:
        """Add item to agent memory"""
        self.memory_context[key] = value
    
    def get_memory(self, key: str) -> Any:
        """Get item from agent memory"""
        return self.memory_context.get(key)
    
    def clear_memory(self, key: str) -> None:
        """Remove item from agent memory"""
        if key in self.memory_context:
            del self.memory_context[key]
    
    async def update_activity(self, activity: str) -> None:
        """Update current activity and persist to database"""
        self.current_activity = activity
        await self._persist_state()
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """Update agent configuration"""
        self.config.update(config)
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
    
    async def stop(self) -> None:
        """Stop the agent"""
        self.is_running = False
        self._stop_requested = True
        await self._update_status("stopped", "Agent stopped")
    
    async def _send_heartbeat(self) -> None:
        """Send heartbeat to database"""
        self._ensure_db_available()
        if self.db is None:
            raise ProcessingError("Database service not initialized", error_code="NO_DB")
        await self.db.update_agent_heartbeat(self.agent_id)
    
    # ========================================================================
    # ABSTRACT METHODS - TO BE IMPLEMENTED BY SUBCLASSES
    # ========================================================================
    
    @abstractmethod
    async def _initialize_agent(self) -> None:
        """Agent-specific initialization logic"""
        pass
    
    @abstractmethod
    async def _execute_cycle(self) -> None:
        """Main agent execution cycle - called repeatedly"""
        pass
    
    @abstractmethod
    async def _cleanup_agent(self) -> None:
        """Agent-specific cleanup logic"""
        pass
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    async def get_agent_capabilities(self) -> List[str]:
        """Get agent capabilities from configuration"""
        return self.config.get("capabilities", [])
    
    async def get_agent_specialization(self) -> Optional[str]:
        """Get agent specialization from configuration"""
        return self.config.get("specialization")
    
    async def log_activity(self, activity: str, details: Optional[Dict[str, Any]] = None):
        """Log agent activity with optional details"""
        self.logger.info(f"Activity: {activity}")
        if details:
            self.logger.debug(f"Activity details: {details}")
        
        await self._add_to_memory(
            f"activity_{datetime.utcnow().isoformat()}", 
            {"activity": activity, "details": details}
        )
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(agent_id='{self.agent_id}', type='{self.agent_type}')"