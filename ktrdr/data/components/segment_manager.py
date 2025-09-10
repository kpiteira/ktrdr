"""
SegmentManager Component

Extracted segmentation logic from DataManager to provide dedicated segment creation,
prioritization, and fetching capabilities for optimal IB Gateway communication.

This component handles:
- Breaking large gaps into IB-compliant segments
- Mode-specific segment sizing strategies
- Segment prioritization for efficient fetching
- Resilient segment fetching with retries and progress tracking
- Periodic data saving during long operations
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Callable, Optional

import pandas as pd

from ktrdr.config.ib_limits import IbLimitsRegistry
from ktrdr.data.components.progress_manager import ProgressManager
from ktrdr.data.loading_modes import DataLoadingMode
from ktrdr.logging import get_logger

logger = get_logger(__name__)


class SegmentManager:
    """
    Component for managing data request segmentation and fetching.

    Provides segmentation functionality extracted from DataManager
    with support for mode-specific sizing and prioritization strategies.
    """

    def __init__(self):
        """Initialize the SegmentManager."""
        self.current_mode: Optional[DataLoadingMode] = None

    def _is_cancelled(self, cancellation_token: Any) -> bool:
        """Check if cancellation token is cancelled using unified protocol."""
        if cancellation_token is None:
            return False

        try:
            return cancellation_token.is_cancelled()
        except Exception as e:
            logger.warning(f"Error checking cancellation token: {e}")
            return False

    def create_segments(
        self,
        gaps: list[tuple[datetime, datetime]],
        mode: DataLoadingMode,
        timeframe: str,
    ) -> list[tuple[datetime, datetime]]:
        """
        Split large gaps into IB-compliant segments.

        Takes gaps that might exceed IB duration limits and splits them
        into smaller segments that can be fetched individually.

        Args:
            gaps: List of gaps to potentially split
            mode: Data loading mode (stored for context but doesn't affect segmentation)
            timeframe: Data timeframe for limit checking

        Returns:
            List of segments ready for IB fetching
        """
        if not gaps:
            return []

        self.current_mode = mode
        segments = []

        # Get IB duration limit for this timeframe
        max_duration = IbLimitsRegistry.get_duration_limit(timeframe)

        for gap_start, gap_end in gaps:
            gap_duration = gap_end - gap_start

            if gap_duration <= max_duration:
                # Gap fits in single request
                segments.append((gap_start, gap_end))
                logger.debug(
                    f"Gap fits in single segment: {gap_start} to {gap_end} ({gap_duration})"
                )
            else:
                # Split into multiple segments
                logger.info(
                    f"Splitting large gap {gap_start} to {gap_end} ({gap_duration}) into segments (max: {max_duration})"
                )

                current_start = gap_start
                while current_start < gap_end:
                    segment_end = min(current_start + max_duration, gap_end)
                    segments.append((current_start, segment_end))
                    logger.debug(f"Created segment: {current_start} to {segment_end}")
                    current_start = segment_end

        logger.info(
            f"⚡ SEGMENTATION: Split {len(gaps)} gaps into {len(segments)} IB-compliant segments"
        )
        for i, (seg_start, seg_end) in enumerate(segments):
            duration = seg_end - seg_start
            logger.debug(
                f"🔷 SEGMENT {i + 1}: {seg_start} → {seg_end} (duration: {duration})"
            )
        return segments

    def prioritize_segments(
        self,
        segments: list[tuple[datetime, datetime]],
        mode: DataLoadingMode,
    ) -> list[tuple[datetime, datetime]]:
        """
        Prioritize segments for optimal fetching order based on mode.

        Args:
            segments: List of segments to prioritize
            mode: Data loading mode for prioritization strategy

        Returns:
            Segments ordered by priority (highest priority first)
        """
        if not segments:
            return segments

        if mode == DataLoadingMode.TAIL:
            # Tail mode: Most recent first (descending by start time)
            return sorted(segments, key=lambda seg: seg[0], reverse=True)

        elif mode == DataLoadingMode.BACKFILL:
            # Backfill mode: Oldest first (ascending by start time)
            return sorted(segments, key=lambda seg: seg[0])

        elif mode == DataLoadingMode.FULL:
            # Full mode: Balanced approach - alternate between recent and old
            sorted_segments = sorted(segments, key=lambda seg: seg[0])
            if len(sorted_segments) <= 2:
                return sorted_segments

            # Interleave recent and old segments
            recent_segments = sorted_segments[len(sorted_segments) // 2 :]
            old_segments = sorted_segments[: len(sorted_segments) // 2]

            prioritized = []
            for i in range(max(len(recent_segments), len(old_segments))):
                if i < len(recent_segments):
                    prioritized.append(
                        recent_segments[-(i + 1)]
                    )  # Most recent first from recent
                if i < len(old_segments):
                    prioritized.append(old_segments[i])  # Oldest first from old

            return prioritized

        else:
            # Local mode or default: Keep original order
            return segments

    def estimate_segment_time(
        self,
        segment: tuple[datetime, datetime],
        timeframe: str,
    ) -> float:
        """
        Estimate fetch time for a segment based on timeframe and duration.

        Args:
            segment: Segment start and end times
            timeframe: Data timeframe

        Returns:
            Estimated fetch time in seconds
        """
        start, end = segment
        duration = end - start

        # Base estimates in seconds per day of data
        # These are rough estimates based on IB Gateway performance
        timeframe_multipliers = {
            "1m": 3.0,  # 1-minute data takes longer due to volume
            "5m": 2.0,  # 5-minute data
            "15m": 1.5,  # 15-minute data
            "1h": 1.0,  # 1-hour data (baseline)
            "1d": 0.5,  # Daily data is fastest
        }

        base_time_per_day = timeframe_multipliers.get(timeframe, 1.0)
        duration_days = duration.total_seconds() / (24 * 3600)

        estimated_time = duration_days * base_time_per_day

        # Add base overhead for IB communication
        return max(estimated_time, 0.5)  # Minimum 0.5 seconds per segment

    async def handle_segment_retry(
        self,
        failed_segment: tuple[datetime, datetime],
        retry_count: int,
        symbol: str,
        timeframe: str,
        external_provider: Any,
        max_retries: int = 3,
    ) -> Optional[pd.DataFrame]:
        """
        Handle retry logic for failed segment fetches.

        Args:
            failed_segment: The segment that failed to fetch
            retry_count: Current retry attempt number
            symbol: Trading symbol
            timeframe: Data timeframe
            external_provider: IB data provider instance
            max_retries: Maximum number of retries

        Returns:
            DataFrame with fetched data or None if max retries exceeded
        """
        if retry_count >= max_retries:
            logger.warning(
                f"Max retries ({max_retries}) exceeded for segment {failed_segment[0]} to {failed_segment[1]}"
            )
            return None

        start, end = failed_segment

        # Exponential backoff with jitter
        delay = min(2**retry_count + 0.5, 10)  # Cap at 10 seconds
        logger.info(
            f"Retrying segment fetch (attempt {retry_count + 1}/{max_retries}) after {delay}s delay"
        )
        await asyncio.sleep(delay)

        try:
            data = await external_provider.fetch_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start=start,
                end=end,
                instrument_type=None,  # Auto-detect
            )

            if data is not None and not data.empty:
                logger.info(f"✅ Retry successful for segment {start} to {end}")
                return data
            else:
                logger.warning(
                    f"❌ Retry returned empty data for segment {start} to {end}"
                )
                return None

        except Exception as e:
            logger.error(f"❌ Retry failed for segment {start} to {end}: {e}")
            return None

    async def fetch_segments_with_resilience(
        self,
        symbol: str,
        timeframe: str,
        segments: list[tuple[datetime, datetime]],
        external_provider: Any,
        cancellation_token: Optional[Any] = None,
        progress_manager: Optional[ProgressManager] = None,
        periodic_save_callback: Optional[Callable[[list[pd.DataFrame]], int]] = None,
        periodic_save_minutes: float = 0.5,
    ) -> tuple[list[pd.DataFrame], int, int]:
        """
        Fetch multiple segments with failure resilience and periodic progress saves.

        Attempts to fetch each segment individually, continuing with other segments
        if some fail. This ensures partial success rather than complete failure.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            segments: List of (start, end) segments to fetch
            external_provider: IB data provider instance
            cancellation_token: Optional cancellation token
            progress_manager: Optional progress manager for reporting
            periodic_save_callback: Optional callback for periodic saves
            periodic_save_minutes: Save progress every N minutes (default: 0.5)

        Returns:
            Tuple of (successful_dataframes, successful_count, failed_count)
        """
        successful_data: list[pd.DataFrame] = []
        successful_count = 0
        failed_count = 0

        if not external_provider:
            logger.warning("External data provider not available for segment fetching")
            return successful_data, successful_count, len(segments)

        logger.info(f"Fetching {len(segments)} segments with failure resilience")

        # Periodic save tracking
        last_save_time = time.time()
        save_interval_seconds = periodic_save_minutes * 60
        total_bars_saved = 0

        if periodic_save_callback:
            logger.info(
                f"💾 Periodic saves enabled: every {periodic_save_minutes} minutes"
            )

        for i, (segment_start, segment_end) in enumerate(segments):
            # Check for cancellation before each segment
            self._check_cancellation(
                cancellation_token, f"segment {i + 1}/{len(segments)}"
            )

            # Update progress for current segment
            if progress_manager:
                segment_detail = f"Segment {i + 1}/{len(segments)}: {segment_start.strftime('%Y-%m-%d %H:%M')} to {segment_end.strftime('%Y-%m-%d %H:%M')}"
                progress_manager.update_step_progress(
                    current=i + 1,
                    total=len(segments),
                    items_processed=total_bars_saved,
                    detail=segment_detail,
                )

            try:
                duration = segment_end - segment_start
                logger.info(
                    f"🚀 IB REQUEST {i + 1}/{len(segments)}: Fetching {symbol} {timeframe} "
                    f"from {segment_start} to {segment_end} (duration: {duration})"
                )

                segment_data = await self._fetch_single_segment(
                    symbol=symbol,
                    timeframe=timeframe,
                    start=segment_start,
                    end=segment_end,
                    external_provider=external_provider,
                    cancellation_token=cancellation_token,
                )

                if segment_data is not None and not segment_data.empty:
                    successful_data.append(segment_data)
                    successful_count += 1
                    logger.info(
                        f"✅ IB SUCCESS {i + 1}: Received {len(segment_data)} bars from IB"
                    )

                    # Update progress with successful segment completion
                    if progress_manager:
                        total_items_processed = sum(len(df) for df in successful_data)
                        progress_manager.update_step_progress(
                            current=successful_count,
                            total=len(segments),
                            items_processed=total_items_processed,
                            detail=f"✅ Loaded {len(segment_data)} bars from segment {i + 1}/{len(segments)}",
                        )

                    # Periodic save: Check if it's time to save progress
                    if periodic_save_callback:
                        current_time = time.time()
                        time_since_last_save = current_time - last_save_time

                        if (
                            time_since_last_save >= save_interval_seconds
                            or i == len(segments) - 1
                        ):
                            try:
                                if successful_data:
                                    bars_to_save = periodic_save_callback(
                                        successful_data
                                    )
                                    total_bars_saved += bars_to_save
                                    last_save_time = current_time

                                    logger.info(
                                        f"💾 Progress saved: {bars_to_save:,} new bars "
                                        f"({total_bars_saved:,} total) after {time_since_last_save / 60:.1f} minutes"
                                    )

                                    if progress_manager:
                                        progress_manager.update_step_progress(
                                            current=i + 1,
                                            total=len(segments),
                                            items_processed=total_bars_saved,
                                            detail=f"💾 Saved {total_bars_saved:,} bars to CSV",
                                        )
                            except Exception as e:
                                logger.warning(
                                    f"⚠️ Failed to save periodic progress: {e}"
                                )
                else:
                    failed_count += 1
                    logger.warning(f"❌ IB FAILURE {i + 1}: No data returned from IB")

            except asyncio.CancelledError:
                logger.info(
                    f"🛑 Segment fetching cancelled at segment {i + 1}/{len(segments)}"
                )
                break
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ IB ERROR {i + 1}: Request failed - {e}")
                continue

        # Check if operation was cancelled
        was_cancelled = self._is_cancelled(cancellation_token)

        if was_cancelled:
            logger.info(
                f"🛑 Segment fetching cancelled after {successful_count} successful segments"
            )
            raise asyncio.CancelledError(
                f"Data loading cancelled during segment {successful_count + 1}"
            )
        else:
            logger.info(
                f"Segment fetching complete: {successful_count} successful, {failed_count} failed"
            )

        return successful_data, successful_count, failed_count

    async def _fetch_single_segment(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        external_provider: Any,
        cancellation_token: Optional[Any] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch a single segment with cancellation support.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start: Start datetime
            end: End datetime
            external_provider: IB data provider instance
            cancellation_token: Optional cancellation token

        Returns:
            DataFrame with fetched data or None if failed
        """
        # Check for cancellation before expensive operation
        if self._is_cancelled(cancellation_token):
            logger.info(f"🛑 Cancellation detected before IB fetch for {symbol}")
            return None

        # Create a cancellable fetch task with polling
        fetch_task = asyncio.create_task(
            external_provider.fetch_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start=start,
                end=end,
                instrument_type=None,  # Auto-detect
            )
        )

        # Poll for cancellation every 0.5 seconds
        while not fetch_task.done():
            # Check cancellation token
            if self._is_cancelled(cancellation_token):
                logger.info(f"🛑 Cancelling IB fetch for {symbol} during operation")
                fetch_task.cancel()
                try:
                    await fetch_task
                except asyncio.CancelledError:
                    pass
                raise asyncio.CancelledError("Operation cancelled during IB fetch")

            # Wait up to 0.5 seconds for fetch completion
            try:
                await asyncio.wait_for(asyncio.shield(fetch_task), timeout=0.5)
                break
            except asyncio.TimeoutError:
                continue

        return await fetch_task

    def _check_cancellation(self, cancellation_token: Optional[Any], context: str = ""):
        """
        Check for cancellation and raise CancelledError if detected.

        Args:
            cancellation_token: Optional cancellation token
            context: Context string for logging

        Raises:
            asyncio.CancelledError: If cancellation is detected
        """
        if self._is_cancelled(cancellation_token):
            logger.info(
                f"🛑 Cancellation detected{' during ' + context if context else ''}"
            )
            raise asyncio.CancelledError(
                f"Operation cancelled{' during ' + context if context else ''}"
            )
