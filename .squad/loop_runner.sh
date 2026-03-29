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
#   --no-pause           Ignore Director's pause signal and keep looping
#   --synthesis-interval N  Run synthesis every N cycles (default: 10)
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
IGNORE_PAUSE=false
SYNTHESIS_INTERVAL=10
CONTEXT_LIMIT=200000

# ---------- paths ----------

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SQUAD_DIR="$REPO_ROOT/.squad"
SHARED_DIR="${SQUAD_SHARED_DIR:-$HOME/.ktrdr/shared/squad}"
STRATEGIES_DIR="${SQUAD_STRATEGIES_DIR:-$HOME/.ktrdr/shared/strategies}"
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
        --no-pause) IGNORE_PAUSE=true; shift ;;
        --synthesis-interval)
            if [[ $# -lt 2 ]]; then
                echo "Error: --synthesis-interval requires a positive integer argument" >&2
                exit 1
            fi
            if ! [[ "$2" =~ ^[1-9][0-9]*$ ]]; then
                echo "Error: --synthesis-interval must be a positive integer (got: '$2')" >&2
                exit 1
            fi
            SYNTHESIS_INTERVAL="$2"
            shift 2
            ;;
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
        # Extract the cadence value (portable — no grep -P)
        awk '$1 == "cadence:" { print $2 }' "$f" 2>/dev/null | head -1 || echo "full_squad"
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
        if [ "$IGNORE_PAUSE" = true ]; then
            log "Director signaled pause (IGNORED — --no-pause active)"
        else
            log "Director signaled pause"
            return 1
        fi
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

**IMPORTANT:** The skill's templates reference \`~/.ktrdr/shared/squad/\` as the default shared directory. In this session, use the paths below instead — they override the skill's defaults. Wherever the skill says \`~/.ktrdr/shared/squad/\`, substitute \`$SHARED_DIR/\`.

Key paths:
- Charters: .squad/agents/{role}/charter.md (repo)
- Knowledge base: $SHARED_DIR/knowledge/ (shared)
- Agent histories: $SHARED_DIR/agents/{role}/history.md (shared)
- Scout files: $SHARED_DIR/agents/scout/{bibliography,reading-queue}.md
- External insights: $SHARED_DIR/roadmap/external-insights.md
- Capability gaps: $SHARED_DIR/roadmap/capability-gaps.md
- Build queue: $SHARED_DIR/roadmap/build-queue.md
- Loop state: $SHARED_DIR/loop/ (shared)
- Nudges: $SHARED_DIR/loop/nudges.md (human feedback — read first!)

## Newly Resolved Capabilities
$(if [ -f "$SHARED_DIR/loop/newly-resolved-issues.txt" ]; then
    echo "The following capability gaps have been resolved since the last cycle (GitHub issues closed):"
    echo ""
    while IFS='|' read -r num title; do
        echo "- **#$num**: $title"
    done < "$SHARED_DIR/loop/newly-resolved-issues.txt"
    echo ""
    echo "The Architect should mark these as RESOLVED in capability-gaps.md and the Scribe should update components.md with the new capabilities."
else
    echo "No new capabilities resolved since last cycle."
fi)

## Context Management

**Post-synthesis context rules apply.** When providing experiment context to agents:
- Most agents receive: synthesis.md + last 5 experiments from experiments.md (NOT full experiments.md)
- Exception: Scribe during SYNTHESIZE gets full experiments.md
- Check if $SHARED_DIR/knowledge/synthesis.md has content beyond the header. If yes, use synthesis-based context.
- This is critical for scaling — full experiments.md is ~$(wc -l < "$SHARED_DIR/knowledge/experiments.md" 2>/dev/null || echo "?") lines and growing.

## Cycle Mode: $cadence
$(if [ "$cadence" = "full_squad" ]; then
    echo "Run the FULL cycle: ORIENT → STRATEGIZE (Scout, Director, Inventor, Quant, Critic) → DESIGN (Engineer, Architect)"
elif [ "$cadence" = "quick_iteration" ]; then
    echo "Run QUICK iteration: Skip ORIENT and STRATEGIZE. Go straight to DESIGN (Engineer designs next variant based on last result and frontiers) → skip Scout/Director/Inventor/Quant/Critic debate"
elif [ "$cadence" = "synthesis" ]; then
    echo "Run SYNTHESIS session: Follow the 'Synthesis Session' instructions in the coordinator skill. Scribe gets FULL experiments.md to produce fresh synthesis.md. Then Director recalibrates frontiers. No experiment execution this cycle."
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

These delimited blocks are REQUIRED — the evaluate phase will use them to write state updates directly to the knowledge base files.
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
1. Spawn the Critic agent — evaluate results using tiered framework (Tier 1 mandatory). Give the Critic its charter (.squad/agents/critic/charter.md), history ($SHARED_DIR/agents/critic/history.md), and the results above.
2. Spawn the Quant agent — assess tradability. Give the Quant its charter, history, and the results + Critic evaluation.
3. Spawn the Scribe agent — record everything.

## CRITICAL: Write State Updates Directly to Files

After the agents have spoken, YOU (the Coordinator) must update the knowledge base files directly using the Edit tool. Do NOT output structured blocks for parsing — write to the files yourself.

**Files to update (all in $SHARED_DIR/):**

1. **knowledge/experiments.md** — APPEND a new entry at the end for this cycle. Include: experiment name, date, hypothesis, setup, results table, assessment, verdict.

2. **knowledge/hypotheses.md** — APPEND any new hypotheses or status changes at the end.

3. **knowledge/decisions.md** — APPEND any new decisions (D-numbered) at the end. Only if this cycle established something new.

4. **knowledge/frontiers.md** — UPDATE frontier statuses if the Director's assessment changed them.

5. **agents/{role}/history.md** — APPEND a "## Cycle $cycle_num" section to each participating agent's history with 1-3 sentences of what they learned.

6. **roadmap/external-insights.md** — UPDATE insight statuses: mark any insight that influenced this experiment's design as CITED (if referenced) or TESTED (if directly tested). Leave other statuses unchanged. If the file doesn't exist or is empty, skip.

7. **roadmap/capability-gaps.md** — If the Architect filed new gaps during DESIGN, verify they were persisted. If any capabilities were newly resolved (check \`$SHARED_DIR/loop/newly-resolved-issues.txt\`), mark the corresponding GAP entries as RESOLVED.

8. **roadmap/build-queue.md** — UPDATE status for any resolved issues (OPEN → RESOLVED). Add any new entries from the Architect.

9. **knowledge/components.md** — If any capabilities were resolved, add the new capability to the appropriate section.

10. **loop/last-result.md** — OVERWRITE with this cycle's result summary.

11. **loop/cadence.md** — OVERWRITE with the cadence decision for the next cycle:
   \`\`\`
   # Cadence

   cadence: full_squad|quick_iteration|synthesis|pause
   reason: one line explanation
   updated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
   \`\`\`

**Rules:**
- APPEND means add to the end of the file. Never overwrite existing content in experiments.md, hypotheses.md, decisions.md, or history.md.
- Read each file first before editing so you know what's already there.
- Use the Edit tool (not Write) for append operations to avoid clobbering.
- If you can't update a file for any reason, log what you would have written so it's not lost.
PROMPT
}

# Extract strategy YAML from Claude output (first document only if multi-doc)
extract_strategy_yaml() {
    local output="$1"
    echo "$output" | python3 -c "
import sys, re
text = sys.stdin.read()
m = re.search(r'# SQUAD_EXPERIMENT_SPEC\n(.*?)(?:\n\`\`\`|\Z)', text, re.DOTALL)
if m:
    yaml_text = m.group(1).strip()
    # If multi-document YAML (contains ---), take only the first document
    if '\n---\n' in yaml_text:
        yaml_text = yaml_text.split('\n---\n')[0].strip()
    # Also strip any trailing comments that aren't valid YAML
    lines = []
    for line in yaml_text.split('\n'):
        # Stop at lines that look like execution instructions, not YAML
        if line.startswith('# --- ') and ('CONTROL' in line or 'EXECUTION' in line or 'SUCCESS' in line):
            break
        lines.append(line)
    print('\n'.join(lines).strip())
"
}

# (Cadence is now written directly by Claude to $SHARED_DIR/loop/cadence.md)

# (State updates are now written directly by Claude during the evaluate phase.
#  No parsing or applying needed — Claude uses Edit/Write tools on the files.)

# (Cadence file is now written directly by Claude during evaluate phase)

# ---------- preflight ----------

log "Squad Loop Runner starting"
log "Max cycles: $MAX_CYCLES"
log "Training: $TRAIN_START to $TRAIN_END"
log "Backtest: $BT_START to $BT_END"
log "Dry run: $DRY_RUN"
log "Synthesis interval: every $SYNTHESIS_INTERVAL cycles"

# Verify prerequisites
[ -d "$SQUAD_DIR" ] || die ".squad/ directory not found at $REPO_ROOT"
[ -f "$SQUAD_DIR/loop_lib.sh" ] || die "loop_lib.sh not found at $SQUAD_DIR/loop_lib.sh"
[ -d "$SHARED_DIR" ] || die "Shared squad dir not found at $SHARED_DIR"
command -v "$CLAUDE_BIN" >/dev/null || die "claude CLI not found"

# Source shared functions (after preflight confirms .squad/ exists)
source "$SQUAD_DIR/loop_lib.sh"

# Create log directory
mkdir -p "$LOG_DIR"

# Ensure GitHub labels exist for squad capability issues
ensure_squad_labels() {
    if ! command -v gh >/dev/null 2>&1; then
        log "WARNING: gh CLI not found — GitHub issue creation will be skipped"
        return 0
    fi

    cd "$REPO_ROOT"
    gh label create "squad:architect" --description "Capability gap identified by Research Squad Architect" --color "7057ff" 2>/dev/null || true
    gh label create "capability-gap" --description "Missing capability blocking squad experiments" --color "d4c5f9" 2>/dev/null || true
    log "GitHub labels verified"
}

# Check for recently closed squad:architect issues and update knowledge base
check_resolved_capabilities() {
    if ! command -v gh >/dev/null 2>&1; then
        return 0
    fi

    local gaps_file="$SHARED_DIR/roadmap/capability-gaps.md"
    local resolved_count=0

    # Find closed issues with squad:architect label (latest 50)
    local closed_issues
    closed_issues=$(cd "$REPO_ROOT" && gh issue list --label "squad:architect" --state closed --json number,title --limit 50 2>/dev/null) || return 0

    if [ -z "$closed_issues" ] || [ "$closed_issues" = "[]" ]; then
        return 0
    fi

    # For each closed issue, check if it's already marked RESOLVED in capability-gaps.md
    while IFS='|' read -r issue_num issue_title; do
        [ -z "$issue_num" ] && continue
        log "Resolved capability: #$issue_num — $issue_title"
        resolved_count=$((resolved_count + 1))

        # Note: The actual file updates (marking RESOLVED in capability-gaps.md,
        # updating build-queue.md status, adding to components.md) are done by
        # the Claude evaluate phase, which has Edit/Write tools. We just log here
        # so the cycle prompt can include the notification.
        echo "$issue_num|$issue_title" >> "$SHARED_DIR/loop/newly-resolved-issues.txt"
    done < <(echo "$closed_issues" | python3 -c "
import sys, json

issues = json.load(sys.stdin)
if not issues:
    sys.exit(0)

gaps_path = '$gaps_file'
try:
    with open(gaps_path, 'r') as f:
        gaps_content = f.read()
except FileNotFoundError:
    sys.exit(0)

for issue in issues:
    num = issue['number']
    title = issue['title']
    # Check if this issue number is already marked RESOLVED
    if f'#{num}' in gaps_content and 'RESOLVED' in gaps_content.split(f'#{num}')[0].split('###')[-1]:
        continue
    # Check if this issue number appears in gaps at all
    if f'#{num}' in gaps_content:
        print(f\"{num}|{title}\")
")

    if [ "$resolved_count" -gt 0 ]; then
        log "Found $resolved_count newly resolved capability issues"
    fi
}

ensure_squad_labels

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

    # Check for resolved capabilities before each cycle
    rm -f "$SHARED_DIR/loop/newly-resolved-issues.txt"
    check_resolved_capabilities

    # Determine cadence
    CADENCE=$(get_cadence)

    # Auto-trigger synthesis if interval reached (overrides cadence)
    LAST_SYNTH=$(get_last_synthesis_cycle "$SHARED_DIR")
    if needs_synthesis "$CYCLE_NUM" "$SYNTHESIS_INTERVAL" "$LAST_SYNTH"; then
        log "Auto-triggering synthesis (interval=$SYNTHESIS_INTERVAL, last=$LAST_SYNTH)"
        CADENCE="synthesis"
    fi

    # Emergency synthesis: check context budget
    EXPERIMENTS_TOKENS=$(estimate_context_tokens "$SHARED_DIR/knowledge/experiments.md")
    if needs_emergency_synthesis "$EXPERIMENTS_TOKENS" "$CONTEXT_LIMIT" && [ "$CADENCE" != "synthesis" ]; then
        log "EMERGENCY: experiments.md at ~${EXPERIMENTS_TOKENS} tokens (limit=${CONTEXT_LIMIT}, threshold=80%)"
        log "Forcing synthesis cycle to prevent context overflow"
        CADENCE="synthesis"
    fi

    log "Cadence: $CADENCE"

    # Skip experiment on synthesis cycles
    if [ "$CADENCE" = "synthesis" ]; then
        log "Synthesis cycle — no experiment execution"
        PROMPT=$(build_cycle_prompt "$CYCLE_NUM" "$CADENCE")

        # Write prompt to temp file to avoid ARG_MAX limit
        SYNTH_PROMPT_FILE=$(mktemp "${TMPDIR:-/tmp}/squad-synth-prompt-XXXXXX")
        echo "$PROMPT" > "$SYNTH_PROMPT_FILE"

        log "Invoking Claude for synthesis session..."
        CLAUDE_OUTPUT=$(cat "$SYNTH_PROMPT_FILE" | "$CLAUDE_BIN" -p \
            --model opus \
            --allowedTools "Agent Read Glob Grep Write Edit Bash WebSearch WebFetch" \
            --permission-mode auto \
            2>>"$CYCLE_LOG") || {
            log "Claude session failed for synthesis cycle $CYCLE_NUM"
            rm -f "$SYNTH_PROMPT_FILE"
            cat "$CYCLE_LOG" >&2
            continue
        }
        rm -f "$SYNTH_PROMPT_FILE"

        # State updates and cadence are written directly by Claude during synthesis
        log "Synthesis state updates written by Claude"

        increment_iteration
        ITERATION=$(get_iteration)
        log "Synthesis cycle $CYCLE_NUM complete"
        continue
    fi

    # --- CHECK FOR PENDING EXPERIMENT (resume after executor failure) ---

    PENDING_STRATEGY=""
    PENDING_NAME=""
    CURRENT_EXP="$SHARED_DIR/loop/current-experiment.md"

    if [ -f "$CURRENT_EXP" ] && grep -q "^\\*\\*Strategy:\\*\\*" "$CURRENT_EXP"; then
        PENDING_STRATEGY=$(grep "^\\*\\*Strategy:\\*\\*" "$CURRENT_EXP" | sed 's/.*\*\*Strategy:\*\* //')
        PENDING_NAME=$(grep "^\\*\\*Name:\\*\\*" "$CURRENT_EXP" | sed 's/.*\*\*Name:\*\* //')

        if [ -n "$PENDING_STRATEGY" ] && [ -f "$PENDING_STRATEGY" ]; then
            log "RESUMING pending experiment: $PENDING_NAME ($PENDING_STRATEGY)"
            log "Skipping discussion — experiment was already designed"
            EXPERIMENT_NAME="$PENDING_NAME"
            STRATEGY_FILE="$PENDING_STRATEGY"
        else
            PENDING_STRATEGY=""  # File doesn't exist, run normal discussion
        fi
    fi

    # --- PHASE 1: Squad Discussion (only if no pending experiment) ---

    if [ -z "$PENDING_STRATEGY" ]; then
        PROMPT=$(build_cycle_prompt "$CYCLE_NUM" "$CADENCE")

        # Write prompt to temp file to avoid ARG_MAX limit
        DISCUSS_PROMPT_FILE=$(mktemp "${TMPDIR:-/tmp}/squad-discuss-prompt-XXXXXX")
        echo "$PROMPT" > "$DISCUSS_PROMPT_FILE"

        log "Invoking Claude for squad discussion..."
        CLAUDE_OUTPUT=$(cat "$DISCUSS_PROMPT_FILE" | "$CLAUDE_BIN" -p \
            --model opus \
            --allowedTools "Agent Read Glob Grep Write Edit Bash WebSearch WebFetch" \
            --permission-mode auto \
            2>>"$CYCLE_LOG") || {
            log "Claude session failed for cycle $CYCLE_NUM discussion phase"
            rm -f "$DISCUSS_PROMPT_FILE"
            cat "$CYCLE_LOG" >&2
            echo "Discussion phase failed" > "$SHARED_DIR/loop/fatal-error.md"
            break
        }
        rm -f "$DISCUSS_PROMPT_FILE"

        # Save full output for debugging
        echo "$CLAUDE_OUTPUT" > "$LOG_DIR/cycle_${CYCLE_NUM}_discussion.md"

        # Extract strategy YAML
        STRATEGY_YAML=$(extract_strategy_yaml "$CLAUDE_OUTPUT")
        if [ -z "$STRATEGY_YAML" ]; then
            log "WARNING: No strategy YAML extracted from cycle $CYCLE_NUM"
            log "Check $LOG_DIR/cycle_${CYCLE_NUM}_discussion.md for details"
            increment_iteration
            ITERATION=$(get_iteration)
            continue
        fi

        # Reject non-v3 strategies (manual analysis protocols, diagnostic specs, etc.)
        if ! echo "$STRATEGY_YAML" | grep -q '^version:.*3\.0'; then
            log "WARNING: Cycle $CYCLE_NUM produced non-v3 strategy (missing version: 3.0). Skipping."
            log "The squad must produce executable v3 strategy YAMLs, not manual analysis protocols."
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
    fi

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

    # Write prompt to temp file to avoid ARG_MAX limit (results JSON can be large)
    EVAL_PROMPT_FILE=$(mktemp "${TMPDIR:-/tmp}/squad-eval-prompt-XXXXXX")
    echo "$EVAL_PROMPT" > "$EVAL_PROMPT_FILE"

    log "Invoking Claude for evaluate + learn..."
    EVAL_OUTPUT=$(cat "$EVAL_PROMPT_FILE" | "$CLAUDE_BIN" -p \
        --model opus \
        --allowedTools "Agent Read Glob Grep Write Edit Bash" \
        --permission-mode auto \
        2>>"$CYCLE_LOG") || {
        log "Claude session failed for cycle $CYCLE_NUM evaluate phase"
        # Don't fatal — we still have results, just missing evaluation
    }
    rm -f "$EVAL_PROMPT_FILE"

    # Save eval output
    echo "$EVAL_OUTPUT" > "$LOG_DIR/cycle_${CYCLE_NUM}_evaluate.md"

    # --- PHASE 4: Verify State Updates ---
    # Claude wrote directly to the knowledge base files during evaluate.
    # Just verify key files were modified.

    EXPERIMENTS_MOD=$(stat -f %m "$SHARED_DIR/knowledge/experiments.md" 2>/dev/null || echo "0")
    if [ "$EXPERIMENTS_MOD" -gt "$(($(date +%s) - 300))" ] 2>/dev/null; then
        log "State updates verified: experiments.md was recently modified"
    else
        log "WARNING: experiments.md was NOT updated during evaluate phase"
    fi

    # Trim agent histories (keep last 20 entries, archive older)
    for agent_dir in "$SHARED_DIR"/agents/*/; do
        local_history="$agent_dir/history.md"
        if [ -f "$local_history" ]; then
            trim_history "$local_history" 20
        fi
    done

    # Log context budget
    TOTAL_CONTEXT=0
    for agent in director inventor quant critic engineer scribe scout architect; do
        AGENT_TOKENS=$(estimate_agent_context "$SHARED_DIR" "$agent")
        TOTAL_CONTEXT=$(( TOTAL_CONTEXT > AGENT_TOKENS ? TOTAL_CONTEXT : AGENT_TOKENS ))
    done
    log "Context budget: max agent ~${TOTAL_CONTEXT} tokens (limit=${CONTEXT_LIMIT})"

    # Read cadence from file (Claude should have written it)
    NEW_CADENCE=$(get_cadence)
    log "Next cycle cadence: $NEW_CADENCE"

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
