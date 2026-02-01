---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 0: Agent Deck Trial

**Branch:** N/A (research/exploration)
**Parallel with:** M1-M6
**Type:** RESEARCH (hands-on trial, not code implementation)

## Goal

Evaluate Agent Deck as external session manager for parallel Claude Code sessions. Determine if it meets our needs for session visibility, state detection, and switching.

---

## Task 0.1: Install and Configure Agent Deck

**Type:** RESEARCH
**Estimated time:** 30 min

**Description:**
Install Agent Deck and configure for KTRDR workflow.

**Steps:**
1. Install via curl or Homebrew:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/asheshgoplani/agent-deck/main/install.sh | bash
   ```
2. Configure `~/.agent-deck/config.toml`:
   ```toml
   [general]
   auto_update = true

   [worktree]
   location = "sibling"  # ../ktrdr-impl-<name>
   ```
3. Verify installation: `agent-deck --version`

**Acceptance Criteria:**
- [ ] Agent Deck installed successfully
- [ ] Configuration file created
- [ ] Command available in PATH

---

## Task 0.2: Test Session Management

**Type:** RESEARCH
**Estimated time:** 1 hour

**Description:**
Create multiple Claude Code sessions and test state detection, switching, and visibility.

**Steps:**
1. Create 2-3 tmux sessions with Claude Code
2. Verify state detection:
   - Running (Claude actively generating)
   - Waiting (Claude waiting for input)
   - Idle (no activity)
   - Error (if detectable)
3. Test tmux status bar integration
4. Test session switching with `Ctrl+b N`
5. Test notification when session needs attention

**Acceptance Criteria:**
- [ ] State detection works for running/waiting/idle
- [ ] Status bar shows session states
- [ ] Switching between sessions works smoothly
- [ ] Can identify which session needs attention

---

## Task 0.3: Test with Worktrees

**Type:** RESEARCH
**Estimated time:** 30 min

**Description:**
Test Agent Deck with actual git worktrees to ensure integration works.

**Steps:**
1. Create a spec worktree manually:
   ```bash
   git worktree add ../ktrdr-spec-test spec/test
   ```
2. Open Claude Code in that worktree
3. Verify Agent Deck detects the session correctly
4. Test that session name reflects worktree

**Acceptance Criteria:**
- [ ] Sessions in worktrees work correctly
- [ ] Session naming makes sense
- [ ] No conflicts with main repo session

---

## Task 0.4: Document Findings

**Type:** RESEARCH
**Estimated time:** 30 min

**Description:**
Document what works, what doesn't, and any configuration needed.

**Deliverables:**
- Notes on state detection accuracy
- Any configuration tweaks needed
- Integration considerations for kinfra workflow
- Decision: adopt, modify approach, or find alternative

**Acceptance Criteria:**
- [ ] Findings documented
- [ ] Go/no-go decision made
- [ ] Next steps identified

---

## Milestone 0 Verification

**Type:** Manual validation

This milestone is validated through hands-on experience, not automated tests.

**Success Criteria:**
- [ ] Agent Deck provides useful session visibility
- [ ] State detection is accurate enough to be helpful
- [ ] Switching between sessions is smooth
- [ ] No major blockers identified

### Completion Checklist

- [ ] All tasks complete
- [ ] Findings documented
- [ ] Decision made on Agent Deck adoption
- [ ] Any follow-up work identified
