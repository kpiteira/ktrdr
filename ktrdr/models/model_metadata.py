"""Enhanced model metadata for multi-scope training and deployment."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

from ktrdr import get_logger

logger = get_logger(__name__)


class ModelScope(str, Enum):
    """Model deployment scope."""
    UNIVERSAL = "universal"
    SYMBOL_GROUP = "symbol_group"
    SYMBOL_SPECIFIC = "symbol_specific"


class TrainingStatus(str, Enum):
    """Training status enumeration."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TrainingDataInfo:
    """Information about training data used."""
    symbols: List[str]
    timeframes: List[str]
    base_timeframe: Optional[str]
    date_range: List[str]  # [start_date, end_date]
    total_samples: int
    samples_per_symbol: Optional[Dict[str, int]] = None
    data_quality_score: Optional[float] = None


@dataclass
class DeploymentCapabilities:
    """Model deployment capabilities and restrictions."""
    symbol_restrictions: Optional[List[str]]  # None = universal
    timeframe_restrictions: List[str]
    asset_class_compatibility: List[str]
    min_liquidity_tier: Optional[str] = None
    geographic_restrictions: Optional[List[str]] = None


@dataclass
class FeatureArchitecture:
    """Model feature architecture details."""
    input_size: int
    timeframe_features: Optional[Dict[str, int]] = None  # {timeframe: feature_count}
    symbol_embedding_dim: Optional[int] = None
    attention_mechanism: bool = False
    feature_combination_method: str = "concatenation"
    total_fuzzy_features: int = 0
    temporal_features: int = 0


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics."""
    # Overall metrics
    cross_symbol_accuracy: Optional[float] = None
    overall_accuracy: float = 0.0
    overall_precision: float = 0.0
    overall_recall: float = 0.0
    overall_f1_score: float = 0.0
    
    # Per-symbol metrics
    per_symbol_accuracy: Optional[Dict[str, float]] = None
    per_symbol_precision: Optional[Dict[str, float]] = None
    per_symbol_recall: Optional[Dict[str, float]] = None
    
    # Multi-timeframe metrics
    per_timeframe_importance: Optional[Dict[str, float]] = None
    attention_diversity_score: Optional[float] = None
    
    # Generalization metrics
    generalization_score: Optional[float] = None  # Performance on unseen symbols
    cross_validation_score: Optional[float] = None
    
    # Training metrics
    final_train_loss: float = 0.0
    final_val_loss: float = 0.0
    training_stability: Optional[float] = None  # Loss variance indicator
    convergence_epoch: Optional[int] = None


@dataclass
class TrainingConfiguration:
    """Training configuration summary."""
    optimizer: str
    learning_rate: float
    batch_size: int
    epochs_trained: int
    early_stopping_epoch: Optional[int] = None
    regularization: Optional[Dict[str, Any]] = None
    data_augmentation: bool = False
    balanced_sampling: bool = False


@dataclass
class ModelCompatibility:
    """Model compatibility information."""
    min_python_version: str = "3.8"
    pytorch_version: str = "2.0.0"
    ktrdr_version: str = "1.0.0"
    required_indicators: List[str] = field(default_factory=list)
    required_fuzzy_sets: List[str] = field(default_factory=list)


@dataclass
class ModelMetadata:
    """Comprehensive model metadata for multi-scope models."""
    
    # Basic information
    strategy_name: str
    strategy_version: str
    model_version: int
    scope: ModelScope
    created_at: Optional[str] = None  # ISO format, auto-generated if None
    training_duration_minutes: Optional[float] = None
    
    # Training data information
    training_data: TrainingDataInfo = None
    
    # Model capabilities
    deployment_capabilities: DeploymentCapabilities = None
    
    # Architecture details
    feature_architecture: FeatureArchitecture = None
    
    # Performance metrics
    performance_metrics: PerformanceMetrics = None
    
    # Training details
    training_config: TrainingConfiguration = None
    
    # Compatibility information
    compatibility: ModelCompatibility = field(default_factory=ModelCompatibility)
    
    # Status and validation
    training_status: TrainingStatus = TrainingStatus.IN_PROGRESS
    validation_passed: bool = False
    notes: Optional[str] = None
    
    # Legacy compatibility
    legacy_symbol: Optional[str] = None  # For migrated legacy models
    legacy_timeframe: Optional[str] = None
    
    def __post_init__(self):
        """Initialize default values and validate consistency."""
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()
        
        # Initialize nested objects if None
        if self.training_data is None:
            self.training_data = TrainingDataInfo(
                symbols=[], timeframes=[], date_range=["", ""], total_samples=0
            )
        
        if self.deployment_capabilities is None:
            self.deployment_capabilities = DeploymentCapabilities(
                symbol_restrictions=None,
                timeframe_restrictions=[],
                asset_class_compatibility=[]
            )
        
        if self.feature_architecture is None:
            self.feature_architecture = FeatureArchitecture(input_size=0)
        
        if self.performance_metrics is None:
            self.performance_metrics = PerformanceMetrics()
        
        if self.training_config is None:
            self.training_config = TrainingConfiguration(
                optimizer="adam", learning_rate=0.001, batch_size=32, epochs_trained=0
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelMetadata":
        """Create from dictionary (JSON deserialization)."""
        
        # Handle nested dataclasses
        if "training_data" in data and isinstance(data["training_data"], dict):
            data["training_data"] = TrainingDataInfo(**data["training_data"])
        
        if "deployment_capabilities" in data and isinstance(data["deployment_capabilities"], dict):
            data["deployment_capabilities"] = DeploymentCapabilities(**data["deployment_capabilities"])
        
        if "feature_architecture" in data and isinstance(data["feature_architecture"], dict):
            data["feature_architecture"] = FeatureArchitecture(**data["feature_architecture"])
        
        if "performance_metrics" in data and isinstance(data["performance_metrics"], dict):
            data["performance_metrics"] = PerformanceMetrics(**data["performance_metrics"])
        
        if "training_config" in data and isinstance(data["training_config"], dict):
            data["training_config"] = TrainingConfiguration(**data["training_config"])
        
        if "compatibility" in data and isinstance(data["compatibility"], dict):
            data["compatibility"] = ModelCompatibility(**data["compatibility"])
        
        # Handle enums
        if "scope" in data and isinstance(data["scope"], str):
            data["scope"] = ModelScope(data["scope"])
        
        if "training_status" in data and isinstance(data["training_status"], str):
            data["training_status"] = TrainingStatus(data["training_status"])
        
        return cls(**data)
    
    def save(self, model_path: Union[str, Path]) -> Path:
        """Save metadata to model directory."""
        model_path = Path(model_path)
        metadata_file = model_path / "metadata.json"
        
        # Ensure directory exists
        model_path.mkdir(parents=True, exist_ok=True)
        
        # Save metadata
        with open(metadata_file, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        
        logger.info(f"Model metadata saved to: {metadata_file}")
        return metadata_file
    
    @classmethod
    def load(cls, model_path: Union[str, Path]) -> "ModelMetadata":
        """Load metadata from model directory."""
        model_path = Path(model_path)
        metadata_file = model_path / "metadata.json"
        
        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_file}")
        
        with open(metadata_file, 'r') as f:
            data = json.load(f)
        
        return cls.from_dict(data)
    
    def is_compatible_with(self, symbol: str, timeframe: str, asset_class: str = None) -> bool:
        """Check if model is compatible with trading target."""
        
        # Check symbol restrictions
        if self.deployment_capabilities.symbol_restrictions is not None:
            if symbol not in self.deployment_capabilities.symbol_restrictions:
                return False
        
        # Check timeframe restrictions
        if timeframe not in self.deployment_capabilities.timeframe_restrictions:
            return False
        
        # Check asset class compatibility
        if asset_class and self.deployment_capabilities.asset_class_compatibility:
            if asset_class not in self.deployment_capabilities.asset_class_compatibility:
                return False
        
        return True
    
    def get_summary(self) -> Dict[str, Any]:
        """Get concise metadata summary."""
        return {
            "strategy": f"{self.strategy_name} v{self.strategy_version}",
            "model_version": self.model_version,
            "scope": self.scope.value,
            "training_symbols": self.training_data.symbols,
            "training_timeframes": self.training_data.timeframes,
            "performance": {
                "accuracy": self.performance_metrics.overall_accuracy,
                "cross_symbol_accuracy": self.performance_metrics.cross_symbol_accuracy,
                "generalization_score": self.performance_metrics.generalization_score
            },
            "feature_count": self.feature_architecture.input_size,
            "training_status": self.training_status.value,
            "created_at": self.created_at
        }
    
    def update_performance_metrics(self, metrics: Dict[str, Any]) -> None:
        """Update performance metrics from training results."""
        pm = self.performance_metrics
        
        # Update overall metrics
        pm.overall_accuracy = metrics.get("accuracy", pm.overall_accuracy)
        pm.overall_precision = metrics.get("precision", pm.overall_precision)
        pm.overall_recall = metrics.get("recall", pm.overall_recall)
        pm.overall_f1_score = metrics.get("f1_score", pm.overall_f1_score)
        
        # Update training metrics
        pm.final_train_loss = metrics.get("train_loss", pm.final_train_loss)
        pm.final_val_loss = metrics.get("val_loss", pm.final_val_loss)
        pm.convergence_epoch = metrics.get("convergence_epoch", pm.convergence_epoch)
        
        # Update multi-scope specific metrics
        if "cross_symbol_accuracy" in metrics:
            pm.cross_symbol_accuracy = metrics["cross_symbol_accuracy"]
        
        if "per_symbol_metrics" in metrics:
            per_symbol = metrics["per_symbol_metrics"]
            pm.per_symbol_accuracy = per_symbol.get("accuracy", {})
            pm.per_symbol_precision = per_symbol.get("precision", {})
            pm.per_symbol_recall = per_symbol.get("recall", {})
        
        if "generalization_score" in metrics:
            pm.generalization_score = metrics["generalization_score"]
        
        if "attention_metrics" in metrics:
            attention = metrics["attention_metrics"]
            pm.per_timeframe_importance = attention.get("timeframe_importance", {})
            pm.attention_diversity_score = attention.get("diversity_score")
        
        logger.debug(f"Updated performance metrics for {self.strategy_name}")


class ModelMetadataManager:
    """Manager for model metadata operations."""
    
    def __init__(self, models_base_path: Union[str, Path] = "models"):
        self.models_base_path = Path(models_base_path)
    
    def create_metadata(
        self,
        strategy_name: str,
        strategy_version: str,
        model_version: int,
        scope: ModelScope,
        training_symbols: List[str],
        training_timeframes: List[str],
        **kwargs
    ) -> ModelMetadata:
        """Create new model metadata."""
        
        training_data = TrainingDataInfo(
            symbols=training_symbols,
            timeframes=training_timeframes,
            base_timeframe=kwargs.get("base_timeframe"),
            date_range=kwargs.get("date_range", ["", ""]),
            total_samples=kwargs.get("total_samples", 0)
        )
        
        metadata = ModelMetadata(
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            model_version=model_version,
            scope=scope,
            training_data=training_data,
            created_at=datetime.utcnow().isoformat()
        )
        
        logger.info(f"Created metadata for {strategy_name} v{model_version} ({scope.value})")
        return metadata
    
    def find_compatible_models(
        self, symbol: str, timeframe: str, asset_class: str = None
    ) -> List[Tuple[str, ModelMetadata]]:
        """Find models compatible with trading target."""
        
        compatible_models = []
        
        # Search all strategy directories
        for strategy_dir in self.models_base_path.iterdir():
            if not strategy_dir.is_dir():
                continue
            
            # Search all model versions in strategy
            for model_dir in strategy_dir.iterdir():
                if not model_dir.is_dir():
                    continue
                
                try:
                    metadata = ModelMetadata.load(model_dir)
                    if metadata.is_compatible_with(symbol, timeframe, asset_class):
                        model_path = f"{strategy_dir.name}/{model_dir.name}"
                        compatible_models.append((model_path, metadata))
                
                except Exception as e:
                    logger.debug(f"Could not load metadata from {model_dir}: {e}")
        
        # Sort by performance (cross-symbol accuracy if available, then overall accuracy)
        compatible_models.sort(
            key=lambda x: (
                x[1].performance_metrics.cross_symbol_accuracy or 0,
                x[1].performance_metrics.overall_accuracy
            ),
            reverse=True
        )
        
        return compatible_models
    
    def get_model_rankings(self, asset_class: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get model rankings by scope and performance."""
        
        rankings = {
            "universal": [],
            "symbol_group": [],
            "symbol_specific": []
        }
        
        for strategy_dir in self.models_base_path.iterdir():
            if not strategy_dir.is_dir():
                continue
            
            for model_dir in strategy_dir.iterdir():
                if not model_dir.is_dir():
                    continue
                
                try:
                    metadata = ModelMetadata.load(model_dir)
                    
                    # Filter by asset class if specified
                    if asset_class and metadata.deployment_capabilities.asset_class_compatibility:
                        if asset_class not in metadata.deployment_capabilities.asset_class_compatibility:
                            continue
                    
                    model_info = {
                        "path": f"{strategy_dir.name}/{model_dir.name}",
                        "summary": metadata.get_summary(),
                        "metadata": metadata
                    }
                    
                    rankings[metadata.scope.value].append(model_info)
                
                except Exception as e:
                    logger.debug(f"Could not load metadata from {model_dir}: {e}")
        
        # Sort each category by performance
        for scope in rankings:
            rankings[scope].sort(
                key=lambda x: (
                    x["metadata"].performance_metrics.cross_symbol_accuracy or 0,
                    x["metadata"].performance_metrics.overall_accuracy
                ),
                reverse=True
            )
        
        return rankings


# Global instance
metadata_manager = ModelMetadataManager()