"""Configuration for MCP server"""

import os
from pathlib import Path

import structlog
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Paths
ROOT_DIR = Path(__file__).parent.parent.parent  # Project root
MCP_DIR = ROOT_DIR / "mcp"
DATA_DIR = ROOT_DIR / "data"
MODELS_DIR = ROOT_DIR / "models"
STRATEGIES_DIR = ROOT_DIR / "strategies"

# API Configuration
KTRDR_API_URL = os.getenv("KTRDR_API_URL", "http://backend:8000/api/v1")
KTRDR_API_KEY = os.getenv("KTRDR_API_KEY", "")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))

# Storage Configuration
EXPERIMENT_DB_PATH = os.getenv("EXPERIMENT_DB_PATH", str(MCP_DIR / "experiments.db"))

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


def get_config(key: str, default=None):
    """Get configuration value from environment or default"""
    return os.getenv(key, default)


def setup_logging():
    """Configure structured logging"""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
