"""Enhanced model storage system supporting multi-scope models and comprehensive metadata."""

import json
import pickle
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

import torch

from ktrdr import get_logger
from ktrdr.config.models import LegacyStrategyConfiguration, StrategyConfigurationV2
from ktrdr.config.strategy_loader import strategy_loader
from ktrdr.models.model_metadata import (
    ModelMetadata,
    ModelMetadataManager,
    ModelScope,
    TrainingStatus,
)

logger = get_logger(__name__)


class ModelStorageV2:
    """Enhanced model storage with multi-scope support and comprehensive metadata."""

    def __init__(self, base_path: Union[str, Path] = "models"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.metadata_manager = ModelMetadataManager(base_path)

    def get_model_path(
        self,
        strategy_config: Union[StrategyConfigurationV2, LegacyStrategyConfiguration],
        model_version: Optional[int] = None,
    ) -> Path:
        """
        Get model storage path based on strategy configuration.

        Args:
            strategy_config: Strategy configuration (v1 or v2)
            model_version: Specific version number (auto-incremented if None)

        Returns:
            Path to model directory
        """
        strategy_dir, model_id = strategy_loader.get_model_storage_path_components(
            strategy_config
        )

        if model_version is None:
            model_version = self._get_next_version(strategy_dir, model_id)

        model_path = self.base_path / strategy_dir / f"{model_id}_v{model_version}"
        return model_path

    def _get_next_version(self, strategy_dir: str, model_id: str) -> int:
        """Get next available version number for model."""
        strategy_path = self.base_path / strategy_dir

        if not strategy_path.exists():
            return 1

        max_version = 0
        for model_dir in strategy_path.iterdir():
            if model_dir.is_dir() and model_dir.name.startswith(f"{model_id}_v"):
                try:
                    version_str = model_dir.name.split("_v")[-1]
                    version = int(version_str)
                    max_version = max(max_version, version)
                except ValueError:
                    continue

        return max_version + 1

    def save_model(
        self,
        model: torch.nn.Module,
        metadata: ModelMetadata,
        strategy_config: Union[StrategyConfigurationV2, LegacyStrategyConfiguration],
        training_metrics: Optional[dict[str, Any]] = None,
        feature_names: Optional[list[str]] = None,
        scaler: Optional[Any] = None,
        model_version: Optional[int] = None,
        save_full_model: bool = True,
    ) -> Path:
        """
        Save model with comprehensive metadata and artifacts.

        Args:
            model: Trained PyTorch model
            metadata: Model metadata object
            strategy_config: Strategy configuration used for training
            training_metrics: Final training metrics
            feature_names: List of feature names
            scaler: Optional feature scaler
            model_version: Specific version number
            save_full_model: Whether to save full model (for inference)

        Returns:
            Path to saved model directory
        """
        # Get model path
        model_path = self.get_model_path(strategy_config, model_version)
        model_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Saving model to: {model_path}")

        # Update metadata with training results
        if training_metrics:
            metadata.update_performance_metrics(training_metrics)

        metadata.training_status = TrainingStatus.COMPLETED
        metadata.validation_passed = True  # TODO: Add actual validation

        # Save model files
        model_files_saved = []

        # 1. Save model state dict (for continued training)
        model_state_path = model_path / "model.pt"
        torch.save(model.state_dict(), model_state_path)
        model_files_saved.append("model.pt")
        logger.debug(f"Saved model state dict: {model_state_path}")

        # 2. Save full model (for inference)
        if save_full_model:
            full_model_path = model_path / "model_full.pt"
            torch.save(model, full_model_path)
            model_files_saved.append("model_full.pt")
            logger.debug(f"Saved full model: {full_model_path}")

        # 3. Save strategy configuration
        config_path = model_path / "config.json"
        if isinstance(strategy_config, StrategyConfigurationV2):
            config_dict = strategy_config.model_dump()
        else:
            # Convert legacy config to dict
            config_dict = {
                "name": strategy_config.name,
                "description": strategy_config.description,
                "version": strategy_config.version,
                "indicators": strategy_config.indicators,
                "fuzzy_sets": strategy_config.fuzzy_sets,
                "model": strategy_config.model,
                "decisions": strategy_config.decisions,
                "training": strategy_config.training,
                "orchestrator": strategy_config.orchestrator,
                "risk_management": strategy_config.risk_management,
                "backtesting": strategy_config.backtesting,
                "data": strategy_config.data,
                "_format": "legacy_v1",
            }

        with open(config_path, "w") as f:
            json.dump(config_dict, f, indent=2, default=str)
        model_files_saved.append("config.json")
        logger.debug(f"Saved strategy config: {config_path}")

        # 4. Save feature names
        if feature_names:
            features_path = model_path / "features.json"
            features_info = {
                "feature_names": feature_names,
                "feature_count": len(feature_names),
                "created_at": datetime.utcnow().isoformat(),
            }
            with open(features_path, "w") as f:
                json.dump(features_info, f, indent=2)
            model_files_saved.append("features.json")
            logger.debug(f"Saved feature names: {features_path}")

        # 5. Save scaler if provided
        if scaler is not None:
            scaler_path = model_path / "scaler.pkl"
            with open(scaler_path, "wb") as f:
                pickle.dump(scaler, f)
            model_files_saved.append("scaler.pkl")
            logger.debug(f"Saved scaler: {scaler_path}")

        # 6. Save training metrics
        if training_metrics:
            metrics_path = model_path / "metrics.json"
            metrics_info = {
                "training_metrics": training_metrics,
                "saved_at": datetime.utcnow().isoformat(),
                "model_files": model_files_saved,
            }
            with open(metrics_path, "w") as f:
                json.dump(metrics_info, f, indent=2, default=str)
            model_files_saved.append("metrics.json")
            logger.debug(f"Saved training metrics: {metrics_path}")

        # 7. Save comprehensive metadata (must be last)
        metadata.save(model_path)
        model_files_saved.append("metadata.json")

        # 8. Create latest symlink for easy access
        self._create_latest_symlink(model_path)

        logger.info(f"✅ Model saved successfully: {model_path}")
        logger.info(f"   Files saved: {', '.join(model_files_saved)}")

        return model_path

    def _create_latest_symlink(self, model_path: Path) -> None:
        """Create 'latest' symlink pointing to most recent model version."""
        strategy_dir = model_path.parent
        latest_link = strategy_dir / f"{model_path.name.split('_v')[0]}_latest"

        # Remove existing symlink if it exists
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()

        # Create new symlink (relative path for portability)
        try:
            latest_link.symlink_to(model_path.name)
            logger.debug(f"Created latest symlink: {latest_link} -> {model_path.name}")
        except OSError as e:
            # Symlinks might not be supported on all filesystems
            logger.debug(f"Could not create symlink: {e}")

    def load_model(
        self,
        model_path: Union[str, Path],
        load_full_model: bool = True,
        device: str = "cpu",
    ) -> tuple[torch.nn.Module, ModelMetadata, dict[str, Any]]:
        """
        Load model with metadata and artifacts.

        Args:
            model_path: Path to model directory or strategy/model_id format
            load_full_model: Whether to load full model or just state dict
            device: Device to load model on

        Returns:
            Tuple of (model, metadata, artifacts)
        """
        # Resolve model path
        model_path = self._resolve_model_path(model_path)

        if not model_path.exists():
            raise FileNotFoundError(f"Model directory not found: {model_path}")

        logger.info(f"Loading model from: {model_path}")

        # Load metadata
        metadata = ModelMetadata.load(model_path)

        # Load model
        if load_full_model:
            full_model_path = model_path / "model_full.pt"
            if full_model_path.exists():
                # Use weights_only=False for backward compatibility
                model = torch.load(
                    full_model_path, map_location=device, weights_only=False
                )
                logger.debug("Loaded full model")
            else:
                raise FileNotFoundError(f"Full model file not found: {full_model_path}")
        else:
            # Load state dict only (requires model architecture)
            state_dict_path = model_path / "model.pt"
            if state_dict_path.exists():
                state_dict = torch.load(
                    state_dict_path, map_location=device, weights_only=False
                )
                # Note: Caller must create model architecture and load state dict
                model = state_dict
                logger.debug("Loaded model state dict")
            else:
                raise FileNotFoundError(
                    f"Model state dict not found: {state_dict_path}"
                )

        # Load artifacts
        artifacts = {}

        # Load strategy config
        config_path = model_path / "config.json"
        if config_path.exists():
            with open(config_path) as f:
                artifacts["config"] = json.load(f)

        # Load feature names
        features_path = model_path / "features.json"
        if features_path.exists():
            with open(features_path) as f:
                artifacts["features"] = json.load(f)

        # Load scaler
        scaler_path = model_path / "scaler.pkl"
        if scaler_path.exists():
            with open(scaler_path, "rb") as f:
                artifacts["scaler"] = pickle.load(f)

        # Load training metrics
        metrics_path = model_path / "metrics.json"
        if metrics_path.exists():
            with open(metrics_path) as f:
                artifacts["training_metrics"] = json.load(f)

        logger.info(
            f"✅ Model loaded successfully: {metadata.strategy_name} v{metadata.model_version}"
        )
        return model, metadata, artifacts

    def _resolve_model_path(self, model_path: Union[str, Path]) -> Path:
        """Resolve model path from various formats."""
        model_path = Path(model_path)

        # If it's already an absolute path to a directory, use it
        if model_path.is_absolute() and model_path.exists():
            return model_path

        # If it starts with base_path, it's already resolved
        if str(model_path).startswith(str(self.base_path)):
            return model_path

        # If it's a relative path from base_path
        if not model_path.is_absolute():
            full_path = self.base_path / model_path
            if full_path.exists():
                return full_path

        # If it's in strategy/model_id format, resolve it
        if "/" in str(model_path):
            return self.base_path / model_path

        return model_path

    def list_models(
        self,
        strategy_name: Optional[str] = None,
        scope: Optional[ModelScope] = None,
        compatible_with: Optional[tuple[str, str]] = None,  # (symbol, timeframe)
    ) -> list[dict[str, Any]]:
        """
        List available models with filtering options.

        Args:
            strategy_name: Filter by strategy name
            scope: Filter by model scope
            compatible_with: Filter by compatibility (symbol, timeframe)

        Returns:
            List of model information dictionaries
        """
        models = []

        for strategy_dir in self.base_path.iterdir():
            if not strategy_dir.is_dir():
                continue

            # Filter by strategy name
            if strategy_name and strategy_dir.name != strategy_name:
                continue

            for model_dir in strategy_dir.iterdir():
                if not model_dir.is_dir() or model_dir.name.endswith("_latest"):
                    continue

                try:
                    metadata = ModelMetadata.load(model_dir)

                    # Filter by scope
                    if scope and metadata.scope != scope:
                        continue

                    # Filter by compatibility
                    if compatible_with:
                        symbol, timeframe = compatible_with
                        if not metadata.is_compatible_with(symbol, timeframe):
                            continue

                    model_info = {
                        "path": f"{strategy_dir.name}/{model_dir.name}",
                        "strategy_name": metadata.strategy_name,
                        "model_version": metadata.model_version,
                        "scope": metadata.scope.value,
                        "training_symbols": metadata.training_data.symbols,
                        "training_timeframes": metadata.training_data.timeframes,
                        "accuracy": metadata.performance_metrics.overall_accuracy,
                        "cross_symbol_accuracy": metadata.performance_metrics.cross_symbol_accuracy,
                        "created_at": metadata.created_at,
                        "training_status": metadata.training_status.value,
                    }

                    models.append(model_info)

                except Exception as e:
                    logger.debug(f"Could not load metadata from {model_dir}: {e}")

        # Sort by creation date (newest first)
        models.sort(key=lambda x: x["created_at"], reverse=True)
        return models

    def delete_model(self, model_path: Union[str, Path], confirm: bool = False) -> bool:
        """
        Delete a model and all its artifacts.

        Args:
            model_path: Path to model directory
            confirm: Safety confirmation flag

        Returns:
            True if deletion successful
        """
        if not confirm:
            logger.warning(
                "Model deletion requires explicit confirmation (confirm=True)"
            )
            return False

        model_path = self._resolve_model_path(model_path)

        if not model_path.exists():
            logger.warning(f"Model path does not exist: {model_path}")
            return False

        try:
            # Load metadata for logging
            try:
                metadata = ModelMetadata.load(model_path)
                logger.info(
                    f"Deleting model: {metadata.strategy_name} v{metadata.model_version}"
                )
            except Exception:
                logger.info(f"Deleting model directory: {model_path}")

            # Remove directory and all contents
            shutil.rmtree(model_path)

            # Remove latest symlink if it exists
            strategy_dir = model_path.parent
            latest_link = strategy_dir / f"{model_path.name.split('_v')[0]}_latest"
            if latest_link.is_symlink() and latest_link.readlink() == model_path.name:
                latest_link.unlink()
                logger.debug(f"Removed latest symlink: {latest_link}")

            logger.info(f"✅ Model deleted successfully: {model_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete model {model_path}: {e}")
            return False

    def migrate_legacy_model(
        self,
        legacy_path: Union[str, Path],
        strategy_config: Union[StrategyConfigurationV2, LegacyStrategyConfiguration],
    ) -> Optional[Path]:
        """
        Migrate a legacy model to the new storage format.

        Args:
            legacy_path: Path to legacy model directory
            strategy_config: Strategy configuration for the model

        Returns:
            Path to migrated model or None if migration failed
        """
        legacy_path = Path(legacy_path)

        if not legacy_path.exists():
            logger.error(f"Legacy model path does not exist: {legacy_path}")
            return None

        logger.info(f"Migrating legacy model: {legacy_path}")

        try:
            # Extract legacy model information
            legacy_name = legacy_path.name
            parts = legacy_name.split("_")

            if len(parts) >= 3 and parts[-1].startswith("v"):
                legacy_symbol = parts[0]
                legacy_timeframe = parts[1]
                legacy_version = int(parts[-1][1:])
            else:
                logger.warning(f"Could not parse legacy model name: {legacy_name}")
                legacy_symbol = "unknown"
                legacy_timeframe = "1h"
                legacy_version = 1

            # Create metadata for legacy model
            symbols, timeframes = (
                strategy_loader.extract_training_symbols_and_timeframes(strategy_config)
            )

            # Determine scope based on strategy config
            if isinstance(strategy_config, StrategyConfigurationV2):
                scope = strategy_config.scope
            else:
                scope = ModelScope.SYMBOL_SPECIFIC  # Legacy models are symbol-specific

            metadata = self.metadata_manager.create_metadata(
                strategy_name=strategy_config.name,
                strategy_version=strategy_config.version or "1.0",
                model_version=legacy_version,
                scope=scope,
                training_symbols=symbols or [legacy_symbol],
                training_timeframes=timeframes or [legacy_timeframe],
            )

            # Set legacy compatibility info
            metadata.legacy_symbol = legacy_symbol
            metadata.legacy_timeframe = legacy_timeframe
            metadata.training_status = TrainingStatus.COMPLETED
            metadata.validation_passed = True

            # Get new model path
            new_path = self.get_model_path(strategy_config, legacy_version)
            new_path.mkdir(parents=True, exist_ok=True)

            # Copy legacy files
            for file_path in legacy_path.iterdir():
                if file_path.is_file():
                    shutil.copy2(file_path, new_path / file_path.name)
                    logger.debug(f"Copied {file_path.name} to new location")

            # Save new metadata
            metadata.save(new_path)

            # Create latest symlink
            self._create_latest_symlink(new_path)

            logger.info(
                f"✅ Legacy model migrated successfully: {legacy_path} -> {new_path}"
            )
            return new_path

        except Exception as e:
            logger.error(f"Failed to migrate legacy model {legacy_path}: {e}")
            return None


# Global instance
model_storage_v2 = ModelStorageV2()
