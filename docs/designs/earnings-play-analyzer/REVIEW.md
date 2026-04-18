# Earnings Play Analyzer — Design Review

**Reviewer**: Fintech Design Squad Reviewer
**Date**: 2026-04-18
**Documents reviewed**: DESIGN.md, ARCHITECTURE.md

---

## Verdict: PROCEED (with corrections applied below)

The design is solid and comprehensive. The following issues were identified, categorized, and corrections have been incorporated into updated DESIGN.md and ARCHITECTURE.md.

---

## Review Checklist

### 1. Completeness

| Area | Status | Notes |
|------|--------|-------|
| All integration points defined | PASS | yfinance, IBKR, ktrdr, Anthropic API all specified |
| Error paths | PASS | Error handling table is thorough |
| Non-goals | PASS | Well-defined, prevents scope creep |
| Data models | PASS | All dataclasses are complete |
| CLI interface | PASS | Command structure is clear |
| Persistence schema | PASS | SQLite schema covers all use cases |
| Fallback behavior | PASS | Rule-based fallback when Opus unavailable |

### 2. Feasibility

| Concern | Assessment |
|---------|------------|
| yfinance earnings dates | **MINOR ISSUE** — `ticker.earnings_dates` is available but can be unreliable for future dates. The property sometimes returns historical analyst estimates, not confirmed dates. **Mitigation**: Cross-reference with `ticker.calendar` and allow manual date override via CLI (`--earnings-date`). Applied to DESIGN.md. |
| yfinance IV data | **MINOR ISSUE** — yfinance does not provide a direct "IV" time series for computing IV rank. Individual option IVs are available per strike, but historical ATM IV must be approximated from options chain snapshots over time. **Mitigation**: Compute IV from ATM options on each data fetch, cache in SQLite, build up history over time. First run will have limited IV rank accuracy. Document this bootstrap period. Applied to ARCHITECTURE.md. |
| yfinance options chain completeness | **OK** — `ticker.option_chain(expiry)` returns adequate data for MVP. Greeks may be computed server-side by Yahoo, not always present. **Mitigation**: Compute Greeks locally from Black-Scholes if missing (add to analysis engine). |
| Opus 4.7 vision extraction | **OK** — Vision capabilities are strong enough for options chain screenshots. Structured extraction prompts work well. The confirm-before-proceeding UX is the right call. |
| ktrdr file-based integration | **OK** — Simple, decoupled. The 24h staleness window is appropriate for earnings setups. |
| Click CLI | **OK** — Standard, well-supported. |

### 3. Domain Correctness

| Concept | Assessment |
|---------|------------|
| IV Rank formula | **CORRECT** — `(current - 52w_low) / (52w_high - 52w_low)` is the standard definition. |
| IV Percentile | **CORRECT** — Percentile rank over trailing year. |
| Implied move from straddle | **CORRECT** — ATM straddle price / underlying price is the standard approximation. More precise: use the weekly expiry straddling the earnings date. Design correctly notes this. |
| Kelly criterion | **CORRECT** — `(p*b - q) / b` is standard. Half-Kelly is the industry-standard conservative adjustment. |
| IV crush mechanics | **MINOR GAP** — Design mentions IV crush but doesn't explicitly model it. For short premium plays (iron condor), the expected P&L depends heavily on post-earnings IV drop, not just move size. **Correction**: Added IV crush estimation to the analysis engine — estimate post-earnings IV as the lower of (a) pre-event IV * 0.5 or (b) IV at same tenor one week prior to earnings run-up. This improves short premium structure scoring. |
| Options structure scoring | **MINOR GAP** — The structure selector should weight by expected P&L, not just edge direction. A long straddle with 3% edge but high break-even spread may be worse than a strangle with 2% edge but cheaper entry. **Correction**: StructureSelector now scores by `expected_value = prob_profit * avg_profit - prob_loss * avg_loss`, using historical move distribution. |
| Earnings time (BMO/AMC) | **CORRECT** — Correctly tracked. Important because BMO earnings use the prior day's close as reference, AMC uses same day. Design handles this. |

### 4. Architecture Quality

| Area | Assessment |
|------|------------|
| Data ownership | **GOOD** — Clear separation. Data layer owns acquisition, analysis engine owns computation, reasoner owns narrative. No overlapping responsibilities. |
| Failure modes | **GOOD** — Each component can fail independently. Orchestrator handles graceful degradation. |
| Testability | **GOOD** — Analysis engine is pure computation with no external dependencies. Easy to test with synthetic data. Fixtures directory is a good call. |
| State management | **GOOD** — SQLite is the single source of truth. No in-memory state that needs synchronization. |
| Provider abstraction | **GOOD** — Protocol-based DataProvider allows swapping yfinance → IBKR without changing upstream code. |
| Prompt design | **ADEQUATE** — Prompt structure is described but actual prompt templates aren't fully specified. This is acceptable for design phase — prompts will be iterated during M3. |

### 5. Gaps Identified and Addressed

#### Gap 1: IV History Bootstrap Problem
**Issue**: IV rank requires 252 trading days of IV history. On first run, this doesn't exist.
**Resolution**: Added bootstrap strategy — on first run, compute approximate IV rank from VIX percentile (for S&P 500 components) or skip IV rank and note "insufficient IV history" in output. After ~2 weeks of daily caching, IV rank becomes usable. Added to ARCHITECTURE.md notes.

#### Gap 2: Earnings Date Override
**Issue**: yfinance earnings dates can be wrong or missing.
**Resolution**: Added `--earnings-date` CLI flag for manual override. Also added `epa set-earnings AAPL 2026-04-24 AMC` command for pre-setting known dates. Applied to DESIGN.md CLI section.

#### Gap 3: Rate Limiting / Data Caching
**Issue**: yfinance has undocumented rate limits. Analyzing 10 tickers in sequence might get throttled.
**Resolution**: Added caching layer — options snapshots cached for 15 minutes, earnings history cached for 24 hours, IV data cached for 1 hour. Cache stored in SQLite `iv_cache` table (already in schema) + new `data_cache` table. Applied to ARCHITECTURE.md.

#### Gap 4: Expected Value Scoring for Structures
**Issue**: Original design scored structures by directional fit only, not expected P&L.
**Resolution**: StructureSelector now computes expected value using historical move distribution to estimate probability of profit for each structure. Applied to ARCHITECTURE.md analysis section.

---

## Summary of Changes Applied

1. **DESIGN.md**: Added `--earnings-date` override to CLI, noted IV history bootstrap limitation
2. **ARCHITECTURE.md**: Added IV crush estimation to analysis engine, added data caching layer, added Greeks computation fallback, refined structure scoring methodology, added `data_cache` table to schema

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| yfinance API changes/breaks | Medium | High | Provider abstraction allows quick swap to alternative |
| Opus API costs for frequent analysis | Low | Medium | Configurable — can run rule-based only for quick checks |
| Kelly sizing suggests too-large positions | Low | High | Hard cap at max_risk_pct, half-Kelly default |
| IV rank inaccurate in early usage | High (first 2 weeks) | Medium | Bootstrap strategy + clear warnings in output |
| ktrdr signal format changes | Low | Low | Adapter pattern isolates changes |

## Final Assessment

The design is well-structured, domain-correct, and implementable. The identified gaps are minor and have been addressed. The milestone progression (data → analysis → reasoning → ktrdr → IBKR) is logical and each milestone delivers testable value. Ready for implementation planning.

**Verdict: PROCEED**
