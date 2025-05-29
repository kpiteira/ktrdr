"""
IB Configuration Management

Handles configuration for Interactive Brokers connection and data fetching
with environment variable support and validation.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from ktrdr.logging import get_logger

logger = get_logger(__name__)


@dataclass
class IbConfig:
    """
    Interactive Brokers configuration settings.
    
    All settings can be overridden via environment variables with IB_ prefix.
    """
    
    # Connection settings
    host: str = field(default_factory=lambda: os.getenv("IB_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("IB_PORT", "4002")))
    client_id: int = field(default_factory=lambda: int(os.getenv("IB_CLIENT_ID", "1")))
    timeout: int = field(default_factory=lambda: int(os.getenv("IB_TIMEOUT", "10")))
    readonly: bool = field(default_factory=lambda: os.getenv("IB_READONLY", "false").lower() == "true")
    
    # Rate limiting settings
    rate_limit: int = field(default_factory=lambda: int(os.getenv("IB_RATE_LIMIT", "50")))
    rate_period: int = field(default_factory=lambda: int(os.getenv("IB_RATE_PERIOD", "60")))
    
    # Data fetching settings
    chunk_days: Dict[str, int] = field(default_factory=lambda: {
        "1 secs": 0.02,    # 30 minutes
        "5 secs": 0.08,    # 2 hours
        "15 secs": 0.17,   # 4 hours
        "30 secs": 0.33,   # 8 hours
        "1 min": 1,        # 1 day
        "2 mins": 2,       # 2 days (conservative)
        "3 mins": 3,       # 3 days (conservative)
        "5 mins": 7,       # 1 week
        "10 mins": 14,     # 2 weeks (conservative)
        "15 mins": 14,     # 2 weeks
        "20 mins": 20,     # 20 days (conservative)
        "30 mins": 30,     # 1 month
        "1 hour": 1,       # 1 day (IB limit for hourly data)
        "2 hours": 60,     # 2 months (conservative)
        "3 hours": 90,     # 3 months (conservative)
        "4 hours": 120,    # 4 months (conservative)
        "1 day": 365,      # 1 year
        "1 week": 730,     # 2 years
        "1 month": 365,    # 1 year
    })
    
    # Retry settings
    max_retries: int = field(default_factory=lambda: int(os.getenv("IB_MAX_RETRIES", "3")))
    retry_base_delay: float = field(default_factory=lambda: float(os.getenv("IB_RETRY_DELAY", "2.0")))
    retry_max_delay: float = field(default_factory=lambda: float(os.getenv("IB_RETRY_MAX_DELAY", "60.0")))
    
    # Pacing settings (based on IB documentation)
    pacing_delay: float = field(default_factory=lambda: float(os.getenv("IB_PACING_DELAY", "0.6")))
    max_requests_per_10min: int = field(default_factory=lambda: int(os.getenv("IB_MAX_REQUESTS_10MIN", "60")))
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate()
        
    def _validate(self):
        """Validate configuration values."""
        # Validate port range
        if not 1 <= self.port <= 65535:
            raise ValueError(f"Invalid port number: {self.port}")
            
        # Validate rate limit
        if self.rate_limit <= 0:
            raise ValueError(f"Rate limit must be positive: {self.rate_limit}")
            
        # Validate timeouts and delays
        if self.timeout <= 0:
            raise ValueError(f"Timeout must be positive: {self.timeout}")
            
        if self.retry_base_delay <= 0:
            raise ValueError(f"Retry base delay must be positive: {self.retry_base_delay}")
            
        if self.retry_max_delay <= self.retry_base_delay:
            raise ValueError(
                f"Retry max delay ({self.retry_max_delay}) must be greater than "
                f"base delay ({self.retry_base_delay})"
            )
            
        logger.info(
            f"IB config loaded: {self.host}:{self.port} "
            f"(client_id={self.client_id}, readonly={self.readonly})"
        )
    
    def get_connection_config(self) -> Dict[str, Any]:
        """Get connection configuration for IbConnectionManager."""
        from ktrdr.data.ib_connection import ConnectionConfig
        
        return ConnectionConfig(
            host=self.host,
            port=self.port,
            client_id=self.client_id,
            timeout=self.timeout,
            readonly=self.readonly
        )
    
    def get_chunk_size(self, bar_size: str) -> int:
        """
        Get maximum chunk size in days for a given bar size.
        
        Args:
            bar_size: IB bar size string (e.g., "1 min", "1 day")
            
        Returns:
            Maximum days to request in a single chunk
        """
        return self.chunk_days.get(bar_size, 1)
    
    def is_paper_trading(self) -> bool:
        """Check if configured for paper trading."""
        # Paper trading ports: TWS=7497, IB Gateway=4002
        return self.port in [7497, 4002]
    
    def is_live_trading(self) -> bool:
        """Check if configured for live trading."""
        # Live trading ports: TWS=7496, IB Gateway=4001
        return self.port in [7496, 4001]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "host": self.host,
            "port": self.port,
            "client_id": self.client_id,
            "timeout": self.timeout,
            "readonly": self.readonly,
            "rate_limit": self.rate_limit,
            "rate_period": self.rate_period,
            "max_retries": self.max_retries,
            "retry_base_delay": self.retry_base_delay,
            "retry_max_delay": self.retry_max_delay,
            "pacing_delay": self.pacing_delay,
            "max_requests_per_10min": self.max_requests_per_10min,
            "is_paper": self.is_paper_trading(),
            "is_live": self.is_live_trading(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IbConfig":
        """Create config from dictionary."""
        # Filter out non-init fields
        init_fields = {
            "host", "port", "client_id", "timeout", "readonly",
            "rate_limit", "rate_period", "max_retries",
            "retry_base_delay", "retry_max_delay", "pacing_delay",
            "max_requests_per_10min"
        }
        
        filtered_data = {k: v for k, v in data.items() if k in init_fields}
        return cls(**filtered_data)


# Default configuration instance
_default_config: Optional[IbConfig] = None


def get_ib_config() -> IbConfig:
    """Get the default IB configuration instance."""
    global _default_config
    if _default_config is None:
        _default_config = IbConfig()
    return _default_config


def reset_ib_config():
    """Reset the default configuration (mainly for testing)."""
    global _default_config
    _default_config = None