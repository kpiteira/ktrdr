"""Discord webhook notifier for orchestrator events.

Provides functionality for sending rich embed notifications to Discord
webhooks. All webhook failures are logged but not raised, ensuring that
notification issues don't block orchestrator execution.
"""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Color scheme for Discord embeds
COLORS = {
    "started": 0x3498DB,  # Blue
    "completed": 0x2ECC71,  # Green
    "failed": 0xE74C3C,  # Red
    "escalation": 0xF39C12,  # Orange
    "milestone_completed": 0x9B59B6,  # Purple
}


@dataclass
class DiscordEmbed:
    """Discord embed message structure.

    Represents the embed portion of a Discord webhook message.
    Discord embeds support rich formatting including title, description,
    color, fields, and timestamps.

    Attributes:
        title: Bold title text at the top of the embed
        description: Main body text of the embed (max 4096 chars)
        color: Integer color value (hex, e.g., 0x00FF00 for green)
        fields: Optional list of field dicts with name, value, inline keys
        timestamp: Optional ISO format timestamp string
    """

    title: str
    description: str
    color: int
    fields: list[dict] | None = None
    timestamp: str | None = None

    def to_dict(self) -> dict:
        """Convert embed to Discord API format.

        Returns dict suitable for the 'embeds' array in webhook payload.
        Only includes optional fields if they are set.
        """
        result = {
            "title": self.title,
            "description": self.description,
            "color": self.color,
        }

        if self.fields is not None:
            result["fields"] = self.fields

        if self.timestamp is not None:
            result["timestamp"] = self.timestamp

        return result


async def send_discord_message(webhook_url: str, embed: DiscordEmbed) -> None:
    """Send a Discord webhook message with an embed.

    Posts a message to the specified Discord webhook URL. Uses a 5 second
    timeout to prevent blocking. All errors (network, timeout, HTTP errors)
    are logged but not raised.

    Args:
        webhook_url: Discord webhook URL
        embed: DiscordEmbed to send

    Note:
        Discord webhooks return 204 No Content on success.
        All failures are logged as warnings but not raised.
    """
    payload = {"embeds": [embed.to_dict()]}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(webhook_url, json=payload)

            if response.status_code >= 400:
                logger.warning(
                    f"Discord webhook returned {response.status_code}: {response.text}"
                )
    except httpx.TimeoutException:
        logger.warning("Discord webhook request timed out")
    except httpx.ConnectError:
        logger.warning("Failed to connect to Discord webhook")
    except Exception as e:
        logger.warning(f"Discord webhook error: {e}")


# Maximum description length for Discord embeds
MAX_DESCRIPTION_LENGTH = 4096
TRUNCATION_SUFFIX = "... [truncated]"


def _truncate_text(text: str, max_length: int) -> str:
    """Truncate text to max_length, adding a truncation indicator if needed.

    Args:
        text: The text to potentially truncate
        max_length: Maximum allowed length

    Returns:
        Original text if under limit, otherwise truncated with indicator
    """
    if len(text) <= max_length:
        return text
    # Leave room for the truncation suffix
    return text[: max_length - len(TRUNCATION_SUFFIX)] + TRUNCATION_SUFFIX


def _format_duration(seconds: float) -> str:
    """Format duration in human-readable form.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "2m 30s" or "1h 15m"
    """
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s" if secs > 0 else f"{minutes}m"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"


def format_milestone_started(milestone_id: str, total_tasks: int) -> DiscordEmbed:
    """Format a milestone started event as a Discord embed.

    Args:
        milestone_id: Identifier for the milestone
        total_tasks: Total number of tasks in the milestone

    Returns:
        DiscordEmbed ready to send to Discord
    """
    return DiscordEmbed(
        title=f"🚀 Milestone Started: {milestone_id}",
        description=f"Starting execution of {total_tasks} tasks.",
        color=COLORS["started"],
    )


def format_task_completed(
    task_id: str, title: str, duration_s: float, cost_usd: float
) -> DiscordEmbed:
    """Format a task completed event as a Discord embed.

    Args:
        task_id: Task identifier (e.g., "1.1", "2.3")
        title: Task title/description
        duration_s: How long the task took in seconds
        cost_usd: Estimated cost in USD

    Returns:
        DiscordEmbed ready to send to Discord
    """
    return DiscordEmbed(
        title=f"✅ Task {task_id}: {title}",
        description=f"Completed in {_format_duration(duration_s)}",
        color=COLORS["completed"],
        fields=[
            {"name": "Duration", "value": _format_duration(duration_s), "inline": True},
            {"name": "Cost", "value": f"${cost_usd:.2f}", "inline": True},
        ],
    )


def format_task_failed(task_id: str, title: str, error: str) -> DiscordEmbed:
    """Format a task failed event as a Discord embed.

    Args:
        task_id: Task identifier (e.g., "1.1", "2.3")
        title: Task title/description
        error: Error message or traceback

    Returns:
        DiscordEmbed ready to send to Discord
    """
    # Build description with error, respecting length limits
    description_parts = [
        f"Task {task_id}: {title}",
        "",
        "**Error:**",
        error,
    ]
    full_description = "\n".join(description_parts)
    truncated_description = _truncate_text(full_description, MAX_DESCRIPTION_LENGTH)

    return DiscordEmbed(
        title="❌ Task Failed",
        description=truncated_description,
        color=COLORS["failed"],
    )


def format_escalation_needed(
    task_id: str, title: str, question: str, options: list[str] | None
) -> DiscordEmbed:
    """Format an escalation needed event as a Discord embed.

    Args:
        task_id: Task identifier (e.g., "1.1", "2.3")
        title: Task title/description
        question: The question Claude is asking
        options: Optional list of answer options

    Returns:
        DiscordEmbed ready to send to Discord
    """
    description_parts = [
        f"Task {task_id}: {title}",
        "",
        "**Claude needs input:**",
        f'"{question}"',
    ]

    if options:
        description_parts.append("")
        description_parts.append("**Options:**")
        for opt in options:
            description_parts.append(f"• {opt}")

    full_description = "\n".join(description_parts)
    truncated_description = _truncate_text(full_description, MAX_DESCRIPTION_LENGTH)

    return DiscordEmbed(
        title="🚨 Escalation Needed",
        description=truncated_description,
        color=COLORS["escalation"],
    )


def format_milestone_completed(
    milestone_id: str, completed: int, total: int, cost_usd: float, duration_s: float
) -> DiscordEmbed:
    """Format a milestone completed event as a Discord embed.

    Args:
        milestone_id: Identifier for the milestone
        completed: Number of tasks completed
        total: Total number of tasks
        cost_usd: Total cost in USD
        duration_s: Total duration in seconds

    Returns:
        DiscordEmbed ready to send to Discord
    """
    return DiscordEmbed(
        title=f"🎉 Milestone Complete: {milestone_id}",
        description=f"Completed {completed}/{total} tasks in {_format_duration(duration_s)}.",
        color=COLORS["milestone_completed"],
        fields=[
            {"name": "Tasks", "value": f"{completed}/{total}", "inline": True},
            {"name": "Duration", "value": _format_duration(duration_s), "inline": True},
            {"name": "Total Cost", "value": f"${cost_usd:.2f}", "inline": True},
        ],
    )
