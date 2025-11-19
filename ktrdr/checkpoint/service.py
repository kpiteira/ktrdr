"""
Checkpoint service for CRUD operations on checkpoints.

This module implements CheckpointService with:
- UPSERT pattern (ONE checkpoint per operation)
- Atomic filesystem writes (temp → rename)
- Transaction rollback with artifact cleanup
- PostgreSQL + filesystem storage
"""

import json
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import psycopg2  # type: ignore[import-untyped]
import yaml
from opentelemetry import trace

from ktrdr.logging import get_logger

# Get tracer for checkpoint service
tracer = trace.get_tracer(__name__)
logger = get_logger(__name__)


class CheckpointService:
    """
    Service for checkpoint CRUD operations.

    Manages checkpoints in PostgreSQL database + filesystem:
    - Database (operation_checkpoints table): Metadata and state (JSON)
    - Filesystem (artifacts_dir): Large binary files (.pt model files)

    Design:
        - ONE checkpoint per operation (UPSERT replaces old)
        - Atomic writes (temp → rename pattern)
        - Transaction safety (rollback cleans up artifacts)
    """

    def __init__(
        self,
        artifacts_dir: Optional[Path] = None,
        db_host: Optional[str] = None,
        db_port: Optional[int] = None,
        db_name: Optional[str] = None,
        db_user: Optional[str] = None,
        db_password: Optional[str] = None,
    ):
        """
        Initialize checkpoint service.

        Args:
            artifacts_dir: Directory for checkpoint artifacts (default: from config)
            db_host: Database host (default: from config/env)
            db_port: Database port (default: from config/env)
            db_name: Database name (default: from config/env)
            db_user: Database user (default: from config/env)
            db_password: Database password (default: from config/env)
        """
        # Load configuration
        config = self._load_config()

        # Configure artifacts directory
        if artifacts_dir is None:
            project_root = Path(__file__).parent.parent.parent
            artifacts_dir = project_root / config.get("checkpointing", {}).get(
                "artifacts_dir", "data/checkpoints/artifacts"
            )

        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Configure database connection
        db_config = config.get("database", {})
        self.db_host = db_host or os.getenv(
            "POSTGRES_HOST", db_config.get("host", "localhost")
        )
        self.db_port = db_port or int(
            os.getenv("POSTGRES_PORT", db_config.get("port", 5432))
        )
        self.db_name = db_name or os.getenv(
            "POSTGRES_DB", db_config.get("database", "ktrdr")
        )
        self.db_user = db_user or os.getenv(
            "POSTGRES_USER", db_config.get("user", "ktrdr_admin")
        )
        self.db_password = db_password or os.getenv(
            "POSTGRES_PASSWORD", db_config.get("password", "ktrdr_dev_password")
        )

        # Database connection (created on demand)
        self._conn = None
        self._cursor = None

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from config/persistence.yaml."""
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "config" / "persistence.yaml"

        if not config_path.exists():
            # Return default config if file doesn't exist
            return {
                "database": {},
                "checkpointing": {"artifacts_dir": "data/checkpoints/artifacts"},
            }

        with open(config_path) as f:
            config_str = f.read()

        # Expand environment variables in config
        # Format: ${VAR_NAME:-default_value}
        def expand_env_var(match):
            var_expr = match.group(1)
            if ":-" in var_expr:
                var_name, default = var_expr.split(":-", 1)
                return os.getenv(var_name.strip(), default.strip())
            else:
                return os.getenv(var_expr.strip(), "")

        expanded_config = re.sub(r"\$\{([^}]+)\}", expand_env_var, config_str)

        return yaml.safe_load(expanded_config) or {}

    def _get_connection(self):
        """Get database connection (create if needed)."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password,
            )
            self._cursor = self._conn.cursor()

        return self._conn, self._cursor

    def save_checkpoint(
        self, operation_id: str, checkpoint_data: dict[str, Any]
    ) -> None:
        """
        Save checkpoint (UPSERT - replaces old checkpoint for operation).

        Args:
            operation_id: Operation ID (primary key in operation_checkpoints)
            checkpoint_data: Checkpoint data dictionary:
                - checkpoint_id: str (for reference/debugging)
                - checkpoint_type: str ('epoch_snapshot', 'bar_snapshot', 'final')
                - metadata: dict (small queryable data: epoch, metrics, etc.)
                - state: dict (full checkpoint state without artifacts)
                - artifacts: optional dict (large binary files: model.pt, etc.)
                - artifacts_path: optional str (for loading existing artifacts)

        Implementation:
            1. Serialize state and metadata to JSON
            2. Calculate sizes
            3. Write artifacts to filesystem (atomic temp → rename)
            4. UPSERT into operation_checkpoints table
            5. Commit transaction
            6. On error: rollback + cleanup artifacts
        """
        with tracer.start_as_current_span("checkpoint.save") as span:
            span.set_attribute("operation.id", operation_id)
            span.set_attribute(
                "checkpoint.type", checkpoint_data.get("checkpoint_type", "unknown")
            )

            conn, cursor = self._get_connection()

            # Extract checkpoint data
            checkpoint_id = checkpoint_data["checkpoint_id"]
            checkpoint_type = checkpoint_data["checkpoint_type"]
            metadata = checkpoint_data.get("metadata", {})
            state = checkpoint_data["state"]
            artifacts = checkpoint_data.get("artifacts", {})
            artifacts_path = checkpoint_data.get("artifacts_path")

            # Serialize to JSON
            metadata_json = json.dumps(metadata)
            state_json = json.dumps(state)

            # Calculate sizes
            state_size_bytes = len(state_json.encode("utf-8"))
            artifacts_size_bytes = 0

            span.set_attribute("checkpoint.state_size_bytes", state_size_bytes)
            span.set_attribute("checkpoint.has_artifacts", bool(artifacts))

            # Write artifacts to filesystem (atomic temp → rename)
            if artifacts and not artifacts_path:
                with tracer.start_as_current_span(
                    "checkpoint.write_artifacts"
                ) as artifact_span:
                    artifacts_path = self._write_artifacts_atomic(
                        operation_id, artifacts
                    )
                    artifacts_size_bytes = self._calculate_artifacts_size(
                        Path(artifacts_path)
                    )
                    artifact_span.set_attribute(
                        "checkpoint.artifacts_size_bytes", artifacts_size_bytes
                    )
            elif artifacts_path:
                artifacts_size_bytes = self._calculate_artifacts_size(
                    Path(artifacts_path)
                )

            span.set_attribute("checkpoint.artifacts_size_bytes", artifacts_size_bytes)
            span.set_attribute(
                "checkpoint.total_size_bytes", state_size_bytes + artifacts_size_bytes
            )

            try:
                # UPSERT into operation_checkpoints table
                # Uses INSERT ... ON CONFLICT DO UPDATE for atomicity
                with tracer.start_as_current_span("checkpoint.db_upsert") as db_span:
                    sql = """
                        INSERT INTO operation_checkpoints (
                            operation_id,
                            checkpoint_id,
                            checkpoint_type,
                            created_at,
                            checkpoint_metadata_json,
                            state_json,
                            artifacts_path,
                            state_size_bytes,
                            artifacts_size_bytes
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (operation_id) DO UPDATE SET
                            checkpoint_id = EXCLUDED.checkpoint_id,
                            checkpoint_type = EXCLUDED.checkpoint_type,
                            created_at = EXCLUDED.created_at,
                            checkpoint_metadata_json = EXCLUDED.checkpoint_metadata_json,
                            state_json = EXCLUDED.state_json,
                            artifacts_path = EXCLUDED.artifacts_path,
                            state_size_bytes = EXCLUDED.state_size_bytes,
                            artifacts_size_bytes = EXCLUDED.artifacts_size_bytes;
                    """

                    params = (
                        operation_id,
                        checkpoint_id,
                        checkpoint_type,
                        datetime.utcnow(),
                        metadata_json,
                        state_json,
                        str(artifacts_path) if artifacts_path else None,
                        state_size_bytes,
                        artifacts_size_bytes,
                    )

                    cursor.execute(sql, params)
                    conn.commit()
                    db_span.set_attribute("checkpoint.db_committed", True)

                span.set_attribute("checkpoint.success", True)
                logger.debug(
                    f"Saved checkpoint for {operation_id}: {checkpoint_type} ({state_size_bytes + artifacts_size_bytes} bytes)"
                )

            except Exception as e:
                # Rollback transaction
                conn.rollback()

                # Cleanup artifacts if they were created
                if artifacts and artifacts_path and Path(artifacts_path).exists():
                    shutil.rmtree(artifacts_path, ignore_errors=True)

                span.set_attribute("error", True)
                span.set_attribute("error.type", type(e).__name__)
                span.set_attribute("error.message", str(e))
                span.set_attribute("checkpoint.success", False)

                logger.error(f"Failed to save checkpoint for {operation_id}: {e}")
                raise

    def load_checkpoint(self, operation_id: str) -> Optional[dict[str, Any]]:
        """
        Load checkpoint from database + filesystem.

        Args:
            operation_id: Operation ID

        Returns:
            Checkpoint data dictionary or None if not found:
                - operation_id: str
                - checkpoint_id: str
                - checkpoint_type: str
                - created_at: str (ISO format)
                - metadata: dict (deserialized from JSON)
                - state: dict (deserialized from JSON)
                - artifacts_path: str (path to artifacts directory)
                - artifacts: dict (loaded artifact files, if requested)
                - state_size_bytes: int
                - artifacts_size_bytes: int
        """
        conn, cursor = self._get_connection()

        # Query operation_checkpoints table
        sql = """
            SELECT
                operation_id,
                checkpoint_id,
                checkpoint_type,
                created_at,
                checkpoint_metadata_json,
                state_json,
                artifacts_path,
                state_size_bytes,
                artifacts_size_bytes
            FROM operation_checkpoints
            WHERE operation_id = %s;
        """

        cursor.execute(sql, (operation_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        # Unpack database row
        (
            operation_id,
            checkpoint_id,
            checkpoint_type,
            created_at,
            metadata_json,
            state_json,
            artifacts_path,
            state_size_bytes,
            artifacts_size_bytes,
        ) = row

        # Deserialize JSON
        try:
            metadata = json.loads(metadata_json) if metadata_json else {}
            state = json.loads(state_json)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON in checkpoint for {operation_id}: {e}"
            ) from e

        # Load artifacts from filesystem (if present)
        artifacts = {}
        if artifacts_path and Path(artifacts_path).exists():
            artifacts = self._load_artifacts(Path(artifacts_path))

        return {
            "operation_id": operation_id,
            "checkpoint_id": checkpoint_id,
            "checkpoint_type": checkpoint_type,
            "created_at": (
                created_at.isoformat()
                if hasattr(created_at, "isoformat")
                else str(created_at)
            ),
            "metadata": metadata,
            "state": state,
            "artifacts_path": artifacts_path,
            "artifacts": artifacts,
            "state_size_bytes": state_size_bytes,
            "artifacts_size_bytes": artifacts_size_bytes,
        }

    def delete_checkpoint(self, operation_id: str) -> None:
        """
        Delete checkpoint from database + filesystem.

        Args:
            operation_id: Operation ID

        Implementation:
            1. Load checkpoint to get artifacts_path
            2. Delete artifacts from filesystem
            3. DELETE from operation_checkpoints table
            4. Commit transaction

        Note: Idempotent (safe to call multiple times)
        """
        conn, cursor = self._get_connection()

        # Load checkpoint to get artifacts_path
        checkpoint = self.load_checkpoint(operation_id)

        # Delete artifacts from filesystem (if present)
        if checkpoint and checkpoint.get("artifacts_path"):
            artifacts_path = Path(checkpoint["artifacts_path"])
            if artifacts_path.exists():
                shutil.rmtree(artifacts_path, ignore_errors=True)

        # DELETE from operation_checkpoints table
        sql = "DELETE FROM operation_checkpoints WHERE operation_id = %s;"

        cursor.execute(sql, (operation_id,))
        conn.commit()

    def _write_artifacts_atomic(
        self, operation_id: str, artifacts: dict[str, bytes]
    ) -> str:
        """
        Write artifacts to filesystem using atomic temp → rename pattern.

        Args:
            operation_id: Operation ID (used in directory name)
            artifacts: Dictionary mapping filename to binary data

        Returns:
            Path to artifacts directory
        """
        # Create artifacts directory for this operation
        artifacts_dir = self.artifacts_dir / f"artifacts_{operation_id}"

        # Write to temp directory first (atomic)
        temp_dir = Path(
            tempfile.mkdtemp(prefix="checkpoint_temp_", dir=self.artifacts_dir)
        )

        try:
            # Write all artifact files to temp directory
            for filename, data in artifacts.items():
                file_path = temp_dir / filename
                file_path.write_bytes(data)

            # Atomic rename (replaces old artifacts if present)
            if artifacts_dir.exists():
                shutil.rmtree(artifacts_dir)

            temp_dir.rename(artifacts_dir)

            return str(artifacts_dir)

        except Exception:
            # Cleanup temp directory on error
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    def _load_artifacts(self, artifacts_path: Path) -> dict[str, bytes]:
        """
        Load artifacts from filesystem.

        Args:
            artifacts_path: Path to artifacts directory

        Returns:
            Dictionary mapping filename to binary data
        """
        artifacts: dict[str, bytes] = {}

        if not artifacts_path.exists() or not artifacts_path.is_dir():
            return artifacts

        for file_path in artifacts_path.iterdir():
            if file_path.is_file():
                artifacts[file_path.name] = file_path.read_bytes()

        return artifacts

    def _calculate_artifacts_size(self, artifacts_path: Path) -> int:
        """
        Calculate total size of artifacts directory (bytes).

        Args:
            artifacts_path: Path to artifacts directory

        Returns:
            Total size in bytes
        """
        if not artifacts_path.exists():
            return 0

        total_size = 0
        for file_path in artifacts_path.iterdir():
            if file_path.is_file():
                total_size += file_path.stat().st_size

        return total_size

    def close(self):
        """Close database connection."""
        if self._cursor:
            self._cursor.close()
        if self._conn:
            self._conn.close()

    def __del__(self):
        """Cleanup on destruction."""
        self.close()
