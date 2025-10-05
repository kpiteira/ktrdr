# Training Service Unified Architecture Documentation

**Last Updated**: 2025-01-05
**Status**: Design Phase - Awaiting Approval

---

## Document Structure

This directory contains the complete architectural analysis, requirements, and design for the unified training service refactor.

### Documents

1. **[01-analysis.md](./01-analysis.md)** - Problem Analysis
   - Four critical issues identified
   - Current state analysis
   - Root cause investigation
   - Technical findings

2. **[02-requirements.md](./02-requirements.md)** - Requirements Definition
   - R1: Unified Training Executor
   - R2: Logging Standardization and Quality
   - R3: Runtime Execution Mode Selection
   - R4: Model Persistence & Result Transfer
   - Success criteria and open questions

3. **[03-architecture.md](./03-architecture.md)** - Architecture Design
   - Component diagrams
   - Execution flows
   - API endpoints
   - File structure
   - Data flow diagrams

4. **Implementation Plan** (TBD)
   - Created after architecture approval
   - Phased implementation
   - Testing strategy
   - Migration plan

---

## Quick Summary

### The Problem

1. **Code Duplication**: Backend and host service have 80% duplicate training logic
2. **Model Persistence Failure**: Host service training succeeds but models not saved
3. **Logging Quality**: Host service logs less structured than backend
4. **Rigid Service Selection**: No runtime override or fallback

### The Solution

1. **Unified TrainingExecutor**: Single source of truth for training logic
2. **Result Transfer**: Host service POSTs trained models back to backend
3. **Quality Logging**: Numbered steps and hierarchy in all modes
4. **Flexible Mode Selection**: Runtime override with intelligent fallback

### Key Design Decisions

- ✅ TrainingExecutor is synchronous (correct current pattern)
- ✅ Backend is source of truth for model storage
- ✅ Host service POSTs results via HTTP callback
- ✅ Execution mode selectable per-request with fallback
- ✅ Maintain backend's structured logging quality

---

## Current Status

### Completed
- ✅ Problem analysis
- ✅ Requirements definition
- ✅ Architecture design

### Pending Approval
- ⏳ All three documents need review
- ⏳ Open questions in requirements need answers
- ⏳ Architecture design needs validation

### Next Steps
1. Review and approve all three documents
2. Answer open questions in requirements
3. Create detailed implementation plan
4. Begin phased implementation

---

## Open Questions

From [02-requirements.md](./02-requirements.md):

**Q1: Progress Callback Interface**
- Proposed separation of logging and progress tracking
- Need confirmation on interface design

**Q2: Error Handling for Result Posting**
- What happens if POST to backend fails?
- Retry strategy needed

**Q3: Model Size Limits**
- HTTP payload size considerations
- Compression strategy

---

## Related Files

### Current Implementation

**Backend**:
- [ktrdr/training/train_strategy.py](../../../ktrdr/training/train_strategy.py) - Backend training logic
- [ktrdr/training/training_manager.py](../../../ktrdr/training/training_manager.py) - Training orchestration
- [ktrdr/api/services/training_service.py](../../../ktrdr/api/services/training_service.py) - Training API service

**Host Service**:
- [training-host-service/services/training_service.py](../../../training-host-service/services/training_service.py) - Host training logic

### Will Be Created

- `ktrdr/training/executor.py` - NEW unified training core
- `ktrdr/training/execution_mode_selector.py` - NEW mode selection logic

---

## Metrics

### Code Reduction

**Before**:
- Backend: ~1,500 lines (train_strategy.py)
- Host Service: ~1,000 lines (training_service.py)
- **Total**: ~2,500 lines (with duplication)

**After**:
- Unified Executor: ~1,200 lines (executor.py)
- Mode Selector: ~150 lines (execution_mode_selector.py)
- Updated Backend: ~300 lines (refactored train_strategy.py)
- Updated Host Service: ~200 lines (refactored training_service.py)
- **Total**: ~1,850 lines (no duplication)

**Savings**: ~650 lines (~26% reduction)

### Expected Benefits

- ✅ Single point of maintenance for training logic
- ✅ Consistent behavior across execution modes
- ✅ Models saved correctly in both modes
- ✅ Better logging quality everywhere
- ✅ Flexible runtime mode selection
- ✅ Automatic fallback on failure

---

**Contact**: Karl (Product Owner)
**Author**: Claude (AI Assistant)
