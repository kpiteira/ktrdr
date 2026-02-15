"""ModelBundle — single model loading point for backtesting.

Replaces the triple-load pattern (ModelLoader + BaseNeuralModel.load_model +
lazy re-load) with a single frozen dataclass. All model artifacts are loaded
from disk in one call via ModelBundle.load().

Also provides standalone utility functions (is_v3_model, load_v3_metadata,
reconstruct_config_from_metadata) that were previously static methods on
BacktestingService. Moving them here fixes the circular dependency where
decision/orchestrator.py imported from backtesting/backtesting_service.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ktrdr.models.model_metadata import ModelMetadata

if TYPE_CHECKING:
    import torch.nn

    from ktrdr.config.models import StrategyConfigurationV3


# ---------------------------------------------------------------------------
# Standalone utility functions (moved from BacktestingService)
# ---------------------------------------------------------------------------


def is_v3_model(model_path: str | Path) -> bool:
    """Check if a model directory contains v3 metadata.

    Args:
        model_path: Path to model directory

    Returns:
        True if metadata_v3.json exists, False otherwise
    """
    model_path = Path(model_path)
    return (model_path / "metadata_v3.json").exists()


def load_v3_metadata(model_path: str | Path) -> ModelMetadata:
    """Load v3 model metadata from model directory.

    Args:
        model_path: Path to model directory

    Returns:
        ModelMetadata instance

    Raises:
        FileNotFoundError: If metadata_v3.json doesn't exist
    """
    model_path = Path(model_path)
    metadata_path = model_path / "metadata_v3.json"

    if not metadata_path.exists():
        raise FileNotFoundError(
            f"V3 metadata not found at {metadata_path}. "
            f"This model may not be a v3 model or may need to be retrained."
        )

    with open(metadata_path) as f:
        data = json.load(f)

    return ModelMetadata.from_dict(data)


def reconstruct_config_from_metadata(
    metadata: ModelMetadata,
) -> StrategyConfigurationV3:
    """Reconstruct StrategyConfigurationV3 from model metadata.

    V3 metadata stores the full strategy configuration for reproducibility.
    This method reconstructs the config for use in backtesting.

    Args:
        metadata: ModelMetadata instance

    Returns:
        StrategyConfigurationV3 that matches the training configuration
    """
    from ktrdr.config.models import (
        FuzzySetDefinition,
        IndicatorDefinition,
        NNInputSpec,
        StrategyConfigurationV3,
        SymbolConfiguration,
        SymbolMode,
        TimeframeConfiguration,
        TimeframeMode,
        TrainingDataConfiguration,
    )

    # Reconstruct indicators
    indicators: dict[str, IndicatorDefinition] = {}
    for indicator_id, indicator_data in metadata.indicators.items():
        indicators[indicator_id] = IndicatorDefinition(**indicator_data)

    # Reconstruct fuzzy sets
    fuzzy_sets: dict[str, FuzzySetDefinition] = {}
    for fuzzy_set_id, fuzzy_data in metadata.fuzzy_sets.items():
        fuzzy_sets[fuzzy_set_id] = FuzzySetDefinition(**fuzzy_data)

    # Reconstruct nn_inputs
    nn_inputs = [NNInputSpec(**inp) for inp in metadata.nn_inputs]

    # Build training_data config from metadata training context
    symbols = metadata.training_symbols or ["UNKNOWN"]
    timeframes = metadata.training_timeframes or ["1h"]

    if len(symbols) == 1:
        symbol_config = SymbolConfiguration(mode=SymbolMode.SINGLE, symbol=symbols[0])
    else:
        symbol_config = SymbolConfiguration(
            mode=SymbolMode.MULTI_SYMBOL, symbols=symbols
        )

    if len(timeframes) == 1:
        timeframe_config = TimeframeConfiguration(
            mode=TimeframeMode.SINGLE,
            timeframe=timeframes[0],
            base_timeframe=timeframes[0],
        )
    else:
        timeframe_config = TimeframeConfiguration(
            mode=TimeframeMode.MULTI_TIMEFRAME,
            timeframes=timeframes,
            base_timeframe=timeframes[0],
        )

    training_data = TrainingDataConfiguration(
        symbols=symbol_config,
        timeframes=timeframe_config,
        history_required=100,
    )

    return StrategyConfigurationV3(
        name=metadata.strategy_name,
        version=metadata.strategy_version,
        description=f"Reconstructed from model {metadata.model_name}",
        indicators=indicators,
        fuzzy_sets=fuzzy_sets,
        nn_inputs=nn_inputs,
        model={"type": "mlp"},
        decisions={"output_format": "classification"},
        training={"epochs": 1},
        training_data=training_data,
    )


# ---------------------------------------------------------------------------
# ModelBundle
# ---------------------------------------------------------------------------


def _build_model(model_config: dict[str, Any], input_size: int) -> torch.nn.Module:
    """Build a model architecture from config and input size.

    Args:
        model_config: Model config dict (with 'architecture' key)
        input_size: Number of input features

    Returns:
        Built nn.Module (not yet loaded with weights)
    """
    from ktrdr.neural.models.mlp import MLPTradingModel

    model_type = model_config.get("type", "mlp").lower()
    if model_type != "mlp":
        raise ValueError(f"Unsupported model type: {model_type}")

    mlp = MLPTradingModel(model_config)
    return mlp.build_model(input_size)


@dataclass(frozen=True)
class ModelBundle:
    """Everything needed for inference. Immutable after creation.

    Replaces ModelLoader, the model-loading half of ModelStorage.load_model(),
    and BaseNeuralModel.load_model(). Single class that loads everything needed
    for inference in one call.

    Attributes:
        model: Ready-to-infer nn.Module, in eval mode, on CPU
        metadata: ModelMetadata from metadata_v3.json
        feature_names: Ordered feature names from model metadata
        strategy_config: Reconstructed StrategyConfigurationV3
    """

    model: Any  # torch.nn.Module — Any to avoid torch import at module level
    metadata: ModelMetadata
    feature_names: list[str]
    strategy_config: StrategyConfigurationV3

    @classmethod
    def load(cls, model_path: str) -> ModelBundle:
        """Load model artifacts from disk. ONE torch.load, always CPU-safe.

        Args:
            model_path: Path to model directory containing model.pt,
                metadata_v3.json, and features.json

        Returns:
            Frozen ModelBundle with model in eval mode on CPU

        Raises:
            FileNotFoundError: If model directory or required files don't exist
            RuntimeError: If model loading fails
        """
        path = Path(model_path)

        if not path.exists():
            raise FileNotFoundError(f"Model directory not found: {path}")

        # 1. Load metadata (JSON only, no torch needed)
        metadata = load_v3_metadata(path)

        # 2. Determine input size from features.json
        features_path = path / "features.json"
        if features_path.exists():
            with open(features_path) as f:
                features_info = json.load(f)
            input_size = features_info.get("feature_count")
        else:
            input_size = None

        # Fallback: infer from resolved_features count
        if input_size is None:
            input_size = len(metadata.resolved_features)

        if input_size is None or input_size == 0:
            raise ValueError(
                f"Cannot determine input_size for model at {path}. "
                f"No features.json and no resolved_features in metadata."
            )

        # 3. Build model architecture from config
        model_config = metadata.indicators  # need the model section from metadata
        # The model architecture is stored in the strategy config, not directly
        # in metadata. Use a default MLP config.
        model_config = {"type": "mlp", "architecture": {"hidden_layers": [64, 32]}}

        # Try to load model config from disk if available
        config_path = path / "config.json"
        if config_path.exists():
            with open(config_path) as f:
                loaded_config = json.load(f)
            # Handle both formats: direct model config or full strategy config
            if "model" in loaded_config and "architecture" in loaded_config.get(
                "model", {}
            ):
                model_config = loaded_config["model"]
            elif "architecture" in loaded_config:
                model_config = loaded_config

        model = _build_model(model_config, input_size)

        # 4. Load weights — ONE load, always safe
        # Lazy torch import: only needed for weight loading, not metadata
        import torch

        state_dict = torch.load(
            path / "model.pt",
            map_location="cpu",
            weights_only=True,
        )
        model.load_state_dict(state_dict)
        model.eval()

        # 5. Reconstruct strategy config
        strategy_config = reconstruct_config_from_metadata(metadata)

        return cls(
            model=model,
            metadata=metadata,
            feature_names=metadata.resolved_features,
            strategy_config=strategy_config,
        )
