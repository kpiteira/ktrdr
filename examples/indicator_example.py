#!/usr/bin/env python
"""
Example demonstrating the use of technical indicators in ktrdr.

This script shows how to use the implemented technical indicators
(SMA, EMA, RSI) to analyze price data, and demonstrates proper error
handling and visualization.
"""

import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Add the project root to sys.path to allow importing ktrdr modules
sys.path.append(str(Path(__file__).parent.parent))

from ktrdr.indicators import SimpleMovingAverage, ExponentialMovingAverage, RSIIndicator
from ktrdr.errors import DataError
from ktrdr import get_logger

# Set up logger
logger = get_logger(__name__)


def create_sample_data(n_points=100):
    """Create sample price data with a trend, cycle, and noise."""
    # Create date index
    dates = pd.date_range(start="2023-01-01", periods=n_points)

    # Create price data with trend, cycle and noise
    trend = np.linspace(100, 150, n_points)
    cycle = 10 * np.sin(np.linspace(0, 4 * np.pi, n_points))
    noise = np.random.normal(0, 5, n_points)
    prices = trend + cycle + noise

    # Create DataFrame
    df = pd.DataFrame(
        {
            "open": prices - np.random.normal(0, 1, n_points),
            "high": prices + np.random.normal(2, 1, n_points),
            "low": prices - np.random.normal(2, 1, n_points),
            "close": prices,
            "volume": np.random.normal(1000000, 200000, n_points),
        },
        index=dates,
    )

    return df


def main():
    """Run the indicator example with sample data."""
    try:
        # Create sample data
        logger.info("Creating sample price data...")
        df = create_sample_data(100)
        print(f"Sample data shape: {df.shape}")
        print(df.head())

        # Create indicators
        logger.info("Creating technical indicators...")
        sma_short = SimpleMovingAverage(period=10)
        sma_long = SimpleMovingAverage(period=30)
        ema_short = ExponentialMovingAverage(period=10)
        ema_long = ExponentialMovingAverage(period=30)
        rsi = RSIIndicator(period=14)

        # Compute indicators
        logger.info("Computing indicator values...")
        df[sma_short.get_column_name()] = sma_short.compute(df)
        df[sma_long.get_column_name()] = sma_long.compute(df)
        df[ema_short.get_column_name()] = ema_short.compute(df)
        df[ema_long.get_column_name()] = ema_long.compute(df)
        df[rsi.get_column_name()] = rsi.compute(df)

        # Show results
        print("\nDataFrame with indicators:")
        print(df.tail())

        # Demonstrate error handling with invalid parameters
        try:
            print("\nTesting error handling with invalid parameter...")
            invalid_rsi = RSIIndicator(period=1)
        except DataError as e:
            print(f"Successfully caught error: {e}")
            print(f"Error code: {e.error_code}")
            print(f"Error details: {e.details}")

        # Demonstrate error handling with insufficient data
        try:
            print("\nTesting error handling with insufficient data...")
            small_df = df.iloc[:5]  # Only 5 rows
            rsi_test = RSIIndicator(period=14)
            rsi_test.compute(small_df)
        except DataError as e:
            print(f"Successfully caught error: {e}")
            print(f"Error code: {e.error_code}")
            print(f"Error details: {e.details}")

        # Optionally plot the data with matplotlib
        try:
            # Create subplots for price with MAs and RSI
            fig, (ax1, ax2) = plt.subplots(
                2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [2, 1]}
            )

            # Plot price and moving averages
            ax1.plot(
                df.index, df["close"], label="Close Price", color="black", alpha=0.5
            )
            ax1.plot(
                df.index,
                df[sma_short.get_column_name()],
                label=f'SMA({sma_short.params["period"]})',
                color="blue",
            )
            ax1.plot(
                df.index,
                df[sma_long.get_column_name()],
                label=f'SMA({sma_long.params["period"]})',
                color="green",
            )
            ax1.plot(
                df.index,
                df[ema_short.get_column_name()],
                label=f'EMA({ema_short.params["period"]})',
                color="red",
                linestyle="--",
            )
            ax1.plot(
                df.index,
                df[ema_long.get_column_name()],
                label=f'EMA({ema_long.params["period"]})',
                color="purple",
                linestyle="--",
            )
            ax1.set_title("Price with Moving Averages")
            ax1.set_ylabel("Price")
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # Plot RSI
            ax2.plot(
                df.index,
                df[rsi.get_column_name()],
                label=f'RSI({rsi.params["period"]})',
                color="orange",
            )
            ax2.axhline(y=70, color="r", linestyle="--", alpha=0.3)
            ax2.axhline(y=30, color="g", linestyle="--", alpha=0.3)
            ax2.set_title("Relative Strength Index (RSI)")
            ax2.set_ylabel("RSI")
            ax2.set_ylim(0, 100)
            ax2.grid(True, alpha=0.3)
            ax2.legend()

            plt.tight_layout()

            # Save the plot
            output_path = Path(__file__).parent / "indicators_example.png"
            plt.savefig(output_path)
            print(f"Plot saved to: {output_path}")
            plt.close()
        except ImportError:
            print("\nMatplotlib not found. Skipping plot generation.")
            print("To install matplotlib, run: uv pip install matplotlib")

        print("\nExample completed successfully!")

    except Exception as e:
        logger.error(f"Error running example: {e}", exc_info=True)
        print(f"Error running example: {e}")
        raise


if __name__ == "__main__":
    main()
