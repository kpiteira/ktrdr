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

# 🧭 KTRDR Frontend UI – Detailed Specification v2

**Last Updated:** May 12, 2025

This document provides a detailed specification for the KTRDR trading research platform's React frontend. It incorporates initial requirements, sketches, and feedback to create a more robust guide for development, particularly when using an LLM for code generation.

**API Base Path:** All backend API endpoints are prefixed with `/api/v1/`.

---

## 🗂️ Recommended File & Folder Structure

```txt
src/
├── app/                        # App-wide layout + routing
│   ├── App.jsx
│   ├── Layout.jsx
│   ├── Sidebar.jsx
│   ├── TopBar.jsx
│   ├── Router.tsx
│   ├── routes.tsx
│   └── ThemeProvider.jsx
│
├── components/shared/          # Truly shared atoms (Modal, Button, Spinner)
│   ├── Modal.jsx
│   ├── Spinner.jsx
│   └── NotificationSystem.jsx
│
├── features/
│   ├── research/
│   │   ├── ResearchPage.jsx
│   │   ├── components/
│   │   │   ├── SymbolTimeframeSelector.jsx
│   │   │   ├── IndicatorPanel.jsx
│   │   │   ├── MainChartPanel.jsx
│   │   │   ├── AddIndicatorModal.jsx
│   │   │   ├── EditIndicatorModal.jsx
│   │   │   └── FuzzyLogicPanel.jsx
│   │   ├── hooks/
│   │   │   ├── useChartData.js
│   │   │   ├── useIndicators.js
│   │   ├── utils/
│   │   │   ├── transformIndicatorConfig.js
│   │   └── research.state.js     # Zustand/Jotai only if needed later
│
│   ├── train/
│   │   └── TrainPage.jsx
│
│   ├── run/
│   │   └── RunPage.jsx
│
├── services/                   # All API access lives here
│   ├── marketDataAPI.js        # fetchSymbols(), fetchChartData()
│   ├── indicatorAPI.js         # fetchAvailableIndicators()
│   └── fuzzyAPI.js             # fetchFuzzyConfig()
│
├── store/                      # Redux (theme/sidebar)
│   ├── index.ts
│   └── uiSlice.ts
│
├── main.jsx
├── index.css                   # Tailwind base
└── index.html
```

---

## 🔧 App Architecture Overview (Recap)

* **Layout**: Horizontal split:
    * Left Sidebar (Mode Switcher)
    * Top Bar (Contextual Title, Global Controls)
    * Main Content Area (Mode-Specific)
    * Optional Right Panel (Mode-Specific Options/Controls) - *As per sketch `scan.jpg`*
* **Routing**: Each mode is a route: `/research`, `/train`, `/run`.
* **Core Technologies**: React, Redux (for *truly* global state), TailwindCSS.

---

## 🗂️ UI Zones (Recap)
```
+-------------------------------------------------------------------+
| Top Bar – App Title | Current Mode | Global Actions (e.g., Theme) |
+----+-----------------------------------------------------+--------+
| S  |                                                     | Right  |
| I  |  Main Content Area for Current Mode                 | Panel  |
| D  |  (e.g., Chart, Strategy Builder, Data Tables)       | (Opt.) |
| E  |                                                     |        |
| B  |                                                     |        |
| A  |                                                     |        |
| R  |                                                     |        |
+----+-----------------------------------------------------+--------+
```

---

## 🟣 Sidebar (Left) - `AppSidebar` Component

* **Purpose**: Permanent vertical menu for mode selection.
* **Components**:
    * `ModeSwitcher`:
        * Displays icons and text labels for "Research", "Train", "Run".
        * Active mode is highlighted.
        * Clicking an item navigates to the respective route (e.g., `/research`).
    * `CollapseButton` (Hamburger Icon):
        * Toggles sidebar between full width (icons and text) and narrow width (icons only).
        * As indicated in `scan0001.jpg`: "When closed, show icons of modes".
* **State**:
    * `isCollapsed` (boolean): Managed globally (Redux, as per original spec "sidebar open/closed").
    * `currentMode` (string): Derived from React Router's current route.
* **Styling**: TailwindCSS. Pinned to the left, fixed height.

---

## 🟥 Top Bar - `AppTopBar` Component

* **Purpose**: Displays active mode title and potentially global actions or breadcrumbs.
* **Components**:
    * `ModeTitleDisplay`: Shows text like "Research Mode", "Training Dashboard", "Live Runtime".
    * **(Optional) Breadcrumbs**: For navigation within complex modes. (Defer for now unless specified for Research Mode).
    * **(Optional) Global Actions**: e.g., Theme toggle, User Profile icon (if applicable later).
* **State**:
    * `activeModeTitle` (string): Passed as a prop or derived from the current route.
* **Styling**: TailwindCSS. Fixed at the top.

---

## ✅ State Management Architecture

### Global (Redux):

* `isSidebarCollapsed`
* `theme`
* `notifications`

### Page-local (Component State in ResearchPage):

* `currentSymbol`
* `currentTimeframe`
* `activeIndicators`
* `chartData`
* `showAddIndicatorModal`, `showEditIndicatorModal`
* `isRightPanelCollapsed`

✅ Zustand or Jotai can be introduced **later** if feature-local global state becomes difficult to manage with props alone.

---

## 🧪 Modes Overview & Detailed Specifications

### 1. 🔬 Research Mode (`/research`) - `ResearchPage` Component (Highest Priority)

> **Goal**: Design, backtest, and refine strategies composed of indicators, fuzzy logic, and neural networks. Focus first on Chart + Indicator View.

* **Parent Component**: `ResearchPage.jsx` (acts as the container for this mode).
* **Layout**:
    * The `MainContent` area will primarily feature a `ResizablePanelLayout` (vertical stack of chart and potentially other data panels).
    * A `RightPanel` (collapsible) will house controls like symbol selection and indicator management, as depicted in `scan0001.jpg`.

#### 1.A. Right Panel (Research Mode Controls) - `ResearchControlsPanel` Component

* **Purpose**: Contains controls for symbol selection, timeframe, and indicator management. Collapsible.
* **Location**: Right side of the screen, as per `scan.jpg` and `scan0001.jpg`.
* **Components**:

    * **`SymbolTimeframeSelector` Component**
        * **Purpose**: Allows selection of financial instrument and chart timeframe.
        * **Visuals/Layout (TailwindCSS)**:
            * Outer `div` with `flex flex-col space-y-4 p-4`.
            * **Symbol Selection**:
                * Label: "Symbol"
                * Input: A searchable dropdown/select input (e.g., using a library like `react-select` or a custom Tailwind component).
            * **Timeframe Selection**:
                * Label: "Timeframe"
                * Row of buttons (`<button>`) for common timeframes (e.g., "1M", "5M", "15M", "1H", "4H", "1D"). Visually indicate active timeframe.
        * **Props**:
            * `availableSymbols: { value: string, label: string }[]`
            * `availableTimeframes: string[]` (e.g., `["1M", "5M", "15M", "1H", "4H", "1D"]`)
            * `currentSymbol: string`
            * `currentTimeframe: string`
            * `onSymbolChange: (newSymbol: string) => void`
            * `onTimeframeChange: (newTimeframe: string) => void`
            * `isLoadingSymbols: boolean`
        * **State (Internal)**:
            * `searchTerm` (for symbol dropdown if searchable).
        * **User Interactions**:
            * Typing in symbol dropdown filters `availableSymbols`. Selection calls `onSymbolChange`.
            * Clicking a timeframe button calls `onTimeframeChange`.
        * **API Interaction**:
            * **YOUR INPUT NEEDED**: Endpoint to fetch available symbols.
                * Example: `GET /api/v1/marketdata/symbols`
                * Expected Response: `[{ "value": "BTC/USD", "label": "Bitcoin / US Dollar" }, ...]`

    * **`IndicatorPanel` Component** (managing active indicators)
        * **Purpose**: Lists currently active indicators on the chart, allows adding new ones, editing, and deleting. Based on `scan0001.jpg` ("Indicator List").
        * **Visuals/Layout (TailwindCSS)**:
            * Section Title: "Indicators"
            * `AddIndicatorButton`: A button ("+ Add Indicator").
            * `ActiveIndicatorList`: A list where each item (`ActiveIndicatorListItem`) displays:
                * Indicator name and parameters (e.g., "RSI (14)", "SMA (20)").
                * "Edit" icon/button.
                * "Delete" icon/button.
        * **Props**:
            * `activeIndicators: { id: string, name: string, params: object }[]`
            * `onAddIndicatorClick: () => void` (opens `AddIndicatorModal`)
            * `onEditIndicatorClick: (indicatorId: string) => void` (opens `EditIndicatorModal` pre-filled)
            * `onDeleteIndicator: (indicatorId: string) => void`
        * **User Interactions**:
            * Click "Add Indicator": Opens `AddIndicatorModal`.
            * Click "Edit" on an indicator: Opens `EditIndicatorModal` with that indicator's settings.
            * Click "Delete" on an indicator: Confirms and then calls `onDeleteIndicator`.
        * **API Interaction**:
            * **YOUR INPUT NEEDED**: Endpoint to fetch available indicators (types and their configurable parameters).
                * Example: `GET /api/v1/indicators/available`
                * Expected Response: `[ { "name": "RSI", "paramsSchema": { "period": { "type": "number", "default": 14, "min": 2 } } }, ... ]`

    * **`FuzzyLogicPanel` Component (Placeholder/Info)**
        * **Purpose**: Displays information that fuzzy logic configurations are managed via YAML. May later show loaded fuzzy set definitions.
        * **Visuals/Layout (TailwindCSS)**:
            * Section Title: "Fuzzy Logic"
            * Informational text: "Fuzzy set definitions are managed via YAML configuration files. Overlays will appear on the chart if active." (As per `scan0001.jpg`: "No UI to define Fuzzy Logic Shapes. Done via YAML").
        * **Props**:
            * **(Future)** `loadedFuzzySets: object[]`
        * **API Interaction**: None directly for configuration. May fetch current fuzzy config for display.
            * **YOUR INPUT NEEDED (Optional for display)**: Endpoint to get current fuzzy logic config for a strategy/symbol.
                * Example: `GET /api/v1/fuzzy/config?symbol=<symbol>`

* **`CollapseToggle` for Right Panel**: Hamburger icon to collapse/expand this panel, similar to the left sidebar. State managed in `ResearchPage`.

#### 1.B. Main Content Area (Research Mode) - `ResearchMainContent` Component

* **Purpose**: Displays charts, indicator overlays, and potentially backtesting results.
* **Layout**: Utilizes a `ResizablePanelLayout` allowing vertical resizing of stacked panels, as mentioned in shared behaviors and implied by `scan0001.jpg` ("Panels can be resized").
* **Charting**: All charting must be implemented with TradingView Lightweight Charts v5.0. Specification documentation available at https://tradingview.github.io/lightweight-charts/docs/api
* **Components**:

    * **`MainChartPanel` Component**
        * **Purpose**: Renders the primary candlestick chart with price data and indicator overlays.
        * **Visuals/Layout (TailwindCSS)**:
            * Uses a charting library (e.g., Plotly, Lightweight Charts, or a React wrapper).
            * Candlestick series for main price data.
            * Overlays for indicators (e.g., SMAs, EMAs, Bollinger Bands) directly on the price chart.
            * Separate sub-panes below the main chart for non-overlay indicators (e.g., RSI, MACD), as shown in `scan0001.jpg` ("Non-overlay indicators").
            * Shaded areas for fuzzy activation regions if applicable and data is available. ("Shading for fuzzy activation" - `scan0001.jpg`).
        * **Props**:
            * `chartData: { ohlcv: any[], indicatorData: { [indicatorId: string]: any[] }, fuzzyActivationData?: any[] }`
            * `symbol: string`
            * `timeframe: string`
            * `activeIndicatorsConfig: { id: string, name: string, params: object, type: 'overlay' | 'pane' }[]` (Needs `type` to know where to render)
        * **State (Internal)**:
            * Chart instance, zoom/pan state (managed by the charting library).
        * **User Interactions**:
            * Zooming, panning (handled by charting library).
            * Hovering over data points shows tooltips.
        * **API Interaction**: Data comes via props. This component primarily renders.

    * **(Future) `BacktestResultsPanel` Component**
        * **Purpose**: Displays results from backtesting runs.
        * **Visuals/Layout**: Placeholder for now. "Backtest UI (to be defined later)."
        * **Props**: `backtestData: any`
        * **API Interaction**: Data via props.

* **State Management within `ResearchPage` (Lifting State):**
    * `currentSymbol: string`
    * `currentTimeframe: string`
    * `activeIndicators: { id: string, name: string, params: object, type: 'overlay' | 'pane' }[]` (This is the central list of active indicators with their configurations)
    * `chartData: object` (Fetched based on symbol, timeframe, and active indicators)
    * `isRightPanelCollapsed: boolean`
    * `showAddIndicatorModal: boolean`
    * `showEditIndicatorModal: boolean` (and `indicatorToEditId: string | null`)

* **Data Flow & API Calls from `ResearchPage`**:
    1.  Initialize: Fetch `availableSymbols`.
    2.  On `currentSymbol` or `currentTimeframe` change, or `activeIndicators` change:
        * **YOUR INPUT NEEDED**: Primary data fetching endpoint for chart.
            * Needs to accept symbol, timeframe, and potentially a list of requested indicators and their params.
            * Example: `POST /api/v1/marketdata/chartdata`
            * Request Body:
                ```json
                {
                  "symbol": "BTC/USD",
                  "timeframe": "1H",
                  "indicators": [
                    { "name": "RSI", "params": { "period": 14 } },
                    { "name": "SMA", "params": { "period": 50 } }
                  ],
                  "startTimestamp": "YYYY-MM-DDTHH:mm:ssZ", // Optional
                  "endTimestamp": "YYYY-MM-DDTHH:mm:ssZ"    // Optional
                }
                ```
            * Expected Response:
                ```json
                {
                  "ohlcv": [ { "t": 1672531200, "o": 100, "h": 105, "l": 98, "c": 102, "v": 10000 }, ... ],
                  "indicatorData": {
                    "RSI_14": [ { "t": 1672531200, "value": 60 }, ... ],
                    "SMA_50": [ { "t": 1672531200, "value": 99 }, ... ]
                  }
                  // Potentially fuzzyActivationData as well
                }
                ```

#### 1.C. Modals for Research Mode

* **`AddIndicatorModal` / `EditIndicatorModal` Component(s)**
    * **Purpose**: Allows users to select an indicator and configure its parameters.
    * **Visuals/Layout (TailwindCSS)**:
        * Modal dialog (reuse existing modal system).
        * Dropdown to select indicator type from `availableIndicators`.
        * Dynamically generated form fields based on `paramsSchema` of the selected indicator.
        * "Save" / "Apply" and "Cancel" buttons.
    * **Props**:
        * `isOpen: boolean`
        * `onClose: () => void`
        * `onSave: (indicatorConfig: { name: string, params: object }) => void`
        * `availableIndicators: { name: string, paramsSchema: object }[]` (fetched once and stored/passed down)
        * `initialData?: { name: string, params: object }` (for editing)
    * **State (Internal)**:
        * `selectedIndicatorName: string`
        * `formValues: object`
    * **User Interactions**:
        * Select indicator, form updates. Fill form, click Save.
    * **API Interaction**: Relies on `availableIndicators` prop. Does not directly call APIs itself but provides config data to `ResearchPage` to then potentially re-fetch chart data.

### 2. 🧠 Train Neural Network (`/train`) - `TrainPage` Component

> **Goal**: Visualize training dynamics, feature attribution, and weight evolution. (Initially a blank screen, reserve layout space).

* **Specification**:
    * For now, `TrainPage.jsx` can render a simple placeholder:
        ```jsx
        <div className="p-4">
          <h1 className="text-2xl font-semibold">Train Neural Network Mode</h1>
          <p className="mt-2">Content to be defined. This area will include strategy design, training triggers, and visualization widgets for training dynamics.</p>
        </div>
        ```
    * It should still exist within the main app layout (Sidebar, TopBar).

### 3. 🚀 Runtime Mode (`/run`) - `RunPage` Component

> **Goal**: Monitor deployed strategies, issue emergency stops, observe triggers. (To be defined later).

* **Specification**:
    * For now, `RunPage.jsx` can render a simple placeholder:
        ```jsx
        <div className="p-4">
          <h1 className="text-2xl font-semibold">Runtime Mode</h1>
          <p className="mt-2">Content to be defined. This area will display deployed strategies, allow emergency stops, and show real-time trigger events.</p>
        </div>
        ```
    * It should still exist within the main app layout.

---

## 🔁 Shared Behaviors & Components (Recap & Additions)

* **Collapsible Panels**: Left sidebar and Right panel (in Research Mode) are collapsible.
* **Resizable Stacked Panels**: `MainContent` in Research Mode needs vertically resizable panels. Consider a library like `react-resizable-panels` or build a simple version.
* **Modal System**: Re-use existing modal system for indicator settings, confirmations, etc.
* **`NotificationSystem` Component (New)**
    * **Purpose**: To display global notifications (errors, successes, info messages).
    * **Visuals**: Toast-like notifications, probably in a corner of the screen.
    * **Integration**: Can be triggered via Redux actions or a context API. Product requirements mention "User-Facing Error Messages" and "Notification path from console logs to UI alerts".

---

## 🗺️ User Flow Examples (for Research Mode)

1.  **Initial Load of Research Mode**:
    * User navigates to `/research`.
    * `ResearchPage` mounts.
    * `SymbolTimeframeSelector` attempts to fetch `availableSymbols` from `GET /api/v1/marketdata/symbols`. Displays a loading state.
    * Default symbol/timeframe might be selected, triggering an initial data load for `MainChartPanel`.
    * `IndicatorPanel` fetches `availableIndicators` from `GET /api/v1/indicators/available`.

2.  **User Changes Symbol/Timeframe**:
    * User interacts with `SymbolTimeframeSelector`.
    * `onSymbolChange` or `onTimeframeChange` callbacks are triggered in `ResearchPage`.
    * `ResearchPage` updates its `currentSymbol` / `currentTimeframe` state.
    * A new API call is made to fetch chart data (e.g., `POST /api/v1/marketdata/chartdata`) with the new parameters.
    * `MainChartPanel` updates with new `chartData`. Loading state shown during fetch.

3.  **User Adds a New Indicator**:
    * User clicks "Add Indicator" in `IndicatorPanel`.
    * `ResearchPage` sets `showAddIndicatorModal = true`.
    * `AddIndicatorModal` appears, populated with `availableIndicators`.
    * User selects an indicator type (e.g., "MACD") and configures its parameters.
    * User clicks "Save" in the modal.
    * `onSave` callback in `ResearchPage` is called with the new indicator config.
    * `ResearchPage` adds this indicator to its `activeIndicators` state array.
    * This state change triggers a re-fetch of chart data (including the new indicator).
    * `MainChartPanel` and `IndicatorPanel` list update.

4.  **User Edits an Existing Indicator**:
    * User clicks "Edit" on "SMA (20)" in `IndicatorPanel`.
    * `ResearchPage` sets `indicatorToEditId` and `showEditIndicatorModal = true`.
    * `EditIndicatorModal` appears, pre-filled with "SMA (20)" settings.
    * User changes period to 30, clicks "Save".
    * `onSave` callback updates the specific indicator in the `activeIndicators` array in `ResearchPage`.
    * Triggers re-fetch and UI updates.

5.  **API Error Handling**:
    * A data fetch (e.g., for chart data) fails (network error, server error).
    * The API hook/service catches the error.
    * An action is dispatched to the `NotificationSystem` to display an error message (e.g., "Failed to load chart data. Please try again.").
    * The relevant component (`MainChartPanel`) might show an inline error message or a stale data indicator.

---

## 🛠️ LLM Implementation Guidelines (Refined)

* **Do**:
    * Use functional React components with Hooks.
    * Use TailwindCSS for all styling. Adhere to a consistent spacing/sizing scale if possible.
    * Co-locate features as suggested:
        ```
        src/
          components/shared/      # Truly shared components (Modal, Button, etc.)
          features/
            research/
              components/         # Specific to research mode (SymbolTimeframeSelector, MainChartPanel)
              hooks/              # Custom hooks for research mode (e.g., useResearchChartData)
              ResearchPage.jsx    # Entry point for /research route
              research.state.js   # (Optional) Zustand/Jotai store if local complex state needed beyond component state
              research.utils.js
            train/
            run/
          services/               # API call abstractions (e.g., marketDataAPI.js, indicatorAPI.js)
          store/                  # Redux store (if used beyond theme/sidebar)
          App.jsx
          main.jsx
          index.css               # Main CSS for Tailwind base/globals
        ```
    * Keep cross-cutting utilities minimal.
    * Component Naming: PascalCase (`MyComponent.jsx`). File names match component names.
    * Hook Naming: camelCase, prefixed with `use` (`useMarketData.js`).
* **Don't**:
    * No class components.
    * No factories, managers, context providers unless *strictly necessary* and justified (prefer Redux for global, prop drilling for local, or dedicated state libs like Zustand/Jotai for feature-level complex state).
    * No abstraction layers like `ChartManager`, `IndicatorService` (meaning, don't create overly complex classes or objects that hide simple React/JS logic. API service functions are fine).
    * No demo logic or mock data in final components. Use placeholder data *only* during early development if backend is not ready, and clearly mark it.
    * No generic component overengineering.
* **Error Handling in UI**:
    * API call functions (in `services/`) should handle catching errors.
    * Display user-friendly errors using the `NotificationSystem`.
    * Components should handle loading states gracefully (see below). Don't let errors break the entire page; contain them.
* **Loading States in UI**:
    * For data fetching:
        * Buttons that trigger API calls should show a loading spinner or disabled state.
        * Areas where data will appear (charts, lists) should show skeleton loaders or a simple "Loading..." message.
        * Example: `isLoadingSymbols` prop for `SymbolTimeframeSelector`.
* **API Prefix**: All API calls must be prefixed with `/api/v1/`.

---
