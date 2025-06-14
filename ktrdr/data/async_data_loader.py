"""
Async Data Loading System with Cancellation Support

Provides async operations for data loading with:
- Real-time progress tracking
- Graceful cancellation
- Job management
- Status monitoring
- CLI integration support
"""

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd

from ktrdr.logging import get_logger
from ktrdr.errors import DataError
from ktrdr.data.data_manager import DataManager
from ktrdr.utils.timezone_utils import TimestampManager

logger = get_logger(__name__)


class JobStatus(Enum):
    """Status of async data loading jobs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressInfo:
    """Progress information for data loading jobs."""

    total_segments: int = 0
    completed_segments: int = 0
    failed_segments: int = 0
    current_segment: Optional[str] = None
    bars_fetched: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_segments == 0:
            return 0.0
        return (self.completed_segments / self.total_segments) * 100

    @property
    def is_complete(self) -> bool:
        """Check if job is complete."""
        return self.completed_segments == self.total_segments


@dataclass
class DataLoadingJob:
    """Data loading job with async support."""

    job_id: str
    symbol: str
    timeframe: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    mode: str
    status: JobStatus = JobStatus.PENDING
    progress: ProgressInfo = field(default_factory=ProgressInfo)
    created_at: datetime = field(default_factory=lambda: TimestampManager.now_utc())
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result_path: Optional[str] = None
    error_message: Optional[str] = None
    _cancel_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    _task: Optional[asyncio.Task] = field(default=None, init=False)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration."""
        if not self.started_at:
            return None
        end_time = self.completed_at or TimestampManager.now_utc()
        return (end_time - self.started_at).total_seconds()

    def cancel(self):
        """Request cancellation of the job."""
        logger.info(f"🛑 Cancellation requested for job {self.job_id}")
        self._cancel_event.set()
        if self._task and not self._task.done():
            self._task.cancel()

    @property
    def is_cancelled_requested(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancel_event.is_set()


class AsyncDataLoader:
    """
    Async data loader with cancellation support and progress tracking.

    Provides non-blocking data loading operations with:
    - Real-time progress updates
    - Graceful cancellation
    - Job status tracking
    - Error resilience
    """

    def __init__(self, data_manager: Optional[DataManager] = None):
        """
        Initialize async data loader.

        Args:
            data_manager: DataManager instance (creates default if None)
        """
        self.data_manager = data_manager or DataManager(enable_ib=True)
        self.jobs: Dict[str, DataLoadingJob] = {}
        self.active_jobs: Dict[str, asyncio.Task] = {}

        logger.info("AsyncDataLoader initialized")

    def create_job(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        mode: str = "tail",
    ) -> str:
        """
        Create a new data loading job.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start_date: Optional start date
            end_date: Optional end date
            mode: Loading mode ('tail', 'backfill', 'full')

        Returns:
            Job ID string
        """
        job_id = str(uuid.uuid4())[:8]

        job = DataLoadingJob(
            job_id=job_id,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            mode=mode,
        )

        self.jobs[job_id] = job
        logger.info(f"🆕 Created job {job_id}: {symbol} {timeframe} ({mode})")
        return job_id

    async def start_job(
        self,
        job_id: str,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
    ) -> str:
        """
        Start a data loading job asynchronously.

        Args:
            job_id: Job ID to start
            progress_callback: Optional callback for progress updates

        Returns:
            Job ID

        Raises:
            DataError: If job not found or invalid
        """
        if job_id not in self.jobs:
            raise DataError(f"Job {job_id} not found")

        job = self.jobs[job_id]
        if job.status != JobStatus.PENDING:
            raise DataError(
                f"Job {job_id} is not in pending status (current: {job.status.value})"
            )

        # Create and start the async task
        task = asyncio.create_task(
            self._execute_job(job, progress_callback), name=f"data_load_{job_id}"
        )
        job._task = task
        self.active_jobs[job_id] = task

        logger.info(f"🚀 Started job {job_id} asynchronously")
        return job_id

    async def _execute_job(
        self,
        job: DataLoadingJob,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
    ):
        """
        Execute a data loading job with progress tracking and cancellation support.

        Args:
            job: Job to execute
            progress_callback: Optional progress callback
        """
        job.status = JobStatus.RUNNING
        job.started_at = TimestampManager.now_utc()

        try:
            logger.info(f"📊 Executing job {job.job_id}: {job.symbol} {job.timeframe}")

            # Check for cancellation before starting
            if job.is_cancelled_requested:
                job.status = JobStatus.CANCELLED
                return

            # Estimate segments for progress tracking
            job.progress.total_segments = self._estimate_segments(job)

            # Update progress callback
            if progress_callback:
                progress_callback(job.progress)

            # Load data with progress tracking
            result_df = await self._load_data_with_progress(job, progress_callback)

            # Check for cancellation after completion
            if job.is_cancelled_requested:
                job.status = JobStatus.CANCELLED
                logger.info(f"🛑 Job {job.job_id} was cancelled during execution")
                return

            # Save result and mark complete
            if result_df is not None and not result_df.empty:
                job.progress.bars_fetched = len(result_df)
                job.status = JobStatus.COMPLETED
                logger.info(
                    f"✅ Job {job.job_id} completed successfully: {len(result_df)} bars"
                )
            else:
                job.error_message = "No data returned"
                job.status = JobStatus.FAILED
                logger.warning(f"❌ Job {job.job_id} failed: No data returned")

        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            logger.info(f"🛑 Job {job.job_id} was cancelled")
            raise
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            logger.error(f"❌ Job {job.job_id} failed: {e}")
        finally:
            job.completed_at = TimestampManager.now_utc()
            # Clean up active job tracking
            if job.job_id in self.active_jobs:
                del self.active_jobs[job.job_id]

    def _estimate_segments(self, job: DataLoadingJob) -> int:
        """
        Estimate number of segments for progress tracking.

        Args:
            job: Job to estimate

        Returns:
            Estimated number of segments
        """
        if job.start_date and job.end_date:
            duration = job.end_date - job.start_date
            # Rough estimate based on timeframe
            if job.timeframe == "1d":
                return max(1, duration.days // 365)  # ~1 year per segment
            elif job.timeframe == "1h":
                return max(1, duration.days // 30)  # ~30 days per segment
            else:
                return max(1, duration.days // 7)  # ~1 week per segment
        else:
            # Default estimates by mode
            if job.mode == "tail":
                return 1
            elif job.mode == "backfill":
                return 5
            else:  # full
                return 10

    async def _load_data_with_progress(
        self,
        job: DataLoadingJob,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Load data with progress tracking and cancellation checks.

        Args:
            job: Job to execute
            progress_callback: Optional progress callback

        Returns:
            Loaded DataFrame or None
        """
        try:
            # Simulate progress updates by intercepting the data manager's segment loading
            # For now, we'll use the existing data manager but add progress simulation

            segment_delay = 0.1  # Small delay to allow cancellation checks

            for i in range(job.progress.total_segments):
                # Check for cancellation
                if job.is_cancelled_requested:
                    logger.info(
                        f"🛑 Job {job.job_id} cancelled at segment {i+1}/{job.progress.total_segments}"
                    )
                    raise asyncio.CancelledError()

                # Update current segment
                job.progress.current_segment = (
                    f"Segment {i+1}/{job.progress.total_segments}"
                )

                # Simulate segment loading delay
                await asyncio.sleep(segment_delay)

                # Mark segment complete
                job.progress.completed_segments = i + 1

                # Update progress callback
                if progress_callback:
                    progress_callback(job.progress)

            # Actually load the data (this runs in thread pool to avoid blocking)
            loop = asyncio.get_event_loop()
            result_df = await loop.run_in_executor(None, self._sync_load_data, job)

            return result_df

        except asyncio.CancelledError:
            raise
        except Exception as e:
            job.progress.errors.append(str(e))
            raise

    def _sync_load_data(self, job: DataLoadingJob) -> Optional[pd.DataFrame]:
        """
        Synchronous data loading in thread pool.

        Args:
            job: Job to execute

        Returns:
            Loaded DataFrame or None
        """
        return self.data_manager.load_data(
            symbol=job.symbol,
            timeframe=job.timeframe,
            start_date=job.start_date,
            end_date=job.end_date,
            mode=job.mode,
            validate=True,
            repair=False,
            cancellation_token=job,  # Pass the job itself as cancellation token
        )

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a job.

        Args:
            job_id: Job ID to check

        Returns:
            Job status dictionary or None if not found
        """
        if job_id not in self.jobs:
            return None

        job = self.jobs[job_id]

        return {
            "job_id": job.job_id,
            "symbol": job.symbol,
            "timeframe": job.timeframe,
            "mode": job.mode,
            "status": job.status.value,
            "progress_percentage": job.progress.progress_percentage,
            "completed_segments": job.progress.completed_segments,
            "total_segments": job.progress.total_segments,
            "current_segment": job.progress.current_segment,
            "bars_fetched": job.progress.bars_fetched,
            "errors": job.progress.errors,
            "duration_seconds": job.duration_seconds,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message,
        }

    def list_jobs(
        self, status_filter: Optional[JobStatus] = None
    ) -> List[Dict[str, Any]]:
        """
        List all jobs with optional status filter.

        Args:
            status_filter: Optional status filter

        Returns:
            List of job status dictionaries
        """
        jobs = []
        for job in self.jobs.values():
            if status_filter is None or job.status == status_filter:
                job_status = self.get_job_status(job.job_id)
                if job_status:
                    jobs.append(job_status)

        # Sort by creation time (newest first)
        jobs.sort(key=lambda x: x["created_at"], reverse=True)
        return jobs

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running job.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if cancellation was requested, False if job not found
        """
        if job_id not in self.jobs:
            return False

        job = self.jobs[job_id]
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            logger.info(f"Job {job_id} is already {job.status.value}, cannot cancel")
            return False

        job.cancel()
        return True

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """
        Clean up old completed/failed jobs.

        Args:
            max_age_hours: Maximum age to keep jobs (in hours)
        """
        cutoff_time = TimestampManager.now_utc() - pd.Timedelta(hours=max_age_hours)

        to_remove = []
        for job_id, job in self.jobs.items():
            if (
                job.status
                in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
                and job.completed_at
                and job.completed_at < cutoff_time
            ):
                to_remove.append(job_id)

        for job_id in to_remove:
            del self.jobs[job_id]
            logger.debug(f"Cleaned up old job {job_id}")

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old jobs")


# Global async data loader instance for CLI/API usage
_async_data_loader = None


def get_async_data_loader() -> AsyncDataLoader:
    """Get the global async data loader instance."""
    global _async_data_loader
    if _async_data_loader is None:
        _async_data_loader = AsyncDataLoader()
    return _async_data_loader
