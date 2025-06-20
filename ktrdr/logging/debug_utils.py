"""
Debug utilities for troubleshooting specific issues.
"""

import logging
from ktrdr.logging.config import set_component_log_level
from ktrdr.logging import get_logger

logger = get_logger(__name__)


def enable_ib_debug_mode():
    """
    Enable enhanced debug logging for IB connection issues.

    This will show detailed connection state information, timing,
    and diagnostic data to help troubleshoot IB Gateway connectivity problems.
    """
    set_component_log_level("ib.connection", logging.DEBUG)
    set_component_log_level("ib.pool", logging.DEBUG)
    set_component_log_level("ib.data_fetcher", logging.DEBUG)

    logger.info(
        "🔧 IB DEBUG MODE ENABLED: Enhanced IB connection diagnostics activated"
    )
    logger.info("   - Connection state tracking: ON")
    logger.info("   - Request/response logging: ON")
    logger.info("   - Health check diagnostics: ON")
    logger.info("   - Performance timing: ON")


def disable_ib_debug_mode():
    """Disable IB debug mode and restore normal log levels."""
    set_component_log_level("ib.connection", logging.WARNING)
    set_component_log_level("ib.pool", logging.INFO)
    set_component_log_level("ib.data_fetcher", logging.INFO)

    logger.info("🔧 IB DEBUG MODE DISABLED: Restored normal logging levels")


def enable_api_debug_mode():
    """
    Enable enhanced debug logging for API request/response issues.
    """
    set_component_log_level("api.middleware", logging.DEBUG)
    set_component_log_level("api.endpoints", logging.DEBUG)
    set_component_log_level("api.services", logging.DEBUG)

    logger.info("🔧 API DEBUG MODE ENABLED: Enhanced API diagnostics activated")


def disable_api_debug_mode():
    """Disable API debug mode and restore normal log levels."""
    set_component_log_level("api.middleware", logging.INFO)
    set_component_log_level("api.endpoints", logging.INFO)
    set_component_log_level("api.services", logging.INFO)

    logger.info("🔧 API DEBUG MODE DISABLED: Restored normal logging levels")


def enable_full_debug_mode():
    """Enable debug logging for all components."""
    enable_ib_debug_mode()
    enable_api_debug_mode()

    logger.info("🔧 FULL DEBUG MODE ENABLED: All components set to DEBUG level")


def disable_full_debug_mode():
    """Disable debug logging for all components."""
    disable_ib_debug_mode()
    disable_api_debug_mode()

    logger.info("🔧 FULL DEBUG MODE DISABLED: All components restored to normal levels")


def show_debug_status():
    """Show current debug status for all components."""
    from ktrdr.logging.config import get_component_log_levels

    levels = get_component_log_levels()

    logger.info("🔧 DEBUG STATUS:")
    for component, level in levels.items():
        level_name = logging.getLevelName(level)
        debug_enabled = "✅" if level == logging.DEBUG else "❌"
        logger.info(f"   {debug_enabled} {component}: {level_name}")


# Convenience functions for CLI usage
def ib_debug_on():
    """Quick function to enable IB debugging."""
    enable_ib_debug_mode()


def ib_debug_off():
    """Quick function to disable IB debugging."""
    disable_ib_debug_mode()
