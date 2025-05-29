"""
Unit tests for IB Resume Handler.

Tests resumable downloads for interrupted IB fetches with comprehensive
scenarios including interruption, failure recovery, and session management.
"""

import json
import tempfile
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
import pandas as pd

from ktrdr.data.ib_resume_handler import IbResumeHandler, DownloadChunk, DownloadSession
from ktrdr.data.ib_data_fetcher_sync import IbDataFetcherSync
from ktrdr.errors import DataError


class TestDownloadChunk:
    """Test DownloadChunk dataclass functionality."""

    def test_chunk_creation(self):
        """Test basic chunk creation."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 31)

        chunk = DownloadChunk(
            symbol="MSFT", timeframe="1h", start_date=start_date, end_date=end_date
        )

        assert chunk.symbol == "MSFT"
        assert chunk.timeframe == "1h"
        assert chunk.start_date == start_date
        assert chunk.end_date == end_date
        assert chunk.status == "pending"
        assert chunk.attempt_count == 0
        assert chunk.last_attempt is None
        assert chunk.error_message is None
        assert chunk.bars_count is None

    def test_chunk_serialization(self):
        """Test chunk serialization to/from dict."""
        start_date = datetime(2023, 1, 1, 12, 30)
        end_date = datetime(2023, 1, 31, 15, 45)

        chunk = DownloadChunk(
            symbol="AAPL",
            timeframe="1d",
            start_date=start_date,
            end_date=end_date,
            status="completed",
            attempt_count=1,
            last_attempt=1234567890.0,
            bars_count=100,
        )

        # Test to_dict
        data = chunk.to_dict()
        assert data["symbol"] == "AAPL"
        assert data["timeframe"] == "1d"
        assert data["start_date"] == start_date.isoformat()
        assert data["end_date"] == end_date.isoformat()
        assert data["status"] == "completed"
        assert data["attempt_count"] == 1
        assert data["last_attempt"] == 1234567890.0
        assert data["bars_count"] == 100

        # Test from_dict
        restored_chunk = DownloadChunk.from_dict(data)
        assert restored_chunk.symbol == chunk.symbol
        assert restored_chunk.timeframe == chunk.timeframe
        assert restored_chunk.start_date == chunk.start_date
        assert restored_chunk.end_date == chunk.end_date
        assert restored_chunk.status == chunk.status
        assert restored_chunk.attempt_count == chunk.attempt_count
        assert restored_chunk.last_attempt == chunk.last_attempt
        assert restored_chunk.bars_count == chunk.bars_count


class TestDownloadSession:
    """Test DownloadSession dataclass functionality."""

    def test_session_creation(self):
        """Test basic session creation."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 12, 31)
        chunks = [
            DownloadChunk("MSFT", "1h", start_date, start_date + timedelta(days=30)),
            DownloadChunk("MSFT", "1h", start_date + timedelta(days=30), end_date),
        ]

        session = DownloadSession(
            session_id="test_session",
            symbol="MSFT",
            timeframe="1h",
            full_start_date=start_date,
            full_end_date=end_date,
            chunks=chunks,
            created_at=time.time(),
            updated_at=time.time(),
        )

        assert session.session_id == "test_session"
        assert session.symbol == "MSFT"
        assert session.timeframe == "1h"
        assert len(session.chunks) == 2
        assert session.status == "pending"
        assert session.total_bars == 0

    def test_session_serialization(self):
        """Test session serialization to/from dict."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 31)
        chunks = [
            DownloadChunk(
                "AAPL", "1d", start_date, end_date, status="completed", bars_count=31
            )
        ]

        session = DownloadSession(
            session_id="test_session",
            symbol="AAPL",
            timeframe="1d",
            full_start_date=start_date,
            full_end_date=end_date,
            chunks=chunks,
            created_at=1234567890.0,
            updated_at=1234567900.0,
            status="completed",
            total_bars=31,
        )

        # Test to_dict
        data = session.to_dict()
        assert data["session_id"] == "test_session"
        assert data["symbol"] == "AAPL"
        assert data["timeframe"] == "1d"
        assert data["full_start_date"] == start_date.isoformat()
        assert data["full_end_date"] == end_date.isoformat()
        assert len(data["chunks"]) == 1
        assert data["status"] == "completed"
        assert data["total_bars"] == 31

        # Test from_dict
        restored_session = DownloadSession.from_dict(data)
        assert restored_session.session_id == session.session_id
        assert restored_session.symbol == session.symbol
        assert restored_session.timeframe == session.timeframe
        assert restored_session.full_start_date == session.full_start_date
        assert restored_session.full_end_date == session.full_end_date
        assert len(restored_session.chunks) == 1
        assert restored_session.status == session.status
        assert restored_session.total_bars == session.total_bars

    def test_progress_percentage(self):
        """Test progress percentage calculation."""
        chunks = [
            DownloadChunk(
                "MSFT",
                "1h",
                datetime(2023, 1, 1),
                datetime(2023, 1, 10),
                status="completed",
            ),
            DownloadChunk(
                "MSFT",
                "1h",
                datetime(2023, 1, 10),
                datetime(2023, 1, 20),
                status="completed",
            ),
            DownloadChunk(
                "MSFT",
                "1h",
                datetime(2023, 1, 20),
                datetime(2023, 1, 30),
                status="pending",
            ),
            DownloadChunk(
                "MSFT",
                "1h",
                datetime(2023, 1, 30),
                datetime(2023, 2, 10),
                status="failed",
            ),
        ]

        session = DownloadSession(
            session_id="test",
            symbol="MSFT",
            timeframe="1h",
            full_start_date=datetime(2023, 1, 1),
            full_end_date=datetime(2023, 2, 10),
            chunks=chunks,
            created_at=time.time(),
            updated_at=time.time(),
        )

        # 2 completed out of 4 total = 50%
        assert session.get_progress_percentage() == 50.0

    def test_remaining_chunks(self):
        """Test getting remaining chunks."""
        chunks = [
            DownloadChunk(
                "MSFT",
                "1h",
                datetime(2023, 1, 1),
                datetime(2023, 1, 10),
                status="completed",
            ),
            DownloadChunk(
                "MSFT",
                "1h",
                datetime(2023, 1, 10),
                datetime(2023, 1, 20),
                status="pending",
            ),
            DownloadChunk(
                "MSFT",
                "1h",
                datetime(2023, 1, 20),
                datetime(2023, 1, 30),
                status="failed",
            ),
            DownloadChunk(
                "MSFT",
                "1h",
                datetime(2023, 1, 30),
                datetime(2023, 2, 10),
                status="in_progress",
            ),
        ]

        session = DownloadSession(
            session_id="test",
            symbol="MSFT",
            timeframe="1h",
            full_start_date=datetime(2023, 1, 1),
            full_end_date=datetime(2023, 2, 10),
            chunks=chunks,
            created_at=time.time(),
            updated_at=time.time(),
        )

        remaining = session.get_remaining_chunks()
        assert len(remaining) == 2  # pending and failed
        assert remaining[0].status == "pending"
        assert remaining[1].status == "failed"

    def test_completed_chunks(self):
        """Test getting completed chunks."""
        chunks = [
            DownloadChunk(
                "MSFT",
                "1h",
                datetime(2023, 1, 1),
                datetime(2023, 1, 10),
                status="completed",
            ),
            DownloadChunk(
                "MSFT",
                "1h",
                datetime(2023, 1, 10),
                datetime(2023, 1, 20),
                status="pending",
            ),
            DownloadChunk(
                "MSFT",
                "1h",
                datetime(2023, 1, 20),
                datetime(2023, 1, 30),
                status="completed",
            ),
        ]

        session = DownloadSession(
            session_id="test",
            symbol="MSFT",
            timeframe="1h",
            full_start_date=datetime(2023, 1, 1),
            full_end_date=datetime(2023, 1, 30),
            chunks=chunks,
            created_at=time.time(),
            updated_at=time.time(),
        )

        completed = session.get_completed_chunks()
        assert len(completed) == 2
        assert all(chunk.status == "completed" for chunk in completed)


class TestIbResumeHandler:
    """Test IbResumeHandler functionality."""

    @pytest.fixture
    def temp_progress_dir(self):
        """Create temporary directory for progress files."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_data_fetcher(self):
        """Create mock data fetcher."""
        mock_fetcher = Mock(spec=IbDataFetcherSync)
        return mock_fetcher

    @pytest.fixture
    def resume_handler(self, mock_data_fetcher, temp_progress_dir):
        """Create resume handler with temp directory."""
        return IbResumeHandler(mock_data_fetcher, temp_progress_dir)

    def test_initialization(self, mock_data_fetcher, temp_progress_dir):
        """Test resume handler initialization."""
        handler = IbResumeHandler(mock_data_fetcher, temp_progress_dir)

        assert handler.data_fetcher is mock_data_fetcher
        assert handler.progress_dir == Path(temp_progress_dir)
        assert handler.progress_file == Path(temp_progress_dir) / "progress.json"
        assert handler.sessions == {}
        assert handler.progress_dir.exists()

    def test_session_id_generation(self, resume_handler):
        """Test session ID generation."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 12, 31)

        session_id = resume_handler._generate_session_id(
            "MSFT", "1h", start_date, end_date
        )

        assert "MSFT" in session_id
        assert "1h" in session_id
        assert "20230101" in session_id
        assert "20231231" in session_id
        assert len(session_id.split("_")) == 5  # symbol_timeframe_start_end_timestamp

    def test_chunk_splitting(self, resume_handler):
        """Test splitting date range into chunks."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 3, 1)  # ~60 days

        chunks = resume_handler._split_into_chunks(
            "MSFT", "1h", start_date, end_date, chunk_size_days=30
        )

        assert len(chunks) == 2  # Should split into 2 chunks of ~30 days each
        assert chunks[0].start_date == start_date
        assert chunks[0].end_date == start_date + timedelta(days=30)
        assert chunks[1].start_date == start_date + timedelta(days=30)
        assert chunks[1].end_date == end_date

        for chunk in chunks:
            assert chunk.symbol == "MSFT"
            assert chunk.timeframe == "1h"
            assert chunk.status == "pending"

    def test_create_download_session(self, resume_handler):
        """Test creating a new download session."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 2, 1)

        session_id = resume_handler.create_download_session(
            symbol="AAPL",
            timeframe="1d",
            start_date=start_date,
            end_date=end_date,
            chunk_size_days=15,
        )

        assert session_id in resume_handler.sessions
        session = resume_handler.sessions[session_id]

        assert session.symbol == "AAPL"
        assert session.timeframe == "1d"
        assert session.full_start_date == start_date
        assert session.full_end_date == end_date
        assert len(session.chunks) == 3  # 31 days / 15 = 3 chunks
        assert session.status == "pending"

    def test_successful_download_resume(self, resume_handler, mock_data_fetcher):
        """Test successful download resume."""
        # Create session
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 15)

        session_id = resume_handler.create_download_session(
            symbol="MSFT",
            timeframe="1h",
            start_date=start_date,
            end_date=end_date,
            chunk_size_days=7,
        )

        # Mock successful data fetch
        mock_df = pd.DataFrame(
            {
                "open": [100, 101, 102],
                "high": [105, 106, 107],
                "low": [99, 100, 101],
                "close": [104, 105, 106],
                "volume": [1000, 1100, 1200],
            }
        )
        mock_data_fetcher.fetch_historical_data.return_value = mock_df

        # Test progress callback
        progress_calls = []

        def progress_callback(session):
            progress_calls.append(session.get_progress_percentage())

        # Resume download
        success = resume_handler.resume_download(
            session_id, progress_callback=progress_callback
        )

        assert success is True

        session = resume_handler.sessions[session_id]
        assert session.status == "completed"
        assert session.total_bars == 6  # 2 chunks * 3 bars each
        assert len(progress_calls) == 2  # Called for each chunk
        assert progress_calls[-1] == 100.0  # Final progress should be 100%

        # All chunks should be completed
        for chunk in session.chunks:
            assert chunk.status == "completed"
            assert chunk.bars_count == 3

    def test_partial_failure_resume(self, resume_handler, mock_data_fetcher):
        """Test resume with some chunks failing."""
        # Create session
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 21)

        session_id = resume_handler.create_download_session(
            symbol="MSFT",
            timeframe="1h",
            start_date=start_date,
            end_date=end_date,
            chunk_size_days=7,
        )

        # Mock alternating success/failure
        mock_df = pd.DataFrame(
            {
                "open": [100],
                "high": [105],
                "low": [99],
                "close": [104],
                "volume": [1000],
            }
        )

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:  # Fail every second call
                raise DataError("Simulated fetch failure")
            return mock_df

        mock_data_fetcher.fetch_historical_data.side_effect = side_effect

        # Resume download with max_retries=1
        success = resume_handler.resume_download(session_id, max_retries=1)

        assert success is False  # Should fail due to some chunks failing

        session = resume_handler.sessions[session_id]
        assert session.status == "failed"

        # Check chunk statuses
        completed_chunks = session.get_completed_chunks()
        remaining_chunks = session.get_remaining_chunks()

        assert len(completed_chunks) > 0  # Some should succeed
        assert len(remaining_chunks) > 0  # Some should fail

    def test_retry_logic(self, resume_handler, mock_data_fetcher):
        """Test retry logic for failed chunks."""
        # Create session with single chunk
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 7)

        session_id = resume_handler.create_download_session(
            symbol="MSFT",
            timeframe="1h",
            start_date=start_date,
            end_date=end_date,
            chunk_size_days=10,  # Single chunk
        )

        # First attempt fails, second succeeds
        mock_df = pd.DataFrame(
            {
                "open": [100],
                "high": [105],
                "low": [99],
                "close": [104],
                "volume": [1000],
            }
        )

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise DataError("First attempt fails")
            return mock_df

        mock_data_fetcher.fetch_historical_data.side_effect = side_effect

        # First resume attempt
        success1 = resume_handler.resume_download(session_id, max_retries=2)
        assert success1 is False

        session = resume_handler.sessions[session_id]
        assert session.chunks[0].attempt_count == 1
        assert session.chunks[0].status == "failed"

        # Second resume attempt should succeed
        success2 = resume_handler.resume_download(session_id, max_retries=2)
        assert success2 is True

        assert session.chunks[0].attempt_count == 2
        assert session.chunks[0].status == "completed"

    def test_max_retries_exceeded(self, resume_handler, mock_data_fetcher):
        """Test behavior when max retries are exceeded."""
        # Create session with single chunk
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 7)

        session_id = resume_handler.create_download_session(
            symbol="MSFT",
            timeframe="1h",
            start_date=start_date,
            end_date=end_date,
            chunk_size_days=10,
        )

        # Always fail
        mock_data_fetcher.fetch_historical_data.side_effect = DataError("Always fails")

        # Resume with max_retries=2 - first attempt
        success1 = resume_handler.resume_download(session_id, max_retries=2)
        assert success1 is False

        session = resume_handler.sessions[session_id]
        chunk = session.chunks[0]

        assert chunk.attempt_count == 1
        assert chunk.status == "failed"

        # Resume again - second attempt
        success2 = resume_handler.resume_download(session_id, max_retries=2)
        assert success2 is False

        assert chunk.attempt_count == 2
        assert chunk.status == "failed"
        assert session.status == "failed"

        # Another resume should skip the chunk (max attempts reached)
        success3 = resume_handler.resume_download(session_id, max_retries=2)
        assert success3 is False
        assert chunk.attempt_count == 2  # Should not increment further

    def test_session_status_retrieval(self, resume_handler):
        """Test getting session status information."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 15)

        session_id = resume_handler.create_download_session(
            symbol="AAPL", timeframe="1d", start_date=start_date, end_date=end_date
        )

        status = resume_handler.get_session_status(session_id)

        assert status is not None
        assert status["session_id"] == session_id
        assert status["symbol"] == "AAPL"
        assert status["timeframe"] == "1d"
        assert status["status"] == "pending"
        assert status["progress_percentage"] == 0.0
        assert status["total_chunks"] > 0
        assert status["completed_chunks"] == 0
        assert status["remaining_chunks"] == status["total_chunks"]
        assert status["total_bars"] == 0
        assert "date_range" in status

        # Test non-existent session
        assert resume_handler.get_session_status("non_existent") is None

    def test_session_list(self, resume_handler):
        """Test listing all sessions."""
        # Create multiple sessions
        session_ids = []
        for i, symbol in enumerate(["MSFT", "AAPL", "GOOGL"]):
            session_id = resume_handler.create_download_session(
                symbol=symbol,
                timeframe="1h",
                start_date=datetime(2023, 1, 1),
                end_date=datetime(2023, 1, 31),
            )
            session_ids.append(session_id)

        session_list = resume_handler.list_sessions()

        assert len(session_list) == 3
        for status in session_list:
            assert status["session_id"] in session_ids
            assert status["symbol"] in ["MSFT", "AAPL", "GOOGL"]

    def test_session_cancellation(self, resume_handler):
        """Test cancelling a download session."""
        session_id = resume_handler.create_download_session(
            symbol="MSFT",
            timeframe="1h",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
        )

        # Cancel session
        success = resume_handler.cancel_session(session_id)
        assert success is True

        session = resume_handler.sessions[session_id]
        assert session.status == "cancelled"

        # Test cancelling non-existent session
        assert resume_handler.cancel_session("non_existent") is False

    def test_persistence(self, resume_handler, temp_progress_dir):
        """Test session persistence to/from disk."""
        # Create session
        session_id = resume_handler.create_download_session(
            symbol="MSFT",
            timeframe="1h",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 15),
        )

        # Verify progress file exists
        progress_file = Path(temp_progress_dir) / "progress.json"
        assert progress_file.exists()

        # Load progress file and verify content
        with open(progress_file, "r") as f:
            data = json.load(f)

        assert "sessions" in data
        assert "last_updated" in data
        assert len(data["sessions"]) == 1

        session_data = data["sessions"][0]
        assert session_data["session_id"] == session_id
        assert session_data["symbol"] == "MSFT"

        # Create new handler and verify it loads existing sessions
        new_handler = IbResumeHandler(resume_handler.data_fetcher, temp_progress_dir)
        assert session_id in new_handler.sessions

        restored_session = new_handler.sessions[session_id]
        assert restored_session.symbol == "MSFT"
        assert restored_session.timeframe == "1h"

    def test_cleanup_completed_sessions(self, resume_handler):
        """Test cleanup of old completed sessions."""
        # Create sessions with different ages
        old_time = time.time() - (10 * 24 * 3600)  # 10 days old
        recent_time = time.time() - (3 * 24 * 3600)  # 3 days old

        # Create old completed session
        old_session_id = resume_handler.create_download_session(
            symbol="OLD",
            timeframe="1h",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 7),
        )
        old_session = resume_handler.sessions[old_session_id]
        old_session.status = "completed"
        old_session.updated_at = old_time

        # Create recent completed session
        recent_session_id = resume_handler.create_download_session(
            symbol="RECENT",
            timeframe="1h",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 7),
        )
        recent_session = resume_handler.sessions[recent_session_id]
        recent_session.status = "completed"
        recent_session.updated_at = recent_time

        # Create pending session (should not be cleaned up)
        pending_session_id = resume_handler.create_download_session(
            symbol="PENDING",
            timeframe="1h",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 7),
        )

        assert len(resume_handler.sessions) == 3

        # Cleanup sessions older than 7 days
        resume_handler.cleanup_completed_sessions(older_than_days=7)

        # Old completed session should be removed
        assert old_session_id not in resume_handler.sessions
        # Recent completed session should remain
        assert recent_session_id in resume_handler.sessions
        # Pending session should remain
        assert pending_session_id in resume_handler.sessions

        assert len(resume_handler.sessions) == 2

    def test_download_statistics(self, resume_handler):
        """Test download statistics calculation."""
        # Create sessions with different statuses
        for i, (symbol, status) in enumerate(
            [
                ("MSFT", "completed"),
                ("AAPL", "completed"),
                ("GOOGL", "failed"),
                ("TSLA", "in_progress"),
                ("NFLX", "pending"),
            ]
        ):
            session_id = resume_handler.create_download_session(
                symbol=symbol,
                timeframe="1h",
                start_date=datetime(2023, 1, 1),
                end_date=datetime(2023, 1, 7),
            )
            session = resume_handler.sessions[session_id]
            session.status = status
            if status == "completed":
                session.total_bars = 100 * (i + 1)  # Different bar counts

        stats = resume_handler.get_download_statistics()

        assert stats["total_sessions"] == 5
        assert stats["completed_sessions"] == 2
        assert stats["failed_sessions"] == 1
        assert stats["in_progress_sessions"] == 1
        assert stats["success_rate"] == 0.4  # 2/5
        assert stats["total_bars_downloaded"] == 300  # 100 + 200
        assert "progress_file" in stats

    def test_nonexistent_session_resume(self, resume_handler):
        """Test resuming a non-existent session."""
        success = resume_handler.resume_download("non_existent_session")
        assert success is False

    def test_empty_data_handling(self, resume_handler, mock_data_fetcher):
        """Test handling of empty data responses."""
        session_id = resume_handler.create_download_session(
            symbol="MSFT",
            timeframe="1h",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 7),
        )

        # Mock empty DataFrame
        mock_data_fetcher.fetch_historical_data.return_value = pd.DataFrame()

        success = resume_handler.resume_download(session_id)
        assert success is False

        session = resume_handler.sessions[session_id]
        chunk = session.chunks[0]
        assert chunk.status == "failed"
        assert chunk.error_message == "No data returned"

    def test_progress_callback_error_handling(self, resume_handler, mock_data_fetcher):
        """Test handling of progress callback errors."""
        session_id = resume_handler.create_download_session(
            symbol="MSFT",
            timeframe="1h",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 7),
        )

        # Mock successful data fetch
        mock_df = pd.DataFrame(
            {
                "open": [100],
                "high": [105],
                "low": [99],
                "close": [104],
                "volume": [1000],
            }
        )
        mock_data_fetcher.fetch_historical_data.return_value = mock_df

        # Progress callback that raises exception
        def failing_callback(session):
            raise Exception("Callback error")

        # Should not fail the whole download due to callback error
        success = resume_handler.resume_download(
            session_id, progress_callback=failing_callback
        )
        assert success is True

        session = resume_handler.sessions[session_id]
        assert session.status == "completed"
