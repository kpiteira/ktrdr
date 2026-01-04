# Strategy Grammar v3: Architecture

## Overview

This document describes the technical changes required to implement Strategy Grammar v3.
The migration touches every component that interacts with strategy configuration, from
parsing through training, backtesting, and model storage.

**Scope:** Complete replacement of v2 grammar. No backward compatibility.

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
        training_timeframes: list[str]
    ) -> list[ResolvedFeature]:
        """
        Resolve nn_inputs to concrete features.

        Args:
            config: The v3 strategy configuration
            training_timeframes: Available timeframes from training_data

        Returns:
            List of ResolvedFeature, one per NN input
        """
        features = []

        for input_spec in config.nn_inputs:
            fuzzy_set = config.fuzzy_sets[input_spec.fuzzy_set]
            indicator_id = fuzzy_set.indicator

            # Resolve timeframes
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

    def compute_for_timeframe(
        self,
        data: pd.DataFrame,
        timeframe: str,
        indicator_ids: set[str]
    ) -> pd.DataFrame:
        """
        Compute specified indicators on data.

        Args:
            data: OHLCV DataFrame
            timeframe: Timeframe string (for column prefixing)
            indicator_ids: Which indicators to compute

        Returns:
            DataFrame with indicator columns prefixed by timeframe
        """
        result = data.copy()
        for indicator_id in indicator_ids:
            if indicator_id not in self._indicators:
                raise ValueError(f"Unknown indicator: {indicator_id}")

            indicator = self._indicators[indicator_id]
            output = indicator.calculate(data)

            # Column name: {timeframe}_{indicator_id}
            col_name = f"{timeframe}_{indicator_id}"
            result[col_name] = output

        return result
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
        for fuzzy_set_id, definition in fuzzy_sets.items():
            self._fuzzy_sets[fuzzy_set_id] = self._build_membership_functions(
                definition
            )

    def fuzzify(
        self,
        fuzzy_set_id: str,
        indicator_values: pd.Series,
        timeframe: str
    ) -> pd.DataFrame:
        """
        Apply fuzzy set to indicator values.

        Args:
            fuzzy_set_id: Which fuzzy set to apply
            indicator_values: Raw indicator values
            timeframe: For feature naming

        Returns:
            DataFrame with columns: {timeframe}_{fuzzy_set_id}_{membership}
        """
        fuzzy_set = self._fuzzy_sets[fuzzy_set_id]
        result = {}

        for membership_name, mf in fuzzy_set.items():
            feature_id = f"{timeframe}_{fuzzy_set_id}_{membership_name}"
            result[feature_id] = mf.evaluate(indicator_values)

        return pd.DataFrame(result)
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
    def __init__(self, config: StrategyConfigurationV3, model_metadata: ModelMetadata):
        self.config = config
        self.feature_resolver = FeatureResolver()
        self.indicator_engine = IndicatorEngine(config.indicators)
        self.fuzzy_engine = FuzzyEngine(config.fuzzy_sets)

        # Expected features from model
        self.expected_features = model_metadata.feature_names

    def compute_features(self, data: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Compute features for backtesting.

        MUST produce same feature_ids as training.
        """
        # Same logic as training pipeline
        ...

        # Validate we produced all expected features
        produced = set(result.columns)
        expected = set(self.expected_features)

        missing = expected - produced
        if missing:
            raise ValueError(f"Missing features: {missing}")
```

### 6. Model Metadata

#### `ktrdr/models/model_metadata.py`

**Store v3 strategy info for reproducibility:**

```python
@dataclass
class ModelMetadataV3:
    # Existing fields...

    # V3-specific
    strategy_version: str = "3.0"
    indicators: dict[str, dict]      # Indicator definitions
    fuzzy_sets: dict[str, dict]      # Fuzzy set definitions
    nn_inputs: list[dict]            # NN input specs
    resolved_features: list[str]     # Ordered list of feature_ids
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
