# Milestone 1: Kronos Vol Regime Classifier

---

## A. Objective

Train and validate a linear classifier head on frozen Kronos-mini (4.1M params, 256-dim) embeddings that classifies the current market volatility regime as SELL_VOL, BUY_VOL, or NEUTRAL. This milestone proves or disproves the central hypothesis: that Kronos hidden states encode vol-relevant information extractable by a simple linear probe. AUC > 0.60 on held-out 2023 test data is the mandatory gate — if it fails, the system falls back to a rule-based IV rank heuristic, and Kronos integration is deprioritized.

---

## B. Go/No-Go Gate (from previous milestone)

**Entry gate**: None — this is the first milestone.

**Prerequisites**:
- Python 3.12 environment with PyTorch available
- Internet access for HuggingFace model download and yfinance data fetch
- Sufficient disk space for Kronos-mini weights (~50MB) and embedding cache (~100MB)

---

## C. Files to Create (proposed paths)

| # | File Path | Purpose | Key Classes/Functions |
|---|-----------|---------|----------------------|
| 1 | `ktrdr-options/pyproject.toml` | Python package definition, dependencies | N/A (config) |
| 2 | `ktrdr-options/ktrdr_options/__init__.py` | Package init | Version string |
| 3 | `ktrdr-options/ktrdr_options/signals/__init__.py` | Signals subpackage init | Exports |
| 4 | `ktrdr-options/ktrdr_options/signals/kronos_classifier.py` | Kronos vol regime classifier | `KronosVolClassifier`, `VolRegimeSignal`, `REGIME_LABELS` |
| 5 | `ktrdr-options/ktrdr_options/data/__init__.py` | Data subpackage init | Exports |
| 6 | `ktrdr-options/ktrdr_options/data/label_builder.py` | Vol regime label construction pipeline | `build_vol_regime_labels()`, `compute_iv_rank_rolling()`, `compute_realized_vol()`, `download_spy_ohlcv()`, `download_vix_history()` |
| 7 | `ktrdr-options/ktrdr_options/train_classifier.py` | CLI: train and evaluate classifier | `main()`, `train()`, `evaluate()`, `generate_report()` |
| 8 | `ktrdr-options/tests/__init__.py` | Test package init | N/A |
| 9 | `ktrdr-options/tests/test_kronos_classifier.py` | Unit tests for classifier | `TestKronosVolClassifier` |
| 10 | `ktrdr-options/tests/test_label_builder.py` | Unit tests for label construction | `TestLabelBuilder` |

---

## D. Files to Modify (in ktrdr repo)

None. Milestone 1 does not require any changes to the ktrdr codebase. The options classifier is a standalone component.

---

## E. Implementation Tasks

### Task 1: Set up `ktrdr-options` Python package structure
- Create `ktrdr-options/pyproject.toml` with dependencies: `torch>=2.0`, `einops==0.8.1`, `huggingface_hub>=0.20`, `safetensors>=0.4`, `yfinance>=0.2`, `scikit-learn>=1.3`, `pandas>=2.0`, `numpy>=1.24`
- Create package directories: `ktrdr_options/`, `ktrdr_options/signals/`, `ktrdr_options/data/`, `tests/`
- Create `__init__.py` files with appropriate exports
- Verify: `pip install -e ktrdr-options/` succeeds and `import ktrdr_options` works
- **Test**: `python -c "import ktrdr_options; print(ktrdr_options.__version__)"` succeeds

### Task 2: Download and validate Kronos-mini from HuggingFace
- In `KronosVolClassifier.__init__()`: accept `kronos_model_name="NeoQuasar/Kronos-mini"` and `tokenizer_name="NeoQuasar/Kronos-Tokenizer-2k"`
- In `KronosVolClassifier.load_model()`:
  - Download model weights via `huggingface_hub.hf_hub_download()` or direct model loading
  - Load Kronos-mini model with frozen weights (`requires_grad_(False)`)
  - Load KronosTokenizer
  - Verify model has expected embedding dimension (256)
  - Set `self._is_loaded = True`
- Handle errors: `FileNotFoundError` if no internet, `RuntimeError` if weights corrupted
- **Test**: Load model, verify `sum(p.numel() for p in model.parameters())` matches expected ~4.1M params, verify all params have `requires_grad=False`

### Task 3: Implement `KronosVolClassifier.extract_embedding()`
- **File**: `ktrdr_options/signals/kronos_classifier.py`
- **Method**: `extract_embedding(self, ohlcv: pd.DataFrame) -> torch.Tensor`
- Input: `pd.DataFrame` with OHLCV columns, at least 50 rows, uses last 512 rows if longer
- Process:
  1. Validate input columns: `[open, high, low, close, volume]`
  2. Tokenize OHLCV via KronosTokenizer
  3. Forward pass through frozen Kronos-mini: `with torch.no_grad():`
  4. Extract hidden states: shape `(batch, seq_len, 256)`
  5. Pool according to `self._pooling`:
     - `"last"`: take `hidden_states[:, -1, :]` → shape `(1, 256)`
     - `"mean"`: take `hidden_states.mean(dim=1)` → shape `(1, 256)`
- Output: `torch.Tensor` shape `(1, 256)`
- **Test**: Assert output shape `(1, 256)`, assert weights don't change after call (`torch.equal` on params before/after), assert deterministic output for same input (run twice, compare)

### Task 4: Implement `KronosVolClassifier.extract_embeddings_batched()`
- **File**: `ktrdr_options/signals/kronos_classifier.py`
- **Method**: `extract_embeddings_batched(self, ohlcv: pd.DataFrame, window_size: int = 512, stride: int = 1) -> torch.Tensor`
- Sliding window over full historical OHLCV DataFrame
- For each window position `i` from `window_size` to `len(ohlcv)` with step `stride`:
  - Extract `ohlcv[i-window_size:i]`
  - Call `extract_embedding()` (or batch multiple windows for efficiency)
- Output: `torch.Tensor` shape `(num_windows, 256)`
- Save progress periodically (every 100 windows) to allow resume on interruption
- **Test**: Given 1000-row DataFrame with window_size=512, stride=1: assert output shape `(489, 256)`. Assert output is deterministic.

### Task 5: Build the label construction pipeline
- **File**: `ktrdr_options/data/label_builder.py`
- **Function**: `download_spy_ohlcv(start: str, end: str) -> pd.DataFrame`
  - Download SPY daily OHLCV from yfinance
  - Return DataFrame with DatetimeIndex, columns `[open, high, low, close, volume]`
- **Function**: `download_vix_history(start: str, end: str) -> pd.Series`
  - Download VIX daily close from yfinance (`^VIX`)
  - Return Series with DatetimeIndex
- **Function**: `compute_iv_rank_rolling(iv_series: pd.Series, lookback: int = 252) -> pd.Series`
  - For each date, compute percentile rank of current IV within trailing 252-day window
  - Return Series with values 0-100
- **Function**: `compute_realized_vol(prices: pd.Series, window: int = 20) -> pd.Series`
  - `log_returns.rolling(window).std() * sqrt(252)`
  - Return annualized RV series
- **Function**: `build_vol_regime_labels(iv_series, prices, iv_rank_high=70, iv_rank_low=30, rv_discount=0.85, rv_premium=1.15, forward_window=20) -> pd.Series`
  - Compute IV rank from `iv_series`
  - Compute forward realized vol from `prices` (shifted by `-forward_window`)
  - Assign labels: 0=NEUTRAL, 1=SELL_VOL, 2=BUY_VOL per Design Sec. 3 rules
  - Drop last `forward_window` rows (no future data available)
  - Return integer Series
- **Test**: 
  - `compute_iv_rank_rolling`: given synthetic IV series [10, 20, 30], verify ranks are correct
  - `compute_realized_vol`: given constant prices, verify RV = 0
  - `build_vol_regime_labels`: verify no look-ahead bias (label at time t only uses prices up to t for IV rank, and forward prices for RV), verify label distribution is reasonable (expect 55-75% NEUTRAL)

### Task 6: Pre-compute and cache all Kronos embeddings
- **File**: `ktrdr_options/train_classifier.py` (or callable from it)
- Download SPY OHLCV 2022-01-01 to 2024-01-01 (via `download_spy_ohlcv()`)
- Call `KronosVolClassifier.extract_embeddings_batched()` on full dataset
- Save embeddings to `cache/kronos/SPY_1d_embeddings.pt`
- Save metadata: `{symbol, timeframe, start_date, end_date, window_size, stride, num_embeddings, embedding_dim}`
- Log progress: "Extracting embeddings: {i}/{total}"
- `[VALIDATE EMPIRICALLY]`: Measure CPU inference latency per window (expected ~100-500ms)
- **Test**: Load saved `.pt` file, verify shape matches expected `(num_windows, 256)`, verify metadata matches

### Task 7: Train `Linear(256 -> 3)` classifier head
- **File**: `ktrdr_options/signals/kronos_classifier.py`
- **Method**: `KronosVolClassifier.train_classifier(embeddings, labels, val_embeddings, val_labels, epochs=100, lr=0.001, class_weights=[1.0, 2.0, 2.5])`
- Initialize `nn.Linear(256, 3)` classifier head
- Optimizer: Adam with `lr=0.001`
- Loss: `nn.CrossEntropyLoss(weight=torch.tensor([1.0, 2.0, 2.5]))` — upweight rare SELL_VOL and BUY_VOL classes
- Training loop:
  1. Forward pass: `logits = self._classifier(embeddings)`
  2. Compute loss
  3. Backward + step
  4. Every epoch: compute validation loss and AUC
  5. Early stopping: patience=10 epochs on val loss
- Chronological train/val/test split: train=2022, val=Jan-Jun 2023, test=Jul-Dec 2023
- Return dict: `{"train_loss", "val_loss", "val_auc", "val_accuracy", "per_class_precision", "per_class_recall"}`
- **Test**: Train on synthetic embeddings (random) with known labels. Verify loss decreases over epochs. Verify early stopping triggers when val loss plateaus.

### Task 8: Evaluate classifier — AUC, confusion matrix, label distribution
- **File**: `ktrdr_options/train_classifier.py`
- **Function**: `evaluate(classifier, test_embeddings, test_labels) -> dict`
- Compute:
  - AUC per class (one-vs-rest) using `sklearn.metrics.roc_auc_score` with `multi_class="ovr"`
  - Macro-averaged AUC
  - Confusion matrix via `sklearn.metrics.confusion_matrix`
  - Per-class precision and recall
  - Label distribution: count and percentage per class
- Compare against IV rank heuristic baseline: compute same metrics using `iv_rank > 70 = SELL_VOL, < 30 = BUY_VOL, else NEUTRAL`
- Print formatted report to stdout
- **Test**: Given perfect predictions, verify AUC = 1.0. Given random predictions, verify AUC ~ 0.50.
- **`[VALIDATE EMPIRICALLY]`**: The AUC > 0.60 gate is checked here.

### Task 9: Implement `KronosVolClassifier.predict()` with IV rank heuristic fallback
- **File**: `ktrdr_options/signals/kronos_classifier.py`
- **Method**: `predict(self, ohlcv: pd.DataFrame, iv_rank: float, timestamp: str | None = None) -> VolRegimeSignal`
- If classifier is loaded (`self._classifier` weights loaded):
  1. Call `extract_embedding(ohlcv)` → embedding
  2. Forward through classifier: `logits = self._classifier(embedding)`
  3. Softmax → probabilities: `{"SELL_VOL": float, "BUY_VOL": float, "NEUTRAL": float}`
  4. `regime = REGIME_LABELS[argmax]`, `confidence = max(probabilities)`
- If classifier NOT loaded (fallback):
  - `regime = "SELL_VOL" if iv_rank > 70 else "BUY_VOL" if iv_rank < 30 else "NEUTRAL"`
  - `confidence = 0.6` (fixed — heuristic has no calibrated confidence)
  - `probabilities` set accordingly
- Return `VolRegimeSignal(regime, confidence, probabilities, iv_rank, timestamp)`
- **Test**: With trained classifier, verify output regime matches expected for known embedding. Verify fallback works when `classifier_weights_path=None`. Verify timestamp defaults to current time.

### Task 10: Implement persistence — save/load classifier head weights
- **File**: `ktrdr_options/signals/kronos_classifier.py`
- **Method**: `save_classifier(self, path: str) -> None`
  - Save `self._classifier.state_dict()` to `{path}/head.pt`
  - Save config to `{path}/config.json`: `{embedding_dim, num_classes, pooling, kronos_model_name}`
- **Method**: `load_classifier(self, path: str) -> None`
  - Load config from `{path}/config.json`
  - Verify `embedding_dim` matches
  - Load `self._classifier.load_state_dict()` from `{path}/head.pt`
- **Test**: Save classifier, load into new instance, verify predictions match original on same input.

### Task 11: Write CLI entry point
- **File**: `ktrdr_options/train_classifier.py`
- **Function**: `main()`
- CLI: `python -m ktrdr_options.train_classifier --symbol SPY --start 2022-01-01 --end 2024-01-01 [--pooling last|mean] [--output-dir models/kronos_classifier]`
- Full pipeline:
  1. Download OHLCV and VIX data
  2. Build labels
  3. Load/compute Kronos embeddings (with caching)
  4. Split chronologically: train/val/test
  5. Train classifier
  6. Evaluate on test set
  7. Print report with AUC, confusion matrix, comparison to IV rank baseline
  8. Save classifier weights if AUC > 0.60
  9. Exit with code 0 if AUC > 0.60, code 1 otherwise
- **Test**: Run CLI end-to-end with `--start 2023-01-01 --end 2023-06-01` (small dataset for speed). Verify it produces output files and prints evaluation report.

---

## F. Acceptance Criteria

### Unit Tests
- [ ] `KronosVolClassifier.load_model()` successfully loads Kronos-mini, all 4.1M params frozen
- [ ] `extract_embedding()` produces deterministic `(1, 256)` tensor for same input
- [ ] `extract_embedding()` does not modify Kronos model weights
- [ ] `extract_embeddings_batched()` produces correct shape for given input length and stride
- [ ] `train_classifier()` reduces training loss over epochs
- [ ] `train_classifier()` triggers early stopping when validation loss plateaus
- [ ] `predict()` returns valid `VolRegimeSignal` with correct fields
- [ ] `predict()` falls back to IV rank heuristic when classifier weights not loaded
- [ ] `save_classifier()` / `load_classifier()` round-trips correctly
- [ ] `build_vol_regime_labels()` produces no NaN values (after dropping forward window)
- [ ] `build_vol_regime_labels()` label distribution has NEUTRAL as majority class
- [ ] `compute_iv_rank_rolling()` returns values in 0-100 range

### Integration Tests
- [ ] Full pipeline: download data → build labels → compute embeddings → train → evaluate runs end-to-end
- [ ] CLI `python -m ktrdr_options.train_classifier` executes without error
- [ ] Saved classifier weights can be loaded in a fresh Python process and produce predictions

### Empirical Validation Gates
- [ ] **`[VALIDATE EMPIRICALLY]`** AUC > 0.60 on held-out test set (Jul-Dec 2023 data)
- [ ] **`[VALIDATE EMPIRICALLY]`** Kronos classifier beats IV rank heuristic baseline on AUC
- [ ] **`[VALIDATE EMPIRICALLY]`** Per-class precision > 0.40 for both SELL_VOL and BUY_VOL
- [ ] **`[VALIDATE EMPIRICALLY]`** Kronos-mini CPU inference latency < 1s per window

### Performance Requirements
- [ ] Embedding extraction: < 1 second per window on CPU
- [ ] Full training pipeline (2 years SPY data): < 30 minutes total
- [ ] Classifier inference (single prediction): < 10ms (after embedding extraction)

---

## G. Estimated Effort

**8 developer-days**

| Task | Days |
|------|------|
| Package setup (Task 1) | 0.5 |
| Kronos model loading (Task 2) | 1.0 |
| Embedding extraction (Tasks 3-4) | 1.5 |
| Label construction pipeline (Task 5) | 1.0 |
| Pre-compute + cache embeddings (Task 6) | 0.5 |
| Classifier training (Task 7) | 1.0 |
| Evaluation + reporting (Task 8) | 1.0 |
| Predict + fallback (Task 9) | 0.5 |
| Persistence + CLI (Tasks 10-11) | 1.0 |

The Kronos model integration (Tasks 2-4) has the most uncertainty — the Kronos API surface may require adaptation. Budget extra time here.

---

## H. Open Questions / Risks

1. **`[VALIDATE EMPIRICALLY]`** Does mean pooling outperform last hidden state? Test both during Task 7 — run training twice with different `pooling` parameter, compare AUC. Default to last hidden state.

2. **`[VALIDATE EMPIRICALLY]`** Does Kronos-small (512-dim) improve AUC enough to justify the extra compute? Only test if Kronos-mini AUC is 0.55-0.60 (borderline).

3. **Kronos API surface**: The Kronos model loading code path needs investigation. The model is on HuggingFace at `NeoQuasar/Kronos-mini`, but the exact Python API for loading and running inference must be validated against the Kronos codebase. The `spec.md` should document this, but verify empirically.

4. **Label quality**: The SELL_VOL/BUY_VOL labels are constructed from the VIX-to-realized-vol relationship. For SPY this is clean (VIX IS the SPY implied vol). For single names, the label quality will be lower. M1 only uses SPY — defer single-name label quality to future work.

5. **Class imbalance**: Expected 55-75% NEUTRAL. The class weights `[1.0, 2.0, 2.5]` are a starting point. If SELL_VOL or BUY_VOL classes have < 10% prevalence, consider focal loss or oversampling.

6. **`[VALIDATE EMPIRICALLY]`** Forward RV window: the design uses 20 days. Test 10, 15, 20, 30 during label construction to find the window that maximizes AUC.

7. **Data availability**: yfinance VIX data must cover the full training period (2022-2024). If yfinance rate-limits or returns gaps, cache data locally after first download.
