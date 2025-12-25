# Milestone: Discord Notifications

**Branch:** `feature/discord-notifications`
**Builds on:** M4 Consolidated Runner
**Capability:** Real-time Discord notifications for orchestrator events

## Overview

Add Discord webhook integration to the orchestrator, enabling notifications for milestone progress, task completions, and escalations. This provides visibility into autonomous task execution without needing to watch the terminal.

## Configuration

The feature uses a single environment variable:

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

When not set, Discord notifications are silently skipped (graceful degradation).

## Tasks

### Task 1.1: Add Discord configuration

**File:** `orchestrator/config.py`
**Type:** CODING

**Description:**
Add `discord_webhook_url` to `OrchestratorConfig`. The field is optional — when not set, Discord notifications are disabled.

**Implementation Notes:**

- Add `discord_webhook_url: str | None` field to `OrchestratorConfig`
- Load from `DISCORD_WEBHOOK_URL` environment variable
- Default to `None` (disabled)
- Add `discord_enabled` property that returns `bool(self.discord_webhook_url)`

**Acceptance Criteria:**

- [ ] Config loads `DISCORD_WEBHOOK_URL` from environment
- [ ] `discord_enabled` property works correctly
- [ ] Missing env var results in `None`, not error

---

### Task 1.2: Create Discord notifier module

**File:** `orchestrator/discord_notifier.py`
**Type:** CODING

**Description:**
Create a module for sending Discord webhook messages with rich embeds.

**Implementation Notes:**

- Use `httpx` for HTTP requests (already a project dependency)
- Create `send_discord_message(webhook_url, embed)` async function
- Support Discord embed format (title, description, color, fields, timestamp)
- Handle errors gracefully — log but don't crash on webhook failures
- Add timeout (5 seconds) to prevent blocking

**Discord Embed Structure:**

```python
@dataclass
class DiscordEmbed:
    title: str
    description: str
    color: int  # Hex color as int (0x00FF00 for green)
    fields: list[dict] | None = None  # [{"name": "...", "value": "...", "inline": True}]
    timestamp: str | None = None  # ISO format
```

**Color Scheme:**

- Started: Blue (0x3498DB)
- Task completed: Green (0x2ECC71)
- Task failed: Red (0xE74C3C)
- Escalation needed: Orange (0xF39C12)
- Milestone completed: Purple (0x9B59B6)

**Acceptance Criteria:**

- [ ] `send_discord_message()` posts to webhook URL
- [ ] Rich embeds render correctly in Discord
- [ ] Webhook failures are logged, not raised
- [ ] Request timeout prevents blocking

---

### Task 1.3: Create notification formatters

**File:** `orchestrator/discord_notifier.py`
**Type:** CODING

**Description:**
Add helper functions to format orchestrator events as Discord embeds.

**Implementation Notes:**

Create these formatter functions:

```python
def format_milestone_started(milestone_id: str, total_tasks: int) -> DiscordEmbed
def format_task_completed(task_id: str, title: str, duration_s: float, cost_usd: float) -> DiscordEmbed
def format_task_failed(task_id: str, title: str, error: str) -> DiscordEmbed
def format_escalation_needed(task_id: str, title: str, question: str, options: list[str] | None) -> DiscordEmbed
def format_milestone_completed(milestone_id: str, completed: int, total: int, cost_usd: float, duration_s: float) -> DiscordEmbed
```

**Example Output:**

Escalation embed:
```
🚨 Escalation Needed
Task 1.3: Implement feature X

Claude needs input:
"Should I use approach A or B for the database schema?"

Options:
• A) Normalized schema
• B) Denormalized for performance
```

**Acceptance Criteria:**

- [ ] All 5 formatters produce valid embeds
- [ ] Embeds are readable and informative
- [ ] Long text is truncated appropriately (Discord limit: 4096 chars for description)

---

### Task 1.4: Integrate with milestone runner

**File:** `orchestrator/milestone_runner.py`
**Type:** CODING

**Description:**
Add Discord notification calls to milestone execution lifecycle.

**Implementation Notes:**

- Import discord notifier functions
- Get webhook URL from config
- Add notification calls at these points:
  1. Milestone started (in `run_milestone()`)
  2. Task completed (in task completion callback)
  3. Task failed (in task failure handling)
  4. Escalation needed (before waiting for user input)
  5. Milestone completed (at end of `run_milestone()`)
- All notifications are fire-and-forget (don't await, use `asyncio.create_task`)
- Check `config.discord_enabled` before sending

**Integration Pattern:**

```python
if config.discord_enabled:
    asyncio.create_task(
        send_discord_message(
            config.discord_webhook_url,
            format_milestone_started(milestone_id, total_tasks)
        )
    )
```

**Acceptance Criteria:**

- [ ] Notifications sent at all 5 lifecycle points
- [ ] Notifications don't block execution
- [ ] Works correctly when Discord is disabled
- [ ] No errors when webhook URL is invalid (graceful failure)

---

### Task 1.5: Add tests and documentation

**Files:**
- `orchestrator/tests/test_discord_notifier.py`
- `README.md` or `docs/` update

**Type:** CODING

**Description:**
Add unit tests for the Discord notifier and document the feature.

**Test Coverage:**

1. `test_send_discord_message_posts_to_webhook` — mock httpx, verify POST
2. `test_send_discord_message_handles_timeout` — mock timeout, verify no exception
3. `test_send_discord_message_handles_error_response` — mock 400/500, verify logged
4. `test_format_milestone_started_produces_valid_embed`
5. `test_format_task_completed_produces_valid_embed`
6. `test_format_escalation_needed_produces_valid_embed`
7. `test_format_escalation_truncates_long_text`
8. `test_config_loads_discord_webhook_url`
9. `test_config_discord_enabled_false_when_no_url`

**Documentation:**

Add a section to orchestrator README or create `docs/architecture/remote-coding/discord/README.md`:

- How to set up Discord webhook
- Environment variable configuration
- Example notification screenshots (optional)

**Acceptance Criteria:**

- [ ] All tests pass
- [ ] Tests mock external HTTP calls (no real Discord calls in tests)
- [ ] Documentation explains setup

---

### Task 1.6: E2E Verification

**Type:** VERIFICATION

**Description:**
Verify Discord notifications work end-to-end with a real webhook.

**Test Steps:**

```bash
# 1. Set webhook URL
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."

# 2. Verify config loads it
uv run python -c "
from orchestrator.config import OrchestratorConfig
config = OrchestratorConfig.from_env()
print(f'Discord enabled: {config.discord_enabled}')
print(f'Webhook URL: {config.discord_webhook_url[:50]}...')
"

# 3. Test direct notification
uv run python -c "
import asyncio
from orchestrator.config import OrchestratorConfig
from orchestrator.discord_notifier import send_discord_message, format_milestone_started

config = OrchestratorConfig.from_env()
embed = format_milestone_started('test-milestone', 3)
asyncio.run(send_discord_message(config.discord_webhook_url, embed))
print('Check Discord for notification!')
"

# 4. Run a real milestone with notifications
uv run orchestrator run orchestrator/test_plans/health_check.md

# 5. Verify in Discord:
#    - Milestone started notification
#    - Task completion notifications
#    - Milestone completed notification

# 6. Quality gates
make quality
uv run pytest orchestrator/tests/test_discord_notifier.py -v
```

**Success Criteria:**

- [ ] Notifications appear in Discord channel
- [ ] Embeds are formatted correctly with colors
- [ ] All lifecycle events produce notifications
- [ ] Quality gates pass

---

## Milestone Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `uv run pytest orchestrator/tests/test_discord_notifier.py`
- [ ] E2E test passes (Task 1.6)
- [ ] Quality gates pass: `make quality`
- [ ] Discord notifications verified in real channel
- [ ] Branch ready for merge: `feature/discord-notifications`

## Future Enhancements (Out of Scope)

These are deferred to future milestones:

1. **Escalation responses via Discord** — Bot that receives button clicks
2. **Full conversation mode** — Stream all tool calls to Discord
3. **Slack/Teams support** — Same pattern, different webhook format
4. **Configurable verbosity** — Choose which events to notify
