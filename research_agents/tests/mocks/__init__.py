"""
Test doubles for research agents services

Provides clean, stateful mocks that implement the same interfaces as production services.
"""

from .llm_service import MockLLMService
from .ktrdr_service import MockKTRDRService  
from .database_service import MockDatabaseService

__all__ = ["MockLLMService", "MockKTRDRService", "MockDatabaseService"]