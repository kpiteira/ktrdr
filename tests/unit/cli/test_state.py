"""Tests for CLIState dataclass.

Tests the immutable state object that holds CLI-wide configuration,
populated by the root Typer callback and passed to commands.
"""

from dataclasses import FrozenInstanceError

import pytest


class TestCLIStateDefaults:
    """Tests for CLIState default values."""

    def test_cli_state_defaults(self) -> None:
        """CLIState has expected default values."""
        from ktrdr.cli.state import CLIState

        state = CLIState()

        assert state.json_mode is False
        assert state.verbose is False
        assert state.api_url == "http://localhost:8000"

    def test_cli_state_default_json_mode_is_false(self) -> None:
        """json_mode defaults to False (human-readable output)."""
        from ktrdr.cli.state import CLIState

        state = CLIState()

        assert state.json_mode is False
        assert isinstance(state.json_mode, bool)

    def test_cli_state_default_verbose_is_false(self) -> None:
        """verbose defaults to False (quiet output)."""
        from ktrdr.cli.state import CLIState

        state = CLIState()

        assert state.verbose is False
        assert isinstance(state.verbose, bool)

    def test_cli_state_default_api_url_is_localhost(self) -> None:
        """api_url defaults to localhost:8000."""
        from ktrdr.cli.state import CLIState

        state = CLIState()

        assert state.api_url == "http://localhost:8000"
        assert isinstance(state.api_url, str)


class TestCLIStateImmutability:
    """Tests for CLIState immutability (frozen dataclass)."""

    def test_cli_state_immutable_json_mode(self) -> None:
        """Cannot modify json_mode after creation."""
        from ktrdr.cli.state import CLIState

        state = CLIState()

        with pytest.raises(FrozenInstanceError):
            state.json_mode = True  # type: ignore[misc]

    def test_cli_state_immutable_verbose(self) -> None:
        """Cannot modify verbose after creation."""
        from ktrdr.cli.state import CLIState

        state = CLIState()

        with pytest.raises(FrozenInstanceError):
            state.verbose = True  # type: ignore[misc]

    def test_cli_state_immutable_api_url(self) -> None:
        """Cannot modify api_url after creation."""
        from ktrdr.cli.state import CLIState

        state = CLIState()

        with pytest.raises(FrozenInstanceError):
            state.api_url = "http://other:9000"  # type: ignore[misc]


class TestCLIStateCustomValues:
    """Tests for CLIState with custom values."""

    def test_cli_state_custom_json_mode(self) -> None:
        """json_mode can be set to True at construction."""
        from ktrdr.cli.state import CLIState

        state = CLIState(json_mode=True)

        assert state.json_mode is True

    def test_cli_state_custom_verbose(self) -> None:
        """verbose can be set to True at construction."""
        from ktrdr.cli.state import CLIState

        state = CLIState(verbose=True)

        assert state.verbose is True

    def test_cli_state_custom_api_url(self) -> None:
        """api_url can be set to custom URL at construction."""
        from ktrdr.cli.state import CLIState

        state = CLIState(api_url="http://backend.example.com:8000")

        assert state.api_url == "http://backend.example.com:8000"

    def test_cli_state_all_custom_values(self) -> None:
        """All fields can be customized at construction."""
        from ktrdr.cli.state import CLIState

        state = CLIState(
            json_mode=True,
            verbose=True,
            api_url="http://remote:9000",
        )

        assert state.json_mode is True
        assert state.verbose is True
        assert state.api_url == "http://remote:9000"


class TestCLIStateLightweightImport:
    """Tests for CLIState import behavior."""

    def test_cli_state_import_is_lightweight(self) -> None:
        """CLIState can be imported without heavy dependencies.

        The state module should not import pandas, OTEL, or other
        heavy dependencies to keep CLI startup fast.
        """
        import sys

        # Clear any cached imports
        modules_before = set(sys.modules.keys())

        from ktrdr.cli.state import CLIState

        modules_after = set(sys.modules.keys())
        new_modules = modules_after - modules_before

        # Should not import heavy dependencies
        heavy_deps = {"pandas", "numpy", "opentelemetry", "torch"}
        imported_heavy = heavy_deps & {m.split(".")[0] for m in new_modules}

        assert not imported_heavy, f"Heavy deps imported: {imported_heavy}"

        # Verify it still works
        state = CLIState()
        assert state is not None
