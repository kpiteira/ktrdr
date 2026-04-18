# M4: ktrdr Integration

**Goal**: Add ktrdr ML directional signal as an optional input. When a signal is available, structure recommendation adapts to favor directional strategies.

**Success criteria**: `epa analyze AAPL` detects and uses a ktrdr signal file to shift recommendations toward directional structures (bull/bear spreads) instead of neutral ones (straddles/iron condors).

**Depends on**: M2 (structure selector), M3 (Opus reasoner prompt includes signal)

---

## Task 4.1: ktrdr Signal Adapter

**Files to create**:
- `epa/integrations/__init__.py`
- `epa/integrations/ktrdr.py` — `KtrdrAdapter` class, `KtrdrSignal` dataclass

**Behavior**:
- `KtrdrAdapter(signal_dir="~/.ktrdr/signals/")`
- `get_signal(ticker)` → `KtrdrSignal | None`
  - Reads `{signal_dir}/{TICKER}.json`
  - Expected format: `{ "signal": "BUY", "confidence": 0.73, "timestamp": "2026-04-18T14:30:00Z", "model_version": "v2.1" }`
  - Returns `None` if: file doesn't exist, file is malformed, signal is stale (>24h old)
  - Staleness threshold configurable via config
- `is_available()` → `bool` — checks if signal directory exists

**Tests**:
- `test_ktrdr.py`:
  - Valid signal file → parsed correctly
  - Missing file → None
  - Stale signal (>24h) → None
  - Malformed JSON → None with logged warning
  - Signal directory doesn't exist → is_available() = False

**Fixture files**:
- `epa/tests/fixtures/sample_signal.json`

---

## Task 4.2: Structure Selector Directional Logic

**Files to modify**:
- `epa/analysis/structures.py` — enhance `select_candidates()` with signal-aware scoring

**Behavior changes**:
- When `signal` is provided:
  - BUY signal: boost score of bull call spread and bull put spread by `signal.confidence * 0.3`
  - SELL signal: boost score of bear put spread and bear call spread by `signal.confidence * 0.3`
  - HOLD signal: treated same as no signal (neutral structures)
- When `signal.confidence > 0.8`: add directional vertical spread as a standalone candidate (not just straddle/strangle + directional adjustment)
- When `signal.confidence < 0.4`: treat as no signal (too weak to act on)
- Rationale string updated to explain signal influence

**Tests**:
- `test_structures_directional.py`:
  - BUY signal with high confidence → bull spread ranks #1
  - SELL signal with high confidence → bear spread ranks #1
  - Low confidence signal → same ranking as no signal
  - HOLD signal → same ranking as no signal
  - Signal + short_vol edge → careful handling (directional + IV crush is tricky)

---

## Task 4.3: Orchestrator + Opus Prompt Update

**Files to modify**:
- `epa/orchestrator.py` — add ktrdr adapter call
- `epa/reasoner/prompts.py` — add signal data section to prompt
- `epa/cli.py` — add `--signal` manual override, display signal info in output

**Behavior**:
- Orchestrator checks ktrdr adapter before analysis
- If signal found: passes to structure selector and Opus reasoner
- CLI `--signal BUY:0.73` allows manual override (useful when ktrdr not running)
- Output includes signal section:
  ```
  ktrdr Signal: BUY (confidence: 0.73, model: v2.1, age: 2h)
  ```
  or:
  ```
  ktrdr Signal: unavailable (no signal file found)
  ```

- Opus prompt updated:
  - Includes signal data in structured input
  - Asks Opus to evaluate whether the signal aligns with other indicators
  - If signal conflicts with edge direction, Opus should flag the tension

**Tests**:
- `test_orchestrator_ktrdr.py`:
  - Signal available → passed to analysis and reasoner
  - Signal unavailable → analysis proceeds without, output notes absence
  - Manual override via CLI → used instead of file
  - Signal + conflicting edge → Opus receives both, can reason about conflict

---

## Task 4.4: M4 Validation

**Files to create**:
- `epa/tests/test_m4_e2e.py`

**Test cases**:
1. Place a signal file, run analysis → recommendation reflects directional view
2. Remove signal file, run same analysis → recommendation is neutral
3. Manual `--signal SELL:0.9` → bear spread recommended
4. Stale signal file (>24h old) → treated as unavailable
5. Signal conflicts with edge → output acknowledges tension

**Validation script** (manual):
```bash
# Create test signal
mkdir -p ~/.ktrdr/signals
echo '{"signal":"BUY","confidence":0.73,"timestamp":"2026-04-18T10:00:00Z","model_version":"v2.1"}' > ~/.ktrdr/signals/AAPL.json

epa analyze AAPL --budget 65000           # Should show BUY signal, may recommend bull spread
rm ~/.ktrdr/signals/AAPL.json
epa analyze AAPL --budget 65000           # Should show "signal unavailable"
epa analyze AAPL --signal SELL:0.9        # Manual override
```

**Done when**: ktrdr signal is seamlessly integrated — used when available, gracefully absent when not, and its influence on the recommendation is clearly explained in the output.
