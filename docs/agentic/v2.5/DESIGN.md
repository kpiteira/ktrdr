# v2.5 Agent Reliability: Design

## Problem Statement

The agent research cycle fails silently on multi-symbol and multi-timeframe strategies, producing contradictory metrics (0% training accuracy but backtest runs anyway with 7% win rate). These failures pollute experiment history, waste compute, and block testing of key hypotheses (H_001, H_004) that could break the 64.2% accuracy plateau.

Root causes identified in [INVESTIGATION_failed_experiments.md](INVESTIGATION_failed_experiments.md):

1. Training returns zeros instead of failing when `X_test = None`
2. Backtest runs even when training clearly failed
3. Quality gates bypassed during testing
4. No mechanism to guide agent toward known-working configurations

---

## Goals

What we're trying to achieve:

1. **Catch catastrophic failures** — 0% accuracy or 0 trades should be detected and rejected, not recorded as valid experiments

2. **Fail loudly** — When training can't produce test data, raise an error instead of returning zeros

3. **Guide the agent** — Introduce a "research brief" mechanism to steer experiments toward specific configurations (for E2E testing and focused research)

4. **Enable exploration** — Gates should be lax enough for Baby stage (allow learning, catch disasters)

5. **Prove fixes work** — Real E2E tests that exercise the full pipeline, not just unit tests

6. **Introduce maturity model** — Document the Baby→Teenager progression concept, implement Baby stage now

7. **Fix multi-symbol/multi-timeframe pipelines** (last priority) — Investigate and fix root causes of data alignment issues so agent can test H_001 and H_004 hypotheses

---

## Non-Goals (Out of Scope)

What we're explicitly NOT doing in v2.5:

1. **Automatic maturity progression** — Gates stay at Baby stage; automatic tightening is v3 scope

2. **Hard constraints system** — No code-enforced limits on what agent can design; brief is guidance, not enforcement

3. **Remove bypass_gates flag** — Keep it for debugging, just don't use it in production

---

## User Experience

### Scenario 1: E2E Test with Research Brief

A developer wants to validate the full pipeline works with a simple configuration.

```python
# In E2E test
result = start_research(
    brief="Validate RSI indicator on EURUSD 1h. "
          "Use single symbol, single timeframe, single indicator. "
          "This is a validation run to prove the pipeline works.",
    model="haiku"
)

# Agent receives brief in its prompt, designs a simple RSI strategy
# Training runs, produces valid metrics (e.g., 45% accuracy)
# Gates pass (Baby mode: accuracy > 10%)
# Backtest runs, produces trades
# Experiment saved to memory with full context
```

### Scenario 2: Catastrophic Failure Caught

Agent designs a multi-symbol strategy that fails during training.

```text
1. Agent designs: RSI + Fisher on EURUSD, GBPUSD, USDJPY
2. Training starts
3. Multi-symbol data combination fails → X_test = None
4. NEW BEHAVIOR: TrainingDataError raised (not silent zeros)
5. Error propagates to assessment
6. Experiment recorded with status="failed", error_message="..."
7. Backtest does NOT run (training failed)
8. Agent learns from failure in next cycle
```

### Scenario 3: Baby Mode Gates

Agent completes training with mediocre results.

```text
Training results:
- test_accuracy: 0.32 (32%)
- loss_decrease: 0.05 (5%)

Gate check (Baby mode):
- min_accuracy: 0.10 → PASS (32% > 10%)
- min_loss_decrease: -0.5 → PASS (5% > -50%, didn't regress badly)

Result: Backtest proceeds. We're exploring, not optimizing.
```

### Scenario 4: Zero Accuracy Caught

Training produces no learning signal.

```text
Training results:
- test_accuracy: 0.0 (0%)

Gate check (Baby mode):
- Catastrophic check: accuracy == 0 → FAIL
- Reason: "Training completely failed (0% accuracy)"

Result: Backtest skipped. Experiment recorded as failed.
```

---

## Key Decisions

### Decision 1: Research Brief as Prompt Guidance

**Choice:** Add `brief` parameter that becomes part of the agent's system prompt. No hard enforcement.

**Alternatives considered:**

- Hard constraints (reject strategies that violate rules) — Too rigid, adds complexity
- No guidance mechanism — Can't steer E2E tests toward simple configs

**Rationale:** Natural language guidance is flexible and aligns with how the agent already works. If agents consistently ignore briefs, we can add enforcement later.

### Decision 2: Baby Stage Gate Thresholds

**Choice:** Very lax thresholds that only catch disasters:

```python
min_accuracy: 0.10        # Only catch 0-10% (completely broken)
min_loss_decrease: -0.5   # Allow regression while exploring
min_win_rate: 0.10        # Only catch catastrophic backtest
```

**Alternatives considered:**

- Current thresholds (45% accuracy, 20% loss decrease) — Too strict for exploration
- No gates — Wastes resources on broken experiments

**Rationale:** We're in Baby stage. The goal is to gather data and learn, not optimize. Gates should only catch obviously broken training.

### Decision 3: Fail Loudly on Missing Test Data

**Choice:** Raise `TrainingDataError` when `X_test is None` instead of returning zeros.

**Alternatives considered:**

- Keep returning zeros, catch at gate level — Hides the root cause
- Log warning and continue — Same problem, silent failure

**Rationale:** Silent failures hide bugs. If training can't produce test data, that's worth investigating, not masking with zeros.

### Decision 4: Record Failed Experiments

**Choice:** Save all experiments to memory, including failures, with appropriate status and error messages.

**Alternatives considered:**

- Only record successes — Loses valuable negative signal
- Don't record gate failures — Misses patterns in what doesn't work

**Rationale:** Failed experiments teach the agent what NOT to do. The memory system should capture the full learning journey.

### Decision 5: Use Haiku for E2E Tests

**Choice:** E2E tests use `model="haiku"` to minimize cost and latency.

**Alternatives considered:**

- Use Opus for higher quality — Too expensive for frequent testing
- Mock the LLM — Doesn't test the real pipeline

**Rationale:** Haiku is fast and cheap. E2E tests should run frequently to catch regressions.

---

## Maturity Model (Concept Introduction)

v2.5 introduces the **maturity model** as a concept. Only Baby stage is implemented now.

### The Progression

| Stage | Accuracy Gate | Loss Gate | Win Rate Gate | Focus |
|-------|--------------|-----------|---------------|-------|
| **Baby** (v2.5) | 10% | -50% | 10% | Explore, gather data |
| Toddler | 35% | 0% | 30% | Validate early patterns |
| Child | 45% | 10% | 40% | Consolidate learnings |
| Pre-teen | 55% | 15% | 45% | Optimize within patterns |
| Teenager | 60% | 20% | 50% | Production ready |

### How Progression Will Work (v3 scope)

In v3, the system will automatically progress based on:

- Number of successful experiments
- Consistency of results
- Hypothesis validation rate

For v2.5, we hardcode Baby stage and document the model for future implementation.

---

## Open Questions

Issues to resolve during architecture or implementation:

1. **How to surface brief in agent prompt?** — Append to system prompt? Separate section? Need to review prompt structure.

2. **What metadata to add to failed experiments?** — Error type, stack trace, which stage failed?

3. **Should gates be configurable per-experiment?** — Or always use the stage defaults?

4. **How to handle partial failures?** — Training succeeds but backtest fails?

---

## Success Criteria

After v2.5 implementation:

1. ✅ E2E test passes with simple RSI config (brief-guided)
2. ✅ 0% accuracy experiments are caught and rejected
3. ✅ Missing test data raises error (not silent zeros)
4. ✅ Failed experiments recorded with error context
5. ✅ Gates set to Baby mode thresholds
6. ✅ Backtest skipped when training fails
7. ✅ Maturity model documented in roadmap

---

*Created: 2025-12-31*
*Status: Draft — awaiting review*
