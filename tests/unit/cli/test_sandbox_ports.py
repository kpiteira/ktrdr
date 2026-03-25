"""
Tests for the sandbox port allocation module.

This module tests port slot allocation for sandbox instances,
ensuring deterministic port mapping and conflict detection.

Observability (Jaeger, Grafana, Prometheus) runs as a shared stack
via devops-ai on fixed ports — not allocated per slot.
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

        assert ports.slot == 0
        assert ports.backend == 8000
        assert ports.db == 5432
        assert ports.worker_ports == [5003, 5004, 5005, 5006]

    def test_slot_1_returns_offset_ports(self):
        """Verify slot 1 has correct +1 offsets."""
        from ktrdr.cli.sandbox_ports import get_ports

        ports = get_ports(1)

        assert ports.slot == 1
        assert ports.backend == 8001
        assert ports.db == 5433
        # Worker ports for slot 1: 5007-5010 (shifted to avoid slot 0's 5003-5006)
        assert ports.worker_ports == [5007, 5008, 5009, 5010]

    def test_slot_2_worker_ports(self):
        """Verify worker port ranges for slot 2 (5017-5020)."""
        from ktrdr.cli.sandbox_ports import get_ports

        ports = get_ports(2)

        assert ports.slot == 2
        assert ports.backend == 8002
        # Slot 2: 5007 + (2-1)*10 = 5017
        assert ports.worker_ports == [5017, 5018, 5019, 5020]

    def test_slot_10_returns_max_offset_ports(self):
        """Verify slot 10 (maximum) has correct offsets."""
        from ktrdr.cli.sandbox_ports import get_ports

        ports = get_ports(10)

        assert ports.slot == 10
        assert ports.backend == 8010
        assert ports.db == 5442
        # Worker ports for slot 10: 5007 + (10-1)*10 = 5097
        assert ports.worker_ports == [5097, 5098, 5099, 5100]

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

        assert env["SLOT_NUMBER"] == "1"
        assert env["KTRDR_API_PORT"] == "8001"
        assert env["KTRDR_DB_PORT"] == "5433"
        # Slot 1 worker ports: 5007-5010 (shifted to avoid slot 0's 5003-5006)
        assert env["KTRDR_WORKER_PORT_1"] == "5007"
        assert env["KTRDR_WORKER_PORT_2"] == "5008"
        assert env["KTRDR_WORKER_PORT_3"] == "5009"
        assert env["KTRDR_WORKER_PORT_4"] == "5010"
        # No observability ports (shared stack)
        assert "KTRDR_GRAFANA_PORT" not in env
        assert "KTRDR_JAEGER_UI_PORT" not in env
        assert "KTRDR_PROMETHEUS_PORT" not in env

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
        """all_ports() should contain all 6 ports (2 services + 4 workers)."""
        from ktrdr.cli.sandbox_ports import get_ports

        ports = get_ports(1)
        all_ports = ports.all_ports()

        # 2 service ports + 4 worker ports = 6 total
        assert len(all_ports) == 6

        assert 8001 in all_ports  # backend
        assert 5433 in all_ports  # db
        assert 5007 in all_ports  # worker 1
        assert 5008 in all_ports  # worker 2
        assert 5009 in all_ports  # worker 3
        assert 5010 in all_ports  # worker 4


class TestPortAvailability:
    """Tests for port availability checking."""

    def test_is_port_free_on_unbound_port(self):
        """is_port_free() returns True for unused port."""
        from ktrdr.cli.sandbox_ports import is_port_free

        result = is_port_free(59999)
        assert result is True

    def test_is_port_free_on_bound_port(self):
        """is_port_free() returns False when port is in use."""
        from ktrdr.cli.sandbox_ports import is_port_free

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 59998))
            s.listen(1)

            result = is_port_free(59998)
            assert result is False

    def test_check_ports_available_all_free(self):
        """check_ports_available() returns empty list when all ports free."""
        from ktrdr.cli.sandbox_ports import check_ports_available

        with patch("ktrdr.cli.sandbox_ports.is_port_free", return_value=True):
            conflicts = check_ports_available(5)
            assert conflicts == []

    def test_check_ports_available_some_in_use(self):
        """check_ports_available() returns list of ports in use."""
        from ktrdr.cli.sandbox_ports import check_ports_available, get_ports

        ports = get_ports(3)

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
