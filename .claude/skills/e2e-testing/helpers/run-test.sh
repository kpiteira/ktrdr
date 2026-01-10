#!/bin/bash
# run-test.sh - Helper for e2e-tester agent
# Usage: ./run-test.sh preflight
#
# Outputs JSON for easy parsing by the agent.
# Exit codes: 0 = all checks passed, 1 = one or more checks failed

set -e

# Load sandbox config if present
[ -f .env.sandbox ] && source .env.sandbox
export API_PORT=${KTRDR_API_PORT:-8000}

case "$1" in
  preflight)
    # Run pre-flight checks, output JSON

    # Check 1: Docker containers
    echo '{"check": "docker", "status": "checking"}'
    # Use table format parsing (more reliable than json across docker compose versions)
    UNHEALTHY=$(docker compose ps --format "table {{.State}}" 2>/dev/null | grep -v "STATE" | grep -v "running" | wc -l | tr -d ' ' || echo "999")
    if [ "$UNHEALTHY" -gt 0 ]; then
      echo '{"check": "docker", "status": "FAILED", "message": "Containers not running"}'
      exit 1
    fi
    echo '{"check": "docker", "status": "PASSED"}'

    # Check 2: Backend API health
    echo '{"check": "api", "status": "checking"}'
    # Use correct health endpoint: /api/v1/health (not /health)
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$API_PORT/api/v1/health" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" != "200" ]; then
      echo "{\"check\": \"api\", \"status\": \"FAILED\", \"message\": \"Backend not responding (HTTP $HTTP_CODE)\"}"
      exit 1
    fi
    echo '{"check": "api", "status": "PASSED"}'

    # Final summary
    echo "{\"preflight\": \"PASSED\", \"api_port\": \"$API_PORT\"}"
    ;;

  *)
    echo '{"error": "Unknown command", "usage": "./run-test.sh preflight"}'
    exit 1
    ;;
esac
