"""
IB Context Manager

Provides context-aware IB operations that work correctly in both:
- FastAPI async context (force-triggered operations)
- Background thread context (normal gap filling)

This module detects the execution context and uses the appropriate
synchronous or asynchronous IB calls accordingly.
"""

import asyncio
import threading
from typing import Optional, Union
from datetime import datetime
import pandas as pd

from ktrdr.logging import get_logger
from ktrdr.data.ib_connection_sync import IbConnectionSync
from ktrdr.errors import DataError

logger = get_logger(__name__)


class IbContextManager:
    """
    Context-aware IB operations manager.
    
    This class detects whether it's running in:
    1. FastAPI async context (with running event loop)
    2. Background thread context (no event loop)
    
    And uses the appropriate IB calling method for each context.
    """
    
    def __init__(self, connection: IbConnectionSync):
        """Initialize with an IB connection."""
        self.connection = connection
        self.ib = connection.ib
    
    def _detect_context(self) -> str:
        """
        Detect the current execution context.
        
        Returns:
            'async_context': Running in FastAPI with active event loop
            'thread_context': Running in background thread, no event loop
            'unknown': Unable to determine context
        """
        try:
            # Check if we're in an async context
            loop = asyncio.get_running_loop()
            if loop and loop.is_running():
                # We're in an async context (FastAPI)
                return 'async_context'
        except RuntimeError:
            # No running event loop - we're in a thread context
            return 'thread_context'
        
        return 'unknown'
    
    def _is_main_thread(self) -> bool:
        """Check if we're running in the main thread."""
        return threading.current_thread() is threading.main_thread()
    
    def fetch_historical_data(
        self, 
        symbol: str, 
        timeframe: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical data with improved callback handling and reduced threading complexity.
        
        This method uses a simplified approach that avoids event loop conflicts
        and properly handles IB's callback-based architecture.
        
        Args:
            symbol: Symbol to fetch
            timeframe: Timeframe (e.g., '1h', '1d')
            start_date: Start datetime
            end_date: End datetime
            
        Returns:
            DataFrame with historical data or None if failed
        """
        context = self._detect_context()
        logger.debug(f"Detected context: {context} for {symbol} {timeframe}")
        
        try:
            # Use direct sync approach with improved error handling
            # This avoids complex threading that can interfere with IB callbacks
            return self._fetch_direct_sync(symbol, timeframe, start_date, end_date)
                
        except Exception as e:
            logger.error(f"Error fetching {symbol} {timeframe}: {e}")
            return None
    
    def _fetch_direct_sync(
        self, 
        symbol: str, 
        timeframe: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Direct synchronous fetch that properly handles background thread contexts.
        
        This detects if we're in a background thread and creates appropriate event loop.
        """
        context = self._detect_context()
        logger.info(f"🔄 Direct sync fetch for {symbol} {timeframe} (context: {context})")
        
        # Background threads need their own IB connection due to event loop isolation
        try:
            from ktrdr.data.ib_connection_sync import IbConnectionSync, ConnectionConfig
            from ktrdr.data.ib_data_fetcher_sync import IbDataFetcherSync
            import threading
            import time
            
            # Create unique client ID for this thread to avoid conflicts
            thread_id = threading.current_thread().ident
            unique_client_id = 200 + (thread_id % 100)  # Range 200-299 for background threads
            
            temp_config = ConnectionConfig(
                host=self.connection.config.host,
                port=self.connection.config.port,
                client_id=unique_client_id,
                timeout=self.connection.config.timeout,
                readonly=self.connection.config.readonly
            )
            
            logger.info(f"📡 Creating thread-specific IB connection for {symbol} (client_id={unique_client_id})")
            temp_connection = IbConnectionSync(temp_config)
            
            if temp_connection.is_connected():
                # Use the thread-specific connection for data fetching
                fetcher = IbDataFetcherSync(temp_connection)
                data = fetcher.fetch_historical_data(symbol, timeframe, start_date, end_date)
                
                # Clean up thread-specific connection
                temp_connection.disconnect()
                
                if data is not None and not data.empty:
                    logger.info(f"✅ Successfully fetched {len(data)} bars for {symbol} {timeframe}")
                    return data
                else:
                    logger.warning(f"📭 No data returned for {symbol} {timeframe}")
                    return None
            else:
                logger.error(f"Failed to create thread-specific connection for {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error with thread-specific connection for {symbol} {timeframe}: {e}")
            return None
    
    def _fetch_sync_in_async_context(
        self, 
        symbol: str, 
        timeframe: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Fetch data when called from FastAPI async context.
        
        In this context, we can't create a new event loop, so we use
        the existing IB connection's synchronous methods.
        """
        from ktrdr.data.ib_data_fetcher_sync import IbDataFetcherSync
        
        try:
            # Use the existing sync data fetcher but avoid any async calls
            fetcher = IbDataFetcherSync(self.connection)
            
            # Call the fetch method but handle it specially for async context
            return self._call_fetcher_sync_only(fetcher, symbol, timeframe, start_date, end_date)
            
        except Exception as e:
            logger.error(f"Error in async context fetch: {e}")
            return None
    
    def _fetch_sync_in_thread_context(
        self, 
        symbol: str, 
        timeframe: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Fetch data when called from background thread context.
        
        Uses the existing IB connection's event loop instead of creating a new one.
        """
        try:
            logger.info(f"🔄 Starting IB data fetch for {symbol} {timeframe} in background thread")
            
            # Use the existing connection's IB instance directly
            # This avoids creating new event loops that conflict
            from ktrdr.data.ib_data_fetcher_sync import IbDataFetcherSync
            
            logger.info(f"📡 Requesting data from IB for {symbol} {timeframe} ({start_date} to {end_date})")
            
            # Check if connection has an active event loop
            if not self.connection.is_connected():
                logger.error(f"IB connection not active for {symbol} {timeframe}")
                return None
            
            # Try to use the connection's existing event loop context
            ib = self.connection.ib
            
            # Create a fresh IB connection for this thread to avoid event loop conflicts
            try:
                from ktrdr.data.ib_connection_sync import IbConnectionSync, ConnectionConfig
                from ktrdr.data.ib_data_fetcher_sync import IbDataFetcherSync
                
                # Create a temporary connection with a different client ID
                temp_config = ConnectionConfig(
                    host=self.connection.config.host,
                    port=self.connection.config.port,
                    client_id=self.connection.config.client_id + 100,  # Offset to avoid conflicts
                    timeout=self.connection.config.timeout,
                    readonly=self.connection.config.readonly
                )
                
                logger.debug(f"Creating temporary IB connection for {symbol} with client ID {temp_config.client_id}")
                temp_connection = IbConnectionSync(temp_config)
                
                if temp_connection.is_connected():
                    # Use the temporary connection for data fetching
                    fetcher = IbDataFetcherSync(temp_connection)
                    data = fetcher.fetch_historical_data(symbol, timeframe, start_date, end_date)
                    
                    # Clean up temporary connection
                    temp_connection.disconnect()
                    
                    if data is not None and not data.empty:
                        logger.info(f"✅ Successfully fetched {len(data)} bars for {symbol} {timeframe}")
                        return data
                    else:
                        logger.warning(f"📭 No data returned for {symbol} {timeframe}")
                        return None
                else:
                    logger.error(f"Failed to create temporary connection for {symbol}")
                    return None
                    
            except Exception as ib_error:
                logger.error(f"IB operation failed for {symbol} {timeframe}: {ib_error}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error in background thread fetch for {symbol} {timeframe}: {e}")
            return None
    
    def _call_fetcher_sync_only(
        self, 
        fetcher, 
        symbol: str, 
        timeframe: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Call the data fetcher in a way that avoids all async operations.
        
        This is a workaround for FastAPI contexts where we can't use
        any async IB operations.
        """
        import threading
        import queue
        
        result_queue: queue.Queue = queue.Queue()
        
        def fetch_in_thread():
            """Run the fetch operation in a separate thread with its own event loop."""
            try:
                # This thread will have no event loop, so normal sync fetcher will work
                data = fetcher.fetch_historical_data(symbol, timeframe, start_date, end_date)
                result_queue.put(('success', data))
            except Exception as e:
                result_queue.put(('error', e))
        
        try:
            # Start the fetch operation in a separate thread
            thread = threading.Thread(target=fetch_in_thread, daemon=True)
            thread.start()
            
            # Wait for result with timeout - IB data fetching can take several minutes
            timeout_seconds = 600  # 10 minutes - IB data requests can be slow
            thread.join(timeout=timeout_seconds)
            
            if thread.is_alive():
                logger.error(f"Fetch operation timed out for {symbol} {timeframe} after {timeout_seconds}s")
                return None
            
            # Get result from queue
            if not result_queue.empty():
                result_type, result_data = result_queue.get_nowait()
                if result_type == 'success':
                    return result_data
                else:
                    logger.error(f"Error in threaded fetch: {result_data}")
                    return None
            else:
                logger.error(f"No result received for {symbol} {timeframe}")
                return None
                
        except Exception as e:
            logger.error(f"Error in sync-only fetch: {e}")
            return None


def create_context_aware_fetcher(connection: IbConnectionSync) -> IbContextManager:
    """
    Create a context-aware IB data fetcher.
    
    Args:
        connection: IB connection to use
        
    Returns:
        IbContextManager instance that detects context automatically
    """
    return IbContextManager(connection)