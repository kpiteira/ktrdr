# KTRDR UI Architecture Blueprint: FastAPI + Modern Frontend

## 1. Introduction & Architecture Overview

This document outlines the architecture for KTRDR's user interface, following a modern approach that separates the frontend and backend via a well-defined API. This architecture is designed to provide a robust, scalable, and maintainable solution that integrates with the core KTRDR modules while providing an excellent user experience.

### 1.1 Architecture Diagram

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│                 │      │                 │      │                 │
│  Modern         │      │  FastAPI        │      │  Existing       │
│  Frontend       │◄────►│  Backend        │◄────►│  KTRDR Modules  │
│  (React/Vue)    │      │  (API Layer)    │      │  (Core Logic)   │
│                 │      │                 │      │                 │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

### 1.2 Core Principles

1. **Separation of Concerns**: Clear boundaries between data management, business logic, and presentation
2. **API-First Design**: All functionality available through a well-defined API
3. **Modern Frontend Practices**: Component-based architecture with strong typing
4. **Preserving Core Investments**: Seamless integration with existing KTRDR modules
5. **Performance-Focused**: Efficient data transfer and rendering optimized for financial visualizations

### 1.3 Key Architectural Components

1. **Frontend Application**: 
   - Single-page application (SPA) built with React and TypeScript
   - Responsive design for desktop and tablet use cases
   - Modular component architecture

2. **Backend API Layer**: 
   - FastAPI-based REST endpoints
   - Structured data models with Pydantic
   - Efficient data transformation between core modules and API clients

3. **Core KTRDR Modules**:
   - Existing data management, indicator computation, etc.
   - Adapted to work with the API layer through service adapters

## 2. Backend Architecture

### 2.1 Directory Structure

```
ktrdr/
├── api/                  # New API module
│   ├── __init__.py
│   ├── main.py           # FastAPI app entry point
│   ├── dependencies.py   # Dependency injection
│   ├── endpoints/        # API endpoints
│   │   ├── __init__.py
│   │   ├── data.py       # Data loading endpoints
│   │   ├── indicators.py # Indicator calculation endpoints
│   │   ├── charts.py     # Chart generation endpoints
│   │   └── strategies.py # Strategy execution endpoints
│   ├── models/           # Pydantic models for API
│   │   ├── __init__.py
│   │   ├── data.py
│   │   ├── indicators.py
│   │   └── charts.py
│   └── services/         # Services connecting to core modules
│       ├── __init__.py
│       ├── data_service.py
│       ├── indicator_service.py
│       └── chart_service.py
```

### 2.2 Key API Modules

#### 2.2.1 Endpoint Modules

Each endpoint module represents a logical grouping of related functionality:

1. **Data Endpoints** (`data.py`):
   - Symbol and timeframe information
   - OHLCV data loading and retrieval
   - Data source management

2. **Indicator Endpoints** (`indicators.py`):
   - Available indicator listing
   - Indicator calculation
   - Indicator parameter management

3. **Chart Endpoints** (`charts.py`):
   - Chart generation and configuration
   - Chart data preparation for visualization
   - Multi-panel layout management

4. **Strategy Endpoints** (`strategies.py`):
   - Strategy configuration
   - Fuzzy logic parameters
   - Execution and results

#### 2.2.2 Service Layer

The service layer adapts existing KTRDR modules to the API requirements:

```python
# Example: ktrdr/api/services/data_service.py
from ktrdr.data import DataManager  # Existing KTRDR module

class DataService:
    def __init__(self):
        self.data_manager = DataManager()
    
    async def load_data(self, symbol, timeframe, start_date=None, end_date=None):
        """Load data and convert to API format."""
        # Call existing DataManager
        df = self.data_manager.load(
            symbol=symbol,
            interval=timeframe,
            start=start_date,
            end=end_date
        )
        
        # Transform to API response format
        return {
            "success": True,
            "data": {
                "dates": df.index.tolist(),
                "ohlcv": df[['open', 'high', 'low', 'close', 'volume']].values.tolist(),
                "metadata": {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "start": df.index.min().isoformat(),
                    "end": df.index.max().isoformat(),
                    "points": len(df)
                }
            }
        }
```

### 2.3 Data Models

Pydantic models ensure type safety and validation:

```python
# Example: ktrdr/api/models/data.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Dict, Any, Optional

class DataLoadRequest(BaseModel):
    """Request model for loading data."""
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Data timeframe (e.g., '1d', '1h')")
    start_date: Optional[datetime] = Field(None, description="Start date")
    end_date: Optional[datetime] = Field(None, description="End date")

class OHLCVData(BaseModel):
    """OHLCV data response model."""
    dates: List[str]
    ohlcv: List[List[float]]
    metadata: Dict[str, Any]

class DataLoadResponse(BaseModel):
    """Response model for data loading."""
    success: bool
    data: Optional[OHLCVData] = None
    error: Optional[str] = None
```

### 2.4 API Contract

The API contract defines the communication interface between frontend and backend:

#### 2.4.1 Data API

```
GET /api/v1/symbols
- Returns list of available symbols

GET /api/v1/timeframes
- Returns available timeframes

POST /api/v1/data/load
- Request: { symbol: string, timeframe: string, start_date?: string, end_date?: string }
- Response: { 
    success: boolean, 
    data: { 
      dates: string[], 
      ohlcv: number[][], 
      metadata: Object 
    } 
  }
```

#### 2.4.2 Indicator API

```
GET /api/v1/indicators
- Returns list of available indicators with metadata

POST /api/v1/indicators/calculate
- Request: { 
    symbol: string, 
    timeframe: string,
    indicators: [{ name: string, parameters: Object }] 
  }
- Response: {
    success: boolean,
    data: {
      dates: string[],
      indicators: { [indicatorName: string]: number[] }
    }
  }
```

#### 2.4.3 Chart API

```
POST /api/v1/charts/render
- Request: { 
    symbol: string,
    timeframe: string,
    indicators: [{ name: string, parameters: Object }],
    options: { theme: string, height: number, ... }
  }
- Response: {
    success: boolean,
    chart_data: Object, // Structured for TradingView charts
    panels: [{ id: string, title: string, ... }]
  }
```

#### 2.4.4 Strategy API

```
GET /api/v1/strategies
- Returns list of available strategies

GET /api/v1/strategies/{strategy_id}
- Returns detailed strategy configuration

POST /api/v1/strategies/evaluate
- Request: { 
    strategy_id: string,
    symbol: string,
    timeframe: string,
    start_date?: string,
    end_date?: string
  }
- Response: {
    success: boolean,
    results: {
      trades: Array,
      metrics: Object,
      equity_curve: number[]
    }
  }
```

### 2.5 Error Handling

Standardized error responses ensure consistent error handling:

```python
# Example error response
{
    "success": false,
    "error": {
        "code": "DATA_NOT_FOUND",
        "message": "No data available for AAPL with timeframe 1d",
        "details": {
            "symbol": "AAPL",
            "timeframe": "1d"
        }
    }
}
```

Error handling middleware in FastAPI:

```python
@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    """Handle all unhandled exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(exc),
                "details": None
            }
        }
    )
```

## 3. Frontend Architecture

### 3.1 Technology Stack

- **Framework**: React with TypeScript
- **State Management**: Redux Toolkit
- **UI Components**: Chakra UI or Material UI
- **Charting**: TradingView Lightweight Charts
- **API Client**: Axios with TypeScript types
- **Build Tools**: Vite for fast development

### 3.2 Directory Structure

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── api/                  # API client
│   │   ├── client.ts         # Base axios setup
│   │   ├── data.ts           # Data API methods
│   │   ├── indicators.ts     # Indicator API methods
│   │   └── charts.ts         # Chart API methods
│   ├── components/           # React components
│   │   ├── common/           # Shared components
│   │   │   ├── Button.tsx
│   │   │   ├── Select.tsx
│   │   │   └── Card.tsx
│   │   ├── charts/           # Chart components
│   │   │   ├── CandlestickChart.tsx
│   │   │   ├── IndicatorPanel.tsx
│   │   │   └── ChartControls.tsx
│   │   ├── data/             # Data components
│   │   │   ├── SymbolSelector.tsx
│   │   │   └── TimeframeSelector.tsx
│   │   └── layouts/          # Layout components
│   │       ├── Header.tsx
│   │       ├── Sidebar.tsx
│   │       └── MainLayout.tsx
│   ├── pages/                # Page components
│   │   ├── Dashboard.tsx
│   │   ├── ChartAnalysis.tsx
│   │   └── StrategyBuilder.tsx
│   ├── store/                # Redux store
│   │   ├── index.ts          # Store configuration
│   │   ├── slices/           # Redux slices
│   │   │   ├── dataSlice.ts
│   │   │   ├── indicatorSlice.ts
│   │   │   └── uiSlice.ts
│   │   └── hooks.ts          # Custom Redux hooks
│   ├── types/                # TypeScript types
│   │   ├── data.ts
│   │   ├── indicators.ts
│   │   └── charts.ts
│   ├── utils/                # Utility functions
│   │   ├── formatting.ts
│   │   ├── date.ts
│   │   └── calculations.ts
│   ├── App.tsx               # Main App component
│   └── index.tsx             # Application entry point
├── package.json
└── tsconfig.json
```

### 3.3 Component Architecture

Components follow a modular, hierarchical structure:

1. **Base Components**: Reusable UI elements (buttons, inputs, cards)
2. **Feature Components**: Domain-specific components (charts, indicators)
3. **Page Components**: Full-page views that compose feature components
4. **Layout Components**: Structure the application (header, sidebar, main layout)

### 3.4 State Management

Redux Toolkit provides centralized state management with these key slices:

#### 3.4.1 Application State Slices

1. **Data Slice**: Manages OHLCV data and related state
   ```typescript
   interface DataState {
     symbols: string[];
     timeframes: string[];
     currentSymbol: string | null;
     currentTimeframe: string | null;
     ohlcvData: OHLCVData | null;
     loadingStatus: 'idle' | 'loading' | 'succeeded' | 'failed';
     error: string | null;
   }
   ```

2. **Indicator Slice**: Manages indicator configurations and data
   ```typescript
   interface IndicatorState {
     availableIndicators: IndicatorMetadata[];
     selectedIndicators: IndicatorConfig[];
     indicatorData: Record<string, number[]>;
     loadingStatus: 'idle' | 'loading' | 'succeeded' | 'failed';
     error: string | null;
   }
   ```

3. **UI Slice**: Manages UI state like theme, layout preferences
   ```typescript
   interface UIState {
     theme: 'light' | 'dark';
     sidebarOpen: boolean;
     currentView: string;
     chartSettings: {
       height: number;
       showVolume: boolean;
       showGridlines: boolean;
     };
   }
   ```

#### 3.4.2 Core Redux Patterns

```typescript
// Example of a slice with async thunk
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { loadData } from '../api/data';

export const fetchData = createAsyncThunk(
  'data/fetchData',
  async ({ symbol, timeframe, startDate, endDate }) => {
    const response = await loadData(symbol, timeframe, startDate, endDate);
    return response.data;
  }
);

const dataSlice = createSlice({
  name: 'data',
  initialState,
  reducers: {
    setCurrentSymbol(state, action) {
      state.currentSymbol = action.payload;
    },
    // Additional reducers
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchData.pending, (state) => {
        state.loadingStatus = 'loading';
      })
      .addCase(fetchData.fulfilled, (state, action) => {
        state.loadingStatus = 'succeeded';
        state.ohlcvData = action.payload;
      })
      .addCase(fetchData.rejected, (state, action) => {
        state.loadingStatus = 'failed';
        state.error = action.error.message;
      });
  },
});
```

### 3.5 Chart Rendering Architecture

Charting is a critical component with specialized architecture:

```typescript
// Example ChartManager component
interface ChartManagerProps {
  symbol: string;
  timeframe: string;
  ohlcvData: OHLCVData;
  indicators: IndicatorConfig[];
  indicatorData: Record<string, number[]>;
  theme: 'light' | 'dark';
}

const ChartManager: React.FC<ChartManagerProps> = ({
  symbol,
  timeframe,
  ohlcvData,
  indicators,
  indicatorData,
  theme,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [chart, setChart] = useState<IChartApi | null>(null);
  
  // Initialize chart on mount
  useEffect(() => {
    if (chartContainerRef.current && ohlcvData) {
      const newChart = createChart(chartContainerRef.current, {
        width: chartContainerRef.current.clientWidth,
        height: 500,
        layout: {
          background: { type: 'solid', color: theme === 'dark' ? '#1E1E1E' : '#FFFFFF' },
          textColor: theme === 'dark' ? '#D9D9D9' : '#191919',
        },
        grid: {
          vertLines: { color: theme === 'dark' ? '#2B2B43' : '#E6E6E6' },
          horzLines: { color: theme === 'dark' ? '#2B2B43' : '#E6E6E6' },
        },
        timeScale: {
          timeVisible: true,
          borderColor: theme === 'dark' ? '#2B2B43' : '#E6E6E6',
        },
      });
      
      // Add candlestick series
      const candlestickSeries = newChart.addCandlestickSeries();
      candlestickSeries.setData(formatOhlcvData(ohlcvData));
      
      // Add indicator series
      indicators.forEach(indicator => {
        // Add appropriate series based on indicator type
        // ...
      });
      
      setChart(newChart);
      
      // Cleanup
      return () => {
        newChart.remove();
      };
    }
  }, [chartContainerRef, ohlcvData, theme]);
  
  // Update chart when data changes
  useEffect(() => {
    // Update logic here
  }, [ohlcvData, indicatorData]);
  
  return <div ref={chartContainerRef} />;
};
```

## 4. Implementation Roadmap

### 4.1 Migration Plan

The transition from the current architecture to the new UI architecture will follow these phases:

#### Phase 1: Infrastructure Setup (4-6 weeks)

1. **Week 1-2**: Set up FastAPI backend structure
   - Create project structure
   - Implement basic endpoints
   - Create Pydantic models

2. **Week 3-4**: Set up React frontend
   - Create project with Vite
   - Set up routing and basic layouts
   - Implement API client

3. **Week 5-6**: Core integration
   - Connect API with existing modules
   - Implement authentication (if required)
   - Set up CI/CD pipeline

#### Phase 2: Feature Parity Implementation (8-10 weeks)

1. **Week 1-3**: Data Management
   - Symbol and timeframe selection
   - Data loading and display
   - Basic charting

2. **Week 4-6**: Indicator Implementation
   - Indicator configuration
   - Calculation and display
   - Multi-panel layouts

3. **Week 7-10**: Strategy Functionality
   - Strategy configuration
   - Execution and visualization
   - Results analysis

#### Phase 3: Enhanced Functionality (6-8 weeks)

1. **Week 1-3**: Advanced UI Features
   - Improved layouts and interactions
   - Saved configurations
   - User preferences

2. **Week 4-6**: Performance Optimization
   - Data caching
   - Rendering optimizations
   - Response time improvements

3. **Week 7-8**: Final Testing and Refinement
   - User acceptance testing
   - Bug fixing
   - Documentation

### 4.2 Transition Strategies

To ensure a smooth transition:

1. **Parallel Development**: Maintain the existing UI while developing the new one
2. **Incremental Features**: Roll out features incrementally rather than all at once
3. **User Feedback**: Gather early feedback on new UI components
4. **Performance Benchmarking**: Compare old vs new for critical operations

## 5. Integration with Existing Modules

### 5.1 Service Adapter Pattern

The service adapter pattern bridges existing modules with the API layer:

```python
# Example integration with indicator module
class IndicatorService:
    def __init__(self):
        self.indicator_engine = IndicatorEngine()
    
    async def calculate_indicators(self, ohlcv_data, indicator_configs):
        """Transform API request to core module format and back."""
        # 1. Convert from API format to core module format
        df = pd.DataFrame(
            ohlcv_data["ohlcv"],
            columns=["open", "high", "low", "close", "volume"],
            index=pd.to_datetime(ohlcv_data["dates"])
        )
        
        # 2. Convert indicator configs to format expected by core
        indicators_dict = {
            indicator["name"]: indicator["parameters"]
            for indicator in indicator_configs
        }
        
        # 3. Call existing core module
        result_df = self.indicator_engine.apply(df, indicators_dict)
        
        # 4. Convert result back to API format
        indicator_columns = [col for col in result_df.columns
                            if col not in ["open", "high", "low", "close", "volume"]]
        
        return {
            "success": True,
            "data": {
                "dates": result_df.index.astype(str).tolist(),
                "indicators": {
                    col: result_df[col].tolist() for col in indicator_columns
                }
            }
        }
```

### 5.2 Preserving Existing Logic

The architecture ensures all core business logic remains unchanged:

1. **No Logic in API Layer**: API endpoints only transform data and call services
2. **Stateless Services**: Service adapters don't maintain state
3. **Clear Boundaries**: Well-defined interfaces between layers

## 6. Testing Strategy

### 6.1 Backend Testing

1. **Unit Tests**: Test individual endpoint functions and services
   ```python
   def test_data_service_load():
       service = DataService()
       result = service.load_data("AAPL", "1d", "2023-01-01", "2023-01-31")
       assert result["success"] is True
       assert "data" in result
       assert len(result["data"]["dates"]) > 0
   ```

2. **Integration Tests**: Test API endpoints with mocked core services
   ```python
   async def test_load_data_endpoint():
       response = await client.post(
           "/api/v1/data/load",
           json={
               "symbol": "AAPL",
               "timeframe": "1d",
               "start_date": "2023-01-01",
               "end_date": "2023-01-31"
           }
       )
       assert response.status_code == 200
       data = response.json()
       assert data["success"] is True
   ```

3. **API Contract Tests**: Ensure API responses match the defined contract

### 6.2 Frontend Testing

1. **Component Tests**: Test individual React components
   ```typescript
   test('SymbolSelector shows available symbols', () => {
       const symbols = ['AAPL', 'MSFT', 'GOOG'];
       render(<SymbolSelector symbols={symbols} />);
       symbols.forEach(symbol => {
           expect(screen.getByText(symbol)).toBeInTheDocument();
       });
   });
   ```

2. **Integration Tests**: Test connected components with Redux store
3. **E2E Tests**: Test complete user workflows with Cypress

### 6.3 Visual Regression Testing

For chart components, visual regression testing ensures consistent rendering:

1. Use tools like Percy or Chromatic to capture screenshots
2. Compare visual changes between builds
3. Approve or reject visual changes in the review process

## 7. Performance Considerations

### 7.1 Data Transfer Optimization

To efficiently transfer large datasets:

1. **Binary Formats**: Use MessagePack for more efficient data transfer
   ```python
   @app.post("/api/v1/data/load/binary")
   async def load_data_binary(request: DataLoadRequest):
       data = data_service.load_data(
           symbol=request.symbol,
           timeframe=request.timeframe,
           start_date=request.start_date,
           end_date=request.end_date
       )
       return Response(
           content=msgpack.packb(data),
           media_type="application/x-msgpack"
       )
   ```

2. **Pagination**: For large datasets, implement pagination
   ```python
   @app.post("/api/v1/data/load/paged")
   async def load_data_paged(
       request: DataLoadRequest, 
       page: int = Query(1), 
       page_size: int = Query(1000)
   ):
       # ...
   ```

3. **Data Compression**: Use gzip compression for HTTP responses
   ```python
   app = FastAPI()
   app.add_middleware(GZipMiddleware, minimum_size=1000)
   ```

### 7.2 Rendering Optimization

For smooth chart rendering with large datasets:

1. **Data Downsampling**: Reduce points for zoomed-out views
2. **Virtualization**: Only render visible data points
3. **Web Workers**: Offload heavy calculations to background threads

## 8. Conclusion

This UI architecture blueprint provides a comprehensive approach for transitioning KTRDR from its current implementation to a modern, scalable, and maintainable architecture using FastAPI and React. The design preserves investments in core modules while enabling a significantly enhanced user experience and developer workflow.

The API-first approach ensures clean separation of concerns while enabling future extensibility. The component-based frontend architecture promotes reusability and maintainability. The clear implementation roadmap provides a practical path forward with appropriate validation points throughout the process.

By following this blueprint, KTRDR will achieve a modern UI architecture that supports both current needs and future growth, with significantly improved development velocity and user experience.