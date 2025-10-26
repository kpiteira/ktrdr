"""Unit tests for TrainingAdapter deprecation warnings."""

import asyncio
import unittest
import warnings
from unittest.mock import AsyncMock, patch

from ktrdr.training.training_adapter import TrainingAdapter


class TestTrainingAdapterDeprecations(unittest.TestCase):
    """Test TrainingAdapter deprecation warnings."""

    def test_get_training_status_deprecation_warning(self):
        """Test that get_training_status raises a DeprecationWarning."""
        adapter = TrainingAdapter(use_host_service=True)

        # Mock the HTTP call to prevent actual network request
        with patch.object(
            adapter, "_call_host_service_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = {"status": "running", "progress": 0.5}

            # Verify deprecation warning is raised
            with warnings.catch_warnings(record=True) as w:
                # Cause all warnings to always be triggered
                warnings.simplefilter("always")

                # Call the method
                result = asyncio.run(adapter.get_training_status("test_session_123"))

                # Verify warning was raised
                self.assertEqual(len(w), 1)
                self.assertTrue(issubclass(w[0].category, DeprecationWarning))
                self.assertIn(
                    "Use OperationServiceProxy.get_operation() instead",
                    str(w[0].message),
                )

            # Verify method still works (backward compatibility)
            self.assertEqual(result["status"], "running")
            mock_get.assert_called_once_with("/training/status/test_session_123")

    def test_get_training_status_functionality_preserved(self):
        """Test that get_training_status still works correctly despite deprecation."""
        adapter = TrainingAdapter(use_host_service=True)

        # Mock the HTTP call
        with patch.object(
            adapter, "_call_host_service_get", new_callable=AsyncMock
        ) as mock_get:
            expected_response = {
                "status": "completed",
                "progress": 1.0,
                "results": {"accuracy": 0.95},
            }
            mock_get.return_value = expected_response

            # Suppress the deprecation warning for this test
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                result = asyncio.run(adapter.get_training_status("session_456"))

            # Verify functionality is preserved
            self.assertEqual(result, expected_response)
            mock_get.assert_called_once_with("/training/status/session_456")

    def test_get_training_status_warning_message_content(self):
        """Test that deprecation warning contains correct migration guidance."""
        adapter = TrainingAdapter(use_host_service=True)

        # Mock the HTTP call
        with patch.object(
            adapter, "_call_host_service_get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = {"status": "running"}

            # Capture the warning
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                asyncio.run(adapter.get_training_status("session_789"))

                # Verify warning message has migration guidance
                warning_message = str(w[0].message)
                self.assertIn("deprecated", warning_message.lower())
                self.assertIn("OperationServiceProxy", warning_message)


if __name__ == "__main__":
    unittest.main()
