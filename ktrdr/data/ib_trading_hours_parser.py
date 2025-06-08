"""
Parser for Interactive Brokers trading hours data.

This module parses the trading hours information provided by IB's contract details
and converts it to our standardized trading hours format.
"""

import re
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from ktrdr.logging import get_logger
from ktrdr.data.trading_hours import TradingHours, TradingSession

logger = get_logger(__name__)


@dataclass
class IBTradingHoursInfo:
    """
    Raw trading hours information from IB contract details.
    
    Attributes:
        timezone_id: IB timezone ID (e.g., 'US/Eastern', 'UTC')
        trading_hours: Raw trading hours string from IB
        liquid_hours: Raw liquid hours string from IB (most restrictive)
    """
    timezone_id: str
    trading_hours: str
    liquid_hours: str


class IBTradingHoursParser:
    """
    Parser for IB trading hours data into standardized format.
    
    IB provides trading hours in format:
    "20161201:0400-20161201:2000;20161202:0400-20161202:2000"
    
    This represents:
    - Date:Time-Date:Time for each session
    - Sessions separated by semicolons
    - Times in exchange timezone
    - YYYYMMDD:HHMM format
    """
    
    # Map IB timezone IDs to standard timezone names
    TIMEZONE_MAPPING = {
        'US/Eastern': 'America/New_York',
        'US/Central': 'America/Chicago', 
        'US/Mountain': 'America/Denver',
        'US/Pacific': 'America/Los_Angeles',
        'Europe/London': 'Europe/London',
        'Europe/Zurich': 'Europe/Zurich',
        'Asia/Tokyo': 'Asia/Tokyo',
        'Asia/Hong_Kong': 'Asia/Hong_Kong',
        'UTC': 'UTC',
        'GMT': 'UTC'
    }
    
    @classmethod
    def parse_ib_trading_hours(cls, ib_info: IBTradingHoursInfo) -> Optional[TradingHours]:
        """
        Parse IB trading hours into our standardized format.
        
        Args:
            ib_info: Raw IB trading hours information
            
        Returns:
            TradingHours object or None if parsing fails
        """
        try:
            # Map IB timezone to standard timezone
            timezone = cls._map_timezone(ib_info.timezone_id)
            if not timezone:
                logger.warning(f"Unknown IB timezone: {ib_info.timezone_id}")
                return None
            
            # Parse liquid hours (most restrictive - represents regular trading)
            regular_sessions = cls._parse_hours_string(ib_info.liquid_hours)
            if not regular_sessions:
                logger.warning(f"Could not parse liquid hours: {ib_info.liquid_hours}")
                return None
            
            # Parse all trading hours (includes extended hours)
            all_sessions = cls._parse_hours_string(ib_info.trading_hours)
            if not all_sessions:
                logger.warning(f"Could not parse trading hours: {ib_info.trading_hours}")
                return None
            
            # Determine regular hours from liquid hours (typically the most restrictive)
            regular_hours = cls._extract_regular_hours(regular_sessions)
            
            # Determine extended hours (difference between all hours and liquid hours)
            extended_hours = cls._extract_extended_hours(all_sessions, regular_sessions)
            
            # Determine trading days from the sessions
            trading_days = cls._extract_trading_days(all_sessions)
            
            return TradingHours(
                timezone=timezone,
                regular_hours=regular_hours,
                extended_hours=extended_hours,
                trading_days=trading_days,
                holidays=[]  # IB doesn't provide holiday info in contract details
            )
            
        except Exception as e:
            logger.error(f"Failed to parse IB trading hours: {e}")
            logger.error(f"  Timezone: {ib_info.timezone_id}")
            logger.error(f"  Trading hours: {ib_info.trading_hours}")
            logger.error(f"  Liquid hours: {ib_info.liquid_hours}")
            return None
    
    @classmethod
    def _map_timezone(cls, ib_timezone: str) -> Optional[str]:
        """Map IB timezone ID to standard timezone name."""
        return cls.TIMEZONE_MAPPING.get(ib_timezone, ib_timezone)
    
    @classmethod
    def _parse_hours_string(cls, hours_string: str) -> List[Tuple[time, time]]:
        """
        Parse IB hours string into list of (start_time, end_time) tuples.
        
        Args:
            hours_string: IB format like "20161201:0400-20161201:2000;20161202:0930-20161202:1600"
            
        Returns:
            List of (start_time, end_time) tuples
        """
        sessions = []
        
        if not hours_string or hours_string == "CLOSED":
            return sessions
        
        # Split by semicolon to get individual sessions
        session_strings = hours_string.split(';')
        
        for session_str in session_strings:
            session_str = session_str.strip()
            if not session_str:
                continue
                
            # Pattern: YYYYMMDD:HHMM-YYYYMMDD:HHMM
            pattern = r'(\d{8}):(\d{4})-(\d{8}):(\d{4})'
            match = re.match(pattern, session_str)
            
            if match:
                start_date, start_time_str, end_date, end_time_str = match.groups()
                
                # Parse times (ignore dates for now, focus on time patterns)
                start_time = cls._parse_time_string(start_time_str)
                end_time = cls._parse_time_string(end_time_str)
                
                if start_time and end_time:
                    sessions.append((start_time, end_time))
                    
            else:
                logger.warning(f"Could not parse session string: {session_str}")
        
        return sessions
    
    @classmethod
    def _parse_time_string(cls, time_str: str) -> Optional[time]:
        """
        Parse HHMM string to time object.
        
        Args:
            time_str: Time in HHMM format (e.g., "0930", "1600")
            
        Returns:
            time object or None if parsing fails
        """
        try:
            if len(time_str) != 4:
                return None
                
            hour = int(time_str[:2])
            minute = int(time_str[2:])
            
            return time(hour, minute)
            
        except (ValueError, IndexError):
            logger.warning(f"Could not parse time string: {time_str}")
            return None
    
    @classmethod
    def _extract_regular_hours(cls, sessions: List[Tuple[time, time]]) -> TradingSession:
        """
        Extract regular trading hours from liquid sessions.
        
        For most markets, this will be the main trading session.
        """
        if not sessions:
            # Default fallback
            return TradingSession(time(9, 30), time(16, 0), "Regular")
        
        # For now, use the first session as regular hours
        # TODO: Could be more sophisticated in detecting main session
        start_time, end_time = sessions[0]
        return TradingSession(start_time, end_time, "Regular")
    
    @classmethod
    def _extract_extended_hours(cls, all_sessions: List[Tuple[time, time]], 
                               regular_sessions: List[Tuple[time, time]]) -> List[TradingSession]:
        """
        Extract extended hours by comparing all sessions with liquid sessions.
        """
        extended = []
        
        if not all_sessions or not regular_sessions:
            return extended
        
        regular_start, regular_end = regular_sessions[0] if regular_sessions else (None, None)
        
        for session_start, session_end in all_sessions:
            # Check if this session extends before regular hours
            if regular_start and session_start < regular_start:
                extended.append(TradingSession(session_start, regular_start, "Pre-Market"))
            
            # Check if this session extends after regular hours  
            if regular_end and session_end > regular_end:
                extended.append(TradingSession(regular_end, session_end, "After-Hours"))
        
        return extended
    
    @classmethod
    def _extract_trading_days(cls, sessions: List[Tuple[time, time]]) -> List[int]:
        """
        Extract trading days from sessions.
        
        For now, we'll use common patterns since IB hours don't directly indicate days.
        """
        if not sessions:
            return [0, 1, 2, 3, 4]  # Default to weekdays
        
        # TODO: Could analyze the date patterns in full IB data to determine actual trading days
        # For now, return standard patterns based on common knowledge
        
        # Most equity markets trade Monday-Friday
        return [0, 1, 2, 3, 4]  # Monday=0 to Friday=4
    
    @classmethod
    def create_from_contract_details(cls, contract_details) -> Optional[TradingHours]:
        """
        Create TradingHours from IB ContractDetails object.
        
        Args:
            contract_details: IB ContractDetails object
            
        Returns:
            TradingHours object or None if parsing fails
        """
        try:
            # Extract IB trading hours information
            ib_info = IBTradingHoursInfo(
                timezone_id=getattr(contract_details, 'timeZoneId', ''),
                trading_hours=getattr(contract_details, 'tradingHours', ''),
                liquid_hours=getattr(contract_details, 'liquidHours', '')
            )
            
            logger.debug(f"Parsing IB trading hours:")
            logger.debug(f"  Timezone: {ib_info.timezone_id}")
            logger.debug(f"  Trading hours: {ib_info.trading_hours}")
            logger.debug(f"  Liquid hours: {ib_info.liquid_hours}")
            
            return cls.parse_ib_trading_hours(ib_info)
            
        except Exception as e:
            logger.error(f"Failed to create trading hours from contract details: {e}")
            return None