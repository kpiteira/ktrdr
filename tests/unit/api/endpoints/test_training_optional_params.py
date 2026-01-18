"""
Tests for Task 1.7: Make symbols/timeframes optional in training API.

These tests verify that:
1. TrainingRequest accepts optional symbols/timeframes
2. TrainingService extracts symbols/timeframes from strategy config when not provided
3. CLI adapter works with optional symbols/timeframes
4. CLI train command works without hardcoded symbols/timeframes
"""

import pytest
from pydantic import ValidationError as PydanticValidationError


class TestTrainingRequestOptionalParams:
    """Test that TrainingRequest accepts optional symbols/timeframes."""

    def test_training_request_accepts_optional_symbols(self) -> None:
        """TrainingRequest should accept request without symbols."""
        from ktrdr.api.endpoints.training import TrainingRequest

        # Should not raise - symbols are optional
        request = TrainingRequest(
            strategy_name="v3_minimal",
            timeframes=["1h"],
        )
        assert request.symbols is None
        assert request.strategy_name == "v3_minimal"
        assert request.timeframes == ["1h"]

    def test_training_request_accepts_optional_timeframes(self) -> None:
        """TrainingRequest should accept request without timeframes."""
        from ktrdr.api.endpoints.training import TrainingRequest

        # Should not raise - timeframes are optional
        request = TrainingRequest(
            strategy_name="v3_minimal",
            symbols=["AAPL"],
        )
        assert request.timeframes is None
        assert request.symbols == ["AAPL"]

    def test_training_request_accepts_both_optional(self) -> None:
        """TrainingRequest should accept request without symbols or timeframes."""
        from ktrdr.api.endpoints.training import TrainingRequest

        # Should not raise - both are optional, strategy config will provide
        request = TrainingRequest(
            strategy_name="v3_minimal",
        )
        assert request.symbols is None
        assert request.timeframes is None

    def test_training_request_validates_symbols_if_provided(self) -> None:
        """TrainingRequest should validate symbols if provided (non-empty list)."""
        from ktrdr.api.endpoints.training import TrainingRequest

        # Empty list should fail validation
        with pytest.raises(PydanticValidationError):
            TrainingRequest(
                strategy_name="v3_minimal",
                symbols=[],  # Empty list not allowed
            )

    def test_training_request_validates_timeframes_if_provided(self) -> None:
        """TrainingRequest should validate timeframes if provided (non-empty list)."""
        from ktrdr.api.endpoints.training import TrainingRequest

        # Empty list should fail validation
        with pytest.raises(PydanticValidationError):
            TrainingRequest(
                strategy_name="v3_minimal",
                timeframes=[],  # Empty list not allowed
            )


class TestTrainingAdapterOptionalParams:
    """Test that TrainingOperationAdapter works with optional params."""

    def test_adapter_accepts_optional_symbols(self) -> None:
        """TrainingOperationAdapter should accept None for symbols."""
        from ktrdr.cli.operation_adapters import TrainingOperationAdapter

        adapter = TrainingOperationAdapter(
            strategy_name="v3_minimal",
            symbols=None,  # Optional
            timeframes=["1h"],
        )
        assert adapter.symbols is None

    def test_adapter_accepts_optional_timeframes(self) -> None:
        """TrainingOperationAdapter should accept None for timeframes."""
        from ktrdr.cli.operation_adapters import TrainingOperationAdapter

        adapter = TrainingOperationAdapter(
            strategy_name="v3_minimal",
            symbols=["AAPL"],
            timeframes=None,  # Optional
        )
        assert adapter.timeframes is None

    def test_adapter_payload_omits_none_symbols(self) -> None:
        """Adapter payload should not include symbols when None."""
        from ktrdr.cli.operation_adapters import TrainingOperationAdapter

        adapter = TrainingOperationAdapter(
            strategy_name="v3_minimal",
            symbols=None,
            timeframes=["1h"],
        )

        payload = adapter.get_start_payload()
        assert "symbols" not in payload
        assert payload["timeframes"] == ["1h"]

    def test_adapter_payload_omits_none_timeframes(self) -> None:
        """Adapter payload should not include timeframes when None."""
        from ktrdr.cli.operation_adapters import TrainingOperationAdapter

        adapter = TrainingOperationAdapter(
            strategy_name="v3_minimal",
            symbols=["AAPL"],
            timeframes=None,
        )

        payload = adapter.get_start_payload()
        assert "timeframes" not in payload
        assert payload["symbols"] == ["AAPL"]

    def test_adapter_payload_omits_both_when_none(self) -> None:
        """Adapter payload should omit both when None."""
        from ktrdr.cli.operation_adapters import TrainingOperationAdapter

        adapter = TrainingOperationAdapter(
            strategy_name="v3_minimal",
            symbols=None,
            timeframes=None,
        )

        payload = adapter.get_start_payload()
        assert "symbols" not in payload
        assert "timeframes" not in payload
        assert payload["strategy_name"] == "v3_minimal"


class TestTrainCommandOptionalParams:
    """Test that train command works without hardcoded symbols/timeframes."""

    def test_train_command_does_not_pass_hardcoded_symbols(self) -> None:
        """Train command should not pass hardcoded symbols to adapter."""
        from unittest.mock import MagicMock, patch

        from typer.testing import CliRunner

        from ktrdr.cli.app import app
        from ktrdr.cli.commands.train import train

        app.command()(train)

        try:
            runner = CliRunner()

            with patch(
                "ktrdr.cli.operation_runner.OperationRunner"
            ) as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner

                with patch(
                    "ktrdr.cli.operation_adapters.TrainingOperationAdapter"
                ) as mock_adapter_class:
                    runner.invoke(
                        app,
                        [
                            "train",
                            "v3_minimal",
                            "--start",
                            "2024-01-01",
                            "--end",
                            "2024-06-01",
                        ],
                    )

                    mock_adapter_class.assert_called_once()
                    call_kwargs = mock_adapter_class.call_args[1]
                    # Should NOT have hardcoded ["AAPL"] - should be None or not present
                    assert (
                        call_kwargs.get("symbols") is None
                        or "symbols" not in call_kwargs
                    )
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "train"
            ]

    def test_train_command_accepts_symbols_override(self) -> None:
        """Train command should accept --symbols override."""
        from unittest.mock import MagicMock, patch

        from typer.testing import CliRunner

        from ktrdr.cli.app import app
        from ktrdr.cli.commands.train import train

        app.command()(train)

        try:
            runner = CliRunner()

            with patch(
                "ktrdr.cli.operation_runner.OperationRunner"
            ) as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner

                with patch(
                    "ktrdr.cli.operation_adapters.TrainingOperationAdapter"
                ) as mock_adapter_class:
                    runner.invoke(
                        app,
                        [
                            "train",
                            "v3_minimal",
                            "--start",
                            "2024-01-01",
                            "--end",
                            "2024-06-01",
                            "--symbols",
                            "AAPL,MSFT",
                        ],
                    )

                    mock_adapter_class.assert_called_once()
                    call_kwargs = mock_adapter_class.call_args[1]
                    assert call_kwargs["symbols"] == ["AAPL", "MSFT"]
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "train"
            ]

    def test_train_command_accepts_timeframes_override(self) -> None:
        """Train command should accept --timeframes override."""
        from unittest.mock import MagicMock, patch

        from typer.testing import CliRunner

        from ktrdr.cli.app import app
        from ktrdr.cli.commands.train import train

        app.command()(train)

        try:
            runner = CliRunner()

            with patch(
                "ktrdr.cli.operation_runner.OperationRunner"
            ) as mock_runner_class:
                mock_runner = MagicMock()
                mock_runner_class.return_value = mock_runner

                with patch(
                    "ktrdr.cli.operation_adapters.TrainingOperationAdapter"
                ) as mock_adapter_class:
                    runner.invoke(
                        app,
                        [
                            "train",
                            "v3_minimal",
                            "--start",
                            "2024-01-01",
                            "--end",
                            "2024-06-01",
                            "--timeframes",
                            "1h,4h",
                        ],
                    )

                    mock_adapter_class.assert_called_once()
                    call_kwargs = mock_adapter_class.call_args[1]
                    assert call_kwargs["timeframes"] == ["1h", "4h"]
        finally:
            app.registered_commands = [
                cmd for cmd in app.registered_commands if cmd.name != "train"
            ]
