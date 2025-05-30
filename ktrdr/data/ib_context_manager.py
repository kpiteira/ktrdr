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
        Fetch historical data using context-appropriate method.
        
        This method automatically detects the execution context and uses:
        - Sync calls with new event loop for background threads
        - Direct sync calls for FastAPI async contexts
        
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
            if context == 'async_context':
                # We're in FastAPI - use sync calls without event loop
                return self._fetch_sync_in_async_context(symbol, timeframe, start_date, end_date)
            elif context == 'thread_context':
                # We're in background thread - use event loop
                return self._fetch_sync_in_thread_context(symbol, timeframe, start_date, end_date)
            else:
                logger.warning(f"Unknown context for IB fetch: {context}")
                # Try thread context as fallback
                return self._fetch_sync_in_thread_context(symbol, timeframe, start_date, end_date)
                
        except Exception as e:
            logger.error(f"Error fetching {symbol} {timeframe}: {e}")
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
        
        In this context, we need to create a new event loop for IB operations.
        """
        import asyncio
        import threading
        import queue
        
        # Even in thread context, we need to run IB operations with proper event loop
        result_queue: queue.Queue = queue.Queue()
        
        def fetch_with_event_loop():
            """Run the fetch operation with a dedicated event loop."""
            try:
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    # Import inside to avoid import cycles
                    from ktrdr.data.ib_data_fetcher_sync import IbDataFetcherSync
                    
                    # Create fetcher and fetch data
                    fetcher = IbDataFetcherSync(self.connection)
                    data = fetcher.fetch_historical_data(symbol, timeframe, start_date, end_date)
                    result_queue.put(('success', data))
                    
                finally:
                    loop.close()
                    asyncio.set_event_loop(None)
                    
            except Exception as e:
                result_queue.put(('error', e))
        
        try:
            # Start the fetch operation in a separate thread with event loop
            thread = threading.Thread(target=fetch_with_event_loop, daemon=True)
            thread.start()
            
            # Wait for result with timeout
            thread.join(timeout=60)  # 60 second timeout
            
            if thread.is_alive():
                logger.error(f"Fetch operation timed out for {symbol} {timeframe}")
                return None
            
            # Get result from queue
            if not result_queue.empty():
                result_type, result_data = result_queue.get_nowait()
                if result_type == 'success':
                    return result_data
                else:
                    logger.error(f"Error in thread context fetch: {result_data}")
                    return None
            else:
                logger.error(f"No result received for {symbol} {timeframe}")
                return None
                
        except Exception as e:
            logger.error(f"Error in thread context fetch: {e}")
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
            
            # Wait for result with timeout
            thread.join(timeout=60)  # 60 second timeout
            
            if thread.is_alive():
                logger.error(f"Fetch operation timed out for {symbol} {timeframe}")
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