"""
Tests to verify version is sourced from ktrdr.version module, not metadata.

This test verifies that after the metadata module removal (Task 7.1),
the version is still correctly accessible via the standard package interface.
"""

from ktrdr.version import __version__, get_version


class TestVersionSource:
    """Verify version is accessible after metadata module removal."""

    def test_version_is_string(self) -> None:
        """Version should be a non-empty string."""
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_version_format(self) -> None:
        """Version should have semantic version format (x.y.z or x.y.z.build)."""
        parts = __version__.split(".")
        assert len(parts) >= 3, f"Version {__version__} should have at least 3 parts"
        # All parts should be numeric
        for part in parts:
            assert part.isdigit(), f"Version part {part} should be numeric"

    def test_get_version_function(self) -> None:
        """get_version() should return the same as __version__."""
        assert get_version() == __version__

    def test_version_accessible_from_package(self) -> None:
        """Version should be accessible from the main package."""
        import ktrdr

        assert hasattr(ktrdr, "__version__")
        assert ktrdr.__version__ == __version__
