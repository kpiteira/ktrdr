# KTRDR

KTRDR is an automated trading agent built around a neuro-fuzzy decision engine. It provides tools for strategy prototyping, validation through backtesting, and eventually paper and live trading.

## Features

- Local data management and processing
- Technical indicator calculation
- Fuzzy logic transformation
- Neural network decision engine
- Interactive visualization
- Paper and live trading through Interactive Brokers (planned)

## Setup

This project uses [UV](https://github.com/astral-sh/uv) for dependency management and virtual environments.

```bash
# Clone the repository
git clone https://github.com/your-username/ktrdr.git
cd ktrdr

# Run the setup script
chmod +x setup_dev.sh
./setup_dev.sh

# Activate the virtual environment
source .venv/bin/activate
```

## Project Structure

- `ktrdr/data/`: Data loading and management
- `ktrdr/indicators/`: Technical indicator calculations
- `ktrdr/fuzzy/`: Fuzzy logic engine
- `ktrdr/neural/`: Neural network components
- `ktrdr/visualization/`: Data visualization tools
- `ktrdr/ui/`: User interface components

## Development

This project follows a vertical slice approach to deliver incremental, testable value at each step.

## License

[MIT](LICENSE)
