"""
Factory for creating indicators from configuration.

This module provides the IndicatorFactory class which creates indicator instances
based on configuration settings.
"""

import importlib
from typing import Union

from ktrdr import get_logger
from ktrdr.config.models import IndicatorConfig, IndicatorsConfig
from ktrdr.errors import ConfigurationError
from ktrdr.indicators.ad_line import ADLineIndicator
from ktrdr.indicators.adx_indicator import ADXIndicator
from ktrdr.indicators.aroon_indicator import AroonIndicator
from ktrdr.indicators.atr_indicator import ATRIndicator
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.indicators.bollinger_band_width_indicator import BollingerBandWidthIndicator
from ktrdr.indicators.bollinger_bands_indicator import BollingerBandsIndicator
from ktrdr.indicators.cci_indicator import CCIIndicator
from ktrdr.indicators.cmf_indicator import CMFIndicator
from ktrdr.indicators.distance_from_ma_indicator import DistanceFromMAIndicator
from ktrdr.indicators.donchian_channels import DonchianChannelsIndicator
from ktrdr.indicators.fisher_transform import FisherTransformIndicator
from ktrdr.indicators.ichimoku_indicator import IchimokuIndicator
from ktrdr.indicators.keltner_channels import KeltnerChannelsIndicator
from ktrdr.indicators.ma_indicators import ExponentialMovingAverage, SimpleMovingAverage
from ktrdr.indicators.macd_indicator import MACDIndicator
from ktrdr.indicators.mfi_indicator import MFIIndicator
from ktrdr.indicators.momentum_indicator import MomentumIndicator
from ktrdr.indicators.obv_indicator import OBVIndicator
from ktrdr.indicators.parabolic_sar_indicator import ParabolicSARIndicator
from ktrdr.indicators.roc_indicator import ROCIndicator
from ktrdr.indicators.rsi_indicator import RSIIndicator
from ktrdr.indicators.rvi_indicator import RVIIndicator
from ktrdr.indicators.squeeze_intensity_indicator import SqueezeIntensityIndicator
from ktrdr.indicators.stochastic_indicator import StochasticIndicator
from ktrdr.indicators.supertrend_indicator import SuperTrendIndicator
from ktrdr.indicators.volume_ratio_indicator import VolumeRatioIndicator
from ktrdr.indicators.vwap_indicator import VWAPIndicator
from ktrdr.indicators.williams_r_indicator import WilliamsRIndicator
from ktrdr.indicators.zigzag_indicator import ZigZagIndicator

logger = get_logger(__name__)

# Registry of built-in indicators for direct access
# Includes PascalCase (official), UPPERCASE, and lowercase variants for compatibility
BUILT_IN_INDICATORS: dict[str, type[BaseIndicator]] = {
    # PascalCase and UPPERCASE variants
    "RSI": RSIIndicator,
    "RSIIndicator": RSIIndicator,
    "SMA": SimpleMovingAverage,
    "SimpleMovingAverage": SimpleMovingAverage,
    "EMA": ExponentialMovingAverage,
    "ExponentialMovingAverage": ExponentialMovingAverage,
    "MACD": MACDIndicator,
    "MACDIndicator": MACDIndicator,
    "ZigZag": ZigZagIndicator,
    "ZigZagIndicator": ZigZagIndicator,
    "Stochastic": StochasticIndicator,
    "StochasticIndicator": StochasticIndicator,
    "WilliamsR": WilliamsRIndicator,
    "WilliamsRIndicator": WilliamsRIndicator,
    "ATR": ATRIndicator,
    "ATRIndicator": ATRIndicator,
    "OBV": OBVIndicator,
    "OBVIndicator": OBVIndicator,
    "BollingerBands": BollingerBandsIndicator,
    "BollingerBandsIndicator": BollingerBandsIndicator,
    "CCI": CCIIndicator,
    "CCIIndicator": CCIIndicator,
    "Momentum": MomentumIndicator,
    "MomentumIndicator": MomentumIndicator,
    "ROC": ROCIndicator,
    "ROCIndicator": ROCIndicator,
    "VWAP": VWAPIndicator,
    "VWAPIndicator": VWAPIndicator,
    "ParabolicSAR": ParabolicSARIndicator,
    "ParabolicSARIndicator": ParabolicSARIndicator,
    "Ichimoku": IchimokuIndicator,
    "IchimokuIndicator": IchimokuIndicator,
    "RVI": RVIIndicator,
    "RVIIndicator": RVIIndicator,
    "MFI": MFIIndicator,
    "MFIIndicator": MFIIndicator,
    "Aroon": AroonIndicator,
    "AroonIndicator": AroonIndicator,
    "DonchianChannels": DonchianChannelsIndicator,
    "DonchianChannelsIndicator": DonchianChannelsIndicator,
    "KeltnerChannels": KeltnerChannelsIndicator,
    "KeltnerChannelsIndicator": KeltnerChannelsIndicator,
    "ADLine": ADLineIndicator,
    "ADLineIndicator": ADLineIndicator,
    "AccumulationDistribution": ADLineIndicator,
    "CMF": CMFIndicator,
    "CMFIndicator": CMFIndicator,
    "ChaikinMoneyFlow": CMFIndicator,
    "ADX": ADXIndicator,
    "ADXIndicator": ADXIndicator,
    "AverageDirectionalIndex": ADXIndicator,
    "SuperTrend": SuperTrendIndicator,
    "SuperTrendIndicator": SuperTrendIndicator,
    "FisherTransform": FisherTransformIndicator,
    "FisherTransformIndicator": FisherTransformIndicator,
    "BollingerBandWidth": BollingerBandWidthIndicator,
    "BollingerBandWidthIndicator": BollingerBandWidthIndicator,
    "VolumeRatio": VolumeRatioIndicator,
    "VolumeRatioIndicator": VolumeRatioIndicator,
    "SqueezeIntensity": SqueezeIntensityIndicator,
    "SqueezeIntensityIndicator": SqueezeIntensityIndicator,
    "DistanceFromMA": DistanceFromMAIndicator,
    "DistanceFromMAIndicator": DistanceFromMAIndicator,
    # Lowercase and camelCase variants for strategy compatibility
    "rsi": RSIIndicator,
    "sma": SimpleMovingAverage,
    "ema": ExponentialMovingAverage,
    "macd": MACDIndicator,
    "zigzag": ZigZagIndicator,
    "stochastic": StochasticIndicator,
    "stoch": StochasticIndicator,
    "williamsr": WilliamsRIndicator,
    "atr": ATRIndicator,
    "obv": OBVIndicator,
    "bollingerbands": BollingerBandsIndicator,
    "bbands": BollingerBandsIndicator,
    "cci": CCIIndicator,
    "momentum": MomentumIndicator,
    "roc": ROCIndicator,
    "vwap": VWAPIndicator,
    "parabolicsar": ParabolicSARIndicator,
    "psar": ParabolicSARIndicator,
    "ichimoku": IchimokuIndicator,
    "rvi": RVIIndicator,
    "mfi": MFIIndicator,
    "aroon": AroonIndicator,
    "donchianchannels": DonchianChannelsIndicator,
    "keltnerchannels": KeltnerChannelsIndicator,
    "adline": ADLineIndicator,
    "cmf": CMFIndicator,
    "adx": ADXIndicator,
    "supertrend": SuperTrendIndicator,
    "fishertransform": FisherTransformIndicator,
    "bollingerbandwidth": BollingerBandWidthIndicator,
    "volumeratio": VolumeRatioIndicator,
    "squeezeintensity": SqueezeIntensityIndicator,
    "distancefromma": DistanceFromMAIndicator,
}


class IndicatorFactory:
    """
    Factory class for creating indicator instances from configuration.

    This class is responsible for instantiating technical indicators based on
    configuration settings. It supports both built-in indicators and custom
    indicators that can be imported dynamically.

    Attributes:
        config: The indicator configuration containing indicator specifications
    """

    def __init__(self, config: Union[IndicatorsConfig, list[IndicatorConfig]]):
        """
        Initialize the indicator factory with a configuration.

        Args:
            config: Either an IndicatorsConfig object or a list of IndicatorConfig objects

        Raises:
            ConfigurationError: If the configuration is invalid
        """
        if isinstance(config, list):
            self.indicators_config = IndicatorsConfig(
                indicators=config, multi_timeframe=None
            )
        elif isinstance(config, IndicatorsConfig):
            self.indicators_config = config
        else:
            raise ConfigurationError(
                message="Invalid indicator configuration type",
                error_code="CONFIG-InvalidType",
                details={
                    "expected": "IndicatorsConfig or List[IndicatorConfig]",
                    "received": type(config).__name__,
                },
            )

        logger.debug(
            f"Initialized IndicatorFactory with {len(self.indicators_config.indicators)} indicator configurations"
        )

    def build(self) -> list[BaseIndicator]:
        """
        Build and return indicator instances based on the configuration.

        Returns:
            List of initialized indicator instances

        Raises:
            ConfigurationError: If an indicator cannot be instantiated
        """
        indicator_instances = []
        errors = []

        for config in self.indicators_config.indicators:
            try:
                indicator = self._create_indicator(config)
                indicator_instances.append(indicator)
                logger.info(
                    f"Successfully created indicator: {indicator.name} ({config.type})"
                )
            except Exception as e:
                error_msg = f"Failed to create indicator {config.type}: {str(e)}"
                logger.error(error_msg)
                errors.append(
                    {
                        "type": config.type,
                        "error": str(e),
                        "config": config.model_dump(),
                    }
                )

        if errors and not indicator_instances:
            # If all indicators failed, raise an error with the first error message
            # This preserves the original error message for better error reporting
            original_error = errors[0]["error"]
            raise ConfigurationError(
                message=f"Failed to create any indicators from configuration: {original_error}",
                error_code="CONFIG-IndicatorCreationFailed",
                details={"errors": errors},
            )
        elif errors:
            # If some indicators failed but not all, log a warning
            logger.warning(
                f"Created {len(indicator_instances)} indicators, but {len(errors)} failed",
                extra={"errors": errors},
            )

        return indicator_instances

    def _create_indicator(self, config: IndicatorConfig) -> BaseIndicator:
        """
        Create a single indicator instance from its configuration.

        Args:
            config: Configuration for the indicator

        Returns:
            An initialized indicator instance

        Raises:
            ConfigurationError: If the indicator cannot be instantiated
        """
        indicator_class = self._get_indicator_class(config.type)

        try:
            # Create a copy of params to avoid modifying the original
            params = config.params.copy()

            # Custom name handling
            custom_name = None
            if config.name:
                custom_name = config.name

            # Create the indicator instance
            # Note: We can't directly pass 'name' to most indicators as they expect specific parameters
            # Instead, we'll capture the custom name and properly handle it based on indicator type
            indicator = indicator_class(**params)

            # If a custom name was specified, update the indicator's name after creation
            if custom_name:
                # Store the original name for reference in case of errors
                original_name = indicator.name
                indicator.name = custom_name
                logger.debug(f"Renamed indicator from {original_name} to {custom_name}")

            return indicator

        except Exception as e:
            raise ConfigurationError(
                message=f"Failed to initialize indicator {config.type}",
                error_code="CONFIG-IndicatorInitializationFailed",
                details={
                    "indicator_type": config.type,
                    "params": config.params,
                    "error": str(e),
                },
            ) from e

    def _get_indicator_class(self, indicator_type: str) -> type[BaseIndicator]:
        """
        Get the indicator class based on its type name.

        Args:
            indicator_type: The type name of the indicator

        Returns:
            The indicator class

        Raises:
            ConfigurationError: If the indicator type is not found
        """
        # First, check if it's a built-in indicator
        indicator_class = BUILT_IN_INDICATORS.get(indicator_type)

        if indicator_class:
            logger.debug(f"Found built-in indicator class for {indicator_type}")
            return indicator_class

        # If not built-in, try to import it dynamically
        try:
            # Try to import from ktrdr.indicators package
            module_path = f"ktrdr.indicators.{indicator_type.lower()}"
            module = importlib.import_module(module_path)

            # Look for a class with the same name as the indicator type
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseIndicator)
                    and attr.__name__ == indicator_type
                ):
                    logger.debug(
                        f"Found indicator class {attr.__name__} in module {module_path}"
                    )
                    return attr

            raise ConfigurationError(
                message=f"Could not find indicator class {indicator_type} in module {module_path}",
                error_code="CONFIG-IndicatorClassNotFound",
                details={"indicator_type": indicator_type, "module": module_path},
            )

        except ImportError as e:
            logger.error(
                f"Failed to import module for indicator {indicator_type}: {str(e)}"
            )
            raise ConfigurationError(
                message=f"Indicator type {indicator_type} not found",
                error_code="CONFIG-IndicatorTypeNotFound",
                details={"indicator_type": indicator_type, "error": str(e)},
            ) from e
