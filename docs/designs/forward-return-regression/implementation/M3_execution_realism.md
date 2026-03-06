---
design: docs/designs/forward-return-regression/DESIGN.md
architecture: docs/designs/forward-return-regression/ARCHITECTURE.md
---

# M3: Execution Realism

Fix look-ahead bias in the backtest engine. Decisions at bar t execute at bar t+1's open price. Applies to both regression and classification modes. Makes backtest results trustworthy.

## Task 3.1: BacktestEngine Next-Bar Execution

**File(s):** Modify `ktrdr/backtesting/engine.py`, create `tests/unit/backtesting/test_next_bar_execution.py`
**Type:** CODING

**Description:**
Change the backtest engine main loop so that trading decisions made at bar t are executed at bar t+1's open price, not bar t's close price. This fixes a documented look-ahead bias.

**Implementation Notes:**
- Current loop (`engine.py`, line ~205-222): decides and executes at same bar's close price
- New pattern: introduce `pending_signal` and `pending_metadata` variables
- At each bar:
  1. First, execute any pending signal from the previous bar at THIS bar's open price
  2. Then, decide based on current bar's features (at close)
  3. If decision is not HOLD, store as pending
  4. Track equity at close price (mark-to-market, unchanged)
- Edge case: last bar with a pending signal — the force-close at end-of-backtest handles this already (verify)
- Edge case: first bar — no pending signal, just decide
- This applies to BOTH regression and classification modes (D6)
- See ARCHITECTURE.md "BacktestEngine Changes" section for the full pattern

**Testing Requirements:**
- [ ] Decision at bar t executes at bar t+1's open price (not bar t's close)
- [ ] Pending signal correctly carried across bars
- [ ] HOLD decisions clear no pending signal (no carry)
- [ ] Last bar's pending signal handled correctly (force-close or execute)
- [ ] First bar has no pending signal
- [ ] Multiple consecutive non-HOLD signals: only the latest pending signal executes
- [ ] Mark-to-market equity tracking still uses close prices
- [ ] Existing position management logic (stop loss, take profit) works with open price execution

**Acceptance Criteria:**
- [ ] All trades execute at next bar's open, not current bar's close
- [ ] Backtest results are slightly worse than before (correct — removes positive bias)
- [ ] Both regression and classification modes use next-bar execution

---

## Task 3.2: Update Affected Tests

**File(s):** Modify existing backtest tests in `tests/unit/backtesting/`, `tests/integration/`
**Type:** CODING

**Description:**
Update all existing backtest tests that depend on same-bar execution to expect next-bar execution behavior.

**Implementation Notes:**
- Search for tests that assert trade execution prices — these will need updating
- Tests that check trade COUNT may not need changes (same decisions, just different prices)
- Tests that check P&L or equity curves WILL need updated expected values
- Key test files to check:
  - `tests/unit/backtesting/test_engine.py`
  - `tests/unit/backtesting/test_decision_function.py` (may not be affected — tests decisions, not execution)
  - `tests/integration/test_backtest_*.py`
- Pattern: where a test previously checked `trade.price == bar_close`, update to `trade.price == next_bar_open`
- Some test fixtures may need an extra bar of data to accommodate the shift

**Testing Requirements:**
- [ ] All existing backtest tests pass with next-bar execution
- [ ] No test disabled or skipped to make things pass
- [ ] Updated expected values are verified by hand for at least 2 tests

**Acceptance Criteria:**
- [ ] Full test suite passes (`make test-unit`)
- [ ] No test suppression or loosened assertions

---

## Task 3.3: Slippage Defaults Standardization

**File(s):** Modify `ktrdr/backtesting/engine.py`, modify `ktrdr/workers/backtest_worker.py`, modify backtest API endpoint
**Type:** CODING

**Description:**
Standardize slippage defaults across all backtest entry points. Currently three different defaults (see RESEARCH.md Section 6):
- BacktestConfig (engine.py): slippage=0.05%
- Backtest worker: slippage=0.0%
- API service: slippage=0.1%

Standardize to 0.05% everywhere.

**Implementation Notes:**
- `engine.py` BacktestConfig dataclass: slippage already 0.0005 (0.05%) — this is correct
- `backtest_worker.py`: find where slippage default is set to 0.0, change to 0.0005
- API endpoint: find where slippage default is 0.001 (0.1%), change to 0.0005
- Commission stays at 0.001 (0.1%) everywhere — only slippage varies
- This is a small change but important for result consistency across entry points

**Testing Requirements:**
- [ ] BacktestConfig default slippage is 0.0005
- [ ] Worker default slippage is 0.0005
- [ ] API default slippage is 0.0005
- [ ] Explicit slippage parameter still overrides default

**Acceptance Criteria:**
- [ ] Slippage default is 0.05% regardless of entry point
- [ ] Explicit user-provided slippage still works

---

## Task 3.4: E2E Validation

**File(s):** No new files — validation against running infrastructure
**Type:** VALIDATION

**Description:**
Validate M3 by running the same regression strategy before and after the look-ahead fix. The fix should produce worse (more realistic) results.

**Validation Steps:**
1. Load the `ke2e` skill before designing any validation
2. Invoke ke2e-test-scout with M3 validation requirements:
   - Train a regression strategy (reuse from M1 validation)
   - Backtest with current code (before M3 merge, or with a flag) — record results
   - Backtest with next-bar execution — record results
   - Compare: next-bar execution should show lower win rate and/or worse Sharpe
   - Verify trade execution prices match next bar's open (spot-check a few trades)
   - Verify slippage is consistent across CLI, API, and worker paths
3. Invoke ke2e-test-runner with identified test recipes

**Acceptance Criteria:**
- [ ] Next-bar execution produces measurably different (worse) results than same-bar
- [ ] Trade prices match next bar's open (verified by inspection)
- [ ] Slippage consistent across all entry points
- [ ] Regression strategy still produces meaningful trades (fix doesn't break everything)
- [ ] Classification backtest also works with next-bar execution
