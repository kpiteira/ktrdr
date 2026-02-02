"""Tests for kinfra error types.

Tests the error hierarchy and messages for worktree and slot operations.
"""


class TestErrorHierarchy:
    """Tests that all errors inherit from KinfraError."""

    def test_kinfra_error_is_exception(self) -> None:
        """KinfraError should inherit from Exception."""
        from ktrdr.cli.kinfra.errors import KinfraError

        assert issubclass(KinfraError, Exception)

    def test_worktree_exists_error_inherits_from_kinfra_error(self) -> None:
        """WorktreeExistsError should inherit from KinfraError."""
        from ktrdr.cli.kinfra.errors import KinfraError, WorktreeExistsError

        assert issubclass(WorktreeExistsError, KinfraError)

    def test_worktree_dirty_error_inherits_from_kinfra_error(self) -> None:
        """WorktreeDirtyError should inherit from KinfraError."""
        from ktrdr.cli.kinfra.errors import KinfraError, WorktreeDirtyError

        assert issubclass(WorktreeDirtyError, KinfraError)

    def test_slot_exhausted_error_inherits_from_kinfra_error(self) -> None:
        """SlotExhaustedError should inherit from KinfraError."""
        from ktrdr.cli.kinfra.errors import KinfraError, SlotExhaustedError

        assert issubclass(SlotExhaustedError, KinfraError)

    def test_slot_claimed_error_inherits_from_kinfra_error(self) -> None:
        """SlotClaimedError should inherit from KinfraError."""
        from ktrdr.cli.kinfra.errors import KinfraError, SlotClaimedError

        assert issubclass(SlotClaimedError, KinfraError)

    def test_milestone_not_found_error_inherits_from_kinfra_error(self) -> None:
        """MilestoneNotFoundError should inherit from KinfraError."""
        from ktrdr.cli.kinfra.errors import KinfraError, MilestoneNotFoundError

        assert issubclass(MilestoneNotFoundError, KinfraError)

    def test_sandbox_start_error_inherits_from_kinfra_error(self) -> None:
        """SandboxStartError should inherit from KinfraError."""
        from ktrdr.cli.kinfra.errors import KinfraError, SandboxStartError

        assert issubclass(SandboxStartError, KinfraError)

    def test_invalid_operation_error_inherits_from_kinfra_error(self) -> None:
        """InvalidOperationError should inherit from KinfraError."""
        from ktrdr.cli.kinfra.errors import InvalidOperationError, KinfraError

        assert issubclass(InvalidOperationError, KinfraError)


class TestErrorMessages:
    """Tests that errors have descriptive messages."""

    def test_worktree_exists_error_with_message(self) -> None:
        """WorktreeExistsError should accept and preserve message."""
        from ktrdr.cli.kinfra.errors import WorktreeExistsError

        error = WorktreeExistsError("Worktree my-feature already exists")
        assert "my-feature" in str(error)
        assert "exists" in str(error)

    def test_worktree_dirty_error_with_message(self) -> None:
        """WorktreeDirtyError should accept and preserve message."""
        from ktrdr.cli.kinfra.errors import WorktreeDirtyError

        error = WorktreeDirtyError("Uncommitted changes in worktree")
        assert "uncommitted" in str(error).lower()

    def test_slot_exhausted_error_with_message(self) -> None:
        """SlotExhaustedError should accept and preserve message."""
        from ktrdr.cli.kinfra.errors import SlotExhaustedError

        error = SlotExhaustedError("All 2 sandbox slots are in use")
        assert "2" in str(error)
        assert "slots" in str(error)

    def test_slot_claimed_error_with_message(self) -> None:
        """SlotClaimedError should accept and preserve message."""
        from ktrdr.cli.kinfra.errors import SlotClaimedError

        error = SlotClaimedError("Slot 1 is claimed by other-worktree")
        assert "slot" in str(error).lower()
        assert "claimed" in str(error).lower()

    def test_milestone_not_found_error_with_message(self) -> None:
        """MilestoneNotFoundError should accept and preserve message."""
        from ktrdr.cli.kinfra.errors import MilestoneNotFoundError

        error = MilestoneNotFoundError("M4_impl.md not found")
        assert "M4" in str(error)
        assert "not found" in str(error)

    def test_sandbox_start_error_with_message(self) -> None:
        """SandboxStartError should accept and preserve message."""
        from ktrdr.cli.kinfra.errors import SandboxStartError

        error = SandboxStartError("docker compose up failed with exit code 1")
        assert "docker" in str(error).lower()
        assert "failed" in str(error)

    def test_invalid_operation_error_with_message(self) -> None:
        """InvalidOperationError should accept and preserve message."""
        from ktrdr.cli.kinfra.errors import InvalidOperationError

        error = InvalidOperationError("Cannot run 'done' on spec worktree")
        assert "done" in str(error)
        assert "spec" in str(error)


class TestErrorsCanBeRaised:
    """Tests that errors can be raised and caught."""

    def test_can_catch_all_kinfra_errors(self) -> None:
        """Should be able to catch any kinfra error with base class."""
        from ktrdr.cli.kinfra.errors import (
            InvalidOperationError,
            KinfraError,
            MilestoneNotFoundError,
            SandboxStartError,
            SlotClaimedError,
            SlotExhaustedError,
            WorktreeDirtyError,
            WorktreeExistsError,
        )

        errors = [
            WorktreeExistsError("test"),
            WorktreeDirtyError("test"),
            SlotExhaustedError("test"),
            SlotClaimedError("test"),
            MilestoneNotFoundError("test"),
            SandboxStartError("test"),
            InvalidOperationError("test"),
        ]

        for error in errors:
            try:
                raise error
            except KinfraError as e:
                assert str(e) == "test"
