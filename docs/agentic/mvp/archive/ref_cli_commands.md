# Reference: Agent CLI Commands

This document specifies the CLI commands for inspecting and controlling the agent system.

---

## Commands Overview

| Command | Purpose |
|---------|---------|
| `ktrdr agent status` | Show current cycle and recent history |
| `ktrdr agent history` | Show detailed cycle history |
| `ktrdr agent session <id>` | Show full details for a session |
| `ktrdr agent budget` | Show budget status |
| `ktrdr agent trigger` | Manually trigger a check |
| `ktrdr agent pause` | Pause automatic triggering |
| `ktrdr agent resume` | Resume automatic triggering |

---

## ktrdr agent status

Shows current cycle state and recent history at a glance.

```
$ ktrdr agent status

=== Current Cycle ===
Session: #42
Phase: TRAINING
Strategy: momentum_breakout_20240115_143022
Started: 15 minutes ago
Training Operation: op_abc123 (running, 67% complete)

=== Recent Cycles ===
#41  momentum_ema_cross        SUCCESS   Sharpe: 0.82  (2 hours ago)
#40  mean_reversion_rsi        FAILED    Gate: backtest, win_rate 41%  (4 hours ago)
#39  volatility_breakout_atr   SUCCESS   Sharpe: 0.34  (6 hours ago)

=== Today's Budget ===
Used: $1.24 / $5.00 (24.8%)
Invocations: 18
Cycles: 3 completed, 1 active
```

---

## ktrdr agent history

Shows detailed cycle history.

**Options:**
- `--limit N` - Number of cycles to show (default: 10)
- `--outcome <outcome>` - Filter by outcome (success, failed_*, etc.)

```
$ ktrdr agent history --limit 5

Session #42 - momentum_breakout_20240115_143022
  Status: TRAINING (in progress)
  Started: 2024-01-15 14:30:22
  Training: op_abc123 (running)
  
Session #41 - momentum_ema_cross
  Status: SUCCESS
  Duration: 45 minutes
  Training: accuracy=52.3%, loss=0.42
  Backtest: sharpe=0.82, win_rate=54.2%, drawdown=12.3%
  Assessment: "Strategy shows consistent edge in trending markets..."
  Cost: $0.08
  
Session #40 - mean_reversion_rsi
  Status: FAILED (backtest_gate)
  Duration: 38 minutes
  Training: accuracy=48.1%, loss=0.51
  Backtest: sharpe=-0.12, win_rate=41.2%, drawdown=28.4%
  Gate Reason: Win rate 41.2% below 45% threshold
  Cost: $0.06

...
```

---

## ktrdr agent session <id>

Shows full details for a specific session.

```
$ ktrdr agent session 41

=== Session #41 ===
Strategy: momentum_ema_cross
Status: SUCCESS
Created: 2024-01-15 12:45:00
Completed: 2024-01-15 13:30:22
Duration: 45 minutes

=== Strategy Config ===
Hypothesis: "Capture momentum using EMA crossovers"
Indicators: ema_12, ema_26, rsi_14
Symbols: EURUSD (training), GBPUSD (backtest)
Timeframe: 1h

=== Training Results ===
Operation: op_training_abc123
Accuracy: 52.3%
Final Loss: 0.42
Epochs: 47/50 (early stopped)

=== Backtest Results ===
Operation: op_backtest_def456
Sharpe Ratio: 0.82
Win Rate: 54.2%
Max Drawdown: 12.3%
Total Trades: 156
Profit Factor: 1.34

=== Assessment ===
Passed: Yes
Explanation: "Strategy shows consistent edge in trending markets.
The EMA crossover combined with RSI confirmation produces reliable
signals. Weakness: performs poorly in ranging markets. Suggestion:
add volatility filter to avoid choppy periods."

=== Cost ===
Tokens: 2,847 input / 1,203 output
Estimated: $0.08

=== Actions ===
14:30:22  get_recent_strategies(n=5)
14:30:25  get_available_indicators()
14:30:28  save_strategy_config("momentum_ema_cross", {...})
14:30:31  start_training(...)
14:30:33  update_agent_state(phase="training")
15:12:45  start_backtest(...)
15:12:48  update_agent_state(phase="backtesting")
15:30:15  update_agent_state(assessment={...}, outcome="success")
```

---

## ktrdr agent budget

Shows budget status.

**Options:**
- `--days N` - Show history for N days (default: 7)

```
$ ktrdr agent budget

=== Today (2024-01-15) ===
Limit: $5.00
Used: $1.24 (24.8%)
Remaining: $3.76

Invocations: 18
Avg cost/invocation: $0.07

=== This Week ===
Mon: $3.42 / $5.00 (12 cycles, 8 successful)
Tue: $4.87 / $5.00 (16 cycles, 11 successful)
Wed: $1.24 / $5.00 (4 cycles, 3 successful) <- today
```

**Set budget:**
```
$ ktrdr agent budget set 10.00
Budget limit updated to $10.00/day
```

---

## ktrdr agent trigger

Manually triggers a check (useful for testing).

```
$ ktrdr agent trigger

Checking for work...
Found: No active session, budget available
Action: Invoking agent with reason 'start_new_cycle'
Session #43 created
```

---

## ktrdr agent pause / resume

Control automatic triggering.

```
$ ktrdr agent pause
Agent triggering paused. Use 'ktrdr agent resume' to restart.

$ ktrdr agent status
...
⚠️  Automatic triggering is PAUSED

$ ktrdr agent resume
Agent triggering resumed.
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Agent not configured |
| 3 | Budget exceeded |
| 4 | No active session found (for session-specific commands) |
