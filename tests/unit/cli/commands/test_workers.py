"""Tests for workers CLI command.

Tests the `ktrdr workers` command that displays worker status.
"""

import json
from unittest.mock import AsyncMock, patch


class TestWorkersCommand:
    """Tests for workers command output."""

    def test_workers_displays_table(self, runner) -> None:
        """Workers command displays worker information in table format."""
        from ktrdr.cli.app import app

        with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = [
                {
                    "worker_type": "backtest",
                    "status": "idle",
                    "capabilities": {"gpu_type": None},
                    "endpoint_url": "http://worker1:8080",
                    "current_operation_id": None,
                },
                {
                    "worker_type": "training",
                    "status": "busy",
                    "capabilities": {"gpu_type": "nvidia-rtx-4090"},
                    "endpoint_url": "http://gpu-worker:8080",
                    "current_operation_id": "op_abc123",
                },
            ]
            mock_client_class.return_value = mock_client

            result = runner.invoke(app, ["workers"])

            assert result.exit_code == 0
            # Check table headers
            assert "TYPE" in result.output
            assert "STATUS" in result.output
            assert "GPU" in result.output
            # Check worker data
            assert "backtest" in result.output
            assert "training" in result.output
            assert "idle" in result.output
            assert "busy" in result.output

    def test_workers_json_output(self, runner) -> None:
        """Workers command with --json outputs raw API data."""
        from ktrdr.cli.app import app

        with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = [
                {
                    "worker_type": "backtest",
                    "status": "idle",
                    "capabilities": {},
                    "endpoint_url": "http://worker1:8080",
                    "current_operation_id": None,
                }
            ]
            mock_client_class.return_value = mock_client

            result = runner.invoke(app, ["--json", "workers"])

            assert result.exit_code == 0
            data = json.loads(result.output)
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["worker_type"] == "backtest"

    def test_workers_empty(self, runner) -> None:
        """Workers command handles no workers gracefully."""
        from ktrdr.cli.app import app

        with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = []
            mock_client_class.return_value = mock_client

            result = runner.invoke(app, ["workers"])

            assert result.exit_code == 0
            assert "no workers" in result.output.lower()

    def test_workers_with_gpu(self, runner) -> None:
        """Workers command displays GPU capability correctly."""
        from ktrdr.cli.app import app

        with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = [
                {
                    "worker_type": "training",
                    "status": "idle",
                    "capabilities": {"gpu_type": "nvidia-rtx-4090"},
                    "endpoint_url": "http://gpu-worker:8080",
                    "current_operation_id": None,
                }
            ]
            mock_client_class.return_value = mock_client

            result = runner.invoke(app, ["workers"])

            assert result.exit_code == 0
            assert "nvidia-rtx-4090" in result.output


class TestWorkersErrors:
    """Tests for error handling in workers command."""

    def test_workers_exits_on_exception(self, runner) -> None:
        """Workers command exits with code 1 on exception."""
        from ktrdr.cli.app import app

        with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.side_effect = Exception("Connection failed")
            mock_client_class.return_value = mock_client

            result = runner.invoke(app, ["workers"])

            assert result.exit_code == 1
