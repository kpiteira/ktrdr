# KTRDR Sandbox Dockerfile
# Isolated environment for Claude Code to run with full permissions
#
# This container provides:
# - Python 3.11+ with uv for dependency management
# - Node.js for Claude Code CLI
# - Docker CLI (daemon runs on host via socket mount)
# - Git for workspace management
# - Claude Code CLI for autonomous task execution

FROM ubuntu:24.04

LABEL org.opencontainers.image.title="KTRDR Sandbox"
LABEL org.opencontainers.image.description="Isolated environment for Claude Code autonomous coding"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Python
    python3 \
    python3-pip \
    python3-venv \
    # Node.js (via nodesource for LTS version)
    curl \
    ca-certificates \
    gnupg \
    # Development tools
    git \
    make \
    jq \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 LTS (required for Claude Code CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI only (daemon runs on host)
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Install uv for Python dependency management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv \
    && mv /root/.local/bin/uvx /usr/local/bin/uvx

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Create workspace directory
RUN mkdir -p /workspace /env/models /env/strategies /env/logs /shared/data

# Copy and setup entrypoint
COPY deploy/docker/sandbox/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set working directory
WORKDIR /workspace

# Use entrypoint script for initialization
ENTRYPOINT ["/entrypoint.sh"]
