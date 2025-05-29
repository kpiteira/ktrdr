# Project Setup Implementation Guidance

When implementing the project setup tasks, here are some UV-specific considerations:

## 1. Sample pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ktrdr"
version = "0.1.0"
description = "Automated trading agent with neuro-fuzzy decision engine"
readme = "README.md"
requires-python = ">=3.9"
license = {file = "LICENSE"}
dependencies = [
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "plotly>=5.13.0",
    "streamlit>=1.22.0",
    "pytorch>=2.0.0",
    "pydantic>=2.0.0",
    "typer>=0.9.0",
    "ib_insync>=0.9.85",
    "pandas-ta>=0.3.14b0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.3.1",
    "black>=23.3.0",
    "isort>=5.12.0",
    "mypy>=1.3.0",
]
```

## 2. UV-compatible requirements files

```
# requirements.txt
pandas>=2.0.0
numpy>=1.24.0
plotly>=5.13.0
streamlit>=1.22.0
pytorch>=2.0.0
pydantic>=2.0.0
typer>=0.9.0
ib_insync>=0.9.85
pandas-ta>=0.3.14b0
```

## 3. Setup script for development environment

```bash
#!/bin/bash
# setup_dev.sh

# Install UV if not installed
pip install --upgrade uv

# Create virtual environment
uv venv

# Install dependencies
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```