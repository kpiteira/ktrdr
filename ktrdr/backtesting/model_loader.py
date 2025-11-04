"""Model loader for loading trained neural network models."""

from pathlib import Path
from typing import Any, Optional

import torch

from ..neural.models.mlp import MLPTradingModel
from ..training.model_storage import ModelStorage


class ModelLoader:
    """Load trained models for inference in backtesting and decision making."""

    def __init__(self, models_dir: str = "models"):
        """Initialize model loader.

        Args:
            models_dir: Base directory containing trained models
        """
        self.model_storage = ModelStorage(models_dir)

    def load_model(
        self,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        version: Optional[str] = None,
    ) -> tuple[torch.nn.Module, dict[str, Any]]:
        """Load a trained model with its configuration.

        Args:
            strategy_name: Name of the strategy
            symbol: Trading symbol
            timeframe: Timeframe
            version: Specific version (None for latest)

        Returns:
            Tuple of (model, metadata)
        """
        # Load model data from storage
        model_data = self.model_storage.load_model(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            version=version,
        )

        # Extract components
        model = model_data["model"]
        config = model_data["config"]
        metadata = model_data["metadata"]

        # If we have a state dict, rebuild the model
        if isinstance(model, dict):  # State dict
            model_type = config["model"]["type"].lower()

            if model_type == "mlp":
                # Build modern MLPTradingModel
                mlp_model = MLPTradingModel(config["model"])
                input_size = metadata.get("input_size")

                if input_size is None:
                    raise ValueError(
                        f"Model metadata missing input_size: {metadata}"
                    )

                mlp_model.model = mlp_model.build_model(input_size)
                mlp_model.model.load_state_dict(model)
                mlp_model.model.eval()
                mlp_model.is_trained = True

                model = mlp_model.model
            else:
                raise ValueError(f"Unknown model type: {model_type}")

        # Ensure model is in eval mode
        model.eval()

        return model, {
            "config": config,
            "metadata": metadata,
            "features": model_data["features"],
            "scaler": model_data.get("scaler"),
            "model_path": model_data["model_path"],
        }

    def load_latest_model(
        self, strategy_name: str
    ) -> tuple[torch.nn.Module, dict[str, Any]]:
        """Load the most recent model for a strategy.

        Args:
            strategy_name: Name of the strategy

        Returns:
            Tuple of (model, metadata)
        """
        # Find all models for this strategy
        all_models = self.model_storage.list_models(strategy_name)

        if not all_models:
            raise FileNotFoundError(f"No models found for strategy: {strategy_name}")

        # Get the most recent model
        latest_model = all_models[0]  # Already sorted by creation date

        # Extract symbol and timeframe from path
        path_parts = Path(latest_model["path"]).name.split("_")
        symbol = path_parts[0]
        timeframe = "_".join(path_parts[1:-1])  # Handle multi-part timeframes

        return self.load_model(strategy_name, symbol, timeframe)

    def get_available_models(self, strategy_name: Optional[str] = None) -> list:
        """Get list of available models.

        Args:
            strategy_name: Filter by strategy name

        Returns:
            List of model information
        """
        return self.model_storage.list_models(strategy_name)
