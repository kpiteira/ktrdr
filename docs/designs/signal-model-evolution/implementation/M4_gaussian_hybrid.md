---
design: docs/designs/signal-model-evolution/DESIGN.md
---

# M4: Gaussian MFs + Hybrid Encoding

**Phase:** 2 — Fix the Features (Layer 2) — CRITICAL
**Dependencies:** None (can run in parallel with M1 and M2)
**Branch:** `impl/sme-M4-gaussian-hybrid`

---

## Task 4.1: NNInputSpec Extension for Raw Indicators

**File(s):** `ktrdr/config/models.py`, `ktrdr/config/feature_resolver.py`
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Extend `NNInputSpec` to support raw indicator values alongside fuzzy set memberships. Currently `NNInputSpec` only has `fuzzy_set: str` — add a `raw_indicator` alternative. The feature resolver must handle both types and produce `ResolvedFeature` objects for raw indicators.

**Implementation Notes:**
- Current `NNInputSpec` (models.py:751-758):
  ```python
  class NNInputSpec(BaseModel):
      fuzzy_set: str = Field(..., description="fuzzy_set_id to include")
      timeframes: Union[list[str], str] = Field(...)
  ```
- Change to support either fuzzy_set OR raw_indicator (mutually exclusive):
  ```python
  class NNInputSpec(BaseModel):
      fuzzy_set: Optional[str] = Field(None, description="fuzzy_set_id to include")
      raw_indicator: Optional[str] = Field(None, description="indicator_id for raw values")
      timeframes: Union[list[str], str] = Field(...)
      normalization: Optional[str] = Field(None, description="minmax, zscore, or none")

      @model_validator(mode="after")
      def exactly_one_input_type(self):
          if self.fuzzy_set and self.raw_indicator:
              raise ValueError("Specify either fuzzy_set or raw_indicator, not both")
          if not self.fuzzy_set and not self.raw_indicator:
              raise ValueError("Must specify either fuzzy_set or raw_indicator")
          return self
  ```
- In `FeatureResolver.resolve()` (feature_resolver.py:76), add handling for raw_indicator:
  ```python
  for nn_input in config.nn_inputs:
      if nn_input.fuzzy_set:
          # existing fuzzy path
      elif nn_input.raw_indicator:
          # new raw path
          indicator_id = nn_input.raw_indicator
          # Handle dot notation for multi-output
          for tf in expanded_timeframes:
              features.append(ResolvedFeature(
                  feature_id=f"{tf}_{indicator_id}_raw",
                  timeframe=tf,
                  fuzzy_set_id="__raw__",    # sentinel for raw features
                  membership_name="raw",
                  indicator_id=base_indicator_id,
                  indicator_output=output_name,
              ))
  ```
- `ResolvedFeature` with `fuzzy_set_id="__raw__"` signals downstream processors to use raw indicator values

**Testing Requirements:**
- [ ] Test NNInputSpec with `raw_indicator` field parses correctly
- [ ] Test NNInputSpec validation: cannot have both `fuzzy_set` and `raw_indicator`
- [ ] Test NNInputSpec validation: must have one of the two
- [ ] Test FeatureResolver resolves raw_indicator specs into ResolvedFeature objects
- [ ] Test raw feature IDs have correct format: `{tf}_{indicator_id}_raw`
- [ ] Test mixed nn_inputs (some fuzzy, some raw) resolve correctly with preserved order
- [ ] Test multi-output raw indicators with dot notation: `raw_indicator: macd.line`
- [ ] Test `timeframes: all` expansion works for raw indicators
- [ ] Test backward compat: existing configs with only `fuzzy_set` entries work unchanged

**Acceptance Criteria:**
- [ ] NNInputSpec supports both `fuzzy_set` and `raw_indicator` (mutually exclusive)
- [ ] FeatureResolver produces ResolvedFeature for raw indicators
- [ ] Feature ordering is preserved: nn_inputs order → timeframes order
- [ ] Existing strategy YAMLs with only fuzzy inputs continue to work

---

## Task 4.2: Hybrid Encoding in FuzzyNeuralProcessor

**File(s):** `ktrdr/training/fuzzy_neural_processor.py`
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Extend `FuzzyNeuralProcessor` to include raw normalized indicator values alongside fuzzy memberships in the feature tensor. When the resolved features include `__raw__` entries, the processor should extract the corresponding indicator column, normalize it, and concatenate it with the fuzzy features.

**Implementation Notes:**
- The processor currently extracts fuzzy columns from the DataFrame: columns matching `{fuzzy_set_id}_{membership_name}` pattern
- For raw features (`fuzzy_set_id == "__raw__"`), extract the indicator column directly from the indicator DataFrame (not the fuzzy DataFrame)
- This means the processor needs access to BOTH raw indicator values and fuzzy memberships — may need to pass both DataFrames
- Normalization for raw features:
  - `minmax`: `(x - x.min()) / (x.max() - x.min())` — compute on training data, store params
  - `zscore`: `(x - x.mean()) / x.std()` — compute on training data, store params
  - `none`: pass through as-is (e.g., RSI is already 0-100)
- Normalization parameters must be saved with model metadata for inference consistency
- Concatenate raw features at the position specified by nn_inputs order (interleaved with fuzzy, not appended at end)
- Multi-timeframe: raw features get timeframe prefix like fuzzy features

**Testing Requirements:**
- [ ] Test hybrid encoding: feature tensor contains both fuzzy and raw values
- [ ] Test feature ordering matches nn_inputs specification order
- [ ] Test minmax normalization produces values in [0, 1]
- [ ] Test zscore normalization produces values with mean≈0, std≈1
- [ ] Test normalization parameters are deterministic (same input → same output)
- [ ] Test with multi-timeframe data: raw features get timeframe prefix
- [ ] Test with NaN values in raw indicators: handled gracefully (0-fill or error)
- [ ] Test backward compat: processor with only fuzzy features (no raw) works unchanged

**Acceptance Criteria:**
- [ ] Feature tensor includes raw indicator values alongside fuzzy memberships
- [ ] Raw values are normalized using configurable method
- [ ] Feature ordering preserves nn_inputs specification order
- [ ] Normalization parameters are accessible for saving in model metadata

---

## Task 4.3: Gaussian MF Strategy Templates

**File(s):** Strategy YAML files (new)
**Type:** CODING
**Estimated time:** 1-2 hours

**Description:**
Create strategy YAML templates that use Gaussian MFs with 3 sets per indicator (replacing 2-set triangular), plus hybrid encoding with raw indicators. GaussianMF is already implemented in `ktrdr/fuzzy/membership.py` — this task verifies it works end-to-end through the fuzzy engine and creates production-ready configs.

**Implementation Notes:**
- GaussianMF is already registered in `MEMBERSHIP_REGISTRY` (auto-registration via `__init_subclass__`)
- `FuzzySetDefinition.expand_shorthand()` handles `{type: "gaussian", parameters: [mean, sigma]}` — this is the full form, no shorthand needed
- Create `trend_tb_gaussian_signal_v1.yaml` with:
  ```yaml
  fuzzy_sets:
    rsi_momentum:
      indicator: rsi_14
      low:
        type: gaussian
        parameters: [30, 15]      # μ=30, σ=15
      neutral:
        type: gaussian
        parameters: [50, 12]
      high:
        type: gaussian
        parameters: [70, 15]
    adx_trend:
      indicator: adx_14
      weak:
        type: gaussian
        parameters: [15, 10]
      moderate:
        type: gaussian
        parameters: [30, 10]
      strong:
        type: gaussian
        parameters: [50, 15]
    # ... similar for MACD, ROC

  nn_inputs:
    - fuzzy_set: rsi_momentum
      timeframes: all
    - raw_indicator: rsi_14        # hybrid: raw + fuzzy
      timeframes: all
      normalization: minmax
    - fuzzy_set: adx_trend
      timeframes: all
    - raw_indicator: adx_14
      timeframes: all
      normalization: minmax
    # ... etc
  ```
- Parameters for Gaussian centers: roughly based on typical indicator ranges
  - RSI: low=30, neutral=50, high=70 (standard oversold/neutral/overbought)
  - ADX: weak=15, moderate=30, strong=50 (trend strength levels)
  - MACD: use data-driven percentiles (MACD has no fixed range)
- Sigma values: wide enough that no dead zones exist (neighboring Gaussians overlap significantly)

**Testing Requirements:**
- [ ] YAML parses correctly via `StrategyConfigurationV3`
- [ ] Fuzzy engine processes Gaussian MFs without errors
- [ ] Dead zone check: fuzzify RSI values across full 0-100 range, verify NO values produce all-zero memberships
- [ ] Ruspini check: for each RSI value, sum of memberships across 3 sets ≈ 1.0 (for Gaussian, won't be exact — that's OK)
- [ ] Strategy validation passes

**Acceptance Criteria:**
- [ ] Strategy YAMLs with Gaussian MFs and hybrid encoding are valid
- [ ] Zero dead zones: every indicator value produces non-zero membership in at least one set
- [ ] Templates ready for use in M5 validation experiments

---

## Task 4.4: FeatureCache Support for Raw Indicators

**File(s):** `ktrdr/backtesting/feature_cache.py`
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Extend `FeatureCache` (the backtest-path feature provider) to serve raw indicator values alongside fuzzy memberships. The training path uses `FuzzyNeuralProcessor` but the backtest path uses `FeatureCache` for per-bar feature lookup — both must produce the same features in the same order.

**Implementation Notes:**
- `FeatureCache` stores precomputed features as a dict-of-dicts: `{timestamp: {feature_name: value}}`
- Currently only stores fuzzy membership values
- Need to also store raw indicator values when resolved features include `__raw__` entries
- The raw indicator column name in the DataFrame follows the pattern `{indicator_id}` or `{indicator_id}.{output}` for multi-output
- Normalization must use the SAME parameters as training (stored in model metadata) — not recomputed on backtest data
- Feature key must match the `ResolvedFeature.feature_id` exactly (e.g., `1h_rsi_14_raw`)
- Verify feature order matches training order by validating against `model.metadata.resolved_features`

**Testing Requirements:**
- [ ] Test FeatureCache stores raw indicator values alongside fuzzy
- [ ] Test per-bar lookup returns raw values with correct keys
- [ ] Test normalization uses stored parameters (not recomputed)
- [ ] Test feature order matches resolved_features from model metadata
- [ ] Test backward compat: models without raw features still work
- [ ] Test multi-timeframe: raw features for each timeframe stored correctly

**Acceptance Criteria:**
- [ ] FeatureCache serves raw + fuzzy features for backtest
- [ ] Normalization is consistent between training and backtest
- [ ] Feature order matches training (critical for correct inference)

---

## Task 4.5: Validation — Dead Zone Elimination

**File(s):** N/A (validation task)
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Validate that Gaussian MFs + hybrid encoding eliminate dead zones. This directly addresses the critical Layer 2 problem: 5.1 of 8 features at zero on average.

**Validation Steps:**
1. Load the `ke2e` skill before designing validation
2. Use `ke2e-test-scout` to search for existing dead-zone or fuzzy encoding tests
3. Design a test (via `ke2e-test-designer` if needed) that:
   a. Loads EURUSD 1h data
   b. Computes fuzzy memberships with OLD config (2-set triangular) and NEW config (3-set Gaussian)
   c. Measures dead zone % per indicator: what fraction of bars have all-zero memberships
   d. Measures average features-at-zero per bar
   e. With hybrid encoding: verifies raw indicators are always non-zero (after normalization)
   f. Optionally trains a model with both encodings to measure activation differences
4. Execute via `ke2e-test-runner`

**Success Criteria (from Design Section 11 — Phase 2):**
- [ ] Zero dead-zone bars across all indicators (currently 39.8-99.7%)
- [ ] Average features-at-zero per bar drops from 5.1/8 to 0/N
- [ ] Ruspini partition approximately satisfied: membership sums ≈ 1.0 at every point
- [ ] Hybrid encoding provides non-zero features at every bar (raw values fill gaps)
