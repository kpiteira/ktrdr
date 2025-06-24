# Phase 0 Stability Testing Guide

## Overview

The 24-hour stability test validates that the IB Host Service integration maintains consistent operation over extended periods. This test monitors key metrics every 5 minutes to detect any degradation, memory leaks, or connection issues.

## Current Test Status

**Started:** June 23, 2025 at 08:40:55 PDT  
**Duration:** 24 hours (288 iterations at 5-minute intervals)  
**Status:** ✅ Running  

## Monitoring Commands

### Quick Status Check
```bash
./monitor-stability-progress.sh
```

### Live Progress Monitoring
```bash
tail -f stability-test.log
```

### View Recent Summaries
```bash
grep "📊 Summary" stability-test.log | tail -5
```

### Check for Errors
```bash
grep "❌" stability-test.log
```

## Monitored Metrics

### Core Health Checks (Every 5 minutes)
- **Host Service Health**: HTTP health endpoint availability
- **Backend Environment**: Docker environment configuration
- **Network Connectivity**: Docker-to-host communication
- **IB Status Consistency**: Status endpoint shows host service mode
- **Backend API Health**: FastAPI health endpoint

### Performance Metrics
- **Response Times**: Host service and backend API latency
- **Memory Usage**: Host service and backend container memory consumption
- **Container Status**: Docker container health

### Error Tracking
- **Iteration Errors**: Per-check failure count
- **Total Errors**: Cumulative error count over test duration
- **Error Patterns**: Identification of recurring issues

## Success Criteria

The stability test passes if:
- ✅ **Zero errors** over 24-hour period
- ✅ **Consistent response times** (< 100ms average)
- ✅ **Stable memory usage** (no continuous growth)
- ✅ **No service interruptions** (100% uptime)
- ✅ **Configuration consistency** (host service mode maintained)

## Test Logs

### Primary Log Files
- `stability-test.log` - Detailed timestamped metrics
- `stability-monitor-output.log` - Script output and errors

### Log Format
```
[2025-06-23 08:40:55] === Iteration 1 (0h elapsed) ===
[2025-06-23 08:40:55] ✅ Host service health: PASS
[2025-06-23 08:40:55] ⏱️  Host service response time: 0.913ms
[2025-06-23 08:40:55] ✅ Backend environment: PASS
[2025-06-23 08:40:55] ✅ Docker→Host network: PASS
[2025-06-23 08:40:55] ✅ IB status endpoint: PASS
[2025-06-23 08:40:55] ✅ Backend API health: PASS
[2025-06-23 08:40:57] 💾 Host service memory: 0.8%
[2025-06-23 08:40:57] 💾 Backend memory: 3.87%
[2025-06-23 08:40:57] 🐳 Backend container status: running
[2025-06-23 08:40:57] ✅ All checks passed
[2025-06-23 08:40:57] 📊 Summary: Iteration 1, Errors: 0, Uptime: 0h
```

## Manual Test Scenarios

While the automated test runs, these manual scenarios can validate resilience:

### Sleep/Wake Test (macOS)
1. Put computer to sleep for 1+ hours
2. Wake and check if host service recovered
3. Verify backend reconnected automatically

### Network Stress Test
1. Temporarily disable/enable network interface
2. Check recovery time and error handling
3. Validate no data corruption

### Memory Pressure Test
1. Run memory-intensive applications
2. Monitor host service and backend behavior
3. Check for graceful degradation

## Stopping the Test

### Planned Stop
```bash
# Get process ID
ps aux | grep "monitor-phase0-stability.sh"

# Stop gracefully
kill <PID>
```

### Emergency Stop
```bash
pkill -f "monitor-phase0-stability.sh"
```

## Test Analysis

### After Completion
1. **Review Error Count**: Should be 0 for passing test
2. **Analyze Response Times**: Check for latency trends
3. **Memory Usage Pattern**: Confirm no memory leaks
4. **Error Distribution**: If errors occurred, analyze timing patterns

### Key Questions
- Were there any service interruptions?
- Did response times remain consistent?
- Was memory usage stable?
- Did the system recover from any transient issues?

## Expected Results

Based on Phase 0 architecture:
- **Error Rate**: 0% (stable networking via host service)
- **Uptime**: 100% (no Docker networking issues)
- **Response Time**: < 5ms average (local HTTP calls)
- **Memory Growth**: < 1% over 24h (minimal memory footprint)

## Next Steps After Test

Upon successful completion:
1. ✅ Mark Phase 0 as production-ready
2. 📊 Analyze performance baselines
3. 📋 Document operational procedures
4. 🚀 Plan Phase 1 (Training service extraction)

## Troubleshooting

### Test Stopped Unexpectedly
```bash
# Check system resources
top -l 1 | grep "CPU usage"
df -h

# Check Docker status
docker ps -a

# Restart test if needed
./monitor-phase0-stability.sh
```

### High Error Rate
```bash
# Immediate validation
./validate-phase0.sh

# Check logs for patterns
grep -A 5 -B 5 "❌" stability-test.log

# Diagnose specific failures
docker logs ktrdr-backend | tail -50
curl -s http://localhost:5001/health | jq .
```

---

**Phase 0 Stability Testing ensures production readiness of the IB Host Service integration.**