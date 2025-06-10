# IB Gap Analysis and Filling System Improvements

## Overview

This specification addresses critical issues with the current IB data gap filling system and proposes a comprehensive redesign to make it trading hours aware, more efficient, and provide better analytical capabilities.

## Current System Analysis

### Existing Implementation Review

**Location**: Primary implementation in `ktrdr/data/ib_gap_filler.py`

**Current Architecture**:
- **Background Service**: Runs every 5 minutes via daemon thread
- **Gap Detection**: Time-based thresholds without trading hours awareness
- **Auto-discovery**: Scans existing CSV files to find symbols/timeframes to monitor
- **IB Integration**: Uses DataManager with "tail" mode for intelligent gap filling
- **Pacing Compliance**: Respects IB API limits with configurable delays

**Current Gap Detection Logic**:
```python
# Simplified current logic
next_expected = calculate_next_expected_timestamp(last_timestamp, timeframe)
current_time = TimestampManager.now_utc()
gap_hours = (current_time - next_expected).total_seconds() / 3600
gap_threshold = IbLimitsRegistry.get_gap_threshold_hours(timeframe)
```

**Current Thresholds** (from `ktrdr/config/ib_limits.py`):
- 1m: 0.5 hours (30 minutes)
- 5m: 1.0 hours
- 15m: 2.0 hours
- 1h: 6.0 hours
- 1d: 18.0 hours
- 1w: 7 days

### Critical Issues Identified

1. **Naive Gap Detection**: Current system treats weekends/holidays as missing data
2. **Excessive Sync Frequency**: 5-minute intervals for training/backtesting system
3. **No Trading Hours Integration**: Existing `trading_hours.py` and `ib_trading_hours_parser.py` not utilized
4. **No Gap Analysis Tools**: No CLI commands or API endpoints for gap analysis
5. **Limited Classification**: No distinction between expected vs unexpected gaps

## Proposed Solution Architecture

### 1. Enhanced Gap Classification System

#### **New Gap Classification Logic**

```python
class GapClassification(Enum):
    EXPECTED_WEEKEND = "expected_weekend"
    EXPECTED_TRADING_HOURS = "expected_trading_hours"  # For intraday timeframes
    EXPECTED_HOLIDAY = "expected_holiday"              # Adjacent to weekends
    UNEXPECTED = "unexpected"                          # Needs investigation
    MARKET_CLOSURE = "market_closure"                  # Extended market closures

def classify_gap(start_time: datetime, end_time: datetime, 
                symbol_metadata: dict, timeframe: str) -> GapClassification:
    """
    Classify gaps using trading hours metadata from symbol_discovery_cache.json
    """
    trading_hours = symbol_metadata.get('trading_hours', {})
    trading_days = trading_hours.get('trading_days', [1,2,3,4,5])  # Mon-Fri default
    
    # Check if gap spans weekend for daily+ timeframes
    if timeframe in ['1d', '1w'] and spans_weekend(start_time, end_time):
        return GapClassification.EXPECTED_WEEKEND
    
    # Check trading hours for intraday timeframes
    if timeframe_is_intraday(timeframe):
        if outside_trading_hours(start_time, end_time, trading_hours):
            return GapClassification.EXPECTED_TRADING_HOURS
    
    # Check for holiday patterns (gaps adjacent to weekends)
    if adjacent_to_weekend_gap(start_time, end_time, trading_days):
        return GapClassification.EXPECTED_HOLIDAY
    
    # Check for extended market closures (> 3 days)
    if (end_time - start_time).days > 3:
        return GapClassification.MARKET_CLOSURE
    
    return GapClassification.UNEXPECTED
```

#### **Symbol-Specific Trading Hours Integration**

Leverage existing `data/symbol_discovery_cache.json` structure:
```json
{
  "EURUSD": {
    "trading_hours": {
      "timezone": "America/New_York",
      "regular_hours": {"start": "17:00", "end": "17:00", "name": "Regular"},
      "extended_hours": [],
      "trading_days": [0,1,2,3,4]  // Sunday-Thursday for forex
    }
  },
  "AAPL": {
    "trading_hours": {
      "timezone": "America/New_York", 
      "regular_hours": {"start": "09:30", "end": "16:00", "name": "Regular"},
      "extended_hours": [
        {"start": "04:00", "end": "09:30", "name": "Pre-Market"},
        {"start": "16:00", "end": "20:00", "name": "After-Hours"}
      ],
      "trading_days": [1,2,3,4,5]  // Monday-Friday for stocks
    }
  }
}
```

### 2. Configurable Sync Frequency

#### **New Configuration Structure**

Add to `config/settings.yaml`:
```yaml
ib_sync:
  # Sync frequency options: disabled, manual, hourly, daily, weekly
  frequency: "daily"
  
  # Schedule for daily sync (after market close)
  daily_schedule:
    time: "18:00"  # 6 PM EST
    timezone: "America/New_York"
  
  # Emergency gap detection (still check frequently for critical gaps)
  emergency_gap_detection:
    enabled: true
    check_interval: 3600  # 1 hour instead of 5 minutes
    critical_threshold_multiplier: 3.0  # Only gaps 3x normal threshold
  
  # Manual override
  force_sync_on_command: true
  
  # Background service control
  auto_start_on_api_startup: true
```

#### **Enhanced Gap Thresholds**

```python
# In IbLimitsRegistry - make thresholds trading hours aware
TRADING_HOURS_AWARE_THRESHOLDS = {
    # During market hours - shorter thresholds
    "market_hours": {
        '1m': 0.25,   # 15 minutes
        '5m': 0.5,    # 30 minutes  
        '1h': 2.0,    # 2 hours
        '1d': 6.0,    # 6 hours (same day)
    },
    
    # Outside market hours - longer thresholds
    "non_market_hours": {
        '1m': 2.0,    # 2 hours (don't gap fill overnight)
        '5m': 4.0,    # 4 hours
        '1h': 12.0,   # 12 hours
        '1d': 36.0,   # Next trading day + buffer
    }
}
```

### 3. Gap Analysis API and CLI

#### **API Endpoint Design**

```python
@router.get("/data/{symbol}/{timeframe}/gaps")
async def analyze_gaps(
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    mode: GapAnalysisMode = GapAnalysisMode.NORMAL,
    include_expected: bool = False,
) -> GapAnalysisResponse:
    """
    Analyze data gaps for a symbol/timeframe in a date range.
    
    Args:
        symbol: Trading symbol (e.g., "EURUSD", "AAPL")
        timeframe: Data timeframe (e.g., "1d", "1h", "5m")
        start_date: Analysis start date (ISO format)
        end_date: Analysis end date (ISO format)
        mode: Analysis detail level (normal, extended, verbose)
        include_expected: Include expected gaps in results
    
    Returns:
        Comprehensive gap analysis with classification and statistics
    """
```

#### **Response Schema**

```python
class GapInfo(BaseModel):
    start_time: datetime
    end_time: datetime
    classification: GapClassification
    bars_missing: int
    duration_hours: float
    day_context: str  # "Monday-Tuesday", "Friday (pre-weekend)", etc.
    note: Optional[str]  # Human-readable explanation

class GapAnalysisResponse(BaseModel):
    symbol: str
    timeframe: str
    analysis_period: dict  # start, end, total_duration
    trading_metadata: dict  # From symbol_discovery_cache.json
    
    summary: dict = {
        "expected_bars": int,
        "actual_bars": int, 
        "total_missing": int,
        "data_completeness_pct": float,
        "missing_breakdown": {
            "expected_weekend": int,
            "expected_trading_hours": int,
            "expected_holiday": int,
            "unexpected": int,
            "market_closure": int
        }
    }
    
    gaps: List[GapInfo] = []  # Populated based on mode and include_expected
    
    recommendations: List[str] = []  # Actionable recommendations
```

#### **CLI Commands**

```bash
# Basic gap analysis
uv run ktrdr ib-analyze-gaps EURUSD 1d --start 2020-01-01 --end 2024-01-01

# Extended analysis (includes unexpected gaps detail)
uv run ktrdr ib-analyze-gaps EURUSD 1h --start 2024-01-01 --end 2024-02-01 --mode extended

# Verbose analysis (includes all gaps)
uv run ktrdr ib-analyze-gaps AAPL 1d --start 2023-01-01 --end 2024-01-01 --mode verbose --include-expected

# Multiple symbols analysis
uv run ktrdr ib-analyze-gaps-batch --symbols AAPL,MSFT,GOOGL --timeframe 1d --start 2023-01-01 --end 2024-01-01

# Gap filler service management
uv run ktrdr ib-gap-service status
uv run ktrdr ib-gap-service start --frequency daily
uv run ktrdr ib-gap-service stop
uv run ktrdr ib-gap-service sync-now --force
```

### 4. Example Response Formats

#### **Normal Mode Response**
```json
{
  "symbol": "EURUSD",
  "timeframe": "1d", 
  "analysis_period": {
    "start": "2020-01-01T00:00:00Z",
    "end": "2024-01-01T00:00:00Z",
    "total_days": 1461,
    "trading_days_expected": 1043
  },
  "trading_metadata": {
    "timezone": "America/New_York",
    "trading_days": [0,1,2,3,4],
    "asset_class": "forex"
  },
  "summary": {
    "expected_bars": 1043,
    "actual_bars": 1038,
    "total_missing": 5,
    "data_completeness_pct": 99.52,
    "missing_breakdown": {
      "expected_weekend": 0,
      "expected_trading_hours": 0,
      "expected_holiday": 3,
      "unexpected": 2,
      "market_closure": 0
    }
  },
  "recommendations": [
    "Data completeness is excellent at 99.52%",
    "2 unexpected gaps need investigation",
    "3 holiday gaps are normal for this timeframe"
  ]
}
```

#### **Extended Mode Response** (adds unexpected gaps)
```json
{
  // ... same as normal mode ...
  "gaps": [
    {
      "start_time": "2023-07-04T00:00:00Z",
      "end_time": "2023-07-04T23:59:59Z", 
      "classification": "unexpected",
      "bars_missing": 1,
      "duration_hours": 24,
      "day_context": "Tuesday (Independence Day)",
      "note": "Missing data on US holiday - broker may have closed early"
    },
    {
      "start_time": "2023-12-25T00:00:00Z",
      "end_time": "2023-12-26T23:59:59Z",
      "classification": "unexpected", 
      "bars_missing": 2,
      "duration_hours": 48,
      "day_context": "Monday-Tuesday (Christmas period)",
      "note": "Extended Christmas closure - verify with broker"
    }
  ]
}
```

#### **Verbose Mode Response** (adds all gaps including expected)
```json
{
  // ... same as extended mode ...
  "gaps": [
    // ... unexpected gaps from extended mode ...
    {
      "start_time": "2023-07-01T00:00:00Z",
      "end_time": "2023-07-03T23:59:59Z",
      "classification": "expected_holiday",
      "bars_missing": 1,
      "duration_hours": 24,
      "day_context": "Monday (between weekend)",
      "note": "Canada Day - typical holiday pattern"
    }
    // ... more gaps ...
  ]
}
```

## Implementation Phases

### Phase 1: Enhanced Gap Classification (High Priority)
**Timeline**: 1-2 weeks

**Tasks**:
1. Create `GapClassifier` class with trading hours integration
2. Update `GapFillerService` to use new classification logic
3. Integrate with existing `symbol_discovery_cache.json` data
4. Add comprehensive unit tests for classification scenarios

**Files to Modify**:
- `ktrdr/data/ib_gap_filler.py`
- `ktrdr/config/ib_limits.py`
- New: `ktrdr/data/gap_classifier.py`

### Phase 2: Configurable Sync Frequency (Medium Priority) 
**Timeline**: 1 week

**Tasks**:
1. Add sync frequency configuration to `config/settings.yaml`
2. Implement scheduled daily sync with timezone awareness
3. Add emergency gap detection for critical gaps only
4. Update API startup configuration

**Files to Modify**:
- `config/settings.yaml`
- `ktrdr/api/startup.py`
- `ktrdr/data/ib_gap_filler.py`

### Phase 3: Gap Analysis API (High Priority)
**Timeline**: 2-3 weeks

**Tasks**:
1. Implement `/data/{symbol}/{timeframe}/gaps` API endpoint
2. Create `GapAnalysisService` with comprehensive gap detection
3. Add response models and validation
4. Implement different analysis modes (normal/extended/verbose)

**Files to Create**:
- `ktrdr/api/endpoints/gap_analysis.py`
- `ktrdr/api/services/gap_analysis_service.py`
- `ktrdr/api/models/gap_analysis.py`

### Phase 4: Gap Analysis CLI (Medium Priority)
**Timeline**: 1-2 weeks  

**Tasks**:
1. Add `ib-analyze-gaps` command suite
2. Implement batch analysis capabilities
3. Add gap filler service management commands
4. Create user-friendly output formatting

**Files to Modify**:
- `ktrdr/cli/commands.py`
- New: `ktrdr/cli/gap_commands.py`

### Phase 5: Integration and Testing (High Priority)
**Timeline**: 1 week

**Tasks**:
1. Comprehensive integration testing
2. Update documentation and examples  
3. Performance optimization
4. User acceptance testing with real gap scenarios

## Success Criteria

### Immediate Goals
- [ ] Eliminate false positive gap detection for weekends/holidays
- [ ] Reduce sync frequency from 5 minutes to daily for training use cases
- [ ] Provide gap analysis API for data quality insights

### Medium-term Goals  
- [ ] 95%+ accuracy in gap classification (expected vs unexpected)
- [ ] Comprehensive CLI tools for gap management
- [ ] Integration with existing trading hours metadata

### Long-term Goals
- [ ] Automated data quality monitoring and alerting
- [ ] Symbol-specific gap handling rules
- [ ] Historical gap analysis for data quality trends

## Risk Mitigation

### Data Integrity Risks
- **Risk**: Missing critical market data during system transition
- **Mitigation**: Implement gradual rollout with fallback to current system

### Performance Risks  
- **Risk**: Gap analysis API becomes too slow for large date ranges
- **Mitigation**: Implement pagination, caching, and async processing

### Configuration Risks
- **Risk**: Misconfigured sync frequency causes data gaps
- **Mitigation**: Comprehensive validation and safe defaults

## Testing Strategy

### Unit Tests
- Gap classification logic with various scenarios
- Trading hours integration accuracy
- Configuration validation

### Integration Tests  
- End-to-end gap analysis workflow
- API endpoint response validation
- CLI command functionality

### Performance Tests
- Large date range gap analysis
- Multiple symbol batch processing
- Memory usage during gap scanning

### Regression Tests
- Ensure existing gap filling continues to work
- Validate no new gaps introduced by changes
- Verify IB API compliance maintained

This specification provides a comprehensive roadmap for transforming the current gap filling system into a trading hours aware, analytically rich, and efficiently scheduled data management system.