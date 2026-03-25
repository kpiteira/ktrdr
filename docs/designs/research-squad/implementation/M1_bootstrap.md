---
design: docs/designs/research-squad/DESIGN.md
architecture: docs/designs/research-squad/ARCHITECTURE.md
---

# M1: Squad Bootstrap + First Cycle

## Goal
The squad produces an experiment informed by prior knowledge (seeded history), with visible tension between agent perspectives (Inventor proposes something novel, Quant grounds it in reality, Critic demands rigor — not consensus), and evaluates real backtest results honestly. One full cycle proving the mechanism produces qualitatively different output than a single agent would.

## Tasks

### Task 1.1: Agent Charters

**File(s):** `.squad/agents/{director,inventor,quant,engineer,critic,architect,scout,scribe}/charter.md`
**Type:** MIXED (writing + research into ktrdr codebase for Engineer/Architect)
**Estimated time:** 3-4 hours

**Description:**
Write the charter for each of the 8 squad agents. Each charter defines who the agent is, how it thinks, what it owns, and how it interacts with other roles. Charters are the system prompts for each agent — they must be specific enough that the agent behaves differently from the others.

**Implementation Notes:**
- Director: strategic, pattern-matching across experiments, owns prioritization and frontiers
- Inventor: divergent, cross-domain analogies, explicitly instructed to push for novelty and disagree with obvious approaches
- Quant: domain-grounded in market microstructure, knows cost models, skeptical of academic metrics
- Engineer: knows ktrdr codebase (strategy grammar, model types, ensemble runner, data pipeline), translates ideas to YAML
- Critic: adversarial, evidence-based, owns the tiered evaluation framework (Tier 1/2/3 from DESIGN.md)
- Architect: gap-analysis, forward-looking, knows what's buildable vs what's missing, produces GitHub issue specifications
- Scout: investigative, maintains bibliography, skeptical of academic claims (no transaction costs, in-sample only), uses WebSearch/WebFetch
- Scribe: synthetic, organizational, doesn't debate — observes, records, synthesizes

Each charter should include:
- Identity and expertise (2-3 paragraphs)
- Thinking style and approach
- What they own (specific responsibilities)
- How they interact with other roles (who they challenge, who they support)
- Output format expected from them
- Explicit failure mode they prevent (from DESIGN.md table)

**Testing Requirements:**
- [ ] Each charter is specific enough to produce distinguishable behavior (not generic "be helpful")
- [ ] Engineer charter references real ktrdr components (strategy grammar v3, LSTM, ensemble runner, etc.)
- [ ] Critic charter includes the tiered evaluation framework
- [ ] Scout charter includes quality filters for external research

**Acceptance Criteria:**
- [ ] 8 charter files created in `.squad/agents/*/charter.md`
- [ ] Each charter is 200-500 words (specific but not overwhelming)
- [ ] Charters reference the design decisions they embody

---

### Task 1.2: Knowledge Base Templates + Seeding

**File(s):** `.squad/knowledge/{experiments,hypotheses,components,decisions,frontiers,synthesis}.md`, `.squad/team.md`, `.squad/agents/*/history.md`
**Type:** MIXED (templates + research into existing experiment history)
**Estimated time:** 2-3 hours

**Description:**
Create the shared knowledge base structure and seed it with everything we've learned from prior work. This is not starting from zero — the squad inherits the full history of signal model evolution, H_003 experiment, and all validated/refuted hypotheses.

**Implementation Notes:**
- `team.md`: roster of 8 agents with one-line descriptions and current focus
- `experiments.md`: seed with synthesized history:
  - v1.5 experiments (RSI ceiling at 64.2%)
  - Signal model evolution M1-M5 (TB labels, focal loss, Gaussian MFs, purged splits — all mechanisms work, features don't carry signal for MLP)
  - H_003 experiment (LSTM 61% val vs MLP 35%, LSTM -0.21% OOS vs MLP 0 trades)
- `hypotheses.md`: curate from existing `memory/hypotheses.yaml`:
  - Keep H_001-006 (original thoughtful ones) and H_INV_001-005 (investigated)
  - Mark H_003 as CONFIRMED
  - Discard 300+ auto-generated noise
  - Add new hypotheses from H_003 results (cross-asset, attention, exit timing)
- `components.md`: current catalog (regime classifier 72%, LSTM signal 61% val, MLP dead, ensemble runner, CFTC provider, etc.)
- `decisions.md`: seed with established decisions:
  - "MLP is dead for signal prediction on standard indicators"
  - "Temporal modeling (LSTM) finds signal MLP can't"
  - "Standard indicators have a ceiling regardless of architecture"
  - "Gaussian MFs with hybrid encoding eliminate dead zones"
- `frontiers.md`: empty (Director populates in first cycle)
- `synthesis.md`: empty (Scribe populates after first synthesis)
- `history.md` per agent: empty (grows from first cycle)

**Testing Requirements:**
- [ ] All template files created and parseable
- [ ] experiments.md contains at least 5 seeded experiments with structured format
- [ ] hypotheses.md contains curated list (< 20 entries, all meaningful)
- [ ] components.md accurately reflects current ktrdr capabilities
- [ ] decisions.md captures the key architectural decisions from prior work

**Acceptance Criteria:**
- [ ] Full `.squad/` directory structure created matching ARCHITECTURE.md
- [ ] Knowledge base seeded with real experiment history (not placeholder)
- [ ] Any agent reading these files gets an accurate picture of where we are

---

### Task 1.3: Coordinator Logic

**File(s):** `.squad/coordinator.py` (or `.squad/coordinator.md` as a Claude Code skill)
**Type:** CODING
**Estimated time:** 3-4 hours

**Description:**
Build the Coordinator that orchestrates one squad cycle. The Coordinator spawns agents in the correct order, routes context between them, collects responses, and assembles the final output (experiment spec + state updates).

**Implementation Notes:**
For M1 this can be a structured prompt/skill that the main Claude Code session executes, rather than a standalone Python script. The Coordinator:

1. Reads all `.squad/` files to build context
2. Spawns agents in order: Scribe (ORIENT) → Scout (STRATEGIZE) → Director → Inventor → Quant → Critic → Engineer (DESIGN) → Architect
3. Routes context per the architecture table:
   - Director gets: scribe briefing + scout findings + own history + frontiers
   - Inventor gets: director proposal + scout findings + own history + components
   - Quant gets: inventor proposal + own history
   - Critic gets: inventor proposal + quant assessment + own history
   - Engineer gets: all perspectives combined + components + own history
   - Architect gets: engineer spec + capability-gaps + own history
4. Collects all responses into a cycle transcript
5. Returns: experiment spec (YAML), hypothesis, capability requests, agent history updates

Each agent spawn should include:
- The agent's charter.md content
- The agent's history.md content
- The specific context for this phase (per architecture table)
- A clear task instruction ("Propose the next frontier", "Find flaws in this plan", etc.)

**Testing Requirements:**
- [ ] Coordinator successfully spawns at least 3 agents in sequence
- [ ] Context routing is correct (Critic doesn't see Inventor's reasoning process)
- [ ] Output contains a parseable experiment specification
- [ ] Agent responses are collected and accessible

**Acceptance Criteria:**
- [ ] One full ORIENT → STRATEGIZE → DESIGN flow executes without error
- [ ] Each agent produces a substantive response (not empty or generic)
- [ ] The Engineer produces a valid strategy YAML
- [ ] The Architect produces a feasibility assessment

---

### Task 1.4: Experiment Executor

**File(s):** `.squad/executor.py` (or shell script)
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Build the component that takes an experiment specification (strategy YAML + hypothesis) from the squad and executes it via ktrdr CLI. Handles: writing the strategy file, triggering training, polling for completion, triggering backtest, polling, and collecting results.

**Implementation Notes:**
- Write strategy YAML to `~/.ktrdr/shared/strategies/{name}.yaml`
- Run: `uv run ktrdr train {name} --start 2015-01-01 --end 2020-12-31`
- Poll operation status (don't use `--follow` — poll via API or `ktrdr status`)
- On training completion, extract model path from operation result
- Run: `uv run ktrdr backtest {name} --start 2021-01-01 --end 2025-01-01 --model-path {path}`
- Poll until complete
- Parse results into structured format for the squad (JSON metrics)
- Handle failures gracefully: training failure, backtest failure, timeout

Training dates (2015-2020 train, 2021-2025 OOS) should be configurable but default to these proven windows.

**Testing Requirements:**
- [ ] Executor writes valid strategy YAML
- [ ] Executor starts training and polls to completion
- [ ] Executor starts backtest with correct model path
- [ ] Executor handles training failure gracefully (returns error, doesn't crash)
- [ ] Results parsed into structured format (dict with Sharpe, win_rate, trades, etc.)

**Acceptance Criteria:**
- [ ] Can execute a complete train → backtest cycle from a strategy YAML
- [ ] Returns structured results or structured error
- [ ] Does not use `--follow` (polls instead)

---

### Task 1.5: First Full Cycle (Manual)

**File(s):** `.squad/loop/current-experiment.md`, `.squad/loop/last-result.md`, `.squad/knowledge/experiments.md` (append)
**Type:** VALIDATION
**Estimated time:** 2-3 hours (including training time)

**Description:**
Execute one complete research cycle manually. This is the integration test: Coordinator runs the squad → squad produces experiment → Executor runs it → results come back → Coordinator runs EVALUATE phase (resume Critic + Quant) → Scribe records learnings.

**Implementation Notes:**
1. Run the Coordinator (Task 1.3) through ORIENT → STRATEGIZE → DESIGN
2. Verify the experiment spec makes sense given the seeded history
3. Run the Executor (Task 1.4) with the experiment spec
4. Wait for training + backtest (30-60 min depending on model type)
5. Run EVALUATE: resume Critic with results, spawn Quant assessment
6. Run LEARN: spawn Scribe to record everything
7. Verify state updates: experiments.md has a new entry, hypotheses.md updated

**Testing Requirements:**
- [ ] Squad produces an experiment informed by seeded history (references known decisions like "MLP is dead" or "LSTM finds temporal signal")
- [ ] At least 2 agents visibly disagree during the cycle (Inventor vs Quant, or Critic challenging the plan)
- [ ] Experiment trains and backtests without error
- [ ] Critic evaluates real results using Tier 1 metrics (not self-assessment)
- [ ] Scribe produces state updates that could be read by the next cycle
- [ ] Agent histories contain meaningful learnings from this cycle

**Acceptance Criteria:**
- [ ] One complete cycle: ORIENT → STRATEGIZE → DESIGN → EXECUTE → EVALUATE → LEARN
- [ ] Experiment spec is informed by prior knowledge AND agent debate (not what a single agent would produce)
- [ ] Visible tension: at least one agent pushes back on the plan and the plan is modified as a result
- [ ] Real backtest metrics produced and evaluated by Critic
- [ ] `.squad/knowledge/experiments.md` has a new structured entry
- [ ] At least 3 agent `history.md` files have new content

---

### Task 1.6: E2E Validation

**File(s):** E2E test recipe
**Type:** VALIDATION
**Estimated time:** 1-2 hours

**Description:**
Validate the full M1 deliverable using the ke2e testing framework.

1. Load the `ke2e` skill
2. Invoke ke2e-test-scout with validation requirements:
   - Squad produces an experiment from seeded history
   - Experiment trains and backtests in sandbox
   - Results are evaluated by Critic and recorded by Scribe
3. Invoke ke2e-test-runner to execute against real sandbox infrastructure
4. Tests must exercise real train + backtest operations, not mocks

**Acceptance Criteria:**
- [ ] ke2e test designed and cataloged
- [ ] Test passes against real sandbox (training completes, backtest produces results)
- [ ] Squad state files updated after the cycle

## Completion Checklist
- [ ] 8 agent charters written with distinct voices
- [ ] Knowledge base seeded with real experiment history
- [ ] Coordinator orchestrates agent spawning and context routing
- [ ] Executor runs train + backtest from strategy YAML
- [ ] One full cycle produces a real experiment with real results
- [ ] State updates persist to disk for the next cycle
