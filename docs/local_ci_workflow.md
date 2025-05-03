# Local Development with GitHub Actions Runner

This document explains how to set up a local GitHub Actions runner to ensure consistent inner and outer development loops for the KTRDR project.

## Overview

By running GitHub Actions workflows locally, you can:

1. **Maintain consistent environments** between local development and CI/CD
2. **Test workflows before pushing** to avoid CI pipeline failures
3. **Debug CI issues** more effectively with local access
4. **Save time** by verifying workflows locally first

## Setting Up a Local GitHub Actions Runner

### 1. Install the GitHub Actions Runner

Follow these steps to set up a local runner:

```bash
# Create a directory for the runner
mkdir -p ~/actions-runner && cd ~/actions-runner

# Download the latest runner package (these URLs may change, check GitHub's documentation)
# For macOS:
curl -o actions-runner-osx-x64-2.303.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.303.0/actions-runner-osx-x64-2.303.0.tar.gz

# For Linux:
# curl -o actions-runner-linux-x64-2.303.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.303.0/actions-runner-linux-x64-2.303.0.tar.gz

# Extract the installer
tar xzf ./actions-runner-osx-x64-2.303.0.tar.gz
```

### 2. Configure the Runner for Your Repository

1. Go to your GitHub repository
2. Navigate to Settings > Actions > Runners
3. Click "New self-hosted runner"
4. Follow the instructions shown on GitHub to configure your runner

```bash
# It will look something like this:
./config.sh --url https://github.com/YOUR-USERNAME/ktrdr2 --token YOUR_TOKEN
```

### 3. Run the Runner

```bash
# Start the runner
./run.sh
```

## Using Act for Local Workflow Execution

For an even simpler approach, you can use [nektos/act](https://github.com/nektos/act), which allows you to run GitHub Actions workflows locally without setting up a runner.

### Installation

```bash
# MacOS
brew install act

# Linux
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

### Usage

Navigate to your local repository and run:

```bash
# Run the default workflow
act

# Run a specific workflow
act -W .github/workflows/ci.yml

# Run a specific job
act -j lint

# Run with event type
act push
```

## Docker Integration

Our existing Docker infrastructure works seamlessly with local GitHub Actions:

```bash
# Start Docker containers before running workflows
./docker_dev.sh start

# Run the CI workflow
act -W .github/workflows/ci.yml

# Check the results and fix any issues locally

# Stop containers when done
./docker_dev.sh stop
```

## Benefits of a Consistent Loop

By using this approach, your development workflow becomes:

1. Make code changes locally
2. Run tests and CI workflows locally
3. Fix any issues before committing
4. Push changes with confidence

This ensures that what works locally will work in the GitHub CI environment, eliminating the frustration of "it works on my machine" issues.

## GitHub Actions Local vs Remote

| Aspect | Local | Remote |
|--------|-------|--------|
| Environment | Your machine | GitHub runners |
| Execution speed | Faster for most tasks | Depends on GitHub load |
| Secrets | Use local .env files | Use GitHub secrets |
| Resource limits | Your machine's limits | GitHub's limits |
| Debugging | Full access | Limited to logs |

## Recommended Local Workflow

For the most consistent experience, we recommend:

1. Use Docker for local development (`./docker_dev.sh start`)
2. Run unit tests locally first (`./docker_dev.sh test`)
3. Run linting and style checks (`act -j lint`)
4. Test full CI workflow before pushing (`act push`)
5. Use GitHub's CI as final validation

This approach minimizes surprises and ensures that your local development experience closely matches the CI environment, making development more efficient and predictable.