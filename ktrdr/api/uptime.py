"""Backend uptime tracking.

This module provides simple uptime tracking for the KTRDR API backend.
Used to provide context in error responses when workers are unavailable.
"""

import time

# Module-level start time, set during lifespan startup
_app_start_time: float = 0.0


def set_start_time() -> None:
    """Record the backend start time. Called once during lifespan startup."""
    global _app_start_time
    _app_start_time = time.time()


def get_uptime_seconds() -> float:
    """Return seconds since backend started.

    Returns:
        Uptime in seconds, rounded to 1 decimal place.
        Returns 0.0 if start time was never set.
    """
    if _app_start_time == 0.0:
        return 0.0
    return round(time.time() - _app_start_time, 1)
