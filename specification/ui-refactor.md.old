# 📐 KTRDR Frontend Refactor & Vertical Slice Implementation Plan

## 🧠 Architectural Context

This project is the frontend for **KTRDR**, a trading strategy research platform. It is built using:

- **React + TypeScript**
- **TailwindCSS**
- **Redux Toolkit (RTK)** for state management
- **Vite** for the build system
- An existing backend API that exposes endpoints for:
  - Symbols (`/api/v1/symbols`)
  - Indicator values
  - OHLCV market data
  - Strategy definitions
  - Transformed data outputs

Previously, the frontend relied on **self-contained example files** that used fake data generators and redundant logic. This led to:

- Confusing abstractions and demo-specific complexity
- Artificial examples instead of real user-facing features
- Task slicing that focused on showcasing functionality, not delivering actual value

## ✅ Refactoring Goals

1. **Eliminate example/demo components** and fake data generation
2. **Use the real API** for everything, even in test pages
3. **Switch from tab navigation to sidebar routing**
4. **Simplify abstractions** and move toward feature-based structure
5. **Refactor tasks into vertical product slices**: each task delivers a working, user-facing feature

---

## 📁 Folder Structure Guidelines

Refactor the codebase toward the following top-level structure:

```
src/
├── api/ ← central API clients
├── app/ ← layout, routing, theme
├── components/ ← generic UI primitives (Card, Button, Tabs, etc.)
├── features/
│ ├── symbols/ ← symbol list + symbol chart
│ ├── charting/ ← chart panel, indicator overlays
│ ├── transformation/ ← before/after data views
│ └── strategies/ ← strategy UI
├── hooks/ ← shared React hooks
├── pages/ ← routing targets
└── index.tsx ← app entry point
```

---

## 🔄 Phase 1: Core Refactor (Before Feature Work)

### ✅ Task 1.0 – Core Refactor & Cleanup

**Objective:** Remove all artificial examples and set the baseline architecture for future vertical slices.

**Instructions:**
- ❌ Delete:
  - `utils/indicators/calculations.ts`
- 🧹 Move reusable components (like `CandlestickChart`, `IndicatorPanel`) into `/features/charting/`
- 🧪 Move anything demo-related into `/demo/legacy/`
    - this includes `ChartExampleWithData`, `DataTransformationPage`, and their mock data generation
- 🧭 Remove tab navigation from `App.tsx`
- ✅ Configure router + sidebar nav
  - Sidebar should show pages like:
    - "Symbols"
    - "Chart"
    - "Data Transform"
    - "Strategies"
- 🧩 Create placeholder routes + pages for each

---

## 🚀 Phase 2: Feature Slices (Vertical Product Increments)

Each task below is a self-contained, user-facing slice.

---

### ✅ Task 1.1 – App Shell

**Goal:** Create the layout scaffold with working sidebar navigation.

**Includes:**
- Header
- Sidebar (left navigation)
- Routing between pages (use React Router)
- Basic theme (light/dark)

📁 Files to create/edit:
- `src/app/Layout.tsx`
- `src/app/Router.tsx`
- `src/pages/EmptyPage.tsx` (temp placeholder for routes)

---

### ✅ Task 1.2 – Symbol List Page

**Goal:** Display all symbols fetched from the backend.

**API:** `GET /api/v1/symbols`

**Includes:**
- Fetch and display a list of available symbols
- Allow searching/filtering
- Clicking a symbol navigates to `/charts/:symbol`

📁 Files to create:
- `features/symbols/SymbolList.tsx`
- `api/symbols.ts`
- `pages/SymbolListPage.tsx`

---

### ✅ Task 1.3 – Symbol Chart View

**Goal:** Show OHLCV chart for a selected symbol

**API:**  
- `GET /api/v1/symbols/:symbol/ohlcv`

**Includes:**
- Candlestick chart with volume
- Use `<CandlestickChart />` from `/features/charting/`
- Basic UI: chart, metadata, symbol name

📁 Files to create:
- `features/charting/ChartPanel.tsx`
- `api/ohlcv.ts`
- `pages/ChartPage.tsx`

---

### ✅ Task 1.4 – Add Indicators to Chart

**Goal:** Overlay indicator data fetched from backend

**API:**  
- `GET /api/v1/indicators?symbol=XYZ&type=sma`

**Includes:**
- Let user toggle SMA, RSI, BBands
- Fetch and display indicator overlays
- No client-side indicator calculations

📁 Files to create/edit:
- `features/charting/IndicatorOverlay.tsx`
- `api/indicators.ts`
- `features/charting/hooks/useIndicatorData.ts`

---

### ✅ Task 1.5 – Data Transformation View

**Goal:** Show raw + transformed data for a symbol

**API:**  
- `GET /api/v1/symbols/:symbol/transform?type=normalize`

**Includes:**
- Side-by-side chart comparison (before/after)
- Toggle transformation type (normalize, log, etc.)
- Optional: download data

📁 Files:
- `features/transformation/TransformationPanel.tsx`
- `api/transform.ts`
- `pages/TransformationPage.tsx`

---

### ✅ Task 1.6 – Strategies Dashboard

**Goal:** Display available strategies and their properties

**API:**  
- `GET /api/v1/strategies`

**Includes:**
- List of strategies with name, symbol, type, performance
- Button to view details
- Optional: edit strategy later

📁 Files:
- `features/strategies/StrategyList.tsx`
- `api/strategies.ts`
- `pages/StrategiesPage.tsx`

---

## ✅ Summary

You should now:
- Have a cleaned, simplified codebase
- Fully API-driven functionality
- A modular structure based on real product goals
- True vertical slices for incremental delivery

Each of these tasks can be handed to an LLM or engineer independently, and they build toward the final user-facing application — **no fake examples, no throwaway UI**.

