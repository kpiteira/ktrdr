"""Tests for AgentGateSettings."""

import pytest

from ktrdr.config import clear_settings_cache


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear settings cache before each test."""
    clear_settings_cache()
    yield
    clear_settings_cache()


class TestAgentGateSettingsDefaults:
    """Test AgentGateSettings default values."""

    def test_default_mode(self):
        """Mode should default to simulation."""
        from ktrdr.config.settings import get_agent_gate_settings

        settings = get_agent_gate_settings()
        assert settings.mode == "simulation"

    def test_default_dry_run(self):
        """Dry run should default to True (safe default)."""
        from ktrdr.config.settings import get_agent_gate_settings

        settings = get_agent_gate_settings()
        assert settings.dry_run is True

    def test_default_confirmation_required(self):
        """Confirmation required should default to True for safety."""
        from ktrdr.config.settings import get_agent_gate_settings

        settings = get_agent_gate_settings()
        assert settings.confirmation_required is True

    def test_default_max_position_size(self):
        """Max position size should default to 0 (no limit)."""
        from ktrdr.config.settings import get_agent_gate_settings

        settings = get_agent_gate_settings()
        assert settings.max_position_size == 0

    def test_default_max_daily_trades(self):
        """Max daily trades should default to 0 (no limit)."""
        from ktrdr.config.settings import get_agent_gate_settings

        settings = get_agent_gate_settings()
        assert settings.max_daily_trades == 0


class TestAgentGateSettingsEnvVars:
    """Test AgentGateSettings with KTRDR_GATE_* env vars."""

    def test_mode_from_env(self, monkeypatch):
        """Should read mode from KTRDR_GATE_MODE."""
        monkeypatch.setenv("KTRDR_GATE_MODE", "live")

        from ktrdr.config.settings import get_agent_gate_settings

        settings = get_agent_gate_settings()
        assert settings.mode == "live"

    def test_dry_run_from_env_false(self, monkeypatch):
        """Should read dry_run from KTRDR_GATE_DRY_RUN."""
        monkeypatch.setenv("KTRDR_GATE_DRY_RUN", "false")

        from ktrdr.config.settings import get_agent_gate_settings

        settings = get_agent_gate_settings()
        assert settings.dry_run is False

    def test_dry_run_from_env_true(self, monkeypatch):
        """Should read dry_run from KTRDR_GATE_DRY_RUN."""
        monkeypatch.setenv("KTRDR_GATE_DRY_RUN", "true")

        from ktrdr.config.settings import get_agent_gate_settings

        settings = get_agent_gate_settings()
        assert settings.dry_run is True

    def test_confirmation_required_from_env(self, monkeypatch):
        """Should read confirmation_required from KTRDR_GATE_CONFIRMATION_REQUIRED."""
        monkeypatch.setenv("KTRDR_GATE_CONFIRMATION_REQUIRED", "false")

        from ktrdr.config.settings import get_agent_gate_settings

        settings = get_agent_gate_settings()
        assert settings.confirmation_required is False

    def test_max_position_size_from_env(self, monkeypatch):
        """Should read max_position_size from KTRDR_GATE_MAX_POSITION_SIZE."""
        monkeypatch.setenv("KTRDR_GATE_MAX_POSITION_SIZE", "10000")

        from ktrdr.config.settings import get_agent_gate_settings

        settings = get_agent_gate_settings()
        assert settings.max_position_size == 10000

    def test_max_daily_trades_from_env(self, monkeypatch):
        """Should read max_daily_trades from KTRDR_GATE_MAX_DAILY_TRADES."""
        monkeypatch.setenv("KTRDR_GATE_MAX_DAILY_TRADES", "50")

        from ktrdr.config.settings import get_agent_gate_settings

        settings = get_agent_gate_settings()
        assert settings.max_daily_trades == 50


class TestAgentGateSettingsValidation:
    """Test AgentGateSettings validation."""

    def test_mode_must_be_valid(self, monkeypatch):
        """Mode must be simulation or live."""
        monkeypatch.setenv("KTRDR_GATE_MODE", "invalid")

        from ktrdr.config.settings import get_agent_gate_settings

        with pytest.raises(Exception) as exc_info:
            get_agent_gate_settings()
        assert "simulation" in str(exc_info.value) or "live" in str(exc_info.value)

    def test_max_position_size_cannot_be_negative(self, monkeypatch):
        """Max position size must be >= 0."""
        monkeypatch.setenv("KTRDR_GATE_MAX_POSITION_SIZE", "-100")

        from ktrdr.config.settings import get_agent_gate_settings

        with pytest.raises(Exception) as exc_info:
            get_agent_gate_settings()
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_max_daily_trades_cannot_be_negative(self, monkeypatch):
        """Max daily trades must be >= 0."""
        monkeypatch.setenv("KTRDR_GATE_MAX_DAILY_TRADES", "-10")

        from ktrdr.config.settings import get_agent_gate_settings

        with pytest.raises(Exception) as exc_info:
            get_agent_gate_settings()
        assert "greater than or equal to 0" in str(exc_info.value)


class TestAgentGateSettingsHelpers:
    """Test AgentGateSettings helper methods."""

    def test_is_live_mode_false(self):
        """is_live_mode should return False for simulation."""
        from ktrdr.config.settings import get_agent_gate_settings

        settings = get_agent_gate_settings()
        assert settings.is_live_mode() is False

    def test_is_live_mode_true(self, monkeypatch):
        """is_live_mode should return True for live mode."""
        monkeypatch.setenv("KTRDR_GATE_MODE", "live")

        from ktrdr.config.settings import get_agent_gate_settings

        settings = get_agent_gate_settings()
        assert settings.is_live_mode() is True

    def test_can_execute_trade_false_dry_run(self):
        """can_execute_trade should return False if dry_run is True."""
        from ktrdr.config.settings import get_agent_gate_settings

        settings = get_agent_gate_settings()
        assert settings.can_execute_trade() is False

    def test_can_execute_trade_true(self, monkeypatch):
        """can_execute_trade should return True if not dry_run and live mode."""
        monkeypatch.setenv("KTRDR_GATE_MODE", "live")
        monkeypatch.setenv("KTRDR_GATE_DRY_RUN", "false")

        from ktrdr.config.settings import get_agent_gate_settings

        settings = get_agent_gate_settings()
        assert settings.can_execute_trade() is True


class TestAgentGateSettingsGetter:
    """Test get_agent_gate_settings() caching behavior."""

    def test_getter_returns_same_instance(self):
        """get_agent_gate_settings() should return cached instance."""
        from ktrdr.config.settings import get_agent_gate_settings

        settings1 = get_agent_gate_settings()
        settings2 = get_agent_gate_settings()
        assert settings1 is settings2

    def test_cache_clear_returns_new_instance(self):
        """clear_settings_cache() should clear the agent gate settings cache."""
        from ktrdr.config.settings import get_agent_gate_settings

        settings1 = get_agent_gate_settings()
        clear_settings_cache()
        settings2 = get_agent_gate_settings()
        assert settings1 is not settings2
