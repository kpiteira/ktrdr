# Trading UI Architecture Document

## System Overview

### High-Level Architecture
```
┌─────────────────┐    HTTP/REST    ┌─────────────────────┐
│   Frontend      │◄───────────────►│   Python Backend   │
│   (React SPA)   │                 │   (FastAPI)         │
└─────────────────┘                 └─────────────────────┘
        │                                      │
        │                                      │
   ┌─────────┐                          ┌──────────────┐
   │ Browser │                          │ Data Sources │
   │ Storage │                          │ & ML Models  │
   └─────────┘                          └──────────────┘
```

### Technology Stack

#### Frontend
- **Framework**: React 18+ with TypeScript
- **Charting**: TradingView Lightweight Charts
- **HTTP Client**: Fetch API with custom wrapper
- **Styling**: Modern CSS (Grid/Flexbox), CSS Modules or Styled Components
- **Build Tool**: Vite (recommended) or Create React App
- **State Management**: Container/Presentation Pattern with Custom Hooks (avoid Redux for MVP)
- **Architecture Pattern**: Container/Presentation Components for scalable state management

#### Integration Layer
- **API Client**: Custom TypeScript client matching backend schema
- **Data Models**: TypeScript interfaces matching backend data structures
- **Error Handling**: Centralized error boundary and API error handling

## Frontend Architecture

### Component Hierarchy

#### Container/Presentation Architecture Pattern

To address fragility issues and improve maintainability, the frontend follows a strict Container/Presentation pattern:

**Container Components** (Smart Components):
- Manage all state and business logic
- Handle API calls and data fetching
- Contain custom hooks for reusable logic
- Pass data and callbacks to Presentation components

**Presentation Components** (Dumb Components):
- Receive props and render UI
- No direct state management or API calls
- Focus purely on rendering and user interactions
- Highly reusable and testable

```
App (Container)
├── Layout (Presentation)
│   ├── Header (Presentation - current mode title only)
│   ├── LeftSidebar (Presentation - mode selection)
│   ├── IndicatorSidebarContainer (Container)
│   │   └── IndicatorSidebar (Presentation)
│   │       ├── InstrumentSelector (Presentation)
│   │       ├── ActiveIndicatorsList (Presentation)
│   │       ├── AddIndicatorButton (Presentation)
│   │       └── ParameterControls (Presentation)
│   └── MainContent (Presentation)
│       └── ResearchView (Presentation)
│           ├── BasicChartContainer (Container)
│           │   └── BasicChart (Presentation)
│           └── RSIChartContainer (Container)
│               └── RSIChart (Presentation)
```

#### Custom Hooks for Reusable Logic

- **useIndicatorManager**: Manages indicator state, CRUD operations, and parameter updates
- **useChartSynchronizer**: Handles time scale and crosshair synchronization between charts
- **useApiClient**: Provides typed API methods with error handling and caching
- **useLocalState**: Manages local UI state to prevent circular updates

### Generic Indicator System

#### Indicator Registry Pattern

To eliminate hardcoded indicator logic and improve scalability:

```typescript
// Generic indicator configuration system
interface IndicatorConfig {
  name: string
  displayName: string
  category: string
  chartType: 'overlay' | 'separate'
  defaultParameters: Record<string, any>
  parameterDefinitions: ParameterDefinition[]
  colorOptions: string[]
}

interface ParameterDefinition {
  name: string
  type: 'number' | 'string' | 'boolean' | 'select'
  min?: number
  max?: number
  step?: number
  options?: string[]
  default: any
}

// Centralized indicator registry
const INDICATOR_REGISTRY: Record<string, IndicatorConfig> = {
  sma: {
    name: 'sma',
    displayName: 'Simple Moving Average',
    category: 'Moving Averages',
    chartType: 'overlay',
    defaultParameters: { period: 20, color: '#2196F3' },
    parameterDefinitions: [
      { name: 'period', type: 'number', min: 1, max: 200, step: 1, default: 20 },
      { name: 'color', type: 'select', options: ['#2196F3', '#FF5722', '#4CAF50'], default: '#2196F3' }
    ],
    colorOptions: ['#2196F3', '#FF5722', '#4CAF50', '#9C27B0', '#FF9800']
  },
  rsi: {
    name: 'rsi',
    displayName: 'Relative Strength Index',
    category: 'Oscillators',
    chartType: 'separate',
    defaultParameters: { period: 14, color: '#FF5722' },
    parameterDefinitions: [
      { name: 'period', type: 'number', min: 2, max: 100, step: 1, default: 14 },
      { name: 'color', type: 'select', options: ['#FF5722', '#2196F3', '#4CAF50'], default: '#FF5722' }
    ],
    colorOptions: ['#FF5722', '#2196F3', '#4CAF50', '#9C27B0', '#FF9800']
  }
}
```

### Core Modules

#### 1. Chart Management (`/src/charts/`)
```typescript
// Chart orchestration and synchronization
interface ChartManager {
  priceChart: PriceChart
  indicatorCharts: IndicatorChart[]
  syncTimeScale(): void
  syncCrosshair(): void
  addIndicatorChart(): void
  removeIndicatorChart(): void
}

// Individual chart wrappers
interface PriceChart {
  chart: IChartApi
  candlestickSeries: ISeriesApi<'Candlestick'>
  overlayIndicators: Map<string, ISeriesApi<'Line'>>
  fuzzyOverlays: Map<string, FuzzyOverlay>
}

interface IndicatorChart {
  chart: IChartApi
  series: ISeriesApi<'Line'>
  fuzzyOverlay?: FuzzyOverlay
  indicatorType: string
}
```

#### 2. API Client (`/src/api/`)
```typescript
interface TradingAPIClient {
  // Symbols & Timeframes
  getSymbols(assetType?: string): Promise<SymbolsResponse>
  getTimeframes(): Promise<TimeframesResponse>
  
  // Data Management
  loadData(request: LoadDataRequest): Promise<LoadDataResponse>
  getLatestData(symbol: string, timeframe: string): Promise<LatestDataResponse>
  getDataStatus(symbol: string, timeframe: string): Promise<DataStatusResponse>
  
  // Indicators
  getAvailableIndicators(category?: string): Promise<IndicatorsResponse>
  calculateIndicators(request: CalculateIndicatorsRequest): Promise<CalculateIndicatorsResponse>
  getIndicatorDefaults(): Promise<IndicatorDefaultsResponse>
  getIndicatorInfo(name: string): Promise<IndicatorInfoResponse>
  
  // Fuzzy Sets (TODO: Add to backend)
  getFuzzyData(symbol: string, timeframe: string): Promise<FuzzyDataResponse>
}

// Data Types based on your API responses
interface Symbol {
  symbol: string
  name: string
  asset_type: string
  exchange: string
}

interface SymbolsResponse {
  success: boolean
  data: {
    symbols: Symbol[]
  }
}

interface Timeframe {
  id: string
  description: string
}

interface TimeframesResponse {
  success: boolean
  data: {
    timeframes: Timeframe[]
  }
}

interface OHLCVPoint {
  timestamp: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

interface LoadDataRequest {
  symbol: string
  timeframe: string
  start_date?: string
  end_date?: string
  source?: 'local' | 'ib' | 'auto'
}

interface LoadDataResponse {
  success: boolean
  data: {
    symbol: string
    timeframe: string
    start_date: string
    end_date: string
    points: number
    ohlcv: OHLCVPoint[]
    metadata: {
      source: string
      last_updated: string
      timezone: string
    }
  }
}

interface Indicator {
  name: string
  display_name: string
  category: string
  description: string
}

interface IndicatorsResponse {
  success: boolean
  data: {
    indicators: Indicator[]
  }
}

interface CalculateIndicatorsRequest {
  data: {
    symbol?: string
    timeframe?: string
    ohlcv: OHLCVPoint[]
  }
  indicators: {
    name: string
    parameters?: Record<string, any>
  }[]
}

interface CalculateIndicatorsResponse {
  success: boolean
  data: {
    input: {
      symbol?: string
      timeframe?: string
      points: number
    }
    results: Record<string, (number | null)[]>
    metadata: Record<string, {
      indicator: string
      parameters: Record<string, any>
      warmup_period: number
      min_data_points: number
    }>
  }
}

interface APIError {
  success: false
  error: {
    code: string
    message: string
    details: Record<string, any>
  }
}

// Fuzzy Data Types (TODO: Define based on your fuzzy implementation)
interface FuzzySet {
  name: string
  color: string
  membership: { timestamp: string; value: number }[]
  threshold?: number
}

interface FuzzyDataResponse {
  success: boolean
  data: {
    symbol: string
    timeframe: string
    indicator: string
    sets: FuzzySet[]
  }
}
```

#### 3. State Management (`/src/store/`)
```typescript
interface AppState {
  // UI Layout
  leftSidebarCollapsed: boolean
  rightSidebarCollapsed: boolean
  currentMode: 'research' | 'train' | 'run'
  
  // Current selection
  selectedSymbol: Symbol | null
  selectedTimeframe: Timeframe | null
  
  // Data
  availableSymbols: Symbol[]
  availableTimeframes: Timeframe[]
  priceData: OHLCVPoint[]
  
  // Indicators
  activeIndicators: ActiveIndicator[]
  availableIndicators: Indicator[]
  indicatorDefaults: Record<string, Record<string, any>>
  
  // UI State
  loading: LoadingState
  errors: ErrorState
}

interface ActiveIndicator {
  id: string // unique identifier for this instance
  name: string // indicator name (e.g., 'rsi')
  display_name: string // human readable name
  parameters: Record<string, any>
  data: (number | null)[] // calculated values
  metadata: {
    indicator: string
    parameters: Record<string, any>
    warmup_period: number
    min_data_points: number
  }
  chartType: 'overlay' | 'separate'
  visible: boolean
  fuzzyData?: FuzzySet[]
  fuzzyVisible: boolean
}

interface LoadingState {
  symbols: boolean
  timeframes: boolean
  priceData: boolean
  indicators: Record<string, boolean> // loading state per indicator
}

interface ErrorState {
  symbols?: string
  timeframes?: string
  priceData?: string
  indicators: Record<string, string> // error per indicator
}

// Actions for state management
type AppAction = 
  | { type: 'TOGGLE_LEFT_SIDEBAR' }
  | { type: 'TOGGLE_RIGHT_SIDEBAR' }
  | { type: 'SET_MODE'; payload: 'research' | 'train' | 'run' }
  | { type: 'SET_SYMBOLS'; payload: Symbol[] }
  | { type: 'SET_TIMEFRAMES'; payload: Timeframe[] }
  | { type: 'SET_SELECTED_SYMBOL'; payload: Symbol }
  | { type: 'SET_SELECTED_TIMEFRAME'; payload: Timeframe }
  | { type: 'SET_PRICE_DATA'; payload: OHLCVPoint[] }
  | { type: 'ADD_INDICATOR'; payload: { indicator: Indicator; parameters: Record<string, any> } }
  | { type: 'REMOVE_INDICATOR'; payload: string }
  | { type: 'UPDATE_INDICATOR_DATA'; payload: { id: string; data: (number | null)[]; metadata: any } }
  | { type: 'TOGGLE_INDICATOR_VISIBILITY'; payload: string }
  | { type: 'TOGGLE_FUZZY_VISIBILITY'; payload: string }
  | { type: 'UPDATE_INDICATOR_PARAMS'; payload: { id: string; params: Record<string, any> } }
  | { type: 'SET_LOADING'; payload: { key: string; loading: boolean } }
  | { type: 'SET_ERROR'; payload: { key: string; error: string | null } }
```

#### 4. Fuzzy Set Visualization (`/src/charts/fuzzy/`)
```typescript
interface FuzzyOverlay {
  indicatorId: string
  sets: FuzzySet[]
  visible: boolean
  render(chart: IChartApi): void
  update(data: FuzzySetData): void
  destroy(): void
}

interface FuzzySet {
  name: string
  color: string
  membership: TimestampValue[]
  threshold: number // activation threshold
}

// Implementation approaches:
// 1. Area series with transparency for membership levels
// 2. Background color changes based on fuzzy activation
// 3. Histogram series showing membership values
```

### Directory Structure

```
src/
├── components/
│   ├── containers/               # Smart components with state
│   │   ├── IndicatorSidebarContainer.tsx
│   │   ├── BasicChartContainer.tsx
│   │   ├── RSIChartContainer.tsx
│   │   └── AppContainer.tsx
│   ├── presentation/             # Dumb components, pure UI
│   │   ├── charts/
│   │   │   ├── BasicChart.tsx
│   │   │   ├── RSIChart.tsx
│   │   │   └── fuzzy/
│   │   │       ├── FuzzyOverlay.tsx
│   │   │       └── FuzzyLegend.tsx
│   │   ├── sidebar/
│   │   │   ├── IndicatorSidebar.tsx
│   │   │   ├── InstrumentSelector.tsx
│   │   │   ├── ActiveIndicatorsList.tsx
│   │   │   ├── IndicatorItem.tsx
│   │   │   ├── AddIndicatorButton.tsx
│   │   │   ├── ParameterControls.tsx
│   │   │   └── FuzzySetControls.tsx
│   │   └── layout/
│   │       ├── Header.tsx
│   │       ├── Layout.tsx
│   │       ├── LeftSidebar.tsx
│   │       └── CollapsibleSidebar.tsx
│   └── common/
│       ├── LoadingSpinner.tsx
│       ├── ErrorBoundary.tsx
│       └── Modal.tsx
├── hooks/
│   ├── useIndicatorManager.ts     # Core indicator state management
│   ├── useChartSynchronizer.ts    # Chart sync logic
│   ├── useApiClient.ts           # Typed API client with caching
│   ├── useLocalState.ts          # Local UI state management
│   ├── useInstrumentData.ts      # Symbol/timeframe data
│   ├── useFuzzyData.ts          # Fuzzy set data
│   └── useSidebarCollapse.ts     # Sidebar state
├── services/
│   ├── api/
│   │   ├── client.ts
│   │   ├── instruments.ts
│   │   ├── indicators.ts
│   │   └── types.ts
│   └── charts/
│       ├── chartManager.ts
│       ├── chartUtils.ts
│       └── fuzzyRenderer.ts
├── store/
│   ├── context.ts                # React Context for global state
│   ├── reducer.ts               # State reducer functions
│   ├── types.ts                # State type definitions
│   └── indicatorRegistry.ts     # Centralized indicator configs
├── utils/
│   ├── dataTransform.ts
│   ├── colorUtils.ts
│   └── constants.ts
└── views/
    ├── ResearchView.tsx
    ├── TrainView.tsx (placeholder)
    └── RunView.tsx (placeholder)
```

### Data Flow

#### 1. Application Initialization
```
1. App loads → Initialize API client
2. Fetch available instruments → Update instrument selector
3. Load default instrument (if any) → Fetch price data
4. Render charts with initial data
```

#### 2. Instrument Selection
```
1. User selects instrument → Dispatch SET_INSTRUMENT
2. Clear existing chart data → Show loading state
3. Fetch new price data via API → Update state
4. Fetch available indicators → Update controls
5. Re-render charts with new data
```

#### 3. Indicator Management
```
1. User adds indicator → Dispatch ADD_INDICATOR
2. Fetch indicator data from API → Update state
3. Determine chart placement (overlay vs separate)
4. Create/update chart series → Render indicator
5. Optionally fetch fuzzy data → Render fuzzy overlay
```

#### 4. Chart Synchronization
```
1. User interacts with any chart → Capture event
2. Propagate time scale changes → Sync all charts
3. Update crosshair position → Show values across charts
4. Maintain zoom/pan state → Consistent user experience
```

## 🚨 CRITICAL ARCHITECTURE ISSUE - POST-MVP PRIORITY

**MAJOR INEFFICIENCY**: The current indicator calculation API requires the frontend to:
1. Load OHLCV data via `POST /api/v1/data/load`
2. Send the same OHLCV data back to `POST /api/v1/indicators/calculate`

This creates unnecessary network overhead and couples data management to the client.

**RECOMMENDED POST-MVP REFACTOR**:
```python
# Better API design - server-side context
POST /api/v1/data/sessions          # Create data session with symbol/timeframe
GET  /api/v1/sessions/{id}/indicators/{name}  # Calculate indicator on server data
POST /api/v1/sessions/{id}/indicators # Add multiple indicators to session
```

**Benefits**:
- Eliminates duplicate data transfer
- Server manages data context and caching
- Faster indicator calculations
- Better scalability
- Reduced client memory usage

**For MVP**: We'll work with current API but this is technical debt that needs addressing.

---

## Backend Integration

### API Endpoints Used
Based on your actual FastAPI backend:

**Data API:**
```python
GET  /api/v1/symbols                 # List available symbols
GET  /api/v1/timeframes              # List available timeframes  
POST /api/v1/data/load               # Load OHLCV data
GET  /api/v1/data/latest             # Get latest data point
GET  /api/v1/data/status             # Check data status
```

**Indicator API:**
```python
GET  /api/v1/indicators              # List available indicators
POST /api/v1/indicators/calculate    # Calculate indicators on data
GET  /api/v1/indicators/defaults     # Get default parameters
GET  /api/v1/indicators/{name}/info  # Get indicator details
```

**Missing for MVP (Fuzzy Sets):**
```python
# These endpoints likely need to be added to your backend
GET  /api/v1/fuzzy/{symbol}          # Get fuzzy sets for symbol
POST /api/v1/fuzzy/calculate         # Calculate fuzzy sets
```

### Data Transformation
Frontend will need to transform backend data formats to TradingView-compatible formats:

```typescript
// Backend OHLCV format → TradingView format
const transformOHLCVData = (backendData: OHLCVPoint[]): CandlestickData[] => {
  return backendData.map(point => ({
    time: new Date(point.timestamp).getTime() / 1000 as UTCTimestamp,
    open: point.open,
    high: point.high,
    low: point.low,
    close: point.close
  }))
}

// Backend indicator data → TradingView LineData
const transformIndicatorData = (
  indicatorValues: (number | null)[], 
  priceData: OHLCVPoint[]
): LineData[] => {
  return indicatorValues.map((value, index) => ({
    time: new Date(priceData[index].timestamp).getTime() / 1000 as UTCTimestamp,
    value: value || undefined // TradingView uses undefined for gaps, not null
  })).filter(point => point.value !== undefined)
}

// Backend fuzzy sets → Chart overlay data
const transformFuzzyData = (
  fuzzySet: FuzzySet,
  priceData: OHLCVPoint[]
): AreaData[] => {
  return fuzzySet.membership.map(point => ({
    time: new Date(point.timestamp).getTime() / 1000 as UTCTimestamp,
    value: point.value
  }))
}

// API error handling
const handleAPIError = (response: any): APIError => {
  if (!response.success) {
    return response as APIError
  }
  throw new Error('Invalid API response format')
}
```

## MVP vs Next Version Features

### MVP (Option A - Simple Approach)

#### Layout & Navigation
- ✅ Collapsible left sidebar with mode selection
- ✅ Collapsible right sidebar with indicator management
- ✅ Header showing current mode title
- ✅ Hamburger buttons for sidebar collapse

#### Indicator Management (Simplified)
- ✅ Instrument selector dropdown (clearly labeled)
- ✅ Active indicators list showing "Name + basic params"
- ✅ Add indicator button with simple dropdown selection
- ✅ Remove indicator (trash icon on hover or simple X button)
- ✅ Show/hide indicator toggle (eye icon or checkbox)
- ✅ Basic parameter inputs (simple text fields, no advanced modal)
- ✅ Fuzzy set visibility toggles per indicator

#### Chart Features
- ✅ Synchronized time-axis across all charts
- ✅ Basic crosshair coordination
- ✅ Fuzzy set overlays with colored shading

### Next Version (Option B - Full TradingView UX)

#### Advanced Indicator Management
- 🎯 **Rich indicator display**: "MACD 12 26 close -0.1061 -1.48 -1.37" format
- 🎯 **Real-time values**: Show current values at crosshair position
- 🎯 **Hover controls**: Icons appear on hover (eye, settings, trash, menu)
- 🎯 **Advanced settings modal** with tabs:
  - **Inputs tab**: All indicator parameters with proper validation
  - **Style tab**: Colors, line thickness, display options
  - **Visibility tab**: Show/hide on different timeframes, price scales
- 🎯 **Drag & drop**: Reorder indicators in sidebar
- 🎯 **Presets**: Save/load indicator configurations

#### Enhanced Chart Features
- 🎯 **Drawing tools**: Trend lines, annotations
- 🎯 **Multi-timeframe** support
- 🎯 **Chart themes**: Dark/light mode, custom color schemes
- 🎯 **Advanced crosshair**: Magnetic crosshair, price/time labels
- 🎯 **Zoom controls**: Zoom to range, fit screen, etc.

#### Advanced Fuzzy Visualization
- 🎯 **Membership function plots**: Dedicated panels showing fuzzy curves
- 🎯 **Activation indicators**: Visual markers when fuzzy sets activate
- 🎯 **Fuzzy rule visualization**: Show rule firing and strength
- 🎯 **Custom fuzzy colors**: User-configurable color schemes

## Performance Considerations

### Chart Optimization
- Use TradingView's built-in virtualization for large datasets
- Implement data windowing for very large historical datasets
- Debounce API calls during rapid user interactions
- Cache indicator calculations when parameters haven't changed

### Memory Management
- Clean up chart instances when components unmount
- Limit number of simultaneous indicator charts
- Implement data garbage collection for off-screen time ranges

### Network Optimization
- Batch API requests where possible
- Implement request caching for recently fetched data
- Use HTTP compression for large data transfers
- Consider WebSocket for future real-time features

## Error Handling & UX

### Error Boundaries
- Component-level error boundaries for chart failures
- Global error boundary for unhandled exceptions
- Graceful degradation when APIs are unavailable

### Loading States
- Skeleton screens for chart loading
- Progress indicators for long-running operations
- Optimistic updates where appropriate

### User Feedback
- Toast notifications for actions and errors
- Clear error messages with suggested actions
- Confirmation dialogs for destructive actions

## Testing Strategy

### Unit Testing
- Chart component logic (without TradingView rendering)
- Data transformation utilities
- API client methods
- State management reducers

### Integration Testing
- Chart synchronization behavior
- API integration with mock backend
- User workflows (add indicator, switch instrument)

### E2E Testing
- Critical user paths through the research interface
- Chart interaction behaviors
- Error scenario handling

## Deployment & DevOps

### Development Environment
- Local development with proxy to backend API
- Hot reload for rapid iteration
- Mock data for offline development

### Production Build
- Static asset optimization
- Environment-specific configuration
- CDN integration for TradingView assets

This architecture provides a solid foundation for your MVP while maintaining flexibility for future Train and Run phases. The modular design ensures each component can be developed and tested independently while maintaining clean data flow throughout the application.