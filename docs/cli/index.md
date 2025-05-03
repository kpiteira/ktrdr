# KTRDR Command Line Interface (CLI)

The KTRDR Command Line Interface (CLI) provides a powerful way to interact with the KTRDR trading system from the terminal. This guide covers the available commands, options, and usage patterns.

## Installation

The KTRDR CLI is automatically installed when you install the KTRDR package. If you've followed the [installation guide](../getting-started/installation.md), you should already have access to it.

## Basic Usage

The basic syntax for KTRDR commands is:

```bash
ktrdr [command] [options]
```

For example:

```bash
ktrdr fetch AAPL --timeframe 1d --start 2023-01-01
```

## Getting Help

To see a list of available commands:

```bash
ktrdr --help
```

To get help for a specific command:

```bash
ktrdr [command] --help
```

For example:

```bash
ktrdr fetch --help
```

## Command Categories

The KTRDR CLI is organized into several categories of commands:

### Data Commands

Commands for retrieving, managing, and analyzing financial data:

- [`fetch`](data-commands.md#fetch): Fetch historical market data
- [`repair`](data-commands.md#repair): Repair and preprocess market data
- [`info`](data-commands.md#info): Display information about available data
- [`export`](data-commands.md#export): Export data to various formats
- [`convert`](data-commands.md#convert): Convert data between timeframes

### Indicator Commands

Commands for calculating and visualizing technical indicators:

- [`calculate`](indicator-commands.md#calculate): Calculate technical indicators
- [`indicators`](indicator-commands.md#indicators): List available indicators
- [`indicator-info`](indicator-commands.md#indicator-info): Display detailed information about an indicator

### Visualization Commands

Commands for creating charts and visual analysis:

- [`plot`](visualization-commands.md#plot): Create price charts
- [`plot-indicator`](visualization-commands.md#plot-indicator): Plot indicators on price charts
- [`plot-fuzzy`](visualization-commands.md#plot-fuzzy): Visualize fuzzy logic sets
- [`export-chart`](visualization-commands.md#export-chart): Export charts to various formats

### Strategy Commands

Commands for working with trading strategies:

- [`create-strategy`](strategy-commands.md#create-strategy): Create a new strategy configuration
- [`backtest`](strategy-commands.md#backtest): Run a backtest with a strategy
- [`optimize`](strategy-commands.md#optimize): Optimize strategy parameters
- [`evaluate`](strategy-commands.md#evaluate): Evaluate a strategy's performance

## Global Options

These options can be used with any command:

| Option | Description |
|--------|-------------|
| `--verbose, -v` | Increase output verbosity |
| `--quiet, -q` | Suppress non-error output |
| `--config FILE` | Use a specific configuration file |
| `--output FORMAT` | Output format (text, json, csv) |
| `--log-level LEVEL` | Set logging level (debug, info, warning, error) |
| `--version` | Show version information and exit |
| `--help, -h` | Show help message and exit |

## Environment Variables

The KTRDR CLI respects the following environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `KTRDR_CONFIG_DIR` | Directory containing configuration files | `/path/to/config` |
| `KTRDR_DATA_DIR` | Directory for storing data files | `/path/to/data` |
| `KTRDR_OUTPUT_DIR` | Directory for output files | `/path/to/output` |
| `KTRDR_LOG_LEVEL` | Default logging level | `INFO` |
| `KTRDR_IB_HOST` | Interactive Brokers host | `127.0.0.1` |
| `KTRDR_IB_PORT` | Interactive Brokers port | `4001` |
| `KTRDR_IB_CLIENT_ID` | Interactive Brokers client ID | `1` |

## Examples

### Basic Data Fetching

Fetch 1-day historical data for AAPL:

```bash
ktrdr fetch AAPL --timeframe 1d
```

### Calculating Indicators

Calculate RSI on AAPL data:

```bash
ktrdr calculate AAPL --indicator rsi --period 14
```

### Visualizing Data

Create a candlestick chart for AAPL with indicators:

```bash
ktrdr plot-indicator AAPL --indicator sma --period 20 --indicator rsi --period 14
```

### Running a Backtest

Backtest a strategy on EURUSD data:

```bash
ktrdr backtest --symbol EURUSD --timeframe 1h --strategy path/to/strategy.yaml
```

## Scripting with the CLI

The KTRDR CLI can be easily used in shell scripts for automation:

```bash
#!/bin/bash
# Download data for multiple symbols
symbols=("AAPL" "MSFT" "GOOGL" "AMZN")
for symbol in "${symbols[@]}"; do
    ktrdr fetch "$symbol" --timeframe 1d --start 2023-01-01
    ktrdr plot-indicator "$symbol" --indicator sma --period 20 --indicator rsi --period 14
done
```

## Exit Codes

The CLI uses the following exit codes:

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Command-line usage error |
| 3 | Data error (e.g., file not found) |
| 4 | Configuration error |
| 5 | Network error (e.g., connection failure) |

## Command Reference

For detailed information about each command, see the specific command documentation:

- [Data Commands](data-commands.md)
- [Indicator Commands](indicator-commands.md)
- [Visualization Commands](visualization-commands.md)
- [Strategy Commands](strategy-commands.md)