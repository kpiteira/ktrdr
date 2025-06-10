# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ CRITICAL: THIS PROJECT USES UV ⚠️

**NEVER run `python` or `python3` directly!** This project uses `uv` for Python dependency management.

## 🚨 CRITICAL: MCP DEVELOPMENT RULES 🚨

**WHEN WORKING ON MCP FEATURES, NEVER TOUCH BACKEND OR FRONTEND CONTAINERS!**

**✅ ALLOWED MCP Commands:**
- `./mcp/restart_mcp.sh` - Restart only MCP container
- `./mcp/build_mcp.sh` - Build and start only MCP container  
- `./mcp/stop_mcp.sh` - Stop only MCP container
- `docker-compose -f docker/docker-compose.yml restart --no-deps mcp`
- `docker-compose -f docker/docker-compose.yml build --no-deps mcp`
- `docker-compose -f docker/docker-compose.yml up -d --no-deps mcp`

**❌ FORBIDDEN Commands (will break backend/frontend):**
- `docker-compose --profile research up -d` (rebuilds ALL containers)
- `docker-compose build` (rebuilds ALL containers) 
- `docker-compose restart` (restarts ALL containers)
- Any command that affects backend or frontend containers

**WHY:** The backend and frontend are delicate and should never be rebuilt during MCP development. Only the MCP container should be modified.

**Always use `uv run` for Python commands:**
- `uv run python script.py` (NOT `python script.py`)
- `uv run pytest` (NOT `pytest`)
- `uv run mypy ktrdr` (NOT `mypy ktrdr`)
- `uv run black ktrdr tests` (NOT `black ktrdr tests`)

Running Python directly will fail because dependencies are managed by uv, not installed globally.

## Build/Test/Lint Commands

- **Setup**: `./setup_dev.sh` to set up the environment
- **Python Tests**: `uv run pytest` (all tests), `uv run pytest tests/path/to/test.py` (specific test)
- **Python Linting**: `uv run black ktrdr tests` (formatting), `uv run mypy ktrdr` (type checking)
- **Frontend Dev**: Use Docker containers: `./docker_dev.sh start` (from root), NOT direct `npm run dev`
- **Frontend Shell**: `./docker_dev.sh shell-frontend` to access frontend container
- **Frontend Tests**: `cd frontend && npm run test` (within frontend container)
- **Frontend Lint**: `cd frontend && npm run lint` (within frontend container)
- **Frontend Typecheck**: `cd frontend && npm run typecheck` (within frontend container)

## CLI Commands

The project provides a comprehensive CLI via `uv run ktrdr` with the following commands:

### Core Data Commands
- **Show Data**: `uv run ktrdr show-data AAPL --timeframe 1h --rows 20`
- **Compute Indicators**: `uv run ktrdr compute-indicator AAPL --type RSI --period 14`
- **Plot Charts**: `uv run ktrdr plot AAPL --indicator SMA --period 20 --timeframe 1h`
- **Fuzzify Data**: `uv run ktrdr fuzzify AAPL --indicator RSI --period 14`

### IB Integration Commands  
- **Test IB**: `uv run ktrdr test-ib --symbol AAPL --verbose`
- **Load IB Data**: `uv run ktrdr ib-load AAPL 1d --mode tail`
- **IB Cleanup**: `uv run ktrdr ib-cleanup`

### Strategy Management
- **Validate Strategy**: `uv run ktrdr strategy-validate strategies/my_strategy.yaml`
- **Upgrade Strategy**: `uv run ktrdr strategy-upgrade strategies/old_strategy.yaml`
- **List Strategies**: `uv run ktrdr strategy-list --validate`

### Training & Backtesting
- **Train Model**: `uv run ktrdr train strategies/neuro_mean_reversion.yaml AAPL 1h --start-date 2024-01-01 --end-date 2024-06-01`
- **Test Model**: `uv run ktrdr model-test strategies/neuro_mean_reversion.yaml AAPL 1h`
- **Backtest Strategy**: `uv run ktrdr backtest strategies/neuro_mean_reversion.yaml AAPL 1h --start-date 2024-07-01 --end-date 2024-12-31`

All commands support `--help` for detailed usage and common options like `--verbose`, `--output`, `--data-dir`.

## Architecture Overview

- **Development Strategy**: Uses vertical slice approach, delivering end-to-end functionality
- **Core Modules**: Data, Indicators, Fuzzy Logic, Neural, Visualization, UI
- **Backend**: FastAPI with Pydantic models at `ktrdr/api/` (port 8000)
- **Frontend**: React/TypeScript with Redux Toolkit at `frontend/` (port 5173)
- **Config**: YAML-based with Pydantic validation in `config/` and `strategies/`
- **Data Storage**: Local files in `data/`, trained models in `models/`
- **IB Integration**: Interactive Brokers data fetching via `ktrdr/data/ib_*` modules

## Code Style Guidelines

- **Python**: Follow PEP 8 guidelines with Black formatting
- **Type Hints**: Required for all function parameters and return values
- **Docstrings**: Use Google-style docstrings
- **Imports**: Group standard library, third-party, and local imports
- **Error Handling**: Use the centralized error framework in `ktrdr.errors`
- **Logging**: Use the logging system with appropriate levels
- **Frontend**: Use TypeScript with React hooks and functional components
- **State Management**: Use Redux Toolkit with slice pattern
- **Testing**: Write unit tests for all new functionality
- **Timestamps**: ALWAYS use timezone-aware UTC timestamps (`pd.Timestamp.now(tz='UTC')`) to prevent timezone comparison errors

## Error Handling Standards

- Use custom exception types from `ktrdr.errors` (`DataError`, `ConnectionError`, etc.)
- Include informative error messages with error codes (e.g., "DATA-FileNotFound")
- Add detailed context in a `details` dictionary
- Use retry decorators for network operations: `@retry_with_backoff()`
- Implement fallbacks for non-critical components: `@fallback()`
- Log errors before raising them

## Logging Framework

- Create module-level logger: `logger = get_logger(__name__)`
- Use appropriate log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Apply logging decorators: `@log_entry_exit`, `@log_performance`, `@log_data_operation`
- Enrich context: `@with_context(operation_name="...")`
- For errors: `log_error(e, include_traceback=True)`

## Data & Config Patterns

- Use central metadata system with `ktrdr.metadata`
- Access config with direct properties: `metadata.VERSION`
- Use path-based access for nested config: `metadata.get("database.host")`
- Use strategy YAML files for complete configurations
- Follow factory pattern for constructing components from config

## API & Component Patterns

- Use Pydantic models for request/response validation
- Follow error model patterns in `ktrdr.api.models.errors`
- Structure API following the module-specific endpoint pattern
- Create service adapters to connect API with core modules
- Follow standardized API response format with `success` flag
- Use consistent data transformation patterns between core and API

## Frontend Patterns

- Create components following examples in `frontend/src/components`
- Structure components in hierarchy: base, feature, page, layout
- Use Redux slices with async thunks for API calls
- Follow TypeScript interface definitions in `src/types`
- Implement API client with typed methods in `src/api`
- Validate user inputs with `InputValidator` to prevent injection attacks
- Sanitize file paths to prevent traversal attacks

## Indicator Implementation

- Inherit from `BaseIndicator` and implement required methods
- Add thorough parameter validation in `_validate_params`
- Use vectorized operations (pandas, numpy) for optimal performance
- Register new indicators in `tests/indicators/indicator_registry.py`
- Create reference datasets for automated testing

## CRITICAL FIXES - DO NOT REMOVE

### Chart Jumping Bug Prevention (CRITICAL)

**Location**: `frontend/src/components/presentation/charts/BasicChart.tsx` lines 288-341

**Issue**: TradingView Lightweight Charts v5 automatically adjusts visible time range when indicators are added to synchronized charts, causing unwanted forward jumps in time that break user experience.

**Solution**: Preventive visibility toggle (hide/show) of first indicator after addition. Forces TradingView to recalculate correct time range without jumping.

**Key Details**:
- Only triggers on first overlay indicator addition to synchronized charts (`preserveTimeScale=true`)
- Uses precisely timed 1ms delays (tested minimum effective timing)
- Completely imperceptible to users but prevents chart jumping
- **SEVERITY: CRITICAL** - Removing this fix will cause immediate regression

**Testing**: Add first indicator (SMA, EMA, etc.) and verify no time range jumping occurs.

**Last Verified**: May 28, 2025 with TradingView Lightweight Charts v5.0.7

## Docker Development Environment

This project uses Docker containers for consistent development:

- **Start Environment**: `./docker_dev.sh start` (from project root)
- **Stop Environment**: `./docker_dev.sh stop`
- **Backend Shell**: `./docker_dev.sh shell-backend` (Python/FastAPI environment)
- **Frontend Shell**: `./docker_dev.sh shell-frontend` (Node.js/React environment)
- **View Logs**: `./docker_dev.sh logs [service]`

The frontend runs in Docker but serves on port 5173, accessible at `http://localhost:5173`. Always use the Docker environment rather than local npm/node installations.

## MCP Server Architecture

This codebase includes specifications for a Model Context Protocol (MCP) server that enables Claude to conduct autonomous trading strategy research:

- **Location**: `specification/ktrdr-mcp-*` files contain the complete architecture
- **Purpose**: Allow Claude to programmatically access KTRDR capabilities for research
- **Status**: Architecture defined, implementation in progress
- **Integration**: Planned as separate Docker service with read-only market data access

Key principles:
- Safety first: No access to live trading, order execution, or production systems
- Research focus: Tools for data analysis, strategy creation, model training, backtesting
- Knowledge preservation: Built-in experiment tracking and insight accumulation