"""
Service error message formatter for creating actionable, user-friendly error messages.

This module provides the ServiceErrorFormatter class that converts technical
service exceptions into clear, actionable error messages with specific
troubleshooting steps for users.
"""

import os
from typing import Optional, Union

from ktrdr.errors.exceptions import (
    KtrdrError,
    ServiceConfigurationError,
    ServiceConnectionError,
    ServiceTimeoutError,
)


class ServiceErrorFormatter:
    """
    Formatter for creating actionable service error messages.

    Converts technical service exceptions into user-friendly messages
    with specific troubleshooting steps and configuration guidance.
    """

    # Service-specific configuration
    SERVICE_CONFIG = {
        "ib-host": {
            "name": "IB Host Service",
            "default_port": "5001",
            "start_script": "./ib-host-service/start.sh",
            "log_path": "ib-host-service/logs/ib-host-service.log",
            "url_env": "IB_HOST_SERVICE_URL",
            "enable_env": "USE_IB_HOST_SERVICE",
            "default_url": "http://localhost:5001",
        },
        "training-host": {
            "name": "Training Host Service",
            "default_port": "8002",
            "start_script": "./training-host-service/start.sh",
            "log_path": "training-host-service/logs/training-host-service.log",
            "url_env": "TRAINING_HOST_SERVICE_URL",
            "enable_env": "USE_TRAINING_HOST_SERVICE",
            "default_url": "http://localhost:8002",
        },
    }

    @classmethod
    def format_service_error(
        cls,
        error: Union[KtrdrError, Exception, None],
        operation_context: Optional[str] = None,
    ) -> str:
        """
        Format a service error into an actionable, user-friendly message.

        Args:
            error: The service exception to format
            operation_context: Optional context about what operation failed

        Returns:
            Formatted error message with troubleshooting steps
        """
        if error is None:
            return "Unknown service error occurred. Check service configuration and connectivity."

        # Handle non-service errors by returning original message
        if not isinstance(
            error,
            (ServiceConnectionError, ServiceTimeoutError, ServiceConfigurationError),
        ):
            return str(error)

        # Extract service info from error details
        service_name = error.details.get("service") if error.details else None
        service_config = (
            cls.SERVICE_CONFIG.get(service_name, {}) if service_name else {}
        )

        # Format based on error type
        if isinstance(error, ServiceConnectionError):
            return cls._format_connection_error(
                error, service_config, operation_context
            )
        elif isinstance(error, ServiceTimeoutError):
            return cls._format_timeout_error(error, service_config, operation_context)
        elif isinstance(error, ServiceConfigurationError):
            return cls._format_configuration_error(
                error, service_config, operation_context
            )
        else:
            return cls._format_generic_error(error, service_config, operation_context)

    @classmethod
    def _format_connection_error(
        cls,
        error: ServiceConnectionError,
        service_config: dict,
        operation_context: Optional[str] = None,
    ) -> str:
        """Format connection errors with actionable troubleshooting steps."""
        service_name = error.details.get("service") if error.details else None
        endpoint = (
            error.details.get("endpoint", "unknown endpoint")
            if error.details
            else "unknown endpoint"
        )

        # Include additional context from operation details
        operation_symbol = error.details.get("symbol") if error.details else None

        if service_config:
            # Known service - provide specific guidance
            service_display_name = service_config["name"]
            start_script = service_config["start_script"]
            log_path = service_config["log_path"]
            port = service_config["default_port"]

            message_parts = []

            # Main error message with operation context
            if operation_context:
                context_msg = operation_context
                if operation_symbol:
                    context_msg += f" for {operation_symbol}"
                message_parts.append(
                    f"{context_msg}: {service_display_name} unavailable."
                )
            else:
                message_parts.append(f"{service_display_name} unavailable.")

            message_parts.append("")
            message_parts.append("Troubleshooting steps:")
            message_parts.append(f"1. Check if service is running: {start_script}")
            message_parts.append(f"2. Verify port {port} is not blocked")
            message_parts.append(f"3. Check logs: tail -f {log_path}")
            message_parts.append(f"4. Confirm service URL: {endpoint}")

            # Include technical details for debugging
            if "original_exception" in error.details:
                message_parts.append("")
                message_parts.append("Technical details:")
                message_parts.append(f"  {error.details['original_exception']}")

        else:
            # Unknown service or missing service details - provide fallback guidance
            message_parts = []

            if operation_context:
                message_parts.append(f"{operation_context}: Service connection failed.")
            elif not service_name:
                # Missing or empty service details
                message_parts.append("Service connection failed.")
            else:
                # Has service name but not in our known services
                message_parts.append(f"Service {service_name} is unavailable.")

            message_parts.append("")
            message_parts.append("Troubleshooting steps:")
            if endpoint != "unknown endpoint":
                message_parts.append(f"1. Check service status at {endpoint}")
            else:
                message_parts.append("1. Check service status")
            message_parts.append("2. Check service configuration")
            message_parts.append("3. Check network connectivity")

        return "\n".join(message_parts)

    @classmethod
    def _format_timeout_error(
        cls,
        error: ServiceTimeoutError,
        service_config: dict,
        operation_context: Optional[str] = None,
    ) -> str:
        """Format timeout errors with performance troubleshooting."""
        service_name = error.details.get("service", "unknown-service")
        timeout_seconds = error.details.get("timeout_seconds", "unknown")
        endpoint = error.details.get("endpoint", "unknown endpoint")

        if service_config:
            service_display_name = service_config["name"]
            log_path = service_config["log_path"]

            message_parts = []

            if operation_context:
                message_parts.append(
                    f"{operation_context}: {service_display_name} request timed out after {timeout_seconds} seconds."
                )
            else:
                message_parts.append(
                    f"{service_display_name} request timed out after {timeout_seconds} seconds."
                )

            message_parts.append("")
            message_parts.append("Troubleshooting steps:")
            message_parts.append("1. Check if service is overloaded or slow to respond")
            message_parts.append(f"2. Check service logs: tail -f {log_path}")
            message_parts.append(
                "3. Increase timeout if this is a large/complex operation"
            )
            message_parts.append(
                "4. Verify service has adequate resources (CPU, memory)"
            )

        else:
            message_parts = []

            if operation_context:
                message_parts.append(
                    f"{operation_context}: Service {service_name} timed out after {timeout_seconds} seconds."
                )
            else:
                message_parts.append(
                    f"Service {service_name} timed out after {timeout_seconds} seconds."
                )

            message_parts.append("")
            message_parts.append("Troubleshooting steps:")
            message_parts.append(f"1. Check service performance at {endpoint}")
            message_parts.append("2. Verify service resources and load")
            message_parts.append(
                "3. Consider increasing timeout for complex operations"
            )

        return "\n".join(message_parts)

    @classmethod
    def _format_configuration_error(
        cls,
        error: ServiceConfigurationError,
        service_config: dict,
        operation_context: Optional[str] = None,
    ) -> str:
        """Format configuration errors with valid options and examples."""
        config_key = error.details.get("config_key", "unknown configuration")
        current_value = error.details.get("current_value")

        message_parts = []

        # Handle specific configuration keys
        if config_key in ["USE_IB_HOST_SERVICE", "USE_TRAINING_HOST_SERVICE"]:
            # Boolean configuration error
            if operation_context:
                message_parts.append(f"{operation_context}: Invalid configuration.")

            message_parts.append(
                f"Invalid configuration: {config_key} must be 'true' or 'false', got '{current_value}'"
            )
            message_parts.append("")
            message_parts.append("Valid options:")
            message_parts.append(f"  export {config_key}=true   # Enable service")
            message_parts.append(f"  export {config_key}=false  # Disable service")

        elif config_key in ["IB_HOST_SERVICE_URL", "TRAINING_HOST_SERVICE_URL"]:
            # URL configuration error
            if service_config:
                default_url = service_config["default_url"]
                service_display_name = service_config["name"]

                if current_value is None:
                    message_parts.append(
                        f"{config_key} is required when {service_display_name} is enabled."
                    )
                else:
                    message_parts.append(f"Invalid {config_key}: '{current_value}'")

                message_parts.append("")
                message_parts.append("Example configuration:")
                message_parts.append(f"  export {config_key}={default_url}")
            else:
                message_parts.append(
                    f"Configuration error: {config_key} = '{current_value}'"
                )
                message_parts.append(
                    "Please check service configuration documentation."
                )

        else:
            # Generic configuration error
            if operation_context:
                message_parts.append(f"{operation_context}: Configuration error.")

            message_parts.append(
                f"Invalid configuration: {config_key} = '{current_value}'"
            )
            message_parts.append("Please check service configuration documentation.")

        return "\n".join(message_parts)

    @classmethod
    def _format_generic_error(
        cls,
        error: KtrdrError,
        service_config: dict,
        operation_context: Optional[str] = None,
    ) -> str:
        """Format generic service errors with fallback guidance."""
        message_parts = []

        if operation_context:
            message_parts.append(f"{operation_context}: Service connection failed.")
        else:
            message_parts.append("Service connection failed.")

        message_parts.append("")
        message_parts.append("Troubleshooting steps:")
        message_parts.append("1. Check service configuration")
        message_parts.append("2. Check service connectivity")
        message_parts.append("3. Review service logs for errors")

        return "\n".join(message_parts)

    @classmethod
    def validate_service_configuration(cls) -> list[str]:
        """
        Validate current service configuration and return list of issues.

        Returns:
            List of configuration error messages, empty if all valid
        """
        errors = []

        # Check IB Host Service configuration
        ib_enabled = os.getenv("USE_IB_HOST_SERVICE", "").lower()
        if ib_enabled and ib_enabled not in ["", "true", "false"]:
            errors.append(
                f"Invalid configuration: USE_IB_HOST_SERVICE must be 'true' or 'false', got '{ib_enabled}'"
            )

        if ib_enabled == "true":
            ib_url = os.getenv("IB_HOST_SERVICE_URL")
            if not ib_url:
                errors.append(
                    "IB_HOST_SERVICE_URL is required when USE_IB_HOST_SERVICE=true\n"
                    "Example: export IB_HOST_SERVICE_URL=http://localhost:5001"
                )

        # Check Training Host Service configuration
        training_enabled = os.getenv("USE_TRAINING_HOST_SERVICE", "").lower()
        if training_enabled and training_enabled not in ["", "true", "false"]:
            errors.append(
                f"Invalid configuration: USE_TRAINING_HOST_SERVICE must be 'true' or 'false', got '{training_enabled}'"
            )

        if training_enabled == "true":
            training_url = os.getenv("TRAINING_HOST_SERVICE_URL")
            if not training_url:
                errors.append(
                    "TRAINING_HOST_SERVICE_URL is required when USE_TRAINING_HOST_SERVICE=true\n"
                    "Example: export TRAINING_HOST_SERVICE_URL=http://localhost:8002"
                )

        return errors
