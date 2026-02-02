"""Tests for kinfra slot container management.

Tests the container start/stop functionality and health check logic
for sandbox slots.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestStartSlotContainersCommand:
    """Tests that start_slot_containers builds correct docker command."""

    @patch("ktrdr.cli.kinfra.slots._wait_for_health")
    @patch("ktrdr.cli.kinfra.slots.subprocess.run")
    def test_start_command_correct(
        self, mock_run: MagicMock, mock_health: MagicMock, tmp_path: Path
    ) -> None:
        """start_slot_containers should build correct docker compose command."""
        from ktrdr.cli.kinfra.slots import start_slot_containers
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path
        slot.ports = {"api": 8001}

        mock_run.return_value = MagicMock(returncode=0, stderr="")

        start_slot_containers(slot)

        # Verify subprocess.run was called with correct command
        mock_run.assert_called_once()
        call_args = mock_run.call_args

        cmd = call_args[0][0]
        assert cmd[0] == "docker"
        assert cmd[1] == "compose"
        assert "--env-file" in cmd
        assert ".env.sandbox" in cmd
        assert "-f" in cmd
        assert "docker-compose.yml" in cmd
        assert "docker-compose.override.yml" in cmd
        assert "up" in cmd
        assert "-d" in cmd

        # Verify cwd is set to infrastructure path
        assert call_args.kwargs["cwd"] == tmp_path

    @patch("ktrdr.cli.kinfra.slots._wait_for_health")
    @patch("ktrdr.cli.kinfra.slots.subprocess.run")
    def test_start_includes_env_file(
        self, mock_run: MagicMock, mock_health: MagicMock, tmp_path: Path
    ) -> None:
        """start_slot_containers should include --env-file .env.sandbox."""
        from ktrdr.cli.kinfra.slots import start_slot_containers
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path
        slot.ports = {"api": 8001}

        mock_run.return_value = MagicMock(returncode=0, stderr="")

        start_slot_containers(slot)

        cmd = mock_run.call_args[0][0]
        # Find index of --env-file and check next arg
        env_file_idx = cmd.index("--env-file")
        assert cmd[env_file_idx + 1] == ".env.sandbox"

    @patch("ktrdr.cli.kinfra.slots._wait_for_health")
    @patch("ktrdr.cli.kinfra.slots.subprocess.run")
    def test_start_raises_on_failure(
        self, mock_run: MagicMock, mock_health: MagicMock, tmp_path: Path
    ) -> None:
        """start_slot_containers should raise RuntimeError on docker failure."""
        from ktrdr.cli.kinfra.slots import start_slot_containers
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path
        slot.ports = {"api": 8001}

        mock_run.return_value = MagicMock(returncode=1, stderr="Container failed")

        with pytest.raises(RuntimeError, match="Failed to start containers"):
            start_slot_containers(slot)

    @patch("ktrdr.cli.kinfra.slots._wait_for_health")
    @patch("ktrdr.cli.kinfra.slots.subprocess.run")
    def test_start_calls_health_check(
        self, mock_run: MagicMock, mock_health: MagicMock, tmp_path: Path
    ) -> None:
        """start_slot_containers should wait for health check after start."""
        from ktrdr.cli.kinfra.slots import start_slot_containers
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path
        slot.ports = {"api": 8001}

        mock_run.return_value = MagicMock(returncode=0, stderr="")

        start_slot_containers(slot, timeout=60)

        mock_health.assert_called_once_with(slot, 60)


class TestStopSlotContainersCommand:
    """Tests that stop_slot_containers builds correct docker command."""

    @patch("ktrdr.cli.kinfra.slots.subprocess.run")
    def test_stop_command_correct(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """stop_slot_containers should build correct docker compose down command."""
        from ktrdr.cli.kinfra.slots import stop_slot_containers
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path

        stop_slot_containers(slot)

        mock_run.assert_called_once()
        call_args = mock_run.call_args

        cmd = call_args[0][0]
        assert cmd == ["docker", "compose", "down"]

        # Verify cwd is set to infrastructure path
        assert call_args.kwargs["cwd"] == tmp_path

    @patch("ktrdr.cli.kinfra.slots.subprocess.run")
    def test_stop_uses_check_true(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """stop_slot_containers should use check=True to raise on failure."""
        from ktrdr.cli.kinfra.slots import stop_slot_containers
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.infrastructure_path = tmp_path

        stop_slot_containers(slot)

        call_args = mock_run.call_args
        assert call_args.kwargs["check"] is True


class TestWaitForHealth:
    """Tests for health check waiting logic."""

    @patch("ktrdr.cli.kinfra.slots.time.sleep")
    @patch("httpx.get")
    def test_health_returns_on_200(
        self, mock_get: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """_wait_for_health should return when health endpoint returns 200."""
        from ktrdr.cli.kinfra.slots import _wait_for_health
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.ports = {"api": 8001}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Should not raise
        _wait_for_health(slot, timeout=10)

        mock_get.assert_called_once()
        assert "8001" in mock_get.call_args[0][0]
        assert "/api/v1/health" in mock_get.call_args[0][0]

    @patch("ktrdr.cli.kinfra.slots.time.time")
    @patch("ktrdr.cli.kinfra.slots.time.sleep")
    @patch("httpx.get")
    def test_health_retries_on_failure(
        self, mock_get: MagicMock, mock_sleep: MagicMock, mock_time: MagicMock
    ) -> None:
        """_wait_for_health should retry when health check fails."""
        import httpx

        from ktrdr.cli.kinfra.slots import _wait_for_health
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.ports = {"api": 8001}

        # First call raises, second succeeds
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.side_effect = [httpx.RequestError("Connection refused"), mock_response]

        # Simulate time progression: 0, 2 (still within timeout)
        mock_time.side_effect = [0, 2, 4]

        _wait_for_health(slot, timeout=10)

        assert mock_get.call_count == 2
        mock_sleep.assert_called_with(2)

    @patch("ktrdr.cli.kinfra.slots.time.time")
    @patch("ktrdr.cli.kinfra.slots.time.sleep")
    @patch("httpx.get")
    def test_health_raises_on_timeout(
        self, mock_get: MagicMock, mock_sleep: MagicMock, mock_time: MagicMock
    ) -> None:
        """_wait_for_health should raise RuntimeError on timeout."""
        import httpx

        from ktrdr.cli.kinfra.slots import _wait_for_health
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.ports = {"api": 8001}

        mock_get.side_effect = httpx.RequestError("Connection refused")

        # Simulate time progression past timeout
        mock_time.side_effect = [0, 5, 11]  # Starts at 0, checks at 5, exceeds 10

        with pytest.raises(RuntimeError, match="not healthy after 10s"):
            _wait_for_health(slot, timeout=10)

    @patch("ktrdr.cli.kinfra.slots.time.time")
    @patch("ktrdr.cli.kinfra.slots.time.sleep")
    @patch("httpx.get")
    def test_health_retries_on_non_200(
        self, mock_get: MagicMock, mock_sleep: MagicMock, mock_time: MagicMock
    ) -> None:
        """_wait_for_health should retry when status is not 200."""
        from ktrdr.cli.kinfra.slots import _wait_for_health
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.ports = {"api": 8001}

        # First returns 503, second returns 200
        mock_response_503 = MagicMock()
        mock_response_503.status_code = 503
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_get.side_effect = [mock_response_503, mock_response_200]

        mock_time.side_effect = [0, 2, 4]

        _wait_for_health(slot, timeout=10)

        assert mock_get.call_count == 2

    @patch("ktrdr.cli.kinfra.slots.time.sleep")
    @patch("httpx.get")
    def test_health_uses_correct_url(
        self, mock_get: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """_wait_for_health should use /api/v1/health endpoint."""
        from ktrdr.cli.kinfra.slots import _wait_for_health
        from ktrdr.cli.sandbox_registry import SlotInfo

        slot = MagicMock(spec=SlotInfo)
        slot.ports = {"api": 8003}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        _wait_for_health(slot, timeout=10)

        expected_url = "http://localhost:8003/api/v1/health"
        mock_get.assert_called_with(expected_url, timeout=5)
