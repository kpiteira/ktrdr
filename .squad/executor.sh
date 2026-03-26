#!/usr/bin/env bash
# Squad Experiment Executor
#
# Takes a strategy YAML file path and executes the full train → backtest cycle.
# Polls operation status until completion. Returns structured JSON results.
#
# Usage:
#   .squad/executor.sh <strategy-yaml-path> [train-start] [train-end] [bt-start] [bt-end]
#
# Defaults:
#   train-start: 2015-01-01
#   train-end:   2020-12-31
#   bt-start:    2021-01-01
#   bt-end:      2025-01-01
#
# Output: JSON to stdout with training and backtest results
# Status updates: stderr

set -euo pipefail

STRATEGY_YAML="${1:?Usage: executor.sh <strategy-yaml-path> [train-start] [train-end] [bt-start] [bt-end]}"
TRAIN_START="${2:-2015-01-01}"
TRAIN_END="${3:-2020-12-31}"
BT_START="${4:-2021-01-01}"
BT_END="${5:-2025-01-01}"

SHARED_STRATEGIES="${HOME}/.ktrdr/shared/strategies"
POLL_INTERVAL=30  # seconds between status polls
MAX_POLL_ATTEMPTS=240  # 240 * 30s = 2 hours max
TMPDIR="${TMPDIR:-/tmp}"
TRAIN_RESULT_FILE=$(mktemp "${TMPDIR}/squad-train-XXXXXX.json")
BT_RESULT_FILE=$(mktemp "${TMPDIR}/squad-bt-XXXXXX.json")
trap 'rm -f "$TRAIN_RESULT_FILE" "$BT_RESULT_FILE"' EXIT

# ---------- helpers ----------

log() { echo "[executor] $*" >&2; }

die() { log "ERROR: $*"; exit 1; }

# Extract strategy name from YAML filename (strip path and .yaml extension)
strategy_name() {
    basename "$1" .yaml
}

# Poll an operation until it reaches a terminal state.
# Returns the final status JSON on stdout.
poll_operation() {
    local op_id="$1"
    local attempt=0

    while (( attempt < MAX_POLL_ATTEMPTS )); do
        local status_json
        status_json=$(uv run ktrdr --json status "$op_id" 2>/dev/null) || true

        if [ -z "$status_json" ]; then
            log "Poll $attempt: no response for $op_id, retrying..."
            sleep "$POLL_INTERVAL"
            (( attempt++ )) || true
            continue
        fi

        local status
        status=$(echo "$status_json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
# Handle both direct status and nested operation status
if isinstance(data, dict):
    print(data.get('status', data.get('operation', {}).get('status', 'unknown')))
else:
    print('unknown')
" 2>/dev/null) || status="unknown"

        case "$status" in
            completed|success)
                log "Operation $op_id completed successfully"
                echo "$status_json"
                return 0
                ;;
            failed|error|cancelled)
                log "Operation $op_id ended with status: $status"
                echo "$status_json"
                return 1
                ;;
            *)
                log "Poll $attempt: $op_id status=$status"
                sleep "$POLL_INTERVAL"
                (( attempt++ )) || true
                ;;
        esac
    done

    die "Operation $op_id timed out after $MAX_POLL_ATTEMPTS polls"
}

# Extract operation ID from ktrdr train/backtest output.
# The CLI prints operation_id in its output.
extract_op_id() {
    local output="$1"
    # ktrdr train/backtest prints the operation ID — extract it
    echo "$output" | python3 -c "
import sys, json, re
text = sys.stdin.read()
# Try JSON parse first
try:
    data = json.loads(text)
    if 'operation_id' in data:
        print(data['operation_id'])
        sys.exit(0)
except (json.JSONDecodeError, KeyError):
    pass
# Fallback: regex for op_ pattern
match = re.search(r'(op_[a-zA-Z0-9_-]+)', text)
if match:
    print(match.group(1))
else:
    print('UNKNOWN')
    sys.exit(1)
" 2>/dev/null
}

# ---------- main ----------

NAME=$(strategy_name "$STRATEGY_YAML")
log "Starting experiment: $NAME"
log "Training: $TRAIN_START to $TRAIN_END"
log "Backtest: $BT_START to $BT_END"

# Step 1: Copy strategy YAML to shared directory
mkdir -p "$SHARED_STRATEGIES"
cp "$STRATEGY_YAML" "$SHARED_STRATEGIES/${NAME}.yaml"
log "Strategy written to $SHARED_STRATEGIES/${NAME}.yaml"

# Step 2: Start training (fire-and-forget)
log "Starting training..."
TRAIN_OUTPUT=$(uv run ktrdr --json train "$NAME" --start "$TRAIN_START" --end "$TRAIN_END" 2>&1) || {
    log "Training command failed"
    echo "{\"error\": \"training_start_failed\", \"output\": $(echo "$TRAIN_OUTPUT" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}"
    exit 1
}

TRAIN_OP_ID=$(extract_op_id "$TRAIN_OUTPUT")
log "Training started: operation=$TRAIN_OP_ID"

# Step 3: Poll training until complete
log "Polling training status..."
poll_operation "$TRAIN_OP_ID" > "$TRAIN_RESULT_FILE" || {
    log "Training failed"
    python3 -c "
import json, sys
result = open('$TRAIN_RESULT_FILE').read()
print(json.dumps({'error': 'training_failed', 'operation_id': '$TRAIN_OP_ID', 'output': result}))
"
    exit 1
}
log "Training complete"

# Step 4: Extract model path from training result
MODEL_PATH=$(python3 -c "
import sys, json
data = json.load(open('$TRAIN_RESULT_FILE'))
result = data.get('result', data.get('result_summary', data))
if isinstance(result, dict):
    path = result.get('model_path', result.get('model_dir', ''))
    if path:
        print(path)
        sys.exit(0)
print('models/$NAME/latest')
" 2>/dev/null) || MODEL_PATH="models/${NAME}/latest"

log "Model path: $MODEL_PATH"

# Step 5: Start backtest
log "Starting backtest..."
BT_CMD=(uv run ktrdr --json backtest "$NAME" --start "$BT_START" --end "$BT_END")
if [ -n "$MODEL_PATH" ] && [ "$MODEL_PATH" != "models/${NAME}/latest" ]; then
    BT_CMD+=(--model-path "$MODEL_PATH")
fi

BT_OUTPUT=$("${BT_CMD[@]}" 2>&1) || {
    log "Backtest command failed"
    printf '%s' "$BT_OUTPUT" | python3 -c 'import sys, json; print(json.dumps({"error": "backtest_start_failed", "output": sys.stdin.read()}))'
    exit 1
}

BT_OP_ID=$(extract_op_id "$BT_OUTPUT")
log "Backtest started: operation=$BT_OP_ID"

# Step 6: Poll backtest until complete
log "Polling backtest status..."
poll_operation "$BT_OP_ID" > "$BT_RESULT_FILE" || {
    log "Backtest failed"
    python3 -c "
import json
result = open('$BT_RESULT_FILE').read()
print(json.dumps({'error': 'backtest_failed', 'operation_id': '$BT_OP_ID', 'output': result}))
"
    exit 1
}
log "Backtest complete"

# Step 7: Assemble structured results
python3 -c "
import json

train_result = json.load(open('$TRAIN_RESULT_FILE'))
bt_result = json.load(open('$BT_RESULT_FILE'))

output = {
    'experiment': '$NAME',
    'training': {
        'operation_id': '$TRAIN_OP_ID',
        'start_date': '$TRAIN_START',
        'end_date': '$TRAIN_END',
        'model_path': '$MODEL_PATH',
        'result': train_result
    },
    'backtest': {
        'operation_id': '$BT_OP_ID',
        'start_date': '$BT_START',
        'end_date': '$BT_END',
        'result': bt_result
    }
}

print(json.dumps(output, indent=2))
"

log "Experiment complete: $NAME"
