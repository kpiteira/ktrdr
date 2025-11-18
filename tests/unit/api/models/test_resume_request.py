"""
Tests for ResumeRequest Pydantic model.

This model is used by workers to receive resume requests from backend.
It contains only operation IDs (no checkpoint data).
"""

import pytest
from pydantic import ValidationError


def test_resume_request_import():
    """Test that ResumeRequest model can be imported."""
    try:
        from ktrdr.api.models.backtesting import ResumeRequest
        assert ResumeRequest is not None
    except ImportError:
        pytest.fail("ResumeRequest model not found in ktrdr.api.models.backtesting")


def test_resume_request_has_required_fields():
    """
    Test ResumeRequest has correct required fields.

    Required fields:
    - task_id: str (new operation ID from backend)
    - original_operation_id: str (operation to resume from)
    """
    from ktrdr.api.models.backtesting import ResumeRequest

    # Valid request
    request = ResumeRequest(
        task_id="new-op-123",
        original_operation_id="original-op-456"
    )

    assert request.task_id == "new-op-123"
    assert request.original_operation_id == "original-op-456"


def test_resume_request_validates_required_fields():
    """
    Test ResumeRequest validates required fields are present.

    Should raise ValidationError if fields missing.
    """
    from ktrdr.api.models.backtesting import ResumeRequest

    # Missing task_id
    with pytest.raises(ValidationError) as exc_info:
        ResumeRequest(original_operation_id="original-op")

    assert "task_id" in str(exc_info.value)

    # Missing original_operation_id
    with pytest.raises(ValidationError) as exc_info:
        ResumeRequest(task_id="new-op")

    assert "original_operation_id" in str(exc_info.value)


def test_resume_request_validates_non_empty_strings():
    """
    Test ResumeRequest validates strings are not empty.

    Should raise ValidationError for empty strings.
    """
    from ktrdr.api.models.backtesting import ResumeRequest

    # Empty task_id
    with pytest.raises(ValidationError) as exc_info:
        ResumeRequest(task_id="", original_operation_id="original-op")

    assert "task_id" in str(exc_info.value).lower()

    # Empty original_operation_id
    with pytest.raises(ValidationError) as exc_info:
        ResumeRequest(task_id="new-op", original_operation_id="")

    assert "original_operation_id" in str(exc_info.value).lower()


def test_resume_request_no_checkpoint_data():
    """
    Test ResumeRequest does NOT contain checkpoint data.

    This verifies minimal payload design - only operation IDs sent over network.
    """
    from ktrdr.api.models.backtesting import ResumeRequest

    request = ResumeRequest(
        task_id="new-op",
        original_operation_id="original-op"
    )

    # Should NOT have checkpoint-related fields
    assert not hasattr(request, "checkpoint_state")
    assert not hasattr(request, "checkpoint_data")
    assert not hasattr(request, "state")
    assert not hasattr(request, "model_state_dict")

    # Only operation IDs
    fields = set(request.model_dump().keys())
    expected_fields = {"task_id", "original_operation_id"}
    assert fields == expected_fields
