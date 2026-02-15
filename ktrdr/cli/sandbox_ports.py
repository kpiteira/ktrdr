"""Port allocation for sandbox instances.

This module provides deterministic port mapping for sandbox slots (0-10).
Each slot gets a unique set of ports to enable parallel sandbox instances
without port conflicts.

Slot 0 uses standard development ports (8000, 5432, etc.).
Slots 1-10 use offset ports for sandbox instances.
"""

import socket
from dataclasses import dataclass


@dataclass
class PortAllocation:
    """Port assignments for a sandbox slot.

    Each sandbox instance is assigned a slot (0-10) with deterministic
    port mappings. This enables multiple parallel instances without conflicts.

    All slots get 4 worker ports matching the 4 workers defined in compose.
    """

    slot: int
    backend: int
    db: int
    grafana: int
    jaeger_ui: int
    jaeger_otlp_grpc: int
    jaeger_otlp_http: int
    prometheus: int
    worker_ports: list[int]  # 4 worker ports

    def to_env_dict(self) -> dict[str, str]:
        """Convert to environment variable dict for .env.sandbox.

        Returns environment variables following the KTRDR_<SERVICE>_PORT
        naming convention established in M1.

        """
        return {
            "SLOT_NUMBER": str(self.slot),
            "KTRDR_API_PORT": str(self.backend),
            "KTRDR_DB_PORT": str(self.db),
            "KTRDR_GRAFANA_PORT": str(self.grafana),
            "KTRDR_JAEGER_UI_PORT": str(self.jaeger_ui),
            "KTRDR_OTLP_GRPC_PORT": str(self.jaeger_otlp_grpc),
            "KTRDR_OTLP_HTTP_PORT": str(self.jaeger_otlp_http),
            "KTRDR_PROMETHEUS_PORT": str(self.prometheus),
            "KTRDR_WORKER_PORT_1": str(self.worker_ports[0]),
            "KTRDR_WORKER_PORT_2": str(self.worker_ports[1]),
            "KTRDR_WORKER_PORT_3": str(self.worker_ports[2]),
            "KTRDR_WORKER_PORT_4": str(self.worker_ports[3]),
        }

    def all_ports(self) -> list[int]:
        """Return all ports for conflict checking.

        Returns a list of all ports (7 services + 4 workers).
        """
        return [
            self.backend,
            self.db,
            self.grafana,
            self.jaeger_ui,
            self.jaeger_otlp_grpc,
            self.jaeger_otlp_http,
            self.prometheus,
            *self.worker_ports,
        ]


def get_ports(slot: int) -> PortAllocation:
    """Get port allocation for a slot.

    Args:
        slot: Slot number (0-10)
            - Slot 0: Standard ports (main dev environment)
            - Slot 1-10: Offset ports for sandbox instances

    Returns:
        PortAllocation with all port assignments for the slot.

    Raises:
        ValueError: If slot is not in range 0-10.
    """
    if slot < 0 or slot > 10:
        raise ValueError(f"Slot must be 0-10, got {slot}")

    if slot == 0:
        # Slot 0 (local-prod) uses standard ports matching docker-compose defaults
        return PortAllocation(
            slot=0,
            backend=8000,
            db=5432,
            grafana=3000,
            jaeger_ui=16686,
            jaeger_otlp_grpc=4317,
            jaeger_otlp_http=4318,
            prometheus=9090,
            worker_ports=[5003, 5004, 5005, 5006],
        )

    # Slots 1-10 use offset worker ports starting at 5007 to avoid slot 0's 5003-5006
    return PortAllocation(
        slot=slot,
        backend=8000 + slot,
        db=5432 + slot,
        grafana=3000 + slot,
        jaeger_ui=16686 + slot,
        jaeger_otlp_grpc=4317 + slot * 10,  # 4327, 4337, ... (10-slot offset)
        jaeger_otlp_http=4318 + slot * 10,  # 4328, 4338, ...
        prometheus=9090 + slot,
        worker_ports=[
            5007 + (slot - 1) * 10,  # 5007, 5017, 5027, ...
            5007 + (slot - 1) * 10 + 1,  # 5008, 5018, 5028, ...
            5007 + (slot - 1) * 10 + 2,  # 5009, 5019, 5029, ...
            5007 + (slot - 1) * 10 + 3,  # 5010, 5020, 5030, ...
        ],
    )


def is_port_free(port: int) -> bool:
    """Check if a port is available for binding.

    Args:
        port: Port number to check.

    Returns:
        True if the port is available, False if in use.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def check_ports_available(slot: int) -> list[int]:
    """Check which ports in a slot are in use.

    Args:
        slot: Slot number (0-10) to check.

    Returns:
        List of ports that are already in use (empty if all available).
    """
    allocation = get_ports(slot)
    return [p for p in allocation.all_ports() if not is_port_free(p)]
