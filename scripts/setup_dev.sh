#!/bin/bash
# setup_dev.sh - UV-based development environment setup for KTRDR

# Install UV if not installed
if ! command -v uv &> /dev/null; then
    echo "UV not found, installing..."
    pip install --upgrade uv
else
    echo "UV already installed, upgrading..."
    pip install --upgrade uv
fi

# Create virtual environment
echo "Creating UV virtual environment..."
uv venv

# Activate the virtual environment (this won't persist, but shows the command)
echo "To activate the environment, run:"
echo "  source .venv/bin/activate  # Unix/Mac"
echo "  # OR"
echo "  .venv\\Scripts\\activate  # Windows"

# Install dependencies
echo "Installing dependencies..."
uv sync --all-extras --dev

# Create necessary directories
echo "Creating necessary directories..."
mkdir -p config
mkdir -p data
mkdir -p logs

# Install pre-commit hooks if available
if command -v pre-commit &> /dev/null; then
    echo "Setting up pre-commit hooks..."
    pre-commit install
else
    echo "Pre-commit not found, skipping hook installation."
    echo "Run 'pip install pre-commit && pre-commit install' to set up hooks later."
fi

echo "Development environment setup complete!"
