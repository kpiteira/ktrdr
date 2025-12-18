"""macOS notification helpers for orchestrator events.

Provides notification functionality for alerting the user when
milestones complete, need input, or encounter errors.
"""

import platform
import subprocess


def send_notification(title: str, message: str, sound: bool = True) -> None:
    """Send a macOS notification.

    Uses osascript to display a notification via macOS notification center.
    Silently does nothing on non-macOS platforms.

    Args:
        title: Notification title (bold text)
        message: Notification body text
        sound: Whether to play the default notification sound (default True)
    """
    if platform.system() != "Darwin":
        return  # Only works on macOS

    # Build AppleScript for notification
    script = f'display notification "{message}" with title "{title}"'
    if sound:
        script += ' sound name "default"'

    subprocess.run(["osascript", "-e", script], check=False)
