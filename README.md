# KTRDR

Trading strategy research system using neuro-fuzzy neural networks

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Note:** This is a personal learning project, not production trading software. I built it as a vehicle for exploring AI-assisted coding, neural networks, fuzzy systems, distributed architectures, and homelab cluster deployments. It's deliberately over-engineered for a solo project — that's the point.

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Development Environments](#development-environments)
- [Architecture](#architecture)
- [CLI Commands](#cli-commands)
- [API Reference](#api-reference)
- [Development](#development)
- [Testing](#testing)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## Overview

KTRDR is a **trading strategy research system** that uses neuro-fuzzy neural networks to develop and validate trading strategies. Unlike black-box ML approaches, neuro-fuzzy models combine neural network learning with fuzzy logic rules, producing **interpretable** trading decisions you can understand and refine.

**The research loop:**

1. **Design** — Define strategies using technical indicators and fuzzy logic rules
2. **Train** — Train neuro-fuzzy models on historical data (GPU-accelerated)
3. **Backtest** — Validate strategies against out-of-sample data
4. **Assess** — Evaluate results, identify what works and why
5. **Learn** — Accumulate knowledge across experiments

**What makes it different:**

- **Interpretable models** — Fuzzy rules you can read, not black-box predictions
- **Distributed workers** — Horizontal scaling for parallel experiments
- **Full observability** — Trace every operation through Jaeger

## Key Features

### Data Management

- Multi-source integration with Interactive Brokers
- Automatic gap detection and filling
- Multi-timeframe synchronization
- Local caching for fast access

### Technical Analysis

- 70+ indicators (RSI, MACD, Bollinger Bands, etc.)
- Multi-timeframe calculations
- Custom indicator framework
- Optimized batch processing

### Neuro-Fuzzy Engine

- Configurable membership functions
- Custom fuzzy rule systems
- PyTorch neural networks
- GPU-accelerated training

### Distributed Execution

- Horizontal scaling with workers
- GPU-first with CPU fallback
- Dynamic worker scaling
- Self-registering architecture

### Research Interfaces

- **CLI** for running experiments (`ktrdr train`, `ktrdr backtest`)
- **REST API** (FastAPI) for automation and integration
- **Interactive Brokers** connection for market data

## Quick Start

### Prerequisites

- Python 3.12 or later
- Docker and Docker Compose
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

```bash
git clone https://github.com/your-username/ktrdr.git
cd ktrdr
./setup_dev.sh
```

### Start the System

```bash
# Start backend with workers
docker compose up -d --scale backtest-worker=3 --scale training-worker=2

# Verify workers registered
curl http://localhost:8000/api/v1/workers | jq
```

For GPU-accelerated training (10x-100x faster):

```bash
cd training-host-service && ./start.sh
```

### Basic Usage

```bash
# Load market data
ktrdr data load AAPL 1d --start-date 2024-01-01

# Validate a strategy
ktrdr validate config/strategies/example.yaml

# Run a backtest
ktrdr backtest config/strategies/example.yaml \
  --start-date 2024-01-01 --end-date 2024-06-01
```

### Service URLs

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/api/v1/docs |
| Frontend | http://localhost:3000 |
| Grafana | http://localhost:3000 |
| Jaeger | http://localhost:16686 |

## Development Environments

KTRDR provides two types of managed environments:

### Local-Prod (Primary Environment)

Local-prod is your main execution environment for real work — connecting to IB Gateway, running GPU training, and using the MCP server with Claude.

```bash
# First-time setup (interactive)
curl -fsSL https://raw.githubusercontent.com/kpiteira/ktrdr/main/scripts/setup-local-prod.sh | bash

# Or manual setup
git clone https://github.com/kpiteira/ktrdr.git ~/Documents/dev/ktrdr-prod
cd ~/Documents/dev/ktrdr-prod
uv sync
uv run ktrdr local-prod init
uv run ktrdr local-prod up
```

**Key features:**
- Standard ports (8000, 3000, etc.) for host service integration
- 1Password secrets management (`ktrdr-local-prod` item)
- MCP server for Claude Code/Desktop integration
- Singleton — only one local-prod instance allowed

Full setup guide: [docs/designs/Sandbox/LOCAL_PROD_SETUP.md](docs/designs/Sandbox/LOCAL_PROD_SETUP.md)

### Sandboxes (Parallel Development)

Sandboxes are isolated environments for parallel feature development and testing. Each sandbox runs on different ports to avoid conflicts.

```bash
# Create a sandbox for feature work
uv run ktrdr sandbox create my-feature
cd ../ktrdr--my-feature
uv run ktrdr sandbox up

# List all sandboxes
uv run ktrdr sandbox list
```

**Key features:**
- Up to 10 parallel sandboxes (slots 1-10)
- Isolated Docker containers on offset ports
- Git worktrees for efficient disk usage
- Shared data directory (`~/.ktrdr/shared/`)

Sandbox guide: [docs/designs/Sandbox/USAGE_GUIDE.md](docs/designs/Sandbox/USAGE_GUIDE.md)

## Architecture

KTRDR uses a distributed architecture where the backend orchestrates and workers execute:

```
                    ┌─────────────────────────┐
                    │    Strategy Config      │
                    │  (indicators + fuzzy    │
                    │       rules)            │
                    └───────────┬─────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────┐
│                      Backend (Orchestrator)                       │
│              Routes operations to available workers               │
└─────────────────────────────┬─────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
  ┌───────────┐         ┌───────────┐         ┌───────────┐
  │ Training  │         │ Training  │         │ Backtest  │
  │ Worker    │         │ Worker    │         │ Workers   │
  │ (GPU)     │         │ (CPU)     │         │           │
  └─────┬─────┘         └─────┬─────┘         └─────┬─────┘
        │                     │                     │
        └──────────┬──────────┘                     │
                   ▼                                ▼
          ┌───────────────┐                ┌───────────────┐
          │ Trained Model │ ──────────────▶│   Backtest    │
          │ (Neuro-Fuzzy) │                │   Results     │
          └───────────────┘                └───────────────┘
```

**Key principles:**

- Backend orchestrates, workers execute
- GPU workers prioritized for training (10-100x faster)
- Workers self-register on startup
- All operations tracked with distributed tracing

For detailed architecture, see [docs/architecture-overviews/distributed-workers.md](docs/architecture-overviews/distributed-workers.md).

## CLI Commands

```bash
# Data management
ktrdr data show AAPL 1d --rows 20
ktrdr data load AAPL 1h --start-date 2024-01-01

# Strategy operations
ktrdr validate config/strategies/example.yaml
ktrdr train config/strategies/example.yaml --start-date 2024-01-01 --end-date 2024-06-01
ktrdr backtest config/strategies/example.yaml --start-date 2024-07-01 --end-date 2024-12-31

# Operations management
ktrdr ops                    # List operations
ktrdr status <operation-id>  # Check status
ktrdr cancel <operation-id>  # Cancel operation

# Interactive Brokers
ktrdr ib test-connection
ktrdr ib check-status
```

Full CLI reference: [docs/user-guides/cli-reference.md](docs/user-guides/cli-reference.md)

## API Reference

The REST API is available at `http://localhost:8000/api/v1/`.

| Category | Endpoint | Description |
|----------|----------|-------------|
| Data | `POST /data/load` | Load market data |
| Indicators | `POST /indicators/calculate` | Calculate indicators |
| Training | `POST /training/start` | Start model training |
| Backtesting | `POST /backtesting/start` | Start backtest |
| Operations | `GET /operations` | List running operations |
| Workers | `GET /workers` | List registered workers |

Interactive documentation: http://localhost:8000/api/v1/docs

## Development

### Prerequisites

- Python 3.12+
- Docker Desktop
- Node.js 18+ (for frontend)
- [uv](https://github.com/astral-sh/uv) package manager

**Important:** Always use `uv run` for Python commands:

```bash
# Correct
uv run pytest tests/

# Wrong - uses system Python
pytest tests/
```

### Setup

```bash
# Install dependencies
uv sync

# Start development environment
docker compose up -d

# Run quality checks
make quality        # Lint + format + typecheck
make test-unit      # Fast tests (<2min)
```

### Environment Configuration

Copy `.env.example` to `.env` and configure as needed.

Full setup guide: [docs/developer/setup.md](docs/developer/setup.md)

## Testing

```bash
make test-unit        # Unit tests (~1 min)
make test-integration # Integration tests (<30s)
make test-e2e         # End-to-end tests (<5min)
make quality          # Lint + format + typecheck
```

**Pre-commit checklist:**

1. `make test-unit` passes
2. `make quality` passes
3. No debug code or secrets
4. Commits are small and focused

Testing guide: [docs/developer/testing-guide.md](docs/developer/testing-guide.md)

## Documentation

| Topic | Location |
|-------|----------|
| CLI Reference | [docs/user-guides/cli-reference.md](docs/user-guides/cli-reference.md) |
| Deployment | [docs/user-guides/deployment.md](docs/user-guides/deployment.md) |
| Architecture | [docs/architecture-overviews/distributed-workers.md](docs/architecture-overviews/distributed-workers.md) |
| Development Guide | [docs/developer/setup.md](docs/developer/setup.md) |
| Testing Guide | [docs/developer/testing-guide.md](docs/developer/testing-guide.md) |
| Strategy Configuration | [docs/user-guides/strategy-management.md](docs/user-guides/strategy-management.md) |

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Run tests: `make test-unit && make quality`
4. Commit changes: `git commit -m 'Add amazing feature'`
5. Push and open a Pull Request

Development guidelines: [CLAUDE.md](CLAUDE.md)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
