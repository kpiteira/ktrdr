"""
IB Download Resume Handler for interrupted fetches.

This module provides functionality to resume interrupted downloads and
track progress for large historical data requests.
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from pathlib import Path

from ktrdr.logging import get_logger
from ktrdr.errors import DataError
from ktrdr.data.ib_data_fetcher_sync import IbDataFetcherSync

logger = get_logger(__name__)


@dataclass
class DownloadChunk:
    """
    Represents a chunk of data to be downloaded.

    Attributes:
        symbol: Symbol to download
        timeframe: Timeframe string
        start_date: Start date for chunk
        end_date: End date for chunk
        status: Chunk status (pending, in_progress, completed, failed)
        attempt_count: Number of download attempts
        last_attempt: Timestamp of last attempt
        error_message: Error message if failed
        bars_count: Number of bars downloaded (if completed)
    """

    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    status: str = "pending"  # pending, in_progress, completed, failed
    attempt_count: int = 0
    last_attempt: Optional[float] = None
    error_message: Optional[str] = None
    bars_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        data["start_date"] = self.start_date.isoformat()
        data["end_date"] = self.end_date.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DownloadChunk":
        """Create from dictionary (JSON deserialization)."""
        # Convert ISO strings back to datetime objects
        data["start_date"] = datetime.fromisoformat(data["start_date"])
        data["end_date"] = datetime.fromisoformat(data["end_date"])
        return cls(**data)


@dataclass
class DownloadSession:
    """
    Represents a complete download session that can be resumed.

    Attributes:
        session_id: Unique identifier for this download session
        symbol: Symbol being downloaded
        timeframe: Timeframe string
        full_start_date: Original start date requested
        full_end_date: Original end date requested
        chunks: List of download chunks
        created_at: When session was created
        updated_at: When session was last updated
        status: Overall session status
        total_bars: Total bars downloaded so far
        progress_callback: Optional callback for progress updates
    """

    session_id: str
    symbol: str
    timeframe: str
    full_start_date: datetime
    full_end_date: datetime
    chunks: List[DownloadChunk]
    created_at: float
    updated_at: float
    status: str = "pending"  # pending, in_progress, completed, failed, cancelled
    total_bars: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "full_start_date": self.full_start_date.isoformat(),
            "full_end_date": self.full_end_date.isoformat(),
            "chunks": [chunk.to_dict() for chunk in self.chunks],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "total_bars": self.total_bars,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DownloadSession":
        """Create from dictionary (JSON deserialization)."""
        data["full_start_date"] = datetime.fromisoformat(data["full_start_date"])
        data["full_end_date"] = datetime.fromisoformat(data["full_end_date"])
        data["chunks"] = [DownloadChunk.from_dict(chunk) for chunk in data["chunks"]]
        return cls(**data)

    def get_progress_percentage(self) -> float:
        """Get completion percentage (0-100)."""
        if not self.chunks:
            return 0.0

        completed_chunks = sum(
            1 for chunk in self.chunks if chunk.status == "completed"
        )
        return (completed_chunks / len(self.chunks)) * 100

    def get_remaining_chunks(self) -> List[DownloadChunk]:
        """Get chunks that still need to be downloaded."""
        return [chunk for chunk in self.chunks if chunk.status in ["pending", "failed"]]

    def get_completed_chunks(self) -> List[DownloadChunk]:
        """Get successfully completed chunks."""
        return [chunk for chunk in self.chunks if chunk.status == "completed"]


class IbResumeHandler:
    """
    Handles resumable downloads for IB historical data fetching.

    This class manages download sessions, tracks progress, and enables
    resumption of interrupted downloads.
    """

    def __init__(
        self, data_fetcher: IbDataFetcherSync, progress_dir: Optional[str] = None
    ):
        """
        Initialize resume handler.

        Args:
            data_fetcher: IB data fetcher instance
            progress_dir: Directory to store progress files (default: .ktrdr/downloads)
        """
        self.data_fetcher = data_fetcher

        # Set up progress directory
        if progress_dir is None:
            progress_dir = os.path.expanduser("~/.ktrdr/downloads")

        self.progress_dir = Path(progress_dir)
        self.progress_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file = self.progress_dir / "progress.json"

        # Load existing sessions
        self.sessions: Dict[str, DownloadSession] = {}
        self._load_sessions()

        logger.info(
            f"IbResumeHandler initialized with progress dir: {self.progress_dir}"
        )

    def _load_sessions(self):
        """Load existing download sessions from disk."""
        try:
            if self.progress_file.exists():
                with open(self.progress_file, "r") as f:
                    data = json.load(f)

                for session_data in data.get("sessions", []):
                    session = DownloadSession.from_dict(session_data)
                    self.sessions[session.session_id] = session

                logger.info(f"Loaded {len(self.sessions)} existing download sessions")
            else:
                logger.debug("No existing progress file found")

        except Exception as e:
            logger.error(f"Error loading download sessions: {e}")
            self.sessions = {}

    def _save_sessions(self):
        """Save download sessions to disk."""
        try:
            data = {
                "sessions": [session.to_dict() for session in self.sessions.values()],
                "last_updated": time.time(),
            }

            with open(self.progress_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved {len(self.sessions)} download sessions")

        except Exception as e:
            logger.error(f"Error saving download sessions: {e}")

    def _generate_session_id(
        self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime
    ) -> str:
        """Generate unique session ID."""
        timestamp = int(time.time())
        return f"{symbol}_{timeframe}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}_{timestamp}"

    def _split_into_chunks(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        chunk_size_days: int = 30,
    ) -> List[DownloadChunk]:
        """
        Split large date range into manageable chunks.

        Args:
            symbol: Symbol to download
            timeframe: Timeframe string
            start_date: Start date
            end_date: End date
            chunk_size_days: Size of each chunk in days

        Returns:
            List of download chunks
        """
        chunks = []
        current_start = start_date

        while current_start < end_date:
            current_end = min(current_start + timedelta(days=chunk_size_days), end_date)

            chunk = DownloadChunk(
                symbol=symbol,
                timeframe=timeframe,
                start_date=current_start,
                end_date=current_end,
            )
            chunks.append(chunk)

            current_start = current_end

        logger.info(
            f"Split {symbol} download into {len(chunks)} chunks of ~{chunk_size_days} days each"
        )
        return chunks

    def create_download_session(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        chunk_size_days: int = 30,
        progress_callback: Optional[Callable[[DownloadSession], None]] = None,
    ) -> str:
        """
        Create a new download session.

        Args:
            symbol: Symbol to download
            timeframe: Timeframe string
            start_date: Start date for download
            end_date: End date for download
            chunk_size_days: Size of each chunk in days
            progress_callback: Optional callback for progress updates

        Returns:
            Session ID for the created session
        """
        session_id = self._generate_session_id(symbol, timeframe, start_date, end_date)

        # Create chunks
        chunks = self._split_into_chunks(
            symbol, timeframe, start_date, end_date, chunk_size_days
        )

        # Create session
        session = DownloadSession(
            session_id=session_id,
            symbol=symbol,
            timeframe=timeframe,
            full_start_date=start_date,
            full_end_date=end_date,
            chunks=chunks,
            created_at=time.time(),
            updated_at=time.time(),
        )

        self.sessions[session_id] = session
        self._save_sessions()

        logger.info(f"Created download session {session_id} for {symbol} {timeframe}")
        logger.info(
            f"Date range: {start_date.date()} to {end_date.date()} ({len(chunks)} chunks)"
        )

        return session_id

    def resume_download(
        self,
        session_id: str,
        progress_callback: Optional[Callable[[DownloadSession], None]] = None,
        max_retries: int = 3,
    ) -> bool:
        """
        Resume or start download for a session.

        Args:
            session_id: Session ID to resume
            progress_callback: Optional callback for progress updates
            max_retries: Maximum retries per chunk

        Returns:
            True if download completed successfully, False otherwise
        """
        if session_id not in self.sessions:
            logger.error(f"Session {session_id} not found")
            return False

        session = self.sessions[session_id]
        session.status = "in_progress"
        session.updated_at = time.time()

        logger.info(f"Resuming download session {session_id}")
        logger.info(f"Progress: {session.get_progress_percentage():.1f}% complete")

        remaining_chunks = session.get_remaining_chunks()
        logger.info(f"Processing {len(remaining_chunks)} remaining chunks")

        try:
            for i, chunk in enumerate(remaining_chunks):
                logger.info(
                    f"Processing chunk {i+1}/{len(remaining_chunks)}: {chunk.start_date.date()} to {chunk.end_date.date()}"
                )

                # Skip if too many attempts
                if chunk.attempt_count >= max_retries:
                    logger.warning(
                        f"Skipping chunk after {max_retries} failed attempts"
                    )
                    continue

                # Update chunk status
                chunk.status = "in_progress"
                chunk.attempt_count += 1
                chunk.last_attempt = time.time()

                try:
                    # Fetch data for this chunk
                    df = self.data_fetcher.fetch_historical_data(
                        symbol=chunk.symbol,
                        timeframe=chunk.timeframe,
                        start=chunk.start_date,
                        end=chunk.end_date,
                    )

                    if not df.empty:
                        chunk.status = "completed"
                        chunk.bars_count = len(df)
                        chunk.error_message = None
                        session.total_bars += len(df)

                        logger.info(f"Chunk completed: {len(df)} bars downloaded")
                    else:
                        chunk.status = "failed"
                        chunk.error_message = "No data returned"
                        logger.warning(f"Chunk failed: No data returned")

                except Exception as e:
                    chunk.status = "failed"
                    chunk.error_message = str(e)
                    logger.error(f"Chunk failed: {e}")

                # Update session
                session.updated_at = time.time()
                self._save_sessions()

                # Call progress callback
                if progress_callback:
                    try:
                        progress_callback(session)
                    except Exception as e:
                        logger.warning(f"Progress callback error: {e}")

                # Small delay to avoid overwhelming IB
                time.sleep(0.5)

            # Check if session is complete
            remaining = session.get_remaining_chunks()
            if not remaining:
                session.status = "completed"
                logger.info(f"Download session {session_id} completed successfully!")
                logger.info(f"Total bars downloaded: {session.total_bars}")
            else:
                failed_chunks = [c for c in remaining if c.attempt_count >= max_retries]
                if failed_chunks:
                    session.status = "failed"
                    logger.error(
                        f"Download session {session_id} failed - {len(failed_chunks)} chunks could not be completed"
                    )
                else:
                    session.status = "pending"  # Some chunks can still be retried

            session.updated_at = time.time()
            self._save_sessions()

            return session.status == "completed"

        except Exception as e:
            session.status = "failed"
            session.updated_at = time.time()
            self._save_sessions()
            logger.error(f"Download session {session_id} failed: {e}")
            return False

    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status information for a download session.

        Args:
            session_id: Session ID to check

        Returns:
            Dictionary with session status information or None if not found
        """
        if session_id not in self.sessions:
            return None

        session = self.sessions[session_id]
        completed_chunks = session.get_completed_chunks()
        remaining_chunks = session.get_remaining_chunks()

        return {
            "session_id": session_id,
            "symbol": session.symbol,
            "timeframe": session.timeframe,
            "status": session.status,
            "progress_percentage": session.get_progress_percentage(),
            "total_chunks": len(session.chunks),
            "completed_chunks": len(completed_chunks),
            "remaining_chunks": len(remaining_chunks),
            "total_bars": session.total_bars,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "date_range": {
                "start": session.full_start_date.isoformat(),
                "end": session.full_end_date.isoformat(),
            },
        }

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all download sessions.

        Returns:
            List of session status dictionaries
        """
        sessions = []
        for session_id in self.sessions.keys():
            status = self.get_session_status(session_id)
            if status is not None:
                sessions.append(status)
        return sessions

    def cancel_session(self, session_id: str) -> bool:
        """
        Cancel a download session.

        Args:
            session_id: Session ID to cancel

        Returns:
            True if cancelled successfully, False if session not found
        """
        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]
        session.status = "cancelled"
        session.updated_at = time.time()
        self._save_sessions()

        logger.info(f"Download session {session_id} cancelled")
        return True

    def cleanup_completed_sessions(self, older_than_days: int = 7):
        """
        Clean up completed download sessions older than specified days.

        Args:
            older_than_days: Remove completed sessions older than this many days
        """
        cutoff_time = time.time() - (older_than_days * 24 * 3600)
        to_remove = []

        for session_id, session in self.sessions.items():
            if session.status == "completed" and session.updated_at < cutoff_time:
                to_remove.append(session_id)

        for session_id in to_remove:
            del self.sessions[session_id]
            logger.info(f"Cleaned up completed session: {session_id}")

        if to_remove:
            self._save_sessions()
            logger.info(f"Cleaned up {len(to_remove)} completed sessions")

    def get_download_statistics(self) -> Dict[str, Any]:
        """
        Get overall download statistics.

        Returns:
            Dictionary with download statistics
        """
        total_sessions = len(self.sessions)
        completed_sessions = sum(
            1 for s in self.sessions.values() if s.status == "completed"
        )
        failed_sessions = sum(1 for s in self.sessions.values() if s.status == "failed")
        in_progress_sessions = sum(
            1 for s in self.sessions.values() if s.status == "in_progress"
        )

        total_bars = sum(s.total_bars for s in self.sessions.values())

        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "failed_sessions": failed_sessions,
            "in_progress_sessions": in_progress_sessions,
            "success_rate": (
                completed_sessions / total_sessions if total_sessions > 0 else 0
            ),
            "total_bars_downloaded": total_bars,
            "progress_file": str(self.progress_file),
        }
