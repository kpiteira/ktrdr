"""
Checkpoint type definitions.

This module defines the CheckpointType enum used to classify
checkpoint triggers and reasons for checkpoint creation.
"""

from enum import Enum


class CheckpointType(str, Enum):
    """
    Types of checkpoints that can be created.

    Each type represents a different trigger or reason for creating a checkpoint:

    - TIMER: Time-based checkpoint (created every N seconds based on policy)
    - FORCE: Force checkpoint (created every N epochs/bars as safety net)
    - CANCELLATION: User cancelled operation (checkpoint saves current state before cancellation)
    - SHUTDOWN: Worker graceful shutdown (checkpoint saves state before worker exits)
    - FAILURE: Operation failed (checkpoint saves state at failure point)

    Usage:
        >>> checkpoint_type = CheckpointType.CANCELLATION
        >>> print(checkpoint_type.value)
        'CANCELLATION'

        >>> if checkpoint_type == CheckpointType.CANCELLATION:
        ...     print("User cancelled the operation")
    """

    TIMER = "TIMER"
    FORCE = "FORCE"
    CANCELLATION = "CANCELLATION"
    SHUTDOWN = "SHUTDOWN"
    FAILURE = "FAILURE"
