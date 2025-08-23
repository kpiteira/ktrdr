"""Model storage and versioning system."""

import json
import pickle
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch


class ModelStorage:
    """Handle model persistence with versioning."""

    def __init__(self, base_path: str = "models"):
        """Initialize model storage.

        Args:
            base_path: Base directory for model storage
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)

    def save_model(
        self,
        model: torch.nn.Module,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        config: dict[str, Any],
        training_metrics: dict[str, Any],
        feature_names: list[str],
        feature_importance: Optional[dict[str, float]] = None,
        scaler: Optional[Any] = None,
    ) -> str:
        """Save a trained model with all metadata.

        Args:
            model: Trained PyTorch model
            strategy_name: Name of the trading strategy
            symbol: Trading symbol (e.g., "AAPL")
            timeframe: Timeframe (e.g., "1h")
            config: Full strategy configuration
            training_metrics: Training results and metrics
            feature_names: List of feature names
            feature_importance: Feature importance scores
            scaler: Feature scaler object

        Returns:
            Path to saved model directory
        """
        # Create version directory
        model_dir = self._create_version_directory(strategy_name, symbol, timeframe)

        # Save model weights
        torch.save(model.state_dict(), model_dir / "model.pt")

        # Save full model architecture (for easier loading)
        torch.save(model, model_dir / "model_full.pt")

        # Save configuration
        with open(model_dir / "config.json", "w") as f:
            json.dump(config, f, indent=2, default=str)

        # Save training metrics
        with open(model_dir / "metrics.json", "w") as f:
            json.dump(training_metrics, f, indent=2, default=str)

        # Determine model type (Phase 4 of feature engineering removal)
        is_pure_fuzzy = scaler is None
        model_version = "pure_fuzzy_v1" if is_pure_fuzzy else "mixed_features_v1"

        # Save feature information with enhanced metadata
        if is_pure_fuzzy:
            # Pure fuzzy model - enhanced metadata
            feature_config = config.get("model", {}).get("features", {})
            feature_info = {
                "model_version": model_version,
                "feature_type": "pure_fuzzy",
                "fuzzy_features": feature_names,
                "feature_count": len(feature_names),
                "temporal_config": {
                    "lookback_periods": feature_config.get("lookback_periods", 0),
                    "enabled": feature_config.get("lookback_periods", 0) > 0,
                },
                "scaling_info": {
                    "requires_scaling": False,
                    "reason": "fuzzy_values_already_normalized",
                },
                "feature_importance": feature_importance or {},
            }
        else:
            # Legacy mixed features model
            feature_info = {
                "model_version": model_version,
                "feature_type": "mixed_features",
                "feature_names": feature_names,
                "feature_count": len(feature_names),
                "scaling_info": {
                    "requires_scaling": True,
                    "scaler_type": type(scaler).__name__ if scaler else None,
                },
                "feature_importance": feature_importance or {},
            }

        with open(model_dir / "features.json", "w") as f:
            json.dump(feature_info, f, indent=2)

        # Save scaler only for mixed feature models
        if scaler is not None:
            with open(model_dir / "scaler.pkl", "wb") as f:
                pickle.dump(scaler, f)

        # Save metadata with enhanced versioning
        metadata = {
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "created_at": datetime.now().isoformat(),
            "model_type": model.__class__.__name__,
            "model_version": model_version,
            "architecture_type": "pure_fuzzy" if is_pure_fuzzy else "mixed_features",
            "input_size": config.get("model", {}).get(
                "input_size", getattr(model, "input_size", None)
            ),
            "pytorch_version": torch.__version__,
            "training_summary": {
                "epochs": training_metrics.get("epochs_trained", 0),
                "final_accuracy": training_metrics.get("final_train_accuracy", 0),
                "best_val_accuracy": training_metrics.get("best_val_accuracy", 0),
            },
            "feature_engineering": {
                "removed": is_pure_fuzzy,
                "scaler_required": not is_pure_fuzzy,
                "fuzzy_only": is_pure_fuzzy,
            },
        }
        with open(model_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        # Create symlink to latest version
        self._update_latest_symlink(strategy_name, symbol, timeframe, model_dir)

        return str(model_dir)

    def load_model(
        self,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        version: Optional[str] = None,
    ) -> dict[str, Any]:
        """Load a saved model with all metadata.

        Args:
            strategy_name: Name of the trading strategy
            symbol: Trading symbol
            timeframe: Timeframe
            version: Specific version to load (None for latest)

        Returns:
            Dictionary containing model, config, and metadata
        """
        if version is None:
            # Load latest version
            model_dir = self.base_path / strategy_name / f"{symbol}_{timeframe}_latest"
            if not model_dir.exists():
                # Fallback: find latest version manually
                model_dir = self._find_latest_version(strategy_name, symbol, timeframe)
                if model_dir is None:
                    raise FileNotFoundError(
                        f"No models found for {strategy_name}/{symbol}_{timeframe}"
                    )
        else:
            model_dir = (
                self.base_path / strategy_name / f"{symbol}_{timeframe}_{version}"
            )

        if not model_dir.exists():
            raise FileNotFoundError(f"Model not found: {model_dir}")

        # Load model
        try:
            # Try loading full model first (easier)
            model = torch.load(model_dir / "model_full.pt", map_location="cpu")
        except:
            # Fallback: load state dict (requires rebuilding model)
            model_state = torch.load(model_dir / "model.pt", map_location="cpu")
            # Note: Would need model architecture info to rebuild
            model = model_state  # Return state dict for now

        # Load configuration
        with open(model_dir / "config.json", "r") as f:
            config = json.load(f)

        # Load metrics
        with open(model_dir / "metrics.json", "r") as f:
            metrics = json.load(f)

        # Load features
        with open(model_dir / "features.json", "r") as f:
            features = json.load(f)

        # Load metadata
        with open(model_dir / "metadata.json", "r") as f:
            metadata = json.load(f)

        # Load scaler if exists (backward compatibility + mixed feature models)
        scaler = None
        scaler_path = model_dir / "scaler.pkl"
        if scaler_path.exists():
            with open(scaler_path, "rb") as f:
                scaler = pickle.load(f)

        # Determine model architecture type
        model_version = metadata.get("model_version", "legacy")
        architecture_type = metadata.get("architecture_type", "unknown")
        is_pure_fuzzy = (
            architecture_type == "pure_fuzzy"
            or features.get("feature_type") == "pure_fuzzy"
        )

        return {
            "model": model,
            "config": config,
            "metrics": metrics,
            "features": features,
            "metadata": metadata,
            "scaler": scaler,
            "model_path": str(model_dir),
            "model_version": model_version,
            "architecture_type": architecture_type,
            "is_pure_fuzzy": is_pure_fuzzy,
        }

    def list_models(self, strategy_name: Optional[str] = None) -> list[dict[str, Any]]:
        """List all available models.

        Args:
            strategy_name: Filter by strategy name (None for all)

        Returns:
            List of model information dictionaries
        """
        models = []

        search_paths = (
            [self.base_path / strategy_name]
            if strategy_name
            else self.base_path.iterdir()
        )

        for strategy_dir in search_paths:
            if not strategy_dir.is_dir():
                continue

            for model_dir in strategy_dir.iterdir():
                if not model_dir.is_dir() or "_latest" in model_dir.name:
                    continue

                metadata_path = model_dir / "metadata.json"
                if metadata_path.exists():
                    with open(metadata_path, "r") as f:
                        metadata = json.load(f)

                    models.append(
                        {
                            "path": str(model_dir),
                            "strategy_name": metadata.get("strategy_name"),
                            "symbol": metadata.get("symbol"),
                            "timeframe": metadata.get("timeframe"),
                            "created_at": metadata.get("created_at"),
                            "accuracy": metadata.get("training_summary", {}).get(
                                "best_val_accuracy", 0
                            ),
                        }
                    )

        return sorted(models, key=lambda x: x["created_at"], reverse=True)

    def delete_model(
        self, strategy_name: str, symbol: str, timeframe: str, version: str
    ):
        """Delete a specific model version.

        Args:
            strategy_name: Strategy name
            symbol: Trading symbol
            timeframe: Timeframe
            version: Version to delete
        """
        model_dir = self.base_path / strategy_name / f"{symbol}_{timeframe}_{version}"

        if model_dir.exists():
            shutil.rmtree(model_dir)

            # Update latest symlink if this was the latest
            latest_link = (
                self.base_path / strategy_name / f"{symbol}_{timeframe}_latest"
            )
            if latest_link.exists() and latest_link.resolve() == model_dir:
                latest_link.unlink()
                # Find and link to the next most recent version
                new_latest = self._find_latest_version(strategy_name, symbol, timeframe)
                if new_latest:
                    latest_link.symlink_to(new_latest)

    def _create_version_directory(
        self, strategy_name: str, symbol: str, timeframe: str
    ) -> Path:
        """Create a new versioned directory for a model.

        Args:
            strategy_name: Strategy name
            symbol: Trading symbol
            timeframe: Timeframe

        Returns:
            Path to new version directory
        """
        strategy_dir = self.base_path / strategy_name
        strategy_dir.mkdir(exist_ok=True)

        # Find next version number
        existing_versions = []
        pattern = f"{symbol}_{timeframe}_v"

        for path in strategy_dir.iterdir():
            if path.is_dir() and path.name.startswith(pattern):
                try:
                    version_num = int(path.name.split("_v")[-1])
                    existing_versions.append(version_num)
                except ValueError:
                    continue

        next_version = max(existing_versions, default=0) + 1
        version_dir = strategy_dir / f"{symbol}_{timeframe}_v{next_version}"
        version_dir.mkdir(exist_ok=True)

        return version_dir

    def _update_latest_symlink(
        self, strategy_name: str, symbol: str, timeframe: str, target_dir: Path
    ):
        """Update the 'latest' symlink to point to the new version.

        Args:
            strategy_name: Strategy name
            symbol: Trading symbol
            timeframe: Timeframe
            target_dir: Directory to link to
        """
        strategy_dir = self.base_path / strategy_name
        latest_link = strategy_dir / f"{symbol}_{timeframe}_latest"

        # Remove existing link
        if latest_link.exists():
            latest_link.unlink()

        # Create new link
        latest_link.symlink_to(target_dir.name)

    def _find_latest_version(
        self, strategy_name: str, symbol: str, timeframe: str
    ) -> Optional[Path]:
        """Find the latest version directory.

        Args:
            strategy_name: Strategy name
            symbol: Trading symbol
            timeframe: Timeframe

        Returns:
            Path to latest version or None
        """
        strategy_dir = self.base_path / strategy_name
        if not strategy_dir.exists():
            return None

        pattern = f"{symbol}_{timeframe}_v"
        versions = []

        for path in strategy_dir.iterdir():
            if path.is_dir() and path.name.startswith(pattern):
                try:
                    version_num = int(path.name.split("_v")[-1])
                    versions.append((version_num, path))
                except ValueError:
                    continue

        if versions:
            return max(versions, key=lambda x: x[0])[1]

        return None
