"""
Service Orchestrator modules for ktrdr management system.

This package contains the ServiceOrchestrator base class and common patterns
for all service managers (Data, Training, Backtesting, etc.).
"""

from .base import ServiceOrchestrator

__all__ = ["ServiceOrchestrator"]
