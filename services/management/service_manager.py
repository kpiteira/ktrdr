#!/usr/bin/env python3
"""
Unified Service Manager for KTRDR Host Services

Manages both IB Host Service and Training Host Service with:
- Unified startup/shutdown coordination
- Health monitoring and dependency validation
- Auto-restart capabilities
- Cross-platform service registration
"""

import os
import sys
import time
import json
import signal
import asyncio
import subprocess
import psutil
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service status enumeration."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class ServiceConfig:
    """Configuration for a host service."""

    name: str
    display_name: str
    port: int
    directory: str
    start_script: str
    stop_script: str
    health_endpoint: str
    dependencies: Optional[List[str]] = None
    startup_delay: int = 5
    health_timeout: int = 10
    max_restart_attempts: int = 3
    restart_delay: int = 30

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class ServiceManager:
    """Unified service manager for KTRDR host services."""

    def __init__(self, project_root: Optional[str] = None):
        """Initialize service manager."""
        self.project_root = Path(project_root or self._find_project_root())
        self.services = self._load_service_configs()
        self.status_file = (
            self.project_root / "services" / "management" / "service_status.json"
        )
        self.pid_file = (
            self.project_root / "services" / "management" / "service_manager.pid"
        )

        # Ensure directories exist
        self.status_file.parent.mkdir(parents=True, exist_ok=True)

        # Track restart attempts
        self.restart_attempts: Dict[str, int] = {}

        logger.info(f"ServiceManager initialized for project: {self.project_root}")

    def _find_project_root(self) -> str:
        """Find the KTRDR project root directory."""
        current_dir = Path(__file__).parent
        while current_dir.parent != current_dir:
            if (current_dir / "pyproject.toml").exists():
                return str(current_dir)
            current_dir = current_dir.parent

        # Fallback to current directory
        return str(Path.cwd())

    def _load_service_configs(self) -> Dict[str, ServiceConfig]:
        """Load service configurations."""
        return {
            "ib-host": ServiceConfig(
                name="ib-host",
                display_name="IB Host Service",
                port=5001,
                directory=str(self.project_root / "ib-host-service"),
                start_script="start.sh",
                stop_script="stop.sh",
                health_endpoint="http://localhost:5001/health",
                dependencies=[],  # IB Host has no dependencies (expects IB Gateway externally)
                startup_delay=10,  # Longer delay for IB connection setup
            ),
            "training-host": ServiceConfig(
                name="training-host",
                display_name="Training Host Service",
                port=5002,
                directory=str(self.project_root / "training-host-service"),
                start_script="start.sh",
                stop_script="stop.sh",
                health_endpoint="http://localhost:5002/health",
                dependencies=["ib-host"],  # Training may depend on IB data
                startup_delay=5,
            ),
        }

    def get_service_status(self, service_name: str) -> ServiceStatus:
        """Get current status of a service."""
        try:
            config = self.services[service_name]

            # Check if process is running on the port
            if self._is_port_in_use(config.port):
                # Verify health endpoint if available
                if self._check_health(config):
                    return ServiceStatus.RUNNING
                else:
                    return ServiceStatus.FAILED
            else:
                return ServiceStatus.STOPPED

        except Exception as e:
            logger.error(f"Error checking status for {service_name}: {e}")
            return ServiceStatus.UNKNOWN

    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is in use."""
        try:
            # Check using psutil
            for conn in psutil.net_connections():
                if hasattr(conn, "laddr") and conn.laddr and conn.laddr.port == port:
                    if conn.status == psutil.CONN_LISTEN:
                        return True
        except Exception as e:
            logger.debug(f"psutil port check failed: {e}")

        # Fallback: try to connect to the port
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.debug(f"socket port check failed: {e}")

        return False

    def _check_health(self, config: ServiceConfig) -> bool:
        """Check service health via HTTP endpoint."""
        try:
            response = requests.get(
                config.health_endpoint, timeout=config.health_timeout
            )
            return response.status_code == 200
        except Exception:
            return False

    def start_service(self, service_name: str, wait: bool = True) -> bool:
        """Start a specific service."""
        if service_name not in self.services:
            logger.error(f"Unknown service: {service_name}")
            return False

        config = self.services[service_name]

        # Check if already running
        if self.get_service_status(service_name) == ServiceStatus.RUNNING:
            logger.info(f"{config.display_name} is already running")
            return True

        # Check dependencies
        dependencies = config.dependencies or []
        for dep in dependencies:
            if self.get_service_status(dep) != ServiceStatus.RUNNING:
                logger.info(f"Starting dependency {dep} for {service_name}")
                if not self.start_service(dep, wait=True):
                    logger.error(f"Failed to start dependency {dep}")
                    return False

        logger.info(f"Starting {config.display_name}...")

        try:
            # Change to service directory
            service_dir = Path(config.directory)
            if not service_dir.exists():
                logger.error(f"Service directory not found: {service_dir}")
                return False

            # Execute start script
            start_script_path = service_dir / config.start_script
            if not start_script_path.exists():
                logger.error(f"Start script not found: {start_script_path}")
                return False

            # Make script executable
            os.chmod(start_script_path, 0o755)

            # Start the service in background
            process = subprocess.Popen(
                [str(start_script_path)],
                cwd=str(service_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if wait:
                # Wait for startup
                logger.info(
                    f"Waiting {config.startup_delay}s for {config.display_name} to start..."
                )
                time.sleep(config.startup_delay)

                # Verify it's running
                status = self.get_service_status(service_name)
                if status == ServiceStatus.RUNNING:
                    logger.info(f"✅ {config.display_name} started successfully")
                    self.restart_attempts[service_name] = 0  # Reset restart counter
                    return True
                else:
                    logger.error(
                        f"❌ {config.display_name} failed to start (status: {status.value})"
                    )
                    return False
            else:
                logger.info(f"Started {config.display_name} in background")
                return True

        except Exception as e:
            logger.error(f"Error starting {config.display_name}: {e}")
            return False

    def stop_service(self, service_name: str, wait: bool = True) -> bool:
        """Stop a specific service."""
        if service_name not in self.services:
            logger.error(f"Unknown service: {service_name}")
            return False

        config = self.services[service_name]

        # Check if already stopped
        if self.get_service_status(service_name) == ServiceStatus.STOPPED:
            logger.info(f"{config.display_name} is already stopped")
            return True

        logger.info(f"Stopping {config.display_name}...")

        try:
            # Change to service directory
            service_dir = Path(config.directory)
            if not service_dir.exists():
                logger.error(f"Service directory not found: {service_dir}")
                return False

            # Execute stop script
            stop_script_path = service_dir / config.stop_script
            if not stop_script_path.exists():
                logger.error(f"Stop script not found: {stop_script_path}")
                return False

            # Make script executable
            os.chmod(stop_script_path, 0o755)

            # Stop the service
            result = subprocess.run(
                [str(stop_script_path)],
                cwd=str(service_dir),
                capture_output=True,
                text=True,
            )

            if wait:
                # Wait a moment for shutdown
                time.sleep(2)

                # Verify it's stopped
                status = self.get_service_status(service_name)
                if status == ServiceStatus.STOPPED:
                    logger.info(f"✅ {config.display_name} stopped successfully")
                    return True
                else:
                    logger.warning(
                        f"⚠️  {config.display_name} may not have stopped cleanly (status: {status.value})"
                    )
                    return False
            else:
                logger.info(f"Sent stop signal to {config.display_name}")
                return True

        except Exception as e:
            logger.error(f"Error stopping {config.display_name}: {e}")
            return False

    def restart_service(self, service_name: str) -> bool:
        """Restart a specific service."""
        logger.info(f"Restarting {service_name}...")

        # Stop first
        if not self.stop_service(service_name, wait=True):
            logger.error(f"Failed to stop {service_name}")
            return False

        # Wait a moment
        time.sleep(2)

        # Start again
        return self.start_service(service_name, wait=True)

    def start_all_services(self) -> bool:
        """Start all services in dependency order."""
        logger.info("Starting all KTRDR host services...")

        # Start in dependency order
        service_order = ["ib-host", "training-host"]

        for service_name in service_order:
            if not self.start_service(service_name, wait=True):
                logger.error(f"Failed to start {service_name}, aborting startup")
                return False

        logger.info("✅ All KTRDR host services started successfully")
        return True

    def stop_all_services(self) -> bool:
        """Stop all services in reverse dependency order."""
        logger.info("Stopping all KTRDR host services...")

        # Stop in reverse dependency order
        service_order = ["training-host", "ib-host"]

        success = True
        for service_name in service_order:
            if not self.stop_service(service_name, wait=True):
                logger.error(f"Failed to stop {service_name}")
                success = False

        if success:
            logger.info("✅ All KTRDR host services stopped successfully")
        else:
            logger.warning("⚠️  Some services may not have stopped cleanly")

        return success

    def get_all_status(self) -> Dict[str, Dict]:
        """Get status of all services."""
        status_info = {}

        for service_name, config in self.services.items():
            status = self.get_service_status(service_name)
            health_ok = False

            if status == ServiceStatus.RUNNING:
                health_ok = self._check_health(config)

            status_info[service_name] = {
                "name": service_name,
                "display_name": config.display_name,
                "status": status.value,
                "port": config.port,
                "health_ok": health_ok,
                "restart_attempts": self.restart_attempts.get(service_name, 0),
            }

        return status_info

    def monitor_services(self, interval: int = 30, max_failures: int = 3) -> None:
        """Monitor services and restart if needed."""
        logger.info(f"Starting service monitoring (interval: {interval}s)")

        failure_counts: Dict[str, int] = {}

        try:
            while True:
                for service_name, config in self.services.items():
                    try:
                        status = self.get_service_status(service_name)

                        if status != ServiceStatus.RUNNING:
                            failure_counts[service_name] = (
                                failure_counts.get(service_name, 0) + 1
                            )

                            if failure_counts[service_name] <= max_failures:
                                logger.warning(
                                    f"Service {service_name} is {status.value}, attempting restart ({failure_counts[service_name]}/{max_failures})"
                                )

                                if self.restart_service(service_name):
                                    failure_counts[service_name] = 0
                                    logger.info(
                                        f"Successfully restarted {service_name}"
                                    )
                                else:
                                    logger.error(f"Failed to restart {service_name}")
                            else:
                                logger.error(
                                    f"Service {service_name} has failed {max_failures} times, giving up"
                                )
                        else:
                            # Reset failure count on successful status
                            failure_counts[service_name] = 0

                    except Exception as e:
                        logger.error(f"Error monitoring {service_name}: {e}")

                time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("Service monitoring stopped by user")
        except Exception as e:
            logger.error(f"Service monitoring error: {e}")

    def create_daemon_mode(self) -> None:
        """Run service manager in daemon mode."""
        # Write PID file
        try:
            with open(self.pid_file, "w") as f:
                f.write(str(os.getpid()))

            # Setup signal handlers
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)

            logger.info("Service manager running in daemon mode")

            # Start monitoring
            self.monitor_services()

        finally:
            # Cleanup PID file
            if self.pid_file.exists():
                self.pid_file.unlink()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down services...")
        self.stop_all_services()
        sys.exit(0)


def main():
    """Main entry point for service manager CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="KTRDR Host Services Manager")
    parser.add_argument(
        "command",
        choices=["start", "stop", "restart", "status", "monitor", "daemon"],
        help="Command to execute",
    )
    parser.add_argument("--service", help="Specific service to manage (optional)")
    parser.add_argument("--all", action="store_true", help="Apply to all services")
    parser.add_argument(
        "--interval", type=int, default=30, help="Monitoring interval in seconds"
    )

    args = parser.parse_args()

    manager = ServiceManager()

    if args.command == "start":
        if args.service:
            success = manager.start_service(args.service)
        else:
            success = manager.start_all_services()
        sys.exit(0 if success else 1)

    elif args.command == "stop":
        if args.service:
            success = manager.stop_service(args.service)
        else:
            success = manager.stop_all_services()
        sys.exit(0 if success else 1)

    elif args.command == "restart":
        if args.service:
            success = manager.restart_service(args.service)
        else:
            success = manager.stop_all_services() and manager.start_all_services()
        sys.exit(0 if success else 1)

    elif args.command == "status":
        status_info = manager.get_all_status()

        print("\n🔧 KTRDR Host Services Status")
        print("=" * 50)

        for service_name, info in status_info.items():
            status_emoji = "✅" if info["status"] == "running" else "❌"
            health_emoji = "💚" if info["health_ok"] else "💔"

            print(f"{status_emoji} {info['display_name']}")
            print(f"   Status: {info['status'].upper()}")
            print(f"   Port: {info['port']}")
            print(
                f"   Health: {health_emoji} {'OK' if info['health_ok'] else 'FAILED'}"
            )
            if info["restart_attempts"] > 0:
                print(f"   Restart Attempts: {info['restart_attempts']}")
            print()

    elif args.command == "monitor":
        manager.monitor_services(interval=args.interval)

    elif args.command == "daemon":
        manager.create_daemon_mode()


if __name__ == "__main__":
    main()
