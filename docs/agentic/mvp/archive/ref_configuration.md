# Reference: Agent Configuration

This document specifies all configuration options for the agent system.

---

## ⚠️ Architecture Update (December 2024)

The agent now uses the Anthropic Python SDK directly instead of Claude Code CLI.

See [ARCHITECTURE_DECISION_anthropic_api.md](ARCHITECTURE_DECISION_anthropic_api.md) for details.

---

## Environment Variables

### Anthropic API Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (required) | Anthropic API key for Claude access |
| `AGENT_MODEL` | `claude-sonnet-4-20250514` | Model ID (sonnet for cost, opus for quality) |

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_ENABLED` | `false` | Enable/disable agent background loop |
| `AGENT_TRIGGER_INTERVAL_SECONDS` | `300` | Trigger interval (5 minutes) |
| `AGENT_RECENT_STRATEGIES_COUNT` | `5` | How many recent strategies to show agent |

### Budget Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_BUDGET_DAILY_USD` | `5.00` | Maximum daily spend |
| `AGENT_BUDGET_BUFFER_USD` | `0.10` | Buffer to keep (don't spend last $0.10) |

### Training Quality Gate

| Variable | Default | Description |
|----------|---------|-------------|
| `GATE_TRAINING_MIN_ACCURACY` | `0.45` | Minimum training accuracy (45%) |
| `GATE_TRAINING_MAX_LOSS` | `0.8` | Maximum final loss |
| `GATE_TRAINING_MIN_LOSS_REDUCTION` | `0.20` | Minimum loss reduction from initial (20%) |

### Backtest Quality Gate

| Variable | Default | Description |
|----------|---------|-------------|
| `GATE_BACKTEST_MIN_WIN_RATE` | `0.45` | Minimum win rate (45%) |
| `GATE_BACKTEST_MAX_DRAWDOWN` | `0.40` | Maximum drawdown (40%) |
| `GATE_BACKTEST_MIN_SHARPE` | `-0.5` | Minimum Sharpe ratio |

### Retry Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_RETRY_MAX_ATTEMPTS` | `3` | Max retries for API calls |
| `AGENT_RETRY_BACKOFF_BASE` | `2` | Exponential backoff base (seconds) |

---

## Feature Flags

| Flag | Default | Description |
|------|---------|-------------|
| `AGENT_BUDGET_ENFORCEMENT` | `true` | Enforce budget limits |
| `AGENT_EARLY_STOPPING_REQUIRED` | `false` | Require early stopping config in strategies |

---

## Example .env

```bash
# Anthropic API
ANTHROPIC_API_KEY=sk-ant-api03-...
AGENT_MODEL=claude-sonnet-4-20250514  # Or claude-opus-4-20250514 for higher quality

# Agent Core
AGENT_ENABLED=true
AGENT_TRIGGER_INTERVAL_SECONDS=300
AGENT_RECENT_STRATEGIES_COUNT=5

# Budget
AGENT_BUDGET_DAILY_USD=5.00

# Quality Gates - Training
GATE_TRAINING_MIN_ACCURACY=0.45
GATE_TRAINING_MAX_LOSS=0.8
GATE_TRAINING_MIN_LOSS_REDUCTION=0.20

# Quality Gates - Backtest
GATE_BACKTEST_MIN_WIN_RATE=0.45
GATE_BACKTEST_MAX_DRAWDOWN=0.40
GATE_BACKTEST_MIN_SHARPE=-0.5

# Retries
AGENT_RETRY_MAX_ATTEMPTS=3
```

---

## Runtime Configuration

Some settings can be changed at runtime via CLI:

```bash
# Change daily budget
ktrdr agent budget set 10.00

# Pause/resume
ktrdr agent pause
ktrdr agent resume
```

---

## Notes

- All thresholds are starting points and should be tuned based on observed data
- Quality gate thresholds are intentionally loose for MVP (we want data on what fails)
- Budget is enforced at trigger time, not during agent execution
