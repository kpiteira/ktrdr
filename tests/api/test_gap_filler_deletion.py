"""
Unit tests verifying gap_filler.py and gap_commands.py have been deleted.

These tests ensure the architectural cleanup is complete and no
gap_filler references remain in the codebase.
"""

import importlib
from pathlib import Path

import pytest


class TestGapFillerDeletion:
    """Test suite verifying gap_filler components are deleted."""

    def test_gap_filler_py_deleted(self):
        """Verify gap_filler.py file has been deleted."""
        gap_filler_path = Path("ktrdr/data/acquisition/gap_filler.py")
        assert not gap_filler_path.exists(), "gap_filler.py should be deleted"

    def test_gap_commands_py_deleted(self):
        """Verify gap_commands.py file has been deleted."""
        gap_commands_path = Path("ktrdr/cli/gap_commands.py")
        assert not gap_commands_path.exists(), "gap_commands.py should be deleted"

    def test_gap_filler_not_importable(self):
        """Verify gap_filler module cannot be imported."""
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("ktrdr.data.acquisition.gap_filler")

    def test_gap_commands_not_importable(self):
        """Verify gap_commands module cannot be imported."""
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("ktrdr.cli.gap_commands")

    def test_get_gap_filler_function_removed_from_system(self):
        """Verify get_gap_filler is not used in system.py."""
        from ktrdr.api.endpoints import system

        # Verify get_gap_filler is not in the module
        assert not hasattr(
            system, "get_gap_filler"
        ), "get_gap_filler should not be imported in system.py"

    def test_gap_filler_status_endpoint_removed(self):
        """Verify gap_filler_status endpoint removed from system.py."""
        from ktrdr.api.endpoints import system

        # Verify endpoint function doesn't exist
        assert not hasattr(
            system, "get_gap_filler_status"
        ), "get_gap_filler_status endpoint should be removed"

    def test_no_gap_filler_references_in_system_status(self):
        """Verify system status endpoints don't reference gap_filler."""
        import inspect

        from ktrdr.api.endpoints.system import get_system_status

        # Get source code of get_system_status function
        source = inspect.getsource(get_system_status)

        # Verify no gap_filler references
        assert (
            "gap_filler" not in source.lower()
        ), "get_system_status should not reference gap_filler"
        assert (
            "GapFiller" not in source
        ), "get_system_status should not reference GapFiller"

    def test_no_gap_filler_in_codebase(self):
        """
        Verify no gap_filler references in ktrdr/ directory.

        This is a comprehensive check to ensure complete removal.
        """
        ktrdr_dir = Path("ktrdr")
        if not ktrdr_dir.exists():
            pytest.skip("ktrdr directory not found")

        violations = []

        # Search all Python files for gap_filler references
        for py_file in ktrdr_dir.rglob("*.py"):
            # Skip __pycache__
            if "__pycache__" in str(py_file):
                continue

            content = py_file.read_text()

            # Check for gap_filler references (case-insensitive)
            if "gap_filler" in content.lower() or "GapFiller" in content:
                violations.append(str(py_file))

        assert len(violations) == 0, f"Found gap_filler references in: {violations}"

    def test_gap_filler_tests_deleted(self):
        """Verify gap_filler test files have been cleaned up."""
        tests_dir = Path("tests")
        if not tests_dir.exists():
            pytest.skip("tests directory not found")

        # Look for any gap_filler references in test files
        violations = []

        for test_file in tests_dir.rglob("test_*.py"):
            if "__pycache__" in str(test_file):
                continue

            # Skip this deletion test file itself
            if "test_gap_filler_deletion.py" in str(test_file):
                continue

            content = test_file.read_text()

            # Check for gap_filler references
            if "gap_filler" in content or "GapFiller" in content:
                violations.append(str(test_file))

        assert (
            len(violations) == 0
        ), f"Found gap_filler references in tests: {violations}"
