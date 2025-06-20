# KTRDR Logging Guidelines

## Overview

This document provides comprehensive guidelines for effective logging in the KTRDR codebase to ensure logs are useful, readable, and not overwhelming.

## Log Level Hierarchy

### CRITICAL
- **Purpose**: System failures that require immediate attention
- **When to use**: 
  - Security breaches
  - System crashes
  - Data corruption
  - Complete service unavailability
- **Example**: `logger.critical("Database connection lost - all trading operations suspended")`

### ERROR  
- **Purpose**: Operation failures that require attention but don't break the system
- **When to use**:
  - API call failures
  - Data processing errors
  - Configuration errors
  - Connection failures
- **Example**: `logger.error("Failed to fetch data for AAPL: Connection timeout")`

### WARNING
- **Purpose**: Issues that should be monitored but don't immediately require action
- **When to use**:
  - Retryable failures
  - Performance degradation
  - Configuration issues with fallbacks
  - Rate limiting triggered
- **Example**: `logger.warning("IB rate limit reached, waiting 30s before retry")`

### INFO
- **Purpose**: Business logic events and significant operations
- **When to use**:
  - Successful completion of major operations
  - System state changes
  - Important business events
  - Configuration changes
- **Example**: `logger.info("Successfully processed 1000 bars for AAPL 1h")`

### DEBUG
- **Purpose**: Technical details for troubleshooting
- **When to use**:
  - Function entry/exit
  - Parameter values
  - Internal state changes
  - Diagnostic information
- **Example**: `logger.debug("Creating contract: AAPL (STK)")`

## Component-Specific Guidelines

### IB Gateway Integration (`ktrdr.ib.*`)

**Default Level**: INFO
**Recommended Settings**:
- Production: WARNING
- Development: INFO  
- Debugging: DEBUG

**Rules**:
- Connection events: INFO level
- Data fetching completion: INFO level
- Parameter details: DEBUG level
- Diagnostic information: DEBUG level
- Error conditions: ERROR level

### API Layer (`ktrdr.api.*`)

**Default Level**: INFO
**High-frequency paths**: DEBUG with rate limiting

**Rules**:
- Request/response logging: INFO for normal operations, DEBUG for polling
- Authentication events: INFO level
- Validation errors: WARNING level
- Internal API errors: ERROR level

### Data Processing (`ktrdr.data.*`)

**Default Level**: INFO

**Rules**:
- Data loading completion: INFO level
- Processing statistics: INFO level
- Data validation issues: WARNING level
- Processing errors: ERROR level

## Anti-Patterns to Avoid

### ❌ Emoji Prefixes
```python
# DON'T DO THIS
logger.info("🔍 DIAGNOSIS: Starting data fetch")
logger.error("🚨 DIAGNOSIS: Connection failed")
```

```python
# DO THIS INSTEAD  
logger.debug("Starting data fetch")
logger.error("Connection failed")
```

### ❌ Excessive Parameter Logging
```python
# DON'T DO THIS
logger.info(f"Parameters: start={start}, end={end}, symbol={symbol}, timeframe={timeframe}, duration={duration}")
```

```python
# DO THIS INSTEAD
logger.debug(f"Fetching data: {symbol} {timeframe} ({duration})")
```

### ❌ High-Frequency Logging Without Sampling
```python
# DON'T DO THIS  
for i in range(10000):
    logger.info(f"Processing iteration {i}")
```

```python
# DO THIS INSTEAD
for i in range(10000):
    if should_sample_log(f"processing_loop", 100):
        logger.debug(f"Processing iteration {i}")
```

### ❌ Wrong Log Levels
```python
# DON'T DO THIS - diagnostic info at INFO level
logger.info("Connection health check passed")
logger.info("Request processing loop iteration 1000")
```

```python
# DO THIS INSTEAD - diagnostic info at DEBUG level
logger.debug("Connection health check passed")  
if should_sample_log("processing_loop", 500):
    logger.debug("Request processing loop iteration 1000")
```

## Best Practices

### 1. Use Structured Logging
```python
# Good - provides context without noise
logger.info(f"Data fetch completed: {len(df)} bars for {symbol}")

# Better - includes timing
logger.info(f"Data fetch completed: {len(df)} bars for {symbol} in {elapsed:.2f}s")
```

### 2. Apply Log Sampling for High-Frequency Operations
```python
from ktrdr.logging.config import should_sample_log

# Sample every 100th iteration
if should_sample_log("processing_loop", 100):
    logger.debug(f"Processing loop iteration {iteration}")
```

### 3. Use Rate Limiting for Repetitive Messages
```python
from ktrdr.logging.config import should_rate_limit_log

# Log at most once per minute
if should_rate_limit_log("connection_retry", 60):
    logger.warning("Connection retry in progress")
```

### 4. Provide Meaningful Context
```python
# Poor context
logger.error("Validation failed")

# Good context  
logger.error(f"Symbol validation failed for {symbol}: {error_message}")

# Excellent context
logger.error(f"Symbol validation failed for {symbol} (attempt {retry_count}/{max_retries}): {error_message}")
```

### 5. Use Component-Specific Loggers
```python
# Get logger for current module
logger = get_logger(__name__)

# This enables component-specific log level control
```

## Runtime Log Management

### Quiet Mode
For reduced logging noise during normal operations:
```python
from ktrdr.logging.management import enable_quiet_mode
enable_quiet_mode()
```

### Debug Mode  
For enhanced debugging during development:
```python
from ktrdr.logging.management import enable_debug_mode
enable_debug_mode()
```

### Production Settings
Optimized for production environments:
```python
from ktrdr.logging.management import log_manager
log_manager.apply_production_settings()
```

### Check Logging Status
```python
from ktrdr.logging.management import get_logging_status
status = get_logging_status()
print(status)
# {'ib.connection': 'WARNING', 'ib.data_fetcher': 'INFO', ...}
```

## Environment-Specific Defaults

### Development
- Default level: DEBUG
- Console: INFO with colors
- File: DEBUG with full details
- High-frequency operations: DEBUG with sampling

### Production  
- Default level: INFO
- Console: WARNING 
- File: INFO with rotation
- High-frequency operations: WARNING with rate limiting

### Testing
- Default level: WARNING
- Minimal output for fast test execution
- Error-only logging for most components

## Migration from Old Patterns

### Removing Emoji Prefixes
```bash
# Use the provided cleanup script
uv run python cleanup_emoji_logs.py
```

### Converting Diagnostic Logs
1. Change INFO diagnostic logs to DEBUG
2. Remove verbose parameter dumps
3. Add log sampling for loops
4. Apply component-specific log levels

### Example Migration
```python
# Before
logger.info("🔍 DIAGNOSIS: Starting connection loop iteration 100")
logger.info("🔍 DIAGNOSIS: Parameters - start=2024-01-01, end=2024-01-02, symbol=AAPL")

# After  
if should_sample_log("connection_loop", 500):
    logger.debug("Connection loop iteration 100")
logger.debug("Fetching data: AAPL 2024-01-01 to 2024-01-02")
```

## Testing Logging Configuration

### Verify Log Levels
```python
import logging
from ktrdr.logging.config import get_component_log_levels

levels = get_component_log_levels()
assert levels["ib.connection"] == logging.WARNING
```

### Test Log Sampling
```python
from ktrdr.logging.config import should_sample_log, reset_sampling_state

reset_sampling_state()
assert should_sample_log("test", 5) == True   # 1st call
assert should_sample_log("test", 5) == False  # 2nd call  
assert should_sample_log("test", 5) == False  # 3rd call
```

### Test Rate Limiting
```python
from ktrdr.logging.config import should_rate_limit_log, reset_rate_limit_state
import time

reset_rate_limit_state()
assert should_rate_limit_log("test", 1) == True   # First call
assert should_rate_limit_log("test", 1) == False  # Too soon
time.sleep(1.1)
assert should_rate_limit_log("test", 1) == True   # After timeout
```

## Monitoring and Metrics

### Log Volume Monitoring
- Track log entries per minute by level
- Alert on excessive ERROR/WARNING volume
- Monitor DEBUG log volume in production

### Performance Impact
- Measure logging overhead in critical paths
- Use sampling to reduce performance impact
- Consider async logging for high-throughput scenarios

### Log Quality Metrics
- Ratio of DEBUG to INFO logs (should be higher)
- Number of emoji prefixes (should be zero)
- Average log message length (aim for concise)

## Tools and Utilities

### Cleanup Script
`cleanup_emoji_logs.py` - Removes emoji prefixes from existing code

### Log Manager
`ktrdr.logging.management.LogManager` - Runtime log level control

### Sampling Utilities
`should_sample_log()` - Frequency-based log sampling
`should_rate_limit_log()` - Time-based log rate limiting

### Component Configuration
`set_component_log_level()` - Set levels for specific components
`get_component_log_levels()` - Get current component levels

## Conclusion

Following these guidelines will result in:
- **Readable logs** that provide useful information without noise
- **Debuggable systems** with appropriate detail levels
- **Performant logging** that doesn't impact system performance
- **Maintainable code** with consistent logging patterns

The key principles are:
1. **Right level for right purpose** - Match log level to information importance
2. **Sample high-frequency logs** - Reduce noise from repetitive operations  
3. **Provide meaningful context** - Include relevant details for troubleshooting
4. **Use component-specific controls** - Enable targeted debugging
5. **Monitor and adjust** - Continuously improve logging effectiveness