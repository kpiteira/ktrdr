"""Tests for agent status CLI command.

Tests the multi-research status display including active researches,
worker utilization, budget, and capacity information.
"""

from unittest.mock import AsyncMock, patch

from ktrdr.cli.app import app


class TestAgentStatusCommand:
    """Tests for ktrdr agent status command."""

    def test_status_command_exists(self, runner) -> None:
        """Agent status command is registered."""
        result = runner.invoke(app, ["agent", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output.lower()

    def test_idle_status_display(self, runner) -> None:
        """Displays idle status when no active researches."""
        mock_response = {
            "status": "idle",
            "active_researches": [],
            "last_cycle": None,
            "workers": {
                "training": {"busy": 0, "total": 2},
                "backtesting": {"busy": 0, "total": 1},
            },
            "budget": {"remaining": 5.0, "daily_limit": 10.0},
            "capacity": {"active": 0, "limit": 6},
        }

        with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = runner.invoke(app, ["agent", "status"])

        assert result.exit_code == 0
        assert "idle" in result.output.lower()
        assert "Workers:" in result.output
        assert "Budget:" in result.output
        assert "Capacity:" in result.output

    def test_active_researches_display(self, runner) -> None:
        """Displays active researches in table format."""
        mock_response = {
            "status": "active",
            "active_researches": [
                {
                    "operation_id": "op_abc123",
                    "phase": "training",
                    "strategy_name": "rsi_variant_7",
                    "duration_seconds": 135,
                    "child_operation_id": "op_train_xyz",
                },
                {
                    "operation_id": "op_def456",
                    "phase": "designing",
                    "strategy_name": None,
                    "duration_seconds": 30,
                    "child_operation_id": "op_design_abc",
                },
            ],
            "workers": {
                "training": {"busy": 1, "total": 2},
                "backtesting": {"busy": 0, "total": 1},
            },
            "budget": {"remaining": 3.42, "daily_limit": 10.0},
            "capacity": {"active": 2, "limit": 6},
        }

        with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = runner.invoke(app, ["agent", "status"])

        assert result.exit_code == 0
        assert "Active researches: 2" in result.output
        assert "op_abc123" in result.output
        assert "training" in result.output
        assert "rsi_variant_7" in result.output
        assert "op_def456" in result.output
        assert "designing" in result.output

    def test_worker_utilization_display(self, runner) -> None:
        """Shows worker busy/total counts."""
        mock_response = {
            "status": "active",
            "active_researches": [
                {
                    "operation_id": "op_abc123",
                    "phase": "training",
                    "strategy_name": "test",
                    "duration_seconds": 60,
                    "child_operation_id": None,
                },
            ],
            "workers": {
                "training": {"busy": 2, "total": 3},
                "backtesting": {"busy": 1, "total": 2},
            },
            "budget": {"remaining": 5.0, "daily_limit": 10.0},
            "capacity": {"active": 1, "limit": 6},
        }

        with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = runner.invoke(app, ["agent", "status"])

        assert result.exit_code == 0
        # Expected format: "Workers: training 2/3, backtest 1/2"
        assert "training 2/3" in result.output
        assert "backtest 1/2" in result.output

    def test_budget_remaining_display(self, runner) -> None:
        """Shows budget remaining."""
        mock_response = {
            "status": "idle",
            "active_researches": [],
            "workers": {
                "training": {"busy": 0, "total": 2},
                "backtesting": {"busy": 0, "total": 1},
            },
            "budget": {"remaining": 3.42, "daily_limit": 10.0},
            "capacity": {"active": 0, "limit": 6},
        }

        with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = runner.invoke(app, ["agent", "status"])

        assert result.exit_code == 0
        # Expected format: "Budget: $3.42 remaining today"
        assert "$3.42" in result.output
        assert "remaining" in result.output.lower()

    def test_capacity_display(self, runner) -> None:
        """Shows capacity active/limit."""
        mock_response = {
            "status": "active",
            "active_researches": [
                {
                    "operation_id": "op_abc123",
                    "phase": "training",
                    "strategy_name": "test",
                    "duration_seconds": 60,
                    "child_operation_id": None,
                },
            ],
            "workers": {
                "training": {"busy": 1, "total": 2},
                "backtesting": {"busy": 0, "total": 1},
            },
            "budget": {"remaining": 5.0, "daily_limit": 10.0},
            "capacity": {"active": 3, "limit": 6},
        }

        with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = runner.invoke(app, ["agent", "status"])

        assert result.exit_code == 0
        # Expected format: "Capacity: 3/6 researches"
        assert "3/6" in result.output
        assert "researches" in result.output.lower()

    def test_duration_formatting(self, runner) -> None:
        """Duration is formatted as Xm Ys."""
        mock_response = {
            "status": "active",
            "active_researches": [
                {
                    "operation_id": "op_abc123",
                    "phase": "training",
                    "strategy_name": "test",
                    "duration_seconds": 135,  # 2m 15s
                    "child_operation_id": None,
                },
            ],
            "workers": {
                "training": {"busy": 1, "total": 2},
                "backtesting": {"busy": 0, "total": 1},
            },
            "budget": {"remaining": 5.0, "daily_limit": 10.0},
            "capacity": {"active": 1, "limit": 6},
        }

        with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = runner.invoke(app, ["agent", "status"])

        assert result.exit_code == 0
        # Expected format: "(2m 15s)"
        assert "2m 15s" in result.output

    def test_strategy_name_missing_shows_dash(self, runner) -> None:
        """Strategy name shows '-' when None."""
        mock_response = {
            "status": "active",
            "active_researches": [
                {
                    "operation_id": "op_abc123",
                    "phase": "designing",
                    "strategy_name": None,
                    "duration_seconds": 30,
                    "child_operation_id": None,
                },
            ],
            "workers": {
                "training": {"busy": 0, "total": 2},
                "backtesting": {"busy": 0, "total": 1},
            },
            "budget": {"remaining": 5.0, "daily_limit": 10.0},
            "capacity": {"active": 1, "limit": 6},
        }

        with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = runner.invoke(app, ["agent", "status"])

        assert result.exit_code == 0
        # When strategy_name is None, show "-"
        assert "strategy: -" in result.output.lower() or "- " in result.output

    def test_last_cycle_shown_when_idle(self, runner) -> None:
        """Shows last cycle info when idle and last_cycle is present."""
        mock_response = {
            "status": "idle",
            "active_researches": [],
            "last_cycle": {
                "operation_id": "op_last123",
                "outcome": "completed",
            },
            "workers": {
                "training": {"busy": 0, "total": 2},
                "backtesting": {"busy": 0, "total": 1},
            },
            "budget": {"remaining": 5.0, "daily_limit": 10.0},
            "capacity": {"active": 0, "limit": 6},
        }

        with patch("ktrdr.cli.client.AsyncCLIClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = runner.invoke(app, ["agent", "status"])

        assert result.exit_code == 0
        assert "op_last123" in result.output
        assert "completed" in result.output.lower()


class TestFormatDuration:
    """Tests for format_duration helper function."""

    def test_format_under_minute(self) -> None:
        """Format seconds under 1 minute."""
        from ktrdr.cli.commands.agent import format_duration

        assert format_duration(30) == "0m 30s"
        assert format_duration(5) == "0m 05s"
        assert format_duration(0) == "0m 00s"

    def test_format_over_minute(self) -> None:
        """Format seconds over 1 minute."""
        from ktrdr.cli.commands.agent import format_duration

        assert format_duration(60) == "1m 00s"
        assert format_duration(135) == "2m 15s"
        assert format_duration(3661) == "61m 01s"
