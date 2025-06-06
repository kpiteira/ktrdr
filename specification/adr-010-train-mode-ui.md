# ADR-010: Train Mode UI and Backtest Analysis Features

## Status
**Draft** - December 2024

## Context
With the neuro-fuzzy training system (ADR-004) and backtesting engine (ADR-005) implemented, we need a user interface that allows users to:
1. View available strategies and their training status
2. Run backtests on trained strategies with a single click
3. Analyze backtest results with detailed metrics
4. Seamlessly transition to Research mode for deeper visual analysis with all context preserved

This represents a new UI mode distinct from the existing Research mode, focusing on strategy management and performance analysis.

## Decision

### Architecture Overview

The Train mode UI will be a new major component in the frontend, parallel to Research mode:

```
Frontend Application
├── Research Mode (existing)
│   ├── Chart visualization
│   ├── Indicator controls
│   └── Fuzzy overlays
├── Train Mode (new)
│   ├── Strategy List Panel
│   ├── Backtest Results Panel
│   └── Performance Metrics Dashboard
└── Shared Components
    ├── Navigation
    ├── Data Context Manager (new)
    └── Mode Transition Handler (new)
```

### Frontend State Management (Single Source of Truth)

**Critical Design Principle**: ALL frontend UI state must live in a single, centralized store. Components should be "dumb" renderers that read from this store and dispatch actions to it.

#### State Architecture

```typescript
// frontend/src/store/trainModeStore.ts
interface TrainModeState {
  // Strategy List State
  strategies: Strategy[];
  strategiesLoading: boolean;
  strategiesError: string | null;
  
  // Selected Strategy State
  selectedStrategyName: string | null;
  
  // Backtest Execution State
  activeBacktest: {
    id: string;
    strategyName: string;
    status: 'idle' | 'starting' | 'running' | 'completed' | 'failed';
    progress: number;
    startedAt: string | null;
  } | null;
  
  // Backtest Results State
  backtestResults: {
    [backtestId: string]: BacktestResults;
  };
  
  // UI View State
  viewMode: 'list' | 'results' | 'details';
  resultsPanel: {
    selectedTab: 'metrics' | 'trades' | 'chart';
    chartTimeRange: { start: string; end: string } | null;
  };
  
  // Research Mode Transition State
  pendingResearchTransition: {
    backtestId: string;
    context: BacktestContext;
  } | null;
}

// SINGLE store instance
export const trainModeStore = createStore<TrainModeState>({
  // Initial state
  strategies: [],
  strategiesLoading: false,
  strategiesError: null,
  selectedStrategyName: null,
  activeBacktest: null,
  backtestResults: {},
  viewMode: 'list',
  resultsPanel: {
    selectedTab: 'metrics',
    chartTimeRange: null
  },
  pendingResearchTransition: null
});
```

#### Store Implementation Pattern

```typescript
// frontend/src/store/createStore.ts
export function createStore<T>(initialState: T) {
  let state = initialState;
  const listeners = new Set<(state: T) => void>();
  
  return {
    getState: () => state,
    
    setState: (updater: (prev: T) => T) => {
      state = updater(state);
      listeners.forEach(listener => listener(state));
    },
    
    subscribe: (listener: (state: T) => void) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    }
  };
}

// Hook for React components
export function useTrainModeStore() {
  const [state, setState] = useState(trainModeStore.getState());
  
  useEffect(() => {
    return trainModeStore.subscribe(setState);
  }, []);
  
  return state;
}
```

#### Actions (The ONLY way to modify state)

```typescript
// frontend/src/store/trainModeActions.ts
export const trainModeActions = {
  // Strategy List Actions
  loadStrategies: async () => {
    trainModeStore.setState(state => ({
      ...state,
      strategiesLoading: true,
      strategiesError: null
    }));
    
    try {
      const response = await fetch('/api/v1/strategies/');
      const data = await response.json();
      
      trainModeStore.setState(state => ({
        ...state,
        strategies: data.strategies,
        strategiesLoading: false
      }));
    } catch (error) {
      trainModeStore.setState(state => ({
        ...state,
        strategiesError: error.message,
        strategiesLoading: false
      }));
    }
  },
  
  selectStrategy: (strategyName: string) => {
    trainModeStore.setState(state => ({
      ...state,
      selectedStrategyName: strategyName
    }));
  },
  
  startBacktest: async (request: BacktestRequest) => {
    // Set starting state
    trainModeStore.setState(state => ({
      ...state,
      activeBacktest: {
        id: '',  // Will be set when API responds
        strategyName: request.strategyName,
        status: 'starting',
        progress: 0,
        startedAt: new Date().toISOString()
      }
    }));
    
    try {
      const response = await fetch('/api/v1/backtests/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request)
      });
      
      const data = await response.json();
      
      // Update with backtest ID
      trainModeStore.setState(state => ({
        ...state,
        activeBacktest: {
          ...state.activeBacktest!,
          id: data.backtest_id,
          status: 'running'
        }
      }));
      
      // Start polling for progress
      pollBacktestStatus(data.backtest_id);
      
    } catch (error) {
      trainModeStore.setState(state => ({
        ...state,
        activeBacktest: {
          ...state.activeBacktest!,
          status: 'failed'
        }
      }));
    }
  },
  
  updateBacktestProgress: (backtestId: string, progress: number, status: string) => {
    trainModeStore.setState(state => {
      if (state.activeBacktest?.id !== backtestId) return state;
      
      return {
        ...state,
        activeBacktest: {
          ...state.activeBacktest,
          progress,
          status: status as any
        }
      };
    });
  },
  
  setBacktestResults: (backtestId: string, results: BacktestResults) => {
    trainModeStore.setState(state => ({
      ...state,
      backtestResults: {
        ...state.backtestResults,
        [backtestId]: results
      },
      viewMode: 'results'
    }));
  },
  
  prepareResearchTransition: (backtestId: string, strategy: Strategy) => {
    const results = trainModeStore.getState().backtestResults[backtestId];
    if (!results) return;
    
    const context: BacktestContext = {
      mode: 'backtest',
      strategy,
      symbol: results.symbol,
      timeframe: results.timeframe,
      dateRange: {
        start: results.startDate,
        end: results.endDate
      },
      indicators: strategy.indicators,
      fuzzyConfig: strategy.fuzzyConfig,
      trades: results.trades,
      backtestId
    };
    
    trainModeStore.setState(state => ({
      ...state,
      pendingResearchTransition: {
        backtestId,
        context
      }
    }));
  }
};
```

### Core Components

#### 1. Strategy List Panel (Pure Component)
**File**: `frontend/src/components/train/StrategyListPanel.tsx`

```typescript
// All components are now "dumb" - they only read state and dispatch actions
export const StrategyListPanel: React.FC = () => {
  const state = useTrainModeStore();
  
  useEffect(() => {
    // Load strategies on mount
    trainModeActions.loadStrategies();
  }, []);
  
  // Pure render based on state
  if (state.strategiesLoading) {
    return <LoadingSpinner />;
  }
  
  return (
    <div className="strategy-list-panel">
      {state.strategies.map(strategy => (
        <StrategyCard
          key={strategy.name}
          strategy={strategy}
          isSelected={strategy.name === state.selectedStrategyName}
          isRunning={state.activeBacktest?.strategyName === strategy.name}
          onSelect={() => trainModeActions.selectStrategy(strategy.name)}
          onRunBacktest={() => {
            trainModeActions.startBacktest({
              strategyName: strategy.name,
              symbol: strategy.symbol,
              timeframe: strategy.timeframe,
              startDate: '2023-01-01',
              endDate: '2024-01-01'
            });
          }}
        />
      ))}
    </div>
  );
};

// Component is purely presentational - no local state!
const StrategyCard: React.FC<{
  strategy: Strategy;
  isSelected: boolean;
  isRunning: boolean;
  onSelect: () => void;
  onRunBacktest: () => void;
}> = ({ strategy, isSelected, isRunning, onSelect, onRunBacktest }) => {
  // Just render props - no state logic here
  return (
    <div 
      className={`strategy-card ${isSelected ? 'selected' : ''}`}
      onClick={onSelect}
    >
      <h3>{strategy.name}</h3>
      <p>{strategy.description}</p>
      <div className="strategy-details">
        <span>Symbol: {strategy.symbol}</span>
        <span>Timeframe: {strategy.timeframe}</span>
        <span>Indicators: {strategy.indicators.length}</span>
      </div>
      <div className="training-status">
        Status: {strategy.trainingStatus}
        {strategy.latestVersion && (
          <span> (v{strategy.latestVersion})</span>
        )}
      </div>
      <button 
        onClick={(e) => {
          e.stopPropagation();
          onRunBacktest();
        }}
        disabled={isRunning || strategy.trainingStatus !== 'trained'}
      >
        {isRunning ? 'Running...' : 'Run Backtest'}
      </button>
    </div>
  );
};
```

#### 2. Backtest Results Panel
**File**: `frontend/src/components/train/BacktestResultsPanel.tsx`

```typescript
export const BacktestResultsPanel: React.FC = () => {
  const state = useTrainModeStore();
  const navigate = useNavigate();
  
  if (!state.activeBacktest || state.activeBacktest.status !== 'completed') {
    return null;
  }
  
  const results = state.backtestResults[state.activeBacktest.id];
  const strategy = state.strategies.find(s => s.name === state.activeBacktest.strategyName);
  
  if (!results || !strategy) return null;
  
  const handleViewInResearch = () => {
    // Prepare transition
    trainModeActions.prepareResearchTransition(state.activeBacktest!.id, strategy);
    
    // Set shared context
    const context = state.pendingResearchTransition?.context;
    if (context) {
      sharedContextActions.setBacktestContext(context);
    }
    
    // Navigate to Research mode
    navigate(`/research?mode=backtest&id=${state.activeBacktest!.id}`);
  };
  
  return (
    <div className="backtest-results-panel">
      <div className="results-header">
        <h2>Backtest Results: {strategy.name}</h2>
        <button 
          onClick={handleViewInResearch}
          className="view-research-btn"
        >
          📊 Analyze in Research Mode
        </button>
      </div>
      
      <PerformanceMetricsCard metrics={results.metrics} />
      <TradeSummaryCard summary={results.summary} />
      <EquityCurveChart data={results.equityCurve} />
    </div>
  );
};
```

#### 3. Research Mode Integration
**File**: `frontend/src/components/research/enhancements/BacktestOverlay.tsx`

```typescript
export const BacktestOverlay: React.FC<{
  chartApi: any;  // TradingView chart API
}> = ({ chartApi }) => {
  const { backtestContext } = useSharedContext();
  const [tradeMarkers, setTradeMarkers] = useState<any[]>([]);
  const [hoveredTrade, setHoveredTrade] = useState<Trade | null>(null);
  
  useEffect(() => {
    if (!backtestContext || !chartApi) return;
    
    // Create trade markers for executed trades
    const markers = backtestContext.trades.map(trade => ({
      time: trade.entryTime,
      position: trade.side === 'BUY' ? 'belowBar' : 'aboveBar',
      color: trade.side === 'BUY' ? '#26a69a' : '#ef5350',
      shape: trade.side === 'BUY' ? 'arrowUp' : 'arrowDown',
      text: trade.side,
      size: 2
    }));
    
    chartApi.setMarkers(markers);
    setTradeMarkers(markers);
    
    return () => {
      chartApi.setMarkers([]);
    };
  }, [backtestContext, chartApi]);
  
  return (
    <>
      <BacktestModeIndicator />
      {hoveredTrade && <TradeDetailsPopup trade={hoveredTrade} />}
    </>
  );
};

const BacktestModeIndicator: React.FC = () => {
  const { backtestContext } = useSharedContext();
  
  if (!backtestContext) return null;
  
  return (
    <div className="backtest-mode-indicator">
      <span className="indicator-badge">
        📊 Viewing Backtest Results
      </span>
      <span className="strategy-name">
        {backtestContext.strategy.name}
      </span>
      <button 
        onClick={() => sharedContextActions.clearBacktestContext()}
        className="exit-backtest-btn"
      >
        ✕ Exit Backtest View
      </button>
    </div>
  );
};
```

### Backend Implementation

#### 1. API Structure Fix Required

**Current Issue**: The backtesting API endpoints exist but aren't registered in the main router.

**File**: `ktrdr/api/__init__.py` (needs update)
```python
# Add these imports to the existing file
from ktrdr.api.endpoints.backtesting import router as backtesting_router
from ktrdr.api.endpoints.strategies import router as strategies_router

# Include routers with appropriate prefixes (add to existing list)
api_router.include_router(backtesting_router, tags=["Backtesting"])  # Need to move existing code here
api_router.include_router(strategies_router, tags=["Strategies"])    # New endpoint file
```

#### 2. Move Existing Backtesting Endpoints

**Action Required**: Move the backtesting endpoints from wherever they currently are to:
**File**: `ktrdr/api/endpoints/backtesting.py`

```python
# ktrdr/api/endpoints/backtesting.py
# This should contain the existing backtesting endpoints that were created in ADR-005
# Just need to move them to follow the project's endpoint organization pattern

from fastapi import APIRouter, HTTPException, BackgroundTasks
# ... other imports ...

router = APIRouter(prefix="/api/v1/backtests")

# Move existing endpoints here:
# - POST /api/v1/backtests/
# - GET /api/v1/backtests/{backtest_id}
# - GET /api/v1/backtests/{backtest_id}/trades
# - GET /api/v1/backtests/{backtest_id}/equity_curve
```

#### 3. Create New Strategies Endpoint

**File**: `ktrdr/api/endpoints/strategies.py` (new file)

```python
# ktrdr/api/endpoints/strategies.py
from fastapi import APIRouter, HTTPException
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import yaml
import json
from datetime import datetime

router = APIRouter(prefix="/api/v1/strategies")

# Response models
class StrategyMetrics(BaseModel):
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None

class StrategyInfo(BaseModel):
    name: str
    description: str
    symbol: str
    timeframe: str
    indicators: List[Dict[str, Any]]
    fuzzy_config: Dict[str, Any]
    training_status: str  # 'untrained', 'training', 'trained', 'failed'
    available_versions: List[int]
    latest_version: Optional[int] = None
    latest_training_date: Optional[str] = None
    latest_metrics: Optional[StrategyMetrics] = None

class StrategiesResponse(BaseModel):
    strategies: List[StrategyInfo]

@router.get("/", response_model=StrategiesResponse)
async def list_strategies():
    """
    List all available strategies with their training status.
    
    This endpoint scans the strategies directory for YAML configurations
    and checks the models directory for training status.
    """
    strategies = []
    strategy_dir = Path("strategies")
    models_dir = Path("models")
    
    if not strategy_dir.exists():
        return StrategiesResponse(strategies=[])
    
    for yaml_file in strategy_dir.glob("*.yaml"):
        try:
            # Load strategy configuration
            with open(yaml_file, 'r') as f:
                config = yaml.safe_load(f)
            
            strategy_name = config["name"]
            
            # Check training status by looking at model directory
            strategy_model_dir = models_dir / strategy_name
            training_status = "untrained"
            available_versions = []
            latest_version = None
            latest_training_date = None
            latest_metrics = None
            
            if strategy_model_dir.exists():
                # Find all version directories
                # Pattern: {symbol}_{timeframe}_v{version}
                symbol = config['data']['symbols'][0]  # MVP: single symbol
                timeframe = config['data']['timeframes'][0]  # MVP: single timeframe
                pattern = f"{symbol}_{timeframe}_v*"
                
                version_dirs = list(strategy_model_dir.glob(pattern))
                
                if version_dirs:
                    training_status = "trained"
                    
                    # Extract version numbers
                    versions = []
                    for vdir in version_dirs:
                        try:
                            version = int(vdir.name.split('_v')[-1])
                            versions.append((version, vdir))
                        except (ValueError, IndexError):
                            continue
                    
                    if versions:
                        versions.sort(key=lambda x: x[0])
                        available_versions = [v[0] for v in versions]
                        
                        # Get latest version info
                        latest_version = versions[-1][0]
                        latest_dir = versions[-1][1]
                        
                        # Load metrics from latest version
                        metrics_file = latest_dir / "metrics.json"
                        if metrics_file.exists():
                            with open(metrics_file, 'r') as f:
                                metrics_data = json.load(f)
                                latest_training_date = metrics_data.get("training_completed_at")
                                
                                # Extract test metrics
                                test_metrics = metrics_data.get("test_metrics", {})
                                if test_metrics:
                                    latest_metrics = StrategyMetrics(
                                        accuracy=test_metrics.get("accuracy"),
                                        precision=test_metrics.get("precision"),
                                        recall=test_metrics.get("recall"),
                                        f1_score=test_metrics.get("f1_score")
                                    )
            
            strategies.append(StrategyInfo(
                name=strategy_name,
                description=config.get("description", ""),
                symbol=symbol,
                timeframe=timeframe,
                indicators=config["indicators"],
                fuzzy_config=config["fuzzy_sets"],
                training_status=training_status,
                available_versions=available_versions,
                latest_version=latest_version,
                latest_training_date=latest_training_date,
                latest_metrics=latest_metrics
            ))
            
        except Exception as e:
            # Log error but continue with other strategies
            print(f"Error loading strategy {yaml_file}: {e}")
            continue
    
    return StrategiesResponse(strategies=strategies)

@router.get("/{strategy_name}", response_model=StrategyInfo)
async def get_strategy_details(strategy_name: str, version: Optional[int] = None):
    """
    Get detailed information about a specific strategy.
    
    Args:
        strategy_name: Name of the strategy
        version: Specific model version (latest if not specified)
    """
    # First, get all strategies
    all_strategies = await list_strategies()
    
    # Find the requested strategy
    strategy = None
    for s in all_strategies.strategies:
        if s.name == strategy_name:
            strategy = s
            break
    
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_name}' not found")
    
    # If specific version requested, validate it exists
    if version is not None and version not in strategy.available_versions:
        raise HTTPException(
            status_code=404, 
            detail=f"Version {version} not found for strategy '{strategy_name}'"
        )
    
    return strategy
```

### Shared Context Between Modes

**File**: `frontend/src/store/sharedContextStore.ts`

```typescript
// This store is shared between Train and Research modes
interface BacktestContext {
  mode: 'backtest';
  strategy: Strategy;
  symbol: string;
  timeframe: string;
  dateRange: { start: string; end: string };
  indicators: IndicatorConfig[];
  fuzzyConfig: FuzzySetConfig;
  trades: Trade[];
  backtestId: string;
}

interface SharedContextState {
  backtestContext: BacktestContext | null;
}

export const sharedContextStore = createStore<SharedContextState>({
  backtestContext: null
});

export const sharedContextActions = {
  setBacktestContext: (context: BacktestContext | null) => {
    sharedContextStore.setState(state => ({
      ...state,
      backtestContext: context
    }));
  },
  
  clearBacktestContext: () => {
    sharedContextStore.setState(state => ({
      ...state,
      backtestContext: null
    }));
  }
};
```

## Implementation Roadmap

### Phase 1: Core Train Mode UI (MVP)
Everything detailed above provides the complete working system:
- Strategy list with training status
- Backtest execution with progress tracking
- Basic results display with key metrics
- Navigation to Research mode with full context
- Trade markers on price chart in Research mode
- Visual indicator showing backtest mode

### Phase 2: Enhanced Analysis (Post-MVP)
- **Trade-by-trade analysis**: Detailed view of each trade with entry/exit reasoning
- **Performance attribution**: Which indicators contributed most to decisions
- **Downloadable reports**: PDF/Excel export of backtest results
- **Confidence visualization**: Show neural network confidence for each decision

### Phase 3: Advanced Features (Future)
- **Strategy comparison**: Run multiple strategies and compare side-by-side
- **Parameter optimization**: Automated hyperparameter tuning
- **Walk-forward analysis**: Rolling window backtests
- **Multi-timeframe support**: Extend beyond single timeframe limitation

## State Management Best Practices

To avoid the state complexity issues that have plagued the project:

1. **Never store derived state** - Always compute from source
2. **Actions are the only mutations** - No direct state updates
3. **Components are pure functions** - Given state, render UI
4. **Single store per domain** - Train mode has one store, Research mode has another, shared context bridges them
5. **Explicit state transitions** - Clear action names that describe what happened

## MVP Implementation Checklist

### Backend Tasks (Do First!)
- [ ] **CRITICAL**: Move backtesting endpoints to `ktrdr/api/endpoints/backtesting.py`
- [ ] **CRITICAL**: Update `ktrdr/api/__init__.py` to register backtesting router
- [ ] Create `ktrdr/api/endpoints/strategies.py` with listing endpoint
- [ ] Test all endpoints appear in `/api/v1/docs`

### Frontend Core (MVP Essential)
- [ ] Create `trainModeStore` with complete state structure
- [ ] Implement core actions (loadStrategies, startBacktest, etc.)
- [ ] Build StrategyListPanel component
- [ ] Add backtest progress tracking
- [ ] Create basic BacktestResultsPanel
- [ ] Implement sharedContextStore for mode transitions
- [ ] Add navigation from Train to Research mode

### Research Mode Integration (MVP Essential)
- [ ] Add BacktestOverlay component
- [ ] Implement trade markers on chart
- [ ] Add backtest mode indicator
- [ ] Handle context from Train mode

### Nice to Have (Post-MVP)
- [ ] Detailed metrics visualization
- [ ] Trade hover tooltips with position size
- [ ] Download functionality
- [ ] Date range configuration

## Consequences

### Positive Consequences
- **Seamless workflow**: Easy transition between training, backtesting, and analysis
- **Context preservation**: No manual re-configuration when analyzing results
- **Clear separation**: Train and Research modes have distinct purposes
- **Single source of truth**: Frontend state management prevents synchronization issues
- **Extensible design**: Easy to add more analysis features

### Negative Consequences
- **State complexity**: Managing context between modes requires careful design
- **Memory usage**: Storing backtest results in frontend context
- **Navigation complexity**: Users need to understand mode transitions

### Mitigation Strategies
- Clear visual indicators for current mode
- Automatic context cleanup on navigation
- Progressive loading for large result sets
- User education through UI hints

## Implementation Notes

**MVP PRIORITY**: The most critical backend task is ensuring the backtesting endpoints are properly registered and accessible. Without this, the entire Train mode UI won't function. This should be done before any frontend work begins.

**STATE MANAGEMENT DISCIPLINE**: Given the project's history with state management issues, strict adherence to the single source of truth pattern is essential. Every piece of UI state must live in the centralized store, and components must remain pure renderers.

## Conclusion

The Train Mode UI and Research Mode integration creates a **seamless workflow** for strategy development and analysis. By maintaining strict state management discipline and preserving context between modes, users can efficiently iterate on their trading strategies without the frustration of state synchronization issues.

**Key design principles**:
- **Single source of truth** for all frontend state
- **Context preservation** between UI modes
- **Progressive disclosure** of trade details
- **Clear visual indicators** for current mode
- **Backend-first** implementation approach