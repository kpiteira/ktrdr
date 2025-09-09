# TASK CORRECTIONS SUMMARY

Based on code analysis and feedback, the following critical corrections need to be made to the task files:

## 1. Branch Strategy and PR Workflow

**Each slice needs:**
- **Branch**: `slice-N-descriptive-name` (e.g., `slice-1-generic-progress-foundation`)
- **Draft PR**: Created at start of slice for continuous review
- **Commit Strategy**: Each task commits with comprehensive testing
- **Merge Strategy**: Branch merged at end of slice after validation

## 2. Current Architecture Understanding

### AsyncHostService
- **Current Purpose**: Base class for ADAPTERS (IbDataAdapter, TrainingAdapter)
- **Current Location**: `ktrdr/managers/async_host_service.py`
- **Current Usage**: Adapters inherit from it for host service communication
- **Correction**: Slice 5 should enhance existing adapter base class, not create host service infrastructure

### ProgressManager
- **Current State**: Already exists as component in `ktrdr/data/components/progress_manager.py`
- **Current Issues**: Contains domain-specific logic (time estimation, data-specific fields)
- **Integration**: DataManager already uses it via builder pattern
- **Correction**: Need to extract generic parts and create domain renderers for existing component

### DataManager Architecture
- **Current State**: Uses builder pattern with components:
  - `DataFetcher` for async data retrieval
  - `ProgressManager` for progress tracking
  - `DataQualityValidator` for validation
- **Integration Point**: Need to integrate generic async at the builder/component level, not replace

### CLI Progress
- **Current State**: Rich progress displays in `ktrdr/cli/progress.py`
- **Training Gap**: Training commands may not show progress or support cancellation
- **Correction**: Need to ensure CLI integration with new async infrastructure

## 3. Critical Task Updates Required

### Slice 1: Generic Progress Foundation
- **CORRECT**: Work with existing ProgressManager component
- **CORRECT**: Create domain renderers, don't replace existing progress system
- **ADD**: Cleanup task to remove domain-specific logic from existing ProgressManager
- **ADD**: Comprehensive testing including all existing tests + make quality

### Slice 2: Cancellation System
- **CORRECT**: Integrate with DataManager's component architecture
- **ADD**: CLI compatibility requirements (maintain existing CLI progress)
- **ADD**: Cleanup existing cancellation patterns

### Slice 3: Orchestration Framework
- **CORRECT**: Work through DataManager's builder pattern
- **ADD**: Integration with existing component architecture
- **ADD**: Cleanup redundant orchestration code

### Slice 4: Training System Integration
- **ADD**: CLI progress and cancellation for training commands (currently missing)
- **CORRECT**: Training system needs new progress/cancellation (not just backend)
- **ADD**: Training CLI command updates

### Slice 5: Host Service Integration
- **CORRECT**: Enhance existing AsyncHostService base class for adapters
- **CORRECT**: Focus on adapter patterns, not host service infrastructure
- **CLARIFY**: This improves IbDataAdapter/TrainingAdapter communication, not host services themselves

## 4. Testing Requirements for All Tasks

**Each task must:**
- Run complete test suite: `make test` (not just new tests)
- Pass all quality checks: `make quality` 
- Maintain 100% backward compatibility
- Performance regression testing
- Integration testing with CLI

## 5. CLI Compatibility Strategy

**For Slices 1-3:**
- Maintain existing CLI progress displays
- Enhance backend with new async infrastructure
- CLI should automatically benefit from backend improvements
- No breaking changes to CLI commands or interfaces

## 6. Cleanup Tasks Required

**Each slice needs cleanup task:**
- **Slice 1**: Remove domain-specific logic from existing ProgressManager
- **Slice 2**: Remove redundant cancellation patterns
- **Slice 3**: Remove duplicate orchestration code
- **Post-implementation**: Archive legacy patterns

## 7. Integration Points Corrections

### DataManager Integration
- Work through existing builder pattern
- Enhance existing components (don't replace)
- Integrate at component initialization level
- Maintain existing public API

### Component Architecture
```
DataManager (ServiceOrchestrator)
├── DataManagerBuilder (enhanced with async components)
├── DataFetcher (enhanced with orchestration)
├── ProgressManager (made generic with domain renderer)
├── DataQualityValidator (integrated with cancellation)
└── IbDataAdapter (enhanced AsyncHostService)
```

## 8. Next Steps

1. **Update all slice task files** with these corrections
2. **Add branch strategy** and PR workflow to each slice
3. **Add comprehensive testing** requirements to each task
4. **Add cleanup tasks** for existing code removal
5. **Clarify CLI integration** strategy for each slice
6. **Fix markdown linting** issues in all files

This ensures the task files accurately reflect the current architecture and provide implementable, safe migration paths.