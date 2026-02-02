"""Error types for kinfra commands.

These errors provide clear failure modes for worktree and slot operations.
"""


class KinfraError(Exception):
    """Base exception for kinfra commands."""

    pass


class WorktreeExistsError(KinfraError):
    """Worktree already exists."""

    pass


class WorktreeDirtyError(KinfraError):
    """Worktree has uncommitted or unpushed changes."""

    pass


class SlotExhaustedError(KinfraError):
    """All sandbox slots are in use."""

    pass


class SlotClaimedError(KinfraError):
    """Slot is already claimed by another worktree."""

    pass


class MilestoneNotFoundError(KinfraError):
    """Milestone file not found in design folder."""

    pass


class SandboxStartError(KinfraError):
    """Failed to start sandbox containers."""

    pass


class InvalidOperationError(KinfraError):
    """Operation not valid for this worktree type."""

    pass
