#!/bin/bash
#
# Switch Backtesting Mode Script
#
# Usage:
#   ./scripts/switch-backtest-mode.sh local   # Switch to local backtesting (in Docker backend)
#   ./scripts/switch-backtest-mode.sh remote  # Switch to remote backtesting (via backtest-worker)
#

set -e

MODE=$1

if [ -z "$MODE" ]; then
    echo "Usage: $0 [local|remote]"
    echo ""
    echo "Examples:"
    echo "  $0 local   # Switch to local backtesting (backend runs backtests)"
    echo "  $0 remote  # Switch to remote backtesting (backend proxies to backtest-worker)"
    exit 1
fi

cd "$(dirname "$0")/.."

case "$MODE" in
    local)
        echo "🔄 Switching to LOCAL backtesting mode (backend runs backtests)..."
        export USE_REMOTE_BACKTEST_SERVICE=false
        ;;
    remote)
        echo "🔄 Switching to REMOTE backtesting mode (backend proxies to worker)..."
        export USE_REMOTE_BACKTEST_SERVICE=true

        # Verify backtest-worker is running
        if ! docker ps | grep -q ktrdr-backtest-worker; then
            echo "⚠️  Warning: backtest-worker container is not running"
            echo "   Starting backtest-worker..."
            cd docker && docker-compose up -d backtest-worker
            cd ..
            echo "   Waiting for worker to be healthy..."
            sleep 5
        fi
        ;;
    *)
        echo "❌ Invalid mode: $MODE"
        echo "Use 'local' or 'remote'"
        exit 1
        ;;
esac

# Important: Use 'up -d' not 'restart' to apply new environment variables
echo "📦 Recreating backend container with new configuration..."
cd docker && docker-compose up -d backend

echo ""
echo "✅ Backtesting mode switched to: $MODE"
echo ""

if [ "$MODE" = "remote" ]; then
    echo "📋 Verify remote mode:"
    echo "   Backend logs:  docker-compose -f docker/docker-compose.yml logs backend | grep 'Backtesting service initialized'"
    echo "   Worker health: curl http://localhost:5003/health"
    echo ""
    echo "🧪 Test remote mode:"
    echo "   curl -X POST http://localhost:8000/api/v1/backtests/start \\"
    echo "     -H 'Content-Type: application/json' \\"
    echo "     -d '{\"strategy_name\":\"test_e2e_local_pull\",\"symbol\":\"EURUSD\",\"timeframe\":\"1d\",\"start_date\":\"2024-01-01\",\"end_date\":\"2024-06-30\"}'"
else
    echo "📋 Verify local mode:"
    echo "   docker-compose -f docker/docker-compose.yml logs backend | grep 'Backtesting service initialized'"
fi
