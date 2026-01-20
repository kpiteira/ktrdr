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

    Slot 0 (local-prod) gets 8 worker ports for extra workers.
    Slots 1-10 (sandboxes) get 4 worker ports.
    """

    slot: int
    backend: int
    db: int
    grafana: int
    jaeger_ui: int
    jaeger_otlp_grpc: int
    jaeger_otlp_http: int
    prometheus: int
    worker_ports: list[int]  # 4 ports for sandboxes, 8 for local-prod (slot 0)

    def to_env_dict(self) -> dict[str, str]:
        """Convert to environment variable dict for .env.sandbox.

        Returns environment variables following the KTRDR_<SERVICE>_PORT
        naming convention established in M1.

        Slot 0 (local-prod) includes KTRDR_WORKER_PORT_5-8 for extra workers.
        """
        env = {
            "SLOT_NUMBER": str(self.slot),
            "KTRDR_API_PORT": str(self.backend),
            "KTRDR_DB_PORT": str(self.db),
            "KTRDR_GRAFANA_PORT": str(self.grafana),
            "KTRDR_JAEGER_UI_PORT": str(self.jaeger_ui),
            "KTRDR_JAEGER_OTLP_GRPC_PORT": str(self.jaeger_otlp_grpc),
            "KTRDR_JAEGER_OTLP_HTTP_PORT": str(self.jaeger_otlp_http),
            "KTRDR_PROMETHEUS_PORT": str(self.prometheus),
            "KTRDR_WORKER_PORT_1": str(self.worker_ports[0]),
            "KTRDR_WORKER_PORT_2": str(self.worker_ports[1]),
            "KTRDR_WORKER_PORT_3": str(self.worker_ports[2]),
            "KTRDR_WORKER_PORT_4": str(self.worker_ports[3]),
        }

        # Add extra worker ports for slot 0 (local-prod)
        if len(self.worker_ports) > 4:
            env["KTRDR_WORKER_PORT_5"] = str(self.worker_ports[4])
            env["KTRDR_WORKER_PORT_6"] = str(self.worker_ports[5])
            env["KTRDR_WORKER_PORT_7"] = str(self.worker_ports[6])
            env["KTRDR_WORKER_PORT_8"] = str(self.worker_ports[7])

        return env

    def all_ports(self) -> list[int]:
        """Return all ports for conflict checking.

        Returns a list of all ports (7 services + 4-8 workers).
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
        # Slot 0 (local-prod) gets 8 worker ports for --profile local-prod
        return PortAllocation(
            slot=0,
            backend=8000,
            db=5432,
            grafana=3000,
            jaeger_ui=16686,
            jaeger_otlp_grpc=4317,
            jaeger_otlp_http=4318,
            prometheus=9090,
            worker_ports=[5003, 5004, 5005, 5006, 5007, 5008, 5009, 5010],
        )

    # Slots 1-10 use offset worker ports starting at 5011 to avoid slot 0's 5003-5010
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
            5011 + (slot - 1) * 10,  # 5011, 5021, 5031, ... (shifted +1 to avoid 5010)
            5011 + (slot - 1) * 10 + 1,  # 5012, 5022, 5032, ...
            5011 + (slot - 1) * 10 + 2,  # 5013, 5023, 5033, ...
            5011 + (slot - 1) * 10 + 3,  # 5014, 5024, 5034, ...
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
