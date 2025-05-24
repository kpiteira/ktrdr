# 🧭 KTRDR Frontend UI – Overall Spec (Research, Runtime, NN Modes)

This document describes the **overall user interface structure** for the KTRDR trading research platform. It includes high-level layout concepts, mode switching architecture, shared UI elements, and interaction design patterns for the three primary application modes.

---

## 🔧 App Architecture Overview

* **Layout**: Horizontal split: left sidebar (mode switcher), top bar (contextual title), main area, optional right panel (mode options)
* **Routing**: Each mode is a route (`/research`, `/train`, `/run`) with its own internal pages or tabs
* **State**:

  * Global state (theme, sidebar open/closed) via Redux (already set up)
  * Mode-specific state handled locally or via feature folders

---

## 🗂️ UI Zones

```
+----------------------------------------------------------+
| Top Bar – shows current mode title (e.g., "Research")     |
+----+--------------------------------------------+--------+
| SB |                                            | Right  |
| ID |  Main Content for Mode                    | Panel  |
| E  |  (Chart, Strategy Builder, etc.)          |        |
| B  |                                            |        |
+----+--------------------------------------------+--------+
```

### 🟪 Sidebar (Left)

* Permanent vertical menu for mode selection:

  * Research
  * Train
  * Run
* Collapsible (with a hamburger button) to show only icons

### 🟥 Top Bar

* Displays active mode title
* Optional breadcrumbs or tabs within the mode

### 🟨 Main Content

* Controlled by active mode
* Flexible layout — often chart-driven in Research or Run

### 🟦 Right Panel (Mode Options)

* Per-mode control panel (e.g., select symbol, add indicator)
* Collapsible via hamburger icon (mirroring sidebar behavior)

---

## 🧪 Modes Overview

### 1. 🔬 Research Mode (Priority)

> Design, backtest, and refine strategies composed of indicators, fuzzy logic, and neural networks.

* Symbol/timeframe selector
* Candlestick chart + indicators
* Indicator panel controls (see: `Indicator UI Spec`)
* Fuzzy activation overlays (if present)
* Vertical resizable sub-panels
* Backtest UI (to be defined later).&#x20;

### 2. 🧠 Train Neural Network.  (later Observation Mode)

> Visualize training dynamics, feature attribution, and weight evolution.

* Leave this as a blank screen for now. Will include:

  * Strategy designer and training trigger.
  * Reserve layout space for future widgets (charts, heatmaps)

### 3. 🚀 Runtime Mode (Secondary, will be defined later)

> Monitor deployed strategies, issue emergency stops, observe triggers.

* Global stop button + strategy list
* For each strategy:

  * Symbol view + indicator setup
  * Last triggered event & reason
  * Real-time fuzzy chart & history

---

## 🔁 Shared Behaviors

* Left sidebar and right panel both collapsible
* Chart layout must support multiple stacked panels (vertically resizable)
* Modal system already in use — reuse for indicator settings or strategy details
* Symbol selector should be prominent and persistent

---

## 🛠️ LLM Implementation Guidelines (Apply Across All Modes)

### ✅ Do:

* Use functional components with hooks
* Use TailwindCSS for styling
* Co-locate features under `features/<mode>/` or `features/shared/`
* Keep cross-cutting utilities minimal (1-2 reusable hooks, shared context if truly global)

### ❌ Don’t:

* No factories, managers, context providers unless strictly necessary
* No abstraction layers like `ChartManager`, `IndicatorService`, etc.
* No demo logic or mock data – use real backend only
* No generic component overengineering

---

## 📦 Next Steps

* Focus first on completing **Research Mode → Chart + Indicator View**
* Implement symbol selector, chart, indicator list + modal as isolated vertical slice
* When this works well, expand into strategy creation and training control

(Refer to `Indicator UI Spec` for detailed logic inside chart + indicator stack.)
