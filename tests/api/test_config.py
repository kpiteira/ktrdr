"""
Test the API config functionality.
"""
import pytest
from ktrdr.api.config import APIConfig
from ktrdr import metadata  # Import the metadata module

class TestAPIConfig:
    """Test the API configuration class."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        config = APIConfig()
        assert config.title == "KTRDR API"
        assert config.description == "REST API for KTRDR trading system"
        assert config.version == metadata.VERSION  # Use VERSION from metadata
        assert config.api_prefix == "/api/v1"
        assert config.cors_origins == ["*"]
    
    def test_environment_variable_override(self):
        """Test that environment variables override default values."""
        # Use from_env method instead of relying on monkeypatch
        env_vars = {
            "KTRDR_API_PORT": "9999",
            "KTRDR_API_LOG_LEVEL": "DEBUG"
        }
        config = APIConfig.from_env(env_vars)
        
        assert config.port == 9999
        assert config.log_level == "DEBUG"
    
    def test_attribute_access(self):
        """Test that attributes can be accessed correctly."""
        config = APIConfig()
        assert hasattr(config, "title")
        assert hasattr(config, "version")
        assert hasattr(config, "port")
        assert hasattr(config, "host")
    
    def test_model_config(self):
        """Test that the Pydantic model has the correct config."""
        assert APIConfig.model_config["env_prefix"] == "KTRDR_API_"
    
    def test_reload_config(self):
        """Test reloading the configuration."""
        # Get initial config
        config = APIConfig()
        initial_port = config.port
        
        # Use from_env method instead of relying on monkeypatch
        env_vars = {
            "KTRDR_API_PORT": "8888"
        }
        new_config = APIConfig.from_env(env_vars)
        
        assert new_config.port == 8888
        assert new_config.port != initial_port
    
    def test_dict_conversion(self):
        """Test converting the config to a dictionary."""
        config = APIConfig()
        config_dict = config.model_dump()
        
        assert isinstance(config_dict, dict)
        assert "title" in config_dict
        assert "version" in config_dict
        assert config_dict["title"] == "KTRDR API"
        assert config_dict["version"] == metadata.VERSION  # Use VERSION from metadata