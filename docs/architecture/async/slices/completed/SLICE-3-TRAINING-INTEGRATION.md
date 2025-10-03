# SLICE 3: TRAINING SERVICE DUMMY PATTERN INTEGRATION - CLEAN RESTART SPECIFICATION

**Branch**: `slice-3-training-dummy-pattern-integration-v2`
**Goal**: Transform TrainingManager to follow DummyService pattern exactly from clean state with proper dual-implementation support and end-to-end testability
**Priority**: High
**Depends on**: Slice 1 and 2 completion
**Approach**: Clean restart (Option 1) - reset to pre-ServiceOrchestrator state and build correctly

## 🎯 **STARTING STATE ANALYSIS**

### **Current State (After Branch Reset)**
- TrainingManager: Plain class, no ServiceOrchestrator inheritance
- TrainingService: Has its own operations management system
- CLI: Manual progress parsing and state reconstruction
- No ServiceOrchestrator integration anywhere in training system

### **Target Architecture (DummyService Pattern)**

```text
CLI → API → TrainingService → TrainingManager (ServiceOrchestrator) → TrainingAdapter → {Local|Host} Training
                                      ↓
                              ServiceOrchestrator handles ALL:
                              - Operation tracking
                              - Progress reporting via TrainingProgressRenderer
                              - Cancellation coordination
                              - API response formatting
```

### **Dual Implementation Requirements**
- **Local Training**: CPU-based training in Docker backend with ServiceOrchestrator integration
- **Host Training**: GPU-based training via external service with ServiceOrchestrator integration
- **Both paths**: Must support cancellation tokens and progress callbacks from ServiceOrchestrator
- **Same UX**: Identical progress reporting and cancellation behavior regardless of implementation

## 📋 **TASK BREAKDOWN FOR PROGRESSIVE IMPLEMENTATION**

### **Task 3.1: Transform TrainingManager to Inherit ServiceOrchestrator**
**End-to-End Testable**: ✅ Training still works, now uses ServiceOrchestrator pattern

#### **Files to Modify**
- `ktrdr/training/training_manager.py`
- `ktrdr/training/components/training_progress_renderer.py` (create)

#### **Specific Changes Required**

**MODIFY TrainingManager Class Declaration:**

```python
# BEFORE: Plain class
class TrainingManager:
    def __init__(self):
        self.training_adapter = self._initialize_training_adapter()

# AFTER: ServiceOrchestrator inheritance (like DummyService)
from ktrdr.managers.base import ServiceOrchestrator
from .components.training_progress_renderer import TrainingProgressRenderer

class TrainingManager(ServiceOrchestrator[TrainingAdapter]):
    def __init__(self) -> None:
        # Initialize ServiceOrchestrator first
        super().__init__()

        # Override with TrainingProgressRenderer for structured progress
        self._training_progress_renderer = TrainingProgressRenderer()
        if self._training_progress_renderer is not None:
            self._progress_renderer = self._training_progress_renderer

            # Recreate progress manager with training-specific renderer
            from ktrdr.async_infrastructure.progress import GenericProgressManager
            self._generic_progress_manager = GenericProgressManager(
                renderer=self._progress_renderer
            )
```

**IMPLEMENT Required ServiceOrchestrator Methods:**

```python
def _initialize_adapter(self) -> TrainingAdapter:
    """Initialize training adapter based on environment variables."""
    # Move existing adapter initialization logic here
    return TrainingAdapter(...)

def _get_service_name(self) -> str:
    return "Training"

def _get_default_host_url(self) -> str:
    return "http://localhost:5002"

def _get_env_var_prefix(self) -> str:
    return "TRAINING"
```

**TRANSFORM Training Methods to ServiceOrchestrator Pattern:**

```python
# BEFORE: Direct adapter calls
async def train_multi_symbol_strategy(self, ...):
    return await self.training_adapter.train_multi_symbol_strategy(...)

# AFTER: ServiceOrchestrator pattern (like DummyService)
async def train_multi_symbol_strategy_async(self, ...) -> dict[str, Any]:
    """ServiceOrchestrator handles ALL complexity automatically."""
    return await self.start_managed_operation(
        operation_name="train_multi_symbol_strategy",
        operation_type="TRAINING",
        operation_func=self._run_training_async,
        # Pass parameters to domain logic
        strategy_config_path=strategy_config_path,
        symbols=symbols,
        timeframes=timeframes,
        start_date=start_date,
        end_date=end_date,
        validation_split=validation_split,
        data_mode=data_mode,
    )

async def _run_training_async(self, **kwargs) -> dict[str, Any]:
    """Clean domain logic with ServiceOrchestrator integration."""
    # Get cancellation token from ServiceOrchestrator
    cancellation_token = self.get_current_cancellation_token()

    # Use adapter with ServiceOrchestrator callbacks
    result = await self.adapter.train_multi_symbol_strategy(
        **kwargs,
        cancellation_token=cancellation_token,
        progress_callback=self.update_operation_progress,
    )

    return self._format_training_api_response(result)
```

**CREATE TrainingProgressRenderer:**

```python
# ktrdr/training/components/training_progress_renderer.py
from ktrdr.async_infrastructure.progress import ProgressRenderer, GenericProgressState

class TrainingProgressRenderer(ProgressRenderer):
    def render_message(self, state: GenericProgressState) -> str:
        """Render training-specific progress messages."""
        context = state.context or {}

        # Extract training context
        symbols = context.get('symbols', [])
        model_type = context.get('model_type', 'Model')
        current_epoch = context.get('current_epoch', 0)
        total_epochs = context.get('total_epochs', 0)

        # Format like: "Training MLP model on AAPL [epoch 5/50]"
        symbol_str = symbols[0] if symbols else "unknown"
        if len(symbols) > 1:
            symbol_str = f"{symbols[0]}+{len(symbols)-1} others"

        epoch_str = ""
        if total_epochs > 0:
            epoch_str = f" [epoch {current_epoch}/{total_epochs}]"

        return f"Training {model_type} model on {symbol_str}{epoch_str}"
```

#### **Integration Points**
- **ServiceOrchestrator inheritance**: Provides automatic operations, progress, cancellation
- **TrainingProgressRenderer**: Provides training-specific structured progress messages
- **Method transformation**: Training methods become `start_managed_operation()` calls
- **Domain logic separation**: Clean `_run_training_async()` with ServiceOrchestrator integration

#### **End-to-End Test Validation**

```bash
# Test that training still starts and completes with ServiceOrchestrator
ktrdr models train strategies/test_strategy.yaml --start-date 2024-01-01 --end-date 2024-01-02

# Verify ServiceOrchestrator operations API shows the training
curl localhost:8000/operations  # Should show training operation managed by ServiceOrchestrator
```

---

### **Task 3.2: Integrate TrainingAdapter with ServiceOrchestrator Callbacks**
**End-to-End Testable**: ✅ Training reports structured progress and supports cancellation

#### **Files to Modify**
- `ktrdr/training/training_adapter.py`

#### **Specific Changes Required**

**MODIFY TrainingAdapter Methods to Accept ServiceOrchestrator Integration:**

```python
async def train_multi_symbol_strategy(
    self,
    strategy_config_path: str,
    symbols: list[str],
    timeframes: list[str],
    start_date: str,
    end_date: str,
    validation_split: float = 0.2,
    data_mode: str = "local",
    progress_callback=None,        # NEW: ServiceOrchestrator progress callback
    cancellation_token=None,       # NEW: ServiceOrchestrator cancellation token
) -> dict[str, Any]:
    """Training adapter with ServiceOrchestrator integration support."""
    if self.use_host_service:
        return await self._call_host_service_training(
            strategy_config_path=strategy_config_path,
            symbols=symbols,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date,
            validation_split=validation_split,
            data_mode=data_mode,
            progress_callback=progress_callback,
            cancellation_token=cancellation_token
        )
    else:
        # Forward to local training with ServiceOrchestrator integration
        return await self._call_local_training(
            strategy_config_path=strategy_config_path,
            symbols=symbols,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date,
            validation_split=validation_split,
            data_mode=data_mode,
            progress_callback=progress_callback,
            cancellation_token=cancellation_token
        )
```

#### **Integration Points**
- **Callback forwarding**: TrainingAdapter forwards ServiceOrchestrator callbacks to implementations
- **Dual path support**: Both local and host service paths accept integration parameters
- **Backward compatibility**: Existing calls work, new parameters are optional

#### **End-to-End Test Validation**

```bash
# Test that TrainingAdapter forwards callbacks properly
ktrdr models train strategies/test_strategy.yaml --start-date 2024-01-01 --end-date 2024-01-02

# Should show structured progress from ServiceOrchestrator integration
curl localhost:8000/operations/{operation_id}
```

---

### **Task 3.3: Integrate Local Training with ServiceOrchestrator**
**End-to-End Testable**: ✅ Local training supports ServiceOrchestrator cancellation and progress

#### **Files to Modify**
- `ktrdr/training/training_adapter.py` (`_call_local_training` method)
- Local training implementation files

#### **Specific Changes Required**

**IMPLEMENT Local Training ServiceOrchestrator Integration:**

```python
async def _call_local_training(
    self,
    strategy_config_path: str,
    symbols: list[str],
    timeframes: list[str],
    start_date: str,
    end_date: str,
    validation_split: float = 0.2,
    data_mode: str = "local",
    progress_callback=None,
    cancellation_token=None,
) -> dict[str, Any]:
    """Local training with ServiceOrchestrator integration."""

    # Load strategy and setup training
    trainer = StrategyTrainer(models_dir="models")

    # Run training with ServiceOrchestrator callbacks
    def training_progress_callback(epoch: int, total_epochs: int, metrics: dict):
        """Convert local training progress to ServiceOrchestrator format."""
        if progress_callback:
            progress_callback(
                step=epoch,
                message=f"Training epoch {epoch+1}",
                context={
                    'model_type': metrics.get('model_type', 'mlp'),
                    'symbols': symbols,
                    'timeframes': timeframes,
                    'current_epoch': epoch + 1,
                    'total_epochs': total_epochs,
                    'current_batch': metrics.get('batch', 0),
                    'total_batches': metrics.get('total_batches', 0),
                    'strategy': Path(strategy_config_path).stem,
                }
            )

    # Check cancellation during training setup
    if cancellation_token and cancellation_token.is_cancelled():
        return {"status": "cancelled", "message": "Training cancelled before start"}

    # Run training with cancellation and progress integration
    result = await self._run_local_training_with_cancellation(
        trainer=trainer,
        strategy_config_path=strategy_config_path,
        symbols=symbols,
        timeframes=timeframes,
        start_date=start_date,
        end_date=end_date,
        validation_split=validation_split,
        data_mode=data_mode,
        progress_callback=training_progress_callback,
        cancellation_token=cancellation_token,
    )

    return result

async def _run_local_training_with_cancellation(
    self,
    trainer,
    strategy_config_path: str,
    symbols: list[str],
    timeframes: list[str],
    start_date: str,
    end_date: str,
    validation_split: float,
    data_mode: str,
    progress_callback,
    cancellation_token,
) -> dict[str, Any]:
    """Run local training with periodic cancellation checks."""

    # Run training in executor to allow cancellation checks
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Submit training task
        training_future = executor.submit(
            trainer.train_multi_symbol_strategy,
            strategy_config_path,
            symbols,
            timeframes,
            start_date,
            end_date,
            validation_split,
            data_mode,
            progress_callback,
        )

        # Monitor for cancellation while training runs
        while not training_future.done():
            if cancellation_token and cancellation_token.is_cancelled():
                # Cancel training (implementation depends on trainer capabilities)
                training_future.cancel()
                return {
                    "status": "cancelled",
                    "message": "Training cancelled by user",
                    "symbols": symbols,
                }

            await asyncio.sleep(1)  # Check every second

        # Get training results
        return training_future.result()
```

#### **Integration Points**
- **Cancellation checks**: Local training checks ServiceOrchestrator cancellation token periodically
- **Progress forwarding**: Local training progress → ServiceOrchestrator progress callback
- **Context structure**: Local training provides structured context for TrainingProgressRenderer
- **Async execution**: Local training runs in executor to allow cancellation monitoring

#### **End-to-End Test Validation**

```bash
# Test local training cancellation
ktrdr models train strategies/test_strategy.yaml --start-date 2024-01-01 --end-date 2024-01-02 &
# Press Ctrl+C within 5 seconds - should cancel gracefully

# Test progress shows local training context
curl localhost:8000/operations/{operation_id}  # Should show epoch/batch progress
```

---

### **Task 3.4: Integrate Host Service Training with ServiceOrchestrator**
**End-to-End Testable**: ✅ Host service training supports ServiceOrchestrator integration

#### **Files to Modify**
- `ktrdr/training/training_adapter.py` (`_call_host_service_training` method)

#### **Specific Changes Required**

**IMPLEMENT Host Service ServiceOrchestrator Integration:**

```python
async def _call_host_service_training(
    self,
    strategy_config_path: str,
    symbols: list[str],
    timeframes: list[str],
    start_date: str,
    end_date: str,
    validation_split: float = 0.2,
    data_mode: str = "local",
    progress_callback=None,
    cancellation_token=None,
) -> dict[str, Any]:
    """Host service training with ServiceOrchestrator integration."""

    # Check cancellation before starting
    if cancellation_token and cancellation_token.is_cancelled():
        return {"status": "cancelled", "message": "Training cancelled before start"}

    # Start host service training session
    training_config = {
        "strategy_config_path": strategy_config_path,
        "symbols": symbols,
        "timeframes": timeframes,
        "start_date": start_date,
        "end_date": end_date,
        "validation_split": validation_split,
        "data_mode": data_mode,
        # Enable ServiceOrchestrator integration features
        "enable_cancellation": cancellation_token is not None,
        "enable_progress_reporting": progress_callback is not None,
    }

    session_id = await self.host_client.start_training_session(training_config)

    # Monitor host service training and forward to ServiceOrchestrator
    while True:
        # Check ServiceOrchestrator cancellation first
        if cancellation_token and cancellation_token.is_cancelled():
            try:
                await self.host_client.cancel_training_session(session_id)
            except Exception as e:
                logger.warning(f"Failed to cancel host training session: {e}")
            return {"status": "cancelled", "message": "Training cancelled by user"}

        # Get progress from host service
        try:
            host_progress = await self.host_client.get_training_status(session_id)
        except Exception as e:
            logger.error(f"Failed to get host training status: {e}")
            await asyncio.sleep(2)
            continue

        # Forward host service progress to ServiceOrchestrator
        if progress_callback and host_progress:
            progress_callback(
                step=host_progress.get("current_step", 0),
                message=host_progress.get("message", "Host training"),
                context={
                    'model_type': host_progress.get("model_type", "mlp"),
                    'symbols': symbols,
                    'timeframes': timeframes,
                    'current_epoch': host_progress.get("current_epoch", 0),
                    'total_epochs': host_progress.get("total_epochs", 0),
                    'current_batch': host_progress.get("current_batch", 0),
                    'total_batches': host_progress.get("total_batches", 0),
                    'strategy': Path(strategy_config_path).stem,
                    'host_service': True,
                }
            )

        # Check if host training completed
        status = host_progress.get("status")
        if status in ["completed", "failed", "cancelled"]:
            return host_progress

        await asyncio.sleep(1)  # Poll interval
```

#### **Integration Points**
- **Cancellation forwarding**: ServiceOrchestrator cancellation → host service cancellation
- **Progress forwarding**: Host service progress → ServiceOrchestrator progress callback
- **Context mapping**: Host service format → TrainingProgressRenderer context
- **Error handling**: Host service errors handled gracefully

#### **End-to-End Test Validation**

```bash
# Test with host service enabled (requires host service running)
USE_TRAINING_HOST_SERVICE=true ktrdr models train strategies/test_strategy.yaml --start-date 2024-01-01 --end-date 2024-01-02

# Verify host service progress forwarding
curl localhost:8000/operations/{operation_id}  # Should show host service context
```

---

### **Task 3.5: Simplify TrainingService to Pure API Adapter**
**End-to-End Testable**: ✅ TrainingService delegates to ServiceOrchestrator, no competing systems

#### **Files to Modify**
- `ktrdr/api/services/training_service.py`

#### **Specific Changes Required**

**REMOVE All Competing Operations Infrastructure:**

```python
# REMOVE these methods entirely:
# - _run_training_async() (if exists)
# - _run_multi_symbol_training_async() (if exists)
# - Any direct operations_service.update_progress() calls
# - Any manual operations management
```

**SIMPLIFY TrainingService to Pure API Adapter:**

```python
class TrainingService(BaseService):
    def __init__(self, operations_service: Optional[OperationsService] = None):
        super().__init__()
        self.model_storage = ModelStorage()
        self.model_loader = ModelLoader()
        # Keep operations_service for other methods, but don't use for training
        self.operations_service = operations_service
        # TrainingManager handles its own operations via ServiceOrchestrator
        self.training_manager = TrainingManager()

    async def start_training(
        self,
        symbols: list[str],
        timeframes: list[str],
        strategy_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        task_id: Optional[str] = None,
        detailed_analytics: bool = False,
    ) -> dict[str, Any]:
        """Pure delegation to TrainingManager ServiceOrchestrator."""

        # Strategy validation (keep existing logic)
        strategy_paths = [
            Path(f"/app/strategies/{strategy_name}.yaml"),
            Path(f"strategies/{strategy_name}.yaml"),
        ]

        strategy_path = None
        for path in strategy_paths:
            if path.exists():
                strategy_path = path
                break

        if not strategy_path:
            raise ValidationError(f"Strategy file not found: {strategy_name}.yaml")

        # Apply analytics if requested (keep existing logic)
        if detailed_analytics:
            # Modify strategy config for analytics
            pass

        # SIMPLE DELEGATION to ServiceOrchestrator (no competing operations!)
        return await self.training_manager.train_multi_symbol_strategy_async(
            strategy_config_path=str(strategy_path),
            symbols=symbols,
            timeframes=timeframes,
            start_date=start_date or "2020-01-01",
            end_date=end_date or datetime.utcnow().strftime("%Y-%m-%d"),
            validation_split=0.2,
            data_mode="local",
        )
```

#### **Integration Points**
- **Pure API adapter**: TrainingService only validates inputs and delegates
- **No competing operations**: ServiceOrchestrator handles all operation management
- **Strategy validation preserved**: Keep existing validation and analytics logic
- **Simple delegation**: Direct call to TrainingManager ServiceOrchestrator method

#### **End-to-End Test Validation**

```bash
# Test that API still works but uses ServiceOrchestrator
curl -X POST localhost:8000/trainings/start -d '{"symbols":["AAPL"],"timeframes":["1h"],"strategy_name":"test"}'

# Verify single operations system
curl localhost:8000/operations  # Should show only ServiceOrchestrator-managed operations
```

---

### **Task 3.6: Fix CLI to Use ServiceOrchestrator's Structured Data**
**End-to-End Testable**: ✅ CLI shows structured progress without manual parsing

#### **Files to Modify**
- `ktrdr/cli/async_model_commands.py`

#### **Specific Changes Required**

**REMOVE Manual Progress State Construction:**

```python
# DELETE manual GenericProgressState construction:
# This assumes we know the start_time and other details, but ServiceOrchestrator manages these
progress_state = GenericProgressState(
    operation_id=operation_id,
    current_step=progress_info.get("steps_completed", 0),
    total_steps=progress_info.get("steps_total", 100),
    message=current_step,
    percentage=progress_percentage,
    start_time=datetime.now(),  # WRONG! ServiceOrchestrator knows the real start time
    items_processed=progress_info.get("items_processed", 0),
    total_items=progress_info.get("items_total", None),
    step_current=progress_info.get("steps_completed", 0),
    step_total=progress_info.get("steps_total", 100),
)
```

**USE ServiceOrchestrator's Structured Data:**

```python
# ServiceOrchestrator provides structured context automatically
context = progress_info.get("context", {})

# Access training-specific structured data (no parsing needed!)
current_epoch = context.get('current_epoch', 0)
total_epochs = context.get('total_epochs', 0)
model_type = context.get('model_type', 'Model')
symbols = context.get('symbols', [])
strategy = context.get('strategy', 'Unknown')

# Let ServiceOrchestrator manage the GenericProgressState properly
progress_state = GenericProgressState(
    operation_id=operation_id,
    current_step=progress_info.get("steps_completed", 0),
    total_steps=progress_info.get("steps_total", 100),
    message=progress_info.get("current_step", "Training..."),
    percentage=progress_info.get("percentage", 0),
    start_time=None,  # Let ServiceOrchestrator manage timing
    context=context,  # Use ServiceOrchestrator's structured context
    items_processed=progress_info.get("items_processed", 0),
    total_items=progress_info.get("items_total", None),
)
```

#### **Integration Points**
- **Remove manual construction**: Let ServiceOrchestrator provide proper state
- **Use structured context**: Access training data from ServiceOrchestrator context
- **TrainingProgressRenderer integration**: Structured context enables proper formatting
- **Timing handled by ServiceOrchestrator**: No more incorrect start_time approximations

#### **End-to-End Test Validation**

```bash
# Test CLI shows structured training progress
ktrdr models train strategies/test_strategy.yaml --start-date 2024-01-01 --end-date 2024-01-02 --verbose

# Should show: "Training MLP model on AAPL [epoch 5/50]"
# Instead of: "Working..." or manual parsing errors
```

---

### **Task 3.7: End-to-End Testing and DummyService Pattern Validation**
**End-to-End Testable**: ✅ Training system works exactly like DummyService

#### **Files to Create**
- `tests/integration/test_training_serviceorchestrator_pattern.py`

#### **Comprehensive Pattern Compliance Tests**

```python
def test_training_manager_follows_dummy_service_pattern():
    """Validate TrainingManager follows exact DummyService pattern."""
    # 1. Inheritance compliance
    assert issubclass(TrainingManager, ServiceOrchestrator)

    # 2. Method structure compliance
    training_manager = TrainingManager()

    # ServiceOrchestrator capabilities (like DummyService)
    assert hasattr(training_manager, 'start_managed_operation')
    assert hasattr(training_manager, 'get_current_cancellation_token')
    assert hasattr(training_manager, 'update_operation_progress')

    # Training-specific methods
    assert hasattr(training_manager, 'train_multi_symbol_strategy_async')
    assert hasattr(training_manager, '_run_training_async')

def test_training_service_is_pure_api_adapter():
    """Validate TrainingService has no competing operations systems."""
    training_service = TrainingService()

    # Should NOT have competing async infrastructure
    assert not hasattr(training_service, '_run_training_async')
    assert not hasattr(training_service, '_run_multi_symbol_training_async')

    # Should be simple delegation
    assert hasattr(training_service, 'start_training')
    assert hasattr(training_service, 'training_manager')

async def test_training_matches_dummy_service_behavior():
    """Test training operations behave identically to dummy operations."""
    # Start training operation
    training_response = await api_client.start_training(...)
    training_op_id = training_response["operation_id"]

    # Compare with dummy operation
    dummy_response = await api_client.start_dummy_task()
    dummy_op_id = dummy_response["operation_id"]

    # Both should use same operations API structure
    training_status = await api_client.get_operation_status(training_op_id)
    dummy_status = await api_client.get_operation_status(dummy_op_id)

    # Same operation structure
    assert set(training_status.keys()) == set(dummy_status.keys())
    assert training_status["data"]["progress"].keys() == dummy_status["data"]["progress"].keys()

async def test_dual_implementation_serviceorchestrator_integration():
    """Test both local and host service integrate with ServiceOrchestrator."""
    # Test local training
    local_result = await training_adapter.train_multi_symbol_strategy(
        ...,
        progress_callback=mock_progress_callback,
        cancellation_token=mock_cancellation_token
    )

    # Test host service training
    with mock.patch.object(training_adapter, 'use_host_service', True):
        host_result = await training_adapter.train_multi_symbol_strategy(
            ...,
            progress_callback=mock_progress_callback,
            cancellation_token=mock_cancellation_token
        )

    # Both should support ServiceOrchestrator integration
    assert mock_progress_callback.called
    assert mock_cancellation_token.checked
```

#### **End-to-End Test Validation**

```bash
# Complete system validation
make test-integration  # Should include ServiceOrchestrator compliance tests

# Manual validation - should work exactly like dummy service
ktrdr models train strategies/test_strategy.yaml --start-date 2024-01-01 --end-date 2024-01-02
ktrdr dummy start

# Both commands should have:
# - Same progress display quality
# - Same cancellation behavior
# - Same operations API structure
# - Same overall UX
```

## 🎯 **SUCCESS CRITERIA**

### **DummyService Pattern Compliance**

- [ ] TrainingManager inherits ServiceOrchestrator[TrainingAdapter] (like DummyService)
- [ ] Training methods are single `start_managed_operation()` calls (like DummyService)
- [ ] Domain logic in clean `_run_training_async()` methods (like DummyService)
- [ ] ServiceOrchestrator handles ALL async complexity automatically
- [ ] TrainingProgressRenderer provides training-specific structured progress

### **Dual Implementation Support**

- [ ] Local training integrates with ServiceOrchestrator (cancellation + progress)
- [ ] Host service training integrates with ServiceOrchestrator (cancellation + progress)
- [ ] Both paths provide identical UX and structured progress
- [ ] Environment variable switching works seamlessly between implementations

### **System Integration**

- [ ] TrainingService is pure API adapter (no competing operations systems)
- [ ] CLI gets structured data from ServiceOrchestrator automatically
- [ ] Progress quality matches DummyService exactly
- [ ] Cancellation works end-to-end through entire system

### **End-to-End Testing**

- [ ] Each task is independently testable and functional
- [ ] Integration tests validate exact DummyService pattern compliance
- [ ] Manual testing shows identical UX to DummyService
- [ ] Both local and host training paths fully validated

## 📋 **CRITICAL SUCCESS CHECKPOINTS**

### **After Task 3.1 (ServiceOrchestrator Inheritance)**

```bash
# Training should still work, now with ServiceOrchestrator
ktrdr models train strategies/test_strategy.yaml --start-date 2024-01-01 --end-date 2024-01-02

# Operations API should show ServiceOrchestrator-managed operation
curl localhost:8000/operations
```

### **After Task 3.3 (Local Training Integration)**

```bash
# Cancellation should work
ktrdr models train strategies/test_strategy.yaml --start-date 2024-01-01 --end-date 2024-01-02 &
# Ctrl+C should cancel gracefully

# Progress should show structured training context
curl localhost:8000/operations/{operation_id}  # Should show epoch/batch info
```

### **After Task 3.6 (CLI Integration)**

```bash
# CLI should show formatted training progress
ktrdr models train strategies/test_strategy.yaml --start-date 2024-01-01 --end-date 2024-01-02 --verbose

# Should display: "Training MLP model on AAPL [epoch 5/50]"
# Not: generic progress or parsing errors
```

### **After Task 3.7 (Complete Integration)**

```bash
# Training should behave exactly like dummy service
ktrdr models train strategies/test_strategy.yaml --start-date 2024-01-01 --end-date 2024-01-02
ktrdr dummy start

# Both should have identical:
# - Progress display patterns
# - Cancellation behavior
# - Operations API responses
# - Overall user experience
```

## 🔍 **CONTEXT STRUCTURE FOR SERVICEORCHESTRATOR INTEGRATION**

All progress callbacks must provide this structured context:

```python
{
    'model_type': str,              # 'mlp', 'cnn', etc.
    'symbols': list[str],           # ['AAPL', 'MSFT']
    'timeframes': list[str],        # ['1h', '4h']
    'current_epoch': int,           # 5
    'total_epochs': int,            # 50
    'current_batch': int,           # 123
    'total_batches': int,           # 500
    'strategy': str,                # Strategy name
    'host_service': bool,           # True if using host service
}
```

This enables TrainingProgressRenderer to format messages like:
- "Training MLP model on AAPL [epoch 5/50] (batch 123/500)"
- "Training CNN model on AAPL+2 others [epoch 8/20] (host service)"

## 📈 **PROGRESSIVE IMPLEMENTATION BENEFITS**

1. **Task 3.1**: Basic ServiceOrchestrator pattern established, training still works
2. **Task 3.2**: Adapter ready for integration, maintains backward compatibility
3. **Task 3.3**: Local training gains cancellation and structured progress
4. **Task 3.4**: Host service gains ServiceOrchestrator integration
5. **Task 3.5**: API layer simplified, no competing systems
6. **Task 3.6**: CLI gains structured progress without manual parsing
7. **Task 3.7**: Full system behaves exactly like DummyService

Each task builds on the previous while maintaining end-to-end functionality, preventing the "all-or-nothing" implementation issues of the previous attempt.