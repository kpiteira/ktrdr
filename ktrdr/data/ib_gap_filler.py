"""
Automatic Gap Filling Service

Automatically fills gaps in market data by:
- Detecting gaps between last available data and current time
- Fetching missing data when IB connection is available  
- Updating local CSV files
- Running continuously in the background
- Working independently of API requests
"""

import threading
import time
import os
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd

from ktrdr.logging import get_logger
from ktrdr.data.ib_connection_manager import get_connection_manager
from ktrdr.data.ib_data_fetcher_sync import IbDataFetcherSync
from ktrdr.data.ib_context_manager import create_context_aware_fetcher
from ktrdr.data.local_data_loader import LocalDataLoader
from ktrdr.config.loader import ConfigLoader

logger = get_logger(__name__)


class GapFillerService:
    """
    Service that automatically fills gaps in market data.
    
    This service:
    - Scans for data gaps periodically
    - Fetches missing data when IB connection is available
    - Updates local CSV files
    - Handles multiple symbols and timeframes
    - Runs independently in the background
    """
    
    def __init__(self, data_dir: Optional[str] = None):
        """Initialize the gap filler service."""
        self.data_dir = data_dir or self._get_data_dir()
        self.data_loader = LocalDataLoader(data_dir=self.data_dir)
        self.connection_manager = get_connection_manager()
        
        # Service control
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Configuration
        self.check_interval = 300  # Check every 5 minutes
        self.max_gap_days = 365    # Allow gaps up to 1 year (reasonable limit)
        self.batch_size = 10       # Process max 10 symbols per cycle
        
        # Supported timeframes for gap filling
        self.supported_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
        
        # Statistics
        self.stats = {
            "gaps_detected": 0,
            "gaps_filled": 0,
            "gaps_failed": 0,
            "last_scan_time": None,
            "symbols_processed": set(),
            "errors": []
        }
        
        logger.info(f"Initialized GapFillerService with data_dir: {self.data_dir}")
    
    def _get_data_dir(self) -> str:
        """Get data directory from configuration."""
        try:
            # Try to get data directory from configuration
            config_loader = ConfigLoader()
            config = config_loader.load_from_env(default_path="config/settings.yaml")
            if hasattr(config, 'data') and hasattr(config.data, 'directory'):
                return config.data.directory
            return "data"
        except Exception:
            # Fall back to default if config loading fails
            return "data"
    
    def start(self) -> bool:
        """
        Start the gap filling service.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self._running:
            logger.warning("Gap filler service is already running")
            return True
            
        try:
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._gap_filling_loop, daemon=True)
            self._thread.start()
            
            logger.info("Started automatic gap filling service")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start gap filler service: {e}")
            self._running = False
            return False
    
    def stop(self) -> None:
        """Stop the gap filling service."""
        if not self._running:
            return
            
        logger.info("Stopping gap filling service...")
        self._running = False
        self._stop_event.set()
        
        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
            
        logger.info("Stopped gap filling service")
    
    def _gap_filling_loop(self) -> None:
        """Main gap filling loop that runs in background thread."""
        logger.info("Starting gap filling loop")
        
        while self._running and not self._stop_event.is_set():
            try:
                # Only scan if IB connection is available
                if self.connection_manager.is_connected():
                    self._scan_and_fill_gaps()
                else:
                    logger.debug("IB not connected, skipping gap scan")
                
                self.stats["last_scan_time"] = datetime.now(timezone.utc)
                
                # Wait before next iteration
                self._stop_event.wait(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in gap filling loop: {e}")
                self.stats["errors"].append({
                    "time": datetime.now(timezone.utc),
                    "error": str(e)
                })
                # Keep only last 10 errors
                self.stats["errors"] = self.stats["errors"][-10:]
                
                # Wait longer on error
                self._stop_event.wait(60)
        
        logger.info("Gap filling loop ended")
    
    def _scan_and_fill_gaps(self) -> None:
        """Scan for gaps and fill them."""
        logger.debug("Scanning for data gaps...")
        
        # Get list of symbols from existing CSV files
        symbols_timeframes = self._discover_symbols_and_timeframes()
        
        if not symbols_timeframes:
            logger.debug("No CSV files found to check for gaps")
            return
        
        # Process symbols sequentially to avoid pacing limits
        processed = 0
        for symbol, timeframe in symbols_timeframes:
            if processed >= self.batch_size:
                logger.debug(f"Reached batch limit ({self.batch_size}), will continue next cycle")
                break
                
            if self._stop_event.is_set():
                break
                
            try:
                # Sequential processing with pacing detection
                gap_filled = self._check_and_fill_gap(symbol, timeframe)
                if gap_filled:
                    processed += 1
                    self.stats["symbols_processed"].add(f"{symbol}_{timeframe}")
                    
                    # Add small delay between successful requests to respect IB pacing
                    if processed < len(symbols_timeframes) and not self._stop_event.is_set():
                        logger.debug(f"Pacing delay after {symbol}_{timeframe}")
                        time.sleep(1.0)  # 1 second between requests
                        
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check for IB pacing limit errors
                if any(pacing_keyword in error_msg for pacing_keyword in [
                    'pacing', 'rate limit', 'too many requests', 'throttle', 'quota'
                ]):
                    logger.warning(f"🚦 IB pacing limit detected for {symbol}_{timeframe}: {e}")
                    logger.info("🛑 Stopping gap filling due to pacing limits - will retry in next cycle")
                    self.stats["gaps_failed"] += 1
                    break  # Stop processing and let regular cycle retry later
                else:
                    logger.warning(f"Error checking gap for {symbol}_{timeframe}: {e}")
                    self.stats["gaps_failed"] += 1
        
        if processed > 0:
            logger.info(f"Gap filling cycle completed: processed {processed} symbols")
    
    def _discover_symbols_and_timeframes(self) -> List[tuple]:
        """Discover symbols and timeframes from existing CSV files."""
        symbols_timeframes = []
        
        try:
            data_path = Path(self.data_dir)
            if not data_path.exists():
                return symbols_timeframes
            
            # Find all CSV files matching pattern: SYMBOL_TIMEFRAME.csv
            for csv_file in data_path.glob("*.csv"):
                filename = csv_file.stem  # Remove .csv extension
                
                # Try to parse SYMBOL_TIMEFRAME format
                parts = filename.split("_")
                if len(parts) >= 2:
                    symbol = "_".join(parts[:-1])  # Handle symbols with underscores
                    timeframe = parts[-1]
                    
                    if timeframe in self.supported_timeframes:
                        symbols_timeframes.append((symbol, timeframe))
            
            logger.debug(f"Discovered {len(symbols_timeframes)} symbol/timeframe combinations")
            return symbols_timeframes
            
        except Exception as e:
            logger.error(f"Error discovering symbols and timeframes: {e}")
            return symbols_timeframes
    
    def _check_and_fill_gap(self, symbol: str, timeframe: str) -> bool:
        """
        Check for gaps in symbol data and fill if needed.
        
        Returns:
            True if gap was filled, False otherwise
        """
        try:
            # Load existing data to check last timestamp
            df = self.data_loader.load(symbol, timeframe)
            
            if df is None or df.empty:
                logger.debug(f"No existing data for {symbol}_{timeframe}")
                return False
            
            # Get last timestamp
            last_timestamp = df.index.max()
            if pd.isna(last_timestamp):
                logger.debug(f"Invalid last timestamp for {symbol}_{timeframe}")
                return False
            
            # Convert to timezone-aware if needed
            if last_timestamp.tz is None:
                last_timestamp = last_timestamp.tz_localize(timezone.utc)
            else:
                last_timestamp = last_timestamp.tz_convert(timezone.utc)
            
            # Calculate expected next timestamp based on timeframe
            next_expected = self._calculate_next_expected_timestamp(last_timestamp, timeframe)
            current_time = datetime.now(timezone.utc)
            
            # Check if gap exists (accounting for market hours and weekends)
            gap_hours = (current_time - next_expected).total_seconds() / 3600
            
            # Different gap thresholds for different timeframes
            gap_threshold = self._get_gap_threshold(timeframe)
            
            if gap_hours < gap_threshold:
                # No significant gap
                return False
            
            # Check if gap is too old to be worth filling
            gap_days = gap_hours / 24
            if gap_days > self.max_gap_days:
                logger.debug(f"Gap too old for {symbol}_{timeframe}: {gap_days:.1f} days")
                return False
            
            logger.info(f"Gap detected for {symbol}_{timeframe}: {gap_hours:.1f} hours")
            self.stats["gaps_detected"] += 1
            
            # Fill the gap - handle large gaps with multiple requests
            success = self._fill_gap_progressive(symbol, timeframe, next_expected, current_time)
            
            if success:
                self.stats["gaps_filled"] += 1
                logger.info(f"✅ Filled gap for {symbol}_{timeframe}")
            else:
                self.stats["gaps_failed"] += 1
                logger.warning(f"❌ Failed to fill gap for {symbol}_{timeframe}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error checking gap for {symbol}_{timeframe}: {e}")
            return False
    
    def _fill_gap_progressive(self, symbol: str, timeframe: str, start_time: datetime, end_time: datetime) -> bool:
        """
        Fill gap progressively with multiple requests if needed for large gaps.
        
        This method handles gaps that exceed IB single-request limits by making
        multiple sequential requests working backwards from end_time.
        
        Returns:
            True if gap was filled successfully, False otherwise
        """
        try:
            # Get IB max duration limit for this timeframe
            max_limits = {
                '1m': 1,      # 1 day
                '5m': 7,      # 1 week  
                '15m': 14,    # 2 weeks
                '30m': 30,    # 1 month
                '1h': 30,     # 1 month
                '4h': 30,     # 1 month (conservative)
                '1d': 365,    # 1 year
                '1w': 730,    # 2 years
                '1M': 365,    # 1 year
            }
            
            max_days = max_limits.get(timeframe, 30)
            total_gap_days = (end_time - start_time).days
            
            if total_gap_days <= max_days:
                # Small gap - use single request
                logger.info(f"Small gap ({total_gap_days} days) - using single request")
                return self._fill_gap(symbol, timeframe, start_time, end_time)
            
            # Large gap - use progressive filling
            logger.info(f"Large gap ({total_gap_days} days) - using progressive filling (max {max_days} days per request)")
            
            current_end = end_time
            total_bars_added = 0
            requests_made = 0
            max_requests = 5  # Limit to prevent excessive API calls
            
            while current_end > start_time and requests_made < max_requests:
                # Calculate start time for this chunk (work backwards)
                chunk_start = max(start_time, current_end - timedelta(days=max_days))
                
                logger.info(f"Progressive fill request {requests_made + 1}: {chunk_start.date()} to {current_end.date()}")
                
                # Fill this chunk
                chunk_success = self._fill_gap(symbol, timeframe, chunk_start, current_end)
                
                if chunk_success:
                    requests_made += 1
                    logger.info(f"✅ Progressive chunk {requests_made} filled successfully")
                    
                    # Move to previous chunk
                    current_end = chunk_start - timedelta(hours=1)  # Move back 1 hour to avoid overlap
                    
                    # Add delay between requests to respect IB pacing
                    if current_end > start_time:
                        logger.debug("Pacing delay between progressive requests")
                        time.sleep(2.0)  # 2 second delay between requests
                else:
                    logger.warning(f"❌ Progressive chunk {requests_made + 1} failed")
                    break
            
            if current_end <= start_time:
                logger.info(f"✅ Progressive gap filling completed in {requests_made} requests")
                return True
            else:
                logger.warning(f"⚠️ Progressive gap filling incomplete after {requests_made} requests")
                return requests_made > 0  # Partial success if at least one request worked
                
        except Exception as e:
            logger.error(f"Error in progressive gap filling for {symbol}_{timeframe}: {e}")
            return False
    
    def _calculate_next_expected_timestamp(self, last_timestamp: datetime, timeframe: str) -> datetime:
        """Calculate when next data point should be expected."""
        timeframe_minutes = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "1d": 1440,  # 24 hours
        }
        
        minutes = timeframe_minutes.get(timeframe, 60)
        return last_timestamp + timedelta(minutes=minutes)
    
    def _get_gap_threshold(self, timeframe: str) -> float:
        """Get gap threshold in hours for different timeframes."""
        thresholds = {
            "1m": 0.5,    # 30 minutes
            "5m": 1.0,    # 1 hour
            "15m": 2.0,   # 2 hours
            "30m": 3.0,   # 3 hours
            "1h": 6.0,    # 6 hours
            "4h": 12.0,   # 12 hours
            "1d": 18.0,   # 18 hours (more reasonable for daily data)
        }
        return thresholds.get(timeframe, 6.0)
    
    def _fill_gap(self, symbol: str, timeframe: str, start_time: datetime, end_time: datetime) -> bool:
        """
        Fill gap by fetching data from IB and updating CSV.
        
        Returns:
            True if gap was filled successfully, False otherwise
        """
        try:
            # Get IB connection
            logger.info(f"🔍 Requesting connection for {symbol}_{timeframe}")
            connection = self.connection_manager.get_connection()
            if not connection:
                logger.warning("No IB connection available for gap filling")
                return False
            
            # Debug: Check connection state
            logger.info(f"📋 Got connection for {symbol}_{timeframe}: connected={connection.is_connected()}, client_id={connection.config.client_id}")
            
            # Create context-aware data fetcher
            context_fetcher = create_context_aware_fetcher(connection)
            
            # Fetch missing data using context-aware method
            logger.debug(f"Fetching data for {symbol} from {start_time} to {end_time}")
            new_data = context_fetcher.fetch_historical_data(symbol, timeframe, start_time, end_time)
            
            if new_data is None or new_data.empty:
                logger.warning(f"No new data received for {symbol}_{timeframe}")
                return False
            
            # Load existing data
            existing_data = self.data_loader.load(symbol, timeframe)
            
            # Combine and save
            if existing_data is not None and not existing_data.empty:
                # Ensure timezone consistency before combining
                if existing_data.index.tz is None and new_data.index.tz is not None:
                    # Existing data is timezone-naive, make it UTC-aware
                    existing_data.index = existing_data.index.tz_localize(timezone.utc)
                elif existing_data.index.tz is not None and new_data.index.tz is None:
                    # New data is timezone-naive, make it UTC-aware  
                    new_data.index = new_data.index.tz_localize(timezone.utc)
                elif existing_data.index.tz is not None and new_data.index.tz is not None:
                    # Both are timezone-aware, convert to UTC
                    existing_data.index = existing_data.index.tz_convert(timezone.utc)
                    new_data.index = new_data.index.tz_convert(timezone.utc)
                
                # Combine data, removing duplicates
                combined = pd.concat([existing_data, new_data])
                combined = combined[~combined.index.duplicated(keep='last')]
                combined = combined.sort_index()
            else:
                combined = new_data
            
            # Save to CSV
            self._save_data_to_csv(symbol, timeframe, combined)
            
            logger.info(f"Added {len(new_data)} bars to {symbol}_{timeframe}")
            return True
            
        except Exception as e:
            logger.error(f"Error filling gap for {symbol}_{timeframe}: {e}")
            return False
    
    def _save_data_to_csv(self, symbol: str, timeframe: str, data: pd.DataFrame) -> None:
        """Save data to CSV file."""
        try:
            # Ensure data directory exists
            os.makedirs(self.data_dir, exist_ok=True)
            
            # Create filename
            filename = f"{symbol}_{timeframe}.csv"
            filepath = os.path.join(self.data_dir, filename)
            
            # Save to CSV
            data.to_csv(filepath)
            logger.debug(f"Saved {len(data)} bars to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving data to CSV: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get gap filling statistics."""
        return {
            **self.stats,
            "symbols_processed": list(self.stats["symbols_processed"]),
            "running": self._running,
            "check_interval": self.check_interval,
            "supported_timeframes": self.supported_timeframes,
        }
    
    def force_scan(self) -> Dict[str, Any]:
        """Force an immediate gap scan (for testing/debugging)."""
        if not self.connection_manager.is_connected():
            return {"error": "IB not connected"}
        
        try:
            self._scan_and_fill_gaps()
            return {"success": True, "stats": self.get_stats()}
        except Exception as e:
            return {"error": str(e)}


# Global instance
_gap_filler = None


def get_gap_filler() -> GapFillerService:
    """Get the global gap filler service instance."""
    global _gap_filler
    if _gap_filler is None:
        _gap_filler = GapFillerService()
    return _gap_filler


def start_gap_filler() -> bool:
    """Start the global gap filler service."""
    return get_gap_filler().start()


def stop_gap_filler() -> None:
    """Stop the global gap filler service."""
    service = get_gap_filler()
    service.stop()