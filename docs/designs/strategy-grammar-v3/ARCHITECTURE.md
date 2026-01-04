# Strategy Grammar v3: Architecture

> **⚠️ TIGHTLY COUPLED WITH INDICATOR STANDARDIZATION**
>
> This architecture and [Indicator Standardization](../indicator-standardization/DESIGN.md) are **interdependent**:
>
> 1. **Indicator Standardization M1-M5** — Must complete **BEFORE** v3 implementation starts
> 2. **Strategy Grammar v3** (all phases below) — Depends on standardized indicator outputs
> 3. **Indicator Standardization M6** — Cleanup happens **AFTER** v3 is complete and verified
>
> See [Milestone 0](#milestone-0-indicator-standardization-prerequisite) for details.

## Overview

This document describes the technical changes required to implement Strategy Grammar v3.
The migration touches every component that interacts with strategy configuration, from
parsing through training, backtesting, and model storage.

**Scope:** Complete replacement of v2 grammar. No backward compatibility.

**Dependency:** Indicator Standardization (see prerequisite above).

---

## Component Inventory

### Components to Modify

| Category | Component | Changes Required |
|----------|-----------|------------------|
| **Config** | `ktrdr/config/models.py` | New Pydantic models for v3 |
| **Config** | `ktrdr/config/strategy_loader.py` | Parse v3 format only |
| **Config** | `ktrdr/config/strategy_validator.py` | New validation rules |
| **Indicators** | `ktrdr/indicators/indicator_engine.py` | Consume indicator dict |
| **Indicators** | `ktrdr/indicators/base_indicator.py` | Remove feature_id handling |
| **Fuzzy** | `ktrdr/fuzzy/engine.py` | New fuzzy set resolution |
| **Fuzzy** | `ktrdr/fuzzy/config.py` | Parse v3 fuzzy_sets format |
| **Fuzzy** | `ktrdr/fuzzy/multi_timeframe_engine.py` | Consume nn_inputs |
| **Training** | `ktrdr/training/training_pipeline.py` | Use v3 config flow |
| **Training** | `ktrdr/training/fuzzy_neural_processor.py` | Generate features from nn_inputs |
| **Training** | `ktrdr/training/training_worker.py` | Pass v3 config |
| **Backtest** | `ktrdr/backtesting/feature_cache.py` | Match training feature generation |
| **Backtest** | `ktrdr/backtesting/backtesting_service.py` | Use v3 config |
| **Backtest** | `ktrdr/backtesting/model_loader.py` | Load v3 metadata |
| **Decision** | `ktrdr/decision/orchestrator.py` | Use v3 feature names |
| **Models** | `ktrdr/models/model_metadata.py` | Store v3 feature info |
| **Checkpoints** | `ktrdr/checkpoint/` | Store v3 strategy config |
| **API** | `ktrdr/api/endpoints/strategies.py` | Validate v3 format |
| **API** | `ktrdr/api/services/training_service.py` | Process v3 config |
| **API** | `ktrdr/api/services/fuzzy_service.py` | Use v3 fuzzy resolution |
| **CLI** | `ktrdr/cli/strategy_commands.py` | v3 commands |
| **Agents** | `ktrdr/agents/prompts.py` | Generate v3 strategies |
| **Agents** | `ktrdr/agents/strategy_utils.py` | Manipulate v3 format |
| **Host Service** | `training-host-service/` | Accept v3 config |
| **MCP** | `mcp/src/tools/strategy_tools.py` | v3 format |

### Files to Delete

- Migration utilities for v1→v2 (no longer needed)
- Tests for v2 format that don't apply to v3

---

## New Data Models

### 1. Strategy Configuration V3

**File:** `ktrdr/config/models.py`

```python
from pydantic import BaseModel, Field
from typing import Optional, Union
from enum import Enum


class IndicatorDefinition(BaseModel):
    """A single indicator calculation definition.

    The key in the indicators dict serves as the indicator_id.
    """
    type: str = Field(..., description="Indicator type (rsi, macd, etc.)")
    # All other fields are indicator-specific parameters

    model_config = {"extra": "allow"}


class FuzzyMembership(BaseModel):
    """A fuzzy membership function definition."""
    type: str = Field(default="triangular")
    parameters: list[float]


class FuzzySetDefinition(BaseModel):
    """A fuzzy interpretation of an indicator.

    The key in the fuzzy_sets dict serves as the fuzzy_set_id.
    """
    indicator: str = Field(..., description="indicator_id to interpret")
    # Remaining fields are membership function definitions
    # Keys are membership names (oversold, neutral, etc.)
    # Values are either [a,b,c] shorthand or FuzzyMembership objects

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


class NNInputSpec(BaseModel):
    """Specification for neural network inputs."""
    fuzzy_set: str = Field(..., description="fuzzy_set_id to include")
    timeframes: Union[list[str], str] = Field(
        ...,
        description="Timeframes to apply this fuzzy set to. 'all' for all training TFs."
    )


class StrategyConfigurationV3(BaseModel):
    """Complete v3 strategy configuration."""

    # Identity
    name: str
    description: Optional[str] = None
    version: str = "3.0"

    # Data scope
    training_data: TrainingDataConfiguration
    deployment: Optional[DeploymentConfiguration] = None

    # The new sections
    indicators: dict[str, IndicatorDefinition]
    fuzzy_sets: dict[str, FuzzySetDefinition]
    nn_inputs: list[NNInputSpec]

    # Model and training (unchanged from v2)
    model: ModelConfiguration
    decisions: DecisionConfiguration
    training: TrainingConfiguration
```

### 2. Resolved Feature Specification

**File:** `ktrdr/config/feature_resolver.py` (NEW)

```python
@dataclass
class ResolvedFeature:
    """A fully resolved NN input feature.

    This is the canonical representation after parsing nn_inputs.
    """
    feature_id: str          # e.g., "5m_rsi_fast_oversold"
    timeframe: str           # e.g., "5m"
    fuzzy_set_id: str        # e.g., "rsi_fast"
    membership_name: str     # e.g., "oversold"
    indicator_id: str        # e.g., "rsi_14"


class FeatureResolver:
    """Resolves nn_inputs into concrete feature specifications."""

    def resolve(
        self,
        config: StrategyConfigurationV3,
    ) -> list[ResolvedFeature]:
        """
        Resolve nn_inputs to concrete features.

        IMPORTANT: The returned list order IS the canonical feature order.
        This order must be:
        1. Stored in ModelMetadataV3.resolved_features during training
        2. Used by FeatureCache during backtest
        3. Validated at backtest time

        Order is determined by:
        1. nn_inputs list order (YAML order preserved)
        2. Within each nn_input: timeframes order × membership function order

        Args:
            config: The v3 strategy configuration

        Returns:
            Ordered list of ResolvedFeature (order is source of truth)
        """
        features = []

        for input_spec in config.nn_inputs:
            fuzzy_set = config.fuzzy_sets[input_spec.fuzzy_set]
            indicator_id = fuzzy_set.indicator

            # Resolve timeframes
            training_timeframes = config.training_data.timeframes.list
            if input_spec.timeframes == "all":
                timeframes = training_timeframes
            else:
                timeframes = input_spec.timeframes

            # Get membership names from fuzzy set
            membership_names = self._get_membership_names(fuzzy_set)

            # Generate features for each timeframe × membership combination
            for tf in timeframes:
                for membership in membership_names:
                    feature_id = f"{tf}_{input_spec.fuzzy_set}_{membership}"
                    features.append(ResolvedFeature(
                        feature_id=feature_id,
                        timeframe=tf,
                        fuzzy_set_id=input_spec.fuzzy_set,
                        membership_name=membership,
                        indicator_id=indicator_id
                    ))

        return features

    def get_indicators_for_timeframe(
        self,
        resolved: list[ResolvedFeature],
        timeframe: str,
    ) -> set[str]:
        """Get indicator_ids needed for a specific timeframe."""
        return {f.indicator_id for f in resolved if f.timeframe == timeframe}

    def get_fuzzy_sets_for_timeframe(
        self,
        resolved: list[ResolvedFeature],
        timeframe: str,
    ) -> set[str]:
        """Get fuzzy_set_ids needed for a specific timeframe."""
        return {f.fuzzy_set_id for f in resolved if f.timeframe == timeframe}
```

---

## Component Changes

### 1. Config Layer

#### `ktrdr/config/strategy_loader.py`

**Current:** Detects v1 vs v2, supports migration
**New:** Only loads v3, rejects v2

```python
class StrategyConfigurationLoader:
    """Loads v3 strategy configurations."""

    def load(self, config_path: Path) -> StrategyConfigurationV3:
        """Load and validate v3 strategy."""
        raw = yaml.safe_load(config_path.read_text())

        if not self._is_v3_format(raw):
            raise ValueError(
                f"Strategy '{config_path}' is not v3 format. "
                "Run 'ktrdr strategy migrate' to upgrade."
            )

        return StrategyConfigurationV3(**raw)

    def _is_v3_format(self, config: dict) -> bool:
        """Check for v3 markers: indicators as dict, nn_inputs present."""
        return (
            isinstance(config.get("indicators"), dict) and
            "nn_inputs" in config
        )
```

#### `ktrdr/config/strategy_validator.py`

**New validations:**

1. All `indicator` references in fuzzy_sets exist in indicators dict
2. All `fuzzy_set` references in nn_inputs exist in fuzzy_sets dict
3. All timeframes in nn_inputs are valid (either "all" or in training_data.timeframes)
4. Warn if indicators defined but not referenced
5. Shorthand `[a,b,c]` converted to `{type: "triangular", parameters: [a,b,c]}`

### 2. Indicator Layer

#### `ktrdr/indicators/indicator_engine.py`

**Current:** Takes list of indicator configs with feature_id
**New:** Takes dict of indicator definitions keyed by indicator_id

```python
class IndicatorEngine:
    def __init__(self, indicators: dict[str, IndicatorDefinition]):
        """
        Args:
            indicators: Dict mapping indicator_id to definition
        """
        self._indicators = {}
        for indicator_id, definition in indicators.items():
            self._indicators[indicator_id] = self._create_indicator(
                indicator_id, definition
            )

    def compute(
        self,
        data: pd.DataFrame,
        indicator_ids: set[str]
    ) -> pd.DataFrame:
        """
        Compute specified indicators on data.

        Args:
            data: OHLCV DataFrame
            indicator_ids: Which indicators to compute

        Returns:
            DataFrame with indicator columns named by indicator_id
            Note: NO timeframe prefix - caller adds that for consistency
        """
        result = data.copy()
        for indicator_id in indicator_ids:
            if indicator_id not in self._indicators:
                raise ValueError(f"Unknown indicator: {indicator_id}")

            indicator = self._indicators[indicator_id]
            output = indicator.calculate(data)

            # Column name is just indicator_id (e.g., "rsi_14")
            result[indicator_id] = output

        return result
```

#### `ktrdr/indicators/base_indicator.py`

**New requirement:** Multi-output indicators must implement `get_output_names()`:

```python
class BaseIndicator(ABC):
    # ... existing methods ...

    @classmethod
    def get_output_names(cls) -> list[str]:
        """
        Return logical output names for multi-output indicators.

        Single-output indicators return empty list (default).
        Multi-output indicators override to return their outputs.

        Used for:
        - Validating dot notation references (e.g., bbands_20_2.middle)
        - Agent discoverability when designing strategies
        - Documentation generation

        Returns:
            List of output names in canonical order
        """
        return []  # Single-output default

# Example implementations:
class BollingerBandsIndicator(BaseIndicator):
    @classmethod
    def get_output_names(cls) -> list[str]:
        return ["upper", "middle", "lower"]

class MACDIndicator(BaseIndicator):
    @classmethod
    def get_output_names(cls) -> list[str]:
        return ["line", "signal", "histogram"]
```

### 3. Fuzzy Layer

#### `ktrdr/fuzzy/engine.py`

**Current:** Takes fuzzy_sets keyed by feature_id (actually indicator alias)
**New:** Takes fuzzy_sets keyed by fuzzy_set_id, each with explicit indicator reference

```python
class FuzzyEngine:
    def __init__(self, fuzzy_sets: dict[str, FuzzySetDefinition]):
        """
        Args:
            fuzzy_sets: Dict mapping fuzzy_set_id to definition
        """
        self._fuzzy_sets = {}
        self._indicator_map = {}  # fuzzy_set_id -> indicator_id
        for fuzzy_set_id, definition in fuzzy_sets.items():
            self._fuzzy_sets[fuzzy_set_id] = self._build_membership_functions(
                definition
            )
            self._indicator_map[fuzzy_set_id] = definition.indicator

    def get_indicator_for_fuzzy_set(self, fuzzy_set_id: str) -> str:
        """Get the indicator_id that a fuzzy_set references."""
        return self._indicator_map[fuzzy_set_id]

    def fuzzify(
        self,
        fuzzy_set_id: str,
        indicator_values: pd.Series,
    ) -> pd.DataFrame:
        """
        Apply fuzzy set to indicator values.

        Args:
            fuzzy_set_id: Which fuzzy set to apply
            indicator_values: Raw indicator values

        Returns:
            DataFrame with columns: {fuzzy_set_id}_{membership}
            Note: NO timeframe prefix - caller adds that for consistency
        """
        fuzzy_set = self._fuzzy_sets[fuzzy_set_id]
        result = {}

        for membership_name, mf in fuzzy_set.items():
            col_name = f"{fuzzy_set_id}_{membership_name}"
            result[col_name] = mf.evaluate(indicator_values)

        return pd.DataFrame(result)

    def get_membership_names(self, fuzzy_set_id: str) -> list[str]:
        """Get ordered list of membership function names for a fuzzy set."""
        return list(self._fuzzy_sets[fuzzy_set_id].keys())
```

### 4. Training Pipeline

#### `ktrdr/training/training_pipeline.py`

**Key change:** Use FeatureResolver to determine what to compute

```python
class TrainingPipeline:
    def __init__(self, config: StrategyConfigurationV3):
        self.config = config
        self.feature_resolver = FeatureResolver()
        self.indicator_engine = IndicatorEngine(config.indicators)
        self.fuzzy_engine = FuzzyEngine(config.fuzzy_sets)

    def prepare_features(self, data: dict[str, dict[str, pd.DataFrame]]) -> pd.DataFrame:
        """
        Prepare NN input features from multi-symbol, multi-timeframe data.

        Args:
            data: {symbol: {timeframe: DataFrame}}

        Returns:
            Feature DataFrame with columns matching resolved feature_ids
        """
        # Resolve what features we need
        timeframes = self.config.training_data.timeframes.list
        resolved = self.feature_resolver.resolve(self.config, timeframes)

        # Determine which indicators to compute per timeframe
        indicators_per_tf = self._group_by_timeframe(resolved)

        all_features = []
        for symbol, tf_data in data.items():
            symbol_features = []

            for timeframe, df in tf_data.items():
                if timeframe not in indicators_per_tf:
                    continue

                # Compute required indicators
                indicator_ids = indicators_per_tf[timeframe]["indicators"]
                indicator_df = self.indicator_engine.compute_for_timeframe(
                    df, timeframe, indicator_ids
                )

                # Apply fuzzy sets
                fuzzy_sets = indicators_per_tf[timeframe]["fuzzy_sets"]
                for fuzzy_set_id in fuzzy_sets:
                    indicator_id = self.config.fuzzy_sets[fuzzy_set_id].indicator
                    indicator_col = f"{timeframe}_{indicator_id}"

                    fuzzy_df = self.fuzzy_engine.fuzzify(
                        fuzzy_set_id,
                        indicator_df[indicator_col],
                        timeframe
                    )
                    symbol_features.append(fuzzy_df)

            all_features.append(pd.concat(symbol_features, axis=1))

        return pd.concat(all_features, axis=0)
```

### 5. Backtesting

#### `ktrdr/backtesting/feature_cache.py`

**Must match training exactly.** Same FeatureResolver, same feature_ids.

```python
class FeatureCache:
    def __init__(self, config: StrategyConfigurationV3, model_metadata: ModelMetadataV3):
        self.config = config
        self.feature_resolver = FeatureResolver()
        self.indicator_engine = IndicatorEngine(config.indicators)
        self.fuzzy_engine = FuzzyEngine(config.fuzzy_sets)

        # Expected features from model (ORDERED list - order matters!)
        self.expected_features = model_metadata.resolved_features

    def compute_features(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Compute features for backtesting.

        MUST produce same feature_ids AND same order as training.
        """
        # Same logic as training pipeline
        ...

        # Validate feature names match
        produced = set(result.columns)
        expected = set(self.expected_features)

        missing = expected - produced
        if missing:
            raise ValueError(f"Missing features: {missing}")

        extra = produced - expected
        if extra:
            logger.warning(f"Extra features will be ignored: {extra}")

        # CRITICAL: Reorder columns to match expected order
        # This ensures model sees features in the same order as training
        result = result[self.expected_features]

        return result
```

### 6. Model Metadata

#### `ktrdr/models/model_metadata.py`

**Store v3 strategy info for reproducibility:**

```python
@dataclass
class ModelMetadataV3:
    # Identity
    model_name: str
    strategy_name: str
    created_at: datetime

    # Version info
    strategy_version: str  # "3.0"

    # V3-specific: full strategy config for reproducibility
    indicators: dict[str, dict]      # Serialized IndicatorDefinition
    fuzzy_sets: dict[str, dict]      # Serialized FuzzySetDefinition
    nn_inputs: list[dict]            # Serialized NNInputSpec

    # CRITICAL: ordered feature list (source of truth for backtest)
    # This list defines the exact order features must appear in
    resolved_features: list[str]     # ["5m_rsi_fast_oversold", ...]

    # Training context
    training_symbols: list[str]
    training_timeframes: list[str]
    training_metrics: dict[str, float]  # loss, accuracy, etc.
```

### 7. Agent Strategy Generation

#### `ktrdr/agents/prompts.py`

**Update prompts to generate v3 format:**

```python
STRATEGY_GENERATION_PROMPT = """
Generate a trading strategy in v3 YAML format.

Structure:
1. indicators: Dict of indicator definitions (keyed by indicator_id)
2. fuzzy_sets: Dict of fuzzy interpretations (each references an indicator_id)
3. nn_inputs: List specifying which fuzzy_set + timeframe combinations

Example:
```yaml
indicators:
  rsi_14:
    type: rsi
    period: 14

fuzzy_sets:
  rsi_momentum:
    indicator: rsi_14
    oversold: [0, 20, 35]
    overbought: [65, 80, 100]

nn_inputs:
  - fuzzy_set: rsi_momentum
    timeframes: all
```
"""
```

---

## Migration Tooling

### CLI Command

```bash
ktrdr strategy migrate <path_or_directory> [--dry-run] [--backup]
```

**Migration rules:**

1. Convert `indicators` list to dict (key = existing feature_id)
2. Add `indicator` field to each fuzzy_set (value = matching indicator key)
3. Generate `nn_inputs` from training_data.timeframes × fuzzy_sets
4. Remove deprecated fields: `feature_id` from indicators

### Validation Command

```bash
ktrdr strategy validate <path>
```

**Checks:**
- v3 format compliance
- All references resolve
- Warns on unused indicators

### Feature Listing Command

```bash
ktrdr strategy features <path>
```

**Output:**
```
Strategy: mtf_forex_momentum
Features (12 total):

  5m_rsi_fast_oversold
  5m_rsi_fast_neutral
  5m_rsi_fast_overbought
  1h_rsi_slow_oversold
  1h_rsi_slow_neutral
  1h_rsi_slow_overbought
  1h_macd_momentum_bearish
  1h_macd_momentum_neutral
  1h_macd_momentum_bullish
  ...
```

---

## Verification Strategy

### Unit Tests

| Component | What to test |
|-----------|--------------|
| `FeatureResolver` | Resolves nn_inputs correctly, handles "all" |
| `StrategyValidator` | Catches invalid references, validates shorthand |
| `IndicatorEngine` | Creates indicators from dict format |
| `FuzzyEngine` | Applies fuzzy sets with new naming |

### Integration Tests

| Test | What it validates |
|------|-------------------|
| Training E2E | Full training with v3 strategy produces expected features |
| Backtest E2E | Backtest feature names match training |
| Migration | v2 strategy migrates correctly and trains identically |

### Smoke Tests

```bash
# Quick validation
ktrdr strategy validate strategies/v3_example.yaml

# Feature listing
ktrdr strategy features strategies/v3_example.yaml

# Full training
ktrdr train strategies/v3_example.yaml --dry-run
```

---

## Implementation Order

### Milestone 0: Indicator Standardization (PREREQUISITE)

**Indicator Standardization M1-M5 must be completed before v3 work begins.**

See [../indicator-standardization/DESIGN.md](../indicator-standardization/DESIGN.md) for full details.

**Summary (M1-M5):**

- Standardize all 29 indicators to consistent naming
- Add `get_output_names()` to BaseIndicator for multi-output discovery
- Single-output: `compute()` returns unnamed Series
- Multi-output: `compute()` returns DataFrame with semantic column names (`upper`, `signal`, `k`)
- IndicatorEngine handles prefixing with indicator_id

**Why M1-M5 first:**

- v3 dot notation (`bbands_20_2.upper`) depends on discoverable output names
- v3 feature naming assumes consistent indicator output format
- Removes technical debt that would complicate v3 implementation
- Can be tested independently before v3 changes

**M6 (Cleanup) comes AFTER v3:**

- M6 removes v2 compatibility code from indicator standardization
- This can only happen after v3 strategies replace all v2 strategies
- See [../indicator-standardization/implementation/M6_cleanup.md](../indicator-standardization/implementation/M6_cleanup.md)

**Scope:** ~29 indicators + engine updates + consumer updates (M1-M5), then cleanup (M6 post-v3)

---

### Phase 1: Core Models (Foundation)
1. `ktrdr/config/models.py` — Add v3 Pydantic models
2. `ktrdr/config/feature_resolver.py` — NEW: Feature resolution logic
3. `ktrdr/config/strategy_validator.py` — v3 validation rules

### Phase 2: Processing Engines
4. `ktrdr/indicators/indicator_engine.py` — Dict-based indicator creation
5. `ktrdr/fuzzy/engine.py` — New fuzzy set resolution
6. `ktrdr/fuzzy/config.py` — Parse v3 fuzzy_sets

### Phase 3: Pipelines
7. `ktrdr/training/training_pipeline.py` — Use FeatureResolver
8. `ktrdr/training/fuzzy_neural_processor.py` — v3 feature names
9. `ktrdr/backtesting/feature_cache.py` — Match training exactly

### Phase 4: Storage & Metadata
10. `ktrdr/models/model_metadata.py` — Store v3 info
11. `ktrdr/checkpoint/` — v3 strategy in checkpoints

### Phase 5: API & CLI
12. `ktrdr/api/endpoints/strategies.py` — v3 validation
13. `ktrdr/cli/strategy_commands.py` — migrate, validate, features commands
14. `ktrdr/config/strategy_loader.py` — Reject v2

### Phase 6: Agents
15. `ktrdr/agents/prompts.py` — Generate v3
16. `ktrdr/agents/strategy_utils.py` — Manipulate v3

### Phase 7: Cleanup
17. Delete v2 migration code
18. Migrate all existing strategies
19. Update all tests

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Training/backtest feature mismatch | FeatureResolver is single source of truth, used by both |
| Existing models incompatible | Model metadata includes strategy version; loader validates |
| Agent generates invalid v3 | Validator runs on all agent output before saving |
| Performance regression | Feature resolution is one-time at pipeline start |

---

## Decisions (Resolved)

1. **Existing trained models** — Delete all. None are production, all are test artifacts.

2. **Old checkpoints** — Delete all. Same situation as models.

3. **Implementation approach** — Incremental with validation that we don't regress.
   Each phase must pass tests before moving to next.

4. **Host service sync** — Training host service updated as part of Phase 3 (Pipelines).

5. **Shorthand expansion timing** — During Pydantic parsing via `@model_validator`.

6. **Feature ordering** — Determined by nn_inputs list order × membership order.
   Stored in `ModelMetadataV3.resolved_features`. Validated at backtest.

7. **Interface changes** — Clean break on IndicatorEngine and FuzzyEngine.
   Neither adds timeframe prefix; caller handles that for consistency.

8. **Multi-output indicator references** — Use dot notation: `bbands_20_2.middle`.
   Multi-output indicators must implement `get_output_names() -> list[str]`.
   Current indicator naming (e.g., `MACD_signal_12_26_9`) must be normalized
   to logical names (`signal`) with parameters handled separately.

9. **Indicator standardization is prerequisite** — Before starting v3 implementation,
   all 29 indicators must be standardized to consistent naming. This removes technical
   debt and establishes the foundation v3 depends on.
   See [../indicator-standardization/DESIGN.md](../indicator-standardization/DESIGN.md).

---

## Related Documents

- [DESIGN.md](DESIGN.md) — Grammar specification and rationale
- [SCENARIOS.md](SCENARIOS.md) — Validation scenarios and interface contracts
- [example_v3_strategy.yaml](example_v3_strategy.yaml) — Comprehensive example with edge cases
- [../indicator-standardization/DESIGN.md](../indicator-standardization/DESIGN.md) — Milestone 0 prerequisite
