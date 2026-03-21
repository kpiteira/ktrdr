# Test: training/gaussian-hybrid-dead-zone-elimination

**Purpose:** Validate that Gaussian MFs + hybrid encoding (raw + fuzzy) eliminate feature dead zones: strategy validates, resolved features include both fuzzy and raw types in correct order, and Gaussian MFs produce non-zero memberships across realistic indicator ranges.
**Duration:** ~30 seconds (validation + feature resolution + membership evaluation, no training)
**Category:** Training (Feature Encoding)

**Dependency:** None (self-contained: uses CLI validate + Python-based feature/membership inspection)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../../e2e-testing/preflight/common.md) -- Docker, sandbox, API health

**Test-specific checks:**
- [ ] Strategy file exists: `ls strategies/trend_tb_gaussian_signal_v1.yaml`
- [ ] Sandbox is running

**Pre-flight commands:**
```bash
source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# 1. Strategy file in repo
test -f strategies/trend_tb_gaussian_signal_v1.yaml || {
  echo "FAIL: trend_tb_gaussian_signal_v1.yaml not found in strategies/"
  exit 1
}

# 2. API health
curl -sf "http://localhost:$API_PORT/api/v1/health" > /dev/null || {
  echo "FAIL: API not healthy on port $API_PORT"
  exit 1
}
```

---

## Execution Steps

### 1. Validate Strategy via CLI

```bash
uv run ktrdr validate ./strategies/trend_tb_gaussian_signal_v1.yaml
```

**Expected:** Exit code 0, output contains "valid", resolved features: 32

### 2. Resolve Features and Verify Count + Order

```bash
uv run python -c "
from ktrdr.config.models import StrategyConfigurationV3
from ktrdr.config.feature_resolver import FeatureResolver
import yaml

with open('strategies/trend_tb_gaussian_signal_v1.yaml') as f:
    raw = yaml.safe_load(f)

config = StrategyConfigurationV3(**raw)
resolver = FeatureResolver()
features = resolver.resolve(config)

fuzzy = [f for f in features if f.fuzzy_set_id != '__raw__']
raw_f = [f for f in features if f.fuzzy_set_id == '__raw__']

assert len(features) == 32, f'Expected 32, got {len(features)}'
assert len(fuzzy) == 24, f'Expected 24 fuzzy, got {len(fuzzy)}'
assert len(raw_f) == 8, f'Expected 8 raw, got {len(raw_f)}'

# Verify interleave: rsi fuzzy (6) then rsi raw (2) then adx fuzzy (6) then adx raw (2)...
assert features[0].fuzzy_set_id == 'rsi_momentum'
assert features[6].fuzzy_set_id == '__raw__' and features[6].indicator_id == 'rsi_14'
assert features[8].fuzzy_set_id == 'adx_trend'
assert features[14].fuzzy_set_id == '__raw__' and features[14].indicator_id == 'adx_14'
print('PASS: 32 features, correct interleave order')
"
```

### 3. Verify Zero Dead Zones (Core Metric)

```bash
uv run python -c "
import numpy as np
from ktrdr.fuzzy.membership import MembershipFunctionFactory

configs = {
    'RSI': ([30, 15], [50, 12], [70, 15], 0, 100),
    'ADX': ([15, 10], [30, 10], [50, 15], 0, 80),
    'MACD': ([-0.002, 0.002], [0, 0.0015], [0.002, 0.002], -0.005, 0.005),
    'ROC': ([-0.4, 0.35], [0, 0.25], [0.4, 0.35], -1.0, 1.0),
}

all_pass = True
for name, (p1, p2, p3, lo, hi) in configs.items():
    mf1 = MembershipFunctionFactory.create('gaussian', list(p1))
    mf2 = MembershipFunctionFactory.create('gaussian', list(p2))
    mf3 = MembershipFunctionFactory.create('gaussian', list(p3))
    values = np.linspace(lo, hi, 1000)
    dead = sum(1 for v in values if max(mf1.evaluate(v), mf2.evaluate(v), mf3.evaluate(v)) < 0.01)
    status = 'PASS' if dead == 0 else 'FAIL'
    print(f'{name}: {dead}/1000 dead zones [{status}]')
    if dead > 0: all_pass = False

print(f'OVERALL: {\"PASS\" if all_pass else \"FAIL\"}')
assert all_pass, 'Dead zones detected'
"
```

**Expected:** All 0/1000, OVERALL: PASS

### 4. Verify Raw Feature Sentinels and Normalization

```bash
uv run python -c "
from ktrdr.config.models import StrategyConfigurationV3
from ktrdr.config.feature_resolver import FeatureResolver
import yaml

with open('strategies/trend_tb_gaussian_signal_v1.yaml') as f:
    raw = yaml.safe_load(f)

config = StrategyConfigurationV3(**raw)
resolver = FeatureResolver()
features = resolver.resolve(config)

raw_f = [f for f in features if f.fuzzy_set_id == '__raw__']
for f in raw_f:
    assert f.feature_id.endswith('_raw'), f'Bad suffix: {f.feature_id}'
    assert f.membership_name == 'raw', f'Bad membership: {f.membership_name}'

# Check normalization on raw nn_inputs
raw_inputs = [inp for inp in config.nn_inputs if inp.raw_indicator is not None]
assert len(raw_inputs) == 4
for inp in raw_inputs:
    assert inp.normalization is not None, f'Missing normalization on {inp.raw_indicator}'
print('PASS: Sentinels and normalization correct')
"
```

---

## Success Criteria

- [ ] CLI `ktrdr validate` accepts the strategy (exit code 0)
- [ ] FeatureResolver produces exactly 32 features (24 fuzzy + 8 raw)
- [ ] Features interleaved: fuzzy block then raw block per indicator
- [ ] All 4 fuzzy sets have zero dead zones across full indicator ranges
- [ ] Raw features use `__raw__` sentinel and `_raw` suffix
- [ ] All raw nn_inputs have normalization specified

---

## Sanity Checks

- [ ] **Feature count is 32, NOT 24** -- If 24, raw_indicator nn_inputs silently skipped
- [ ] **Raw features have fuzzy_set_id == "__raw__"** -- Sentinel prevents raw-as-fuzzy processing
- [ ] **Dead zone count is exactly 0** -- Even 1 means Gaussian params too narrow
- [ ] **Normalization preserved on raw inputs** -- Without it, raw values dominate training

---

## Troubleshooting

**"Unknown membership function type: gaussian":** `MembershipFunctionFactory.create()` missing gaussian branch. Check `ktrdr/fuzzy/membership.py`.

**Feature count 24 not 32:** `FeatureResolver.resolve()` missing `elif nn_input.raw_indicator:` branch. Check `ktrdr/config/feature_resolver.py`.

**Dead zones in MACD/ROC:** Gaussian sigma too narrow for domain. Widen sigma values in strategy YAML.
