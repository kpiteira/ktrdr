"""
IB Pace Manager

Simple rate limiting for IB API calls based on official IB pacing rules:
https://interactivebrokers.github.io/tws-api/historical_limitations.html

Official Pacing Rules:
1. Max 50 simultaneous open historical data requests
2. Cannot make identical requests within 15 seconds  
3. Cannot make 6+ requests for same Contract/Exchange/Tick Type within 2 seconds
4. Cannot make more than 60 requests in any 10-minute period
5. BID_ASK requests count double

Additional Rules:
- Max 50 requests per second for general API calls
- 2 second minimum between historical data calls (conservative approach)
"""

import time
import asyncio
import threading
from collections import deque, defaultdict
from typing import Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ktrdr.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RequestInfo:
    """Information about a request for pacing tracking"""
    timestamp: float
    request_type: str  # 'historical', 'general', etc.
    contract_key: str  # symbol+exchange+tick_type for duplicate detection
    is_bid_ask: bool = False


class IbPaceManager:
    """
    Simple rate limiting for IB API calls based on official IB pacing guidelines.
    
    Enforces the key pacing rules:
    - 50 requests per second max (general API calls)
    - 2 seconds minimum between historical data calls (conservative)
    - 60 requests per 10-minute window
    - 15 second minimum between identical requests
    - 6 requests max per contract/exchange/tick type per 2 seconds
    """
    
    def __init__(self):
        self.lock = threading.RLock()
        
        # General rate limiting (50/sec)
        self.request_times = deque(maxlen=50)
        
        # Historical data specific tracking
        self.last_historical_time = 0.0
        self.historical_requests = deque(maxlen=60)  # 60 requests per 10 min
        
        # Contract-specific tracking (6 per 2 seconds)
        self.contract_requests = defaultdict(lambda: deque(maxlen=6))
        
        # Identical request tracking (15 second minimum)
        self.identical_requests = {}  # contract_key -> timestamp
        
        logger.info("IB Pace Manager initialized with official pacing rules")
    
    async def wait_if_needed(self, 
                           is_historical: bool = False,
                           contract_key: Optional[str] = None,
                           is_bid_ask: bool = False) -> None:
        """
        Sleep if needed to respect pacing limits.
        
        Args:
            is_historical: True for historical data requests
            contract_key: Identifier for contract (symbol+exchange+tick_type)
            is_bid_ask: True if this is a BID_ASK request (counts double)
        """
        with self.lock:
            now = time.time()
            
            # 1. General rate limit: 50 requests per second
            await self._enforce_general_rate_limit()
            
            if is_historical:
                # 2. Historical data specific limits
                await self._enforce_historical_limits(now, contract_key, is_bid_ask)
            
            # Record this request
            self._record_request(now, is_historical, contract_key, is_bid_ask)
    
    async def _enforce_general_rate_limit(self):
        """Enforce 50 requests per second limit"""
        now = time.time()
        
        if len(self.request_times) >= 50:
            oldest = self.request_times[0]
            elapsed = now - oldest
            if elapsed < 1.0:
                wait_time = 1.0 - elapsed
                logger.debug(f"General rate limit: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
    
    async def _enforce_historical_limits(self, now: float, contract_key: Optional[str], is_bid_ask: bool):
        """Enforce historical data specific limits"""
        
        # 2a. Minimum 2 seconds between historical requests (conservative)
        elapsed_since_last = now - self.last_historical_time
        if elapsed_since_last < 2.0:
            wait_time = 2.0 - elapsed_since_last
            logger.debug(f"Historical data pacing: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        
        # 2b. 60 requests per 10 minutes
        await self._enforce_ten_minute_limit(now, is_bid_ask)
        
        # 2c. Contract-specific limits (6 per 2 seconds)
        if contract_key:
            await self._enforce_contract_limits(now, contract_key)
            
        # 2d. Identical request limit (15 seconds)
        if contract_key:
            await self._enforce_identical_request_limit(now, contract_key)
    
    async def _enforce_ten_minute_limit(self, now: float, is_bid_ask: bool):
        """Enforce 60 requests per 10 minutes (BID_ASK counts double)"""
        # Clean old requests (older than 10 minutes)
        cutoff_time = now - 600  # 10 minutes
        while self.historical_requests and self.historical_requests[0].timestamp < cutoff_time:
            self.historical_requests.popleft()
        
        # Count requests (BID_ASK counts double)
        request_count = 0
        for req in self.historical_requests:
            request_count += 2 if req.is_bid_ask else 1
        
        # Add current request count
        current_request_count = 2 if is_bid_ask else 1
        
        if request_count + current_request_count > 60:
            # Calculate wait time until oldest request falls off
            if self.historical_requests:
                oldest_request = self.historical_requests[0]
                wait_time = (oldest_request.timestamp + 600) - now
                logger.debug(f"10-minute limit: waiting {wait_time:.2f}s")
                await asyncio.sleep(max(wait_time, 0))
    
    async def _enforce_contract_limits(self, now: float, contract_key: str):
        """Enforce 6 requests per contract per 2 seconds"""
        contract_requests = self.contract_requests[contract_key]
        
        # Clean old requests (older than 2 seconds)
        cutoff_time = now - 2.0
        while contract_requests and contract_requests[0] < cutoff_time:
            contract_requests.popleft()
        
        if len(contract_requests) >= 6:
            # Wait until oldest request is 2 seconds old
            oldest_time = contract_requests[0]
            wait_time = (oldest_time + 2.0) - now
            logger.debug(f"Contract limit ({contract_key}): waiting {wait_time:.2f}s")
            await asyncio.sleep(max(wait_time, 0))
    
    async def _enforce_identical_request_limit(self, now: float, contract_key: str):
        """Enforce 15 seconds between identical requests"""
        if contract_key in self.identical_requests:
            last_time = self.identical_requests[contract_key]
            elapsed = now - last_time
            if elapsed < 15.0:
                wait_time = 15.0 - elapsed
                logger.debug(f"Identical request limit ({contract_key}): waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
    
    def _record_request(self, now: float, is_historical: bool, contract_key: Optional[str], is_bid_ask: bool):
        """Record request for future pacing calculations"""
        
        # Record in general request times
        self.request_times.append(now)
        
        if is_historical:
            # Update last historical time
            self.last_historical_time = now
            
            # Record in historical requests
            self.historical_requests.append(RequestInfo(
                timestamp=now,
                request_type="historical",
                contract_key=contract_key or "unknown",
                is_bid_ask=is_bid_ask
            ))
            
            if contract_key:
                # Record for contract-specific tracking
                self.contract_requests[contract_key].append(now)
                
                # Record for identical request tracking
                self.identical_requests[contract_key] = now
    
    def can_make_request(self, 
                        is_historical: bool = False,
                        contract_key: Optional[str] = None,
                        is_bid_ask: bool = False) -> Tuple[bool, float]:
        """
        Check if request can be made immediately.
        
        Returns:
            Tuple of (can_proceed, seconds_to_wait)
        """
        with self.lock:
            now = time.time()
            max_wait = 0.0
            
            # Check general rate limit
            if len(self.request_times) >= 50:
                oldest = self.request_times[0]
                elapsed = now - oldest
                if elapsed < 1.0:
                    max_wait = max(max_wait, 1.0 - elapsed)
            
            if is_historical:
                # Check historical data limits
                
                # 2 second minimum between historical requests
                elapsed_since_last = now - self.last_historical_time
                if elapsed_since_last < 2.0:
                    max_wait = max(max_wait, 2.0 - elapsed_since_last)
                
                # 10 minute window limit
                cutoff_time = now - 600
                request_count = sum(
                    2 if req.is_bid_ask else 1 
                    for req in self.historical_requests 
                    if req.timestamp >= cutoff_time
                )
                current_count = 2 if is_bid_ask else 1
                if request_count + current_count > 60:
                    if self.historical_requests:
                        oldest_req = next(
                            req for req in self.historical_requests 
                            if req.timestamp >= cutoff_time
                        )
                        wait_time = (oldest_req.timestamp + 600) - now
                        max_wait = max(max_wait, wait_time)
                
                if contract_key:
                    # Contract-specific limit
                    contract_requests = self.contract_requests[contract_key]
                    recent_requests = [
                        t for t in contract_requests 
                        if t >= now - 2.0
                    ]
                    if len(recent_requests) >= 6:
                        oldest_time = min(recent_requests)
                        wait_time = (oldest_time + 2.0) - now
                        max_wait = max(max_wait, wait_time)
                    
                    # Identical request limit
                    if contract_key in self.identical_requests:
                        last_time = self.identical_requests[contract_key]
                        elapsed = now - last_time
                        if elapsed < 15.0:
                            max_wait = max(max_wait, 15.0 - elapsed)
            
            can_proceed = max_wait <= 0.0
            return can_proceed, max_wait
    
    def get_stats(self) -> dict:
        """Get current pacing statistics"""
        with self.lock:
            now = time.time()
            
            # Count recent historical requests
            recent_historical = sum(
                1 for req in self.historical_requests 
                if req.timestamp >= now - 600  # Last 10 minutes
            )
            
            return {
                "general_requests_last_second": len(self.request_times),
                "historical_requests_last_10min": recent_historical,
                "seconds_since_last_historical": now - self.last_historical_time,
                "tracked_contracts": len(self.contract_requests),
                "identical_request_cache_size": len(self.identical_requests)
            }
    
    def reset_stats(self):
        """Reset all pacing statistics (for testing)"""
        with self.lock:
            self.request_times.clear()
            self.historical_requests.clear()
            self.contract_requests.clear()
            self.identical_requests.clear()
            self.last_historical_time = 0.0
            logger.info("Pace manager statistics reset")