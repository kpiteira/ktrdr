"""Tests for AgentSettings."""

import pytest

from ktrdr.config import clear_settings_cache


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear settings cache before each test."""
    clear_settings_cache()
    yield
    clear_settings_cache()


class TestAgentSettingsDefaults:
    """Test AgentSettings default values."""

    def test_default_poll_interval(self):
        """Poll interval should default to 5 seconds."""
        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.poll_interval == 5

    def test_default_model(self, monkeypatch):
        """Model should default to claude-sonnet-4-20250514.

        Note: conftest.py sets AGENT_MODEL=haiku globally, so we need to
        explicitly remove it to test the true default.
        """
        monkeypatch.delenv("AGENT_MODEL", raising=False)

        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.model == "claude-sonnet-4-20250514"

    def test_default_max_tokens(self):
        """Max tokens should default to 4096."""
        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.max_tokens == 4096

    def test_default_timeout_seconds(self):
        """Timeout should default to 300 seconds."""
        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.timeout_seconds == 300

    def test_default_max_iterations(self):
        """Max iterations should default to 10."""
        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.max_iterations == 10

    def test_default_max_input_tokens(self):
        """Max input tokens should default to 50000."""
        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.max_input_tokens == 50000

    def test_default_daily_budget(self):
        """Daily budget should default to 5.0."""
        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.daily_budget == 5.0

    def test_default_budget_dir(self):
        """Budget dir should default to data/budget."""
        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.budget_dir == "data/budget"

    def test_default_max_concurrent_researches(self):
        """Max concurrent researches should default to 0 (unlimited)."""
        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.max_concurrent_researches == 0

    def test_default_concurrency_buffer(self):
        """Concurrency buffer should default to 1."""
        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.concurrency_buffer == 1

    def test_default_training_dates_none(self):
        """Training dates should default to None."""
        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.training_start_date is None
        assert settings.training_end_date is None

    def test_default_backtest_dates_none(self):
        """Backtest dates should default to None."""
        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.backtest_start_date is None
        assert settings.backtest_end_date is None


class TestAgentSettingsEnvVars:
    """Test AgentSettings with new KTRDR_AGENT_* env vars."""

    def test_poll_interval_from_env(self, monkeypatch):
        """Should read poll_interval from KTRDR_AGENT_POLL_INTERVAL."""
        monkeypatch.setenv("KTRDR_AGENT_POLL_INTERVAL", "10")

        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.poll_interval == 10

    def test_model_from_env(self, monkeypatch):
        """Should read model from KTRDR_AGENT_MODEL."""
        monkeypatch.setenv("KTRDR_AGENT_MODEL", "claude-opus-4-20250514")

        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.model == "claude-opus-4-20250514"

    def test_max_tokens_from_env(self, monkeypatch):
        """Should read max_tokens from KTRDR_AGENT_MAX_TOKENS."""
        monkeypatch.setenv("KTRDR_AGENT_MAX_TOKENS", "8192")

        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.max_tokens == 8192

    def test_daily_budget_from_env(self, monkeypatch):
        """Should read daily_budget from KTRDR_AGENT_DAILY_BUDGET."""
        monkeypatch.setenv("KTRDR_AGENT_DAILY_BUDGET", "10.5")

        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.daily_budget == 10.5


class TestAgentSettingsDeprecatedNames:
    """Test AgentSettings with deprecated AGENT_* env vars."""

    def test_deprecated_poll_interval(self, monkeypatch):
        """Deprecated AGENT_POLL_INTERVAL should still work."""
        monkeypatch.setenv("AGENT_POLL_INTERVAL", "15")

        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.poll_interval == 15

    def test_deprecated_model(self, monkeypatch):
        """Deprecated AGENT_MODEL should still work."""
        monkeypatch.setenv("AGENT_MODEL", "haiku")

        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.model == "haiku"

    def test_deprecated_daily_budget(self, monkeypatch):
        """Deprecated AGENT_DAILY_BUDGET should still work."""
        monkeypatch.setenv("AGENT_DAILY_BUDGET", "20.0")

        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.daily_budget == 20.0


class TestAgentSettingsPrecedence:
    """Test that new names take precedence over deprecated names."""

    def test_new_name_takes_precedence(self, monkeypatch):
        """KTRDR_AGENT_* should take precedence over AGENT_*."""
        monkeypatch.setenv("KTRDR_AGENT_POLL_INTERVAL", "100")
        monkeypatch.setenv("AGENT_POLL_INTERVAL", "200")

        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.poll_interval == 100


class TestAgentSettingsValidation:
    """Test AgentSettings validation."""

    def test_poll_interval_must_be_positive(self, monkeypatch):
        """Poll interval must be > 0."""
        monkeypatch.setenv("KTRDR_AGENT_POLL_INTERVAL", "0")

        from ktrdr.config.settings import get_agent_settings

        with pytest.raises(Exception) as exc_info:
            get_agent_settings()
        assert "greater than 0" in str(exc_info.value)

    def test_max_tokens_must_be_positive(self, monkeypatch):
        """Max tokens must be > 0."""
        monkeypatch.setenv("KTRDR_AGENT_MAX_TOKENS", "0")

        from ktrdr.config.settings import get_agent_settings

        with pytest.raises(Exception) as exc_info:
            get_agent_settings()
        assert "greater than 0" in str(exc_info.value)

    def test_daily_budget_can_be_zero(self, monkeypatch):
        """Daily budget >= 0 (0 means disabled)."""
        monkeypatch.setenv("KTRDR_AGENT_DAILY_BUDGET", "0")

        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.daily_budget == 0

    def test_max_concurrent_researches_can_be_zero(self, monkeypatch):
        """Max concurrent researches >= 0 (0 means unlimited)."""
        monkeypatch.setenv("KTRDR_AGENT_MAX_CONCURRENT_RESEARCHES", "0")

        from ktrdr.config.settings import get_agent_settings

        settings = get_agent_settings()
        assert settings.max_concurrent_researches == 0


class TestAgentSettingsGetter:
    """Test get_agent_settings() caching behavior."""

    def test_getter_returns_same_instance(self):
        """get_agent_settings() should return cached instance."""
        from ktrdr.config.settings import get_agent_settings

        settings1 = get_agent_settings()
        settings2 = get_agent_settings()
        assert settings1 is settings2

    def test_cache_clear_returns_new_instance(self):
        """clear_settings_cache() should clear the agent settings cache."""
        from ktrdr.config.settings import get_agent_settings

        settings1 = get_agent_settings()
        clear_settings_cache()
        settings2 = get_agent_settings()
        assert settings1 is not settings2
