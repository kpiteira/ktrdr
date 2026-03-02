---
design: docs/designs/sdk-evolution-researchers/DESIGN.md
architecture: docs/designs/sdk-evolution-researchers/ARCHITECTURE.md
---

# Milestone 1: MCP Server Agent Gap-Fill

## User Value

**Any Claude Code session connected to ktrdr MCP can save validated strategies and assessments, and see what strategies have been tried before.**

Today, strategy saving requires the old in-process tool executor — only the backend's agent code can save. After M1, your manual Claude Desktop sessions, any Claude Code session, and the future containerized agents can all design, validate, save, and discover strategies through MCP. This is useful immediately for manual research, not just evolution.

## E2E Validation

### Test: MCP Strategy Save Round-Trip

**Purpose**: Verify a Claude Code session (or MCP client) can save a validated strategy and then find it via get_recent_strategies.

**Duration**: ~30 seconds

**Prerequisites**: Backend running (sandbox or local-prod)

**Test Steps**:

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| 1 | Start MCP server as stdio subprocess | Server starts, no errors on stderr | Process running |
| 2 | Call `tools/list` | Response includes `save_strategy_config`, `save_assessment`, `get_recent_strategies` | Tool names in list |
| 3 | Call `tools/list` | Response does NOT include `get_training_status` | Deprecated tool removed |
| 4 | Call `save_strategy_config` with valid v3 strategy YAML | Returns success, strategy_name, strategy_path | Response JSON |
| 5 | Verify strategy file exists at returned path | File exists and is valid YAML | `ls` + `python -c "yaml.safe_load(...)"` |
| 6 | Call `get_recent_strategies` with limit=5 | Returns list including the strategy just saved | Strategy name in list |
| 7 | Call `save_strategy_config` with invalid YAML (missing required field) | Returns validation error, no file created | Error message in response |
| 8 | Call `save_assessment` with structured assessment | Returns success, assessment file created | Response JSON + file exists |

**Success Criteria**:
- [ ] All 3 new tools respond correctly via stdio transport
- [ ] Deprecated `get_training_status` is gone
- [ ] Invalid strategies are rejected (atomic validate-then-save)
- [ ] Round-trip works: save → find via get_recent_strategies

---

## Task 1.1: Register save_strategy_config MCP tool

**File(s)**: `mcp/src/tools/strategy_tools.py`, `mcp/src/server.py`
**Type**: CODING
**Architectural Pattern**: D8 (atomic save via MCP tools)

**Description**:
Register `save_strategy_config` as an MCP tool that validates v3 format then saves atomically. The validation logic already exists in `ktrdr/agents/strategy_service.py` (used by the current in-process ToolExecutor). The MCP tool needs to:
1. Accept strategy YAML content (as string) and strategy name
2. Validate v3 format via the strategies client → backend API
3. Save to the strategies directory only if valid
4. Return strategy_name and strategy_path on success, validation errors on failure

**Implementation Notes**:
- Check if a backend API endpoint for strategy saving exists. If not, the MCP tool may need to save via filesystem (the MCP server runs with the strategies directory mounted).
- Follow the pattern in `mcp/src/tools/strategy_tools.py` where `validate_strategy` is already registered.
- The tool must be atomic: never save an invalid strategy. Validate FIRST, save SECOND.

**Tests**:
- Unit: `tests/unit/mcp/test_strategy_tools_save.py`
  - [ ] Valid v3 strategy → saved + returns path
  - [ ] Invalid strategy (missing indicators) → rejected, no file created
  - [ ] Duplicate strategy name → appropriate handling (overwrite or error?)
  - [ ] Strategy with invalid indicator names → validation catches it

**Acceptance Criteria**:
- [ ] `save_strategy_config` appears in `tools/list` response
- [ ] Valid strategies saved atomically (validate then write)
- [ ] Invalid strategies rejected with descriptive error
- [ ] Returns strategy_name and strategy_path on success

---

## Task 1.2: Add save_assessment MCP tool

**File(s)**: `mcp/src/tools/assessment_tools.py` (NEW), `mcp/src/server.py`
**Type**: CODING
**Architectural Pattern**: D8 (atomic save via MCP tools)

**Description**:
New MCP tool for saving structured assessment results. Accepts:
- `strategy_name`: which strategy was assessed
- `verdict`: "promising" | "neutral" | "poor"
- `strengths`: list of strings
- `weaknesses`: list of strings
- `suggestions`: list of strings
- `hypotheses`: list of dicts (optional, new hypotheses generated)

Validates the structure (verdict is valid enum, required fields present), then saves as JSON to the strategies directory alongside the strategy YAML.

**Implementation Notes**:
- Create new file `mcp/src/tools/assessment_tools.py` following the pattern of `strategy_tools.py`
- Register via a `register_assessment_tools(mcp)` function called from `server.py`
- Save path: `strategies/{strategy_name}/assessment.json` or `strategies/{strategy_name}_assessment.json` (check existing patterns)
- The assessment agent (M4) will call this tool to save its output

**Tests**:
- Unit: `tests/unit/mcp/test_assessment_tools.py` (NEW)
  - [ ] Valid assessment → saved as JSON
  - [ ] Invalid verdict value → rejected
  - [ ] Missing required fields → rejected
  - [ ] Assessment for non-existent strategy → appropriate handling

**Acceptance Criteria**:
- [ ] `save_assessment` appears in `tools/list` response
- [ ] Valid assessments saved as structured JSON
- [ ] Invalid assessments rejected with descriptive error
- [ ] Returns assessment_path on success

---

## Task 1.3: Register get_recent_strategies with filtering

**File(s)**: `mcp/src/server.py`, `mcp/src/clients/strategies_client.py`
**Type**: CODING

**Description**:
Register `get_recent_strategies` MCP tool. The implementation exists in the strategies client but isn't wired into `server.py`. Add `limit` (default 10) and `sort_by` (default "created_date") parameters so agents can see what's been tried recently.

Should return for each strategy: name, creation date, indicators used, and last experiment outcome (if available). This gives design agents enough context for novelty without bloating the prompt.

**Implementation Notes**:
- Check `mcp/src/clients/strategies_client.py` for existing `list_strategies()` method
- The `get_available_strategies` tool already exists but returns all strategies without filtering or context
- This tool should be distinct: focused on recent strategies with experiment outcomes

**Tests**:
- Unit: `tests/unit/mcp/test_strategy_tools_recent.py`
  - [ ] Returns strategies sorted by date
  - [ ] Respects limit parameter
  - [ ] Includes indicator summary per strategy
  - [ ] Empty result when no strategies exist

**Acceptance Criteria**:
- [ ] `get_recent_strategies` appears in `tools/list`
- [ ] Returns recent strategies with useful context (indicators, date, outcome)
- [ ] Respects limit parameter

---

## Task 1.4: Remove deprecated get_training_status + update endpoint mapping

**File(s)**: `mcp/src/server.py`, `mcp/endpoint_mapping.json`
**Type**: CODING

**Description**:
1. Remove `get_training_status` tool registration from `server.py`. It's deprecated in favor of `get_operation_status`.
2. Update `mcp/endpoint_mapping.json` to document all ~20 tools accurately (currently missing 5 tools).

**Tests**:
- Unit: Verify `get_training_status` not in tools list
- [ ] `tools/list` does not include `get_training_status`
- [ ] `endpoint_mapping.json` has entries for all registered tools

**Acceptance Criteria**:
- [ ] Deprecated tool removed
- [ ] Endpoint mapping complete and accurate

---

## Task 1.5: Execute E2E Test — MCP Strategy Save Round-Trip

**Type**: VALIDATION

**Description**:
Validate M1 is complete using the E2E test scenario defined above. Verify all new tools work via stdio transport.

**⚠️ MANDATORY: Use the E2E Agent System**

1. Invoke `e2e-test-designer` to confirm test (or hand off to architect for new test)
2. Invoke `e2e-tester` to execute against real system

**Acceptance Criteria**:
- [ ] All 3 new tools respond correctly via stdio transport
- [ ] Deprecated tool removed
- [ ] Round-trip: save_strategy_config → get_recent_strategies finds it
- [ ] Invalid inputs rejected with clear errors
- [ ] E2E test executed via agent (not ad-hoc commands)

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes (MCP strategy save round-trip)
- [ ] Quality gates pass: `make quality`
- [ ] `endpoint_mapping.json` matches reality
- [ ] No regressions in existing MCP tools
