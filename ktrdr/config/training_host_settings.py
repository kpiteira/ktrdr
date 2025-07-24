"""
Training Host Service Configuration.

This module provides training host service specific configuration settings.
It's a convenience module that re-exports training host settings from settings.py.
"""

from .settings import TrainingHostSettings, get_training_host_settings

__all__ = [
    "TrainingHostSettings",
    "get_training_host_settings",
]