"""Tests for orchestrator configuration module.

These tests verify config defaults and environment variable overrides.
"""

import os
from pathlib import Path
from unittest.mock import patch


class TestOrchestratorConfigDefaults:
    """Test that config loads with sensible defaults."""

    def test_sandbox_container_default(self):
        """Default sandbox container should be ktrdr-sandbox."""
        from orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig()
        assert config.sandbox_container == "ktrdr-sandbox"

    def test_workspace_path_default(self):
        """Default workspace path should be /workspace."""
        from orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig()
        assert config.workspace_path == "/workspace"

    def test_max_turns_default(self):
        """Default max turns should be 50."""
        from orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig()
        assert config.max_turns == 50

    def test_task_timeout_default(self):
        """Default task timeout should be 600 seconds."""
        from orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig()
        assert config.task_timeout_seconds == 600

    def test_allowed_tools_default(self):
        """Default allowed tools should include standard tools."""
        from orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig()
        expected_tools = ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]
        assert config.allowed_tools == expected_tools

    def test_otlp_endpoint_default(self):
        """Default OTLP endpoint should be localhost:4317."""
        from orchestrator.config import OrchestratorConfig

        with patch.dict(os.environ, {}, clear=True):
            config = OrchestratorConfig()
            assert config.otlp_endpoint == "http://localhost:4317"

    def test_service_name_default(self):
        """Default service name should be orchestrator."""
        from orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig()
        assert config.service_name == "orchestrator"

    def test_state_dir_default(self):
        """Default state directory should be 'state'."""
        from orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig()
        assert config.state_dir == Path("state")

    def test_discord_webhook_url_default(self):
        """Default discord webhook URL should be None."""
        from orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig()
        assert config.discord_webhook_url is None

    def test_discord_enabled_false_when_no_url(self):
        """discord_enabled should be False when no webhook URL."""
        from orchestrator.config import OrchestratorConfig

        config = OrchestratorConfig()
        assert config.discord_enabled is False


class TestOrchestratorConfigEnvOverrides:
    """Test that environment variables override defaults."""

    def test_max_turns_env_override(self):
        """ORCHESTRATOR_MAX_TURNS should override max_turns."""
        from orchestrator.config import OrchestratorConfig

        with patch.dict(os.environ, {"ORCHESTRATOR_MAX_TURNS": "100"}):
            config = OrchestratorConfig.from_env()
            assert config.max_turns == 100

    def test_task_timeout_env_override(self):
        """ORCHESTRATOR_TASK_TIMEOUT should override task_timeout_seconds."""
        from orchestrator.config import OrchestratorConfig

        with patch.dict(os.environ, {"ORCHESTRATOR_TASK_TIMEOUT": "1200"}):
            config = OrchestratorConfig.from_env()
            assert config.task_timeout_seconds == 1200

    def test_otlp_endpoint_env_override(self):
        """OTLP_ENDPOINT should override otlp_endpoint."""
        from orchestrator.config import OrchestratorConfig

        with patch.dict(os.environ, {"OTLP_ENDPOINT": "http://jaeger:4317"}):
            config = OrchestratorConfig.from_env()
            assert config.otlp_endpoint == "http://jaeger:4317"

    def test_from_env_uses_defaults_when_no_env_vars(self):
        """from_env() should use defaults when env vars are not set."""
        from orchestrator.config import OrchestratorConfig

        with patch.dict(os.environ, {}, clear=True):
            config = OrchestratorConfig.from_env()
            assert config.max_turns == 50
            assert config.task_timeout_seconds == 600
            assert config.otlp_endpoint == "http://localhost:4317"

    def test_discord_webhook_url_env_override(self):
        """DISCORD_WEBHOOK_URL should set discord_webhook_url."""
        from orchestrator.config import OrchestratorConfig

        webhook_url = "https://discord.com/api/webhooks/123/abc"
        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": webhook_url}):
            config = OrchestratorConfig.from_env()
            assert config.discord_webhook_url == webhook_url

    def test_discord_enabled_true_when_url_set(self):
        """discord_enabled should be True when webhook URL is set."""
        from orchestrator.config import OrchestratorConfig

        webhook_url = "https://discord.com/api/webhooks/123/abc"
        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": webhook_url}):
            config = OrchestratorConfig.from_env()
            assert config.discord_enabled is True


class TestOrchestratorConfigTypeHints:
    """Test that all fields have proper type hints."""

    def test_config_has_type_annotations(self):
        """Config class should have type annotations for all fields."""
        from orchestrator.config import OrchestratorConfig

        annotations = OrchestratorConfig.__annotations__
        expected_fields = [
            "sandbox_container",
            "workspace_path",
            "max_turns",
            "task_timeout_seconds",
            "allowed_tools",
            "otlp_endpoint",
            "service_name",
            "state_dir",
        ]
        for field in expected_fields:
            assert field in annotations, f"Missing type annotation for {field}"

    def test_config_is_dataclass(self):
        """Config should be a dataclass."""
        from dataclasses import is_dataclass

        from orchestrator.config import OrchestratorConfig

        assert is_dataclass(OrchestratorConfig)
