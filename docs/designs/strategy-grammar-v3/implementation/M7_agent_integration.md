---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 7: Agent Integration

**Branch:** `feature/strategy-grammar-v3-m7`
**Prerequisite:** M6 complete (CLI tools work)
**Builds on:** M6 CLI & Migration

## Goal

Agents (LLM-powered) can generate valid v3 strategies. Agent prompts are updated to produce v3 format.

## Why This Milestone

- Agents are primary strategy creators in KTRDR
- Must generate v3 format for training to work
- Prompt changes are non-breaking (agents just produce different output)

---

## Tasks

### Task 7.1: Update Strategy Generation Prompt

**File(s):** `ktrdr/agents/prompts.py`
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Configuration

**Description:**
Update the strategy generation prompt to instruct the LLM to produce v3 format.

**Implementation Notes:**

Key changes:
- Explain the v3 structure (indicators, fuzzy_sets, nn_inputs)
- Provide example v3 strategy
- Emphasize that `nn_inputs` is required
- Remove v2 terminology (`feature_id`)

```python
STRATEGY_GENERATION_PROMPT = '''
Generate a trading strategy in YAML format following the v3 specification.

## Structure

A v3 strategy has these sections:

1. **indicators**: Dict of indicator calculations (keyed by indicator_id)
   - Each indicator has a `type` and parameters
   - indicator_id should be descriptive: `rsi_14`, `bbands_20_2`, etc.

2. **fuzzy_sets**: Dict of fuzzy interpretations (keyed by fuzzy_set_id)
   - Each fuzzy set references an indicator via the `indicator` field
   - Multiple fuzzy sets can reference the same indicator
   - For multi-output indicators, use dot notation: `indicator: bbands_20_2.upper`

3. **nn_inputs**: List specifying which fuzzy_set + timeframe combinations
   - This explicitly defines what features the neural network receives
   - Use `timeframes: all` to apply to all training timeframes
   - Use `timeframes: [5m, 1h]` for specific timeframes

## Example

```yaml
name: "momentum_strategy"
description: "RSI-based momentum strategy with timeframe adaptation"
version: "3.0"

training_data:
  symbols:
    mode: multi_symbol
    list: [EURUSD, GBPUSD]
  timeframes:
    mode: multi_timeframe
    list: [5m, 1h, 1d]
    base_timeframe: 1h
  history_required: 300

indicators:
  rsi_14:
    type: rsi
    period: 14
  macd_12_26_9:
    type: macd
    fast_period: 12
    slow_period: 26
    signal_period: 9

fuzzy_sets:
  # Fast RSI interpretation for short timeframes
  rsi_fast:
    indicator: rsi_14
    oversold: [0, 25, 40]
    neutral: [35, 50, 65]
    overbought: [60, 75, 100]

  # Slow RSI interpretation for longer timeframes
  rsi_slow:
    indicator: rsi_14
    oversold: [0, 15, 30]
    overbought: [70, 85, 100]

  macd_momentum:
    indicator: macd_12_26_9.histogram
    bearish: [-50, -10, 0]
    bullish: [0, 10, 50]

nn_inputs:
  - fuzzy_set: rsi_fast
    timeframes: [5m]
  - fuzzy_set: rsi_slow
    timeframes: [1h, 1d]
  - fuzzy_set: macd_momentum
    timeframes: [1h]

model:
  type: mlp
  architecture:
    hidden_layers: [128, 64, 32]
    activation: relu
    dropout: 0.3
  training:
    learning_rate: 0.001
    epochs: 100
    batch_size: 32

decisions:
  output_format: classification
  confidence_threshold: 0.65

training:
  method: supervised
  labels:
    source: zigzag
    zigzag_threshold: 0.025
```

## Guidelines

1. **Indicator IDs**: Use descriptive names with parameters: `rsi_14`, `bbands_20_2`
2. **Fuzzy set IDs**: Describe the interpretation: `rsi_fast`, `rsi_slow`, `volatility_regime`
3. **Multiple interpretations**: Different fuzzy sets can reference the same indicator
4. **Timeframe adaptation**: Use different fuzzy sets for different timeframes
5. **nn_inputs is required**: Explicitly list all fuzzy_set + timeframe combinations
6. **Shorthand syntax**: Use `[a, b, c]` for triangular membership functions

## Common Patterns

- Short-term timeframes (5m, 15m): Use "fast" interpretations with wider neutral zones
- Long-term timeframes (1d, 1w): Use "slow" interpretations with narrower extremes
- Volatility context: Apply same fuzzy set to all timeframes with `timeframes: all`

Generate a strategy based on the user's requirements.
'''
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/agents/test_prompts_v3.py`
- [ ] Prompt contains v3 keywords (indicators dict, nn_inputs)
- [ ] Prompt does NOT contain v2 keywords (feature_id)
- [ ] Example in prompt is valid v3 YAML

*Smoke Test:*
```bash
uv run python -c "
from ktrdr.agents.prompts import STRATEGY_GENERATION_PROMPT
assert 'nn_inputs' in STRATEGY_GENERATION_PROMPT
assert 'feature_id' not in STRATEGY_GENERATION_PROMPT
assert 'indicators:' in STRATEGY_GENERATION_PROMPT
print('Prompt contains v3 structure: OK')
"
```

**Acceptance Criteria:**
- [ ] Prompt matches ARCHITECTURE.md lines 579-605
- [ ] Example is valid v3 YAML
- [ ] No v2 terminology

---

### Task 7.2: Update Strategy Utilities

**File(s):** `ktrdr/agents/strategy_utils.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** Cross-Component

**Description:**
Update agent utility functions to work with v3 format.

**Implementation Notes:**

Functions to update:
- `parse_strategy_response()`: Handle v3 structure
- `validate_agent_strategy()`: Use v3 validator
- `extract_features()`: Use FeatureResolver

```python
def parse_strategy_response(response: str) -> dict:
    """
    Parse LLM response containing strategy YAML.

    Extracts YAML from markdown code blocks if present.
    """
    # Extract from code block if present
    if '```yaml' in response:
        start = response.find('```yaml') + 7
        end = response.find('```', start)
        yaml_str = response[start:end].strip()
    elif '```' in response:
        start = response.find('```') + 3
        end = response.find('```', start)
        yaml_str = response[start:end].strip()
    else:
        yaml_str = response.strip()

    return yaml.safe_load(yaml_str)


def validate_agent_strategy(config: dict) -> tuple[bool, list[str]]:
    """
    Validate agent-generated strategy.

    Returns:
        (is_valid, list of error messages)
    """
    errors = []

    # Check v3 markers
    if not isinstance(config.get('indicators'), dict):
        errors.append("indicators must be a dict (v3 format)")

    if 'nn_inputs' not in config:
        errors.append("nn_inputs section required (v3 format)")

    if errors:
        return False, errors

    # Full validation
    try:
        parsed = StrategyConfigurationV3(**config)
        warnings = validate_v3_strategy(parsed)
        return True, [w.message for w in warnings]
    except Exception as e:
        return False, [str(e)]


def extract_features(config: dict) -> list[str]:
    """Extract feature list from v3 config."""
    parsed = StrategyConfigurationV3(**config)
    resolver = FeatureResolver()
    resolved = resolver.resolve(parsed)
    return [f.feature_id for f in resolved]
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/agents/test_strategy_utils_v3.py`
- [ ] Parses YAML from markdown code blocks
- [ ] Validates v3 structure
- [ ] Rejects v2 structure with clear error
- [ ] Extracts features correctly

**Acceptance Criteria:**
- [ ] Utilities work with v3 format
- [ ] Clear errors for v2 format
- [ ] Unit tests pass

---

### Task 7.3: Update MCP Strategy Tools

**File(s):** `mcp/src/tools/strategy_tools.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** API Endpoint

**Description:**
Update MCP tools that interact with strategies to expect v3 format.

**Implementation Notes:**

MCP tools should:
- Use v3 validator for strategy validation
- Return v3-specific information (resolved features)
- Guide users toward v3 format

```python
async def validate_strategy(path: str) -> dict:
    """
    Validate a strategy file.

    Returns dict with:
    - valid: bool
    - format: "v3" | "v2"
    - features: list[str] (if v3)
    - errors: list[str] (if invalid)
    """
    loader = StrategyConfigurationLoader()

    try:
        config = loader.load(Path(path))
        resolver = FeatureResolver()
        features = resolver.resolve(config)

        return {
            'valid': True,
            'format': 'v3',
            'features': [f.feature_id for f in features],
            'feature_count': len(features),
        }

    except ValueError as e:
        if 'not v3 format' in str(e):
            return {
                'valid': False,
                'format': 'v2',
                'errors': [str(e)],
                'suggestion': 'Run ktrdr strategy migrate to upgrade'
            }
        return {
            'valid': False,
            'format': 'unknown',
            'errors': [str(e)]
        }
```

**Testing Requirements:**

*Smoke Test:*
```bash
# Test via MCP if available, or direct call
uv run python -c "
from mcp.src.tools.strategy_tools import validate_strategy
import asyncio

result = asyncio.run(validate_strategy('strategies/v3_test_example.yaml'))
print(result)
assert result['format'] == 'v3'
print('MCP strategy tools: OK')
"
```

**Acceptance Criteria:**
- [ ] MCP tools work with v3
- [ ] Clear guidance for v2 files
- [ ] Feature list returned

---

## E2E Test Scenario

**Purpose:** Prove agents can generate and validate v3 strategies
**Duration:** ~10 seconds
**Prerequisites:** M6 complete

### Test Steps

```bash
#!/bin/bash
# M7 E2E Test: Agent Integration

set -e

echo "=== M7 E2E Test: Agent Integration ==="

# Test 1: Verify prompt contains v3 structure
echo "Test 1: Prompt structure..."
uv run python << 'EOF'
from ktrdr.agents.prompts import STRATEGY_GENERATION_PROMPT

# Must have v3 markers
assert 'nn_inputs' in STRATEGY_GENERATION_PROMPT, "Missing nn_inputs"
assert 'indicators:' in STRATEGY_GENERATION_PROMPT, "Missing indicators section"
assert 'fuzzy_sets:' in STRATEGY_GENERATION_PROMPT, "Missing fuzzy_sets section"

# Must NOT have v2 markers
assert 'feature_id' not in STRATEGY_GENERATION_PROMPT, "Contains v2 feature_id"

print("Prompt structure: PASS")
EOF
echo "Test 1: PASS"

# Test 2: Validate example in prompt
echo "Test 2: Example in prompt is valid..."
uv run python << 'EOF'
import yaml
import re
from ktrdr.agents.prompts import STRATEGY_GENERATION_PROMPT
from ktrdr.config.models import StrategyConfigurationV3

# Extract YAML example from prompt
yaml_match = re.search(r'```yaml\n(.+?)```', STRATEGY_GENERATION_PROMPT, re.DOTALL)
if yaml_match:
    example_yaml = yaml_match.group(1)
    config = yaml.safe_load(example_yaml)

    # Should parse as v3
    parsed = StrategyConfigurationV3(**config)
    print(f"Example strategy: {parsed.name}")
    print(f"Indicators: {len(parsed.indicators)}")
    print(f"NN Inputs: {len(parsed.nn_inputs)}")
    print("Example validation: PASS")
else:
    print("No YAML example found in prompt")
EOF
echo "Test 2: PASS"

# Test 3: Strategy utilities work with v3
echo "Test 3: Strategy utilities..."
uv run python << 'EOF'
from ktrdr.agents.strategy_utils import validate_agent_strategy, extract_features

# Valid v3 config
v3_config = {
    'name': 'test',
    'version': '3.0',
    'training_data': {
        'symbols': {'mode': 'single_symbol', 'list': ['EURUSD']},
        'timeframes': {'mode': 'single_timeframe', 'list': ['1h'], 'base_timeframe': '1h'},
        'history_required': 100,
    },
    'indicators': {
        'rsi_14': {'type': 'rsi', 'period': 14}
    },
    'fuzzy_sets': {
        'rsi_momentum': {
            'indicator': 'rsi_14',
            'oversold': {'type': 'triangular', 'parameters': [0, 20, 35]},
            'overbought': {'type': 'triangular', 'parameters': [65, 80, 100]},
        }
    },
    'nn_inputs': [
        {'fuzzy_set': 'rsi_momentum', 'timeframes': 'all'}
    ],
    'model': {'type': 'mlp', 'architecture': {'hidden_layers': [32]}},
    'decisions': {'output_format': 'classification'},
    'training': {'method': 'supervised', 'labels': {'source': 'zigzag'}},
}

is_valid, messages = validate_agent_strategy(v3_config)
assert is_valid, f"Should be valid: {messages}"

features = extract_features(v3_config)
assert len(features) == 2, f"Expected 2 features, got {len(features)}"
assert '1h_rsi_momentum_oversold' in features
assert '1h_rsi_momentum_overbought' in features

print(f"Features: {features}")
print("Strategy utilities: PASS")
EOF
echo "Test 3: PASS"

# Test 4: V2 rejection in utilities
echo "Test 4: V2 rejection..."
uv run python << 'EOF'
from ktrdr.agents.strategy_utils import validate_agent_strategy

# V2 config (list indicators, no nn_inputs)
v2_config = {
    'name': 'v2_test',
    'indicators': [
        {'name': 'rsi', 'feature_id': 'rsi_14', 'period': 14}
    ],
    'fuzzy_sets': {},
}

is_valid, messages = validate_agent_strategy(v2_config)
assert not is_valid, "V2 should be rejected"
assert any('dict' in m or 'nn_inputs' in m for m in messages), \
    f"Error should mention v3 requirements: {messages}"

print("V2 rejection: PASS")
EOF
echo "Test 4: PASS"

echo ""
echo "=== M7 E2E Test: ALL PASSED ==="
```

### Success Criteria

- [ ] Prompt contains v3 structure (nn_inputs, indicators dict)
- [ ] Prompt example is valid v3 YAML
- [ ] No v2 terminology in prompt (feature_id)
- [ ] Agent utilities validate v3 correctly
- [ ] Agent utilities reject v2 with clear error

---

## Completion Checklist

- [ ] Task 7.1: Strategy generation prompt updated
- [ ] Task 7.2: Strategy utilities updated
- [ ] Task 7.3: MCP tools updated
- [ ] All unit tests pass: `make test-unit`
- [ ] E2E test script passes
- [ ] M1-M6 E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] Code reviewed and merged
