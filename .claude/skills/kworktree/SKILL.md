---
name: kworktree
description: Use when user wants to create or manage worktrees with agent-deck integration. Commands: /kworktree spec, /kworktree impl, /kworktree done
user_invocable: true
---

# kworktree - Worktree + Agent Deck Integration

Orchestrates `kinfra` commands with `agent-deck` session management.

---

## Commands

### `/kworktree spec <feature>`

Create a spec worktree for design work with an agent-deck session.

**Steps:**
1. Run: `uv run kinfra spec <feature>`
2. Run: `agent-deck add -t "spec/<feature>" -g "dev" -c claude ../ktrdr-spec-<feature>`

**Example:**
```bash
# User runs: /kworktree spec genome

uv run kinfra spec genome
# Creates ../ktrdr-spec-genome with branch spec/genome

agent-deck add -t "spec/genome" -g "dev" -c claude ../ktrdr-spec-genome
# Adds session to agent-deck TUI
```

---

### `/kworktree impl <feature/milestone>`

Create an impl worktree with sandbox slot and agent-deck session.

**Steps:**
1. Run: `uv run kinfra impl <feature/milestone>`
2. Extract the worktree path from output (e.g., `../ktrdr-impl-<feature>-<milestone>`)
3. Run: `agent-deck add -t "<feature>/<milestone>" -g "dev" -c claude <worktree_path>`

**Example:**
```bash
# User runs: /kworktree impl genome/M1

uv run kinfra impl genome/M1
# Creates ../ktrdr-impl-genome-M1 with sandbox slot

agent-deck add -t "genome/M1" -g "dev" -c claude ../ktrdr-impl-genome-M1
# Adds session to agent-deck TUI
```

---

### `/kworktree done <name>`

Complete a worktree and remove its agent-deck session.

**Steps:**
1. Determine the session title from the worktree name
2. Run: `agent-deck remove "<session_title>"`
3. Run: `uv run kinfra done <name> --force` (if user confirms)

**Session title mapping:**
- `ktrdr-spec-<feature>` → session title: `spec/<feature>`
- `ktrdr-impl-<feature>-<milestone>` → session title: `<feature>/<milestone>`

**Example:**
```bash
# User runs: /kworktree done genome-M1

agent-deck remove "genome/M1"
# Removes session from agent-deck

uv run kinfra done genome-M1 --force
# Stops containers, releases slot, removes worktree
```

---

## Execution

When the user invokes a kworktree command:

1. **Parse the command** to extract feature/milestone names
2. **Run the commands** in sequence using Bash tool
3. **Report results** including:
   - Worktree path created
   - Slot claimed (for impl)
   - Agent-deck session added/removed
4. **Handle errors** gracefully — if kinfra fails, don't run agent-deck

---

## Notes

- **agent-deck not installed?** — Skip the agent-deck step with a note
- **Session naming** — Uses `<feature>/<milestone>` format (e.g., `genome/M1`)
- **Group** — All sessions go to `dev` group
- **Command** — All sessions use `claude` as the command
- **TUI updates live** — User will see session appear/disappear in agent-deck TUI immediately
