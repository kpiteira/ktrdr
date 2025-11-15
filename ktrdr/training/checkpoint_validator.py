"""
Checkpoint validation utilities.

Validates checkpoint state structure and data types to ensure
checkpoints can be safely restored.
"""

from typing import Any


def validate_checkpoint_state(checkpoint_state: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate checkpoint state structure and types.

    Args:
        checkpoint_state: Checkpoint state dictionary to validate

    Returns:
        Tuple of (is_valid, errors):
            - is_valid: True if checkpoint is valid, False otherwise
            - errors: List of validation error messages

    Validation checks:
        - Required fields present
        - Field types correct
        - Byte fields are actually bytes
    """
    errors = []

    # Required fields and their expected types
    required_fields = {
        "epoch": int,
        "model_state_dict": bytes,
        "optimizer_state_dict": bytes,
        "config": dict,
    }

    # Check required fields
    for field, expected_type in required_fields.items():
        if field not in checkpoint_state:
            errors.append(f"Missing required field: {field}")
        elif not isinstance(checkpoint_state[field], expected_type):
            actual_type = type(checkpoint_state[field]).__name__
            expected_type_name = expected_type.__name__
            errors.append(
                f"Invalid type for field '{field}': "
                f"expected {expected_type_name}, got {actual_type}"
            )

    # Optional fields and their expected types (if present)
    optional_fields = {
        "scheduler_state_dict": (bytes, type(None)),
        "history": list,
        "best_model_state": (bytes, type(None)),
        "best_val_accuracy": (int, float),
        "early_stopping_state": (dict, type(None)),
        "operation_id": (str, type(None)),
        "checkpoint_type": str,
        "created_at": str,
        "pytorch_version": str,
        "checkpoint_version": str,
    }

    # Check optional fields (if present)
    for field, expected_types in optional_fields.items():
        if field in checkpoint_state:
            if not isinstance(checkpoint_state[field], expected_types):
                actual_type = type(checkpoint_state[field]).__name__
                if isinstance(expected_types, tuple):
                    expected_names = " or ".join(t.__name__ for t in expected_types)
                else:
                    expected_names = expected_types.__name__
                errors.append(
                    f"Invalid type for field '{field}': "
                    f"expected {expected_names}, got {actual_type}"
                )

    is_valid = len(errors) == 0
    return is_valid, errors
