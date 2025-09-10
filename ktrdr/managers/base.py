"""
ServiceOrchestrator base class for unified service management patterns.

This module provides the ServiceOrchestrator abstract base class that standardizes
environment-based configuration, adapter initialization, and common management
patterns across all service managers (Data, Training, Backtesting, etc.).
"""

import asyncio
import os
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable
from contextlib import asynccontextmanager
from typing import (
    Any,
    Callable,
    Generic,
    Optional,
    Protocol,
    TypeVar,
)

from ktrdr.async_infrastructure.cancellation import (
    CancellationError,
    create_cancellation_token,
    get_global_coordinator,
)
from ktrdr.async_infrastructure.cancellation import (
    CancellationToken as UnifiedCancellationToken,
)
from ktrdr.async_infrastructure.progress import (
    GenericProgressManager,
    GenericProgressState,
    ProgressRenderer,
)
from ktrdr.errors import DataError
from ktrdr.logging import get_logger

logger = get_logger(__name__)

# Generic type for the adapter
T = TypeVar("T")


class ProgressCallback(Protocol):
    """Type protocol for progress callback functions."""

    def __call__(self, progress: dict[str, Any]) -> None: ...


class CancellationToken(Protocol):
    """Type protocol for cancellation tokens."""

    @property
    def is_cancelled_requested(self) -> bool: ...


class DefaultServiceProgressRenderer(ProgressRenderer):
    """Default progress renderer for ServiceOrchestrator operations."""

    def __init__(self, service_name: str = "Service"):
        self.service_name = service_name

    def render_message(self, state: GenericProgressState) -> str:
        """Render basic progress message with service context."""
        base_message = state.message

        parts = [base_message]

        # Add service context if available
        if state.context:
            service_context = []

            # Add operation name if different from message
            operation = state.context.get("operation")
            if operation and operation != state.operation_id:
                service_context.append(operation)

            # Add any domain-specific context
            for key in ["symbol", "timeframe", "mode"]:
                if key in state.context:
                    service_context.append(f"{key}={state.context[key]}")

            if service_context:
                parts.append(f"({', '.join(service_context)})")

        # Add step progress
        if state.total_steps > 0:
            parts.append(f"[{state.current_step}/{state.total_steps}]")

        # Add percentage if available
        if state.percentage > 0:
            parts.append(f"({state.percentage:.1f}%)")

        # Add time estimation if available
        if state.estimated_remaining:
            remaining_seconds = int(state.estimated_remaining.total_seconds())
            if remaining_seconds > 0:
                if remaining_seconds < 60:
                    eta_str = f"{remaining_seconds}s"
                elif remaining_seconds < 3600:
                    eta_str = f"{remaining_seconds // 60}m {remaining_seconds % 60}s"
                else:
                    hours = remaining_seconds // 3600
                    minutes = (remaining_seconds % 3600) // 60
                    eta_str = f"{hours}h {minutes}m"
                parts.append(f"ETA: {eta_str}")

        return " ".join(parts)

    def enhance_state(self, state: GenericProgressState) -> GenericProgressState:
        """Basic state enhancement with timing estimation."""
        # Add simple time estimation if we have progress information
        if state.current_step > 0 and state.total_steps > 0 and state.start_time:
            from datetime import datetime, timedelta

            elapsed = datetime.now() - state.start_time
            if state.percentage > 0:
                estimated_total = elapsed.total_seconds() / (state.percentage / 100.0)
                estimated_remaining = max(0, estimated_total - elapsed.total_seconds())
                state.estimated_remaining = timedelta(seconds=estimated_remaining)

        return state


class ServiceOrchestrator(ABC, Generic[T]):
    """
    Base class for all service managers (Data, Training, Backtesting, etc.).

    This class orchestrates complex operations across multiple backend services,
    providing unified environment-based configuration, adapter initialization,
    and common management patterns.

    Key responsibilities:
    - Environment-based adapter configuration (host service vs local)
    - Standardized configuration interface across all managers
    - Common patterns for health checks and statistics
    - Unified error handling and logging patterns

    Subclasses must implement:
    - _initialize_adapter(): Create and configure the appropriate adapter
    - _get_service_name(): Return human-readable service name for logging
    - _get_default_host_url(): Return default host service URL
    - _get_env_var_prefix(): Return environment variable prefix (e.g., 'IB', 'TRAINING')
    """

    def __init__(self) -> None:
        """
        Initialize service orchestrator with environment-based configuration.

        This constructor automatically initializes the appropriate adapter based
        on environment variables specific to each service type.
        """
        logger.debug(f"Initializing {self._get_service_name()} orchestrator")
        self.adapter: T = self._initialize_adapter()

        # Initialize enhanced progress infrastructure
        self._progress_renderer = DefaultServiceProgressRenderer(
            self._get_service_name()
        )
        self._generic_progress_manager = GenericProgressManager(
            renderer=self._progress_renderer
        )
        self._current_operation_progress: Optional[GenericProgressManager] = None

        # Initialize unified cancellation infrastructure
        self._current_cancellation_token: Optional[UnifiedCancellationToken] = None

        logger.info(
            f"{self._get_service_name()} orchestrator initialized "
            f"(mode: {'host_service' if self.is_using_host_service() else 'local'})"
        )

    @abstractmethod
    def _initialize_adapter(self) -> T:
        """
        Initialize the appropriate adapter based on environment variables.

        This method should:
        1. Check environment variables for host service configuration
        2. Create and configure the adapter with appropriate settings
        3. Return the initialized adapter instance

        Returns:
            Initialized adapter instance specific to the service type
        """
        pass

    @abstractmethod
    def _get_service_name(self) -> str:
        """
        Get the human-readable service name for logging and configuration.

        Examples:
        - "Data/IB"
        - "Training"
        - "Backtesting"

        Returns:
            Service name string for display and logging
        """
        pass

    @abstractmethod
    def _get_default_host_url(self) -> str:
        """
        Get the default host service URL for this service type.

        Examples:
        - "http://localhost:8001" for IB Host Service
        - "http://localhost:8002" for Training Host Service

        Returns:
            Default URL string for host service
        """
        pass

    @abstractmethod
    def _get_env_var_prefix(self) -> str:
        """
        Get environment variable prefix for this service type.

        Used to construct environment variable names:
        - USE_{PREFIX}_HOST_SERVICE
        - {PREFIX}_HOST_SERVICE_URL

        Examples:
        - "IB" -> USE_IB_HOST_SERVICE, IB_HOST_SERVICE_URL
        - "TRAINING" -> USE_TRAINING_HOST_SERVICE, TRAINING_HOST_SERVICE_URL

        Returns:
            Environment variable prefix string (uppercase)
        """
        pass

    def is_using_host_service(self) -> bool:
        """
        Check if orchestrator is configured to use host service.

        Returns:
            True if using host service, False if using local/direct connection
        """
        return getattr(self.adapter, "use_host_service", False)

    def get_host_service_url(self) -> Optional[str]:
        """
        Get host service URL if using host service.

        Returns:
            Host service URL if using host service, None if using local mode
        """
        if self.is_using_host_service():
            return getattr(self.adapter, "host_service_url", None)
        return None

    def get_configuration_info(self) -> dict[str, Any]:
        """
        Get current configuration information for diagnostics and debugging.

        Returns comprehensive configuration details including:
        - Service identification
        - Operating mode (host_service vs local)
        - Host service URL (if applicable)
        - Environment variables
        - Adapter statistics

        Returns:
            Dictionary with complete configuration information
        """
        prefix = self._get_env_var_prefix()
        use_env_var = f"USE_{prefix}_HOST_SERVICE"
        url_env_var = f"{prefix}_HOST_SERVICE_URL"

        return {
            "service": self._get_service_name(),
            "mode": "host_service" if self.is_using_host_service() else "local",
            "host_service_url": self.get_host_service_url(),
            "environment_variables": {
                use_env_var: os.getenv(use_env_var),
                url_env_var: os.getenv(url_env_var),
            },
            "adapter_info": {
                "type": type(self.adapter).__name__,
                "statistics": self.get_adapter_statistics(),
            },
        }

    def get_adapter_statistics(self) -> dict[str, Any]:
        """
        Get adapter usage statistics if available.

        Returns:
            Dictionary with adapter statistics, or indication if not available
        """
        if hasattr(self.adapter, "get_statistics"):
            return self.adapter.get_statistics()
        elif hasattr(self.adapter, "requests_made"):
            # Basic statistics for adapters with simple counters
            return {
                "requests_made": getattr(self.adapter, "requests_made", 0),
                "errors_encountered": getattr(self.adapter, "errors_encountered", 0),
                "last_request_time": getattr(self.adapter, "last_request_time", None),
            }
        else:
            return {"statistics": "not_available"}

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on the orchestrator and its adapter.

        This default implementation checks adapter health if available.
        Subclasses can override to add service-specific health checks.

        Returns:
            Dictionary with health status information
        """
        orchestrator_info = {
            "orchestrator": "healthy",
            "service": self._get_service_name(),
            "mode": "host_service" if self.is_using_host_service() else "local",
        }

        if hasattr(self.adapter, "health_check"):
            try:
                adapter_health = await self.adapter.health_check()
                return {**orchestrator_info, "adapter": adapter_health}
            except Exception as e:
                logger.warning(f"Adapter health check failed: {e}")
                return {
                    **orchestrator_info,
                    "adapter": {"status": "error", "error": str(e)},
                }
        else:
            return {
                **orchestrator_info,
                "adapter": {"status": "unknown", "health_check": "not_available"},
            }

    # ==========================================
    # Enhanced Async Execution Patterns (TASK-1.4)
    # ==========================================

    async def execute_with_progress(
        self,
        operation: Awaitable[T],
        progress_callback: Optional[ProgressCallback] = None,
        timeout: Optional[float] = None,
        operation_name: str = "operation",
        total_steps: int = 0,
        context: Optional[dict[str, Any]] = None,
    ) -> T:
        """
        Execute an async operation with enhanced progress tracking and optional timeout.

        This enhanced version uses GenericProgressManager to provide rich progress features
        including TimeEstimationEngine integration, hierarchical progress, and context awareness.

        Args:
            operation: The async operation to execute
            progress_callback: Optional callback for progress updates (backward compatible)
            timeout: Optional timeout in seconds
            operation_name: Name for logging purposes
            total_steps: Total steps for hierarchical progress tracking
            context: Optional context for domain-specific information

        Returns:
            Result of the operation

        Raises:
            asyncio.TimeoutError: If operation exceeds timeout
            asyncio.CancelledError: If operation is cancelled
        """
        logger.debug(f"Starting {operation_name} with enhanced progress tracking")

        # Create enhanced progress callback wrapper for backward compatibility
        enhanced_callback = None
        if progress_callback:

            def smart_wrapper(state: GenericProgressState):
                # Try GenericProgressState first, fall back to dict format for backward compatibility
                try:
                    # First attempt: pass GenericProgressState directly
                    progress_callback(state)  # type: ignore[arg-type]
                except (TypeError, AssertionError):
                    # Fallback: convert to legacy dict format for backward compatibility
                    # AssertionError catches cases where callback tests isinstance(data, dict)
                    legacy_dict = {
                        "percentage": state.percentage,
                        "message": state.message,
                        "operation": state.operation_id,
                        "current_step": state.current_step,
                        "total_steps": state.total_steps,
                    }
                    if state.context.get("error"):
                        legacy_dict["error"] = state.context["error"]
                    progress_callback(legacy_dict)

            enhanced_callback = smart_wrapper

        # Create operation-specific progress manager
        operation_context = context or {}
        operation_context["operation"] = operation_name

        operation_progress = GenericProgressManager(
            callback=enhanced_callback, renderer=self._progress_renderer
        )

        # Store for use by update_operation_progress method
        self._current_operation_progress = operation_progress

        # Start the operation tracking
        operation_progress.start_operation(
            operation_id=operation_name,
            total_steps=max(total_steps, 1),  # Ensure at least 1 step
            context=operation_context,
        )

        try:
            if timeout:
                result = await asyncio.wait_for(operation, timeout=timeout)
            else:
                result = await operation

            # Complete the operation
            operation_progress.complete_operation()

            logger.debug(f"Completed {operation_name}")
            return result

        except asyncio.TimeoutError:
            logger.warning(f"Operation {operation_name} timed out after {timeout}s")
            # Update with timeout error
            operation_progress.update_progress(
                step=0,
                message=f"Timeout: {operation_name}",
                context={"error": "timeout"},
            )
            raise
        except Exception as e:
            logger.error(f"Operation {operation_name} failed: {e}")
            # Update with error information
            operation_progress.update_progress(
                step=0, message=f"Failed: {operation_name}", context={"error": str(e)}
            )
            raise
        finally:
            # Clear current operation
            self._current_operation_progress = None

    def update_operation_progress(
        self,
        step: int,
        message: str = "",
        items_processed: int = 0,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Update the progress of the current operation.

        This method can be called from within operations running under
        execute_with_progress to provide step-by-step progress updates.

        Args:
            step: Current step number or percentage (0-100)
            message: Progress message
            items_processed: Number of items processed
            context: Additional context information
        """
        if self._current_operation_progress:
            # Convert percentage to step if step > 100
            if step > 100:
                # Treat as percentage, convert to step based on total_steps
                if (
                    hasattr(self._current_operation_progress, "_state")
                    and self._current_operation_progress._state
                ):
                    total = self._current_operation_progress._state.total_steps
                    step = min(int((step / 100.0) * total), total)

            self._current_operation_progress.update_progress(
                step=step,
                message=message,
                items_processed=items_processed,
                context=context,
            )

    def get_current_cancellation_token(self) -> Optional[UnifiedCancellationToken]:
        """
        Get the current operation's cancellation token.

        This method can be called from within operations running under
        execute_with_cancellation to get access to the cancellation token.

        Returns:
            Current unified cancellation token if available, None otherwise
        """
        return self._current_cancellation_token

    def _is_token_cancelled(self, token: Any) -> bool:
        """
        Check if a cancellation token is cancelled, handling different token types.

        Args:
            token: Cancellation token of any type

        Returns:
            True if token indicates cancellation, False otherwise
        """
        if hasattr(token, "is_cancelled_requested"):
            return token.is_cancelled_requested
        elif hasattr(token, "is_set"):
            return token.is_set()
        elif hasattr(token, "is_cancelled"):
            return token.is_cancelled()
        elif hasattr(token, "cancelled"):
            return token.cancelled()
        return False

    async def execute_with_cancellation(
        self,
        operation: Awaitable[T],
        cancellation_token: Optional[CancellationToken] = None,
        check_interval: float = 0.1,
        operation_name: str = "operation",
    ) -> T:
        """
        Execute an async operation with unified cancellation support.

        This enhanced version integrates with the unified cancellation system while
        maintaining backward compatibility with existing CancellationToken protocol.

        Args:
            operation: The async operation to execute
            cancellation_token: Optional cancellation token to check
            check_interval: How often to check for cancellation (seconds)
            operation_name: Name for logging purposes

        Returns:
            Result of the operation

        Raises:
            asyncio.CancelledError: If operation is cancelled
            CancellationError: If operation is cancelled via unified system
        """
        logger.debug(f"Starting {operation_name} with unified cancellation support")

        # Check if token is already cancelled before starting
        if cancellation_token and self._is_token_cancelled(cancellation_token):
            logger.info(f"Operation {operation_name} cancelled before start")
            raise asyncio.CancelledError(f"Operation {operation_name} was cancelled")

        # Use unified cancellation coordinator for enhanced functionality
        coordinator = get_global_coordinator()
        operation_id = f"{self._get_service_name()}-{operation_name}-{id(operation)}"

        try:
            # If a modern cancellation token is provided, use it directly
            if cancellation_token and hasattr(cancellation_token, "operation_id"):
                # This is already our unified cancellation token
                async def wrapped_operation(token):
                    return await operation

                return await coordinator.execute_with_cancellation(
                    operation_id, wrapped_operation, operation_name
                )

            # For backward compatibility with old-style tokens or no token
            unified_token = create_cancellation_token(operation_id, coordinator)

            # Store current token for access by operations
            self._current_cancellation_token = unified_token

            # If legacy token provided, create a bridge
            if cancellation_token:

                async def legacy_bridge_check():
                    """Bridge legacy cancellation tokens to unified system."""
                    while not unified_token.is_cancelled():
                        if self._is_token_cancelled(cancellation_token):
                            unified_token.cancel("Legacy token cancellation")
                            break
                        await asyncio.sleep(check_interval)

                # Start the bridge task
                bridge_task = asyncio.create_task(legacy_bridge_check())
            else:
                bridge_task = None

            # Execute with unified cancellation
            async def bridged_operation(token):
                try:
                    return await operation
                finally:
                    # Clean up bridge task
                    if bridge_task and not bridge_task.done():
                        bridge_task.cancel()
                        try:
                            await bridge_task
                        except asyncio.CancelledError:
                            pass

            result = await coordinator.execute_with_cancellation(
                operation_id, bridged_operation, operation_name
            )

            logger.debug(f"Completed {operation_name}")
            return result

        except CancellationError as e:
            # Convert unified CancellationError to asyncio.CancelledError for backward compatibility
            logger.info(f"Operation {operation_name} was cancelled: {e.reason}")
            raise asyncio.CancelledError(
                f"Operation {operation_name} was cancelled: {e.reason}"
            )
        except asyncio.CancelledError:
            logger.info(f"Operation {operation_name} was cancelled")
            raise
        finally:
            # Clean up current token reference
            self._current_cancellation_token = None

    # ==========================================
    # Enhanced Error Handling (TASK-1.4)
    # ==========================================

    @asynccontextmanager
    async def error_context(self, operation_name: str, **context):
        """
        Context manager for standardized error handling with service context.

        Usage:
            async with orchestrator.error_context("load_data", symbol="AAPL"):
                data = await some_operation()

        Args:
            operation_name: Name of the operation for logging
            **context: Additional context information for error reporting
        """
        logger.debug(f"Starting operation: {operation_name}")
        start_time = time.time()

        try:
            yield
            duration = time.time() - start_time
            logger.debug(f"Completed operation: {operation_name} in {duration:.3f}s")
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Operation failed: {operation_name} after {duration:.3f}s - {e}",
                extra={"context": context, "operation": operation_name},
            )
            # Re-raise with additional context if it's one of our custom errors
            if hasattr(e, "details") and isinstance(e, DataError):
                e.details.update(
                    {
                        "service": self._get_service_name(),
                        "operation": operation_name,
                        "duration": duration,
                        **context,
                    }
                )
            raise

    async def with_error_handling(
        self, operation: Awaitable[T], operation_name: str, **context
    ) -> T:
        """
        Execute an operation with standardized error handling.

        Args:
            operation: The async operation to execute
            operation_name: Name of the operation for logging
            **context: Additional context for error reporting

        Returns:
            Result of the operation
        """
        async with self.error_context(operation_name, **context):
            return await operation

    # ==========================================
    # Enhanced Configuration Management (TASK-1.4)
    # ==========================================

    def validate_configuration(self) -> dict[str, Any]:
        """
        Validate current configuration and return validation report.

        Returns:
            Dictionary with validation results and any issues found
        """
        logger.debug(f"Validating configuration for {self._get_service_name()}")

        validation_report: dict[str, Any] = {
            "service": self._get_service_name(),
            "valid": True,
            "issues": [],
            "warnings": [],
        }

        # Validate environment variables
        prefix = self._get_env_var_prefix()
        use_env_var = f"USE_{prefix}_HOST_SERVICE"
        url_env_var = f"{prefix}_HOST_SERVICE_URL"

        env_enabled = os.getenv(use_env_var, "").lower()
        host_url = os.getenv(url_env_var)

        # Check for configuration consistency
        if env_enabled in ("true", "1", "yes"):
            if not host_url:
                validation_report["warnings"].append(
                    {
                        "type": "missing_url",
                        "message": f"{url_env_var} not set but host service is enabled",
                        "recommendation": f"Set {url_env_var} or use default: {self._get_default_host_url()}",
                    }
                )

        # Validate adapter configuration
        if hasattr(self.adapter, "validate_configuration"):
            try:
                adapter_validation = self.adapter.validate_configuration()
                if not adapter_validation.get("valid", True):
                    validation_report["valid"] = False
                    validation_report["issues"].extend(
                        adapter_validation.get("issues", [])
                    )
            except Exception as e:
                validation_report["warnings"].append(
                    {
                        "type": "adapter_validation_failed",
                        "message": f"Could not validate adapter configuration: {e}",
                    }
                )

        logger.debug(
            f"Configuration validation completed: "
            f"{'valid' if validation_report['valid'] else 'invalid'}"
        )
        return validation_report

    def get_configuration_schema(self) -> dict[str, Any]:
        """
        Get the configuration schema for this service orchestrator.

        Returns:
            Dictionary describing the expected configuration structure
        """
        prefix = self._get_env_var_prefix()
        return {
            "service": self._get_service_name(),
            "environment_variables": {
                f"USE_{prefix}_HOST_SERVICE": {
                    "type": "boolean",
                    "description": "Whether to use host service or direct connection",
                    "values": ["true", "false", "1", "0", "yes", "no"],
                    "default": "false",
                },
                f"{prefix}_HOST_SERVICE_URL": {
                    "type": "url",
                    "description": "URL for the host service",
                    "default": self._get_default_host_url(),
                    "required_when": f"USE_{prefix}_HOST_SERVICE is true",
                },
            },
            "adapter_configuration": "Adapter-specific configuration (see adapter schema)",
        }

    # ==========================================
    # Enhanced Health Check Interface (TASK-1.4)
    # ==========================================

    async def health_check_with_custom_checks(
        self, custom_checks: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """
        Perform enhanced health check with optional custom checks.

        Args:
            custom_checks: List of custom check names to perform

        Returns:
            Dictionary with comprehensive health status
        """
        # Start with base health check
        health_status = await self.health_check()

        # Add configuration validation
        config_validation = self.validate_configuration()
        health_status["configuration"] = {
            "valid": config_validation["valid"],
            "issues_count": len(config_validation["issues"]),
            "warnings_count": len(config_validation["warnings"]),
        }

        # Add custom checks if requested
        if custom_checks:
            custom_results = {}
            for check_name in custom_checks:
                try:
                    if hasattr(self.adapter, f"health_check_{check_name}"):
                        check_method = getattr(
                            self.adapter, f"health_check_{check_name}"
                        )
                        if asyncio.iscoroutinefunction(check_method):
                            custom_results[check_name] = await check_method()
                        else:
                            custom_results[check_name] = check_method()
                    else:
                        custom_results[check_name] = {
                            "status": "not_implemented",
                            "message": f"Check {check_name} not available",
                        }
                except Exception as e:
                    custom_results[check_name] = {"status": "error", "error": str(e)}

            health_status["custom_checks"] = custom_results

        return health_status

    # ==========================================
    # Reusable Operation Patterns (TASK-1.4)
    # ==========================================

    def wrap_operation(
        self,
        operation_name: str,
        progress_callback: Optional[ProgressCallback] = None,
        cancellation_token: Optional[CancellationToken] = None,
        timeout: Optional[float] = None,
    ):
        """
        Create a wrapper for common operation patterns.

        This is a convenience method that combines progress tracking,
        cancellation support, and error handling.

        Args:
            operation_name: Name of the operation
            progress_callback: Optional progress callback
            cancellation_token: Optional cancellation token
            timeout: Optional timeout in seconds

        Returns:
            Decorator function for operations
        """

        def decorator(operation_func):
            async def wrapper(*args, **kwargs):
                async def run_operation():
                    if cancellation_token:
                        return await self.execute_with_cancellation(
                            operation_func(*args, **kwargs),
                            cancellation_token=cancellation_token,
                            operation_name=operation_name,
                        )
                    else:
                        return await operation_func(*args, **kwargs)

                return await self.execute_with_progress(
                    run_operation(),
                    progress_callback=progress_callback,
                    timeout=timeout,
                    operation_name=operation_name,
                )

            return wrapper

        return decorator

    async def retry_with_backoff(
        self,
        operation: Callable[[], Awaitable[T]],
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_factor: float = 2.0,
        operation_name: str = "operation",
    ) -> T:
        """
        Execute an operation with exponential backoff retry logic.

        Args:
            operation: Function that returns an awaitable
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            exponential_factor: Factor for exponential backoff
            operation_name: Name for logging purposes

        Returns:
            Result of the operation

        Raises:
            The last exception encountered if all retries fail
        """
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                logger.debug(
                    f"Attempting {operation_name} (attempt {attempt + 1}/{max_retries + 1})"
                )
                result = await operation()

                if attempt > 0:
                    logger.info(
                        f"Operation {operation_name} succeeded on attempt {attempt + 1}"
                    )

                return result

            except Exception as e:
                last_exception = e

                if attempt < max_retries:
                    delay = min(base_delay * (exponential_factor**attempt), max_delay)
                    logger.warning(
                        f"Operation {operation_name} failed on attempt {attempt + 1}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Operation {operation_name} failed after {max_retries + 1} attempts: {e}"
                    )

        # Re-raise the last exception
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError(
                f"Operation {operation_name} failed with no exception recorded"
            )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"{self.__class__.__name__}("
            f"service={self._get_service_name()}, "
            f"mode={'host_service' if self.is_using_host_service() else 'local'}, "
            f"adapter={type(self.adapter).__name__})"
        )
