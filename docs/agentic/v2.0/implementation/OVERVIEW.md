# v2.0: Memory Foundation - Implementation Plan

## Milestone Summary

| # | Name | Tasks | E2E Test | Status |
|---|------|-------|----------|--------|
| M1 | Memory Infrastructure | 4 | Bootstrap loads 24 experiments | ⏳ |
| M2 | Shared HaikuBrain | 4 | Orchestrator + agent both use shared brain | ⏳ |
| M3 | Prompt Integration | 4 | Agent sees experiment history in prompt | ⏳ |
| M4 | Assessment → Memory | 4 | Assessment creates experiment record | ⏳ |
| M5 | Hypothesis Lifecycle | 3 | Hypothesis status updates when tested | ⏳ |

**Total Tasks:** 19
**Branch Strategy:** `feature/v2-memory-m{N}` per milestone

---

## Dependency Graph

```
M1 (Memory Infrastructure)
 ↓
M2 (Shared HaikuBrain) ──→ M4 (Assessment → Memory)
 ↓                              ↓
M3 (Prompt Integration) ────→ M5 (Hypothesis Lifecycle)
```

- M1 must complete first (memory module needed by all)
- M2 can start after M1 (HaikuBrain refactor independent of memory content)
- M3 depends on M1 (needs memory to load)
- M4 depends on M1 + M2 (needs memory to save, HaikuBrain to parse)
- M5 depends on M3 + M4 (needs both read and write paths)

---

## Reference Documents

- **Design:** [../DESIGN.md](../DESIGN.md)
- **Philosophy:** [../PHILOSOPHY.md](../PHILOSOPHY.md)
- **Validation:** [../SCENARIOS.md](../SCENARIOS.md)

---

## Architecture Alignment

### Core Patterns

| Pattern | Description | Implementing Tasks |
|---------|-------------|-------------------|
| Contextual Memory | Observations tied to full context | M1: 1.1, 1.2 |
| Haiku Parsing | LLM extraction from variable output | M2: 2.3 |
| Graceful Degradation | Memory enhances, doesn't block | M1: 1.1, M3: 3.3 |
| Caller Loads | Workers load memory, pass to builder | M3: 3.3, M4: 4.2 |

### What We Will NOT Do

- ❌ Regex parsing of assessment output (always Haiku)
- ❌ Hardcoded rules like "ADX doesn't work" (contextual observations only)
- ❌ Memory as blocking requirement (agent works without it)
- ❌ PromptBuilder loading memory internally (caller responsibility)

---

## Key Decisions (from Validation)

1. **Always Haiku for parsing** — No regex fallback, simpler and more robust
2. **Shared HaikuBrain** — Single module in `ktrdr/llm/` used by orchestrator and agents
3. **Memory in ktrdr/agents/** — Memory is about research loop, not orchestrator
4. **Caller loads memory** — Design worker loads, passes to PromptContext
5. **Context flows through** — strategy_config available at save time

---

## File Structure After Implementation

```
ktrdr/
├── llm/
│   ├── __init__.py
│   └── haiku_brain.py          # Shared (moved from orchestrator)
├── agents/
│   ├── memory.py               # NEW
│   ├── prompts.py              # Extended
│   ├── design_worker.py        # Modified
│   └── assessment_worker.py    # Modified

memory/
├── experiments/
│   ├── exp_v15_rsi_zigzag_1_5.yaml
│   └── ...                     # 24 bootstrap + new
└── hypotheses.yaml

orchestrator/
├── runner.py                   # Updated import
└── ...

scripts/
└── bootstrap_v15_memory.py     # One-time script
```

---

## Open Questions

1. **Hypothesis ID format:** `H_001` vs `H_multi_timeframe_001`?
   - Resolution: Use simple `H_001` for now, can extend later

2. **Memory directory location:** `memory/` at root vs `data/memory/`?
   - Resolution: Use `memory/` at root (it's not data, it's knowledge)

3. **Capability requests:** Defer to v2.1?
   - Resolution: Yes, defer — focus on core memory loop first
