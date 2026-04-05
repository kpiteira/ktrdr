---
design: docs/designs/research-squad-v2/DESIGN.md
architecture: docs/designs/research-squad-v2/ARCHITECTURE.md
---

# M2: Director-Driven Consultation

**When this works:** The squad's experiments improve because the Director brings in the right expertise at the right time — Quant catches a cost problem before the Engineer wastes training compute, Critic identifies an overfitting risk before execution — instead of v1's fixed pipeline where all 8 agents speak every cycle regardless of relevance.

**Scenario (from design doc — "Scenario 1: Standard Research Cycle"):** Director reads state: synthesis says standard indicators are exhausted on 1h, 5m shows promise. Nudges say use LSTM/GRU. Director spawns Quant to discuss 5m cost assumptions, then spawns Engineer with the mission AND Quant's cost assessment. Engineer designs with cost awareness it wouldn't have had alone.

**Scenario (from design doc — "Scenario 4: Capability Gap"):** Engineer wants to use DXY as a cross-asset feature. Director spawns Architect — Architect says BLOCKED, no cross-asset pipeline exists. Architect files a GAP, proposes fallback. Director adjusts the frontier without wasting a training cycle on an impossible experiment.

**Prerequisite:** M1 complete (core tools + single cycle with Director + Engineer + Scribe)

**Scope:** All 5 consultants available. Director selects per cycle based on KB state. Single-turn per consultant (multi-turn debate is M3). v1 shell scripts still functional alongside.

---

## Task 2.1: Full Agent Roster + Concurrent Sessions

**File(s):** `.squad/orchestrator/tools.py` (AgentManager), `.squad/orchestrator/session.py`
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Open AgentManager to all 7 agent roles and handle concurrent session management. M1 restricted to engineer + scribe; now Director can spawn any combination. Multiple sessions may be alive simultaneously (Director talks to Engineer, then Quant, then back to Engineer — all in the same cycle).

**Implementation Notes:**
- Remove M1's `allowed_roles` restriction — all 7 roles available: engineer, quant, inventor, scout, critic, architect, scribe
- Concurrent sessions: Director may have Engineer + Quant + Critic alive simultaneously
  - Each session gets isolated temp working directory (avoids file conflicts between agents)
  - Agent-specific tool access: Scout needs WebSearch (for external research), Architect needs Bash (for `gh issue create`), Scribe needs Write/Edit (for KB updates). These are Claude Code tools available natively — the charter instructs each agent what to use.
- Total cost tracking across all active sessions via SafetyGuard
- Context budget awareness: estimate aggregate context across sessions, warn Director when approaching budget

**Testing Requirements:**
- [ ] Unit test: all 7 roles can be spawned without error
- [ ] Unit test: 3+ concurrent sessions (engineer + quant + critic) maintained without interference
- [ ] Unit test: each session gets isolated working directory
- [ ] Unit test: total cost aggregated across all sessions
- [ ] Unit test: teardown_all cleans up all concurrent sessions in parallel

**Acceptance Criteria:**
- [ ] All 7 agent roles available via spawn_agent
- [ ] Multiple sessions alive concurrently without interference
- [ ] Aggregate budget tracking across sessions
- [ ] Clean concurrent teardown

---

## Task 2.2: Context Routing — Director Decides What Each Agent Sees

**File(s):** `.squad/orchestrator/context.py` (extend), `.squad/orchestrator/director_prompt.py` (extend)
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Enable the Director to specify which KB files each agent gets via the `context` parameter of `spawn_agent`. The Director prompt includes a reference table (guidance, not enforcement) of typical context per role.

**Implementation Notes:**
- Director prompt adds context routing guidance (from architecture doc):
  - Engineer: components.md, synthesis.md, last 5 experiments
  - Quant: current proposal or results being discussed
  - Inventor: current frontier, what's been tried (frontiers.md + recent experiments)
  - Scout: frontiers.md, agents/scout/bibliography.md, roadmap/external-insights.md
  - Critic: the specific proposal or results to challenge
  - Architect: capability-gaps.md, the Engineer's current spec
  - Scribe: full cycle transcript, synthesis.md, last 5 experiments
- These are **suggestions in the Director prompt**, not enforced by code — the Director decides
- Context files loaded by ContextLoader, concatenated into initial session message
- Large files gated: full experiments.md only when Director explicitly requests it (Scribe during synthesis)
- Director can pass inline context too — e.g., "Quant says X" doesn't require loading a file

**Testing Requirements:**
- [ ] Unit test: spawn_agent with context=["knowledge/synthesis.md", "knowledge/frontiers.md"] loads both
- [ ] Unit test: missing context files skipped with warning (no crash)
- [ ] Unit test: Director prompt includes context routing guidance table
- [ ] Unit test: inline message context works without any context files

**Acceptance Criteria:**
- [ ] Director controls what each agent sees via spawn_agent context parameter
- [ ] Prompt guidance helps Director make good context decisions
- [ ] Context loading handles missing files gracefully

---

## Task 2.3: Director Prompt — When to Consult Whom

**File(s):** `.squad/orchestrator/director_prompt.py`
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Extend the Director's system prompt with guidance on when each consultant adds value, how to relay perspectives to the Engineer, and when NOT to consult (quick iterations don't need everyone).

**Implementation Notes:**
- **Consultant selection triggers** (from design doc):
  - Quant: evaluating profitability, designing cost-aware experiments, assessing 5m vs 1h cost tradeoffs
  - Inventor: frontier exhausted (3+ cycles with diminishing returns), incrementalism detected
  - Scout: exploring a new frontier, Engineer stuck, need external techniques
  - Critic: before execution (challenge the design), after execution (challenge the results)
  - Architect: Engineer proposes something needing new infrastructure, capability gap suspected
- **Relay pattern** — Director synthesizes, doesn't just forward:
  - Bad: "Quant said: [raw 500-word response]"
  - Good: "Quant's assessment: 5m EURUSD has $1.20/trade spread cost. Your current design needs >$2/trade profit to be viable. Adjust your target or your approach."
- **When NOT to consult:**
  - `quick_iteration` cadence: Director + Engineer only (minor variant of previous experiment)
  - `synthesis` cadence: Director + Scribe only
  - When the experiment is a direct repeat with one changed parameter — no new perspective needed
- Cadence mode passed to Director prompt so it can adjust agent selection

**Testing Requirements:**
- [ ] Unit test: Director prompt includes all 5 consultant triggers with specific examples
- [ ] Unit test: prompt includes relay synthesis guidance with good/bad examples
- [ ] Unit test: prompt adapts based on cadence mode (full_squad shows all consultants, quick_iteration restricts)
- [ ] Unit test: prompt assembly stays within token budget

**Acceptance Criteria:**
- [ ] Director has enough context to make intelligent consultant selection decisions
- [ ] Relay pattern guidance prevents raw forwarding
- [ ] Cadence-aware prompt adapts to cycle mode

---

## Task 2.4: VALIDATION — Director Selects Different Agents Based on Context

**Type:** VALIDATION
**Estimated time:** 2-3 hours

**Description:**
Run 3+ cycles and verify the Director dynamically selects different agent combinations based on KB state. This proves the conversational model produces intelligent orchestration, not a fixed pipeline.

**Scenario under test:** Cycle 1 (full_squad): Director reads frontiers.md, identifies a cost concern, spawns Quant + Engineer. Cycle 2 (quick_iteration): Director sees previous results were close, spawns Engineer only for a parameter variant. Cycle 3 (full_squad): Director recognizes diminishing returns, spawns Inventor + Scout for new directions, then Engineer.

**Validation Steps:**

1. **Load the `ke2e` skill** before designing any validation
2. **Invoke ke2e-test-scout** with: "Squad v2 dynamic consultation: Director selects different agent combinations across 3+ cycles based on KB state. At least 2 different combinations observed. Director's reasoning correlates with KB content (not random). Consultant input visibly influences Engineer's output."
3. **Invoke ke2e-test-runner** with the identified test recipe
4. **Tests must exercise real Claude sessions reading real KB state**

**Success Criteria:**
- [ ] At least 2 distinct agent combinations across 3 cycles
- [ ] Director's selection reasoning cites specific KB content (frontiers, results, nudges)
- [ ] Engineer's output shows influence from consultant perspectives (e.g., cost constraint from Quant reflected in strategy design)
- [ ] Quick iteration cycle uses fewer agents than full_squad cycle
- [ ] Token usage: cycles with fewer consultants use measurably fewer tokens
- [ ] All sessions tear down cleanly between cycles

**Evidence Required:**
- Per-cycle agent roster (which agents spawned, in what order)
- Director's reasoning text for each consultant selection
- Engineer output showing consultant influence (before/after consultant input)
- Token usage per cycle
