"""
Interactive Brokers Error Handler

Centralized error classification, pace violation detection, and recovery logic.
Based on official IB API error codes and empirical testing.
"""

import time
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone

from ktrdr.logging import get_logger
from ktrdr.config.ib_limits import IbLimitsRegistry
from ktrdr.utils.timezone_utils import TimestampManager

logger = get_logger(__name__)


class IbErrorType(Enum):
    """Classification of IB error types for appropriate handling."""
    PACING_VIOLATION = "pacing_violation"
    NO_DATA_AVAILABLE = "no_data_available"
    FUTURE_DATE_REQUEST = "future_date_request"  # NEW: Future date validation error
    HISTORICAL_DATA_LIMIT = "historical_data_limit"  # NEW: Data not available for historical period
    CONNECTION_ERROR = "connection_error"
    PERMISSION_ERROR = "permission_error"
    INVALID_REQUEST = "invalid_request"
    SERVER_ERROR = "server_error"
    INFORMATIONAL = "informational"
    UNKNOWN = "unknown"


@dataclass
class IbErrorInfo:
    """Detailed information about an IB error."""
    error_code: int
    error_message: str
    error_type: IbErrorType
    is_retryable: bool
    suggested_wait_time: float  # seconds
    description: str


class IbErrorHandler:
    """
    Centralized IB error handling with pace violation detection and recovery.
    
    Based on official IB API documentation and community knowledge:
    - https://ibkrcampus.com/ibkr-api-page/trader-workstation-api/#error-codes
    - https://interactivebrokers.github.io/tws-api/message_codes.html
    """
    
    # Official IB error code classifications
    ERROR_CLASSIFICATIONS = {
        # GENUINE PACING VIOLATIONS (these require waiting)
        165: IbErrorInfo(
            error_code=165,
            error_message="Historical data request pacing violation",
            error_type=IbErrorType.PACING_VIOLATION,
            is_retryable=True,
            suggested_wait_time=60.0,
            description="Direct pacing violation message"
        ),
        200: IbErrorInfo(
            error_code=200,
            error_message="No security definition has been found",
            error_type=IbErrorType.INVALID_REQUEST,
            is_retryable=False,
            suggested_wait_time=0.0,
            description="Invalid contract - not a pacing issue"
        ),
        354: IbErrorInfo(
            error_code=354,
            error_message="Requested market data is not subscribed",
            error_type=IbErrorType.PERMISSION_ERROR,
            is_retryable=False,
            suggested_wait_time=0.0,
            description="Market data subscription required"
        ),
        
        # CONNECTION ISSUES (retryable)
        502: IbErrorInfo(
            error_code=502,
            error_message="Couldn't connect to TWS",
            error_type=IbErrorType.CONNECTION_ERROR,
            is_retryable=True,
            suggested_wait_time=5.0,
            description="Connection to TWS/Gateway failed"
        ),
        504: IbErrorInfo(
            error_code=504,
            error_message="Not connected",
            error_type=IbErrorType.CONNECTION_ERROR,
            is_retryable=True,
            suggested_wait_time=2.0,
            description="Client not connected to TWS/Gateway"
        ),
        
        # INFORMATIONAL (not errors)
        2106: IbErrorInfo(
            error_code=2106,
            error_message="HMDS data farm connection is OK",
            error_type=IbErrorType.INFORMATIONAL,
            is_retryable=False,
            suggested_wait_time=0.0,
            description="Connection status update"
        ),
        2107: IbErrorInfo(
            error_code=2107,
            error_message="HMDS data farm connection is OK",
            error_type=IbErrorType.INFORMATIONAL,
            is_retryable=False,
            suggested_wait_time=0.0,
            description="Historical data connection OK"
        ),
        2119: IbErrorInfo(
            error_code=2119,
            error_message="Market data farm connection is OK",
            error_type=IbErrorType.INFORMATIONAL,
            is_retryable=False,
            suggested_wait_time=0.0,
            description="Market data connection OK"
        ),
    }
    
    def __init__(self):
        """Initialize the error handler with tracking state."""
        self.pace_violation_count = 0
        self.last_pace_violation_time = 0.0
        self.total_wait_time = 0.0
        self.last_request_context = {}  # Store context for better error classification
        
    def set_request_context(self, symbol: str, start_date: datetime, end_date: datetime, timeframe: str) -> None:
        """
        Set context for the current request to enable intelligent error classification.
        
        Args:
            symbol: Trading symbol being requested
            start_date: Start date of the request
            end_date: End date of the request
            timeframe: Timeframe being requested
        """
        self.last_request_context = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "timeframe": timeframe,
            "is_future_request": end_date > TimestampManager.now_utc(),
            "request_time": TimestampManager.now_utc()
        }
        
    def classify_error(self, error_code: int, error_message: str, use_context: bool = True) -> IbErrorInfo:
        """
        Classify an IB error for appropriate handling with enhanced 162 classification.
        
        Args:
            error_code: IB error code
            error_message: Full error message from IB
            use_context: Whether to use request context for enhanced classification
            
        Returns:
            IbErrorInfo with classification and handling guidance
        """
        # Enhanced handling for error 162 - the most problematic one
        if error_code == 162:
            return self._classify_error_162(error_message, use_context)
        
        # Use predefined classification if available
        if error_code in self.ERROR_CLASSIFICATIONS:
            base_info = self.ERROR_CLASSIFICATIONS[error_code]
            # Update with actual message
            return IbErrorInfo(
                error_code=error_code,
                error_message=error_message,
                error_type=base_info.error_type,
                is_retryable=base_info.is_retryable,
                suggested_wait_time=base_info.suggested_wait_time,
                description=base_info.description
            )
        
        # Unknown error - conservative handling
        return IbErrorInfo(
            error_code=error_code,
            error_message=error_message,
            error_type=IbErrorType.UNKNOWN,
            is_retryable=True,
            suggested_wait_time=30.0,
            description=f"Unknown error code {error_code}"
        )
    
    def _classify_error_162(self, error_message: str, use_context: bool) -> IbErrorInfo:
        """
        Enhanced classification for error 162 with context awareness.
        
        Error 162 can mean:
        1. Future date request (user error)
        2. Historical data limit reached (symbol limitation)  
        3. Actual pacing violation (retry needed)
        4. Temporary server issue (retry needed)
        
        Args:
            error_message: Full error message from IB
            use_context: Whether to use request context
            
        Returns:
            IbErrorInfo with specific 162 classification
        """
        message_lower = error_message.lower()
        
        # Check if we have request context for intelligent classification
        if use_context and self.last_request_context:
            context = self.last_request_context
            
            # 1. Future date request detection
            if context.get("is_future_request", False):
                logger.warning(f"🔮 Error 162 for FUTURE DATE request: {context['end_date']} > now")
                return IbErrorInfo(
                    error_code=162,
                    error_message=error_message,
                    error_type=IbErrorType.FUTURE_DATE_REQUEST,
                    is_retryable=False,
                    suggested_wait_time=0.0,
                    description="Cannot request data for future dates"
                )
            
            # 2. Very old historical data (likely symbol limitation)
            start_date = context.get("start_date")
            if start_date:
                days_ago = (TimestampManager.now_utc() - start_date).days
                if days_ago > 365 * 5:  # More than 5 years ago
                    logger.info(f"📅 Error 162 for VERY OLD data: {days_ago} days ago for {context['symbol']}")
                    return IbErrorInfo(
                        error_code=162,
                        error_message=error_message,
                        error_type=IbErrorType.HISTORICAL_DATA_LIMIT,
                        is_retryable=False,
                        suggested_wait_time=0.0,
                        description=f"Historical data not available {days_ago} days ago for {context['symbol']}"
                    )
        
        # 3. Message-based classification (fallback when no context)
        if any(phrase in message_lower for phrase in ["no data", "no historical data", "insufficient data"]):
            return IbErrorInfo(
                error_code=162,
                error_message=error_message,
                error_type=IbErrorType.NO_DATA_AVAILABLE,
                is_retryable=False,
                suggested_wait_time=0.0,
                description="No historical data available for requested period"
            )
        
        # 4. Assume pacing violation for other 162 errors (most common case)
        logger.warning(f"🚦 Assuming error 162 is PACING VIOLATION: {error_message}")
        return IbErrorInfo(
            error_code=162,
            error_message=error_message,
            error_type=IbErrorType.PACING_VIOLATION,
            is_retryable=True,
            suggested_wait_time=60.0,
            description="Assumed HMDS pacing violation based on error 162"
        )
    
    def handle_error(self, error_code: int, error_message: str, req_id: Optional[int] = None) -> Tuple[bool, float]:
        """
        Handle an IB error with appropriate logging and recovery guidance.
        
        Args:
            error_code: IB error code
            error_message: Full error message from IB
            req_id: Request ID if available
            
        Returns:
            Tuple of (should_retry, wait_time_seconds)
        """
        error_info = self.classify_error(error_code, error_message)
        
        # Log based on error type
        if error_info.error_type == IbErrorType.INFORMATIONAL:
            logger.debug(f"IB Info {error_code}: {error_message}")
            return False, 0.0
        
        elif error_info.error_type == IbErrorType.NO_DATA_AVAILABLE:
            logger.info(f"IB: No data available for request (code {error_code})")
            return False, 0.0
        
        elif error_info.error_type == IbErrorType.FUTURE_DATE_REQUEST:
            logger.error(f"🔮 FUTURE DATE ERROR: {error_message}")
            logger.error("⚠️  Cannot request data for future dates - check your date parameters!")
            return False, 0.0
            
        elif error_info.error_type == IbErrorType.HISTORICAL_DATA_LIMIT:
            logger.warning(f"📅 HISTORICAL LIMIT: {error_message}")
            logger.warning("💡 Try requesting more recent data or use a different data source for older periods")
            return False, 0.0
        
        elif error_info.error_type == IbErrorType.PACING_VIOLATION:
            self.pace_violation_count += 1
            self.last_pace_violation_time = time.time()
            
            logger.warning(f"🚦 PACE VIOLATION #{self.pace_violation_count}: IB error {error_code}")
            logger.warning(f"🚦 Will wait {error_info.suggested_wait_time}s before retry")
            
            return True, error_info.suggested_wait_time
        
        elif error_info.error_type in [IbErrorType.CONNECTION_ERROR]:
            logger.warning(f"IB Connection Error {error_code}: {error_message}")
            return True, error_info.suggested_wait_time
            
        else:
            # Other errors
            if error_info.is_retryable:
                logger.warning(f"IB Error {error_code}: {error_message}")
            else:
                logger.error(f"IB Error {error_code}: {error_message}")
            return error_info.is_retryable, error_info.suggested_wait_time
    
    def wait_for_recovery(self, wait_time: float) -> None:
        """
        Wait for the specified time with progress logging.
        
        Args:
            wait_time: Time to wait in seconds
        """
        if wait_time <= 0:
            return
            
        logger.info(f"⏳ Waiting {wait_time}s for IB pace recovery...")
        self.total_wait_time += wait_time
        
        # Wait with periodic progress updates for long waits
        if wait_time > 10:
            intervals = int(wait_time / 10)  # Update every 10 seconds
            for i in range(intervals):
                time.sleep(10)
                remaining = wait_time - ((i + 1) * 10)
                if remaining > 0:
                    logger.debug(f"⏳ Still waiting... {remaining}s remaining")
            
            # Sleep the remainder
            remainder = wait_time % 10
            if remainder > 0:
                time.sleep(remainder)
        else:
            time.sleep(wait_time)
        
        logger.info(f"✅ Wait complete, resuming IB requests")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get error handling statistics."""
        return {
            "pace_violations": self.pace_violation_count,
            "last_pace_violation": self.last_pace_violation_time,
            "total_wait_time": self.total_wait_time,
            "time_since_last_violation": time.time() - self.last_pace_violation_time if self.last_pace_violation_time > 0 else 0
        }