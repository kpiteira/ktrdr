# 🏗️ **VERTICAL IMPLEMENTATION PLAN: SLICE-BY-SLICE ASYNC INFRASTRUCTURE**

## 🎯 **CORE PRINCIPLE: BUILD SMALL, TEST IMMEDIATELY, INTEGRATE CONTINUOUSLY**

This plan implements generic async infrastructure through **complete vertical slices** that deliver working functionality at each step. Each slice builds one piece of the infrastructure while integrating it with real, testable functionality.

## 🧩 **VERTICAL SLICE STRATEGY**

Instead of building all infrastructure first, we implement **one complete feature slice at a time**:
- Each slice adds one piece of infrastructure
- Each slice integrates immediately with working code  
- Each slice is fully tested before moving to the next
- Always have a working, improved system

## 📋 **IMPLEMENTATION SLICES**

---

## 🎯 **SLICE 1: GENERIC PROGRESS FOUNDATION**
**Duration**: 1 week  
**Goal**: Create working generic progress system integrated with DataManager.load_data()

### **Day 1: Build Minimal GenericProgressManager**

**Create**: `ktrdr/async/progress.py`
```python
@dataclass
class GenericProgressState:
    """Generic progress state - no domain knowledge."""
    operation_id: str
    current_step: int
    total_steps: int
    percentage: float
    message: str
    context: dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)

class ProgressRenderer(ABC):
    """Abstract progress renderer for domain-specific display."""
    
    @abstractmethod
    def render_message(self, state: GenericProgressState) -> str:
        """Render progress message for this domain."""
        pass

class GenericProgressManager:
    """Domain-agnostic progress manager - minimal implementation."""
    
    def __init__(self, 
                 callback: Optional[Callable[[GenericProgressState], None]] = None,
                 renderer: Optional[ProgressRenderer] = None):
        self.callback = callback
        self.renderer = renderer
        self._state: Optional[GenericProgressState] = None
        self._lock = threading.RLock()
    
    def start_operation(self, operation_id: str, total_steps: int, context: dict = None):
        """Start tracking operation."""
        with self._lock:
            self._state = GenericProgressState(
                operation_id=operation_id,
                current_step=0,
                total_steps=total_steps,
                percentage=0.0,
                message=f"Starting {operation_id}",
                context=context or {}
            )
            self._trigger_callback()
    
    def update_progress(self, step: int, message: str, context: dict = None):
        """Update progress with domain-agnostic information."""
        with self._lock:
            if not self._state:
                return
                
            self._state.current_step = step
            self._state.percentage = min(100.0, (step / self._state.total_steps) * 100.0)
            
            # Update context
            if context:
                self._state.context.update(context)
            
            # Use renderer if available, otherwise use message directly
            if self.renderer:
                self._state.message = self.renderer.render_message(self._state)
            else:
                self._state.message = message
            
            self._trigger_callback()
    
    def complete_operation(self):
        """Mark operation complete."""
        with self._lock:
            if self._state:
                self._state.current_step = self._state.total_steps
                self._state.percentage = 100.0
                self._state.message = f"Operation {self._state.operation_id} completed"
                self._trigger_callback()
    
    def _trigger_callback(self):
        """Trigger progress callback."""
        if self.callback and self._state:
            try:
                self.callback(self._state)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
```

### **Day 2: Build Data Progress Renderer**

**Create**: `ktrdr/data/async/__init__.py` and `data_progress_renderer.py`
```python
# ktrdr/data/async/data_progress_renderer.py
from ktrdr.async.progress import ProgressRenderer, GenericProgressState

class DataProgressRenderer(ProgressRenderer):
    """Renders progress messages for data operations."""
    
    def render_message(self, state: GenericProgressState) -> str:
        """Render progress message with data context."""
        context = state.context
        base_message = self._extract_base_message(state.message)
        
        # Add data-specific context
        parts = [base_message]
        
        symbol = context.get('symbol')
        timeframe = context.get('timeframe')
        mode = context.get('mode')
        
        if symbol and timeframe:
            context_str = f"({symbol} {timeframe}"
            if mode:
                context_str += f", {mode} mode"
            context_str += ")"
            parts.append(context_str)
        
        # Add step progress if available
        if state.total_steps > 0:
            parts.append(f"[{state.current_step}/{state.total_steps}]")
        
        return " ".join(parts)
    
    def _extract_base_message(self, message: str) -> str:
        """Extract base message without previous context."""
        # Simple implementation - just return the message
        # Can be enhanced later to strip previous context
        return message
```

### **Day 3: Integrate with DataManager.load_data()**

**Update**: `ktrdr/data/data_manager.py`
```python
# Add to DataManager.__init__()
from ktrdr.async.progress import GenericProgressManager
from ktrdr.data.async.data_progress_renderer import DataProgressRenderer

def __init__(self):
    # ... existing initialization
    self._generic_progress_renderer = DataProgressRenderer()

def load_data(self, symbol: str, timeframe: str, mode: str = "local", 
              progress_callback: Optional[Callable] = None, **kwargs) -> pd.DataFrame:
    """Load data using new generic progress system."""
    
    # Create progress manager with data renderer
    progress_manager = GenericProgressManager(
        callback=self._wrap_legacy_callback(progress_callback),
        renderer=self._generic_progress_renderer
    )
    
    # Start operation with data context
    progress_manager.start_operation(
        operation_id=f"load_data_{symbol}_{timeframe}",
        total_steps=5,  # Existing step count
        context={
            'symbol': symbol,
            'timeframe': timeframe, 
            'mode': mode
        }
    )
    
    # Call existing implementation with new progress manager
    return self._load_with_fallback(
        symbol=symbol,
        timeframe=timeframe,
        mode=mode,
        progress_manager=progress_manager,  # Pass new progress manager
        **kwargs
    )

def _wrap_legacy_callback(self, legacy_callback: Optional[Callable]) -> Optional[Callable]:
    """Wrap legacy progress callback to work with GenericProgressState."""
    if not legacy_callback:
        return None
        
    def wrapper(state: GenericProgressState):
        # Convert to legacy format if needed
        legacy_callback(state)
    
    return wrapper
```

### **Day 4: Update _load_with_fallback() to Use GenericProgressManager**

**Update**: Internal method to use new progress system
```python
def _load_with_fallback(self, symbol: str, timeframe: str, mode: str,
                       progress_manager: GenericProgressManager, **kwargs) -> pd.DataFrame:
    """Updated to use GenericProgressManager instead of embedded progress."""
    
    # Step 1: Validate symbol
    progress_manager.update_progress(
        step=1, 
        message="Validating symbol and timeframe",
        context={'current_operation': 'validation'}
    )
    # ... existing validation logic
    
    # Step 2: Check local data
    progress_manager.update_progress(
        step=2,
        message="Checking local data availability",
        context={'current_operation': 'local_check'}
    )
    # ... existing local data logic
    
    # Continue with existing steps using progress_manager.update_progress()
    # ...
    
    # Final step
    progress_manager.complete_operation()
    return result
```

### **Day 5: Test and Validate Slice 1**

**Testing Requirements**:
- [ ] All existing `load_data()` tests pass
- [ ] Progress messages now include data context (symbol, timeframe, mode)
- [ ] Progress callbacks still work with legacy code
- [ ] New progress system provides better information than before
- [ ] No performance regressions

**Deliverables**:
- ✅ Working GenericProgressManager with domain-agnostic core
- ✅ DataProgressRenderer providing data-specific display
- ✅ One complete DataManager method using new infrastructure
- ✅ All existing functionality preserved with enhanced progress

---

## 🛑 **SLICE 2: CANCELLATION SYSTEM INTEGRATION**
**Duration**: 1 week  
**Goal**: Add universal cancellation to the same DataManager.load_data() operation

### **Day 1: Build Minimal CancellationSystem**

**Create**: `ktrdr/async/cancellation.py`
```python
import asyncio
import threading
from typing import Optional

class OperationCancelledException(Exception):
    """Exception raised when an operation is cancelled."""
    
    def __init__(self, operation_id: str):
        self.operation_id = operation_id
        super().__init__(f"Operation '{operation_id}' was cancelled")

class CancellationToken:
    """Generic cancellation token."""
    
    def __init__(self, operation_id: str):
        self.operation_id = operation_id
        self._cancelled = False
        self._lock = threading.Lock()
    
    def cancel(self) -> None:
        """Cancel the operation."""
        with self._lock:
            self._cancelled = True
    
    def is_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        with self._lock:
            return self._cancelled
    
    def check_cancellation(self, context: str = "operation") -> None:
        """Check for cancellation and raise if cancelled."""
        if self.is_cancelled():
            raise OperationCancelledException(f"{self.operation_id} during {context}")

class CancellationSystem:
    """Universal cancellation system."""
    
    def __init__(self):
        self._tokens: dict[str, CancellationToken] = {}
        self._lock = threading.Lock()
    
    def create_token(self, operation_id: str) -> CancellationToken:
        """Create cancellation token for operation."""
        with self._lock:
            token = CancellationToken(operation_id)
            self._tokens[operation_id] = token
            return token
    
    def cancel_operation(self, operation_id: str) -> bool:
        """Cancel specific operation."""
        with self._lock:
            token = self._tokens.get(operation_id)
            if token:
                token.cancel()
                return True
            return False
    
    def cleanup_token(self, operation_id: str) -> None:
        """Clean up completed operation token."""
        with self._lock:
            self._tokens.pop(operation_id, None)
```

### **Day 2: Integrate Cancellation with GenericProgressManager**

**Update**: `ktrdr/async/progress.py`
```python
class GenericProgressManager:
    def __init__(self, callback=None, renderer=None, cancellation_token=None):
        # ... existing init
        self.cancellation_token = cancellation_token
    
    def set_cancellation_token(self, token: CancellationToken):
        """Set cancellation token for this operation."""
        self.cancellation_token = token
    
    def update_progress(self, step: int, message: str, context: dict = None):
        """Update progress with cancellation check."""
        # Check for cancellation first
        if self.cancellation_token:
            self.cancellation_token.check_cancellation(f"step {step}")
        
        # ... existing progress logic
```

### **Day 3: Add Cancellation to DataManager.load_data()**

**Update**: `ktrdr/data/data_manager.py`
```python
from ktrdr.async.cancellation import CancellationSystem

class DataManager:
    def __init__(self):
        # ... existing init
        self._cancellation_system = CancellationSystem()
    
    def load_data(self, symbol: str, timeframe: str, mode: str = "local",
                  progress_callback: Optional[Callable] = None, **kwargs) -> pd.DataFrame:
        """Load data with cancellation support."""
        
        operation_id = f"load_data_{symbol}_{timeframe}_{datetime.now().isoformat()}"
        
        # Create cancellation token
        cancellation_token = self._cancellation_system.create_token(operation_id)
        
        try:
            # Create progress manager with cancellation
            progress_manager = GenericProgressManager(
                callback=self._wrap_legacy_callback(progress_callback),
                renderer=self._generic_progress_renderer,
                cancellation_token=cancellation_token
            )
            
            # ... rest of existing logic
            
            result = self._load_with_fallback(
                symbol=symbol,
                timeframe=timeframe, 
                mode=mode,
                progress_manager=progress_manager,
                cancellation_token=cancellation_token,  # Pass to internal methods
                **kwargs
            )
            
            return result
            
        except OperationCancelledException:
            logger.info(f"Data load operation {operation_id} was cancelled")
            raise
        finally:
            # Clean up cancellation token
            self._cancellation_system.cleanup_token(operation_id)
    
    def cancel_operation(self, operation_id: str) -> bool:
        """Cancel a data loading operation."""
        return self._cancellation_system.cancel_operation(operation_id)
```

### **Day 4: Add Cancellation Checks in _load_with_fallback()**

**Update**: Add cancellation checks at key points
```python
def _load_with_fallback(self, symbol: str, timeframe: str, mode: str,
                       progress_manager: GenericProgressManager,
                       cancellation_token: CancellationToken, **kwargs) -> pd.DataFrame:
    
    # Check cancellation before each major step
    cancellation_token.check_cancellation("validation")
    progress_manager.update_progress(1, "Validating symbol and timeframe")
    # ... validation logic
    
    cancellation_token.check_cancellation("local data check")
    progress_manager.update_progress(2, "Checking local data")
    # ... local data logic
    
    # Continue adding cancellation checks at each step
    # ...
```

### **Day 5: Test and Validate Slice 2**

**Testing Requirements**:
- [ ] All existing functionality preserved
- [ ] Cancellation works during data loading operations
- [ ] Cancellation response time < 1 second
- [ ] Proper cleanup when operations are cancelled
- [ ] No resource leaks from cancellation tokens

**Deliverables**:
- ✅ Universal cancellation system
- ✅ DataManager.load_data() supports cancellation
- ✅ Clean exception handling for cancelled operations
- ✅ Token cleanup prevents memory leaks

---

## 🎭 **SLICE 3: ORCHESTRATION FRAMEWORK**
**Duration**: 1 week  
**Goal**: Add coordinated async execution to the same DataManager operation

### **Day 1-2: Build Minimal AsyncOrchestrationFramework**

**Create**: `ktrdr/async/orchestration.py`
```python
@dataclass
class AsyncOperation:
    """Generic async operation definition."""
    operation_id: str
    operation_type: str  # "data_load", "model_train", etc.
    total_steps: int
    context: dict[str, Any] = field(default_factory=dict)
    estimated_duration: Optional[timedelta] = None

class AsyncOrchestrationFramework:
    """Generic orchestration for all async operations."""
    
    def __init__(self):
        self.cancellation_system = CancellationSystem()
    
    def execute_operation(self, 
                         operation: AsyncOperation,
                         operation_func: Callable,
                         progress_renderer: Optional[ProgressRenderer] = None,
                         progress_callback: Optional[Callable] = None) -> Any:
        """Execute operation with full orchestration."""
        
        # Create cancellation token
        cancellation_token = self.cancellation_system.create_token(operation.operation_id)
        
        # Create progress manager
        progress_manager = GenericProgressManager(
            callback=progress_callback,
            renderer=progress_renderer,
            cancellation_token=cancellation_token
        )
        
        try:
            # Start operation tracking
            progress_manager.start_operation(
                operation_id=operation.operation_id,
                total_steps=operation.total_steps,
                context=operation.context
            )
            
            # Execute the operation function
            result = operation_func(
                operation=operation,
                progress_manager=progress_manager,
                cancellation_token=cancellation_token
            )
            
            progress_manager.complete_operation()
            return result
            
        except OperationCancelledException:
            logger.info(f"Operation {operation.operation_id} was cancelled")
            raise
        except Exception as e:
            logger.error(f"Operation {operation.operation_id} failed: {e}")
            raise
        finally:
            self.cancellation_system.cleanup_token(operation.operation_id)
    
    def cancel_operation(self, operation_id: str) -> bool:
        """Cancel a running operation."""
        return self.cancellation_system.cancel_operation(operation_id)
```

### **Day 3-4: Integrate Orchestration with DataManager**

**Update**: `ktrdr/data/data_manager.py`
```python
from ktrdr.async.orchestration import AsyncOrchestrationFramework, AsyncOperation

class DataManager(ServiceOrchestrator):
    def __init__(self):
        # ... existing init
        self._async_orchestration = AsyncOrchestrationFramework()
    
    def load_data(self, symbol: str, timeframe: str, mode: str = "local",
                  progress_callback: Optional[Callable] = None, **kwargs) -> pd.DataFrame:
        """Load data using orchestration framework."""
        
        # Create operation definition
        operation = AsyncOperation(
            operation_id=f"load_data_{symbol}_{timeframe}_{datetime.now().isoformat()}",
            operation_type="data_load",
            total_steps=5,
            context={
                'symbol': symbol,
                'timeframe': timeframe,
                'mode': mode,
                **kwargs  # Additional context
            }
        )
        
        # Execute through orchestration framework
        return self._async_orchestration.execute_operation(
            operation=operation,
            operation_func=self._perform_data_load,
            progress_renderer=self._generic_progress_renderer,
            progress_callback=progress_callback
        )
    
    def _perform_data_load(self, 
                          operation: AsyncOperation, 
                          progress_manager: GenericProgressManager,
                          cancellation_token: CancellationToken) -> pd.DataFrame:
        """Actual data loading implementation."""
        
        # Extract parameters from operation context
        symbol = operation.context['symbol']
        timeframe = operation.context['timeframe']
        mode = operation.context['mode']
        
        # Use existing _load_with_fallback with orchestration components
        return self._load_with_fallback(
            symbol=symbol,
            timeframe=timeframe,
            mode=mode,
            progress_manager=progress_manager,
            cancellation_token=cancellation_token,
            **{k: v for k, v in operation.context.items() 
               if k not in ['symbol', 'timeframe', 'mode']}
        )
    
    def cancel_data_load(self, operation_id: str) -> bool:
        """Cancel data loading operation."""
        return self._async_orchestration.cancel_operation(operation_id)
```

### **Day 5: Test and Validate Slice 3**

**Testing Requirements**:
- [ ] All existing functionality preserved
- [ ] Operations now go through orchestration framework
- [ ] Better error handling and resource management
- [ ] Operation cancellation works through orchestration
- [ ] Clean logging and monitoring of operations

**Deliverables**:
- ✅ Complete orchestration framework
- ✅ DataManager using orchestrated execution
- ✅ Unified progress, cancellation, and error handling
- ✅ Foundation ready for training system integration

---

## 🧠 **SLICE 4: TRAINING SYSTEM INTEGRATION**
**Duration**: 1 week  
**Goal**: Use same infrastructure for training operations

### **Day 1: Build Training Progress Renderer**

**Create**: `ktrdr/training/async/training_progress_renderer.py`
```python
from ktrdr.async.progress import ProgressRenderer, GenericProgressState

class TrainingProgressRenderer(ProgressRenderer):
    """Renders progress messages for training operations."""
    
    def render_message(self, state: GenericProgressState) -> str:
        """Render progress message with training context."""
        context = state.context
        base_message = self._extract_base_message(state.message)
        
        # Add training-specific context
        parts = [base_message]
        
        model_type = context.get('model_type')
        symbols = context.get('symbols', [])
        timeframes = context.get('timeframes', [])
        
        if model_type:
            context_parts = [model_type]
            
            if symbols:
                # Show first 2 symbols, indicate if more
                symbol_str = ', '.join(symbols[:2])
                if len(symbols) > 2:
                    symbol_str += f" (+{len(symbols)-2} more)"
                context_parts.append(f"on {symbol_str}")
            
            if timeframes:
                tf_str = ', '.join(timeframes[:2])
                if len(timeframes) > 2:
                    tf_str += f" (+{len(timeframes)-2} more)"
                context_parts.append(f"[{tf_str}]")
            
            parts.append(f"({' '.join(context_parts)})")
        
        # Add step progress
        if state.total_steps > 0:
            parts.append(f"[{state.current_step}/{state.total_steps}]")
        
        return " ".join(parts)
    
    def _extract_base_message(self, message: str) -> str:
        """Extract base message without previous context."""
        return message
```

### **Day 2-3: Create Training Domain Interface**

**Create**: `ktrdr/training/async/training_domain_interface.py`
```python
from ktrdr.async.orchestration import AsyncOrchestrationFramework, AsyncOperation
from ktrdr.training.async.training_progress_renderer import TrainingProgressRenderer

class TrainingDomainInterface:
    """Bridges training operations to generic async framework."""
    
    def __init__(self, orchestrator: Optional[AsyncOrchestrationFramework] = None):
        self.orchestrator = orchestrator or AsyncOrchestrationFramework()
        self.progress_renderer = TrainingProgressRenderer()
    
    def execute_training(self,
                        strategy_config_path: str,
                        symbols: list[str],
                        timeframes: list[str],
                        start_date: str,
                        end_date: str,
                        validation_split: float = 0.2,
                        data_mode: str = "local",
                        progress_callback: Optional[Callable] = None) -> dict[str, Any]:
        """Execute training using generic async framework."""
        
        operation = AsyncOperation(
            operation_id=f"train_{len(symbols)}symbols_{datetime.now().isoformat()}",
            operation_type="model_train",
            total_steps=4,  # Training-specific step count
            context={
                'model_type': 'mlp',  # Could extract from config
                'symbols': symbols,
                'timeframes': timeframes,
                'strategy_config_path': strategy_config_path,
                'start_date': start_date,
                'end_date': end_date,
                'validation_split': validation_split,
                'data_mode': data_mode
            }
        )
        
        return self.orchestrator.execute_operation(
            operation=operation,
            operation_func=self._perform_training,
            progress_renderer=self.progress_renderer,
            progress_callback=progress_callback
        )
    
    def _perform_training(self,
                         operation: AsyncOperation,
                         progress_manager: GenericProgressManager,
                         cancellation_token: CancellationToken) -> dict[str, Any]:
        """Actual training implementation using orchestration components."""
        
        # Extract parameters from operation context
        context = operation.context
        
        # Step 1: Setup
        progress_manager.update_progress(1, "Setting up training environment")
        # ... setup logic with cancellation checks
        
        # Step 2: Data preparation
        cancellation_token.check_cancellation("data preparation")
        progress_manager.update_progress(2, "Preparing training data")
        # ... data prep logic
        
        # Step 3: Model training
        cancellation_token.check_cancellation("model training")
        progress_manager.update_progress(3, "Training model")
        # ... actual training logic
        
        # Step 4: Validation
        cancellation_token.check_cancellation("validation")
        progress_manager.update_progress(4, "Validating results")
        # ... validation logic
        
        return {
            "success": True,
            "operation_id": operation.operation_id,
            # ... other results
        }
    
    def cancel_training(self, operation_id: str) -> bool:
        """Cancel training operation."""
        return self.orchestrator.cancel_operation(operation_id)
```

### **Day 4: Update TrainingManager to Use Domain Interface**

**Update**: `ktrdr/training/training_manager.py`
```python
from ktrdr.training.async.training_domain_interface import TrainingDomainInterface

class TrainingManager(ServiceOrchestrator):
    def __init__(self):
        # ... existing init
        self._training_domain = TrainingDomainInterface()
    
    def train_multi_symbol_strategy(self,
                                   strategy_config_path: str,
                                   symbols: list[str],
                                   timeframes: list[str],
                                   start_date: str,
                                   end_date: str,
                                   validation_split: float = 0.2,
                                   data_mode: str = "local",
                                   progress_callback=None) -> dict[str, Any]:
        """Train strategy using generic async infrastructure."""
        
        return self._training_domain.execute_training(
            strategy_config_path=strategy_config_path,
            symbols=symbols,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date,
            validation_split=validation_split,
            data_mode=data_mode,
            progress_callback=progress_callback
        )
    
    def cancel_training(self, operation_id: str) -> bool:
        """Cancel training operation."""
        return self._training_domain.cancel_training(operation_id)
```

### **Day 5: Test and Validate Slice 4**

**Testing Requirements**:
- [ ] Training operations use same infrastructure as data operations
- [ ] Training-specific progress messages with model/symbol context
- [ ] Training operations can be cancelled consistently
- [ ] Same orchestration patterns for both data and training
- [ ] All existing training functionality preserved

**Deliverables**:
- ✅ Training system using generic async infrastructure
- ✅ Training-specific progress rendering
- ✅ Consistent patterns between data and training systems
- ✅ Both systems benefit from shared infrastructure

---

## 🌐 **SLICE 5: HOST SERVICE INTEGRATION**
**Duration**: 1 week  
**Goal**: Add generic host service support to orchestration framework

### **Day 1-2: Extract Generic AsyncHostService**

**Update**: `ktrdr/async/host_service.py` (move from managers)
```python
# Remove all domain-specific integrations
# Use CancellationSystem instead of embedded cancellation
# Make it pure HTTP infrastructure

class AsyncHostService(ABC):
    """Generic host service base - no domain knowledge."""
    
    def __init__(self, config: HostServiceConfig):
        self.config = config
        self._http_client: Optional[httpx.AsyncClient] = None
        # Remove _current_cancellation_token - will use CancellationSystem
    
    # Remove _check_cancellation method
    # Cancellation handled by CancellationSystem at operation level
    
    async def _call_host_service_post(self, endpoint: str, data: dict[str, Any],
                                     cancellation_token: Optional[CancellationToken] = None) -> dict[str, Any]:
        """POST request with external cancellation token."""
        
        for attempt in range(self.max_retries + 1):
            try:
                # Check cancellation using external token
                if cancellation_token:
                    cancellation_token.check_cancellation(f"POST {endpoint} attempt {attempt + 1}")
                
                # ... rest of HTTP logic
                
            except OperationCancelledException:
                # Let cancellation bubble up
                raise
            # ... rest of retry logic
```

### **Day 3-4: Integrate Host Services with Orchestration**

**Update**: Both IB and Training adapters to use generic host service
```python
# Update IbDataAdapter and TrainingAdapter to:
# 1. Use generic AsyncHostService
# 2. Pass cancellation tokens from orchestration
# 3. Benefit from shared connection pooling

class IbDataAdapter(AsyncHostService):
    async def fetch_data(self, symbol: str, timeframe: str,
                        cancellation_token: Optional[CancellationToken] = None) -> pd.DataFrame:
        """Fetch data with orchestration-provided cancellation."""
        
        return await self._call_host_service_post(
            "/data/fetch",
            {"symbol": symbol, "timeframe": timeframe},
            cancellation_token=cancellation_token
        )

class TrainingAdapter(AsyncHostService):
    async def start_training(self, config: dict,
                            cancellation_token: Optional[CancellationToken] = None) -> dict:
        """Start training with orchestration-provided cancellation."""
        
        return await self._call_host_service_post(
            "/training/start",
            config,
            cancellation_token=cancellation_token
        )
```

### **Day 5: Test and Validate Slice 5**

**Testing Requirements**:
- [ ] Both IB and training host services use generic infrastructure
- [ ] Connection pooling benefits both systems
- [ ] Consistent cancellation behavior across all host service calls
- [ ] No domain-specific coupling in AsyncHostService
- [ ] Performance improvements measurable

**Deliverables**:
- ✅ Generic AsyncHostService without domain coupling
- ✅ Both data and training systems benefit from connection pooling
- ✅ Unified cancellation across all host service communication
- ✅ Complete generic async infrastructure serving both systems

---

## 🎯 **SLICE COMPLETION CRITERIA**

Each slice is considered complete when:

### **Functional Requirements**
- [ ] All existing functionality preserved
- [ ] New capabilities working and tested
- [ ] Integration tests pass
- [ ] No breaking changes to public APIs

### **Quality Requirements**  
- [ ] Code coverage maintained or improved
- [ ] Performance maintained or improved
- [ ] Memory usage stable
- [ ] Error handling comprehensive

### **Documentation Requirements**
- [ ] New APIs documented
- [ ] Integration examples provided
- [ ] Migration notes updated
- [ ] Architecture diagrams current

### **Integration Requirements**
- [ ] Works with rest of system
- [ ] No conflicts with existing patterns
- [ ] Clean interfaces between components
- [ ] Proper error propagation

## 🚀 **BENEFITS OF VERTICAL SLICE APPROACH**

### **1. Continuous Value Delivery**
- **Slice 1**: Better progress reporting for data operations
- **Slice 2**: Cancellation support for data operations
- **Slice 3**: Full orchestration benefits for data operations  
- **Slice 4**: Training automatically gets all benefits
- **Slice 5**: Both systems benefit from host service improvements

### **2. Risk Mitigation**
- Small, testable changes at each step
- Can rollback individual slices without affecting others
- Problems discovered immediately when they're small
- Always have working system to fall back to

### **3. Early Validation**
- Architecture decisions validated with real code
- Performance impacts measured incrementally
- User experience improvements visible early
- Adjustments possible based on learning

### **4. Flexible Timeline**
- Can pause after any slice with improved system
- Each slice independently valuable
- Priorities can be adjusted between slices
- Clear checkpoints for stakeholder review

## 📊 **SUCCESS METRICS**

### **After Slice 1**
- [ ] GenericProgressManager working in production
- [ ] Better progress messages for data operations
- [ ] Foundation established for further slices

### **After Slice 3**  
- [ ] Complete orchestration framework operational
- [ ] One subsystem (data) fully integrated
- [ ] Performance improvements measurable

### **After Slice 5**
- [ ] Both data and training systems use shared infrastructure
- [ ] Zero domain knowledge in generic components
- [ ] 30%+ performance improvement from connection pooling
- [ ] Easy to add new operation types in any domain

## 🎉 **FINAL OUTCOME**

This vertical implementation delivers:
- **Working improvements every week**
- **Complete generic async infrastructure**
- **Both data and training systems integrated**
- **Easy extensibility for future systems**
- **Proven architecture through incremental validation**

Each slice builds on the previous one while delivering immediate value, ensuring you always have a working, improved system that can be shipped at any point.