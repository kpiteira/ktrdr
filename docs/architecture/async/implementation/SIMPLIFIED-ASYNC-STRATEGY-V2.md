# Simplified Async Strategy V2: With Mode Handling & Progress Reporting

## Critical Features We Must Preserve

### 1. Loading Modes Drive Everything

The `mode` parameter fundamentally changes the behavior:

| Mode | Behavior | Gap Analysis | Fetching Strategy |
|------|----------|--------------|-------------------|
| **local** | Local data only | None | No fetching |
| **tail** | Recent gaps only | From last local data to now | Fetch recent segments |
| **backfill** | Historical gaps | From start date to first local | Fetch historical segments |
| **full** | Complete coverage | Both tail + backfill | Fetch all missing segments |

### 2. Progress Reporting Is Essential

Users need feedback during operations that can take 10+ minutes:
- Which step is currently running
- How many segments completed
- Estimated time remaining
- Ability to cancel

## The Clean Architecture

```
DataManager (async orchestrator)
├── Receives mode, coordinates flow
├── Creates ProgressManager
├── Calls components in mode-specific order
│
├── GapAnalyzer (sync, mode-aware)
│   ├── tail: analyze recent gaps
│   ├── backfill: analyze historical gaps
│   └── full: analyze all gaps
│
├── SegmentManager (sync, mode-aware)
│   ├── Different segment sizes per mode
│   └── Reports progress
│
├── DataFetcher (async, progress-critical)
│   ├── Detailed segment progress
│   ├── Periodic saving
│   └── Cancellation checks
│
└── DataProcessor/Validator (sync)
    └── Final processing with progress updates
```

## Implementation Priority

1. **Week 1**: ProgressManager + mode handling in GapAnalyzer
2. **Week 2**: SegmentManager with mode strategies
3. **Week 3**: DataFetcher with progress and saving
4. **Week 4**: Integration and testing

This preserves all critical functionality while keeping the clean sync/async separation!