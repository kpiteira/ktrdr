# M3: Opus Reasoning

**Goal**: Wire Opus 4.7 to reason over the structured analysis, producing natural language rationale and a refined final recommendation. Full E2E: ticker in → recommendation with reasoning out.

**Success criteria**: `epa analyze AAPL` produces an Opus-generated recommendation that cites specific data points, explains the structure choice, and identifies risk factors.

**Depends on**: M2 (analysis engine, edge, structures, sizing)

---

## Task 3.1: Opus Reasoner Core

**Files to create**:
- `epa/reasoner/__init__.py`
- `epa/reasoner/opus.py` — `OpusReasoner` class
- `epa/reasoner/prompts.py` — prompt templates

**Behavior**:
- `OpusReasoner.__init__(api_key, model="claude-opus-4-6")`
  - Initializes Anthropic client
  - Model configurable via `~/.epa/config.toml`

- `reason_about_trade(history, iv_data, edge, candidates, sizing, signal=None)` → `TradeRecommendation`
  - Constructs prompt with:
    - System prompt: role definition (experienced options trader), output format spec (JSON + rationale)
    - User message: all structured data as JSON
  - Sends to Opus with `max_tokens=4096`
  - Parses response: expects JSON block with `action`, `structure_name`, `rationale`, `confidence`, `risk_factors`
  - Opus may override the rule-based recommendation if it identifies issues the rules miss
  - Uses prompt caching: system prompt is stable across calls, only user data changes

- Error handling:
  - API timeout/error → retry 2x with backoff
  - After retries fail → fall back to rule-based recommendation from M2
  - Parse error → log raw response, fall back to rule-based

**Prompt design** (in `prompts.py`):
```
SYSTEM: You are an experienced options trader specializing in earnings plays.
You are given structured data about a ticker's earnings setup and candidate
trade structures. Your job is to:
1. Validate the edge estimate — does the data support it?
2. Select the best structure (or reject all candidates)
3. Confirm or adjust the sizing
4. Provide a clear, concise rationale citing specific numbers
5. Identify 2-3 key risk factors

Output JSON: { action, structure_name, sizing_adjustment, rationale, confidence, risk_factors }
```

**Tests**:
- `test_opus.py`:
  - Mock Anthropic client — verify prompt construction includes all data
  - Verify response parsing for valid JSON response
  - Verify fallback on API error
  - Verify fallback on malformed response
  - Verify prompt caching headers sent

---

## Task 3.2: Vision Extraction

**Files to create**:
- `epa/data/providers/vision_provider.py` — `VisionProvider` class

**Behavior**:
- `extract_options_chain(image_path)` → `OptionsSnapshot`
  - Sends image to Opus 4.7 vision with extraction prompt
  - Prompt asks for: underlying price, expiry date, list of (strike, call_bid, call_ask, call_iv, put_bid, put_ask, put_iv)
  - Parses structured response into `OptionsSnapshot`
  - Returns extracted data with confidence flag

- CLI integration: `epa analyze AAPL --screenshot /path/to/chain.png`
  - Extracts data from screenshot
  - Prints extracted values and asks for confirmation (interactive)
  - Proceeds with analysis using extracted data

**Tests**:
- `test_vision.py`:
  - Mock Opus response with sample extraction
  - Verify parsing into `OptionsSnapshot`
  - Test with malformed response → graceful error

---

## Task 3.3: Post-Earnings Review

**Files to modify**:
- `epa/orchestrator.py` — add `review` workflow
- `epa/cli.py` — implement `review` command
- `epa/store/db.py` — add `save_actual()`, `get_calibration_stats()`

**Behavior**:
- `epa review AAPL`
  1. Look up most recent prediction for AAPL in store
  2. Fetch actual post-earnings price move from yfinance
  3. Compare: predicted edge direction vs actual move vs implied move
  4. Compute: was the edge call correct? (predicted overpricing → actual move < implied?)
  5. Save actual result to store
  6. Display comparison

- `epa calibration`
  1. Query all prediction/actual pairs
  2. Compute: hit rate (% correct edge direction), average edge estimation error, systematic biases
  3. Display summary table

**Tests**:
- `test_review.py`:
  - Prediction exists + actual available → correct comparison
  - No prediction found → helpful error
  - Earnings not yet occurred → "earnings haven't happened yet"
  - Calibration stats with mix of correct/incorrect predictions

---

## Task 3.4: Orchestrator E2E Integration

**Files to modify**:
- `epa/orchestrator.py` — wire Opus reasoner into analyze pipeline

**Behavior**:
- Full pipeline: data → analysis → Opus reasoning → output
- Opus is called after rule-based recommendation is computed
- If Opus and rules agree → high confidence output
- If Opus disagrees with rules → Opus recommendation takes priority, but the disagreement is noted
- If `config.opus.enabled = false` → skip Opus, use rule-based only
- Output clearly indicates whether Opus or rules produced the recommendation

**Tests**:
- `test_orchestrator_e2e.py`:
  - Full pipeline with mocked provider + mocked Opus → verify all components called in order
  - Opus disabled → rule-based output produced
  - Opus error → graceful fallback to rule-based

---

## Task 3.5: M3 Validation

**Files to create**:
- `epa/tests/test_m3_e2e.py`

**Test cases** (integration, requires ANTHROPIC_API_KEY):
1. `epa analyze AAPL --budget 65000` → Opus-generated recommendation with rationale
2. Verify rationale cites specific numbers from the input data
3. Verify `epa review AAPL` works after a prediction exists
4. Verify `epa calibration` produces stats
5. `epa analyze AAPL --json` → valid JSON with Opus rationale embedded

**Validation script** (manual):
```bash
export ANTHROPIC_API_KEY=sk-...
epa analyze AAPL --budget 65000          # Full Opus recommendation
epa analyze TSLA --budget 65000          # Different setup
epa review AAPL                          # If earnings already passed
epa calibration                          # Should show stats
epa analyze AAPL --screenshot chain.png  # Vision extraction
```

**Done when**: Full E2E works — ticker in, Opus-reasoned recommendation out. Karl can use this before an earnings event to get a well-reasoned trade recommendation.
