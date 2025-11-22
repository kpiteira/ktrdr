# KTRDR Installation Guide

This guide provides step-by-step instructions for installing and setting up the KTRDR trading system. 

**Difficulty**: Beginner

**Time to complete**: Approximately 10-15 minutes

## Prerequisites

Before installing KTRDR, ensure you have the following:

- **Python 3.13+** installed on your system
- **Git** for cloning the repository (or download the ZIP file directly)
- **Interactive Brokers TWS or Gateway** (optional, for live data)

## Installation Methods

There are several ways to install KTRDR:

1. **Using UV** (Recommended)
2. **Using pip**
3. **Using Docker**
4. **Development install**

## Method 1: Using UV (Recommended)

UV is a fast, reliable Python package installer that's recommended for KTRDR installation.

### Step 1: Install UV

```bash
# Install UV if you don't have it already
pip install uv
```

### Step 2: Clone the Repository

```bash
git clone https://github.com/yourusername/ktrdr2.git
cd ktrdr2
```

### Step 3: Install Dependencies

```bash
# Install dependencies (automatically creates venv)
uv sync --all-extras
```

### Step 4: Verify Installation

```bash
# Run the CLI to verify installation
python ktrdr_cli.py --version
```

You should see the current version of KTRDR displayed.

## Method 2: Using pip (Legacy)

> **Note**: UV is the recommended installation method. This method is provided for compatibility.

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/ktrdr2.git
cd ktrdr2
```

### Step 2: Install UV and Dependencies

```bash
# Install UV
pip install uv

# Install dependencies
uv sync --all-extras
```

### Step 3: Verify Installation

```bash
# Run the CLI to verify installation
uv run ktrdr --version
```

## Method 3: Using Docker

Docker provides an isolated environment with all dependencies pre-configured.

### Step 1: Install Docker

First, ensure Docker is installed on your system. See the [Docker installation guide](https://docs.docker.com/get-docker/) for instructions.

### Step 2: Clone the Repository

```bash
git clone https://github.com/yourusername/ktrdr2.git
cd ktrdr2
```

### Step 3: Build and Run the Docker Container

```bash
# Build the Docker image
docker build -t ktrdr:latest .

# Run the container
docker run -it --name ktrdr ktrdr:latest
```

For development, you can use the development Docker setup:

```bash
# Build and start the development container
./docker_dev.sh
```

## Method 4: Development Install

For contributors and developers who want to modify the codebase:

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/ktrdr2.git
cd ktrdr2
```

### Step 2: Install in Development Mode

```bash
# Install all dependencies including dev tools
uv sync --all-extras --dev
```

This installs the package in development mode, allowing you to modify the code and see changes immediately.

## Configuration

After installation, you'll need to set up your configuration:

### Step 1: Create Configuration Files

```bash
# Create config directory if it doesn't exist
mkdir -p config/environment

# Copy example configuration files
cp config/ktrdr_metadata.yaml.example config/ktrdr_metadata.yaml
cp config/settings.yaml.example config/settings.yaml
```

### Step 2: Edit Configuration Files

Edit the configuration files to match your environment and preferences. At minimum, you'll need to:

1. Set data directory paths in `settings.yaml`
2. Configure Interactive Brokers connection (if using live data)

## Interactive Brokers Setup (Optional)

If you plan to use Interactive Brokers for live data:

### Step 1: Install TWS or IB Gateway

Download and install Interactive Brokers Trader Workstation (TWS) or IB Gateway from the [Interactive Brokers website](https://www.interactivebrokers.com).

### Step 2: Enable API Connections

1. Open TWS or IB Gateway
2. Go to File > Global Configuration > API > Settings
3. Enable "Enable ActiveX and Socket Clients"
4. Set the port number (default: 7496 for TWS, 4001 for Gateway)
5. Add your IP address to the trusted IPs list

### Step 3: Update KTRDR Configuration

Edit your `settings.yaml` file to include the IB connection details:

```yaml
interactive_brokers:
  enabled: true
  host: "127.0.0.1"
  port: 7496  # or 4001 for Gateway
  client_id: 1
  timeout: 30
```

## Verification

To verify your installation and configuration:

```bash
# Test data fetching
python ktrdr_cli.py fetch AAPL --timeframe 1d --source local

# If IB is configured, test live data fetching
python ktrdr_cli.py fetch AAPL --timeframe 1d --source ib
```

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "ModuleNotFoundError" | Ensure your virtual environment is activated and all dependencies are installed |
| IB connection error | Verify TWS/Gateway is running and API connections are enabled |
| Permission errors | Check file system permissions for config and data directories |
| Package conflicts | Try using a clean virtual environment and UV for installation |

### Getting Help

If you encounter problems not covered here:

1. Check the [FAQ](../faq.md) for common questions
2. Look at the [Troubleshooting Guide](../troubleshooting.md) for more solutions
3. Search for or report issues on the [GitHub repository](https://github.com/yourusername/ktrdr2/issues)

## Next Steps

Now that you've installed KTRDR, continue with:

- [Quickstart Tutorial](quickstart.md) to learn the basics
- [Key Concepts](key-concepts.md) to understand how KTRDR works
- [Developer Setup](../developer/setup.md) if you're interested in contributing