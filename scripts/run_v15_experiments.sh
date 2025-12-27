#!/bin/bash
# v1.5 Experiment Execution Script
# Runs training on all 27 v1.5 strategies and logs results
#
# Usage: ./scripts/run_v15_experiments.sh [--dry-run] [--resume-from STRATEGY]
#
# Options:
#   --dry-run         Show what would be run without executing
#   --resume-from     Start from a specific strategy (skip earlier ones)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/docs/agentic/v1.5"
LOG_FILE="$LOG_DIR/experiment_results.txt"
EXECUTION_LOG="$LOG_DIR/EXECUTION_LOG.md"

# Parse arguments
DRY_RUN=false
RESUME_FROM=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --resume-from)
      RESUME_FROM="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# All 27 experiment strategies in order
STRATEGIES=(
  # Single Indicator (9)
  "v15_rsi_only"
  "v15_stochastic_only"
  "v15_williams_only"
  "v15_mfi_only"
  "v15_adx_only"
  "v15_aroon_only"
  "v15_cmf_only"
  "v15_rvi_only"
  "v15_di_only"
  # Two Indicator Combinations (11)
  "v15_rsi_adx"
  "v15_rsi_stochastic"
  "v15_rsi_williams"
  "v15_rsi_mfi"
  "v15_rsi_cmf"
  "v15_adx_aroon"
  "v15_adx_di"
  "v15_adx_rsi"
  "v15_stochastic_williams"
  "v15_mfi_cmf"
  "v15_aroon_rvi"
  # Three Indicator Combinations (3)
  "v15_rsi_adx_stochastic"
  "v15_mfi_adx_aroon"
  "v15_williams_stochastic_cmf"
  # Zigzag Threshold Variations (4)
  "v15_rsi_zigzag_1.5"
  "v15_rsi_zigzag_2.0"
  "v15_rsi_zigzag_3.0"
  "v15_rsi_zigzag_3.5"
)

API_URL="http://localhost:8000/api/v1"
POLL_INTERVAL=30  # seconds between status checks

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
  local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
  echo -e "$msg"
  echo "$msg" >> "$LOG_FILE"
}

log_result() {
  local strategy=$1
  local status=$2
  local duration=$3
  local op_id=$4
  local notes=$5

  # Append to results file
  echo "$strategy|$status|$duration|$op_id|$notes" >> "$LOG_FILE.csv"
}

check_backend() {
  local health=$(curl -s "$API_URL/health" | jq -r '.status // .data.status // "error"' 2>/dev/null)
  if [ "$health" != "ok" ]; then
    log "${RED}ERROR: Backend not healthy (status: $health)${NC}"
    exit 1
  fi
}

run_training() {
  local strategy=$1

  log "Starting training: $strategy"

  local start_time=$(date +%s)
  local start_timestamp=$(date '+%Y-%m-%d %H:%M')

  # Start training
  local response=$(curl -s -X POST "$API_URL/trainings/start" \
    -H "Content-Type: application/json" \
    -d "{\"strategy_name\": \"$strategy\", \"symbols\": [\"EURUSD\"], \"timeframes\": [\"1h\"], \"detailed_analytics\": true}")

  local op_id=$(echo "$response" | jq -r '.task_id // empty')

  if [ -z "$op_id" ]; then
    local error=$(echo "$response" | jq -r '.error.message // .detail // .message // "Unknown error"')
    log "${RED}FAILED to start $strategy: $error${NC}"
    log_result "$strategy" "failed" "-" "-" "Failed to start: $error"
    return 1
  fi

  log "  Operation ID: $op_id"

  # Poll for completion
  local status="running"
  local last_progress=""

  while [ "$status" = "running" ] || [ "$status" = "pending" ]; do
    sleep $POLL_INTERVAL

    local status_response=$(curl -s "$API_URL/operations/$op_id")
    status=$(echo "$status_response" | jq -r '.data.status // .status // "unknown"')

    # Show progress if available
    local progress=$(echo "$status_response" | jq -r '.data.progress.percentage // empty')
    local step=$(echo "$status_response" | jq -r '.data.progress.current_step // empty')

    if [ -n "$progress" ] && [ "$progress" != "$last_progress" ]; then
      log "  Progress: ${progress}% - $step"
      last_progress=$progress
    fi
  done

  local end_time=$(date +%s)
  local duration=$((end_time - start_time))
  local duration_min=$((duration / 60))
  local duration_sec=$((duration % 60))
  local duration_str="${duration_min}m ${duration_sec}s"

  if [ "$status" = "completed" ]; then
    log "${GREEN}COMPLETED: $strategy in $duration_str${NC}"
    log_result "$strategy" "completed" "$duration_str" "$op_id" ""
    return 0
  else
    local error=$(echo "$status_response" | jq -r '.data.error // .error // "Unknown error"')
    log "${RED}FAILED: $strategy - $error${NC}"
    log_result "$strategy" "failed" "$duration_str" "$op_id" "$error"
    return 1
  fi
}

# Main execution
main() {
  log "=========================================="
  log "v1.5 Experiment Execution"
  log "Started: $(date)"
  log "=========================================="

  if $DRY_RUN; then
    log "${YELLOW}DRY RUN MODE - No training will be executed${NC}"
  fi

  # Check backend health
  check_backend
  log "Backend health check: OK"

  # Initialize CSV log
  echo "strategy|status|duration|operation_id|notes" > "$LOG_FILE.csv"

  local completed=0
  local failed=0
  local skipped=0
  local skip_until_found=false

  if [ -n "$RESUME_FROM" ]; then
    skip_until_found=true
    log "Resuming from: $RESUME_FROM"
  fi

  for strategy in "${STRATEGIES[@]}"; do
    # Handle resume
    if $skip_until_found; then
      if [ "$strategy" = "$RESUME_FROM" ]; then
        skip_until_found=false
      else
        log "Skipping: $strategy (resuming from $RESUME_FROM)"
        skipped=$((skipped + 1))
        continue
      fi
    fi

    if $DRY_RUN; then
      log "Would run: $strategy"
      continue
    fi

    echo ""
    log "=========================================="
    log "[$((completed + failed + 1))/27] $strategy"
    log "=========================================="

    if run_training "$strategy"; then
      completed=$((completed + 1))
    else
      failed=$((failed + 1))
    fi

    # Brief pause between runs
    sleep 5
  done

  echo ""
  log "=========================================="
  log "EXECUTION COMPLETE"
  log "=========================================="
  log "Completed: $completed"
  log "Failed: $failed"
  log "Skipped: $skipped"
  log "Success rate: $(echo "scale=1; $completed * 100 / ($completed + $failed)" | bc)%"
  log "Finished: $(date)"

  # Summary
  if [ $failed -le 2 ] && [ $completed -ge 25 ]; then
    log "${GREEN}SUCCESS: Met >90% completion target${NC}"
    exit 0
  else
    log "${YELLOW}WARNING: Did not meet >90% completion target${NC}"
    exit 1
  fi
}

main
