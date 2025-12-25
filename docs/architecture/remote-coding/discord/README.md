# Discord Notifications

Real-time Discord notifications for orchestrator events. Get visibility into milestone progress, task completions, and escalations without watching the terminal.

## Setup

### 1. Create a Discord Webhook

1. Open Discord and go to your server
2. Right-click on the channel where you want notifications
3. Select **Edit Channel** > **Integrations** > **Webhooks**
4. Click **New Webhook**
5. Give it a name (e.g., "Orchestrator")
6. Copy the **Webhook URL**

### 2. Configure the Environment Variable

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
```

For persistent configuration, add to your shell profile or `.env` file.

### 3. Verify Configuration

```bash
uv run python -c "
from orchestrator.config import OrchestratorConfig
config = OrchestratorConfig.from_env()
print(f'Discord enabled: {config.discord_enabled}')
"
```

## Notification Types

| Event | Color | Description |
|-------|-------|-------------|
| Milestone Started | Blue | When a milestone begins execution |
| Task Completed | Green | Each task completion with duration and cost |
| Task Failed | Red | Task failures with error message |
| Escalation Needed | Orange | When Claude needs human input |
| Milestone Completed | Purple | Final summary with stats |

## Graceful Degradation

When `DISCORD_WEBHOOK_URL` is not set:
- Discord notifications are silently skipped
- No errors or warnings
- Orchestrator functions normally

When webhook fails (invalid URL, network issues):
- Failure is logged as a warning
- Execution continues uninterrupted
- No retry attempts (fire-and-forget)

## Testing

Send a test notification:

```bash
uv run python -c "
import asyncio
from orchestrator.config import OrchestratorConfig
from orchestrator.discord_notifier import send_discord_message, format_milestone_started

config = OrchestratorConfig.from_env()
if config.discord_enabled:
    embed = format_milestone_started('test-milestone', 3)
    asyncio.run(send_discord_message(config.discord_webhook_url, embed))
    print('Check Discord for the notification!')
else:
    print('DISCORD_WEBHOOK_URL not set')
"
```

## Architecture

```
milestone_runner.py
    |
    +-- discord_notifier.py
    |       |
    |       +-- send_discord_message()  # async, fire-and-forget
    |       +-- format_*() functions    # event -> DiscordEmbed
    |
    +-- config.py
            |
            +-- discord_webhook_url     # from DISCORD_WEBHOOK_URL env
            +-- discord_enabled         # bool property
```

Notifications are sent with `asyncio.create_task()` so they don't block milestone execution. A 5-second timeout prevents hanging on slow webhooks.
