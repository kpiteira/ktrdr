"""Production-grade error handling and monitoring for KTRDR training systems."""

import json
import logging
import logging.handlers
import os
import smtplib
import socket
import sys
import threading
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import psutil

from ktrdr import get_logger
from ktrdr.training.error_handler import ErrorHandler

logger = get_logger(__name__)


class AlertLevel(Enum):
    """Alert severity levels for production monitoring."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class AlertConfig:
    """Configuration for production alerting."""

    email_enabled: bool = False
    email_smtp_server: str = ""
    email_smtp_port: int = 587
    email_username: str = ""
    email_password: str = ""
    email_recipients: list[str] = field(default_factory=list)

    webhook_enabled: bool = False
    webhook_url: str = ""
    webhook_timeout: int = 10

    console_alerts: bool = True
    file_alerts: bool = True
    alert_file_path: Optional[str] = None

    rate_limit_window_minutes: int = 15
    max_alerts_per_window: int = 10


@dataclass
class SystemHealth:
    """System health status for production monitoring."""

    timestamp: float
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    gpu_memory_percent: float
    network_connections: int
    process_count: int
    training_active: bool
    uptime_seconds: float
    error_rate_per_hour: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "disk_percent": self.disk_percent,
            "gpu_memory_percent": self.gpu_memory_percent,
            "network_connections": self.network_connections,
            "process_count": self.process_count,
            "training_active": self.training_active,
            "uptime_hours": self.uptime_seconds / 3600,
            "error_rate_per_hour": self.error_rate_per_hour,
        }


@dataclass
class ProductionAlert:
    """Production alert message."""

    timestamp: float
    level: AlertLevel
    component: str
    message: str
    details: dict[str, Any]
    system_health: Optional[SystemHealth]
    resolved: bool = False
    resolution_time: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "level": self.level.value,
            "component": self.component,
            "message": self.message,
            "details": self.details,
            "system_health": (
                self.system_health.to_dict() if self.system_health else None
            ),
            "resolved": self.resolved,
            "resolution_time": self.resolution_time,
            "resolution_datetime": (
                datetime.fromtimestamp(self.resolution_time).isoformat()
                if self.resolution_time
                else None
            ),
        }


class ProductionErrorHandler:
    """Production-grade error handling with monitoring and alerting."""

    def __init__(
        self,
        config: AlertConfig,
        log_dir: Path,
        base_error_handler: Optional[ErrorHandler] = None,
    ):
        """Initialize production error handler.

        Args:
            config: Alert configuration
            log_dir: Directory for log files
            base_error_handler: Base error handler for recovery
        """
        self.config = config
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.base_error_handler = base_error_handler or ErrorHandler()

        # Production monitoring state
        self.alerts: deque = deque(maxlen=1000)  # Keep last 1000 alerts
        self.system_health_history: deque = deque(
            maxlen=288
        )  # 24 hours at 5-min intervals
        self.error_count_history: deque = deque(maxlen=60)  # Last hour by minute

        # Rate limiting for alerts
        self.alert_timestamps: dict[str, deque] = {}

        # System monitoring
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.start_time = time.time()

        # Host information (must be set before logging setup)
        try:
            self.hostname = socket.gethostname()
        except Exception:
            self.hostname = "unknown"
        self.process_id = os.getpid()

        # Production logging setup
        self._setup_production_logging()

        logger.info(
            f"ProductionErrorHandler initialized on {self.hostname} (PID: {self.process_id})"
        )

    def _setup_production_logging(self):
        """Setup production-grade logging configuration."""
        # Create production logger
        self.prod_logger = logging.getLogger("ktrdr_production")
        self.prod_logger.setLevel(logging.DEBUG)

        # Remove existing handlers to avoid duplicates
        for handler in self.prod_logger.handlers[:]:
            self.prod_logger.removeHandler(handler)

        # File handler with rotation
        log_file = self.log_dir / "production.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=10,  # 10MB files, keep 10
        )
        file_handler.setLevel(logging.DEBUG)

        # Error file handler for errors and above
        error_log_file = self.log_dir / "production_errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        error_handler.setLevel(logging.ERROR)

        # JSON formatter for structured logging
        json_formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "component": "%(name)s", "message": "%(message)s", "hostname": "'
            + self.hostname
            + '", "pid": '
            + str(self.process_id)
            + "}"
        )

        file_handler.setFormatter(json_formatter)
        error_handler.setFormatter(json_formatter)

        self.prod_logger.addHandler(file_handler)
        self.prod_logger.addHandler(error_handler)

        # Don't propagate to root logger to avoid duplication
        self.prod_logger.propagate = False

    def start_monitoring(self):
        """Start production system monitoring."""
        if self.monitoring_active:
            logger.warning("Production monitoring already active")
            return

        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self.monitoring_thread.start()

        logger.info("Production monitoring started")
        self.prod_logger.info("Production monitoring started")

    def stop_monitoring(self):
        """Stop production system monitoring."""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5.0)
            self.monitoring_thread = None

        logger.info("Production monitoring stopped")
        self.prod_logger.info("Production monitoring stopped")

    def _monitoring_loop(self):
        """Background monitoring loop for production systems."""
        while self.monitoring_active:
            try:
                # Capture system health
                health = self._capture_system_health()
                self.system_health_history.append(health)

                # Check for system health alerts
                self._check_system_health_alerts(health)

                # Update error rate tracking
                self._update_error_rate()

                # Sleep for 5 minutes
                time.sleep(300)

            except Exception as e:
                logger.error(f"Production monitoring error: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

    def _capture_system_health(self) -> SystemHealth:
        """Capture current system health metrics."""
        # CPU and memory
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        # Disk usage
        disk_usage = psutil.disk_usage("/")
        disk_percent = (disk_usage.used / disk_usage.total) * 100

        # GPU memory (if available)
        gpu_memory_percent = 0.0
        try:
            import torch

            if torch.cuda.is_available():
                gpu_memory_used = torch.cuda.memory_allocated()
                gpu_memory_total = torch.cuda.get_device_properties(0).total_memory
                gpu_memory_percent = (gpu_memory_used / gpu_memory_total) * 100
        except ImportError:
            pass

        # Network connections (with error handling)
        try:
            connections = len(psutil.net_connections())
        except (psutil.AccessDenied, Exception):
            connections = 0

        # Process count (with error handling)
        try:
            process_count = len(psutil.pids())
        except (psutil.AccessDenied, Exception):
            process_count = 0

        # Check if training is active (simplified check)
        training_active = False
        try:
            for p in psutil.process_iter(["name", "cmdline"]):
                try:
                    if (
                        p.info["name"]
                        and "python" in p.info["name"].lower()
                        and p.info["cmdline"]
                        and "train" in " ".join(p.info["cmdline"]).lower()
                    ):
                        training_active = True
                        break
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    continue
        except Exception:
            pass  # Default to False if we can't check

        # Uptime
        uptime_seconds = time.time() - self.start_time

        # Error rate (errors in last hour)
        current_hour_errors = sum(self.error_count_history)
        error_rate_per_hour = current_hour_errors

        return SystemHealth(
            timestamp=time.time(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            disk_percent=disk_percent,
            gpu_memory_percent=gpu_memory_percent,
            network_connections=connections,
            process_count=process_count,
            training_active=training_active,
            uptime_seconds=uptime_seconds,
            error_rate_per_hour=error_rate_per_hour,
        )

    def _check_system_health_alerts(self, health: SystemHealth):
        """Check system health and generate alerts if needed."""
        # CPU alert
        if health.cpu_percent > 95:
            self.send_alert(
                AlertLevel.CRITICAL,
                "SystemHealth",
                f"Critical CPU usage: {health.cpu_percent:.1f}%",
                {"cpu_percent": health.cpu_percent, "threshold": 95},
                health,
            )
        elif health.cpu_percent > 85:
            self.send_alert(
                AlertLevel.WARNING,
                "SystemHealth",
                f"High CPU usage: {health.cpu_percent:.1f}%",
                {"cpu_percent": health.cpu_percent, "threshold": 85},
                health,
            )

        # Memory alert
        if health.memory_percent > 95:
            self.send_alert(
                AlertLevel.CRITICAL,
                "SystemHealth",
                f"Critical memory usage: {health.memory_percent:.1f}%",
                {"memory_percent": health.memory_percent, "threshold": 95},
                health,
            )
        elif health.memory_percent > 85:
            self.send_alert(
                AlertLevel.WARNING,
                "SystemHealth",
                f"High memory usage: {health.memory_percent:.1f}%",
                {"memory_percent": health.memory_percent, "threshold": 85},
                health,
            )

        # Disk alert
        if health.disk_percent > 95:
            self.send_alert(
                AlertLevel.CRITICAL,
                "SystemHealth",
                f"Critical disk usage: {health.disk_percent:.1f}%",
                {"disk_percent": health.disk_percent, "threshold": 95},
                health,
            )
        elif health.disk_percent > 90:
            self.send_alert(
                AlertLevel.WARNING,
                "SystemHealth",
                f"High disk usage: {health.disk_percent:.1f}%",
                {"disk_percent": health.disk_percent, "threshold": 90},
                health,
            )

        # GPU memory alert
        if health.gpu_memory_percent > 95:
            self.send_alert(
                AlertLevel.CRITICAL,
                "SystemHealth",
                f"Critical GPU memory usage: {health.gpu_memory_percent:.1f}%",
                {"gpu_memory_percent": health.gpu_memory_percent, "threshold": 95},
                health,
            )

        # Error rate alert
        if health.error_rate_per_hour > 100:
            self.send_alert(
                AlertLevel.ERROR,
                "ErrorRate",
                f"High error rate: {health.error_rate_per_hour} errors/hour",
                {"error_rate": health.error_rate_per_hour, "threshold": 100},
                health,
            )

        # Training status alert
        if (
            not health.training_active and health.uptime_seconds > 3600
        ):  # After 1 hour uptime
            self.send_alert(
                AlertLevel.WARNING,
                "TrainingStatus",
                "Training appears to be inactive",
                {
                    "training_active": False,
                    "uptime_hours": health.uptime_seconds / 3600,
                },
                health,
            )

    def _update_error_rate(self):
        """Update error rate tracking."""
        # Add current minute's error count
        current_minute = int(time.time() / 60)

        # Initialize if needed
        if not hasattr(self, "_last_minute"):
            self._last_minute = current_minute
            self._current_minute_errors = 0

        # If we've moved to a new minute, record the count
        if current_minute > self._last_minute:
            self.error_count_history.append(self._current_minute_errors)
            self._current_minute_errors = 0
            self._last_minute = current_minute

    def handle_production_error(
        self,
        error: Exception,
        component: str,
        operation: str,
        context: Optional[dict[str, Any]] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        """Handle production error with comprehensive logging and alerting.

        Args:
            error: Exception that occurred
            component: Component where error occurred
            operation: Operation that failed
            context: Additional context information
            user_id: User ID if applicable
            request_id: Request ID for tracing
        """
        timestamp = time.time()
        error_type = type(error).__name__
        error_message = str(error)
        traceback_str = traceback.format_exc()

        # Increment error count for rate tracking
        self._current_minute_errors = getattr(self, "_current_minute_errors", 0) + 1

        # Create enhanced context
        enhanced_context = {
            "component": component,
            "operation": operation,
            "error_type": error_type,
            "timestamp": timestamp,
            "hostname": self.hostname,
            "process_id": self.process_id,
            "user_id": user_id,
            "request_id": request_id,
            "python_version": sys.version,
            "traceback": traceback_str,
        }

        if context:
            enhanced_context.update(context)

        # Log to production logger
        self.prod_logger.error(
            f"Production {component}.{operation} failed: {error_message}",
            extra={"error_context": enhanced_context},
        )

        # Determine alert level based on error severity
        if isinstance(error, (SystemError, MemoryError, KeyboardInterrupt)):
            alert_level = AlertLevel.EMERGENCY
        elif isinstance(error, (RuntimeError, ImportError, ModuleNotFoundError)):
            alert_level = AlertLevel.CRITICAL
        elif isinstance(error, (ConnectionError, TimeoutError, IOError)):
            alert_level = AlertLevel.ERROR
        else:
            alert_level = AlertLevel.WARNING

        # Send production alert
        self.send_alert(
            alert_level,
            component,
            f"Production {operation} failed: {error_message}",
            enhanced_context,
            self._capture_system_health(),
        )

        # Use base error handler for recovery
        recovery_action = self.base_error_handler.handle_error(
            error, component, operation, enhanced_context
        )

        return recovery_action

    def send_alert(
        self,
        level: AlertLevel,
        component: str,
        message: str,
        details: dict[str, Any],
        system_health: Optional[SystemHealth] = None,
    ):
        """Send production alert through configured channels.

        Args:
            level: Alert severity level
            component: Component generating the alert
            message: Alert message
            details: Additional alert details
            system_health: Current system health snapshot
        """
        # Check rate limiting
        alert_key = f"{level.value}:{component}:{message}"
        if not self._should_send_alert(alert_key):
            return

        # Create alert
        alert = ProductionAlert(
            timestamp=time.time(),
            level=level,
            component=component,
            message=message,
            details=details,
            system_health=system_health,
        )

        self.alerts.append(alert)

        # Send through configured channels
        if self.config.console_alerts:
            self._send_console_alert(alert)

        if self.config.file_alerts:
            self._send_file_alert(alert)

        if self.config.email_enabled and level.value in ["critical", "emergency"]:
            self._send_email_alert(alert)

        if self.config.webhook_enabled:
            self._send_webhook_alert(alert)

    def _should_send_alert(self, alert_key: str) -> bool:
        """Check if alert should be sent based on rate limiting."""
        current_time = time.time()
        window_start = current_time - (self.config.rate_limit_window_minutes * 60)

        # Initialize if needed
        if alert_key not in self.alert_timestamps:
            self.alert_timestamps[alert_key] = deque()

        # Remove old timestamps
        alert_queue = self.alert_timestamps[alert_key]
        while alert_queue and alert_queue[0] < window_start:
            alert_queue.popleft()

        # Check if under rate limit
        if len(alert_queue) >= self.config.max_alerts_per_window:
            return False

        # Add current timestamp
        alert_queue.append(current_time)
        return True

    def _send_console_alert(self, alert: ProductionAlert):
        """Send alert to console."""
        level_colors = {
            AlertLevel.DEBUG: "\033[36m",  # Cyan
            AlertLevel.INFO: "\033[32m",  # Green
            AlertLevel.WARNING: "\033[33m",  # Yellow
            AlertLevel.ERROR: "\033[31m",  # Red
            AlertLevel.CRITICAL: "\033[35m",  # Magenta
            AlertLevel.EMERGENCY: "\033[1;31m",  # Bold Red
        }

        reset_color = "\033[0m"
        color = level_colors.get(alert.level, "")

        print(
            f"{color}[{alert.level.value.upper()}] {datetime.fromtimestamp(alert.timestamp).isoformat()} "
            f"{alert.component}: {alert.message}{reset_color}"
        )

    def _send_file_alert(self, alert: ProductionAlert):
        """Send alert to file."""
        alert_file = (
            Path(self.config.alert_file_path)
            if self.config.alert_file_path
            else self.log_dir / "alerts.log"
        )

        alert_data = {
            "timestamp": alert.timestamp,
            "datetime": datetime.fromtimestamp(alert.timestamp).isoformat(),
            "level": alert.level.value,
            "component": alert.component,
            "message": alert.message,
            "details": alert.details,
            "hostname": self.hostname,
            "process_id": self.process_id,
        }

        try:
            with open(alert_file, "a") as f:
                f.write(json.dumps(alert_data) + "\n")
        except Exception as e:
            logger.error(f"Failed to write alert to file: {e}")

    def _send_email_alert(self, alert: ProductionAlert):
        """Send alert via email."""
        if not self.config.email_recipients:
            return

        try:
            msg = MIMEMultipart()
            msg["From"] = self.config.email_username
            msg["To"] = ", ".join(self.config.email_recipients)
            msg["Subject"] = (
                f"[{alert.level.value.upper()}] KTRDR Production Alert - {alert.component}"
            )

            body = f"""
Production Alert Details:

Time: {datetime.fromtimestamp(alert.timestamp).isoformat()}
Level: {alert.level.value.upper()}
Component: {alert.component}
Message: {alert.message}

System Information:
- Hostname: {self.hostname}
- Process ID: {self.process_id}

Alert Details:
{json.dumps(alert.details, indent=2)}
"""

            if alert.system_health:
                body += f"""
System Health:
- CPU: {alert.system_health.cpu_percent:.1f}%
- Memory: {alert.system_health.memory_percent:.1f}%
- Disk: {alert.system_health.disk_percent:.1f}%
- GPU Memory: {alert.system_health.gpu_memory_percent:.1f}%
- Error Rate: {alert.system_health.error_rate_per_hour} errors/hour
"""

            msg.attach(MIMEText(body, "plain"))

            # Send email
            server = smtplib.SMTP(
                self.config.email_smtp_server, self.config.email_smtp_port
            )
            server.starttls()
            server.login(self.config.email_username, self.config.email_password)
            server.send_message(msg)
            server.quit()

            logger.debug(f"Email alert sent for {alert.level.value} level alert")

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")

    def _send_webhook_alert(self, alert: ProductionAlert):
        """Send alert via webhook."""
        try:
            import requests

            payload = alert.to_dict()
            payload["hostname"] = self.hostname
            payload["process_id"] = self.process_id

            response = requests.post(
                self.config.webhook_url,
                json=payload,
                timeout=self.config.webhook_timeout,
            )

            if response.status_code == 200:
                logger.debug(f"Webhook alert sent for {alert.level.value} level alert")
            else:
                logger.warning(f"Webhook returned status {response.status_code}")

        except ImportError:
            logger.warning("requests library not available for webhook alerts")
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")

    def get_production_status(self) -> dict[str, Any]:
        """Get comprehensive production system status."""
        current_health = self._capture_system_health()

        # Calculate alert statistics
        alert_stats = {level.value: 0 for level in AlertLevel}
        recent_alerts = [
            a for a in self.alerts if time.time() - a.timestamp < 3600
        ]  # Last hour

        for alert in recent_alerts:
            alert_stats[alert.level.value] += 1

        # Calculate uptime
        uptime_seconds = time.time() - self.start_time
        uptime_days = uptime_seconds / 86400

        return {
            "system_info": {
                "hostname": self.hostname,
                "process_id": self.process_id,
                "uptime_days": uptime_days,
                "monitoring_active": self.monitoring_active,
            },
            "current_health": current_health.to_dict(),
            "alert_statistics": {
                "total_alerts": len(self.alerts),
                "recent_alerts_1h": len(recent_alerts),
                "alerts_by_level": alert_stats,
            },
            "error_rate": {
                "current_hour": sum(self.error_count_history),
                "average_per_minute": sum(self.error_count_history)
                / max(len(self.error_count_history), 1),
            },
            "configuration": {
                "email_enabled": self.config.email_enabled,
                "webhook_enabled": self.config.webhook_enabled,
                "rate_limit_window_minutes": self.config.rate_limit_window_minutes,
                "max_alerts_per_window": self.config.max_alerts_per_window,
            },
        }

    def export_production_report(self, file_path: Optional[Path] = None) -> Path:
        """Export comprehensive production report.

        Args:
            file_path: Output file path (auto-generated if None)

        Returns:
            Path to exported report
        """
        if file_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = self.log_dir / f"production_report_{timestamp}.json"

        report_data = {
            "metadata": {
                "export_timestamp": time.time(),
                "export_datetime": datetime.now().isoformat(),
                "report_period_hours": 24,
                "hostname": self.hostname,
                "process_id": self.process_id,
            },
            "production_status": self.get_production_status(),
            "recent_alerts": [
                alert.to_dict() for alert in list(self.alerts)[-100:]
            ],  # Last 100 alerts
            "system_health_history": [
                health.to_dict() for health in list(self.system_health_history)
            ],
            "error_rate_history": list(self.error_count_history),
        }

        with open(file_path, "w") as f:
            json.dump(report_data, f, indent=2, default=str)

        logger.info(f"Production report exported to: {file_path}")
        return file_path

    def __enter__(self):
        """Context manager entry."""
        self.start_monitoring()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_monitoring()

        # Export final report
        try:
            self.export_production_report()
        except Exception as e:
            logger.error(f"Failed to export final production report: {e}")
