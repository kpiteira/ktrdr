"""
IB Connection Diagnosis Utilities

Provides rapid diagnosis of IB Gateway connectivity issues
to give clear, actionable error messages.
"""

import asyncio
import socket
import time
from typing import Dict, Any, Optional, Tuple
from enum import Enum

from ktrdr import get_logger
from ktrdr.config.ib_config import get_ib_config

logger = get_logger(__name__)


class IBProblemType(Enum):
    UNRECOVERABLE = "unrecoverable"  # Restart IB Gateway required
    RECOVERABLE = "recoverable"  # Retry may work
    CONFIGURATION = "configuration"  # Settings issue
    UNKNOWN = "unknown"  # Unknown issue


class IBDiagnosis:
    """Rapid IB connectivity diagnosis."""

    @staticmethod
    async def diagnose_connection() -> Tuple[IBProblemType, str, Dict[str, Any]]:
        """
        Rapidly diagnose IB connection issues.

        Returns:
            (problem_type, message, details)
        """
        config = get_ib_config()
        host = config.host
        port = config.port

        # Step 1: Test TCP connectivity
        tcp_ok, tcp_details = await IBDiagnosis._test_tcp_connection(host, port)

        if not tcp_ok:
            return (
                IBProblemType.UNRECOVERABLE,
                f"🚨 IB Gateway NOT ACCESSIBLE at {host}:{port}\n\n"
                f"REQUIRED ACTION: Start IB Gateway/TWS and ensure it's listening on port {port}",
                {"tcp_test": tcp_details, "host": host, "port": port},
            )

        # Step 2: Test if it's a silent connection (TCP works but IB doesn't)
        silent_connection = await IBDiagnosis._test_silent_connection()

        if silent_connection:
            return (
                IBProblemType.UNRECOVERABLE,
                f"🚨 SILENT IB CONNECTION DETECTED\n\n"
                f"TCP connection to {host}:{port} works but IB operations timeout.\n"
                f"This indicates a port forwarding or API configuration issue.\n\n"
                f"REQUIRED ACTION:\n"
                f"1. Check IB Gateway API settings (Enable API, correct port)\n"
                f"2. If using Docker: verify host.docker.internal resolution\n"
                f"3. Restart IB Gateway to refresh API connections\n"
                f"4. Check firewall/network blocking data transmission",
                {"tcp_test": tcp_details, "silent_connection": True},
            )

        # Step 3: If we get here, it's likely a temporary/recoverable issue
        return (
            IBProblemType.RECOVERABLE,
            f"⚠️ Temporary IB connectivity issue\n\n"
            f"Connection to {host}:{port} appears functional but operations are failing.\n"
            f"This may be a temporary network or IB server issue.\n\n"
            f"SUGGESTED ACTION: Wait and retry. If problem persists, restart IB Gateway.",
            {"tcp_test": tcp_details, "silent_connection": False},
        )

    @staticmethod
    async def _test_tcp_connection(
        host: str, port: int, timeout: float = 5.0
    ) -> Tuple[bool, Dict[str, Any]]:
        """Test basic TCP connectivity to IB Gateway."""
        start_time = time.time()

        try:
            # Try to connect via socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)

            # Resolve host.docker.internal if needed
            if host == "host.docker.internal":
                try:
                    resolved_host = socket.gethostbyname(host)
                except socket.gaierror:
                    return (
                        False,
                        {
                            "error": "host.docker.internal resolution failed",
                            "suggestion": "Docker Desktop not running or host resolution issue",
                        },
                    )
            else:
                resolved_host = host

            result = sock.connect_ex((resolved_host, port))
            sock.close()

            duration_ms = (time.time() - start_time) * 1000

            if result == 0:
                return (
                    True,
                    {
                        "status": "connected",
                        "host": host,
                        "resolved_host": resolved_host,
                        "port": port,
                        "duration_ms": duration_ms,
                    },
                )
            else:
                return (
                    False,
                    {
                        "error": f"Connection refused (code: {result})",
                        "host": host,
                        "port": port,
                        "suggestion": "IB Gateway not running or not listening on this port",
                    },
                )

        except socket.timeout:
            return (
                False,
                {
                    "error": "Connection timeout",
                    "timeout_seconds": timeout,
                    "suggestion": "Network issue or wrong host/port",
                },
            )
        except Exception as e:
            return (
                False,
                {"error": str(e), "suggestion": "Network or configuration issue"},
            )

    @staticmethod
    async def _test_silent_connection() -> bool:
        """Test if we have a silent connection (TCP works but IB operations don't)."""
        try:
            # Try to import and test IB connection quickly
            from ktrdr.data.ib_connection_pool import acquire_ib_connection
            from ktrdr.data.ib_client_id_registry import ClientIdPurpose

            # Quick test with very short timeout
            async with acquire_ib_connection(
                purpose=ClientIdPurpose.API_POOL, requested_by="diagnosis_test"
            ) as connection:
                # Try a very simple operation with short timeout
                try:
                    await asyncio.wait_for(
                        connection.ib.reqCurrentTimeAsync(),
                        timeout=3.0,  # Very short timeout
                    )
                    return False  # Operation worked - not a silent connection
                except asyncio.TimeoutError:
                    return True  # Timeout = silent connection detected
                except Exception:
                    return False  # Other error, not necessarily silent

        except Exception:
            # If we can't even acquire a connection, it's not a silent connection issue
            return False


def get_clear_error_message(problem_type: IBProblemType, message: str) -> str:
    """Get a clear, actionable error message for CLI/API responses."""

    if problem_type == IBProblemType.UNRECOVERABLE:
        return (
            f"❌ UNRECOVERABLE IB GATEWAY ISSUE\n\n"
            f"{message}\n\n"
            f"This error will persist until you fix the IB Gateway connection.\n"
            f"All IB operations are currently disabled to prevent system overload."
        )
    elif problem_type == IBProblemType.RECOVERABLE:
        return (
            f"⚠️ TEMPORARY IB ISSUE\n\n"
            f"{message}\n\n"
            f"The system will retry automatically. If problem persists, check IB Gateway."
        )
    else:
        return f"❓ IB CONNECTION ISSUE\n\n{message}"
