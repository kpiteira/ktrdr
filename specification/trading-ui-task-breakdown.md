# Trading UI Development - Vertical Slice Approach

## Vertical Slice Philosophy
Each slice delivers a **working, testable feature** that provides value. You can see it working, test it, and give feedback before moving to the next slice.

## Slice 1: "Hello Trading Data" (Day 1)
**Goal**: Load and display basic candlestick chart for one hardcoded symbol

### Deliverable
A working React app that shows EURUSD candlestick data in a TradingView chart.

### Tasks:
- [ ] Project setup (React + TypeScript + TradingView Charts)
- [ ] Basic logging system
- [ ] Simple API client for `/api/v1/data/load`
- [ ] Hardcoded data loading (EURUSD, 1d, last 100 days)
- [ ] Basic candlestick chart display
- [ ] Error handling with console logs

### Success Criteria:
- ✅ Navigate to localhost:3000
- ✅ See EURUSD candlestick chart with real data
- ✅ Can pan/zoom the chart
- ✅ Console shows meaningful logs
- ✅ Graceful error if backend is down

---

## Slice 2: "Symbol Selection" (Day 2)
**Goal**: User can pick any symbol and see its chart

### Deliverable
Add a dropdown to select different symbols, chart updates when changed.

### Tasks:
- [ ] Fetch available symbols from API
- [ ] Create symbol selector dropdown
- [ ] Update chart when symbol changes
- [ ] Add loading state during data fetch
- [ ] Handle "no data available" cases

### Success Criteria:
- ✅ Dropdown shows available symbols (AAPL, EURUSD, etc.)
- ✅ Selecting different symbol updates the chart
- ✅ Loading spinner appears during data fetch
- ✅ Error message if symbol has no data

---

## Slice 3: "First Indicator" (Day 3)
**Goal**: Add one indicator (SMA) to the price chart

### Deliverable
Button to add SMA(20) overlay on the price chart.

### Tasks:
- [ ] Fetch available indicators from API
- [ ] Add "Add SMA" button
- [ ] Calculate SMA using current chart data
- [ ] Display SMA line overlay on price chart
- [ ] Handle calculation errors

### Success Criteria:
- ✅ "Add SMA" button appears
- ✅ Clicking adds SMA(20) line to chart
- ✅ SMA line follows price movements
- ✅ Works with different symbols
- ✅ Error handling if calculation fails

---

## Slice 4: "Indicator Management" (Day 4)
**Goal**: Manage multiple indicators with basic controls

### Deliverable
Sidebar showing active indicators with remove/hide functionality.

### Tasks:
- [ ] Create right sidebar layout
- [ ] List active indicators
- [ ] Add remove indicator functionality
- [ ] Add show/hide toggle
- [ ] Support multiple indicators simultaneously

### Success Criteria:
- ✅ Sidebar shows "SMA 20" when added
- ✅ Can remove indicators from sidebar
- ✅ Can hide/show indicators
- ✅ Multiple indicators work together
- ✅ Indicator state persists during symbol changes

---

## Slice 5: "Second Chart Type" (Day 5)
**Goal**: Add oscillator indicator in separate panel

### Deliverable
RSI indicator in its own chart panel below the main chart.

### Tasks:
- [ ] Create separate chart component for oscillators
- [ ] Add "Add RSI" functionality
- [ ] Display RSI in dedicated panel below price chart
- [ ] Implement time-axis synchronization
- [ ] Add chart resizing/layout management

### Success Criteria:
- ✅ Can add RSI indicator
- ✅ RSI appears in separate panel below price chart
- ✅ Both charts scroll/zoom together (time sync)
- ✅ RSI values look correct (0-100 range)
- ✅ Layout adjusts properly with multiple panels

---

## Slice 6: "Parameter Control" (Day 6)
**Goal**: Change indicator parameters and see results

### Deliverable
Simple way to edit indicator parameters (like SMA period).

### Tasks:
- [ ] Add parameter editing to sidebar
- [ ] Re-calculate indicators when parameters change
- [ ] Add input validation
- [ ] Handle recalculation loading states

### Success Criteria:
- ✅ Can change SMA period from 20 to 50
- ✅ Chart updates to show SMA(50)
- ✅ Can change RSI period from 14 to 21
- ✅ Invalid parameters show error messages
- ✅ Loading state during recalculation

---

## Slice 7: "Full Sidebar Layout" (Day 7)
**Goal**: Complete sidebar layout with collapsible panels

### Deliverable
Professional sidebar layout with mode selection and collapsible functionality.

### Tasks:
- [ ] Add left sidebar with mode selection
- [ ] Implement hamburger menu collapse
- [ ] Polish right sidebar styling
- [ ] Add timeframe selection
- [ ] Improve overall layout and spacing

### Success Criteria:
- ✅ Left sidebar shows Research/Train/Run modes
- ✅ Sidebars collapse/expand with hamburger buttons
- ✅ Can change timeframes (1h, 1d, etc.)
- ✅ Layout looks professional and responsive
- ✅ All functionality still works after layout changes

---

## Slice 8: "Error & Loading Polish" (Day 8)
**Goal**: Professional error handling and loading states

### Deliverable
Smooth user experience with proper feedback for all operations.

### Tasks:
- [ ] Add toast notifications for errors
- [ ] Improve loading states throughout app
- [ ] Add empty states for no data
- [ ] Polish error messages
- [ ] Add keyboard shortcuts

### Success Criteria:
- ✅ Network errors show toast notifications
- ✅ All operations have clear loading states
- ✅ Empty states guide user to take action
- ✅ Error messages are helpful, not technical
- ✅ Common keyboard shortcuts work

---

## Benefits of This Approach

### For Development:
- **Immediate feedback** - See working features quickly
- **Risk reduction** - Problems caught early
- **Motivation** - Always have something working
- **Flexibility** - Can adjust priorities based on learnings

### For Testing:
- **Real user testing** - Can use the app at each stage
- **Progressive complexity** - Each slice builds on proven foundation
- **Clear success criteria** - Easy to verify each slice works

### For Claude Code:
- **Focused context** - Each slice has clear, bounded scope
- **Incremental builds** - Less chance of breaking existing functionality
- **Clear handoffs** - Each slice is complete before moving on

## Slice Dependencies

```
Slice 1 (Basic Chart) 
    ↓
Slice 2 (Symbol Selection)
    ↓
Slice 3 (First Indicator) ← Core functionality
    ↓
Slice 4 (Indicator Management)
    ↓
Slice 5 (Second Chart) ← Major feature
    ↓
Slice 6 (Parameters) ← User control
    ↓
Slice 7 (Layout Polish) ← UX improvement
    ↓
Slice 8 (Error Polish) ← Professional finish
```

## Success Metrics Per Slice

Each slice should result in:
- **Working demo** you can show someone
- **All previous functionality** still works
- **Clear value add** over previous slice
- **Specific user workflow** can be tested
- **Foundation** for next slice

## Risk Mitigation

### If a slice takes too long:
- **Reduce scope** - Cut non-essential parts
- **Split slice** - Break into smaller pieces
- **Skip and return** - Move to next slice, come back later

### If integration issues arise:
- **Previous slice still works** - Always have fallback
- **Clear isolation** - Easy to identify problem area
- **Incremental debugging** - Smaller surface area

Would you like me to start with Slice 1, or would you prefer to modify any of these slices first?