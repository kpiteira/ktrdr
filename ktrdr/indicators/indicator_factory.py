"""
Registry of built-in indicators.

This module provides the BUILT_IN_INDICATORS registry mapping indicator type
names to their implementation classes.
"""

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
