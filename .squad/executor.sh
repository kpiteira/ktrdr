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
STALL_TIMEOUT=900  # 15 minutes with no progress change = stalled
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
# Detects stalls: if progress doesn't change for STALL_TIMEOUT seconds, abort.
# No fixed timeout — training can take as long as it needs if making progress.
poll_operation() {
    local op_id="$1"
    local last_progress="-1"
    local last_progress_time
    last_progress_time=$(date +%s)
    local consecutive_empty=0
    local max_consecutive_empty=10  # 10 consecutive empty responses (~5 min) = give up

    while true; do
        local status_json
        local raw_output
        raw_output=$(uv run ktrdr --json status "$op_id" 2>/dev/null) || true
        status_json=$(echo "$raw_output" | grep -E '^\{' | tail -1) || true

        if [ -z "$status_json" ]; then
            consecutive_empty=$((consecutive_empty + 1))
            if (( consecutive_empty >= max_consecutive_empty )); then
                log "Operation $op_id: $max_consecutive_empty consecutive empty responses, aborting"
                echo '{"error": "no_response", "operation_id": "'"$op_id"'"}'
                return 1
            fi
            log "Poll: no response for $op_id ($consecutive_empty/$max_consecutive_empty), retrying..."
            sleep "$POLL_INTERVAL"
            continue
        fi
        consecutive_empty=0

        # Parse status and progress
        local status progress
        read -r status progress < <(echo "$status_json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if isinstance(data, dict):
    status = data.get('status', data.get('operation', {}).get('status', 'unknown'))
    progress = data.get('progress', data.get('operation', {}).get('progress', {}))
    if isinstance(progress, dict):
        pct = progress.get('percentage', 0)
    else:
        pct = progress or 0
    print(f'{status} {pct}')
else:
    print('unknown 0')
" 2>/dev/null) || { status="unknown"; progress="0"; }

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
                # Check for stall: has progress changed?
                if [ "$progress" != "$last_progress" ]; then
                    last_progress="$progress"
                    last_progress_time=$(date +%s)
                fi

                local now
                now=$(date +%s)
                local stall_duration=$(( now - last_progress_time ))

                if (( stall_duration >= STALL_TIMEOUT )); then
                    log "Operation $op_id STALLED: progress stuck at ${progress}% for ${stall_duration}s"
                    echo "$status_json"
                    return 1
                fi

                log "Poll: $op_id status=$status progress=${progress}% (last change ${stall_duration}s ago)"
                sleep "$POLL_INTERVAL"
                ;;
        esac
    done
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

# Step 1: Copy strategy YAML to shared directory (skip if already there)
mkdir -p "$SHARED_STRATEGIES"
if [ "$(realpath "$STRATEGY_YAML" 2>/dev/null)" != "$(realpath "$SHARED_STRATEGIES/${NAME}.yaml" 2>/dev/null)" ]; then
    cp "$STRATEGY_YAML" "$SHARED_STRATEGIES/${NAME}.yaml"
fi
log "Strategy at $SHARED_STRATEGIES/${NAME}.yaml"

# Step 2: Validate strategy YAML before training
log "Validating strategy..."
VALIDATE_OUTPUT=$(uv run ktrdr validate "$NAME" 2>&1) || {
    log "Strategy validation FAILED: $NAME"
    echo "{\"error\": \"validation_failed\", \"strategy\": \"$NAME\", \"output\": $(echo "$VALIDATE_OUTPUT" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}"
    exit 1
}
log "Strategy valid: $NAME"

# Step 3: Start training (fire-and-forget)
log "Starting training..."
TRAIN_OUTPUT=$(uv run ktrdr --json train "$NAME" --start "$TRAIN_START" --end "$TRAIN_END" 2>&1) || {
    log "Training command failed"
    echo "{\"error\": \"training_start_failed\", \"output\": $(echo "$TRAIN_OUTPUT" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}"
    exit 1
}

TRAIN_OP_ID=$(extract_op_id "$TRAIN_OUTPUT")
log "Training started: operation=$TRAIN_OP_ID"

# Step 4: Poll training until complete
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

# Step 5: Extract model path from training result
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

# Step 6: Start backtest
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

# Step 7: Poll backtest until complete
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

# Step 8: Assemble structured results
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
