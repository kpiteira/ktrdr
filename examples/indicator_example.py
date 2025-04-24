#!/usr/bin/env python
"""
Example demonstrating the use of the BaseIndicator abstract class.

This script shows how to create a concrete indicator class (SimpleMovingAverage)
by extending the BaseIndicator abstract class, and demonstrates how to use it
to calculate indicator values from sample data.
"""

import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Add the project root to sys.path to allow importing ktrdr modules
sys.path.append(str(Path(__file__).parent.parent))

from ktrdr.indicators import BaseIndicator
from ktrdr.errors import DataError


class SimpleMovingAverage(BaseIndicator):
    """
    A simple moving average (SMA) indicator implementation.
    
    This class demonstrates how to implement a concrete indicator by
    extending the BaseIndicator abstract class.
    """
    
    def __init__(self, period=14, source='close'):
        """
        Initialize a Simple Moving Average indicator.
        
        Args:
            period (int): The period (window size) for the moving average
            source (str): The column name to use as input data
        """
        super().__init__(name="SMA", period=period, source=source)
    
    def _validate_params(self, params):
        """
        Validate the parameters for the SMA indicator.
        
        Args:
            params (dict): Parameters to validate
            
        Returns:
            dict: Validated parameters
            
        Raises:
            DataError: If period is less than 2
        """
        # Add custom validation logic
        if 'period' in params and params['period'] < 2:
            raise DataError(
                message="Period must be at least 2 for SMA calculation",
                error_code="DATA-InvalidPeriod",
                details={"parameter": "period", "value": params['period'], "min_allowed": 2}
            )
        return params
    
    def compute(self, df):
        """
        Compute the Simple Moving Average for the given DataFrame.
        
        Args:
            df (pd.DataFrame): DataFrame containing data to compute SMA for
            
        Returns:
            pd.Series: Series containing the computed SMA values
            
        Raises:
            DataError: If the input data is invalid or insufficient
        """
        # Validate input data
        self.validate_input_data(df, [self.params['source']])
        self.validate_sufficient_data(df, self.params['period'])
        
        # Compute the SMA
        return df[self.params['source']].rolling(
            window=self.params['period']
        ).mean().rename(self.get_column_name())


def create_sample_data(n_points=100):
    """Create sample price data with a trend and noise."""
    # Create date index
    dates = pd.date_range(start='2023-01-01', periods=n_points)
    
    # Create price data with trend and noise
    trend = np.linspace(100, 150, n_points)
    noise = np.random.normal(0, 5, n_points)
    prices = trend + noise
    
    # Create DataFrame
    df = pd.DataFrame({
        'open': prices - np.random.normal(0, 1, n_points),
        'high': prices + np.random.normal(2, 1, n_points),
        'low': prices - np.random.normal(2, 1, n_points),
        'close': prices,
        'volume': np.random.normal(1000000, 200000, n_points)
    }, index=dates)
    
    return df


def main():
    """Run the indicator example with sample data."""
    try:
        # Create sample data
        print("Creating sample price data...")
        df = create_sample_data(100)
        print(f"Sample data shape: {df.shape}")
        print(df.head())
        
        # Create indicators with different periods
        print("\nCreating SMA indicators with different periods...")
        sma_short = SimpleMovingAverage(period=5)
        sma_medium = SimpleMovingAverage(period=20)
        sma_long = SimpleMovingAverage(period=50)
        
        # Compute indicators
        print("Computing indicator values...")
        df[sma_short.get_column_name()] = sma_short.compute(df)
        df[sma_medium.get_column_name()] = sma_medium.compute(df)
        df[sma_long.get_column_name()] = sma_long.compute(df)
        
        # Show results
        print("\nDataFrame with indicators:")
        print(df.tail())
        
        # Demonstrate error handling with invalid parameters
        try:
            print("\nTesting error handling with invalid parameter...")
            invalid_sma = SimpleMovingAverage(period=1)
        except DataError as e:
            print(f"Successfully caught error: {e}")
            print(f"Error code: {e.error_code}")
            print(f"Error details: {e.details}")
        
        # Demonstrate error handling with insufficient data
        try:
            print("\nTesting error handling with insufficient data...")
            small_df = df.iloc[:3]  # Only 3 rows
            sma_big = SimpleMovingAverage(period=10)
            sma_big.compute(small_df)
        except DataError as e:
            print(f"Successfully caught error: {e}")
            print(f"Error code: {e.error_code}")
            print(f"Error details: {e.details}")
        
        # Optionally plot the data if matplotlib is available
        try:
            # Plot results
            print("\nPlotting results...")
            plt.figure(figsize=(12, 6))
            plt.plot(df.index, df['close'], label='Close Price', color='black', alpha=0.5)
            plt.plot(df.index, df[sma_short.get_column_name()], label=f'SMA({sma_short.params["period"]})')
            plt.plot(df.index, df[sma_medium.get_column_name()], label=f'SMA({sma_medium.params["period"]})')
            plt.plot(df.index, df[sma_long.get_column_name()], label=f'SMA({sma_long.params["period"]})')
            plt.title('Simple Moving Average Indicator Example')
            plt.xlabel('Date')
            plt.ylabel('Price')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            # Save the plot
            output_path = Path(__file__).parent / "sma_example.png"
            plt.savefig(output_path)
            print(f"Plot saved to: {output_path}")
            plt.close()
        except ImportError:
            print("\nMatplotlib not found. Skipping plot generation.")
            print("To install matplotlib, run: uv pip install matplotlib")
        
        print("\nExample completed successfully!")
        
    except Exception as e:
        print(f"Error running example: {e}")
        raise


if __name__ == "__main__":
    main()