"""Repository layer for database access.

Repositories provide an abstraction over database operations,
isolating persistence logic from business logic.
"""

from ktrdr.api.repositories.operations_repository import OperationsRepository

__all__ = ["OperationsRepository"]
