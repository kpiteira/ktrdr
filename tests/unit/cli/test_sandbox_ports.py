"""
Tests for the sandbox port allocation module.

This module tests port slot allocation for sandbox instances,
ensuring deterministic port mapping and conflict detection.
"""

import socket
from unittest.mock import patch

import pytest


class TestPortAllocation:
    """Tests for PortAllocation dataclass."""

    def test_slot_0_returns_standard_ports(self):
        """Verify slot 0 matches current docker-compose defaults."""
        from ktrdr.cli.sandbox_ports import get_ports

        ports = get_ports(0)

        # Standard ports from current docker-compose.yml
        # Slot 0 (local-prod) gets 8 worker ports for extra workers
        assert ports.slot == 0
        assert ports.backend == 8000
        assert ports.db == 5432
        assert ports.grafana == 3000
        assert ports.jaeger_ui == 16686
        assert ports.jaeger_otlp_grpc == 4317
        assert ports.jaeger_otlp_http == 4318
        assert ports.prometheus == 9090
        assert ports.worker_ports == [5003, 5004, 5005, 5006, 5007, 5008, 5009, 5010]

    def test_slot_1_returns_offset_ports(self):
        """Verify slot 1 has correct +1 offsets."""
        from ktrdr.cli.sandbox_ports import get_ports

        ports = get_ports(1)

        assert ports.slot == 1
        assert ports.backend == 8001
        assert ports.db == 5433
        assert ports.grafana == 3001
        assert ports.jaeger_ui == 16687
        # Jaeger OTLP uses 10-slot offset to avoid overlap
        assert ports.jaeger_otlp_grpc == 4327
        assert ports.jaeger_otlp_http == 4328
        assert ports.prometheus == 9091
        # Worker ports for slot 1: 5011-5014 (shifted to avoid slot 0's 5003-5010)
        assert ports.worker_ports == [5011, 5012, 5013, 5014]

    def test_slot_2_worker_ports(self):
        """Verify worker port ranges for slot 2 (5021-5024)."""
        from ktrdr.cli.sandbox_ports import get_ports

        ports = get_ports(2)

        assert ports.slot == 2
        assert ports.backend == 8002
        # Slot 2: 5011 + (2-1)*10 = 5021
        assert ports.worker_ports == [5021, 5022, 5023, 5024]

    def test_slot_10_returns_max_offset_ports(self):
        """Verify slot 10 (maximum) has correct offsets."""
        from ktrdr.cli.sandbox_ports import get_ports

        ports = get_ports(10)

        assert ports.slot == 10
        assert ports.backend == 8010
        assert ports.db == 5442
        assert ports.grafana == 3010
        assert ports.jaeger_ui == 16696
        # Slot 10: 4317 + 10*10 = 4417
        assert ports.jaeger_otlp_grpc == 4417
        assert ports.jaeger_otlp_http == 4418
        assert ports.prometheus == 9100
        # Worker ports for slot 10: 5011 + (10-1)*10 = 5101
        assert ports.worker_ports == [5101, 5102, 5103, 5104]

    def test_invalid_slot_negative_raises(self):
        """Slot -1 should raise ValueError."""
        from ktrdr.cli.sandbox_ports import get_ports

        with pytest.raises(ValueError, match="Slot must be 0-10"):
            get_ports(-1)

    def test_invalid_slot_above_10_raises(self):
        """Slot 11 should raise ValueError."""
        from ktrdr.cli.sandbox_ports import get_ports

        with pytest.raises(ValueError, match="Slot must be 0-10"):
            get_ports(11)


class TestToEnvDict:
    """Tests for PortAllocation.to_env_dict() method."""

    def test_to_env_dict_format(self):
        """Verify env var names and values match expected format."""
        from ktrdr.cli.sandbox_ports import get_ports

        ports = get_ports(1)
        env = ports.to_env_dict()

        # Check all required keys are present
        assert env["SLOT_NUMBER"] == "1"
        assert env["KTRDR_API_PORT"] == "8001"
        assert env["KTRDR_DB_PORT"] == "5433"
        assert env["KTRDR_GRAFANA_PORT"] == "3001"
        assert env["KTRDR_JAEGER_UI_PORT"] == "16687"
        assert env["KTRDR_JAEGER_OTLP_GRPC_PORT"] == "4327"
        assert env["KTRDR_JAEGER_OTLP_HTTP_PORT"] == "4328"
        assert env["KTRDR_PROMETHEUS_PORT"] == "9091"
        # Slot 1 worker ports: 5011-5014 (shifted to avoid slot 0's 5003-5010)
        assert env["KTRDR_WORKER_PORT_1"] == "5011"
        assert env["KTRDR_WORKER_PORT_2"] == "5012"
        assert env["KTRDR_WORKER_PORT_3"] == "5013"
        assert env["KTRDR_WORKER_PORT_4"] == "5014"

    def test_to_env_dict_all_values_are_strings(self):
        """All values in env dict should be strings."""
        from ktrdr.cli.sandbox_ports import get_ports

        ports = get_ports(2)
        env = ports.to_env_dict()

        for key, value in env.items():
            assert isinstance(value, str), f"{key} should be string, got {type(value)}"

    def test_to_env_dict_slot_0_defaults(self):
        """Slot 0 env dict should match standard defaults."""
        from ktrdr.cli.sandbox_ports import get_ports

        ports = get_ports(0)
        env = ports.to_env_dict()

        assert env["KTRDR_API_PORT"] == "8000"
        assert env["KTRDR_DB_PORT"] == "5432"
        assert env["KTRDR_WORKER_PORT_1"] == "5003"


class TestAllPorts:
    """Tests for PortAllocation.all_ports() method."""

    def test_all_ports_returns_list(self):
        """all_ports() should return a list of integers."""
        from ktrdr.cli.sandbox_ports import get_ports

        ports = get_ports(1)
        all_ports = ports.all_ports()

        assert isinstance(all_ports, list)
        assert all(isinstance(p, int) for p in all_ports)

    def test_all_ports_contains_all_services(self):
        """all_ports() should contain all 11 ports."""
        from ktrdr.cli.sandbox_ports import get_ports

        ports = get_ports(1)
        all_ports = ports.all_ports()

        # 7 service ports + 4 worker ports = 11 total
        assert len(all_ports) == 11

        # Verify specific ports are included
        assert 8001 in all_ports  # backend
        assert 5433 in all_ports  # db
        assert 3001 in all_ports  # grafana
        assert 16687 in all_ports  # jaeger_ui
        assert 4327 in all_ports  # jaeger_otlp_grpc
        assert 4328 in all_ports  # jaeger_otlp_http
        assert 9091 in all_ports  # prometheus
        # Slot 1 worker ports: 5011-5014
        assert 5011 in all_ports  # worker 1
        assert 5012 in all_ports  # worker 2
        assert 5013 in all_ports  # worker 3
        assert 5014 in all_ports  # worker 4


class TestPortAvailability:
    """Tests for port availability checking."""

    def test_is_port_free_on_unbound_port(self):
        """is_port_free() returns True for unused port."""
        from ktrdr.cli.sandbox_ports import is_port_free

        # Port 59999 is unlikely to be in use
        # Using a high port to avoid conflicts
        result = is_port_free(59999)
        assert result is True

    def test_is_port_free_on_bound_port(self):
        """is_port_free() returns False when port is in use."""
        from ktrdr.cli.sandbox_ports import is_port_free

        # Bind a socket to test
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 59998))
            s.listen(1)

            result = is_port_free(59998)
            assert result is False

    def test_check_ports_available_all_free(self):
        """check_ports_available() returns empty list when all ports free."""
        from ktrdr.cli.sandbox_ports import check_ports_available

        # Mock is_port_free to return True for all
        with patch("ktrdr.cli.sandbox_ports.is_port_free", return_value=True):
            conflicts = check_ports_available(5)
            assert conflicts == []

    def test_check_ports_available_some_in_use(self):
        """check_ports_available() returns list of ports in use."""
        from ktrdr.cli.sandbox_ports import check_ports_available, get_ports

        ports = get_ports(3)

        # Mock: only backend port is in use
        def mock_is_port_free(port):
            return port != ports.backend

        with patch(
            "ktrdr.cli.sandbox_ports.is_port_free", side_effect=mock_is_port_free
        ):
            conflicts = check_ports_available(3)
            assert ports.backend in conflicts
            assert len(conflicts) == 1


class TestSlotConsistency:
    """Tests for slot allocation consistency."""

    def test_all_slots_have_unique_ports(self):
        """Each slot should have unique ports (no overlap)."""
        from ktrdr.cli.sandbox_ports import get_ports

        all_ports_seen = set()

        for slot in range(11):  # 0-10
            ports = get_ports(slot)
            slot_ports = set(ports.all_ports())

            # Check no overlap with previous slots
            overlap = all_ports_seen & slot_ports
            assert not overlap, f"Slot {slot} overlaps with previous slots: {overlap}"

            all_ports_seen.update(slot_ports)

    def test_deterministic_allocation(self):
        """Same slot should always return same ports."""
        from ktrdr.cli.sandbox_ports import get_ports

        ports_first = get_ports(3)
        ports_second = get_ports(3)

        assert ports_first.backend == ports_second.backend
        assert ports_first.db == ports_second.db
        assert ports_first.worker_ports == ports_second.worker_ports
