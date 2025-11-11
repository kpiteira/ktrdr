"""
Worker module for KTRDR distributed operations.

This module provides the WorkerAPIBase class extracted from training-host-service,
which provides common worker infrastructure for all worker types.
"""

from ktrdr.workers.base import WorkerAPIBase

__all__ = ["WorkerAPIBase"]
