"""
Logging management utilities for runtime control and monitoring.
"""

import logging
from typing import Dict, List

from ktrdr.logging.config import (
    get_component_log_levels,
    reset_rate_limit_state,
    reset_sampling_state,
    set_component_log_level,
)


class LogManager:
    """Runtime logging management and control."""

    def __init__(self):
        self._original_levels = {}

    def set_quiet_mode(self, enabled: bool = True) -> None:
        """
        Enable/disable quiet mode for reduced logging noise.

        Args:
            enabled: True to enable quiet mode, False to restore normal levels
        """
        if enabled:
            # Store original levels and set quiet levels
            self._original_levels = get_component_log_levels().copy()
            set_component_log_level("ib.connection", logging.ERROR)
            set_component_log_level("ib.data_fetcher", logging.WARNING)
            set_component_log_level("ib.pool", logging.WARNING)
            set_component_log_level("ib.pace_manager", logging.ERROR)
            set_component_log_level("api.middleware", logging.WARNING)

            # Reset sampling and rate limiting state
            reset_sampling_state()
            reset_rate_limit_state()

            logging.getLogger("ktrdr").info(
                "Quiet mode enabled - reduced logging verbosity"
            )
        else:
            # Restore original levels
            for component, level in self._original_levels.items():
                set_component_log_level(component, level)

            logging.getLogger("ktrdr").info(
                "Quiet mode disabled - restored normal logging"
            )

    def set_debug_mode(self, enabled: bool = True) -> None:
        """
        Enable/disable debug mode for enhanced logging.

        Args:
            enabled: True to enable debug mode, False to restore normal levels
        """
        if enabled:
            self._original_levels = get_component_log_levels().copy()
            set_component_log_level("ib.connection", logging.DEBUG)
            set_component_log_level("ib.data_fetcher", logging.DEBUG)
            set_component_log_level("ib.pool", logging.DEBUG)
            set_component_log_level("ib.pace_manager", logging.DEBUG)
            set_component_log_level("api.middleware", logging.DEBUG)

            logging.getLogger("ktrdr").info(
                "Debug mode enabled - enhanced logging verbosity"
            )
        else:
            for component, level in self._original_levels.items():
                set_component_log_level(component, level)

            logging.getLogger("ktrdr").info(
                "Debug mode disabled - restored normal logging"
            )

    def get_component_status(self) -> dict[str, str]:
        """
        Get current logging status for all components.

        Returns:
            Dictionary mapping component names to log level names
        """
        levels = get_component_log_levels()
        return {
            component: logging.getLevelName(level)
            for component, level in levels.items()
        }

    def list_noisy_loggers(self, threshold: int = 10) -> list[str]:
        """
        Identify loggers that might be generating excessive output.

        Args:
            threshold: Minimum number of log entries to consider "noisy"

        Returns:
            List of logger names that might be noisy
        """
        # This is a placeholder - in a real implementation, you'd track
        # log counts per logger over time
        potentially_noisy = [
            "ktrdr.ib.connection",
            "ktrdr.ib.data_fetcher",
            "ktrdr.ib.pool",
            "ktrdr.api.middleware",
        ]
        return potentially_noisy

    def apply_production_settings(self) -> None:
        """Apply logging settings optimized for production use."""
        set_component_log_level("ib.connection", logging.WARNING)
        set_component_log_level("ib.data_fetcher", logging.INFO)
        set_component_log_level("ib.pool", logging.INFO)
        set_component_log_level("ib.pace_manager", logging.WARNING)
        set_component_log_level("api.middleware", logging.INFO)

        logging.getLogger("ktrdr").info("Applied production logging settings")

    def apply_development_settings(self) -> None:
        """Apply logging settings optimized for development use."""
        set_component_log_level("ib.connection", logging.INFO)
        set_component_log_level("ib.data_fetcher", logging.DEBUG)
        set_component_log_level("ib.pool", logging.DEBUG)
        set_component_log_level("ib.pace_manager", logging.INFO)
        set_component_log_level("api.middleware", logging.DEBUG)

        logging.getLogger("ktrdr").info("Applied development logging settings")


# Global log manager instance
log_manager = LogManager()


def enable_quiet_mode() -> None:
    """Enable quiet mode for reduced logging noise."""
    log_manager.set_quiet_mode(True)


def disable_quiet_mode() -> None:
    """Disable quiet mode and restore normal logging."""
    log_manager.set_quiet_mode(False)


def enable_debug_mode() -> None:
    """Enable debug mode for enhanced logging."""
    log_manager.set_debug_mode(True)


def disable_debug_mode() -> None:
    """Disable debug mode and restore normal logging."""
    log_manager.set_debug_mode(False)


def get_logging_status() -> dict[str, str]:
    """Get current logging status for all components."""
    return log_manager.get_component_status()


# Import debug utilities for easy access
