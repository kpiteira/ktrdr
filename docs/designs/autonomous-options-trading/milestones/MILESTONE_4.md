# Milestone 4: Live/Paper Infrastructure (No IBKR Yet)

---

## A. Objective

Build the live analysis pipeline: ktrdr HTTP client for real-time signal fetching, Opus 4.7 strategy advisor with structured prompting and fallback logic, and the LuxOrchestrator that ties everything together in a scheduled analysis cycle. This milestone validates that the full analysis loop (fetch signals → aggregate → advise → log → notify) runs cleanly end-to-end in under 90 seconds, with proper SQLite persistence and Telegram notifications. No trade execution occurs — this is analysis-only mode.

---

## B. Go/No-Go Gate (from previous milestone)

**Entry gate from M3**:
- [ ] Synthetic backtest Sharpe > 0.50 on 2022-2024 SPY data
- [ ] >= 50 trades produced in backtest
- [ ] Max drawdown < 25%
- [ ] All backtest trades and metrics persisted to SQLite
- [ ] `OptionsDecisionMatrix`, `OptionsPositionManager`, `SignalAggregator` fully tested and working
- [ ] `BlackScholesEngine` validated and tested

**Additional prerequisites**:
- [ ] ktrdr REST API server can be started and responds to health check
- [ ] Anthropic API key available (env var: `ANTHROPIC_API_KEY`)
- [ ] Telegram bot token and chat ID configured (env vars: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`)

---

## C. Files to Create (proposed paths)

| # | File Path | Purpose | Key Classes/Functions |
|---|-----------|---------|----------------------|
| 1 | `ktrdr-options/ktrdr_options/signals/ktrdr_client.py` | Async HTTP client for ktrdr REST API | `KtrdrSignalClient`, `KtrdrSignal`, `KtrdrAPIError`, `KtrdrStaleDataError` |
| 2 | `ktrdr-options/ktrdr_options/strategy/opus_advisor.py` | Opus 4.7 strategy advisor with fallback | `OpusStrategyAdvisor`, `TradeRecommendation`, `OptionsLeg`, `ExitPlan` |
| 3 | `ktrdr-options/ktrdr_options/orchestrator.py` | Main analysis/trading loop | `LuxOrchestrator`, `CycleResult` |
| 4 | `ktrdr-options/ktrdr_options/strategy/opus_prompt.py` | Opus 4.7 prompt template and JSON schema | `build_opus_prompt()`, `OPUS_SYSTEM_PROMPT`, `TRADE_RECOMMENDATION_SCHEMA` |
| 5 | `ktrdr-options/tests/test_ktrdr_client.py` | ktrdr client tests with mock HTTP | `TestKtrdrSignalClient` |
| 6 | `ktrdr-options/tests/test_opus_advisor.py` | Opus advisor tests with mock API | `TestOpusStrategyAdvisor` |
| 7 | `ktrdr-options/tests/test_orchestrator.py` | Orchestrator integration tests | `TestLuxOrchestrator` |

---

## D. Files to Modify (in ktrdr repo)

| # | File Path | Change | Why |
|---|-----------|--------|-----|
| 1 | `ktrdr/api/endpoints/models.py` | Add `probabilities: dict[str, float] | None = None` to `Prediction` model. In prediction handler, extract `nn_probabilities` from `reasoning` dict and populate field. | Enables KtrdrSignalClient to receive full probability distribution needed for position sizing and Opus context. |

**Exact change (~10 lines)**:

```python
# In Prediction model (approx line 200):
class Prediction(BaseModel):
    signal: str
    confidence: float
    signal_strength: float
    probabilities: dict[str, float] | None = None  # ADD THIS LINE

# In prediction endpoint handler (approx line 225), after obtaining TradingDecision:
# ADD: Extract nn_probabilities from reasoning dict
nn_probs = trading_decision.reasoning.get("nn_probabilities") if trading_decision.reasoning else None
# MODIFY: Pass to Prediction constructor
prediction = Prediction(
    signal=trading_decision.signal.value,
    confidence=trading_decision.confidence,
    signal_strength=trading_decision.signal_strength,
    probabilities=nn_probs,  # ADD THIS LINE
)
```

**Backward compatibility**: Field is optional with `None` default. Existing clients unaffected.

---

## E. Implementation Tasks

### Task 1: Extend ktrdr API — add `probabilities` to `PredictionResponse`
- **File**: `ktrdr/api/endpoints/models.py` (in ktrdr repo)
- Add `probabilities: dict[str, float] | None = None` to `Prediction` Pydantic model
- In prediction endpoint handler: extract `reasoning.get("nn_probabilities")` from `TradingDecision` and pass to `Prediction`
- **Test**: Start ktrdr server, call `POST /api/v1/models/predict`. Verify response JSON includes `prediction.probabilities` with keys "BUY", "HOLD", "SELL" summing to ~1.0.

### Task 2: Implement `KtrdrSignalClient.predict()` — async HTTP with retries
- **File**: `ktrdr_options/signals/ktrdr_client.py`
- **Method**: `predict(self, model_name, symbol, timeframe, test_date) -> KtrdrSignal`
- Use `httpx.AsyncClient` for async HTTP
- Retry logic: 3 retries with exponential backoff (2s, 4s, 8s)
- Stale data detection: if `response.test_date` is > 2 bars behind current time, raise `KtrdrStaleDataError`
- Map response to `KtrdrSignal` dataclass:
  - `signal`, `confidence`, `signal_strength` from `prediction`
  - `probabilities` from `prediction.probabilities` (handle None: construct from signal+confidence as fallback)
  - `input_features` from response
- Raise `KtrdrAPIError` after retries exhausted
- **Test**: Mock httpx to return valid response → verify KtrdrSignal fields. Mock httpx to return 500 3 times → verify KtrdrAPIError raised. Mock httpx to return stale test_date → verify KtrdrStaleDataError.

### Task 3: Implement `KtrdrSignalClient.health_check()` — simple GET /health
- **File**: `ktrdr_options/signals/ktrdr_client.py`
- **Method**: `health_check(self) -> bool`
- `GET {base_url}/health` or `GET {base_url}/api/v1/health`
- Return True if status 200, False otherwise
- No retries (quick check)
- **Test**: Mock healthy server → True. Mock unreachable → False.

### Task 4: Implement `OptionsDataProvider.get_options_chain()` — yfinance for paper mode
- **File**: `ktrdr_options/data/options_data.py`
- **Method**: `get_options_chain(self, symbol, min_dte, max_dte, min_delta, max_delta) -> OptionsChain`
- For `mode == "paper"` or `mode == "backtest"`:
  - Use `yfinance.Ticker(symbol).option_chain(expiry)` for each available expiry
  - Filter by DTE range and delta range
  - Map to `OptionContract` dataclass list
  - Compute Greeks via `BlackScholesEngine` if not provided by yfinance
- For `mode == "live"`: stub (implemented in M5 via IBKR MCP)
- Return `OptionsChain` with filtered contracts
- **Test**: Mock yfinance response → verify filtering logic. Verify contracts sorted by strike.

### Task 5: Implement `OptionsDataProvider.get_iv_data()` — combined IV context
- **File**: `ktrdr_options/data/options_data.py`
- **Method**: `get_iv_data(self, symbol, as_of) -> IVData`
- Fetch VIX history (from cache or yfinance)
- Compute IV rank from trailing 252-day VIX
- Compute current IV: `vix / 100` for SPY, `vix / 100 * beta_scalar` for single names
- Compute 20-day realized vol from underlying prices
- Return `IVData(current_iv, iv_rank, iv_percentile, iv_history, vix, rv_20d)`
- **Test**: Verify all fields populated. Verify iv_rank in [0, 100]. Verify rv_20d > 0.

### Task 6: Implement `OpusStrategyAdvisor.advise()` — full Opus 4.7 integration
- **File**: `ktrdr_options/strategy/opus_advisor.py`
- **Method**: `advise(self, decision_input: DecisionInput) -> TradeRecommendation`
- Flow:
  1. Build prompt via `self._build_prompt(decision_input)`
  2. Call Anthropic API: `self._client.messages.create(model=self._model, ...)` with extended thinking enabled
  3. Parse JSON from response text → `TradeRecommendation`
  4. Validate via `self._validate_recommendation(recommendation, decision_input)`
  5. If validation fails: retry up to `self._max_retries` times with explicit error feedback in prompt
  6. If still fails: fall back to `self._fallback_to_matrix(decision_input, reason)`
- Set `recommendation.source = "opus"` or `"matrix"` accordingly
- **Test**: Mock Anthropic API to return valid JSON → verify TradeRecommendation parsed correctly. Mock API to return invalid JSON → verify retry then matrix fallback. Mock API timeout → verify matrix fallback with `warnings=["opus_fallback"]`.

### Task 7: Implement `OpusStrategyAdvisor._build_prompt()` — structured prompt template
- **File**: `ktrdr_options/strategy/opus_prompt.py`
- **Constant**: `OPUS_SYSTEM_PROMPT` — system prompt for Opus 4.7:
  ```
  You are an options strategy advisor for an autonomous trading system. You receive structured market data and must recommend a specific options trade.

  ALLOWED STRUCTURES: bull_put_spread, iron_condor, bull_call_spread, bear_call_spread, long_call, long_straddle, bear_put_spread, long_put

  CONSTRAINTS:
  - max_risk must not exceed the provided max_risk_per_trade
  - All strikes must come from the provided options chain (if available)
  - Expiry must be within the provided DTE range
  - Respond ONLY with valid JSON matching the schema below

  RESPONSE SCHEMA:
  {
    "action": "OPEN" | "HOLD",
    "structure": "<structure_name>",
    "legs": [{"action": "BUY"|"SELL", "option_type": "CALL"|"PUT", "strike": float, "expiry": "YYYY-MM-DD", "contracts": int}],
    "expected_credit": float | null,
    "expected_debit": float | null,
    "max_risk": float,
    "max_profit": float,
    "breakeven": float | [float, float],
    "exit_plan": {"take_profit_pct": float, "stop_loss_pct": float, "time_exit_dte": int},
    "reasoning": "string",
    "confidence": "HIGH" | "MEDIUM" | "LOW",
    "warnings": []
  }
  ```
- **Function**: `build_opus_prompt(decision_input: DecisionInput) -> str`
  - Render `DecisionInput.to_dict()` as formatted JSON in user message
  - Include: current price, ktrdr signal + probabilities, Kronos regime + confidence, IV rank, VIX, RV_20d, options chain (if available), current positions, account state, decision matrix suggestion
  - Add the matrix suggestion as context: "The deterministic decision matrix suggests: {structure}. You may agree, modify, or override."
- **Test**: Build prompt with sample DecisionInput, verify JSON is well-formed and contains all required fields. Verify prompt length < 4000 tokens (stay within reasonable limits).

### Task 8: Implement `OpusStrategyAdvisor._parse_response()` and `_validate_recommendation()`
- **File**: `ktrdr_options/strategy/opus_advisor.py`
- **Method**: `_parse_response(self, response_text: str) -> TradeRecommendation`
  - Extract JSON from response (handle markdown code blocks)
  - Map to `TradeRecommendation` dataclass
  - Raise `ValueError` if JSON is malformed or missing required fields
- **Method**: `_validate_recommendation(self, recommendation, decision_input) -> list[str]`
  - Check: `structure in ALLOWED_STRUCTURES`
  - Check: `max_risk <= decision_input.max_risk_per_trade`
  - Check: all legs have `contracts > 0`
  - Check: expiry in future
  - Check: if options_chain available, strikes exist in chain
  - Return list of validation errors (empty = valid)
- **Test**: Parse valid JSON → success. Parse JSON missing "legs" → ValueError. Validate recommendation exceeding risk → returns error. Validate recommendation with unknown structure → returns error.

### Task 9: Implement `OpusStrategyAdvisor._fallback_to_matrix()`
- **File**: `ktrdr_options/strategy/opus_advisor.py`
- **Method**: `_fallback_to_matrix(self, decision_input, reason) -> TradeRecommendation`
- Call `self._fallback_matrix.select(decision_input)` → `StructureChoice`
- Build `TradeRecommendation` from `StructureChoice`:
  - Use `BlackScholesEngine` to compute strikes and prices from structure parameters
  - Set `source = "matrix"`
  - Set `reasoning = f"Opus fallback: {reason}. {matrix_reasoning}"`
  - Set `warnings = ["opus_fallback"]`
- **Test**: Call with reason="timeout" → verify TradeRecommendation has source="matrix" and warnings includes "opus_fallback".

### Task 10: Implement `LuxOrchestrator.run_cycle()` — 10-step analysis flow
- **File**: `ktrdr_options/orchestrator.py`
- **Method**: `run_cycle(self) -> CycleResult`
- 10-step flow per ARCHITECTURE.md Section 2.K:
  1. Fetch ktrdr signal via `KtrdrSignalClient.predict()`
  2. Fetch recent OHLCV for Kronos (from ktrdr data or yfinance)
  3. Run `KronosVolClassifier.predict()` on recent OHLCV
  4. Fetch IV data via `OptionsDataProvider.get_iv_data()`
  5. Fetch options chain via `OptionsDataProvider.get_options_chain()` (paper mode)
  6. Aggregate via `SignalAggregator.aggregate()`
  7. Get recommendation via `OpusStrategyAdvisor.advise()`
  8. Mark-to-market all open positions
  9. Check exit conditions on all open positions, close if triggered
  10. If recommendation.action == "OPEN" and risk budget available: log recommendation (no execution in M4)
- Persist `signals` row to SQLite
- Build and return `CycleResult`
- Wrap entire flow in try/except — log errors, continue
- **Test**: Mock all dependencies, run cycle → verify CycleResult has all fields. Verify signals table has new row. Verify errors are caught and logged.

### Task 11: Implement `LuxOrchestrator.start()` — scheduler loop
- **File**: `ktrdr_options/orchestrator.py`
- **Method**: `start(self, interval_minutes: int = 60) -> None`
- `asyncio` loop that runs `run_cycle()` every `interval_minutes`
- Only run during market hours if `schedule.trading_hours_only == True`:
  - Check current time against `market_open` and `market_close` in configured timezone
- Set `self._running = True`; loop until `stop()` is called
- **Test**: Start with interval_minutes=0 (immediate), verify cycle runs. Call stop(), verify loop exits.

### Task 12: Implement `LuxOrchestrator._send_telegram_report()`
- **File**: `ktrdr_options/orchestrator.py`
- **Method**: `_send_telegram_report(self, cycle_result: CycleResult) -> None`
- Format message based on notification type:
  - **trade_opened**: "OPEN: {structure} {symbol} {strikes} exp {expiry} — max risk ${max_risk}"
  - **trade_closed**: "CLOSED: {position_id} — {exit_reason} — PnL: ${pnl} ({pnl_pct}%)"
  - **error**: "ERROR: {error_message}"
  - **daily_summary**: aggregate stats: open positions, total PnL, portfolio Greeks
- Send via Telegram Bot API: `POST https://api.telegram.org/bot{token}/sendMessage`
- Use `httpx.AsyncClient` for non-blocking send
- Graceful failure: if Telegram API unreachable, log warning and continue
- **Test**: Mock Telegram API → verify message format. Mock Telegram failure → verify no exception raised.

### Task 13: Wire SQLite live schema — `positions`, `trades`, `signals` tables
- **File**: `ktrdr_options/persistence/schema.py`
- Implement `create_live_schema()` (stubbed in M3):
  - Create `positions` table per ARCHITECTURE.md Section 4
  - Create `trades` table
  - Create `signals` table
  - Create `calibration` table (stub for M5)
  - Create all indexes
- Wire into `LuxOrchestrator.__init__()`: create/connect to SQLite database
- Wire into `run_cycle()`: write `signals` row after each cycle
- **Test**: Initialize orchestrator, verify all tables exist. Run cycle, verify signals row written with all fields populated.

---

## F. Acceptance Criteria

### Unit Tests
- [ ] `KtrdrSignalClient.predict()` returns valid `KtrdrSignal` from mock HTTP response
- [ ] `KtrdrSignalClient.predict()` retries 3 times with exponential backoff on failure
- [ ] `KtrdrSignalClient.predict()` raises `KtrdrStaleDataError` for stale data
- [ ] `KtrdrSignalClient.health_check()` returns True/False appropriately
- [ ] `OpusStrategyAdvisor.advise()` parses valid Opus response into `TradeRecommendation`
- [ ] `OpusStrategyAdvisor.advise()` falls back to matrix on Opus failure (timeout, invalid JSON, validation error)
- [ ] `OpusStrategyAdvisor._validate_recommendation()` catches risk limit violations and unknown structures
- [ ] `OpusStrategyAdvisor._build_prompt()` includes all required context fields
- [ ] `LuxOrchestrator.run_cycle()` completes all 10 steps with mocked dependencies
- [ ] `LuxOrchestrator._send_telegram_report()` formats messages correctly
- [ ] Telegram failure does not crash the cycle

### Integration Tests
- [ ] ktrdr API returns `probabilities` field after code change (requires running ktrdr server)
- [ ] Full cycle with mock ktrdr API + mock Anthropic API → correct signals logged to SQLite
- [ ] Matrix fallback produces valid `TradeRecommendation` when Opus is mocked to fail
- [ ] SQLite `signals` table has a row for each completed cycle
- [ ] SQLite `positions` table is updated on mark-to-market

### Empirical Validation Gates
- [ ] **Full analysis cycle completes in < 90 seconds** (including Opus call with mock or real API)
- [ ] SQLite records are written correctly after each cycle
- [ ] Telegram notification fires (with mock or real bot)
- [ ] Fallback to matrix works when Opus is mocked to return errors

### Performance Requirements
- [ ] ktrdr signal fetch: < 5 seconds (localhost)
- [ ] Kronos inference: < 2 seconds (CPU)
- [ ] Opus 4.7 call: < 60 seconds (including extended thinking)
- [ ] Total cycle time: < 90 seconds
- [ ] SQLite write: < 100ms per row

---

## G. Estimated Effort

**10 developer-days**

| Task | Days |
|------|------|
| ktrdr API extension (Task 1) | 0.5 |
| KtrdrSignalClient (Tasks 2-3) | 1.5 |
| OptionsDataProvider — chain + IV (Tasks 4-5) | 1.0 |
| OpusStrategyAdvisor — advise + prompt (Tasks 6-7) | 2.0 |
| OpusStrategyAdvisor — parse + validate + fallback (Tasks 8-9) | 1.5 |
| LuxOrchestrator — cycle + scheduler (Tasks 10-11) | 1.5 |
| Telegram + SQLite wiring (Tasks 12-13) | 1.0 |
| Integration testing | 1.0 |

The Opus prompt engineering (Tasks 6-7) may require iteration — the prompt must reliably produce valid JSON with correct structure. Budget time for prompt refinement.

---

## H. Open Questions / Risks

1. **Opus 4.7 prompt reliability**: Getting Opus to consistently return valid JSON matching the `TradeRecommendation` schema is the primary risk. The prompt must be explicit about the schema. Consider using tool use / function calling instead of free-form JSON generation if available in the API. `[VALIDATE EMPIRICALLY]`: Test prompt with 50+ diverse inputs and measure JSON parse success rate. Target: > 95%.

2. **Opus 4.7 extended thinking latency**: Extended thinking can take 10-60 seconds depending on complexity. The 60-second timeout is generous but may not be enough for complex scenarios. Monitor actual latencies during testing. If consistently > 45s, consider disabling extended thinking or simplifying the prompt.

3. **`[DECISION NEEDED]` ktrdr API extension**: The ~10 line change to add `probabilities` to the REST response is the recommended approach. Alternative: call ktrdr as a library from the orchestrator (bypasses REST, but tighter coupling). Karl's preference?

4. **Telegram bot setup**: Assumes a Telegram bot is already configured with `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` environment variables. If not set up, the notification system should degrade gracefully (log-only mode).

5. **OHLCV data for Kronos in live mode**: The orchestrator needs recent OHLCV bars to feed Kronos. In live mode, these must come from ktrdr's data layer or from yfinance. Need to decide: (a) call ktrdr's data API endpoint, (b) use yfinance directly, or (c) share ktrdr's local CSV cache. Option (c) is simplest if both services run on the same machine.

6. **Options chain data quality**: yfinance options chain data can be delayed by 15 minutes and may have gaps. For paper trading analysis, this is acceptable. For live trading (M5), IBKR data is required.

7. **Opus 4.7 prompt template**: The full prompt template must be included in this milestone document. See Task 7 for the complete system prompt and schema. The prompt should be version-controlled and configurable — prompt changes are a form of model tuning and should be trackable.

### Opus 4.7 Prompt Template (Complete)

**System Prompt**:
```
You are an expert options strategy advisor for an autonomous trading system. You receive structured market data including directional signals, volatility regime classification, and options chain data. Your task is to recommend a specific options trade or advise holding.

## Allowed Structures
- bull_put_spread: Sell OTM put + buy further OTM put (bullish, premium collection)
- bear_call_spread: Sell OTM call + buy further OTM call (bearish, premium collection)
- bull_call_spread: Buy ATM call + sell OTM call (bullish, defined risk)
- bear_put_spread: Buy ATM put + sell OTM put (bearish, defined risk)
- iron_condor: Sell OTM put + buy further OTM put + sell OTM call + buy further OTM call (neutral, premium collection)
- long_call: Buy OTM call (bullish + vol expansion)
- long_put: Buy OTM put (bearish + vol expansion)
- long_straddle: Buy ATM call + ATM put (neutral direction, vol expansion)

## Constraints
- max_risk MUST NOT exceed the provided max_risk_per_trade
- All strikes should be realistic given the underlying price
- Expiry should be 14-45 DTE depending on structure
- For credit spreads: short strike delta should be 0.16-0.30
- For debit spreads: long strike delta should be 0.40-0.50
- Respond ONLY with valid JSON matching the schema below — no other text

## Response JSON Schema
{
  "action": "OPEN" or "HOLD",
  "structure": "<one of the allowed structures>",
  "legs": [
    {
      "action": "BUY" or "SELL",
      "option_type": "CALL" or "PUT",
      "strike": <float>,
      "expiry": "<YYYY-MM-DD>",
      "contracts": <int>
    }
  ],
  "expected_credit": <float or null>,
  "expected_debit": <float or null>,
  "max_risk": <float, in dollars>,
  "max_profit": <float, in dollars>,
  "breakeven": <float or [float, float]>,
  "exit_plan": {
    "take_profit_pct": <float, e.g. 50.0>,
    "stop_loss_pct": <float, e.g. 100.0>,
    "time_exit_dte": <int, e.g. 7>
  },
  "reasoning": "<1-3 sentences explaining the trade logic>",
  "confidence": "HIGH" or "MEDIUM" or "LOW",
  "warnings": ["<any concerns>"]
}

If you believe no trade should be opened, respond with:
{"action": "HOLD", "structure": "no_trade", "legs": [], "reasoning": "<why>", "confidence": "HIGH", "warnings": []}
```

**User Message** (rendered from DecisionInput):
```
Analyze the following market data and recommend an options trade:

{decision_input.to_json()}

The deterministic decision matrix suggests: {matrix_suggestion}
Reasoning: {matrix_reasoning}

Consider the matrix suggestion as a starting point. You may agree, modify strikes/expiry, adjust position size, or override entirely if you see a better opportunity or risk concern.
```
