# ✅ Post–Task 0 TODO (Pre–Task 1.1 Cleanup)

## 📁 Folder & File Structure

### 🔲 1. Resolve `App.tsx` Duplication
- [x] Remove either `src/App.tsx` or `src/app/App.ts` to eliminate ambiguity. To do so, analyse the 2 and understand which one has the most up to date implementation and check where either are imported in the rest of the frontend codebase.
- [x] Confirm `Router.tsx` uses the remaining one.

### 🔲 2. Move Chart Components to Feature Folder
- [x] Create `src/features/charting/`
- [x] Move files from `src/components/charts/` to `src/features/charting/components/` or just `src/features/charting/` if flat.
- [x] Update all imports accordingly.

### 🔲 3. Delete `components/charts/index.ts`
- [x] This file is unused and introduces accidental coupling.
- [x] Safely delete it and validate imports remain clean.

## 🧩 Component Renaming (Clarity & Consistency)

### 🔲 4. Rename Verbose Chart Component
- [x] Rename `CandlestickTradingView.tsx` to `CandlestickChart.tsx`
- [ ] (Optional) Re-export it from `ChartPanel.tsx` or `index.tsx` inside `features/charting/` if needed for external use

### 🔲 5. Rename `ChartContainer.tsx`
- [x] Rename to `ChartPanel.tsx` if it's used for layout/coordination
- [ ] Or collapse its logic into `CandlestickChart.tsx` if it has minimal value

## 🧪 Testing Structure

### 🔲 6. Move `uiSlice.test.ts` into Central Test Folder
- [x] Move `src/app/store/uiSlice.test.ts` → `src/tests/store/uiSlice.test.ts`
- [x] Create the `store/` subfolder under `tests/` if needed

### 🔲 7. Add Minimal Tests to Key Components
- [ ] `tests/app/Sidebar.test.tsx`
- [ ] `tests/app/Layout.test.tsx`
- [ ] `tests/features/charting/CandlestickChart.test.tsx`

## 🧠 Code Clarity

### 🔲 8. Rename `useUI.ts` → `useUIStore.ts`
- [x] Clarifies that it's Redux-powered, not a custom context.
- [x] Update the import wherever used.

## 📡 API & Utility Cleanup

### 🔲 9. Relocate `api/utils/dataTransformations.ts`
- [x] Move to: `features/transformation/utils/dataTransformations.ts`
- [x] Update imports to match.

### 🔲 10. Split Overloaded API Types File
- [x] Review `api/types.ts`
- [x] If it contains symbol-specific, indicator-specific, or transformation-specific types, move them into the relevant `features/<domain>/types.ts`.

## 🧭 Sidebar Navigation Prep

### 🔲 11. Introduce a Central Route Definition (Optional Prep for 1.1)
- [ ] Create `src/app/routes.ts`:
```ts
export const routes = [
  { path: "/symbols", label: "Symbols", element: <SymbolListPage /> },
  ...
];
```
- [ ] Use this in both `Router.tsx` and `Sidebar.tsx` to keep things DRY.

## 🧹 Bonus: Remove Unused Files

### 🔲 12. Check and Remove These
- [ ] `src/components/charts/index.ts` (already covered, but re-listing for safety)
- [ ] Any leftover `example/`, `demo/`, `mockData.ts` etc. (confirm all were removed during Task 0)
