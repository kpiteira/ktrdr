"""Training system for neuro-fuzzy strategies."""

from .model_storage import ModelStorage

# Guard torch-dependent imports so torch-free modules (context_labeler,
# forward_return_labeler) remain importable without torch installed.
try:
    from .model_trainer import EarlyStopping, ModelTrainer, TrainingMetrics
except ModuleNotFoundError as _e:
    if _e.name == "torch":
        pass  # torch not installed — torch-free modules still importable
    else:
        raise

# StrategyTrainer removed - use LocalTrainingOrchestrator or HostTrainingOrchestrator
from .zigzag_labeler import ZigZagConfig, ZigZagLabeler

# Multi-timeframe label generator temporarily disabled while updating for pure fuzzy
# from .multi_timeframe_label_generator import (
#     MultiTimeframeLabelGenerator,
#     MultiTimeframeLabelConfig,
#     TimeframeLabelConfig,
#     LabelClass,
#     LabelValidationResult,
#     MultiTimeframeLabelResult,
#     create_multi_timeframe_label_generator,
# )
# Multi-timeframe temporarily disabled while updating for pure fuzzy
# from .multi_timeframe_model_storage import (
#     MultiTimeframeModelStorage,
#     create_multi_timeframe_model_storage,
# )

__all__ = [
    "ZigZagLabeler",
    "ZigZagConfig",
    "ModelStorage",
    # "StrategyTrainer",  # Removed - use LocalTrainingOrchestrator or HostTrainingOrchestrator
    # "MultiTimeframeLabelGenerator",  # Temporarily disabled
    # "MultiTimeframeLabelConfig",  # Temporarily disabled
    # "TimeframeLabelConfig",  # Temporarily disabled
    # "LabelClass",  # Temporarily disabled
    # "LabelValidationResult",  # Temporarily disabled
    # "MultiTimeframeLabelResult",  # Temporarily disabled
    # "create_multi_timeframe_label_generator",  # Temporarily disabled
    # "MultiTimeframeModelStorage",  # Temporarily disabled
    # "create_multi_timeframe_model_storage",  # Temporarily disabled
]
