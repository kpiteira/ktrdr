"""
Interactive Brokers Error Handler

Centralized error classification, pace violation detection, and recovery logic.
Based on official IB API error codes and empirical testing.
"""

import time
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from ktrdr.logging import get_logger
from ktrdr.config.ib_limits import IbLimitsRegistry

logger = get_logger(__name__)


class IbErrorType(Enum):
    """Classification of IB error types for appropriate handling."""
    PACING_VIOLATION = "pacing_violation"
    NO_DATA_AVAILABLE = "no_data_available"
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
        
    def classify_error(self, error_code: int, error_message: str) -> IbErrorInfo:
        """
        Classify an IB error for appropriate handling.
        
        Args:
            error_code: IB error code
            error_message: Full error message from IB
            
        Returns:
            IbErrorInfo with classification and handling guidance
        """
        # Special handling for error 162 - depends on message content
        if error_code == 162:
            if "no data" in error_message.lower():
                return IbErrorInfo(
                    error_code=162,
                    error_message=error_message,
                    error_type=IbErrorType.NO_DATA_AVAILABLE,
                    is_retryable=False,
                    suggested_wait_time=0.0,
                    description="No historical data available for requested period"
                )
            else:
                # Other 162 errors are likely pacing violations
                return IbErrorInfo(
                    error_code=162,
                    error_message=error_message,
                    error_type=IbErrorType.PACING_VIOLATION,
                    is_retryable=True,
                    suggested_wait_time=60.0,
                    description="HMDS pacing violation - too many requests"
                )
        
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