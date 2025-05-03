# `fetch` - Fetch Historical Price Data

## Synopsis

```
ktrdr fetch <symbol> [options]
```

## Description

The `fetch` command retrieves historical price data for a specified financial instrument (symbol) from various data sources. It handles downloading, processing, and storing the data in a format that can be used by other KTRDR commands.

The command intelligently manages data sources, prioritizing cached data when available and only fetching missing data points from external sources when necessary. All fetched data is stored locally for future use.

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `symbol` | Yes | The trading symbol (e.g., "AAPL", "MSFT", "EURUSD") |

## Options

| Option | Shorthand | Default | Description |
|--------|-----------|---------|-------------|
| `--timeframe` | `-t` | `1d` | Data timeframe (e.g., "1m", "5m", "1h", "1d") |
| `--start` | `-s` | 1 year ago | Start date for the data (format: YYYY-MM-DD) |
| `--end` | `-e` | today | End date for the data (format: YYYY-MM-DD) |
| `--source` | | `auto` | Data source: "ib" (Interactive Brokers), "local", or "auto" |
| `--force-download` | `-f` | `False` | Force download even if data exists locally |
| `--output` | `-o` | | Save output to specified CSV file (optional) |
| `--help` | `-h` | | Display help for the command |

## Examples

### Basic Usage

```bash
ktrdr fetch AAPL
```

This fetches daily AAPL data for the last year up to today.

### With Specific Timeframe and Date Range

```bash
ktrdr fetch MSFT --timeframe 1h --start 2023-01-01 --end 2023-03-31
```

This fetches hourly MSFT data from January 1, 2023, to March 31, 2023.

### Force Download from Interactive Brokers

```bash
ktrdr fetch EURUSD --source ib --force-download
```

This forces a data download from Interactive Brokers even if the data exists locally.

### Save to Custom Output File

```bash
ktrdr fetch AAPL --output custom_data/aapl_special.csv
```

This fetches AAPL data and saves it to the specified file path.

## Output

When successful, the command displays a summary of the fetched data:

```
Successfully fetched data for AAPL (1d)
- Start date: 2022-05-01
- End date: 2023-05-01
- Data points: 252
- Source: Interactive Brokers
- Saved to: data/AAPL_1d.csv
```

## Error Handling

Common errors and how to resolve them:

| Error Message | Cause | Solution |
|---------------|-------|----------|
| "Connection failed" | Could not connect to Interactive Brokers | Check IB TWS/Gateway is running and API connections are allowed |
| "Symbol not found" | The requested symbol doesn't exist | Check symbol spelling and availability in your data subscription |
| "No data available" | No data for the specified date range | Try a different date range or check if the symbol was trading then |
| "Permission denied" | Insufficient permissions to write data | Check file system permissions for the data directory |

## Related Commands

- [`list-data`](./list-data.md): View available data files
- [`calculate`](./calculate.md): Calculate indicators using fetched data
- [`plot`](./plot.md): Visualize the fetched data

## Notes

- Data is cached locally in the `data/` directory for future use
- Incremental fetches only download missing data to optimize performance
- The command automatically handles different asset types (stocks, forex, futures)
- For Interactive Brokers data source, make sure TWS or IB Gateway is running