"""Logging utilities for neural network models."""

# This is a compatibility module to fix import errors
# Redirect to the main logging system

from ..logging import get_logger

__all__ = ["get_logger"]
