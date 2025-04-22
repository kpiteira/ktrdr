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

[Include any specific questions or clarifications needed]

Please help me implement this component following the UV-based structure and project standards, providing:
1. Directory and file structure
2. Implementation code with proper typing and docstrings
3. Basic tests to validate functionality
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
   - Use the custom exception hierarchy defined in Task 1.4
   - Add appropriate error handling for expected failure conditions

4. **Testing**:
   - Create tests in the appropriate test directory
   - Include both happy path and error case tests

5. **Configuration**:
   - Use YAML-based configuration as defined in Task 1.2
   - Leverage Pydantic for configuration validation

## Task Success Criteria

For each implemented task, clearly define and verify the following success criteria:

1. **Task 1.1 - Project Structure**:
   - Directory structure matches the requirements
   - pyproject.toml contains all required dependencies
   - All __init__.py files are in place with correct imports
   - .gitignore includes standard Python patterns
   - UV setup script successfully creates virtual environment

2. **Task 1.2 - Configuration Framework**:
   - YAML structure correctly loads configuration files
   - ConfigLoader properly validates against schema
   - Pydantic models enforce required fields
   - Validation errors are properly handled

3. **Task 1.3 - LocalDataLoader**:
   - Successfully loads CSV data from specified directory
   - Handles missing/corrupt files gracefully
   - Enforces correct data format
   - Data saving works correctly

4. **Task 1.4 - Error Handling Framework**:
   - Custom exception hierarchy is well-organized
   - Error handler classifies errors properly
   - User-friendly error messages generated
   - Retry mechanism works for network operations

5. **Task 1.5 - Logging System**:
   - Logs to both console and file
   - Enriches entries with context information
   - Rotating file handler works as expected
   - Debug flag controls verbose output

6. **Task 1.6 - Security Measures**:
   - Credentials load securely from environment
   - Input validation prevents invalid data
   - Sensitive files excluded via .gitignore
   - Credential loading utility works

7. **Task 1.7 - Testing Infrastructure**:
   - pytest finds and runs all tests
   - Test fixtures load test data correctly
   - All tests pass

8. **Task 1.8 - CLI Implementation**:
   - Typer framework generates help text
   - show-data command displays formatted output
   - Parameter validation prevents errors

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
