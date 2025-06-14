"""
IB Health Monitor

Advanced health monitoring and alerting system for Interactive Brokers connections.
Provides real-time health assessment, anomaly detection, and automated recovery.
"""

import asyncio
import time
import statistics
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from collections import deque, defaultdict
import json
from pathlib import Path

from ktrdr.logging import get_logger
from ktrdr.data.ib_metrics_collector import (
    get_metrics_collector,
    record_counter,
    record_gauge,
    record_operation_start,
    record_operation_end,
)

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthMetric:
    """Individual health metric."""

    name: str
    value: float
    threshold_warning: float
    threshold_critical: float
    unit: str = ""
    direction: str = "lower_is_better"  # "lower_is_better" or "higher_is_better"
    timestamp: float = field(default_factory=time.time)

    def get_status(self) -> HealthStatus:
        """Get health status based on thresholds."""
        if self.direction == "lower_is_better":
            if self.value >= self.threshold_critical:
                return HealthStatus.CRITICAL
            elif self.value >= self.threshold_warning:
                return HealthStatus.WARNING
        else:  # higher_is_better
            if self.value <= self.threshold_critical:
                return HealthStatus.CRITICAL
            elif self.value <= self.threshold_warning:
                return HealthStatus.WARNING

        return HealthStatus.HEALTHY


@dataclass
class HealthAlert:
    """Health alert notification."""

    id: str
    component: str
    metric_name: str
    severity: AlertSeverity
    status: HealthStatus
    message: str
    value: float
    threshold: float
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: Optional[float] = None


@dataclass
class ComponentHealth:
    """Health assessment for a component."""

    component_name: str
    status: HealthStatus
    metrics: Dict[str, HealthMetric] = field(default_factory=dict)
    alerts: List[HealthAlert] = field(default_factory=list)
    last_check: float = field(default_factory=time.time)
    consecutive_failures: int = 0
    recovery_actions_taken: List[str] = field(default_factory=list)


class IbHealthMonitor:
    """
    Advanced health monitoring system for IB components.

    Features:
    - Real-time health assessment
    - Anomaly detection and alerting
    - Automated recovery actions
    - Health trend analysis
    - Configurable thresholds and actions
    """

    def __init__(
        self,
        check_interval: float = 30.0,
        enable_auto_recovery: bool = True,
        alert_cooldown: float = 300.0,  # 5 minutes
        max_recovery_attempts: int = 3,
    ):
        """
        Initialize health monitor.

        Args:
            check_interval: How often to check health (seconds)
            enable_auto_recovery: Whether to enable automatic recovery
            alert_cooldown: Minimum time between similar alerts (seconds)
            max_recovery_attempts: Maximum recovery attempts per issue
        """
        self.check_interval = check_interval
        self.enable_auto_recovery = enable_auto_recovery
        self.alert_cooldown = alert_cooldown
        self.max_recovery_attempts = max_recovery_attempts

        # Component health tracking
        self._component_health: Dict[str, ComponentHealth] = {}
        self._overall_status = HealthStatus.HEALTHY

        # Alert management
        self._alerts: List[HealthAlert] = []
        self._alert_history: deque = deque(maxlen=1000)
        self._last_alert_time: Dict[str, float] = {}  # alert_key -> timestamp

        # Health trends
        self._health_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # Recovery actions
        self._recovery_actions: Dict[str, Callable] = {}
        self._recovery_attempts: Dict[str, int] = defaultdict(int)

        # Monitoring control
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

        # Default health metrics configuration
        self._metric_configs = {
            "connection_pool": {
                "success_rate": HealthMetric(
                    "success_rate", 0, 95.0, 80.0, "%", "higher_is_better"
                ),
                "average_duration": HealthMetric(
                    "average_duration", 0, 5.0, 10.0, "s", "lower_is_better"
                ),
                "failed_connections": HealthMetric(
                    "failed_connections", 0, 3, 10, "count", "lower_is_better"
                ),
                "unhealthy_connections": HealthMetric(
                    "unhealthy_connections", 0, 1, 3, "count", "lower_is_better"
                ),
            },
            "data_fetcher": {
                "success_rate": HealthMetric(
                    "success_rate", 0, 90.0, 70.0, "%", "higher_is_better"
                ),
                "average_duration": HealthMetric(
                    "average_duration", 0, 10.0, 30.0, "s", "lower_is_better"
                ),
                "pace_violations": HealthMetric(
                    "pace_violations", 0, 5, 20, "count", "lower_is_better"
                ),
            },
            "symbol_validator": {
                "success_rate": HealthMetric(
                    "success_rate", 0, 95.0, 85.0, "%", "higher_is_better"
                ),
                "cache_hit_rate": HealthMetric(
                    "cache_hit_rate", 0, 80.0, 50.0, "%", "higher_is_better"
                ),
            },
            "pace_manager": {
                "violations_per_hour": HealthMetric(
                    "violations_per_hour", 0, 10, 50, "count/h", "lower_is_better"
                ),
                "average_wait_time": HealthMetric(
                    "average_wait_time", 0, 30.0, 120.0, "s", "lower_is_better"
                ),
            },
        }

        # Register default recovery actions
        self._register_default_recovery_actions()

        logger.info(
            f"IB Health Monitor initialized (check_interval: {check_interval}s)"
        )

    def _register_default_recovery_actions(self):
        """Register default recovery actions for common issues."""

        async def restart_connection_pool():
            """Restart the connection pool."""
            try:
                from ktrdr.data.ib_connection_pool import get_connection_pool

                pool = await get_connection_pool()
                await pool.stop()
                await asyncio.sleep(2)
                await pool.start()
                logger.info("🔄 Connection pool restarted as recovery action")
                return True
            except Exception as e:
                logger.error(f"Failed to restart connection pool: {e}")
                return False

        async def cleanup_unhealthy_connections():
            """Clean up unhealthy connections."""
            try:
                from ktrdr.data.ib_connection_pool import get_connection_pool

                pool = await get_connection_pool()
                await pool._cleanup_idle_connections()
                logger.info("🧹 Cleaned up unhealthy connections as recovery action")
                return True
            except Exception as e:
                logger.error(f"Failed to cleanup connections: {e}")
                return False

        async def reset_pace_manager():
            """Reset pace manager statistics."""
            try:
                from ktrdr.data.ib_pace_manager import get_pace_manager

                pace_manager = get_pace_manager()
                pace_manager.reset_statistics()
                logger.info("🔄 Pace manager reset as recovery action")
                return True
            except Exception as e:
                logger.error(f"Failed to reset pace manager: {e}")
                return False

        # Register recovery actions
        self._recovery_actions["restart_connection_pool"] = restart_connection_pool
        self._recovery_actions["cleanup_unhealthy_connections"] = (
            cleanup_unhealthy_connections
        )
        self._recovery_actions["reset_pace_manager"] = reset_pace_manager

    async def start(self) -> bool:
        """Start the health monitoring."""
        if self._running:
            logger.warning("Health monitor is already running")
            return True

        try:
            self._running = True
            self._stop_event.clear()

            # Start monitoring task
            self._monitor_task = asyncio.create_task(self._monitoring_loop())

            logger.info("✅ IB Health Monitor started")
            record_counter("health_monitor", "monitor_started")
            return True

        except Exception as e:
            logger.error(f"Failed to start health monitor: {e}")
            self._running = False
            return False

    async def stop(self):
        """Stop the health monitoring."""
        if not self._running:
            return

        logger.info("Stopping health monitor...")
        self._running = False
        self._stop_event.set()

        # Wait for monitoring task to finish
        if self._monitor_task:
            try:
                await asyncio.wait_for(self._monitor_task, timeout=10.0)
            except asyncio.TimeoutError:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass

        logger.info("✅ Health monitor stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        logger.info("Health monitoring loop started")

        while self._running and not self._stop_event.is_set():
            try:
                operation_id = record_operation_start("health_monitor", "health_check")

                # Perform health checks
                await self._check_all_components()

                # Update overall status
                self._update_overall_status()

                # Process alerts
                await self._process_alerts()

                # Record metrics
                self._record_health_metrics()

                record_operation_end(
                    operation_id, "health_monitor", "health_check", True
                )

            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                record_counter("health_monitor", "monitoring_error")

            # Wait for next check
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.check_interval
                )
                break  # Stop event was set
            except asyncio.TimeoutError:
                pass  # Continue monitoring

        logger.info("Health monitoring loop ended")

    async def _check_all_components(self):
        """Check health of all IB components."""
        metrics_collector = get_metrics_collector()

        # Check connection pool
        await self._check_component_health("connection_pool", metrics_collector)

        # Check data fetcher
        await self._check_component_health("data_fetcher", metrics_collector)

        # Check symbol validator
        await self._check_component_health("symbol_validator", metrics_collector)

        # Check pace manager
        await self._check_component_health("pace_manager", metrics_collector)

    async def _check_component_health(self, component_name: str, metrics_collector):
        """Check health of a specific component."""
        try:
            # Get component metrics
            component_metrics = metrics_collector.get_component_metrics(component_name)
            if not component_metrics:
                # Component not found or no metrics
                self._set_component_status(component_name, HealthStatus.OFFLINE)
                return

            # Get metric configurations for this component
            metric_configs = self._metric_configs.get(component_name, {})

            # Initialize component health if not exists
            if component_name not in self._component_health:
                self._component_health[component_name] = ComponentHealth(
                    component_name=component_name, status=HealthStatus.HEALTHY
                )

            component_health = self._component_health[component_name]
            component_health.last_check = time.time()

            # Check each metric
            worst_status = HealthStatus.HEALTHY

            for metric_name, config in metric_configs.items():
                # Get current value from metrics
                current_value = self._get_metric_value(component_metrics, metric_name)

                # Create health metric
                health_metric = HealthMetric(
                    name=metric_name,
                    value=current_value,
                    threshold_warning=config.threshold_warning,
                    threshold_critical=config.threshold_critical,
                    unit=config.unit,
                    direction=config.direction,
                )

                # Update component health
                component_health.metrics[metric_name] = health_metric

                # Check status
                metric_status = health_metric.get_status()
                if metric_status.value in ["critical", "degraded"]:
                    worst_status = HealthStatus.CRITICAL
                elif (
                    metric_status.value == "warning"
                    and worst_status == HealthStatus.HEALTHY
                ):
                    worst_status = HealthStatus.WARNING

                # Generate alerts if needed
                await self._check_metric_alerts(component_name, health_metric)

            # Update component status
            if worst_status != HealthStatus.HEALTHY:
                component_health.consecutive_failures += 1
            else:
                component_health.consecutive_failures = 0

            component_health.status = worst_status

            # Record health trend
            self._health_history[component_name].append(
                {
                    "timestamp": time.time(),
                    "status": worst_status.value,
                    "metrics": {
                        name: metric.value
                        for name, metric in component_health.metrics.items()
                    },
                }
            )

        except Exception as e:
            logger.error(f"Error checking health for {component_name}: {e}")
            self._set_component_status(component_name, HealthStatus.CRITICAL)

    def _get_metric_value(self, component_metrics, metric_name: str) -> float:
        """Extract metric value from component metrics."""
        if metric_name == "success_rate":
            return component_metrics.success_rate
        elif metric_name == "average_duration":
            return component_metrics.average_duration
        elif metric_name == "failed_connections":
            return component_metrics.connections_failed
        elif metric_name == "pace_violations":
            return component_metrics.pace_violations
        elif metric_name == "cache_hit_rate":
            total_requests = (
                component_metrics.cache_hits + component_metrics.cache_misses
            )
            if total_requests > 0:
                return (component_metrics.cache_hits / total_requests) * 100
            return 100.0
        elif metric_name == "violations_per_hour":
            # Calculate violations per hour based on uptime
            uptime_hours = max(1, component_metrics.total_duration / 3600)
            return component_metrics.pace_violations / uptime_hours
        elif metric_name == "average_wait_time":
            if component_metrics.pace_waits > 0:
                return (
                    component_metrics.total_pace_wait_time
                    / component_metrics.pace_waits
                )
            return 0.0
        elif metric_name == "unhealthy_connections":
            # This would need to be calculated from connection pool
            return 0  # Placeholder

        return 0.0

    async def _check_metric_alerts(self, component_name: str, metric: HealthMetric):
        """Check if metric should generate alerts."""
        metric_status = metric.get_status()

        if metric_status in [HealthStatus.WARNING, HealthStatus.CRITICAL]:
            alert_key = f"{component_name}_{metric.name}_{metric_status.value}"

            # Check cooldown
            last_alert = self._last_alert_time.get(alert_key, 0)
            if time.time() - last_alert < self.alert_cooldown:
                return

            # Create alert
            severity = (
                AlertSeverity.WARNING
                if metric_status == HealthStatus.WARNING
                else AlertSeverity.CRITICAL
            )
            threshold = (
                metric.threshold_warning
                if metric_status == HealthStatus.WARNING
                else metric.threshold_critical
            )

            alert = HealthAlert(
                id=f"{alert_key}_{int(time.time())}",
                component=component_name,
                metric_name=metric.name,
                severity=severity,
                status=metric_status,
                message=f"{component_name} {metric.name} is {metric.value:.2f}{metric.unit} (threshold: {threshold:.2f}{metric.unit})",
                value=metric.value,
                threshold=threshold,
            )

            self._alerts.append(alert)
            self._alert_history.append(alert)
            self._last_alert_time[alert_key] = time.time()

            logger.warning(f"🚨 Health Alert: {alert.message}")
            record_counter(
                "health_monitor",
                "alert_generated",
                labels={"component": component_name, "severity": severity.value},
            )

            # Trigger recovery if enabled
            if self.enable_auto_recovery:
                await self._trigger_recovery(component_name, metric.name, metric_status)

    async def _trigger_recovery(
        self, component_name: str, metric_name: str, status: HealthStatus
    ):
        """Trigger automatic recovery actions."""
        recovery_key = f"{component_name}_{metric_name}"

        # Check if we've exceeded max recovery attempts
        if self._recovery_attempts[recovery_key] >= self.max_recovery_attempts:
            logger.warning(f"Max recovery attempts reached for {recovery_key}")
            return

        # Determine recovery action
        recovery_action = None
        if component_name == "connection_pool":
            if metric_name in ["failed_connections", "unhealthy_connections"]:
                recovery_action = "cleanup_unhealthy_connections"
            elif metric_name == "success_rate":
                recovery_action = "restart_connection_pool"
        elif component_name == "pace_manager":
            recovery_action = "reset_pace_manager"

        if recovery_action and recovery_action in self._recovery_actions:
            logger.info(
                f"🔧 Triggering recovery action '{recovery_action}' for {recovery_key}"
            )

            try:
                success = await self._recovery_actions[recovery_action]()
                self._recovery_attempts[recovery_key] += 1

                if success:
                    logger.info(
                        f"✅ Recovery action '{recovery_action}' completed successfully"
                    )
                    record_counter(
                        "health_monitor",
                        "recovery_success",
                        labels={"component": component_name, "action": recovery_action},
                    )

                    # Record recovery action
                    if component_name in self._component_health:
                        self._component_health[
                            component_name
                        ].recovery_actions_taken.append(
                            f"{recovery_action}@{datetime.now().isoformat()}"
                        )
                else:
                    logger.error(f"❌ Recovery action '{recovery_action}' failed")
                    record_counter(
                        "health_monitor",
                        "recovery_failed",
                        labels={"component": component_name, "action": recovery_action},
                    )

            except Exception as e:
                logger.error(
                    f"Error executing recovery action '{recovery_action}': {e}"
                )
                record_counter(
                    "health_monitor",
                    "recovery_error",
                    labels={"component": component_name, "action": recovery_action},
                )

    def _set_component_status(self, component_name: str, status: HealthStatus):
        """Set status for a component."""
        if component_name not in self._component_health:
            self._component_health[component_name] = ComponentHealth(
                component_name=component_name, status=status
            )
        else:
            self._component_health[component_name].status = status
            self._component_health[component_name].last_check = time.time()

    def _update_overall_status(self):
        """Update overall system health status."""
        if not self._component_health:
            self._overall_status = HealthStatus.OFFLINE
            return

        statuses = [health.status for health in self._component_health.values()]

        if any(status == HealthStatus.CRITICAL for status in statuses):
            self._overall_status = HealthStatus.CRITICAL
        elif any(status == HealthStatus.DEGRADED for status in statuses):
            self._overall_status = HealthStatus.DEGRADED
        elif any(status == HealthStatus.WARNING for status in statuses):
            self._overall_status = HealthStatus.WARNING
        elif any(status == HealthStatus.OFFLINE for status in statuses):
            self._overall_status = HealthStatus.DEGRADED
        else:
            self._overall_status = HealthStatus.HEALTHY

    async def _process_alerts(self):
        """Process and manage alerts."""
        current_time = time.time()

        # Auto-resolve old alerts
        for alert in self._alerts[:]:
            if not alert.resolved and current_time - alert.timestamp > 3600:  # 1 hour
                alert.resolved = True
                alert.resolved_at = current_time
                logger.info(f"🔄 Auto-resolved old alert: {alert.message}")

        # Remove resolved alerts older than 24 hours
        self._alerts = [
            alert
            for alert in self._alerts
            if not alert.resolved or (current_time - alert.resolved_at < 86400)
        ]

    def _record_health_metrics(self):
        """Record health metrics to metrics collector."""
        # Record overall status
        status_values = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.WARNING: 1,
            HealthStatus.DEGRADED: 2,
            HealthStatus.CRITICAL: 3,
            HealthStatus.OFFLINE: 4,
        }

        record_gauge(
            "health_monitor", "overall_status", status_values[self._overall_status]
        )
        record_gauge(
            "health_monitor",
            "active_alerts",
            len([a for a in self._alerts if not a.resolved]),
        )
        record_gauge(
            "health_monitor", "components_monitored", len(self._component_health)
        )

        # Record component statuses
        for component_name, health in self._component_health.items():
            record_gauge(
                "health_monitor",
                "component_status",
                status_values[health.status],
                {"component": component_name},
            )

    # Public API methods

    def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        return {
            "status": self._overall_status.value,
            "components_total": len(self._component_health),
            "components_healthy": len(
                [
                    h
                    for h in self._component_health.values()
                    if h.status == HealthStatus.HEALTHY
                ]
            ),
            "components_warning": len(
                [
                    h
                    for h in self._component_health.values()
                    if h.status == HealthStatus.WARNING
                ]
            ),
            "components_critical": len(
                [
                    h
                    for h in self._component_health.values()
                    if h.status
                    in [
                        HealthStatus.CRITICAL,
                        HealthStatus.DEGRADED,
                        HealthStatus.OFFLINE,
                    ]
                ]
            ),
            "active_alerts": len([a for a in self._alerts if not a.resolved]),
            "monitoring_active": self._running,
            "last_check": (
                max([h.last_check for h in self._component_health.values()])
                if self._component_health
                else 0
            ),
        }

    def get_component_health(self, component_name: str) -> Optional[Dict[str, Any]]:
        """Get health status for a specific component."""
        health = self._component_health.get(component_name)
        if not health:
            return None

        return {
            "component_name": health.component_name,
            "status": health.status.value,
            "last_check": health.last_check,
            "consecutive_failures": health.consecutive_failures,
            "metrics": {
                name: {
                    "value": metric.value,
                    "status": metric.get_status().value,
                    "warning_threshold": metric.threshold_warning,
                    "critical_threshold": metric.threshold_critical,
                    "unit": metric.unit,
                }
                for name, metric in health.metrics.items()
            },
            "recovery_actions_taken": health.recovery_actions_taken[
                -5:
            ],  # Last 5 actions
            "active_alerts": [
                {
                    "id": alert.id,
                    "severity": alert.severity.value,
                    "message": alert.message,
                    "timestamp": alert.timestamp,
                }
                for alert in self._alerts
                if alert.component == component_name and not alert.resolved
            ],
        }

    def get_all_alerts(self, include_resolved: bool = False) -> List[Dict[str, Any]]:
        """Get all alerts."""
        alerts = (
            self._alerts
            if include_resolved
            else [a for a in self._alerts if not a.resolved]
        )

        return [
            {
                "id": alert.id,
                "component": alert.component,
                "metric_name": alert.metric_name,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "message": alert.message,
                "value": alert.value,
                "threshold": alert.threshold,
                "timestamp": alert.timestamp,
                "acknowledged": alert.acknowledged,
                "resolved": alert.resolved,
                "resolved_at": alert.resolved_at,
            }
            for alert in alerts
        ]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                logger.info(f"Alert {alert_id} acknowledged")
                record_counter("health_monitor", "alert_acknowledged")
                return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Manually resolve an alert."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.resolved = True
                alert.resolved_at = time.time()
                logger.info(f"Alert {alert_id} resolved")
                record_counter("health_monitor", "alert_resolved")
                return True
        return False


# Global instance
_health_monitor: Optional[IbHealthMonitor] = None


def get_health_monitor() -> IbHealthMonitor:
    """Get the global health monitor instance."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = IbHealthMonitor()
    return _health_monitor


async def start_health_monitoring() -> bool:
    """Start the global health monitoring."""
    return await get_health_monitor().start()


async def stop_health_monitoring():
    """Stop the global health monitoring."""
    await get_health_monitor().stop()
