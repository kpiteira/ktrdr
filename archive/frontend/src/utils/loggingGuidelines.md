# KTRDR Frontend Logging Guidelines

## Strategic Logging Framework

This document defines our approach to clean, meaningful logging that helps users and developers without creating noise.

## Log Levels

### 🔵 **INFO** - User-facing events (default level)
**What users should know about their actions and system state**
```typescript
// Application lifecycle
logger.info('KTRDR Trading Research started', { mode: 'research', version: 'Slice 8' });

// User actions
logger.info('Mode changed to', 'research');
logger.info('Symbol changed to', 'MSFT 1h');
logger.info('Timeframe changed to', '1d');

// Data operations
logger.info('Data loaded for MSFT 1h', { points: 1234 });
logger.info('Indicator added: RSI', { period: 14 });
logger.info('Indicator removed: SMA', { period: 20 });

// Context changes
logger.info('Backtest context cleared');
logger.info('Mode switched to Research', { backtestId: 'abc123' });
```

### 🔍 **DEBUG** - Developer debugging (hidden by default)
**Technical details for debugging, enabled with VITE_LOG_LEVEL=DEBUG**
```typescript
// Component lifecycle
logger.debug('Component mounted: IndicatorSidebar');
logger.debug('Main chart created, storing reference for BacktestOverlay');
logger.debug('Emitting chartReady event for BacktestOverlay integration');

// Data caching and performance
logger.debug('Using cached fuzzy data for rsi-123');
logger.debug('Chart dimensions calculated', { width: 1200, height: 400 });
logger.debug('Time range changed', { start: '2024-01-01', end: '2024-06-07' });

// API calls (detailed)
logger.debug('API request started', { endpoint: '/data/load', params: {...} });
logger.debug('API response received', { status: 200, dataPoints: 1234 });
```

### ⚠️ **WARN** - Performance & fallback behaviors
**Important but non-critical issues that affect user experience**
```typescript
// Performance concerns
logger.warn('Large dataset detected, enabling data windowing', { points: 10000 });
logger.warn('Chart resize loop detected, switching to fixed dimensions');
logger.warn('API response slow', { duration: '5.2s', endpoint: '/data/load' });

// Fallback behaviors
logger.warn('Fuzzy data unavailable for RSI, showing indicator only');
logger.warn('Cache miss for symbol data, fetching from API');
logger.warn('Invalid indicator parameters, using defaults', { provided: {...}, defaults: {...} });
```

### ❌ **ERROR** - Critical failures
**System failures that prevent normal operation**
```typescript
// Network failures
logger.error('Failed to load data for MSFT', new Error('Network timeout'));
logger.error('API connection lost, attempting reconnection...');

// Component failures
logger.error('Chart creation failed', new Error('Container not found'));
logger.error('Indicator calculation failed for RSI', error);

// Data corruption
logger.error('Invalid OHLCV data received', { symbol: 'MSFT', issue: 'negative prices' });
```

## Usage Patterns

### ✅ **Good Examples**
```typescript
// Clean, actionable messages
logger.info('Symbol changed to', `${symbol} ${timeframe}`);
logger.debug('Using cached data for', indicatorId);
logger.warn('Large dataset detected', { points: data.length });
logger.error('Data loading failed', error);
```

### ❌ **Bad Examples**
```typescript
// Too verbose, should be DEBUG
logger.info('BasicChart: Emitting chartReady event');

// Redundant information
logger.info('Switching to Research mode from Train mode', { backtestId: backtest });

// Object dumps without context
logger.info('All backtestTrades:', state.backtestTrades);

// Multiple identical messages
logger.info('App initialized', { symbol: 'MSFT', timeframe: '1h' }); // x4
```

## Configuration

### Development
```bash
# Default: INFO level (clean startup)
npm run dev

# Enable debug logging when needed
VITE_LOG_LEVEL=DEBUG npm run dev

# Minimal logging for performance testing
VITE_LOG_LEVEL=WARN npm run dev
```

### Runtime Control
```javascript
// In browser console
window.__logger.setLevel(window.__LogLevel.DEBUG);
window.__logger.setLevel(window.__LogLevel.INFO);
```

## Expected Startup Output

### Default (INFO level)
```
[Logger] Initialized with level: INFO
[Logger] Available in window.__logger for debugging
[2025-06-07T15:29:10.663Z] [INFO] [App] KTRDR Trading Research started {mode: "research", version: "Slice 8"}
```

### Debug enabled (DEBUG level)
```
[Logger] Initialized with level: DEBUG
[Logger] Available in window.__logger for debugging
[2025-06-07T15:29:10.663Z] [INFO] [App] KTRDR Trading Research started {mode: "research", version: "Slice 8"}
[2025-06-07T15:29:10.665Z] [DEBUG] [BasicChart] Component mounted with props {symbol: "MSFT", timeframe: "1h"}
[2025-06-07T15:29:10.667Z] [DEBUG] [BasicChart] Emitting chartReady event for BacktestOverlay integration
[2025-06-07T15:29:10.668Z] [DEBUG] [App] Main chart created, storing reference for BacktestOverlay
```

## Best Practices

1. **Use appropriate log levels**: INFO for user actions, DEBUG for technical details
2. **Be concise**: "Mode changed to research" not "Switching to Research mode from Train mode"
3. **Include context**: Always include relevant identifiers (symbol, backtestId, etc.)
4. **Avoid duplicates**: Check for component re-renders causing multiple identical logs
5. **Use structured data**: Pass objects as additional parameters, not stringified
6. **No console.log**: Always use the logger with appropriate levels
7. **Performance aware**: Large objects should only be logged at DEBUG level

## Migration Checklist

When updating existing logging:
- [ ] Replace `console.log` with `logger.debug`
- [ ] Replace `console.info` with `logger.info` (if user-relevant) or `logger.debug`
- [ ] Move technical details to DEBUG level
- [ ] Simplify log messages to be more scannable
- [ ] Add structured context data as separate parameters
- [ ] Check for duplicate messages from re-renders