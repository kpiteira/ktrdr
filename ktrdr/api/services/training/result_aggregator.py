"""Result aggregator that normalizes training outputs across execution modes."""

from __future__ import annotations

from typing import Any

from ktrdr import get_logger
from ktrdr.api.services.training.context import TrainingOperationContext

logger = get_logger(__name__)


def from_local_run(
    context: TrainingOperationContext,
    raw_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Aggregate result from local training run into standardized format.

    Args:
        context: Training operation context
        raw_result: Raw result dict from StrategyTrainer.train_multi_symbol_strategy

    Returns:
        Standardized result summary with keys:
        - training_metrics: final losses/accuracies, epochs, time, early stopping
        - validation_metrics: validation set performance
        - test_metrics: test set performance including precision/recall/f1
        - resource_usage: system resource stats (GPU/CPU)
        - artifacts: model paths, analytics directories, checkpoints
        - session_info: metadata about the training session
    """
    training_metrics_raw = raw_result.get("training_metrics") or {}
    test_metrics_raw = raw_result.get("test_metrics") or {}
    model_info_raw = raw_result.get("model_info") or {}
    data_summary = raw_result.get("data_summary") or {}

    # Extract training metrics
    training_metrics = {
        "final_train_loss": training_metrics_raw.get("final_train_loss", 0.0),
        "final_val_loss": training_metrics_raw.get("final_val_loss", 0.0),
        "final_train_accuracy": training_metrics_raw.get("final_train_accuracy", 0.0),
        "final_val_accuracy": training_metrics_raw.get("final_val_accuracy", 0.0),
        "epochs_completed": training_metrics_raw.get(
            "epochs_completed", context.total_steps
        ),
        "early_stopped": training_metrics_raw.get("early_stopped", False),
        "training_time_minutes": training_metrics_raw.get("training_time_minutes", 0.0),
        "best_epoch": training_metrics_raw.get("best_epoch"),
        "final_learning_rate": training_metrics_raw.get("final_learning_rate"),
    }

    # Extract validation metrics (same as final val metrics from training)
    validation_metrics = {
        "val_loss": training_metrics_raw.get("final_val_loss", 0.0),
        "val_accuracy": training_metrics_raw.get("final_val_accuracy", 0.0),
    }

    # Extract test metrics
    test_metrics = {
        "test_loss": test_metrics_raw.get("test_loss", 0.0),
        "test_accuracy": test_metrics_raw.get("test_accuracy", 0.0),
        "precision": test_metrics_raw.get("precision", 0.0),
        "recall": test_metrics_raw.get("recall", 0.0),
        "f1_score": test_metrics_raw.get("f1_score", 0.0),
    }

    # Extract resource usage (placeholder for local runs)
    resource_usage: dict[str, Any] = {
        "gpu_used": False,
        "peak_memory_mb": None,
        "training_mode": "local",
    }

    # Extract artifacts
    artifacts: dict[str, Any] = {
        "model_path": raw_result.get("model_path"),
        "analytics_dir": None,  # Not yet implemented in local runner
        "checkpoints": [],
        "feature_importance": raw_result.get("feature_importance"),
        "per_symbol_metrics": raw_result.get("per_symbol_metrics"),
    }

    # Build session info
    session_info: dict[str, Any] = {
        "operation_id": context.operation_id,
        "strategy_name": context.strategy_name,
        "symbols": context.symbols,
        "timeframes": context.timeframes,
        "training_mode": "local",
        "use_host_service": False,
        "start_date": context.start_date,
        "end_date": context.end_date,
    }

    # Add data summary if available
    if data_summary:
        session_info["data_summary"] = data_summary

    return {
        "training_metrics": training_metrics,
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "resource_usage": resource_usage,
        "artifacts": artifacts,
        "session_info": session_info,
        "model_info": model_info_raw,
    }


def from_host_run(
    context: TrainingOperationContext,
    host_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """
    Aggregate result from host-service training run into standardized format.

    Args:
        context: Training operation context
        host_snapshot: Final status snapshot from host service

    Returns:
        Standardized result summary (same schema as from_local_run)
    """
    # Extract metrics from host snapshot
    metrics = host_snapshot.get("metrics") or {}
    training_metrics_raw = metrics.get("training") or {}
    validation_metrics_raw = metrics.get("validation") or {}
    test_metrics_raw = metrics.get("test") or {}
    resource_usage_raw = host_snapshot.get("resource_usage") or {}

    # Extract training metrics
    training_metrics = {
        "final_train_loss": training_metrics_raw.get("final_train_loss", 0.0),
        "final_val_loss": validation_metrics_raw.get("val_loss", 0.0),
        "final_train_accuracy": training_metrics_raw.get("final_train_accuracy", 0.0),
        "final_val_accuracy": validation_metrics_raw.get("val_accuracy", 0.0),
        "epochs_completed": training_metrics_raw.get(
            "epochs_completed", context.total_steps
        ),
        "early_stopped": training_metrics_raw.get("early_stopped", False),
        "training_time_minutes": training_metrics_raw.get("training_time_minutes", 0.0),
        "best_epoch": training_metrics_raw.get("best_epoch"),
        "final_learning_rate": training_metrics_raw.get("final_learning_rate"),
    }

    # Extract validation metrics
    validation_metrics = {
        "val_loss": validation_metrics_raw.get("val_loss", 0.0),
        "val_accuracy": validation_metrics_raw.get("val_accuracy", 0.0),
    }

    # Extract test metrics
    test_metrics = {
        "test_loss": test_metrics_raw.get("test_loss", 0.0),
        "test_accuracy": test_metrics_raw.get("test_accuracy", 0.0),
        "precision": test_metrics_raw.get("precision", 0.0),
        "recall": test_metrics_raw.get("recall", 0.0),
        "f1_score": test_metrics_raw.get("f1_score", 0.0),
    }

    # Extract resource usage
    resource_usage = {
        "gpu_used": resource_usage_raw.get("gpu_used", True),
        "gpu_name": resource_usage_raw.get("gpu_name"),
        "gpu_utilization_percent": resource_usage_raw.get("gpu_utilization_percent"),
        "peak_memory_mb": resource_usage_raw.get("peak_memory_mb"),
        "training_mode": "host",
    }

    # Extract artifacts
    artifacts_raw = host_snapshot.get("artifacts") or {}
    artifacts = {
        "model_path": artifacts_raw.get("model_path"),
        "analytics_dir": artifacts_raw.get("analytics_dir"),
        "checkpoints": artifacts_raw.get("checkpoints") or [],
        "download_url": artifacts_raw.get("download_url"),
        "feature_importance": artifacts_raw.get("feature_importance"),
        "per_symbol_metrics": artifacts_raw.get("per_symbol_metrics"),
    }

    # Build session info
    session_info = {
        "operation_id": context.operation_id,
        "session_id": context.session_id,
        "strategy_name": context.strategy_name,
        "symbols": context.symbols,
        "timeframes": context.timeframes,
        "training_mode": "host",
        "use_host_service": True,
        "start_date": context.start_date,
        "end_date": context.end_date,
        "host_status": host_snapshot.get("status"),
    }

    # Add model info if available
    model_info = host_snapshot.get("model_info") or {}

    return {
        "training_metrics": training_metrics,
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "resource_usage": resource_usage,
        "artifacts": artifacts,
        "session_info": session_info,
        "model_info": model_info,
    }
