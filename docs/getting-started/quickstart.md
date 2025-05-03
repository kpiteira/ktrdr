# KTRDR Quickstart Tutorial

This quickstart guide will help you get started with the KTRDR trading system, covering the basic operations for analyzing financial data and developing trading strategies.

**Difficulty**: Beginner

**Time to complete**: Approximately 15 minutes

**Prerequisites**:
- KTRDR installed (see [Installation Guide](installation.md))
- Basic understanding of financial markets and technical indicators

## Introduction

KTRDR is a comprehensive trading system that combines technical indicators, fuzzy logic, and neural networks to help analyze financial markets and develop trading strategies. This quickstart tutorial will guide you through the basics of using KTRDR, including:

1. Fetching historical data
2. Calculating and visualizing technical indicators
3. Creating a simple trading strategy
4. Viewing results and analyzing performance

## Step 1: Fetch Historical Price Data

The first step in any analysis is to retrieve historical price data. KTRDR makes this simple with the `fetch` command.

```bash
# Fetch daily data for Apple (AAPL) for the last year
ktrdr fetch AAPL --timeframe 1d
```

Expected output:
```
Successfully fetched data for AAPL (1d)
- Start date: 2024-05-02
- End date: 2025-05-02
- Data points: 252
- Source: Interactive Brokers
- Saved to: data/AAPL_1d.csv
```

You can also specify a date range:

```bash
# Fetch specific date range
ktrdr fetch MSFT --timeframe 1d --start 2024-01-01 --end 2024-04-30
```

## Step 2: Calculate and Visualize Indicators

After fetching data, you can calculate technical indicators and visualize them alongside price data.

```bash
# Calculate RSI indicator for AAPL
ktrdr plot-indicator AAPL --indicator rsi --period 14
```

This command will generate an interactive chart showing AAPL's price with the RSI indicator in a separate panel below.

You can also combine multiple indicators:

```bash
# Plot price with multiple indicators
ktrdr plot-indicator AAPL --indicator sma --period 20 --indicator ema --period 50
```

## Step 3: Create a Simple Trading Strategy

KTRDR uses YAML files to define trading strategies. Let's create a simple moving average crossover strategy.

Create a file named `ma_crossover.yaml` with the following content:

```yaml
name: "ma_crossover"
description: "Simple moving average crossover strategy"
version: "1.0.0"
author: "KTRDR User"

# Indicator configuration
indicators:
  - name: "sma"
    period: 20
    source: "close"
  - name: "sma"
    period: 50
    source: "close"

# Fuzzy set configuration
fuzzy_sets:
  sma:
    crossover:
      type: "triangular"
      parameters: [-1, 0, 1]
    above:
      type: "triangular"
      parameters: [0, 1, 2]
    below:
      type: "triangular"
      parameters: [-2, -1, 0]

# Trading parameters
trading:
  position_size: 0.1
  max_positions: 1
  stop_loss: 0.02
  take_profit: 0.05
```

## Step 4: Run a Backtest

Now let's run a backtest to see how our strategy performs:

```bash
# Run backtest using our strategy
ktrdr backtest --symbol AAPL --strategy ma_crossover.yaml --start 2024-01-01 --end 2025-04-30
```

The command will execute the strategy on historical data and display the results, including:
- Total number of trades
- Win rate
- Profit/Loss
- Maximum drawdown
- Sharpe ratio

## Step 5: Visualize Strategy Results

To visualize the strategy results, including entry and exit points:

```bash
# Visualize strategy results
ktrdr visualize --symbol AAPL --strategy ma_crossover.yaml --include-trades
```

This will generate an interactive chart showing:
- Price data with moving averages
- Entry and exit markers
- Equity curve in a separate panel

## Advanced Usage

Once you're comfortable with the basics, you can explore more advanced features:

### Custom Indicators

You can create custom indicators by extending the `BaseIndicator` class:

```python
from ktrdr.indicators import BaseIndicator
import pandas as pd

class MyCustomIndicator(BaseIndicator):
    def __init__(self, period1=14, period2=28, source='close'):
        self.period1 = period1
        self.period2 = period2
        self.source = source
        
    def compute(self, df):
        # Your indicator calculation logic here
        result = pd.Series(index=df.index)
        # ... calculation ...
        return result
```

### Fuzzy Logic Configuration

Customize fuzzy logic sets to create more sophisticated trading rules:

```yaml
fuzzy_sets:
  rsi:
    low: [0, 30, 45]
    neutral: [30, 50, 70]
    high: [55, 70, 100]
```

### Neural Network Integration

For advanced strategies, you can train neural networks on fuzzy logic inputs:

```yaml
model:
  type: "mlp"
  input_size: 8
  hidden_layers: [16, 16]
  output_size: 2
  weights: "weights/my_model.pt"
```

## Common Issues and Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Connection failed" error | Could not connect to Interactive Brokers | Check that IB TWS or Gateway is running |
| Missing data points | Exchange holidays or market closures | Use the `--repair` flag to fill gaps |
| Strategy not generating trades | Parameters may not be optimal | Adjust indicator parameters or fuzzy sets |

## Next Steps

Now that you've learned the basics, you might want to explore:

1. [Creating Custom Indicators](../examples/indicator-examples.md)
2. [Advanced Fuzzy Logic Configurations](../examples/fuzzy-examples.md)
3. [Optimizing Strategy Parameters](../user-guides/strategy-development.md)

## Additional Resources

- [KTRDR API Documentation](../api-reference/index.md)
- [Complete CLI Reference](../cli/index.md)
- [Configuration Reference](../configuration/schema.md)