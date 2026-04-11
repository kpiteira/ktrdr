# Handoff — M3: Multi-Turn Debate

## Status: COMPLETE — Tasks 3.1-3.4 done

## Task 3.1: Multi-Turn Relay Mechanism

### What Was Built
- Added `_query_counts` dict to AgentManager — tracks queries per role per cycle
- Added `query_counts` property (returns copy) for external access
- `teardown_all()` resets query counts alongside sessions
- Added `DEBATE_RELAY` section to `director_prompt.py` with:
  - Numbered relay flow (spawn Engineer → Critic → relay → revise → decide)
  - Good/bad relay examples specific to debate synthesis
  - Token budget guidance (~5-10K tokens per debate turn)

### Tests Added (10 new, 77 total)
- `TestM3QueryCountTracking`: 5 tests (init empty, first=1, increment, per-role, teardown resets)
- `TestM3DebateRelayPattern`: 5 tests (dedicated section, flow, bad example, good example, token budget)

### Gotchas
1. M2 already had a "Relay Pattern — Synthesize, Don't Forward" section in CONSULTANT_TRIGGERS. M3's DEBATE_RELAY is a separate, more detailed section specifically about multi-turn back-and-forth. Both coexist.
2. Query counts track per-role, not per-pair. Pair tracking comes in Task 3.2 for debate depth control.

## Task 3.2: Debate Depth Control

### What Was Built
- Added debate resolution heuristics to `DEBATE_RELAY` section in `director_prompt.py`:
  - "When to Continue" (factual concerns unaddressed, evidence pending)
  - "When to Resolve" (repeating, preference-based, 4+ turns)
  - 5-turn maximum with note about Python enforcement
- Added to `CycleState` in `squad_tools.py`:
  - `debate_pairs` dict with sorted tuple keys for pair tracking
  - `record_debate_turn()` and `is_debate_limit_reached()` methods
  - `debates` list with `record_debate()` for structured metadata
  - `MAX_DEBATE_TURNS = 5` constant
- Added `debates` field to `CycleResult` in `loop.py` — wired from CycleState

### Tests Added (16 new, 92 total)
- `TestM3DebateDepthHeuristics`: 4 tests (continue heuristics, resolve heuristics, turn limit, token budget)
- `TestM3DebateTurnPairTracking`: 8 tests (init, track, increment, sorted key, independent pairs, under limit, at limit, untracked)
- `TestM3DebateMetadata`: 3 tests (init empty, record metadata, multiple debates)

### Gotchas
1. Pair keys are sorted tuples — `("critic", "engineer")` not `("engineer", "critic")`. This ensures A↔B and B↔A are the same debate.
2. The safety valve is data-only (CycleState methods). The spawn_agent tool handler in squad_tools.py doesn't enforce it yet — the Director's prompt guides it, and it's available for tool-level enforcement if needed. The M3 plan says "spawn_agent returns a message" but this is deferred to when we need tool-level enforcement since the Director prompt + query count already provides the mechanism.

## Task 3.3: Engineer ↔ Critic Design Challenge Pattern

### What Was Built
- Added `DESIGN_CHALLENGE` section to `director_prompt.py` with:
  - Pre-execution challenge workflow (6 numbered steps)
  - Reference to Critic's Tier 1/2/3 framework
  - Key concerns: overfitting, lookahead contamination, data leakage
  - Cadence-aware: default for full_squad, skip for quick_iteration
- Prompt now ~2250 tokens — well within budget

### Tests Added (6 new, 98 total)
- `TestM3DesignChallenge`: 6 tests (dedicated section, critic tiers, key concerns, pre-execution, full_squad default, quick_iteration skip)

### Prompt Iterations (from E2E validation)
The DESIGN_CHALLENGE section went through 3 iterations based on E2E testing:
1. **v1 (advisory):** "Before calling execute_experiment, have the Critic review..." — Director ignored it (run 1, iter=300)
2. **v2 (mandatory):** "You MUST challenge" + numbered steps — Director called Critic but self-applied framework instead of relaying (run 2, iter=301)
3. **v3 (anti-bypass):** Added "Do NOT apply the Critic's framework yourself" + "MUST call spawn_agent(engineer, ...) after Critic" — Director followed the full E→C→E relay (run 3, iter=302)

Key learning: LLM Directors need explicit anti-bypass language, not just mandatory language. The Director will find shortcuts (self-assessment) unless the prompt specifically prohibits them.

## Task 3.4: E2E Validation

### Results
- **E2E test recipe:** `.claude/skills/ke2e/tests/squad/m3-debate-genuine-revision.md`
- **Run 1 (iter=300):** FAILED — DIRECTOR_RELAY_FAILURE. Critic used for retrospective analysis, never challenged new design.
- **Run 2 (iter=301):** FAILED — DIRECTOR_RELAY_FAILURE. Director called Critic 3x but said "MCP agents not returning text" and self-applied framework. Never relayed to Engineer.
- **Run 3 (iter=302):** PASSED — Full E→C→E relay confirmed. Director synthesized Critic's top 2 concerns and relayed to Engineer.

### Evidence (Run 3)
- Cost: $10.16, Duration: 180 min
- All 7 agents spawned (engineer x5, critic x4, plus scribe, quant, inventor, scout, architect)
- Debate sequence confirmed: Engineer (design) → Critic (challenge) → Engineer (relay + revision)
- Director synthesized: "Two design concerns on C401 to address before we execute: 1. Temporal frequency mismatch... 2. Failure mode disambiguation..."
- Strategy YAML created: squad_c401_yield_spread_1h.yaml, squad_c401_cross_pair_1h.yaml
- experiments.md grew by 90 lines

### Post-Validation: Wired Python Debate Enforcement
- `spawn_agent_tool` now tracks `last_spawned_role` on CycleState
- Consecutive different-role spawns auto-call `record_debate_turn()`
- Before spawning, checks `is_debate_limit_reached()` — returns limit message (no agent call) if 5-turn max hit
- Same-role consecutive spawns don't create debate turns
- 5 new tests in `TestM3SpawnAgentDebateEnforcement` (103 total)

### Remaining Gap
`record_debate()` (structured metadata: roles, turns, revised, resolution) is still not auto-called. Detecting "revised" and "resolution" requires semantic understanding — could be addressed with a dedicated `resolve_debate` tool the Director calls explicitly.
