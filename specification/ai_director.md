# KTRDR AI Implementation Director

This document provides guidance for AI assistants on how to generate optimal prompts and implement tasks for the KTRDR project.

## Primary Implementation Documents

When implementing tasks, refer to these key documents:
- `ktrdr_phase1_task_breakdown_v2.md`: Task definitions and sequence
- `ktrdr-architecture-blueprint.md`: Architecture guidelines and module structure
- `ktrdr_product_requirements_v2.md`: Product requirements and acceptance criteria
- `ktrdr_product_roadmap.md`: Overall product vision and roadmap

## Prompt Generation Process

When asked to "generate a prompt for task X.Y" or "implement task X.Y", follow this process:

1. **Task Identification**:
   - Locate the specified task in `ktrdr_phase1_task_breakdown_v2.md`
   - Identify the slice it belongs to and related subtasks

2. **Context Collection**:
   - Find relevant architectural guidance in `ktrdr-architecture-blueprint.md`
   - Identify relevant requirements in `ktrdr_product_requirements_v2.md`
   - Check for any roadmap considerations in `ktrdr_product_roadmap.md`

3. **Prompt Generation**:
   - Construct a prompt that includes:
     - Task description and objectives
     - Related architectural principles (condensed)
     - Implementation requirements
     - Relevant code snippets or interfaces
   - Focus on ONLY including context that is directly relevant to the task

4. **Implementation**:
   - After generating the prompt, proceed with implementing the task
   - Create the necessary directory structure if it doesn't exist
   - Write code that adheres to the architectural guidelines
   - Add appropriate error handling and logging
   - Include tests as specified in the task breakdown

## Prompt Templates

### Task Implementation Template

```
I'm implementing the [Component] for KTRDR according to Task [X.Y]. This component [brief description of purpose].

Key details from the architecture document:
[paste only the most relevant 5-10 lines from architecture document]

The specific subtasks are:
[paste subtasks from task breakdown]

Relevant requirements from the product requirements document:
[paste any specific requirements or acceptance criteria]

Error handling considerations:
- Error types needed: [list relevant error types]
- Operations that need retry mechanisms: [list operations]
- Components that should use graceful degradation: [list components]

Logging requirements:
- Key events to log: [list important events]
- Debug information needed: [list debug info]

[Include any specific questions or clarifications needed]

Please help me implement this component following the UV-based structure and project standards, providing:
1. Directory and file structure
2. Implementation code with proper typing and docstrings
3. Error handling with appropriate patterns from ktrdr.errors
4. Consistent logging using the module-level logger
5. Basic tests to validate functionality including error cases
```

### Module Interface Template

```
I'm defining the interface for KTRDR's [Module] according to Task [X.Y].

According to the architecture document:
[paste relevant architectural guidance]

This module should interact with:
[list related modules/components]

Please design a clean, well-typed interface for this module that:
1. Follows Python best practices
2. Includes proper type hints
3. Has comprehensive docstrings
4. Aligns with the architectural principles
```

## Implementation Guidelines

1. **Directory Structure**:
   - Follow the module structure defined in Task 1.1
   - Place code in appropriate modules (data, indicators, fuzzy, neural, visualization, ui)

2. **Code Style**:
   - Use type hints consistently
   - Include comprehensive docstrings
   - Follow PEP 8 conventions

3. **Error Handling**:
   - Import from the `ktrdr.errors` package: exception types, decorators, and utilities
   - Apply the appropriate error handling pattern for each operation type:
     - File operations: Use retry for transient issues and specific error types (DataError)
     - Network operations: Use retry with backoff and handle connection failures
     - Configuration: Use fallbacks where appropriate and validate inputs
   - Always include error codes and contextual details in exceptions
   - Log errors before raising them

4. **Logging**:
   - Create a module-level logger in each file
   - Use appropriate log levels based on the information importance
   - Include relevant context in log messages (IDs, counts, states)
   - Log at entry/exit points of significant operations
   - Add debug logging for detailed troubleshooting information

5. **Testing**:
   - Create tests in the appropriate test directory
   - Include both happy path and error case tests
   - Test error handling and retry mechanisms
   - Verify appropriate log messages are generated

5. **Configuration**:
   - Use YAML-based configuration as defined in Task 1.2
   - Leverage Pydantic for configuration validation

## Error Handling and Logging Standards

### Error Handling Framework

When implementing any component, follow these error handling standards:

1. **Exception Hierarchy**:
   - Use the custom exception hierarchy from `ktrdr.errors` 
   - Choose the appropriate exception type based on the error category:
     - `DataError`: For issues with missing, corrupt, or invalid data
     - `ConnectionError`: For network issues, API timeouts, service unavailability
     - `ConfigurationError`: For invalid settings or configuration problems
     - `ProcessingError`: For calculation failures or unexpected results
     - `SystemError`: For resource limitations, crashes, or environment issues

2. **Error Messages and Context**:
   - Include meaningful error messages with actionable information
   - Use error codes with appropriate prefixes (e.g., "DATA-FileNotFound")
   - Include a `details` dictionary with contextual information
   - Format: `raise ErrorType(message="...", error_code="...", details={...})`

3. **Error Handling Patterns**:
   - **Retry with Backoff**: Apply to network operations or other potentially transient failures
     ```python
     @retry_with_backoff(retryable_exceptions=[ConnectionError], logger=logger)
     def fetch_data(self):
         # Implementation
     ```
   
   - **Graceful Degradation**: For non-critical components that should not fail the entire operation
     ```python
     @fallback(strategy=FallbackStrategy.DEFAULT_VALUE, default_value=[], logger=logger)
     def get_recommendations(self):
         # Implementation
     ```
   
   - **Centralized Error Handling**: For consistent error handling across components
     ```python
     @ErrorHandler.with_error_handling(logger=logger)
     def process_data(self):
         # Implementation
     ```

### Logging Standards

All components must implement logging according to these guidelines:

1. **Logger Setup**:
   - Import the logging system from the main `ktrdr` package:
     ```python
     from ktrdr import get_logger
     
     # Create a module-level logger
     logger = get_logger(__name__)
     ```
   - Do not configure loggers in component code (configuration is handled by the centralized system)

2. **Log Levels**:
   - `DEBUG`: Detailed information for diagnosing problems
   - `INFO`: Confirmation that things are working as expected
   - `WARNING`: Indication that something unexpected happened, but the program can still work
   - `ERROR`: Due to a more serious problem, the software couldn't perform a function
   - `CRITICAL`: A serious error indicating the program may be unable to continue running

3. **Logging Helper Decorators**:
   - Use the provided decorators for common patterns:
     ```python
     from ktrdr import log_entry_exit, log_performance, log_data_operation
     
     @log_entry_exit(log_args=True, log_result=True)
     def important_function(param1, param2):
         # Function code
         
     @log_performance(threshold_ms=100)
     def performance_sensitive_function():
         # Function code
         
     @log_data_operation(operation="load", data_type="price data")
     def load_prices(symbol):
         # Function code
     ```

4. **Context Enrichment**:
   - Use the context enrichment decorator for complex operations:
     ```python
     from ktrdr import with_context
     
     @with_context(operation_name="data_processing", include_args=True)
     def process_data(parameters):
         # Processing code
     ```

5. **Error Logging**:
   - Use the specialized error logging helper:
     ```python
     from ktrdr import log_error
     
     try:
         # Operation code
     except Exception as e:
         log_error(e, include_traceback=True)
         raise
     ```

6. **Debug Mode**:
   - Use the debug mode utilities for conditional verbose logging:
     ```python
     from ktrdr import set_debug_mode, is_debug_mode
     
     # Check if debug mode is enabled
     if is_debug_mode():
         logger.debug("Detailed diagnostic information")
         
     # Enable debug mode for a specific section
     set_debug_mode(True)
     # Operations that need debug logging
     set_debug_mode(False)
     ```

## Security Implementation Standards

When implementing any new component or enhancing existing ones, follow these security standards:

1. **Input Validation**:
   - Always validate user-provided inputs using the `InputValidator` class from `ktrdr.config.validation`
   - Apply appropriate validation rules based on the input type:
     ```python
     from ktrdr.config import InputValidator, sanitize_parameter
     
     # Validate string inputs
     validated_string = InputValidator.validate_string(
         input_string,
         min_length=1,
         max_length=100,
         pattern=r'^[A-Za-z0-9_\-\.]+$'  # Example pattern
     )
     
     # Validate date inputs
     validated_date = InputValidator.validate_date(
         input_date,
         min_date="1900-01-01",
         max_date=None  # No upper limit
     )
     
     # Sanitize path parameters to prevent path traversal
     safe_path = sanitize_parameter("path_param", user_provided_path)
     ```

2. **Path Security**:
   - Sanitize all file paths to prevent path traversal attacks
   - Validate file extensions for uploaded or processed files
   - Use absolute paths when dealing with configuration or data files
   - Example for secure path handling:
     ```python
     from pathlib import Path
     from ktrdr.config import sanitize_parameter
     
     # Convert to absolute path and sanitize
     raw_path = user_input
     safe_path = sanitize_parameter("file_path", raw_path)
     path_obj = Path(safe_path)
     
     # Ensure path is within allowed directories
     allowed_dir = Path("/allowed/directory")
     if not path_obj.is_relative_to(allowed_dir):
         raise SecurityError("Path traversal attempt detected")
     ```

3. **Environment Variable Security**:
   - Validate environment variable names against injection attempts
   - Use pattern matching to ensure only valid characters are used
   - Example:
     ```python
     env_var = InputValidator.validate_string(
         env_var_name,
         pattern=r'^[A-Za-z0-9_]+$'  # Only alphanumeric and underscore
     )
     ```

4. **Error Handling for Security Issues**:
   - Use specific error types for security-related failures
   - Include informative but non-revealing error messages
   - Log security incidents with appropriate severity
   - Example:
     ```python
     try:
         # Operation with security implications
         validated_input = InputValidator.validate_string(user_input)
     except ValidationError as e:
         log_error(e, logger=logger, extra={"security_relevance": "high"})
         raise SecurityError(
             message="Input validation failed",
             error_code="SEC-InputValidation",
             details={"validation_type": "string"}  # Don't include the actual input
         )
     ```

Follow these security guidelines for all new code and when updating existing components, especially those that handle user inputs, file paths, or environment variables.

## Indicator Implementation Guide

When implementing new indicators for the KTRDR system, follow this comprehensive guide to ensure consistent, well-tested, and validated implementations that automatically leverage the enhanced testing framework.

### Indicator Implementation Template

```
I'm implementing a new [INDICATOR NAME] indicator for KTRDR as part of Task [X.Y]. This indicator [brief description of indicator purpose and calculation method].

This technical indicator calculates [specific calculation description]:
[Include mathematical formula or algorithm description]

According to the architecture and the enhanced testing framework from Task 2.6, I need to:
1. Implement the indicator class inheriting from BaseIndicator
2. Add proper parameter validation
3. Create reference data for testing
4. Register the indicator with the validation system

Please help me create a well-structured implementation that:
1. Follows the established indicator pattern
2. Includes comprehensive parameter validation
3. Has optimized calculation logic
4. Integrates with the testing framework from Task 2.6
5. Includes appropriate error handling and logging
```

### Step-by-Step Indicator Implementation Procedure

All indicators should be implemented following these strict steps:

1. **Class Definition**:
   - Create a new class that inherits from `BaseIndicator`
   - Implement `__init__`, `_validate_params`, and `compute` methods
   - Define clear parameter defaults and ranges in `__init__`
   - Use proper typing and comprehensive docstrings

2. **Parameter Validation**:
   - Implement thorough parameter validation in `_validate_params`
   - Check parameter types, ranges, and combinations
   - Use appropriate error types from `ktrdr.errors`
   - Include descriptive error messages with error codes

3. **Computation Implementation**:
   - Use vectorized operations when possible (pandas, numpy)
   - Follow the indicators industry standard calculation methods
   - Include proper error handling for edge cases
   - Add appropriate logging for debugging

4. **Reference Value Creation**:
   - Calculate reference values for standard datasets
   - Include values for different parameter combinations
   - Cover key data patterns (trends, reversals, plateaus)

5. **Testing Integration**:
   - Register the indicator in `tests/indicators/indicator_registry.py`
   - Update reference datasets in `tests/indicators/reference_datasets.py`
   - Define appropriate tolerance values for validation
   - Include specialized edge cases if needed

### Indicator Testing Requirements

Every indicator implementation **MUST** include comprehensive testing that verifies:

1. **Calculation Accuracy**:
   - Test against known reference values
   - Verify behavior with multiple parameter sets
   - Validate across different data patterns

2. **Parameter Validation**:
   - Test with invalid parameter types
   - Test with out-of-range parameters
   - Verify appropriate errors are raised

3. **Edge Case Handling**:
   - Test with insufficient data points
   - Test with constant price values
   - Test with extreme values (zeros, very large numbers)
   - Test with missing values (NaN)

4. **Performance Characteristics**:
   - Verify calculation efficiency for large datasets
   - Test memory usage is appropriate

5. **Auto-Registration**:
   - Verify the indicator works with the automated testing system
   - Confirm it passes all standard indicator tests

### Example Indicator Registration

When registering a new indicator with the testing framework, follow this pattern:

```python
# In tests/indicators/indicator_registry.py:
from ktrdr.indicators import MyNewIndicator

# Register your indicator
register_indicator(
    indicator_class=MyNewIndicator,
    default_params={'period': 14, 'source': 'close'},
    reference_datasets=['reference_dataset_1', 'reference_dataset_2'],
    reference_values=REFERENCE_VALUES.get('MY_INDICATOR', {}),
    tolerance=1.0,  # Appropriate tolerance for your indicator
    known_edge_cases=[
        # Add any indicator-specific edge cases
        {
            'name': 'constant_values',
            'data': pd.DataFrame({'close': [100] * 20}),
            'should_raise': False,
            'expected_values': {14: 50.0}  # Expected output at index 14
        }
    ]
)
```

### Indicator Performance Guidelines

For optimal indicator performance, follow these guidelines:

1. Use vectorized operations with pandas and numpy
2. Minimize loops and iterations
3. Pre-allocate result Series for better performance
4. Consider using numba for computationally intensive calculations
5. Add caching for repeated calculations if appropriate
6. Test with realistic dataset sizes (10,000+ data points)

### Indicator Validation Checklist

Before considering an indicator implementation complete, verify:

- [ ] Indicator class properly inherits from BaseIndicator
- [ ] All required methods are implemented
- [ ] Parameter validation is comprehensive and accurate
- [ ] Calculation logic follows standard definitions
- [ ] Error handling covers edge cases
- [ ] Appropriate logging is included
- [ ] Reference values are provided for testing
- [ ] Indicator is registered with the testing framework
- [ ] All automated tests pass
- [ ] Performance is optimized for large datasets
- [ ] Documentation and docstrings are complete

### Completed Example Documentation

Include the following mandatory information in the indicator class docstring:

```python
class MyNewIndicator(BaseIndicator):
    """
    My New Indicator (MNI) implementation.
    
    This indicator calculates [description of what it does and measures].
    Formula: [Include mathematical formula or algorithm description]
    
    Common uses:
    - [Use case 1]
    - [Use case 2]
    
    Parameters:
        period (int): The lookback period for calculation (default: 14)
        source (str): The price data column to use (default: 'close')
        [any other parameters]
    
    References:
        - [Author/paper that defined the indicator]
        - [Link to industry standard definition]
    
    Notes:
        - [Any implementation notes or limitations]
        - [Performance considerations]
    """
```

Always adhere to this indicator implementation guide when creating new indicators to ensure consistency, correct behavior, and comprehensive testing integration.

## Task Success Criteria

For each implemented task, clearly define and verify the following success criteria:

### Slice 3 - Basic Visualization (v1.0.3)

1. **Task 3.1 - Core Visualization Framework**:
   - Directory structure for visualization module is correctly created
   - `DataAdapter` class successfully transforms DataFrame data to lightweight-charts format
   - Conversion methods for OHLCV, line, and histogram data are implemented
   - `ConfigBuilder` correctly generates chart configuration
   - `TemplateManager` properly handles HTML templates
   - `Renderer` class generates proper HTML/JS output

2. **Task 3.2 - Basic Visualizer API**:
   - `Visualizer` class implements core functionality
   - `create_chart()` method creates a basic chart
   - `add_indicator_overlay()` method adds price-aligned indicators
   - `add_indicator_panel()` method adds separate panels for indicators
   - `save()` method exports charts to HTML files
   - `show()` method displays charts (e.g., in Jupyter notebooks or returned for Streamlit)

3. **Task 3.3 - Essential Chart Types**:
   - Candlestick chart correctly displays price data
   - Line charts properly show indicator overlays
   - Histogram charts successfully visualize volume data
   - Dark/light theme support works correctly
   - Charts maintain proper proportions and layout

4. **Task 3.4 - CLI Enhancement for Visualization**:
   - `plot` command works with indicator options
   - Options to save plots as HTML files function correctly
   - Combined price and indicator plot command works as expected
   - CLI help provides clear guidance on visualization options

5. **Task 3.5 - Visual Testing Framework**:
   - Test fixtures with sample data are created
   - Tests for data transformations validate correct output
   - Tests for HTML/JS generation confirm proper rendering
   - Smoke tests verify basic visualization component functionality
   - Test coverage is comprehensive for core visualization features

When implementing any task, define clear verification steps and include minimal demo code to prove functionality. After implementation, verify all success criteria are met before considering the task complete.

## Task Completion Reporting

At the end of each task implementation, the AI must provide the user with:

1. **Verification Checklist**:
   - A checklist matching the success criteria for the specific task
   - Each item should be actionable and verifiable by running specific commands

2. **Test Instructions**:
   - Step-by-step instructions to verify the implementation works
   - Commands to run to exercise the functionality
   - Expected output of these commands

3. **Self-Contained Example**:
   - A minimal working example showing the implemented feature in action
   - This should be copy-pastable into a temporary Python file for immediate testing
   - Include instructions for cleaning up temporary verification files after testing

4. **Clean-up Instructions**:
   - Clear directions on how to clean up any temporary verification scripts
   - Guidance on what artifacts should be kept as part of the project structure
   - Commands to run for removing temporary testing files

Example completion report for Task 1.2:
```
## Task 1.2 Completion Report

### Implementation Verification Checklist:
- [ ] ConfigLoader class loads YAML files correctly
- [ ] Pydantic models validate configuration against schema
- [ ] Invalid configurations are properly rejected with clear error messages
- [ ] Default values are applied when optional fields are missing

### Testing Steps:
1. Create a test YAML file at `config/test_config.yaml` with sample content
2. Run `python -c "from ktrdr.config import ConfigLoader; config = ConfigLoader().load('config/test_config.yaml'); print(config)"`
3. Try with an invalid config to verify error handling

### Minimal Working Example:
```python
# verification_example.py
from ktrdr.config import ConfigLoader

# Create a simple config loader
config_loader = ConfigLoader()

# Load a config file
try:
    config = config_loader.load('config/settings.yaml')
    print(f"Config loaded successfully: {config}")
    
    # Verify schema validation works
    print(f"Data directory: {config.data.directory}")
except Exception as e:
    print(f"Error handling works: {e}")
```

Run with: `python verification_example.py`
Expected output: Configuration details or appropriate error message
```

The user should be able to follow these instructions to verify the task is successfully completed without having to infer what constitutes success.

## Task Prioritization

When implementing tasks, respect the vertical slice approach:
1. Implement foundation tasks first (1.x)
2. Move to data management and indicators (2.x)
3. Add visualization components (3.x)
4. Implement fuzzy logic (4.x)
5. Build the UI foundation (5.x)
6. Add IB integration (6.x)
7. Implement neural components (7.x)
8. Add decision logic and backtesting (8.x)

## Example Usage

When the user types:
```
Use the prompting guide and task list, generate a prompt for task 1.2 and implement it
```

The AI should:
1. Look up Task 1.2 in the task breakdown document
2. Find relevant architectural guidance
3. Generate a prompt following the template above
4. Proceed with implementation
5. **Always conclude with a complete Task Completion Report** including verification checklist, testing steps, and minimal working example

## Verification-First Implementation

A critical part of the AI Director's role is to ensure all tasks are properly verified and wrapped up. To achieve this, always follow the "Verification-First" approach:

1. **Begin With The End In Mind**: 
   - When starting any task, first identify all success criteria that will need to be verified
   - Design verification tests BEFORE writing implementation code
   - Create a draft verification checklist at the beginning of development

2. **Integrated Verification**:
   - While implementing, continuously update the verification checklist
   - Write test cases alongside implementation code
   - Keep track of clean-up steps that will be needed

3. **Comprehensive Task Completion**:
   - NEVER consider a task complete without the full Task Completion Report
   - ALL FOUR elements must be present (Verification Checklist, Testing Steps, Working Example, Clean-up Instructions)
   - The verification must be concrete and actionable (specific commands to run)

4. **Reference Documentation**:
   - Always refer to `specification/task_completion_checklist.md` for the complete verification requirements
   - Use the checklist to validate that your Task Completion Report is complete
   - The task is not complete until all items in the checklist are addressed

As a critical implementation rule, the AI must ALWAYS reserve sufficient context for including the complete Task Completion Report at the end of each implementation. This is a non-negotiable requirement.

## Mandatory Implementation Requirements

Every task implementation **must** include the following elements regardless of task complexity:

1. **Complete implementation** of all subtasks specified in the task breakdown
2. **Working tests** that validate the implementation
3. **Clear documentation** with docstrings and comments
4. **A comprehensive Task Completion Report** that contains:
   - Detailed verification checklist matching the task's success criteria
   - Concrete testing steps with exact commands to run
   - Expected output for each testing step
   - A self-contained example that proves the functionality works
   - Clean-up instructions for temporary verification scripts
   - Any additional troubleshooting guidance
5. **Update the task checkboxes** in the task breakdown document to mark the task and all subtasks as completed

After implementation and verification, the AI should provide instructions to update the task breakdown document, changing the task status from:
```markdown
- [ ] **Task X.Y**: Task name
  - [ ] Subtask 1
  - [ ] Subtask 2
```

to:
```markdown
- [x] **Task X.Y**: Task name
  - [x] Subtask 1
  - [x] Subtask 2
```

The implementation is not considered complete until the user can successfully verify all functionality using the provided Task Completion Report and the task checkboxes have been updated in the task breakdown document.

## Implementation Checklist

Before submitting a task implementation, verify:

### Error Handling
- [ ] All public methods use appropriate error types from the `ktrdr.errors` package
- [ ] Error messages are clear and actionable
- [ ] Error codes follow the established format (CATEGORY-ErrorName)
- [ ] Detailed context is included in the `details` dictionary
- [ ] Retry mechanisms are applied to appropriate operations
- [ ] Fallback strategies are implemented for non-critical functions

### Logging
- [ ] Module-level logger is defined and used consistently
- [ ] Appropriate log levels are used for different information
- [ ] Log messages include relevant context
- [ ] Entry/exit logs for significant operations
- [ ] Errors are logged before being raised
- [ ] No sensitive information is logged (credentials, tokens)

### Security
- [ ] All user inputs are validated using `InputValidator` utilities
- [ ] String inputs are validated with appropriate patterns, min/max lengths
- [ ] Numerical inputs have proper range validation
- [ ] Date inputs are validated with appropriate range checks
- [ ] File paths are sanitized to prevent path traversal attacks
- [ ] Environment variable names are validated against injection
- [ ] Security-related errors are logged with high severity
- [ ] Security errors provide informative but non-revealing messages
- [ ] No sensitive information is included in error details
- [ ] Credentials are loaded from secure sources (environment variables)
- [ ] No hardcoded secrets or credentials in the code
- [ ] File operations are restricted to allowed directories
- [ ] Security-sensitive operations have appropriate access controls
