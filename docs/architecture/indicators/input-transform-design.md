# Design: Input Transform in Fuzzy Configuration

**Status**: Architectural Decision
**Date**: 2025-10-13
**Replaces**: Phase 3.5 (Distance Ratio Indicator Types) in implementation plan

---

## Problem Statement

Moving averages (SMA/EMA) produce **unbounded absolute values** (e.g., 150.25, 3250.80) that are difficult to fuzzify because fuzzy membership functions work best with **normalized bounded values**.

**Current Solution** (in training pipeline):
```python
# Training pipeline transforms SMA/EMA to price ratios
if indicator_type in ["SMA", "EMA"]:
    mapped_results[name] = price_data["close"] / indicator_results[col]
```

**Problem**: This is **training-specific** logic that won't be available in backtesting or live trading.

---

## Architectural Decision: Input Transform in Fuzzy Configuration

### Rationale

The transformation is not about:
- **Indicator computation** (indicator computes MA correctly)
- **Training pipeline** (reusability issue)

The transformation is about:
- **How to fuzzify** a moving average
- **Preparing input** for fuzzy membership calculation
- **Property of the fuzzy system** (not indicator or training)

### Location in Architecture

**Fuzzy Configuration** is the correct place because:

1. **Already per-indicator**: Fuzzy config is organized by indicator/feature
2. **Fuzzification preparation**: Transform happens before membership calculation
3. **Reusable**: Same config used in training, backtesting, live trading
4. **Explicit**: User sees transformation in strategy configuration
5. **Extensible**: Can support other transforms (log scale, z-score, etc.)

---

## Configuration Schema

### New Field in Fuzzy Sets: `input_transform`

```yaml
fuzzy_sets:
  <feature_id>:
    input_transform:  # NEW: Optional transformation before fuzzification
      type: <transform_type>
      <transform_parameters>

    <fuzzy_set_name>:
      type: <membership_function_type>
      parameters: [...]
```

### Supported Transforms

#### 1. Price Ratio Transform

**Purpose**: Normalize MA to price ratio for fuzzification

**Configuration**:
```yaml
input_transform:
  type: "price_ratio"
  reference: "close"  # Numerator (price column)
  # Computes: reference_value / indicator_value
```

**Example**:
```yaml
indicators:
  - type: "sma"
    feature_id: "sma_20"
    period: 20

fuzzy_sets:
  sma_20:
    input_transform:
      type: "price_ratio"
      reference: "close"

    # Fuzzy sets work on ratio (normalized around 1.0)
    below:
      type: "triangular"
      parameters: [0.93, 0.97, 1.00]  # 7-3% below MA
    at_ma:
      type: "triangular"
      parameters: [0.98, 1.00, 1.02]  # ±2% of MA
    above:
      type: "triangular"
      parameters: [1.00, 1.03, 1.07]  # 3-7% above MA
```

**Data Flow**:
1. Indicator computes SMA: `150.25`
2. Price: `155.00`
3. Transform: `155.00 / 150.25 = 1.032`
4. Fuzzify ratio: `1.032` → membership degrees

#### 2. Identity Transform (Default)

**Purpose**: No transformation (use indicator value as-is)

**Configuration**: Omit `input_transform` field

**Example**:
```yaml
fuzzy_sets:
  rsi_14:
    # No input_transform = identity (use raw RSI value)
    oversold:
      type: "triangular"
      parameters: [0, 20, 40]  # Raw RSI values
```

#### 3. Future: Z-Score Transform

**Purpose**: Standardize to mean=0, std=1

```yaml
input_transform:
  type: "z_score"
  window: 50  # Lookback period for mean/std
```

#### 4. Future: Log Scale Transform

**Purpose**: Logarithmic scaling for exponential data

```yaml
input_transform:
  type: "log_scale"
  base: 10  # or "e" for natural log
```

---

## Implementation

### Phase 1: Update Fuzzy Config Model

**File**: `ktrdr/fuzzy/config.py`

**Add Transform Configuration**:
```python
class PriceRatioTransformConfig(BaseModel):
    """Price ratio transform: reference / indicator_value"""
    type: Literal["price_ratio"] = "price_ratio"
    reference: str = Field(..., description="Price column to use as numerator")

    @field_validator('reference')
    @classmethod
    def validate_reference(cls, v: str) -> str:
        valid = ['open', 'high', 'low', 'close']
        if v not in valid:
            raise ValueError(f"reference must be one of {valid}, got: {v}")
        return v


class IdentityTransformConfig(BaseModel):
    """Identity transform: no transformation"""
    type: Literal["identity"] = "identity"


# Union of all transform types
InputTransformConfig = Annotated[
    Union[PriceRatioTransformConfig, IdentityTransformConfig],
    Field(discriminator="type")
]


class FuzzySetConfigModel(RootModel[dict[str, MembershipFunctionConfig]]):
    """Fuzzy set configuration WITH input transform"""

    # Add optional input_transform field
    input_transform: Optional[InputTransformConfig] = None

    # Membership functions (existing)
    root: dict[str, MembershipFunctionConfig]
```

### Phase 2: Update Fuzzy Engine

**File**: `ktrdr/fuzzy/engine.py`

**Add Transform Logic**:
```python
class FuzzyEngine:
    def fuzzify(
        self,
        indicator: str,
        values: Union[float, pd.Series, np.ndarray],
        context_data: Optional[pd.DataFrame] = None  # NEW: For price_ratio transform
    ) -> Union[dict, pd.DataFrame]:
        """Fuzzify indicator values with optional input transform."""

        # Get fuzzy set config for this indicator
        fuzzy_set_config = self._config.root[indicator]

        # Apply input transform if configured
        if hasattr(fuzzy_set_config, 'input_transform') and fuzzy_set_config.input_transform:
            values = self._apply_input_transform(
                fuzzy_set_config.input_transform,
                values,
                context_data
            )

        # Fuzzify transformed values (existing logic)
        return self._fuzzify_values(indicator, values)

    def _apply_input_transform(
        self,
        transform_config: InputTransformConfig,
        indicator_values: Union[float, pd.Series, np.ndarray],
        context_data: Optional[pd.DataFrame]
    ) -> Union[float, pd.Series, np.ndarray]:
        """Apply configured input transformation."""

        if transform_config.type == "identity":
            return indicator_values

        elif transform_config.type == "price_ratio":
            if context_data is None:
                raise ProcessingError(
                    "price_ratio transform requires context_data with price columns",
                    error_code="FUZZY-MissingContextData"
                )

            reference = transform_config.reference
            if reference not in context_data.columns:
                raise ProcessingError(
                    f"Reference column '{reference}' not found in context data",
                    error_code="FUZZY-InvalidReference",
                    details={
                        "reference": reference,
                        "available": list(context_data.columns)
                    }
                )

            reference_values = context_data[reference]

            # Compute ratio: reference / indicator
            if isinstance(indicator_values, pd.Series):
                ratio = reference_values / indicator_values
            else:
                # Scalar or array
                ratio = reference_values.iloc[-1] / indicator_values

            return ratio

        else:
            raise ConfigurationError(
                f"Unknown transform type: {transform_config.type}",
                error_code="FUZZY-UnknownTransform"
            )
```

### Phase 3: Update Training Pipeline

**File**: `ktrdr/training/training_pipeline.py`

**Remove transformation logic**, pass context data to fuzzy engine:

```python
# OLD: Training pipeline transforms
if indicator_type in ["SMA", "EMA"]:
    mapped_results[name] = price_data["close"] / indicator_results[col]

# NEW: Let fuzzy engine handle it
fuzzy_engine.fuzzify(
    feature_id,
    indicator_values,
    context_data=combined_data  # Includes price columns
)
```

### Phase 4: Update Migration Tool

**File**: `scripts/migrate_to_feature_ids.py`

**Detect SMA/EMA and add input_transform**:

```python
def migrate_strategy(strategy: dict) -> dict:
    """Migrate strategy to feature_ids with input_transforms."""

    # Migrate indicators (existing logic)
    for ind in strategy['indicators']:
        # Add feature_id...
        pass

    # Add input_transforms for SMA/EMA
    for ind in strategy['indicators']:
        if ind['type'] in ['sma', 'ema']:
            feature_id = ind['feature_id']

            # Add input_transform to corresponding fuzzy_sets
            if feature_id in strategy['fuzzy_sets']:
                strategy['fuzzy_sets'][feature_id]['input_transform'] = {
                    'type': 'price_ratio',
                    'reference': 'close'
                }

    return strategy
```

---

## Impact Analysis

### Code Changes

| Component | Change | Lines |
|-----------|--------|-------|
| `fuzzy/config.py` | Add transform models | +50 |
| `fuzzy/engine.py` | Add transform logic | +60 |
| `training/training_pipeline.py` | Remove transform logic | -30 |
| `scripts/migrate_to_feature_ids.py` | Add transform detection | +20 |
| **Net Change** | | **+100 lines** |

### Benefits

1. **Proper Architecture**: Transformation in correct layer (fuzzy, not training)
2. **Reusable**: Same logic in training, backtesting, live trading
3. **Explicit**: User sees transformation in configuration
4. **Extensible**: Easy to add new transform types
5. **Maintainable**: No special cases in training pipeline

### Migration Impact

**Automatic**: Migration tool detects SMA/EMA and adds `input_transform`

**Example Migration**:
```yaml
# BEFORE
indicators:
  - name: "sma"
    period: 20

fuzzy_sets:
  sma_20:  # Uses transformed values (implicit)
    below: [0.93, 0.97, 1.00]

# AFTER (automatic)
indicators:
  - type: "sma"
    feature_id: "sma_20"
    period: 20

fuzzy_sets:
  sma_20:
    input_transform:  # ADDED by migration tool
      type: "price_ratio"
      reference: "close"
    below: {type: "triangular", parameters: [0.93, 0.97, 1.00]}
```

---

## Testing Strategy

### Unit Tests

**File**: `tests/unit/fuzzy/test_input_transforms.py`

1. Test PriceRatioTransform configuration validation
2. Test transform application (scalar, Series, array)
3. Test missing context data error
4. Test invalid reference column error
5. Test identity transform (no-op)

### Integration Tests

**File**: `tests/integration/fuzzy/test_transform_integration.py`

1. Test SMA with price_ratio transform in full pipeline
2. Test EMA with price_ratio transform in full pipeline
3. Test indicator without transform (RSI, MACD)
4. Test mixed indicators (some with, some without transforms)

### Migration Tests

**File**: `tests/unit/scripts/test_migration_transforms.py`

1. Test SMA detected and transform added
2. Test EMA detected and transform added
3. Test non-MA indicator unchanged
4. Test already-migrated strategy unchanged

---

## Timeline

**Phase 1** (Config Model): 0.5 days
**Phase 2** (Fuzzy Engine): 1 day
**Phase 3** (Training Pipeline): 0.5 days
**Phase 4** (Migration Tool): 0.5 days
**Testing**: 1 day

**Total**: 3.5 days

---

## Comparison: Input Transform vs Distance Ratio Indicators

| Aspect | Distance Ratio Indicators (rejected) | Input Transform (chosen) |
|--------|-------------------------------------|--------------------------|
| **Location** | Indicator layer | Fuzzy layer |
| **Reusability** | Need separate indicator types | Single transform config |
| **User Impact** | Must choose correct indicator type | Transparent, automatic |
| **Maintenance** | More indicator types to maintain | One transform system |
| **Extensibility** | New indicator per transform | Add transform types easily |
| **Architecture** | Mixes concerns | Clean separation |

---

## Success Criteria

- [ ] Input transform configuration validates correctly
- [ ] Price ratio transform computes correctly
- [ ] Fuzzy engine applies transforms before fuzzification
- [ ] Training pipeline removes transform logic (simpler)
- [ ] Migration tool adds transforms for SMA/EMA automatically
- [ ] All tests pass (unit, integration, migration)
- [ ] Documentation updated with transform examples
- [ ] No regression in training outputs (equivalent results)

---

**END OF INPUT TRANSFORM DESIGN**
