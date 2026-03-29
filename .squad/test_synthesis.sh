#!/usr/bin/env bash
# =============================================================================
# Tests for synthesis auto-trigger and context management
# Run: bash .squad/test_synthesis.sh
# =============================================================================

set -euo pipefail

PASS=0
FAIL=0
TEST_DIR=$(mktemp -d)

cleanup() { rm -rf "$TEST_DIR"; }
trap cleanup EXIT

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }

# Source the functions we're testing
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SQUAD_DIR="$REPO_ROOT/.squad"

if [ ! -f "$SQUAD_DIR/loop_lib.sh" ]; then
    echo "FAIL: loop_lib.sh not found (not yet implemented)"
    echo ""
    echo "=========================================="
    echo "Results: 0 passed, 1 failed"
    echo "=========================================="
    exit 1
fi

# shellcheck source=loop_lib.sh
source "$SQUAD_DIR/loop_lib.sh"

# ---------- Test helpers ----------

setup_test_shared_dir() {
    local dir="$TEST_DIR/shared"
    mkdir -p "$dir"/{knowledge,loop,agents/{scribe,director,inventor,quant,critic,engineer,architect,scout}}
    echo "0" > "$dir/loop/iteration-count.txt"
    echo "# Experiments" > "$dir/knowledge/experiments.md"
    echo "# Synthesis" > "$dir/knowledge/synthesis.md"
    echo "$dir"
}

# ---------- Test: needs_synthesis function ----------

echo "=== Test: needs_synthesis ==="

if type needs_synthesis &>/dev/null; then
    # Test: Should NOT need synthesis at cycle 1
    SYNTHESIS_INTERVAL=10
    if needs_synthesis 1 "$SYNTHESIS_INTERVAL" ""; then
        fail "cycle 1 should not trigger synthesis"
    else
        pass "cycle 1 does not trigger synthesis"
    fi

    # Test: Should need synthesis at cycle 10
    if needs_synthesis 10 "$SYNTHESIS_INTERVAL" ""; then
        pass "cycle 10 triggers synthesis"
    else
        fail "cycle 10 should trigger synthesis"
    fi

    # Test: Should need synthesis at cycle 20
    if needs_synthesis 20 "$SYNTHESIS_INTERVAL" ""; then
        pass "cycle 20 triggers synthesis"
    else
        fail "cycle 20 should trigger synthesis"
    fi

    # Test: Should NOT need synthesis at cycle 11
    if needs_synthesis 11 "$SYNTHESIS_INTERVAL" ""; then
        fail "cycle 11 should not trigger synthesis"
    else
        pass "cycle 11 does not trigger synthesis"
    fi

    # Test: Custom interval (5)
    if needs_synthesis 5 5 ""; then
        pass "cycle 5 with interval=5 triggers synthesis"
    else
        fail "cycle 5 with interval=5 should trigger synthesis"
    fi

    # Test: Should NOT need synthesis if synthesis was done recently (last_synthesis within interval)
    if needs_synthesis 10 10 "8"; then
        fail "should not trigger synthesis if last synthesis was at cycle 8 (only 2 cycles ago)"
    else
        pass "skips synthesis when last synthesis was recent"
    fi
else
    echo "  SKIP: needs_synthesis function not defined"
    FAIL=$((FAIL + 1))
fi

# ---------- Test: get_context_for_agent ----------

echo ""
echo "=== Test: get_context_for_agent ==="

if type get_context_for_agent &>/dev/null; then
    SHARED_DIR=$(setup_test_shared_dir)

    # Write some experiments
    for i in $(seq 1 15); do
        echo -e "\n## C$i: Experiment $i\nResults here.\n---" >> "$SHARED_DIR/knowledge/experiments.md"
    done

    # Write a synthesis
    cat > "$SHARED_DIR/knowledge/synthesis.md" <<'EOF'
# Synthesis
Last updated: Cycle 10

## Established Facts
1. Fact one
2. Fact two

## Active Frontiers
- F1: Something

## Dead Ends
- MLP exhausted

## Open Questions
1. Does LSTM work?

## Best Result
C8: Sharpe -0.37
EOF

    # Test: Scribe gets FULL experiments (for synthesis production)
    result=$(get_context_for_agent "scribe" "synthesis" "$SHARED_DIR")
    if echo "$result" | grep -q "C1:.*Experiment 1"; then
        pass "Scribe gets full experiment history during synthesis"
    else
        fail "Scribe should get full experiments during synthesis"
    fi

    # Test: Director gets synthesis + last 5 (not full history)
    result=$(get_context_for_agent "director" "strategize" "$SHARED_DIR")
    if echo "$result" | grep -q "Established Facts" && ! echo "$result" | grep -q "C1:.*Experiment 1"; then
        pass "Director gets synthesis (not full history) post-synthesis"
    else
        fail "Director should get synthesis instead of full history"
    fi

    # Test: Director still sees last 5 experiments
    if echo "$result" | grep -q "C15:.*Experiment 15"; then
        pass "Director sees recent experiments alongside synthesis"
    else
        fail "Director should see last 5 experiments with synthesis"
    fi
else
    echo "  SKIP: get_context_for_agent function not defined"
    FAIL=$((FAIL + 1))
fi

# ---------- Test: trim_history ----------

echo ""
echo "=== Test: trim_history ==="

if type trim_history &>/dev/null; then
    SHARED_DIR=$(setup_test_shared_dir)

    # Write 30 history entries for a single agent
    for i in $(seq 1 30); do
        echo -e "\n## Cycle $i\nLearned something in cycle $i.\n" >> "$SHARED_DIR/agents/critic/history.md"
    done

    ORIGINAL_LINES=$(wc -l < "$SHARED_DIR/agents/critic/history.md")

    trim_history "$SHARED_DIR/agents/critic/history.md" 20

    # Test: history file should now have <= 20 entries
    REMAINING=$(grep -c "^## Cycle" "$SHARED_DIR/agents/critic/history.md")
    if [ "$REMAINING" -le 20 ]; then
        pass "trim_history keeps at most 20 entries ($REMAINING remaining)"
    else
        fail "trim_history should keep <= 20 entries (got $REMAINING)"
    fi

    # Test: archive file should exist
    if [ -f "$SHARED_DIR/agents/critic/history_archive.md" ]; then
        pass "trim_history creates archive file"
    else
        fail "trim_history should create archive file"
    fi

    # Test: most recent entries preserved
    if grep -q "Cycle 30" "$SHARED_DIR/agents/critic/history.md"; then
        pass "most recent entry (Cycle 30) preserved"
    else
        fail "most recent entry should be preserved"
    fi

    # Test: oldest entries archived
    if grep -q "Cycle 1" "$SHARED_DIR/agents/critic/history_archive.md"; then
        pass "oldest entry (Cycle 1) archived"
    else
        fail "oldest entry should be in archive"
    fi
else
    echo "  SKIP: trim_history function not defined"
    FAIL=$((FAIL + 1))
fi

# ---------- Test: estimate_context_tokens ----------

echo ""
echo "=== Test: estimate_context_tokens ==="

if type estimate_context_tokens &>/dev/null; then
    SHARED_DIR=$(setup_test_shared_dir)

    # Write ~1000 words (approx 1300 tokens)
    for i in $(seq 1 200); do
        echo "This is line $i with some words to simulate context content." >> "$SHARED_DIR/knowledge/experiments.md"
    done

    tokens=$(estimate_context_tokens "$SHARED_DIR/knowledge/experiments.md")
    if [ "$tokens" -gt 0 ]; then
        pass "estimate_context_tokens returns positive count ($tokens)"
    else
        fail "estimate_context_tokens should return positive count"
    fi

    # Rough check: ~200 lines * ~12 words * 1.3 tokens/word ≈ 3120 tokens
    if [ "$tokens" -gt 1000 ] && [ "$tokens" -lt 10000 ]; then
        pass "token estimate is in reasonable range ($tokens)"
    else
        fail "token estimate out of range: $tokens (expected 1000-10000)"
    fi
else
    echo "  SKIP: estimate_context_tokens function not defined"
    FAIL=$((FAIL + 1))
fi

# ---------- Test: needs_emergency_synthesis ----------

echo ""
echo "=== Test: needs_emergency_synthesis ==="

if type needs_emergency_synthesis &>/dev/null; then
    # Context limit = 200000, 80% = 160000
    # Simulate under limit
    if needs_emergency_synthesis 100000 200000; then
        fail "100K tokens should not trigger emergency synthesis"
    else
        pass "under 80% does not trigger emergency synthesis"
    fi

    # Simulate over 80%
    if needs_emergency_synthesis 170000 200000; then
        pass "170K tokens triggers emergency synthesis (85% > 80%)"
    else
        fail "170K tokens should trigger emergency synthesis"
    fi
else
    echo "  SKIP: needs_emergency_synthesis function not defined"
    FAIL=$((FAIL + 1))
fi

# ---------- Summary ----------

echo ""
echo "=========================================="
echo "Results: $PASS passed, $FAIL failed"
echo "=========================================="

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
