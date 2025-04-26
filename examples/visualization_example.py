"""
Visualization Framework Example

This example demonstrates how to use the visualization framework to create
interactive financial charts using TradingView's lightweight-charts library.
"""

import os
import pandas as pd
from pathlib import Path
import numpy as np

from ktrdr.visualization.data_adapter import DataAdapter
from ktrdr.visualization.config_builder import ConfigBuilder
from ktrdr.visualization.template_manager import TemplateManager
from ktrdr.visualization.renderer import Renderer


def load_sample_data():
    """Load sample OHLCV data from the data directory."""
    # Using MSFT_1h.csv instead of AAPL_1d.csv
    data_path = Path(__file__).parents[1] / "data" / "MSFT_1h.csv"
    
    if not data_path.exists():
        print(f"Sample data not found at: {data_path}")
        print("Using generated sample data instead...")
        
        # Generate sample data if file doesn't exist
        dates = pd.date_range(start="2025-01-01", periods=100, freq="H")
        base_price = 300.0
        
        # Generate price data with some randomness but trending upward
        np.random.seed(42)  # For reproducibility
        
        hourly_returns = np.random.normal(0.0001, 0.003, len(dates))
        cumulative_returns = np.cumprod(1 + hourly_returns)
        
        closes = base_price * cumulative_returns
        opens = closes * (1 + np.random.normal(0, 0.001, len(dates)))
        highs = np.maximum(opens, closes) * (1 + np.abs(np.random.normal(0, 0.002, len(dates))))
        lows = np.minimum(opens, closes) * (1 - np.abs(np.random.normal(0, 0.002, len(dates))))
        volumes = np.random.normal(500000, 100000, len(dates))
        
        df = pd.DataFrame({
            'date': dates,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        })
        
        return df
    
    # Load the actual CSV file
    df = pd.read_csv(data_path, parse_dates=['date'])
    print(f"Loaded {len(df)} rows from MSFT hourly data")
    
    # Filter to only keep 2025 data
    df = df[df['date'].dt.year == 2025]
    print(f"Filtered to {len(df)} rows from 2025")
    
    return df


def create_basic_chart():
    """Create a basic price chart with volume panel."""
    # Load data
    df = load_sample_data()
    print(f"Loaded {len(df)} data points")
    
    # Create renderer instance
    renderer = Renderer()
    
    # Transform data for the charts
    ohlc_data = DataAdapter.transform_ohlc(df)
    volume_data = DataAdapter.transform_histogram(
        df, 
        time_column='date', 
        value_column='volume',
        positive_color="#26a69a",
        negative_color="#ef5350"
    )
    
    # Calculate SMA 20
    df['sma20'] = df['close'].rolling(window=20).mean()
    sma_data = DataAdapter.transform_line(df, time_column='date', value_column='sma20')
    
    # Create chart configs
    price_chart_options = ConfigBuilder.create_price_chart_options(height=400)
    volume_chart_options = ConfigBuilder.create_indicator_chart_options(height=150)
    
    # Create series options for price chart and SMA
    price_series_options = ConfigBuilder.create_series_options(series_type='candlestick')
    sma_series_options = ConfigBuilder.create_series_options(
        series_type='line', 
        color='#2962FF', 
        line_width=1.5, 
        title='SMA 20'
    )
    volume_series_options = ConfigBuilder.create_series_options(series_type='histogram')
    
    # Define chart configurations with synchronization and proper structure
    chart_configs = [
        {
            "id": "price_chart",
            "type": "price",
            "title": "Price Chart",
            "height": 400,
            "options": price_chart_options,
            "series_options": price_series_options,
            "overlay_series": [
                {
                    "id": "sma20_series",
                    "type": "line",
                    "options": sma_series_options
                }
            ]
        },
        {
            "id": "volume_chart",
            "type": "histogram",
            "title": "Volume",
            "height": 150,
            "options": volume_chart_options,
            "series_options": volume_series_options,
            "sync": {"target": "price_chart"}  # Sync with the price chart
        }
    ]
    
    # Prepare data for the charts
    chart_data = {
        "price_chart": ohlc_data,
        "sma20_series": sma_data,
        "volume_chart": volume_data
    }
    
    # Create and save the chart
    title = "MSFT Hourly Chart - KTRDR Visualization Example"
    
    # Save the chart to the output directory instead of examples
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    output_path = os.path.join(output_dir, "visualization_example.html")
    
    # Render the chart with all components
    html_content = renderer.render_chart(
        title=title,
        chart_configs=chart_configs,
        chart_data=chart_data,
        theme="dark"
    )
    
    # Save the chart to a file
    renderer.save_chart(html_content, output_path, overwrite=True)
    print(f"Chart saved to: {output_path}")
    
    return output_path


def create_multi_panel_chart():
    """Create a multi-panel chart with price, volume, and indicators."""
    # Load data
    df = load_sample_data()
    
    # Create renderer instance
    renderer = Renderer()
    
    # Transform price and volume data
    ohlc_data = DataAdapter.transform_ohlc(df)
    
    # Create volume data with appropriate colors based on price movement
    df['price_up'] = df['close'] >= df['open']
    volume_data = DataAdapter.transform_histogram(
        df, 
        time_column='date', 
        value_column='volume',
        color_column='price_up',
        positive_color="#26a69a",  # Green for up days
        negative_color="#ef5350"   # Red for down days
    )
    
    # Calculate SMA and EMA for price chart
    df['sma20'] = df['close'].rolling(window=20).mean()
    df['ema10'] = df['close'].ewm(span=10, adjust=False).mean()
    
    sma_data = DataAdapter.transform_line(df, time_column='date', value_column='sma20')
    ema_data = DataAdapter.transform_line(df, time_column='date', value_column='ema10')
    
    # Calculate RSI for separate panel
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Fill NaN values for better visualization
    df['rsi'] = df['rsi'].fillna(50)  # Fill NaNs with neutral RSI value
    
    rsi_data = DataAdapter.transform_line(df, time_column='date', value_column='rsi')
    
    # Create chart configurations
    price_chart_options = ConfigBuilder.create_price_chart_options(height=400)
    volume_chart_options = ConfigBuilder.create_indicator_chart_options(height=150)
    rsi_chart_options = ConfigBuilder.create_indicator_chart_options(height=150)
    
    # Create a range slider configuration
    range_slider_options = ConfigBuilder.create_indicator_chart_options(
        height=60, 
        visible_time_scale=True,
        handle_scale=True,
        handle_scroll=True
    )
    
    # Create series options
    price_series_options = ConfigBuilder.create_series_options(series_type='candlestick')
    sma_series_options = ConfigBuilder.create_series_options(
        series_type='line', 
        color='#2962FF',  # Blue
        line_width=1.5, 
        title='SMA 20'
    )
    ema_series_options = ConfigBuilder.create_series_options(
        series_type='line', 
        color='#FF6D00',  # Orange
        line_width=1.5, 
        title='EMA 10'
    )
    volume_series_options = ConfigBuilder.create_series_options(
        series_type='histogram',
        color='#26a69a'  # Default color (will be overridden by data)
    )
    rsi_series_options = ConfigBuilder.create_series_options(
        series_type='line', 
        color='#9C27B0',  # Purple
        line_width=1.5,
        title='RSI 14'
    )
    range_slider_series_options = ConfigBuilder.create_series_options(
        series_type='area',
        color='#2962FF80',  # Semi-transparent blue
        line_width=1
    )
    
    # Define chart configurations with synchronization
    chart_configs = [
        {
            "id": "price_chart",
            "type": "price",
            "title": "Price Chart with Moving Averages",
            "height": 400,
            "options": price_chart_options,
            "series_options": price_series_options,
            "overlay_series": [
                {
                    "id": "sma20_series",
                    "type": "line",
                    "options": sma_series_options
                },
                {
                    "id": "ema10_series",
                    "type": "line",
                    "options": ema_series_options
                }
            ]
        },
        {
            "id": "volume_chart",
            "type": "histogram",
            "title": "Volume",
            "height": 150,
            "options": volume_chart_options,
            "series_options": volume_series_options,
            "sync": {"target": "price_chart"}
        },
        {
            "id": "rsi_chart",
            "type": "indicator",
            "title": "RSI (14)",
            "height": 150,
            "options": rsi_chart_options,
            "series_options": rsi_series_options,
            "sync": {"target": "price_chart"}
        },
        {
            "id": "range_slider",
            "type": "range",
            "title": "Range Selector",
            "height": 60,
            "options": range_slider_options,
            "series_options": range_slider_series_options,
            "is_range_slider": True,
            "sync": {"target": "price_chart", "mode": "range"}
        }
    ]
    
    # Prepare data for the charts
    chart_data = {
        "price_chart": ohlc_data,
        "sma20_series": sma_data,
        "ema10_series": ema_data,
        "volume_chart": volume_data,
        "rsi_chart": rsi_data,
        "range_slider": ohlc_data  # Use price data for the range slider
    }
    
    # Create and save the chart
    title = "MSFT Hourly - KTRDR Multi-Panel Chart Example"
    
    # Save the chart to the output directory instead of examples
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    output_path = os.path.join(output_dir, "visualization_multi_panel_example.html")
    
    # Render the chart with proper sync between all panels
    html_content = renderer.render_chart(
        title=title,
        chart_configs=chart_configs,
        chart_data=chart_data,
        theme="dark",
        has_range_slider=True  # Tell the renderer this chart has a range slider
    )
    
    # Save the chart to a file
    renderer.save_chart(html_content, output_path, overwrite=True)
    print(f"Multi-panel chart saved to: {output_path}")
    
    return output_path


if __name__ == "__main__":
    print("KTRDR Visualization Framework Example")
    print("-" * 40)
    
    # Create basic chart
    basic_chart_path = create_basic_chart()
    
    print("\nCreating multi-panel chart...")
    multi_panel_chart_path = create_multi_panel_chart()
    
    print("\nExamples created successfully!")
    print(f"1. Basic Chart: {basic_chart_path}")
    print(f"2. Multi-Panel Chart: {multi_panel_chart_path}")
    
    print("\nOpen these HTML files in your browser to view the interactive charts.")