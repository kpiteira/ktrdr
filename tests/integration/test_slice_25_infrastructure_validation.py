"""
SLICE-2.5 Infrastructure Validation Tests

This test module validates that ALL SLICE-2.5 cleanup tasks have been completed successfully:
- Task 2.5.1: Zero hasattr() cancellation patterns remain
- Task 2.5.2: TimeEstimationEngine moved to generic infrastructure
- Task 2.5.3: ProgressManager migration completed and CLI uses GenericProgressState
- Task 2.5.4: Complete infrastructure validation (this module)

These tests ensure the unified async infrastructure is clean and complete.
"""

import subprocess
from pathlib import Path

import pytest


class TestSlice25InfrastructureValidation:
    """Comprehensive validation tests for SLICE-2.5 infrastructure cleanup."""

    @pytest.fixture
    def ktrdr_root(self) -> Path:
        """Get the ktrdr package root directory."""
        return Path(__file__).parent.parent.parent / "ktrdr"

    def test_zero_hasattr_cancellation_patterns(self, ktrdr_root: Path):
        """
        Validate that NO hasattr() cancellation patterns exist in the codebase.

        Task 2.5.1 should have eliminated ALL patterns like:
        - hasattr(token, "is_cancelled_requested")
        - hasattr(token, "is_set")
        - hasattr(token, "is_cancelled")
        - hasattr(cancellation_token, "cancelled")
        """
        problematic_files = []

        for py_file in ktrdr_root.rglob("*.py"):
            if py_file.is_file():
                try:
                    content = py_file.read_text(encoding="utf-8")

                    # Check for hasattr patterns related to cancellation

                    lines = content.split("\n")
                    for line_num, line in enumerate(lines, 1):
                        line_lower = line.lower()
                        if "hasattr(" in line and any(
                            pattern in line_lower for pattern in ["cancel", "is_set"]
                        ):
                            problematic_files.append(
                                {
                                    "file": str(py_file.relative_to(ktrdr_root)),
                                    "line": line_num,
                                    "content": line.strip(),
                                }
                            )

                except Exception as e:
                    pytest.fail(f"Failed to read {py_file}: {e}")

        if problematic_files:
            error_msg = "Found hasattr() cancellation patterns that should have been eliminated:\n"
            for issue in problematic_files:
                error_msg += f"  {issue['file']}:{issue['line']}: {issue['content']}\n"
            pytest.fail(error_msg)

    def test_unified_cancellation_token_usage(self, ktrdr_root: Path):
        """
        Validate that all cancellation checking uses CancellationToken protocol exclusively.

        ServiceOrchestrator and AsyncHostService should only use:
        - token.is_cancelled()
        - CancellationToken protocol methods
        """
        # Check ServiceOrchestrator (base.py)
        base_py = ktrdr_root / "managers" / "base.py"
        if base_py.exists():
            content = base_py.read_text()

            # Should NOT contain hasattr patterns related to cancellation
            lines = content.split("\n")
            for line_num, line in enumerate(lines, 1):
                if "hasattr(" in line and any(
                    pattern in line.lower() for pattern in ["cancel", "is_set"]
                ):
                    pytest.fail(
                        f"ServiceOrchestrator in {base_py} still contains hasattr() cancellation patterns at line {line_num}: {line.strip()}"
                    )

            # Should contain unified cancellation checking
            assert (
                "token.is_cancelled()" in content
            ), f"ServiceOrchestrator in {base_py} missing unified cancellation method"

        # Check AsyncHostService
        async_host_py = ktrdr_root / "managers" / "async_host_service.py"
        if async_host_py.exists():
            content = async_host_py.read_text()

            # Should NOT contain hasattr patterns related to cancellation
            lines = content.split("\n")
            for line_num, line in enumerate(lines, 1):
                if "hasattr(" in line and any(
                    pattern in line.lower() for pattern in ["cancel", "is_set"]
                ):
                    pytest.fail(
                        f"AsyncHostService in {async_host_py} still contains hasattr() cancellation patterns at line {line_num}: {line.strip()}"
                    )

    def test_progress_manager_file_size_reduction(self, ktrdr_root: Path):
        """
        Validate that ProgressManager file has been completely eliminated.

        Task 2.5.3 should have completely removed the ProgressManager file
        and migrated all components to GenericProgressManager.
        """
        progress_manager_py = ktrdr_root / "data" / "components" / "progress_manager.py"

        # File should be completely removed (not just reduced)
        assert (
            not progress_manager_py.exists()
        ), f"ProgressManager file should be completely removed, but still exists: {progress_manager_py}"

        # Validate that components no longer import from the removed file
        problematic_imports = []
        for py_file in ktrdr_root.rglob("*.py"):
            if py_file.is_file():
                try:
                    content = py_file.read_text()
                    if "from ktrdr.data.components.progress_manager import" in content:
                        problematic_imports.append(str(py_file.relative_to(ktrdr_root)))
                except Exception:
                    pass

        if problematic_imports:
            error_msg = "Found imports from removed progress_manager.py file:\n"
            for file_path in problematic_imports:
                error_msg += f"  {file_path}\n"
            pytest.fail(error_msg)

    def test_time_estimation_engine_location(self, ktrdr_root: Path):
        """
        Validate that TimeEstimationEngine has been moved to generic infrastructure.

        Task 2.5.2 should have moved TimeEstimationEngine from:
        - FROM: ktrdr/data/components/progress_manager.py
        - TO: ktrdr/async_infrastructure/time_estimation.py
        """
        # New location should exist
        new_location = ktrdr_root / "async_infrastructure" / "time_estimation.py"
        assert (
            new_location.exists()
        ), f"TimeEstimationEngine missing at new location: {new_location}"

        # Should contain TimeEstimationEngine class
        new_content = new_location.read_text()
        assert (
            "class TimeEstimationEngine" in new_content
        ), f"TimeEstimationEngine class missing from {new_location}"

        # Should be domain-agnostic (no data-specific logic)
        assert (
            "data_manager" not in new_content.lower()
        ), f"TimeEstimationEngine in {new_location} should not contain data-specific logic"

        # Old location should not contain TimeEstimationEngine class anymore
        old_location = ktrdr_root / "data" / "components" / "progress_manager.py"
        if old_location.exists():
            old_content = old_location.read_text()
            assert (
                "class TimeEstimationEngine(" not in old_content
            ), f"TimeEstimationEngine class should be removed from {old_location}"

    def test_cli_uses_generic_progress_state(self, ktrdr_root: Path):
        """
        Validate that CLI components use GenericProgressState directly.

        Task 2.5.3 should have migrated CLI to use:
        - GenericProgressState (not ProgressState from progress_manager)
        """
        cli_dir = ktrdr_root / "cli"
        if not cli_dir.exists():
            pytest.skip("CLI directory not found")

        problematic_imports = []

        for py_file in cli_dir.rglob("*.py"):
            if py_file.is_file():
                try:
                    content = py_file.read_text()

                    # Should NOT import ProgressState from progress_manager
                    if (
                        "from ktrdr.data.components.progress_manager import" in content
                        and "ProgressState" in content
                    ):
                        problematic_imports.append(str(py_file.relative_to(ktrdr_root)))

                    # Should import GenericProgressState
                    if (
                        "ProgressState" in content
                        and "GenericProgressState" not in content
                    ):
                        # Check if it's actually using progress state functionality
                        if any(
                            pattern in content
                            for pattern in [
                                "progress_callback",
                                "progress_state",
                                "ProgressDisplay",
                            ]
                        ):
                            problematic_imports.append(
                                str(py_file.relative_to(ktrdr_root))
                            )

                except Exception as e:
                    pytest.fail(f"Failed to read {py_file}: {e}")

        if problematic_imports:
            error_msg = "CLI files still using old ProgressState instead of GenericProgressState:\n"
            for file_path in problematic_imports:
                error_msg += f"  {file_path}\n"
            pytest.fail(error_msg)

    def test_multi_timeframe_coordinator_migration(self, ktrdr_root: Path):
        """
        Validate that MultiTimeframeCoordinator uses GenericProgressManager.

        Task 2.5.3 should have migrated MultiTimeframeCoordinator to use
        GenericProgressManager instead of old ProgressManager.
        """
        coordinator_file = ktrdr_root / "data" / "multi_timeframe_coordinator.py"

        if not coordinator_file.exists():
            pytest.skip("MultiTimeframeCoordinator file not found")

        content = coordinator_file.read_text()

        # Should NOT import old ProgressManager
        assert (
            "from ktrdr.data.components.progress_manager import ProgressManager"
            not in content
        ), "MultiTimeframeCoordinator should not import old ProgressManager"

        # Should import GenericProgressManager
        assert (
            "GenericProgressManager" in content
        ), "MultiTimeframeCoordinator should use GenericProgressManager"

    def test_no_direct_progress_manager_instantiations(self, ktrdr_root: Path):
        """
        Validate that no code directly instantiates ProgressManager class.

        All components should use GenericProgressManager instead.
        """
        problematic_files = []

        for py_file in ktrdr_root.rglob("*.py"):
            if py_file.is_file():
                try:
                    content = py_file.read_text()

                    # Look for direct ProgressManager instantiation patterns
                    # Check for ProgressManager( but NOT GenericProgressManager(
                    lines = content.split("\n")
                    for line_num, line in enumerate(lines, 1):
                        if (
                            "ProgressManager(" in line
                            and "GenericProgressManager(" not in line
                        ):
                            # Skip the actual progress_manager.py file (may have deprecation examples)
                            if "progress_manager.py" not in str(py_file):
                                problematic_files.append(
                                    f"{py_file.relative_to(ktrdr_root)}:{line_num}"
                                )

                except Exception as e:
                    pytest.fail(f"Failed to read {py_file}: {e}")

        if problematic_files:
            error_msg = "Found direct ProgressManager instantiations (should use GenericProgressManager):\n"
            for file_path in problematic_files:
                error_msg += f"  {file_path}\n"
            pytest.fail(error_msg)

    def test_threading_event_only_for_service_lifecycle(self, ktrdr_root: Path):
        """
        Validate that threading.Event is only used for legitimate service lifecycle control.

        Should ONLY exist in:
        - training/data_optimization.py (performance optimization)
        - ib/gap_filler.py (service lifecycle)
        - ib/connection.py (connection management)

        Should NOT be used for async operation cancellation.
        """
        threading_event_files = []

        for py_file in ktrdr_root.rglob("*.py"):
            if py_file.is_file():
                try:
                    content = py_file.read_text()

                    if "threading.Event" in content:
                        threading_event_files.append(
                            str(py_file.relative_to(ktrdr_root))
                        )

                except Exception as e:
                    pytest.fail(f"Failed to read {py_file}: {e}")

        # Define allowed files for threading.Event usage
        allowed_files = {
            "training/data_optimization.py",
            "ib/gap_filler.py",
            "ib/connection.py",
        }

        unexpected_files = [f for f in threading_event_files if f not in allowed_files]

        if unexpected_files:
            error_msg = "Found unexpected threading.Event usage (should use CancellationToken for async operations):\n"
            for file_path in unexpected_files:
                error_msg += f"  {file_path}\n"
            error_msg += (
                f"\nAllowed files for service lifecycle control: {allowed_files}\n"
            )
            pytest.fail(error_msg)

    def test_import_paths_validation(self, ktrdr_root: Path):
        """
        Validate that all imports use correct async infrastructure paths.

        Components should import from:
        - ktrdr.async_infrastructure.time_estimation (not data.components.progress_manager)
        - ktrdr.async_infrastructure.progress (for GenericProgressState, GenericProgressManager)
        """
        problematic_imports = []

        for py_file in ktrdr_root.rglob("*.py"):
            if py_file.is_file() and "progress_manager.py" not in str(
                py_file
            ):  # Skip the deprecated file itself
                try:
                    content = py_file.read_text()

                    # Check for old import patterns that should be updated
                    old_patterns = [
                        "from ktrdr.data.components.progress_manager import TimeEstimationEngine",
                        "from ktrdr.data.components.progress_manager import ProgressState",
                    ]

                    for pattern in old_patterns:
                        if pattern in content:
                            problematic_imports.append(
                                {
                                    "file": str(py_file.relative_to(ktrdr_root)),
                                    "pattern": pattern,
                                }
                            )

                except Exception as e:
                    pytest.fail(f"Failed to read {py_file}: {e}")

        if problematic_imports:
            error_msg = "Found old import paths that should use new async infrastructure locations:\n"
            for issue in problematic_imports:
                error_msg += f"  {issue['file']}: {issue['pattern']}\n"
            pytest.fail(error_msg)

    def test_complete_test_suite_passes(self):
        """
        Validate that the complete test suite passes after infrastructure cleanup.

        This ensures no functionality regressions were introduced during cleanup.
        """
        # Run the complete test suite
        result = subprocess.run(
            ["make", "test-unit"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        if result.returncode != 0:
            pytest.fail(
                f"Test suite failed after infrastructure cleanup:\n{result.stdout}\n{result.stderr}"
            )

    def test_quality_checks_pass(self):
        """
        Validate that all quality checks pass after infrastructure cleanup.

        This ensures code quality is maintained throughout the cleanup process.
        """
        # Run quality checks
        result = subprocess.run(
            ["make", "quality"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        if result.returncode != 0:
            pytest.fail(
                f"Quality checks failed after infrastructure cleanup:\n{result.stdout}\n{result.stderr}"
            )

    def test_architecture_documentation_updated(self, ktrdr_root: Path):
        """
        Validate that architecture documentation reflects the cleaned infrastructure.

        This ensures documentation stays current with implementation.
        """
        # Check that async architecture spec exists and references unified patterns
        arch_spec = (
            ktrdr_root.parent
            / "docs"
            / "architecture"
            / "async"
            / "async-architecture-spec.md"
        )

        if arch_spec.exists():
            content = arch_spec.read_text()

            # Should document unified patterns
            assert (
                "CancellationToken" in content
            ), "Architecture documentation should reference unified CancellationToken protocol"

            assert (
                "GenericProgressManager" in content or "ServiceOrchestrator" in content
            ), "Architecture documentation should reference unified progress management"


class TestInfrastructureIntegration:
    """Integration tests to verify the cleaned infrastructure works correctly."""

    def test_cancellation_token_protocol_integration(self):
        """Test that cancellation works through the unified protocol."""
        from ktrdr.async_infrastructure.cancellation import create_cancellation_token

        # Create a cancellation token
        token = create_cancellation_token()

        # Initially not cancelled
        assert not token.is_cancelled()

        # Cancel the token
        token.cancel()

        # Now cancelled
        assert token.is_cancelled()

    def test_generic_progress_manager_integration(self):
        """Test that GenericProgressManager works correctly."""
        try:
            from ktrdr.async_infrastructure.progress import GenericProgressManager

            # Should be able to create instance
            progress_manager = GenericProgressManager()
            assert progress_manager is not None

        except ImportError as e:
            pytest.skip(f"GenericProgressManager not available: {e}")

    def test_time_estimation_engine_integration(self):
        """Test that TimeEstimationEngine works from new location."""
        try:
            from ktrdr.async_infrastructure.time_estimation import TimeEstimationEngine

            # Should be able to create instance
            engine = TimeEstimationEngine()
            assert engine is not None

        except ImportError as e:
            pytest.skip(f"TimeEstimationEngine not available: {e}")


# Additional validation helpers
def find_pattern_in_files(root_dir: Path, pattern: str) -> list[str]:
    """Find files containing a specific pattern."""
    matching_files = []

    for py_file in root_dir.rglob("*.py"):
        if py_file.is_file():
            try:
                content = py_file.read_text()
                if pattern in content:
                    matching_files.append(str(py_file.relative_to(root_dir)))
            except Exception:
                pass

    return matching_files


if __name__ == "__main__":
    # Allow running validation directly
    pytest.main([__file__, "-v"])
