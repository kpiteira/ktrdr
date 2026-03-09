# Context Label Analysis: EURUSD 1d (2020-01-01 to 2025-01-01)

**Date:** 2026-03-09
**Data:** 1292 daily bars, 28173 hourly bars

## Summary

Default thresholds (H=5, ±0.5%) fail the quality gate: neutral context has only 2.3 days
mean duration, and hourly returns don't differentiate by context direction. Tuning the
horizon to 10 days and thresholds to ±0.7% passes all three gates.

## Best Configuration

**Horizon=10, threshold=±0.7%** — passes all gates (DPR):

| Metric | Value | Gate |
|--------|-------|------|
| Distribution | Bullish: 28%, Bearish: 33%, Neutral: 39% | PASS (max 39% < 60%) |
| Min persistence | 3.1 days | PASS (> 3 days) |
| Bullish hourly return | +0.000275% | PASS (positive) |
| Bearish hourly return | -0.000464% | PASS (negative) |

## Alternative: H=10, T=±1.0%

Stronger return differentiation but more skewed distribution:

| Metric | Value |
|--------|-------|
| Distribution | Bullish: 21%, Bearish: 24%, Neutral: 54% |
| Min persistence | 3.8 days |
| Bullish hourly return | +0.000994% |
| Bearish hourly return | -0.000192% |

## Parameter Sweep Results

Configurations that pass all 3 gates (D=Distribution <60%, P=Persistence >3d, R=Return diff):

| Horizon | Threshold | Bull% | Bear% | Neut% | Min Dur | Bull Ret | Bear Ret | Gates |
|---------|-----------|-------|-------|-------|---------|----------|----------|-------|
| 10 | ±0.007 | 28% | 33% | 39% | 3.1d | +0.000275% | -0.000464% | DPR |
| 10 | ±0.010 | 21% | 24% | 54% | 3.8d | +0.000994% | -0.000192% | DPR |

Only H=10 produces configurations passing all gates. H=5 lacks persistence; H=15/20
lose return differentiation due to longer horizon blurring the signal.

## Interpretation

- 10-day forward horizon captures the right timescale for FX trend context (2 trading weeks)
- The 0.7% threshold (~70 pips/10 days) matches the scale of genuine directional moves in EURUSD
- Return differentiation is small but directionally correct — enough for threshold modification
- Context and regime (once built) should have low correlation since they measure different things

## Decision

**PROCEED with Thread 2.** Context labels show genuine structure:
1. Balanced distribution with no dominant class
2. Multi-day persistence (not noise)
3. Hourly returns move in the expected direction during each context period

**Recommended defaults for context model training:** horizon=10, threshold=±0.007
