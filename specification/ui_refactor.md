# 🚀 KTRDR Frontend Task Plan (Post-Refactor)

This task plan is optimized for AI-assisted implementation using LLMs. It reflects the cleaned architecture from Task 0 and includes detailed, self-contained instructions per task to minimize human intervention.

---

## 🧠 Architectural Overview

* **Framework**: React + TypeScript + TailwindCSS + Redux Toolkit
* **Routing**: React Router (defined in `src/app/routes.tsx`)
* **Layout**: Provided via `MainLayout`, `Header`, `Sidebar` in `src/app/`
* **API Access**: All data must be fetched via real API endpoints using the working method from `DataSelection` (see `api/hooks/useData.ts`, etc.)
* **State Management**: Redux is used, but only for UI/global layout state (in `uiSlice.ts`). Feature-specific state should be local or via hooks.

**Folder Structure**:

```txt
src/
├── api/                    ← central API clients
├── app/                    ← layout, routing, theme
├── components/             ← generic UI primitives (Card, Button, Tabs, etc.)
├── features/
│   ├── symbols/            ← symbol list + symbol chart
│   ├── charting/           ← chart panel, indicator overlays
│   ├── transformation/     ← before/after data views
│   └── strategies/         ← strategy UI
├── hooks/                  ← shared React hooks
├── pages/                  ← routing targets
└── index.tsx               ← app entry point
```

**🚫 Do not use:** mock data, demo-only pages, factories, or extra abstractions unless required.

---

## 🔧 Task 1.3.1 – Charting Folder Cleanup (Required Before Continuing)

**Goal:** Clean up and consolidate the `features/charting/` folder to remove legacy components, enforce structure, and prevent LLM confusion.

### Instructions:

This task must be completed **before** Task 1.3 continues. It resolves duplicated files, restructures the folder, and aligns everything with the vertical slicing pattern.

* ✅ Identify and **keep only one** `CandlestickChart.tsx` (whichever is canonical and used by `ChartPage.tsx`)
* ✅ Remove `CandlestickTradingView.tsx`, both at root and under `components/` if present
* ✅ Remove either `ChartContainer.tsx` (root) or `components/ChartContainer.tsx` — pick one
* ✅ Move `ChartPanel.tsx` from `components/` to the root if it is the main coordinator of the chart view
* ✅ Delete `components/index.ts` if it’s unused
* ✅ Move files from `components/transformers/` into `core/` or `utils/` folder if they are non-visual helpers

### Resulting Folder Structure:

```txt
features/charting/
├── ChartPage.tsx
├── ChartPanel.tsx
├── CandlestickChart.tsx
├── ChartControls/
├── ChartLegend/
├── CrosshairInfo/
├── components/
│   └── indicators/
├── core/ or utils/
│   └── indicatorAdapters.ts
├── hooks/
├── store/
├── types.ts
```

### Tests:

* Run all existing charting tests to validate the updated folder
* Refactor any imports in `ChartPage.tsx` or other chart features to point to the retained files

---

## ✅ Task 1.1 – App Shell & Navigation (Extend Existing)

**Goal:** Establish the base layout and routing shell for the real app.

### Instructions:

This task builds on the **existing app shell and navigation**, not from scratch.

* **Do not recreate** `MainLayout`, `Sidebar`, or `Router` from scratch
* Review `MainLayout.tsx` and `Sidebar.tsx` to ensure they are correctly consuming and rendering entries from the new `routes.tsx`
* Add a default route (e.g. `/home`) to connect to `HomePage`
* Make sure the `Sidebar` dynamically renders nav items from `routes.tsx`
* Add missing test coverage for layout or sidebar behavior if not already present

### Files to Create/Edit:

* `src/app/routes.tsx`: declare and export route structure
* `src/app/Router.tsx`: implement routing logic from routes
* `src/app/Sidebar.tsx`: render menu items from `routes.tsx`
* `src/features/home/HomePage.tsx`: basic landing page

### Tests:

* `tests/app/Layout.test.tsx`
* `tests/app/Sidebar.test.tsx`

---

## ✅ Task 1.2 – Symbol List Page (Add on Top of Current Shell)

**Goal:** Display all tradable symbols from the backend.

### Instructions:

This task **extends the existing app** by adding the first real user-facing feature using the real backend API (no mock data).

* Do not modify or duplicate layout logic; use the current layout and routing foundation
* Add a new route to `routes.tsx` for `/symbols`
* Implement a page at `SymbolListPage.tsx` under `features/symbols/`
* Fetch symbols using `useData()` or create a scoped `useSymbols()` hook if reuse is expected
* Display symbols in a simple table or list with optional filtering
* On click, navigate to `/charts/:symbol`

### Files:

* `features/symbols/SymbolListPage.tsx`
* `api/endpoints/symbols.ts` (if needed)
* `features/symbols/hooks/useSymbols.ts`
* `features/symbols/types.ts` (if not already in `api/types.ts`)

### Tests:

* `tests/features/symbols/SymbolListPage.test.tsx`

---

## ✅ Task 1.3 – Symbol Chart View (Integrate into Main Flow)

**Goal:** Render OHLCV chart using TradingView for a selected symbol.

### Instructions:

This task integrates the chart view into the main app.

* ⚠️ If a Redux-based implementation for OHLCV data already exists and is working, prefer using it.

* Only build a new `useOhlcvData()` hook if the feature does not already exist or if the Redux version is insufficiently scoped.

* Reuse the layout, navigation, and sidebar from the existing shell

* Add a new route `/charts/:symbol` in `routes.tsx`

* Extract `:symbol` from the route params

* Use `ChartPanel` or `CandlestickChart` in `features/charting/`

* Fetch real OHLCV data from `/api/v1/symbols/:symbol/ohlcv`

* Ensure correct loading state and error handling

### Files:

* `features/charting/ChartPage.tsx`
* `features/charting/hooks/useOhlcvData.ts`
* `api/endpoints/ohlcv.ts` (if needed)

### Tests:

* `tests/features/charting/ChartPage.test.tsx`
* Add test for hook if logic is complex

---

## ✅ Task 1.4 – Add Indicator Overlays

**Goal:** Overlay one or more indicators (SMA, RSI, etc.) on top of the candlestick chart.

### Instructions:

This task adds real-time indicator overlays to the chart using real backend API data (no frontend calculations).

* ⚠️ If indicator state or logic is already managed via Redux and is functional, prefer reusing it.

* Only build new hooks if necessary or clearly scoped for reuse.

* Fetch indicator data from the backend (`/api/v1/indicators?...`) using real backend API data (no frontend calculations).

* Fetch indicator data from the backend (`/api/v1/indicators?...`) (`/api/v1/indicators?...`)

* Display toggle/select UI to control visible indicators

* Do **not** calculate indicators in the frontend

### Files:

* `features/charting/components/IndicatorOverlay.tsx`
* `features/charting/hooks/useIndicators.ts`

### Tests:

* `tests/features/charting/IndicatorOverlay.test.tsx`
* Add test coverage for indicator hook

---

## ✅ Task 1.5 – Data Transformation View

**Goal:** Visualize raw vs transformed OHLCV data for a symbol.

### Instructions:

This task fetches and visualizes raw and transformed OHLCV data from the real backend API (no mock logic).

* ⚠️ If a Redux implementation already manages transformed data successfully, reuse it.

* Use a hook-based approach only if the Redux version is absent or not sufficiently scoped.

* Fetch original + transformed data from the backend from the real backend API (no mock logic).

* Fetch original + transformed data from the backend

* Show them side by side with an explanation

* Allow the user to toggle transformation type (e.g., normalize, log)

### Files:

* `features/transformation/TransformationPage.tsx`
* `features/transformation/hooks/useTransformedData.ts`
* `features/transformation/utils/explainTransform.ts`

### Tests:

* `tests/features/transformation/TransformationPage.test.tsx`

---

## ✅ Task 1.6 – Strategy Dashboard

**Goal:** Display a list of existing trading strategies and their metadata.

### Instructions:

This task integrates strategy data by consuming the backend API.

* ⚠️ If Redux is already managing strategy state effectively, prefer using the existing slice.

* Do not reimplement existing logic as a hook unless there's a clear justification..

* Fetch from `/api/v1/strategies`

* Display strategy name, type, attached symbol, performance (if available)

* Add a detail button (placeholder for now)

### Files:

* `features/strategies/StrategyListPage.tsx`
* `api/endpoints/strategies.ts`
* `features/strategies/hooks/useStrategies.ts`

### Tests:

* `tests/features/strategies/StrategyListPage.test.tsx`

---

## 🧼 After Each Task

* Always confirm components are routed via `routes.tsx`
* If Redux state is required, add slice under `features/<domain>/store/`
* Always clean up any unused test stubs or imports
* Use `tests/` to colocate test logic by feature/app scope

---

## 📌 Notes for LLM Agents

* Always use real API clients and fetch hooks — no demo logic
* Use Tailwind classes for styling unless instructed otherwise
* Never create factory patterns, abstraction layers, or mock data generators
* Each component or hook must live in the corresponding `features/<domain>/` folder unless shared across the app
