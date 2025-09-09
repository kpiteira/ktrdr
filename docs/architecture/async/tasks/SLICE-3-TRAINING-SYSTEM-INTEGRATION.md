# SLICE 3: TRAINING SERVICEORCHESTRATOR INTEGRATION

**Branch**: `slice-3-training-serviceorchestrator-integration`
**Goal**: Make TrainingManager inherit ServiceOrchestrator to provide structured progress information like DataManager
**Priority**: High
**Depends on**: Slice 1 and 2 completion

## Overview

This slice makes TrainingManager inherit from ServiceOrchestrator, following the same pattern as DataManager. This provides training operations with structured progress information and eliminates the complex string parsing in CLI commands.

**KEY INSIGHT**: The CLI progress issue isn't the polling mechanism - both data and training CLI poll the operations API. The issue is that training operations don't use ServiceOrchestrator to provide structured progress information.

**Current Problem**: Training CLI has 50+ lines of brittle string parsing (async_model_commands.py:424-512) because TrainingManager doesn't provide structured progress context.

**CRITICAL CANCELLATION ISSUE**: Training operations continue running even after cancellation requests because cancellation tokens aren't passed through to the actual training loops. This wastes resources and prevents new operations.

**Solution**: Make TrainingManager inherit ServiceOrchestrator like DataManager does, AND establish complete cancellation flow through all training layers.

## Success Criteria

- [ ] TrainingManager inherits ServiceOrchestrator[TrainingAdapter]
- [ ] TrainingProgressRenderer provides training-specific progress context  
- [ ] Training operations provide structured progress (no more string parsing needed)
- [ ] Training CLI progress quality matches data loading CLI progress
- [ ] ALL existing training functionality preserved
- [ ] **CRITICAL**: Complete cancellation flow implemented through all training layers
- [ ] **CRITICAL**: Training can be cancelled effectively without performance degradation

## Current Architecture Issue

**DataManager (works well)**:
- Inherits ServiceOrchestrator → structured progress via operations API
- CLI gets clean progress context → simple display logic

**TrainingManager (the problem)**:
- Doesn't inherit ServiceOrchestrator → basic progress info
- CLI gets unstructured strings → complex parsing logic (50+ lines)

## Tasks

### Task 3.1: Make TrainingManager Inherit ServiceOrchestrator

**Description**: Update TrainingManager to inherit ServiceOrchestrator[TrainingAdapter], following the exact same pattern as DataManager.

**Why this is needed**: Currently TrainingManager doesn't inherit ServiceOrchestrator, so it can't provide structured progress information like DataManager does. The CLI has to parse complex strings instead of using clean structured data.

**What this provides**:
- Automatic `execute_with_progress()` and `execute_with_cancellation()` methods
- Structured progress registration with operations API
- Environment variable configuration (USE_TRAINING_HOST_SERVICE) 
- Same async patterns as DataManager

**CRITICAL: Cancellation Flow Issue**: Currently training operations don't receive cancellation tokens, so they continue running even after cancellation requests. This task must establish the cancellation pipeline from TrainingManager → TrainingAdapter → LocalTrainer/HostService.

**Implementation approach**:
```python
# Current: TrainingManager is a plain class
class TrainingManager:
    def __init__(self):
        self.training_adapter = self._initialize_training_adapter()

# After: TrainingManager inherits ServiceOrchestrator like DataManager
class TrainingManager(ServiceOrchestrator[TrainingAdapter]):
    def _initialize_adapter(self) -> TrainingAdapter:
        # Same logic as current constructor
        return TrainingAdapter(...)
    
    async def train_multi_symbol_strategy(self, ...):
        # NOW passes cancellation_token like DataManager does
        return await self.training_adapter.train_multi_symbol_strategy(
            ...,
            cancellation_token=self.get_current_cancellation_token()
        )
```

**Acceptance Criteria**:
- [ ] TrainingManager inherits ServiceOrchestrator[TrainingAdapter]
- [ ] All existing methods preserved and functional
- [ ] Environment configuration maintained (USE_TRAINING_HOST_SERVICE)
- [ ] TrainingManager gets ServiceOrchestrator capabilities automatically
- [ ] Same pattern as DataManager (consistency)
- [ ] **CRITICAL**: Cancellation token passed to TrainingAdapter

---

### Task 3.2: Create TrainingProgressRenderer

**Description**: Create TrainingProgressRenderer following the DataProgressRenderer pattern from Slice 1 to provide structured progress context for training operations.

**Why this is needed**: Training operations need to provide structured progress context so the CLI can display meaningful information instead of parsing complex strings like "Epoch: 15, Bars: 342/500 (Val Acc: 0.123)".

**Architecture Decision**: Unlike data operations, training operations are simpler - TrainingManager delegates work in one block to TrainingAdapter. No job orchestration layer (TrainingJobManager/TrainingJob) is needed because training doesn't involve complex multi-step operations like data loading does.

**Purpose**: Format training progress with proper context instead of relying on brittle string parsing in CLI.

**Progress format examples**:
- Single symbol: "Training MLP model on AAPL [1H] [epoch 15/50] (batch 342/500) [2/4]"
- Multi-symbol: "Training MLP model on AAPL, MSFT (+2 more) [1H, 4H] [epoch 15/50] [3/4]"
- Different models: "Training CNN model on TSLA [5m] [epoch 8/20] (batch 156/800) [1/4]"

**Context provided**:
- Model type (MLP, CNN, LSTM, etc.) - extracted from strategy config
- Symbols being trained (with smart truncation for readability)
- Timeframes (with smart truncation for readability)
- Epoch progress (coarse-grained) - current/total epochs
- Batch progress (fine-grained) - current/total batches within epoch  
- Step progress from ServiceOrchestrator - overall operation steps

**How it works**:
```python
# ServiceOrchestrator calls renderer with context
context = {
    'model_type': 'mlp',
    'symbols': ['AAPL', 'MSFT', 'TSLA'],
    'timeframes': ['1H', '4H'],
    'current_epoch': 15,
    'total_epochs': 50,
    'current_batch': 342,
    'total_batches': 500
}
# Renderer formats: "Training MLP model on AAPL, MSFT (+1 more) [1H, 4H] [epoch 15/50] (batch 342/500)"
```

**Acceptance Criteria**:
- [ ] TrainingProgressRenderer extends ProgressRenderer interface
- [ ] Renders training context clearly and consistently
- [ ] Handles multi-symbol/timeframe scenarios with truncation
- [ ] Provides both coarse (epoch) and fine (batch) progress
- [ ] Context includes model type, symbols, timeframes, epochs, batches

---

### Task 3.3: Implement Deep Cancellation Flow for Training Operations

**Description**: Establish complete cancellation token flow from TrainingAdapter through LocalTrainer and HostService to the actual training loops, ensuring training can be cancelled effectively.

**CRITICAL ISSUE**: Currently training operations continue running even after cancellation because:

1. **Local Training**: `model_trainer.py` has progress callbacks but NO cancellation checking in training loops
2. **Host Service Training**: TrainingAdapter doesn't pass cancellation context to host service
3. **Performance Impact**: Need efficient cancellation checks that don't slow down training

**Why this is critical**: Training operations can run for hours. Without proper cancellation flow, cancelled training continues consuming resources and prevents new operations.

**Implementation Strategy - Following Data Pattern**:

**1. TrainingAdapter Cancellation Handling**:
```python
# TrainingAdapter.train_multi_symbol_strategy() - ADD cancellation_token parameter
async def train_multi_symbol_strategy(self, ..., cancellation_token=None):
    if self.use_host_service:
        # Pass cancellation context to host service (like data does)
        response = await self._call_host_service_post("/training/start", {
            ...,
            "cancellation_context": {
                "cancellation_token_id": id(cancellation_token) if cancellation_token else None
            }
        })
    else:
        # Pass to local trainer
        return self.local_trainer.train_multi_symbol_strategy(
            ..., 
            cancellation_token=cancellation_token
        )
```

**2. Local Training Cancellation Checks**:
```python
# model_trainer.py - Add efficient cancellation checks
def _check_cancellation(self, cancellation_token, operation="training"):
    """Check cancellation efficiently (same pattern as data)."""
    if cancellation_token is None:
        return False
    
    # Same logic as DataManager._check_cancellation()
    is_cancelled = False
    if hasattr(cancellation_token, "is_cancelled_requested"):
        is_cancelled = cancellation_token.is_cancelled_requested
    # ... handle other token types
    
    if is_cancelled:
        raise asyncio.CancelledError(f"Training cancelled during {operation}")

# Training loop modifications
def train(self, ...):
    for epoch in range(epochs):
        # Check cancellation at epoch boundaries (low overhead)
        self._check_cancellation(self.cancellation_token, f"epoch {epoch}")
        
        for batch_idx, batch in enumerate(train_loader):
            # Check cancellation every 50 batches (balance performance vs responsiveness)
            if batch_idx % 50 == 0:
                self._check_cancellation(self.cancellation_token, f"epoch {epoch}, batch {batch_idx}")
```

**3. Host Service Cancellation Support**:
```python
# Host service should accept cancellation context and check regularly
# This requires host service API changes to support cancellation
```

**Performance Considerations**:
- **Epoch-level checks**: Always check at epoch boundaries (minimal overhead)
- **Batch-level checks**: Check every 50 batches (balanced approach)
- **Avoid checking every batch**: Too much overhead for high-frequency operations
- **Match with progress updates**: Check cancellation when updating progress (efficient)

**Acceptance Criteria**:
- [ ] TrainingAdapter accepts and forwards cancellation_token parameter
- [ ] Local training (model_trainer.py) implements efficient cancellation checking
- [ ] Cancellation checks at epoch boundaries (minimal overhead)  
- [ ] Cancellation checks every 50 batches (balanced performance/responsiveness)
- [ ] Host service training accepts cancellation context
- [ ] Training operations can be cancelled effectively without excessive performance impact
- [ ] Same cancellation pattern as data operations (consistency)
- [ ] CancelledError properly raised and handled

---

### Task 3.4: Simplify CLI Training Progress Parsing

**Description**: Replace the complex string parsing in CLI training commands with structured progress data usage.

**Current problem**: The CLI has 50+ lines of brittle string parsing (async_model_commands.py:424-512) that tries to extract progress information from strings like:
```
"Epoch: 15, Bars: 342/500 (Val Acc: 0.123)"
```

This parsing is fragile and breaks when the string format changes. It also requires complex regex and error handling.

**Root cause**: TrainingManager doesn't provide structured progress context, so the CLI has to parse strings.

**After fix**: Use clean structured context from ServiceOrchestrator:
```python
# BEFORE: Complex string parsing (50+ lines)
if current_step and "Epoch:" in current_step and "Bars:" in current_step:
    try:
        epoch_part = current_step.split("Epoch:")[1].split(",")[0].strip()
        current_epoch = int(epoch_part)
        bars_part = current_step.split("Bars:")[1].strip()
        if bars_part and "(" in bars_part:
            bars_part = bars_part.split("(")[0].strip()
        # ... 40+ more lines of parsing logic
    except (IndexError, ValueError, ZeroDivisionError):
        current_epoch = 0

# AFTER: Clean structured data (5 lines)
context = progress_info.get("context", {})
current_epoch = context.get('current_epoch', 0)
total_epochs = context.get('total_epochs', 0)
current_batch = context.get('current_batch', 0)
total_batches = context.get('total_batches', 0)
```

**Benefits**:
- Remove 50+ lines of complex, brittle parsing code
- More reliable progress display (no parsing errors)
- Consistent with data loading CLI approach
- Easier to maintain and extend
- Better error handling (no parsing failures)

**Implementation approach**:
1. Remove string parsing logic from CLI training commands
2. Use structured context from operations API
3. Format progress display using clean structured data
4. Test that progress display is more reliable

**Acceptance Criteria**:
- [ ] Remove complex string parsing from CLI training commands (lines 424-512)
- [ ] Use structured progress context from ServiceOrchestrator operations
- [ ] Training progress display more reliable and consistent
- [ ] CLI training progress quality matches data loading CLI
- [ ] No more parsing errors or edge case failures

---

### Task 3.5: Validate Complete Integration

**Description**: Comprehensive testing that training operations now work exactly like data operations through ServiceOrchestrator integration.

**Why this validation is critical**: This slice makes fundamental changes to how training operations work. We need to ensure that:
1. Nothing breaks (regression testing)
2. Training gets the same quality as data operations (enhancement testing)
3. The CLI improvements actually work (integration testing)
4. Both systems use identical patterns (consistency testing)
5. **CRITICAL**: Cancellation actually works and doesn't break training performance

**Validation focus**:
- **Functional validation**: Training operations provide structured progress like data operations
- **CLI validation**: Training commands show enhanced, reliable progress without parsing errors
- **Regression validation**: All existing training functionality preserved exactly
- **Pattern validation**: ServiceOrchestrator patterns working correctly for training
- **Integration validation**: Training operations integrate properly with operations API
- **Cancellation validation**: Training can be cancelled effectively without performance degradation

**Testing strategy**:
1. **Regression testing**: All existing training tests pass without modification
2. **Enhancement testing**: Training progress structured and consistent like data loading
3. **CLI improvement testing**: Progress parsing simplified and more reliable than before
4. **Consistency testing**: Training and data operations use identical ServiceOrchestrator patterns
5. **Integration testing**: Training operations work properly with operations API and CLI

**What success looks like**:
- Training CLI commands work exactly like data CLI commands
- Progress display is consistent between training and data operations
- No more complex string parsing errors in training CLI
- Training operations get automatic cancellation support
- Both DataManager and TrainingManager follow identical patterns

**Acceptance Criteria**:
- [ ] All existing training tests pass (100% regression compatibility)
- [ ] Training progress quality matches data loading progress quality
- [ ] CLI training commands enhanced and more reliable than before
- [ ] Training and data systems use identical ServiceOrchestrator patterns
- [ ] Training operations integrate properly with operations API framework
- [ ] Progress context provides rich training information (epochs, batches, symbols, timeframes)
- [ ] **CRITICAL**: Training cancellation works reliably for both local and host service modes
- [ ] **CRITICAL**: Cancellation checks don't degrade training performance significantly (<5% impact)
- [ ] **CRITICAL**: Cancelled training stops within reasonable time (epoch boundary or 50 batches)

## Architecture Consistency Analysis

**Current Architecture Status:**

**Data (complex multi-step pattern):**
```
DataManager (ServiceOrchestrator)
    ↓ (handles complex logic - validation, gap detection, quality checks)
IbDataAdapter (routes: local IB vs host service)
    ↓ (multiple calls for data chunks)
DataJobManager (job orchestration for complex operations)
    ↓
DataLoadingJob (individual chunk jobs)
```

**Training (simple delegation pattern):**
```
TrainingManager 
    ↓ (simple pass-through delegation)
TrainingAdapter (routes: local training vs host service)
    ↓ (single block operation - trains entire model)
[Local Training OR Host Service - handles all complexity internally]
```

**Key Insight**: Training operations are fundamentally simpler than data operations. Training delegates work "in 1 block" to the adapter, while data loading involves complex logic with "multiple" chunk operations.

**Why training doesn't need job orchestration:**

- **Simple delegation**: TrainingManager just passes parameters to TrainingAdapter
- **Single operation**: Training happens as one atomic operation in adapter
- **No chunking**: Unlike data loading, training doesn't break work into multiple jobs
- **Adapter handles complexity**: Whether local or host service, training complexity is encapsulated

**Training Architecture Should Remain Simple:**

```text
TrainingManager (ServiceOrchestrator after Slice 3)
    ↓ (simple parameter passing)
TrainingAdapter (routes: local training vs host service)
    ↓ (single atomic training operation)
[Training Implementation - handles all training complexity]
```

**Slice 3 Scope**: Add ServiceOrchestrator inheritance for structured progress, but keep the simple delegation pattern appropriate for training operations.

## Expected Outcome

**Before Slice 3**:

- Training CLI: Complex string parsing, brittle progress display
- Training operations: Basic progress info via operations API
- Architecture: DataManager uses ServiceOrchestrator, TrainingManager doesn't

**After Slice 3**:

- Training CLI: Clean structured data usage, reliable progress display  
- Training operations: Rich structured progress via ServiceOrchestrator
- Architecture: Both DataManager and TrainingManager use ServiceOrchestrator patterns

**User benefit**: Training commands show progress like data commands - clear, consistent, reliable.

## Integration Points

**Slice 4 Integration Readiness**:

- TrainingManager ready for AsyncServiceAdapter integration
- ServiceOrchestrator patterns established across both systems
- Unified async infrastructure foundation complete
