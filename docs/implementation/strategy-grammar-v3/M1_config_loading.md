---
design: docs/designs/strategy-grammar-v3/DESIGN.md
architecture: docs/designs/strategy-grammar-v3/ARCHITECTURE.md
---

# Milestone 1: V3 Config Loading & Validation

**Branch:** `feature/strategy-grammar-v3-m1`
**Prerequisite:** Indicator Standardization M1-M5 complete
**Builds on:** Nothing (foundation milestone)

## Goal

User can load and validate a v3 strategy file, seeing the resolved NN input features. V2 strategies are rejected with helpful migration guidance.

## Why This Is M1

- Proves the new Pydantic models parse correctly
- Proves FeatureResolver correctly expands nn_inputs
- Proves validation catches invalid references
- Requires NO changes to indicator/fuzzy engines (config layer only)
- Smallest slice that proves v3 architecture works

---

## Tasks

### Task 1.1: Create V3 Pydantic Models

**File(s):** `ktrdr/config/models.py`
**Type:** CODING
**Estimated time:** 2-3 hours

**Task Categories:** Configuration, Wiring/DI

**Description:**
Add new Pydantic models for v3 strategy configuration. These coexist with v2 models temporarily (v2 models removed in M8).

**Implementation Notes:**

Models to create:
- `IndicatorDefinition`: type + arbitrary params via `model_config = {"extra": "allow"}`
- `FuzzyMembership`: type + parameters
- `FuzzySetDefinition`: indicator reference + membership functions, with `@model_validator` for shorthand expansion
- `NNInputSpec`: fuzzy_set + timeframes (list or "all")
- `StrategyConfigurationV3`: top-level model composing all sections

Key pattern — shorthand expansion in `FuzzySetDefinition`:

```python
class FuzzyMembership(BaseModel):
    """A fuzzy membership function definition."""
    type: str = Field(default="triangular")
    parameters: list[float]


class FuzzySetDefinition(BaseModel):
    """A fuzzy interpretation of an indicator."""
    indicator: str = Field(..., description="indicator_id to interpret (supports dot notation)")
    model_config = {"extra": "allow"}

    @model_validator(mode='before')
    @classmethod
    def expand_shorthand(cls, data: dict) -> dict:
        """Convert [a,b,c] shorthand to {type: triangular, parameters: [a,b,c]}."""
        result = {}
        for key, value in data.items():
            if key == 'indicator':
                result[key] = value
            elif isinstance(value, list):
                # Shorthand: [0, 20, 35] -> FuzzyMembership
                result[key] = {'type': 'triangular', 'parameters': value}
            else:
                result[key] = value
        return result

    def get_membership_names(self) -> list[str]:
        """Return ordered list of membership function names."""
        return [k for k in self.__pydantic_extra__ if k != 'indicator']
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/config/test_models_v3.py`
- [ ] `IndicatorDefinition` accepts arbitrary params (period, multiplier, etc.)
- [ ] `FuzzyMembership` validates parameters list
- [ ] `FuzzySetDefinition` expands `[0,20,35]` shorthand to full form
- [ ] `FuzzySetDefinition` preserves full `{type, parameters}` form unchanged
- [ ] `FuzzySetDefinition.get_membership_names()` returns correct order
- [ ] `NNInputSpec` accepts `timeframes: "all"`
- [ ] `NNInputSpec` accepts `timeframes: ["5m", "1h"]`
- [ ] `StrategyConfigurationV3` parses complete example from DESIGN.md

*Smoke Test:*
```bash
uv run python -c "from ktrdr.config.models import StrategyConfigurationV3; print('OK')"
```

**Acceptance Criteria:**
- [ ] All v3 models defined with docstrings
- [ ] Shorthand expansion works in `FuzzySetDefinition`
- [ ] Models match spec in ARCHITECTURE.md lines 70-151
- [ ] Unit tests written and passing

---

### Task 1.2: Create FeatureResolver

**File(s):** `ktrdr/config/feature_resolver.py` (NEW)
**Type:** CODING
**Estimated time:** 2-3 hours

**Task Categories:** Cross-Component, Configuration

**Description:**
Create `FeatureResolver` class that resolves `nn_inputs` into concrete `ResolvedFeature` objects. This is the **single source of truth** for feature ordering — both training and backtest use this.

**Implementation Notes:**

Feature naming: `{timeframe}_{fuzzy_set_id}_{membership_name}`

Order is deterministic:
1. `nn_inputs` list order (YAML order preserved)
2. Within each nn_input: timeframes order × membership function order

Must handle:
- `timeframes: "all"` → expand to `config.training_data.timeframes.list`
- `timeframes: ["5m", "1h"]` → use as-is
- Multiple fuzzy sets referencing same indicator

```python
from dataclasses import dataclass

@dataclass
class ResolvedFeature:
    """A fully resolved NN input feature."""
    feature_id: str          # "5m_rsi_fast_oversold"
    timeframe: str           # "5m"
    fuzzy_set_id: str        # "rsi_fast"
    membership_name: str     # "oversold"
    indicator_id: str        # "rsi_14" (without dot notation output)
    indicator_output: str | None  # "upper" if dot notation, else None


class FeatureResolver:
    """Resolves nn_inputs into concrete feature specifications."""

    def resolve(self, config: StrategyConfigurationV3) -> list[ResolvedFeature]:
        """
        Resolve nn_inputs to concrete features.

        CRITICAL: The returned list order IS the canonical feature order.
        This order must be stored in ModelMetadataV3 and validated at backtest.
        """

    def get_indicators_for_timeframe(
        self,
        resolved: list[ResolvedFeature],
        timeframe: str
    ) -> set[str]:
        """Get indicator_ids needed for a specific timeframe."""

    def get_fuzzy_sets_for_timeframe(
        self,
        resolved: list[ResolvedFeature],
        timeframe: str
    ) -> set[str]:
        """Get fuzzy_set_ids needed for a specific timeframe."""
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/config/test_feature_resolver.py`
- [ ] Resolves simple nn_inputs correctly
- [ ] Handles `timeframes: "all"` expansion
- [ ] Handles `timeframes: ["5m", "1h"]` explicit list
- [ ] Feature order matches nn_inputs × timeframes × memberships exactly
- [ ] `get_indicators_for_timeframe()` returns correct set
- [ ] `get_fuzzy_sets_for_timeframe()` returns correct set
- [ ] Multiple fuzzy sets referencing same indicator both resolved
- [ ] Dot notation (`bbands_20_2.upper`) parsed into indicator_id + indicator_output

*Smoke Test:*
```bash
uv run python -c "from ktrdr.config.feature_resolver import FeatureResolver, ResolvedFeature; print('OK')"
```

**Acceptance Criteria:**
- [ ] `FeatureResolver` matches interface in SCENARIOS.md lines 249-267
- [ ] Order determinism verified by test (same input → same output)
- [ ] All helper methods implemented
- [ ] Unit tests written and passing

---

### Task 1.3: Create V3 Strategy Validator

**File(s):** `ktrdr/config/strategy_validator.py`
**Type:** CODING
**Estimated time:** 1-2 hours

**Task Categories:** Configuration, Cross-Component

**Description:**
Add validation rules specific to v3 format. Either extend existing validator or create new `validate_v3_strategy()` function.

**Implementation Notes:**

Validations to implement:

1. **Indicator reference check:** All `fuzzy_sets.*.indicator` must reference existing `indicators` keys
2. **Fuzzy set reference check:** All `nn_inputs.*.fuzzy_set` must reference existing `fuzzy_sets` keys
3. **Timeframe check:** All timeframes in `nn_inputs` must be valid ("all" or in `training_data.timeframes.list`)
4. **Unused indicator warning:** Warn (don't error) if indicators defined but never referenced by any fuzzy_set
5. **Dot notation validation:** If `indicator: bbands_20_2.upper`, verify `upper` is valid output for bbands type

For dot notation validation, need to:
- Parse indicator reference to extract base indicator_id and output name
- Look up indicator type from `indicators` dict
- Use indicator's `get_output_names()` to validate output exists

**Note:** Dot notation validation depends on indicator standardization being complete (prerequisite).

```python
class StrategyValidationError(Exception):
    """Raised when strategy validation fails."""
    pass

class StrategyValidationWarning:
    """Non-fatal validation issue."""
    message: str
    location: str  # e.g., "indicators.rsi_14"

def validate_v3_strategy(
    config: StrategyConfigurationV3
) -> list[StrategyValidationWarning]:
    """
    Validate v3 strategy configuration.

    Raises:
        StrategyValidationError: If validation fails

    Returns:
        List of warnings (non-fatal issues)
    """
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/config/test_strategy_validator_v3.py`
- [ ] Valid v3 strategy passes validation with no warnings
- [ ] Invalid indicator reference raises `StrategyValidationError`
- [ ] Invalid fuzzy_set reference raises `StrategyValidationError`
- [ ] Invalid timeframe raises `StrategyValidationError`
- [ ] Unused indicator produces warning (not error)
- [ ] Invalid dot notation output raises error (e.g., `bbands_20_2.invalid`)
- [ ] Valid dot notation passes (e.g., `bbands_20_2.upper`)
- [ ] Error messages include location context

*Smoke Test:*
```bash
uv run python -c "from ktrdr.config.strategy_validator import validate_v3_strategy; print('OK')"
```

**Acceptance Criteria:**
- [ ] All validation rules from ARCHITECTURE.md lines 279-287 implemented
- [ ] Clear error messages with context (which field, what's wrong)
- [ ] Warnings logged for unused indicators
- [ ] Unit tests written and passing

---

### Task 1.4: Update Strategy Loader for V3

**File(s):** `ktrdr/config/strategy_loader.py`
**Type:** CODING
**Estimated time:** 1-2 hours

**Task Categories:** Configuration, Wiring/DI

**Description:**
Modify `StrategyConfigurationLoader` to detect and load v3 format. V2 strategies should be rejected with migration guidance.

**Implementation Notes:**

Detection logic:
- V3: `indicators` is dict AND `nn_inputs` present
- V2: `indicators` is list OR no `nn_inputs`

On v2 detection, raise `ValueError` with actionable message.

```python
class StrategyConfigurationLoader:
    """Loads v3 strategy configurations."""

    def load(self, config_path: Path) -> StrategyConfigurationV3:
        """Load and validate v3 strategy."""
        raw = yaml.safe_load(config_path.read_text())

        if not self._is_v3_format(raw):
            raise ValueError(
                f"Strategy '{config_path.name}' is not v3 format. "
                "Run 'ktrdr strategy migrate' to upgrade."
            )

        config = StrategyConfigurationV3(**raw)

        # Run validation
        warnings = validate_v3_strategy(config)
        for w in warnings:
            logger.warning(f"Strategy validation: {w.message} at {w.location}")

        return config

    def _is_v3_format(self, config: dict) -> bool:
        """Check for v3 markers."""
        return (
            isinstance(config.get("indicators"), dict) and
            "nn_inputs" in config
        )
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/config/test_strategy_loader_v3.py`
- [ ] V3 strategy loads successfully
- [ ] V2 strategy (list indicators) rejected with clear message
- [ ] V2 strategy (no nn_inputs) rejected with clear message
- [ ] Invalid YAML produces sensible error
- [ ] Validation runs automatically on load
- [ ] Warnings from validation are logged

*Integration Tests:*
- [ ] Loader callable from other modules

*Smoke Test:*
```bash
uv run python -c "
from ktrdr.config.strategy_loader import StrategyConfigurationLoader
loader = StrategyConfigurationLoader()
print('Loader initialized OK')
"
```

**Acceptance Criteria:**
- [ ] V3 detection logic correct per ARCHITECTURE.md lines 271-277
- [ ] V2 rejection message mentions `ktrdr strategy migrate`
- [ ] Validation runs automatically on load
- [ ] Unit tests written and passing

---

### Task 1.5: Add CLI `strategy validate` Command

**File(s):** `ktrdr/cli/strategy_commands.py`
**Type:** CODING
**Estimated time:** 1-2 hours

**Task Categories:** API Endpoint, Cross-Component

**Description:**
Add or update `ktrdr strategy validate <path>` command to validate v3 strategies and display resolved features.

**Implementation Notes:**

Command should:
1. Load strategy via `StrategyConfigurationLoader`
2. Resolve features via `FeatureResolver`
3. Display: strategy name, version, validation result, feature count, feature list

Output format:
```
Strategy 'my_strategy' is valid (v3 format)
Resolved features (8):
  5m_rsi_fast_oversold
  5m_rsi_fast_overbought
  1h_rsi_slow_oversold
  ...
```

On error:
```
Strategy 'my_strategy' validation failed:
  - fuzzy_sets.bad_ref.indicator: 'nonexistent' not found in indicators
```

```python
@strategy.command()
@click.argument('path', type=click.Path(exists=True))
def validate(path: str):
    """Validate a v3 strategy and show resolved features."""
    try:
        loader = StrategyConfigurationLoader()
        config = loader.load(Path(path))

        resolver = FeatureResolver()
        features = resolver.resolve(config)

        click.echo(f"Strategy '{config.name}' is valid (v3 format)")
        click.echo(f"Resolved features ({len(features)}):")
        for f in features:
            click.echo(f"  {f.feature_id}")

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except StrategyValidationError as e:
        click.echo(f"Strategy validation failed:\n  {e}", err=True)
        raise SystemExit(1)
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/cli/test_strategy_commands.py`
- [ ] Command exists with correct signature
- [ ] Valid strategy shows features
- [ ] Invalid strategy shows error message and exits 1
- [ ] V2 strategy shows migration message and exits 1

*Integration Tests:*
- [ ] CLI command callable via `ktrdr strategy validate`

*Smoke Test:*
```bash
ktrdr strategy validate --help
# Should show usage without error
```

**Acceptance Criteria:**
- [ ] Command output matches E2E test scenario
- [ ] Output is clear and useful for debugging
- [ ] Errors are actionable (say what to do)
- [ ] Exit codes correct (0 success, 1 failure)
- [ ] Tests written and passing

---

### Task 1.6: Create Example V3 Strategy

**File(s):** `strategies/v3_test_example.yaml` (NEW)
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Configuration

**Description:**
Create a comprehensive v3 example strategy for testing and documentation. Should exercise all v3 features.

**Implementation Notes:**

Include:
- Multiple indicators (single and multi-output)
- Multiple fuzzy sets (including two referencing same indicator)
- Mixed timeframe specs ("all" and explicit list)
- Both shorthand `[0,20,35]` and full `{type, parameters}` fuzzy syntax
- Dot notation for multi-output indicator (`bbands.upper`)

Based on example in DESIGN.md lines 247-366 but adapted for test use.

```yaml
name: "v3_test_example"
description: "Comprehensive v3 example for testing"
version: "3.0"

training_data:
  symbols:
    mode: single_symbol
    list: [EURUSD]
  timeframes:
    mode: multi_timeframe
    list: [5m, 1h, 1d]
    base_timeframe: 1h
  history_required: 200

indicators:
  rsi_14:
    type: rsi
    period: 14
  bbands_20_2:
    type: bbands
    period: 20
    multiplier: 2.0
  macd_12_26_9:
    type: macd
    fast_period: 12
    slow_period: 26
    signal_period: 9

fuzzy_sets:
  # Two interpretations of the same indicator
  rsi_fast:
    indicator: rsi_14
    oversold: [0, 25, 40]      # Shorthand
    overbought: [60, 75, 100]

  rsi_slow:
    indicator: rsi_14
    oversold:                   # Full form
      type: triangular
      parameters: [0, 15, 25]
    overbought:
      type: triangular
      parameters: [75, 85, 100]

  # Dot notation for multi-output
  bbands_position:
    indicator: bbands_20_2.middle
    below: [0, 0.3, 0.5]
    above: [0.5, 0.7, 1.0]

  macd_momentum:
    indicator: macd_12_26_9.histogram
    bearish: [-50, -10, 0]
    bullish: [0, 10, 50]

nn_inputs:
  - fuzzy_set: rsi_fast
    timeframes: [5m]
  - fuzzy_set: rsi_slow
    timeframes: [1h, 1d]
  - fuzzy_set: bbands_position
    timeframes: all
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

**Testing Requirements:**

*Smoke Test:*
```bash
ktrdr strategy validate strategies/v3_test_example.yaml
```

**Acceptance Criteria:**
- [ ] Strategy passes `ktrdr strategy validate`
- [ ] Demonstrates all v3 features (shorthand, full form, dot notation, "all" timeframes)
- [ ] Can be used for M2-M5 testing
- [ ] YAML is well-commented for documentation value

---

## E2E Test Scenario

**Purpose:** Prove v3 config loading, validation, and feature resolution work
**Duration:** ~5 seconds
**Prerequisites:** Indicator Standardization M1-M5 complete (for dot notation validation)

### Test Steps

```bash
#!/bin/bash
# M1 E2E Test: V3 Config Loading & Validation

set -e  # Exit on error

echo "=== M1 E2E Test: V3 Config Loading ==="

# 1. Create test strategy
echo "Creating test strategy..."
cat > /tmp/m1_test_v3.yaml << 'EOF'
name: "m1_e2e_test"
version: "3.0"

training_data:
  symbols:
    mode: single_symbol
    list: [EURUSD]
  timeframes:
    mode: multi_timeframe
    list: [5m, 1h]
    base_timeframe: 1h
  history_required: 100

indicators:
  rsi_14:
    type: rsi
    period: 14
  bbands_20_2:
    type: bbands
    period: 20
    multiplier: 2.0

fuzzy_sets:
  rsi_fast:
    indicator: rsi_14
    oversold: [0, 25, 40]
    overbought: [60, 75, 100]
  rsi_slow:
    indicator: rsi_14
    oversold: [0, 15, 25]
    overbought: [75, 85, 100]
  bbands_squeeze:
    indicator: bbands_20_2.middle
    tight: [0, 0.5, 1.0]
    wide: [1.5, 2.5, 5.0]

nn_inputs:
  - fuzzy_set: rsi_fast
    timeframes: [5m]
  - fuzzy_set: rsi_slow
    timeframes: [1h]
  - fuzzy_set: bbands_squeeze
    timeframes: all

model:
  type: mlp
  architecture:
    hidden_layers: [64, 32]
    activation: relu
    dropout: 0.2
  training:
    learning_rate: 0.001
    epochs: 50
    batch_size: 32

decisions:
  output_format: classification
  confidence_threshold: 0.6

training:
  method: supervised
  labels:
    source: zigzag
    zigzag_threshold: 0.02
EOF

# 2. Validate the strategy
echo "Validating v3 strategy..."
OUTPUT=$(ktrdr strategy validate /tmp/m1_test_v3.yaml)
echo "$OUTPUT"

# Verify expected features
echo "$OUTPUT" | grep -q "5m_rsi_fast_oversold" || { echo "FAIL: missing 5m_rsi_fast_oversold"; exit 1; }
echo "$OUTPUT" | grep -q "1h_rsi_slow_overbought" || { echo "FAIL: missing 1h_rsi_slow_overbought"; exit 1; }
echo "$OUTPUT" | grep -q "5m_bbands_squeeze_tight" || { echo "FAIL: missing 5m_bbands_squeeze_tight"; exit 1; }
echo "$OUTPUT" | grep -q "1h_bbands_squeeze_wide" || { echo "FAIL: missing 1h_bbands_squeeze_wide"; exit 1; }
echo "Feature resolution: PASS"

# 3. Test v2 rejection (create a v2-style strategy)
echo "Testing v2 rejection..."
cat > /tmp/v2_style.yaml << 'EOF'
name: "v2_style"
version: "2.0"
training_data:
  symbols: {mode: single_symbol, list: [TEST]}
  timeframes: {mode: single_timeframe, list: [1h], base_timeframe: 1h}
indicators:
  - name: rsi
    feature_id: rsi_14
    period: 14
fuzzy_sets:
  rsi_14:
    oversold: {type: triangular, parameters: [0, 20, 35]}
model: {type: mlp, architecture: {hidden_layers: [32]}}
decisions: {output_format: classification}
training: {method: supervised, labels: {source: zigzag}}
EOF

if ktrdr strategy validate /tmp/v2_style.yaml 2>&1 | grep -q "not v3 format"; then
    echo "V2 rejection: PASS"
else
    echo "FAIL: V2 strategy should be rejected"
    exit 1
fi

# 4. Test invalid reference detection
echo "Testing invalid reference detection..."
cat > /tmp/invalid_ref.yaml << 'EOF'
name: "invalid"
version: "3.0"
training_data:
  symbols: {mode: single_symbol, list: [TEST]}
  timeframes: {mode: single_timeframe, list: [1h], base_timeframe: 1h}
  history_required: 100
indicators:
  rsi_14: {type: rsi, period: 14}
fuzzy_sets:
  bad_ref:
    indicator: nonexistent_indicator
    low: [0, 25, 50]
nn_inputs:
  - fuzzy_set: bad_ref
    timeframes: all
model: {type: mlp, architecture: {hidden_layers: [32]}}
decisions: {output_format: classification}
training: {method: supervised, labels: {source: zigzag}}
EOF

if ktrdr strategy validate /tmp/invalid_ref.yaml 2>&1 | grep -qi "nonexistent"; then
    echo "Invalid reference detection: PASS"
else
    echo "FAIL: Invalid indicator reference should be caught"
    exit 1
fi

# 5. Cleanup
rm -f /tmp/m1_test_v3.yaml /tmp/v2_style.yaml /tmp/invalid_ref.yaml

echo ""
echo "=== M1 E2E Test: ALL PASSED ==="
```

### Success Criteria

- [ ] Valid v3 strategy passes validation
- [ ] Feature list includes all expected features (10 total)
- [ ] V2 strategy rejected with "not v3 format" message
- [ ] Invalid indicator reference caught with clear error
- [ ] No errors in test run

---

## Completion Checklist

- [ ] Task 1.1: V3 Pydantic models created and tested
- [ ] Task 1.2: FeatureResolver created and tested
- [ ] Task 1.3: V3 validator created and tested
- [ ] Task 1.4: Strategy loader updated for v3
- [ ] Task 1.5: CLI `strategy validate` command works
- [ ] Task 1.6: Example v3 strategy created
- [ ] All unit tests pass: `make test-unit`
- [ ] E2E test script passes
- [ ] Quality gates pass: `make quality`
- [ ] No regressions in existing tests
- [ ] Code reviewed and merged to feature branch
