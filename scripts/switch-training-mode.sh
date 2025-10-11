#!/bin/bash
#
# Switch Training Mode Script
#
# Usage:
#   ./scripts/switch-training-mode.sh local   # Switch to local (CPU) training
#   ./scripts/switch-training-mode.sh host    # Switch to host service (GPU) training
#

set -e

MODE=$1

if [ -z "$MODE" ]; then
    echo "Usage: $0 [local|host]"
    echo ""
    echo "Examples:"
    echo "  $0 local   # Switch to local training (CPU in Docker)"
    echo "  $0 host    # Switch to host service training (GPU if available)"
    exit 1
fi

cd "$(dirname "$0")/.."

case "$MODE" in
    local)
        echo "🔄 Switching to LOCAL training mode (CPU in Docker)..."
        export USE_TRAINING_HOST_SERVICE=false
        ;;
    host)
        echo "🔄 Switching to HOST SERVICE training mode (GPU if available)..."
        export USE_TRAINING_HOST_SERVICE=true
        ;;
    *)
        echo "❌ Invalid mode: $MODE"
        echo "Use 'local' or 'host'"
        exit 1
        ;;
esac

# Important: Use 'up -d' not 'restart' to apply new environment variables
echo "📦 Recreating backend container with new configuration..."
cd docker && docker-compose up -d backend

echo ""
echo "✅ Training mode switched to: $MODE"
echo ""
echo "📋 View logs to confirm:"
echo "   docker-compose -f docker/docker-compose.yml logs -f backend | grep 'TRAINING MODE'"
