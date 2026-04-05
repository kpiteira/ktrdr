---
design: docs/designs/research-squad-v2/DESIGN.md
architecture: docs/designs/research-squad-v2/ARCHITECTURE.md
---

# M3: Multi-Turn Debate

**When this works:** The squad produces experiments the Engineer wouldn't reach alone. A Critic challenge forces the Engineer to genuinely redesign — not just acknowledge the critique. An Inventor brainstorm opens a frontier the Engineer wouldn't have explored. The Director mediates these exchanges skillfully, synthesizing rather than forwarding, and knowing when to stop.

**Scenario (from design doc — "Scenario 2: Frontier Exhaustion"):** After 5 cycles on 5m with diminishing returns, Director recognizes the pattern. Invokes Inventor + Scout: "We need a structural shift." Scout finds papers on temporal fusion transformers. Inventor proposes regime-conditional feature selection. Engineer synthesizes both into a concrete experiment. Critic challenges: "How will you validate this isn't overfitting to the selection criterion?" Engineer revises. This multi-turn exchange produces a qualitative leap that can't happen in a parameter-optimization loop.

**Prerequisite:** M2 complete (all consultants available, Director selects dynamically)

**Scope:** Multi-turn relay between agent pairs. Director as debate mediator with depth control. No loop automation changes (M4).

---

## Task 3.1: Multi-Turn Relay Mechanism

**File(s):** `.squad/orchestrator/director_prompt.py`, `.squad/orchestrator/tools.py`
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Enable the Director to orchestrate back-and-forth exchanges between agents. The mechanical capability exists from M1 (spawn_agent reuses sessions for multi-turn). This task adds the relay pattern to the Director's prompt and debate tracking to AgentManager.

**Implementation Notes:**
- The mechanism is already there: `spawn_agent(critic, "Challenge this: ...")` → get response → `spawn_agent(engineer, "Critic says X, address it")` → get response → ...
- **Director prompt additions — the debate relay pattern:**
  1. Director spawns Engineer with design task
  2. Director spawns Critic: "Challenge this design: [synthesized summary of Engineer's output]"
  3. Director relays Critic's concerns to Engineer: "Critic raises two concerns: (1) overfitting from too many features, (2) no out-of-sample split. Address both."
  4. Engineer revises (or argues back with evidence)
  5. Director decides: relay revision back to Critic, or accept and move on
- **Key: Director synthesizes, doesn't copy-paste:**
  - Bad relay: "Here's what Critic said: [raw 500-word response]"
  - Good relay: "Critic's core concern: your 12-feature input vector is likely to overfit on 6 months of 5m data. Suggested constraint: ≤6 features. Your response?"
- Add query count tracking per role per cycle in AgentManager — needed for debate depth control in 3.2

**Testing Requirements:**
- [ ] Unit test: Director prompt includes debate relay pattern with good/bad examples
- [ ] Unit test: AgentManager tracks query count per role per cycle
- [ ] Unit test: multiple queries to same role maintain conversation context (verified by checking session reuse)
- [ ] Integration test: mock Director orchestrates 3-turn Engineer ↔ Critic exchange — verify context maintained

**Acceptance Criteria:**
- [ ] Director prompt teaches relay-and-synthesize pattern
- [ ] Director can orchestrate back-and-forth between any two agent pairs
- [ ] Conversation context maintained across turns within each session
- [ ] Query count per role tracked for depth control

---

## Task 3.2: Debate Depth Control

**File(s):** `.squad/orchestrator/director_prompt.py`, `.squad/orchestrator/tools.py`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Give the Director heuristics for when to continue a debate and when to resolve it. Without depth control, debates either terminate too early (Critic raises a concern, Engineer says "OK" and the strategy doesn't change) or run forever (burning tokens on preference disagreements). Add a Python safety valve for maximum turns.

**Implementation Notes:**
- **Director prompt — debate resolution heuristics:**
  - **Continue if:** agent raised a factual concern that hasn't been addressed, revision is substantive and merits re-evaluation, concrete evidence was requested and not yet provided
  - **Resolve if:** agents are repeating themselves (no new arguments), disagreement is preference-based not factual, 4+ turns without convergence, remaining concerns are minor and acknowledged
  - **Maximum:** 5 turns per debate pair (enforced by Python, not just guidance)
- **Python enforcement:** AgentManager tracks turn pairs (e.g., engineer↔critic). After 5 total turns in a pair, spawn_agent returns a message to Director: "Debate between Engineer and Critic reached 5-turn limit. Please resolve and proceed."
- **Debate metadata in CycleResult:** debates list with `{roles: [str, str], turns: int, revised: bool, resolution: str}`
- Token budget: Director prompt should note that each debate turn costs ~5-10K tokens — budget accordingly

**Testing Requirements:**
- [ ] Unit test: Python enforces 5-turn maximum per debate pair
- [ ] Unit test: turn pair tracking correct (engineer→critic = 1, critic→engineer = 2, etc.)
- [ ] Unit test: limit message returned to Director (not an exception)
- [ ] Unit test: debate metadata captured in CycleResult
- [ ] Unit test: turn pair resets between different debates in the same cycle (engineer↔critic vs engineer↔inventor)

**Acceptance Criteria:**
- [ ] Director has heuristics for debate depth decisions in prompt
- [ ] Python safety valve at 5 turns per debate pair
- [ ] Debate metadata (turns, revised, resolution) in cycle results
- [ ] Budget guidance in Director prompt

---

## Task 3.3: Engineer ↔ Critic Design Challenge Pattern

**File(s):** `.squad/orchestrator/director_prompt.py`
**Type:** CODING
**Estimated time:** 1-2 hours

**Description:**
Implement the specific pre-execution design challenge: before calling execute_experiment, the Director should have the Critic review the Engineer's strategy. This is the highest-value debate pattern — catching overfitting, lookahead leaks, and feature validity before wasting training compute.

**Implementation Notes:**
- **Director prompt — design challenge workflow:**
  1. Engineer produces strategy design
  2. Director sends to Critic: "Evaluate for: overfitting risk, feature validity, labeling bias, lookahead contamination, out-of-sample design"
  3. Director relays Critic's assessment to Engineer with synthesis
  4. Engineer revises or argues with evidence
  5. Director decides: accept or send back to Critic
- Critic's charter already defines Tier 1/2/3 framework — reference it: "Critic uses their tiered framework: Tier 1 (mandatory) = no lookahead, no data leakage, valid train/test split"
- **Default, not mandatory:** Director should challenge before execute_experiment in full_squad mode. Skip for quick_iteration where the design is a minor variant of an already-challenged strategy.
- This is the v1 Evaluate phase done right — v1's ~50% evaluate failure rate was because the Critic got one shot with no retry. Here the Critic has a persistent session and the Director can relay back and forth.

**Testing Requirements:**
- [ ] Unit test: Director prompt includes pre-execution challenge workflow with Critic tier references
- [ ] Unit test: prompt makes challenge default for full_squad, skippable for quick_iteration
- [ ] Unit test: prompt references Critic's existing Tier 1/2/3 framework

**Acceptance Criteria:**
- [ ] Design challenge pattern in Director prompt as pre-execution default
- [ ] References Critic's existing evaluation framework
- [ ] Cadence-aware: full_squad challenges, quick_iteration can skip

---

## Task 3.4: VALIDATION — Debate Produces Genuine Revision

**Type:** VALIDATION
**Estimated time:** 2-3 hours

**Description:**
Run a cycle where the Director mediates an Engineer ↔ Critic debate that produces a genuine strategy revision. "Genuine" means the strategy YAML changes substantively in response to the Critic's concern — not just "acknowledged, proceeding as planned."

**Scenario under test:** Engineer designs a strategy. Critic identifies a specific flaw (e.g., too many correlated features, no out-of-sample validation, potential lookahead). Director relays with synthesis. Engineer revises the strategy — removes correlated features, adjusts the split, fixes the leak. The final strategy is measurably different from the first draft.

**Validation Steps:**

1. **Load the `ke2e` skill** before designing any validation
2. **Invoke ke2e-test-scout** with: "Squad v2 debate: Director mediates 2+ turn Engineer ↔ Critic exchange. Critic identifies specific design flaw. Engineer revises strategy YAML substantively (not just acknowledging). Strategy before and after revision are diffable and different."
3. **Invoke ke2e-test-runner** with the identified test recipe
4. **Tests must exercise real Claude sessions with real debate**

**Success Criteria:**
- [ ] 2+ turn exchange between Engineer and Critic (via Director relay)
- [ ] Critic identifies at least one specific, actionable design concern
- [ ] Engineer produces a revised strategy that addresses the specific concern
- [ ] Strategy YAML differs substantively before and after (diffable evidence)
- [ ] Director synthesized perspectives (didn't raw-forward between agents)
- [ ] Director resolved the debate with a clear decision
- [ ] Debate metadata in CycleResult: turns, roles, whether revised, resolution summary

**Evidence Required:**
- Debate transcript: Director → Critic → Director → Engineer → Director sequence with synthesis visible
- Strategy YAML v1 (pre-critique) and v2 (post-revision) with diff
- Debate metadata from CycleResult
- Director's synthesis messages (proving it distilled, not forwarded)
