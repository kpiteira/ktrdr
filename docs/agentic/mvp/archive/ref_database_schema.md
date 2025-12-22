# Reference: Agent Database Schema

This document contains the database schema for the autonomous agent system.

---

## Tables Overview

| Table | Purpose |
|-------|---------|
| `agent_sessions` | Tracks each research cycle from start to finish |
| `agent_actions` | Logs every tool call the agent makes |
| `agent_triggers` | Logs every trigger event (whether agent was invoked or not) |
| `agent_metrics` | Aggregated metrics per completed cycle |
| `agent_budget` | Daily budget tracking |

---

## agent_sessions

Tracks each research cycle from start to finish.

```sql
CREATE TABLE agent_sessions (
    id SERIAL PRIMARY KEY,
    
    -- State
    phase VARCHAR(20) NOT NULL DEFAULT 'idle',
    -- Values: 'idle', 'designing', 'training', 'backtesting', 'assessing'
    
    -- Strategy
    strategy_name VARCHAR(100),
    strategy_config JSONB,
    strategy_file_path VARCHAR(255),
    
    -- Operations
    training_operation_id VARCHAR(100),
    backtest_operation_id VARCHAR(100),
    
    -- Results
    training_results JSONB,
    backtest_results JSONB,
    
    -- Assessment (filled by agent)
    assessment JSONB,
    /*
    {
        "passed": boolean,
        "explanation": "text explanation",
        "metrics": {
            "sharpe": float,
            "win_rate": float,
            "max_drawdown": float,
            ...
        }
    }
    */
    
    -- Outcome
    outcome VARCHAR(30),
    -- Values: 'success', 'failed_design', 'failed_training', 'failed_training_gate',
    --         'failed_backtest', 'failed_backtest_gate', 'failed_assessment'
    failure_reason TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    
    CONSTRAINT valid_phase CHECK (phase IN ('idle', 'designing', 'training', 'backtesting', 'assessing'))
);

CREATE INDEX idx_sessions_phase ON agent_sessions(phase);
CREATE INDEX idx_sessions_outcome ON agent_sessions(outcome);
CREATE INDEX idx_sessions_created ON agent_sessions(created_at DESC);
```

---

## agent_actions

Logs every tool call the agent makes (for debugging and cost tracking).

```sql
CREATE TABLE agent_actions (
    id SERIAL PRIMARY KEY,
    session_id INT REFERENCES agent_sessions(id) ON DELETE CASCADE,
    
    action_at TIMESTAMPTZ DEFAULT NOW(),
    tool_name VARCHAR(100) NOT NULL,
    tool_args JSONB,
    tool_result JSONB,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    
    -- Cost tracking
    tokens_input INT,
    tokens_output INT
);

CREATE INDEX idx_actions_session ON agent_actions(session_id);
CREATE INDEX idx_actions_tool ON agent_actions(tool_name);
```

---

## agent_triggers

Logs every trigger check (whether or not agent was invoked).

```sql
CREATE TABLE agent_triggers (
    id SERIAL PRIMARY KEY,
    
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    trigger_reason VARCHAR(50) NOT NULL,
    -- Values: 'start_new_cycle', 'training_completed', 'training_failed',
    --         'backtest_completed', 'backtest_failed', 'gate_check'
    
    session_id INT REFERENCES agent_sessions(id),
    context JSONB,  -- Data passed to agent
    
    -- Decision
    agent_invoked BOOLEAN DEFAULT FALSE,
    skip_reason VARCHAR(100),  -- If not invoked, why?
    -- e.g., 'budget_exceeded', 'operation_still_running', 'gate_failed'
    
    -- Budget tracking
    budget_used_today_usd DECIMAL(10, 4),
    budget_remaining_usd DECIMAL(10, 4)
);

CREATE INDEX idx_triggers_date ON agent_triggers(triggered_at DESC);
CREATE INDEX idx_triggers_session ON agent_triggers(session_id);
```

---

## agent_metrics

Aggregated metrics per completed cycle for easy querying.

```sql
CREATE TABLE agent_metrics (
    id SERIAL PRIMARY KEY,
    session_id INT UNIQUE REFERENCES agent_sessions(id) ON DELETE CASCADE,
    
    -- Timing
    cycle_started_at TIMESTAMPTZ,
    cycle_completed_at TIMESTAMPTZ,
    cycle_duration_seconds INT,
    
    -- Training metrics
    training_accuracy DECIMAL(5, 4),
    training_final_loss DECIMAL(10, 6),
    training_epochs_completed INT,
    training_early_stopped BOOLEAN,
    
    -- Backtest metrics (null if gate failed)
    backtest_sharpe DECIMAL(10, 4),
    backtest_win_rate DECIMAL(5, 4),
    backtest_max_drawdown DECIMAL(5, 4),
    backtest_total_trades INT,
    backtest_profit_factor DECIMAL(10, 4),
    
    -- Cost
    total_tokens_input INT,
    total_tokens_output INT,
    estimated_cost_usd DECIMAL(10, 4),
    
    -- Outcome
    outcome VARCHAR(30),
    gate_failed VARCHAR(30)  -- 'training' or 'backtest' if applicable
);

CREATE INDEX idx_metrics_outcome ON agent_metrics(outcome);
CREATE INDEX idx_metrics_date ON agent_metrics(cycle_completed_at DESC);
```

---

## agent_budget

Daily budget tracking.

```sql
CREATE TABLE agent_budget (
    id SERIAL PRIMARY KEY,
    date DATE UNIQUE NOT NULL DEFAULT CURRENT_DATE,
    
    budget_limit_usd DECIMAL(10, 4) DEFAULT 5.00,
    budget_used_usd DECIMAL(10, 4) DEFAULT 0.00,
    
    invocations_count INT DEFAULT 0,
    cycles_started INT DEFAULT 0,
    cycles_completed INT DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_budget_date ON agent_budget(date);
```

---

## Useful Queries

### Current cycle status
```sql
SELECT * FROM agent_sessions 
WHERE phase != 'idle' 
ORDER BY created_at DESC 
LIMIT 1;
```

### Recent completed cycles
```sql
SELECT s.id, s.strategy_name, s.outcome, m.backtest_sharpe, m.estimated_cost_usd
FROM agent_sessions s
JOIN agent_metrics m ON s.id = m.session_id
ORDER BY s.completed_at DESC
LIMIT 10;
```

### Today's budget status
```sql
SELECT * FROM agent_budget WHERE date = CURRENT_DATE;
```

### Cost per successful strategy
```sql
SELECT AVG(estimated_cost_usd), COUNT(*)
FROM agent_metrics 
WHERE outcome = 'success';
```
