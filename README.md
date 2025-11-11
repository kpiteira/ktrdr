# KTRDR - Advanced Trading System

KTRDR is an advanced automated trading system built around a neuro-fuzzy decision engine. It provides comprehensive tools for market data analysis, technical indicator calculation, fuzzy logic processing, neural network training, strategy backtesting, and Interactive Brokers integration.

## ✨ Key Features

### 🔄 Data Management

- **Multi-source data integration** with Interactive Brokers
- **Gap analysis and filling** for data quality
- **Multi-timeframe data synchronization**
- **Local data caching and storage**

### 📊 Technical Analysis

- **70+ technical indicators** (RSI, MACD, Bollinger Bands, etc.)
- **Multi-timeframe indicator calculations**
- **Custom indicator development framework**
- **Performance-optimized batch processing**

### 🧠 Fuzzy Logic Engine

- **Configurable membership functions** (triangular, trapezoidal, gaussian)
- **Multi-timeframe fuzzy analysis**
- **Custom fuzzy rule systems**
- **Real-time fuzzy evaluation**

### 🤖 Neural Networks

- **PyTorch-based models** for trading decisions
- **Multi-symbol training capabilities**
- **GPU memory management**
- **Model versioning and storage**

### 📈 Strategy Development

- **Strategy configuration and validation**
- **Comprehensive backtesting engine**
- **Performance metrics and analytics**
- **Strategy comparison tools**

### ⚡ Distributed Execution

- **Horizontal scaling** with distributed workers
- **Concurrent operations** across worker cluster
- **GPU-first training** with CPU fallback
- **Dynamic worker scaling** (`docker-compose up --scale`)
- **Self-registering workers** (infrastructure-agnostic)

### 🌐 API & Web Interface

- **RESTful API** with FastAPI
- **React frontend** for visualization
- **Real-time data streaming**
- **Interactive charts with TradingView**

### 🔌 Interactive Brokers Integration

- **Connection management and health monitoring**
- **Real-time market data**
- **Historical data fetching**
- **Trade execution capabilities**

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Docker and Docker Compose
- [UV](https://github.com/astral-sh/uv) package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/ktrdr.git
cd ktrdr

# Run the setup script
chmod +x setup_dev.sh
./setup_dev.sh
```

### Starting Workers

**IMPORTANT**: KTRDR uses a distributed architecture where operations execute on workers. You must start workers alongside the backend.

#### Quick Start: Docker Compose with Workers

```bash
# Start backend + workers (recommended for development)
docker-compose -f docker/docker-compose.yml up -d \
  --scale backtest-worker=3 \
  --scale training-worker=2

# Verify workers registered
curl http://localhost:8000/api/v1/workers | jq

# Expected: 3 backtest workers + 2 training workers showing as AVAILABLE
```

**Worker Scaling**: Add more workers for more concurrent operations:
- `--scale backtest-worker=10` → 10 concurrent backtests
- `--scale training-worker=5` → 5 concurrent training operations (CPU)

#### Optional: GPU Training (10x-100x Faster)

```bash
# Start GPU training host service (outside Docker, for GPU access)
cd training-host-service && ./start.sh

# GPU worker automatically registers with backend
# Training operations will prefer GPU (if available) before CPU fallback
```

#### For Production Deployments

**Deployment Options**:
- **Development**: [Docker Compose Guide](docs/user-guides/deployment.md) - Single-host, quick setup
- **Production**: [Proxmox LXC Guide](docs/user-guides/deployment-proxmox.md) - Multi-host, 5-15% better performance
- **Operations**: [CI/CD Runbook](docs/developer/cicd-operations-runbook.md) - Deployment automation, incident response

**Key Benefits of Proxmox (Production)**:
- Lower overhead (~5-15% performance improvement vs Docker)
- Template-based rapid worker cloning
- Full OS environment with systemd
- Proxmox management tools (backups, snapshots, monitoring)

### Launching KTRDR

#### Option 1: Complete System (Recommended)

```bash
# Start both IB Host Service and Docker backend
./start_ktrdr.sh
```

This will start:

- IB Host Service on port 5001
- API server on <http://localhost:8000>
- Frontend on <http://localhost:3000>
- **Note**: You still need to start workers separately (see above)

#### Option 2: Docker Development Environment

```bash
# Start development containers
./docker_dev.sh start

# View logs
./docker_dev.sh logs

# Stop containers
./docker_dev.sh stop

# Note: Start workers separately for backtesting/training operations
```

#### Option 3: API Server Only

```bash
# Using UV (recommended)
uv run python scripts/run_api_server.py

# Or using Python directly
python scripts/run_api_server.py --host 0.0.0.0 --port 8000

# Note: Backend alone won't execute operations - requires workers
```

## 📚 API Documentation

Once the server is running, visit:

- **Swagger UI**: <http://localhost:8000/api/v1/docs>
- **ReDoc**: <http://localhost:8000/api/v1/redoc>

### Key API Endpoints

#### Data Management

- `GET /api/v1/data/info` - Get data directory information
- `GET /api/v1/data/symbols` - List available symbols
- `POST /api/v1/data/load` - Load market data
- `GET /api/v1/data/range` - Get data range information

#### Technical Indicators

- `GET /api/v1/indicators` - List available indicators
- `POST /api/v1/indicators/calculate` - Calculate indicators
- `GET /api/v1/indicators/categories` - Get indicator categories

#### Fuzzy Logic

- `GET /api/v1/fuzzy/indicators` - List fuzzy indicators
- `POST /api/v1/fuzzy/fuzzify` - Fuzzify data values
- `GET /api/v1/fuzzy/sets` - Get fuzzy set definitions

#### Trading Models

- `GET /api/v1/models` - List trained models
- `POST /api/v1/models/train` - Start model training
- `POST /api/v1/models/predict` - Make predictions

#### Strategy Management

- `GET /api/v1/strategies` - List available strategies
- `POST /api/v1/strategies/validate` - Validate strategy configuration
- `POST /api/v1/backtesting/start` - Start backtest

#### Interactive Brokers

- `GET /api/v1/ib/status` - Check IB connection status
- `GET /api/v1/ib/health` - Health check
- `POST /api/v1/ib/cleanup` - Clean up connections

#### System Operations

- `GET /api/v1/operations` - List running operations
- `GET /api/v1/system/status` - System health status

## 🖥️ CLI Commands

KTRDR provides a comprehensive CLI interface:

```bash
# Main command
ktrdr --help

# Data management
ktrdr data show AAPL 1d --start-date 2024-01-01
ktrdr data load AAPL 1h --end-date 2024-12-31
ktrdr data get-range EURUSD 1d

# Technical indicators
ktrdr indicators list
ktrdr indicators compute AAPL 1d rsi --period 14
ktrdr indicators plot AAPL 1d --indicators rsi,macd

# Fuzzy logic
ktrdr fuzzy compute AAPL 1d --config config/fuzzy/default.yaml
ktrdr fuzzy visualize AAPL 1d --indicator rsi

# Model training
ktrdr models train --strategy config/strategies/example.yaml
ktrdr models list
ktrdr models test model_v1.0.0 --symbol AAPL

# Strategy backtesting
ktrdr strategies validate config/strategies/example.yaml
ktrdr strategies backtest config/strategies/example.yaml --start-date 2024-01-01

# Interactive Brokers
ktrdr ib test-connection
ktrdr ib check-status
ktrdr ib cleanup-connections

# Operations management
ktrdr operations list
ktrdr operations status <operation-id>
ktrdr operations cancel <operation-id>

# Gap analysis
ktrdr gap-analysis analyze AAPL 1d --start-date 2024-01-01
ktrdr gap-analysis service-status
```

## 🏗️ Project Architecture

```
ktrdr/
├── api/                    # FastAPI REST API
│   ├── endpoints/          # API route handlers
│   ├── models/            # Pydantic data models
│   ├── services/          # Business logic services
│   └── middleware/        # Custom middleware
├── cli/                   # Command-line interface
│   ├── data_commands.py   # Data management commands
│   ├── model_commands.py  # ML model commands
│   └── ib_commands.py     # IB integration commands
├── data/                  # Data management layer
│   ├── ib_data_adapter.py # IB data integration
│   └── data_manager.py    # Core data operations
├── indicators/            # Technical analysis
│   ├── base_indicator.py  # Base indicator class
│   ├── rsi_indicator.py   # RSI implementation
│   └── indicator_engine.py # Batch processing
├── fuzzy/                 # Fuzzy logic system
│   ├── membership.py      # Membership functions
│   ├── engine.py          # Fuzzy inference
│   └── multi_timeframe_engine.py
├── neural/                # Neural network models
│   ├── models/            # PyTorch model definitions
│   └── training/          # Training infrastructure
├── backtesting/           # Strategy backtesting
│   ├── engine.py          # Backtesting engine
│   └── performance.py     # Performance analysis
├── training/              # ML training pipeline
│   ├── training_manager.py # Training orchestration
│   └── model_storage.py   # Model persistence
├── config/                # Configuration management
├── errors/                # Custom exception handling
└── logging/               # Logging infrastructure

frontend/                  # React web interface
docker/                    # Docker configurations
scripts/                   # Utility scripts
tests/                     # Test suites
```

## 🔧 Development

### Prerequisites

- **CRITICAL**: This project uses `uv` for dependency management
- Never run `python` directly - always use `uv run python`
- Docker for containerized development
- Node.js for frontend development

### Development Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Code formatting
uv run black ktrdr tests

# Type checking
uv run mypy ktrdr

# Start development environment
./docker_dev.sh start

# Run backend tests
./docker_dev.sh test

# View logs
./docker_dev.sh logs-backend
./docker_dev.sh logs-frontend

# Switch to LOCAL training mode (CPU in Docker)
./scripts/switch-training-mode.sh local

# Switch to HOST SERVICE training mode (GPU if available)
./scripts/switch-training-mode.sh host
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Interactive Brokers
IB_HOST=127.0.0.1
IB_PORT=7497
IB_CLIENT_ID=1

# API Settings
KTRDR_API_HOST=0.0.0.0
KTRDR_API_PORT=8000
KTRDR_API_ENVIRONMENT=development

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/ktrdr

# OpenAI (for research features)
OPENAI_API_KEY=your_api_key_here
```

## 📊 Configuration

### Strategy Configuration

Strategies are defined in YAML files in `config/strategies/`:

```yaml
strategy:
  name: "Example Strategy"
  description: "Basic RSI strategy"
  
symbols:
  mode: "single"
  symbol: "AAPL"
  
timeframes:
  primary: "1d"
  
indicators:
  rsi:
    type: "rsi"
    parameters:
      period: 14
      
fuzzy:
  variables:
    rsi_level:
      type: "input"
      range: [0, 100]
      
neural:
  model_type: "mlp"
  hidden_layers: [64, 32, 16]
```

### Indicator Configuration

Configure custom indicators in `config/indicators/`:

```yaml
indicators:
  custom_rsi:
    type: "rsi"
    parameters:
      period: 21
      overbought: 75
      oversold: 25
```

## 🧪 Testing

### Running Tests

```bash
# All tests
uv run pytest

# Specific test categories
uv run pytest tests/unit/
uv run pytest tests/integration/
uv run pytest tests/e2e/

# With coverage
uv run pytest --cov=ktrdr --cov-report=html
```

### Test Categories

- **Unit tests**: Individual component testing
- **Integration tests**: Multi-component interaction
- **E2E tests**: Full system workflow testing
- **Real E2E tests**: Tests with live data (requires IB connection)

## 🚨 Troubleshooting

### Common Issues

#### IB Connection Problems

```bash
# Check IB Gateway status
ktrdr ib check-status

# Test connection
ktrdr ib test-connection

# Clean up stale connections
ktrdr ib cleanup-connections
```

#### Docker Issues

```bash
# Rebuild containers
./docker_dev.sh rebuild

# Clean environment
./docker_dev.sh clean

# View container logs
./docker_dev.sh logs-backend
```

#### Data Issues

```bash
# Check data availability
ktrdr data get-range AAPL 1d

# Analyze data gaps
ktrdr gap-analysis analyze AAPL 1d --start-date 2024-01-01
```

### Log Locations

- **IB Host Service**: `ib-host-service/logs/ib-host-service.log`
- **Backend**: `docker logs ktrdr-backend`
- **Frontend**: `docker logs ktrdr-frontend`

## 📝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes following the coding guidelines in `CLAUDE.md`
4. Run tests: `uv run pytest`
5. Run linting: `uv run black ktrdr tests && uv run mypy ktrdr`
6. Commit your changes: `git commit -m 'Add amazing feature'`
7. Push to the branch: `git push origin feature/amazing-feature`
8. Open a Pull Request

### Development Guidelines

- Follow the patterns documented in `CLAUDE.md`
- Use type hints for all functions
- Write comprehensive docstrings
- Add tests for new functionality
- Keep commits focused and atomic

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: Check the API docs at `/docs` when running the server
- **Issues**: Report bugs via GitHub Issues
- **Development**: See `CLAUDE.md` for detailed development guidelines
