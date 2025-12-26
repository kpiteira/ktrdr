"""Tests for Discord notifier module.

Tests cover:
- send_discord_message() posts to webhook URL
- Webhook failures are logged, not raised
- Request timeout prevents blocking
- DiscordEmbed dataclass structure
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


class TestDiscordEmbed:
    """Test the DiscordEmbed dataclass."""

    def test_embed_with_required_fields(self):
        """Should create embed with required fields."""
        from orchestrator.discord_notifier import DiscordEmbed

        embed = DiscordEmbed(
            title="Test Title",
            description="Test Description",
            color=0x00FF00,
        )

        assert embed.title == "Test Title"
        assert embed.description == "Test Description"
        assert embed.color == 0x00FF00
        assert embed.fields is None
        assert embed.timestamp is None

    def test_embed_with_all_fields(self):
        """Should create embed with all optional fields."""
        from orchestrator.discord_notifier import DiscordEmbed

        embed = DiscordEmbed(
            title="Test Title",
            description="Test Description",
            color=0x00FF00,
            fields=[{"name": "Field1", "value": "Value1", "inline": True}],
            timestamp="2024-01-01T00:00:00Z",
        )

        assert embed.title == "Test Title"
        assert embed.fields == [{"name": "Field1", "value": "Value1", "inline": True}]
        assert embed.timestamp == "2024-01-01T00:00:00Z"

    def test_embed_to_dict(self):
        """Should convert embed to dict for Discord API."""
        from orchestrator.discord_notifier import DiscordEmbed

        embed = DiscordEmbed(
            title="Test",
            description="Desc",
            color=0x3498DB,
        )

        embed_dict = embed.to_dict()

        assert embed_dict["title"] == "Test"
        assert embed_dict["description"] == "Desc"
        assert embed_dict["color"] == 0x3498DB
        # Optional fields should not be included if None
        assert "fields" not in embed_dict
        assert "timestamp" not in embed_dict

    def test_embed_to_dict_with_all_fields(self):
        """Should include all fields in dict when set."""
        from orchestrator.discord_notifier import DiscordEmbed

        embed = DiscordEmbed(
            title="Test",
            description="Desc",
            color=0x3498DB,
            fields=[{"name": "F", "value": "V", "inline": False}],
            timestamp="2024-01-01T00:00:00Z",
        )

        embed_dict = embed.to_dict()

        assert embed_dict["fields"] == [{"name": "F", "value": "V", "inline": False}]
        assert embed_dict["timestamp"] == "2024-01-01T00:00:00Z"


class TestSendDiscordMessage:
    """Test the send_discord_message async function."""

    @pytest.mark.asyncio
    async def test_posts_to_webhook_url(self):
        """Should POST embed to the webhook URL."""
        from orchestrator.discord_notifier import DiscordEmbed, send_discord_message

        embed = DiscordEmbed(
            title="Test",
            description="Test message",
            color=0x00FF00,
        )

        with patch("orchestrator.discord_notifier.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = MagicMock(status_code=204)
            mock_client_class.return_value = mock_client

            await send_discord_message("https://discord.com/api/webhooks/test", embed)

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://discord.com/api/webhooks/test"
            assert "json" in call_args[1]
            assert "embeds" in call_args[1]["json"]

    @pytest.mark.asyncio
    async def test_embed_included_in_payload(self):
        """Should include embed data in the POST payload."""
        from orchestrator.discord_notifier import DiscordEmbed, send_discord_message

        embed = DiscordEmbed(
            title="My Title",
            description="My Description",
            color=0x2ECC71,
        )

        with patch("orchestrator.discord_notifier.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = MagicMock(status_code=204)
            mock_client_class.return_value = mock_client

            await send_discord_message("https://discord.com/api/webhooks/test", embed)

            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["embeds"][0]["title"] == "My Title"
            assert payload["embeds"][0]["description"] == "My Description"
            assert payload["embeds"][0]["color"] == 0x2ECC71

    @pytest.mark.asyncio
    async def test_uses_5_second_timeout(self):
        """Should use 5 second timeout to prevent blocking."""
        from orchestrator.discord_notifier import DiscordEmbed, send_discord_message

        embed = DiscordEmbed(title="Test", description="Test", color=0x00FF00)

        with patch("orchestrator.discord_notifier.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = MagicMock(status_code=204)
            mock_client_class.return_value = mock_client

            await send_discord_message("https://discord.com/api/webhooks/test", embed)

            # Verify timeout was set to 5 seconds
            mock_client_class.assert_called_once_with(timeout=5.0)

    @pytest.mark.asyncio
    async def test_handles_timeout_gracefully(self):
        """Should log but not raise on timeout."""
        from orchestrator.discord_notifier import DiscordEmbed, send_discord_message

        embed = DiscordEmbed(title="Test", description="Test", color=0x00FF00)

        with patch("orchestrator.discord_notifier.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")
            mock_client_class.return_value = mock_client

            with patch("orchestrator.discord_notifier.logger") as mock_logger:
                # Should not raise
                await send_discord_message("https://discord.com/api/webhooks/test", embed)

                # Should log warning
                mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_handles_connection_error_gracefully(self):
        """Should log but not raise on connection error."""
        from orchestrator.discord_notifier import DiscordEmbed, send_discord_message

        embed = DiscordEmbed(title="Test", description="Test", color=0x00FF00)

        with patch("orchestrator.discord_notifier.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = httpx.ConnectError("Connection failed")
            mock_client_class.return_value = mock_client

            with patch("orchestrator.discord_notifier.logger") as mock_logger:
                # Should not raise
                await send_discord_message("https://discord.com/api/webhooks/test", embed)

                # Should log warning
                mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_handles_http_error_response(self):
        """Should log but not raise on 4xx/5xx responses."""
        from orchestrator.discord_notifier import DiscordEmbed, send_discord_message

        embed = DiscordEmbed(title="Test", description="Test", color=0x00FF00)

        with patch("orchestrator.discord_notifier.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            # Simulate HTTP 400 error
            mock_response = MagicMock(status_code=400, text="Bad Request")
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with patch("orchestrator.discord_notifier.logger") as mock_logger:
                # Should not raise
                await send_discord_message("https://discord.com/api/webhooks/test", embed)

                # Should log warning for non-2xx response
                mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_success_with_204_no_content(self):
        """Should succeed silently with 204 response (Discord's success)."""
        from orchestrator.discord_notifier import DiscordEmbed, send_discord_message

        embed = DiscordEmbed(title="Test", description="Test", color=0x00FF00)

        with patch("orchestrator.discord_notifier.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = MagicMock(status_code=204)
            mock_client_class.return_value = mock_client

            with patch("orchestrator.discord_notifier.logger") as mock_logger:
                await send_discord_message("https://discord.com/api/webhooks/test", embed)

                # Should not log warning on success
                mock_logger.warning.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_generic_exception(self):
        """Should handle any unexpected exception gracefully."""
        from orchestrator.discord_notifier import DiscordEmbed, send_discord_message

        embed = DiscordEmbed(title="Test", description="Test", color=0x00FF00)

        with patch("orchestrator.discord_notifier.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = Exception("Unexpected error")
            mock_client_class.return_value = mock_client

            with patch("orchestrator.discord_notifier.logger") as mock_logger:
                # Should not raise
                await send_discord_message("https://discord.com/api/webhooks/test", embed)

                # Should log warning
                mock_logger.warning.assert_called()


class TestFormatMilestoneStarted:
    """Test the format_milestone_started formatter."""

    def test_returns_discord_embed(self):
        """Should return a DiscordEmbed instance."""
        from orchestrator.discord_notifier import DiscordEmbed, format_milestone_started

        result = format_milestone_started("M1", 5)

        assert isinstance(result, DiscordEmbed)

    def test_uses_started_color(self):
        """Should use the blue 'started' color."""
        from orchestrator.discord_notifier import COLORS, format_milestone_started

        result = format_milestone_started("M1", 5)

        assert result.color == COLORS["started"]

    def test_includes_milestone_id_in_title(self):
        """Should include milestone ID in the title."""
        from orchestrator.discord_notifier import format_milestone_started

        result = format_milestone_started("M1-discord-notifications", 3)

        assert "M1-discord-notifications" in result.title

    def test_includes_task_count_in_description(self):
        """Should mention total task count in description."""
        from orchestrator.discord_notifier import format_milestone_started

        result = format_milestone_started("M1", 7)

        assert "7" in result.description


class TestFormatTaskCompleted:
    """Test the format_task_completed formatter."""

    def test_returns_discord_embed(self):
        """Should return a DiscordEmbed instance."""
        from orchestrator.discord_notifier import DiscordEmbed, format_task_completed

        result = format_task_completed("1.1", "Add config", 120.5, 0.05)

        assert isinstance(result, DiscordEmbed)

    def test_uses_completed_color(self):
        """Should use the green 'completed' color."""
        from orchestrator.discord_notifier import COLORS, format_task_completed

        result = format_task_completed("1.1", "Add config", 120.5, 0.05)

        assert result.color == COLORS["completed"]

    def test_includes_task_id_and_title(self):
        """Should include task ID and title."""
        from orchestrator.discord_notifier import format_task_completed

        result = format_task_completed("2.3", "Implement feature X", 60.0, 0.10)

        assert "2.3" in result.title or "2.3" in result.description
        assert "Implement feature X" in result.title or "Implement feature X" in result.description

    def test_includes_duration_and_cost(self):
        """Should include duration and cost information."""
        from orchestrator.discord_notifier import format_task_completed

        result = format_task_completed("1.1", "Test task", 300.0, 0.25)

        # Duration should be shown (300s = 5m)
        full_text = result.description + str(result.fields or "")
        assert "5" in full_text or "300" in full_text  # Either 5m or 300s
        # Cost should be shown
        assert "0.25" in full_text


class TestFormatTaskFailed:
    """Test the format_task_failed formatter."""

    def test_returns_discord_embed(self):
        """Should return a DiscordEmbed instance."""
        from orchestrator.discord_notifier import DiscordEmbed, format_task_failed

        result = format_task_failed("1.2", "Config task", "Connection refused")

        assert isinstance(result, DiscordEmbed)

    def test_uses_failed_color(self):
        """Should use the red 'failed' color."""
        from orchestrator.discord_notifier import COLORS, format_task_failed

        result = format_task_failed("1.2", "Config task", "Error message")

        assert result.color == COLORS["failed"]

    def test_includes_task_id_and_title(self):
        """Should include task ID and title."""
        from orchestrator.discord_notifier import format_task_failed

        result = format_task_failed("3.1", "Broken task", "Some error")

        assert "3.1" in result.title or "3.1" in result.description
        assert "Broken task" in result.title or "Broken task" in result.description

    def test_includes_error_message(self):
        """Should include the error message."""
        from orchestrator.discord_notifier import format_task_failed

        result = format_task_failed("1.1", "Task", "FileNotFoundError: config.yaml")

        assert "FileNotFoundError" in result.description


class TestFormatEscalationNeeded:
    """Test the format_escalation_needed formatter."""

    def test_returns_discord_embed(self):
        """Should return a DiscordEmbed instance."""
        from orchestrator.discord_notifier import DiscordEmbed, format_escalation_needed

        result = format_escalation_needed(
            "1.3", "Feature task", "Which approach?", ["A", "B"]
        )

        assert isinstance(result, DiscordEmbed)

    def test_uses_escalation_color(self):
        """Should use the orange 'escalation' color."""
        from orchestrator.discord_notifier import COLORS, format_escalation_needed

        result = format_escalation_needed("1.3", "Task", "Question?", None)

        assert result.color == COLORS["escalation"]

    def test_includes_task_info(self):
        """Should include task ID and title."""
        from orchestrator.discord_notifier import format_escalation_needed

        result = format_escalation_needed(
            "2.1", "Important task", "What do?", None
        )

        assert "2.1" in result.title or "2.1" in result.description
        assert "Important task" in result.title or "Important task" in result.description

    def test_includes_question(self):
        """Should include the question in description."""
        from orchestrator.discord_notifier import format_escalation_needed

        result = format_escalation_needed(
            "1.1", "Task", "Should I use approach A or B?", None
        )

        assert "Should I use approach A or B?" in result.description

    def test_includes_options_when_provided(self):
        """Should list options when provided."""
        from orchestrator.discord_notifier import format_escalation_needed

        result = format_escalation_needed(
            "1.1", "Task", "Which one?", ["Option A", "Option B", "Option C"]
        )

        assert "Option A" in result.description
        assert "Option B" in result.description
        assert "Option C" in result.description

    def test_works_without_options(self):
        """Should work when options is None."""
        from orchestrator.discord_notifier import format_escalation_needed

        result = format_escalation_needed(
            "1.1", "Task", "Open ended question?", None
        )

        assert result.description  # Has content
        assert "Open ended question?" in result.description


class TestFormatMilestoneCompleted:
    """Test the format_milestone_completed formatter."""

    def test_returns_discord_embed(self):
        """Should return a DiscordEmbed instance."""
        from orchestrator.discord_notifier import (
            DiscordEmbed,
            format_milestone_completed,
        )

        result = format_milestone_completed("M1", 5, 5, 1.50, 3600.0)

        assert isinstance(result, DiscordEmbed)

    def test_uses_milestone_completed_color(self):
        """Should use the purple 'milestone_completed' color."""
        from orchestrator.discord_notifier import COLORS, format_milestone_completed

        result = format_milestone_completed("M1", 5, 5, 1.50, 3600.0)

        assert result.color == COLORS["milestone_completed"]

    def test_includes_milestone_id(self):
        """Should include milestone ID."""
        from orchestrator.discord_notifier import format_milestone_completed

        result = format_milestone_completed("discord-notifications", 3, 3, 0.50, 1800.0)

        assert "discord-notifications" in result.title

    def test_includes_completion_stats(self):
        """Should include completed/total count."""
        from orchestrator.discord_notifier import format_milestone_completed

        result = format_milestone_completed("M1", 4, 5, 1.00, 2400.0)

        full_text = result.description + str(result.fields or "")
        assert "4" in full_text
        assert "5" in full_text

    def test_includes_cost_and_duration(self):
        """Should include cost and duration."""
        from orchestrator.discord_notifier import format_milestone_completed

        result = format_milestone_completed("M1", 5, 5, 2.75, 7200.0)

        full_text = result.description + str(result.fields or "")
        # Cost should be shown
        assert "2.75" in full_text
        # Duration (7200s = 2h) should be shown
        assert "2" in full_text or "7200" in full_text


class TestFormatTestNotification:
    """Test the format_test_notification formatter."""

    def test_returns_discord_embed(self):
        """Should return a DiscordEmbed instance."""
        from orchestrator.discord_notifier import DiscordEmbed, format_test_notification

        result = format_test_notification()

        assert isinstance(result, DiscordEmbed)

    def test_uses_teal_color(self):
        """Should use teal color (0x1ABC9C)."""
        from orchestrator.discord_notifier import format_test_notification

        result = format_test_notification()

        assert result.color == 0x1ABC9C

    def test_has_test_notification_title(self):
        """Should have test notification title."""
        from orchestrator.discord_notifier import format_test_notification

        result = format_test_notification()

        assert "Test" in result.title or "test" in result.title.lower()

    def test_has_success_description(self):
        """Should indicate webhook is configured correctly."""
        from orchestrator.discord_notifier import format_test_notification

        result = format_test_notification()

        assert "configured" in result.description.lower() or "working" in result.description.lower()

    def test_includes_timestamp_and_hostname(self):
        """Should include timestamp and hostname fields."""
        from orchestrator.discord_notifier import format_test_notification

        result = format_test_notification()

        assert result.fields is not None
        field_names = [f["name"] for f in result.fields]
        assert "Sent at" in field_names
        assert "From" in field_names


class TestTextTruncation:
    """Test that long text is truncated appropriately."""

    def test_long_error_message_truncated(self):
        """Should truncate very long error messages."""
        from orchestrator.discord_notifier import format_task_failed

        long_error = "A" * 5000  # Exceeds Discord's 4096 limit
        result = format_task_failed("1.1", "Task", long_error)

        # Description should be under Discord limit
        assert len(result.description) <= 4096

    def test_long_question_truncated(self):
        """Should truncate very long questions in escalation."""
        from orchestrator.discord_notifier import format_escalation_needed

        long_question = "Q" * 5000
        result = format_escalation_needed("1.1", "Task", long_question, None)

        assert len(result.description) <= 4096

    def test_truncation_adds_indicator(self):
        """Should add truncation indicator when text is cut."""
        from orchestrator.discord_notifier import format_task_failed

        long_error = "E" * 5000
        result = format_task_failed("1.1", "Task", long_error)

        # Should indicate truncation
        assert "..." in result.description or "truncated" in result.description.lower()
