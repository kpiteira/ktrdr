# Phase 1: Strategy Design Only

**Objective:** Agent can design valid neuro-fuzzy strategy configurations

**Duration:** 2-3 days

**Prerequisites:** Phase 0 complete (plumbing works)

---

## Branch Strategy

**Branch:** `feature/agent-mvp`

Continue on the same branch from Phase 0. All MVP phases (0-3) use this single branch.

---

## ⚠️ Implementation Principles

**Check Before Creating:**
For ANY functionality that might already exist in KTRDR:
1. **Search** the codebase for existing implementations
2. **Review** if existing code covers requirements
3. **Enhance** existing code if gaps found
4. **Create new** only if nothing suitable exists

**Why:** KTRDR is a mature codebase with validation, CLI commands, MCP tools. Duplicating functionality creates maintenance burden and inconsistency.

**Known Existing Systems to Check:**
- `ktrdr/validation/` - validation framework
- `ktrdr/cli/commands/strategies.py` - strategy CLI commands
- `mcp/src/tools/` - existing MCP tools
- `ktrdr/indicators/` - indicator registry
- `ktrdr/config/` - configuration parsing

---

## Success Criteria

- [ ] Agent generates valid YAML strategy configurations
- [ ] Strategies use available indicators and symbols
- [ ] Agent avoids repeating recent strategies
- [ ] Generated strategies pass KTRDR validation
- [ ] Strategies saved to `strategies/` folder

---

## Tasks

### 1.1 Implement Full Agent Prompt

**Goal:** Replace Phase 0 test prompt with real strategy design prompt

**Prompt must include:**
- Role: Autonomous neuro-fuzzy strategy researcher
- Available indicators (injected from KTRDR)
- Available symbols and timeframes
- Strategy configuration format
- Instructions for novelty and experimentation

**Context injection:**
- Recent strategies (last 5) to avoid repetition
- Current session state
- Trigger reason

**File:** `research_agents/prompts/strategy_designer.py`

**Reference:** See `ref_agent_prompt.md` for full prompt specification

**Acceptance:**
- Prompt generates coherent strategy designs
- Agent understands available options
- Agent explains its design choices

**Effort:** 3-4 hours

---

### 1.2 Strategy Validation (Check-First)

**⚠️ IMPORTANT:** Check existing code before implementing!

**Step 1: Inventory existing validation**
- [ ] Review `ktrdr/validation/` module
- [ ] Review `ktrdr/cli/commands/strategies.py` (validate command)
- [ ] Check for existing strategy schema/config classes
- [ ] Document what already exists

**Step 2: Gap analysis against requirements**

| Requirement | Check If Exists | If Missing |
|-------------|-----------------|------------|
| YAML syntax validation | ? | Enhance existing |
| Required fields check | ? | Enhance existing |
| Indicators exist in KTRDR | ? | Enhance existing |
| Symbols have available data | ? | Enhance existing |
| Fuzzy membership functions valid | ? | Enhance existing |
| No duplicate strategy names | ? | Enhance existing |

**Step 3: Enhance existing OR create wrapper**
- If 80%+ exists: enhance `ktrdr/validation/`
- If major gaps: create thin wrapper in `research_agents/validation/` that calls existing code + adds missing checks

**DO NOT** create parallel validation system - extend what exists!

**Files to Check:**
- `ktrdr/validation/*.py`
- `ktrdr/cli/commands/strategies.py`
- `ktrdr/config/*.py` (strategy config parsing)

**Files to Modify (if gaps found):**
- Existing `ktrdr/validation/` module (preferred)
- OR wrapper at `research_agents/validation/strategy_validator.py`

**Acceptance:**
- Valid strategies pass
- Invalid strategies return clear error messages
- Error messages help agent fix issues
- **No duplicate code** with existing validation

**Effort:** 3-4 hours (includes investigation)

---

### 1.3 Implement save_strategy_config MCP Tool

**Goal:** Agent can save validated strategy to disk

**Tool signature:**
```python
@mcp.tool()
def save_strategy_config(
    name: str,
    config: dict,
    description: str
) -> dict:
    """
    Validate and save strategy configuration.
    Returns: {success: bool, path: str, errors: list}
    """
```

**Behavior:**
1. Validate config (Task 1.2)
2. If valid, save to `strategies/{name}.yaml`
3. Return result with path or errors

**File:** `mcp/src/tools/strategy_tools.py`

**Acceptance:**
- Tool saves valid strategies
- Tool rejects invalid strategies with clear errors
- Files appear in strategies folder

**Effort:** 2-3 hours

---

### 1.4 Implement get_recent_strategies MCP Tool

**Goal:** Agent can see what it recently tried

**Tool signature:**
```python
@mcp.tool()
def get_recent_strategies(n: int = 5) -> list[dict]:
    """
    Get last N strategies designed by agent.
    Returns: [{name, type, indicators, outcome, created_at}]
    """
```

**Data source:** Query `agent_sessions` table for recent completed sessions

**File:** `mcp/src/tools/strategy_tools.py`

**Acceptance:**
- Returns recent strategies with key details
- Helps agent avoid repetition

**Effort:** 1-2 hours

---

### 1.5 get_available_indicators MCP Tool (Check-First)

**⚠️ CHECK FIRST:** This likely exists in `mcp/src/tools/`

**Step 1: Search existing MCP tools**
```bash
grep -r "available_indicators\|get_indicators" mcp/src/tools/
```

**Step 2: If exists, verify it returns:**
- All 26+ indicators
- Parameter specifications (name, type, default, range)
- Category information
- Description

**Step 3: Action**
- If exists and complete: Document location, move on
- If exists but incomplete: Enhance existing tool
- If missing: Create in `mcp/src/tools/indicator_tools.py`

**DO NOT** create duplicate tool if one exists!

**Acceptance:**
- Returns all 26+ indicators
- Includes parameter specifications
- Agent can use this to design valid configs

**Effort:** 0-2 hours (depends on what exists)

---

### 1.6 get_available_symbols MCP Tool (Check-First)

**⚠️ CHECK FIRST:** This likely exists in `mcp/src/tools/`

**Step 1: Search existing MCP tools**
```bash
grep -r "available_symbols\|get_symbols" mcp/src/tools/
```

**Step 2: If exists, verify it returns:**
- All available symbols (EURUSD, GBPUSD, etc.)
- Available timeframes per symbol
- Data date ranges

**Step 3: Action**
- If exists and complete: Document location, move on
- If exists but incomplete: Enhance existing tool
- If missing: Create in `mcp/src/tools/data_tools.py`

**DO NOT** create duplicate tool if one exists!

**Acceptance:**
- Returns symbols with available timeframes
- Includes date ranges for data
- Agent can plan train/test splits

**Effort:** 0-2 hours (depends on what exists)

---

### 1.7 Update Trigger Service for Design Phase

**Goal:** Trigger invokes agent for strategy design

**Updates:**
- Check if session is in IDLE state
- Invoke agent with design context
- Handle design completion (agent sets phase to DESIGNED)

**State flow:**
```
IDLE → (trigger invokes agent) → DESIGNING → (agent completes) → DESIGNED
```

For Phase 1, we stop at DESIGNED. Phase 2 adds training.

**File:** `research_agents/services/trigger.py`

**Acceptance:**
- Agent invoked when IDLE
- Session transitions to DESIGNING
- Session transitions to DESIGNED when complete

**Effort:** 2-3 hours

---

### 1.8 Strategy Design Tests

**Goal:** Verify agent designs valid strategies

**Test cases:**
1. Agent generates valid YAML
2. Agent uses available indicators
3. Agent uses available symbols
4. Agent avoids recent strategy patterns
5. Invalid config rejected with helpful error

**Files:** 
- `tests/unit/research_agents/test_strategy_validator.py`
- `tests/integration/research_agents/test_strategy_design.py`

**Acceptance:**
- Unit tests for validator
- Integration test for full design flow
- Can observe agent designing strategies

**Effort:** 3-4 hours

---

## Task Summary

| Task | Description | Effort | Dependencies |
|------|-------------|--------|--------------|
| 1.1 | Full agent prompt | 3-4h | Phase 0 |
| 1.2 | Strategy validation (check-first) | 2-4h | Review existing |
| 1.3 | save_strategy_config tool | 2-3h | 1.2 |
| 1.4 | get_recent_strategies tool | 1-2h | Phase 0 |
| 1.5 | get_available_indicators (check-first) | 0-2h | Check if exists |
| 1.6 | get_available_symbols (check-first) | 0-2h | Check if exists |
| 1.7 | Trigger service updates | 2-3h | 1.1, 1.3 |
| 1.8 | Tests | 3-4h | All above |

**Total estimated effort:** 13-24 hours (2-3 days)

*Note: Effort varies based on what already exists. Tasks 1.2, 1.5, 1.6 may require minimal work if existing code is sufficient.*

---

## Out of Scope for Phase 1

- Starting training (Phase 2)
- Running backtests (Phase 2)
- Quality gates (Phase 2)
- Cost tracking (Phase 3)
- Observability (Phase 3)

---

## Files to Create/Modify

**Note:** Several items require check-first - actual files created depend on what exists.

```
research_agents/
├── prompts/
│   └── strategy_designer.py        # 1.1 - NEW
├── validation/                     # 1.2 - ONLY if ktrdr/validation/ insufficient
│   └── strategy_validator.py       #       (prefer enhancing existing)
└── services/
    └── trigger.py                  # 1.7 - MODIFY

mcp/src/tools/
├── strategy_tools.py               # 1.3, 1.4 - NEW (agent-specific tools)
├── [existing tools]                # 1.5 - CHECK if indicator tools exist
└── [existing tools]                # 1.6 - CHECK if symbol/data tools exist

ktrdr/validation/                   # 1.2 - ENHANCE if needed
└── [existing files]                #       (preferred over new files)

tests/
├── unit/research_agents/
│   └── test_strategy_validator.py  # 1.8
└── integration/research_agents/
    └── test_strategy_design.py     # 1.8
```

**Check-first files** (may already exist):
- `mcp/src/tools/` - search for indicator and symbol tools
- `ktrdr/validation/` - review existing validation logic
- `ktrdr/cli/commands/strategies.py` - review validate command

---

## Example Generated Strategy

After Phase 1, the agent should produce strategies matching KTRDR's actual format.

**Reference:** See `strategies/neuro_mean_reversion.yaml` for the canonical format.

```yaml
# === STRATEGY IDENTITY ===
name: "momentum_crossover_v1"
description: "RSI divergence with MACD confirmation for trend entries on EURUSD"
version: "1.0"
hypothesis: "RSI divergence combined with MACD crossover confirmation
  creates higher-probability trend entry signals"

# === STRATEGY SCOPE ===
scope: "universal"

# === TRAINING APPROACH ===
training_data:
  symbols:
    mode: "single_symbol"
    list:
      - "EURUSD"
  timeframes:
    mode: "single_timeframe"
    list:
      - "1h"
    base_timeframe: "1h"
  history_required: 200

# === DEPLOYMENT TARGETS ===
deployment:
  target_symbols:
    mode: "same_as_training"
  target_timeframes:
    mode: "single_timeframe"
    supported:
      - "1h"

# === TECHNICAL INDICATORS ===
indicators:
  - name: "rsi"
    feature_id: rsi_14
    period: 14
    source: "close"
  - name: "macd"
    feature_id: macd_12_26_9
    fast_period: 12
    slow_period: 26
    signal_period: 9
    source: "close"

# === FUZZY LOGIC CONFIGURATION ===
fuzzy_sets:
  rsi_14:
    oversold:
      type: "triangular"
      parameters: [0, 20, 35]
    neutral:
      type: "triangular"
      parameters: [30, 50, 70]
    overbought:
      type: "triangular"
      parameters: [65, 80, 100]

# === NEURAL NETWORK MODEL ===
model:
  type: "mlp"
  architecture:
    hidden_layers: [32, 16]
    activation: "relu"
    output_activation: "softmax"
    dropout: 0.2
  features:
    include_price_context: false
    lookback_periods: 2
    scale_features: true
  training:
    learning_rate: 0.001
    batch_size: 32
    epochs: 50
    optimizer: "adam"

# === DECISION LOGIC ===
decisions:
  output_format: "classification"
  confidence_threshold: 0.6
  position_awareness: true
  filters:
    min_signal_separation: 4
    volume_filter: false

# === TRAINING CONFIGURATION ===
training:
  method: "supervised"
  labels:
    source: "zigzag"
    zigzag_threshold: 0.03
    label_lookahead: 20
  data_split:
    train: 0.7
    validation: 0.15
    test: 0.15
```

**Key format requirements:**
- Use `training_data.symbols` not top-level `symbols`
- Use `fuzzy_sets` not `fuzzy_config`
- Use `parameters` not `params` for fuzzy membership
- Include `feature_id` for each indicator
- Include full `model`, `decisions`, and `training` blocks

---

## Definition of Done

Phase 1 is complete when:
1. Agent designs novel strategy configurations
2. Strategies pass validation
3. Strategies save to disk
4. Agent avoids recent patterns
5. Tests pass

Then we move to Phase 2: Full Research Cycle.
