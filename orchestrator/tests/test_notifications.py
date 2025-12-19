"""Tests for notifications module.

These tests verify macOS notification functionality.
"""

from unittest.mock import patch


class TestSendNotification:
    """Test the send_notification function."""

    def test_sends_notification_on_macos(self):
        """Should call osascript on macOS."""
        from orchestrator.notifications import send_notification

        with patch("orchestrator.notifications.platform") as mock_platform:
            mock_platform.system.return_value = "Darwin"

            with patch("orchestrator.notifications.subprocess") as mock_subprocess:
                send_notification("Test Title", "Test Message")

        mock_subprocess.run.assert_called_once()
        call_args = mock_subprocess.run.call_args[0][0]
        assert call_args[0] == "osascript"

    def test_notification_contains_title(self):
        """Notification script should contain the title."""
        from orchestrator.notifications import send_notification

        with patch("orchestrator.notifications.platform") as mock_platform:
            mock_platform.system.return_value = "Darwin"

            with patch("orchestrator.notifications.subprocess") as mock_subprocess:
                send_notification("My Title", "My Message")

        call_args = mock_subprocess.run.call_args[0][0]
        script = call_args[2]  # osascript -e "script"
        assert "My Title" in script

    def test_notification_contains_message(self):
        """Notification script should contain the message."""
        from orchestrator.notifications import send_notification

        with patch("orchestrator.notifications.platform") as mock_platform:
            mock_platform.system.return_value = "Darwin"

            with patch("orchestrator.notifications.subprocess") as mock_subprocess:
                send_notification("My Title", "My Message")

        call_args = mock_subprocess.run.call_args[0][0]
        script = call_args[2]
        assert "My Message" in script

    def test_no_op_on_non_macos(self):
        """Should do nothing on non-macOS platforms."""
        from orchestrator.notifications import send_notification

        with patch("orchestrator.notifications.platform") as mock_platform:
            mock_platform.system.return_value = "Linux"

            with patch("orchestrator.notifications.subprocess") as mock_subprocess:
                send_notification("Title", "Message")

        mock_subprocess.run.assert_not_called()

    def test_no_op_on_windows(self):
        """Should do nothing on Windows."""
        from orchestrator.notifications import send_notification

        with patch("orchestrator.notifications.platform") as mock_platform:
            mock_platform.system.return_value = "Windows"

            with patch("orchestrator.notifications.subprocess") as mock_subprocess:
                send_notification("Title", "Message")

        mock_subprocess.run.assert_not_called()

    def test_sound_enabled_by_default(self):
        """Sound should be enabled by default."""
        from orchestrator.notifications import send_notification

        with patch("orchestrator.notifications.platform") as mock_platform:
            mock_platform.system.return_value = "Darwin"

            with patch("orchestrator.notifications.subprocess") as mock_subprocess:
                send_notification("Title", "Message")

        call_args = mock_subprocess.run.call_args[0][0]
        script = call_args[2]
        assert "sound" in script.lower()

    def test_sound_can_be_disabled(self):
        """Sound can be disabled via parameter."""
        from orchestrator.notifications import send_notification

        with patch("orchestrator.notifications.platform") as mock_platform:
            mock_platform.system.return_value = "Darwin"

            with patch("orchestrator.notifications.subprocess") as mock_subprocess:
                send_notification("Title", "Message", sound=False)

        call_args = mock_subprocess.run.call_args[0][0]
        script = call_args[2]
        assert "sound" not in script.lower()

    def test_subprocess_called_without_check(self):
        """Should use check=False to avoid raising on notification failure."""
        from orchestrator.notifications import send_notification

        with patch("orchestrator.notifications.platform") as mock_platform:
            mock_platform.system.return_value = "Darwin"

            with patch("orchestrator.notifications.subprocess") as mock_subprocess:
                send_notification("Title", "Message")

        call_kwargs = mock_subprocess.run.call_args[1]
        assert call_kwargs.get("check") is False
