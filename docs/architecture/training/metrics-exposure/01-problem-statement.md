# Training Metrics Exposure for Agent Decision Making: Problem Statement

**Date**: 2025-01-17
**Status**: Draft - Design Phase
**Related**: Training Progress Infrastructure, MCP Integration

---

## Executive Summary

Currently, training operations report real-time progress (epoch, batch, percentage complete) but **do not expose historical training metrics** that would enable AI agents to make intelligent decisions about whether training is progressing effectively. Agents need access to loss trends, accuracy curves, and diagnostic signals to determine if training should continue, be stopped early, or be reconfigured.

This creates a situation where agents can **see** that training is happening but cannot **assess** if it's working.

---

## Current Behavior

### What's Available Now

**Via Progress API** (`GET /operations/{operation_id}`):
```json
{
  "progress": {
    "percentage": 65.0,
    "current_step": "Epoch 65/100",
    "context": {
      "epoch_index": 65,
      "total_epochs": 100,
      "epoch_metrics": {
        "train_loss": 0.4235,
        "val_loss": 0.5123,
        "train_accuracy": 0.82,
        "val_accuracy": 0.75
      }
    }
  }
}
```

**What Agents Can See:**
- ✅ Current epoch number
- ✅ Current train_loss (single value)
- ✅ Current val_loss (single value)
- ✅ Current accuracies

**What Agents CANNOT See:**
- ❌ **Historical loss values** (all previous epochs)
- ❌ **Loss trends** (is it improving, plateauing, diverging?)
- ❌ **Best epoch so far** (which epoch had lowest val_loss?)
- ❌ **Overfitting signals** (train_loss ↓ but val_loss ↑)
- ❌ **Learning dynamics** (learning rate changes, gradient health)
- ❌ **Early stopping readiness** (how many epochs without improvement?)

---

## The Problem

### Scenario: Agent Monitoring Training

**User Request**: "Train this model and let me know if it's learning properly"

**What Currently Happens:**

```
Agent polls /operations/{op_id} every 30 seconds:

Poll 1 (Epoch 10): train_loss=0.8234, val_loss=0.8912
Poll 2 (Epoch 20): train_loss=0.6543, val_loss=0.7234
Poll 3 (Epoch 30): train_loss=0.5123, val_loss=0.6789
Poll 4 (Epoch 40): train_loss=0.4567, val_loss=0.7123  ← val_loss went UP!
Poll 5 (Epoch 50): train_loss=0.3987, val_loss=0.7456  ← still going up!
```

**Agent's Dilemma:**
- Sees val_loss = 0.7456 at epoch 50
- But has NO CONTEXT - is this good or bad?
- Cannot see that val_loss was 0.6789 at epoch 30 (better!)
- Cannot detect overfitting pattern
- Cannot recommend early stopping
- Cannot determine if training is stuck

**What the Agent SHOULD Be Able to Do:**
```python
# Agent analyzes training metrics
metrics = await mcp.get_training_metrics(operation_id)

# Check for overfitting
if metrics.is_overfitting():
    await mcp.cancel_operation(operation_id,
        reason="Overfitting detected: val_loss increasing while train_loss decreasing")

# Check for plateau
if metrics.is_plateaued(patience=10):
    await mcp.cancel_operation(operation_id,
        reason="Training plateaued: no val_loss improvement in 10 epochs")

# Check for divergence
if metrics.is_diverging():
    await mcp.cancel_operation(operation_id,
        reason="Training diverging: loss increasing")
```

---

## Root Causes

### 1. **Progress Updates Are Stateless**

The `OperationProgress.context` field contains **only the current epoch's metrics**. Previous epochs are discarded. The `context` dict is rebuilt on every update with just the latest values.

**Location**: [TrainingProgressBridge.on_epoch()](../../ktrdr/api/services/training/progress_bridge.py:97-139)

```python
context = {
    "epoch_index": epoch_index,
    "total_epochs": self._total_epochs,
    "epoch_metrics": metrics or {},  # ← ONLY current epoch!
}
```

### 2. **Training History Exists But Isn't Exposed**

`ModelTrainer` maintains complete training history in `self.history: List[TrainingMetrics]`:

**Location**: [ModelTrainer.train()](../../ktrdr/training/model_trainer.py:162-598)

```python
# Line ~482: Metrics are recorded
metrics = TrainingMetrics(
    epoch=epoch,
    train_loss=avg_train_loss,
    train_accuracy=train_accuracy,
    val_loss=val_loss,
    val_accuracy=val_accuracy,
    learning_rate=optimizer.param_groups[0]["lr"],
    duration=duration,
)
self.history.append(metrics)  # ← STORED but not exposed!
```

**The Gap**: This `history` is used for:
- Final training summary (`_create_training_summary()`)
- Analytics export
- Early stopping decisions

But **NOT** for real-time progress updates to agents.

### 3. **No Metrics-Specific API Endpoint**

Current API structure:
- ✅ `GET /operations` - List operations
- ✅ `GET /operations/{id}` - Get operation status + progress
- ✅ `GET /operations/{id}/results` - Get final results (after completion)
- ❌ `GET /operations/{id}/metrics` - **DOES NOT EXIST**

There's no dedicated endpoint for retrieving training metrics history during training.

### 4. **MCP Client Has No Metrics Interface**

**Location**: [mcp/src/clients/operations_client.py](../../mcp/src/clients/operations_client.py)

```python
class OperationsAPIClient(BaseAPIClient):
    async def list_operations(...)  # ✅ Exists
    async def get_operation_status(...)  # ✅ Exists
    async def cancel_operation(...)  # ✅ Exists
    async def get_operation_results(...)  # ✅ Exists
    async def get_training_metrics(...)  # ❌ DOES NOT EXIST
```

---

## User Impact

### For AI Agents (High Impact)

**Current State:**
- ❌ Cannot assess training health
- ❌ Cannot detect overfitting
- ❌ Cannot detect plateaus
- ❌ Cannot recommend early stopping
- ❌ Cannot provide intelligent guidance
- ❌ Can only report "Training at 65%, val_loss=0.7456" (meaningless without context)

**Desired State:**
- ✅ Can analyze loss trends
- ✅ Can detect overfitting patterns
- ✅ Can identify plateaus
- ✅ Can recommend optimal stopping point
- ✅ Can provide actionable feedback: "Training looks good, validation loss improving steadily"
- ✅ Can intervene: "Stop training now - validation loss hasn't improved in 15 epochs, best was epoch 42"

### For Human Users (Moderate Impact)

Humans typically:
- Watch logs directly (can see all epochs)
- Use TensorBoard or analytics dashboards
- Wait for training to complete

**But** if using agents to monitor training:
- Need agents to provide intelligent summaries
- Want agents to alert on issues
- Expect agents to know when to stop training early

---

## Success Criteria

A successful solution must:

1. **Expose Training Metrics History**
   - All epochs' train_loss, val_loss, train_accuracy, val_accuracy
   - Learning rate trajectory
   - Epoch durations
   - Available during training (not just after completion)

2. **Provide Diagnostic Signals**
   - Best epoch so far (lowest val_loss)
   - Epochs since improvement (for early stopping assessment)
   - Overfitting detection (train vs val divergence)
   - Plateau detection (loss not changing)

3. **Enable Agent Decision Making**
   - Agents can fetch metrics via MCP
   - Agents can compute trends
   - Agents can make recommendations
   - Agents can trigger early stopping

4. **Maintain Performance**
   - Metrics storage overhead < 1MB for typical 100-epoch training
   - Metrics retrieval < 100ms
   - No impact on training speed
   - Efficient serialization for API transfer

5. **Preserve Existing Functionality**
   - Progress reporting continues as-is
   - Training pipeline unchanged
   - Final results unchanged
   - Analytics unchanged

6. **Support Real-Time Access**
   - Metrics available while training is running
   - Updates as each epoch completes
   - No need to wait for training completion

---

## Additional Metrics to Consider

Beyond train_loss and val_loss, these could be valuable for agents:

### Currently Collected (but not fully exposed):
- ✅ **train_accuracy / val_accuracy** - Classification performance
- ✅ **learning_rate** - Scheduler adjustments
- ✅ **duration** - Training speed per epoch

### Potentially Valuable (would require collection):
- **Gradient norms** - Detect exploding/vanishing gradients
- **Parameter norms** - Model weight magnitudes
- **Loss components** - If using composite loss
- **Per-class accuracy** - For imbalanced datasets
- **Batch-level loss** - More granular than epochs
- **Memory usage** - GPU/CPU memory tracking
- **Early stopping signals** - Patience counter, threshold checks

**For initial implementation**: Focus on what's **already collected** (train_loss, val_loss, accuracies, learning_rate). Additional diagnostics can be added incrementally.

---

## Constraints

### Technical Constraints
- Must work with both local and host service training
- Must support async operations
- Must not break existing progress reporting
- Must handle concurrent access (multiple agents polling)

### Architectural Constraints
- Follow existing patterns (ServiceOrchestrator, OperationsService)
- Use existing progress infrastructure
- Maintain separation of concerns
- Keep storage in OperationsService (not in ModelTrainer)

### Performance Constraints
- Metrics storage overhead < 1MB per operation
- Metrics retrieval < 100ms
- No impact on training performance
- Efficient JSON serialization

---

## Out of Scope

The following are explicitly **NOT** part of this design:

1. **Changing how metrics are collected** (ModelTrainer already does this well)
2. **Real-time streaming** (polling every 10-30s is sufficient)
3. **TensorBoard integration** (separate concern)
4. **Analytics dashboard** (separate concern)
5. **Model checkpointing** (already handled)
6. **Distributed training metrics** (not currently supported)
7. **Custom metric definitions** (use what's already collected)

---

## Next Steps

1. **Design Document** → Define metrics exposure architecture
2. **Architecture Document** → Detail API endpoints, storage, and flow
3. **Implementation Plan** → Break down into testable tasks

---

**END OF PROBLEM STATEMENT**
