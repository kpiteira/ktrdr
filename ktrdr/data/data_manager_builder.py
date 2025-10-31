"""
DataManagerBuilder - Builder pattern for DataManager initialization.

This builder pattern reduces the complexity of DataManager initialization by:
- Separating configuration concerns from business logic
- Providing fluent interface for optional configurations
- Centralizing validation and error handling
- Making initialization steps more testable and maintainable
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ktrdr.data.data_manager import DataManager

from ktrdr import get_logger

# NEW: Async infrastructure imports
from ktrdr.async_infrastructure.progress import GenericProgressManager
from ktrdr.async_infrastructure.time_estimation import TimeEstimationEngine
from ktrdr.config.loader import ConfigLoader
from ktrdr.config.models import IbHostServiceConfig, KtrdrConfig
from ktrdr.data.acquisition.data_loading_orchestrator import DataLoadingOrchestrator
from ktrdr.data.acquisition.gap_analyzer import GapAnalyzer
from ktrdr.data.acquisition.gap_classifier import GapClassifier
from ktrdr.data.acquisition.segment_manager import SegmentManager
from ktrdr.data.async_infrastructure.data_progress_renderer import DataProgressRenderer
from ktrdr.data.components.data_health_checker import DataHealthChecker
from ktrdr.data.components.data_processor import DataProcessor
from ktrdr.data.ib_data_adapter import IbDataAdapter
from ktrdr.data.local_data_loader import LocalDataLoader
from ktrdr.data.repository.data_quality_validator import DataQualityValidator
from ktrdr.errors import DataError

logger = get_logger(__name__)


class DataManagerConfiguration:
    """Configuration container for DataManager initialization."""

    def __init__(self):
        # Core parameters
        self.data_dir: Optional[str] = None
        self.max_gap_percentage: float = 5.0
        self.default_repair_method: str = "ffill"

        # IB configuration
        self.ib_host_service_config: Optional[IbHostServiceConfig] = None
        self.external_provider: Optional[IbDataAdapter] = None

        # Component instances (will be created by builder)
        self.data_loader: Optional[LocalDataLoader] = None
        self.data_validator: Optional[DataQualityValidator] = None
        self.gap_classifier: Optional[GapClassifier] = None
        self.gap_analyzer: Optional[GapAnalyzer] = None
        self.segment_manager: Optional[SegmentManager] = None
        self.data_processor: Optional[DataProcessor] = None
        self.data_loading_orchestrator: Optional[DataLoadingOrchestrator] = None
        self.health_checker: Optional[DataHealthChecker] = None

        # NEW: Generic async infrastructure components
        self.generic_progress_manager: Optional[GenericProgressManager] = None
        self.data_progress_renderer: Optional[DataProgressRenderer] = None
        self.time_estimation_engine: Optional[TimeEstimationEngine] = None


class IbConfigurationLoader:
    """Handles IB host service configuration loading and environment overrides."""

    @staticmethod
    def load_configuration() -> IbHostServiceConfig:
        """Load IB host service configuration from files and environment."""
        try:
            config_loader = ConfigLoader()
            config_path = Path("config/settings.yaml")

            # Load base configuration
            if config_path.exists():
                config = config_loader.load(config_path, KtrdrConfig)
                host_service_config = config.ib_host_service
            else:
                # Use defaults if no config file
                host_service_config = IbHostServiceConfig(
                    enabled=False, url="http://localhost:5001"
                )

            # Check for environment override file
            override_file = os.getenv("IB_HOST_SERVICE_CONFIG")
            if override_file:
                override_path = Path(f"config/environment/{override_file}.yaml")
                if override_path.exists():
                    override_config = config_loader.load(override_path, KtrdrConfig)
                    if override_config.ib_host_service:
                        host_service_config = override_config.ib_host_service
                        logger.info(
                            f"Loaded IB host service override from {override_path}"
                        )

            # Environment variable overrides for enabled flag and URL
            env_enabled = os.getenv("USE_IB_HOST_SERVICE", "").lower()
            if env_enabled in ("true", "1", "yes"):
                host_service_config.enabled = True
                env_url = os.getenv("IB_HOST_SERVICE_URL")
                if env_url:
                    host_service_config.url = env_url
            elif env_enabled in ("false", "0", "no"):
                host_service_config.enabled = False

            return host_service_config

        except Exception as e:
            logger.warning(f"Failed to load host service config, using defaults: {e}")
            return IbHostServiceConfig(enabled=False, url="http://localhost:5001")


class DataManagerBuilder:
    """
    Builder for DataManager initialization.

    Provides a fluent interface for configuring and building DataManager instances
    while centralizing complex initialization logic.
    """

    # Valid repair methods
    REPAIR_METHODS = {"ffill", "bfill", "interpolate", "zero", "mean", "median", "drop"}

    def __init__(self):
        self._config = DataManagerConfiguration()

    def with_data_directory(self, data_dir: Optional[str]) -> "DataManagerBuilder":
        """Set the data directory path."""
        self._config.data_dir = data_dir
        return self

    def with_gap_settings(self, max_gap_percentage: float) -> "DataManagerBuilder":
        """Set gap tolerance settings."""
        if max_gap_percentage < 0 or max_gap_percentage > 100:
            raise DataError(
                message=f"Invalid max_gap_percentage: {max_gap_percentage}. Must be between 0 and 100.",
                error_code="DATA-InvalidParameter",
                details={
                    "parameter": "max_gap_percentage",
                    "value": max_gap_percentage,
                    "valid_range": "0-100",
                },
            )
        self._config.max_gap_percentage = max_gap_percentage
        return self

    def with_repair_method(self, repair_method: str) -> "DataManagerBuilder":
        """Set the default repair method for missing data."""
        if repair_method not in self.REPAIR_METHODS:
            raise DataError(
                message=f"Invalid repair method: {repair_method}",
                error_code="DATA-InvalidParameter",
                details={
                    "parameter": "default_repair_method",
                    "value": repair_method,
                    "valid_options": list(self.REPAIR_METHODS),
                },
            )
        self._config.default_repair_method = repair_method
        return self

    def with_ib_configuration(
        self, config: IbHostServiceConfig
    ) -> "DataManagerBuilder":
        """Set custom IB host service configuration."""
        self._config.ib_host_service_config = config
        return self

    def _build_data_loader(self) -> LocalDataLoader:
        """Build the data loader component."""
        return LocalDataLoader(data_dir=self._config.data_dir)

    def _build_ib_adapter(self) -> IbDataAdapter:
        """Build the IB data adapter with configuration."""
        if self._config.ib_host_service_config is None:
            self._config.ib_host_service_config = (
                IbConfigurationLoader.load_configuration()
            )

        config = self._config.ib_host_service_config

        try:
            adapter = IbDataAdapter(
                use_host_service=config.enabled,
                host_service_url=config.url,
            )

            if config.enabled:
                logger.info(
                    f"IB integration enabled using host service at {config.url}"
                )
            else:
                logger.info("IB integration enabled (direct connection)")

            return adapter

        except Exception as e:
            logger.warning(f"Failed to initialize IB adapter, using fallback: {e}")
            return IbDataAdapter()  # Fallback to direct connection

    def _build_core_components(self) -> None:
        """Build all core data processing components."""
        # Core data components
        self._config.data_loader = self._build_data_loader()
        self._config.external_provider = self._build_ib_adapter()

        # Data processing components
        self._config.data_validator = DataQualityValidator(
            auto_correct=True,
            max_gap_percentage=self._config.max_gap_percentage,
        )

        self._config.gap_classifier = GapClassifier()
        self._config.gap_analyzer = GapAnalyzer(
            gap_classifier=self._config.gap_classifier
        )
        self._config.segment_manager = SegmentManager()
        self._config.data_processor = DataProcessor()

    def _build_orchestration_components(self, data_manager) -> None:
        """Build components that require DataManager reference."""
        self._config.data_loading_orchestrator = DataLoadingOrchestrator(data_manager)

        # Build health checker with all dependencies
        repair_methods = {
            "ffill": lambda df: df.ffill(),
            "bfill": lambda df: df.bfill(),
            "interpolate": lambda df: df.interpolate(),
            "zero": lambda df: df.fillna(0),
            "mean": lambda df: df.fillna(df.mean()),
            "median": lambda df: df.fillna(df.median()),
            "drop": lambda df: df.dropna(),
        }

        self._config.health_checker = DataHealthChecker(
            data_loader=self._config.data_loader,
            data_validator=self._config.data_validator,
            gap_classifier=self._config.gap_classifier,
            ib_adapter=self._config.external_provider,
            enable_ib=True,  # Always enabled
            max_gap_percentage=self._config.max_gap_percentage,
            default_repair_method=self._config.default_repair_method,
            repair_methods=repair_methods,
        )

    def _create_async_infrastructure(self, config: DataManagerConfiguration) -> None:
        """Create generic async infrastructure with existing features."""

        # Create time estimation engine (preserve existing logic)
        cache_dir = Path.home() / ".ktrdr" / "cache"
        cache_file = cache_dir / "progress_time_estimation.pkl"
        config.time_estimation_engine = TimeEstimationEngine(cache_file)

        # Create data progress renderer with existing features
        config.data_progress_renderer = DataProgressRenderer(
            time_estimation_engine=config.time_estimation_engine,
            enable_hierarchical_progress=True,
        )

        # Create generic progress manager
        config.generic_progress_manager = GenericProgressManager(
            renderer=config.data_progress_renderer
        )

        logger.info("Created generic async infrastructure with preserved features")

    def build_configuration(self) -> DataManagerConfiguration:
        """
        Build and return the complete configuration.

        This method is used internally by DataManager to get the built configuration.
        """
        # Build core components first
        self._build_core_components()

        # NEW: Create async infrastructure
        self._create_async_infrastructure(self._config)

        logger.info(
            f"Built DataManager configuration with max_gap_percentage={self._config.max_gap_percentage}%, "
            f"default_repair_method='{self._config.default_repair_method}'"
        )

        return self._config

    def build(self) -> "DataManager":
        """Build DataManager with enhanced async infrastructure."""
        # Build the configuration with all components including async infrastructure
        config = self.build_configuration()

        # Create DataManager with enhanced configuration and builder reference
        from ktrdr.data.data_manager import DataManager

        return DataManager(
            data_dir=config.data_dir,
            max_gap_percentage=config.max_gap_percentage,
            default_repair_method=config.default_repair_method,
            builder=self,  # Pass builder so finalize_configuration gets called
            builder_config=config,  # Pass full configuration
        )

    def finalize_configuration(self, data_manager) -> DataManagerConfiguration:
        """
        Finalize configuration with DataManager-dependent components.

        This is called by DataManager after it's been initialized with the base configuration.
        """
        self._build_orchestration_components(data_manager)
        return self._config


def create_default_datamanager_builder() -> DataManagerBuilder:
    """Create a DataManagerBuilder with sensible defaults."""
    return DataManagerBuilder().with_gap_settings(5.0).with_repair_method("ffill")


def create_datamanager_builder_for_testing() -> DataManagerBuilder:
    """Create a DataManagerBuilder configured for testing."""
    return (
        DataManagerBuilder()
        .with_gap_settings(10.0)  # More lenient for test data
        .with_repair_method("interpolate")
    )
