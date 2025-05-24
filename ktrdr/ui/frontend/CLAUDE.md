# KTRDR Frontend Development Guide

## Project Overview

**MVP Goal**: Research Phase trading UI for visualizing instrument data, indicators, and fuzzy sets.

**Architecture**: React + TypeScript with TradingView Lightweight Charts, following vertical slice development approach.

## Environment Setup

- Use Docker for development: `./docker_dev.sh start` from the root directory
- Frontend runs on port 5173 (Vite dev server)
- Backend API available at `http://localhost:8000/api/v1`
- Commands should be run inside the Docker container

## Library Versions

- **TradingView Lightweight Charts**: v5.0.7
  - Uses ES2020 modules with improved tree-shaking
  - Working examples should be created following v5 API patterns

## Architecture Overview

### Component Hierarchy (from trading-ui-architecture.md)
```
App
├── Layout
│   ├── Header (current mode title only)
│   ├── LeftSidebar (collapsible - mode selection)
│   ├── RightSidebar (collapsible - indicator management)
│   │   ├── InstrumentSelector
│   │   ├── ActiveIndicatorsList
│   │   ├── AddIndicatorButton
│   │   └── FuzzySetControls
│   └── MainContent
│       └── ResearchView
│           └── ChartContainer
│               ├── PriceChart (main candlestick + overlays)
│               └── IndicatorChart[] (RSI, MACD, etc.)
```

### State Management
- **MVP Approach**: React Context + useReducer (avoid Redux for MVP)
- **Data Flow**: API client → Context → Components
- **Error Handling**: Centralized error boundary and API error handling

## Development Workflow

### Vertical Slice Approach (8 slices total)
Development follows incremental slices, each delivering working functionality:

1. **Slice 1**: Basic candlestick chart with hardcoded EURUSD data
2. **Slice 2**: Symbol selection dropdown
3. **Slice 3**: First indicator (SMA overlay)
4. **Slice 4**: Indicator management sidebar
5. **Slice 5**: Second chart type (RSI in separate panel)
6. **Slice 6**: Parameter controls
7. **Slice 7**: Full sidebar layout with collapsible panels
8. **Slice 8**: Error & loading polish

### Common Tasks

- **Start Development**:
  ```bash
  ./docker_dev.sh start
  ./docker_dev.sh shell-frontend
  npm run dev  # Runs on port 5173
  ```

- **API Testing**:
  ```bash
  # Test backend connectivity
  curl http://localhost:8000/api/v1/symbols
  ```

- **Build & Test**:
  ```bash
  npm run build
  npm run test
  npm run lint
  npm run typecheck
  ```

## Lightweight Charts v5.0.7 Usage

### ES2020 Module Imports

The project uses Lightweight Charts v5.0.7 as an ES module. Import directly from the package:

```typescript
import { 
  createChart, 
  CandlestickSeries, 
  HistogramSeries, 
  LineSeries,
  createSeriesMarkers,
  createTextWatermark 
} from 'lightweight-charts';
```

### Breaking Changes from v4 to v5

**1. Unified Series Creation API:**
```typescript
// ❌ v4 approach (deprecated)
const candlestickSeries = chart.addCandlestickSeries(options);
const volumeSeries = chart.addHistogramSeries(options);
const lineSeries = chart.addLineSeries(options);

// ✅ v5 approach (correct)
const candlestickSeries = chart.addSeries(CandlestickSeries, options);
const volumeSeries = chart.addSeries(HistogramSeries, options);
const lineSeries = chart.addSeries(LineSeries, options);
```

**2. Series Markers (now separate primitives):**
```typescript
// ✅ v5 approach
import { createSeriesMarkers } from 'lightweight-charts';
const seriesMarkers = createSeriesMarkers(series, [
    {
        time: '2019-04-09',
        position: 'aboveBar',
        color: 'black',
        shape: 'arrowDown'
    }
]);
```

**3. Watermarks (now plugins):**
```typescript
// ✅ v5 approach
import { createTextWatermark } from 'lightweight-charts';
const firstPane = chart.panes()[0];
createTextWatermark(firstPane, {
    lines: [{
        text: 'Watermark Text',
        color: 'rgba(255,0,0,0.5)'
    }]
});
```

### Complete v5 Example

```typescript
import { createChart, CandlestickSeries, HistogramSeries } from 'lightweight-charts';

// Create chart
const chart = createChart(container, {
  width: 800,
  height: 400,
  // other options...
});

// Add a candlestick series (v5 unified API)
const candlestickSeries = chart.addSeries(CandlestickSeries, {
  upColor: '#26a69a',
  downColor: '#ef5350',
  wickUpColor: '#26a69a',
  wickDownColor: '#ef5350',
  borderVisible: false,
});

// Add volume series (v5 unified API)
const volumeSeries = chart.addSeries(HistogramSeries, {
  color: '#26a69a',
  priceFormat: { type: 'volume' },
  priceScaleId: 'volume',
  scaleMargins: { top: 0.8, bottom: 0 },
});

// Set data (unchanged)
candlestickSeries.setData(candleData);
volumeSeries.setData(volumeData);

// Configure scales (unchanged)
chart.priceScale('volume').applyOptions({
  scaleMargins: { top: 0.8, bottom: 0 },
  borderVisible: false,
});

// Fit chart to content (unchanged)
chart.timeScale().fitContent();
```

### Lessons Learned

1. **ES2020 Modules**: v5 uses ES2020 modules with improved tree-shaking. No longer supports CommonJS or global CDN loading.

2. **Unified API**: v5 uses `chart.addSeries(SeriesType, options)` instead of individual methods like `addCandlestickSeries()`.

3. **Chart Lifecycle**: Always handle chart cleanup properly in the component's unmount/cleanup function.

4. **Error Handling**: Use proper try/catch blocks around chart operations, as they can throw errors that might crash the app.

5. **Migration Required**: Any existing v4 components need to be updated to use the new v5 API.

6. **Preventing Resize Loops**: When implementing resize handling:
   - Use a debounce function to prevent rapid successive resizes
   - Track previous dimensions to avoid unnecessary resize calls
   - Only resize if dimensions have actually changed (with a small threshold)
   - Separate chart initialization from resize handling logic
   - Be careful with calling `applyOptions()` during resize as it can trigger another resize
   - Use `useRef` to store the latest dimensions and prevent stale closures

7. **Handling Multiple Resize Sources**: Resize events can come from:
   - Window resize events
   - Container size changes (flexbox, grid layout changes)
   - Theme changes (if they affect layout)
   - Props changes (explicit width/height)
   - Be careful when implementing multiple resize handlers to ensure they don't conflict

## API Integration

### Available Backend Endpoints
Your FastAPI backend provides these endpoints (confirmed working):

```typescript
// Data Management
GET  /api/v1/symbols                 // List available symbols
GET  /api/v1/timeframes              // List available timeframes  
POST /api/v1/data/load               // Load OHLCV data

// Indicators
GET  /api/v1/indicators              // List available indicators
POST /api/v1/indicators/calculate    // Calculate indicators on data
GET  /api/v1/indicators/defaults     // Get default parameters
GET  /api/v1/indicators/{name}/info  // Get indicator details

// Future: Fuzzy Sets (to be implemented)
GET  /api/v1/fuzzy/{symbol}          // Get fuzzy sets for symbol
POST /api/v1/fuzzy/calculate         // Calculate fuzzy sets
```

### API Client Usage
Use the existing API client in `src/api/client.ts`:

```typescript
import { apiClient } from '../api/client';

// Get symbols
const symbols = await apiClient.get('symbols');

// Load data
const data = await apiClient.post('data/load', {
  symbol: 'EURUSD',
  timeframe: '1d',
  start_date: '2024-01-01',
  end_date: '2024-12-31'
});
```

### Data Transformation
Transform backend data for TradingView charts:

```typescript
// Backend OHLCV → TradingView CandlestickData
const transformOHLCVData = (backendData: OHLCVPoint[]): CandlestickData[] => {
  return backendData.map(point => ({
    time: new Date(point.timestamp).getTime() / 1000 as UTCTimestamp,
    open: point.open,
    high: point.high,
    low: point.low,
    close: point.close
  }));
};
```

## MVP Requirements Summary

### Core Features (Research Phase)
- ✅ Instrument selection and data loading
- ✅ Main candlestick chart with TradingView
- ✅ Technical indicators (overlay + oscillator types)
- 🔄 Fuzzy set visualization (backend integration needed)
- ✅ Synchronized chart interactions
- ✅ Collapsible sidebar layout

### Success Criteria
- Load EURUSD 1H data and display candlestick chart
- Add SMA(20) overlay on price chart
- Add RSI(14) in separate synchronized panel
- Charts stay synchronized when panning/zooming
- Professional loading states and error handling

### Working Examples

Start with Slice 1: Create a basic chart component using v5 API patterns above.

## Directory Structure (recommended)

```
src/
├── components/
│   ├── charts/
│   │   ├── PriceChart.tsx
│   │   ├── IndicatorChart.tsx
│   │   ├── ChartContainer.tsx
│   │   └── fuzzy/
│   │       ├── FuzzyOverlay.tsx
│   │       └── FuzzyLegend.tsx
│   ├── sidebar/
│   │   ├── LeftSidebar.tsx (mode selection)
│   │   ├── RightSidebar.tsx (indicator management)
│   │   ├── InstrumentSelector.tsx
│   │   ├── ActiveIndicatorsList.tsx
│   │   ├── IndicatorItem.tsx
│   │   ├── AddIndicatorButton.tsx
│   │   └── FuzzySetControls.tsx
│   ├── layout/
│   │   ├── Header.tsx
│   │   ├── Layout.tsx
│   │   └── CollapsibleSidebar.tsx
│   └── common/
│       ├── LoadingSpinner.tsx
│       ├── ErrorBoundary.tsx
│       └── Modal.tsx
├── hooks/
│   ├── useChartSync.ts
│   ├── useIndicators.ts
│   ├── useInstrumentData.ts
│   ├── useFuzzyData.ts
│   └── useSidebarCollapse.ts
├── context/  (state management)
│   ├── AppContext.tsx
│   ├── AppReducer.ts
│   └── types.ts
├── utils/
│   ├── dataTransform.ts
│   ├── colorUtils.ts
│   └── constants.ts
└── views/
    ├── ResearchView.tsx
    ├── TrainView.tsx (placeholder)
    └── RunView.tsx (placeholder)
```

## Development Guidelines

### Code Style
- **TypeScript**: Required for all components with proper typing
- **React Hooks**: Use functional components with hooks
- **State Management**: React Context + useReducer (avoid Redux for MVP)
- **Testing**: Write unit tests for all new functionality
- **Error Handling**: Use centralized error boundaries

### Performance Considerations
- Use TradingView's built-in virtualization for large datasets
- Implement data windowing for very large historical datasets
- Debounce API calls during rapid user interactions
- Cache indicator calculations when parameters haven't changed
- Clean up chart instances when components unmount

## Known Issues and Solutions

### Infinite Resize Loop Issue

The TradingView Lightweight Charts library can sometimes get into an infinite resize loop, causing browser performance issues. This happens when:

1. A resize operation triggers a change in container dimensions
2. The chart's `resize()` or `applyOptions({ width: x, height: y })` is called
3. This causes the container to resize again, triggering another resize
4. This loop continues infinitely, slowing down the browser

**Ultimate Solution: USE FIXED DIMENSIONS**

After multiple attempts to solve the resize loop, we found that **the only fully reliable approach is to use fixed dimensions**:

1. **Best Practice: Fixed Width & Height**
   - When using CandlestickTradingView, always provide FIXED `width` and `height` props
   - Set `autoResize={false}` to completely disable resize handling
   - Wrap the component in a container that handles the responsive behavior

   Example:
   ```jsx
   <div style={{ 
      width: '100%', 
      maxWidth: '1200px', 
      height: '500px',
      overflow: 'hidden',
      margin: '0 auto',
      boxSizing: 'border-box'
    }}>
     <CandlestickTradingView
       data={data}
       width={1200} // Fixed width
       height={500}  // Fixed height
       autoResize={false} // Disable resize handling
     />
   </div>
   ```

2. **CSS Containment**:
   - Use `contain: strict` on chart containers to prevent them from affecting layout
   - Always set `box-sizing: border-box` and `overflow: hidden`
   - Use fixed dimensions rather than percentages for chart components

**Alternative Approach (less reliable):**

If you must use responsive charts:

1. **Container Management**:
   - Add `overflow: hidden` to chart containers to prevent potential overflows
   - Make sure containers have explicit dimensions or stable dimensions from CSS

2. **Resize Logic Improvements**:
   - Add dimension tracking with refs to prevent unnecessary resizes
   - Implement a larger threshold (5-10px) to account for floating-point errors
   - Use debounce pattern with longer timeouts (250-300ms) to limit resize frequency
   - Only resize when dimensions change significantly

3. **Proper Cleanup**:
   - Fix multiple cleanup functions to ensure no memory leaks
   - Make sure event listeners are properly removed
   - Ensure chart instances are properly disposed when components unmount

4. **Separate Operations**:
   - Separate chart initialization from resize handling
   - Isolate theme changes to only apply visual options, not layout options
   - NEVER call `chartInstance.applyOptions()` during resize operations

5. **React Hook Rules**:
   - NEVER call React hooks (like useRef, useState) inside useEffect or any other function
   - Always declare all refs at the component level, outside of any hooks or functions
   - Use refs to store mutable values that need to persist between renders
   - When working with timeouts or intervals in resize handlers, store the IDs in refs to properly clean them up