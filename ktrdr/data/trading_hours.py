"""
Trading hours metadata for different exchanges and asset types.

This module provides comprehensive trading hours information for various exchanges
to enhance market hours detection and symbol validation.
"""

from typing import Dict, List, Optional, Tuple, NamedTuple
from dataclasses import dataclass
from datetime import time
import pandas as pd

from ktrdr.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TradingSession:
    """
    Represents a trading session with start and end times.

    Attributes:
        start: Session start time (in exchange timezone)
        end: Session end time (in exchange timezone)
        name: Session name (e.g., "Regular", "Pre-Market", "After-Hours")
    """

    start: time
    end: time
    name: str


@dataclass
class TradingHours:
    """
    Complete trading hours information for an exchange/asset type.

    Attributes:
        timezone: Exchange timezone (e.g., 'America/New_York')
        regular_hours: Regular trading session
        extended_hours: List of extended trading sessions (pre/after market)
        trading_days: Days of the week when trading occurs (0=Monday, 6=Sunday)
        holidays: List of holiday dates when markets are closed
    """

    timezone: str
    regular_hours: TradingSession
    extended_hours: List[TradingSession]
    trading_days: List[int]  # 0=Monday, 6=Sunday
    holidays: List[str] = None  # ISO date strings


class TradingHoursManager:
    """
    Central manager for trading hours metadata across different exchanges.
    """

    # Comprehensive trading hours database
    EXCHANGE_HOURS: Dict[str, TradingHours] = {
        # US Stock Exchanges
        "NASDAQ": TradingHours(
            timezone="America/New_York",
            regular_hours=TradingSession(time(9, 30), time(16, 0), "Regular"),
            extended_hours=[
                TradingSession(time(4, 0), time(9, 30), "Pre-Market"),
                TradingSession(time(16, 0), time(20, 0), "After-Hours"),
            ],
            trading_days=[0, 1, 2, 3, 4],  # Monday-Friday
        ),
        "NYSE": TradingHours(
            timezone="America/New_York",
            regular_hours=TradingSession(time(9, 30), time(16, 0), "Regular"),
            extended_hours=[
                TradingSession(time(4, 0), time(9, 30), "Pre-Market"),
                TradingSession(time(16, 0), time(20, 0), "After-Hours"),
            ],
            trading_days=[0, 1, 2, 3, 4],
        ),
        "ARCA": TradingHours(
            timezone="America/New_York",
            regular_hours=TradingSession(time(9, 30), time(16, 0), "Regular"),
            extended_hours=[
                TradingSession(time(4, 0), time(9, 30), "Pre-Market"),
                TradingSession(time(16, 0), time(20, 0), "After-Hours"),
            ],
            trading_days=[0, 1, 2, 3, 4],
        ),
        "AMEX": TradingHours(
            timezone="America/New_York",
            regular_hours=TradingSession(time(9, 30), time(16, 0), "Regular"),
            extended_hours=[
                TradingSession(time(4, 0), time(9, 30), "Pre-Market"),
                TradingSession(time(16, 0), time(20, 0), "After-Hours"),
            ],
            trading_days=[0, 1, 2, 3, 4],
        ),
        # Forex (24/5 trading)
        "IDEALPRO": TradingHours(
            timezone="UTC",
            regular_hours=TradingSession(
                time(22, 0), time(21, 59), "24H"
            ),  # Sunday 22:00 to Friday 22:00 UTC
            extended_hours=[],
            trading_days=[0, 1, 2, 3, 4, 6],  # Monday-Friday + Sunday evening
        ),
        # Futures
        "GLOBEX": TradingHours(
            timezone="America/Chicago",
            regular_hours=TradingSession(time(8, 30), time(15, 15), "Regular"),
            extended_hours=[
                TradingSession(time(17, 0), time(8, 30), "Electronic")  # Nearly 24/5
            ],
            trading_days=[0, 1, 2, 3, 4, 6],  # Monday-Friday + Sunday evening
        ),
        # International Exchanges
        "LSE": TradingHours(
            timezone="Europe/London",
            regular_hours=TradingSession(time(8, 0), time(16, 30), "Regular"),
            extended_hours=[],
            trading_days=[0, 1, 2, 3, 4],
        ),
        "TSE": TradingHours(  # Tokyo Stock Exchange
            timezone="Asia/Tokyo",
            regular_hours=TradingSession(time(9, 0), time(15, 0), "Regular"),
            extended_hours=[],
            trading_days=[0, 1, 2, 3, 4],
        ),
        "HKFE": TradingHours(  # Hong Kong Futures Exchange
            timezone="Asia/Hong_Kong",
            regular_hours=TradingSession(time(9, 0), time(16, 30), "Regular"),
            extended_hours=[TradingSession(time(17, 15), time(23, 59), "Evening")],
            trading_days=[0, 1, 2, 3, 4],
        ),
    }

    # Asset type specific overrides
    ASSET_TYPE_HOURS: Dict[str, Dict[str, TradingHours]] = {
        "CASH": {
            # Forex markets typically trade 24/5
            "default": TradingHours(
                timezone="UTC",
                regular_hours=TradingSession(time(22, 0), time(21, 59), "24H"),
                extended_hours=[],
                trading_days=[0, 1, 2, 3, 4, 6],
            )
        }
    }

    @classmethod
    def get_trading_hours(
        cls, exchange: str, asset_type: str = "STK"
    ) -> Optional[TradingHours]:
        """
        Get trading hours for a specific exchange and asset type.

        Args:
            exchange: Exchange code (e.g., 'NASDAQ', 'NYSE')
            asset_type: Asset type (e.g., 'STK', 'CASH', 'FUT')

        Returns:
            TradingHours object or None if not found
        """
        # Check asset type specific overrides first
        if asset_type in cls.ASSET_TYPE_HOURS:
            if exchange in cls.ASSET_TYPE_HOURS[asset_type]:
                return cls.ASSET_TYPE_HOURS[asset_type][exchange]
            elif "default" in cls.ASSET_TYPE_HOURS[asset_type]:
                return cls.ASSET_TYPE_HOURS[asset_type]["default"]

        # Fall back to exchange-specific hours
        return cls.EXCHANGE_HOURS.get(exchange)

    @classmethod
    def is_market_open(
        cls,
        timestamp: pd.Timestamp,
        exchange: str,
        asset_type: str = "STK",
        include_extended: bool = False,
    ) -> bool:
        """
        Check if market is open at a specific timestamp.

        Args:
            timestamp: UTC timestamp to check
            exchange: Exchange code
            asset_type: Asset type
            include_extended: Whether to include extended hours

        Returns:
            True if market is open, False otherwise
        """
        hours = cls.get_trading_hours(exchange, asset_type)
        if not hours:
            logger.warning(f"No trading hours found for {exchange} ({asset_type})")
            return False

        # Convert UTC timestamp to exchange timezone
        try:
            local_time = timestamp.tz_convert(hours.timezone)
        except Exception as e:
            logger.error(f"Failed to convert timestamp to {hours.timezone}: {e}")
            return False

        # Check if it's a trading day
        if local_time.weekday() not in hours.trading_days:
            return False

        # Get current time
        current_time = local_time.time()

        # Check regular hours
        if cls._is_time_in_session(current_time, hours.regular_hours):
            return True

        # Check extended hours if requested
        if include_extended:
            for session in hours.extended_hours:
                if cls._is_time_in_session(current_time, session):
                    return True

        return False

    @classmethod
    def _is_time_in_session(cls, current_time: time, session: TradingSession) -> bool:
        """
        Check if current time falls within a trading session.

        Args:
            current_time: Time to check
            session: Trading session

        Returns:
            True if time is within session
        """
        # Handle sessions that cross midnight
        if session.start > session.end:
            return current_time >= session.start or current_time <= session.end
        else:
            return session.start <= current_time <= session.end

    @classmethod
    def get_market_status(
        cls, timestamp: pd.Timestamp, exchange: str, asset_type: str = "STK"
    ) -> str:
        """
        Get detailed market status at a specific timestamp.

        Args:
            timestamp: UTC timestamp to check
            exchange: Exchange code
            asset_type: Asset type

        Returns:
            Market status string ("Open", "Closed", "Pre-Market", "After-Hours")
        """
        hours = cls.get_trading_hours(exchange, asset_type)
        if not hours:
            return "Unknown"

        try:
            local_time = timestamp.tz_convert(hours.timezone)
        except Exception:
            return "Unknown"

        # Check if it's a trading day
        if local_time.weekday() not in hours.trading_days:
            return "Closed"

        current_time = local_time.time()

        # Check regular hours
        if cls._is_time_in_session(current_time, hours.regular_hours):
            return "Open"

        # Check extended hours
        for session in hours.extended_hours:
            if cls._is_time_in_session(current_time, session):
                return session.name

        return "Closed"

    @classmethod
    def to_dict(cls, hours: TradingHours) -> Dict:
        """
        Convert TradingHours to dictionary for JSON serialization.

        Args:
            hours: TradingHours object

        Returns:
            Dictionary representation
        """
        return {
            "timezone": hours.timezone,
            "regular_hours": {
                "start": hours.regular_hours.start.strftime("%H:%M"),
                "end": hours.regular_hours.end.strftime("%H:%M"),
                "name": hours.regular_hours.name,
            },
            "extended_hours": [
                {
                    "start": session.start.strftime("%H:%M"),
                    "end": session.end.strftime("%H:%M"),
                    "name": session.name,
                }
                for session in hours.extended_hours
            ],
            "trading_days": hours.trading_days,
            "holidays": hours.holidays or [],
        }
