# Milestone 8: Cost Optimization

**Branch**: `feature/agent-mvp`
**Builds On**: M7 (Budget & Observability)
**Capability**: Reduce token costs by 60%+ through prompt optimization and model configuration

---

## Why This Milestone

M7 revealed a critical cost issue: the design phase uses ~33k input tokens ($1.40) instead of the expected ~4k tokens ($0.15). This is because:

1. **Discovery round trips** - Claude calls `get_available_indicators`, `get_available_symbols`, `get_recent_strategies` as tools, each requiring an API round trip
2. **Message accumulation** - Each API call sends the full conversation history, compounding token usage
3. **No model configuration** - Hardcoded to Sonnet 4 instead of configurable Opus 4.5/Haiku 4.5

### Current Token Flow (Design Phase)

```text
Call 1: System (~2k) + User (~0.5k) + Tools (~2k) = ~4.5k input
        → Claude requests get_recent_strategies

Call 2: Previous (~4.5k) + Tool result (~1k) = ~5.5k input
        → Claude requests get_available_indicators

Call 3: Previous (~5.5k) + Tool result (~4k) = ~9.5k input
        → Claude generates strategy and calls save_strategy_config

Call 4: Previous (~9.5k) + Tool result (~0.5k) = ~10k input
        → Claude confirms

TOTAL: 4.5k + 5.5k + 9.5k + 10k = ~30k input tokens
```

### Optimized Token Flow (Target)

```text
Call 1: System (~2k) + User with context (~3k) + Tools (~1k) = ~6k input
        → Claude generates strategy and calls save_strategy_config

Call 2: Previous (~6k) + Tool result (~0.5k) = ~6.5k input
        → Claude confirms

TOTAL: 6k + 6.5k = ~12.5k input tokens (60% reduction)
```

---

## E2E Test

```bash
# Set test model
export AGENT_MODEL=claude-haiku-4-5-20250514

# Run cycle and check cost
ktrdr agent trigger
# Wait for design phase

ktrdr agent budget
# Expected: Spend ~$0.05-0.10 for design (vs $1.40 before)

# Check token usage in operation
ktrdr operations status <design_op_id>
# Expected: input_tokens < 15000 (vs 33000 before)

# Verify model in logs
docker logs ktrdr-backend 2>&1 | grep "model="
# Expected: Shows claude-haiku-4-5-20250514
```

---

## Task 8.1: Pre-populate Design Prompt with Context

**File(s)**: `ktrdr/agents/prompts.py`, `ktrdr/agents/workers/design_worker.py`
**Type**: CODING

**Description**: Include available indicators, symbols, timeframes, and recent strategies directly in the user prompt instead of requiring tool calls.

**Implementation Notes**:

```python
# In design_worker.py - gather context before prompt
async def run(self, parent_operation_id: str) -> dict[str, Any]:
    # Gather context data upfront (these are fast API calls internally)
    available_indicators = await self._get_indicators_compact()
    available_symbols = await self._get_symbols_with_timeframes()
    recent_strategies = await self._get_recent_strategies(limit=5)

    # Build prompt with context embedded
    prompt_data = get_strategy_designer_prompt(
        trigger_reason=TriggerReason.START_NEW_CYCLE,
        operation_id=op.operation_id,
        phase="designing",
        # Context now passed directly, not discovered via tools
        available_indicators=available_indicators,
        available_symbols=available_symbols,
        recent_strategies=recent_strategies,
    )
```

**Compact Format for Indicators** (saves ~50% tokens):
```python
def _format_indicators_compact(indicators: list) -> str:
    """Format indicators in token-efficient way."""
    # Instead of full JSON objects, use compact format:
    # RSI(period:14,source:close) - momentum
    # MACD(fast:12,slow:26,signal:9) - trend
    lines = []
    for ind in indicators:
        params = ",".join(f"{p['name']}:{p['default']}" for p in ind.get('parameters', []))
        lines.append(f"{ind['name']}({params}) - {ind.get('type', 'other')}")
    return "\n".join(lines)
```

**Compact Format for Symbols**:
```python
def _format_symbols_compact(symbols: list) -> str:
    """Format symbols with available timeframes."""
    # AAPL: 1m,5m,15m,1h,4h,1d (2020-01-01 to 2024-12-01)
    # EURUSD: 1h,4h,1d (2015-01-01 to 2024-12-01)
    lines = []
    for sym in symbols:
        tfs = ",".join(sym.get('timeframes', []))
        date_range = f"({sym.get('start_date', '?')} to {sym.get('end_date', '?')})"
        lines.append(f"{sym['symbol']}: {tfs} {date_range}")
    return "\n".join(lines)
```

**Unit Tests**:
- [ ] Test: Compact indicator format produces valid string
- [ ] Test: Compact symbol format includes timeframes
- [ ] Test: Design prompt includes context data
- [ ] Test: Design phase completes without discovery tool calls

**Acceptance Criteria**:
- [ ] Design prompt includes indicators, symbols, timeframes, recent strategies
- [ ] Format is human-readable but token-efficient
- [ ] No data truncation (all options available to Claude)
- [ ] Design phase makes ≤2 API calls (vs 4+ before)

---

## Task 8.2: Remove Discovery Tools from Design Phase

**File(s)**: `ktrdr/agents/tools.py`, `ktrdr/agents/workers/design_worker.py`
**Type**: CODING

**Description**: Remove `get_available_indicators`, `get_available_symbols`, `get_recent_strategies` from design phase tools since context is now in the prompt.

**Implementation Notes**:

```python
# In tools.py - create design-specific tool subset
DESIGN_PHASE_TOOLS = [
    tool for tool in AGENT_TOOLS
    if tool["name"] in ["validate_strategy_config", "save_strategy_config"]
]

# In design_worker.py
result = await self.invoker.run(
    prompt=prompt_data["user"],
    tools=DESIGN_PHASE_TOOLS,  # Only validation/save tools
    system_prompt=prompt_data["system"],
    tool_executor=self.tool_executor,
)
```

**Acceptance Criteria**:
- [ ] Design phase only has 2 tools: validate_strategy_config, save_strategy_config
- [ ] Discovery tools remain available for assessment phase (may need them)
- [ ] No regression in strategy quality

---

## Task 8.3: Add Model Configuration

**File(s)**: `ktrdr/agents/invoker.py`, `docker-compose.yml`, documentation
**Type**: CODING

**Description**: Make Claude model configurable via environment variable with validation.

**Implementation Notes**:

```python
# In invoker.py
VALID_MODELS = {
    # Production (high quality)
    "claude-opus-4-5-20250514": {"tier": "opus", "cost": "high"},
    # Development (balanced)
    "claude-sonnet-4-20250514": {"tier": "sonnet", "cost": "medium"},
    # Testing (fast, cheap)
    "claude-haiku-4-5-20250514": {"tier": "haiku", "cost": "low"},
}

DEFAULT_MODEL = "claude-opus-4-5-20250514"  # Production default

@dataclass
class AnthropicInvokerConfig:
    model: str = field(default_factory=lambda: os.getenv("AGENT_MODEL", DEFAULT_MODEL))

    def __post_init__(self):
        if self.model not in VALID_MODELS:
            logger.warning(
                f"Unknown model {self.model}, using {DEFAULT_MODEL}. "
                f"Valid models: {list(VALID_MODELS.keys())}"
            )
            self.model = DEFAULT_MODEL

        tier = VALID_MODELS[self.model]["tier"]
        logger.info(f"Agent using model: {self.model} (tier: {tier})")
```

**Environment Variables**:
```yaml
# docker-compose.yml (production)
backend:
  environment:
    AGENT_MODEL: claude-opus-4-5-20250514

# docker-compose.test.yml (testing)
backend:
  environment:
    AGENT_MODEL: claude-haiku-4-5-20250514
```

**Acceptance Criteria**:
- [ ] AGENT_MODEL env var controls model selection
- [ ] Default is claude-opus-4-5-20250514 (production quality)
- [ ] Invalid model falls back to default with warning
- [ ] Model logged at startup

---

## Task 8.4: Update Cost Estimation

**File(s)**: `ktrdr/agents/workers/research_worker.py`
**Type**: CODING

**Description**: Update cost estimation to use actual model pricing.

**Implementation Notes**:

```python
# Per-model pricing (as of Dec 2024, per 1M tokens)
# Source: https://www.anthropic.com/pricing
MODEL_PRICING = {
    "claude-opus-4-5-20250514": {"input": 5.0, "output": 25.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20250514": {"input": 1.0, "output": 5.0},
}

def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost based on actual model pricing."""
    model = os.getenv("AGENT_MODEL", "claude-opus-4-5-20250514")
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-opus-4-5-20250514"])

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    return input_cost + output_cost
```

**Acceptance Criteria**:
- [ ] Cost estimation uses model-specific pricing
- [ ] Budget tracking reflects actual costs
- [ ] Haiku cycles cost ~$0.01-0.02 per phase
- [ ] Opus cycles cost ~$0.05-0.10 per phase (after optimization)

---

## Task 8.5: Add Token Budget Limits

**File(s)**: `ktrdr/agents/invoker.py`
**Type**: CODING

**Description**: Add optional per-invocation token limits to prevent runaway costs.

**Implementation Notes**:

```python
@dataclass
class AnthropicInvokerConfig:
    model: str = "claude-opus-4-5-20250514"
    max_tokens_per_call: int = 4096  # Output limit
    max_input_tokens: int = 50000   # Circuit breaker
    max_iterations: int = 10        # Tool call loop limit

async def run(self, ...):
    iterations = 0
    while True:
        iterations += 1
        if iterations > self.config.max_iterations:
            raise WorkerError(f"Tool call loop exceeded {self.config.max_iterations} iterations")

        # Check input size before sending
        estimated_input = self._estimate_input_tokens(messages)
        if estimated_input > self.config.max_input_tokens:
            raise WorkerError(f"Input tokens ({estimated_input}) exceed limit ({self.config.max_input_tokens})")

        response = await self._create_message(...)
```

**Acceptance Criteria**:
- [ ] Max iterations prevents infinite tool loops
- [ ] Input token estimation warns before expensive calls
- [ ] Configurable via environment variables
- [ ] Clear error messages when limits hit

---

## Milestone 8 Verification Script

```bash
#!/bin/bash
set -e

echo "=== M8: Cost Optimization Verification ==="

# 1. Test with Haiku (cheap)
echo ""
echo "1. Testing with Haiku model..."
export AGENT_MODEL=claude-haiku-4-5-20250514

# Check model is set
MODEL=$(docker exec ktrdr-backend printenv AGENT_MODEL 2>/dev/null || echo "not set")
echo "   Backend model: $MODEL"

# 2. Run design phase only (trigger then cancel after design)
echo ""
echo "2. Running design phase..."
RESULT=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
OP_ID=$(echo $RESULT | jq -r '.operation_id')
echo "   Operation: $OP_ID"

# Wait for design to complete
for i in {1..30}; do
    STATUS=$(curl -s http://localhost:8000/api/v1/agent/status)
    PHASE=$(echo $STATUS | jq -r '.phase')
    if [ "$PHASE" != "designing" ]; then
        break
    fi
    sleep 2
done

# Cancel before training (we just want design cost)
curl -s -X DELETE http://localhost:8000/api/v1/agent/cancel > /dev/null

# 3. Check token usage
echo ""
echo "3. Checking token usage..."
DESIGN_OP=$(curl -s "http://localhost:8000/api/v1/operations/$OP_ID" | jq -r '.data.metadata.parameters.design_op_id')
if [ "$DESIGN_OP" != "null" ]; then
    TOKENS=$(curl -s "http://localhost:8000/api/v1/operations/$DESIGN_OP")
    INPUT=$(echo $TOKENS | jq -r '.data.result_summary.input_tokens')
    OUTPUT=$(echo $TOKENS | jq -r '.data.result_summary.output_tokens')
    echo "   Input tokens: $INPUT"
    echo "   Output tokens: $OUTPUT"

    if [ "$INPUT" -lt 15000 ]; then
        echo "   PASS: Input tokens < 15000 (target met)"
    else
        echo "   WARN: Input tokens >= 15000 (optimization may not be working)"
    fi
fi

# 4. Check cost
echo ""
echo "4. Checking cost..."
BUDGET=$(curl -s http://localhost:8000/api/v1/agent/budget)
SPEND=$(echo $BUDGET | jq -r '.today_spend')
echo "   Today's spend: \$$SPEND"

if (( $(echo "$SPEND < 0.20" | bc -l) )); then
    echo "   PASS: Design cost < \$0.20"
else
    echo "   WARN: Design cost >= \$0.20"
fi

# 5. Verify no discovery tool calls
echo ""
echo "5. Checking tool calls..."
TOOL_CALLS=$(docker logs ktrdr-backend 2>&1 | grep "Executing tool" | grep "$OP_ID" | grep -c "get_available" || echo "0")
if [ "$TOOL_CALLS" -eq 0 ]; then
    echo "   PASS: No discovery tool calls"
else
    echo "   FAIL: Found $TOOL_CALLS discovery tool calls"
fi

echo ""
echo "=== M8 Complete ==="
```

---

## Files Created/Modified in M8

**Modified files**:
```
ktrdr/agents/prompts.py              # Add compact formatting, context in prompt
ktrdr/agents/tools.py                # Add DESIGN_PHASE_TOOLS subset
ktrdr/agents/workers/design_worker.py # Pre-gather context, use reduced tools
ktrdr/agents/invoker.py              # Model validation, token limits
ktrdr/agents/workers/research_worker.py # Model-aware cost estimation
docker-compose.yml                   # AGENT_MODEL env var
```

---

## Expected Outcome

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Design input tokens | ~33,000 | ~12,000 | 64% reduction |
| Design API calls | 4+ | 2 | 50% reduction |
| Design cost (Opus 4.5) | ~$0.22 | ~$0.08 | 64% reduction |
| Design cost (Haiku 4.5) | N/A | ~$0.02 | 75% vs Opus |
| Full cycle cost (Opus 4.5) | ~$0.30 | ~$0.12 | 60% reduction |

**Pricing Reference** (per 1M tokens):

| Model | Input | Output |
|-------|-------|--------|
| Opus 4.5 | $5 | $25 |
| Sonnet 4 | $3 | $15 |
| Haiku 4.5 | $1 | $5 |

---

*Estimated effort: ~3-4 hours*
