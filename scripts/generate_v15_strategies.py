#!/usr/bin/env python3
"""Generate all 27 v1.5 experiment strategy files.

This script generates strategy YAML files from the template,
ensuring consistency across all experiments.
"""

from pathlib import Path

# Base template sections (fixed across all strategies)
FIXED_HEADER = '''# =============================================================================
# v1.5 EXPERIMENTAL STRATEGY
# =============================================================================
# This strategy is part of the v1.5 experiment to validate neuro-fuzzy learning.
# DO NOT modify training parameters - consistency is critical for valid comparisons.
# =============================================================================

'''

FIXED_TRAINING_DATA = '''# === TRAINING DATA CONFIG (FIXED) ===
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

'''

FIXED_MODEL = '''# === NEURAL NETWORK MODEL (FIXED) ===
model:
  type: "mlp"
  architecture:
    hidden_layers: [64, 32]
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
    epochs: 100
    optimizer: "adam"
    early_stopping:
      enabled: true
      patience: 15
      min_delta: 0.001
    analytics:
      enabled: true
      export_csv: true
      export_json: true
      export_alerts: true

# === DECISION LOGIC ===
decisions:
  output_format: "classification"
  confidence_threshold: 0.6
  position_awareness: true
  filters:
    min_signal_separation: 4
    volume_filter: false

'''


def fixed_training(zigzag_threshold: float = 0.025) -> str:
    """Generate fixed training section with optional zigzag threshold override."""
    return f'''# === TRAINING CONFIGURATION (FIXED) ===
training:
  method: "supervised"
  labels:
    source: "zigzag"
    zigzag_threshold: {zigzag_threshold}
    label_lookahead: 20
  data_split:
    train: 0.7
    validation: 0.15
    test: 0.15
  date_range:
    start: "2015-01-01"
    end: "2023-12-31"
'''


# =============================================================================
# Indicator definitions with their fuzzy sets
# =============================================================================

INDICATORS = {
    "rsi": {
        "config": '''  - name: "rsi"
    feature_id: rsi_14
    period: 14
    source: "close"
''',
        "fuzzy_sets": '''  rsi_14:
    oversold:
      type: "triangular"
      parameters: [0, 30, 40]
    neutral:
      type: "triangular"
      parameters: [35, 50, 65]
    overbought:
      type: "triangular"
      parameters: [60, 70, 100]
''',
    },
    "stochastic": {
        "config": '''  - name: "stochastic"
    feature_id: stochastic_14
    k_period: 14
    d_period: 3
    source: "close"
''',
        "fuzzy_sets": '''  stochastic_14:
    oversold:
      type: "triangular"
      parameters: [0, 20, 30]
    neutral:
      type: "triangular"
      parameters: [25, 50, 75]
    overbought:
      type: "triangular"
      parameters: [70, 80, 100]
''',
    },
    "williams": {
        "config": '''  - name: "williams_r"
    feature_id: williams_14
    period: 14
    source: "close"
''',
        "fuzzy_sets": '''  williams_14:
    oversold:
      type: "triangular"
      parameters: [-100, -80, -60]
    neutral:
      type: "triangular"
      parameters: [-65, -50, -35]
    overbought:
      type: "triangular"
      parameters: [-40, -20, 0]
''',
    },
    "mfi": {
        "config": '''  - name: "mfi"
    feature_id: mfi_14
    period: 14
''',
        "fuzzy_sets": '''  mfi_14:
    oversold:
      type: "triangular"
      parameters: [0, 30, 40]
    neutral:
      type: "triangular"
      parameters: [35, 50, 65]
    overbought:
      type: "triangular"
      parameters: [60, 70, 100]
''',
    },
    "adx": {
        "config": '''  - name: "adx"
    feature_id: adx_14
    period: 14
''',
        # Note: ADX indicator produces ADX_14 column name (uppercase)
        "fuzzy_sets": '''  ADX_14:
    weak:
      type: "triangular"
      parameters: [0, 15, 25]
    moderate:
      type: "triangular"
      parameters: [20, 35, 50]
    strong:
      type: "triangular"
      parameters: [45, 60, 100]
''',
    },
    "di": {
        # +DI and -DI come from the ADX indicator
        # Note: ADX indicator produces DI_Plus_14 and DI_Minus_14 column names
        "config": '''  - name: "adx"
    feature_id: adx_14
    period: 14
''',
        "fuzzy_sets": '''  DI_Plus_14:
    weak:
      type: "triangular"
      parameters: [0, 15, 25]
    moderate:
      type: "triangular"
      parameters: [20, 35, 50]
    strong:
      type: "triangular"
      parameters: [45, 60, 100]
  DI_Minus_14:
    weak:
      type: "triangular"
      parameters: [0, 15, 25]
    moderate:
      type: "triangular"
      parameters: [20, 35, 50]
    strong:
      type: "triangular"
      parameters: [45, 60, 100]
''',
    },
    "aroon": {
        "config": '''  - name: "aroon"
    feature_id: aroon_25
    period: 25
''',
        "fuzzy_sets": '''  aroon_up_25:
    weak:
      type: "triangular"
      parameters: [0, 25, 40]
    moderate:
      type: "triangular"
      parameters: [35, 50, 65]
    strong:
      type: "triangular"
      parameters: [60, 75, 100]
  aroon_down_25:
    weak:
      type: "triangular"
      parameters: [0, 25, 40]
    moderate:
      type: "triangular"
      parameters: [35, 50, 65]
    strong:
      type: "triangular"
      parameters: [60, 75, 100]
''',
    },
    "cmf": {
        "config": '''  - name: "cmf"
    feature_id: cmf_20
    period: 20
''',
        "fuzzy_sets": '''  cmf_20:
    selling:
      type: "triangular"
      parameters: [-1, -0.3, -0.05]
    neutral:
      type: "triangular"
      parameters: [-0.1, 0, 0.1]
    buying:
      type: "triangular"
      parameters: [0.05, 0.3, 1]
''',
    },
    "rvi": {
        "config": '''  - name: "rvi"
    feature_id: rvi_10
    period: 10
''',
        "fuzzy_sets": '''  rvi_10:
    low:
      type: "triangular"
      parameters: [0, 20, 40]
    neutral:
      type: "triangular"
      parameters: [30, 50, 70]
    high:
      type: "triangular"
      parameters: [60, 80, 100]
''',
    },
}


# =============================================================================
# Strategy definitions
# =============================================================================

STRATEGIES = {
    # Single indicator strategies (9)
    "v15_rsi_only": {
        "description": "RSI only - baseline bounded momentum indicator",
        "indicators": ["rsi"],
    },
    "v15_stochastic_only": {
        "description": "Stochastic only - momentum oscillator alternative",
        "indicators": ["stochastic"],
    },
    "v15_williams_only": {
        "description": "Williams %R only - negative range indicator test",
        "indicators": ["williams"],
    },
    "v15_mfi_only": {
        "description": "MFI only - volume-weighted momentum",
        "indicators": ["mfi"],
    },
    "v15_adx_only": {
        "description": "ADX only - trend strength (no direction)",
        "indicators": ["adx"],
    },
    "v15_aroon_only": {
        "description": "Aroon Up + Down - trend timing pair",
        "indicators": ["aroon"],
    },
    "v15_cmf_only": {
        "description": "CMF only - money flow (bipolar range)",
        "indicators": ["cmf"],
    },
    "v15_rvi_only": {
        "description": "RVI only - vigor/momentum alternative",
        "indicators": ["rvi"],
    },
    "v15_di_only": {
        "description": "+DI + -DI only - directional movement pair",
        "indicators": ["di"],
    },
    # Two indicator combinations (11)
    "v15_rsi_adx": {
        "description": "RSI + ADX - momentum with trend strength filter",
        "indicators": ["rsi", "adx"],
    },
    "v15_rsi_stochastic": {
        "description": "RSI + Stochastic - dual momentum oscillators",
        "indicators": ["rsi", "stochastic"],
    },
    "v15_rsi_williams": {
        "description": "RSI + Williams %R - momentum confirmation",
        "indicators": ["rsi", "williams"],
    },
    "v15_rsi_mfi": {
        "description": "RSI + MFI - price momentum with volume",
        "indicators": ["rsi", "mfi"],
    },
    "v15_adx_aroon": {
        "description": "ADX + Aroon - trend strength with timing",
        "indicators": ["adx", "aroon"],
    },
    "v15_adx_di": {
        "description": "ADX + DI - full ADX directional system",
        "indicators": ["adx", "di"],
    },
    "v15_stochastic_williams": {
        "description": "Stochastic + Williams %R - oversold/overbought confirmation",
        "indicators": ["stochastic", "williams"],
    },
    "v15_mfi_cmf": {
        "description": "MFI + CMF - dual volume indicators",
        "indicators": ["mfi", "cmf"],
    },
    "v15_rsi_cmf": {
        "description": "RSI + CMF - momentum with money flow",
        "indicators": ["rsi", "cmf"],
    },
    "v15_adx_rsi": {
        "description": "ADX + RSI - filter momentum by trend strength",
        "indicators": ["adx", "rsi"],
    },
    "v15_aroon_rvi": {
        "description": "Aroon + RVI - trend timing with vigor",
        "indicators": ["aroon", "rvi"],
    },
    # Three indicator combinations (3)
    "v15_rsi_adx_stochastic": {
        "description": "RSI + ADX + Stochastic - comprehensive momentum/trend",
        "indicators": ["rsi", "adx", "stochastic"],
    },
    "v15_mfi_adx_aroon": {
        "description": "MFI + ADX + Aroon - volume, strength, and timing",
        "indicators": ["mfi", "adx", "aroon"],
    },
    "v15_williams_stochastic_cmf": {
        "description": "Williams + Stochastic + CMF - oscillators with money flow",
        "indicators": ["williams", "stochastic", "cmf"],
    },
    # Zigzag threshold variations (4)
    "v15_rsi_zigzag_1.5": {
        "description": "RSI with 1.5% zigzag threshold (more signals)",
        "indicators": ["rsi"],
        "zigzag_threshold": 0.015,
    },
    "v15_rsi_zigzag_2.0": {
        "description": "RSI with 2.0% zigzag threshold",
        "indicators": ["rsi"],
        "zigzag_threshold": 0.020,
    },
    "v15_rsi_zigzag_3.0": {
        "description": "RSI with 3.0% zigzag threshold",
        "indicators": ["rsi"],
        "zigzag_threshold": 0.030,
    },
    "v15_rsi_zigzag_3.5": {
        "description": "RSI with 3.5% zigzag threshold (fewer signals)",
        "indicators": ["rsi"],
        "zigzag_threshold": 0.035,
    },
}


def generate_strategy(name: str, config: dict) -> str:
    """Generate a complete strategy YAML file."""
    parts = [FIXED_HEADER]

    # Strategy identity
    parts.append(f'''# === STRATEGY IDENTITY ===
name: "{name}"
description: "v1.5 experiment: {config['description']}"
version: "1.0"

''')

    parts.append(FIXED_TRAINING_DATA)

    # Indicators section
    parts.append("# === TECHNICAL INDICATORS ===\nindicators:\n")
    seen_indicators = set()
    for ind_name in config["indicators"]:
        ind = INDICATORS[ind_name]
        # Avoid duplicate indicator configs (e.g., adx appears in both adx and di)
        ind_config = ind["config"]
        if ind_config not in seen_indicators:
            parts.append(ind_config)
            seen_indicators.add(ind_config)

    parts.append("\n")

    # Fuzzy sets section
    parts.append("# === FUZZY LOGIC CONFIGURATION ===\nfuzzy_sets:\n")
    for ind_name in config["indicators"]:
        ind = INDICATORS[ind_name]
        parts.append(ind["fuzzy_sets"])

    parts.append("\n")
    parts.append(FIXED_MODEL)

    # Training section with optional zigzag threshold override
    zigzag = config.get("zigzag_threshold", 0.025)
    parts.append(fixed_training(zigzag))

    return "".join(parts)


def main():
    """Generate all 27 strategy files."""
    output_dir = Path("strategies")
    output_dir.mkdir(exist_ok=True)

    generated = []
    for name, config in STRATEGIES.items():
        content = generate_strategy(name, config)
        output_path = output_dir / f"{name}.yaml"
        output_path.write_text(content)
        generated.append(name)
        print(f"Generated: {output_path}")

    print(f"\nTotal: {len(generated)} strategy files generated")


if __name__ == "__main__":
    main()
