# CRITICAL: Chart Jumping Bug Fix Documentation

## ⚠️ DO NOT REMOVE - CRITICAL BUG FIX ⚠️

### Overview
This document protects a critical fix for chart jumping bug in TradingView Lightweight Charts v5.

### Issue Description
- **Problem**: Adding indicators to synchronized charts causes unwanted forward jumps in time
- **Root Cause**: TradingView's auto-scaling conflicts with chart synchronization (`preserveTimeScale=true`)
- **Impact**: Breaks user experience, makes charts jump to future dates unexpectedly
- **Frequency**: Occurs consistently when adding first overlay indicator to synchronized charts

### Fix Location
**File**: `ktrdr/ui/frontend/src/components/presentation/charts/BasicChart.tsx`  
**Lines**: 288-341  
**Section**: Marked with "CRITICAL FIX" comment blocks

### Fix Implementation
```typescript
// Preventive visibility toggle when first overlay indicator added
if (indicatorCountChanged && preserveTimeScale && chartRef.current) {
  const isFirstOverlayIndicator = chartData.indicators.length === 1 && existingIndicatorCount === 0;
  
  if (isFirstOverlayIndicator) {
    setTimeout(() => {
      // Hide indicator briefly
      eyeButtons[0].click();
      setTimeout(() => {
        // Show indicator again - forces TradingView to recalculate range
        eyeButtons[0].click();
      }, 1); // 1ms - tested minimum effective delay
    }, 1); // 1ms - tested minimum effective delay
  }
}
```

### Critical Requirements
- **Timing**: 1ms delays are precisely calibrated - DO NOT MODIFY
- **Trigger**: Only on first overlay indicator - optimized for performance
- **Detection**: Uses `preserveTimeScale` flag to identify synchronized charts
- **Stealth**: Completely imperceptible to users (faster than human perception)

### Testing Protocol
1. Open frontend application
2. Add first overlay indicator (SMA, EMA, etc.)
3. Verify chart time range does NOT jump forward
4. Verify no perceptible flicker occurs
5. Add additional indicators - should not trigger fix

### Verification Commands
```bash
# Frontend tests
cd ktrdr/ui/frontend && npm run test

# Check specific chart component
cd ktrdr/ui/frontend && npm run test BasicChart

# Manual testing
./docker_dev.sh start
# Navigate to http://localhost:5173
# Add SMA indicator and verify no jumping
```

### Library Compatibility
- **Tested**: TradingView Lightweight Charts v5.0.7
- **Last Verified**: May 28, 2025
- **Future Versions**: Re-test if upgrading TradingView library

### Protection Measures
1. **Extensive Comments**: Code marked with warning blocks
2. **Documentation**: This file + CLAUDE.md entries
3. **Location Tracking**: Specific file and line numbers documented
4. **Test Protocol**: Manual verification steps defined

### If Fix is Accidentally Removed
**Symptoms**: Chart will jump forward in time when adding first indicator
**Emergency Restore**: Revert to git commit containing this fix
**Git Location**: Search for "CRITICAL FIX: Chart jumping bug"

### Contact
If this fix needs modification, ensure:
1. Issue is reproduced first
2. New solution is tested extensively
3. Timing requirements are validated
4. User experience remains seamless
5. Documentation is updated

---

**⚠️ CRITICAL: This fix prevents a severe user experience bug. Do not remove without replacement solution. ⚠️**