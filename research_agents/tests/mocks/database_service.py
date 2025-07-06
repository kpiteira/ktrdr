"""
Mock database service for testing

Provides a clean, stateful mock that maintains state in memory without SQL string matching.
"""

from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4
from datetime import datetime
from ...services.database import ResearchDatabaseService


class MockDatabaseService(ResearchDatabaseService):
    """Mock database service that maintains state in memory"""
    
    def __init__(self):
        # In-memory storage - no SQL strings needed!
        self.sessions: Dict[UUID, Dict[str, Any]] = {}
        self.experiments: Dict[UUID, Dict[str, Any]] = {}
        self.knowledge_entries: Dict[UUID, Dict[str, Any]] = {}
        self.agent_states: Dict[str, Dict[str, Any]] = {}
        
        # Call tracking for verification
        self.call_history: List[Dict[str, Any]] = []
        self.call_count = 0
        
        # Error injection for testing
        self.errors: Dict[str, Exception] = {}
    
    def set_error(self, method: str, error: Exception):
        """Set error to raise for a method"""
        self.errors[method] = error
    
    def clear_data(self):
        """Clear all stored data"""
        self.sessions.clear()
        self.experiments.clear()
        self.knowledge_entries.clear()
        self.agent_states.clear()
        self.call_history.clear()
        self.call_count = 0
    
    def _track_call(self, method: str, **kwargs):
        """Track method calls for verification"""
        self.call_count += 1
        self.call_history.append({
            "method": method,
            "call_number": self.call_count,
            "timestamp": datetime.utcnow(),
            **kwargs
        })
    
    # ========================================================================
    # SESSION OPERATIONS
    # ========================================================================
    
    async def create_session(
        self, 
        session_name: str, 
        description: Optional[str] = None,
        strategic_goals: Optional[List[str]] = None,
        priority_areas: Optional[List[str]] = None,
        coordinator_id: Optional[UUID] = None
    ) -> UUID:
        """Create a new session"""
        self._track_call("create_session", session_name=session_name)
        
        if "create_session" in self.errors:
            raise self.errors["create_session"]
        
        session_id = uuid4()
        self.sessions[session_id] = {
            "id": session_id,
            "session_name": session_name,
            "description": description,
            "status": "active",
            "started_at": datetime.utcnow(),
            "strategic_goals": strategic_goals or [],
            "priority_areas": priority_areas or [],
            "coordinator_id": coordinator_id
        }
        
        return session_id
    
    async def get_active_session(self) -> Optional[Dict[str, Any]]:
        """Get the currently active session"""
        self._track_call("get_active_session")
        
        if "get_active_session" in self.errors:
            raise self.errors["get_active_session"]
        
        # Find the most recent active session
        active_sessions = [
            session for session in self.sessions.values()
            if session["status"] == "active"
        ]
        
        if not active_sessions:
            return None
        
        # Return most recently created
        return max(active_sessions, key=lambda s: s["started_at"])
    
    # ========================================================================
    # EXPERIMENT OPERATIONS
    # ========================================================================
    
    async def create_experiment(
        self,
        session_id: UUID,
        experiment_name: str,
        hypothesis: str,
        experiment_type: str,
        configuration: Dict[str, Any],
        assigned_agent_id: Optional[UUID] = None
    ) -> UUID:
        """Create a new experiment"""
        self._track_call(
            "create_experiment", 
            session_id=str(session_id),
            experiment_name=experiment_name
        )
        
        if "create_experiment" in self.errors:
            raise self.errors["create_experiment"]
        
        experiment_id = uuid4()
        self.experiments[experiment_id] = {
            "id": experiment_id,
            "experiment_id": experiment_id,  # API expects this field
            "session_id": session_id,
            "experiment_name": experiment_name,
            "hypothesis": hypothesis,
            "experiment_type": experiment_type,
            "status": "pending",
            "configuration": configuration,
            "assigned_agent_id": assigned_agent_id,
            "created_at": datetime.utcnow(),
            "started_at": None,
            "completed_at": None,
            "results": None,
            "fitness_score": None,
            "error_details": None
        }
        
        return experiment_id
    
    async def get_experiment(self, experiment_id: UUID) -> Optional[Dict[str, Any]]:
        """Get experiment by ID"""
        self._track_call("get_experiment", experiment_id=str(experiment_id))
        
        if "get_experiment" in self.errors:
            raise self.errors["get_experiment"]
        
        return self.experiments.get(experiment_id)
    
    async def update_experiment_status(
        self,
        experiment_id: UUID,
        status: str,
        results: Optional[Dict[str, Any]] = None,
        fitness_score: Optional[float] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update experiment status and results"""
        self._track_call(
            "update_experiment_status",
            experiment_id=str(experiment_id),
            status=status
        )
        
        if "update_experiment_status" in self.errors:
            raise self.errors["update_experiment_status"]
        
        if experiment_id in self.experiments:
            exp = self.experiments[experiment_id]
            exp["status"] = status
            
            if results is not None:
                exp["results"] = results
            if fitness_score is not None:
                exp["fitness_score"] = fitness_score
            if error_details is not None:
                exp["error_details"] = error_details
            
            # Set timestamps based on status
            if status == "running" and exp["started_at"] is None:
                exp["started_at"] = datetime.utcnow()
            elif status in ("completed", "failed", "aborted"):
                exp["completed_at"] = datetime.utcnow()
    
    async def get_experiments_by_session(
        self, 
        session_id: UUID,
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get experiments for a specific session"""
        self._track_call(
            "get_experiments_by_session",
            session_id=str(session_id),
            status_filter=status_filter
        )
        
        if "get_experiments_by_session" in self.errors:
            raise self.errors["get_experiments_by_session"]
        
        session_experiments = [
            exp for exp in self.experiments.values()
            if exp["session_id"] == session_id
        ]
        
        if status_filter:
            session_experiments = [
                exp for exp in session_experiments
                if exp["status"] == status_filter
            ]
        
        # Sort by creation time, most recent first
        return sorted(session_experiments, key=lambda x: x["created_at"], reverse=True)
    
    async def get_queued_experiments(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get queued experiments ready for processing"""
        self._track_call("get_queued_experiments", limit=limit)
        
        if "get_queued_experiments" in self.errors:
            raise self.errors["get_queued_experiments"]
        
        queued = [
            exp for exp in self.experiments.values()
            if exp["status"] == "pending"
        ]
        
        # Sort by creation time, oldest first
        queued.sort(key=lambda x: x["created_at"])
        
        return queued[:limit]
    
    # ========================================================================
    # AGENT STATE OPERATIONS
    # ========================================================================
    
    async def create_agent_state(
        self,
        agent_id: str,
        agent_type: str,
        status: str,
        current_activity: str,
        state_data: Dict[str, Any],
        memory_context: Dict[str, Any]
    ) -> None:
        """Create new agent state record"""
        self._track_call("create_agent_state", agent_id=agent_id)
        
        if "create_agent_state" in self.errors:
            raise self.errors["create_agent_state"]
        
        self.agent_states[agent_id] = {
            "id": uuid4(),  # Internal database ID
            "agent_id": agent_id,
            "agent_type": agent_type,
            "status": status,
            "current_activity": current_activity,
            "state_data": state_data,
            "memory_context": memory_context,
            "last_heartbeat": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    
    async def get_agent_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent state by ID"""
        self._track_call("get_agent_state", agent_id=agent_id)
        
        if "get_agent_state" in self.errors:
            raise self.errors["get_agent_state"]
        
        return self.agent_states.get(agent_id)
    
    async def update_agent_state(
        self,
        agent_id: str,
        status: str,
        current_activity: str,
        state_data: Dict[str, Any],
        memory_context: Dict[str, Any]
    ) -> None:
        """Update complete agent state"""
        self._track_call("update_agent_state", agent_id=agent_id)
        
        if "update_agent_state" in self.errors:
            raise self.errors["update_agent_state"]
        
        if agent_id in self.agent_states:
            agent = self.agent_states[agent_id]
            agent["status"] = status
            agent["current_activity"] = current_activity
            agent["state_data"] = state_data
            agent["memory_context"] = memory_context
            agent["last_heartbeat"] = datetime.utcnow()
            agent["updated_at"] = datetime.utcnow()
    
    async def update_agent_heartbeat(self, agent_id: str) -> None:
        """Update agent's last heartbeat timestamp"""
        self._track_call("update_agent_heartbeat", agent_id=agent_id)
        
        if "update_agent_heartbeat" in self.errors:
            raise self.errors["update_agent_heartbeat"]
        
        if agent_id in self.agent_states:
            self.agent_states[agent_id]["last_heartbeat"] = datetime.utcnow()
    
    async def get_active_agents(self) -> List[Dict[str, Any]]:
        """Get all active agents"""
        self._track_call("get_active_agents")
        
        if "get_active_agents" in self.errors:
            raise self.errors["get_active_agents"]
        
        active_agents = [
            {
                "agent_id": agent["agent_id"],
                "agent_type": agent["agent_type"],
                "status": agent["status"],
                "current_activity": agent["current_activity"],
                "last_heartbeat": agent["last_heartbeat"]
            }
            for agent in self.agent_states.values()
            if agent["status"] in ("idle", "active", "processing")
        ]
        
        # Sort by agent type, then by last heartbeat
        return sorted(active_agents, key=lambda x: (x["agent_type"], x["last_heartbeat"]), reverse=True)
    
    # ========================================================================
    # KNOWLEDGE BASE OPERATIONS
    # ========================================================================
    
    async def add_knowledge_entry(
        self,
        content_type: str,
        title: str,
        content: str,
        summary: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        source_experiment_id: Optional[UUID] = None,
        source_agent_id: Optional[UUID] = None,
        quality_score: Optional[float] = None,
        embedding: Optional[List[float]] = None
    ) -> UUID:
        """Add new knowledge entry"""
        self._track_call("add_knowledge_entry", title=title)
        
        if "add_knowledge_entry" in self.errors:
            raise self.errors["add_knowledge_entry"]
        
        entry_id = uuid4()
        self.knowledge_entries[entry_id] = {
            "id": entry_id,
            "content_type": content_type,
            "title": title,
            "content": content,
            "summary": summary,
            "keywords": keywords or [],
            "tags": tags or [],
            "source_experiment_id": source_experiment_id,
            "source_agent_id": source_agent_id,
            "quality_score": quality_score,
            "relevance_score": None,
            "embedding": embedding,
            "created_at": datetime.utcnow()
        }
        
        return entry_id
    
    async def search_knowledge_by_tags(
        self,
        tags: List[str],
        content_type_filter: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search knowledge base by tags"""
        self._track_call("search_knowledge_by_tags", tags=tags)
        
        if "search_knowledge_by_tags" in self.errors:
            raise self.errors["search_knowledge_by_tags"]
        
        results = []
        for entry in self.knowledge_entries.values():
            # Check if any search tags match entry tags
            if any(tag in entry["tags"] for tag in tags):
                # Apply content type filter if specified
                if content_type_filter and entry["content_type"] != content_type_filter:
                    continue
                results.append(entry)
                
                if len(results) >= limit:
                    break
        
        # Sort by creation time, most recent first
        return sorted(results, key=lambda x: x["created_at"], reverse=True)
    
    async def search_knowledge_by_keywords(
        self,
        keywords: List[str],
        content_type_filter: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search knowledge base by keywords"""
        self._track_call("search_knowledge_by_keywords", keywords=keywords)
        
        if "search_knowledge_by_keywords" in self.errors:
            raise self.errors["search_knowledge_by_keywords"]
        
        results = []
        for entry in self.knowledge_entries.values():
            # Check if any search keywords match entry keywords
            if any(keyword in entry["keywords"] for keyword in keywords):
                # Apply content type filter if specified
                if content_type_filter and entry["content_type"] != content_type_filter:
                    continue
                results.append(entry)
                
                if len(results) >= limit:
                    break
        
        # Sort by creation time, most recent first
        return sorted(results, key=lambda x: x["created_at"], reverse=True)
    
    # ========================================================================
    # ANALYTICS AND STATISTICS
    # ========================================================================
    
    async def get_experiment_statistics(
        self, 
        session_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get experiment statistics for analytics"""
        self._track_call("get_experiment_statistics", session_id=str(session_id) if session_id else None)
        
        if "get_experiment_statistics" in self.errors:
            raise self.errors["get_experiment_statistics"]
        
        if session_id:
            experiments = [exp for exp in self.experiments.values() if exp["session_id"] == session_id]
        else:
            experiments = list(self.experiments.values())
        
        total = len(experiments)
        completed = len([exp for exp in experiments if exp["status"] == "completed"])
        failed = len([exp for exp in experiments if exp["status"] == "failed"])
        running = len([exp for exp in experiments if exp["status"] == "running"])
        queued = len([exp for exp in experiments if exp["status"] == "pending"])
        
        # Calculate fitness statistics
        fitness_scores = [exp["fitness_score"] for exp in experiments if exp["fitness_score"] is not None]
        avg_fitness = sum(fitness_scores) / len(fitness_scores) if fitness_scores else None
        max_fitness = max(fitness_scores) if fitness_scores else None
        high_quality = len([score for score in fitness_scores if score > 0.6])
        
        return {
            "total_experiments": total,
            "completed_experiments": completed,
            "pending_experiments": queued,
            "failed": failed,
            "running": running,
            "queued": queued,
            "avg_fitness": avg_fitness,
            "max_fitness": max_fitness,
            "high_quality_results": high_quality
        }
    
    # ========================================================================
    # HEALTH AND UTILITY
    # ========================================================================
    
    async def health_check(self) -> Dict[str, Any]:
        """Mock health check"""
        return {
            "status": "healthy",
            "current_time": datetime.utcnow(),
            "database": "mock_database",
            "host": "localhost",
            "sessions": len(self.sessions),
            "experiments": len(self.experiments),
            "knowledge_entries": len(self.knowledge_entries),
            "agent_states": len(self.agent_states)
        }
    
    async def initialize(self) -> None:
        """Mock initialization"""
        pass
    
    async def close(self) -> None:
        """Mock close"""
        pass
    
    # ========================================================================
    # SQL QUERY MOCKING (for API compatibility)
    # ========================================================================
    
    async def execute_query(self, query: str, *args, fetch: str = "none", **kwargs):
        """Mock SQL query execution for API compatibility"""
        self._track_call("execute_query", query=query[:50] + "...", fetch=fetch)
        
        if "execute_query" in self.errors:
            raise self.errors["execute_query"]
        
        # Handle session queries
        if "SELECT id FROM research.sessions WHERE session_name" in query and fetch == "all":
            session_name = args[0] if args else None
            if session_name:
                # Check if session name exists
                for session in self.sessions.values():
                    if session["session_name"] == session_name:
                        return [{"id": session["id"]}]
            return []  # No duplicates found
        
        elif "SELECT id, session_name, description, status, started_at" in query and fetch == "one":
            session_id = args[0] if args else None
            if session_id:
                session = self.sessions.get(session_id)
                if session:
                    return {
                        "id": session["id"],
                        "session_name": session["session_name"],
                        "description": session["description"],
                        "status": session["status"],
                        "started_at": session["started_at"],
                        "strategic_goals": session["strategic_goals"],
                        "priority_areas": session["priority_areas"]
                    }
            return None
        
        elif "SELECT id, session_name, description, status, started_at" in query and "ORDER BY started_at DESC" in query:
            # List sessions
            return sorted(self.sessions.values(), key=lambda x: x["started_at"], reverse=True)
        
        # Handle experiment queries
        elif "SELECT * FROM research.experiments WHERE id" in query and fetch == "one":
            experiment_id = args[0] if args else None
            if experiment_id:
                return self.experiments.get(experiment_id)
            return None
        
        # Handle knowledge queries
        elif "SELECT * FROM research.knowledge_base WHERE id" in query and fetch == "one":
            entry_id = args[0] if args else None
            if entry_id:
                return self.knowledge_entries.get(entry_id)
            return None
        
        elif "SELECT * FROM research.knowledge_base ORDER BY created_at DESC LIMIT" in query and fetch == "all":
            limit = int(query.split("LIMIT")[1].strip()) if "LIMIT" in query else 10
            entries = sorted(self.knowledge_entries.values(), key=lambda x: x["created_at"], reverse=True)
            return entries[:limit]
        
        # Default fallback
        if fetch == "all":
            return []
        elif fetch == "one":
            return None
        else:
            return None
    
    # ========================================================================
    # TEST HELPERS
    # ========================================================================
    
    def assert_called_with(self, method: str, **expected_kwargs):
        """Assert method was called with expected arguments"""
        calls = [call for call in self.call_history if call["method"] == method]
        assert len(calls) > 0, f"Method {method} was not called"
        
        latest_call = calls[-1]
        for key, expected_value in expected_kwargs.items():
            assert key in latest_call, f"Method {method} call missing argument: {key}"
            assert latest_call[key] == expected_value, f"Method {method} called with wrong {key}: expected {expected_value}, got {latest_call[key]}"
    
    def assert_called_once(self, method: str):
        """Assert method was called exactly once"""
        calls = [call for call in self.call_history if call["method"] == method]
        assert len(calls) == 1, f"Method {method} was called {len(calls)} times, expected 1"
    
    def get_call_count(self, method: str) -> int:
        """Get number of times method was called"""
        return len([call for call in self.call_history if call["method"] == method])