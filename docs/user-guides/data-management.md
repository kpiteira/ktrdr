# Data Management Guide

This guide explains how to work with market data in KTRDR, including loading, managing, and preprocessing financial data for analysis and trading.

## Overview

KTRDR provides a comprehensive data management system that allows you to:

- Fetch historical price data from various sources
- Store and cache data locally for fast access
- Repair and preprocess data for analysis
- Manage multiple data formats and timeframes

## Data Sources

KTRDR supports the following data sources:

### Interactive Brokers

KTRDR can fetch data directly from Interactive Brokers via the IB Gateway or TWS (Trader Workstation). This requires:

- An active Interactive Brokers account
- IB Gateway or TWS running on your machine
- Proper configuration in KTRDR settings

### Local CSV Files

KTRDR can load data from local CSV files in the standard OHLCV (Open, High, Low, Close, Volume) format.

### Data Caching

To optimize performance and reduce external API calls, KTRDR automatically caches data:

- Downloaded data is stored in CSV format in the `data/` directory
- Each instrument has separate files for different timeframes (e.g., `data/AAPL_1d.csv`)
- KTRDR intelligently merges new data with existing cached data

## Loading Data

You can load data using either the Python API or the command-line interface.

### Using the Python API

```python
from ktrdr.data import DataManager

# Initialize the DataManager
data_manager = DataManager()

# Load daily data for AAPL
df = data_manager.load(
    symbol="AAPL",
    interval="1d",
    start="2023-01-01",
    end="2023-12-31"
)

# Print the first few rows
print(df.head())
```

### Using the CLI

```bash
# Fetch daily data for AAPL for the last year
ktrdr fetch AAPL --timeframe 1d

# Fetch data for a specific date range
ktrdr fetch MSFT --timeframe 1d --start 2023-01-01 --end 2023-12-31

# Fetch data and force download from Interactive Brokers
ktrdr fetch EURUSD --source ib --force-download
```

## Data Structure

KTRDR uses pandas DataFrames for data manipulation. The standard OHLCV DataFrame has:

- DatetimeIndex with timezone-aware timestamps
- Columns: `open`, `high`, `low`, `close`, `volume`

Example:

```
                     open    high     low   close    volume
timestamp                                                  
2023-01-03 00:00:00  130.28  130.90  124.17  125.07  112117500
2023-01-04 00:00:00  126.89  128.66  125.08  126.36   89113600
2023-01-05 00:00:00  127.13  127.77  124.76  125.02   70892900
```

## Data Repair and Preprocessing

KTRDR provides tools for data cleaning and preprocessing:

### Handling Missing Data

```python
from ktrdr.data import DataManager, DataRepair

# Load data with potential gaps
df = data_manager.load("AAPL", interval="1d")

# Repair missing data
repair = DataRepair()
df_repaired = repair.fill_gaps(df)

# Or with the CLI
# ktrdr repair AAPL --timeframe 1d --method forward-fill
```

### Available Repair Methods

| Method | Description |
|--------|-------------|
| `forward-fill` | Fill missing values with the last known values |
| `backward-fill` | Fill missing values with the next known values |
| `interpolate` | Linear interpolation between known points |
| `zero` | Fill missing values with zeros |
| `none` | Don't fill missing values (keep NaN) |

### Detecting Data Gaps

```python
from ktrdr.data import DataAnalyzer

analyzer = DataAnalyzer()
gaps = analyzer.find_gaps(df)

if gaps:
    print(f"Found {len(gaps)} gaps in the data:")
    for gap in gaps:
        print(f"Gap from {gap.start} to {gap.end} ({gap.size} points)")
```

## Advanced Usage

### Custom Data Sources

You can implement custom data sources by extending the `DataSource` base class:

```python
from ktrdr.data import DataSource

class MyCustomDataSource(DataSource):
    def __init__(self, api_key=None):
        self.api_key = api_key
        
    def fetch(self, symbol, interval, start, end):
        # Implement your custom fetching logic
        # ...
        return df  # Return a pandas DataFrame
```

### Working with Multiple Timeframes

You can easily convert between timeframes:

```python
from ktrdr.data import TimeframeConverter

# Load minute data
df_1m = data_manager.load("EURUSD", interval="1m")

# Convert to hourly data
converter = TimeframeConverter()
df_1h = converter.convert(df_1m, target_interval="1h")
```

### Saving and Exporting Data

```python
# Save to CSV
df.to_csv("my_data.csv")

# Export to Excel
df.to_excel("my_data.xlsx")

# Export to JSON
df.to_json("my_data.json", orient="records")
```

## Best Practices

1. **Use Local Caching**: Let KTRDR handle data caching to minimize redundant downloads.

2. **Validate Data Quality**: Always check for gaps and anomalies in your data using `DataAnalyzer`.

3. **Proper Date Handling**: Use timezone-aware timestamps when working with international markets.

4. **Memory Management**: For very large datasets, consider loading smaller chunks or using lower resolution timeframes.

5. **Regular Updates**: Set up a schedule to regularly update your cached data for active instruments.

## Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| "Connection failed" | Could not connect to Interactive Brokers | Check IB TWS/Gateway is running and API connections are allowed |
| "Symbol not found" | The requested symbol doesn't exist | Check symbol spelling and availability in your data subscription |
| "No data available" | No data for the specified date range | Try a different date range or check if the symbol was trading then |
| "Data inconsistency" | Gaps or outliers in the data | Use the repair tools to clean the data |

## Related Documentation

- [API Reference: Data API](../api-reference/data-api.md)
- [CLI Reference: Data Commands](../cli/data-commands.md)
- [Configuration: Data Sources](../configuration/data-sources.md)