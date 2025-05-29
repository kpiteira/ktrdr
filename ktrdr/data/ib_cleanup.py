"""
IB Connection Cleanup Utilities

Utilities for managing and cleaning up IB connections to prevent
connection exhaustion and ensure proper resource management.
"""

import asyncio
import time
from typing import List, Dict, Any
from ktrdr.data.ib_connection import IbConnectionManager
from ktrdr.logging import get_logger

logger = get_logger(__name__)


class IbConnectionCleaner:
    """Utility for managing IB connection cleanup."""
    
    @staticmethod
    async def cleanup_all():
        """Clean up all active IB connections."""
        logger.info("Starting IB connection cleanup...")
        
        # Get connection count before cleanup
        before_count = IbConnectionManager.get_connection_count()
        
        if before_count > 0:
            logger.info(f"Found {before_count} active connections")
            await IbConnectionManager.cleanup_all_connections()
            
            # Give IB Gateway a moment to process disconnections
            await asyncio.sleep(1)
            
            after_count = IbConnectionManager.get_connection_count()
            logger.info(f"Cleanup complete: {before_count - after_count} connections closed")
        else:
            logger.info("No active connections to clean up")
            
    @staticmethod
    def cleanup_all_sync():
        """Synchronous wrapper for cleanup_all."""
        from ib_insync import util
        util.run(IbConnectionCleaner.cleanup_all())
        
    @staticmethod
    def get_connection_status() -> Dict[str, Any]:
        """Get status of all active connections."""
        connections = IbConnectionManager.get_active_connections()
        
        status = {
            "total_connections": len(connections),
            "connections": []
        }
        
        for conn_id, connection in connections.items():
            conn_status = {
                "id": conn_id,
                "host": connection.config.host,
                "port": connection.config.port,
                "client_id": connection.config.client_id,
                "connected": connection._connected,
                "is_closing": connection.is_closing,
                "metrics": connection.metrics
            }
            status["connections"].append(conn_status)
            
        return status
        
    @staticmethod
    def print_connection_status():
        """Print status of all active connections."""
        status = IbConnectionCleaner.get_connection_status()
        
        print(f"\n📊 IB Connection Status:")
        print(f"Total active connections: {status['total_connections']}")
        
        if status["connections"]:
            print("\nConnection Details:")
            for conn in status["connections"]:
                print(f"  🔗 {conn['id']}")
                print(f"     Connected: {conn['connected']}")
                print(f"     Closing: {conn['is_closing']}")
                print(f"     Total attempts: {conn['metrics'].get('total_connections', 0)}")
        else:
            print("No active connections")
            
    @staticmethod
    async def wait_for_cleanup(max_wait_seconds: int = 10):
        """Wait for all connections to be cleaned up."""
        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            count = IbConnectionManager.get_connection_count()
            if count == 0:
                logger.info("All connections cleaned up successfully")
                return True
                
            logger.debug(f"Waiting for {count} connections to close...")
            await asyncio.sleep(0.5)
            
        remaining = IbConnectionManager.get_connection_count()
        if remaining > 0:
            logger.warning(f"Timeout waiting for cleanup: {remaining} connections still active")
            return False
        return True


# Convenience functions
async def cleanup_ib_connections():
    """Clean up all IB connections (async)."""
    await IbConnectionCleaner.cleanup_all()


def cleanup_ib_connections_sync():
    """Clean up all IB connections (sync)."""
    IbConnectionCleaner.cleanup_all_sync()


def show_ib_connection_status():
    """Show current IB connection status."""
    IbConnectionCleaner.print_connection_status()