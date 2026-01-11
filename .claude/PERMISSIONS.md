# Claude Code Permissions Strategy

This document explains the permission configuration in `settings.local.json`.

## Philosophy

**Trust the development workflow, not individual commands.**

Rather than approving each `git commit`, `docker compose up`, or `curl` individually, we pre-approve entire categories of safe operations. This reduces friction while maintaining security boundaries.

## Permission Categories

### Git Operations
```
Bash(git:*)
```
All git commands. Safe because git operates on the local repo only.

### GitHub CLI
```
Bash(gh:*)
```
All `gh` commands (PRs, issues, checks). Requires prior GitHub authentication.

### Testing
```
Bash(make test-unit:*)
Bash(make test-integration:*)
Bash(make test-e2e:*)
Bash(make quality:*)
Bash(uv run pytest:*)
```
Test runners. Safe — they only read code and report results.

### Python/UV
```
Bash(uv run:*)
Bash(uv run ktrdr:*)
Bash(timeout * uv run:*)
```
Python execution via uv, including the KTRDR CLI. The `timeout *` pattern allows any timeout value.

### Docker
```
Bash(docker:*)
Bash(docker compose:*)
```
All Docker operations. Required for local development environment.

### HTTP/API
```
Bash(curl:*)
Bash(timeout * curl:*)
```
HTTP requests. Used for API testing against localhost.

### Common Utilities
```
Bash(jq:*)
Bash(grep:*)
Bash(find:*)
Bash(ls:*)
...
```
Standard Unix utilities for inspecting files and output.

### .claude/ Directory
```
Edit(.claude/**)
Write(.claude/**)
Read(.claude/**)
```
Full access to the `.claude/` directory for managing skills, agents, and settings.

### Skills
```
Skill(ktask)
Skill(kdesign)
Skill(kdesign-impl-plan)
Skill(kdesign-validate)
```
Custom skills that can be invoked without prompting.

## Agent Permissions

Agents defined in `.claude/agents/` can have their own permission mode:

```yaml
---
name: e2e-tester
permissionMode: bypassPermissions
---
```

| Mode | Behavior |
|------|----------|
| `default` | Normal prompts |
| `acceptEdits` | Auto-accept file edits |
| `dontAsk` | Auto-deny unless in allow list |
| `bypassPermissions` | Skip all permission checks |
| `plan` | Read-only mode |

The `e2e-tester` agent uses `bypassPermissions` because E2E tests need to run many commands without interruption.

## What's NOT Pre-Approved

- **Destructive operations** — `rm -rf`, `git push --force`
- **System modifications** — Installing packages, modifying system files
- **Network access** — Except localhost via curl
- **Sensitive file access** — `.env` files with secrets (handled separately)

## Maintenance

When you find yourself repeatedly approving a command:
1. Check if it fits an existing category
2. If safe and recurring, add it to `settings.local.json`
3. Prefer broad patterns (`Bash(git:*)`) over specific commands

## Files

- `settings.local.json` — Project-specific permissions (gitignored, your local copy)
- `settings.local.example.json` — Template checked into git
- `~/.claude/settings.json` — Global permissions (all repos)

## Sandbox Setup

When creating a new sandbox with `ktrdr sandbox create`, the setup automatically copies `settings.local.example.json` to `settings.local.json` if it doesn't exist. This ensures new sandboxes get the standard permissions.
