"""
IB Diagnosis utilities for CLI error handling.

This module provides CLI-specific diagnosis of IB Gateway connectivity issues
to give clear, actionable error messages that match the backend diagnosis.
"""

from enum import Enum
from typing import Any, Optional

from ktrdr.logging import get_logger

logger = get_logger(__name__)


class IBProblemType(Enum):
    """Types of IB connection problems that can be diagnosed."""

    UNRECOVERABLE = "unrecoverable"  # Restart IB Gateway required
    RECOVERABLE = "recoverable"  # Retry may work
    CONFIGURATION = "configuration"  # Settings issue
    UNKNOWN = "unknown"  # Unknown issue


def detect_ib_issue_from_api_response(
    response: dict[str, Any],
) -> tuple[Optional[IBProblemType], Optional[str], dict[str, Any]]:
    """
    Detect IB Gateway issues from API response.

    Args:
        response: API response dictionary

    Returns:
        (problem_type, clear_message, details) or (None, None, {}) if no IB issue detected
    """
    if not response:
        return None, None, {}

    error_info = response.get("error", {})
    if not error_info:
        return None, None, {}

    # Check both complete failures and partial successes with error info

    error_code = error_info.get("code", "")
    error_message = error_info.get("message", "")
    error_details = error_info.get("details", {})

    # Check for explicit IB Gateway issues from backend diagnosis
    if "IB-GATEWAY-ISSUE" in error_code:
        problem_type_str = error_details.get("problem_type", "unknown")
        diagnosis_details = error_details.get("diagnosis", {})

        try:
            problem_type = IBProblemType(problem_type_str)
        except ValueError:
            problem_type = IBProblemType.UNKNOWN

        return problem_type, error_message, diagnosis_details

    # Check for circuit breaker issues
    if "CIRCUIT" in error_code or "circuit" in error_message.lower():
        return (
            IBProblemType.UNRECOVERABLE,
            "🚨 IB GATEWAY CONNECTION ISSUE DETECTED\n\n"
            "The system has detected repeated IB Gateway failures and has temporarily\n"
            "disabled IB operations to prevent system overload.\n\n"
            "REQUIRED ACTION:\n"
            "1. Check that IB Gateway/TWS is running and connected\n"
            "2. Verify API settings are enabled in IB Gateway\n"
            "3. Restart IB Gateway to refresh connections\n"
            "4. Wait a moment, then retry your operation",
            error_details,
        )

    # Check for timeout errors that may indicate silent connections
    if "timeout" in error_message.lower() or "TIMEOUT" in error_code:
        return (
            IBProblemType.UNRECOVERABLE,
            "🚨 IB GATEWAY SILENT CONNECTION DETECTED\n\n"
            "TCP connection to IB Gateway works but operations timeout.\n"
            "This indicates a port forwarding or API configuration issue.\n\n"
            "REQUIRED ACTION:\n"
            "1. Check IB Gateway API settings (Enable API, correct port)\n"
            "2. If using Docker: verify host.docker.internal resolution\n"
            "3. Restart IB Gateway to refresh API connections\n"
            "4. Check firewall/network blocking data transmission",
            error_details,
        )

    # Check for connection errors
    if any(
        term in error_message.lower()
        for term in ["connection", "connect", "unreachable", "refused"]
    ):
        return (
            IBProblemType.UNRECOVERABLE,
            "🚨 IB GATEWAY NOT ACCESSIBLE\n\n"
            "Cannot establish connection to IB Gateway.\n\n"
            "REQUIRED ACTION:\n"
            "1. Start IB Gateway/TWS and ensure it's running\n"
            "2. Verify the correct port is configured\n"
            "3. Check that API access is enabled in IB Gateway settings\n"
            "4. Ensure no firewall is blocking the connection",
            error_details,
        )

    # Check for IB-specific error codes
    ib_error_patterns = ["IB-", "ib-", "gateway", "tws", "interactive", "brokers"]

    if any(
        pattern in error_code.lower() or pattern in error_message.lower()
        for pattern in ib_error_patterns
    ):
        return (
            IBProblemType.RECOVERABLE,
            "⚠️ IB GATEWAY ISSUE\n\n"
            f"{error_message}\n\n"
            "This may be a temporary IB connectivity issue.\n"
            "The system will retry automatically. If problem persists, check IB Gateway.",
            error_details,
        )

    return None, None, {}


def format_ib_diagnostic_message(
    problem_type: IBProblemType, message: str, details: Optional[dict[str, Any]] = None
) -> str:
    """
    Format a clear, actionable IB diagnostic message for CLI display.

    Args:
        problem_type: Type of IB problem detected
        message: Diagnostic message
        details: Additional diagnostic details

    Returns:
        Formatted error message for CLI display
    """
    if problem_type == IBProblemType.UNRECOVERABLE:
        header = "❌ UNRECOVERABLE IB GATEWAY ISSUE"
        footer = "\nThis error will persist until you fix the IB Gateway connection.\nAll IB operations are currently disabled to prevent system overload."

    elif problem_type == IBProblemType.RECOVERABLE:
        header = "⚠️ TEMPORARY IB ISSUE"
        footer = "\nThe system will retry automatically. If problem persists, check IB Gateway."

    elif problem_type == IBProblemType.CONFIGURATION:
        header = "🔧 IB CONFIGURATION ISSUE"
        footer = "\nPlease verify your IB Gateway settings and configuration."

    else:
        header = "❓ IB CONNECTION ISSUE"
        footer = "\nPlease check your IB Gateway connection."

    formatted_message = f"{header}\n\n{message}{footer}"

    # Add diagnostic details if available and useful
    if details and logger.isEnabledFor(logger.level):
        # Only show details in verbose/debug mode
        formatted_message += f"\n\nDiagnostic details: {details}"

    return formatted_message


def get_ib_recovery_suggestions(problem_type: IBProblemType) -> str:
    """
    Get recovery suggestions for different types of IB issues.

    Args:
        problem_type: Type of IB problem

    Returns:
        Recovery suggestions text
    """
    if problem_type == IBProblemType.UNRECOVERABLE:
        return (
            "💡 Recovery Steps:\n"
            "1. Restart IB Gateway/TWS application\n"
            "2. Wait for it to fully connect to IB servers\n"
            "3. Verify API settings are enabled\n"
            "4. Try your operation again\n"
            "5. If still failing, check network connectivity"
        )

    elif problem_type == IBProblemType.RECOVERABLE:
        return (
            "💡 Recovery Steps:\n"
            "1. Wait a moment and try again\n"
            "2. If problem persists, restart IB Gateway\n"
            "3. Check IB server status at interactivebrokers.com"
        )

    elif problem_type == IBProblemType.CONFIGURATION:
        return (
            "💡 Configuration Steps:\n"
            "1. Open IB Gateway/TWS settings\n"
            "2. Go to API > Settings\n"
            "3. Enable 'Enable ActiveX and Socket Clients'\n"
            "4. Set correct port (4002 for paper, 4001 for live)\n"
            "5. Restart IB Gateway after changes"
        )

    else:
        return (
            "💡 General Steps:\n"
            "1. Check IB Gateway is running and connected\n"
            "2. Verify API settings are enabled\n"
            "3. Restart IB Gateway if needed\n"
            "4. Check network connectivity"
        )


def should_show_ib_diagnosis(response: dict[str, Any]) -> bool:
    """
    Determine if we should show IB diagnosis for this response.

    Args:
        response: API response dictionary

    Returns:
        True if IB diagnosis should be shown
    """
    if not response:
        return False

    # Check both complete failures and partial successes with errors
    error_info = response.get("error", {})
    if not error_info:
        return False

    problem_type, _, _ = detect_ib_issue_from_api_response(response)
    return problem_type is not None
