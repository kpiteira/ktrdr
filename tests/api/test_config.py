"""
API configuration module tests.

This module tests the configuration module with environment variable support.
"""
import os
import pytest

from ktrdr.api.config import APIConfig

class TestAPIConfig:
    """Tests for the APIConfig class."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        config = APIConfig()
        assert config.title == "KTRDR API"
        assert config.description == "REST API for KTRDR trading system"
        assert config.version == "1.0.5.5"
        assert config.host == "127.0.0.1"
        assert config.port == 8000
        assert config.reload is True
        assert config.log_level == "INFO"
        assert config.environment == "development"
        assert config.api_prefix == "/api/v1"
        assert config.cors_origins == ["*"]
        assert config.cors_allow_credentials is True
        assert config.cors_allow_methods == ["*"]
        assert config.cors_allow_headers == ["*"]
        assert config.cors_max_age == 600
    
    def test_environment_variable_override(self):
        """Test that environment variables override default values."""
        # Use the new from_env method which handles env vars better
        config = APIConfig.from_env({
            "KTRDR_API_TITLE": "Custom API",
            "KTRDR_API_PORT": "9000",
            "KTRDR_API_RELOAD": "false",
            "KTRDR_API_ENVIRONMENT": "production"
        })
        assert config.title == "Custom API"
        assert config.port == 9000
        assert config.reload is False
        assert config.environment == "production"
    
    def test_cors_origins_parsing(self):
        """Test that CORS origins are correctly parsed from string."""
        # Use the new from_env method which handles env vars better
        config = APIConfig.from_env({
            "KTRDR_API_CORS_ORIGINS": "http://localhost:3000,http://example.com"
        })
        assert config.cors_origins == ["http://localhost:3000", "http://example.com"]
    
    def test_cors_methods_parsing(self):
        """Test that CORS methods are correctly parsed from string."""
        # Use the new from_env method which handles env vars better
        config = APIConfig.from_env({
            "KTRDR_API_CORS_ALLOW_METHODS": "GET,POST,PUT"
        })
        assert config.cors_allow_methods == ["GET", "POST", "PUT"]
    
    def test_cors_headers_parsing(self):
        """Test that CORS headers are correctly parsed from string."""
        # Use the new from_env method which handles env vars better
        config = APIConfig.from_env({
            "KTRDR_API_CORS_ALLOW_HEADERS": "Content-Type,Authorization"
        })
        assert config.cors_allow_headers == ["Content-Type", "Authorization"]
    
    def test_environment_validation(self):
        """Test that environment validation works correctly."""
        with pytest.raises(ValueError) as excinfo:
            APIConfig.from_env({"KTRDR_API_ENVIRONMENT": "invalid"})
        assert "Environment must be one of" in str(excinfo.value)
    
    def test_log_level_validation(self):
        """Test that log level validation works correctly."""
        with pytest.raises(ValueError) as excinfo:
            APIConfig.from_env({"KTRDR_API_LOG_LEVEL": "invalid"})
        assert "Log level must be one of" in str(excinfo.value)