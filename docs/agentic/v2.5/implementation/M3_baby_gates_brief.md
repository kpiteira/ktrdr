---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 3: Baby Gates + Brief

**Branch:** `feature/v2.5-m3-baby-gates`
**Depends on:** M2 (gate rejection → memory)

**Goal:** Update gate thresholds to Baby mode (lax exploration) and add `brief` parameter to guide agent design.

---

## E2E Test Scenario

**Purpose:** Verify brief guides design and Baby gates allow exploration

```bash
# Prerequisites: Backend running, real workers (not stubs)

# 1. Trigger research with a brief
curl -X POST http://localhost:8000/api/v1/agent/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "brief": "Design a simple RSI strategy for EURUSD 1h only. Single indicator, single symbol, single timeframe.",
    "model": "haiku"
  }'

OP_ID=$(curl -s http://localhost:8000/api/v1/agent/status | jq -r '.operation_id')

# 2. Poll until cycle completes (may take several minutes with real training)
for i in {1..180}; do
  PHASE=$(curl -s http://localhost:8000/api/v1/agent/status | jq -r '.phase')
  echo "Phase: $PHASE"
  if [ "$PHASE" = "idle" ]; then break; fi
  sleep 5
done

# 3. Check experiment was saved
LATEST=$(ls -t memory/experiments/*.yaml | head -1)

# 4. Verify strategy matches brief guidance
cat "$LATEST" | grep -A 20 "strategy_config"
# Should show: single symbol (EURUSD), single timeframe (1h), RSI indicator

# 5. Verify Baby gates allowed exploration
# Even 30% accuracy should pass (old threshold was 45%)
cat "$LATEST" | grep -E "test_accuracy|status"
# Expected: status: completed (or gate_rejected only if < 10%)
```

**Success Criteria:**
- [ ] Brief parameter accepted by API
- [ ] Agent designs strategy matching brief guidance
- [ ] 30% accuracy passes Baby gates (would fail 45% threshold)
- [ ] Experiment saved with full results

---

## Task 3.1: Update Gate Thresholds to Baby Mode

**File:** `ktrdr/agents/gates.py`
**Type:** CODING
**Estimated time:** 45 min

**What to do:**

Update default thresholds to Baby stage values:

```python
# gates.py

@dataclass
class GateConfig:
    # Baby stage thresholds - allow exploration, catch disasters
    min_accuracy: float = 0.10        # Only catch 0-10% (completely broken)
    max_loss: float = 0.8             # Keep existing
    min_loss_decrease: float = -0.5   # Allow regression while exploring
    min_win_rate: float = 0.10        # Only catch catastrophic backtest


def check_training_gate(metrics: dict, config: GateConfig | None = None) -> tuple[bool, str]:
    """Check if training metrics pass the gate."""
    if config is None:
        config = GateConfig()

    accuracy = metrics.get("test_accuracy", 0)

    # Catastrophic failure check (always applies)
    if accuracy == 0.0:
        return False, "training_completely_failed (0% accuracy)"

    if accuracy < config.min_accuracy:
        return False, f"accuracy_too_low ({accuracy:.1%} < {config.min_accuracy:.1%})"

    # Loss decrease check (Baby mode allows regression)
    loss_decrease = metrics.get("loss_decrease", 0)
    if loss_decrease < config.min_loss_decrease:
        return False, f"loss_regressed_too_much ({loss_decrease:.1%} < {config.min_loss_decrease:.1%})"

    return True, "passed"
```

**Tests:**

- Unit: `tests/unit/agent_tests/test_gates.py`
  - [ ] Default thresholds are Baby values (10%, -50%, 10%)
  - [ ] 0% accuracy always fails (catastrophic check)
  - [ ] 8% accuracy fails Baby gate
  - [ ] 15% accuracy passes Baby gate
  - [ ] 30% accuracy passes Baby gate
  - [ ] 50% loss regression (decrease = -0.5) passes Baby gate

**Acceptance Criteria:**

- [ ] Default GateConfig uses Baby thresholds
- [ ] 0% accuracy always caught as catastrophic
- [ ] Thresholds documented in code comments

---

## Task 3.2: Add Brief Parameter to API

**File:** `ktrdr/api/routes/agent.py`, `ktrdr/api/models/agent.py`
**Type:** CODING
**Estimated time:** 1 hour

**What to do:**

Add `brief` parameter to the trigger endpoint:

```python
# ktrdr/api/models/agent.py

class AgentTriggerRequest(BaseModel):
    trigger_reason: str | None = None
    brief: str | None = None  # NEW: guidance for the designer
    model: str = "opus"  # "opus" or "haiku"
```

```python
# ktrdr/api/routes/agent.py

@router.post("/trigger")
async def trigger_agent(
    request: AgentTriggerRequest,
    agent_service: AgentService = Depends(get_agent_service),
):
    result = await agent_service.trigger(
        trigger_reason=request.trigger_reason,
        brief=request.brief,  # Pass through
        model=request.model,
    )
    return AgentTriggerResponse(...)
```

**Tests:**

- Unit: `tests/unit/api/test_agent_endpoint.py`
  - [ ] POST /agent/trigger accepts `brief` parameter
  - [ ] Brief parameter is optional (null allowed)
  - [ ] Brief parameter passed to service

**Acceptance Criteria:**

- [ ] API accepts `brief` in request body
- [ ] Brief propagates to AgentService

---

## Task 3.3: Pass Brief Through to DesignWorker

**File:** `ktrdr/agents/service.py`, `ktrdr/agents/workers/research_worker.py`, `ktrdr/agents/workers/design_worker.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**What to do:**

Thread the `brief` parameter through the service layers to the design worker:

```python
# ktrdr/agents/service.py

async def trigger(
    self,
    trigger_reason: str | None = None,
    brief: str | None = None,
    model: str = "opus",
) -> dict:
    # Pass brief to research worker
    await self.research_worker.start(
        brief=brief,
        model=model,
    )
```

```python
# ktrdr/agents/workers/research_worker.py

async def start(self, brief: str | None = None, model: str = "opus"):
    self._brief = brief
    self._model = model
    # ...

async def _start_design(self, operation_id: str):
    result = await self.design_worker.run(
        operation_id=operation_id,
        brief=self._brief,
    )
```

```python
# ktrdr/agents/workers/design_worker.py

async def run(self, operation_id: str, brief: str | None = None) -> dict:
    prompt = get_strategy_designer_prompt(
        context=self._build_context(),
        brief=brief,
    )
    # ...
```

**Tests:**

- Integration: `tests/integration/agent_tests/test_brief_propagation.py`
  - [ ] Brief flows from API → service → research_worker → design_worker
  - [ ] Brief=None handled gracefully

**Acceptance Criteria:**

- [ ] Brief reaches DesignWorker
- [ ] No errors when brief is None

---

## Task 3.4: Inject Brief into Designer Prompt

**File:** `ktrdr/agents/prompts.py`
**Type:** CODING
**Estimated time:** 1 hour

**What to do:**

Update `get_strategy_designer_prompt()` to include brief:

```python
def get_strategy_designer_prompt(
    context: dict,
    brief: str | None = None,
) -> str:
    """Build the strategy designer system prompt."""

    prompt_parts = []

    # Add brief section if provided
    if brief:
        prompt_parts.append(f"""
## Research Brief

{brief}

Follow this brief carefully when designing your strategy. The brief provides specific guidance for this research cycle.

---
""")

    # Rest of prompt...
    prompt_parts.append("""
## Your Task

Design a trading strategy based on the context provided...
""")

    return "\n".join(prompt_parts)
```

**Tests:**

- Unit: `tests/unit/agent_tests/test_prompts.py`
  - [ ] Brief included in prompt when provided
  - [ ] Brief section omitted when None
  - [ ] Brief text appears verbatim in prompt

**Acceptance Criteria:**

- [ ] Brief appears in prompt with clear section header
- [ ] Prompt still valid when brief is None
- [ ] No special characters escaped/broken

---

## Milestone 3 Completion Checklist

- [ ] Task 3.1: Gate thresholds updated to Baby mode
- [ ] Task 3.2: API accepts brief parameter
- [ ] Task 3.3: Brief propagates to DesignWorker
- [ ] Task 3.4: Brief injected into prompt
- [ ] M1 E2E test still passes
- [ ] M2 E2E test still passes
- [ ] M3 E2E test passes (brief-guided research completes)
- [ ] Unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] Code committed to branch: `feature/v2.5-m3-baby-gates`

---

## Notes

**Baby vs Current thresholds:**

| Metric | Current | Baby |
|--------|---------|------|
| min_accuracy | 45% | 10% |
| min_loss_decrease | 20% | -50% |
| min_win_rate | 20% | 10% |

**Brief is guidance only:** No enforcement. If agent ignores brief, log it but don't fail.

**Next:** M4 (Fix Multi-Symbol) - with Baby gates and clear errors, we can debug multi-symbol issues
