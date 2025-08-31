"""
Data Loading Orchestration Service

Extracted from DataManager's _load_with_fallback method to separate
orchestration logic from primitive data operations.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional, Union

import pandas as pd

from ktrdr.data.loading_modes import DataLoadingMode
from ktrdr.logging import get_logger

logger = get_logger(__name__)


class DataLoadingOrchestrator:
    """
    Orchestrates complex data loading operations extracted from DataManager.
    
    This class handles the _load_with_fallback logic with minimal changes,
    using dependency injection to avoid tight coupling with DataManager.
    """

    def __init__(self, data_manager):
        """Initialize with DataManager reference for access to all methods."""
        self.data_manager = data_manager

    def load_with_fallback(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        mode: str = "tail",
        cancellation_token: Optional[Any] = None,
        progress_manager: Optional[Any] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Load data with intelligent gap analysis and resilient segment fetching.

        ENHANCED STRATEGY:
        1. Load existing local data (fast)
        2. Perform intelligent gap analysis vs requested range
        3. Split gaps into IB-compliant segments
        4. Use "dumb" IbDataLoader to fetch only missing segments
        5. Merge all data sources chronologically
        6. Handle partial failures gracefully

        This replaces the old "naive" approach of fetching entire ranges
        with a smart approach that only fetches missing data segments.

        Args:
            symbol: The trading symbol
            timeframe: The timeframe of the data
            start_date: Optional start date
            end_date: Optional end date
            mode: Loading mode - 'tail' (recent gaps), 'backfill' (historical), 'full' (backfill + tail)

        Returns:
            DataFrame with data or None if no data found
        """
        # Legacy progress parameter removed - using ProgressManager integration

        # Step 1: FAIL FAST - Validate symbol and get metadata FIRST (2%)
        if progress_manager:
            progress_manager.update_progress_with_context(
                1,
                "Validating symbol with IB Gateway",
                current_item_detail=f"Checking if {symbol} is valid and tradeable",
            )

        logger.info("📋 STEP 0A: Symbol validation and metadata lookup")
        self.data_manager._check_cancellation(cancellation_token, "symbol validation")

        validation_result = None
        cached_head_timestamp = None

        if self.data_manager.external_provider:
            try:
                # Simplified async validation call
                async def validate_async():
                    return await self.data_manager.external_provider.validate_and_get_metadata(
                        symbol, [timeframe]
                    )

                validation_result = asyncio.run(validate_async())

                logger.info(f"✅ Symbol {symbol} validated successfully")

                # Cache head timestamp for later use
                if (
                    validation_result.head_timestamps
                    and timeframe in validation_result.head_timestamps
                ):
                    cached_head_timestamp = validation_result.head_timestamps[timeframe]
                    logger.info(
                        f"📅 Cached head timestamp for {symbol} ({timeframe}): {cached_head_timestamp}"
                    )

            except Exception as e:
                logger.error(f"❌ Symbol validation failed for {symbol}: {e}")
                from ktrdr.errors import DataError
                raise DataError(
                    message=f"Symbol validation failed: {e}",
                    error_code="DATA-SymbolValidationFailed",
                    details={"symbol": symbol, "timeframe": timeframe, "error": str(e)},
                ) from e
        else:
            logger.warning("External data provider not available for symbol validation")

        # Step 2: Set intelligent date ranges using head timestamp info
        # ALWAYS respect user-provided dates, but use head timestamp for defaults
        if start_date is None:
            # Default range based on mode and head timestamp
            if mode == "tail":
                # Tail: recent data if no range specified
                requested_start = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=30)
            elif mode == "backfill" or mode == "full":
                # Use head timestamp if available, otherwise fall back to IB limits
                if cached_head_timestamp:
                    normalized_ts = self.data_manager._normalize_timezone(cached_head_timestamp)
                    if normalized_ts is not None:
                        requested_start = normalized_ts
                    logger.info(
                        f"📅 Using head timestamp for default start: {requested_start}"
                    )
                else:
                    # Fallback: go back as far as IB allows for this timeframe
                    from ktrdr.config.ib_limits import IbLimitsRegistry

                    max_duration = IbLimitsRegistry.get_duration_limit(timeframe)
                    requested_start = pd.Timestamp.now(tz="UTC") - max_duration
                    logger.info(
                        f"📅 Using IB duration limit for default start: {requested_start}"
                    )
            else:
                # Other modes: use IB limits
                from ktrdr.config.ib_limits import IbLimitsRegistry

                max_duration = IbLimitsRegistry.get_duration_limit(timeframe)
                requested_start = pd.Timestamp.now(tz="UTC") - max_duration
        else:
            # ALWAYS respect user-provided start_date regardless of mode
            normalized_start = self.data_manager._normalize_timezone(start_date)
            if normalized_start is not None:
                requested_start = normalized_start

        if end_date is None:
            requested_end = pd.Timestamp.now(tz="UTC")
        else:
            # ALWAYS respect user-provided end_date regardless of mode
            normalized_end = self.data_manager._normalize_timezone(end_date)
            if normalized_end is not None:
                requested_end = normalized_end

        if requested_start >= requested_end:
            logger.warning(
                f"Invalid date range: start {requested_start} >= end {requested_end}"
            )
            return None

        logger.info(
            f"🧠 ENHANCED STRATEGY ({mode}): Loading {symbol} {timeframe} from {requested_start} to {requested_end}"
        )

        # Step 2: Validate request range against cached head timestamp (4%)
        if progress_manager:
            progress_manager.start_step(
                "Validate request range", step_number=2, step_percentage=2.0
            )

        logger.info("📅 STEP 0B: Validating request against head timestamp data")
        self.data_manager._check_cancellation(cancellation_token, "head timestamp validation")

        # Use cached head timestamp from validation step if available
        if cached_head_timestamp:
            try:
                # Handle both datetime objects and string timestamps
                if isinstance(cached_head_timestamp, datetime):
                    head_dt = cached_head_timestamp
                    # Ensure timezone awareness
                    if head_dt.tzinfo is None:
                        head_dt = head_dt.replace(tzinfo=timezone.utc)
                else:
                    # Convert ISO timestamp string to datetime for range validation
                    head_dt = datetime.fromisoformat(
                        cached_head_timestamp.replace("Z", "+00:00")
                    )
                    if head_dt.tzinfo is None:
                        head_dt = head_dt.replace(tzinfo=timezone.utc)

                # Check if requested start is before available data
                if requested_start < head_dt:
                    logger.warning(
                        f"📅 Requested start {requested_start} is before available data {head_dt}"
                    )
                    logger.info(
                        f"📅 Adjusting start time to earliest available: {head_dt}"
                    )
                    requested_start = pd.Timestamp(head_dt)

                logger.info("📅 Request range validated against head timestamp")

            except Exception as e:
                logger.warning(
                    f"📅 Failed to parse cached head timestamp {cached_head_timestamp}: {e}"
                )
                # Continue without validation if parsing fails
        else:
            # Fallback to old method if no cached head timestamp
            logger.info("📅 No cached head timestamp, trying fallback method")
            try:
                has_head_timestamp = self.data_manager._ensure_symbol_has_head_timestamp(
                    symbol, timeframe
                )

                if has_head_timestamp:
                    # Validate the request range against head timestamp
                    is_valid, error_message, adjusted_start = (
                        self.data_manager._validate_request_against_head_timestamp(
                            symbol, timeframe, requested_start, requested_end
                        )
                    )

                    if not is_valid:
                        logger.error(f"📅 Request validation failed: {error_message}")
                        logger.error(
                            f"📅 Cannot load data for {symbol} from {requested_start} - data not available"
                        )
                        return None
                    elif adjusted_start:
                        logger.info(
                            f"📅 Request adjusted based on head timestamp: {requested_start} → {adjusted_start}"
                        )
                        requested_start = pd.Timestamp(adjusted_start)
                else:
                    logger.info(
                        f"📅 No head timestamp available for {symbol}, proceeding with original request"
                    )
            except Exception as e:
                logger.warning(f"📅 Fallback head timestamp validation failed: {e}")
                logger.info("📅 Proceeding with original request range")

        # Step 3: Load existing local data (ALL modes need this for gap analysis) (6%)
        if progress_manager:
            progress_manager.start_step(
                "Load existing local data", step_number=3, step_percentage=4.0
            )

        existing_data = None
        try:
            logger.info(f"📁 Loading existing local data for {symbol}")
            self.data_manager._check_cancellation(cancellation_token, "loading existing data")
            existing_data = self.data_manager.data_loader.load(symbol, timeframe)
            if existing_data is not None and not existing_data.empty:
                existing_data = self.data_manager._normalize_dataframe_timezone(existing_data)
                logger.info(
                    f"✅ Found existing data: {len(existing_data)} bars ({existing_data.index.min()} to {existing_data.index.max()})"
                )
            else:
                logger.info("📭 No existing local data found")
        except Exception as e:
            logger.info(f"📭 No existing local data: {e}")
            existing_data = None

        # Step 4: Intelligent gap analysis (8%)
        if progress_manager:
            progress_manager.start_step(
                "Analyze data gaps", step_number=4, step_percentage=6.0
            )

        logger.info(
            f"🔍 GAP ANALYSIS: Starting intelligent gap detection for {symbol} {timeframe}"
        )
        self.data_manager._check_cancellation(cancellation_token, "gap analysis")
        logger.debug(
            f"🔍 GAP ANALYSIS: Requested range = {requested_start} to {requested_end}"
        )
        if existing_data is not None and not existing_data.empty:
            logger.debug(
                f"🔍 GAP ANALYSIS: Existing data range = {existing_data.index.min()} to {existing_data.index.max()}"
            )
        else:
            logger.debug("🔍 GAP ANALYSIS: No existing data found")
        # Convert string mode to DataLoadingMode enum
        loading_mode = DataLoadingMode[mode.upper()] if isinstance(mode, str) else mode
        gaps = self.data_manager.gap_analyzer.analyze_gaps(
            existing_data,
            requested_start,
            requested_end,
            timeframe,
            symbol,
            loading_mode,
        )

        if not gaps:
            logger.info("✅ No gaps found - existing data covers requested range!")
            # Filter existing data to requested range if needed
            if existing_data is not None:
                mask = (existing_data.index >= requested_start) & (
                    existing_data.index <= requested_end
                )
                filtered_data = existing_data[mask] if mask.any() else existing_data
                logger.info(
                    f"📊 Returning {len(filtered_data)} bars from existing data (filtered to requested range)"
                )
                return filtered_data
            return existing_data

        # Step 5: Split gaps into IB-compliant segments (10%)
        if progress_manager:
            progress_manager.start_step(
                "Create IB-compliant segments", step_number=5, step_percentage=8.0
            )

        logger.info(
            f"⚡ SEGMENTATION: Splitting {len(gaps)} gaps into IB-compliant segments..."
        )
        self.data_manager._check_cancellation(cancellation_token, "segmentation")
        segments = self.data_manager.segment_manager.create_segments(
            gaps, DataLoadingMode(mode), timeframe
        )
        logger.info(
            f"⚡ SEGMENTATION COMPLETE: Created {len(segments)} segments for IB fetching"
        )

        if not segments:
            logger.info("✅ No segments to fetch after filtering")
            return existing_data

        # Step 4: Fetch segments via IB fetcher (handles connection issues internally)
        fetched_data_frames = []

        if self.data_manager.external_provider:
            # Step 6: Start segment fetching with expected bars if we can estimate (10% → 96%)
            if progress_manager:
                progress_manager.start_step(
                    f"Fetch {len(segments)} segments from IB",
                    step_number=6,
                    step_percentage=10.0,  # Starts at 10%
                    step_end_percentage=96.0,  # Ends at 96% - this is the big phase!
                    expected_items=None,  # We don't know total bars yet
                )

            logger.info(
                f"🚀 Fetching {len(segments)} segments using resilient strategy..."
            )
            self.data_manager._check_cancellation(cancellation_token, "IB fetch preparation")
            successful_frames, successful_count, failed_count = (
                self.data_manager._fetch_segments_with_component(
                    symbol,
                    timeframe,
                    segments,
                    cancellation_token,
                    progress_manager,
                )
            )
            fetched_data_frames = successful_frames

            if successful_count > 0:
                logger.info(
                    f"✅ Successfully fetched {successful_count}/{len(segments)} segments"
                )
            if failed_count > 0:
                logger.warning(
                    f"⚠️ {failed_count}/{len(segments)} segments failed - continuing with partial data"
                )

                # Check if complete IB failure should fail the operation for certain modes
                if successful_count == 0 and mode in ["full", "tail", "backfill"]:
                    # All IB segments failed and mode requires fresh data
                    if mode == "full":
                        error_msg = f"Complete IB failure in 'full' mode - all {failed_count} segments failed. Cannot provide fresh data."
                    elif mode == "tail":
                        error_msg = f"Complete IB failure in 'tail' mode - all {failed_count} segments failed. Cannot provide recent data."
                    elif mode == "backfill":
                        error_msg = f"Complete IB failure in 'backfill' mode - all {failed_count} segments failed. Cannot provide historical data."

                    logger.error(f"❌ {error_msg}")

                    # For modes that require IB data, complete failure should fail the operation
                    # instead of returning stale cached data
                    from ktrdr.errors import DataError
                    raise DataError(
                        message=error_msg,
                        error_code="DATA-IBCompleteFail",
                        details={
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "mode": mode,
                            "failed_segments": failed_count,
                            "successful_segments": successful_count,
                        },
                    )
        else:
            logger.info("ℹ️ IB fetching disabled - using existing data only")

        # Step 7: Merge all data sources (96% → 98%)
        if progress_manager:
            progress_manager.start_step(
                "Merge data sources", step_number=7, step_percentage=96.0
            )

        all_data_frames = []

        # Add existing data if available
        if existing_data is not None and not existing_data.empty:
            all_data_frames.append(existing_data)

        # Add fetched data
        all_data_frames.extend(fetched_data_frames)

        if not all_data_frames:
            logger.warning("❌ No data available from any source")
            return None

        # Combine and sort all data
        logger.info(f"🔄 Merging {len(all_data_frames)} data sources...")

        # Log details about each data source for debugging
        for i, df in enumerate(all_data_frames):
            if not df.empty:
                logger.debug(
                    f"📊 Data source {i+1}: {len(df)} bars from {df.index.min()} to {df.index.max()}"
                )
            else:
                logger.debug(f"📊 Data source {i+1}: EMPTY DataFrame")

        combined_data = pd.concat(all_data_frames, ignore_index=False)
        logger.info(f"🔗 After concat: {len(combined_data)} total bars")

        # Remove duplicates and sort
        duplicates_count = combined_data.index.duplicated().sum()
        if duplicates_count > 0:
            logger.info(f"🗑️ Removing {duplicates_count} duplicate timestamps")
        combined_data = combined_data[~combined_data.index.duplicated(keep="last")]
        combined_data = combined_data.sort_index()
        logger.info(f"✅ After deduplication and sorting: {len(combined_data)} bars")

        # Filter to requested range
        mask = (combined_data.index >= requested_start) & (
            combined_data.index <= requested_end
        )
        final_data = combined_data[mask] if mask.any() else combined_data

        logger.info(
            f"📊 Final dataset: {len(final_data)} bars covering {final_data.index.min() if not final_data.empty else 'N/A'} to {final_data.index.max() if not final_data.empty else 'N/A'}"
        )

        # Step 8: Save the enhanced dataset back to CSV for future use (98%)
        if progress_manager:
            progress_manager.start_step(
                "Save enhanced dataset", step_number=8, step_percentage=98.0
            )

        if len(fetched_data_frames) > 0:  # Only save if we fetched new data
            try:
                self.data_manager.data_loader.save(combined_data, symbol, timeframe)
                logger.info(f"💾 Saved enhanced dataset: {len(combined_data)} bars")
            except Exception as e:
                logger.warning(f"⚠️ Failed to save enhanced dataset: {e}")

        # Step 9: Data loading completed (100%)
        if progress_manager:
            progress_manager.start_step(
                "Data loading completed", step_number=9, step_percentage=100.0
            )

        logger.info(f"🎉 ENHANCED STRATEGY COMPLETE: Returning {len(final_data)} bars")
        return final_data