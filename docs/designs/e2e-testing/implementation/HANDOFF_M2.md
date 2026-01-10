# Handoff: Milestone 2 - Tester Agent Core

## Task 2.1 Complete: e2e-tester Agent Definition

**Agent file:** `.claude/agents/e2e-tester.md`

### Key Design Decisions

1. **Model choice: sonnet** — Reasoning needed for test execution, interpreting results, and generating diagnostic reports.

2. **Color: green** — Consistent with test/validation theme (green = go/pass).

3. **Tools: Bash, Read, Grep, Write, Glob** — Matches integration-test-specialist pattern. Write included for potential diagnostic file output.

### Contracts Match VALIDATION.md

Input format expects:
```markdown
## E2E Test Execution Request
**Tests to Run:**
**Context:**
```

Output format includes:
- Summary table with Result and Duration
- Per-test sections with Category, Pre-flight, Evidence
- Failure categorization: CODE_BUG | ENVIRONMENT | CONFIGURATION | TEST_ISSUE

### Next Task Notes

Task 2.2 creates a helper script `run-test.sh`. Note that:
- The agent already documents sandbox detection in the "Sandbox Awareness" section
- Helper script should use same port detection pattern: `${KTRDR_API_PORT:-8000}`
- JSON output from helper script should be parseable by the agent
