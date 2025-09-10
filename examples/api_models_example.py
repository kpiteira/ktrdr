#!/usr/bin/env python
"""
KTRDR API Models Example.

This script demonstrates how to use the KTRDR API models for creating
and validating data structures for API requests and responses.
"""

import sys
from datetime import datetime, timedelta
from pprint import pprint

# Add project root to path
sys.path.append("/Users/karl/Documents/dev/ktrdr2")

from ktrdr.api.models.base import ApiResponse
from ktrdr.api.models.data import (
    DataLoadRequest,
    OHLCVData,
    OHLCVPoint,
    SymbolInfo,
    TimeframeInfo,
)
from ktrdr.api.models.fuzzy import (
    FuzzyRule,
    FuzzySystem,
    FuzzyVariable,
    MembershipFunction,
    MembershipFunctionType,
)
from ktrdr.api.models.indicators import (
    IndicatorCalculateRequest,
    IndicatorConfig,
    IndicatorMetadata,
    IndicatorParameter,
    IndicatorType,
)


def demo_data_models():
    """Demonstrate the data models."""
    print("\n=== Data Models ===")

    # Create a data load request
    data_request = DataLoadRequest(
        symbol="AAPL",
        timeframe="1d",
        start_date=datetime.now() - timedelta(days=30),
        end_date=datetime.now(),
    )
    print("\nData Load Request:")
    pprint(data_request.model_dump())

    # Create some OHLCV points
    ohlcv_points = [
        OHLCVPoint(
            timestamp=datetime.now() - timedelta(days=i),
            open=150.0 + i,
            high=155.0 + i,
            low=148.0 + i,
            close=153.0 + i,
            volume=1000000.0 + i * 10000,
        )
        for i in range(5)
    ]

    # Create OHLCV data
    ohlcv_data = OHLCVData(
        dates=[point.timestamp.isoformat() for point in ohlcv_points],
        ohlcv=[
            [point.open, point.high, point.low, point.close, point.volume]
            for point in ohlcv_points
        ],
        metadata={"symbol": "AAPL", "timeframe": "1d"},
    )
    print("\nOHLCV Data:")
    pprint(ohlcv_data.model_dump())

    # Create ApiResponse with OHLCV data
    response = ApiResponse[OHLCVData](success=True, data=ohlcv_data)
    print("\nAPI Response with OHLCV data:")
    pprint(response.model_dump())

    # Create Symbol Info
    symbol_info = SymbolInfo(
        symbol="AAPL",
        name="Apple Inc.",
        type="stock",
        exchange="NASDAQ",
        available_timeframes=["1d", "1h", "15m"],
    )
    print("\nSymbol Info:")
    pprint(symbol_info.model_dump())

    # Create Timeframe Info
    timeframe_info = TimeframeInfo(
        id="1d", name="Daily", description="Daily price data"
    )
    print("\nTimeframe Info:")
    pprint(timeframe_info.model_dump())


def demo_indicator_models():
    """Demonstrate the indicator models."""
    print("\n=== Indicator Models ===")

    # Create indicator parameters
    period_param = IndicatorParameter(
        name="period",
        type="int",
        description="Lookback period",
        default=14,
        min_value=2,
        max_value=100,
    )
    source_param = IndicatorParameter(
        name="source",
        type="str",
        description="Price source",
        default="close",
        options=["open", "high", "low", "close"],
    )

    # Create indicator metadata
    indicator_metadata = IndicatorMetadata(
        id="rsi",
        name="Relative Strength Index",
        description="Momentum oscillator that measures the speed and change of price movements",
        type=IndicatorType.MOMENTUM,
        parameters=[period_param, source_param],
    )
    print("\nIndicator Metadata:")
    pprint(indicator_metadata.model_dump())

    # Create indicator configuration
    indicator_config = IndicatorConfig(
        id="rsi", parameters={"period": 14, "source": "close"}, output_name="RSI_14"
    )
    print("\nIndicator Config:")
    pprint(indicator_config.model_dump())

    # Create indicator calculate request
    calculate_request = IndicatorCalculateRequest(
        symbol="AAPL",
        timeframe="1d",
        indicators=[
            indicator_config,
            IndicatorConfig(id="sma", parameters={"period": 20}, output_name="SMA_20"),
        ],
        start_date="2023-01-01",
        end_date="2023-01-31",
    )
    print("\nCalculate Request:")
    pprint(calculate_request.model_dump())


def demo_fuzzy_models():
    """Demonstrate the fuzzy models."""
    print("\n=== Fuzzy Models ===")

    # Create membership functions
    membership_functions = [
        MembershipFunction(
            type=MembershipFunctionType.TRIANGULAR,
            name="low",
            parameters={"points": [0.0, 0.0, 50.0]},
        ),
        MembershipFunction(
            type=MembershipFunctionType.TRIANGULAR,
            name="medium",
            parameters={"points": [25.0, 50.0, 75.0]},
        ),
        MembershipFunction(
            type=MembershipFunctionType.TRIANGULAR,
            name="high",
            parameters={"points": [50.0, 100.0, 100.0]},
        ),
    ]
    print("\nMembership Functions:")
    pprint(membership_functions[1].model_dump())

    # Create fuzzy variables
    input_var = FuzzyVariable(
        name="rsi",
        description="RSI indicator value",
        range=[0, 100],
        membership_functions=membership_functions,
    )

    output_var = FuzzyVariable(
        name="signal",
        description="Trading signal",
        range=[-100, 100],
        membership_functions=[
            MembershipFunction(
                type=MembershipFunctionType.TRIANGULAR,
                name="sell",
                parameters={"points": [-100.0, -100.0, 0.0]},
            ),
            MembershipFunction(
                type=MembershipFunctionType.TRIANGULAR,
                name="neutral",
                parameters={"points": [-50.0, 0.0, 50.0]},
            ),
            MembershipFunction(
                type=MembershipFunctionType.TRIANGULAR,
                name="buy",
                parameters={"points": [0.0, 100.0, 100.0]},
            ),
        ],
    )
    print("\nFuzzy Variable:")
    pprint(input_var.model_dump())

    # Create fuzzy rules
    rules = [
        FuzzyRule(
            id="rule1",
            description="If RSI is low then signal is buy",
            antecedent="IF rsi IS low",
            consequent="THEN signal IS buy",
            weight=1.0,
        ),
        FuzzyRule(
            id="rule2",
            description="If RSI is medium then signal is neutral",
            antecedent="IF rsi IS medium",
            consequent="THEN signal IS neutral",
            weight=1.0,
        ),
        FuzzyRule(
            id="rule3",
            description="If RSI is high then signal is sell",
            antecedent="IF rsi IS high",
            consequent="THEN signal IS sell",
            weight=1.0,
        ),
    ]
    print("\nFuzzy Rule:")
    pprint(rules[0].model_dump())

    # Create fuzzy system
    fuzzy_system = FuzzySystem(
        name="rsi_trading_system",
        description="Trading system based on RSI",
        input_variables=[input_var],
        output_variables=[output_var],
        rules=rules,
        defuzzification_method="centroid",
    )
    print("\nFuzzy System:")
    pprint(
        fuzzy_system.model_dump(
            exclude={"input_variables", "output_variables", "rules"}
        )
    )
    print(f"Input variables: {[v.name for v in fuzzy_system.input_variables]}")
    print(f"Output variables: {[v.name for v in fuzzy_system.output_variables]}")
    print(f"Rules: {len(fuzzy_system.rules)}")


def main():
    """Main function to demonstrate API models."""
    print("KTRDR API Models Example")
    print("=======================")

    # Demonstrate data models
    demo_data_models()

    # Demonstrate indicator models
    demo_indicator_models()

    # Demonstrate fuzzy models
    demo_fuzzy_models()


if __name__ == "__main__":
    main()
