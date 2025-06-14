"""
Async DataManager for managing, validating, and processing OHLCV data.

This is the clean async version of DataManager that integrates with the new
async IB architecture without threading complexity.
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any, Set, Callable
from datetime import datetime, timedelta
import pandas as pd

from ktrdr import (
    get_logger,
    log_entry_exit,
    log_performance,
    log_data_operation,
)
from ktrdr.utils.timezone_utils import TimestampManager

from ktrdr.errors import (
    DataError,
    DataNotFoundError,
    DataCorruptionError,
)

from ktrdr.data.local_data_loader import LocalDataLoader
from ktrdr.data.ib_data_fetcher_unified import IbDataFetcherUnified
from ktrdr.data.ib_symbol_validator_unified import IbSymbolValidatorUnified
from ktrdr.data.data_quality_validator import DataQualityValidator
from ktrdr.data.gap_classifier import GapClassifier, GapClassification
from ktrdr.data.timeframe_constants import TimeframeConstants

logger = get_logger(__name__)


class DataManagerAsync:
    """
    Async DataManager for sophisticated data management with IB integration.

    This clean async version eliminates threading complexity and uses
    ib_insync natively for all IB operations.
    """

    # Repair methods for backward compatibility
    REPAIR_METHODS = {
        "ffill": pd.DataFrame.ffill,
        "bfill": pd.DataFrame.bfill,
        "interpolate": pd.DataFrame.interpolate,
        "zero": lambda df: df.fillna(0),
        "mean": lambda df: df.fillna(df.mean()),
        "median": lambda df: df.fillna(df.median()),
        "drop": lambda df: df.dropna(),
    }

    def __init__(
        self,
        data_dir: Optional[str] = None,
        max_gap_percentage: float = 5.0,
        default_repair_method: str = "ffill",
        enable_ib: bool = True,
    ):
        """
        Initialize the async DataManager.

        Args:
            data_dir: Path to the directory containing data files
            max_gap_percentage: Maximum allowed percentage of gaps in data
            default_repair_method: Default method for repairing missing values
            enable_ib: Whether to enable IB integration
        """
        # Validate parameters
        if max_gap_percentage < 0 or max_gap_percentage > 100:
            raise DataError(
                message=f"Invalid max_gap_percentage: {max_gap_percentage}. Must be between 0 and 100.",
                error_code="DATA-InvalidParameter",
            )

        if default_repair_method not in self.REPAIR_METHODS:
            raise DataError(
                message=f"Invalid repair method: {default_repair_method}",
                error_code="DATA-InvalidParameter",
            )

        # Initialize components
        self.data_loader = LocalDataLoader(data_dir=data_dir)
        self.max_gap_percentage = max_gap_percentage
        self.default_repair_method = default_repair_method
        self.enable_ib = enable_ib

        # Initialize async IB components
        if enable_ib:
            self.ib_data_fetcher = IbDataFetcherUnified(
                component_name="data_manager_async"
            )
            self.ib_symbol_validator = IbSymbolValidatorUnified(
                component_name="data_manager_async"
            )
            logger.info("IB integration enabled (async)")
        else:
            self.ib_data_fetcher = None
            self.ib_symbol_validator = None
            logger.info("IB integration disabled")

        # Initialize validators
        self.data_validator = DataQualityValidator(
            auto_correct=True,
            max_gap_percentage=max_gap_percentage,
        )
        self.gap_classifier = GapClassifier()

        logger.info(
            f"DataManagerAsync initialized (max_gap_percentage={max_gap_percentage}%)"
        )

    def _check_cancellation(
        self,
        cancellation_token: Optional[Any],
        operation_description: str = "operation",
    ) -> bool:
        """Check if cancellation has been requested."""
        if cancellation_token is None:
            return False

        is_cancelled = False
        if hasattr(cancellation_token, "is_cancelled_requested"):
            is_cancelled = cancellation_token.is_cancelled_requested
        elif hasattr(cancellation_token, "is_set"):
            is_cancelled = cancellation_token.is_set()
        elif hasattr(cancellation_token, "cancelled"):
            is_cancelled = cancellation_token.cancelled()

        if is_cancelled:
            logger.info(f"🛑 Cancellation requested during {operation_description}")
            raise asyncio.CancelledError(
                f"Operation cancelled during {operation_description}"
            )

        return False

    @log_entry_exit(logger=logger, log_args=True)
    @log_performance(threshold_ms=500, logger=logger)
    async def load_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        mode: str = "local",
        validate: bool = True,
        repair: bool = False,
        repair_outliers: bool = True,
        strict: bool = False,
        cancellation_token: Optional[Any] = None,
    ) -> pd.DataFrame:
        """
        Load data with optional validation and repair.

        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'EURUSD')
            timeframe: Timeframe (e.g., '1h', '1d')
            start_date: Optional start date
            end_date: Optional end date
            mode: Loading mode ('local', 'tail', 'backfill', 'full')
            validate: Whether to validate data integrity
            repair: Whether to repair detected issues
            repair_outliers: Whether to repair outliers when repair=True
            strict: If True, raises exception for integrity issues
            cancellation_token: Optional cancellation token

        Returns:
            DataFrame with validated (and optionally repaired) OHLCV data
        """
        logger.info(f"Loading data for {symbol} ({timeframe}) - mode: {mode}")

        if mode == "local":
            # Local-only mode: use basic loader without IB integration
            df = self.data_loader.load(symbol, timeframe, start_date, end_date)
        else:
            # Enhanced modes: use intelligent gap analysis with IB integration
            df = await self._load_with_fallback(
                symbol, timeframe, start_date, end_date, mode, cancellation_token
            )

        # Check if df is None
        if df is None:
            raise DataNotFoundError(
                message=f"Data not found for {symbol} ({timeframe})",
                error_code="DATA-FileNotFound",
                details={"symbol": symbol, "timeframe": timeframe},
            )

        if validate:
            # Validate and repair if requested
            df = await self._validate_and_repair_data(
                df, symbol, timeframe, repair, repair_outliers, strict
            )

        logger.debug(f"Successfully loaded {len(df)} rows for {symbol} ({timeframe})")
        return df

    async def _validate_and_repair_data(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        repair: bool,
        repair_outliers: bool,
        strict: bool,
    ) -> pd.DataFrame:
        """Validate and optionally repair data quality issues."""
        validation_type = "local"

        # Create validator based on repair setting
        if not repair:
            validator = DataQualityValidator(
                auto_correct=False, max_gap_percentage=self.max_gap_percentage
            )
        else:
            validator = self.data_validator

        # Perform validation
        df_validated, quality_report = validator.validate_data(
            df, symbol, timeframe, validation_type
        )

        # Handle repair_outliers parameter
        if repair and not repair_outliers:
            logger.info(
                "Outlier repair was skipped as requested (repair_outliers=False)"
            )

        # Check health based on strict mode
        is_healthy = quality_report.is_healthy(
            max_critical=0, max_high=0 if strict else 5
        )

        if not is_healthy:
            issues_summary = quality_report.get_summary()
            issues_str = f"{issues_summary['total_issues']} issues found"

            if strict:
                logger.error(
                    f"Data quality issues found and strict mode enabled: {issues_str}"
                )
                raise DataCorruptionError(
                    message=f"Data quality issues found: {issues_str}",
                    error_code="DATA-IntegrityIssue",
                    details={
                        "issues": issues_summary,
                        "symbol": symbol,
                        "timeframe": timeframe,
                    },
                )
            else:
                logger.warning(f"Data quality issues found: {issues_str}")
                if repair:
                    df = df_validated
                    logger.info(
                        f"Data repaired: {quality_report.corrections_made} corrections made"
                    )
        else:
            if repair and quality_report.corrections_made > 0:
                df = df_validated
                logger.info(
                    f"Minor corrections applied: {quality_report.corrections_made} corrections made"
                )

        return df

    async def _load_with_fallback(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        mode: str = "tail",
        cancellation_token: Optional[Any] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Load data with intelligent gap analysis and IB integration.

        Enhanced async strategy:
        1. Load existing local data
        2. Perform intelligent gap analysis
        3. Split gaps into IB-compliant segments
        4. Use async IB fetcher to get missing segments
        5. Merge all data sources
        """
        # Normalize and validate date range
        requested_start, requested_end = self._normalize_date_range(
            start_date, end_date, timeframe, mode
        )

        if requested_start >= requested_end:
            logger.warning(
                f"Invalid date range: start {requested_start} >= end {requested_end}"
            )
            return None

        logger.info(
            f"🧠 ASYNC STRATEGY ({mode}): Loading {symbol} {timeframe} from {requested_start} to {requested_end}"
        )

        # Step 0: Validate request against head timestamp
        if await self._should_validate_head_timestamp():
            adjusted_start = await self._validate_against_head_timestamp(
                symbol, timeframe, requested_start, requested_end, cancellation_token
            )
            if adjusted_start is not None:
                requested_start = adjusted_start

        # Step 1: Load existing local data
        existing_data = await self._load_existing_data(
            symbol, timeframe, cancellation_token
        )

        # Step 2: Intelligent gap analysis
        gaps = await self._analyze_gaps(
            existing_data,
            requested_start,
            requested_end,
            timeframe,
            symbol,
            mode,
            cancellation_token,
        )

        if not gaps:
            logger.info("✅ No gaps found - existing data covers requested range!")
            return self._filter_to_range(existing_data, requested_start, requested_end)

        # Step 3: Split gaps into IB-compliant segments
        segments = self._split_into_segments(gaps, timeframe)

        if not segments:
            logger.info("✅ No segments to fetch after filtering")
            return existing_data

        # Step 4: Fetch segments with IB
        fetched_data_frames = await self._fetch_segments_async(
            symbol, timeframe, segments, cancellation_token
        )

        # Step 5: Merge all data sources
        return await self._merge_all_data(
            existing_data,
            fetched_data_frames,
            requested_start,
            requested_end,
            symbol,
            timeframe,
        )

    def _normalize_date_range(
        self,
        start_date: Optional[Union[str, datetime]],
        end_date: Optional[Union[str, datetime]],
        timeframe: str,
        mode: str,
    ) -> Tuple[datetime, datetime]:
        """Normalize and validate date range based on mode."""
        if start_date is None:
            if mode == "tail":
                requested_start = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=30)
            elif mode in ["backfill", "full"]:
                from ktrdr.config.ib_limits import IbLimitsRegistry

                max_duration = IbLimitsRegistry.get_duration_limit(timeframe)
                requested_start = pd.Timestamp.now(tz="UTC") - max_duration
            else:
                requested_start = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=30)
        else:
            requested_start = TimestampManager.to_utc(start_date)

        if end_date is None:
            requested_end = pd.Timestamp.now(tz="UTC")
        else:
            requested_end = TimestampManager.to_utc(end_date)

        return requested_start, requested_end

    async def _should_validate_head_timestamp(self) -> bool:
        """Check if head timestamp validation should be performed."""
        return self.enable_ib and self.ib_symbol_validator is not None

    async def _validate_against_head_timestamp(
        self,
        symbol: str,
        timeframe: str,
        requested_start: datetime,
        requested_end: datetime,
        cancellation_token: Optional[Any],
    ) -> Optional[datetime]:
        """Validate request against head timestamp and return adjusted start if needed."""
        self._check_cancellation(cancellation_token, "head timestamp validation")

        try:
            # Ensure we have head timestamp
            head_timestamp = await self.ib_symbol_validator.fetch_head_timestamp(
                symbol, timeframe
            )

            if head_timestamp:
                # Validate range
                is_valid, error_message, suggested_start = (
                    self.ib_symbol_validator.validate_date_range_against_head_timestamp(
                        symbol, requested_start, timeframe
                    )
                )

                if not is_valid:
                    logger.error(f"📅 Request validation failed: {error_message}")
                    return None
                elif suggested_start:
                    logger.info(
                        f"📅 Request adjusted: {requested_start} → {suggested_start}"
                    )
                    return suggested_start

            return None

        except Exception as e:
            logger.warning(f"Head timestamp validation failed: {e}")
            return None

    async def _load_existing_data(
        self,
        symbol: str,
        timeframe: str,
        cancellation_token: Optional[Any],
    ) -> Optional[pd.DataFrame]:
        """Load existing local data."""
        self._check_cancellation(cancellation_token, "loading existing data")

        try:
            logger.info(f"📁 Loading existing local data for {symbol}")
            existing_data = self.data_loader.load(symbol, timeframe)

            if existing_data is not None and not existing_data.empty:
                existing_data = TimestampManager.convert_dataframe_index(existing_data)
                logger.info(
                    f"✅ Found existing data: {len(existing_data)} bars ({existing_data.index.min()} to {existing_data.index.max()})"
                )
                return existing_data
            else:
                logger.info("📭 No existing local data found")
                return None

        except Exception as e:
            logger.info(f"📭 No existing local data: {e}")
            return None

    async def _analyze_gaps(
        self,
        existing_data: Optional[pd.DataFrame],
        requested_start: datetime,
        requested_end: datetime,
        timeframe: str,
        symbol: str,
        mode: str,
        cancellation_token: Optional[Any],
    ) -> List[Tuple[datetime, datetime]]:
        """Analyze gaps using intelligent gap classification."""
        self._check_cancellation(cancellation_token, "gap analysis")

        logger.info(
            f"🔍 GAP ANALYSIS: Starting intelligent gap detection for {symbol} {timeframe}"
        )

        gaps_to_fill = []

        # If no existing data, entire range is a gap
        if existing_data is None or existing_data.empty:
            logger.info(
                f"No existing data - entire range is a gap: {requested_start} to {requested_end}"
            )
            return [(requested_start, requested_end)]

        # Ensure timezone consistency
        if existing_data.index.tz is None:
            existing_data.index = existing_data.index.tz_localize("UTC")
        elif existing_data.index.tz != requested_start.tzinfo:
            existing_data.index = existing_data.index.tz_convert(requested_start.tzinfo)

        data_start = existing_data.index.min()
        data_end = existing_data.index.max()

        # Find all potential gaps
        all_gaps = []

        # Gap before existing data
        if requested_start < data_start:
            gap_end = min(data_start, requested_end)
            all_gaps.append((requested_start, gap_end))

        # Gap after existing data
        if requested_end > data_end:
            gap_start = max(data_end, requested_start)
            all_gaps.append((gap_start, requested_end))

        # Internal gaps (only for tail mode to avoid micro-analysis)
        if requested_start < data_end and requested_end > data_start and mode == "tail":
            internal_gaps = self._find_internal_gaps(
                existing_data,
                max(requested_start, data_start),
                min(requested_end, data_end),
                timeframe,
            )
            all_gaps.extend(internal_gaps)

        # Use intelligent gap classifier
        for gap_start, gap_end in all_gaps:
            gap_duration = gap_end - gap_start

            # Large gaps (> 7 days) always worth filling
            if gap_duration > timedelta(days=7):
                gaps_to_fill.append((gap_start, gap_end))
                logger.info(f"📍 LARGE GAP TO FILL: {gap_start} → {gap_end}")
            else:
                # Classify smaller gaps
                gap_info = self.gap_classifier.analyze_gap(
                    gap_start, gap_end, symbol, timeframe
                )

                if gap_info.classification in [
                    GapClassification.UNEXPECTED,
                    GapClassification.MARKET_CLOSURE,
                ]:
                    gaps_to_fill.append((gap_start, gap_end))
                    logger.debug(
                        f"📍 UNEXPECTED GAP TO FILL: {gap_start} → {gap_end} ({gap_info.classification.value})"
                    )
                else:
                    logger.debug(
                        f"📅 EXPECTED GAP SKIPPED: {gap_start} → {gap_end} ({gap_info.classification.value})"
                    )

        logger.info(
            f"🔍 INTELLIGENT GAP ANALYSIS: Found {len(gaps_to_fill)} gaps to fill (filtered out {len(all_gaps) - len(gaps_to_fill)} expected gaps)"
        )
        return gaps_to_fill

    def _find_internal_gaps(
        self,
        data: pd.DataFrame,
        range_start: datetime,
        range_end: datetime,
        timeframe: str,
    ) -> List[Tuple[datetime, datetime]]:
        """Find gaps within existing data."""
        gaps = []

        # Filter data to requested range
        mask = (data.index >= range_start) & (data.index <= range_end)
        range_data = data[mask].sort_index()

        if len(range_data) < 2:
            return gaps

        # Calculate expected frequency
        expected_freq = TimeframeConstants.get_pandas_timedelta(timeframe)

        # Look for gaps larger than expected frequency
        for i in range(len(range_data) - 1):
            current_time = range_data.index[i]
            next_time = range_data.index[i + 1]
            gap_size = next_time - current_time

            if gap_size > expected_freq * 1.5:
                gap_start = current_time + expected_freq
                gap_end = next_time
                gaps.append((gap_start, gap_end))

        return gaps

    def _split_into_segments(
        self,
        gaps: List[Tuple[datetime, datetime]],
        timeframe: str,
    ) -> List[Tuple[datetime, datetime]]:
        """Split large gaps into IB-compliant segments."""
        from ktrdr.config.ib_limits import IbLimitsRegistry

        segments = []
        max_duration = IbLimitsRegistry.get_duration_limit(timeframe)

        for gap_start, gap_end in gaps:
            gap_duration = gap_end - gap_start

            if gap_duration <= max_duration:
                segments.append((gap_start, gap_end))
            else:
                # Split into multiple segments
                logger.info(f"Splitting large gap into segments (max: {max_duration})")
                current_start = gap_start
                while current_start < gap_end:
                    segment_end = min(current_start + max_duration, gap_end)
                    segments.append((current_start, segment_end))
                    current_start = segment_end

        logger.info(
            f"⚡ SEGMENTATION: Split {len(gaps)} gaps into {len(segments)} segments"
        )
        return segments

    async def _fetch_segments_async(
        self,
        symbol: str,
        timeframe: str,
        segments: List[Tuple[datetime, datetime]],
        cancellation_token: Optional[Any],
    ) -> List[pd.DataFrame]:
        """Fetch segments using async IB data fetcher."""
        if not self.enable_ib or not self.ib_data_fetcher:
            logger.warning("IB integration not available for segment fetching")
            return []

        successful_data = []
        logger.info(f"Fetching {len(segments)} segments with async resilience")

        for i, (segment_start, segment_end) in enumerate(segments):
            self._check_cancellation(
                cancellation_token, f"segment {i+1}/{len(segments)}"
            )

            try:
                logger.debug(
                    f"🚀 ASYNC IB REQUEST {i+1}/{len(segments)}: {symbol} {timeframe} from {segment_start} to {segment_end}"
                )

                segment_data = await self.ib_data_fetcher.fetch_historical_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    start=segment_start,
                    end=segment_end,
                )

                if segment_data is not None and not segment_data.empty:
                    successful_data.append(segment_data)
                    logger.info(
                        f"✅ ASYNC IB SUCCESS {i+1}: Received {len(segment_data)} bars"
                    )
                else:
                    logger.warning(f"❌ ASYNC IB FAILURE {i+1}: No data returned")

            except Exception as e:
                logger.error(f"❌ ASYNC IB ERROR {i+1}: Request failed - {e}")
                continue

        logger.info(
            f"Async segment fetching complete: {len(successful_data)} successful, {len(segments) - len(successful_data)} failed"
        )
        return successful_data

    def _filter_to_range(
        self,
        data: Optional[pd.DataFrame],
        start: datetime,
        end: datetime,
    ) -> Optional[pd.DataFrame]:
        """Filter data to requested range."""
        if data is None or data.empty:
            return data

        mask = (data.index >= start) & (data.index <= end)
        filtered = data[mask] if mask.any() else data

        logger.info(f"📊 Filtered to range: {len(filtered)} bars")
        return filtered

    async def _merge_all_data(
        self,
        existing_data: Optional[pd.DataFrame],
        fetched_data_frames: List[pd.DataFrame],
        requested_start: datetime,
        requested_end: datetime,
        symbol: str,
        timeframe: str,
    ) -> Optional[pd.DataFrame]:
        """Merge all data sources and return final result."""
        all_data_frames = []

        # Add existing data
        if existing_data is not None and not existing_data.empty:
            all_data_frames.append(existing_data)

        # Add fetched data
        all_data_frames.extend(fetched_data_frames)

        if not all_data_frames:
            logger.warning("❌ No data available from any source")
            return None

        # Combine and sort
        logger.info(f"🔄 Merging {len(all_data_frames)} data sources...")
        combined_data = pd.concat(all_data_frames, ignore_index=False)

        # Remove duplicates and sort
        duplicates_count = combined_data.index.duplicated().sum()
        if duplicates_count > 0:
            logger.info(f"🗑️ Removing {duplicates_count} duplicate timestamps")
        combined_data = combined_data[~combined_data.index.duplicated(keep="last")]
        combined_data = combined_data.sort_index()

        # Filter to requested range
        final_data = self._filter_to_range(
            combined_data, requested_start, requested_end
        )

        if final_data is not None and not final_data.empty:
            logger.info(
                f"📊 Final dataset: {len(final_data)} bars from {final_data.index.min()} to {final_data.index.max()}"
            )

            # Save enhanced dataset if we fetched new data
            if len(fetched_data_frames) > 0:
                try:
                    self.data_loader.save(combined_data, symbol, timeframe)
                    logger.info(f"💾 Saved enhanced dataset: {len(combined_data)} bars")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to save enhanced dataset: {e}")

        return final_data

    # Backward compatibility methods (sync wrappers)
    def load(
        self,
        symbol: str,
        interval: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        days: Optional[int] = None,
        validate: bool = True,
        repair: bool = False,
    ) -> pd.DataFrame:
        """
        Sync wrapper for backward compatibility.

        This method runs the async load_data in a new event loop.
        """
        # Handle days parameter
        if days is not None and end_date is None:
            end_date = TimestampManager.now_utc()

        if days is not None:
            if isinstance(end_date, str):
                end_date = pd.to_datetime(end_date)
            start_date = end_date - timedelta(days=days)

        # Run async method in event loop
        return asyncio.run(
            self.load_data(
                symbol=symbol,
                timeframe=interval,
                start_date=start_date,
                end_date=end_date,
                validate=validate,
                repair=repair,
            )
        )

    # Other methods can be added here as needed for full compatibility

    def get_metrics(self) -> Dict[str, Any]:
        """Get data manager metrics."""
        metrics = {}

        if self.ib_data_fetcher:
            metrics.update(self.ib_data_fetcher.get_metrics())

        if self.ib_symbol_validator:
            metrics.update(self.ib_symbol_validator.get_cache_stats())

        return metrics
