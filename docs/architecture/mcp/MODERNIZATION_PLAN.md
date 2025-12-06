# MCP Server Modernization Plan

**Status**: Planning
**Created**: 2024-11-29
**Estimated Effort**: Medium (2-3 sessions)

---

## Executive Summary

The current MCP server uses only ~20% of the MCP SDK's capabilities. This plan modernizes it to leverage:
- **Resources** for data exposure
- **Prompts** for guided workflows
- **Context injection** for progress/logging
- **Lifespan management** for connection reuse

Expected benefits:
- Better Claude UX with guided workflows
- Real-time progress visibility
- Faster tool execution (connection reuse)
- Richer data discovery via resources

---

## Current Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ server.py                                                    │
│                                                              │
│  mcp = FastMCP("KTRDR-Trading-Research")                    │
│                                                              │
│  @mcp.tool() ─────────────────────────────────────────────┐ │
│  │ 20 tools (hello, health, data, training, backtest...) │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Each tool creates new API client per call                   │
└─────────────────────────────────────────────────────────────┘
```

## Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ server.py                                                    │
│                                                              │
│  mcp = FastMCP(                                             │
│      "KTRDR-Trading-Research",                              │
│      lifespan=app_lifespan,      # Shared API client        │
│      instructions="...",          # Server guidance          │
│  )                                                           │
│                                                              │
│  @mcp.resource() ─────────────────────────────────────────┐ │
│  │ data://summary/{symbol}/{tf}  - Data summaries         │ │
│  │ config://strategy/{name}      - Strategy configs       │ │
│  │ status://workers              - Worker status          │ │
│  │ status://operations           - Active operations      │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  @mcp.prompt() ───────────────────────────────────────────┐ │
│  │ train_model_workflow     - Guided training             │ │
│  │ backtest_workflow        - Guided backtesting          │ │
│  │ data_exploration         - Guided data analysis        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  @mcp.tool() with ctx: Context ───────────────────────────┐ │
│  │ All existing tools + progress reporting + logging      │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Tasks

### Phase 1: Foundation (Low Risk)

#### Task 1.1: Add Lifespan Management
**File**: `mcp/src/server.py`
**Effort**: Small
**Risk**: Low

Add lifespan context manager for shared API client:

```python
from contextlib import asynccontextmanager
from dataclasses import dataclass

@dataclass
class AppContext:
    client: KTRDRAPIClient

@asynccontextmanager
async def app_lifespan(server: FastMCP):
    """Manage API client lifecycle."""
    client = KTRDRAPIClient()
    await client.__aenter__()
    try:
        yield AppContext(client=client)
    finally:
        await client.__aexit__(None, None, None)

mcp = FastMCP(
    "KTRDR-Trading-Research",
    lifespan=app_lifespan,
)
```

**Acceptance Criteria**:
- [ ] Single API client instance per server session
- [ ] Proper cleanup on shutdown
- [ ] All existing tools continue to work

---

#### Task 1.2: Add Server Instructions
**File**: `mcp/src/server.py`
**Effort**: Small
**Risk**: Low

Add server-level instructions:

```python
mcp = FastMCP(
    "KTRDR-Trading-Research",
    lifespan=app_lifespan,
    instructions="""
KTRDR MCP Server - AI-powered trading strategy research.

IMPORTANT WORKFLOWS:
1. Always check backend health first: check_backend_health()
2. Data flow: load data → train model → backtest strategy
3. Long operations return operation_id - poll with get_operation_status()

BEST PRACTICES:
- Use list_operations(active_only=True) to find running operations
- Check get_data_summary() before loading large datasets
- Training can take 5-60 minutes - use progress polling
""",
)
```

**Acceptance Criteria**:
- [ ] Instructions visible to Claude
- [ ] Helps Claude understand workflows

---

### Phase 2: Prompts (High Value, Low Risk)

#### Task 2.1: Add Training Workflow Prompt
**File**: `mcp/src/server.py`
**Effort**: Small
**Risk**: Low

```python
@mcp.prompt()
def train_model_workflow(
    symbol: str = "AAPL",
    strategy: str = "neuro_mean_reversion",
    timeframe: str = "1h"
) -> str:
    """Guided workflow for training a neural network model."""
    return f"""
## Training Workflow for {symbol}

### Step 1: Check System Health
```
health = await check_backend_health()
if health["status"] != "healthy":
    STOP - fix backend issues first
```

### Step 2: Check Data Availability
```
summary = await get_data_summary("{symbol}", "{timeframe}")
if not summary["data"]["data_available"]:
    # Load data first
    result = await trigger_data_loading("{symbol}", "{timeframe}", mode="local")
    # Poll until complete
    while status["data"]["status"] == "running":
        status = await get_operation_status(result["data"]["operation_id"])
        wait 5 seconds
```

### Step 3: Start Training
```
result = await start_training(
    symbols=["{symbol}"],
    timeframes=["{timeframe}"],
    strategy_name="{strategy}"
)
operation_id = result["data"]["operation_id"]
```

### Step 4: Monitor Progress
```
while True:
    status = await get_operation_status(operation_id)
    print(f"Progress: {{status['data']['progress_percentage']}}%")
    if status["data"]["status"] in ["completed", "failed"]:
        break
    wait 30 seconds
```

### Step 5: Get Results
```
results = await get_operation_results(operation_id)
print(f"Model accuracy: {{results['data']['metrics']['accuracy']}}")
```
"""
```

**Acceptance Criteria**:
- [ ] Prompt appears in Claude's prompt list
- [ ] Workflow is accurate and helpful

---

#### Task 2.2: Add Backtest Workflow Prompt
**File**: `mcp/src/server.py`
**Effort**: Small
**Risk**: Low

```python
@mcp.prompt()
def backtest_workflow(
    symbol: str = "EURUSD",
    strategy: str = "neuro_mean_reversion",
    timeframe: str = "1d"
) -> str:
    """Guided workflow for backtesting a trading strategy."""
    return f"""
## Backtesting Workflow for {symbol}

### Prerequisites
- Trained model exists for {strategy}
- Data available for {symbol}/{timeframe}

### Step 1: Start Backtest
```
result = await start_backtest(
    strategy_name="{strategy}",
    symbol="{symbol}",
    timeframe="{timeframe}",
    start_date="2024-01-01",
    end_date="2024-12-31",
    initial_capital=100000.0
)
operation_id = result["operation_id"]
```

### Step 2: Monitor Progress
```
while True:
    status = await get_operation_status(operation_id)
    if status["data"]["status"] != "running":
        break
    wait 2 seconds
```

### Step 3: Analyze Results
Key metrics to check:
- Total return (%)
- Sharpe ratio (>1.0 is good, >2.0 is excellent)
- Max drawdown (lower is better)
- Win rate (%)
- Number of trades

```
results = await get_operation_results(operation_id)
```
"""
```

---

#### Task 2.3: Add Data Exploration Prompt
**File**: `mcp/src/server.py`
**Effort**: Small
**Risk**: Low

```python
@mcp.prompt()
def explore_data(symbol: str = "AAPL") -> str:
    """Guided workflow for exploring market data."""
    return f"""
## Data Exploration for {symbol}

### Step 1: Check Available Data
```
summary = await get_data_summary("{symbol}", "1h")
```

### Step 2: Get Recent Data Sample
```
data = await get_market_data(
    symbol="{symbol}",
    timeframe="1h",
    limit_bars=50  # Keep small for analysis
)
```

### Step 3: Analyze Data Structure
The response contains:
- dates: List of timestamps
- open, high, low, close: Price arrays
- volume: Volume array
- metadata: Data range info

### Tips
- Use limit_bars to control response size
- Use start_date/end_date for specific ranges
- trading_hours_only=True filters out extended hours
"""
```

---

### Phase 3: Resources (High Value, Medium Risk)

#### Task 3.1: Add Data Summary Resource
**File**: `mcp/src/server.py`
**Effort**: Medium
**Risk**: Medium

```python
@mcp.resource("data://summary/{symbol}/{timeframe}")
async def data_summary_resource(symbol: str, timeframe: str, ctx: Context) -> str:
    """Data summary for a symbol/timeframe combination."""
    client = ctx.request_context.lifespan_context.client
    try:
        data = await client.data.get_cached_data(
            symbol=symbol, timeframe=timeframe, limit=1
        )
        metadata = data.get("data", {}).get("metadata", {})
        return json.dumps({
            "symbol": symbol,
            "timeframe": timeframe,
            "available": len(data.get("data", {}).get("dates", [])) > 0,
            "metadata": metadata
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
```

**Acceptance Criteria**:
- [ ] Resource appears in resource list
- [ ] Returns accurate metadata
- [ ] Handles errors gracefully

---

#### Task 3.2: Add Strategy Config Resource
**File**: `mcp/src/server.py`
**Effort**: Medium
**Risk**: Low

```python
@mcp.resource("config://strategies")
async def strategies_list_resource(ctx: Context) -> str:
    """List of all available trading strategies."""
    client = ctx.request_context.lifespan_context.client
    response = await client.strategies.list_strategies()
    return json.dumps(response, indent=2)
```

---

#### Task 3.3: Add Operations Status Resource
**File**: `mcp/src/server.py`
**Effort**: Medium
**Risk**: Low

```python
@mcp.resource("status://operations/active")
async def active_operations_resource(ctx: Context) -> str:
    """Currently active operations."""
    client = ctx.request_context.lifespan_context.client
    result = await client.operations.list_operations(active_only=True, limit=20)
    return json.dumps(result, indent=2)
```

---

### Phase 4: Context Integration (High Value, Medium Risk)

#### Task 4.1: Add Context to Long-Running Tools
**File**: `mcp/src/server.py`
**Effort**: Medium
**Risk**: Medium

Update tools that trigger long operations to use context:

```python
from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession

@mcp.tool()
async def start_training(
    symbols: list[str],
    timeframes: list[str],
    strategy_name: str,
    ctx: Context[ServerSession, AppContext],  # ADD THIS
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    """Train a neural network model on market data (async)."""

    # Log start
    await ctx.info(f"Starting training for {symbols} with {strategy_name}")

    client = ctx.request_context.lifespan_context.client

    # Report initial progress
    await ctx.report_progress(0.0, 1.0, "Submitting training request")

    result = await client.training.start_neural_training(
        symbols=symbols,
        timeframes=timeframes,
        strategy_name=strategy_name,
        start_date=start_date,
        end_date=end_date,
    )

    await ctx.report_progress(0.1, 1.0, "Training submitted to worker")
    await ctx.info(f"Training operation started: {result.get('operation_id')}")

    return result
```

**Acceptance Criteria**:
- [ ] Progress appears in Claude UI
- [ ] Logging visible in debug mode
- [ ] No breaking changes to existing behavior

---

#### Task 4.2: Update All Tools to Use Shared Client
**File**: `mcp/src/server.py`
**Effort**: Medium
**Risk**: Medium

Replace all `async with get_api_client() as client:` patterns with context access:

```python
# BEFORE
@mcp.tool()
async def check_backend_health() -> dict[str, Any]:
    async with get_api_client() as client:
        health_data = await client.health_check()
        return {...}

# AFTER
@mcp.tool()
async def check_backend_health(ctx: Context[ServerSession, AppContext]) -> dict[str, Any]:
    client = ctx.request_context.lifespan_context.client
    health_data = await client.system.health_check()
    return {...}
```

---

## Testing Strategy

### Unit Tests
- [ ] Test lifespan creates/destroys client correctly
- [ ] Test each resource returns valid JSON
- [ ] Test prompts return valid strings

### Integration Tests
- [ ] Test full training workflow via prompt
- [ ] Test resource access from Claude
- [ ] Test progress reporting visibility

### Manual Testing
- [ ] Verify all tools still work in Claude Desktop
- [ ] Verify prompts appear and are useful
- [ ] Verify resources are discoverable

---

## Rollback Plan

Each phase is independent. If issues arise:
1. Revert the specific phase's changes
2. Tools will fall back to individual client instances
3. No data loss or corruption risk

---

## Migration Checklist

### Phase 1 (Foundation)
- [ ] Add lifespan management
- [ ] Add server instructions
- [ ] Test existing tools still work
- [ ] Commit

### Phase 2 (Prompts)
- [ ] Add train_model_workflow prompt
- [ ] Add backtest_workflow prompt
- [ ] Add explore_data prompt
- [ ] Test prompts in Claude
- [ ] Commit

### Phase 3 (Resources)
- [ ] Add data summary resource
- [ ] Add strategies resource
- [ ] Add operations resource
- [ ] Test resource access
- [ ] Commit

### Phase 4 (Context)
- [ ] Add Context to start_training
- [ ] Add Context to start_backtest
- [ ] Add Context to trigger_data_loading
- [ ] Update remaining tools to use shared client
- [ ] Test progress reporting
- [ ] Commit

---

## Estimated Timeline

| Phase | Effort | Sessions |
|-------|--------|----------|
| Phase 1: Foundation | Small | 0.5 |
| Phase 2: Prompts | Small | 0.5 |
| Phase 3: Resources | Medium | 1 |
| Phase 4: Context | Medium | 1 |
| **Total** | | **3 sessions** |

---

## Open Questions

1. **Resource caching**: Should resources be cached? For how long?
2. **Progress granularity**: How often should we report progress?
3. **Error handling**: Should resources return errors or empty data?

---

## References

- [MCP Python SDK Documentation](https://github.com/modelcontextprotocol/python-sdk)
- [FastMCP Examples](https://github.com/modelcontextprotocol/python-sdk/tree/main/examples)
- [Current MCP Server](mcp/src/server.py)
