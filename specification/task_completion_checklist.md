# KTRDR Task Completion Checklist

This document serves as a mandatory reference for all task implementations in the KTRDR project. Every task implementation **must** include a comprehensive Task Completion Report that follows the structure outlined below.

## Required Components for Every Task Implementation

### 1. Complete Implementation

- [ ] All subtasks specified in the task breakdown are fully implemented
- [ ] Code follows the architectural guidelines from `ktrdr-architecture-blueprint.md`
- [ ] Implementation satisfies all requirements from `ktrdr_product_requirements_v2.md`

### 2. Documentation and Code Quality

- [ ] All classes and functions have comprehensive docstrings
- [ ] Code includes appropriate comments for complex logic
- [ ] Code follows PEP 8 conventions
- [ ] Type hints are used consistently

### 3. Error Handling and Logging

- [ ] Appropriate error types from `ktrdr.errors` are used
- [ ] Error messages are clear and actionable
- [ ] Error codes follow the established format (CATEGORY-ErrorName)
- [ ] Module-level logger is defined and used consistently
- [ ] Appropriate log levels are used throughout the code

### 4. Testing

- [ ] Working tests validate all implemented functionality
- [ ] Tests cover both success and error cases
- [ ] Tests validate error handling and retry mechanisms

## Task Completion Report Template

Every implementation **must** end with a Task Completion Report using this exact format:

```markdown
## Task X.Y Completion Report

### Implementation Verification Checklist:
- [ ] Criterion 1: [Specific verification for this task]
- [ ] Criterion 2: [Specific verification for this task]
...

### Testing Steps:
1. Run: `[exact command to run]`
   Expected output: [What the user should see]
2. Run: `[exact command to run]`
   Expected output: [What the user should see]
...

### Minimal Working Example:
```python
# verification_example.py
# This code demonstrates the functionality implemented in Task X.Y

[Include a complete, runnable example that demonstrates the key functionality]
```

Run with: `python verification_example.py`
Expected output: [Describe what the user should see when running the example]

### Clean-up Instructions:
1. Remove temporary files: `rm verification_example.py`
2. [Any other cleanup steps needed]
3. Update the task breakdown document:
   - Change "- [ ] **Task X.Y**:" to "- [x] **Task X.Y**:"
   - Mark all subtasks as completed
```

## Checklist for Specific Task Types

### Configuration Tasks:
- [ ] Configuration loading works correctly from YAML files
- [ ] Validation correctly rejects invalid configurations
- [ ] Default values are applied when optional fields are missing

### Data Loading Tasks:
- [ ] Data loads correctly from specified sources
- [ ] Missing/corrupt files are handled gracefully
- [ ] Loaded data matches expected format

### Error Handling Tasks:
- [ ] Exception hierarchy is properly organized
- [ ] Error handlers classify errors correctly
- [ ] Retry mechanisms work for appropriate operations

### Logging Tasks:
- [ ] Logs are written to appropriate destinations
- [ ] Log entries contain required context information
- [ ] Log levels are used appropriately

### UI and Visualization Tasks:
- [ ] Components render correctly
- [ ] User interactions work as expected
- [ ] Visual elements match design requirements

## Indicator Implementation Checklist

When implementing new technical indicators, ensure the following requirements are met:

### Indicator Class Structure
- [ ] Class properly inherits from `BaseIndicator`
- [ ] `__init__` method defines all parameters with appropriate defaults
- [ ] `_validate_params` method includes comprehensive validation
- [ ] `compute` method has proper DataFrame input and Series output typing
- [ ] Consistent naming convention is followed for the indicator

### Indicator Implementation
- [ ] Vectorized calculations using pandas/numpy where possible
- [ ] Proper handling of warmup period (NaN values at the beginning)
- [ ] Edge cases handled (insufficient data, constant values, etc.)
- [ ] Performance optimized for large datasets (10,000+ data points)
- [ ] Consistent output name format using `get_column_name()` method

### Testing Integration
- [ ] Reference values created in `tests/indicators/reference_datasets.py`
- [ ] Different parameter configurations tested
- [ ] Reference values cover key patterns (trends, reversals, plateaus)
- [ ] Indicator registered in `tests/indicators/indicator_registry.py`
- [ ] Appropriate tolerance value defined in `TOLERANCES` dictionary
- [ ] Special edge cases added if needed in registration

### Validation Requirements
- [ ] Automated tests validate calculation accuracy
- [ ] Tests for invalid parameter handling
- [ ] Tests for edge case behavior
- [ ] Tests for consistent output format
- [ ] All tests pass when running `pytest tests/indicators/`

### Documentation
- [ ] Comprehensive class docstring includes:
  - [ ] Purpose and calculation description
  - [ ] Formula or algorithm
  - [ ] Common use cases
  - [ ] Parameter descriptions
  - [ ] References to standard definitions
  - [ ] Any implementation notes or limitations
- [ ] Method docstrings for all public methods
- [ ] Inline comments for complex calculations

### Error Handling & Logging
- [ ] Data validation uses `validate_input_data` and `validate_sufficient_data`
- [ ] Appropriate error types from `ktrdr.errors` for parameter validation
- [ ] Clear error messages with descriptive codes
- [ ] Appropriate logging at key points
- [ ] Try/except blocks around calculation logic with proper error wrapping

Verify all checklist items are complete before considering an indicator implementation finished. This ensures consistent, well-tested, and properly integrated indicators that work with the validation framework implemented in Task 2.6.

## Rules for Task Completion

1. **No Exceptions**: Every task implementation must include the full Task Completion Report, regardless of task complexity.

2. **Verification First**: Design verification steps at the beginning of the task implementation, not as an afterthought.

3. **Concrete Evidence**: The Task Completion Report must provide concrete, verifiable evidence that the implementation satisfies all requirements.

4. **Clean Up After Testing**: Always include steps to remove temporary verification files.

5. **Update Task Status**: After implementation and verification, update the task breakdown document to mark the task and all subtasks as completed.

A task is not considered complete until the user can successfully verify all functionality using the provided Task Completion Report.
