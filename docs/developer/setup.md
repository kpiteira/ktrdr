# KTRDR Developer Setup Guide

This guide helps new developers set up their development environment for the KTRDR project.

## Prerequisites

Before starting, ensure you have the following installed:

- **Python 3.11+**: Required for running the KTRDR application
- **Git**: For version control
- **Docker** and **Docker Compose**: For containerized development
- **Interactive Brokers TWS or Gateway** (optional): For live data integration

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/ktrdr2.git
cd ktrdr2
```

### 2. Environment Setup

KTRDR uses UV for dependency management. If you don't have UV installed, you can install it with:

```bash
pip install uv
```

Set up your development environment:

```bash
# Create virtual environment
uv venv

# Activate the virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate

# Install dependencies
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt
```

### 3. Configuration Setup

Copy the example configuration files:

```bash
# Create config directory if it doesn't exist
mkdir -p config/environment

# Copy example config files
cp config/ktrdr_metadata.yaml.example config/ktrdr_metadata.yaml
cp config/settings.yaml.example config/settings.yaml
```

Edit the configuration files as needed for your environment.

### 4. Docker Setup (Alternative)

For containerized development, use the provided Docker setup:

```bash
# Build and start the development containers
./docker_dev.sh

# Or use docker-compose directly
docker-compose -f docker-compose.yml up --build
```

### 5. Local Development

#### Running the API Server

```bash
# Start the FastAPI server
python -m ktrdr.api.main

# Or use the development script
./setup_dev.sh
```

#### Using the CLI

```bash
# Run KTRDR CLI commands
python ktrdr_cli.py [command] [options]

# For example, to fetch data
python ktrdr_cli.py fetch AAPL --timeframe 1d
```

#### Running Tests

```bash
# Run all tests
pytest

# Run specific tests
pytest tests/test_data_loading.py

# Run tests with coverage
pytest --cov=ktrdr
```

## Project Structure

```
ktrdr2/
├── .uv/                    # UV virtual environment directory
├── ktrdr/                  # Main package
│   ├── __init__.py         # Package initialization
│   ├── api/                # API module (FastAPI)
│   ├── cli/                # Command-line interface module
│   ├── config/             # Configuration management
│   ├── data/               # Data access layer
│   ├── errors/             # Error handling framework
│   ├── fuzzy/              # Fuzzy logic engine
│   ├── indicators/         # Indicator engine
│   ├── logging/            # Logging system
│   ├── neural/             # Neural network engine
│   ├── ui/                 # User interface components
│   └── visualization/      # Visualization components
├── tests/                  # Test suite
├── docs/                   # Documentation
├── scripts/                # Utility scripts
├── config/                 # Configuration files
├── data/                   # Data storage
├── output/                 # Generated files and visualizations
└── logs/                   # Log files
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Implement Changes

Follow these guidelines when implementing changes:

- Use type hints consistently
- Add docstrings for all public functions, classes, and methods
- Follow the error handling patterns in `ktrdr.errors`
- Create appropriate unit tests for your changes
- Use the logging system with appropriate log levels

### 3. Run Tests

```bash
# Run tests to ensure your changes don't break anything
pytest
```

### 4. Format and Lint Code

```bash
# Format code with black
black ktrdr tests

# Check typing with mypy
mypy ktrdr
```

### 5. Submit a Pull Request

Push your branch to GitHub and create a pull request:

```bash
git push origin feature/your-feature-name
```

## Code Style Guidelines

KTRDR follows these code style guidelines:

- **Black**: For code formatting
- **PEP 8**: For general Python style guidelines
- **Type Hints**: Use type hints for all function parameters and return values
- **Docstrings**: Use Google-style docstrings
- **Error Handling**: Use the error handling framework in `ktrdr.errors`
- **Logging**: Use the logging system with appropriate levels

## Common Development Tasks

### Adding a New Indicator

See [Adding New Indicators](../adding_new_indicators.md) for a detailed guide on implementing new technical indicators.

### Adding a New API Endpoint

1. Create a new endpoint function in the appropriate module in `ktrdr/api/endpoints/`
2. Define request and response models in `ktrdr/api/models/`
3. Implement service functions in `ktrdr/api/services/`
4. Add tests in `tests/api/endpoints/`
5. Update API documentation

### Implementing a CLI Command

1. Add a new command function in `ktrdr/cli/commands/`
2. Register the command in `ktrdr/cli/__init__.py`
3. Add tests in `tests/cli/`
4. Create CLI documentation in `docs/cli/`

## Troubleshooting

### Common Issues

#### "ModuleNotFoundError: No module named 'ktrdr'"

- Make sure your virtual environment is activated
- Ensure the KTRDR package is installed (`pip install -e .`)

#### "Connection failed" with Interactive Brokers

- Make sure IB TWS or Gateway is running
- Check that API connections are enabled
- Verify the port and client ID settings

#### Docker container won't start

- Check that ports are not already in use
- Ensure Docker has sufficient resources
- Look at container logs with `docker-compose logs`

## Getting Help

If you need help with development, you can:

- Check the [documentation](../index.md)
- Look at code examples in the `examples/` directory
- Refer to the API reference documentation
- Check the code comments and docstrings

## Contributing

Please see [CONTRIBUTING.md](../../CONTRIBUTING.md) for detailed information on how to contribute to the KTRDR project.