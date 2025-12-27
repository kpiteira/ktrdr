# v1.5: Architecture

> **Superseded:** This architecture has been replaced by a lean experiment-focused approach.
> Instead of building new modules (TrainingDiagnostics, IndicatorReference), we use
> existing TrainingAnalyzer and run controlled experiments manually.
> See [PLAN.md](PLAN.md) for the actual implementation.

---

## Overview

v1.5 adds two capabilities to the MVP agent system:

1. **Indicator Constraints**: Agent is restricted to bounded indicators with provided fuzzy set references
2. **Failure Diagnostics**: Training results include structured analysis explaining why strategies succeed or fail

These are surgical additions to the existing architecture, not a redesign.

---

## Component Changes

### Component 1: Indicator Reference (NEW)

**Responsibility:** Provide agent with correct fuzzy set ranges for bounded indicators

**Location:** `ktrdr/agents/references/indicator_reference.py`

**Interface:**
```python
@dataclass
class IndicatorReference:
    name: str                    # e.g., "RSI"
    range_min: float            # e.g., 0
    range_max: float            # e.g., 100
    typical_fuzzy_sets: dict    # e.g., {"oversold": [0,30,40], ...}
    description: str            # What this indicator measures

BOUNDED_INDICATORS: dict[str, IndicatorReference] = {
    "RSI": IndicatorReference(
        name="RSI", range_min=0, range_max=100,
        typical_fuzzy_sets={"oversold": [0,30,40], "neutral": [35,50,65], "overbought": [60,70,100]},
        description="Momentum oscillator (0-100)"
    ),
    "Stochastic": IndicatorReference(
        name="Stochastic", range_min=0, range_max=100,
        typical_fuzzy_sets={"oversold": [0,20,30], "neutral": [25,50,75], "overbought": [70,80,100]},
        description="Momentum oscillator comparing close to high-low range (0-100)"
    ),
    "WilliamsR": IndicatorReference(
        name="WilliamsR", range_min=-100, range_max=0,
        typical_fuzzy_sets={"oversold": [-100,-80,-60], "neutral": [-65,-50,-35], "overbought": [-40,-20,0]},
        description="Momentum oscillator (-100 to 0)"
    ),
    "MFI": IndicatorReference(
        name="MFI", range_min=0, range_max=100,
        typical_fuzzy_sets={"oversold": [0,30,40], "neutral": [35,50,65], "overbought": [60,70,100]},
        description="Volume-weighted RSI (0-100)"
    ),
    "ADX": IndicatorReference(
        name="ADX", range_min=0, range_max=100,
        typical_fuzzy_sets={"weak": [0,15,25], "moderate": [20,35,50], "strong": [45,60,100]},
        description="Trend strength (0-100, not direction)"
    ),
    "DI_Plus": IndicatorReference(
        name="+DI", range_min=0, range_max=100,
        typical_fuzzy_sets={"weak": [0,15,25], "moderate": [20,35,50], "strong": [45,60,100]},
        description="Positive directional indicator (0-100)"
    ),
    "DI_Minus": IndicatorReference(
        name="-DI", range_min=0, range_max=100,
        typical_fuzzy_sets={"weak": [0,15,25], "moderate": [20,35,50], "strong": [45,60,100]},
        description="Negative directional indicator (0-100)"
    ),
    "AroonUp": IndicatorReference(
        name="AroonUp", range_min=0, range_max=100,
        typical_fuzzy_sets={"weak": [0,25,40], "moderate": [35,50,65], "strong": [60,75,100]},
        description="Time since highest high (0-100)"
    ),
    "AroonDown": IndicatorReference(
        name="AroonDown", range_min=0, range_max=100,
        typical_fuzzy_sets={"weak": [0,25,40], "moderate": [35,50,65], "strong": [60,75,100]},
        description="Time since lowest low (0-100)"
    ),
    "CMF": IndicatorReference(
        name="CMF", range_min=-1, range_max=1,
        typical_fuzzy_sets={"selling": [-1,-0.3,-0.05], "neutral": [-0.1,0,0.1], "buying": [0.05,0.3,1]},
        description="Chaikin Money Flow (-1 to 1)"
    ),
    "RVI": IndicatorReference(
        name="RVI", range_min=0, range_max=100,
        typical_fuzzy_sets={"low": [0,20,40], "neutral": [30,50,70], "high": [60,80,100]},
        description="Relative Vigor Index (0-100)"
    ),
}

def get_indicator_reference(name: str) -> IndicatorReference | None:
    """Get reference for an indicator, None if not bounded/supported."""

def get_allowed_indicators() -> list[str]:
    """Get list of indicators the agent can use."""

def validate_fuzzy_sets(indicator: str, fuzzy_sets: dict) -> list[str]:
    """Return list of warnings if fuzzy sets seem incorrect for indicator range."""
```

### Component 2: Agent Context Enhancement (MODIFY)

**Responsibility:** Include indicator reference in agent prompt

**Location:** `ktrdr/agents/research_agent.py` (or equivalent)

**Changes:**
```python
def build_agent_context(self) -> str:
    context = self._get_base_context()

    # NEW: Add indicator reference
    context += "\n\n## Available Indicators\n"
    context += "You may ONLY use these bounded indicators:\n\n"
    for name, ref in BOUNDED_INDICATORS.items():
        context += f"### {name}\n"
        context += f"- Range: [{ref.range_min}, {ref.range_max}]\n"
        context += f"- Typical fuzzy sets: {ref.typical_fuzzy_sets}\n"
        context += f"- Description: {ref.description}\n\n"

    context += "DO NOT use indicators not listed above (ATR, MACD, etc.)"

    return context
```

### Component 3: Training Diagnostics (NEW)

**Responsibility:** Analyze training results and classify failure modes

**Location:** `ktrdr/training/diagnostics.py`

**Interface:**
```python
@dataclass
class LossCurveAnalysis:
    classification: str  # "decreasing", "flat", "oscillating", "diverging"
    initial_loss: float
    final_loss: float
    improvement_pct: float
    plateau_epoch: int | None  # When improvement stopped

@dataclass
class PredictionAnalysis:
    distribution: dict[int, float]  # {0: 0.33, 1: 0.34, 2: 0.33}
    dominant_class: int | None      # None if balanced
    collapse_detected: bool         # True if >90% single class

@dataclass
class FeatureAnalysis:
    feature_variances: dict[str, float]   # Variance per feature
    zero_variance_features: list[str]     # Features with no signal
    label_correlations: dict[str, float]  # Correlation with labels

@dataclass
class TrainingDiagnostics:
    loss_curve: LossCurveAnalysis
    predictions: PredictionAnalysis
    features: FeatureAnalysis

    # Synthesized diagnosis
    likely_cause: str              # Human-readable explanation
    suggested_remediation: str     # What to try next
    learning_detected: bool        # True if accuracy > 40%

def analyze_training(
    training_history: dict,        # Loss curves, metrics
    predictions: np.ndarray,       # Model predictions on val set
    features: np.ndarray,          # Input features
    labels: np.ndarray             # Ground truth
) -> TrainingDiagnostics:
    """Comprehensive analysis of training results."""
```

**Diagnosis Logic:**
```python
def _synthesize_diagnosis(
    loss: LossCurveAnalysis,
    preds: PredictionAnalysis,
    feats: FeatureAnalysis
) -> tuple[str, str]:
    """Determine likely cause and remediation."""

    # Pattern 1: Flat loss + prediction collapse
    if loss.classification == "flat" and preds.collapse_detected:
        return (
            "Model collapsed to predicting single class. "
            "Likely cause: Features don't discriminate between classes.",
            "Try different indicators or wider fuzzy set ranges."
        )

    # Pattern 2: Flat loss + zero variance features
    if loss.classification == "flat" and feats.zero_variance_features:
        features = ", ".join(feats.zero_variance_features)
        return (
            f"Features have no variance: {features}. "
            "Fuzzy sets may not capture indicator variation.",
            "Adjust fuzzy set ranges to match actual indicator distribution."
        )

    # Pattern 3: Oscillating loss
    if loss.classification == "oscillating":
        return (
            "Loss oscillating - learning rate may be too high.",
            "Reduce learning rate or increase batch size."
        )

    # Pattern 4: Good loss, bad accuracy
    if loss.improvement_pct > 20 and not learning_detected:
        return (
            "Loss improved but accuracy stayed near random. "
            "Model may be fitting noise rather than signal.",
            "Try simpler architecture or more regularization."
        )

    # Pattern 5: Success
    if learning_detected:
        return (
            "Model learned predictive patterns from features.",
            "Consider further optimization or backtest evaluation."
        )

    # Default
    return (
        "No clear diagnosis - results are marginal.",
        "Try different indicator combination."
    )
```

### Component 4: Training Pipeline Integration (MODIFY)

**Responsibility:** Generate diagnostics after each training run

**Location:** `ktrdr/training/training_pipeline.py`

**Changes:**
```python
def train(self, ...) -> TrainingResult:
    # ... existing training code ...

    # NEW: Generate diagnostics
    from ktrdr.training.diagnostics import analyze_training

    diagnostics = analyze_training(
        training_history=history,
        predictions=model.predict(val_features),
        features=val_features,
        labels=val_labels
    )

    # Include in result
    result.diagnostics = diagnostics

    return result
```

### Component 5: Strategy Validator Enhancement (MODIFY)

**Responsibility:** Warn if strategy uses non-bounded indicators

**Location:** `ktrdr/config/strategy_validator.py`

**Changes:**
```python
def validate_indicators(self, config: dict) -> list[ValidationWarning]:
    warnings = []

    from ktrdr.agents.references.indicator_reference import (
        get_allowed_indicators,
        validate_fuzzy_sets
    )

    allowed = get_allowed_indicators()

    for indicator in config.get("indicators", []):
        name = indicator.get("name", "").upper()

        # Check if indicator is allowed
        if name not in allowed:
            warnings.append(ValidationWarning(
                level="ERROR",
                message=f"Indicator '{name}' is not in allowed list. "
                        f"Use one of: {', '.join(allowed)}",
                field=f"indicators.{name}"
            ))

        # Check fuzzy set ranges
        feature_id = indicator.get("feature_id")
        if feature_id and feature_id in config.get("fuzzy_sets", {}):
            fuzzy_warnings = validate_fuzzy_sets(
                name,
                config["fuzzy_sets"][feature_id]
            )
            warnings.extend(fuzzy_warnings)

    return warnings
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT STRATEGY DESIGN                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Agent Context includes:                                         │
│  - Indicator Reference (bounded indicators only)                │
│  - Fuzzy set range guidelines                                   │
│  - Previous experiment results (if any)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Strategy Validator:                                             │
│  - ERROR if non-bounded indicator used                          │
│  - WARNING if fuzzy sets outside expected range                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Training Pipeline:                                              │
│  - Standard training (unchanged)                                │
│  - NEW: Generate diagnostics after training                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Training Result includes:                                       │
│  - Standard metrics (loss, accuracy)                            │
│  - NEW: TrainingDiagnostics                                     │
│    - Loss curve analysis                                        │
│    - Prediction distribution                                    │
│    - Feature analysis                                           │
│    - Likely cause & remediation                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Agent Assessment:                                               │
│  - Receives full diagnostics                                    │
│  - Can reason about WHY training succeeded/failed               │
│  - Informs next strategy design                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## API Contracts

### Training Result Extension

```python
# Existing
@dataclass
class TrainingResult:
    success: bool
    model_path: str | None
    metrics: TrainingMetrics

# Extended
@dataclass
class TrainingResult:
    success: bool
    model_path: str | None
    metrics: TrainingMetrics
    diagnostics: TrainingDiagnostics | None  # NEW
```

### MCP Tool: Get Training Diagnostics

```python
@mcp_tool
def get_training_diagnostics(operation_id: str) -> dict:
    """
    Get detailed diagnostics for a training operation.

    Returns:
        {
            "loss_curve": {
                "classification": "flat",
                "initial_loss": 1.09,
                "final_loss": 1.08,
                "improvement_pct": 0.9
            },
            "predictions": {
                "distribution": {"0": 0.02, "1": 0.96, "2": 0.02},
                "collapse_detected": true,
                "dominant_class": 1
            },
            "features": {
                "zero_variance_features": ["adx_14_weak_trend"],
                "label_correlations": {"rsi_14_oversold": 0.03, ...}
            },
            "diagnosis": {
                "likely_cause": "Model collapsed to predicting HOLD...",
                "suggested_remediation": "Try different indicators...",
                "learning_detected": false
            }
        }
    """
```

---

## State Management

### No New Persistent State

v1.5 does not add persistent state. Diagnostics are:
- Generated on-the-fly after each training
- Included in training result
- Not stored separately

This keeps the system simple. v2 will add persistent learning storage.

### Indicator Reference is Static

The indicator reference is defined in code, not database:
- Easy to version and review
- No migration needed
- Can be updated in future versions

---

## Error Handling

### Invalid Indicator Error

**When:** Agent specifies indicator not in allowed list

**Response:**
```json
{
    "error": "STRATEGY-InvalidIndicator",
    "message": "Indicator 'ATR' is not allowed in v1.5. Use one of: RSI, ADX, Stochastic, Williams_R, MFI, Aroon, CMF",
    "allowed_indicators": ["RSI", "ADX", "Stochastic", "Williams_R", "MFI", "Aroon", "CMF"]
}
```

**User experience:** Strategy rejected before training starts, clear guidance provided.

### Fuzzy Set Warning

**When:** Fuzzy set parameters seem wrong for indicator range

**Response:**
```json
{
    "warnings": [
        {
            "level": "WARNING",
            "message": "RSI fuzzy set 'oversold' has peak at 50, but RSI oversold is typically 20-30",
            "field": "fuzzy_sets.rsi_14.oversold"
        }
    ]
}
```

**User experience:** Warning logged, training proceeds (agent may be experimenting intentionally).

### Diagnostics Generation Failure

**When:** Diagnostics analysis fails (e.g., missing data)

**Response:** Training result includes `diagnostics: null` with warning in logs.

**User experience:** Training result still available, just without diagnostics.

---

## Integration Points

### Existing Components (Unchanged)

- **Async Operations**: Training still uses operation tracking
- **Checkpoint System**: Training checkpoints unchanged
- **Backtest Pipeline**: Backtest unchanged (receives model as before)
- **Database Schema**: No changes to agent state tables

### New Integration Points

| Point | Integration |
|-------|-------------|
| Agent prompt generation | Includes indicator reference |
| Strategy validation | Checks indicator allowlist |
| Training pipeline | Generates diagnostics |
| Training result | Includes diagnostics |
| Agent assessment | Receives diagnostics |

---

## Verification Strategy

### Indicator Reference

**Unit Test Focus:**
- Reference data is complete (all 7 indicators)
- Fuzzy set validation catches obvious errors
- `get_allowed_indicators()` returns correct list

**Integration Test:**
- Agent context includes indicator reference
- Strategy with ATR is rejected
- Strategy with RSI + correct fuzzy sets passes

**Smoke Test:**
```bash
# Should fail - uses ATR
ktrdr strategy validate test_atr_strategy.yaml
# Expected: ERROR - Indicator 'ATR' is not allowed

# Should pass - uses RSI
ktrdr strategy validate test_rsi_strategy.yaml
# Expected: Strategy valid
```

### Training Diagnostics

**Unit Test Focus:**
- Loss curve classification (flat/decreasing/oscillating)
- Prediction collapse detection
- Zero variance feature detection
- Diagnosis synthesis logic

**Integration Test:**
- Training run produces diagnostics
- Diagnostics included in operation result
- Agent can access diagnostics via MCP tool

**Smoke Test:**
```bash
# Run training and check diagnostics
ktrdr train test_strategy.yaml
ktrdr operations get <operation_id> --include-diagnostics
# Expected: JSON with loss_curve, predictions, features, diagnosis
```

---

## File Structure

```
ktrdr/
├── agents/
│   ├── references/
│   │   ├── __init__.py
│   │   └── indicator_reference.py    # NEW
│   └── research_agent.py             # MODIFIED
├── training/
│   ├── diagnostics.py                # NEW
│   └── training_pipeline.py          # MODIFIED
└── config/
    └── strategy_validator.py         # MODIFIED

tests/
├── unit/
│   ├── agents/
│   │   └── test_indicator_reference.py    # NEW
│   └── training/
│       └── test_diagnostics.py            # NEW
└── integration/
    └── test_v15_constraints.py            # NEW
```

---

## Migration / Rollout

### No Migration Required

- New code is additive
- Existing strategies continue to work (with warnings)
- Database schema unchanged

### Rollout Steps

1. Deploy indicator reference + validation
2. Deploy training diagnostics
3. Update agent prompts to include reference
4. Run validation experiments

### Rollback

Remove agent context additions. Diagnostics are optional and don't affect training.

---

*Document Version: 1.0*
*Created: December 2024*
