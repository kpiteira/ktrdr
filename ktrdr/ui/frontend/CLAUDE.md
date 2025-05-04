# KTRDR Frontend Development Notes

## Environment Setup

- Use Docker for development: `./docker_dev.sh` from the root directory
- Commands should be run inside the Docker container, not on the host machine

## Library Versions

- **TradingView Lightweight Charts**: v4.1.1
  - Working examples are found in the WorkingChart.tsx component

## Common Tasks

- **Starting Development Server**:
  ```bash
  ./docker_dev.sh
  # Inside the container
  npm run dev
  ```

- **Building for Production**:
  ```bash
  ./docker_dev.sh
  # Inside the container
  npm run build
  ```

- **Running Tests**:
  ```bash
  ./docker_dev.sh
  # Inside the container
  npm run test
  ```

## Lightweight Charts v4.1.1 Usage

### Important: Library Loading and Global Object

The project uses Lightweight Charts v4.1.1 loaded from a CDN rather than through ES modules. Any chart component should:

1. Include the script tag to load the library or check that it's loaded:
   ```html
   <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
   ```

2. Access the library through the global `window.LightweightCharts` object:
   ```typescript
   // Add type declaration for TypeScript
   declare global {
     interface Window {
       LightweightCharts: any;
     }
   }
   
   // Use the global object
   const chart = window.LightweightCharts.createChart(container, options);
   ```

3. Don't import from the module directly:
   ```typescript
   // ❌ Don't do this - it will cause errors
   import { createChart } from 'lightweight-charts';
   ```

### API Method Reference

The correct API methods for v4.1.1 are:

- `chart.addCandlestickSeries(options)` - For creating candlestick charts
- `chart.addHistogramSeries(options)` - For creating histogram/volume charts
- `chart.addLineSeries(options)` - For creating line charts

Example usage:

```typescript
// Create chart
const chart = window.LightweightCharts.createChart(container, {
  width: 800,
  height: 400,
  // other options...
});

// Add a candlestick series
const candlestickSeries = chart.addCandlestickSeries({
  upColor: '#26a69a',
  downColor: '#ef5350',
  wickUpColor: '#26a69a',
  wickDownColor: '#ef5350',
  borderVisible: false,
});

// Add volume series
const volumeSeries = chart.addHistogramSeries({
  color: '#26a69a',
  priceFormat: { type: 'volume' },
  priceScaleId: 'volume',
  scaleMargins: { top: 0.8, bottom: 0 },
});

// Set data
candlestickSeries.setData(candleData);
volumeSeries.setData(volumeData);

// Configure scales
chart.priceScale('volume').applyOptions({
  scaleMargins: { top: 0.8, bottom: 0 },
  borderVisible: false,
});

// Fit chart to content
chart.timeScale().fitContent();
```

### Lessons Learned

1. **ES Modules vs. Global CDN**: When using Lightweight Charts, check how it's loaded in the project first. Our project uses the global CDN version rather than the ES module version.

2. **API Version Differences**: Be careful with API references from the web - v5.x (and possibly v3.x) have different APIs than v4.1.1.

3. **Chart Lifecycle**: Always handle chart cleanup properly in the component's unmount/cleanup function.

4. **Error Handling**: Use proper try/catch blocks around chart operations, as they can throw errors that might crash the app.

5. **Reference Components**: When making new chart components, start by examining the working examples in the codebase like `WorkingChart.tsx`.

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

### Working Examples

- `/ktrdr/ui/frontend/src/components/charts/WorkingChart.tsx` - Basic chart example
- `/ktrdr/ui/frontend/src/components/charts/DataTransformationExample.tsx` - More complex chart with data transformation

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