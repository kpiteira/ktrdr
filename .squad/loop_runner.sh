#!/usr/bin/env bash
# =============================================================================
# Squad Loop Runner — Ralph Pattern
#
# Runs N research cycles autonomously. Each cycle:
#   1. Reads state from disk (knowledge base, agent histories, loop state)
#   2. Invokes `claude -p` with the coordinator prompt (fresh context each cycle)
#   3. Claude runs the squad (ORIENT → STRATEGIZE → DESIGN)
#   4. Extracts strategy YAML from output
#   5. Runs train + backtest via executor.sh
#   6. Invokes `claude -p` for EVALUATE + LEARN (Critic + Quant + Scribe)
#   7. Writes state updates to disk
#   8. Checks should_continue() and loops
#
# Usage:
#   .squad/loop_runner.sh [options]
#
# Options:
#   --max-cycles N       Maximum cycles to run (default: 5)
#   --train-start DATE   Training start date (default: 2015-01-01)
#   --train-end DATE     Training end date (default: 2020-12-31)
#   --bt-start DATE      Backtest start date (default: 2021-01-01)
#   --bt-end DATE        Backtest end date (default: 2025-01-01)
#   --dry-run            Run squad discussion only, skip training/backtest
#   --resume             Resume from last state (skip if current-experiment exists)
#
# All state lives in ~/.ktrdr/shared/squad/ (persists across worktrees).
# Squad machinery (charters, executor) lives in .squad/ (repo).
# =============================================================================

set -euo pipefail

# ---------- defaults ----------

MAX_CYCLES=5
TRAIN_START="2015-01-01"
TRAIN_END="2020-12-31"
BT_START="2021-01-01"
BT_END="2025-01-01"
DRY_RUN=false
RESUME=false

# ---------- paths ----------

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SQUAD_DIR="$REPO_ROOT/.squad"
SHARED_DIR="$HOME/.ktrdr/shared/squad"
STRATEGIES_DIR="$HOME/.ktrdr/shared/strategies"
LOG_DIR="$REPO_ROOT/logs/squad"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"

# ---------- parse args ----------

while [[ $# -gt 0 ]]; do
    case "$1" in
        --max-cycles) MAX_CYCLES="$2"; shift 2 ;;
        --train-start) TRAIN_START="$2"; shift 2 ;;
        --train-end) TRAIN_END="$2"; shift 2 ;;
        --bt-start) BT_START="$2"; shift 2 ;;
        --bt-end) BT_END="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        --resume) RESUME=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ---------- helpers ----------

log() { echo "[loop $(date +%H:%M:%S)] $*" >&2; }
die() { log "FATAL: $*"; exit 1; }

timestamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

# Read current iteration count
get_iteration() {
    local f="$SHARED_DIR/loop/iteration-count.txt"
    if [ -f "$f" ]; then
        cat "$f" | tr -d '[:space:]'
    else
        echo "0"
    fi
}

# Increment iteration count
increment_iteration() {
    local current
    current=$(get_iteration)
    echo $((current + 1)) > "$SHARED_DIR/loop/iteration-count.txt"
}

# Read cadence signal (full_squad / quick_iteration / synthesis / pause)
get_cadence() {
    local f="$SHARED_DIR/loop/cadence.md"
    if [ -f "$f" ]; then
        # Extract the cadence value from the file
        grep -oP '(?<=cadence:\s)(full_squad|quick_iteration|synthesis|pause)' "$f" 2>/dev/null || echo "full_squad"
    else
        echo "full_squad"
    fi
}

# Check if we should continue looping
should_continue() {
    local iteration=$1

    # Check max cycles
    if (( iteration >= MAX_CYCLES )); then
        log "Reached max cycles ($MAX_CYCLES)"
        return 1
    fi

    # Check for pause signal
    local cadence
    cadence=$(get_cadence)
    if [ "$cadence" = "pause" ]; then
        log "Director signaled pause"
        return 1
    fi

    # Check for fatal error marker
    if [ -f "$SHARED_DIR/loop/fatal-error.md" ]; then
        log "Fatal error marker found"
        return 1
    fi

    return 0
}

# Build the prompt for a squad cycle
build_cycle_prompt() {
    local cycle_num=$1
    local cadence=$2

    cat <<PROMPT
You are the Coordinator of a trading research squad. Run one complete research cycle.

## Cycle $cycle_num — Mode: $cadence

## Instructions
Load the squad-coordinator skill and execute one cycle. The skill is at .claude/skills/squad-coordinator/SKILL.md.

Key paths:
- Charters: .squad/agents/{role}/charter.md (repo)
- Knowledge base: ~/.ktrdr/shared/squad/knowledge/ (shared)
- Agent histories: ~/.ktrdr/shared/squad/agents/{role}/history.md (shared)
- Loop state: ~/.ktrdr/shared/squad/loop/ (shared)
- Nudges: ~/.ktrdr/shared/squad/loop/nudges.md (human feedback — read first!)

## Cycle Mode: $cadence
$(if [ "$cadence" = "full_squad" ]; then
    echo "Run the FULL cycle: ORIENT → STRATEGIZE (Scout, Director, Inventor, Quant, Critic) → DESIGN (Engineer, Architect)"
elif [ "$cadence" = "quick_iteration" ]; then
    echo "Run QUICK iteration: Skip ORIENT and STRATEGIZE. Go straight to DESIGN (Engineer designs next variant based on last result and frontiers) → skip Scout/Director/Inventor/Quant/Critic debate"
elif [ "$cadence" = "synthesis" ]; then
    echo "Run SYNTHESIS session: ORIENT (Scribe presents macro patterns) → full squad review → Director recalibrates frontiers. No experiment execution this cycle."
fi)

## Output Requirements

At the end of your cycle, output a clearly delimited block with the experiment specification:

\`\`\`yaml
# SQUAD_EXPERIMENT_SPEC
name: experiment_name_here
... (full v3 strategy YAML)
\`\`\`

And a cadence decision for the next cycle:

\`\`\`
# SQUAD_CADENCE
cadence: full_squad|quick_iteration|synthesis|pause
reason: one line explanation
\`\`\`

And the Scribe's state updates in clearly labeled sections:

\`\`\`markdown
# SQUAD_STATE_UPDATES

## EXPERIMENT_ENTRY
(new entry for experiments.md)

## HYPOTHESIS_UPDATES
(changes to hypotheses.md — new hypotheses, status changes)

## DECISION_UPDATES
(new decisions for decisions.md, if any)

## FRONTIER_UPDATES
(changes to frontiers.md, if any)

## AGENT_HISTORIES
### director
(1-3 sentence learning)
### inventor
(1-3 sentence learning)
### quant
(1-3 sentence learning)
### engineer
(1-3 sentence learning)
### critic
(1-3 sentence learning)
### architect
(1-3 sentence learning)
### scout
(1-3 sentence learning)
### scribe
(1-3 sentence learning)
\`\`\`

These delimited blocks are REQUIRED — the loop runner parses them to update state files.
PROMPT
}

# Build the evaluate+learn prompt (post-experiment)
build_evaluate_prompt() {
    local cycle_num=$1
    local experiment_name=$2
    local results_file=$3

    cat <<PROMPT
You are the Coordinator of a trading research squad. Run the EVALUATE + LEARN phases for Cycle $cycle_num.

## Context
The experiment "$experiment_name" has completed. Results are below.

## Experiment Results
$(cat "$results_file")

## Instructions
1. Load the squad-coordinator skill (.claude/skills/squad-coordinator/SKILL.md)
2. Resume the Critic agent — evaluate results using tiered framework (Tier 1 mandatory)
3. Resume the Quant agent — assess tradability
4. Spawn the Scribe — record everything

Key paths:
- Agent histories: ~/.ktrdr/shared/squad/agents/{role}/history.md
- Knowledge base: ~/.ktrdr/shared/squad/knowledge/
- Last result: ~/.ktrdr/shared/squad/loop/last-result.md

## Output Requirements

Output the cadence decision:
\`\`\`
# SQUAD_CADENCE
cadence: full_squad|quick_iteration|synthesis|pause
reason: one line explanation
\`\`\`

And the Scribe's state updates:
\`\`\`markdown
# SQUAD_STATE_UPDATES

## EXPERIMENT_ENTRY
(new entry for experiments.md — include full metrics)

## HYPOTHESIS_UPDATES
(changes to hypotheses.md)

## DECISION_UPDATES
(new decisions, if any)

## FRONTIER_UPDATES
(changes to frontiers.md, if any)

## AGENT_HISTORIES
### director
(learning)
### inventor
(learning)
... (all participating agents)
\`\`\`
PROMPT
}

# Extract strategy YAML from Claude output
extract_strategy_yaml() {
    local output="$1"
    echo "$output" | python3 -c "
import sys, re
text = sys.stdin.read()
m = re.search(r'# SQUAD_EXPERIMENT_SPEC\n(.*?)(?:\n\`\`\`|\Z)', text, re.DOTALL)
if m:
    print(m.group(1).strip())
"
}

# Extract cadence from Claude output
extract_cadence() {
    local output="$1"
    echo "$output" | python3 -c "
import sys, re
text = sys.stdin.read()
m = re.search(r'# SQUAD_CADENCE\n.*?cadence:\s*(full_squad|quick_iteration|synthesis|pause)', text)
if m:
    print(m.group(1))
"
}

# Extract state updates section from Claude output
extract_state_updates() {
    local output="$1"
    echo "$output" | python3 -c "
import sys, re
text = sys.stdin.read()
m = re.search(r'# SQUAD_STATE_UPDATES\n(.*?)(?:\n\`\`\`|\Z)', text, re.DOTALL)
if m:
    print(m.group(1).strip())
"
}

# Apply state updates to knowledge base files
apply_state_updates() {
    local updates="$1"
    local cycle_num=$2

    # Use Python to parse sections and write updates
    echo "$updates" | python3 -c "
import sys, re, os

text = sys.stdin.read()
shared = os.environ.get('SHARED_DIR', os.path.expanduser('~/.ktrdr/shared/squad'))
cycle = int(os.environ.get('CYCLE_NUM', '$cycle_num'))

def extract_section(name):
    pattern = rf'^## {name}\n(.*?)(?=\n## [A-Z]|\Z)'
    m = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ''

# Experiment entry — append
exp = extract_section('EXPERIMENT_ENTRY')
if exp:
    with open(f'{shared}/knowledge/experiments.md', 'a') as f:
        f.write(f'\n\n---\n\n{exp}\n')
    print('Updated experiments.md', file=sys.stderr)

# Hypothesis updates — append
hyp = extract_section('HYPOTHESIS_UPDATES')
if hyp:
    with open(f'{shared}/knowledge/hypotheses.md', 'a') as f:
        f.write(f'\n\n<!-- Cycle {cycle} updates -->\n{hyp}\n')
    print('Updated hypotheses.md', file=sys.stderr)

# Decision updates — append
dec = extract_section('DECISION_UPDATES')
if dec:
    with open(f'{shared}/knowledge/decisions.md', 'a') as f:
        f.write(f'\n\n{dec}\n')
    print('Updated decisions.md', file=sys.stderr)

# Frontier updates — replace (not append)
front = extract_section('FRONTIER_UPDATES')
if front:
    with open(f'{shared}/knowledge/frontiers.md', 'w') as f:
        f.write(front + '\n')
    print('Updated frontiers.md', file=sys.stderr)

# Agent histories — append per agent
agents_section = extract_section('AGENT_HISTORIES')
if agents_section:
    for agent in ['director','inventor','quant','engineer','critic','architect','scout','scribe']:
        pattern = rf'^### {agent}\n(.*?)(?=\n### [a-z]|\Z)'
        m = re.search(pattern, agents_section, re.MULTILINE | re.DOTALL)
        if m and m.group(1).strip():
            hist_file = f'{shared}/agents/{agent}/history.md'
            with open(hist_file, 'a') as f:
                f.write(f'\n\n## Cycle {cycle}\n{m.group(1).strip()}\n')
    print('Updated agent histories', file=sys.stderr)
" SHARED_DIR="$SHARED_DIR" CYCLE_NUM="$cycle_num"

    log "State updates applied"
}

# Write cadence file
write_cadence() {
    local cadence=$1
    local reason=${2:-""}
    cat > "$SHARED_DIR/loop/cadence.md" <<EOF
# Cadence

cadence: $cadence
reason: $reason
updated: $(timestamp)
EOF
}

# ---------- preflight ----------

log "Squad Loop Runner starting"
log "Max cycles: $MAX_CYCLES"
log "Training: $TRAIN_START to $TRAIN_END"
log "Backtest: $BT_START to $BT_END"
log "Dry run: $DRY_RUN"

# Verify prerequisites
[ -d "$SQUAD_DIR" ] || die ".squad/ directory not found at $REPO_ROOT"
[ -d "$SHARED_DIR" ] || die "Shared squad dir not found at $SHARED_DIR"
command -v "$CLAUDE_BIN" >/dev/null || die "claude CLI not found"

# Create log directory
mkdir -p "$LOG_DIR"

# ---------- main loop ----------

ITERATION=$(get_iteration)
log "Starting from iteration $ITERATION"

while should_continue "$ITERATION"; do
    CYCLE_NUM=$((ITERATION + 1))
    CYCLE_START=$(timestamp)
    CYCLE_LOG="$LOG_DIR/cycle_${CYCLE_NUM}_$(date +%Y%m%d_%H%M%S).log"

    log "=========================================="
    log "CYCLE $CYCLE_NUM starting"
    log "=========================================="

    # Determine cadence
    CADENCE=$(get_cadence)
    log "Cadence: $CADENCE"

    # Skip experiment on synthesis cycles
    if [ "$CADENCE" = "synthesis" ]; then
        log "Synthesis cycle — no experiment execution"
        PROMPT=$(build_cycle_prompt "$CYCLE_NUM" "$CADENCE")

        log "Invoking Claude for synthesis session..."
        CLAUDE_OUTPUT=$("$CLAUDE_BIN" -p \
            --model opus \
            --allowedTools "Agent Read Glob Grep Write Edit Bash WebSearch WebFetch" \
            --permission-mode auto \
            "$PROMPT" 2>>"$CYCLE_LOG") || {
            log "Claude session failed for synthesis cycle $CYCLE_NUM"
            cat "$CYCLE_LOG" >&2
            continue
        }

        # Apply state updates from synthesis
        STATE_UPDATES=$(extract_state_updates "$CLAUDE_OUTPUT")
        if [ -n "$STATE_UPDATES" ]; then
            apply_state_updates "$STATE_UPDATES" "$CYCLE_NUM"
        fi

        # Extract and write cadence
        NEW_CADENCE=$(extract_cadence "$CLAUDE_OUTPUT")
        if [ -n "$NEW_CADENCE" ]; then
            write_cadence "$NEW_CADENCE" "Post-synthesis"
        fi

        increment_iteration
        ITERATION=$(get_iteration)
        log "Synthesis cycle $CYCLE_NUM complete"
        continue
    fi

    # --- PHASE 1: Squad Discussion (ORIENT → STRATEGIZE → DESIGN) ---

    PROMPT=$(build_cycle_prompt "$CYCLE_NUM" "$CADENCE")

    log "Invoking Claude for squad discussion..."
    CLAUDE_OUTPUT=$("$CLAUDE_BIN" -p \
        --model opus \
        --allowedTools "Agent Read Glob Grep Write Edit Bash WebSearch WebFetch" \
        --permission-mode auto \
        "$PROMPT" 2>>"$CYCLE_LOG") || {
        log "Claude session failed for cycle $CYCLE_NUM discussion phase"
        cat "$CYCLE_LOG" >&2
        echo "Discussion phase failed" > "$SHARED_DIR/loop/fatal-error.md"
        break
    }

    # Save full output for debugging
    echo "$CLAUDE_OUTPUT" > "$LOG_DIR/cycle_${CYCLE_NUM}_discussion.md"

    # Extract strategy YAML
    STRATEGY_YAML=$(extract_strategy_yaml "$CLAUDE_OUTPUT")
    if [ -z "$STRATEGY_YAML" ]; then
        log "WARNING: No strategy YAML extracted from cycle $CYCLE_NUM"
        log "Check $LOG_DIR/cycle_${CYCLE_NUM}_discussion.md for details"
        # Try to continue — maybe the squad decided not to run an experiment
        increment_iteration
        ITERATION=$(get_iteration)
        continue
    fi

    # Determine experiment name from YAML
    EXPERIMENT_NAME=$(echo "$STRATEGY_YAML" | grep "^name:" | head -1 | sed 's/name:\s*//' | tr -d '"'"'" | tr -d '[:space:]')
    if [ -z "$EXPERIMENT_NAME" ]; then
        EXPERIMENT_NAME="squad_cycle${CYCLE_NUM}"
    fi
    log "Experiment: $EXPERIMENT_NAME"

    # Write strategy file
    STRATEGY_FILE="$STRATEGIES_DIR/${EXPERIMENT_NAME}.yaml"
    mkdir -p "$STRATEGIES_DIR"
    echo "$STRATEGY_YAML" > "$STRATEGY_FILE"
    log "Strategy written to $STRATEGY_FILE"

    # Update current experiment
    cat > "$SHARED_DIR/loop/current-experiment.md" <<EOF
# Current Experiment

**Cycle:** $CYCLE_NUM
**Name:** $EXPERIMENT_NAME
**Started:** $(timestamp)
**Strategy:** $STRATEGY_FILE
EOF

    # --- PHASE 2: Execute Experiment ---

    if [ "$DRY_RUN" = true ]; then
        log "DRY RUN — skipping training and backtest"
        RESULTS_FILE="$LOG_DIR/cycle_${CYCLE_NUM}_results.json"
        echo '{"dry_run": true, "experiment": "'"$EXPERIMENT_NAME"'"}' > "$RESULTS_FILE"
    else
        log "Executing experiment: train + backtest"
        RESULTS_FILE="$LOG_DIR/cycle_${CYCLE_NUM}_results.json"

        "$SQUAD_DIR/executor.sh" "$STRATEGY_FILE" \
            "$TRAIN_START" "$TRAIN_END" \
            "$BT_START" "$BT_END" \
            > "$RESULTS_FILE" 2>>"$CYCLE_LOG" || {
            log "Executor failed for $EXPERIMENT_NAME"
            # Record failure but don't stop the loop
            echo '{"error": "executor_failed", "experiment": "'"$EXPERIMENT_NAME"'"}' > "$RESULTS_FILE"
        }
    fi

    log "Results saved to $RESULTS_FILE"

    # --- PHASE 3: Evaluate + Learn ---

    EVAL_PROMPT=$(build_evaluate_prompt "$CYCLE_NUM" "$EXPERIMENT_NAME" "$RESULTS_FILE")

    log "Invoking Claude for evaluate + learn..."
    EVAL_OUTPUT=$("$CLAUDE_BIN" -p \
        --model opus \
        --allowedTools "Agent Read Glob Grep Write Edit Bash" \
        --permission-mode auto \
        "$EVAL_PROMPT" 2>>"$CYCLE_LOG") || {
        log "Claude session failed for cycle $CYCLE_NUM evaluate phase"
        # Don't fatal — we still have results, just missing evaluation
    }

    # Save eval output
    echo "$EVAL_OUTPUT" > "$LOG_DIR/cycle_${CYCLE_NUM}_evaluate.md"

    # --- PHASE 4: Apply State Updates ---

    STATE_UPDATES=$(extract_state_updates "$EVAL_OUTPUT")
    if [ -n "$STATE_UPDATES" ]; then
        apply_state_updates "$STATE_UPDATES" "$CYCLE_NUM"
    else
        log "WARNING: No state updates extracted from evaluate phase"
    fi

    # Extract and write cadence for next cycle
    NEW_CADENCE=$(extract_cadence "$EVAL_OUTPUT")
    if [ -n "$NEW_CADENCE" ]; then
        CADENCE_REASON=$(echo "$EVAL_OUTPUT" | grep -A1 "# SQUAD_CADENCE" | grep "reason:" | sed 's/.*reason:\s*//')
        write_cadence "$NEW_CADENCE" "$CADENCE_REASON"
        log "Next cycle cadence: $NEW_CADENCE"
    fi

    # Write last result summary
    cat > "$SHARED_DIR/loop/last-result.md" <<EOF
# Last Result

## Cycle $CYCLE_NUM — $EXPERIMENT_NAME

**Date:** $(timestamp)
**Strategy:** $STRATEGY_FILE
**Results file:** $RESULTS_FILE

$(cat "$RESULTS_FILE" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if 'error' in data:
        print(f'**Status:** FAILED — {data[\"error\"]}')
    elif 'dry_run' in data:
        print('**Status:** DRY RUN — no execution')
    else:
        bt = data.get('backtest', {}).get('result', {})
        metrics = bt.get('result_summary', bt).get('metrics', {})
        print(f'**Trades:** {metrics.get(\"total_trades\", \"?\")}')
        print(f'**Win Rate:** {metrics.get(\"win_rate\", \"?\"):.1%}' if isinstance(metrics.get('win_rate'), (int, float)) else f'**Win Rate:** {metrics.get(\"win_rate\", \"?\")}')
        print(f'**Sharpe:** {metrics.get(\"sharpe_ratio\", \"?\")}')
        print(f'**Total Return:** {metrics.get(\"total_return_pct\", \"?\"):.2%}' if isinstance(metrics.get('total_return_pct'), (int, float)) else f'**Total Return:** {metrics.get(\"total_return_pct\", \"?\")}')
except Exception as e:
    print(f'**Status:** Could not parse results — {e}')
" 2>/dev/null)
EOF

    # Clear current experiment
    echo "# Current Experiment" > "$SHARED_DIR/loop/current-experiment.md"
    echo "" >> "$SHARED_DIR/loop/current-experiment.md"
    echo "_No active experiment._" >> "$SHARED_DIR/loop/current-experiment.md"

    # Increment iteration
    increment_iteration
    ITERATION=$(get_iteration)

    CYCLE_END=$(timestamp)
    log "Cycle $CYCLE_NUM complete ($CYCLE_START → $CYCLE_END)"
    log "Iteration count: $ITERATION / $MAX_CYCLES"
    log ""
done

log "=========================================="
log "Loop complete. Ran $ITERATION iterations."
log "=========================================="
