# ADR-001: Current Architecture Assessment

## Status
**Accepted** - December 2024

## Context
KTRDR has evolved from initial MVP concepts into a sophisticated trading research platform. Before implementing the Core Decision Engine and neuro-fuzzy strategies, we need a comprehensive assessment of the current architecture to identify strengths, extension points, and areas for evolution.

This assessment serves as the foundation for architectural decisions in the next development phase, focusing on backtesting capabilities and algorithmic strategy implementation.

## Current Architecture Overview

### System Architecture
KTRDR follows a **service-oriented architecture** with clear separation between:
- **Backend**: FastAPI-based REST API with business logic
- **Frontend**: React/TypeScript SPA with TradingView charts
- **Data Layer**: Hybrid storage (CSV files + in-memory caching)
- **External Integration**: Interactive Brokers TWS/Gateway

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │◄──►│   Backend API   │◄──►│ Interactive     │
│   React/TS      │    │   FastAPI       │    │ Brokers         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐             │
         └─────────────►│   Data Layer    │◄────────────┘
                        │   CSV + Cache   │
                        └─────────────────┘
```

### Component Relationships
- **Data Management** → **Indicator Engine** → **Fuzzy Logic** → **Frontend Visualization**
- **Configuration System** → All components (YAML-based strategy definitions)
- **Error Handling** → Cross-cutting concern with centralized exception hierarchy

## API Layer Architecture

### Endpoint Organization
**Base URL**: `/api/v1/`

#### Core Data Endpoints (`/data/`)
- **GET `/symbols`** - Trading symbol discovery with contract validation
- **GET `/timeframes`** - Supported time frequencies (1m to 1M)
- **GET `/data/{symbol}/{timeframe}`** - Cached OHLCV data retrieval
- **POST `/data/load`** - Enhanced data loading with IB integration
- **POST `/data/range`** - Available date range discovery

#### Technical Analysis (`/indicators/`)
- **GET `/`** - Available indicators with metadata and parameters
- **POST `/calculate`** - Batch indicator calculation with pagination

#### Fuzzy Logic (`/fuzzy/`)
- **GET `/indicators`** - Fuzzy-enabled indicator discovery
- **GET `/sets/{indicator}`** - Fuzzy set configurations
- **GET `/data`** - Time series fuzzy membership overlays
- **POST `/evaluate`** - Real-time fuzzification
- **POST `/data`** - Complete data-to-fuzzy pipeline

#### System Management
- **GET `/ib/status`** - Interactive Brokers connection health
- **GET `/system/health`** - System status and diagnostics

### Key Data Schemas

#### Standard API Response Envelope
```typescript
interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details: object;
  };
}
```

#### Core Data Models
```typescript
// Price data structure
interface OHLCVData {
  dates: string[];
  ohlcv: [open: number, high: number, low: number, close: number, volume: number][];
}

// Indicator calculation request
interface IndicatorRequest {
  symbol: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  indicators: IndicatorConfig[];
}

// Fuzzy membership response
interface FuzzyMembership {
  set: string;
  membership: { timestamp: string; value: number | null }[];
}
```

### API Design Principles
- **Consistent Error Handling**: Standardized error envelope with codes
- **Pagination Support**: Large datasets handled with cursor-based pagination
- **Type Safety**: Full Pydantic validation on all endpoints
- **Performance**: Aggressive caching with TTL expiration

## Core Modules

### Data Management (`ktrdr/data/`)

#### DataManager - Central Data Orchestration
**File**: `ktrdr/data/data_manager.py`

**Core Capabilities**:
- **Intelligent Loading Modes**: "tail", "backfill", "full" with gap analysis
- **Multi-Source Support**: IB real-time + historical, local CSV files
- **Trading Calendar Awareness**: Market hours and holiday handling
- **Progressive Loading**: Partial failure resilience with retry mechanisms
- **Performance Optimization**: Vectorized pandas operations

**Key Methods**:
```python
def load_data(symbol: str, timeframe: str, mode: str = "tail") -> pd.DataFrame
def get_available_range(symbol: str, timeframe: str) -> DateRange
def validate_and_repair(data: pd.DataFrame) -> pd.DataFrame
```

#### IB Integration Layer
**Files**: `ktrdr/data/ib_*.py`

**Architecture**:
- **Connection Management**: Pool-based connection handling
- **Rate Limiting**: TWS API compliance with backoff strategies
- **Contract Validation**: Automatic symbol-to-contract resolution
- **Gap Detection**: Smart missing data identification

#### Data Quality & Validation
**File**: `ktrdr/data/data_quality_validator.py`

**Features**:
- **OHLCV Validation**: Price relationship checks, volume validation
- **Gap Detection**: Missing timestamp identification
- **Repair Strategies**: Forward fill, interpolation, market-aware healing
- **Quality Metrics**: Data completeness scoring

### Indicator Engine (`ktrdr/indicators/`)

#### Architecture Pattern
**Base Class**: `BaseIndicator` with factory pattern instantiation

**Core Indicators**:
- **Trend**: SMA, EMA, MACD, Bollinger Bands
- **Momentum**: RSI, Stochastic Oscillator
- **Volume**: Volume-based analysis
- **Custom**: Extensible framework for new indicators

#### Calculation Engine
**File**: `ktrdr/indicators/indicator_engine.py`

**Design Principles**:
- **Vectorized Operations**: NumPy/pandas for performance
- **Parameter Validation**: Type checking and range validation
- **Batch Processing**: Multiple indicators in single pass
- **Memory Efficiency**: Streaming calculations for large datasets

**Key Interface**:
```python
class BaseIndicator:
    def calculate(self, data: pd.DataFrame) -> pd.Series | pd.DataFrame
    def validate_parameters(self, params: dict) -> dict
    def get_required_history(self) -> int
```

#### Indicator Registry
**File**: `ktrdr/indicators/indicator_factory.py`

**Capabilities**:
- **Dynamic Discovery**: Runtime indicator registration
- **Metadata Management**: Parameter schemas and documentation
- **Type Safety**: Full typing support for all indicators

### Fuzzy Logic System (`ktrdr/fuzzy/`)

#### Fuzzy Engine
**File**: `ktrdr/fuzzy/engine.py`

**Core Features**:
- **Membership Functions**: Triangular, trapezoidal support
- **Batch Evaluation**: Efficient time series processing
- **Multi-Set Support**: Complex fuzzy logic with multiple sets per indicator
- **Strategy Integration**: YAML-based fuzzy set configuration

#### Configuration System
**File**: `ktrdr/fuzzy/config.py`

**YAML Schema Support**:
```yaml
# Example: RSI fuzzy sets
rsi:
  low: [0, 10, 30]
  neutral: [25, 50, 75] 
  high: [70, 90, 100]
```

**Dynamic Scaling**:
- **RSI**: Fixed 0-100 scaling
- **MACD**: Dynamic range detection
- **Custom**: Configurable scaling per indicator type

#### Fuzzy API Integration
**Advanced Pipeline**:
```python
# Current fuzzy evaluation flow
indicators = indicator_engine.calculate_multiple(data, configs)
fuzzy_values = fuzzy_engine.evaluate_batch(indicators, fuzzy_config)
time_series = fuzzy_engine.create_time_series(fuzzy_values, timestamps)
```

## Frontend Architecture

### Chart System
**Technology**: TradingView Lightweight Charts v5.0.7

#### Multi-Panel Architecture
**Files**: `frontend/src/components/containers/OscillatorPanelManager.tsx`

**Design Pattern**: Container/Presentation separation
- **OscillatorPanelManager**: Panel lifecycle and synchronization
- **BaseOscillatorPanel**: Generic panel functionality  
- **Specialized Panels**: RSIPanel, MACDPanel with indicator-specific features

**Key Features**:
- **Dynamic Panel Creation**: Automatic panel management based on active indicators
- **Chart Synchronization**: Time range and crosshair coordination
- **Error Boundaries**: Isolated error handling per panel
- **Performance**: Critical chart jumping bug prevention system

#### State Management
**Pattern**: React hooks with local state + Redux-style patterns

**Key Hooks**:
- `useIndicatorManager`: Indicator configuration and lifecycle
- `useFuzzyOverlay`: Fuzzy data fetching and visualization
- `useChartSynchronizer`: Multi-chart coordination

#### Real-time Data Flow
```typescript
// Current data flow
Symbol/Timeframe Change → 
  Data Loading → 
    Indicator Calculation → 
      Fuzzy Evaluation → 
        Chart Rendering + Overlay Updates
```

### User Interface Patterns

#### Sidebar Controls
**File**: `frontend/src/components/presentation/sidebar/IndicatorSidebar.tsx`

**Features**:
- **Dynamic Forms**: Parameter-specific input validation
- **Real-time Updates**: Immediate chart updates on parameter changes
- **Fuzzy Controls**: Opacity, color scheme, visibility toggles
- **Responsive Design**: Mobile-friendly responsive layouts

#### Keyboard Shortcuts & Accessibility
**File**: `frontend/src/hooks/useKeyboardShortcuts.ts`

**Global Shortcuts**:
- Symbol selection, timeframe changes, panel management
- Help modal with shortcut discovery
- Full keyboard navigation support

## Configuration & Strategy Framework

### Central Metadata System
**File**: `ktrdr/metadata.py`

**Architecture**: Single source of truth for project-wide configuration
- **Environment Awareness**: Development/production/testing configs
- **Path Management**: Centralized file path resolution
- **Type Safety**: Pydantic-based validation

### Strategy Configuration Types

#### System Configuration
**Files**: `config/environment/*.yaml`
- **Database connections**, **API endpoints**, **logging levels**
- **IB connection parameters**, **rate limiting settings**

#### Strategy Definitions  
**Files**: `strategies/*.yaml`
**Schema**:
```yaml
name: strategy_name
indicators:
  - name: rsi
    period: 14
    source: close
fuzzy_sets:
  rsi:
    oversold: [0, 10, 30]
    neutral: [25, 50, 75]
    overbought: [70, 90, 100]
model:
  type: neural_network
  architecture: [input_size, hidden_layers, output_size]
```

#### Indicator Configuration
**Registry Pattern**: Type-safe parameter definitions
```python
# Example indicator config
IndicatorConfig = {
    "name": "rsi",
    "parameters": {"period": 14, "source": "close"},
    "chartType": "separate",  # overlay | separate
    "fuzzyEnabled": True
}
```

### Configuration Management Principles
- **Validation**: Pydantic schemas for all configuration types
- **Environment Overrides**: Development vs production parameter sets
- **Hot Reload**: Runtime configuration updates (development mode)
- **Documentation**: Self-documenting schemas with examples

## Infrastructure & Deployment

### Current Docker Architecture
**Files**: `docker/docker-compose.yml`, `docker/backend/Dockerfile.dev`

**Development Setup**:
```yaml
services:
  backend:
    build: docker/backend/Dockerfile.dev
    ports: ["8000:8000"]
    volumes: [source_code, data, logs]
    environment: [IB_HOST, IB_PORT, ENVIRONMENT]
  
  frontend:
    build: frontend/Dockerfile.dev  
    ports: ["5173:5173"]
    environment: [VITE_API_BASE_URL]
```

**Features**:
- **Hot Reloading**: Live code updates for both services
- **Volume Mounting**: Persistent data and log storage
- **Network**: Bridge network for service communication
- **Health Checks**: Container monitoring and restart policies

### Performance Characteristics
**Current Benchmarks**:
- **API Response Time**: < 500ms for 10K data points
- **Memory Usage**: ~200MB base + 50MB per active symbol
- **Concurrent Users**: Tested to 10 simultaneous connections
- **Data Loading**: 1M+ data points processed in < 2 seconds

### Logging & Error Handling Principles

#### Centralized Logging
**File**: `ktrdr/logging/config.py`

**Design**:
- **Structured Logging**: JSON format with contextual metadata
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Performance Tracking**: Request timing and resource usage
- **Error Context**: Stack traces with business context

#### Error Handling Strategy
**Files**: `ktrdr/errors/*.py`

**Principles**:
- **Exception Hierarchy**: Custom exceptions with error codes
- **Graceful Degradation**: Partial failure handling
- **Retry Mechanisms**: Exponential backoff for network operations
- **User Feedback**: Meaningful error messages for UI

## Architectural Strengths

### 1. **Modular Design**
- **Clear separation** between data, analysis, and presentation layers
- **Pluggable architecture** for indicators and fuzzy logic
- **Independent testing** of each module

### 2. **Robust Data Management**
- **Multi-source integration** with intelligent caching
- **Quality validation** and repair mechanisms  
- **Performance optimization** with vectorized operations

### 3. **Advanced Visualization**
- **Professional charting** with TradingView integration
- **Real-time updates** with smooth user experience
- **Multi-panel coordination** for complex analysis

### 4. **Configuration-Driven**
- **YAML-based strategies** for non-technical users
- **Type-safe validation** prevents configuration errors
- **Environment-specific** configurations for deployment flexibility

### 5. **Error Resilience**
- **Comprehensive error handling** with graceful degradation
- **Retry mechanisms** for network operations
- **User feedback** for all error conditions

## Technical Debt & Evolution Opportunities

### 1. **State Management Complexity**
**Current Issue**: Mixed patterns between React local state and pseudo-Redux patterns
**Impact**: Difficult to reason about data flow, potential race conditions
**Evolution Opportunity**: Unified state management with proper event sourcing

### 2. **Configuration Type Safety**
**Current Issue**: YAML configurations lack compile-time validation
**Impact**: Runtime errors from invalid configurations
**Evolution Opportunity**: Code-generated TypeScript types from schemas

### 3. **Data Storage Limitations**
**Current Issue**: CSV-based storage doesn't scale for complex queries
**Impact**: Difficulty with portfolio tracking, trade history, backtesting metadata
**Evolution Opportunity**: Hybrid approach with database for transactional data

### 4. **Real-time Data Flow**
**Current Issue**: Polling-based updates instead of event-driven
**Impact**: Inefficient resource usage, delayed updates
**Evolution Opportunity**: WebSocket/SSE for real-time data streaming

### 5. **Testing Coverage**
**Current Issue**: Integration tests limited, especially for complex data flows
**Impact**: Regression risk during evolution
**Evolution Opportunity**: Comprehensive test harness for end-to-end flows

## Ready Integration Points for Decision Engine

### 1. **Data Pipeline Integration**
**Extension Point**: `ktrdr/data/data_manager.py`
**Capability**: Real-time and historical data feeds ready for strategy consumption
**Interface**: `DecisionEngine.consume_data(symbol, timeframe, data)`

### 2. **Indicator Output Consumption**
**Extension Point**: `ktrdr/indicators/indicator_engine.py`
**Capability**: Calculated indicator values ready for signal generation
**Interface**: `DecisionEngine.process_indicators(indicator_results)`

### 3. **Fuzzy Logic Integration**
**Extension Point**: `ktrdr/fuzzy/engine.py`
**Capability**: Fuzzy membership values ready for neuro-fuzzy processing
**Interface**: `DecisionEngine.evaluate_fuzzy_signals(fuzzy_memberships)`

### 4. **Configuration Framework**
**Extension Point**: Strategy YAML configurations
**Capability**: User-defined strategies ready for automated execution
**Interface**: `DecisionEngine.load_strategy(strategy_config)`

### 5. **API Extension Points**
**Ready Endpoints**: 
- `POST /api/v1/strategies/` - Strategy management
- `POST /api/v1/decisions/` - Real-time decision execution
- `GET /api/v1/backtest/` - Historical simulation

### 6. **Frontend Integration**
**Extension Point**: Multi-panel architecture
**Capability**: Strategy visualization and performance monitoring
**Interface**: New panels for decision tracking, P&L, risk metrics

## Conclusion

The current KTRDR architecture provides a **solid foundation** for evolution toward algorithmic trading capabilities. The modular design, robust data management, and flexible configuration system create natural extension points for the Decision Engine implementation.

**Key strengths** to preserve:
- Clean separation of concerns between modules
- Robust error handling and data quality validation
- Professional-grade visualization system
- Configuration-driven strategy definitions

**Primary evolution areas**:
- Enhanced state management for complex decision workflows  
- Database integration for portfolio and trade tracking
- Real-time event processing for strategy execution
- Comprehensive testing for algorithmic trading scenarios

The architecture is **well-positioned** for the next phase of development, with clear integration points and minimal coupling between existing modules and the planned Decision Engine components.