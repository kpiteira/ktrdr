# Test: squad/m3-debate-genuine-revision

**Purpose:** Validate the Director's multi-turn debate relay: Engineer designs a strategy, Critic challenges it, Director synthesizes Critic's concern and relays to Engineer, Engineer produces a measurably revised strategy. Proves the debate loop produces genuine revision (not rubber-stamping) and that debate metadata is captured in CycleResult.

**Duration:** ~20-45 minutes (1 cycle with debate adds ~5-10 min over baseline)

**Category:** Squad / Conversational Orchestrator / M3

**Estimated cost:** ~$3-8 (1 Director session + Engineer multi-turn + Critic + Scribe)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) -- Docker, sandbox (slot 1, port 8001), API health

**Test-specific checks:**

- [ ] Sandbox running on slot 1 (port 8001)

```bash
source .env.sandbox
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${KTRDR_API_PORT}/api/v1/health)
if [ "$HTTP_CODE" != "200" ]; then
  echo "FAIL: Backend API not responding on port ${KTRDR_API_PORT} (HTTP $HTTP_CODE)"
  exit 1
fi
echo "OK: Backend API healthy on port ${KTRDR_API_PORT}"
```

- [ ] KB files exist at shared dir

```bash
SHARED="$HOME/.ktrdr/shared/squad"
MISSING=""
for KB_FILE in knowledge/experiments.md knowledge/hypotheses.md knowledge/decisions.md knowledge/frontiers.md knowledge/synthesis.md loop/cadence.md loop/nudges.md; do
  if [ ! -f "$SHARED/$KB_FILE" ]; then
    MISSING="$MISSING $KB_FILE"
  fi
done

if [ -n "$MISSING" ]; then
  echo "FAIL: Missing KB files:$MISSING"
  exit 1
fi
echo "OK: All KB files present"
```

- [ ] Claude Code CLI available

```bash
if ! which claude >/dev/null 2>&1; then
  echo "FAIL: claude CLI not found in PATH"
  exit 1
fi
echo "OK: claude CLI available at $(which claude)"
```

- [ ] Executor script exists and is executable

```bash
if [ ! -x ".squad/executor.sh" ]; then
  echo "FAIL: .squad/executor.sh not found or not executable"
  exit 1
fi
echo "OK: executor.sh exists and is executable"
```

- [ ] All 8 agent charters present (director + 7 consultants)

```bash
MISSING=""
for AGENT in director engineer scribe quant inventor scout critic architect; do
  if [ ! -f ".squad/agents/${AGENT}/charter.md" ]; then
    MISSING="$MISSING $AGENT"
  fi
done

if [ -n "$MISSING" ]; then
  echo "FAIL: Missing charters:$MISSING"
  exit 1
fi
echo "OK: All 8 agent charters present"
```

- [ ] Critic charter contains adversarial/challenge guidance

```bash
if ! grep -qi "challenge\|adversarial\|rigor\|tier" .squad/agents/critic/charter.md; then
  echo "FAIL: Critic charter lacks challenge/adversarial language -- may not produce substantive critiques"
  exit 1
fi
echo "OK: Critic charter contains adversarial guidance"
```

- [ ] Strategies dir exists and is writable

```bash
STRAT_DIR="$HOME/.ktrdr/shared/strategies"
mkdir -p "$STRAT_DIR"
if [ ! -w "$STRAT_DIR" ]; then
  echo "FAIL: Cannot write to $STRAT_DIR"
  exit 1
fi
echo "OK: Strategies directory writable"
```

- [ ] CycleState has debate tracking methods

```bash
python3 -c "
import sys
sys.path.insert(0, '.squad')
from squad_engine.squad_tools import CycleState
cs = CycleState()
assert hasattr(cs, 'record_debate'), 'Missing record_debate method'
assert hasattr(cs, 'record_debate_turn'), 'Missing record_debate_turn method'
assert hasattr(cs, 'debates'), 'Missing debates field'
assert hasattr(cs, 'debate_pairs'), 'Missing debate_pairs field'
print('OK: CycleState has debate tracking (record_debate, record_debate_turn, debates, debate_pairs)')
"
```

- [ ] CycleResult has debates field

```bash
python3 -c "
import sys
sys.path.insert(0, '.squad')
from squad_engine.loop import CycleResult
cr = CycleResult(iteration=0)
assert hasattr(cr, 'debates'), 'Missing debates field'
assert hasattr(cr, 'conversation_log'), 'Missing conversation_log field'
print('OK: CycleResult has debates and conversation_log fields')
"
```

---

## Execution Steps

### Phase 1: Snapshot Pre-Cycle State

Capture baseline state so we can diff strategies and KB after the cycle.

#### 1.1 Record Baseline and Set Cadence to full_squad

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
STRAT_DIR="$HOME/.ktrdr/shared/strategies"

# Count existing strategy files
STRAT_COUNT_BEFORE=$(ls "$STRAT_DIR"/*.yaml 2>/dev/null | wc -l | tr -d ' ')
echo "Strategies before: $STRAT_COUNT_BEFORE"

# Snapshot all existing strategy names and their checksums
ls "$STRAT_DIR"/*.yaml 2>/dev/null | while read f; do
  echo "$(basename "$f"):$(md5 -q "$f" 2>/dev/null || md5sum "$f" | cut -d' ' -f1)"
done > /tmp/squad-m3-strat-checksums-before.txt
cat /tmp/squad-m3-strat-checksums-before.txt

# Record experiments.md line count
EXP_LINES_BEFORE=$(wc -l < "$SHARED/knowledge/experiments.md" | tr -d ' ')
echo "experiments.md lines before: $EXP_LINES_BEFORE"

# Set cadence to full_squad (required for debate -- quick_iteration skips Critic)
echo "cadence: full_squad" > "$SHARED/loop/cadence.md"
echo "Cadence set to full_squad"

# Save baselines
echo "$STRAT_COUNT_BEFORE" > /tmp/squad-m3-strat-count-before.txt
echo "$EXP_LINES_BEFORE" > /tmp/squad-m3-exp-lines-before.txt

# Clean prior test output
rm -f /tmp/squad-m3-cycle-output.txt
rm -f /tmp/squad-m3-result.json
```

**Expected:**
- Baselines captured, cadence set to full_squad
- Exit code: 0

---

### Phase 2: Run the Cycle

Run one full_squad cycle. The Director should trigger the debate relay pattern:
Engineer designs, Critic challenges, Director synthesizes and relays, Engineer revises.

#### 2.1 Execute run_cycle

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-research-squad-v2-M3
source .env.sandbox

uv run python3 -c "
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path('.squad')))
from squad_engine.loop import run_cycle

async def main():
    result = await run_cycle(
        iteration=300,
        shared_dir=str(Path.home() / '.ktrdr/shared/squad'),
        charter_dir=str(Path('.squad/agents')),
    )

    # Serialize CycleResult including debate metadata
    output = {
        'status': result.status,
        'iteration': result.iteration,
        'total_cost_usd': result.total_cost_usd,
        'agents_spawned': result.agents_spawned,
        'experiment_result': result.experiment_result,
        'cadence_next': result.cadence_next,
        'error': result.error,
        'duration_seconds': result.duration_seconds,
        'debates': result.debates,
        'conversation_log': [
            {
                'role': e.role,
                'message_to_agent': e.message_to_agent,
                'agent_response': e.agent_response[:500],
                'cost_usd': e.cost_usd,
                'turns': e.turns,
            }
            for e in result.conversation_log
        ],
    }
    print('CYCLE_RESULT_JSON:' + json.dumps(output, default=str))

asyncio.run(main())
" 2>&1 | tee /tmp/squad-m3-cycle-output.txt
```

**Expected:**
- Output contains `CYCLE_RESULT_JSON:` with valid JSON
- Duration: 15-45 minutes (debate adds some overhead)
- agents_spawned should include engineer, critic, and scribe at minimum

#### 2.2 Extract and Save CycleResult JSON

**Command:**
```bash
RESULT_LINE=$(grep 'CYCLE_RESULT_JSON:' /tmp/squad-m3-cycle-output.txt | tail -1)
if [ -z "$RESULT_LINE" ]; then
  echo "FAIL: No CYCLE_RESULT_JSON found in output"
  echo "Last 30 lines of output:"
  tail -30 /tmp/squad-m3-cycle-output.txt
  exit 1
fi

RESULT_JSON=$(echo "$RESULT_LINE" | sed 's/^CYCLE_RESULT_JSON://')
echo "$RESULT_JSON" > /tmp/squad-m3-result.json

# Pretty-print summary
python3 -c "
import json
with open('/tmp/squad-m3-result.json') as f:
    data = json.load(f)
print(f'Status: {data[\"status\"]}')
print(f'Agents: {data[\"agents_spawned\"]}')
print(f'Cost: \${data[\"total_cost_usd\"]:.4f}')
print(f'Duration: {data[\"duration_seconds\"]:.1f}s')
print(f'Debates: {len(data.get(\"debates\", []))}')
print(f'Conversation entries: {len(data.get(\"conversation_log\", []))}')
print(f'Error: {data.get(\"error\")}')
"
```

**Expected:**
- JSON parsed successfully
- Status is COMPLETE, error is None

---

### Phase 3: Validate Debate Mechanics

This is the core M3 validation. We prove multi-turn debate happened with genuine revision.

#### 3.1 Verify Cycle Completed Successfully

**Command:**
```bash
python3 -c "
import json, sys

with open('/tmp/squad-m3-result.json') as f:
    data = json.load(f)

status = data['status']
error = data.get('error')

if status != 'COMPLETE':
    print(f'FAIL: status={status}, error={error}')
    sys.exit(1)

if error is not None:
    print(f'FAIL: error is not None: {error}')
    sys.exit(1)

print('OK: Cycle completed successfully (status=COMPLETE, error=None)')
"
```

#### 3.2 Verify Critic Was Spawned (Debate Participant Present)

**Command:**
```bash
python3 -c "
import json, sys

with open('/tmp/squad-m3-result.json') as f:
    data = json.load(f)

agents = data['agents_spawned']
print(f'Agents spawned: {agents}')

if 'critic' not in agents:
    print('FAIL: Critic not spawned -- no debate possible without adversarial agent')
    print('This means the Director did not trigger the debate relay pattern')
    sys.exit(1)

if 'engineer' not in agents:
    print('FAIL: Engineer not spawned -- no strategy to debate')
    sys.exit(1)

print('OK: Both Engineer and Critic spawned (debate participants present)')
"
```

**Expected:**
- Both `engineer` and `critic` in agents_spawned

#### 3.3 Verify 2+ Turn Exchange Between Engineer and Critic (via Director Relay)

This is the key M3 assertion. The conversation_log must show:
1. Director -> Engineer (design task)
2. Director -> Critic (challenge task)
3. Director -> Engineer again (relay of Critic's concern)

At minimum, Engineer must appear 2+ times in the conversation log.

**Command:**
```bash
python3 -c "
import json, sys

with open('/tmp/squad-m3-result.json') as f:
    data = json.load(f)

log = data.get('conversation_log', [])
if not log:
    print('FAIL: conversation_log is empty -- no exchanges recorded')
    sys.exit(1)

# Count queries per role
role_counts = {}
for entry in log:
    role = entry['role']
    role_counts[role] = role_counts.get(role, 0) + 1

print('Query counts per role:')
for role, count in sorted(role_counts.items()):
    print(f'  {role}: {count}')

engineer_count = role_counts.get('engineer', 0)
critic_count = role_counts.get('critic', 0)

if engineer_count < 2:
    print(f'FAIL: Engineer queried only {engineer_count} time(s) -- need 2+ for debate relay')
    print('Director must query Engineer at least twice: initial design + revision after Critic')
    sys.exit(1)

if critic_count < 1:
    print(f'FAIL: Critic queried 0 times -- no challenge issued')
    sys.exit(1)

# Verify the debate SEQUENCE: Engineer before Critic before Engineer-again
roles_in_order = [e['role'] for e in log]
print(f'Exchange sequence: {\" -> \".join(roles_in_order)}')

# Find pattern: engineer...critic...engineer (with any agents between)
first_engineer = roles_in_order.index('engineer')
first_critic = None
second_engineer = None

for i in range(first_engineer + 1, len(roles_in_order)):
    if roles_in_order[i] == 'critic' and first_critic is None:
        first_critic = i
    elif roles_in_order[i] == 'engineer' and first_critic is not None and second_engineer is None:
        second_engineer = i
        break

if first_critic is None:
    print('FAIL: No Critic query found after initial Engineer query')
    sys.exit(1)

if second_engineer is None:
    print('FAIL: No second Engineer query found after Critic -- debate relay did not happen')
    print('Director received Critic feedback but did not relay it back to Engineer')
    sys.exit(1)

total_debate_turns = engineer_count + critic_count
print(f'OK: Debate relay confirmed -- Engineer({engineer_count}) + Critic({critic_count}) = {total_debate_turns} turns')
print(f'  Exchange {first_engineer+1}: Director -> Engineer (initial design)')
print(f'  Exchange {first_critic+1}: Director -> Critic (challenge)')
print(f'  Exchange {second_engineer+1}: Director -> Engineer (revision after Critic relay)')
"
```

**Expected:**
- Engineer queried 2+ times, Critic queried 1+ times
- Sequence: Engineer -> ... -> Critic -> ... -> Engineer (relay pattern)

#### 3.4 Verify Director Synthesized Critic's Concern (Not Raw Forwarding)

The Director should distill the Critic's output into an actionable concern, not paste it verbatim.

**Command:**
```bash
python3 -c "
import json, sys

with open('/tmp/squad-m3-result.json') as f:
    data = json.load(f)

log = data.get('conversation_log', [])

# Find the Critic's response and the subsequent Engineer message
critic_response = None
relay_message = None

roles_in_order = [e['role'] for e in log]
first_critic_idx = None
second_engineer_idx = None

for i, entry in enumerate(log):
    if entry['role'] == 'critic' and first_critic_idx is None:
        first_critic_idx = i
        critic_response = entry['agent_response']
    elif entry['role'] == 'engineer' and first_critic_idx is not None and second_engineer_idx is None:
        second_engineer_idx = i
        relay_message = entry['message_to_agent']
        break

if critic_response is None or relay_message is None:
    print('FAIL: Could not find Critic response + subsequent Engineer message for relay analysis')
    sys.exit(1)

# Synthesis check: the relay message should be SHORTER than the raw Critic response
# (Director distills, not forwards)
critic_len = len(critic_response)
relay_len = len(relay_message)

print(f'Critic response length: {critic_len} chars')
print(f'Director relay message length: {relay_len} chars')

# Check it is not a raw copy-paste (allow some tolerance for quoting)
# If relay contains >80% of Critic's response verbatim, that is raw forwarding
if critic_len > 100:
    # Find longest common substring as a rough plagiarism check
    # Simpler heuristic: check if any 200-char chunk of Critic output appears in relay
    chunk_size = min(200, critic_len // 2)
    raw_forward = False
    for start in range(0, critic_len - chunk_size, 50):
        chunk = critic_response[start:start + chunk_size]
        if chunk in relay_message:
            raw_forward = True
            break

    if raw_forward:
        print('WARNING: Director appears to have raw-forwarded a large chunk of Critic output')
        print('Expected synthesis (shorter, actionable) not copy-paste')
        # This is a WARNING, not FAIL -- the Director may quote briefly
    else:
        print('OK: Director relay does not contain large verbatim chunks of Critic output')

# The relay message should reference the concern (some keyword overlap expected)
# but be shorter or comparable, not longer
if relay_len > critic_len * 1.5 and relay_len > 300:
    print(f'WARNING: Relay message ({relay_len}) is longer than Critic response ({critic_len}) -- unusual')

# Print the actual relay message for human review
print()
print('=== Director relay message to Engineer (first 500 chars) ===')
print(relay_message[:500])
print('=== end ===')
print()
print('OK: Director relay message captured for human review')
"
```

**Expected:**
- Relay message is not a verbatim copy of Critic's response
- Relay message is present and references a concern

#### 3.5 Verify Strategy YAML Is Measurably Different Before and After Revision

The Engineer should produce a revised strategy after receiving the Critic's concern.
We check that the strategy file was modified (or a second version created).

**Command:**
```bash
python3 -c "
import json, sys

with open('/tmp/squad-m3-result.json') as f:
    data = json.load(f)

log = data.get('conversation_log', [])

# Find the Engineer's initial response and post-revision response
engineer_responses = [e for e in log if e['role'] == 'engineer']

if len(engineer_responses) < 2:
    print(f'FAIL: Only {len(engineer_responses)} Engineer response(s) -- need 2+ for before/after diff')
    sys.exit(1)

initial = engineer_responses[0]['agent_response']
revised = engineer_responses[1]['agent_response']

initial_len = len(initial)
revised_len = len(revised)

print(f'Initial Engineer response: {initial_len} chars')
print(f'Revised Engineer response: {revised_len} chars')

# They should NOT be identical -- that would mean no revision happened
if initial == revised:
    print('FAIL: Initial and revised Engineer responses are IDENTICAL -- no revision occurred')
    sys.exit(1)

# Compute a rough similarity ratio
# Using simple set-of-words overlap as proxy
initial_words = set(initial.lower().split())
revised_words = set(revised.lower().split())

if initial_words and revised_words:
    overlap = len(initial_words & revised_words)
    total = len(initial_words | revised_words)
    similarity = overlap / total if total > 0 else 0
    print(f'Word-level similarity: {similarity:.2%}')

    # Some overlap expected (same strategy domain), but not 100%
    if similarity > 0.95:
        print('WARNING: Responses are >95% similar -- revision may be superficial')
    elif similarity < 0.05:
        print('WARNING: Responses are <5% similar -- may be completely different strategies, not a revision')
    else:
        print(f'OK: Responses differ meaningfully (similarity={similarity:.2%})')
else:
    print('WARNING: Could not compute similarity (empty responses?)')

print()
print('OK: Engineer produced different output before and after Critic relay')
"
```

**Expected:**
- Initial and revised Engineer responses are NOT identical
- Some meaningful difference (not 100% similarity, not 0% similarity)

#### 3.6 Verify Strategy YAML File Changed on Disk

If the Engineer rewrites the strategy file after revision, the on-disk file should differ from the pre-cycle checksum.

**Command:**
```bash
STRAT_DIR="$HOME/.ktrdr/shared/strategies"
STRAT_COUNT_BEFORE=$(cat /tmp/squad-m3-strat-count-before.txt)
STRAT_COUNT_AFTER=$(ls "$STRAT_DIR"/*.yaml 2>/dev/null | wc -l | tr -d ' ')

echo "Strategy count: before=$STRAT_COUNT_BEFORE, after=$STRAT_COUNT_AFTER"

if [ "$STRAT_COUNT_AFTER" -le "$STRAT_COUNT_BEFORE" ]; then
  echo "FAIL: No new strategy YAML created (before=$STRAT_COUNT_BEFORE, after=$STRAT_COUNT_AFTER)"
  exit 1
fi

# Compare checksums -- find files that are new or changed
echo ""
echo "Checksum changes:"
ls "$STRAT_DIR"/*.yaml 2>/dev/null | while read f; do
  NAME=$(basename "$f")
  NEW_HASH=$(md5 -q "$f" 2>/dev/null || md5sum "$f" | cut -d' ' -f1)
  OLD_HASH=$(grep "^${NAME}:" /tmp/squad-m3-strat-checksums-before.txt 2>/dev/null | cut -d: -f2)
  if [ -z "$OLD_HASH" ]; then
    echo "  NEW: $NAME ($NEW_HASH)"
  elif [ "$OLD_HASH" != "$NEW_HASH" ]; then
    echo "  CHANGED: $NAME (was $OLD_HASH, now $NEW_HASH)"
  fi
done

NEWEST=$(ls -t "$STRAT_DIR"/*.yaml | head -1)
echo ""
echo "Newest strategy file: $NEWEST"
echo "First 10 lines:"
head -10 "$NEWEST"
echo ""
echo "OK: Strategy YAML created or modified on disk"
```

**Expected:**
- At least one new or changed strategy file
- File has valid YAML content

#### 3.7 Verify Debate Metadata in CycleResult

The `debates` field should contain structured metadata about the debate.

**Command:**
```bash
python3 -c "
import json, sys

with open('/tmp/squad-m3-result.json') as f:
    data = json.load(f)

debates = data.get('debates', [])

if not debates:
    print('WARNING: debates list is empty -- record_debate() may not have been called')
    print('This could mean the Director ran the debate but Python did not capture metadata')
    print('Checking conversation_log as fallback evidence...')

    # Fallback: verify debate happened via conversation_log even if metadata not captured
    log = data.get('conversation_log', [])
    engineer_count = sum(1 for e in log if e['role'] == 'engineer')
    critic_count = sum(1 for e in log if e['role'] == 'critic')

    if engineer_count >= 2 and critic_count >= 1:
        print(f'  conversation_log shows debate pattern: Engineer={engineer_count}, Critic={critic_count}')
        print('  Debate occurred but metadata not captured in debates field')
        print('  This is a partial pass -- metadata recording needs implementation')
    else:
        print('FAIL: No debate evidence in either debates field or conversation_log')
        sys.exit(1)
else:
    print(f'Debate metadata entries: {len(debates)}')
    for i, debate in enumerate(debates):
        roles = debate.get('roles', [])
        turns = debate.get('turns', 0)
        revised = debate.get('revised', False)
        resolution = debate.get('resolution', '')
        print(f'  Debate {i+1}: roles={roles}, turns={turns}, revised={revised}')
        print(f'    Resolution: {resolution[:200]}')

        if turns < 2:
            print(f'  WARNING: Debate {i+1} has only {turns} turn(s) -- expected 2+')

        if not revised:
            print(f'  WARNING: Debate {i+1} revised=False -- Engineer did not revise')

    # At least one debate should show revision
    any_revised = any(d.get('revised', False) for d in debates)
    if not any_revised:
        print('WARNING: No debate shows revised=True -- revision may have happened but flag not set')

    print(f'OK: {len(debates)} debate(s) recorded with metadata')
"
```

**Expected:**
- debates list is non-empty (or conversation_log proves debate happened as fallback)
- At least one debate entry with turns >= 2

#### 3.8 Verify Token Cost Confirms Real Sessions

**Command:**
```bash
python3 -c "
import json, sys

with open('/tmp/squad-m3-result.json') as f:
    data = json.load(f)

cost = data['total_cost_usd']
print(f'Total cost: \${cost:.4f}')

if cost <= 0:
    print('FAIL: total_cost_usd is 0 or negative -- sessions did not run')
    sys.exit(1)

# With debate, cost should be higher than a minimal cycle
# Rough expectation: Director + Engineer(2+) + Critic(1+) + Scribe = ~\$2-8
if cost < 0.50:
    print(f'WARNING: Cost \${cost:.4f} seems very low for a debate cycle -- possible short-circuit')
elif cost > 20.0:
    print(f'WARNING: Cost \${cost:.4f} seems very high -- check for runaway sessions')

print(f'OK: Real Claude sessions confirmed (cost=\${cost:.4f})')
"
```

#### 3.9 Verify Conversation Log Shows Director's Synthesis Framing

The relay message from Director to Engineer (after Critic) should contain synthesis
language -- references to what the Critic found, framed as a question or constraint.

**Command:**
```bash
python3 -c "
import json, sys, re

with open('/tmp/squad-m3-result.json') as f:
    data = json.load(f)

log = data.get('conversation_log', [])

# Find the relay: first Engineer-message AFTER Critic
roles = [e['role'] for e in log]
critic_idx = None
relay_idx = None

for i, role in enumerate(roles):
    if role == 'critic' and critic_idx is None:
        critic_idx = i
    elif role == 'engineer' and critic_idx is not None and relay_idx is None:
        relay_idx = i
        break

if relay_idx is None:
    print('FAIL: Could not find relay message (Engineer query after Critic)')
    sys.exit(1)

relay_msg = log[relay_idx]['message_to_agent']

# Look for synthesis indicators: reference to concern, question framing, constraint language
synthesis_indicators = [
    r'concern',
    r'raises?\b',
    r'identif',
    r'point(s|ed)? out',
    r'challeng',
    r'overfit',
    r'address',
    r'revis',
    r'adjust',
    r'your response',
    r'how (would|will|do) you',
    r'critic',
    r'featur',
    r'risk',
    r'suggest',
]

found = []
for pattern in synthesis_indicators:
    if re.search(pattern, relay_msg, re.IGNORECASE):
        found.append(pattern)

print(f'Synthesis indicators found in relay message: {len(found)}/{len(synthesis_indicators)}')
for f_pattern in found:
    print(f'  matched: {f_pattern}')

if len(found) == 0:
    print('WARNING: No synthesis indicators found -- Director may not be synthesizing Critic output')
    print('Relay message (first 300 chars):')
    print(relay_msg[:300])
else:
    print(f'OK: Director relay shows synthesis language ({len(found)} indicators)')
"
```

**Expected:**
- At least 1-2 synthesis indicators in the relay message

---

### Phase 4: Verify Side Effects

#### 4.1 Verify experiments.md Was Modified (Scribe Recorded)

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
EXP_LINES_BEFORE=$(cat /tmp/squad-m3-exp-lines-before.txt)
EXP_LINES_AFTER=$(wc -l < "$SHARED/knowledge/experiments.md" | tr -d ' ')

echo "experiments.md: before=$EXP_LINES_BEFORE, after=$EXP_LINES_AFTER"

if [ "$EXP_LINES_AFTER" -le "$EXP_LINES_BEFORE" ]; then
  echo "FAIL: experiments.md not modified after cycle"
  exit 1
fi

GROWTH=$(( EXP_LINES_AFTER - EXP_LINES_BEFORE ))
echo "Growth: $GROWTH lines"
echo "OK: experiments.md grew by $GROWTH lines"
```

#### 4.2 Verify Conversation Log Written to Disk

**Command:**
```bash
LOG_FILE="$HOME/.ktrdr/shared/squad/logs/cycle_300_conversation.md"
if [ ! -f "$LOG_FILE" ]; then
  echo "FAIL: Conversation log not written to $LOG_FILE"
  exit 1
fi

LINE_COUNT=$(wc -l < "$LOG_FILE" | tr -d ' ')
echo "Conversation log: $LOG_FILE ($LINE_COUNT lines)"

# Check log mentions both Critic and Engineer
if grep -qi "critic" "$LOG_FILE" && grep -qi "engineer" "$LOG_FILE"; then
  echo "OK: Conversation log references both Critic and Engineer"
else
  echo "WARNING: Conversation log may not contain both debate participants"
fi

# Show a snippet for review
echo ""
echo "=== First 30 lines ==="
head -30 "$LOG_FILE"
echo "=== end ==="
```

---

## Success Criteria

All must pass:

- [ ] Cycle completes with status=COMPLETE and error=None
- [ ] Both Engineer and Critic spawned (debate participants present)
- [ ] Engineer queried 2+ times (initial design + post-relay revision)
- [ ] Critic queried 1+ times (challenge issued)
- [ ] Debate sequence confirmed: Engineer -> ... -> Critic -> ... -> Engineer
- [ ] Engineer's pre-revision and post-revision responses are measurably different
- [ ] Director's relay message is not a raw copy-paste of Critic's output
- [ ] total_cost_usd > 0 (real Claude sessions ran)
- [ ] New or modified strategy YAML on disk
- [ ] experiments.md grew (Scribe recorded results)

---

## Sanity Checks

**CRITICAL:** These catch false positives

| Check | What It Catches |
|-------|----------------|
| Engineer queried 2+ times in conversation_log | Director received Critic feedback but never relayed it (skipped revision) |
| Debate sequence (E -> C -> E) not just counts | Director queried Engineer twice for unrelated reasons, Critic queried but not as part of debate |
| Engineer responses differ (word-level similarity check) | Engineer returned the same strategy both times (rubber-stamp revision) |
| Relay message not verbatim Critic output | Director copy-pasted Critic's raw response instead of synthesizing |
| Relay message has synthesis indicators | Director sent a generic "please revise" without referencing Critic's specific concern |
| total_cost_usd > 0 | Mocked or short-circuited sessions |
| Strategy YAML checksum changed on disk | Strategy file exists from before the cycle, not actually modified |
| Critic charter checked in preflight | Critic without adversarial guidance produces soft reviews that trigger no revision |
| debates metadata checked (with fallback) | Python captured the debate but record_debate() not called -- still valid if conversation_log proves it |

---

## Failure Categorization

| Failure | Category | Action |
|---------|----------|--------|
| CYCLE_RESULT_JSON not found | EXECUTION_FAILURE | Check /tmp/squad-m3-cycle-output.txt for Python traceback |
| status=FAILED | ORCHESTRATION_FAILURE | Read error field -- Director may have failed tool calls |
| Critic not in agents_spawned | DIRECTOR_INTELLIGENCE | Director skipped Critic in full_squad mode -- strengthen DESIGN_CHALLENGE section in director_prompt.py |
| Engineer queried only once | DIRECTOR_RELAY_FAILURE | Director received Critic output but did not relay to Engineer -- check DEBATE_RELAY prompt section |
| No debate sequence (E->C->E) | DIRECTOR_RELAY_FAILURE | Director queried agents in wrong order or skipped relay step |
| Engineer responses identical | ENGINEER_FAILURE | Engineer ignored the Critic concern -- check if relay message was actionable |
| Relay is raw copy-paste | DIRECTOR_SYNTHESIS_FAILURE | Director not following "Synthesize, Don't Forward" guidance -- strengthen RELAY_PATTERN instructions |
| No synthesis indicators | DIRECTOR_SYNTHESIS_FAILURE | Relay message is generic ("please revise") without Critic's specific concern |
| debates list empty | METADATA_FAILURE | record_debate() not called by Python -- check spawn_agent_tool or cycle flow |
| total_cost_usd == 0 | SESSION_FAILURE | Claude sessions did not connect -- check claude CLI |
| experiments.md not modified | SCRIBE_FAILURE | Scribe was not spawned or failed silently |
| Strategy YAML not created | ENGINEER_FAILURE | Engineer did not write YAML or wrong path |

---

## Troubleshooting

**If Critic is not spawned:**
- full_squad cadence should trigger Critic via DESIGN_CHALLENGE instructions
- Check director_prompt.py includes DESIGN_CHALLENGE section
- Check cadence.md was actually set to full_squad: `cat ~/.ktrdr/shared/squad/loop/cadence.md`
- The Director has discretion -- it may skip Critic if KB state suggests iteration over challenge
- If consistently skipped, strengthen the DESIGN_CHALLENGE instructions to make Critic mandatory in full_squad

**If Engineer is only queried once (no relay):**
- The Director received Critic feedback but decided not to relay it
- Check the Critic's response in conversation_log -- was it substantive enough to warrant relay?
- Check DEBATE_RELAY section instructs the Director to always relay back
- The Director may have judged Critic's concerns as minor and proceeded without revision
- If consistently happening, add explicit instruction: "ALWAYS relay Critic concerns to Engineer for response"

**If Engineer responses are identical:**
- The relay message may not have been actionable
- Check what the Director told Engineer in the relay -- was it specific?
- Engineer may have refused to revise (argued the design is fine)
- Check if the strategy YAML on disk changed even if the response text is similar

**If Director raw-forwards Critic output:**
- The RELAY_PATTERN section says "Synthesize, Don't Forward" but is advisory
- Strengthen the instruction or add an example of good vs bad relay
- Check if the relay message length exceeds Critic response length (bloated relay)

**If debates metadata is empty but conversation_log shows debate:**
- The record_debate() call may not be wired into the tool flow yet
- This is a partial pass -- the debate happened but Python did not capture structured metadata
- Check if CycleState.record_debate() is called after the debate resolves
- The spawn_agent_tool may need to detect debate patterns and call record_debate_turn()

**If the cycle hangs:**
- Training + backtest execution dominates (10-30 min normal)
- Debate adds 5-10 min of additional LLM queries
- Check executor.sh 15-minute stall timeout
- Check sandbox health: `curl http://localhost:${KTRDR_API_PORT}/api/v1/health`
- Check for stuck claude processes: `ps aux | grep claude`

---

## Evidence to Capture

- Full /tmp/squad-m3-cycle-output.txt (all session logs)
- /tmp/squad-m3-result.json (parsed CycleResult with debates + conversation_log)
- Conversation log on disk: ~/.ktrdr/shared/squad/logs/cycle_300_conversation.md
- Strategy YAML file(s) created or modified (path + first 20 lines)
- Director relay message to Engineer (full text from conversation_log)
- Critic response (full text from conversation_log)
- Engineer initial vs revised response comparison
- experiments.md diff (before/after line count + tail of new content)
- debates metadata from CycleResult
- Total cost and duration
