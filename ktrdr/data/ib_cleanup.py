"""
IB Connection Cleanup Utilities (Sync Version)

Simple utilities for managing sync IB connections.
Note: Sync connections are much simpler - they disconnect automatically
when out of scope or explicitly disconnected.
"""

import time
from typing import Dict, Any
from ktrdr.logging import get_logger

logger = get_logger(__name__)


class IbConnectionCleaner:
    """Utility for managing sync IB connection cleanup."""

    @staticmethod
    def cleanup_all_sync():
        """
        Sync connection cleanup.

        Note: With sync connections, cleanup is automatic through destructors.
        This method exists for CLI compatibility but doesn't need to do much.
        """
        logger.info("Sync connections clean up automatically - no action needed")
        logger.info("If you have connection issues, restart IB Gateway/TWS")

    @staticmethod
    def get_connection_status() -> Dict[str, Any]:
        """Get general connection status info."""
        return {
            "message": "Sync connections don't maintain global state",
            "recommendation": "Check IB Gateway/TWS status directly",
            "cleanup_method": "Automatic via destructors",
        }

    @staticmethod
    def print_connection_status():
        """Print status of sync connections."""
        print(f"\n📊 IB Connection Status (Sync Mode):")
        print("✅ Sync connections clean up automatically")
        print("💡 No global connection tracking needed")
        print("🔧 If issues persist, restart IB Gateway/TWS")
