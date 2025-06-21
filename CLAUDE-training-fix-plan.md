# Training-Indicator Coupling Fix Plan

## Context & Problem
- **Date**: June 21, 2025
- **Issue**: Training fails with "NaN loss on first batch" for neuro_mean_reversion strategy
- **Root Cause**: Commit `1efe5ab` (June 21) added hard-coded derived metric calculations to training pipeline that run regardless of strategy configuration
- **Violation**: Training pipeline now calculates BB width, volume ratio, squeeze intensity even when strategy doesn't use these indicators

## Architecture Violation
Training pipeline should be **indicator-agnostic** and only process indicators declared in strategy config. The addition of hard-coded derived metrics violates separation of concerns.

## Complete Surgical Fix Plan: Remove Training-Indicator Coupling

### Objective
Remove inappropriate indicator calculations added to training pipeline in commit `1efe5ab` (June 21) to restore working training behavior from June 5, while maintaining proper architectural separation AND ensuring derived metrics are available as proper indicator classes.

## Phase 1: Create Proper Indicator Classes (FIRST - Better Approach)

### Step 1: Audit Current Violations & Extract Formulas
- Locate all hard-coded indicator calculations in `ktrdr/training/train_strategy.py`
- Document the exact mathematical formulas being used:
  - Bollinger Band width calculation (`bb_width`)
  - Volume ratio calculation (`volume_ratio`) 
  - Squeeze intensity calculation (`squeeze_intensity`)
- Note parameter requirements and dependencies

### Step 2: BollingerBandWidthIndicator
- Create `ktrdr/indicators/bollinger_band_width_indicator.py` following established pattern:
  - Inherit from BaseIndicator with `display_as_overlay=True`
  - Implement `__init__`, `_validate_params`, and `compute` methods
  - Calculate: `(upper_band - lower_band) / middle_band`
  - Return pd.Series with proper column naming
- Create `BOLLINGER_BAND_WIDTH_SCHEMA` in `schemas.py`
- Register in `indicator_factory.py` (import + BUILT_IN_INDICATORS dict)
- Add comprehensive tests following existing test patterns

### Step 3: VolumeRatioIndicator  
- Create `ktrdr/indicators/volume_ratio_indicator.py` following established pattern:
  - Inherit from BaseIndicator with `display_as_overlay=False`
  - Implement calculation: `current_volume / volume_sma`
  - Handle volume SMA period configuration as parameter
  - Proper error handling for missing volume data
- Create `VOLUME_RATIO_SCHEMA` in `schemas.py`
- Register in `indicator_factory.py` (import + BUILT_IN_INDICATORS dict)
- Add comprehensive tests following existing test patterns

### Step 4: SqueezeIntensityIndicator
- Create `ktrdr/indicators/squeeze_intensity_indicator.py` following established pattern:
  - Inherit from BaseIndicator with `display_as_overlay=False`
  - Implement composite calculation using external BB and KC data
  - Handle complex squeeze detection logic as found in training code
  - Parameters for BB and KC configuration references
- Create `SQUEEZE_INTENSITY_SCHEMA` in `schemas.py`
- Register in `indicator_factory.py` (import + BUILT_IN_INDICATORS dict)
- Add comprehensive tests following existing test patterns

### Step 5: Follow Established Architecture Pattern
**All new indicators will automatically integrate with existing systems:**
- ✅ API endpoints (`/api/v1/indicators`) - automatic via factory registration
- ✅ CLI commands (`ktrdr indicators list`) - automatic via factory registration  
- ✅ Strategy configurations - automatic via schema validation
- ✅ Indicator engine processing - automatic via BaseIndicator inheritance

**Architecture Pattern to Follow:**
```python
class IndicatorNameIndicator(BaseIndicator):
    def __init__(self, param1=default1, param2=default2):
        super().__init__(name="IndicatorName", display_as_overlay=True/False, param1=param1, param2=param2)
    
    def _validate_params(self, params):
        return INDICATOR_SCHEMA.validate(params)
    
    def compute(self, data: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        # Implementation with proper error handling using DataError
```

## Phase 2: Test Indicator Classes Independently

### Step 1: Unit Tests for New Indicators
- Unit tests for each derived indicator
- Integration tests with indicator engine
- Validation of mathematical correctness
- Edge case and error handling tests

### Step 2: Test Strategy Configurations Using Derived Indicators
- Create test strategy that uses `bollinger_band_width`
- Create test strategy that uses `volume_ratio`
- Create test strategy that uses `squeeze_intensity`
- Verify indicators work properly in isolation

## Phase 3: Remove Training Pipeline Violations

### Step 1: Surgical Removal from Training
- Remove ALL hard-coded derived metric calculations from `_calculate_indicators` method
- Restore indicator processing to only handle indicators explicitly configured in strategy
- Remove any logic that assumes indicators exist when they're not configured
- Keep existing indicator mapping logic (RSI, MACD, SMA) that was working on June 5

### Step 2: Test Core Strategy
- Verify `neuro_mean_reversion` strategy trains successfully
- Confirm no "NaN loss on first batch" errors
- Validate feature engineering produces reasonable feature counts
- Check that only RSI, MACD, SMA indicators are processed

## Phase 4: Strategy Configuration Updates

### Step 1: Document Usage Patterns
- Create examples showing how strategies can use derived indicators
- Document parameter requirements for each derived indicator
- Show proper strategy configuration syntax

### Step 2: Update Any Dependent Strategies
- Check if any existing strategies expect these derived metrics
- Update their configurations to explicitly declare derived indicators
- Ensure backward compatibility where possible

## Phase 5: Integration Testing & Verification

### Step 1: End-to-End Testing with Derived Indicators
- Verify end-to-end training works with derived indicators
- Test strategies that use new indicator classes
- Confirm proper integration with existing systems

### Step 2: Regression Testing
- Test other existing strategies to ensure no functionality broken
- Verify debug branch changes don't interfere with fix
- Confirm training metrics are reasonable

## Phase 6: Interface Contracts & Architecture

### Step 1: Establish Clean Boundaries
- Document that training pipeline is indicator-agnostic
- Establish rule: all mathematical calculations belong in indicator classes
- Create architectural guidelines to prevent future violations

### Step 2: Standardize Indicator Outputs
- Ensure all indicators return bounded, validated values
- Add proper error handling for edge cases
- Standardize naming conventions and output formats

## Phase 7: Clean Up & Documentation

### Step 1: Remove Debug Code
- Remove comprehensive NaN detection debug logging added during investigation
- Keep minimal essential logging for normal operation
- Revert any temporary debugging modifications

### Step 2: Code Documentation
- Add clear comments about architectural separation
- Document proper usage of derived indicators
- Add examples in indicator documentation
- Note the June 21 incident to prevent future violations

### Step 3: Architecture Documentation
- Update training pipeline documentation to emphasize indicator-agnostic design
- Document proper separation of concerns in `docs/` folder
- Create guidelines for future indicator development

## Success Criteria

1. ✅ `neuro_mean_reversion` strategy trains without NaN errors
2. ✅ All derived indicators available as proper indicator classes
3. ✅ Zero hard-coded derived metrics calculations in training pipeline
4. ✅ New indicator classes pass comprehensive tests
5. ✅ Training pipeline is completely indicator-agnostic
6. ✅ Strategies can optionally use derived indicators via proper configuration
7. ✅ No regression in existing working functionality
8. ✅ Clear architectural boundaries established and documented

## Implementation Notes

- **Scope**: Surgical fix + proper indicator class creation
- **Target**: Restore June 5 working behavior + provide derived indicators properly
- **Approach**: Create indicator classes FIRST, then remove training violations, maintain separation
- **Validation**: Working training + available derived indicators as separate components
- **Branch Strategy**: Commit current debug work, create new `fix/remove-training-indicator-coupling` branch
- **Testing Priority**: Indicators first (independent), then training cleanup, then integration
- **Documentation**: Use `docs/` folder for architecture guidelines and examples

## Architecture Principles

### Training Pipeline Responsibilities:
- ✅ Load strategy configuration
- ✅ Orchestrate indicator engine (calculate raw indicators)
- ✅ Orchestrate fuzzy engine (convert indicators to fuzzy memberships)
- ✅ Feature engineering (scaling, selection of fuzzy outputs)
- ✅ Neural network training
- ❌ Direct indicator calculations
- ❌ Derived metrics calculations
- ❌ Mathematical transformations of indicator data

### Indicator Engine Responsibilities:
- ✅ All mathematical calculations
- ✅ Derived metrics as separate indicators
- ✅ Input validation and bounds checking
- ✅ Error handling for edge cases
- ✅ Standardized output formats

## Key Files to Modify

1. `ktrdr/training/train_strategy.py` - Remove hard-coded derived metrics
2. `ktrdr/indicators/bollinger_band_width_indicator.py` - NEW
3. `ktrdr/indicators/volume_ratio_indicator.py` - NEW  
4. `ktrdr/indicators/squeeze_intensity_indicator.py` - NEW
5. `ktrdr/indicators/indicator_factory.py` - Register new indicators
6. `ktrdr/indicators/schemas.py` - Add parameter schemas
7. Strategy configs - Update any that need derived indicators

## Git Context
- **Working state**: commit `f49399b` (June 5, 2025)
- **Breaking commit**: commit `1efe5ab` (June 21, 2025)
- **Current branch**: `debug/training-nan-investigation`
- **Target**: Restore working training with proper architectural separation