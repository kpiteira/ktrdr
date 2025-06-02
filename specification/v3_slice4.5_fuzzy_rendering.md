# 🧩 Slice Execution Spec: Fuzzy Overlay Rendering (Slice 4.5) - UPDATED

## 🎯 Goal

Render fuzzy membership overlays per indicator on the appropriate charts in the frontend. Fuzzy overlays are loaded when indicators are added and visibility is user-controllable as an indicator parameter toggle. Use shading, gradients, or visual bands to represent fuzzy set activation levels per timestamp. This slice assumes fuzzy data is available via the backend API from Slice 4.

---

## 🧩 Background

Fuzzy data includes set-wise activation levels (0.0–1.0) per indicator per timestamp. These should be visualized as transparent overlays on existing indicator charts (e.g. shaded bands behind RSI). Slice 4 introduced the backend API; this slice implements the frontend rendering logic using our **React hooks + Context architecture**.

---

## 📦 Inputs

| Source           | Data                                             |
| ---------------- | ------------------------------------------------ |
| Backend API      | `/api/v1/fuzzy/data` endpoint from Slice 4      |
| Indicator State  | Current chart panel and indicator being rendered |
| Theme Config     | Optional color map per fuzzy set (light/dark)   |
| Local Component  | React useState for fuzzy visibility toggles     |

---

## 🔁 Logic & Flow

### 🔄 Architecture-Aligned Behavior

* Fuzzy data is fetched **when an indicator is added** using custom hooks
* Overlay visibility is controlled by local React state in each indicator component
* No Redux store - uses **React useState + Context** for state management
* Indicator components manage their own fuzzy state independently

1. **Determine Target Chart Panel**

   * Overlay should match indicator panel (e.g., RSI → OscillatorChart panel)
   * Use `chartRef` and component props to locate chart instance
   * Follow existing Container/Presentation pattern

2. **Fetch Fuzzy Data with Custom Hook**

   * Use `useFuzzyOverlay(indicatorId, symbol, timeframe)` custom hook
   * Hook fetches data from `/api/v1/fuzzy/data` endpoint
   * Returns: `{ fuzzyData, isLoading, error, toggleVisibility }`
   * Manages local state without Redux complexity

3. **Process Fuzzy Overlay Data**

   * Loop over sets: `low`, `neutral`, `high`, etc.
   * For each set:
     * Create TradingView `AreaSeries` with transparent fill
     * Use timestamp as X and membership value (0.0–1.0) as Y
     * Apply proper z-index ordering (behind indicator line)

4. **Rendering Strategy**

   * **Primary**: TradingView Lightweight Charts AreaSeries (v5 API)
   * Use native chart features for smooth performance
   * Conditional rendering based on `fuzzyVisible` local state
   * Color schemes via utility functions (no global themes)

5. **Sync Behavior**

   * Time-synced with price + indicator series automatically
   * Uses existing chart synchronization infrastructure
   * Crosshair interactions work seamlessly with overlays

---

## 🧪 Tests (Definition of Done)

| Test                | Condition                                           |
| ------------------- | --------------------------------------------------- |
| Overlay alignment   | Fuzzy overlay matches correct chart and time axis   |
| Visual smoothness   | Transparent areas render smoothly, no flicker       |
| Toggle visibility   | User can toggle on/off fuzzy overlays per indicator |
| Performance on load | Acceptable FPS with 3+ overlays active              |

---

## 🛡 Affected Modules

**Following Container/Presentation + React Hooks Architecture:**

| Module                                              | Description                                      |
| --------------------------------------------------- | ------------------------------------------------ |
| `store/indicatorRegistry.ts`                       | Extend `IndicatorInfo` with fuzzy properties    |
| `containers/OscillatorChartContainer.tsx`          | Add fuzzy data fetching to oscillator container |
| `presentation/charts/OscillatorChart.tsx`          | Render fuzzy overlays on RSI/MACD charts        |
| `presentation/charts/FuzzyOverlay.tsx`             | Create reusable FuzzyOverlay component           |
| `hooks/useFuzzyOverlay.ts`                         | Custom hook for fuzzy data + visibility         |
| `presentation/sidebar/IndicatorItem.tsx`           | Add fuzzy toggle to existing indicator controls |
| `utils/fuzzyColors.ts`                             | Color scheme utilities (no global state)        |
| `api/endpoints/fuzzy.ts`                           | Frontend API client (already exists)            |
| `api/types/fuzzy.ts`                               | TypeScript interfaces (already exists)          |

**Key Architecture Differences:**
- **No Redux store changes** - uses existing `useIndicatorManager` pattern
- **Container components** handle fuzzy data fetching via hooks
- **Presentation components** receive fuzzy data as props
- **Local state management** using React useState in containers
- **Follows existing patterns** established in the codebase

---

## 🎨 Rendering Considerations

* Use color palettes mapped to sets (e.g. low = blue, high = red)
* Use opacity (alpha) proportional to membership strength
* Use smooth interpolation if data is sparse
* Avoid clutter: max 3 visible sets per chart

---

## 🔄 Follow-up Slice Ideas

* Chart legends + tooltips for fuzzy membership levels
* Export fuzzy overlays to file or analysis tool
* Animate overlay transitions when switching symbols