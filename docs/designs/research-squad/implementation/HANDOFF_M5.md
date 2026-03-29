# Handoff — M5: Synthesis + Long-Run Evaluation

## Status: Tasks 5.1 + 5.2 COMPLETE — Task 5.3 (evaluation) pending

## What Changed

### Task 5.1: Scribe Synthesis Cycle

**loop_lib.sh** (new file — `.squad/loop_lib.sh`):
- Extracted shared functions from loop_runner: `needs_synthesis`, `get_last_synthesis_cycle`, `get_context_for_agent`, `_extract_last_n_experiments`, `trim_history`, `estimate_context_tokens`, `needs_emergency_synthesis`, `estimate_agent_context`
- Auto-trigger synthesis every N cycles (default 10, configurable via `--synthesis-interval`)
- Emergency synthesis triggers when experiments.md exceeds 80% of context limit (200K tokens default)

**loop_runner.sh** (updated):
- Sources `loop_lib.sh` for shared functions
- Added `--synthesis-interval` CLI option
- Auto-triggers synthesis cadence when cycle number is a multiple of interval
- Emergency synthesis check before each cycle based on experiments.md token count
- History trimming after each evaluate phase (all agent histories capped at 20 entries)
- Context budget logging after each cycle (max agent token estimate)

**Coordinator SKILL.md** (updated):
- Added full synthesis phase with dedicated Scribe prompt producing structured synthesis.md (5 mandatory sections + patterns)
- Added Director recalibration step after synthesis
- Added "Post-Synthesis Context Rules" section: agents get synthesis + last 5 experiments instead of full experiments.md
- Updated ORIENT template to use synthesis-based experiment context
- Updated synthesis cycle mode description with explicit coordinator instructions

**Scribe charter** (updated):
- Added detailed synthesis output format (6 sections: facts, frontiers, dead ends, questions, best result, patterns)
- Added synthesis rules: <3 pages, replaces previous, flag repetition

### Task 5.2: Context Management

**Context switching** (in coordinator SKILL.md):
- Post-synthesis: most agents receive `synthesis.md + last 5 experiments` instead of full `experiments.md`
- Scribe during SYNTHESIZE gets full experiments.md (exception — needs everything to produce synthesis)
- Loop runner `build_cycle_prompt` includes context management instructions with current experiments.md size

**History trimming** (in loop_lib.sh + loop_runner.sh):
- `trim_history` function: keeps last N entries (default 20), archives older to `history_archive.md`
- Runs automatically after each evaluate phase for all 8 agents

**Context budget** (in loop_lib.sh + loop_runner.sh):
- `estimate_context_tokens`: rough word-based estimate (words * 1.3)
- `estimate_agent_context`: total tokens across all knowledge files for an agent
- `needs_emergency_synthesis`: triggers at 80% of context limit
- Budget logged after each cycle

### Tests

**test_synthesis.sh** (new — `.squad/test_synthesis.sh`):
- 17 tests covering: synthesis auto-trigger, context assembly, history trimming, token estimation, emergency synthesis
- All passing

## Key Design Decisions

- **Functions extracted to loop_lib.sh** rather than inline in loop_runner.sh — enables testing and reuse
- **Synthesis is a fresh replacement** of previous synthesis.md, not append — keeps it concise
- **Context switching is prompt-level**, not file-level — the coordinator assembles context per-agent based on the skill instructions. No files are modified; the coordinator reads synthesis.md vs experiments.md based on the rules.
- **History trimming is automatic**, not opt-in — every cycle trims all agents to 20 entries. The trim-then-archive pattern preserves full history for audit.
- **Emergency synthesis threshold is 80%** of a 200K token context limit. This is conservative; actual Claude context is larger, but we want headroom for the prompt template overhead.

## Gotchas

- **Synthesis quality depends on experiment count.** The structured synthesis format is designed for 10+ experiments. For <10, the synthesis may be thin. The auto-trigger interval (default 10) accounts for this.
- **Token estimation is rough.** `words * 1.3` is a heuristic. For precise counting, you'd need tiktoken or similar. Good enough for budget monitoring and emergency triggers.
- **History archive grows unbounded.** `history_archive.md` is append-only. For very long runs (100+ cycles), consider periodic archive pruning.
- **Context switching is instruction-based.** The coordinator must follow the SKILL.md instructions to provide synthesis-based context. If a coordinator session ignores the rules, agents will get full experiments.md (larger but still functional).

## Next: Task 5.3 (Long-Run Evaluation)

Task 5.3 is VALIDATION type — requires running 20-30 experiments and evaluating whether the squad compounds knowledge. This is the meta-experiment that determines if the whole mechanism works.
