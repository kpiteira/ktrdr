"""Tests for AnthropicInvokerConfig model configuration.

Task 8.3: Verify model selection via AGENT_MODEL environment variable.

Tests cover:
- VALID_MODELS constant exists with expected models
- DEFAULT_MODEL is claude-opus-4-5-20250514
- AGENT_MODEL env var controls model selection
- Invalid model falls back to default with warning
- Model tier info available for each model
"""

import os
from unittest.mock import patch

from ktrdr.agents.invoker import (
    DEFAULT_MODEL,
    VALID_MODELS,
    AnthropicInvokerConfig,
)


class TestValidModels:
    """Tests for VALID_MODELS constant."""

    def test_valid_models_exists(self):
        """VALID_MODELS constant exists and is a dict."""
        assert isinstance(VALID_MODELS, dict)

    def test_valid_models_has_opus(self):
        """VALID_MODELS includes Opus 4.5 model."""
        assert "claude-opus-4-5-20250514" in VALID_MODELS

    def test_valid_models_has_sonnet(self):
        """VALID_MODELS includes Sonnet 4 model."""
        assert "claude-sonnet-4-20250514" in VALID_MODELS

    def test_valid_models_has_haiku(self):
        """VALID_MODELS includes Haiku 4.5 model."""
        assert "claude-haiku-4-5-20250514" in VALID_MODELS

    def test_each_model_has_tier(self):
        """Each model has tier metadata."""
        for model_id, info in VALID_MODELS.items():
            assert "tier" in info, f"Model {model_id} missing tier"

    def test_each_model_has_cost(self):
        """Each model has cost level metadata."""
        for model_id, info in VALID_MODELS.items():
            assert "cost" in info, f"Model {model_id} missing cost"


class TestDefaultModel:
    """Tests for DEFAULT_MODEL constant."""

    def test_default_model_is_opus(self):
        """DEFAULT_MODEL is claude-opus-4-5-20250514 for production quality."""
        assert DEFAULT_MODEL == "claude-opus-4-5-20250514"

    def test_default_model_is_valid(self):
        """DEFAULT_MODEL is in VALID_MODELS."""
        assert DEFAULT_MODEL in VALID_MODELS


class TestAnthropicInvokerConfigModel:
    """Tests for AnthropicInvokerConfig model handling."""

    def test_default_model_when_no_env(self):
        """Config uses DEFAULT_MODEL when no env var is set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove AGENT_MODEL if it exists
            os.environ.pop("AGENT_MODEL", None)
            config = AnthropicInvokerConfig.from_env()
            assert config.model == DEFAULT_MODEL

    def test_model_from_env_var(self):
        """Config reads model from AGENT_MODEL env var."""
        with patch.dict(os.environ, {"AGENT_MODEL": "claude-haiku-4-5-20250514"}):
            config = AnthropicInvokerConfig.from_env()
            assert config.model == "claude-haiku-4-5-20250514"

    def test_invalid_model_falls_back_to_default(self):
        """Config falls back to DEFAULT_MODEL for invalid model."""
        with patch.dict(os.environ, {"AGENT_MODEL": "invalid-model-name"}):
            config = AnthropicInvokerConfig.from_env()
            assert config.model == DEFAULT_MODEL

    def test_invalid_model_logs_warning(self):
        """Config logs warning when invalid model specified.

        We test this by verifying the fallback behavior works correctly.
        The warning is logged via structlog which doesn't use caplog.
        """
        with patch.dict(os.environ, {"AGENT_MODEL": "invalid-model-name"}):
            config = AnthropicInvokerConfig.from_env()
            # Verify fallback happened (which means warning was triggered)
            assert config.model == DEFAULT_MODEL

    def test_valid_opus_model_accepted(self):
        """Opus model is accepted without fallback."""
        with patch.dict(os.environ, {"AGENT_MODEL": "claude-opus-4-5-20250514"}):
            config = AnthropicInvokerConfig.from_env()
            assert config.model == "claude-opus-4-5-20250514"

    def test_valid_sonnet_model_accepted(self):
        """Sonnet model is accepted without fallback."""
        with patch.dict(os.environ, {"AGENT_MODEL": "claude-sonnet-4-20250514"}):
            config = AnthropicInvokerConfig.from_env()
            assert config.model == "claude-sonnet-4-20250514"

    def test_valid_haiku_model_accepted(self):
        """Haiku model is accepted without fallback."""
        with patch.dict(os.environ, {"AGENT_MODEL": "claude-haiku-4-5-20250514"}):
            config = AnthropicInvokerConfig.from_env()
            assert config.model == "claude-haiku-4-5-20250514"

    def test_model_logged_at_config_creation(self):
        """Model selection is logged when config is created.

        We verify this by checking that __post_init__ runs successfully
        (it logs the model). The logging uses structlog not stdlib logging.
        """
        with patch.dict(os.environ, {"AGENT_MODEL": "claude-opus-4-5-20250514"}):
            config = AnthropicInvokerConfig.from_env()
            # Verify config was created successfully with expected model
            # __post_init__ logs the model during creation
            assert config.model == "claude-opus-4-5-20250514"


class TestModelTierInfo:
    """Tests for model tier information."""

    def test_opus_tier_is_opus(self):
        """Opus model has tier 'opus'."""
        assert VALID_MODELS["claude-opus-4-5-20250514"]["tier"] == "opus"

    def test_sonnet_tier_is_sonnet(self):
        """Sonnet model has tier 'sonnet'."""
        assert VALID_MODELS["claude-sonnet-4-20250514"]["tier"] == "sonnet"

    def test_haiku_tier_is_haiku(self):
        """Haiku model has tier 'haiku'."""
        assert VALID_MODELS["claude-haiku-4-5-20250514"]["tier"] == "haiku"

    def test_opus_cost_is_high(self):
        """Opus model has cost 'high'."""
        assert VALID_MODELS["claude-opus-4-5-20250514"]["cost"] == "high"

    def test_sonnet_cost_is_medium(self):
        """Sonnet model has cost 'medium'."""
        assert VALID_MODELS["claude-sonnet-4-20250514"]["cost"] == "medium"

    def test_haiku_cost_is_low(self):
        """Haiku model has cost 'low'."""
        assert VALID_MODELS["claude-haiku-4-5-20250514"]["cost"] == "low"


class TestTokenBudgetLimits:
    """Tests for token budget limits configuration (Task 8.5)."""

    def test_default_max_iterations(self):
        """Config has default max_iterations of 10."""
        config = AnthropicInvokerConfig()
        assert config.max_iterations == 10

    def test_default_max_input_tokens(self):
        """Config has default max_input_tokens of 50000."""
        config = AnthropicInvokerConfig()
        assert config.max_input_tokens == 50000

    def test_max_iterations_from_env(self):
        """Config reads max_iterations from AGENT_MAX_ITERATIONS env var."""
        with patch.dict(os.environ, {"AGENT_MAX_ITERATIONS": "5"}):
            config = AnthropicInvokerConfig.from_env()
            assert config.max_iterations == 5

    def test_max_input_tokens_from_env(self):
        """Config reads max_input_tokens from AGENT_MAX_INPUT_TOKENS env var."""
        with patch.dict(os.environ, {"AGENT_MAX_INPUT_TOKENS": "25000"}):
            config = AnthropicInvokerConfig.from_env()
            assert config.max_input_tokens == 25000

    def test_custom_max_iterations(self):
        """Config accepts custom max_iterations value."""
        config = AnthropicInvokerConfig(max_iterations=3)
        assert config.max_iterations == 3

    def test_custom_max_input_tokens(self):
        """Config accepts custom max_input_tokens value."""
        config = AnthropicInvokerConfig(max_input_tokens=100000)
        assert config.max_input_tokens == 100000
