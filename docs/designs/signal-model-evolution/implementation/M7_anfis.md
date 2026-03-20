---
design: docs/designs/signal-model-evolution/DESIGN.md
---

# M7: Learnable MFs / ANFIS

**Phase:** 4 — Optional Enhancement Layer
**Dependencies:** M5 (Combined Validation) — requires Gaussian MFs working; optionally enhanced by M6
**Branch:** `impl/sme-M7-anfis`

**JTBD:** *When I train signal models with Gaussian MFs, I want the MF parameters (μ, σ) to be learnable via backpropagation, so that the model discovers optimal market-structure boundaries instead of relying on my expert guesses — and I can inspect what it learned.*

---

## Task 7.1: LearnableFuzzyLayer

**File(s):** `ktrdr/neural/layers/learnable_fuzzy.py` (new), `ktrdr/neural/layers/__init__.py` (new)
**Type:** CODING
**Estimated time:** 3-4 hours

**Description:**
Create a PyTorch `nn.Module` that implements learnable Gaussian membership functions. Instead of fixed MF parameters (μ, σ) defined in YAML, the parameters become `nn.Parameter` tensors trained end-to-end alongside the NN weights via backpropagation.

**Implementation Notes:**
- The forward pass: `membership = exp(-(x - μ)² / (2σ²))` — fully differentiable
- For N indicators with K sets each: μ is shape `(N, K)`, σ is shape `(N, K)`
- Initialize from either:
  - `percentile`: compute 20th, 40th, 60th, 80th percentiles of training data
  - `expert`: use values from strategy YAML Gaussian MF definitions
  - `uniform`: evenly space across indicator range
- σ must be constrained to be positive: store `log_sigma` as the parameter, compute `sigma = exp(log_sigma)`
- Optional Ruspini enforcement via softmax: `normalized = softmax(raw_memberships, dim=-1)` — ensures sum=1 per indicator
- Optional ordered means constraint: `μ_sorted = cumsum(softplus(μ_deltas))` — prevents sets from crossing
- Output shape: `(batch_size, N * K)` — flattened memberships, same shape as fixed fuzzy output

```python
class LearnableFuzzyLayer(nn.Module):
    def __init__(
        self,
        num_indicators: int,
        num_sets: int = 4,
        init_centers: Optional[torch.Tensor] = None,  # shape (N, K)
        init_widths: Optional[torch.Tensor] = None,   # shape (N, K)
        ruspini: bool = True,
        ordered: bool = True,
    ):
        super().__init__()
        self.mu = nn.Parameter(init_centers or torch.randn(num_indicators, num_sets))
        self.log_sigma = nn.Parameter(init_widths_log or torch.zeros(num_indicators, num_sets))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x shape: (batch, num_indicators) → output shape: (batch, num_indicators * num_sets)"""
        sigma = torch.exp(self.log_sigma)
        # x: (batch, N) → (batch, N, 1) for broadcasting
        x_expanded = x.unsqueeze(-1)  # (batch, N, 1)
        # mu: (N, K) → (1, N, K) for broadcasting
        memberships = torch.exp(-0.5 * ((x_expanded - self.mu) / sigma) ** 2)  # (batch, N, K)
        if self.ruspini:
            memberships = F.softmax(memberships, dim=-1)
        return memberships.flatten(start_dim=1)  # (batch, N*K)
```

**Testing Requirements:**
- [ ] Test forward pass produces correct shape output
- [ ] Test Gaussian formula: known μ, σ, x → expected membership value
- [ ] Test gradients flow through μ and σ: `loss.backward()` updates parameters
- [ ] Test σ positivity constraint via log_sigma parameterization
- [ ] Test Ruspini enforcement: output sums to 1.0 per indicator
- [ ] Test ordered means constraint: μ values stay sorted
- [ ] Test percentile initialization from data
- [ ] Test expert initialization from YAML-like config
- [ ] Test output is compatible with downstream MLP layers (correct shape)
- [ ] Test with batch sizes 1, 32, 256

**Acceptance Criteria:**
- [ ] LearnableFuzzyLayer is a valid nn.Module with trainable μ and σ
- [ ] Forward pass is fully differentiable
- [ ] Ruspini enforcement and ordered means are optional
- [ ] Initialization from data percentiles or expert values

---

## Task 7.2: End-to-End Trainable Model

**File(s):** `ktrdr/neural/models/mlp.py`, `ktrdr/neural/layers/learnable_fuzzy.py`
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Integrate `LearnableFuzzyLayer` into `MLPTradingModel` so the fuzzy encoding and NN weights train jointly. When `learnable: true` is set in strategy config, the model replaces the fixed fuzzy encoding with a learnable layer.

**Implementation Notes:**
- The model architecture becomes:
  ```
  Raw indicators (N) → LearnableFuzzyLayer(N, K) → [N*K] → MLP hidden layers → Output
  ```
- In `build_model()`, if `learnable_fuzzy` config is present:
  1. Create `LearnableFuzzyLayer` as the first layer
  2. Input to MLP hidden layers is `N * K` (not the raw indicator count)
  3. Optionally concatenate raw indicators alongside learned fuzzy (hybrid)
- The FuzzyNeuralProcessor is bypassed when using learnable fuzzy — raw indicator values are passed directly to the model, and the model's internal fuzzy layer handles encoding
- This requires the training pipeline to pass raw indicator values instead of pre-fuzzified values
- Config:
  ```yaml
  model:
    type: mlp
    learnable_fuzzy:
      enabled: true
      num_sets: 4
      init_method: percentile   # or expert, uniform
      ruspini: true
      ordered: true
      include_raw: true          # hybrid: raw + learned fuzzy
  ```
- After training, learned MF parameters (μ, σ) are stored in the saved model and inspectable

**Testing Requirements:**
- [ ] Test end-to-end training: model with learnable fuzzy layer trains without errors
- [ ] Test gradients update both MF params and NN weights
- [ ] Test learned μ values differ from initialization after training
- [ ] Test model saves and loads with learnable fuzzy layer intact
- [ ] Test inference produces correct output shape
- [ ] Test hybrid mode: raw + learned fuzzy concatenated
- [ ] Test backward compat: `learnable_fuzzy.enabled: false` uses standard pipeline

**Acceptance Criteria:**
- [ ] MLPTradingModel supports learnable fuzzy layer as first layer
- [ ] Joint training of MF params + NN weights via single optimizer
- [ ] Learned parameters inspectable after training
- [ ] Hybrid mode (raw + learned fuzzy) supported

---

## Task 7.3: MF Parameter Inspection and Logging

**File(s):** `ktrdr/neural/layers/learnable_fuzzy.py` (extend)
**Type:** CODING
**Estimated time:** 1-2 hours

**Description:**
Add methods to inspect and log learned MF parameters after training. This enables the autoresearch agent to read what the model learned about market structure.

**Implementation Notes:**
- Add `get_learned_parameters() -> dict` to `LearnableFuzzyLayer`:
  ```python
  def get_learned_parameters(self, indicator_names: list[str]) -> dict:
      """Returns {indicator: {set_0: {mu: float, sigma: float}, ...}}"""
      mu = self.mu.detach().cpu().numpy()
      sigma = torch.exp(self.log_sigma).detach().cpu().numpy()
      return {
          ind_name: {
              f"set_{k}": {"mu": float(mu[i, k]), "sigma": float(sigma[i, k])}
              for k in range(mu.shape[1])
          }
          for i, ind_name in enumerate(indicator_names)
      }
  ```
- Add `compare_with_init(init_params) -> dict` that shows delta from initialization
- Store learned params in model metadata for reproducibility
- Log learned params at end of training: "RSI set_0: μ=28.3 (init: 30.0, Δ=-1.7), σ=17.2 (init: 15.0, Δ=+2.2)"

**Testing Requirements:**
- [ ] Test get_learned_parameters returns correct structure
- [ ] Test compare_with_init shows meaningful deltas
- [ ] Test learned params are included in model metadata after save
- [ ] Test logging output is readable and includes deltas from init

**Acceptance Criteria:**
- [ ] Learned MF parameters are inspectable programmatically
- [ ] Comparison with initialization values available
- [ ] Parameters stored in model metadata

---

## Task 7.4: Per-Regime Learnable MFs (Experiment 8)

**File(s):** `ktrdr/neural/layers/learnable_fuzzy.py` (extend)
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Support per-regime learnable MF parameters. Each regime (trending, ranging) may have different optimal market partitioning — the trend model's "oversold" center may differ from the range model's.

**Implementation Notes:**
- Since we already train separate per-regime signal models (trend_signal, range_signal), per-regime learnable MFs come naturally — each model has its own `LearnableFuzzyLayer` with independently trained parameters
- The interesting comparison is: do the learned parameters differ between regime models?
- This task is primarily about creating the experiment infrastructure:
  1. Train trend model with learnable MFs → inspect learned params
  2. Train range model with learnable MFs → inspect learned params
  3. Compare: do RSI μ/σ values differ between trend and range?
- Create a comparison utility that takes two sets of learned params and reports differences
- The hypothesis: trending regime should learn wider μ for momentum indicators, ranging should learn tighter μ for mean-reversion indicators

**Testing Requirements:**
- [ ] Test per-regime models train independently with learnable MFs
- [ ] Test comparison utility reports meaningful differences
- [ ] Test models with different learned MFs produce different inference results

**Acceptance Criteria:**
- [ ] Per-regime learnable MFs work (same mechanism, different model instances)
- [ ] Comparison utility available for experiment analysis
- [ ] Results documented for regime-specific MF specialization

---

## Task 7.5: Validation — ANFIS Impact (Experiments 7+8)

**File(s):** N/A (validation task)
**Type:** VALIDATION
**Estimated time:** 3 hours

**Description:**
Execute Design Experiments 7 and 8: Fixed vs Learnable MFs, and Per-Regime Learnable MFs. Validates that learnable MFs discover meaningful market structure beyond expert-defined parameters.

**Validation Steps:**
1. Load the `ke2e` skill before designing validation
2. Use `ke2e-test-scout` to search for existing tests covering learnable fuzzy, ANFIS, or MF parameter learning
3. If no match found, hand off to `ke2e-test-designer` to design a new test that:
   a. Starts the sandbox (`uv run kinfra sandbox up`)
   b. **Experiment 7**: Train two models via CLI on same EURUSD 1h data — one with `learnable_fuzzy.enabled: false` (fixed Gaussian), one with `learnable_fuzzy.enabled: true`. Compare val accuracy.
   c. **Experiment 8**: Train trend and range models both with learnable MFs. Inspect learned μ/σ parameters — do they differ between regimes?
   d. Stability check: train learnable MF model on 2020-2022 and 2021-2023, compare learned params
4. Execute the test via `ke2e-test-runner` against the real sandbox

**What "real E2E" means here:** Real training runs producing real model files with inspectable learned parameters. The test reads saved model metadata to compare μ/σ values against initialization — not synthetic parameter updates.

**Success Criteria (from Design Section 11 — Phase 4):**
- [ ] Learned MF parameters differ meaningfully from expert initialization
- [ ] Val accuracy improves vs fixed MFs (or at least matches — not worse)
- [ ] Learned MFs are stable across different training windows (not overfit artifacts)
- [ ] Per-regime MFs show interpretable specialization (trend ≠ range parameters)
