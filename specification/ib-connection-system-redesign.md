# IB Connection System Redesign Plan - With Proper Module Isolation

**Status**: Implementation In Progress  
**Created**: 2024-12-18  
**Last Updated**: 2024-12-18

## Problem Summary

The current issue is that IB connections die silently because:
1. API calls create async contexts that acquire IB connections
2. When the async context ends, the event loop and TCP transport get destroyed
3. This leaves connections in an invalid state (transport closed but `ib.isConnected()` returns True)
4. The system correctly detects and replaces these broken connections, but this happens for every API call

## Design Goals

1. **Isolate IB into its own module** (`ktrdr/ib/`) - completely separate from data folder
2. **Create clean interface** between data layer and IB implementation
3. **Keep connections alive** with their own dedicated thread and event loop (3-minute idle timeout)
4. **Maintain connection pool** for reuse across multiple API calls
5. **Simplify architecture** by removing unnecessary components
6. **Implement proper IB error handling** based on CORRECT error codes from official documentation
7. **Enforce key pacing rules** (50 req/sec, 2 sec between historical data calls)
8. **Proper error propagation** to API callers

## New Module Structure

### Create New IB Module: `ktrdr/ib/`
```
ktrdr/
├── ib/                          # NEW: Isolated IB module
│   ├── __init__.py
│   ├── connection.py            # IbConnection class with dedicated thread
│   ├── pool.py                  # IbConnectionPool 
│   ├── error_classifier.py     # IB error code handling (CORRECTED)
│   ├── pace_manager.py          # Simple rate limiting
│   ├── data_fetcher.py          # IB-specific data fetching
│   └── symbol_validator.py      # IB-specific symbol validation
└── data/
    ├── external_data_interface.py  # NEW: Interface for external data sources
    └── ib_data_adapter.py          # NEW: Adapter that uses ktrdr.ib module
```

### Data Layer Interface
The data layer will only know about a generic external data interface:

```python
# ktrdr/data/external_data_interface.py
from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd
from datetime import datetime

class ExternalDataProvider(ABC):
    """Interface for external data providers (IB, Alpha Vantage, etc.)"""
    
    @abstractmethod
    async def fetch_historical_data(
        self, 
        symbol: str, 
        timeframe: str, 
        start: datetime, 
        end: datetime,
        instrument_type: Optional[str] = None
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data"""
        pass
    
    @abstractmethod
    async def validate_symbol(self, symbol: str) -> bool:
        """Check if symbol is valid"""
        pass
    
    @abstractmethod
    async def get_head_timestamp(self, symbol: str, timeframe: str) -> Optional[datetime]:
        """Get earliest available data timestamp"""
        pass

# ktrdr/data/ib_data_adapter.py  
from ktrdr.ib.data_fetcher import IbDataFetcher
from .external_data_interface import ExternalDataProvider

class IbDataAdapter(ExternalDataProvider):
    """Adapter that bridges data layer to IB module"""
    
    def __init__(self):
        self.ib_fetcher = IbDataFetcher()
    
    async def fetch_historical_data(self, symbol, timeframe, start, end, instrument_type=None):
        return await self.ib_fetcher.fetch_historical_data(
            symbol, timeframe, start, end, instrument_type
        )
    
    async def validate_symbol(self, symbol):
        return await self.ib_fetcher.validate_symbol(symbol)
    
    async def get_head_timestamp(self, symbol, timeframe):
        return await self.ib_fetcher.get_head_timestamp(symbol, timeframe)
```

## Files to Delete

### Delete These Files (Move to `ktrdr/ib/`)
1. `ktrdr/data/ib_client_id_registry.py` - Delete (no longer needed)
2. `ktrdr/data/ib_connection_pool.py` - Move to `ktrdr/ib/pool.py`
3. `ktrdr/data/ib_data_fetcher_unified.py` - Move to `ktrdr/ib/data_fetcher.py`
4. `ktrdr/data/ib_error_handler.py` - Move to `ktrdr/ib/error_classifier.py` and FIX
5. `ktrdr/data/ib_pace_manager.py` - Move to `ktrdr/ib/pace_manager.py` and simplify
6. `ktrdr/data/ib_symbol_validator_unified.py` - Move to `ktrdr/ib/symbol_validator.py`
7. `ktrdr/data/ib_health_monitor.py` - Delete (redundant)
8. `ktrdr/data/ib_metrics_collector.py` - Delete (over-engineered)
9. `ktrdr/data/ib_gap_filler.py` - Move to `ktrdr/ib/gap_filler.py`
10. `ktrdr/data/ib_trading_hours_parser.py` - Move to `ktrdr/ib/trading_hours_parser.py`
11. `ktrdr/data/data_manager_async.py` - Delete (consolidate into main data_manager)

### Update These Files
1. `ktrdr/data/data_manager.py` - Use ExternalDataProvider interface
2. `ktrdr/api/services/data_service.py` - Remove complex async handling
3. All test files - Update imports and adapt to new structure

## New IB Module Implementation

### 1. IbConnection Class (`ktrdr/ib/connection.py`)
```python
import threading
import asyncio
import time
from typing import Any, Callable
from queue import Queue
from ib_insync import IB

class IbConnection:
    """
    IB connection with dedicated thread and persistent event loop.
    Keeps connection alive for up to 3 minutes idle.
    """
    
    def __init__(self, client_id: int, host: str, port: int):
        self.client_id = client_id
        self.host = host
        self.port = port
        self.ib = IB()
        
        # Threading components
        self.thread = None
        self.loop = None
        self.request_queue = asyncio.Queue()
        self.stop_event = threading.Event()
        
        # Connection state
        self.connected = False
        self.last_activity = time.time()
        self.idle_timeout = 180  # 3 minutes
        
    def start(self):
        """Start connection thread with persistent event loop"""
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()
        
    def _run_event_loop(self):
        """Run event loop in dedicated thread"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._connection_loop())
        finally:
            self.loop.close()
            
    async def _connection_loop(self):
        """Main connection loop - connect and process requests"""
        try:
            await self._connect()
            await self._process_requests()
        except Exception as e:
            logger.error(f"Connection {self.client_id} loop failed: {e}")
        finally:
            await self._disconnect()
            
    async def _connect(self):
        """Connect to IB Gateway"""
        await self.ib.connectAsync(
            host=self.host,
            port=self.port,
            clientId=self.client_id,
            timeout=15
        )
        self.connected = True
        logger.info(f"IB connection {self.client_id} established")
        
    async def _process_requests(self):
        """Process requests and handle idle timeout"""
        while not self.stop_event.is_set():
            try:
                # Check for idle timeout
                if time.time() - self.last_activity > self.idle_timeout:
                    logger.info(f"Connection {self.client_id} idle timeout")
                    break
                    
                # Process pending requests or wait
                request = await asyncio.wait_for(
                    self.request_queue.get(), 
                    timeout=1.0
                )
                
                self.last_activity = time.time()
                await self._execute_request(request)
                
            except asyncio.TimeoutError:
                continue  # Normal timeout, check idle again
            except Exception as e:
                logger.error(f"Request processing error: {e}")
                
    async def execute_request(self, func: Callable, *args, **kwargs) -> Any:
        """Execute IB request in connection thread (thread-safe)"""
        future = asyncio.Future()
        request = (func, args, kwargs, future)
        
        # Submit to connection thread
        asyncio.run_coroutine_threadsafe(
            self.request_queue.put(request), 
            self.loop
        )
        
        # Wait for result
        return await future
        
    def is_healthy(self) -> bool:
        """Check if connection is healthy"""
        return (
            self.connected and 
            self.ib.isConnected() and 
            self.thread.is_alive() and
            not self.stop_event.is_set()
        )
        
    def stop(self):
        """Stop connection gracefully"""
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
```

### 2. Simplified Connection Pool (`ktrdr/ib/pool.py`)
```python
import asyncio
from typing import Optional, List
from .connection import IbConnection
from .error_classifier import IbErrorClassifier

class IbConnectionPool:
    """
    Simple connection pool that manages IbConnection instances.
    No client ID registry - just try sequential IDs on conflicts.
    """
    
    def __init__(self, host: str = "localhost", port: int = 4002):
        self.host = host
        self.port = port
        self.connections: List[IbConnection] = []
        self.lock = asyncio.Lock()
        self.next_client_id = 1
        
    async def acquire_connection(self) -> IbConnection:
        """Get healthy connection or create new one"""
        async with self.lock:
            # Try to find healthy existing connection
            for conn in self.connections:
                if conn.is_healthy():
                    return conn
                    
            # Remove unhealthy connections
            self.connections = [c for c in self.connections if c.is_healthy()]
            
            # Create new connection
            return await self._create_connection()
            
    async def _create_connection(self) -> IbConnection:
        """Create new connection with next available client ID"""
        max_attempts = 10
        
        for attempt in range(max_attempts):
            client_id = self.next_client_id
            self.next_client_id += 1
            
            try:
                conn = IbConnection(client_id, self.host, self.port)
                conn.start()
                
                # Wait for connection to establish
                await asyncio.sleep(1)
                
                if conn.is_healthy():
                    self.connections.append(conn)
                    return conn
                else:
                    conn.stop()
                    
            except Exception as e:
                # Check if it's a client ID conflict
                if IbErrorClassifier.is_client_id_conflict(str(e)):
                    continue  # Try next ID
                else:
                    raise
                    
        raise ConnectionError("Failed to create IB connection after multiple attempts")
```

### 3. CORRECTED Error Classifier (`ktrdr/ib/error_classifier.py`)
```python
from typing import Tuple
from enum import Enum

class IbErrorType(Enum):
    FATAL = "fatal"
    RETRYABLE = "retryable"
    PACING = "pacing"
    DATA_UNAVAILABLE = "data_unavailable"

class IbErrorClassifier:
    """
    Classify IB errors based on OFFICIAL IB documentation.
    
    IMPORTANT: This implementation must be reviewed against the official
    IB documentation at implementation time to ensure accuracy:
    https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/#api-error-codes
    https://interactivebrokers.github.io/tws-api/message_codes.html
    """
    
    # PLACEHOLDER MAPPINGS - TO BE VERIFIED AGAINST OFFICIAL DOCS
    TENTATIVE_MAPPINGS = {
        # Connection errors (likely retryable)
        326: ("Client ID already in use", IbErrorType.RETRYABLE, 2.0),
        502: ("Couldn't connect to TWS", IbErrorType.RETRYABLE, 5.0),
        504: ("Not connected", IbErrorType.RETRYABLE, 2.0),
        
        # Historical data errors (need proper classification)
        162: ("Historical market Data Service query message", IbErrorType.DATA_UNAVAILABLE, 0.0),
        165: ("Historical market Data Service query message", IbErrorType.DATA_UNAVAILABLE, 0.0),
        
        # Pacing violations (need to identify correct codes)
        420: ("Invalid real-time query", IbErrorType.PACING, 60.0),
        
        # Fatal errors (likely no retry)
        200: ("No security definition has been found", IbErrorType.FATAL, 0.0),
        354: ("Requested market data is not subscribed", IbErrorType.FATAL, 0.0),
    }
    
    @classmethod
    def classify(cls, error_code: int, error_message: str) -> Tuple[IbErrorType, float]:
        """
        Classify error and return (type, suggested_wait_seconds)
        
        WARNING: This is a placeholder implementation that MUST be reviewed
        and corrected against official IB documentation during implementation.
        """
        if error_code in cls.TENTATIVE_MAPPINGS:
            description, error_type, wait_time = cls.TENTATIVE_MAPPINGS[error_code]
            return error_type, wait_time
            
        # Check message for transport errors (these are usually retryable)
        if any(keyword in error_message.lower() for keyword in [
            'handler is closed', 'transport closed', 'connection closed'
        ]):
            return IbErrorType.RETRYABLE, 1.0
            
        # Default to retryable with moderate wait
        return IbErrorType.RETRYABLE, 5.0
    
    @classmethod
    def is_client_id_conflict(cls, error_message: str) -> bool:
        """Check if error is client ID conflict"""
        return "326" in error_message or "already in use" in error_message.lower()
    
    @classmethod
    def should_retry(cls, error_type: IbErrorType) -> bool:
        """Determine if error should be retried"""
        return error_type in [IbErrorType.RETRYABLE, IbErrorType.PACING]
```

### 4. Simple Pace Manager (`ktrdr/ib/pace_manager.py`)
```python
import time
import asyncio
from collections import deque
from typing import Tuple

class IbPaceManager:
    """
    Simple rate limiting for IB API calls.
    Enforces: 50 req/sec max, 2 sec between historical data calls.
    
    Based on IB pacing guidelines:
    https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/#requests-limitations
    """
    
    def __init__(self):
        self.request_times = deque(maxlen=50)  # For 50/sec limit
        self.last_historical_time = 0
        
    async def wait_if_needed(self, is_historical: bool = False):
        """Sleep if needed to respect pacing limits"""
        now = time.time()
        
        # 50 requests per second limit
        if len(self.request_times) >= 50:
            oldest = self.request_times[0]
            if now - oldest < 1.0:
                wait_time = 1.0 - (now - oldest)
                await asyncio.sleep(wait_time)
                
        # 2 seconds between historical data requests
        if is_historical:
            elapsed = now - self.last_historical_time
            if elapsed < 2.0:
                wait_time = 2.0 - elapsed
                await asyncio.sleep(wait_time)
            self.last_historical_time = time.time()
            
        self.request_times.append(time.time())
        
    def can_make_request(self, is_historical: bool = False) -> Tuple[bool, float]:
        """
        Check if request can be made now.
        Returns (can_proceed, seconds_to_wait)
        """
        now = time.time()
        
        # Check general rate limit
        if len(self.request_times) >= 50:
            oldest = self.request_times[0]
            if now - oldest < 1.0:
                return False, 1.0 - (now - oldest)
                
        # Check historical data limit
        if is_historical:
            elapsed = now - self.last_historical_time
            if elapsed < 2.0:
                return False, 2.0 - elapsed
                
        return True, 0.0
```

## Data Layer Changes

### Update DataManager (`ktrdr/data/data_manager.py`)
```python
from .external_data_interface import ExternalDataProvider
from .ib_data_adapter import IbDataAdapter

class DataManager:
    def __init__(self, data_dir: Optional[str] = None):
        # ...existing code...
        
        # Use adapter pattern for external data
        self.external_provider: ExternalDataProvider = IbDataAdapter()
        
    async def _fetch_from_external_source(self, symbol, timeframe, start, end):
        """Fetch data from external provider (IB via adapter)"""
        return await self.external_provider.fetch_historical_data(
            symbol, timeframe, start, end
        )
```

## Critical Implementation Note: Error Code Verification

**BEFORE IMPLEMENTING THE ERROR CLASSIFIER, WE MUST:**

1. **Review the complete official IB documentation** at:
   - https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/#api-error-codes
   - https://interactivebrokers.github.io/tws-api/message_codes.html

2. **Verify each error code mapping** especially:
   - What codes 162 and 165 actually mean
   - Which codes indicate genuine pacing violations
   - Which codes are fatal vs retryable
   - Which codes indicate data availability issues

3. **Test with real IB Gateway** to confirm error behavior

4. **Document our findings** in the error classifier with references to official docs

## Test Updates

### Unit Tests
- Move IB-specific tests to `tests/ib/`
- Create interface tests in `tests/data/test_external_data_interface.py`
- Update connection pool tests for new architecture
- **Add comprehensive error handling tests** with correct error codes

### Integration Tests  
- Test data layer works with IB adapter
- Test connection reuse across operations
- Test error propagation through adapter
- **Test error classification with real IB responses**

### E2E Tests
- Update all to use new module structure
- Test adapter pattern works end-to-end

### Real E2E Tests
- Verify connections survive multi-segment operations
- Test proper error messages reach API responses
- **Verify error handling with actual IB Gateway**

## Migration Steps

1. **Phase 1: Research & Verify**
   - **CRITICAL: Study official IB error documentation thoroughly**
   - Create accurate error code mappings
   - Document findings

2. **Phase 2: Create IB Module**
   - Create `ktrdr/ib/` directory
   - Implement core classes with CORRECT error handling
   - Create data interface and adapter

3. **Phase 3: Move and Simplify**
   - Move IB files from `data/` to `ib/`
   - Apply corrected error handling
   - Remove unnecessary complexity

4. **Phase 4: Update Data Layer**
   - Implement ExternalDataProvider interface
   - Update DataManager to use adapter
   - Remove direct IB dependencies from data layer

5. **Phase 5: Update API Layer**
   - Remove complex async handling
   - Ensure error propagation works
   - Clean up service layer

6. **Phase 6: Testing & Cleanup**
   - Update all tests for new structure
   - Remove unused files
   - Verify connection reuse works
   - **Test error handling extensively with real IB**

## Key Benefits

1. **Clean Separation**: Data layer knows nothing about IB specifics
2. **Future-Proof**: Easy to add other data providers
3. **Container-Ready**: IB module can be moved to separate container
4. **Simplified**: Fewer files, clearer responsibilities
5. **Thread-Safe**: Proper connection lifecycle management
6. **CORRECT Error Handling**: Based on official IB documentation
7. **Error Propagation**: All IB errors reach API responses

## Success Criteria

1. Connections survive across multiple IB API calls within same operation
2. No more "handler is closed" errors during normal operation
3. Clean separation between data layer and IB implementation
4. Data layer can work with different external providers
5. IB module is completely self-contained
6. **Accurate error classification based on official IB docs**
7. Proper error messages in API responses
8. Significant reduction in codebase complexity

This plan addresses both the technical threading issue AND creates the architectural foundation for the future deployment evolution where IB will be containerized separately, with CORRECT error handling based on official IB documentation.

## Implementation Progress

- [ ] Research and verify IB error codes from official documentation
- [ ] Create ktrdr/ib/ module directory structure
- [ ] Implement IbConnection class with dedicated thread
- [ ] Implement simplified IbConnectionPool
- [ ] Create corrected IbErrorClassifier with official error codes
- [ ] Implement simple IbPaceManager
- [ ] Create ExternalDataProvider interface
- [ ] Create IbDataAdapter to bridge data layer to IB module
- [ ] Move IB files from data/ to ib/ module
- [ ] Update DataManager to use ExternalDataProvider interface
- [ ] Update tests for new module structure