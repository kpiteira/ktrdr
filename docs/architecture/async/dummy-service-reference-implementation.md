# DummyService Reference Implementation Specification

## Purpose

This document specifies the **most awesome yet simple** reference implementation for the ServiceOrchestrator async pattern. The DummyService demonstrates the perfect way to build async operations - clean, simple, and powerful.

## Vision: The Perfect Async Service

Create a **beautifully simple** service that:

1. **ServiceOrchestrator handles ALL complexity** - no manual async code needed
2. **Clean domain logic** - just a simple loop with progress
3. **Perfect UX** - smooth progress bars and instant cancellation
4. **Zero boilerplate** - minimal code, maximum power

## Architecture Overview

```text
CLI Command → API Endpoint → DummyService → Enhanced ServiceOrchestrator → Simple Domain Logic
     ↓              ↓              ↓                    ↓                           ↓
Progress Bar    Super Simple   One Method Call   Handles EVERYTHING           Cancellable Loop
Cancellation      Endpoint      to Orchestrator   - Operations Service        (2s per iteration)
                                                   - Progress Tracking
                                                   - Cancellation
                                                   - API Response Format
```

### The Beauty: ServiceOrchestrator Does EVERYTHING

1. **Enhanced ServiceOrchestrator** - handles ALL async complexity including operations service
2. **DummyService** - extends ServiceOrchestrator, calls it with one method  
3. **API Endpoint** - trivially simple: just calls DummyService
4. **CLI Command** - provides awesome UX

That's it! ServiceOrchestrator is the hero that eliminates ALL complexity.

## ServiceOrchestrator Enhancements Required

**First, we need to enhance ServiceOrchestrator with operations service integration:**

```python
# Add to ServiceOrchestrator base class:

async def start_managed_operation(
    self,
    operation_name: str,
    operation_type: str,  # For OperationType enum
    operation_func: Callable,
    *args,
    **kwargs
) -> dict[str, Any]:
    """
    Start operation with full management:
    - Creates operation ID via operations service
    - Handles background task execution 
    - Manages progress tracking integration
    - Handles cancellation coordination
    - Returns proper API response format
    
    Returns:
        {
            "operation_id": "op_xxx",
            "status": "started", 
            "message": "Operation started"
        }
    """

def run_sync_operation(
    self,
    operation_name: str,
    operation_func: Callable, 
    *args,
    **kwargs
) -> dict[str, Any]:
    """
    Run operation synchronously with progress/cancellation support.
    Uses _run_async_method pattern but integrates with progress system.
    
    Returns:
        Direct results from operation_func
    """
```

## Component Specifications

### 1. DummyService (`ktrdr/api/services/dummy_service.py`)

**Purpose**: The most awesome yet simple async service ever!

```python
class DummyService(ServiceOrchestrator):
    """The perfect async service - simple, clean, powerful."""
    
    # Required ServiceOrchestrator abstract methods (minimal implementation for dummy)
    def _initialize_adapter(self) -> None:
        """No adapter needed for dummy service."""
        return None
    
    def _get_service_name(self) -> str:
        return "DummyService"
    
    def _get_default_host_url(self) -> str:
        return "http://localhost:8000"  # Not used for dummy
    
    def _get_env_var_prefix(self) -> str:
        return "DUMMY"  # Not used for dummy
    
    async def start_dummy_task(self) -> dict[str, Any]:
        """
        Start dummy task with full ServiceOrchestrator management.
        
        ServiceOrchestrator handles ALL complexity:
        - Operation creation & tracking
        - Progress reporting  
        - Cancellation support
        - API response formatting
        
        Simple: no parameters, runs 200s (100 iterations)
            
        Returns:
            API response with operation_id for async tracking
        """
        # ServiceOrchestrator handles EVERYTHING - one method call!
        return await self.start_managed_operation(
            operation_name="dummy_task",
            operation_type="DUMMY",  # For OperationType enum
            operation_func=self._run_dummy_task_async
        )
    
    def run_dummy_task_sync(self) -> dict[str, Any]:
        """
        Run dummy task synchronously (for CLI direct usage).
        
        ServiceOrchestrator still handles progress and cancellation,
        but returns results directly instead of operation tracking.
        
        Simple: no parameters, runs 200s (100 iterations)
            
        Returns:
            Direct results dict
        """
        # ServiceOrchestrator handles sync execution with progress/cancellation
        return self.run_sync_operation(
            operation_name="dummy_task",
            operation_func=self._run_dummy_task_async
        )
    
    async def _run_dummy_task_async(self) -> dict[str, Any]:
        """The actual work - clean domain logic with cancellation."""
        
        duration_seconds = 200  # Simple: hardcoded 200s = 100 iterations  
        iterations = duration_seconds // 2  # 2 seconds per iteration
        
        for i in range(iterations):
            # ServiceOrchestrator provides cancellation - just check it!
            cancellation_token = self.get_current_cancellation_token()
            if cancellation_token and cancellation_token.is_cancelled():
                return {
                    "status": "cancelled", 
                    "iterations_completed": i,
                    "message": f"Stopped after {i} iterations"
                }
            
            # Do the work (simulate with sleep)
            await asyncio.sleep(2)
            
            # Report progress via ServiceOrchestrator
            self.update_operation_progress(
                step=i + 1,
                message=f"Working hard on iteration {i+1}!",
                items_processed=i + 1,
                context={
                    "current_step": f"Iteration {i+1}/{iterations}",
                    "current_item": f"Processing step {i+1}"
                }
            )
        
        # Success! 
        return {
            "status": "success", 
            "iterations_completed": iterations,
            "total_duration_seconds": duration_seconds,
            "message": f"Completed all {iterations} iterations!"
        }
```

### 2. API Endpoint (`ktrdr/api/endpoints/dummy.py`)

**Purpose**: Super simple endpoint that calls DummyService directly

```python
from ktrdr.api.services.dummy_service import DummyService

@router.post(
    "/dummy/start",
    response_model=DummyOperationResponse,
    tags=["Dummy"],
    summary="Start awesome dummy task",
    description="The most beautiful async operation ever - ServiceOrchestrator handles everything!"
)
async def start_dummy_task() -> DummyOperationResponse:
    """Start the most awesome dummy task ever! ServiceOrchestrator does ALL the work!"""
    
    try:
        # ServiceOrchestrator handles EVERYTHING - operations service, progress, cancellation!
        dummy_service = DummyService()
        result = await dummy_service.start_dummy_task()
        
        # ServiceOrchestrator already formatted the response perfectly
        return DummyOperationResponse(
            success=True,
            data=result  # Contains operation_id, status, etc.
        )
        
    except Exception as e:
        return DummyOperationResponse(
            success=False,
            error={"code": "DUMMY-001", "message": f"Failed to start: {e}"}
        )
```

### 3. CLI Command (`ktrdr/cli/dummy_commands.py`)

**Purpose**: Beautiful CLI with awesome UX - progress bars and instant cancellation!

```python
@cli.command("dummy")
def dummy_task():
    """
    Run the most awesome dummy task ever!
    
    Features:
    - 🎯 Perfect progress reporting - exactly like data loading
    - 🛑 Instant cancellation with Ctrl+C  
    - 🚀 ServiceOrchestrator handles ALL complexity
    - ✨ Same beautiful UX as all KTRDR operations
    
    Simple: no parameters, just runs 200s (100 iterations)
    """
    
    try:
        # CLI calls API endpoint - exact same pattern as data loading!
        async def run_async():
            manager = AsyncOperationManager()
            handler = DummyOperationHandler()
            
            return await manager.execute_operation(
                handler=handler,
                operation_params={},  # No parameters needed
                console=Console(),
                show_progress=True,
                verbose=False,
                quiet=False,
            )
        
        result = asyncio.run(run_async())
        
        # Beautiful result reporting (same style as data loading)
        if result and result.get("status") == "success":
            click.echo(f"✅ Completed {result['iterations_completed']} iterations")
        elif result and result.get("status") == "cancelled":
            iterations = result.get('iterations_completed', 0)
            click.echo(f"🛑 Cancelled after {iterations} iterations")
        else:
            click.echo("❌ Task failed")
            
    except KeyboardInterrupt:
        click.echo("\n🛑 Cancelled by user")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise click.ClickException(str(e))


class DummyOperationHandler(DomainOperationHandler):
    """Handler for the AsyncOperationManager - calls API endpoint!"""
    
    async def start_operation(self, operation_params: dict) -> dict:
        """Start the dummy operation via API."""
        api_client = get_api_client()
        return await api_client.start_dummy_task()  # No parameters
    
    def get_operation_name(self) -> str:
        return "dummy_task"
    
    def get_operation_context(self) -> dict:
        return {"type": "dummy", "description": "Awesome demo task"}
    
    async def process_final_results(self, final_response: dict, operation_params: dict):
        """Process results - just return them!"""
        return final_response.get("data", {}).get("result_summary", {})

```

## Data Models

```python
# Beautiful simple data models (no parameters needed!)
class DummyOperationResponse(BaseModel):
    success: bool
    data: Optional[dict] = None  # Contains operation_id, status, message
    error: Optional[dict] = None
```

## Usage Examples

### CLI Usage - The Most Beautiful UX Ever!

```bash
# Run the awesome dummy task (200 seconds, 100 iterations - exact same UX as data loading!)
ktrdr dummy
# ⚡ Process 100 iterations: Iteration 50/100: Working hard on iteration 50! (5/100) (DUMMY, full mode) ——————————————— 50% 50/100 0:01:40 0:01:40

# When complete:
# ✅ Completed 100 iterations

# Test cancellation (press Ctrl+C during execution)
ktrdr dummy  
# ⚡ Process 100 iterations: Iteration 20/100: Working hard on iteration 20! (20/100) (DUMMY, full mode) ———————           20% 20/100 0:00:40 0:02:40
# ^C 🛑 Cancelled after 20 iterations
```

### API Usage - Simple and Clean!

```bash
# Start the awesome operation (no parameters - simple!)
curl -X POST "http://localhost:8000/api/v1/dummy/start"

# Beautiful response
{
  "success": true,
  "data": {
    "operation_id": "op_dummy_awesome_123",
    "status": "started", 
    "message": "Started awesome 200s dummy task!"
  }
}

# Check progress (watch it grow!)
curl "http://localhost:8000/api/v1/operations/op_dummy_awesome_123/status"
{
  "success": true,
  "data": {
    "status": "running",
    "progress": {
      "percentage": 45.0,
      "current_step": "Working hard on iteration 45/100"
    }
  }
}

# Cancel gracefully
curl -X POST "http://localhost:8000/api/v1/operations/op_dummy_awesome_123/cancel"
# Operation stops within 2 seconds!
```

## Expected Behavior

### ✨ The Magic Experience

**Perfect Progress Reporting:**
- 🎯 **Duration**: Configurable (default: 200s = 100 iterations)
- ⏱️ **Updates**: Every 2 seconds (smooth 1% increments)
- 📊 **Progress Bar**: Beautiful real-time advancement 
- 💬 **Messages**: "Working hard on iteration X!" 

**Instant Cancellation:**
- 🛑 **Trigger**: Ctrl+C in CLI or API cancel request
- ⚡ **Response**: Immediate "Cancelled gracefully" message
- 🧹 **Cleanup**: Background task stops within 2 seconds maximum
- 📈 **Status**: Returns exactly how many iterations completed

**Perfect Error Handling:**
- 🎯 **Service Errors**: Beautiful, helpful messages 
- 🔄 **Network Issues**: Graceful degradation
- ✅ **Input Validation**: Clear, friendly error messages

## 🏆 Success Criteria - The Gold Standard!

1. **✨ Magical Simplicity**: ServiceOrchestrator handles ALL complexity
2. **🎨 Beautiful UX**: Smooth progress bars and instant cancellation
3. **🧠 Smart Architecture**: Clean separation of concerns
4. **⚡ Lightning Fast**: Cancellation responds within 2 seconds
5. **📊 Perfect Progress**: Exactly 1% every 2 seconds
6. **🛡️ Bulletproof**: Handles every error scenario gracefully
7. **🔄 Consistent**: Same UX patterns across all KTRDR operations

## 🚀 Implementation Phases

**Phase 1: The Foundation** 
- Enhance ServiceOrchestrator with operations service integration
- Add `start_managed_operation()` and `run_sync_operation()` methods

**Phase 2: The Service**
- DummyService implementation (extends enhanced ServiceOrchestrator)

**Phase 3: The Interfaces**
- API Endpoint (trivially simple)
- CLI Command (beautiful UX)

**Phase 4: The Validation**
- Testing the enhanced ServiceOrchestrator
- Testing DummyService awesome features
- Proving it eliminates ALL complexity

## 🎯 The Ultimate Goal

Create the **perfect reference** that proves ServiceOrchestrator is:
- ✨ **Simple** - minimal boilerplate code
- 🎯 **Powerful** - handles all async complexity
- 🎨 **Beautiful** - amazing user experience  
- 🛡️ **Reliable** - bulletproof error handling
- 🔄 **Consistent** - same patterns everywhere

**This will be the template for ALL future async services!**