#!/bin/bash
# Script to build Docker development images with optimized caching

set -e  # Exit on error

# Display header
echo "=========================================="
echo "   Building KTRDR Docker Dev Environment "
echo "=========================================="

# Enable Docker BuildKit for better caching
export DOCKER_BUILDKIT=1

# Create Docker build cache directories if they don't exist
mkdir -p .docker_cache/pip
mkdir -p .docker_cache/uv
mkdir -p .docker_cache/npm

# Build backend with cache optimization
echo "Building backend dev image..."
docker build \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  --cache-from ktrdr-backend:dev \
  -f Dockerfile.dev \
  -t ktrdr-backend:dev .

# Build frontend with cache optimization
echo "Building frontend dev image..."
docker build \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  --cache-from ktrdr-frontend:dev \
  -f ktrdr/ui/frontend/Dockerfile.dev \
  -t ktrdr-frontend:dev ./ktrdr/ui/frontend

echo "=========================================="
echo "Build complete! Run './docker_dev.sh start' to start the environment."
echo "=========================================="