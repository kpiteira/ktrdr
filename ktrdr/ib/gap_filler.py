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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

import pandas as pd

from ktrdr.config.ib_limits import IbLimitsRegistry
from ktrdr.config.loader import ConfigLoader
from ktrdr.data.data_manager import DataManager
from ktrdr.data.gap_classifier import GapClassifier
from ktrdr.data.local_data_loader import LocalDataLoader
from ktrdr.logging import get_logger
from ktrdr.utils.timezone_utils import TimestampManager

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

    def __init__(
        self, data_dir: Optional[str] = None, data_manager: Optional[DataManager] = None
    ):
        """Initialize the gap filler service."""
        self.data_dir = data_dir or self._get_data_dir()

        # Initialize local data loader for reading existing CSV files
        self.local_data_loader = LocalDataLoader(data_dir=self.data_dir)

        # Use injected DataManager or create default for intelligent gap operations
        if data_manager:
            self.data_manager = data_manager
        else:
            # Create default DataManager with IB integration enabled
            self.data_manager = DataManager(
                data_dir=self.data_dir,
                enable_ib=True,  # Enable IB integration for gap filling
            )

        # Service control
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Load configuration
        self.config = self._load_config()

        # Configuration with fallbacks
        self.check_interval = self._get_check_interval()
        self.max_gap_days = self.config.get("gap_filling", {}).get(
            "max_gap_age_days", 365
        )
        self.batch_size = self.config.get("gap_filling", {}).get("batch_size", 10)
        self.fill_unexpected_only = self.config.get("gap_filling", {}).get(
            "fill_unexpected_only", True
        )

        # Supported timeframes for gap filling
        self.supported_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]

        # Initialize gap classifier for intelligent gap detection
        self.gap_classifier = GapClassifier()

        # Statistics
        self.stats: Dict[str, Union[int, Optional[datetime], Set[str], List[Dict[str, Any]], Dict[str, int]]] = {
            "gaps_detected": 0,
            "gaps_filled": 0,
            "gaps_failed": 0,
            "gaps_expected_skipped": 0,  # New: track expected gaps we skip
            "last_scan_time": None,
            "symbols_processed": set(),
            "errors": [],
            "gap_classifications": {  # Track gap types
                "unexpected": 0,
                "expected_weekend": 0,
                "expected_trading_hours": 0,
                "expected_holiday": 0,
                "market_closure": 0,
            },
        }

        logger.info(f"Initialized GapFillerService with data_dir: {self.data_dir}")

    def _get_data_dir(self) -> str:
        """Get data directory from configuration."""
        try:
            # Try to get data directory from configuration
            config_loader = ConfigLoader()
            config = config_loader.load_from_env(default_path="config/settings.yaml")
            if hasattr(config, "data") and hasattr(config.data, "directory"):
                return config.data.directory
            return "data"
        except Exception:
            # Fall back to default if config loading fails
            return "data"

    def _load_config(self) -> dict[str, Any]:
        """Load IB sync configuration from settings."""
        try:
            config_loader = ConfigLoader()
            config = config_loader.load_from_env(default_path="config/settings.yaml")
            if hasattr(config, "ib_sync"):
                # Convert to dict for easier access
                return (
                    config.ib_sync.__dict__
                    if hasattr(config.ib_sync, "__dict__")
                    else {}
                )
            return {}
        except Exception as e:
            logger.warning(f"Failed to load ib_sync config: {e}, using defaults")
            return {}

    def _get_check_interval(self) -> int:
        """Get appropriate check interval based on configuration."""
        frequency = self.config.get("frequency", "daily")

        if frequency == "disabled":
            return 86400  # Check once per day but don't actually process
        elif frequency == "manual":
            return 3600  # Check hourly for manual triggers
        elif frequency == "hourly":
            return 3600  # Check every hour
        elif frequency == "daily":
            # Check if emergency gap detection is enabled
            emergency_config = self.config.get("emergency_gap_detection", {})
            if emergency_config.get("enabled", True):
                return emergency_config.get("check_interval", 3600)  # Default 1 hour
            else:
                return 3600  # Check hourly for daily sync scheduling
        else:
            logger.warning(f"Unknown sync frequency '{frequency}', defaulting to daily")
            return 3600

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
                # Check if IB is available via DataManager
                try:
                    # Check if DataManager has IB integration enabled
                    if (
                        self.data_manager.enable_ib
                        and hasattr(self.data_manager, 'ib_data_fetcher')
                        and self.data_manager.ib_data_fetcher
                    ):
                        # Try a simple IB operation to verify connectivity
                        # We can check this by testing if the IB data loader is functional
                        self._scan_and_fill_gaps()
                    else:
                        logger.debug("IB not enabled in DataManager, skipping gap scan")
                except Exception as e:
                    logger.debug(
                        f"IB availability check failed: {e}, skipping gap scan"
                    )

                self.stats["last_scan_time"] = datetime.now(timezone.utc)

                # Wait before next iteration
                self._stop_event.wait(self.check_interval)

            except Exception as e:
                logger.error(f"Error in gap filling loop: {e}")
                self.stats["errors"].append(
                    {"time": datetime.now(timezone.utc), "error": str(e)}
                )
                # Keep only last 10 errors
                self.stats["errors"] = self.stats["errors"][-10:]

                # Wait longer on error
                self._stop_event.wait(60)

        logger.info("Gap filling loop ended")

    def _scan_and_fill_gaps(self) -> None:
        """Scan for gaps and fill them."""
        # Check if we should run gap scan based on frequency
        if not self._should_run_gap_scan():
            logger.debug("Gap scan skipped due to frequency configuration")
            return

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
                logger.debug(
                    f"Reached batch limit ({self.batch_size}), will continue next cycle"
                )
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
                    if (
                        processed < len(symbols_timeframes)
                        and not self._stop_event.is_set()
                    ):
                        pacing_delay = IbLimitsRegistry.get_safe_delay(
                            "between_requests"
                        )
                        logger.debug(
                            f"Pacing delay after {symbol}_{timeframe}: {pacing_delay}s"
                        )
                        time.sleep(pacing_delay)

            except Exception as e:
                error_msg = str(e).lower()

                # Check for IB pacing limit errors
                if any(
                    pacing_keyword in error_msg
                    for pacing_keyword in [
                        "pacing",
                        "rate limit",
                        "too many requests",
                        "throttle",
                        "quota",
                    ]
                ):
                    logger.warning(
                        f"🚦 IB pacing limit detected for {symbol}_{timeframe}: {e}"
                    )
                    logger.info(
                        "🛑 Stopping gap filling due to pacing limits - will retry in next cycle"
                    )
                    self.stats["gaps_failed"] += 1
                    break  # Stop processing and let regular cycle retry later
                else:
                    logger.warning(f"Error checking gap for {symbol}_{timeframe}: {e}")
                    self.stats["gaps_failed"] += 1

        if processed > 0:
            logger.info(f"Gap filling cycle completed: processed {processed} symbols")

    def _discover_symbols_and_timeframes(self) -> list[tuple]:
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

            logger.debug(
                f"Discovered {len(symbols_timeframes)} symbol/timeframe combinations"
            )
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
            df = self.local_data_loader.load(symbol, timeframe)

            if df is None or df.empty:
                logger.debug(f"No existing data for {symbol}_{timeframe}")
                return False

            # Get last timestamp
            last_timestamp = df.index.max()
            if pd.isna(last_timestamp):
                logger.debug(f"Invalid last timestamp for {symbol}_{timeframe}")
                return False

            # Convert to UTC using TimestampManager
            last_timestamp = TimestampManager.to_utc(last_timestamp)

            # Calculate expected next timestamp based on timeframe
            next_expected = self._calculate_next_expected_timestamp(
                last_timestamp, timeframe
            )
            current_time = TimestampManager.now_utc()

            # Check if gap exists (accounting for market hours and weekends)
            gap_hours = (current_time - next_expected).total_seconds() / 3600

            # Different gap thresholds for different timeframes
            gap_threshold = IbLimitsRegistry.get_gap_threshold_hours(timeframe)

            if gap_hours < gap_threshold:
                # No significant gap
                return False

            # Check if gap is too old to be worth filling
            gap_days = gap_hours / 24
            if gap_days > self.max_gap_days:
                logger.debug(
                    f"Gap too old for {symbol}_{timeframe}: {gap_days:.1f} days"
                )
                return False

            # Perform intelligent gap analysis using the new classifier
            gap_info = self.gap_classifier.analyze_gap(
                start_time=next_expected,
                end_time=current_time,
                symbol=symbol,
                timeframe=timeframe,
            )

            # Update classification statistics
            classification_key = gap_info.classification.value
            if classification_key in self.stats["gap_classifications"]:
                self.stats["gap_classifications"][classification_key] += 1

            # Log gap detection with classification
            logger.info(
                f"Gap detected for {symbol}_{timeframe}: {gap_hours:.1f}h "
                f"[{gap_info.classification.value}] - {gap_info.note}"
            )
            self.stats["gaps_detected"] += 1

            # Decide whether to fill based on classification and configuration
            should_fill = self._should_fill_gap(gap_info)

            if not should_fill:
                logger.debug(
                    f"Skipping gap for {symbol}_{timeframe}: "
                    f"{gap_info.classification.value} - {gap_info.note}"
                )
                self.stats["gaps_expected_skipped"] += 1
                return False

            # Fill the gap using the enhanced DataManager (intelligent gap analysis)
            try:
                # Use DataManager's tail mode to fill gaps automatically
                df = self.data_manager.load_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=next_expected,
                    end_date=current_time,
                    mode="tail",  # Tail mode is perfect for gap filling
                    validate=True,
                    repair=False,
                )

                if df is not None and not df.empty:
                    # Filter to just the new data (after next_expected)
                    new_data = df[df.index >= next_expected]
                    fetched_bars = len(new_data)

                    if fetched_bars > 0:
                        self.stats["gaps_filled"] += 1
                        logger.info(
                            f"Filled gap for {symbol}_{timeframe}: {fetched_bars} bars fetched"
                        )
                        return True
                    else:
                        self.stats["gaps_failed"] += 1
                        logger.warning(
                            f"No new data fetched for gap in {symbol}_{timeframe}"
                        )
                        return False
                else:
                    self.stats["gaps_failed"] += 1
                    logger.warning(f"No data returned for gap in {symbol}_{timeframe}")
                    return False

            except Exception as e:
                self.stats["gaps_failed"] += 1
                logger.error(f" {e}")
                return False

        except Exception as e:
            logger.error(f"Error checking gap for {symbol}_{timeframe}: {e}")
            return False

    def _should_fill_gap(self, gap_info: Any) -> bool:
        """
        Determine if a gap should be filled based on classification and configuration.

        Args:
            gap_info: GapInfo object from gap analysis

        Returns:
            True if gap should be filled
        """
        # Check sync frequency setting
        frequency = self.config.get("frequency", "daily")
        if frequency == "disabled":
            logger.debug("Gap filling disabled by configuration")
            return False

        # If configured to fill unexpected only, check classification
        if self.fill_unexpected_only:
            # Only fill unexpected gaps and market closures
            fill_classifications = ["unexpected", "market_closure"]
            should_fill = gap_info.classification.value in fill_classifications

            if not should_fill:
                logger.debug(
                    f"Skipping {gap_info.classification.value} gap (unexpected_only=True)"
                )

            return should_fill
        else:
            # Use the classifier's default logic
            return self.gap_classifier.is_gap_worth_filling(gap_info)

    def _should_run_gap_scan(self) -> bool:
        """
        Determine if gap scan should run based on frequency and schedule.

        Returns:
            True if scan should run
        """
        frequency = self.config.get("frequency", "daily")

        if frequency == "disabled":
            return False
        elif frequency == "manual":
            # Only run on explicit force_scan calls
            return False
        elif frequency in ["hourly", "daily"]:
            # For daily frequency, implement simple scheduling logic
            # For now, always return True - more sophisticated scheduling can be added later
            return True
        else:
            return True

    def _calculate_next_expected_timestamp(
        self, last_timestamp: datetime, timeframe: str
    ) -> datetime:
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

    def get_stats(self) -> dict[str, Any]:
        """Get gap filling statistics."""
        return {
            **self.stats,
            "symbols_processed": list(self.stats["symbols_processed"]),
            "running": self._running,
            "check_interval": self.check_interval,
            "supported_timeframes": self.supported_timeframes,
            "configuration": {
                "frequency": self.config.get("frequency", "daily"),
                "max_gap_days": self.max_gap_days,
                "batch_size": self.batch_size,
                "fill_unexpected_only": self.fill_unexpected_only,
                "auto_start_on_api_startup": self.config.get(
                    "auto_start_on_api_startup", True
                ),
            },
        }

    def force_scan(self) -> dict[str, Any]:
        """Force an immediate gap scan (for testing/debugging)."""
        try:
            # Check IB availability via DataManager
            if not self.data_manager.enable_ib or not self.data_manager.ib_data_fetcher:
                return {"error": "IB not enabled in DataManager"}

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
