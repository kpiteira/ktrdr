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

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


def get_config(key: str, default=None):
    """Get configuration value from environment or default"""
    return os.getenv(key, default)


def setup_logging():
    """Configure logging - JSON to stderr (for MCP), human-readable to file"""
    import logging

    # Ensure logs directory exists
    log_dir = Path("/app/logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "mcp.log"

    # Human-readable format for file logs
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL))

    # Clear existing handlers
    root_logger.handlers.clear()

    # File handler (human-readable for debugging)
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(getattr(logging, LOG_LEVEL))
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    root_logger.addHandler(file_handler)

    # Configure structlog for JSON output to stderr (MCP protocol)
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
            structlog.processors.JSONRenderer(),  # JSON for MCP protocol
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
