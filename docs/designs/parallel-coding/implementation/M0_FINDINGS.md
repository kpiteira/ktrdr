# M0 Agent Deck Trial - Findings

**Date:** 2026-02-01
**Agent Deck Version:** v0.9.2
**tmux Version:** 3.6a
**Status:** ✅ COMPLETE - Recommend Adoption

---

## Summary

Agent Deck is a terminal session manager for AI coding agents built on tmux. It provides session visibility, state detection, and multi-session management. **Testing confirms it meets our needs for the parallel coding workflow.**

---

## Installation & Configuration

### Status: ✅ Complete

- Agent Deck v0.9.2 installed at `~/.local/bin/agent-deck`
- Configuration created at `~/.agent-deck/config.toml`
- tmux 3.6a available as required dependency

### Configuration

```toml
[general]
auto_update = true

[worktree]
location = "sibling"  # ../ktrdr-impl-<name>
```

---

## Feature Evaluation

### Session Management

| Feature | Works? | Notes |
|---------|--------|-------|
| Add sessions | ✅ | `agent-deck add <path>` - straightforward |
| List sessions | ✅ | Shows title, group, path, ID |
| Status summary | ✅ | Shows waiting/running/idle counts |
| Session details | ✅ | `agent-deck session show <name>` |
| Groups | ✅ | Auto-groups by parent directory |

### Worktree Integration

| Feature | Works? | Notes |
|---------|--------|-------|
| Detect worktrees | ✅ | `agent-deck worktree list` shows all |
| Branch association | ✅ | Shows branch for each worktree |
| Session linking | ✅ | Links sessions to worktrees |
| Cleanup orphans | ✅ | `agent-deck worktree cleanup` |

### State Detection ✅ VERIFIED

| Feature | Status | Notes |
|---------|--------|-------|
| Running detection | ✅ | Shows when Claude is actively working (tools running) |
| Waiting detection | ✅ | Shows when Claude waiting for user input |
| Idle detection | ✅ | Shows when Claude finished and session quiet |
| Error detection | ✅ | Shows "error" for unmanaged sessions (correct behavior) |

**Testing confirmed:** All three primary states (running, waiting, idle) are accurately detected in real-time. The TUI status bar updates immediately as Claude's state changes.

### TUI Features ✅ VERIFIED

| Feature | Works? | Notes |
|---------|--------|-------|
| TUI interface | ✅ | Clean, responsive interface |
| Live output preview | ✅ | Shows Claude's recent output in preview pane |
| Session info | ✅ | Shows Claude version, model, context %, session duration |
| Keyboard navigation | ✅ | Enter to attach, standard tmux bindings |
| Status bar | ✅ | Real-time state counts at top |

### Additional Features

| Feature | Works? | Notes |
|---------|--------|-------|
| MCP management | ✅ | `agent-deck mcp` commands available |
| Session forking | ✅ | `agent-deck session fork` |
| Profiles | ✅ | Multiple profiles supported |
| Tool auto-detection | ✅ | Detects "claude" when Claude Code started in shell |

---

## Key Observations

### What Works Well

1. **State Detection is Accurate:** The TUI correctly shows waiting/running/idle states in real-time. This is the core value proposition and it works.

2. **Output Preview:** The preview pane shows recent Claude output, making it easy to see what each session is doing without attaching.

3. **Session Metadata:** Shows useful info like Claude version, model (Opus 4.5), context usage (11.8%), and session duration.

4. **Tool Auto-Detection:** When you run `claude` in a shell session, Agent Deck automatically detects it and changes the session type from "shell" to "claude".

### Workflow Considerations

1. **Start via Agent Deck:** For state tracking, sessions should be started through Agent Deck:
   ```bash
   agent-deck session start <name>  # Starts shell
   # Then run `claude` in that shell
   ```

2. **Or Add Existing Sessions:** You can add existing directories and start sessions later:
   ```bash
   agent-deck add /path/to/repo
   agent-deck session start repo-name
   ```

3. **Detach to Monitor:** Use `Ctrl+b d` to detach and return to TUI for monitoring multiple sessions.

---

## Recommended Usage Pattern

For KTRDR parallel coding workflow:

1. **Start Agent Deck TUI:** `agent-deck`
2. **Add session for worktree:** `agent-deck add ../ktrdr-impl-feature`
3. **Start session:** `agent-deck session start ktrdr-impl-feature`
4. **Run Claude:** Type `claude` in the started shell
5. **Detach:** `Ctrl+b d` to return to TUI
6. **Monitor:** TUI shows all sessions with states
7. **Switch:** Select session and press Enter to attach

---

## Decision: ✅ ADOPT

**Recommendation: Adopt Agent Deck for parallel coding workflow**

**Confirmed benefits:**
- Accurate state detection (waiting/running/idle)
- Real-time output preview without attaching
- Good worktree integration
- Active development (v0.9.x)
- Clean TUI interface

**Minor adjustments needed:**
- Sessions should be started through Agent Deck for tracking
- Learn tmux navigation (Ctrl+b shortcuts)

**No blockers identified.**

---

## Commands Reference

```bash
# Session management
agent-deck                        # Start TUI
agent-deck add <path>             # Add session
agent-deck list                   # List sessions
agent-deck status                 # Status summary
agent-deck session start <name>   # Start session (shell)
agent-deck session attach <name>  # Attach to session

# Navigation (in tmux)
Ctrl+b d                          # Detach from session
Ctrl+b w                          # List windows
Ctrl+b n/p                        # Next/previous window

# Worktree integration
agent-deck worktree list          # List worktrees
agent-deck worktree cleanup       # Clean orphans

# MCP management
agent-deck mcp list               # Available MCPs
agent-deck mcp attach <id> <mcp>  # Attach MCP to session
```

---

## Milestone Completion Status

| Task | Status | Notes |
|------|--------|-------|
| 0.1 Install & Configure | ✅ Complete | v0.9.2 + config |
| 0.2 Test Session Management | ✅ Complete | State detection verified |
| 0.3 Test with Worktrees | ✅ Complete | Integration verified |
| 0.4 Document Findings | ✅ Complete | This document |

**Overall: ✅ MILESTONE COMPLETE**

---

## Next Steps

1. Integrate Agent Deck into M1-M6 parallel coding workflow
2. Configure worktree naming convention (`ktrdr-impl-<feature>`)
3. Document session startup in workflow guides
