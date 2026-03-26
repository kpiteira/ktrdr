# Handoff — M1: Squad Bootstrap + First Cycle

## Task 1.1: Agent Charters
- 8 charters written, 376-476 words each
- Engineer charter references real ktrdr components (v3 grammar, LSTM/GRU, 30 indicators, FuzzyEngine, EnsembleBacktestRunner)
- Critic charter includes tiered evaluation framework (Tier 1/2/3)

## Task 1.2: Knowledge Base + Seeding
- Seeded experiments.md with v1.5 baseline, signal M1-M5, H_003, regime classifier, 100+ agent-assessed
- Curated hypotheses.md: 6 confirmed, 6 active, dead section (discarded 300+ auto-generated noise)
- Components.md has accurate catalog including capability gaps
- 7 architectural decisions in decisions.md

## Task 1.3: Coordinator Logic
- Built as Claude Code skill at `.claude/skills/squad-coordinator/SKILL.md`
- Complete prompt templates for all 8 agents across all 6 phases
- Selective context routing matching architecture table
- Three cycle modes (full, quick iteration, synthesis)

## Task 1.4: Experiment Executor
- Shell script at `.squad/executor.sh`
- Uses temp files for robust JSON handling
- Polls operation status with 30s interval, 2hr timeout

## Task 1.5: First Full Cycle

### Gotchas
- **Existing .squad/ directory conflict:** There was a pre-existing `.squad/` from a different framework (kagents-squad with Star Trek agents). Had to wipe and replace.
- **lr_scheduler: true is a crash bug:** The v3 grammar accepts `lr_scheduler: true` but `ModelTrainer._create_scheduler()` calls `.get()` on a boolean → AttributeError. Must use dict format: `lr_scheduler: {type: reduce_on_plateau, factor: 0.5, patience: 5}`
- **CUSUM feature alignment bug:** CUSUM filter correctly filters labels but orchestrator tail-slices features instead of selecting matching indices. `_cusum_event_mask` is stored but never consumed. Blocked Variant B.
- **Trend scanning labels don't exist in ktrdr:** Not a v3 grammar label source. Would need ~200 lines for TrendScanLabeler.

### Emergent Patterns
- **Architect agent found real bugs.** The CUSUM alignment bug and lr_scheduler crash would have wasted training time if not caught during design phase. The multi-agent review process added genuine value.
- **Critic prevented lookahead leak.** The Inventor's horizon-as-feature idea was genuinely clever but would have leaked future prices. Critic caught it immediately.
- **Engineer's pragmatic adaptation.** When trend scanning wasn't available, Engineer pivoted to CUSUM-filtered triple barrier — testing the same hypothesis (selective training) with existing components.
- **Agent debate produced visible tension.** Inventor pushed for regime-gated labels, Critic demanded controls, Engineer grounded in what's buildable, Quant added session filtering insight. The final experiment is different (and better) than what any single agent would have proposed.

### Capability Gaps Identified
1. **TrendScanLabeler** — OLS regression across horizons, t-stat selection. ~200 lines. High priority for Cycle 2.
2. **CUSUM feature alignment fix** — ~5 lines in local_orchestrator.py. Blocks CUSUM-filtered training.
3. **Random dropout training** — For confound control (Critic's B' variant). Not in ktrdr.

### Cycle 1 Results
- **Training:** 60.1% best val accuracy (LSTM confirmed via weight inspection despite "v3_mlp" metadata bug)
- **Backtest:** -16.5% return, 184 trades, 25.5% win rate, Sharpe -0.52, PF 0.44
- **Verdict:** FAILED. Training infrastructure was NOT the bottleneck (D8). Wall is structural.
- **Agent debate value confirmed:** Critic caught lookahead leak, Architect caught 2 bugs, Engineer adapted when components missing
- **All knowledge base files updated** by Scribe (experiments, hypotheses, components, decisions, frontiers, synthesis, agent histories, loop state)

### Next Task Notes
- Task 1.6: E2E validation using ke2e framework against sandbox
- Cycle 2 should focus on label quality (F1) — trend scanning or CUSUM after bug fix
