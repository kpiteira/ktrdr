---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 4: Training Pipeline V3

**Branch:** `feature/strategy-grammar-v3-m4`
**Prerequisite:** M3 complete (both engines work with v3)
**Builds on:** M3 FuzzyEngine

## Goal

Full training pipeline works with v3 strategy configuration, producing a model with correct feature metadata stored in `ModelMetadataV3`.

## Why This Milestone

- Integrates all v3 components into working training flow
- Establishes feature order as source of truth (stored in metadata)
- Critical for M5 (backtest must match training)

---

## Tasks

### Task 4.1: Update TrainingPipeline for V3 Config

**File(s):** `ktrdr/training/training_pipeline.py`
**Type:** CODING
**Estimated time:** 3 hours

**Task Categories:** Cross-Component, Wiring/DI

**Description:**
Modify `TrainingPipeline` to use `FeatureResolver` and v3 engines for feature preparation.

**Implementation Notes:**

Key flow:
1. Load `StrategyConfigurationV3`
2. Use `FeatureResolver` to get ordered feature list
3. Initialize `IndicatorEngine` with v3 config
4. Initialize `FuzzyEngine` with v3 config
5. For each timeframe: compute indicators, apply fuzzy sets
6. Combine into feature DataFrame with correct column order

```python
class TrainingPipeline:
    def __init__(self, config: StrategyConfigurationV3):
        self.config = config
        self.feature_resolver = FeatureResolver()
        self.indicator_engine = IndicatorEngine(config.indicators)
        self.fuzzy_engine = FuzzyEngine(config.fuzzy_sets)

    def prepare_features(
        self,
        data: dict[str, dict[str, pd.DataFrame]]
    ) -> pd.DataFrame:
        """
        Prepare NN input features from multi-symbol, multi-timeframe data.

        Args:
            data: {symbol: {timeframe: DataFrame}}

        Returns:
            Feature DataFrame with columns matching resolved feature_ids,
            in the exact order from FeatureResolver
        """
        # Get canonical feature order
        resolved = self.feature_resolver.resolve(self.config)
        expected_columns = [f.feature_id for f in resolved]

        # Group by timeframe for efficient computation
        tf_requirements = self._group_requirements_by_timeframe(resolved)

        all_features = []
        for symbol, tf_data in data.items():
            symbol_dfs = []

            for timeframe, df in tf_data.items():
                if timeframe not in tf_requirements:
                    continue

                reqs = tf_requirements[timeframe]

                # Compute required indicators
                indicator_df = self.indicator_engine.compute_for_timeframe(
                    df, timeframe, reqs['indicators']
                )

                # Apply required fuzzy sets
                for fuzzy_set_id in reqs['fuzzy_sets']:
                    indicator_id = self.fuzzy_engine.get_indicator_for_fuzzy_set(
                        fuzzy_set_id
                    )
                    # Handle dot notation
                    indicator_col = f"{timeframe}_{indicator_id}"

                    fuzzy_df = self.fuzzy_engine.fuzzify(
                        fuzzy_set_id,
                        indicator_df[indicator_col]
                    )
                    # Add timeframe prefix
                    fuzzy_df = fuzzy_df.rename(columns={
                        col: f"{timeframe}_{col}"
                        for col in fuzzy_df.columns
                    })
                    symbol_dfs.append(fuzzy_df)

            if symbol_dfs:
                all_features.append(pd.concat(symbol_dfs, axis=1))

        result = pd.concat(all_features, axis=0)

        # CRITICAL: Reorder columns to match canonical order
        result = result[expected_columns]

        return result

    def _group_requirements_by_timeframe(
        self,
        resolved: list[ResolvedFeature]
    ) -> dict[str, dict]:
        """Group indicator/fuzzy requirements by timeframe."""
        result = {}
        for f in resolved:
            if f.timeframe not in result:
                result[f.timeframe] = {'indicators': set(), 'fuzzy_sets': set()}
            result[f.timeframe]['indicators'].add(f.indicator_id)
            result[f.timeframe]['fuzzy_sets'].add(f.fuzzy_set_id)
        return result
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/training/test_training_pipeline_v3.py`
- [ ] Pipeline accepts v3 config
- [ ] Features computed for all timeframes
- [ ] Column order matches FeatureResolver output
- [ ] Multiple symbols handled correctly
- [ ] Missing timeframe data handled gracefully

*Integration Tests:*
- [ ] Pipeline wired correctly with v3 engines

*Smoke Test:*
```bash
uv run python -c "
from ktrdr.config.strategy_loader import StrategyConfigurationLoader
from ktrdr.training.training_pipeline import TrainingPipeline
from pathlib import Path

loader = StrategyConfigurationLoader()
config = loader.load(Path('strategies/v3_test_example.yaml'))
pipeline = TrainingPipeline(config)
print('TrainingPipeline v3 init: OK')
"
```

**Acceptance Criteria:**
- [ ] Pipeline matches ARCHITECTURE.md lines 440-494
- [ ] Feature order is deterministic
- [ ] Unit tests pass

---

### Task 4.2: Update FuzzyNeuralProcessor for V3

**File(s):** `ktrdr/training/fuzzy_neural_processor.py`
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Cross-Component

**Description:**
Update `FuzzyNeuralProcessor` to work with v3 feature naming conventions.

**Implementation Notes:**

The processor should:
1. Accept features with v3 naming (`{timeframe}_{fuzzy_set_id}_{membership}`)
2. Pass through to model without modification (naming is already correct)
3. Ensure feature count matches model input size

```python
class FuzzyNeuralProcessor:
    def __init__(
        self,
        config: StrategyConfigurationV3,
        resolved_features: list[str]
    ):
        """
        Args:
            config: V3 strategy configuration
            resolved_features: Ordered list of feature IDs from FeatureResolver
        """
        self.config = config
        self.resolved_features = resolved_features
        self.n_features = len(resolved_features)

    def validate_features(self, features: pd.DataFrame) -> None:
        """Validate feature DataFrame has correct columns."""
        missing = set(self.resolved_features) - set(features.columns)
        if missing:
            raise ValueError(f"Missing features: {missing}")

        extra = set(features.columns) - set(self.resolved_features)
        if extra:
            logger.warning(f"Extra columns will be ignored: {extra}")
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/training/test_fuzzy_neural_processor_v3.py`
- [ ] Processor accepts v3 config and feature list
- [ ] Validates feature columns correctly
- [ ] Warns on extra columns
- [ ] Errors on missing columns

**Acceptance Criteria:**
- [ ] Works with v3 feature naming
- [ ] Unit tests pass

---

### Task 4.3: Create ModelMetadataV3

**File(s):** `ktrdr/models/model_metadata.py`
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Persistence, Configuration

**Description:**
Create `ModelMetadataV3` dataclass to store v3-specific model information, including the critical `resolved_features` list.

**Implementation Notes:**

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class ModelMetadataV3:
    """Metadata for v3-trained models."""

    # Identity
    model_name: str
    strategy_name: str
    created_at: datetime = field(default_factory=datetime.now)

    # Version info
    strategy_version: str = "3.0"

    # V3-specific: full config for reproducibility
    indicators: dict[str, dict[str, Any]] = field(default_factory=dict)
    fuzzy_sets: dict[str, dict[str, Any]] = field(default_factory=dict)
    nn_inputs: list[dict[str, Any]] = field(default_factory=list)

    # CRITICAL: ordered feature list (source of truth for backtest)
    resolved_features: list[str] = field(default_factory=list)

    # Training context
    training_symbols: list[str] = field(default_factory=list)
    training_timeframes: list[str] = field(default_factory=list)
    training_metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        return {
            'model_name': self.model_name,
            'strategy_name': self.strategy_name,
            'created_at': self.created_at.isoformat(),
            'strategy_version': self.strategy_version,
            'indicators': self.indicators,
            'fuzzy_sets': self.fuzzy_sets,
            'nn_inputs': self.nn_inputs,
            'resolved_features': self.resolved_features,
            'training_symbols': self.training_symbols,
            'training_timeframes': self.training_timeframes,
            'training_metrics': self.training_metrics,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ModelMetadataV3':
        """Deserialize from dict."""
        return cls(
            model_name=data['model_name'],
            strategy_name=data['strategy_name'],
            created_at=datetime.fromisoformat(data['created_at']),
            strategy_version=data.get('strategy_version', '3.0'),
            indicators=data.get('indicators', {}),
            fuzzy_sets=data.get('fuzzy_sets', {}),
            nn_inputs=data.get('nn_inputs', []),
            resolved_features=data.get('resolved_features', []),
            training_symbols=data.get('training_symbols', []),
            training_timeframes=data.get('training_timeframes', []),
            training_metrics=data.get('training_metrics', {}),
        )
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/models/test_model_metadata_v3.py`
- [ ] Serialization round-trip works
- [ ] All fields preserved
- [ ] Datetime handling correct
- [ ] Default values work

*Smoke Test:*
```bash
uv run python -c "
from ktrdr.models.model_metadata import ModelMetadataV3
meta = ModelMetadataV3(
    model_name='test',
    strategy_name='test_strategy',
    resolved_features=['5m_rsi_fast_oversold', '5m_rsi_fast_overbought']
)
d = meta.to_dict()
meta2 = ModelMetadataV3.from_dict(d)
assert meta2.resolved_features == meta.resolved_features
print('ModelMetadataV3: OK')
"
```

**Acceptance Criteria:**
- [ ] Matches ARCHITECTURE.md lines 548-571
- [ ] Serialization works for JSON storage
- [ ] Unit tests pass

---

### Task 4.4: Update Training Worker for V3

**File(s):** `ktrdr/training/training_worker.py`, `training-host-service/`
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Cross-Component, Wiring/DI

**Description:**
Update training worker to pass v3 config and save `ModelMetadataV3`.

**Implementation Notes:**

The worker should:
1. Receive v3 strategy config
2. Use `TrainingPipeline` with v3 config
3. After training, save `ModelMetadataV3` with resolved features

```python
async def train(self, config: StrategyConfigurationV3, ...):
    # Resolve features for metadata
    resolver = FeatureResolver()
    resolved = resolver.resolve(config)

    # Train using pipeline
    pipeline = TrainingPipeline(config)
    ...

    # Save metadata
    metadata = ModelMetadataV3(
        model_name=model_name,
        strategy_name=config.name,
        indicators={k: v.model_dump() for k, v in config.indicators.items()},
        fuzzy_sets={k: v.model_dump() for k, v in config.fuzzy_sets.items()},
        nn_inputs=[inp.model_dump() for inp in config.nn_inputs],
        resolved_features=[f.feature_id for f in resolved],
        training_symbols=config.training_data.symbols.list,
        training_timeframes=config.training_data.timeframes.list,
        training_metrics=metrics,
    )
    self._save_metadata(metadata)
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/training/test_training_worker_v3.py`
- [ ] Worker accepts v3 config
- [ ] Metadata saved with resolved_features
- [ ] All config fields preserved in metadata

*Integration Tests:*
- [ ] Training host service accepts v3 config

**Acceptance Criteria:**
- [ ] V3 config flows through worker
- [ ] Metadata saved correctly
- [ ] Unit tests pass

---

### Task 4.5: Add Training Dry-Run Mode

**File(s):** `ktrdr/cli/train_commands.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** API Endpoint

**Description:**
Add `--dry-run` flag to `ktrdr train` command to validate v3 config and show what would be computed without actually training.

**Implementation Notes:**

```python
@train.command()
@click.argument('strategy_path', type=click.Path(exists=True))
@click.option('--dry-run', is_flag=True, help='Validate config and show features without training')
def run(strategy_path: str, dry_run: bool):
    """Train a model from a v3 strategy."""
    loader = StrategyConfigurationLoader()
    config = loader.load(Path(strategy_path))

    resolver = FeatureResolver()
    resolved = resolver.resolve(config)

    if dry_run:
        click.echo(f"Strategy: {config.name}")
        click.echo(f"Version: {config.version}")
        click.echo(f"\nIndicators ({len(config.indicators)}):")
        for ind_id, ind_def in config.indicators.items():
            click.echo(f"  {ind_id}: {ind_def.type}")

        click.echo(f"\nFuzzy Sets ({len(config.fuzzy_sets)}):")
        for fs_id, fs_def in config.fuzzy_sets.items():
            click.echo(f"  {fs_id} -> {fs_def.indicator}")

        click.echo(f"\nNN Inputs ({len(resolved)} features):")
        for f in resolved:
            click.echo(f"  {f.feature_id}")

        click.echo("\n[Dry run - no training performed]")
        return

    # Actual training...
```

**Testing Requirements:**

*Smoke Test:*
```bash
ktrdr train strategies/v3_test_example.yaml --dry-run
```

**Acceptance Criteria:**
- [ ] `--dry-run` shows config summary without training
- [ ] Feature list displayed
- [ ] Useful for debugging strategy config

---

## E2E Test Scenario

**Purpose:** Prove full training pipeline works with v3 config
**Duration:** ~30 seconds (dry-run) or ~5 minutes (full train with minimal epochs)
**Prerequisites:** M3 complete, test data available

### Test Steps

```bash
#!/bin/bash
# M4 E2E Test: Training Pipeline V3

set -e

echo "=== M4 E2E Test: Training Pipeline V3 ==="

# Test 1: Dry-run validation
echo "Test 1: Training dry-run..."
ktrdr train strategies/v3_test_example.yaml --dry-run

# Verify output contains expected elements
OUTPUT=$(ktrdr train strategies/v3_test_example.yaml --dry-run 2>&1)
echo "$OUTPUT" | grep -q "rsi_14" || { echo "FAIL: Missing indicator"; exit 1; }
echo "$OUTPUT" | grep -q "rsi_fast" || { echo "FAIL: Missing fuzzy set"; exit 1; }
echo "$OUTPUT" | grep -q "5m_rsi_fast_oversold" || { echo "FAIL: Missing feature"; exit 1; }
echo "Test 1: PASS"

# Test 2: Full training (minimal epochs)
echo "Test 2: Full training (1 epoch)..."
ktrdr train strategies/v3_test_example.yaml --epochs 1 --output /tmp/m4_test_model

# Test 3: Verify metadata
echo "Test 3: Verify model metadata..."
uv run python << 'EOF'
import json
from pathlib import Path

metadata_path = Path('/tmp/m4_test_model/metadata.json')
if not metadata_path.exists():
    print("FAIL: metadata.json not found")
    exit(1)

with open(metadata_path) as f:
    meta = json.load(f)

assert meta['strategy_version'] == '3.0', "Wrong strategy version"
assert 'resolved_features' in meta, "Missing resolved_features"
assert len(meta['resolved_features']) > 0, "Empty resolved_features"
assert '5m_rsi_fast_oversold' in meta['resolved_features'], "Missing expected feature"

print(f"Metadata valid: {len(meta['resolved_features'])} features")
print("Test 3: PASS")
EOF

# Cleanup
rm -rf /tmp/m4_test_model

echo ""
echo "=== M4 E2E Test: ALL PASSED ==="
```

### Success Criteria

- [ ] Dry-run shows config summary and features
- [ ] Full training completes without error
- [ ] `metadata.json` contains `strategy_version: "3.0"`
- [ ] `resolved_features` list present and correct
- [ ] Feature order matches FeatureResolver output

---

## Completion Checklist

- [ ] Task 4.1: TrainingPipeline updated for v3
- [ ] Task 4.2: FuzzyNeuralProcessor updated
- [ ] Task 4.3: ModelMetadataV3 created
- [ ] Task 4.4: Training worker updated
- [ ] Task 4.5: Dry-run mode added
- [ ] All unit tests pass: `make test-unit`
- [ ] E2E test script passes
- [ ] M1, M2, M3 E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] Code reviewed and merged
