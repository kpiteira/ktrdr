"""
Data Manager modules for ktrdr data management system.

This package contains the new async DataManager that extends ServiceOrchestrator
for unified data loading, validation, and management operations.
"""

from .data_manager import DataManager

__all__ = ["DataManager"]
