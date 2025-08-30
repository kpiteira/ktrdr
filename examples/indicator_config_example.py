#!/usr/bin/env python
"""
Example script demonstrating the Indicator Configuration Framework.

This script shows how to:
1. Load indicator configurations from a YAML file
2. Create indicator instances using the IndicatorFactory
3. Apply the indicators to price data
4. Display the results

Run with:
    python examples/indicator_config_example.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from ktrdr import get_logger
from ktrdr.config.models import IndicatorsConfig
from ktrdr.indicators import IndicatorFactory

# Set up logger
logger = get_logger(__name__)


def create_sample_data(n_points: int = 100) -> pd.DataFrame:
    """
    Create sample price data for demonstration.

    Args:
        n_points (int): Number of data points to create

    Returns:
        pd.DataFrame: DataFrame with sample OHLCV data
    """
    # Set random seed for reproducibility
    np.random.seed(42)

    # Create date range
    dates = pd.date_range("2023-01-01", periods=n_points, freq="D")

    # Create price series with some randomness and trend
    close = 100 + np.cumsum(np.random.normal(0.05, 1, n_points))
    # Add a sine wave pattern
    close += 10 * np.sin(np.linspace(0, 4 * np.pi, n_points))

    # Create OHLCV data
    high = close + np.random.uniform(0, 3, n_points)
    low = close - np.random.uniform(0, 3, n_points)
    open_price = low + np.random.uniform(0, high - low, n_points)
    volume = np.random.uniform(100000, 1000000, n_points)

    # Create DataFrame
    df = pd.DataFrame(
        {
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )

    return df


def load_indicators_from_file(file_path: str) -> list:
    """
    Load indicator configurations from a YAML file and create instances.

    Args:
        file_path (str): Path to the YAML file with indicator configurations

    Returns:
        list: List of instantiated indicators
    """
    logger.info(f"Loading indicator configurations from {file_path}")

    try:
        # Load the YAML file
        with open(file_path) as f:
            config_data = yaml.safe_load(f)

        # Create IndicatorsConfig from the loaded data
        indicators_config = IndicatorsConfig(**config_data)

        # Create indicator instances using IndicatorFactory
        factory = IndicatorFactory(indicators_config)
        indicators = factory.build()

        logger.info(f"Successfully created {len(indicators)} indicators")
        return indicators

    except Exception as e:
        logger.error(f"Failed to load indicator configurations: {str(e)}")
        raise


def main():
    """Run the indicator configuration example."""
    try:
        # Get the path to the indicators.yaml file
        config_dir = Path(__file__).parents[1] / "config"
        indicators_file = config_dir / "indicators.yaml"

        if not indicators_file.exists():
            logger.error(f"Indicators file not found at {indicators_file}")
            return

        # Create sample data
        logger.info("Creating sample price data...")
        df = create_sample_data(200)
        print(f"Sample data shape: {df.shape}")
        print(df.head())

        # Load indicators from configuration
        logger.info("Loading indicators from configuration...")
        indicators = load_indicators_from_file(indicators_file)

        # Display loaded indicators
        print("\nLoaded indicators:")
        for i, indicator in enumerate(indicators, 1):
            print(f"{i}. {indicator.name} with params: {indicator.params}")

        # Compute indicators on sample data
        logger.info("Computing indicator values...")
        for indicator in indicators:
            df[indicator.get_column_name()] = indicator.compute(df)

        print("\nDataFrame with indicators:")
        print(df.tail())

        # Plot the results
        try:
            logger.info("Creating plots...")
            # Split indicators into price-based and oscillator-based types
            price_indicators = [ind for ind in indicators if ind.name in ["SMA", "EMA"]]
            oscillator_indicators = [ind for ind in indicators if ind.name == "RSI"]

            # Create subplots according to the indicators we have
            n_subplots = 1 + (len(oscillator_indicators) > 0)
            fig, axes = plt.subplots(
                n_subplots,
                1,
                figsize=(12, 8 * n_subplots),
                gridspec_kw={"height_ratios": [2, 1] if n_subplots > 1 else [1]},
            )

            if n_subplots == 1:
                axes = [axes]

            # Plot price and price-based indicators
            ax1 = axes[0]
            ax1.plot(
                df.index, df["close"], label="Close Price", color="black", alpha=0.5
            )

            for indicator in price_indicators:
                column_name = indicator.get_column_name()
                ax1.plot(df.index, df[column_name], label=column_name, alpha=0.8)

            ax1.set_title("Price with Moving Averages")
            ax1.set_ylabel("Price")
            ax1.legend(loc="best")
            ax1.grid(True, alpha=0.3)

            # Plot oscillator indicators if any
            if len(oscillator_indicators) > 0:
                ax2 = axes[1]
                for indicator in oscillator_indicators:
                    column_name = indicator.get_column_name()
                    ax2.plot(df.index, df[column_name], label=column_name, alpha=0.8)

                # Add reference lines for RSI
                if any(ind.name == "RSI" for ind in oscillator_indicators):
                    ax2.axhline(y=70, color="r", linestyle="--", alpha=0.3)
                    ax2.axhline(y=30, color="g", linestyle="--", alpha=0.3)
                    ax2.set_ylim(0, 100)

                ax2.set_title("Oscillator Indicators")
                ax2.legend(loc="best")
                ax2.grid(True, alpha=0.3)

            plt.tight_layout()

            # Save figure to examples directory
            output_path = Path(__file__).parent / "indicators_config_example.png"
            plt.savefig(output_path)
            logger.info(f"Plot saved to {output_path}")

            # Show plot
            plt.show()

        except Exception as e:
            logger.error(f"Error creating plot: {str(e)}")

    except Exception as e:
        logger.error(f"Error in example script: {str(e)}")


if __name__ == "__main__":
    main()
