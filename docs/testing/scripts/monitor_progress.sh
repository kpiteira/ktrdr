#!/bin/bash
# Monitor operation progress
# Usage: ./monitor_progress.sh <operation_id> [interval_seconds] [max_polls]
#
# Examples:
#   ./monitor_progress.sh op_data_load_20251028_123456 10 12
#   ./monitor_progress.sh op_training_20251028_123456 5 20

set -e

OPERATION_ID="$1"
INTERVAL="${2:-5}"  # Default 5 seconds
MAX_POLLS="${3:-20}"  # Default 20 polls

if [ -z "$OPERATION_ID" ]; then
  echo "Usage: $0 <operation_id> [interval_seconds] [max_polls]"
  echo "Example: $0 op_data_load_20251028_123456 10 12"
  exit 1
fi

echo "Monitoring operation: $OPERATION_ID"
echo "Polling every ${INTERVAL}s, max ${MAX_POLLS} polls"
echo "========================================"
echo ""

for i in $(seq 1 $MAX_POLLS); do
  ELAPSED=$((i * INTERVAL))
  echo "=== Poll $i (${ELAPSED}s) ==="

  RESPONSE=$(curl -s "http://localhost:8000/api/v1/operations/$OPERATION_ID")
  STATUS=$(echo "$RESPONSE" | jq -r '.data.status')

  echo "$RESPONSE" | jq '{
    status: .data.status,
    percentage: .data.progress.percentage,
    step: .data.progress.current_step,
    items: .data.progress.items_processed
  }'

  # Stop if completed or failed
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    echo ""
    echo "Operation finished with status: $STATUS"
    break
  fi

  echo ""

  # Don't sleep after last poll
  if [ $i -lt $MAX_POLLS ]; then
    sleep $INTERVAL
  fi
done

echo "========================================"
echo "Final status check:"
curl -s "http://localhost:8000/api/v1/operations/$OPERATION_ID" | jq '{
  status: .data.status,
  percentage: .data.progress.percentage,
  result_summary: .data.result_summary
}'
