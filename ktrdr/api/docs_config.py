"""
Documentation configuration module for KTRDR API.

This module provides a centralized way to load and access documentation
configuration used across the API and documentation templates.
"""
import os
from pathlib import Path
import yaml
from pydantic import BaseModel, Field
from typing import List, Optional

# Configuration file path
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "docs_config.yaml"


class OrganizationConfig(BaseModel):
    """Organization information configuration."""
    name: str = "KTRDR"
    website: str = "https://ktrdr.example.com"
    github: str = "https://github.com/yourusername/ktrdr"
    email: str = "support@example.com"
    docs_url: str = "https://ktrdr-docs.example.com"


class ApiConfig(BaseModel):
    """API information configuration."""
    title: str = "KTRDR API"
    description: str = "REST API for KTRDR trading system"
    version: str = "1.0.5"
    base_url: str = "http://127.0.0.1:8000"
    prefix: str = "/api/v1"


class BrandingConfig(BaseModel):
    """Branding configuration."""
    logo_url: str = "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    logo_alt: str = "KTRDR API Logo"
    primary_color: str = "#4CAF50"
    secondary_color: str = "#1a1a1a"


class ExamplesConfig(BaseModel):
    """Documentation examples configuration."""
    symbols: List[str] = Field(default_factory=lambda: ["AAPL", "MSFT", "GOOGL"])
    timeframes: List[str] = Field(
        default_factory=lambda: ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w", "1M"]
    )
    default_symbol: str = "AAPL"
    default_timeframe: str = "1d"


class DocsConfig(BaseModel):
    """Main documentation configuration."""
    organization: OrganizationConfig = Field(default_factory=OrganizationConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    branding: BrandingConfig = Field(default_factory=BrandingConfig)
    examples: ExamplesConfig = Field(default_factory=ExamplesConfig)


def load_docs_config(config_path: Optional[str] = None) -> DocsConfig:
    """
    Load the documentation configuration from YAML file.
    
    Args:
        config_path: Path to the configuration file. If None, uses the default path.
        
    Returns:
        DocsConfig: Loaded documentation configuration
        
    Raises:
        FileNotFoundError: If the configuration file cannot be found
        yaml.YAMLError: If the configuration file has invalid YAML
    """
    # Determine config path
    path = config_path or os.getenv("KTRDR_DOCS_CONFIG_PATH") or DEFAULT_CONFIG_PATH
    
    try:
        # Load the configuration file
        with open(path, "r") as f:
            config_data = yaml.safe_load(f)
        
        # Convert to Pydantic model
        return DocsConfig(**config_data)
    except FileNotFoundError:
        # Return default configuration if file not found
        print(f"Documentation config file not found at {path}, using defaults")
        return DocsConfig()
    except yaml.YAMLError as e:
        print(f"Error parsing documentation config file: {e}")
        raise


# Create a global instance for easy import
docs_config = load_docs_config()