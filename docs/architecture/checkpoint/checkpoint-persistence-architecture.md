# Checkpoint Persistence System - Architecture Document
**Document Version:** 1.0
**Date:** January 2025
**Status:** Proposed
**Authors:** Principal Architect
---
## Table of Contents
1. [System Overview](#1-system-overview)
2. [Component Architecture](#2-component-architecture)
3. [Data Models](#3-data-models)
4. [Database Schema](#4-database-schema)
5. [Checkpoint Flow](#5-checkpoint-flow)
6. [Resume Flow](#6-resume-flow)
7. [Integration Points](#7-integration-points)
8. [State Management](#8-state-management)
9. [Error Handling and Recovery](#9-error-handling-and-recovery)
10. [Performance Considerations](#10-performance-considerations)
11. [Security and Validation](#11-security-and-validation)
---
## 1. System Overview
### 1.1 High-Level Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                         KTRDR API Layer                         │
│                                                                 │
│  ┌──────────────────┐         ┌──────────────────┐            │
│  │ Training Service │         │Backtesting Service│            │
│  └────────┬─────────┘         └────────┬─────────┘            │
│           │                             │                       │
│           └──────────┬──────────────────┘                       │
│                      │                                          │
│           ┌──────────▼──────────┐                              │
│           │ Operations Service   │                              │
│           │  (Enhanced)          │                              │
│           └──────────┬───────────┘                              │
│                      │                                          │
└──────────────────────┼──────────────────────────────────────────┘
                       │
            ┌──────────▼──────────────────────────┐
            │      Checkpoint Service (NEW)       │
            │                                      │
            │  Storage:                            │
            │  • PostgreSQL (state + metadata)    │
            │  • Filesystem (PyTorch .pt files)   │
            │                                      │
            │  Policy: Loaded from config file    │
            └──────────────────────────────────────┘
```
### 1.2 Component Responsibilities
| Component | Responsibility |
|-----------|---------------|
| **CheckpointService** | Checkpoint CRUD operations, cleanup, validation |
| **CheckpointPolicy** | Configuration (loaded from config/persistence.yaml) |
| **OperationsService** | Operation lifecycle, resume orchestration |
| **PostgreSQL** | Persist operation metadata and checkpoint state |
| **Filesystem** | Store large binary artifacts (model .pt files) |
| **TrainingService** | Training resume logic, checkpoint integration |
| **BacktestingService** | Backtest resume logic, checkpoint integration |
---
## 2. Component Architecture
### 2.1 CheckpointService
**Purpose:** Central service for all checkpoint operations.
**Interface:**
```python
class CheckpointService:
    """
    Checkpoint service for managing operation state persistence.

    Design: ONE checkpoint per operation (the latest).
    When new checkpoint is saved, old one is replaced (UPSERT).

    Responsibilities:
    - Save/load checkpoints from PostgreSQL + filesystem
    - Manage checkpoint lifecycle (create, retrieve, delete)
    - Handle artifact storage (model weights, optimizer state)
    - Enforce retention policies
    """

    def save_checkpoint(
        operation_id: str,
        state: dict,
        checkpoint_type: str,
        metadata: dict | None
    ) -> str:
        """
        Save checkpoint (replaces existing checkpoint if present).
        Uses PostgreSQL UPSERT to replace old checkpoint.
        Deletes old artifact files after successful UPSERT.
        Returns checkpoint_id.
        """

    def load_checkpoint(
        operation_id: str
    ) -> dict | None:
        """
        Load checkpoint for operation (returns None if not found).
        Loads state from PostgreSQL and artifacts from filesystem.
        """

    def delete_checkpoint(
        operation_id: str
    ) -> None:
        """
        Delete checkpoint for operation.
        Removes DB record and artifact files.
        """
```
**Dependencies:**
- PostgreSQL connection (via psycopg2)
- Filesystem access (for artifact storage)
- Configuration (retention policies, paths)
**State:**
- Stateless (all state in PostgreSQL)
- Connection pool for database connections
### 2.2 CheckpointPolicy
**Purpose:** Encapsulate checkpoint decision logic.
**Source:** Loaded from `config/persistence.yaml` at startup.
**Interface:**
```python
@dataclass
class CheckpointPolicy:
    """Time-based checkpoint policy configuration."""
    checkpoint_interval_seconds: float  # Target time between checkpoints (e.g., 300 = 5 min)
    force_checkpoint_every_n: int       # Safety net: force checkpoint every N boundaries
    delete_on_completion: bool          # Delete checkpoint when operation completes
    checkpoint_on_failure: bool         # Save checkpoint when operation fails
 
 
class CheckpointDecisionEngine:
    """Determines when to checkpoint based on policy."""

    def should_checkpoint(
        policy: CheckpointPolicy,
        last_checkpoint_time: float,
        current_time: float,
        natural_boundary: int,  # epoch or bar number
        total_boundaries: int
    ) -> bool:
        """
        Decide whether to checkpoint now.

        Algorithm:
        1. Check if at forced boundary (safety net)
        2. Check if enough time elapsed since last checkpoint
        3. Return decision
        """
```
**State:**
- Stateless (pure functions)
- Policy configuration passed as parameter
### 2.3 Enhanced OperationsService
**Purpose:** Manage operation lifecycle with checkpoint integration.
**New Methods:**
```python
class OperationsService:
    """Enhanced with checkpoint support."""
 
    # Existing methods (unchanged)
    async def create_operation(...) -> OperationInfo
    async def start_operation(...)
    async def update_progress(...)
    async def complete_operation(...)
    async def fail_operation(...)
 
    # NEW: Persistence
    async def persist_operation(operation: OperationInfo) -> None:
        """Save operation to PostgreSQL."""

    async def load_operations(status: OperationStatus | None) -> list[OperationInfo]:
        """Load operations from PostgreSQL."""

    # NEW: Startup Recovery
    async def recover_interrupted_operations(self) -> int:
        """
        Mark all RUNNING operations as FAILED on startup.
        Called during API startup to recover orphaned operations.

        Algorithm:
        1. Load all RUNNING operations from PostgreSQL
        2. Mark each as FAILED with error: "Operation interrupted by API restart"
        3. Log recovery count
        4. Return number of operations recovered

        Returns:
            Number of operations recovered
        """

    # NEW: Resume
    async def resume_operation(
        original_operation_id: str
    ) -> dict[str, Any]:
        """
        Resume operation from checkpoint.

        Algorithm:
        1. Validate original operation is resumable (FAILED/CANCELLED)
        2. Load latest checkpoint via CheckpointService
        3. Create NEW operation with new operation_id
        4. Dispatch to appropriate service (TrainingService/BacktestingService)
        5. Delete original operation's checkpoint
        6. Return new operation info
        """

    # NEW: Cleanup
    async def cleanup_on_completion(operation_id: str) -> None:
        """
        Delete checkpoint when operation completes.
        Called by complete_operation() if policy.delete_on_completion is True.
        """
```
**State:**
- In-memory registry (existing)
- PostgreSQL backing store (new)

**API Startup Flow:**
On API startup (via `@app.on_event("startup")`), the system automatically recovers interrupted operations:
1. Call `operations_service.recover_interrupted_operations()`
2. Load all operations with status = RUNNING from database
3. Mark each as FAILED with error: "Operation interrupted by API restart"
4. Log: "Startup recovery: N operations marked as FAILED"
5. These operations are now resumable via `resume_operation()`

This handles the primary use case: **API crashes/restarts**.
### 2.4 Training Integration Components
**ModelTrainer Enhancement:**
```python
class ModelTrainer:
    """Enhanced with checkpoint support."""
 
    # NEW: Checkpoint tracking
    checkpoint_service: CheckpointService | None
    checkpoint_policy: CheckpointPolicy
    last_checkpoint_time: float | None
    operation_id: str | None
 
    # MODIFIED: Training loop
    def train(self, model, X_train, y_train, X_val, y_val):
        """
        Enhanced training loop with checkpointing.
 
        Pseudocode:
        1. Initialize checkpoint tracking
        2. For each epoch:
           a. Train epoch
           b. Check if should_checkpoint()
           c. If yes, save_checkpoint()
           d. Update last_checkpoint_time
        3. On completion, final checkpoint (if policy allows)
        """
 
    # NEW: Checkpoint operations
    def _should_checkpoint(epoch, current_time) -> bool:
        """Delegate to CheckpointDecisionEngine."""
 
    def _save_checkpoint(epoch, model, optimizer, scheduler):
        """
        Capture training state and save via CheckpointService.
 
        State captured:
        - Current epoch
        - Model state_dict
        - Optimizer state_dict
        - Scheduler state_dict
        - Training history
        - Best model state
        - Configuration
        """
 
    # NEW: Resume support
    def load_from_checkpoint(checkpoint_state: dict):
        """
        Restore training state from checkpoint.
 
        Restoration:
        - Load model.state_dict
        - Load optimizer.state_dict
        - Load scheduler.state_dict
        - Restore history
        - Set start_epoch
        """
```
**TrainingService Enhancement:**
```python
class TrainingService(ServiceOrchestrator):
    """Enhanced with resume support."""
 
    # NEW: Resume method
    async def resume_training(
        new_operation_id: str,
        checkpoint_state: dict
    ) -> dict:
        """
        Resume training from checkpoint.
 
        Algorithm:
        1. Extract configuration from checkpoint
        2. Determine resume epoch (checkpoint epoch + 1)
        3. Create ModelTrainer with resume state
        4. Start training from resume epoch
        5. Return results
        """
```
### 2.5 Backtesting Integration Components
**BacktestingEngine Enhancement:**
```python
class BacktestingEngine:
    """Enhanced with checkpoint support."""
 
    # NEW: Checkpoint tracking
    checkpoint_service: CheckpointService | None
    checkpoint_policy: CheckpointPolicy
    last_checkpoint_time: float | None
    operation_id: str | None
 
    # MODIFIED: Backtest loop
    def run(self, bridge, cancellation_token):
        """
        Enhanced backtest loop with checkpointing.
 
        Pseudocode:
        1. Initialize checkpoint tracking
        2. For each bar:
           a. Process bar
           b. Check if should_checkpoint()
           c. If yes, save_checkpoint()
           d. Update last_checkpoint_time
        3. On completion, final checkpoint (if policy allows)
        """
 
    # NEW: Checkpoint operations
    def _save_checkpoint(bar_idx, timestamp, price):
        """
        Capture backtest state and save via CheckpointService.
 
        State captured:
        - Current bar index
        - Current timestamp
        - PositionManager state
        - PerformanceTracker state
        - DecisionOrchestrator state
        - Configuration
        """
 
    # NEW: Resume support
    def load_from_checkpoint(checkpoint_state: dict):
        """
        Restore backtest state from checkpoint.
 
        Restoration:
        - Restore PositionManager
        - Restore PerformanceTracker
        - Restore DecisionOrchestrator
        - Set start_bar_index
        """
```
**PositionManager State Capture:**
```python
class PositionManager:
    """Enhanced with state capture."""
 
    # NEW: State serialization
    def get_state(self) -> dict:
        """
        Capture position manager state.
 
        Returns:
            {
                "current_position": str,
                "available_capital": float,
                "shares_held": int,
                "avg_entry_price": float,
                "trade_history": [Trade.to_dict() for each trade],
                "open_trade": OpenTrade.to_dict() if exists
            }
        """
 
    def restore_state(self, state: dict):
        """Restore from serialized state."""
```
**PerformanceTracker State Capture:**
```python
class PerformanceTracker:
    """Enhanced with state capture."""
 
    def get_state(self) -> dict:
        """
        Capture performance tracker state.
 
        Returns:
            {
                "equity_curve": [
                    {
                        "timestamp": str,
                        "portfolio_value": float,
                        "position": str,
                        "price": float
                    }
                    for each point
                ]
            }
        """
 
    def restore_state(self, state: dict):
        """Restore from serialized state."""
```
---
## 3. Data Models
### 3.1 Checkpoint State Structure
#### 3.1.1 Training Checkpoint State
```python
TrainingCheckpointState = {
    # Metadata
    "checkpoint_version": "1.0",
    "ktrdr_version": "0.5.0",
    "checkpoint_type": "epoch_snapshot",
    "created_at": "2025-01-17T12:00:00Z",
 
    # Training progress
    "epoch": 45,
    "total_epochs": 100,
    "batch": 0,  # Always 0 for epoch-level checkpoints
 
    # Training configuration
    "config": {
        "learning_rate": 0.001,
        "batch_size": 32,
        "epochs": 100,
        "optimizer": "adam",
        # ... full training config
    },
 
    # Training history (all epochs so far)
    "training_history": [
        {
            "epoch": 0,
            "train_loss": 0.823,
            "train_accuracy": 0.65,
            "val_loss": 0.891,
            "val_accuracy": 0.58,
            "learning_rate": 0.001,
            "duration": 12.5,
            "timestamp": "2025-01-17T10:00:00Z"
        },
        # ... one entry per epoch
    ],
 
    # Best model tracking
    "best_val_accuracy": 0.72,
    "best_epoch": 32,
 
    # Early stopping state
    "early_stopping": {
        "counter": 5,
        "best_score": 0.72,
        "patience": 10
    },
 
    # Data split info (for validation)
    "data_split": {
        "train_samples": 7200,
        "val_samples": 1800,
        "test_samples": 1000
    },
 
    # Artifacts (stored separately, referenced here)
    # These are stored as .pt files on disk, not in JSON
    "artifacts": {
        "model_state_dict": "models/checkpoints/{checkpoint_id}/model_state_dict.pt",
        "optimizer_state_dict": "models/checkpoints/{checkpoint_id}/optimizer_state_dict.pt",
        "scheduler_state_dict": "models/checkpoints/{checkpoint_id}/scheduler_state_dict.pt",
        "best_model_state": "models/checkpoints/{checkpoint_id}/best_model_state.pt"
    }
}
```
#### 3.1.2 Backtesting Checkpoint State
```python
BacktestCheckpointState = {
    # Metadata
    "checkpoint_version": "1.0",
    "ktrdr_version": "0.5.0",
    "checkpoint_type": "bar_snapshot",
    "created_at": "2025-01-17T12:00:00Z",
 
    # Backtest progress
    "current_bar_index": 15000,
    "total_bars": 50000,
    "current_timestamp": "2024-06-15T14:30:00Z",
    "current_price": 185.25,
 
    # Backtest configuration
    "config": {
        "symbol": "AAPL",
        "timeframe": "1h",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "initial_capital": 100000.0,
        "commission": 0.001,
        "slippage": 0.001
    },
 
    # Position manager state
    "position_manager": {
        "current_position": "LONG",
        "available_capital": 52000.0,
        "shares_held": 100,
        "avg_entry_price": 180.00,
 
        "trade_history": [
            {
                "entry_price": 175.00,
                "exit_price": 178.50,
                "entry_time": "2024-03-15T10:00:00Z",
                "exit_time": "2024-03-20T15:30:00Z",
                "shares": 100,
                "gross_pnl": 350.0,
                "net_pnl": 332.5,
                "side": "LONG"
            },
            # ... all completed trades
        ],
 
        "open_trade": {
            "entry_price": 180.00,
            "entry_time": "2024-06-10T09:30:00Z",
            "shares": 100,
            "side": "LONG"
        }
    },
 
    # Performance tracker state
    "performance_tracker": {
        "equity_curve": [
            {
                "timestamp": "2024-01-01T09:30:00Z",
                "portfolio_value": 100000.0,
                "position": "FLAT",
                "price": 170.00
            },
            # ... all points in equity curve
        ]
    },
 
    # Decision orchestrator state (feature cache)
    "decision_orchestrator": {
        "current_position": "LONG",
        "feature_cache_size": 15000  # Number of bars cached
        # Note: Feature cache not serialized (recomputed on resume)
    }
}
```
### 3.2 Checkpoint Metadata
```python
CheckpointMetadata = {
    "checkpoint_id": "op_training_20250117_100000_1737115200",
    "operation_id": "op_training_20250117_100000",
    "checkpoint_type": "epoch_snapshot",
    "created_at": "2025-01-17T12:00:00Z",
 
    # Queryable metrics (for UI/API)
    "metadata": {
        # Training-specific
        "epoch": 45,
        "val_accuracy": 0.72,
        "val_loss": 0.65,
 
        # Or backtesting-specific
        "bar_index": 15000,
        "portfolio_value": 107500.0,
        "trades_executed": 25
    },
 
    # Storage locations
    "state_json_size_bytes": 125000,
    "artifacts_path": "data/checkpoints/artifacts/op_training_20250117_100000_1737115200",
    "artifacts_size_bytes": 52000000  # 52 MB
}
```
---
## 4. Database Schema
### 4.1 PostgreSQL Tables
```sql
-- ================================================================
-- operations table
-- Stores operation metadata (enhanced from in-memory only)
-- ================================================================
CREATE TABLE operations (
    -- Primary key
    operation_id TEXT PRIMARY KEY,
 
    -- Operation classification
    operation_type TEXT NOT NULL,  -- 'training', 'backtesting', etc.
    status TEXT NOT NULL,  -- 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED'
 
    -- Timestamps
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    last_updated TIMESTAMP,
 
    -- Operation data (JSON)
    metadata_json TEXT,  -- OperationMetadata as JSON
    result_summary_json TEXT,  -- Final results (set on completion)
 
    -- Error tracking
    error_message TEXT,
 
    -- Indexes for common queries
    INDEX idx_operations_status (status),
    INDEX idx_operations_type (operation_type),
    INDEX idx_operations_created_at (created_at DESC),
    INDEX idx_operations_status_type (status, operation_type)
);
 
-- ================================================================
-- operation_checkpoints table
-- Stores checkpoint metadata and state (ephemeral)
-- Design: ONE checkpoint per operation (the latest)
-- ================================================================
CREATE TABLE operation_checkpoints (
    -- Primary key: operation_id (only 1 checkpoint per operation)
    operation_id TEXT PRIMARY KEY,

    -- Checkpoint identification
    checkpoint_id TEXT NOT NULL,  -- For reference/debugging

    -- Checkpoint classification
    checkpoint_type TEXT NOT NULL,  -- 'epoch_snapshot', 'bar_snapshot', 'final'

    -- Timestamp
    created_at TIMESTAMP NOT NULL,

    -- Checkpoint data
    checkpoint_metadata_json TEXT,  -- Small queryable metadata (epoch, metrics)
    state_json TEXT NOT NULL,  -- Full checkpoint state (without artifacts)

    -- Artifacts reference
    artifacts_path TEXT,  -- Path to directory with .pt files

    -- Size tracking (for monitoring)
    state_size_bytes BIGINT,
    artifacts_size_bytes BIGINT,

    -- Foreign key constraint (cascade delete)
    FOREIGN KEY (operation_id)
        REFERENCES operations(operation_id)
        ON DELETE CASCADE
);
 
-- ================================================================
-- Automatic cleanup trigger
-- Delete checkpoint when operation completes
-- ================================================================
CREATE OR REPLACE FUNCTION cleanup_checkpoint_on_completion()
RETURNS TRIGGER AS $$
BEGIN
    -- Only cleanup if status changed to COMPLETED and policy allows
    IF NEW.status = 'COMPLETED'
       AND OLD.status NOT IN ('COMPLETED', 'FAILED', 'CANCELLED') THEN

        -- Note: Actual artifact file deletion handled by application
        -- This just removes DB record (artifacts cleaned up via CheckpointService)
        DELETE FROM operation_checkpoints
        WHERE operation_id = NEW.operation_id;

    END IF;

    -- FAILED and CANCELLED operations keep checkpoint for resume

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_cleanup_checkpoint
AFTER UPDATE ON operations
FOR EACH ROW
EXECUTE FUNCTION cleanup_checkpoint_on_completion();
```
### 4.2 Artifact Storage Layout
```
data/checkpoints/artifacts/
├── {checkpoint_id_1}/
│   ├── model_state_dict.pt
│   ├── optimizer_state_dict.pt
│   ├── scheduler_state_dict.pt
│   └── best_model_state.pt
├── {checkpoint_id_2}/
│   ├── model_state_dict.pt
│   └── ...
└── {checkpoint_id_N}/
    └── ...

# Design: Only 1 checkpoint per operation
# When new checkpoint saved:
#   1. Save new artifacts to {new_checkpoint_id}/
#   2. UPSERT to operation_checkpoints (replaces old DB record)
#   3. Delete old artifacts directory (if different from new)
#
# On operation completion:
#   1. DELETE FROM operation_checkpoints (removes DB record)
#   2. CheckpointService.delete_checkpoint() (removes artifact directory)
```
---
## 5. Checkpoint Flow
### 5.0 API Startup Recovery Flow
```
┌─────────────────────────────────────────────────────────────────┐
│                  API Startup Recovery Flow                       │
└─────────────────────────────────────────────────────────────────┘

[API Starts]
         │
         ├─ FastAPI @app.on_event("startup")
         │  │
         │  └─ startup_recovery()
         │     │
         │     ├─ Get OperationsService instance
         │     │
         │     └─ Call recover_interrupted_operations()
         │        │
         │        ├─ Query PostgreSQL:
         │        │  SELECT * FROM operations WHERE status = 'RUNNING'
         │        │
         │        ├─ Found operations: [op_1, op_2, op_3]
         │        │
         │        ├─ For each operation:
         │        │  │
         │        │  ├─ Update status to 'FAILED'
         │        │  ├─ Set error_message = "Operation interrupted by API restart"
         │        │  │
         │        │  └─ UPDATE operations
         │        │     SET status = 'FAILED',
         │        │         error_message = '...',
         │        │         completed_at = NOW()
         │        │     WHERE operation_id = 'op_1'
         │        │
         │        └─ Log: "Startup recovery: 3 operations marked as FAILED"
         │
         └─ API Ready (operations now resumable)

[Result]
- All orphaned RUNNING operations → FAILED
- Checkpoints preserved (can be resumed)
- Users see clear status: "Operation interrupted by API restart"
```

**Why This Matters:**
This solves the **primary use case**: API crashes/restarts. Without startup recovery, crashed operations would remain in RUNNING status forever and couldn't be resumed.

---
### 5.1 Training Checkpoint Flow
```
┌─────────────────────────────────────────────────────────────────┐
│                    Training Checkpoint Flow                      │
└─────────────────────────────────────────────────────────────────┘
 
[ModelTrainer.train() - Epoch Loop]
         │
         ├─ Epoch 1 starts
         │  └─ Initialize: last_checkpoint_time = now()
         │
         ├─ Epoch 2 completes
         │  └─ Check: should_checkpoint()
         │     └─ No (only 30 seconds elapsed)
         │
         ├─ Epoch 10 completes
         │  └─ Check: should_checkpoint()
         │     └─ Yes (5 minutes elapsed)
         │     └─ save_checkpoint()
         │         │
         │         ├─ Capture state:
         │         │  ├─ model.state_dict()
         │         │  ├─ optimizer.state_dict()
         │         │  ├─ training_history
         │         │  └─ best_model_state
         │         │
         │         ├─ CheckpointService.save_checkpoint()
         │         │  │
         │         │  ├─ Extract artifacts (model_state_dict, etc.)
         │         │  ├─ Save artifacts to disk:
         │         │  │  └─ torch.save(..., artifacts/{checkpoint_id}/model_state_dict.pt)
         │         │  │
         │         │  ├─ UPSERT into PostgreSQL:
         │         │  │  └─ INSERT INTO operation_checkpoints (...)
         │         │  │     ON CONFLICT (operation_id) DO UPDATE
         │         │  │     SET checkpoint_id = ..., state_json = ..., etc.
         │         │  │
         │         │  └─ Delete old artifacts directory (if different from new)
         │         │
         │         └─ Update: last_checkpoint_time = now()
         │
         ├─ Epoch 20 completes
         │  └─ Check: should_checkpoint()
         │     └─ Yes (5 minutes elapsed again)
         │     └─ save_checkpoint() (same flow as above)
         │
         └─ Epoch 100 completes (final)
            └─ Training complete
            └─ OperationsService.complete_operation()
               └─ Trigger: cleanup_checkpoint_on_completion()
                  └─ DELETE FROM operation_checkpoints WHERE operation_id = ...
                  └─ CheckpointService.delete_checkpoint()
                     └─ Remove artifact directory
```
### 5.2 Backtesting Checkpoint Flow
```
┌─────────────────────────────────────────────────────────────────┐
│                   Backtesting Checkpoint Flow                    │
└─────────────────────────────────────────────────────────────────┘
 
[BacktestingEngine.run() - Bar Loop]
         │
         ├─ Bar 50 (start after warm-up)
         │  └─ Initialize: last_checkpoint_time = now()
         │
         ├─ Bar 1000 completes
         │  └─ Check: should_checkpoint()
         │     └─ No (only 30 seconds elapsed)
         │
         ├─ Bar 5000 completes
         │  └─ Check: should_checkpoint()
         │     └─ Yes (5 minutes elapsed)
         │     └─ save_checkpoint()
         │         │
         │         ├─ Capture state:
         │         │  ├─ position_manager.get_state()
         │         │  ├─ performance_tracker.get_state()
         │         │  ├─ current_bar_index, timestamp, price
         │         │  └─ config
         │         │
         │         ├─ CheckpointService.save_checkpoint()
         │         │  └─ (same flow as training)
         │         │
         │         └─ Update: last_checkpoint_time = now()
         │
         ├─ Bar 10000 completes
         │  └─ (checkpoint again if 5 min elapsed)
         │
         └─ Bar 50000 completes (final)
            └─ Backtest complete
            └─ OperationsService.complete_operation()
               └─ Cleanup checkpoints (same as training)
```
### 5.3 Checkpoint Decision Algorithm
```python
def should_checkpoint(
    policy: CheckpointPolicy,
    last_checkpoint_time: float,
    current_time: float,
    natural_boundary: int,  # epoch or bar
    total_boundaries: int
) -> bool:
    """
    Checkpoint decision algorithm.

    Rules:
    1. Force checkpoint every N boundaries (safety net)
    2. Checkpoint if enough time elapsed since last checkpoint

    Decision tree:

    1. First boundary?
       └─ NO (skip, no progress yet)

    2. At forced boundary? (every N epochs/bars)
       └─ YES (safety net checkpoint)

    3. Enough time elapsed?
       └─ time_since_last >= checkpoint_interval_seconds?
          └─ YES (checkpoint)
          └─ NO (skip)

    4. Default: NO
    """

    # Step 1: First boundary check
    if natural_boundary == 0:
        return False

    # Step 2: Force checkpoint safety net
    if (natural_boundary + 1) % policy.force_checkpoint_every_n == 0:
        logger.debug(f"Force checkpoint at boundary {natural_boundary}")
        return True

    # Step 3: Time-based check
    if last_checkpoint_time is None:
        return False

    time_since_last = current_time - last_checkpoint_time

    if time_since_last >= policy.checkpoint_interval_seconds:
        return True

    # Step 4: Default
    return False
```
---
## 6. Resume Flow
### 6.1 Training Resume Flow
```
┌─────────────────────────────────────────────────────────────────┐
│                      Training Resume Flow                        │
└─────────────────────────────────────────────────────────────────┘
 
User: POST /api/v1/operations/{operation_id}/resume
         │
         ├─ OperationsService.resume_operation(operation_id)
         │  │
         │  ├─ Step 1: Validate
         │  │  ├─ Load original operation
         │  │  ├─ Check status (must be FAILED or CANCELLED)
         │  │  └─ If invalid: return 400 error
         │  │
         │  ├─ Step 2: Load checkpoint
         │  │  ├─ CheckpointService.load_checkpoint(operation_id)
         │  │  │  │
         │  │  │  ├─ Query PostgreSQL:
         │  │  │  │  └─ SELECT * FROM operation_checkpoints
         │  │  │  │     WHERE operation_id = {operation_id}
         │  │  │  │
         │  │  │  ├─ Parse state_json
         │  │  │  │
         │  │  │  ├─ Load artifacts from disk:
         │  │  │  │  ├─ torch.load(artifacts_path/model_state_dict.pt)
         │  │  │  │  ├─ torch.load(artifacts_path/optimizer_state_dict.pt)
         │  │  │  │  └─ torch.load(artifacts_path/scheduler_state_dict.pt)
         │  │  │  │
         │  │  │  └─ Return complete checkpoint_state
         │  │  │
         │  │  └─ If no checkpoint: return 404 error
         │  │
         │  ├─ Step 3: Create new operation
         │  │  ├─ Generate new operation_id
         │  │  ├─ Copy metadata from original
         │  │  ├─ Add "resumed_from" parameter
         │  │  ├─ INSERT INTO operations (...)
         │  │  └─ Return new OperationInfo
         │  │
         │  ├─ Step 4: Delete original checkpoint
         │  │  └─ CheckpointService.delete_checkpoint(original_operation_id)
         │  │     ├─ DELETE FROM operation_checkpoints WHERE operation_id = ...
         │  │     └─ Remove artifact directory
         │  │
         │  ├─ Step 5: Dispatch to TrainingService
         │  │  └─ TrainingService.resume_training(
         │  │        new_operation_id,
         │  │        checkpoint_state
         │  │     )
         │  │
         │  └─ Step 6: Return response
         │     └─ {
         │           "original_operation_id": "op_training_..._100000",
         │           "new_operation_id": "op_training_..._140000",
         │           "resumed_from_checkpoint": "checkpoint_epoch_45"
         │        }
         │
         └─ TrainingService.resume_training(new_operation_id, checkpoint_state)
            │
            ├─ Extract from checkpoint:
            │  ├─ start_epoch = checkpoint_state["epoch"] + 1  # 46
            │  ├─ total_epochs = checkpoint_state["total_epochs"]  # 100
            │  ├─ config = checkpoint_state["config"]
            │  ├─ model_state_dict = checkpoint_state["artifacts"]["model_state_dict"]
            │  └─ optimizer_state_dict = checkpoint_state["artifacts"]["optimizer_state_dict"]
            │
            ├─ Setup training:
            │  ├─ Load data (same as original)
            │  ├─ Create model, load model_state_dict
            │  ├─ Create optimizer, load optimizer_state_dict
            │  ├─ Restore training history
            │  └─ Set current_epoch = start_epoch
            │
            ├─ Start training loop:
            │  └─ for epoch in range(start_epoch, total_epochs):
            │     └─ (normal training continues from epoch 46)
            │
            └─ On completion:
               └─ Save final model
               └─ Delete checkpoints
               └─ Return results
```
### 6.2 Backtesting Resume Flow
```
┌─────────────────────────────────────────────────────────────────┐
│                    Backtesting Resume Flow                       │
└─────────────────────────────────────────────────────────────────┘
 
User: POST /api/v1/operations/{operation_id}/resume
         │
         ├─ OperationsService.resume_operation(operation_id)
         │  └─ (same validation and checkpoint loading as training)
         │  └─ Dispatch to BacktestingService
         │
         └─ BacktestingService.resume_backtest(new_operation_id, checkpoint_state)
            │
            ├─ Extract from checkpoint:
            │  ├─ start_bar_index = checkpoint_state["current_bar_index"] + 1
            │  ├─ position_manager_state = checkpoint_state["position_manager"]
            │  ├─ performance_tracker_state = checkpoint_state["performance_tracker"]
            │  └─ config = checkpoint_state["config"]
            │
            ├─ Setup backtest:
            │  ├─ Load data (same as original)
            │  ├─ Create PositionManager, restore state
            │  ├─ Create PerformanceTracker, restore state
            │  ├─ Create DecisionOrchestrator
            │  │  └─ Rebuild feature cache (recompute from start_bar_index)
            │  └─ Set current_bar_index = start_bar_index
            │
            ├─ Start backtest loop:
            │  └─ for bar_idx in range(start_bar_index, len(data)):
            │     └─ (normal backtesting continues from bar 15001)
            │
            └─ On completion:
               └─ Generate results
               └─ Delete checkpoints
               └─ Return results
```
### 6.3 Resume Error Handling
```
┌─────────────────────────────────────────────────────────────────┐
│                     Resume Error Scenarios                       │
└─────────────────────────────────────────────────────────────────┘
 
Scenario 1: No checkpoint found
   User: resume op_training_20250117_100000
   ├─ CheckpointService.load_checkpoint() → None
   └─ Response: 404 "No checkpoint found, cannot resume"
 
Scenario 2: Checkpoint corrupted
   User: resume op_training_20250117_100000
   ├─ CheckpointService.load_checkpoint()
   │  ├─ JSON parse error or missing artifacts
   │  └─ Raise CheckpointCorruptedError
   └─ Response: 500 "Checkpoint corrupted, cannot resume"
 
Scenario 3: Version mismatch
   User: resume op_training_20250117_100000
   ├─ checkpoint_state["ktrdr_version"] = "0.4.0"
   ├─ Current KTRDR version = "0.5.0"
   └─ Response: 400 "Checkpoint from incompatible version, cannot resume"
 
Scenario 4: Data not available
   User: resume op_training_20250117_100000
   ├─ Checkpoint loads successfully
   ├─ TrainingService.resume_training()
   │  ├─ Attempt to load data
   │  └─ DataNotFoundError (data deleted/moved)
   └─ Response: 500 "Training data not found, cannot resume"
 
Scenario 5: Resume successful
   User: resume op_training_20250117_100000
   ├─ All validations pass
   ├─ New operation created: op_training_20250117_140000
   ├─ Training resumes from epoch 46
   └─ Response: 200 with new operation_id
```
---
## 7. Integration Points
### 7.1 ServiceOrchestrator Integration
```python
# ktrdr/async_infrastructure/service_orchestrator.py
 
class ServiceOrchestrator(ABC):
    """
    Enhanced with checkpoint service injection.
    """
 
    def __init__(self):
        # Existing initialization
        self.adapter = self._initialize_adapter()
        self._progress_renderer = ...
 
        # NEW: Checkpoint service injection
        self.checkpoint_service = self._get_checkpoint_service()
        self.checkpoint_policy = self._get_checkpoint_policy()
 
    def _get_checkpoint_service(self) -> CheckpointService | None:
        """
        Get checkpoint service instance.
 
        Default implementation returns None (no checkpointing).
        Subclasses override to enable checkpointing.
        """
        return None
 
    def _get_checkpoint_policy(self) -> CheckpointPolicy:
        """
        Get checkpoint policy for this service.
 
        Subclasses override to customize policy.
        """
        return CheckpointPolicy()  # Default policy
 
    async def start_managed_operation(
        self,
        operation_name: str,
        operation_type: str,
        operation_func: Callable,
        *args,
        **kwargs
    ) -> dict[str, Any]:
        """
        Enhanced to inject checkpoint service into operation.
        """
        # Existing logic...
 
        # NEW: Inject checkpoint service if available
        if self.checkpoint_service and "checkpoint_service" not in kwargs:
            kwargs["checkpoint_service"] = self.checkpoint_service
            kwargs["checkpoint_policy"] = self.checkpoint_policy
            kwargs["operation_id"] = operation_id
 
        # Execute operation
        result = await operation_func(*args, **kwargs)
 
        return result
```
### 7.2 TrainingService Integration
```python
# ktrdr/api/services/training/training_service.py
 
class TrainingService(ServiceOrchestrator):
    """Enhanced with checkpoint support."""
 
    def __init__(self):
        super().__init__()
        # Checkpoint service injected by ServiceOrchestrator
 
    def _get_checkpoint_service(self) -> CheckpointService:
        """Return checkpoint service instance."""
        return get_checkpoint_service()
 
    def _get_checkpoint_policy(self) -> CheckpointPolicy:
        """Return training-specific checkpoint policy."""
        return CHECKPOINT_POLICIES["training"]
 
    async def train_multi_symbol_strategy(
        self,
        strategy_config_path: str,
        symbols: list[str],
        timeframes: list[str],
        start_date: str,
        end_date: str,
        operation_id: str,  # Injected by start_managed_operation
        checkpoint_service: CheckpointService,  # Injected
        checkpoint_policy: CheckpointPolicy,  # Injected
        **kwargs
    ) -> dict:
        """
        Train with checkpoint support.
        """
        # Load config, data, etc. (existing logic)
 
        # Create ModelTrainer with checkpoint support
        trainer = ModelTrainer(
            config=training_config,
            progress_callback=progress_callback,
            cancellation_token=cancellation_token,
        )
 
        # Inject checkpoint support
        trainer.checkpoint_service = checkpoint_service
        trainer.checkpoint_policy = checkpoint_policy
        trainer.operation_id = operation_id
 
        # Train (with checkpointing)
        result = trainer.train(model, X_train, y_train, X_val, y_val)
 
        return result
 
    # NEW: Resume support
    async def resume_training(
        self,
        new_operation_id: str,
        checkpoint_state: dict,
    ) -> dict:
        """Resume training from checkpoint."""
        # Implementation as described in Resume Flow
```
### 7.3 BacktestingService Integration
```python
# ktrdr/backtesting/backtesting_service.py
 
class BacktestingService(ServiceOrchestrator):
    """Enhanced with checkpoint support."""
 
    def __init__(self):
        super().__init__()
        # Checkpoint service injected by ServiceOrchestrator
 
    def _get_checkpoint_service(self) -> CheckpointService:
        """Return checkpoint service instance."""
        return get_checkpoint_service()
 
    def _get_checkpoint_policy(self) -> CheckpointPolicy:
        """Return backtesting-specific checkpoint policy."""
        return CHECKPOINT_POLICIES["backtesting"]
 
    async def run_backtest(
        self,
        symbol: str,
        timeframe: str,
        strategy_config_path: str,
        model_path: str,
        start_date: datetime,
        end_date: datetime,
        operation_id: str,  # Injected
        checkpoint_service: CheckpointService,  # Injected
        checkpoint_policy: CheckpointPolicy,  # Injected
        **kwargs
    ) -> dict:
        """Run backtest with checkpoint support."""
        # Create engine
        engine = BacktestingEngine(config=backtest_config)
 
        # Inject checkpoint support
        engine.checkpoint_service = checkpoint_service
        engine.checkpoint_policy = checkpoint_policy
        engine.operation_id = operation_id
 
        # Run backtest (with checkpointing)
        results = await asyncio.to_thread(
            engine.run,
            bridge=bridge,
            cancellation_token=cancellation_token
        )
 
        return results.to_dict()
 
    # NEW: Resume support
    async def resume_backtest(
        self,
        new_operation_id: str,
        checkpoint_state: dict,
    ) -> dict:
        """Resume backtest from checkpoint."""
        # Implementation as described in Resume Flow
```
---
## 8. State Management
### 8.1 State Lifecycle
```
┌─────────────────────────────────────────────────────────────────┐
│                     Checkpoint State Lifecycle                   │
└─────────────────────────────────────────────────────────────────┘
 
[Operation Created]
   └─ operations table: INSERT (status=PENDING)

[Operation Started]
   └─ operations table: UPDATE (status=RUNNING)

[First Checkpoint]
   ├─ Checkpoint created (epoch 5 or bar 1000)
   ├─ operation_checkpoints table: INSERT (operation_id as PK)
   └─ Artifacts: create directory /checkpoint_1/, save .pt files

[Second Checkpoint - UPSERT Pattern]
   ├─ Checkpoint created (epoch 10 or bar 5000)
   ├─ operation_checkpoints table: UPSERT (ON CONFLICT operation_id DO UPDATE)
   │  └─ Replaces previous checkpoint record atomically
   ├─ Artifacts: create directory /checkpoint_2/, save .pt files
   └─ Cleanup: DELETE old artifacts /checkpoint_1/ (only 1 checkpoint exists now)

[Nth Checkpoint]
   └─ (repeat UPSERT pattern - only 1 checkpoint per operation at any time)

[Operation Completes]
   ├─ operations table: UPDATE (status=COMPLETED, result_summary)
   ├─ Trigger: cleanup_checkpoint_on_completion()
   ├─ operation_checkpoints table: DELETE checkpoint for this operation
   └─ Artifacts: remove checkpoint directory

[Operation Fails]
   ├─ operations table: UPDATE (status=FAILED, error_message)
   └─ Checkpoint PRESERVED for resume (trigger does NOT delete FAILED checkpoints)

[Operation Cancelled]
   ├─ operations table: UPDATE (status=CANCELLED)
   └─ Checkpoint PRESERVED for resume (trigger does NOT delete CANCELLED checkpoints)
```
### 8.2 Concurrent Access Patterns
```
┌─────────────────────────────────────────────────────────────────┐
│                    Concurrent Access Scenarios                   │
└─────────────────────────────────────────────────────────────────┘
 
Scenario 1: Single operation running
   ├─ Training thread: epoch loop, checkpoint every 5 min
   ├─ API thread: GET /operations/{id} (read status/progress)
   └─ No conflict (operations table read, checkpoints not queried)
 
Scenario 2: Operation completing while user queries
   ├─ Training thread: complete operation → trigger cleanup
   ├─ API thread: GET /operations/{id}/checkpoints
   └─ Potential race: checkpoints deleted mid-query
       ├─ Solution: PostgreSQL transaction isolation
       └─ Query returns snapshot before deletion
 
Scenario 3: User resumes while checkpoint cleanup running
   ├─ Cleanup thread: DELETE FROM operation_checkpoints
   ├─ API thread: resume_operation() → load_checkpoint()
   └─ Potential race: checkpoint deleted before load
       ├─ Solution: Atomic check-and-load in transaction
       └─ If checkpoint missing, return 404
 
Scenario 4: Multiple operations checkpointing simultaneously
   ├─ Training 1: save_checkpoint() for op_1
   ├─ Training 2: save_checkpoint() for op_2
   └─ No conflict (different operation_ids, independent transactions)
```
### 8.3 Transaction Boundaries
```python
# CheckpointService.save_checkpoint() transaction
def save_checkpoint(...) -> str:
    """
    Transaction ensures atomic checkpoint update.
    Uses UPSERT to replace old checkpoint with new one.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Step 1: Get old checkpoint info (to cleanup old artifacts)
        cursor.execute("""
            SELECT artifacts_path FROM operation_checkpoints
            WHERE operation_id = %s
        """, (operation_id,))
        old_row = cursor.fetchone()
        old_artifacts_path = old_row["artifacts_path"] if old_row else None

        # Step 2: Save new artifacts to disk FIRST (outside transaction)
        new_artifacts_path = _save_artifacts_to_disk(checkpoint_id, artifacts)

        # Step 3: UPSERT checkpoint record (inside transaction)
        conn.begin()
        cursor.execute("""
            INSERT INTO operation_checkpoints (
                operation_id, checkpoint_id, created_at, state_json, artifacts_path,
                checkpoint_type, checkpoint_metadata_json, state_size_bytes, artifacts_size_bytes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (operation_id) DO UPDATE
            SET checkpoint_id = EXCLUDED.checkpoint_id,
                created_at = EXCLUDED.created_at,
                state_json = EXCLUDED.state_json,
                artifacts_path = EXCLUDED.artifacts_path,
                checkpoint_type = EXCLUDED.checkpoint_type,
                checkpoint_metadata_json = EXCLUDED.checkpoint_metadata_json,
                state_size_bytes = EXCLUDED.state_size_bytes,
                artifacts_size_bytes = EXCLUDED.artifacts_size_bytes
        """, (operation_id, checkpoint_id, now(), state_json, new_artifacts_path, ...))

        conn.commit()

        # Step 4: Cleanup old artifacts AFTER successful commit (outside transaction)
        if old_artifacts_path and old_artifacts_path != new_artifacts_path:
            if os.path.exists(old_artifacts_path):
                shutil.rmtree(old_artifacts_path)

        return checkpoint_id

    except Exception as e:
        conn.rollback()
        # Clean up new artifacts if DB operation failed
        if new_artifacts_path and os.path.exists(new_artifacts_path):
            shutil.rmtree(new_artifacts_path)
        raise
```
---
## 9. Error Handling and Recovery
### 9.1 Checkpoint Save Failures
```python
# Failure modes and handling
 
def save_checkpoint(...):
    try:
        # Mode 1: Disk full (artifacts)
        artifacts_path = _save_artifacts_to_disk(...)
        # → Raises OSError: No space left on device
        # → Log error, skip checkpoint, continue operation
        # → Alert user (disk space low)
 
    except OSError as e:
        logger.error(f"Failed to save checkpoint artifacts: {e}")
        # Don't fail operation, just skip this checkpoint
        # Next checkpoint attempt may succeed (if user frees space)
        return None
 
    try:
        # Mode 2: Database error (connection lost, constraint violation)
        cursor.execute("INSERT INTO operation_checkpoints ...")
        # → Raises psycopg2.Error
        # → Rollback transaction, clean up artifacts
        # → Log error, skip checkpoint, continue operation
 
    except psycopg2.Error as e:
        conn.rollback()
        _cleanup_orphaned_artifacts(artifacts_path)
        logger.error(f"Failed to save checkpoint to database: {e}")
        return None
 
    # Mode 3: Partial success (artifacts saved, DB insert failed)
    # → Transaction rollback ensures no orphaned DB records
    # → Cleanup removes orphaned artifact files
    # → Operation continues without checkpoint
```
### 9.2 Checkpoint Load Failures
```python
# Failure modes and handling
 
def load_checkpoint(operation_id, checkpoint_id=None, latest=False):
    try:
        # Mode 1: Checkpoint not found
        cursor.execute("SELECT ... FROM operation_checkpoints ...")
        row = cursor.fetchone()
        if not row:
            # → Return None (caller handles 404)
            return None
 
        # Mode 2: State JSON parse error
        state = json.loads(row["state_json"])
        # → Raises json.JSONDecodeError
        # → Log error, raise CheckpointCorruptedError
        # → Caller returns 500 error to user
 
    except json.JSONDecodeError as e:
        logger.error(f"Checkpoint {checkpoint_id} corrupted (JSON): {e}")
        raise CheckpointCorruptedError(f"Checkpoint corrupted: {e}")
 
    try:
        # Mode 3: Artifacts missing/corrupted
        artifacts = _load_artifacts_from_disk(artifacts_path)
        # → Raises FileNotFoundError or torch.serialization error
        # → Log error, raise CheckpointCorruptedError
 
    except (FileNotFoundError, Exception) as e:
        logger.error(f"Checkpoint {checkpoint_id} artifacts missing/corrupted: {e}")
        raise CheckpointCorruptedError(f"Checkpoint artifacts corrupted: {e}")
 
    # Mode 4: Version mismatch
    if state["ktrdr_version"] != current_version:
        # → Raise VersionMismatchError
        # → Caller returns 400 error to user
        raise VersionMismatchError(
            f"Checkpoint from version {state['ktrdr_version']}, "
            f"current version {current_version}"
        )
```
### 9.3 Resume Failures
```python
# Failure scenarios during resume
 
async def resume_operation(operation_id):
    # Scenario 1: Original operation not found
    original_op = await operations_service.get_operation(operation_id)
    if not original_op:
        raise HTTPException(404, f"Operation not found: {operation_id}")
 
    # Scenario 2: Operation not resumable (wrong status)
    if original_op.status not in [OperationStatus.FAILED, OperationStatus.CANCELLED]:
        raise HTTPException(
            400,
            f"Cannot resume {original_op.status} operation. "
            "Only FAILED or CANCELLED operations can be resumed."
        )
 
    # Scenario 3: No checkpoint found
    checkpoint = checkpoint_service.load_checkpoint(operation_id, latest=True)
    if not checkpoint:
        raise HTTPException(
            404,
            f"No checkpoint found for {operation_id}. Cannot resume."
        )
 
    # Scenario 4: Checkpoint corrupted
    # → Handled by load_checkpoint (raises CheckpointCorruptedError)
    # → Caught and converted to HTTPException(500, ...)
 
    # Scenario 5: Data not available (training data deleted)
    try:
        data = load_data_from_cache(...)
    except DataNotFoundError as e:
        raise HTTPException(
            500,
            f"Training data not found. Cannot resume. Details: {e}"
        )
 
    # Scenario 6: Resume execution fails (model architecture changed)
    try:
        model.load_state_dict(checkpoint["model_state_dict"])
    except RuntimeError as e:
        # State dict doesn't match model architecture
        raise HTTPException(
            500,
            f"Cannot load checkpoint: model architecture mismatch. Details: {e}"
        )
```
---
## 10. Performance Considerations
### 10.1 Checkpoint Performance Analysis
```
┌─────────────────────────────────────────────────────────────────┐
│                  Checkpoint Performance Budget                   │
└─────────────────────────────────────────────────────────────────┘
 
Training Checkpoint (per checkpoint):
   ├─ Capture state: ~10ms (dict creation, state_dict extraction)
   ├─ Save artifacts to disk: ~500ms (50 MB model @ 100 MB/s)
   ├─ JSON serialization: ~50ms (small state without artifacts)
   ├─ PostgreSQL INSERT: ~10ms (small JSON payload)
   ├─ Cleanup old checkpoints: ~50ms (DELETE query + artifact removal)
   └─ Total: ~620ms per checkpoint
 
Training with 5-minute checkpoint interval:
   ├─ Epoch time: 30 seconds (fast) to 30 minutes (slow)
   ├─ Fast epochs (30s): checkpoint every 10 epochs = 300s training + 0.62s checkpoint = 0.2% overhead
   ├─ Slow epochs (30m): checkpoint every 1 epoch = 1800s training + 0.62s checkpoint = 0.03% overhead
   └─ Overhead: < 1% in all scenarios ✓
 
Backtesting Checkpoint (per checkpoint):
   ├─ Capture state: ~5ms (smaller state, no model weights)
   ├─ JSON serialization: ~20ms (position history, equity curve)
   ├─ PostgreSQL INSERT: ~10ms
   ├─ Cleanup old checkpoints: ~20ms
   └─ Total: ~55ms per checkpoint
 
Backtesting with 5-minute checkpoint interval:
   ├─ Bar processing: 1ms (fast) to 100ms (slow with ML inference)
   ├─ Checkpoint every 5 minutes = 300,000ms runtime + 55ms checkpoint = 0.02% overhead
   └─ Overhead: < 0.1% ✓
```
### 10.2 Database Performance

#### Write Load Analysis

**Checkpoint Write Frequency:**
```
Concurrent operations: 5 training + 5 backtesting = 10 operations max
Checkpoint interval: 5 minutes = 300 seconds
Write rate: 10 operations / 300 seconds = 0.033 writes/second
Peak rate (all checkpoint simultaneously): 0.033 writes/sec
```

**PostgreSQL Capacity:**
```
PostgreSQL write capacity: ~1,000 writes/second (conservative estimate)
KTRDR checkpoint write load: 0.033 writes/second
Utilization: 0.003% of capacity
```

**Conclusion:**
PostgreSQL will not notice this load. Write throughput is **5 orders of magnitude below capacity**. Redis would add deployment complexity for zero performance benefit.

**Why Not Redis?**
- Redis excels at high-frequency writes (1000s/sec) - we have 0.033/sec
- Redis requires additional deployment, monitoring, backup
- PostgreSQL ACID guarantees more important than Redis speed
- Can add Redis later if bottleneck emerges (it won't)

#### Query Performance Analysis

```sql
-- 1. Save checkpoint (UPSERT)
-- Payload: ~10 KB state_json + metadata
-- Expected: < 10ms
INSERT INTO operation_checkpoints (...) VALUES (...)
ON CONFLICT (operation_id) DO UPDATE SET ...;

-- 2. Load checkpoint (SELECT by PK)
-- Expected: < 5ms (PK lookup, no index scan needed)
SELECT * FROM operation_checkpoints
WHERE operation_id = 'op_training_...';

-- 3. Delete checkpoint (DELETE by PK)
-- Expected: < 5ms (PK delete, single row)
DELETE FROM operation_checkpoints
WHERE operation_id = 'op_training_...';

-- 4. List operations (SELECT)
-- Expected: < 20ms (return 100 operations with pagination)
SELECT * FROM operations
WHERE status = 'RUNNING'
ORDER BY created_at DESC
LIMIT 100;

-- Index usage:
-- ✓ PRIMARY KEY on operation_id
--   → Used for all checkpoint queries (load, delete)
-- ✓ idx_operations_status (status)
--   → Used for filtering by status
-- ✓ idx_operations_created_at (created_at DESC)
--   → Used for recent operations
```
### 10.3 Disk I/O Optimization
```python
# Artifact save optimization
 
def _save_artifacts_to_disk(checkpoint_id, artifacts):
    """
    Optimize disk writes:
    1. Write to temporary location first
    2. Atomic rename to final location
    3. Prevents partial writes if interrupted
    """
    temp_dir = artifacts_dir / f"{checkpoint_id}.tmp"
    final_dir = artifacts_dir / checkpoint_id
 
    try:
        # Write to temp location
        temp_dir.mkdir(parents=True, exist_ok=True)
        for name, data in artifacts.items():
            temp_path = temp_dir / f"{name}.pt"
            torch.save(data, temp_path)
 
        # Atomic rename (on same filesystem)
        temp_dir.rename(final_dir)
 
        return final_dir
 
    except Exception as e:
        # Cleanup temp directory on failure
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        raise
 
 
# Parallel artifact loading (future optimization)
def _load_artifacts_from_disk(artifacts_path):
    """
    Load artifacts in parallel for faster resume.
 
    Current: Sequential (500ms total)
    Optimized: Parallel (200ms total with 3 threads)
    """
    from concurrent.futures import ThreadPoolExecutor
 
    artifact_files = list(Path(artifacts_path).glob("*.pt"))
 
    def load_artifact(file_path):
        return file_path.stem, torch.load(file_path)
 
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = executor.map(load_artifact, artifact_files)
 
    return dict(results)
```
---
## 11. Security and Validation
### 11.1 Input Validation
```python
# Checkpoint validation
 
def validate_checkpoint_state(state: dict) -> bool:
    """
    Validate checkpoint state structure and content.
 
    Checks:
    1. Required fields present
    2. Version compatibility
    3. Data types correct
    4. Value ranges reasonable
    """
    # Required fields
    required_fields = [
        "checkpoint_version",
        "ktrdr_version",
        "checkpoint_type",
        "created_at"
    ]
 
    for field in required_fields:
        if field not in state:
            raise ValueError(f"Missing required field: {field}")
 
    # Version validation
    if state["checkpoint_version"] != "1.0":
        raise ValueError(
            f"Unsupported checkpoint version: {state['checkpoint_version']}"
        )
 
    # Type-specific validation
    if state["checkpoint_type"] == "epoch_snapshot":
        if "epoch" not in state or not isinstance(state["epoch"], int):
            raise ValueError("Invalid epoch in training checkpoint")
        if state["epoch"] < 0:
            raise ValueError(f"Invalid epoch: {state['epoch']}")
 
    elif state["checkpoint_type"] == "bar_snapshot":
        if "current_bar_index" not in state:
            raise ValueError("Missing current_bar_index in backtest checkpoint")
        if state["current_bar_index"] < 0:
            raise ValueError(f"Invalid bar index: {state['current_bar_index']}")
 
    return True


def validate_checkpoint_version(checkpoint_state: dict) -> bool:
    """
    Validate checkpoint version compatibility.

    Rules:
    - Compatible: Same major.minor version (0.5.0 ↔ 0.5.1) ✅
    - Incompatible: Different major or minor (0.5.x ↔ 0.6.x) ❌

    Rationale:
    - Patch versions (0.5.0 → 0.5.1): Bug fixes, safe to load
    - Minor versions (0.5.x → 0.6.x): Features changed, checkpoint invalid
    - Major versions (0.x.x → 1.x.x): Complete refactor, checkpoint invalid
    """
    checkpoint_version = checkpoint_state["ktrdr_version"]
    current_version = get_ktrdr_version()

    checkpoint_parts = checkpoint_version.split(".")
    current_parts = current_version.split(".")

    # Check major.minor match
    if checkpoint_parts[:2] != current_parts[:2]:
        raise VersionMismatchError(
            f"Checkpoint from version {checkpoint_version}, "
            f"current version {current_version}. "
            f"Major.minor must match."
        )

    # Patch differences are okay
    if checkpoint_parts[2] != current_parts[2]:
        logger.warning(
            f"Checkpoint from patch version {checkpoint_version}, "
            f"current is {current_version}. This is usually safe."
        )

    return True
```
### 11.2 Access Control
```python
# Operation ownership validation
 
def validate_operation_access(user_id: str, operation_id: str) -> bool:
    """
    Validate user has permission to access/resume operation.
 
    Note: Current KTRDR is single-user, but this provides
    foundation for multi-user support.
    """
    operation = get_operation(operation_id)
 
    # Check if operation belongs to user
    if operation.metadata.parameters.get("user_id") != user_id:
        raise PermissionError(
            f"User {user_id} does not have permission to access operation {operation_id}"
        )
 
    return True
```
### 11.3 Data Integrity
```python
# Checkpoint integrity validation
 
def verify_checkpoint_integrity(checkpoint_id: str) -> bool:
    """
    Verify checkpoint data integrity.
 
    Checks:
    1. State JSON parseable
    2. Artifacts exist and loadable
    3. Checksums match (future enhancement)
    """
    checkpoint = load_checkpoint_metadata(checkpoint_id)
 
    # Verify state JSON
    try:
        state = json.loads(checkpoint["state_json"])
        validate_checkpoint_state(state)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Checkpoint {checkpoint_id} state validation failed: {e}")
        return False
 
    # Verify artifacts exist
    if checkpoint["artifacts_path"]:
        artifacts_path = Path(checkpoint["artifacts_path"])
        if not artifacts_path.exists():
            logger.error(f"Checkpoint {checkpoint_id} artifacts missing")
            return False
 
        # Verify artifacts loadable
        try:
            artifacts = _load_artifacts_from_disk(artifacts_path)
        except Exception as e:
            logger.error(f"Checkpoint {checkpoint_id} artifacts corrupted: {e}")
            return False
 
    return True
```
---
## 12. Operational Considerations
### 12.1 Monitoring and Observability
```python
# Checkpoint metrics for monitoring
 
class CheckpointMetrics:
    """Metrics for checkpoint operations."""
 
    # Counters
    checkpoints_created_total: Counter
    checkpoints_loaded_total: Counter
    checkpoints_deleted_total: Counter
    checkpoint_save_failures_total: Counter
    checkpoint_load_failures_total: Counter
 
    # Histograms
    checkpoint_save_duration_seconds: Histogram
    checkpoint_load_duration_seconds: Histogram
    checkpoint_size_bytes: Histogram
    artifacts_size_bytes: Histogram
 
    # Gauges
    active_checkpoints_count: Gauge
    total_checkpoints_size_bytes: Gauge
 
 
# Logging structured data
logger.info(
    "Checkpoint saved",
    extra={
        "checkpoint_id": checkpoint_id,
        "operation_id": operation_id,
        "checkpoint_type": checkpoint_type,
        "state_size_bytes": len(state_json),
        "artifacts_size_bytes": artifacts_size,
        "duration_ms": duration * 1000,
    }
)
```
### 12.2 Backup and Disaster Recovery
```
┌─────────────────────────────────────────────────────────────────┐
│                    Backup Strategy (Future)                      │
└─────────────────────────────────────────────────────────────────┘
 
PostgreSQL Database:
   ├─ pg_dump daily (operations + operation_checkpoints tables)
   ├─ Point-in-time recovery enabled
   └─ Retention: 7 days
 
Checkpoint Artifacts:
   ├─ rsync to backup location daily
   ├─ Incremental backups (only new/modified files)
   └─ Retention: 7 days
 
Disaster Recovery:
   ├─ Restore PostgreSQL from backup
   ├─ Restore checkpoint artifacts from backup
   ├─ Resume operations from last checkpoint
   └─ RTO: < 1 hour, RPO: < 24 hours
```
---
## Appendix A: Configuration Reference
```yaml
# config/persistence.yaml
 
database:
  host: localhost
  port: 5432
  database: ktrdr
  user: ktrdr
  password: ${POSTGRES_PASSWORD}
  pool_size: 10
  pool_timeout: 30
 
checkpointing:
  enabled: true

  artifacts_dir: data/checkpoints/artifacts

  # Training checkpoints
  training:
    checkpoint_interval_seconds: 300  # 5 minutes (time-based)
    force_checkpoint_every_n: 50      # Safety: every 50 epochs
    delete_on_completion: true
    checkpoint_on_failure: true

  # Backtesting checkpoints
  backtesting:
    checkpoint_interval_seconds: 300  # 5 minutes (time-based)
    force_checkpoint_every_n: 5000    # Safety: every 5000 bars
    delete_on_completion: true
    checkpoint_on_failure: true

  # Cleanup policies
  cleanup:
    run_interval_hours: 24            # Daily cleanup
    delete_old_checkpoints_days: 30   # Delete >30 days old
    warn_disk_usage_percent: 80       # Alert at 80% disk usage

# Design Note: Only 1 checkpoint per operation (the latest)
# When new checkpoint saved, old one is replaced (UPSERT)
```
---
## Appendix B: API Reference
### B.1 Checkpoint Service API
```python
class CheckpointService:
 
    def save_checkpoint(
        operation_id: str,
        state: dict[str, Any],
        checkpoint_type: str = "snapshot",
        metadata: dict[str, Any] | None = None
    ) -> str:
        """
        Save operation checkpoint (replaces existing checkpoint if present).

        Design: Uses PostgreSQL UPSERT to replace old checkpoint.
        Deletes old artifact files after successful UPSERT.

        Args:
            operation_id: Operation identifier
            state: Complete checkpoint state (artifacts will be extracted)
            checkpoint_type: "epoch_snapshot", "bar_snapshot", "final"
            metadata: Small queryable metadata (epoch, metrics)

        Returns:
            checkpoint_id

        Raises:
            OSError: Disk full or artifacts write failed
            psycopg2.Error: Database error
        """

    def load_checkpoint(
        operation_id: str
    ) -> dict[str, Any] | None:
        """
        Load checkpoint for operation (only 1 checkpoint per operation).

        Args:
            operation_id: Operation identifier

        Returns:
            Complete checkpoint state with artifacts, or None if not found

        Raises:
            CheckpointCorruptedError: Checkpoint data corrupted
            VersionMismatchError: Incompatible KTRDR version
        """

    def delete_checkpoint(operation_id: str) -> None:
        """
        Delete checkpoint for operation.

        Removes DB record and artifact files.
        """
```
### B.2 REST API Endpoints
```
POST /api/v1/operations/{operation_id}/resume
   Resume operation from latest checkpoint
 
   Response 200:
   {
       "success": true,
       "original_operation_id": "op_training_..._100000",
       "new_operation_id": "op_training_..._140000",
       "resumed_from_checkpoint": "checkpoint_epoch_45",
       "message": "Training will resume from epoch 46/100"
   }
 
   Response 404: No checkpoint found
   Response 400: Operation not resumable
   Response 500: Checkpoint corrupted or load failed

GET /api/v1/operations/{operation_id}/checkpoint
   Get checkpoint info for operation (only 1 checkpoint per operation)

   Response 200:
   {
       "success": true,
       "checkpoint_id": "op_training_..._1737115200",
       "checkpoint_type": "epoch_snapshot",
       "created_at": "2025-01-17T12:00:00Z",
       "metadata": {
           "epoch": 45,
           "val_accuracy": 0.72
       },
       "size_mb": 52.5
   }

   Response 404: No checkpoint found
```
---
## Appendix C: Testing Strategy

### C.1 Unit Tests

**CheckpointPolicy:**
- `should_checkpoint()` decision logic
- Time-based interval calculation
- Force checkpoint boundary detection

**CheckpointService:**
- `save_checkpoint()` - artifact storage, DB UPSERT
- `load_checkpoint()` - artifact loading, DB query
- `delete_checkpoint()` - cleanup logic
- State serialization/deserialization

**State Capture:**
- `ModelTrainer.get_checkpoint_state()`
- `BacktestingEngine.get_checkpoint_state()`
- `PositionManager.get_state()` / `restore_state()`
- `PerformanceTracker.get_state()` / `restore_state()`

### C.2 Integration Tests

**Training Checkpoint Flow:**
```python
def test_training_checkpoint_and_resume():
    # Start training
    op1 = start_training(epochs=100)

    # Wait for checkpoint
    wait_for_checkpoint(op1.operation_id)

    # Simulate failure (cancel operation)
    cancel_operation(op1.operation_id)

    # Resume
    op2 = resume_operation(op1.operation_id)

    # Verify resumed from correct epoch
    assert op2.metadata["resumed_from"] == op1.operation_id
    assert op2.start_epoch == op1.last_checkpoint_epoch + 1

    # Complete training
    wait_for_completion(op2.operation_id)

    # Verify checkpoints cleaned up
    assert checkpoint_exists(op1.operation_id) == False
    assert checkpoint_exists(op2.operation_id) == False
```

**Backtesting Checkpoint Flow:**
```python
def test_backtest_checkpoint_and_resume():
    # Similar flow for backtesting
    # Verify bar_index resume point
    # Verify position/performance state restored
```

### C.3 Chaos/Resilience Tests

**Kill API Mid-Checkpoint:**
```python
def test_api_crash_during_checkpoint():
    # Start training
    op = start_training()

    # Inject fault: kill API process during checkpoint write
    inject_fault_at("checkpoint_service.save_checkpoint", "SIGKILL")

    # Restart API
    restart_api()

    # Verify operation marked FAILED
    # Verify checkpoint either complete or absent (no partial state)
    # Verify can resume from previous valid checkpoint
```

**Disk Full During Checkpoint:**
```python
def test_disk_full_during_checkpoint():
    # Fill disk to near capacity
    # Trigger checkpoint
    # Verify graceful failure (operation continues without checkpoint)
    # Verify error logged
    # Verify no orphaned artifacts
```

**Database Connection Loss:**
```python
def test_db_connection_loss_during_checkpoint():
    # Start training
    # Drop database connection during checkpoint
    # Verify transaction rolled back
    # Verify artifacts cleaned up
    # Verify operation continues (checkpoint skipped)
```

### C.4 Performance Tests

**Checkpoint Overhead Measurement:**
```python
def test_checkpoint_overhead():
    # Train with checkpointing enabled
    time_with = measure_training_time(checkpoint_interval=300)

    # Train with checkpointing disabled
    time_without = measure_training_time(checkpoint_interval=None)

    overhead = (time_with - time_without) / time_without

    # Verify < 1% overhead
    assert overhead < 0.01, f"Checkpoint overhead {overhead:.2%} exceeds 1%"
```

### C.5 Test Coverage Goals

- Unit test coverage: >90% for checkpoint components
- Integration test coverage: 100% of resume flows
- Chaos test coverage: All failure modes documented in Section 9
- Performance test: Verify <1% overhead guarantee

---
**End of Architecture Document**

This architecture provides a robust, performant, and maintainable foundation for checkpoint persistence in KTRDR.

**Key Design Decisions:**
- **ONE checkpoint per operation** (simplifies retention, reduces disk usage by 10x)
- **PostgreSQL-only** (no Redis needed for 0.033 writes/sec)
- **Time-based checkpointing** (adapts to operation speed automatically)
- **Synchronous writes** (0.2% overhead acceptable, avoids async complexity)
- **UPSERT pattern** (atomic checkpoint replacement)
- **< 1% performance overhead** (620ms every 5 minutes)
- **~1 GB disk budget** (5 training + 5 backtest operations)

The design prioritizes simplicity, performance, and reliability (ACID transactions, atomic operations).
