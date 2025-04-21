# Effective AI Prompting Strategy for KTRDR Implementation

To maximize the effectiveness of AI coding assistance while keeping context window costs manageable, I recommend the following structured approach:

## Initial Context Setting

Begin with a focused introduction that provides just enough context:

```
I'm building KTRDR, a trading system with a neuro-fuzzy decision engine following my architecture blueprint and task breakdown. For this session, I'd like to implement [specific component/task].
```

## Document Reference Strategy

Rather than pasting entire documents, use this approach:

1. **Reference documents by name**:
   ```
   The implementation should follow the architecture in ktrdr-architecture-blueprint.md and detailed tasks in ktrdr_phase1_task_breakdown.md.
   ```

2. **Provide targeted excerpts**:
   ```
   For this task, the relevant architecture section states:
   [paste only the 5-10 lines that are directly relevant]
   
   And the specific subtasks are:
   [paste only the immediate subtasks]
   ```

3. **Use "load more if needed" approach**:
   ```
   Let me know if you need more details from any specific document section.
   ```

## Task-Based Implementation

Structure your coding sessions by discrete tasks:

1. **Focus on one component at a time**:
   ```
   Let's implement the [specific component] which handles [specific responsibility].
   ```

2. **Start with interfaces before implementation**:
   ```
   First, let's define the interface for this component based on the architecture.
   ```

3. **Implement in logical chunks**:
   ```
   Now let's implement the core logic for [specific functionality].
   ```

## Example Effective Prompt

Here's a complete example of an effective prompt:

```
I'm implementing the DataManager component of KTRDR following my architecture blueprint. Let's focus on tasks 1.2.3.1-1.2.3.4.

The architecture describes DataManager as:
"Orchestrates data loading, gap detection, and intelligent fetching between local and remote sources"

The specific subtasks are:
- Task 1.2.3.1: Create DataManager class with constructor accepting config parameters (data_dir, default_assets)
- Task 1.2.3.2: Implement load() method that accepts symbol, asset_type, interval, start_date, end_date parameters
- Task 1.2.3.3: Add logic to check for local data first using LocalDataLoader
- Task 1.2.3.4: Implement gap detection algorithm to identify missing date ranges in local data

Please implement these components following the project structure defined in my architecture document, with proper type hints and docstrings.
```

## Progressive Implementation

For complex components, break implementation into multiple sessions:

1. **Session 1**: Define interfaces and basic structure
2. **Session 2**: Implement core logic
3. **Session 3**: Add error handling and edge cases
4. **Session 4**: Write tests

This approach keeps each interaction focused and minimizes context window usage while still producing high-quality code that aligns with your architecture.

## Reference Existing Code

When building upon previous work:

```
I've already implemented the LocalDataLoader and IBDataLoader components. Here are their interfaces:

[paste minimal interface code]

Now I want to implement the DataManager that will use these loaders.
```

By following this structured approach, you'll get the most value from AI coding assistance while keeping costs manageable and ensuring alignment with your architecture and task breakdown.