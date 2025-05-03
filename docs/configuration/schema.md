# KTRDR Configuration Reference

This document provides a comprehensive reference for KTRDR's configuration system, including all available configuration options, validation rules, and examples.

## Configuration Overview

KTRDR uses a YAML-based configuration system with multiple configuration files for different aspects of the system:

- `ktrdr_metadata.yaml`: Core project metadata and centralized configuration
- `settings.yaml`: General system settings and environment configuration
- `indicators.yaml`: Default technical indicator configurations
- `fuzzy.yaml`: Default fuzzy logic set configurations
- Strategy-specific configuration files (in the `strategies/` directory)

All configuration files are validated against schemas using Pydantic to ensure correctness and provide helpful error messages.

## Configuration Resolution Order

KTRDR resolves configuration values in the following priority order:

1. Environment variables (highest priority)
2. Command-line arguments (when using CLI)
3. Environment-specific configuration files (e.g., `development.yaml`)
4. Default configuration files
5. Built-in defaults (lowest priority)

## Core Metadata Configuration

The `ktrdr_metadata.yaml` file contains central project metadata and serves as a single source of truth for system-wide configuration.

### Schema

```yaml
# Basic metadata
name: "ktrdr"
version: "1.0.0"
description: "KTRDR Trading System"

# Environment configuration
environment:
  current: "development"
  supported: ["development", "testing", "production"]

# API configuration  
api:
  host: "127.0.0.1"
  port: 8000
  prefix: "/api/v1"
  timeout: 30
  
# Database configuration
database:
  host: "localhost"
  port: 5432
  name: "ktrdr"
  user: "ktrdr"
  
# Logging configuration
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "logs/ktrdr.log"
  max_size: 10485760  # 10 MB
  backup_count: 5

# Docker configuration
docker:
  labels:
    title: "KTRDR Backend"
    description: "KTRDR trading system backend API"
    licenses: "Proprietary"
    authors: "KTRDR Team"
    documentation: "https://ktrdr-docs.example.com"
  
# UI Configuration  
ui:
  title: "KTRDR Dashboard"
  theme:
    primary_color: "#4CAF50"
    secondary_color: "#1a1a1a"
  logo_url: "/static/images/logo.png"
  
# Examples for Documentation
examples:
  symbols: ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
  timeframes: ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w", "1M"]
```

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `name` | string | Yes | | Project name |
| `version` | string | Yes | | Project version (semver format) |
| `description` | string | No | `""` | Project description |
| `environment.current` | string | Yes | `"development"` | Current environment |
| `environment.supported` | array | Yes | `["development", "testing", "production"]` | Supported environments |
| `api.host` | string | No | `"127.0.0.1"` | API host address |
| `api.port` | integer | No | `8000` | API port number |
| `api.prefix` | string | No | `"/api/v1"` | API endpoint prefix |
| `api.timeout` | integer | No | `30` | API timeout in seconds |
| `database.*` | object | No | | Database connection settings |
| `logging.*` | object | No | | Logging configuration |
| `docker.labels.*` | object | No | | Docker container labels |
| `ui.*` | object | No | | UI configuration |
| `examples.*` | object | No | | Documentation examples |

### Environment Variables

The following environment variables can override core metadata configuration:

| Environment Variable | Configuration Property | Example | Description |
|----------------------|------------------------|---------|-------------|
| `KTRDR_ENVIRONMENT` | `environment.current` | `"production"` | Override current environment |
| `KTRDR_API_HOST` | `api.host` | `"0.0.0.0"` | Override API host |
| `KTRDR_API_PORT` | `api.port` | `9000` | Override API port |
| `KTRDR_LOG_LEVEL` | `logging.level` | `"DEBUG"` | Override logging level |
| `KTRDR_DB_HOST` | `database.host` | `"db.example.com"` | Override database host |

## Strategy Configuration

Strategy configuration files define trading strategies with indicators, fuzzy sets, and model configurations.

### Schema

```yaml
# Basic strategy metadata
name: "basic_rsi_trend"
description: "Simple RSI-based trend following strategy"
version: "1.0.0"
author: "KTRDR Team"

# Indicator configuration
indicators:
  - name: "rsi"
    period: 14
    source: "close"
  - name: "ema"
    period: 20
    source: "close"

# Fuzzy set configuration
fuzzy_sets:
  rsi:
    low: [0, 30, 45]
    high: [55, 70, 100]

# Neural model configuration
model:
  type: "mlp"
  input_size: 3
  hidden_layers: [10, 10]
  output_size: 2
  weights: "weights/basic_rsi_trend.pt"

# Trading parameters
trading:
  position_size: 0.1
  max_positions: 1
  stop_loss: 0.02
  take_profit: 0.05
```

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `name` | string | Yes | | Strategy name |
| `description` | string | No | `""` | Strategy description |
| `version` | string | No | `"1.0.0"` | Strategy version |
| `author` | string | No | `""` | Strategy author |
| `indicators` | array | Yes | | List of indicator configurations |
| `indicators[].name` | string | Yes | | Indicator name |
| `indicators[].period` | integer | No | Depends on indicator | Indicator period |
| `indicators[].source` | string | No | `"close"` | Price data source ("open", "high", "low", "close") |
| `fuzzy_sets` | object | Yes | | Fuzzy set configurations |
| `fuzzy_sets.<indicator>.<set>` | array | Yes | | Fuzzy set parameters for each indicator |
| `model` | object | Yes | | Neural model configuration |
| `model.type` | string | Yes | | Model type (e.g., "mlp", "lstm") |
| `model.input_size` | integer | Yes | | Number of input neurons |
| `model.hidden_layers` | array | Yes | | Array of hidden layer sizes |
| `model.output_size` | integer | Yes | | Number of output neurons |
| `model.weights` | string | No | | Path to pre-trained weights file |
| `trading` | object | No | | Trading parameters |

## Indicator Configuration

The `indicators.yaml` file defines default indicator configurations.

### Schema

```yaml
# Default indicator configurations
rsi:
  default_period: 14
  min_period: 2
  max_period: 100
  default_source: "close"
  sources: ["close", "open", "high", "low"]

sma:
  default_period: 20
  min_period: 2
  max_period: 500
  default_source: "close"
  sources: ["close", "open", "high", "low"]

ema:
  default_period: 20
  min_period: 2
  max_period: 500
  default_source: "close"
  sources: ["close", "open", "high", "low"]

macd:
  fast_period: 12
  slow_period: 26
  signal_period: 9
  default_source: "close"
  sources: ["close"]

bollinger_bands:
  default_period: 20
  default_std_dev: 2.0
  min_period: 2
  max_period: 500
  min_std_dev: 0.5
  max_std_dev: 5.0
  default_source: "close"
  sources: ["close", "open", "high", "low"]
```

## Fuzzy Logic Configuration

The `fuzzy.yaml` file defines default fuzzy set configurations for indicators.

### Schema

```yaml
# Default fuzzy set configurations
rsi:
  low: [0, 30, 45]
  neutral: [30, 50, 70]
  high: [55, 70, 100]

macd:
  negative: [-100, -1, 0]
  neutral: [-1, 0, 1]
  positive: [0, 1, 100]

bollinger_bands:
  lower: [-100, -1, -0.5]
  middle: [-0.75, 0, 0.75]
  upper: [0.5, 1, 100]
```

## Best Practices

1. **Use Environment Variables for Sensitive Information**: Never store passwords or API keys in configuration files. Use environment variables instead.

2. **Version Your Configuration Files**: Keep your configuration files under version control, but use environment-specific configuration for values that change between environments.

3. **Validate Configuration Early**: The system validates configuration at startup, but for custom configurations, it's good practice to validate them before deployment.

4. **Document Custom Configurations**: When creating custom strategies or indicators, document their configuration parameters.

5. **Use Default Values Wisely**: The system provides sensible defaults for most parameters, but adjust them based on your specific needs.

## Examples

### Development Environment Configuration

```yaml
environment:
  current: "development"

api:
  host: "127.0.0.1"
  port: 8000

logging:
  level: "DEBUG"
  file: "logs/ktrdr_dev.log"
```

### Production Environment Configuration

```yaml
environment:
  current: "production"

api:
  host: "0.0.0.0"
  port: 8080

logging:
  level: "INFO"
  file: "/var/log/ktrdr/ktrdr.log"
```

### Custom Strategy Configuration

```yaml
name: "mean_reversion_bbands"
description: "Mean reversion strategy based on Bollinger Bands"

indicators:
  - name: "bollinger_bands"
    period: 20
    std_dev: 2.0
    source: "close"
  - name: "rsi"
    period: 14
    source: "close"

fuzzy_sets:
  bollinger_bands:
    lower: [-100, -1, -0.5]
    middle: [-0.75, 0, 0.75]
    upper: [0.5, 1, 100]
  rsi:
    low: [0, 30, 45]
    high: [55, 70, 100]

model:
  type: "mlp"
  input_size: 5
  hidden_layers: [10, 10]
  output_size: 2
```