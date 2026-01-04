---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 5: Backtest Pipeline V3

**Branch:** `feature/strategy-grammar-v3-m5`
**Prerequisite:** M4 complete (training produces v3 models)
**Builds on:** M4 Training Pipeline

## Goal

Backtest pipeline generates features that exactly match training — same feature names AND same order. Feature alignment is validated against model metadata.

## Why This Milestone

- Critical for correct model inference (wrong order = garbage predictions)
- Uses same `FeatureResolver` as training for consistency
- Validates against `ModelMetadataV3.resolved_features`

---

## Tasks

### Task 5.1: Update FeatureCache for V3

**File(s):** `ktrdr/backtesting/feature_cache.py`
**Type:** CODING
**Estimated time:** 3 hours

**Task Categories:** Cross-Component, Wiring/DI

**Description:**
Modify `FeatureCache` to use v3 engines and validate features against model metadata.

**Implementation Notes:**

Critical: FeatureCache MUST produce features in the exact same order as training. This is validated by comparing against `ModelMetadataV3.resolved_features`.

```python
class FeatureCache:
    def __init__(
        self,
        config: StrategyConfigurationV3,
        model_metadata: ModelMetadataV3
    ):
        self.config = config
        self.metadata = model_metadata
        self.feature_resolver = FeatureResolver()
        self.indicator_engine = IndicatorEngine(config.indicators)
        self.fuzzy_engine = FuzzyEngine(config.fuzzy_sets)

        # Expected features from model (ORDERED list)
        self.expected_features = model_metadata.resolved_features

    def compute_features(
        self,
        data: dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """
        Compute features for backtesting.

        CRITICAL: Must produce same feature_ids AND same order as training.

        Args:
            data: {timeframe: DataFrame} for single symbol

        Returns:
            Feature DataFrame with columns in expected order
        """
        # Resolve what we need
        resolved = self.feature_resolver.resolve(self.config)

        # Group by timeframe
        tf_requirements = self._group_requirements_by_timeframe(resolved)

        feature_dfs = []
        for timeframe, df in data.items():
            if timeframe not in tf_requirements:
                continue

            reqs = tf_requirements[timeframe]

            # Compute indicators
            indicator_df = self.indicator_engine.compute_for_timeframe(
                df, timeframe, reqs['indicators']
            )

            # Apply fuzzy sets
            for fuzzy_set_id in reqs['fuzzy_sets']:
                indicator_id = self.fuzzy_engine.get_indicator_for_fuzzy_set(
                    fuzzy_set_id
                )
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
                feature_dfs.append(fuzzy_df)

        result = pd.concat(feature_dfs, axis=1)

        # CRITICAL: Validate and reorder
        self._validate_features(result)
        result = result[self.expected_features]

        return result

    def _validate_features(self, result: pd.DataFrame) -> None:
        """Validate features match expected from model metadata."""
        produced = set(result.columns)
        expected = set(self.expected_features)

        missing = expected - produced
        if missing:
            raise ValueError(
                f"Feature mismatch: missing {len(missing)} features.\n"
                f"Missing: {sorted(missing)[:5]}{'...' if len(missing) > 5 else ''}\n"
                f"This usually means the strategy config doesn't match the trained model."
            )

        extra = produced - expected
        if extra:
            logger.warning(
                f"Extra features will be ignored: {sorted(extra)[:5]}"
                f"{'...' if len(extra) > 5 else ''}"
            )
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/backtesting/test_feature_cache_v3.py`
- [ ] FeatureCache accepts v3 config and metadata
- [ ] Features computed correctly
- [ ] Missing features raise clear error
- [ ] Extra features produce warning
- [ ] Column order matches expected_features exactly

*Integration Tests:*
- [ ] FeatureCache produces same features as TrainingPipeline

*Smoke Test:*
```bash
uv run python -c "
from ktrdr.config.strategy_loader import StrategyConfigurationLoader
from ktrdr.models.model_metadata import ModelMetadataV3
from ktrdr.backtesting.feature_cache import FeatureCache
from pathlib import Path

loader = StrategyConfigurationLoader()
config = loader.load(Path('strategies/v3_test_example.yaml'))

# Mock metadata
meta = ModelMetadataV3(
    model_name='test',
    strategy_name='test',
    resolved_features=['5m_rsi_fast_oversold', '5m_rsi_fast_overbought']
)

cache = FeatureCache(config, meta)
print('FeatureCache v3 init: OK')
"
```

**Acceptance Criteria:**
- [ ] Matches ARCHITECTURE.md lines 502-539
- [ ] Validation catches mismatches with clear errors
- [ ] Order is explicitly validated and enforced
- [ ] Unit tests pass

---

### Task 5.2: Update BacktestingService for V3

**File(s):** `ktrdr/backtesting/backtesting_service.py`
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Cross-Component

**Description:**
Update `BacktestingService` to load v3 models and use v3 feature cache.

**Implementation Notes:**

```python
class BacktestingService:
    async def run_backtest(
        self,
        model_path: Path,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> BacktestResult:
        # Load model metadata
        metadata = self._load_metadata(model_path)

        if metadata.strategy_version != '3.0':
            raise ValueError(
                f"Model uses strategy version {metadata.strategy_version}, "
                f"expected 3.0. This model may need to be retrained."
            )

        # Reconstruct config from metadata
        config = self._reconstruct_config(metadata)

        # Create feature cache
        cache = FeatureCache(config, metadata)

        # Load data
        data = await self._load_data(symbol, start_date, end_date)

        # Compute features
        features = cache.compute_features(data)

        # Run inference
        ...

    def _load_metadata(self, model_path: Path) -> ModelMetadataV3:
        """Load and validate model metadata."""
        metadata_path = model_path / 'metadata.json'
        with open(metadata_path) as f:
            data = json.load(f)
        return ModelMetadataV3.from_dict(data)

    def _reconstruct_config(
        self,
        metadata: ModelMetadataV3
    ) -> StrategyConfigurationV3:
        """Reconstruct strategy config from metadata."""
        # Metadata stores the full config for reproducibility
        ...
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/backtesting/test_backtesting_service_v3.py`
- [ ] Service loads v3 metadata correctly
- [ ] Non-v3 models rejected with clear error
- [ ] Config reconstructed from metadata
- [ ] FeatureCache used with correct config

*Integration Tests:*
- [ ] Full backtest flow with v3 model

**Acceptance Criteria:**
- [ ] V3 models loaded correctly
- [ ] Non-v3 models rejected
- [ ] Unit tests pass

---

### Task 5.3: Add Feature Order Validation

**File(s):** `ktrdr/backtesting/feature_cache.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Cross-Component

**Description:**
Add explicit validation that feature order matches between computed and expected.

**Implementation Notes:**

This is a safety check beyond just column names — it verifies the ORDER is identical.

```python
def _validate_feature_order(self, result: pd.DataFrame) -> None:
    """
    Validate feature order matches expected EXACTLY.

    This is critical because neural networks are not invariant to
    input order — the same features in different order will produce
    garbage predictions.
    """
    computed_order = list(result.columns)
    expected_order = self.expected_features

    if computed_order != expected_order:
        # Find first mismatch
        for i, (computed, expected) in enumerate(
            zip(computed_order, expected_order)
        ):
            if computed != expected:
                raise ValueError(
                    f"Feature order mismatch at position {i}:\n"
                    f"  Expected: {expected}\n"
                    f"  Got: {computed}\n"
                    f"This is a bug in feature generation. "
                    f"Please report this issue."
                )

        # Length mismatch
        raise ValueError(
            f"Feature count mismatch: "
            f"expected {len(expected_order)}, got {len(computed_order)}"
        )
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/backtesting/test_feature_cache_v3.py`
- [ ] Order validation catches reordered features
- [ ] Error message shows first mismatch
- [ ] Length mismatch caught

**Acceptance Criteria:**
- [ ] Order validation is explicit
- [ ] Error messages are helpful for debugging
- [ ] Unit tests pass

---

### Task 5.4: Integration Test: Training → Backtest Consistency

**File(s):** `tests/integration/test_training_backtest_consistency.py` (NEW)
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Cross-Component

**Description:**
Create integration test that verifies features produced by backtest exactly match training.

**Implementation Notes:**

```python
def test_backtest_features_match_training():
    """
    Critical test: Backtest must produce identical features to training.

    This test:
    1. Creates a v3 strategy
    2. Generates features via TrainingPipeline
    3. Generates features via FeatureCache (simulating backtest)
    4. Verifies they are IDENTICAL (names, order, values)
    """
    config = load_test_v3_strategy()
    data = load_test_data()

    # Training path
    training_pipeline = TrainingPipeline(config)
    training_features = training_pipeline.prepare_features(data)

    # Backtest path (with mock metadata)
    resolver = FeatureResolver()
    resolved = resolver.resolve(config)
    metadata = ModelMetadataV3(
        model_name='test',
        strategy_name=config.name,
        resolved_features=[f.feature_id for f in resolved],
    )

    cache = FeatureCache(config, metadata)
    backtest_features = cache.compute_features(data['EURUSD'])

    # Verify names match
    assert list(training_features.columns) == list(backtest_features.columns), \
        "Column names don't match"

    # Verify order matches
    assert list(training_features.columns) == metadata.resolved_features, \
        "Training columns don't match resolved order"

    # Verify values match (within floating point tolerance)
    pd.testing.assert_frame_equal(
        training_features,
        backtest_features,
        check_exact=False,
        rtol=1e-5
    )
```

**Testing Requirements:**

This IS the test — it validates the critical training/backtest consistency.

**Acceptance Criteria:**
- [ ] Test covers feature name matching
- [ ] Test covers feature order matching
- [ ] Test covers value matching
- [ ] Test passes

---

## E2E Test Scenario

**Purpose:** Prove backtest produces features matching training
**Duration:** ~30 seconds
**Prerequisites:** M4 complete, trained model exists

### Test Steps

```bash
#!/bin/bash
# M5 E2E Test: Backtest Pipeline V3

set -e

echo "=== M5 E2E Test: Backtest Pipeline V3 ==="

# Prerequisite: Train a model (or use existing)
if [ ! -d "/tmp/m5_test_model" ]; then
    echo "Training test model..."
    ktrdr train strategies/v3_test_example.yaml --epochs 1 --output /tmp/m5_test_model
fi

# Test 1: Run backtest
echo "Test 1: Running backtest..."
ktrdr backtest /tmp/m5_test_model --symbol EURUSD --start 2024-01-01 --end 2024-01-31

# Test 2: Verify feature alignment
echo "Test 2: Verifying feature alignment..."
uv run python << 'EOF'
import json
from pathlib import Path
from ktrdr.config.strategy_loader import StrategyConfigurationLoader
from ktrdr.config.feature_resolver import FeatureResolver
from ktrdr.models.model_metadata import ModelMetadataV3

# Load metadata
with open('/tmp/m5_test_model/metadata.json') as f:
    meta_dict = json.load(f)
metadata = ModelMetadataV3.from_dict(meta_dict)

# Reconstruct config and resolve features
# (This simulates what backtest does)
from ktrdr.config.models import StrategyConfigurationV3

# The metadata should store enough to reconstruct the config
assert len(metadata.resolved_features) > 0, "No resolved features in metadata"
print(f"Model has {len(metadata.resolved_features)} features")

# Verify first few features match expected pattern
expected_patterns = ['5m_', '1h_', '1d_']
for feature in metadata.resolved_features[:3]:
    has_tf = any(feature.startswith(p) for p in expected_patterns)
    assert has_tf, f"Feature {feature} missing timeframe prefix"

print("Feature format validation: PASS")
print("Test 2: PASS")
EOF

# Test 3: Test feature mismatch detection
echo "Test 3: Feature mismatch detection..."
uv run python << 'EOF'
from ktrdr.backtesting.feature_cache import FeatureCache
from ktrdr.config.strategy_loader import StrategyConfigurationLoader
from ktrdr.models.model_metadata import ModelMetadataV3
from pathlib import Path

# Load real config
loader = StrategyConfigurationLoader()
config = loader.load(Path('strategies/v3_test_example.yaml'))

# Create metadata with WRONG features
bad_metadata = ModelMetadataV3(
    model_name='test',
    strategy_name='test',
    resolved_features=['nonexistent_feature_1', 'nonexistent_feature_2'],
)

cache = FeatureCache(config, bad_metadata)

# This should fail when we try to compute features
import pandas as pd
import numpy as np

test_data = {
    '5m': pd.DataFrame({
        'open': [100]*50, 'high': [101]*50, 'low': [99]*50,
        'close': [100]*50, 'volume': [1000]*50
    })
}

try:
    cache.compute_features(test_data)
    print("FAIL: Should have raised error for mismatched features")
    exit(1)
except ValueError as e:
    if "missing" in str(e).lower() or "mismatch" in str(e).lower():
        print("Feature mismatch correctly detected")
        print("Test 3: PASS")
    else:
        print(f"FAIL: Unexpected error: {e}")
        exit(1)
EOF

# Cleanup
rm -rf /tmp/m5_test_model

echo ""
echo "=== M5 E2E Test: ALL PASSED ==="
```

### Success Criteria

- [ ] Backtest runs without feature errors
- [ ] Feature format matches training (timeframe prefix, naming)
- [ ] Mismatched features detected with clear error
- [ ] No NaN values in computed features

---

## Completion Checklist

- [ ] Task 5.1: FeatureCache updated for v3
- [ ] Task 5.2: BacktestingService updated
- [ ] Task 5.3: Feature order validation added
- [ ] Task 5.4: Integration test created
- [ ] All unit tests pass: `make test-unit`
- [ ] Integration test passes
- [ ] E2E test script passes
- [ ] M1-M4 E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] Code reviewed and merged
