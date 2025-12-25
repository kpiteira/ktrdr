# Milestone: Discord Notify-Test Command

**Branch:** `feature/discord-notify-test`
**Builds on:** Discord Notifications (feature/discord-notifications)
**Capability:** CLI command to verify Discord webhook configuration

## Overview

Add a `notify-test` command to the orchestrator CLI that sends a test notification to Discord. This allows users to verify their webhook is configured correctly without running a full milestone.

## Tasks

### Task 1.1: Add notify-test CLI command

**File:** `orchestrator/cli.py`
**Type:** CODING

**Description:**
Add a new `notify-test` command that sends a test Discord notification.

**Implementation Notes:**

- Add new click command `notify-test`
- Load config and check if `discord_enabled`
- If enabled: send test notification using `format_test_notification()` and `send_discord_message()`
- If disabled: print error message about missing `DISCORD_WEBHOOK_URL`
- Use `asyncio.run()` to call async send function

**CLI behavior:**

```bash
# When configured:
$ uv run orchestrator notify-test
Sending test notification to Discord...
✓ Discord notification sent successfully!

# When not configured:
$ uv run orchestrator notify-test
✗ Discord not configured. Set DISCORD_WEBHOOK_URL environment variable.
```

**Acceptance Criteria:**

- [ ] `orchestrator notify-test` command exists
- [ ] Sends test notification when webhook configured
- [ ] Shows clear error when webhook not configured
- [ ] Works with `--help` flag

---

### Task 1.2: Add test notification formatter

**File:** `orchestrator/discord_notifier.py`
**Type:** CODING

**Description:**
Add a formatter function for the test notification.

**Implementation Notes:**

- Add `format_test_notification() -> DiscordEmbed`
- Use a distinct color (e.g., cyan/teal 0x1ABC9C)
- Include helpful info: timestamp, hostname, config status

**Embed content:**

```
Title: 🔔 Test Notification
Description: Discord webhook is configured correctly!
Color: Teal (0x1ABC9C)
Fields:
  - Sent at: <timestamp>
  - From: <hostname or "orchestrator">
```

**Acceptance Criteria:**

- [ ] `format_test_notification()` function exists
- [ ] Returns valid DiscordEmbed
- [ ] Embed renders nicely in Discord

---

### Task 1.3: Add tests

**File:** `orchestrator/tests/test_cli.py` (or `test_discord_notifier.py`)
**Type:** CODING

**Description:**
Add unit tests for the notify-test command.

**Test cases:**

1. `test_notify_test_command_exists` — command shows in help
2. `test_notify_test_shows_error_when_not_configured` — proper error message
3. `test_format_test_notification_returns_valid_embed` — formatter works

**Acceptance Criteria:**

- [ ] All tests pass
- [ ] Tests mock HTTP calls (no real Discord requests in tests)

---

### Task 1.4: E2E Verification

**Type:** VERIFICATION

**Description:**
Verify the command works end-to-end with a real webhook.

**Test Steps:**

```bash
# 1. Verify command exists
uv run orchestrator notify-test --help

# 2. Test without webhook (should show error)
unset DISCORD_WEBHOOK_URL
uv run orchestrator notify-test

# 3. Test with webhook (should send notification)
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
uv run orchestrator notify-test

# 4. Check Discord channel for test notification

# 5. Run tests
uv run pytest orchestrator/tests/ -k "notify" -v

# 6. Quality gates
make quality
```

**Success Criteria:**

- [ ] Command works with and without webhook configured
- [ ] Test notification appears in Discord
- [ ] All tests pass
- [ ] Quality gates pass

---

## Milestone Completion Checklist

- [ ] All tasks complete and committed
- [ ] Tests pass
- [ ] E2E verification passes
- [ ] Quality gates pass
- [ ] Branch ready for PR into `feature/discord-notifications`
