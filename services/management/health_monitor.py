#!/usr/bin/env python3
"""
Enhanced Health Monitor for KTRDR Host Services

Provides comprehensive health monitoring including:
- GPU-specific metrics and status
- Performance monitoring and baseline tracking
- Service health trends and anomaly detection
- Alerting and notification systems
"""

import os
import sys
import json
import time
import psutil
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any, cast
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class GPUMetrics:
    """GPU-specific metrics."""

    available: bool = False
    device_count: int = 0
    memory_total_mb: float = 0.0
    memory_allocated_mb: float = 0.0
    memory_utilization_percent: float = 0.0
    temperature_celsius: Optional[float] = None
    power_usage_watts: Optional[float] = None
    compute_utilization_percent: Optional[float] = None
    manager_status: str = "unknown"
    error: Optional[str] = None


@dataclass
class ServiceHealthMetrics:
    """Comprehensive service health metrics."""

    timestamp: datetime
    service_name: str
    status: str
    port: int
    response_time_ms: float
    cpu_usage_percent: float
    memory_usage_mb: float
    active_connections: int
    uptime_seconds: float
    gpu_metrics: Optional[GPUMetrics] = None
    custom_metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.custom_metrics is None:
            self.custom_metrics = {}


@dataclass
class PerformanceBaseline:
    """Performance baseline for comparison."""

    service_name: str
    avg_response_time_ms: float
    max_response_time_ms: float
    avg_cpu_usage_percent: float
    max_memory_usage_mb: float
    success_rate_percent: float
    measurement_period_hours: int
    last_updated: datetime


class HealthMonitor:
    """Enhanced health monitor for KTRDR host services."""

    def __init__(self, project_root: Optional[str] = None):
        """Initialize health monitor."""
        self.project_root = Path(project_root or self._find_project_root())
        self.metrics_dir = self.project_root / "services" / "management" / "metrics"
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

        # Service configurations
        self.services = {
            "ib-host": {
                "name": "IB Host Service",
                "port": 5001,
                "health_endpoint": "http://localhost:5001/health",
                "detailed_endpoint": "http://localhost:5001/health/detailed",
            },
            "training-host": {
                "name": "Training Host Service",
                "port": 5002,
                "health_endpoint": "http://localhost:5002/health",
                "detailed_endpoint": "http://localhost:5002/health/detailed",
            },
        }

        # Monitoring configuration
        self.baseline_file = self.metrics_dir / "performance_baselines.json"
        self.history_file = self.metrics_dir / "health_history.json"
        self.alerts_file = self.metrics_dir / "alerts_config.json"

        # Load existing baselines
        self.baselines = self._load_baselines()

        logger.info(f"HealthMonitor initialized for project: {self.project_root}")

    def _find_project_root(self) -> str:
        """Find the KTRDR project root directory."""
        current_dir = Path(__file__).parent
        while current_dir.parent != current_dir:
            if (current_dir / "pyproject.toml").exists():
                return str(current_dir)
            current_dir = current_dir.parent
        return str(Path.cwd())

    def _load_baselines(self) -> Dict[str, PerformanceBaseline]:
        """Load performance baselines from file."""
        if not self.baseline_file.exists():
            return {}

        try:
            with open(self.baseline_file, "r") as f:
                data = json.load(f)

            baselines = {}
            for service_name, baseline_data in data.items():
                baselines[service_name] = PerformanceBaseline(
                    service_name=baseline_data["service_name"],
                    avg_response_time_ms=baseline_data["avg_response_time_ms"],
                    max_response_time_ms=baseline_data["max_response_time_ms"],
                    avg_cpu_usage_percent=baseline_data["avg_cpu_usage_percent"],
                    max_memory_usage_mb=baseline_data["max_memory_usage_mb"],
                    success_rate_percent=baseline_data["success_rate_percent"],
                    measurement_period_hours=baseline_data["measurement_period_hours"],
                    last_updated=datetime.fromisoformat(baseline_data["last_updated"]),
                )

            return baselines

        except Exception as e:
            logger.error(f"Error loading baselines: {e}")
            return {}

    def _save_baselines(self) -> None:
        """Save performance baselines to file."""
        try:
            data = {}
            for service_name, baseline in self.baselines.items():
                data[service_name] = {
                    "service_name": baseline.service_name,
                    "avg_response_time_ms": baseline.avg_response_time_ms,
                    "max_response_time_ms": baseline.max_response_time_ms,
                    "avg_cpu_usage_percent": baseline.avg_cpu_usage_percent,
                    "max_memory_usage_mb": baseline.max_memory_usage_mb,
                    "success_rate_percent": baseline.success_rate_percent,
                    "measurement_period_hours": baseline.measurement_period_hours,
                    "last_updated": baseline.last_updated.isoformat(),
                }

            with open(self.baseline_file, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving baselines: {e}")

    def get_gpu_metrics(self, service_endpoint: str) -> GPUMetrics:
        """Get GPU metrics from a service endpoint."""
        try:
            response = requests.get(service_endpoint, timeout=5)
            if response.status_code == 200:
                data = response.json()

                # Extract GPU metrics from detailed health response
                return GPUMetrics(
                    available=data.get("gpu_available", False),
                    device_count=data.get("gpu_device_count", 0),
                    memory_total_mb=data.get("gpu_memory_total_mb", 0.0),
                    memory_allocated_mb=data.get("gpu_memory_allocated_mb", 0.0),
                    memory_utilization_percent=data.get(
                        "gpu_memory_utilization_percent", 0.0
                    ),
                    temperature_celsius=data.get("gpu_temperature_celsius"),
                    power_usage_watts=data.get("gpu_power_usage_watts"),
                    compute_utilization_percent=data.get(
                        "gpu_compute_utilization_percent"
                    ),
                    manager_status=data.get("gpu_manager_status", {}).get(
                        "reason", "unknown"
                    ),
                    error=data.get("error"),
                )
            else:
                return GPUMetrics(error=f"HTTP {response.status_code}")

        except Exception as e:
            return GPUMetrics(error=str(e))

    def get_service_health(self, service_name: str) -> ServiceHealthMetrics:
        """Get comprehensive health metrics for a service."""
        config = self.services.get(service_name)
        if not config:
            raise ValueError(f"Unknown service: {service_name}")

        start_time = time.time()

        try:
            # Basic health check
            health_endpoint = config.get("health_endpoint")
            if not isinstance(health_endpoint, str):
                raise ValueError(f"Invalid health endpoint for {service_name}")
            response = requests.get(health_endpoint, timeout=5)
            response_time_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                status = "running"
                error = None
            else:
                status = "failed"
                error = f"HTTP {response.status_code}"

        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            status = "failed"
            error = str(e)

        # Get system metrics for the service process
        cpu_usage = 0.0
        memory_usage = 0.0
        active_connections = 0
        uptime_seconds = 0.0

        try:
            # Find process using the port
            for conn in psutil.net_connections():
                if (
                    hasattr(conn, "laddr")
                    and conn.laddr
                    and conn.laddr.port == config["port"]
                ):
                    if conn.pid:
                        process = psutil.Process(conn.pid)
                        cpu_usage = process.cpu_percent()
                        memory_usage = process.memory_info().rss / 1024 / 1024  # MB
                        uptime_seconds = time.time() - process.create_time()
                        break

            # Count active connections to the port
            active_connections = sum(
                1
                for conn in psutil.net_connections()
                if hasattr(conn, "raddr")
                and conn.raddr
                and conn.raddr.port == config["port"]
            )

        except Exception as e:
            logger.debug(f"Error getting system metrics for {service_name}: {e}")

        # Get GPU metrics if available
        gpu_metrics = None
        if status == "running" and "detailed_endpoint" in config:
            detailed_endpoint = config["detailed_endpoint"]
            if isinstance(detailed_endpoint, str):
                gpu_metrics = self.get_gpu_metrics(detailed_endpoint)

        return ServiceHealthMetrics(
            timestamp=datetime.now(),
            service_name=service_name,
            status=status,
            port=cast(int, config.get("port", 0)),
            response_time_ms=response_time_ms,
            cpu_usage_percent=cpu_usage,
            memory_usage_mb=memory_usage,
            active_connections=active_connections,
            uptime_seconds=uptime_seconds,
            gpu_metrics=gpu_metrics,
            error=error,
        )

    def get_all_health_metrics(self) -> Dict[str, ServiceHealthMetrics]:
        """Get health metrics for all services."""
        metrics = {}
        for service_name in self.services:
            try:
                metrics[service_name] = self.get_service_health(service_name)
            except Exception as e:
                logger.error(f"Error getting health metrics for {service_name}: {e}")
                # Create error metric
                metrics[service_name] = ServiceHealthMetrics(
                    timestamp=datetime.now(),
                    service_name=service_name,
                    status="error",
                    port=cast(int, self.services[service_name].get("port", 0)),
                    response_time_ms=0.0,
                    cpu_usage_percent=0.0,
                    memory_usage_mb=0.0,
                    active_connections=0,
                    uptime_seconds=0.0,
                    error=str(e),
                )

        return metrics

    def save_health_history(self, metrics: Dict[str, ServiceHealthMetrics]) -> None:
        """Save health metrics to history file."""
        try:
            # Load existing history
            history = []
            if self.history_file.exists():
                with open(self.history_file, "r") as f:
                    history = json.load(f)

            # Add new metrics
            timestamp = datetime.now().isoformat()
            history_entry = {"timestamp": timestamp, "metrics": {}}

            metrics_dict = {}
            for service_name, metric in metrics.items():
                metric_dict = asdict(metric)
                # Convert datetime to string for JSON serialization
                metric_dict["timestamp"] = metric.timestamp.isoformat()
                metrics_dict[service_name] = metric_dict
            history_entry["metrics"] = metrics_dict

            history.append(history_entry)

            # Keep only last 1000 entries (roughly 8 hours at 30s intervals)
            if len(history) > 1000:
                history = history[-1000:]

            # Save history
            with open(self.history_file, "w") as f:
                json.dump(history, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving health history: {e}")

    def update_baseline(
        self, service_name: str, metrics_window_hours: int = 24
    ) -> None:
        """Update performance baseline for a service."""
        try:
            # Load recent history
            if not self.history_file.exists():
                logger.warning("No health history available for baseline calculation")
                return

            with open(self.history_file, "r") as f:
                history = json.load(f)

            # Filter to recent metrics
            cutoff_time = datetime.now() - timedelta(hours=metrics_window_hours)
            recent_metrics = []

            for entry in history:
                entry_time = datetime.fromisoformat(entry["timestamp"])
                if entry_time > cutoff_time and service_name in entry["metrics"]:
                    service_metrics = entry["metrics"][service_name]
                    if service_metrics["status"] == "running":
                        recent_metrics.append(service_metrics)

            if len(recent_metrics) < 10:
                logger.warning(
                    f"Insufficient data for baseline calculation: {len(recent_metrics)} samples"
                )
                return

            # Calculate baseline metrics
            response_times = [m["response_time_ms"] for m in recent_metrics]
            cpu_usages = [m["cpu_usage_percent"] for m in recent_metrics]
            memory_usages = [m["memory_usage_mb"] for m in recent_metrics]

            success_count = len(recent_metrics)
            total_count = len(
                [
                    entry["metrics"][service_name]
                    for entry in history
                    if datetime.fromisoformat(entry["timestamp"]) > cutoff_time
                    and service_name in entry["metrics"]
                ]
            )

            baseline = PerformanceBaseline(
                service_name=service_name,
                avg_response_time_ms=sum(response_times) / len(response_times),
                max_response_time_ms=max(response_times),
                avg_cpu_usage_percent=sum(cpu_usages) / len(cpu_usages),
                max_memory_usage_mb=max(memory_usages),
                success_rate_percent=(
                    (success_count / total_count) * 100 if total_count > 0 else 0
                ),
                measurement_period_hours=metrics_window_hours,
                last_updated=datetime.now(),
            )

            self.baselines[service_name] = baseline
            self._save_baselines()

            logger.info(
                f"Updated baseline for {service_name}: "
                f"avg_response={baseline.avg_response_time_ms:.1f}ms, "
                f"success_rate={baseline.success_rate_percent:.1f}%"
            )

        except Exception as e:
            logger.error(f"Error updating baseline for {service_name}: {e}")

    def check_anomalies(
        self, metrics: Dict[str, ServiceHealthMetrics]
    ) -> List[Dict[str, Any]]:
        """Check for performance anomalies against baselines."""
        anomalies = []

        for service_name, metric in metrics.items():
            if service_name not in self.baselines:
                continue

            baseline = self.baselines[service_name]

            # Check response time anomaly (> 2x average)
            if metric.response_time_ms > baseline.avg_response_time_ms * 2:
                anomalies.append(
                    {
                        "type": "high_response_time",
                        "service": service_name,
                        "current": metric.response_time_ms,
                        "baseline": baseline.avg_response_time_ms,
                        "severity": (
                            "warning"
                            if metric.response_time_ms < baseline.max_response_time_ms
                            else "critical"
                        ),
                    }
                )

            # Check CPU usage anomaly (> 1.5x average)
            if metric.cpu_usage_percent > baseline.avg_cpu_usage_percent * 1.5:
                anomalies.append(
                    {
                        "type": "high_cpu_usage",
                        "service": service_name,
                        "current": metric.cpu_usage_percent,
                        "baseline": baseline.avg_cpu_usage_percent,
                        "severity": "warning",
                    }
                )

            # Check memory usage anomaly (> baseline max)
            if metric.memory_usage_mb > baseline.max_memory_usage_mb * 1.2:
                anomalies.append(
                    {
                        "type": "high_memory_usage",
                        "service": service_name,
                        "current": metric.memory_usage_mb,
                        "baseline": baseline.max_memory_usage_mb,
                        "severity": "warning",
                    }
                )

            # Check GPU memory anomaly (if available)
            if metric.gpu_metrics and metric.gpu_metrics.available:
                if metric.gpu_metrics.memory_utilization_percent > 90:
                    anomalies.append(
                        {
                            "type": "high_gpu_memory",
                            "service": service_name,
                            "current": metric.gpu_metrics.memory_utilization_percent,
                            "severity": "critical",
                        }
                    )

        return anomalies

    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report."""
        metrics = self.get_all_health_metrics()
        anomalies = self.check_anomalies(metrics)

        # Save metrics to history
        self.save_health_history(metrics)

        # Overall system status
        all_healthy = all(m.status == "running" for m in metrics.values())
        any_critical = any(a["severity"] == "critical" for a in anomalies)

        if not all_healthy or any_critical:
            overall_status = "critical"
        elif anomalies:
            overall_status = "warning"
        else:
            overall_status = "healthy"

        return {
            "timestamp": datetime.now().isoformat(),
            "overall_status": overall_status,
            "services": {name: asdict(metric) for name, metric in metrics.items()},
            "anomalies": anomalies,
            "baselines": {
                name: asdict(baseline) for name, baseline in self.baselines.items()
            },
        }

    def print_health_dashboard(self) -> None:
        """Print a comprehensive health dashboard."""
        report = self.generate_health_report()

        print("\n" + "=" * 80)
        print("🔧 KTRDR Host Services Health Dashboard")
        print("=" * 80)

        # Overall status
        overall_status_emoji = {"healthy": "✅", "warning": "⚠️", "critical": "❌"}
        print(
            f"\n{overall_status_emoji.get(report['overall_status'], '❓')} Overall Status: {report['overall_status'].upper()}"
        )
        print(f"📅 Timestamp: {report['timestamp']}")

        # Service details
        print(f"\n📊 Service Details:")
        print("-" * 80)

        for service_name, metrics in report["services"].items():
            status = str(metrics["status"])
            response_time = metrics["response_time_ms"]

            status_emoji = "✅" if status == "running" else "❌"
            service_config = self.services.get(service_name, {})
            service_name_display = (
                service_config.get("name", service_name)
                if isinstance(service_config, dict)
                else service_name
            )
            print(f"{status_emoji} {service_name_display}")
            print(f"   Status: {status.upper()}")
            print(f"   Port: {metrics['port']}")
            print(f"   Response Time: {response_time:.1f}ms")
            print(f"   CPU Usage: {metrics['cpu_usage_percent']:.1f}%")
            print(f"   Memory Usage: {metrics['memory_usage_mb']:.1f}MB")
            print(f"   Uptime: {metrics['uptime_seconds']:.0f}s")

            # GPU metrics if available
            if metrics.get("gpu_metrics") and metrics["gpu_metrics"]["available"]:
                gpu = metrics["gpu_metrics"]
                print(f"   🎮 GPU: {gpu['device_count']} device(s)")
                print(
                    f"      Memory: {gpu['memory_allocated_mb']:.1f}/{gpu['memory_total_mb']:.1f}MB "
                    f"({gpu['memory_utilization_percent']:.1f}%)"
                )
                if gpu.get("temperature_celsius"):
                    print(f"      Temperature: {gpu['temperature_celsius']:.1f}°C")

            if metrics.get("error"):
                print(f"   ❌ Error: {metrics['error']}")

            print()

        # Anomalies
        if report["anomalies"]:
            print("⚠️  Performance Anomalies:")
            print("-" * 80)

            for anomaly in report["anomalies"]:
                severity_emoji = "❌" if anomaly["severity"] == "critical" else "⚠️"
                print(f"{severity_emoji} {anomaly['type']} in {anomaly['service']}")
                if "current" in anomaly and "baseline" in anomaly:
                    print(
                        f"   Current: {anomaly['current']:.1f}, Baseline: {anomaly['baseline']:.1f}"
                    )
                print()

        # Baselines
        if report["baselines"]:
            print("📈 Performance Baselines:")
            print("-" * 80)

            for service_name, baseline in report["baselines"].items():
                print(
                    f"📊 {self.services.get(service_name, {}).get('name', service_name)}"
                )
                print(f"   Avg Response: {baseline['avg_response_time_ms']:.1f}ms")
                print(f"   Success Rate: {baseline['success_rate_percent']:.1f}%")
                print(f"   Period: {baseline['measurement_period_hours']}h")
                print(f"   Updated: {baseline['last_updated']}")
                print()

        print("=" * 80)

    def continuous_monitoring(
        self, interval: int = 30, update_baseline_hours: int = 24
    ) -> None:
        """Run continuous health monitoring."""
        logger.info(f"Starting continuous health monitoring (interval: {interval}s)")

        last_baseline_update: Dict[str, datetime] = {}

        try:
            while True:
                # Generate and display health report
                report = self.generate_health_report()

                # Print dashboard every 10 cycles (5 minutes at 30s intervals)
                if time.time() % (interval * 10) < interval:
                    self.print_health_dashboard()

                # Update baselines periodically
                for service_name in self.services:
                    last_update = last_baseline_update.get(service_name, datetime.min)
                    if datetime.now() - last_update > timedelta(
                        hours=update_baseline_hours
                    ):
                        logger.info(f"Updating baseline for {service_name}")
                        self.update_baseline(service_name)
                        last_baseline_update[service_name] = datetime.now()

                # Log critical anomalies
                critical_anomalies = [
                    a for a in report["anomalies"] if a["severity"] == "critical"
                ]
                if critical_anomalies:
                    for anomaly in critical_anomalies:
                        logger.error(
                            f"CRITICAL ANOMALY: {anomaly['type']} in {anomaly['service']}"
                        )

                time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("Health monitoring stopped by user")
        except Exception as e:
            logger.error(f"Health monitoring error: {e}")


def main():
    """Main entry point for health monitor CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="KTRDR Host Services Health Monitor")
    parser.add_argument(
        "command",
        choices=["status", "dashboard", "monitor", "baseline", "report"],
        help="Command to execute",
    )
    parser.add_argument("--service", help="Specific service to monitor")
    parser.add_argument(
        "--interval", type=int, default=30, help="Monitoring interval in seconds"
    )
    parser.add_argument(
        "--hours", type=int, default=24, help="Hours for baseline calculation"
    )

    args = parser.parse_args()

    monitor = HealthMonitor()

    if args.command == "status":
        if args.service:
            metrics = monitor.get_service_health(args.service)
            print(json.dumps(asdict(metrics), indent=2, default=str))
        else:
            metrics = monitor.get_all_health_metrics()
            for name, metric in metrics.items():
                print(f"{name}: {metric.status} ({metric.response_time_ms:.1f}ms)")

    elif args.command == "dashboard":
        monitor.print_health_dashboard()

    elif args.command == "monitor":
        monitor.continuous_monitoring(interval=args.interval)

    elif args.command == "baseline":
        if args.service:
            monitor.update_baseline(args.service, args.hours)
        else:
            for service_name in monitor.services:
                monitor.update_baseline(service_name, args.hours)

    elif args.command == "report":
        report = monitor.generate_health_report()
        print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
