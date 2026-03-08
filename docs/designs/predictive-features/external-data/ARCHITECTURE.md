# External Data Sources: Architecture

## Status: Design
## Date: 2026-03-07

---

## 1. System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     Strategy Grammar V3                          │
│                                                                  │
│  training_data:         context_data:                            │
│    symbol: EURUSD         - provider: ib                         │
│    timeframe: 1h            symbol: GBPUSD                       │
│                           - provider: fred                       │
│                             series: [DGS2, IRLTLT01DEM156N]      │
│                           - provider: cftc_cot                   │
│                             report: EUR                          │
│                           - provider: economic_calendar          │
│                             currencies: [USD, EUR]               │
│                                                                  │
│  indicators:            fuzzy_sets:          nn_inputs:           │
│    rsi_14: {...}          rsi_momentum:        - fuzzy_set: ...   │
│    yield_rsi:               indicator: rsi_14    timeframes: all  │
│      type: rsi            yield_trend:                            │
│      data_source: yield_spread   indicator: yield_rsi             │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                   Data Acquisition Layer                         │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐   │
│  │    IB    │  │   FRED   │  │   CFTC   │  │   Calendar     │   │
│  │ Provider │  │ Provider │  │ Provider │  │   Provider     │   │
│  │          │  │          │  │          │  │                │   │
│  │ Forex    │  │ Yields   │  │ COT      │  │ Events         │   │
│  │ Indices  │  │ Spreads  │  │ Weekly   │  │ Impact levels  │   │
│  │ Equities │  │ Rates    │  │ data     │  │ Timing         │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───────┬────────┘   │
│       │             │             │                 │             │
│       ▼             ▼             ▼                 ▼             │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │              Context Data Cache                          │     │
│  │  Per-provider, per-series cached data                    │     │
│  │  Forward-fill alignment to primary timeframe             │     │
│  └──────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                   Feature Computation                            │
│                                                                  │
│  IndicatorEngine:                                                │
│    - Receives primary OHLCV + context DataFrames                 │
│    - Computes indicators per data_source (rsi on EURUSD, rsi on  │
│      yield_spread, etc.)                                         │
│    - Each indicator tagged with its data_source for col prefixing│
│                                                                  │
│  FuzzyEngine:                                                    │
│    - Applies membership functions to indicator outputs           │
│    - Source-agnostic (works on any indicator output)              │
│                                                                  │
│  FeatureResolver:                                                │
│    - Resolves nn_inputs → ordered feature vector                 │
│    - Handles data_source-prefixed indicator IDs                  │
│    - Maintains canonical feature ordering for train/backtest     │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│              Training / Backtest Pipeline                        │
│                                                                  │
│  1. Load primary data (IB/cache)                                 │
│  2. Load context data (per provider, per entry)                  │
│  3. Align context to primary timeframe (forward-fill)            │
│  4. Compute indicators on each data source                       │
│  5. Compute fuzzy memberships                                    │
│  6. Resolve nn_inputs to ordered feature vector                  │
│  7. Train/evaluate model                                         │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Grammar Extension

### 2.1 `context_data` Section

New top-level field on `StrategyConfigurationV3`:

```python
class ContextDataEntry(BaseModel):
    """Single external data source declaration."""

    provider: str                          # "ib", "fred", "cftc_cot", "economic_calendar", "sentiment"
    alignment: str = "forward_fill"        # How to align to primary timeframe

    # Provider-specific fields (validated per provider)
    # IB provider
    symbol: Optional[str] = None           # e.g., "GBPUSD"
    timeframe: Optional[str] = None        # e.g., "1h"
    instrument_type: Optional[str] = None  # e.g., "FOREX", "INDEX"

    # FRED provider
    series: Optional[Union[str, list[str]]] = None  # e.g., "DGS2" or ["DGS2", "IRLTLT01DEM156N"]
    frequency: Optional[str] = None                  # e.g., "daily"

    # CFTC provider
    report: Optional[str] = None           # e.g., "EUR" (currency code)

    # Calendar provider
    currencies: Optional[list[str]] = None # e.g., ["USD", "EUR"]
    min_impact: Optional[str] = None       # e.g., "high"

    # Sentiment provider
    broker: Optional[str] = None           # e.g., "myfxbook"


class StrategyConfigurationV3(BaseModel):
    # ... existing fields ...
    context_data: Optional[list[ContextDataEntry]] = None  # NEW
```

### 2.2 `data_source` Field on Indicators

Extended `IndicatorDefinition`:

```python
class IndicatorDefinition(BaseModel):
    type: str                              # Indicator type (rsi, macd, etc.)
    data_source: Optional[str] = None      # Context data reference (None = primary)
    # ... remaining fields are indicator parameters
```

**Important naming note:** The field is `data_source`, NOT `source`. The existing `IndicatorDefinition` uses `model_config = {"extra": "allow"}` and some indicators already use `source` as a parameter (e.g., RSI has `source: close` to specify which OHLCV column to compute on). Using `source` for context data would collide with these existing parameters.

The `data_source` value must match one of:
- A `context_data[].symbol` (for IB provider)
- A `context_data[].series` element or computed name (for FRED provider)
- A synthetic series ID (future: `synthetics` section)

### 2.3 Example Strategy YAML

```yaml
name: eurusd_carry_momentum_v1
version: "3.0"
description: "EURUSD with carry factor (yield spread) and cross-pair context"

training_data:
  symbols:
    mode: single
    symbol: EURUSD
  timeframes:
    mode: single
    timeframe: "1h"
  history_required: 200
  start_date: "2019-01-01"
  end_date: "2025-01-01"

context_data:
  # Cross-pair context
  - provider: ib
    symbol: GBPUSD
    timeframe: "1h"
    instrument_type: FOREX
    alignment: forward_fill

  # Yield spread (carry factor)
  - provider: fred
    series: [DGS2, IRLTLT01DEM156N]
    frequency: daily
    alignment: forward_fill

  # Positioning
  - provider: cftc_cot
    report: EUR
    alignment: forward_fill

indicators:
  # Primary instrument
  rsi_14:
    type: rsi
    period: 14

  ema_20:
    type: ema
    period: 20

  # Cross-pair context
  gbp_rsi_14:
    type: rsi
    period: 14
    data_source: GBPUSD

  # Yield spread indicators
  yield_spread_rsi:
    type: rsi
    period: 14
    data_source: yield_spread_DGS2_IRLTLT01DEM156N   # Computed spread name

  yield_spread_ema:
    type: ema
    period: 20
    data_source: yield_spread_DGS2_IRLTLT01DEM156N

  # COT positioning (pre-computed percentile series)
  cot_percentile_ema:
    type: ema
    period: 4                                     # 4-week smoothing
    data_source: cot_EUR_net_pct

fuzzy_sets:
  rsi_momentum:
    indicator: rsi_14
    oversold: [0, 25, 40]
    neutral: [30, 50, 70]
    overbought: [60, 75, 100]

  gbp_momentum:
    indicator: gbp_rsi_14
    weak: [0, 30, 50]
    strong: [50, 70, 100]

  carry_direction:
    indicator: yield_spread_rsi
    usd_strengthening: [60, 75, 100]    # Spread widening = USD carry advantage
    neutral: [35, 50, 65]
    eur_strengthening: [0, 25, 40]      # Spread narrowing = EUR carry advantage

  positioning:
    indicator: cot_percentile_ema
    crowded_long: [75, 90, 100]         # Contrarian bearish
    neutral: [25, 50, 75]
    crowded_short: [0, 10, 25]          # Contrarian bullish

nn_inputs:
  - fuzzy_set: rsi_momentum
    timeframes: all
  - fuzzy_set: gbp_momentum
    timeframes: all
  - fuzzy_set: carry_direction
    timeframes: all
  - fuzzy_set: positioning
    timeframes: all

model:
  type: mlp
  hidden_layers: [32, 16]
  dropout: 0.2
  output_format: regression

decisions:
  mode: regression
  prediction_target: forward_return
  forward_periods: 20
  cost_threshold: 0.0045

training:
  epochs: 100
  batch_size: 64
  learning_rate: 0.001
  validation_split: 0.2
```

### 2.4 Validation Rules

Strategy validation must enforce:

1. Every `data_source` value in `indicators` must resolve to a declared `context_data` entry or its computed derivative
2. Every `context_data` entry's provider must be a registered provider type
3. Provider-specific required fields are present (IB needs symbol+timeframe, FRED needs series, etc.)
4. `alignment` values are valid (currently only `forward_fill`)
5. FRED series IDs are syntactically valid (checked at validation; availability checked at data load)
6. Warn (don't error) if `context_data` entries are declared but no indicator references them

---

## 3. Data Provider Architecture

### 3.1 Provider Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import pandas as pd


@dataclass
class ContextDataResult:
    """Result from a context data provider."""

    source_id: str                    # Unique identifier for this data source
    data: pd.DataFrame                # OHLCV-like DataFrame (index=datetime)
    frequency: str                    # "hourly", "daily", "weekly"
    provider: str                     # Provider name
    metadata: dict[str, Any]          # Provider-specific metadata


class ContextDataProvider(ABC):
    """Abstract interface for external data providers."""

    @abstractmethod
    async def fetch(
        self,
        config: ContextDataEntry,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ContextDataResult]:
        """Fetch data for a context_data entry.

        Returns a list because one entry may produce multiple series
        (e.g., FRED entry with series: [DGS2, IRLTLT01DEM156N] produces
        two results plus a computed spread).
        """
        ...

    @abstractmethod
    async def validate(self, config: ContextDataEntry) -> list[str]:
        """Validate that this config entry is fetchable.

        Returns list of error messages (empty = valid).
        """
        ...

    @abstractmethod
    def get_source_ids(self, config: ContextDataEntry) -> list[str]:
        """Return the source_id values this entry will produce.

        Used by strategy validation to check indicator source references.
        """
        ...
```

### 3.2 Provider Implementations

#### FRED Provider

```
FredDataProvider
├── fetch()
│   ├── For each series ID in config.series:
│   │   ├── HTTP GET https://api.stlouisfed.org/fred/series/observations
│   │   ├── Parse CSV response → DataFrame (date index, value column)
│   │   └── Cache locally (data/context/fred/{series_id}.csv)
│   ├── If multiple series: compute spread (series[0] - series[1])
│   └── Return [individual series results + spread result]
├── validate()
│   └── Check series IDs are syntactically valid
└── get_source_ids()
    ├── For single series: ["fred_{series_id}"]
    ├── For multiple: ["fred_{s1}", "fred_{s2}", "yield_spread_{s1}_{s2}"]
    └── Spread name is deterministic from series list
```

**FRED API details:**
- Base URL: `https://api.stlouisfed.org/fred/series/observations`
- Parameters: `series_id`, `observation_start`, `observation_end`, `file_type=json`
- API key: free registration required (store in env var `FRED_API_KEY`)
- Rate limit: 120 requests/minute
- Response: JSON with `observations: [{date, value}]`

**Data shape:** Single column DataFrame with DatetimeIndex:
```
                     value
2024-01-02 00:00:00  4.38
2024-01-03 00:00:00  4.35
2024-01-04 00:00:00  4.40
```

**Spread computation:** When `series` is a list of 2, automatically compute `series[0] - series[1]` and expose as `yield_spread_{s1}_{s2}`. This covers the US-DE yield differential use case.

#### IB Context Provider

```
IbContextDataProvider
├── fetch()
│   ├── Reuse existing IbDataProvider (already implemented)
│   ├── Fetch OHLCV for config.symbol at config.timeframe
│   └── Return as ContextDataResult with source_id = symbol
├── validate()
│   └── Delegate to IbDataProvider.validate_symbol()
└── get_source_ids()
    └── [config.symbol]  # e.g., ["GBPUSD"]
```

**Key point:** This is a thin wrapper around the existing `IbDataProvider`. No new IB infrastructure needed.

#### CFTC COT Provider

```
CftcCotProvider
├── fetch()
│   ├── Use cot_reports library to download TFF report
│   ├── Filter for config.report currency
│   ├── Extract: net_speculative_long, net_speculative_short, net_position
│   ├── Compute percentile over rolling window (52w, 156w)
│   ├── Cache locally (data/context/cftc/{report}.csv)
│   └── Return results: raw position + percentile series
├── validate()
│   └── Check report code is valid currency code
└── get_source_ids()
    └── ["cot_{report}_net_pos", "cot_{report}_net_pct"]
```

**Data shape:** Weekly DataFrame:
```
                     net_position  net_pct_52w  net_pct_156w
2024-01-02 00:00:00  45230         72.5         65.3
2024-01-09 00:00:00  48100         78.2         70.1
```

#### Economic Calendar Provider

```
EconomicCalendarProvider
├── fetch()
│   ├── Fetch events from Finnhub/calendar API
│   ├── Filter by config.currencies and config.min_impact
│   ├── Compute features per timestamp:
│   │   - hours_until_next_event (continuous)
│   │   - is_event_day (binary)
│   │   - event_impact_level (categorical → numeric)
│   ├── Cache events list (data/context/calendar/events.json)
│   └── Return as time-indexed DataFrame
├── validate()
│   └── Check currencies are valid ISO codes
└── get_source_ids()
    └── ["calendar_{currency}" for currency in config.currencies]
```

**Data shape:** Hourly DataFrame (computed from event schedule):
```
                     hours_to_next  is_event_day  impact_level
2024-01-05 08:00:00  5.5            1             3
2024-01-05 09:00:00  4.5            1             3
...
2024-01-05 13:30:00  0.0            1             3   # NFP release
2024-01-05 14:00:00  168.0          0             0   # Next event in 7 days
```

### 3.3 Provider Registry

```python
class ContextDataProviderRegistry:
    """Registry of available context data providers."""

    _providers: dict[str, type[ContextDataProvider]]

    def register(self, name: str, provider_class: type[ContextDataProvider]) -> None: ...
    def get(self, name: str) -> ContextDataProvider: ...
    def available_providers(self) -> list[str]: ...

# Default registration
registry = ContextDataProviderRegistry()
registry.register("ib", IbContextDataProvider)
registry.register("fred", FredDataProvider)
registry.register("cftc_cot", CftcCotProvider)
registry.register("economic_calendar", EconomicCalendarProvider)
```

---

## 4. Data Alignment

### 4.1 Forward-Fill Strategy

Context data arrives at different frequencies. All must be aligned to the primary instrument's timeframe.

```
Primary (1h):    |-----|-----|-----|-----|-----|-----|-----|
                 09:00 10:00 11:00 12:00 13:00 14:00 15:00

FRED (daily):    |==========================|
                 Previous close              Next close
                 (forward-filled to all bars)

COT (weekly):    |=====================================================|
                 Tuesday snapshot (forward-filled to all bars until next)
```

### 4.2 Alignment Implementation

```python
class ContextDataAligner:
    """Aligns context data to primary instrument's datetime index."""

    def align(
        self,
        context_data: pd.DataFrame,     # Lower-frequency context
        primary_index: pd.DatetimeIndex, # Primary instrument's index
        method: str = "forward_fill",    # Alignment method
    ) -> pd.DataFrame:
        """
        1. Reindex context data to primary's datetime index
        2. Forward-fill NaN values
        3. Drop any remaining leading NaN rows (before first context observation)
        """
        ...
```

**Edge cases:**
- **Leading NaNs:** If context data starts after primary data, those bars have no context. Drop them from training (they're at the start of the window, usually outside the useful range anyway).
- **Weekend gaps:** FRED/CFTC don't publish on weekends. Forward-fill carries Friday's value through to Monday. This is correct — the data hasn't changed.
- **Holiday gaps:** Same treatment as weekends. Forward-fill.

### 4.3 Data Availability Matrix

| Provider | Frequency | Trading Hours | Alignment Notes |
|----------|-----------|---------------|-----------------|
| IB (forex) | 1h | 24h Sun-Fri | Direct match |
| IB (equities) | 1h | US market hours | Forward-fill ~16h/day |
| FRED (yields) | Daily | US business days | Forward-fill to all hourly bars |
| CFTC (COT) | Weekly | Tuesday snapshot | Forward-fill ~168 bars |
| Calendar | Event-based | N/A | Pre-computed to hourly |
| Sentiment | Real-time snapshot | 24h | Forward-fill between snapshots |

---

## 5. Feature Computation Flow

### 5.1 Extended IndicatorEngine

The existing `IndicatorEngine` computes indicators on a single DataFrame. Extension needed:

```python
class IndicatorEngine:
    def compute_indicators(
        self,
        primary_data: pd.DataFrame,
        indicators: dict[str, IndicatorDefinition],
        context_data: Optional[dict[str, pd.DataFrame]] = None,  # NEW
    ) -> dict[str, pd.DataFrame]:
        """
        For each indicator:
          - If indicator.data_source is None: compute on primary_data
          - If indicator.data_source is set: compute on context_data[data_source]

        Returns dict mapping indicator_id to result DataFrame.
        """
```

**Key constraint:** The indicator itself doesn't know about sources. It receives a DataFrame and computes. The engine selects which DataFrame to pass based on `indicator.data_source`.

### 5.2 Extended FeatureResolver

The existing `FeatureResolver` maps nn_inputs → ordered feature list. Source awareness is transparent:

```python
class ResolvedFeature:
    feature_id: str           # e.g., "1h_carry_direction_usd_strengthening"
    timeframe: str            # e.g., "1h"
    fuzzy_set_id: str         # e.g., "carry_direction"
    membership_name: str      # e.g., "usd_strengthening"
    indicator_id: str         # e.g., "yield_spread_rsi"
    indicator_output: Optional[str]  # For multi-output indicators
    # No source field needed — indicator_id already encodes the source
```

**No changes needed to FeatureResolver.** The source information is encapsulated in the indicator_id → indicator definition mapping. The resolver doesn't need to know where the data comes from — it just resolves fuzzy_set → indicator → feature.

### 5.3 Feature Cache

The existing `FeatureCache` needs extension to handle context data:

```python
class FeatureCache:
    def compute_features(
        self,
        primary_data: pd.DataFrame,
        context_data: Optional[dict[str, pd.DataFrame]] = None,  # NEW
    ) -> pd.DataFrame:
        """Compute all features (indicators → fuzzy → resolved vector).

        1. Compute indicators (primary + context sources)
        2. Apply fuzzy memberships
        3. Resolve to ordered feature vector
        """
```

---

## 6. Context Data Cache

### 6.1 Cache Structure

```
data/
├── EURUSD_1h.csv              # Primary data (existing)
├── GBPUSD_1h.csv              # Cross-pair context (existing format)
├── context/                    # NEW: external provider cache
│   ├── fred/
│   │   ├── DGS2.csv
│   │   ├── IRLTLT01DEM156N.csv
│   │   └── metadata.json      # Last fetch time, date range
│   ├── cftc/
│   │   ├── EUR_tff.csv
│   │   └── metadata.json
│   ├── calendar/
│   │   ├── events_2024.json
│   │   └── metadata.json
│   └── sentiment/
│       ├── myfxbook_EURUSD.csv
│       └── metadata.json
```

### 6.2 Cache Strategy

- **IB data:** Uses existing DataRepository cache (no change)
- **FRED data:** Fetch once, cache locally. Append new data on subsequent fetches. Check for updates daily.
- **CFTC data:** Fetch weekly. Cache entire history. Append new weeks.
- **Calendar data:** Fetch for date range. Cache events as JSON. Re-fetch periodically for schedule updates.
- **Sentiment data:** No historical cache available from providers. Must collect going forward.

---

## 7. Model Bundle Extension

The model bundle (saved after training) must include context data requirements so backtesting and inference can reproduce the exact data pipeline:

```python
class ModelMetadata:
    # ... existing fields ...
    context_data_config: Optional[list[dict]] = None  # Serialized ContextDataEntry list
    context_source_ids: Optional[list[str]] = None    # Ordered list of source IDs used
```

During backtesting, the engine reads `context_data_config` from the bundle, fetches the required data, and computes features identically to training.

---

## 8. Integration Points (Existing Code Changes)

### 8.1 Files to Modify

| File | Change |
|------|--------|
| `ktrdr/config/models.py` | Add `ContextDataEntry`, `context_data` field on `StrategyConfigurationV3`, `data_source` field on `IndicatorDefinition` |
| `ktrdr/config/strategy_validator.py` | Validate `data_source` references against `context_data` entries |
| `ktrdr/config/feature_resolver.py` | No changes needed (data_source is transparent) |
| `ktrdr/indicators/indicator_engine.py` | Accept `context_data` dict, route indicators by `data_source` |
| `ktrdr/training/training_pipeline.py` | Load context data alongside primary data |
| `ktrdr/training/feature_cache.py` | Pass context data through to IndicatorEngine |
| `ktrdr/backtesting/engine.py` | Load context data from model bundle metadata |
| `ktrdr/training/model_bundle.py` | Store context_data_config in metadata |
| `ktrdr/agents/design_sdk_prompt.py` | Update design agent with context_data awareness |
| `ktrdr/evolution/genome.py` | Add data source dimensions to genome |

### 8.2 New Files

| File | Purpose |
|------|---------|
| `ktrdr/data/context/` | New package for context data providers |
| `ktrdr/data/context/base.py` | `ContextDataProvider` ABC, `ContextDataResult`, `ContextDataAligner` |
| `ktrdr/data/context/registry.py` | `ContextDataProviderRegistry` |
| `ktrdr/data/context/fred_provider.py` | FRED API client + cache |
| `ktrdr/data/context/ib_context_provider.py` | Thin wrapper around existing `IbDataProvider` |
| `ktrdr/data/context/cftc_provider.py` | CFTC COT data fetcher + percentile computation |
| `ktrdr/data/context/calendar_provider.py` | Economic calendar event fetcher |
| `ktrdr/data/context/sentiment_provider.py` | Retail sentiment API client |

---

## 9. Error Handling

### 9.1 Provider Failures

| Failure | Behavior |
|---------|----------|
| FRED API down | Use cached data if available. Fail with clear error if no cache exists. |
| CFTC data delayed | Forward-fill from last known week. Log warning. |
| IB context symbol unavailable | Fail strategy validation (context symbol must be fetchable) |
| Calendar API rate-limited | Retry with backoff. Calendar data is pre-fetchable. |
| Sentiment API unavailable | Degrade gracefully — sentiment features become NaN, model proceeds without |

### 9.2 Data Quality

| Issue | Handling |
|-------|----------|
| FRED series has missing days (holidays) | Forward-fill (standard for daily data) |
| COT report has revised data | Use latest revision. No point-in-time reconstruction for weekly data. |
| Context data starts after primary data | Trim primary data to context availability window |
| Context data has suspicious values (spikes, zeros) | Provider-level validation with configurable thresholds |

---

## 10. Thread 1 Interaction (Multi-Network)

Thread 1 (regime detection) may produce a multi-network architecture where different model heads consume different features. The external data design is compatible:

- **Grammar level:** `context_data` declares what data is available. Which model head consumes which nn_inputs is a Thread 1 concern.
- **Feature level:** All context features are computed identically regardless of which model consumes them.
- **Possible future extension:** nn_inputs could be grouped by model head:

```yaml
# Future (Thread 1 design)
models:
  regime_model:
    nn_inputs:
      - fuzzy_set: carry_direction
      - fuzzy_set: positioning
    output: regime_label

  signal_model:
    nn_inputs:
      - fuzzy_set: rsi_momentum
      - fuzzy_set: gbp_momentum
    context: regime_model.output     # Regime gates signal
    output: forward_return
```

This is explicitly out of scope for this design. We note it for compatibility and defer to Thread 1.

---

## 11. LLM Consumption Reference

### Context Data Entry Types

| Provider | Required Fields | Optional Fields | Source IDs Produced |
|----------|----------------|-----------------|---------------------|
| `ib` | `symbol`, `timeframe` | `instrument_type`, `alignment` | `{symbol}` |
| `fred` | `series` | `frequency`, `alignment` | `fred_{series_id}`, `yield_spread_{s1}_{s2}` |
| `cftc_cot` | `report` | `alignment` | `cot_{report}_net_pos`, `cot_{report}_net_pct` |
| `economic_calendar` | `currencies` | `min_impact`, `alignment` | `calendar_{currency}` |
| `sentiment` | `broker` | `alignment` | `sentiment_{broker}_{symbol}` |

### Data Flow Per Provider

```
IB:       config.symbol → IbDataProvider.fetch() → OHLCV DataFrame → align → indicators
FRED:     config.series → HTTP GET FRED API → value DataFrame → align → indicators
CFTC:     config.report → cot_reports lib → position DataFrame → percentile → align → indicators
Calendar: config.currencies → Finnhub API → events → compute features → hourly DataFrame
Sentiment: config.broker → Myfxbook API → ratio DataFrame → align → indicators
```

### Alignment Rules

```
Source frequency → Primary timeframe:
  hourly → hourly:   direct join (same frequency)
  daily → hourly:    forward-fill (1 value → ~24 bars)
  weekly → hourly:   forward-fill (1 value → ~168 bars)
  event → hourly:    pre-compute countdown features at each hourly bar
```
