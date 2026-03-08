---
design: docs/designs/predictive-features/regime-detection/DESIGN.md
architecture: docs/designs/predictive-features/regime-detection/ARCHITECTURE.md
---

# M10: Agent Integration

**Thread:** All (Regime + Context + External)
**JTBD:** "As a researcher, I want the evolution system to generate ensemble configs, evolve per-regime strategies, and evaluate regime routing effectiveness so the system can autonomously discover optimal multi-model compositions."
**Depends on:** M7 (Ensemble + Regime Backtest), M8 (Context Gate)
**Tasks:** 5

---

## Task 10.1: Update Design Agent Prompt with Ensemble Awareness

**File(s):**
- `ktrdr/agents/design_sdk_prompt.py` (extend design brief)

**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Update the design agent's system prompt to be aware of regime classification, context classification, and ensemble composition. The agent should be able to generate: regime classifier strategies, context classifier strategies, per-regime signal strategies, and ensemble configuration YAMLs.

**Implementation Notes:**
- Add to design prompt: knowledge of `labels.source: regime` and `labels.source: context` (new label sources)
- Add: ensemble config YAML format (models, composition, rules)
- Add: `output_type` values and their meaning
- Add: context_data section for external data strategies
- The agent should understand: "generate a regime classifier" vs "generate a trend-following signal model for the trending_up regime" vs "generate an ensemble config that routes to these models"
- Follow existing prompt structure in `design_sdk_prompt.py`

**Testing Requirements:**
- [ ] Design prompt includes regime/context/ensemble knowledge
- [ ] Generated regime strategy uses `labels.source: regime`
- [ ] Generated context strategy uses `labels.source: context`
- [ ] Generated ensemble config references correct model types

**Acceptance Criteria:**
- [ ] Design agent can generate strategies for all model types
- [ ] Design agent can generate ensemble configuration YAMLs
- [ ] Prompt includes external data awareness (context_data section)

---

## Task 10.2: Extend Assessment Workflow for Ensemble Evaluation

**File(s):**
- `ktrdr/agents/workers/` (assessment-related workers)

**Type:** CODING
**Estimated time:** 3 hours

**Description:**
Extend the assessment workflow to evaluate ensemble effectiveness. Assessment should: compare ensemble performance vs single-model baseline, evaluate regime classification quality (accuracy, persistence), evaluate context gate contribution (trades blocked, net effect), and report per-regime signal model quality.

**Implementation Notes:**
- Current assessment evaluates individual models. Extend to evaluate ensembles.
- Assessment inputs: ensemble config + backtest results
- Assessment outputs: regime accuracy, transition cost analysis, per-regime signal quality, context gate analysis (if present), overall ensemble vs baseline comparison
- Capability requests: the assessment agent should be able to request "better regime classifier" or "different signal model for ranging regime" or "adjust context gate parameters"
- Follow existing assessment worker patterns

**Testing Requirements:**
- [ ] Assessment processes ensemble backtest results
- [ ] Per-regime analysis included in assessment output
- [ ] Context gate contribution analyzed when present
- [ ] Capability requests reference specific ensemble components

**Acceptance Criteria:**
- [ ] Assessment evaluates ensemble as a composition, not just individual models
- [ ] Actionable feedback for improving specific ensemble components

---

## Task 10.3: Evolution Genome for Ensemble Composition

**File(s):**
- `ktrdr/evolution/genome.py` (or equivalent — add ensemble dimensions)

**Type:** CODING
**Estimated time:** 3 hours

**Description:**
Add ensemble-related dimensions to the evolution genome. The researcher should be able to evolve: regime classifier indicator sets, per-regime signal model strategies, ensemble routing parameters (regime_threshold, stability_bars), and context gate parameters (aligned_discount, counter_premium).

**Implementation Notes:**
- New genome dimensions:
  - `regime_labeling_params`: horizon, trending_threshold, vol_crisis_threshold
  - `context_labeling_params`: horizon, bullish_threshold, bearish_threshold
  - `ensemble_routing`: regime_threshold, stability_bars, on_regime_transition
  - `context_modifiers`: aligned_discount, counter_premium, neutral_effect
- Mutation operators for each dimension
- Crossover: regime params from parent A, signal strategies from parent B, etc.
- The researcher can independently evolve regime classifier vs signal models vs ensemble params
- This is where the Researcher gains true architectural evolution capability

**Testing Requirements:**
- [ ] Genome includes ensemble-related dimensions
- [ ] Mutation produces valid parameter values
- [ ] Crossover respects dimension boundaries
- [ ] Default genome produces a valid ensemble config

**Acceptance Criteria:**
- [ ] Researcher can evolve ensemble composition parameters
- [ ] Genome dimensions cover regime, context, and routing parameters

---

## Task 10.4: End-to-End Ensemble Evolution Run

**File(s):** None (execution/evaluation task)
**Type:** MIXED
**Estimated time:** 4 hours

**Description:**
Run a multi-generation evolution cycle where the researcher generates regime classifier, per-regime signal models, and ensemble configs. Assess each generation's ensemble. Verify the system autonomously improves ensemble composition.

**Implementation Notes:**
- This is the capstone test — does the full adult brain architecture work as an integrated system?
- Setup: initial genome with seed strategies + default ensemble params
- Run: 3-5 generations with regime + signal model + ensemble evolution
- Evaluate: does Sharpe improve? Does regime routing add value? Does context gate help?
- Document: what the researcher discovered, what mutations worked, what didn't
- This requires M1's multi-TF fix (for multi-TF signal strategies), M7's ensemble runner, and M8's context gate

**Acceptance Criteria:**
- [ ] Multi-generation evolution run completes
- [ ] Researcher generates valid ensemble configurations
- [ ] Assessment evaluates ensemble effectiveness
- [ ] Some improvement observed across generations (or clear documentation of why not)

---

## Task 10.5: Validation

**File(s):** None (validation task)
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Validate the full agent integration pipeline.

**Validation Steps:**
1. Load the `ke2e` skill before designing any validation
2. Invoke `ke2e-test-scout` with: "Run an agent research cycle that generates a regime classifier strategy, trains it, generates per-regime signal strategies, trains them, creates an ensemble config, runs ensemble backtest, and assesses the results. The full cycle must complete with ensemble evaluation."
3. Invoke `ke2e-test-runner` with the identified test recipes
4. Tests must exercise real infrastructure — real agent, real training, real backtest
5. Verify: strategies generated, models trained, ensemble config created, backtest runs, assessment produced

**Thread-Level JTBD Verification:**
This milestone verifies all three thread-level JTBDs:
- **Regime Detection:** "System detects market regime and routes to specialized strategies for better risk-adjusted returns than unrouted." → Verified by ensemble backtest results showing per-regime routing.
- **Multi-TF Context:** "Daily trend context adjusts trading aggressiveness to trade with macro trend." → Verified by context gate metrics in ensemble results.
- **External Data:** "Train and backtest strategies using interest rate differentials, cross-pair context, and positioning data." → Verified by strategies using context_data section.

**Acceptance Criteria:**
- [ ] Full agent cycle: design → train → ensemble → backtest → assess
- [ ] Ensemble includes regime routing + context gate
- [ ] Assessment provides actionable feedback on ensemble composition
- [ ] All three thread-level JTBDs can be demonstrated
