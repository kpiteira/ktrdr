# Handoff — M2: Director-Driven Consultation

## Status: IN PROGRESS — Tasks 2.1-2.3 complete, 2.4 pending

## What Was Built

### Task 2.1: Full Agent Roster + Concurrent Sessions
- Removed `allowed_roles={"engineer", "scribe"}` restriction from `loop.py`
- Updated `squad_tools.py` spawn_agent MCP tool schema: enum now lists all 7 roles (engineer, quant, inventor, scout, critic, architect, scribe)
- Updated spawn_agent description to explain each consultant role
- Updated `director_prompt.py` TOOL_GUIDANCE to list all roles with descriptions
- AgentManager already supported all roles via `ALL_ROLES` default — no changes needed there

### Task 2.2: Context Routing
- Added `CONTEXT_ROUTING` section to `director_prompt.py` with per-role file suggestions
- Framed as guidance ("typical suggestions"), not enforcement
- Tips for token efficiency (inline via message for Quant/Critic, full experiments.md only for Scribe synthesis)

### Task 2.3: Director Prompt — When to Consult Whom
- Added `CONSULTANT_TRIGGERS` section with per-consultant trigger conditions
- Added "When NOT to Consult" section (quick_iteration, synthesis, parameter repeats)
- Added relay pattern guidance with Bad/Good examples
- Made task instructions cadence-aware via `_build_task_instructions(cadence)`:
  - `full_squad`: full ORIENT → WORK → LEARN with consultant guidance
  - `quick_iteration`: Engineer only, minor variant focus
  - `synthesis`: Scribe only, consolidation focus

### Tests Added (23 new tests, 63 total)
- `TestM2AllRolesAvailable`: 11 tests (7 parametrized role spawns + concurrent + cost + teardown)
- `TestM2SpawnAgentSchema`: 2 tests (schema enum + description)
- `TestM2ContextRouting`: 4 tests (routing section + roles + files + guidance framing)
- `TestM2ConsultantTriggers`: 7 tests (dedicated section + triggers + relay + cadence adaptation + budget)

## Gotchas

1. **No code changes needed in AgentManager.** The M1 implementation already defaulted to ALL_ROLES when no `allowed_roles` parameter was passed. The restriction was only in `loop.py`'s call to the constructor.

2. **Prompt token budget.** The full prompt with all sections is ~1100 tokens. Well within the 4000 token budget. The charter (loaded separately by PersistentAgentSession) is not counted in this estimate.

3. **Linter auto-formatted test files.** The pre-commit hooks reformatted some list literals to multi-line. No functional change.

### Conversation Logging (added during 2.4)
- Added `ConversationEntry` dataclass to `squad_tools.py` — captures each Director→Agent exchange
- Added `conversation_log` field to `CycleState` — populated by spawn_agent tool handler
- Added `conversation_log` and `director_transcript` fields to `CycleResult`
- Added `_write_conversation_log()` to `loop.py` — writes human-readable markdown to `{shared_dir}/logs/cycle_{N}_conversation.md`
- Log includes: Director reasoning, tool calls, agent exchanges, experiment results

### Task 2.4: E2E Validation
- E2E test recipe designed at `.claude/skills/ke2e/tests/squad/m2-director-consultation.md`
- Runs 3 cycles: full_squad → quick_iteration → full_squad
- Validates: distinct agent combinations, cadence adaptation, consultant influence, KB evolution
- E2E execution running (background agent)

## E2E Test Recipe
Located at `.claude/skills/ke2e/tests/squad/m2-director-consultation.md`. Key validation criteria:
- At least 2 distinct agent combinations across 3 cycles
- quick_iteration cycle uses fewer agents than full_squad cycles
- At least one consultant (beyond engineer/scribe) in full_squad cycles
- KB state changes between cycles (experiments.md grows)

## Next: M3 (Multi-Turn Debate)
Engineer ↔ Critic debate with real back-and-forth that produces strategy revisions.
