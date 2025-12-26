"""Checkpoint persistence service.

Provides CRUD operations for operation checkpoints using hybrid storage:
- PostgreSQL for metadata and state (queryable)
- Filesystem for large artifacts (model weights, optimizer state)
"""

import asyncio
import json
import logging
import shutil
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ktrdr.api.models.db.checkpoints import CheckpointRecord

logger = logging.getLogger(__name__)


class CheckpointCorruptedError(Exception):
    """Raised when checkpoint artifacts are missing or corrupted."""

    pass


@dataclass
class CheckpointData:
    """Data structure for a loaded checkpoint.

    Attributes:
        operation_id: Unique identifier for the operation.
        checkpoint_type: Type of checkpoint (periodic, cancellation, failure, shutdown).
        created_at: When the checkpoint was created.
        state: JSON-serializable state dictionary.
        artifacts_path: Path to artifacts directory on filesystem.
        artifacts: Loaded artifact data (lazy loaded).
    """

    operation_id: str
    checkpoint_type: str
    created_at: datetime
    state: dict
    artifacts_path: Optional[str] = None
    artifacts: Optional[dict[str, bytes]] = None


@dataclass
class CheckpointSummary:
    """Summary of a checkpoint for listing.

    Attributes:
        operation_id: Unique identifier for the operation.
        checkpoint_type: Type of checkpoint.
        created_at: When the checkpoint was created.
        state_summary: Key fields from state for display.
        artifacts_size_bytes: Total size of artifacts.
    """

    operation_id: str
    checkpoint_type: str
    created_at: datetime
    state_summary: dict
    artifacts_size_bytes: Optional[int] = None


class CheckpointService:
    """Service for checkpoint CRUD operations.

    Provides atomic checkpoint persistence using hybrid storage:
    - PostgreSQL for metadata and state
    - Filesystem for large artifacts

    Uses UPSERT semantics - each operation has at most one checkpoint.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        artifacts_dir: str = "data/checkpoints",
    ):
        """Initialize the checkpoint service.

        Args:
            session_factory: Factory for creating async database sessions.
            artifacts_dir: Directory path for storing checkpoint artifacts.
        """
        self._session_factory = session_factory
        self._artifacts_dir = Path(artifacts_dir)

    @asynccontextmanager
    async def _get_session(self):
        """Get a database session for an operation."""
        async with self._session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def save_checkpoint(
        self,
        operation_id: str,
        checkpoint_type: str,
        state: dict,
        artifacts: Optional[dict[str, bytes]] = None,
    ) -> None:
        """Save checkpoint (UPSERT - overwrites existing).

        Atomic behavior:
        1. Write artifacts to temp directory
        2. Rename to final location (atomic on POSIX)
        3. UPSERT to database
        4. If DB fails, delete artifact files

        Args:
            operation_id: Unique identifier for the operation.
            checkpoint_type: Type of checkpoint (periodic, cancellation, failure, shutdown).
            state: JSON-serializable state dictionary.
            artifacts: Optional mapping of filename to binary data.

        Raises:
            Exception: If database write fails (artifacts are cleaned up).
        """
        artifacts_path: Optional[Path] = None
        artifacts_size_bytes: Optional[int] = None

        # Step 1-2: Write artifacts if provided
        if artifacts:
            artifacts_path = await self._write_artifacts(operation_id, artifacts)
            artifacts_size_bytes = sum(len(data) for data in artifacts.values())

        # Calculate state size
        state_json = json.dumps(state)
        state_size_bytes = len(state_json.encode("utf-8"))

        # Step 3: UPSERT to database
        try:
            async with self._get_session() as session:
                stmt = insert(CheckpointRecord).values(
                    operation_id=operation_id,
                    checkpoint_type=checkpoint_type,
                    state=state,
                    artifacts_path=str(artifacts_path) if artifacts_path else None,
                    state_size_bytes=state_size_bytes,
                    artifacts_size_bytes=artifacts_size_bytes,
                )

                # On conflict (operation_id already exists), update all fields
                stmt = stmt.on_conflict_do_update(
                    index_elements=["operation_id"],
                    set_={
                        "checkpoint_type": stmt.excluded.checkpoint_type,
                        "created_at": datetime.now(timezone.utc),
                        "state": stmt.excluded.state,
                        "artifacts_path": stmt.excluded.artifacts_path,
                        "state_size_bytes": stmt.excluded.state_size_bytes,
                        "artifacts_size_bytes": stmt.excluded.artifacts_size_bytes,
                    },
                )

                await session.execute(stmt)
                await session.commit()

                logger.debug(
                    f"Checkpoint saved for operation {operation_id} "
                    f"(type={checkpoint_type}, state={state_size_bytes}B, "
                    f"artifacts={artifacts_size_bytes or 0}B)"
                )

        except Exception as e:
            # Step 4: Cleanup artifacts on DB failure
            if artifacts_path and artifacts_path.exists():
                logger.warning(
                    f"DB write failed for checkpoint {operation_id}, "
                    f"cleaning up artifacts: {e}"
                )
                shutil.rmtree(artifacts_path, ignore_errors=True)
            raise

    async def load_checkpoint(
        self,
        operation_id: str,
        load_artifacts: bool = True,
    ) -> Optional[CheckpointData]:
        """Load checkpoint for resume.

        Args:
            operation_id: Unique identifier for the operation.
            load_artifacts: Whether to load artifacts from filesystem.

        Returns:
            CheckpointData if found, None otherwise.

        Raises:
            CheckpointCorruptedError: If artifacts are missing when load_artifacts=True.
        """
        async with self._get_session() as session:
            stmt = select(CheckpointRecord).where(
                CheckpointRecord.operation_id == operation_id
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if record is None:
                return None

            checkpoint = CheckpointData(
                operation_id=record.operation_id,
                checkpoint_type=record.checkpoint_type,
                created_at=record.created_at,
                state=record.state,
                artifacts_path=record.artifacts_path,
            )

            # Load artifacts from filesystem if requested
            if load_artifacts and record.artifacts_path:
                checkpoint.artifacts = await self._load_artifacts(
                    record.artifacts_path, operation_id
                )

            return checkpoint

    async def delete_checkpoint(self, operation_id: str) -> bool:
        """Delete checkpoint after successful completion.

        Args:
            operation_id: Unique identifier for the operation.

        Returns:
            True if checkpoint was deleted, False if not found.
        """
        async with self._get_session() as session:
            # First get the record to find artifacts_path
            stmt = select(CheckpointRecord).where(
                CheckpointRecord.operation_id == operation_id
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if record is None:
                return False

            # Delete artifacts from filesystem
            if record.artifacts_path:
                artifacts_path = Path(record.artifacts_path)
                if artifacts_path.exists():
                    shutil.rmtree(artifacts_path, ignore_errors=True)
                    logger.debug(f"Deleted artifacts at {artifacts_path}")

            # Delete DB row
            await session.delete(record)
            await session.commit()

            logger.debug(f"Checkpoint deleted for operation {operation_id}")
            return True

    async def list_checkpoints(
        self,
        older_than_days: Optional[int] = None,
    ) -> list[CheckpointSummary]:
        """List checkpoints for admin/cleanup.

        Args:
            older_than_days: If set, only return checkpoints older than this.

        Returns:
            List of CheckpointSummary objects.
        """
        async with self._get_session() as session:
            stmt = select(CheckpointRecord)

            if older_than_days is not None:
                cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
                stmt = stmt.where(CheckpointRecord.created_at < cutoff)

            stmt = stmt.order_by(CheckpointRecord.created_at.desc())

            result = await session.execute(stmt)
            records = result.scalars().all()

            return [
                CheckpointSummary(
                    operation_id=record.operation_id,
                    checkpoint_type=record.checkpoint_type,
                    created_at=record.created_at,
                    state_summary=record.state,
                    artifacts_size_bytes=record.artifacts_size_bytes,
                )
                for record in records
            ]

    async def _write_artifacts(
        self,
        operation_id: str,
        artifacts: dict[str, bytes],
    ) -> Path:
        """Write artifacts atomically using temp directory + rename.

        Args:
            operation_id: Unique identifier for the operation.
            artifacts: Mapping of filename to binary data.

        Returns:
            Path to the final artifacts directory.
        """
        final_path = self._artifacts_dir / operation_id
        temp_path = self._artifacts_dir / f"{operation_id}.tmp"

        # Ensure artifacts directory exists
        self._artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Clean up any existing temp directory
        if temp_path.exists():
            shutil.rmtree(temp_path)

        # Write to temp directory (run in thread to avoid blocking)
        def _write_sync():
            temp_path.mkdir(parents=True)
            for name, data in artifacts.items():
                (temp_path / name).write_bytes(data)

        await asyncio.to_thread(_write_sync)

        # Atomic rename (remove existing first if present)
        if final_path.exists():
            shutil.rmtree(final_path)
        temp_path.rename(final_path)

        return final_path

    async def _load_artifacts(
        self, artifacts_path: str, operation_id: str
    ) -> dict[str, bytes]:
        """Load all artifacts from directory.

        Args:
            artifacts_path: Path to artifacts directory.
            operation_id: Operation ID for error messages.

        Returns:
            Mapping of filename to binary data.

        Raises:
            CheckpointCorruptedError: If artifacts directory is missing.
        """
        path = Path(artifacts_path)
        if not path.exists():
            raise CheckpointCorruptedError(
                f"Artifacts directory missing for checkpoint {operation_id}: "
                f"{artifacts_path}"
            )

        # Load artifacts in thread to avoid blocking
        def _load_sync() -> dict[str, bytes]:
            artifacts = {}
            for file_path in path.iterdir():
                if file_path.is_file():
                    artifacts[file_path.name] = file_path.read_bytes()
            return artifacts

        return await asyncio.to_thread(_load_sync)
