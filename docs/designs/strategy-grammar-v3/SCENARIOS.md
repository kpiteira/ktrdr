# Strategy Grammar v3: Validation Scenarios

**Validation Date:** 2026-01-04
**Documents Validated:** DESIGN.md, ARCHITECTURE.md
**Prerequisite:** [Indicator Standardization](../indicator-standardization/DESIGN.md) must be completed first

## Validation Summary

| Metric | Value |
|--------|-------|
| Scenarios Validated | 8 |
| Critical Gaps Found | 6 (all resolved) |
| Interface Contracts | 5 components |

---

## Key Decisions

These decisions emerged from scenario tracing and should guide implementation:

### Decision 1: Shorthand Expansion Timing

**Context:** V3 allows `oversold: [0, 20, 35]` as shorthand for `{type: triangular, parameters: [0, 20, 35]}`.

**Decision:** Expand during Pydantic parsing via `@model_validator`.

**Rationale:** Keeps the model self-consistent. Once parsed, all code sees the full form.

### Decision 2: IndicatorEngine Interface Change

**Context:** V2 takes `list[dict]`, V3 needs `dict[str, IndicatorDefinition]`.

**Decision:** Replace interface entirely (breaking change within v3 migration).

**Rationale:** No production models exist, so clean break is acceptable.

### Decision 3: FuzzyEngine Interface Change

**Context:** V2 `fuzzify(indicator, values)` uses indicator name. V3 fuzzy_sets have separate `indicator` field.

**Decision:** New signature `fuzzify(fuzzy_set_id, indicator_values)` with fuzzy_set_id as primary key.

**Rationale:** Matches v3 conceptual model where fuzzy_set is the primary entity.

### Decision 4: Feature Order Determinism

**Context:** Training and backtest must produce identical feature order.

**Decision:** Order determined by:
1. `nn_inputs` list order (YAML order)
2. Within each nn_input: timeframes order × membership function order
3. Stored in `ModelMetadataV3.resolved_features`
4. Validated at backtest time

**Rationale:** Explicit ordering prevents subtle bugs from alphabetical sorting.

### Decision 5: Old Model Compatibility

**Context:** What happens to v2-trained models after migration?

**Decision:** Delete all existing models. No migration path needed.

**Rationale:** Confirmed no production models exist.

### Decision 6: Multi-Output Indicator References

**Context:** Indicators like bbands produce multiple outputs (upper, middle, lower). How does a fuzzy set specify which output to use?

**Decision:** Dot notation: `indicator: bbands_20_2.middle`

**Implementation requirements:**

- Multi-output indicators must implement `get_output_names() -> list[str]`
- If no dot in reference, use primary output (`get_primary_output_suffix()`)
- Validator checks that output name is valid for the indicator type
- Standardize output names across all multi-output indicators

**Rationale:** Explicit, readable, and enables validation and agent discoverability.

---

## Scenarios Validated

### Scenario 1: Simple V3 Strategy Load

**Trigger:** `ktrdr strategy validate strategies/v3_test.yaml`

**Execution Trace:**
1. CLI parses command → filepath
2. StrategyConfigurationLoader detects v3 (indicators as dict + nn_inputs present)
3. Pydantic parses to StrategyConfigurationV3 (shorthand expanded)
4. StrategyValidator checks:
   - All fuzzy_sets.*.indicator reference existing indicator_ids
   - All nn_inputs.*.fuzzy_set reference existing fuzzy_set_ids
   - All nn_inputs.*.timeframes are valid ("all" or in training_data)
   - Warn on unused indicators
5. FeatureResolver resolves to concrete features
6. CLI displays result

**Gaps Identified:** GAP-1 (shorthand timing) → resolved

---

### Scenario 2: Multi-Timeframe Training

**Trigger:** Agent triggers training with v3 strategy

**Execution Trace:**
1. TrainingPipeline loads StrategyConfigurationV3
2. FeatureResolver.resolve() → ordered list of ResolvedFeature
3. IndicatorEngine initialized with `config.indicators` (dict)
4. FuzzyEngine initialized with `config.fuzzy_sets`
5. For each timeframe:
   - Compute required indicators (once per indicator, even if multiple fuzzy sets use it)
   - Apply required fuzzy sets
   - Prefix columns with timeframe
6. FuzzyNeuralProcessor combines multi-TF features
7. Model trains
8. ModelMetadataV3 saved with resolved_features

**Gaps Identified:** GAP-2 (IndicatorEngine interface), GAP-3 (FuzzyEngine interface) → resolved

---

### Scenario 3: Training → Backtest Feature Consistency

**Trigger:** Backtest model trained with v3 strategy

**Execution Trace:**
1. Load ModelMetadataV3 (includes resolved_features)
2. Load StrategyConfigurationV3 from metadata
3. FeatureCache uses same FeatureResolver as training
4. Compute features with identical naming
5. Validate: `set(produced_columns) == set(metadata.resolved_features)`
6. Validate: order matches
7. Model inference with correct feature alignment

**Gaps Identified:** GAP-4 (config storage), GAP-5 (feature order) → resolved

---

### Scenario 4: Same Indicator, Multiple Fuzzy Sets

**Trigger:** Strategy with rsi_14 interpreted by both rsi_fast and rsi_slow

```yaml
indicators:
  rsi_14:
    type: rsi
    period: 14

fuzzy_sets:
  rsi_fast:
    indicator: rsi_14
    oversold: [0, 25, 40]
  rsi_slow:
    indicator: rsi_14
    oversold: [0, 15, 25]

nn_inputs:
  - fuzzy_set: rsi_fast
    timeframes: [5m]
  - fuzzy_set: rsi_slow
    timeframes: [1d]
```

**Execution Trace:**
1. FeatureResolver produces: `5m_rsi_fast_oversold`, `1d_rsi_slow_oversold`
2. IndicatorEngine computes rsi_14 once per timeframe
3. FuzzyEngine applies rsi_fast to 5m data → `5m_rsi_fast_*`
4. FuzzyEngine applies rsi_slow to 1d data → `1d_rsi_slow_*`

**Result:** Traces cleanly. Key insight: indicator computed once, multiple interpretations.

---

### Scenario 5: `timeframes: all` Resolution

**Trigger:** nn_input with `timeframes: all`

```yaml
training_data:
  timeframes:
    list: [5m, 1h, 1d]

nn_inputs:
  - fuzzy_set: volatility_regime
    timeframes: all  # Expands to [5m, 1h, 1d]
```

**Execution Trace:**
1. FeatureResolver sees `timeframes: all`
2. Resolves to `config.training_data.timeframes.list`
3. Generates features for all three timeframes

**Result:** Simple expansion, no issues.

---

### Scenario 6: V2 Strategy Rejection

**Trigger:** User loads v2 strategy after migration

**Execution Trace:**
1. StrategyConfigurationLoader detects v2 (indicators is list, no nn_inputs)
2. Raises ValueError with message:
   ```
   Strategy 'neuro_mean_reversion.yaml' is not v3 format.
   Run 'ktrdr strategy migrate' to upgrade.
   ```

**Result:** Clear guidance for users.

---

### Scenario 7: Feature Mismatch at Backtest

**Trigger:** Model metadata doesn't match computed features

**Execution Trace:**
1. FeatureCache computes features
2. Validation: `missing = expected - produced`
3. If missing: `ValueError: Missing features: {1h_rsi_momentum_oversold, ...}`
4. If extra: Warning logged, extra features ignored

**Result:** Fail-fast with clear diagnostic.

---

### Scenario 8: Agent Generates V3 Strategy

**Trigger:** Agent designs new strategy

**Execution Trace:**
1. AgentService calls LLM with v3-format prompt
2. LLM generates YAML
3. AgentService parses and validates
4. If invalid: retry with error feedback
5. If valid: save to strategies/

**Gaps Identified:** GAP-7 (prompt update) → deferred to M7

---

## Interface Contracts

### FeatureResolver

```python
@dataclass
class ResolvedFeature:
    feature_id: str          # "5m_rsi_fast_oversold"
    timeframe: str           # "5m"
    fuzzy_set_id: str        # "rsi_fast"
    membership_name: str     # "oversold"
    indicator_id: str        # "rsi_14"

class FeatureResolver:
    def resolve(self, config: StrategyConfigurationV3) -> list[ResolvedFeature]:
        """Returns ordered list - this IS the feature order."""

    def get_indicators_for_timeframe(self, resolved, timeframe) -> set[str]:
        """Indicator IDs needed for a timeframe."""

    def get_fuzzy_sets_for_timeframe(self, resolved, timeframe) -> set[str]:
        """Fuzzy set IDs needed for a timeframe."""
```

### IndicatorEngine (V3)

```python
class IndicatorEngine:
    def __init__(self, indicators: dict[str, IndicatorDefinition]):
        """Initialize with v3 indicator definitions."""

    def compute(self, data: pd.DataFrame, indicator_ids: set[str]) -> pd.DataFrame:
        """Returns columns named by indicator_id (no timeframe prefix)."""
```

### FuzzyEngine (V3)

```python
class FuzzyEngine:
    def __init__(self, fuzzy_sets: dict[str, FuzzySetDefinition]):
        """Initialize with v3 fuzzy set definitions."""

    def get_indicator_for_fuzzy_set(self, fuzzy_set_id: str) -> str:
        """Get the indicator_id that a fuzzy_set references."""

    def fuzzify(self, fuzzy_set_id: str, indicator_values: pd.Series) -> pd.DataFrame:
        """Returns columns: {fuzzy_set_id}_{membership} (no timeframe prefix)."""

    def get_membership_names(self, fuzzy_set_id: str) -> list[str]:
        """Ordered list of membership function names."""
```

### ModelMetadataV3

```python
@dataclass
class ModelMetadataV3:
    model_name: str
    strategy_name: str
    strategy_version: str  # "3.0"

    # V3-specific: full config for reproducibility
    indicators: dict[str, dict]
    fuzzy_sets: dict[str, dict]
    nn_inputs: list[dict]

    # Critical: ordered feature list
    resolved_features: list[str]  # ["5m_rsi_fast_oversold", ...]

    training_symbols: list[str]
    training_timeframes: list[str]
```

---

## Milestone Structure

| Milestone | Description | E2E Testable |
|-----------|-------------|--------------|
| M1 | V3 Config Loading & Validation | `ktrdr strategy validate` works |
| M2 | IndicatorEngine V3 | Dict-based indicator computation |
| M3 | FuzzyEngine V3 | fuzzy_set_id-based fuzzification |
| M4 | Training Pipeline V3 | Training produces correct features |
| M5 | Backtest Pipeline V3 | Backtest matches training features |
| M6 | CLI & Migration Tools | `ktrdr strategy migrate` works |
| M7 | Agent Integration | Agent generates valid v3 |
| M8 | Cleanup | No v2 remnants |

See ARCHITECTURE.md for detailed milestone specifications.
