"""Tests for orchestrator package structure.

These tests verify the basic package setup and entry point functionality.
"""

import subprocess
import sys
from pathlib import Path


class TestPackageImportable:
    """Test that the orchestrator package is properly importable."""

    def test_import_orchestrator_package(self):
        """Orchestrator package should be importable."""
        import orchestrator

        assert orchestrator is not None

    def test_package_has_version(self):
        """Package should expose a __version__ attribute."""
        import orchestrator

        assert hasattr(orchestrator, "__version__")
        assert isinstance(orchestrator.__version__, str)
        assert len(orchestrator.__version__) > 0


class TestCLIEntryPoint:
    """Test that the CLI entry point works correctly."""

    def test_cli_help_works(self):
        """Running 'orchestrator --help' should succeed and show help text."""
        result = subprocess.run(
            [sys.executable, "-m", "orchestrator", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert (
            "orchestrator" in result.stdout.lower() or "usage" in result.stdout.lower()
        )

    def test_cli_via_uv_run(self):
        """Running 'uv run orchestrator --help' should work."""
        result = subprocess.run(
            ["uv", "run", "orchestrator", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=Path(__file__).parent.parent.parent,  # Project root
        )
        assert result.returncode == 0, f"Failed with stderr: {result.stderr}"


class TestTypeHints:
    """Test that type hints are enabled via py.typed marker."""

    def test_py_typed_marker_exists(self):
        """Package should have py.typed marker for type hint support."""
        import orchestrator

        package_dir = Path(orchestrator.__file__).parent
        py_typed_path = package_dir / "py.typed"
        assert py_typed_path.exists(), f"py.typed marker not found at {py_typed_path}"
