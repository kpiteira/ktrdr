"""
Synchronous IB Data Fetcher based on proven working pattern.
"""

import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import pandas as pd
from ib_insync import Stock, Forex, Contract
from ktrdr.logging import get_logger
from ktrdr.errors import DataError
from ktrdr.data.ib_connection_sync import IbConnectionSync, ConnectionConfig

logger = get_logger(__name__)


class IbDataFetcherSync:
    """
    Synchronous IB data fetcher that avoids event loop issues.
    
    Based on proven working pattern without async/await complexity.
    """
    
    def __init__(self, connection: Optional[IbConnectionSync] = None, config: Optional[ConnectionConfig] = None):
        """
        Initialize the data fetcher.
        
        Args:
            connection: Optional IbConnectionSync instance
            config: Optional ConnectionConfig
        """
        if connection:
            self.connection = connection
        else:
            self.connection = IbConnectionSync(config)
        
        self.ib = self.connection.ib
        
        # Metrics
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_bars_fetched": 0,
        }
    
    def get_contract(self, symbol: str, instrument_type: str = 'stock') -> Contract:
        """
        Get IB contract for a symbol.
        
        Args:
            symbol: Symbol to get contract for
            instrument_type: Type of instrument ('stock' or 'forex')
            
        Returns:
            Qualified IB contract
        """
        if not self.connection.ensure_connection():
            raise ConnectionError("Not connected to IB")
        
        try:
            if instrument_type == 'stock':
                contracts = self.ib.qualifyContracts(Stock(symbol, 'SMART', 'USD'))
            elif instrument_type == 'forex':
                contracts = self.ib.qualifyContracts(Forex(symbol))
            else:
                raise ValueError(f"Unsupported instrument type: {instrument_type}")
            
            if not contracts:
                raise DataError(f"Could not qualify contract for {symbol}")
            
            return contracts[0]
            
        except Exception as e:
            logger.error(f"Error qualifying contract for {symbol}: {e}")
            raise
    
    def determine_duration_str(self, timeframe: str, days: int) -> str:
        """
        Determine the appropriate duration string based on timeframe and days.
        
        Args:
            timeframe: Timeframe like '1h', '1d', etc.
            days: Number of days to fetch
            
        Returns:
            IB-compatible duration string like '1 W', '1 M', etc.
        """
        # IB duration format
        if days >= 365:
            years = days // 365
            return f"{years} Y"
        elif days >= 30:
            months = days // 30
            return f"{months} M"
        elif days >= 7:
            weeks = days // 7
            return f"{weeks} W"
        else:
            return f"{days} D"
    
    def get_bar_size(self, timeframe: str) -> str:
        """
        Convert our timeframe format to IB bar size format.
        
        Args:
            timeframe: Our format like '1h', '1d'
            
        Returns:
            IB format like '1 hour', '1 day'
        """
        mappings = {
            '1m': '1 min',
            '5m': '5 mins',
            '15m': '15 mins',
            '30m': '30 mins',
            '1h': '1 hour',
            '4h': '4 hours',
            '1d': '1 day',
            '1w': '1 week',
        }
        
        bar_size = mappings.get(timeframe)
        if not bar_size:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        
        return bar_size
    
    def format_ib_datetime(self, dt: Optional[datetime]) -> str:
        """
        Format datetime for IB API.
        
        Args:
            dt: Datetime to format
            
        Returns:
            Formatted string 'YYYYMMDD HH:MM:SS' or empty string
        """
        if dt is None:
            return ''
        
        # Ensure it's a datetime object
        if isinstance(dt, pd.Timestamp):
            dt = dt.to_pydatetime()
        
        # Format as IB expects
        return dt.strftime('%Y%m%d %H:%M:%S')
    
    def fetch_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        instrument_type: str = 'stock',
        what_to_show: str = 'TRADES'
    ) -> pd.DataFrame:
        """
        Fetch historical data from IB.
        
        Args:
            symbol: Symbol to fetch
            timeframe: Timeframe like '1h', '1d'
            start: Start datetime
            end: End datetime
            instrument_type: Type of instrument
            what_to_show: IB data type (TRADES, BID, ASK, MIDPOINT)
            
        Returns:
            DataFrame with OHLCV data
        """
        if not self.connection.ensure_connection():
            raise ConnectionError("Not connected to IB")
        
        try:
            # Get contract
            contract = self.get_contract(symbol, instrument_type)
            
            # Convert timeframe to IB bar size
            bar_size = self.get_bar_size(timeframe)
            
            # Calculate duration
            days_diff = (end - start).days
            if days_diff < 1:
                days_diff = 1
            duration_str = self.determine_duration_str(timeframe, days_diff)
            
            # Format end datetime for IB
            end_dt_str = self.format_ib_datetime(end)
            
            # Adjust what_to_show for forex
            if instrument_type == 'forex' and what_to_show == 'TRADES':
                what_to_show = 'BID'
                logger.info(f"Adjusted whatToShow to 'BID' for forex instrument")
            
            logger.info(
                f"Requesting historical data: {symbol} ({instrument_type}), "
                f"bar size: {bar_size}, duration: {duration_str}, "
                f"end: {end_dt_str}, whatToShow: {what_to_show}"
            )
            
            # Make the request
            self.metrics["total_requests"] += 1
            
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_dt_str,
                durationStr=duration_str,
                barSizeSetting=bar_size,
                whatToShow=what_to_show,
                useRTH=False,  # Use all trading hours
                formatDate=1   # Return as datetime objects
            )
            
            if not bars:
                logger.warning(f"No data returned for {symbol}")
                self.metrics["failed_requests"] += 1
                return pd.DataFrame()
            
            # Convert to DataFrame
            data = []
            for bar in bars:
                data.append({
                    'timestamp': bar.date,
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume
                })
            
            df = pd.DataFrame(data)
            df.set_index('timestamp', inplace=True)
            df.index = pd.to_datetime(df.index)
            
            # Ensure UTC timezone
            if df.index.tz is None:
                df.index = df.index.tz_localize('UTC')
            else:
                df.index = df.index.tz_convert('UTC')
            
            self.metrics["successful_requests"] += 1
            self.metrics["total_bars_fetched"] += len(df)
            
            logger.info(f"Successfully fetched {len(df)} bars for {symbol}")
            
            return df
            
        except Exception as e:
            self.metrics["failed_requests"] += 1
            logger.error(f"Error fetching data for {symbol}: {e}")
            raise DataError(
                f"Failed to fetch historical data: {e}",
                details={"symbol": symbol, "error": str(e)}
            )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get fetcher metrics."""
        metrics = self.metrics.copy()
        
        # Calculate success rate
        total = metrics["total_requests"]
        if total > 0:
            metrics["success_rate"] = metrics["successful_requests"] / total
        else:
            metrics["success_rate"] = 0
        
        return metrics