# KTRDR Async Standard - One Pattern for All Services

## Goal: Consistency and Simplicity

You have two working async patterns that are **almost the same** but implemented differently. This creates maintenance overhead and complexity. 

The goal is to create **one standard pattern** that both data and training services can use consistently.

## The Standard: Host Service Pattern

Based on your successful IB Host Service implementation, here's the standard pattern that every service should follow:

### Layer 1: CLI - Keep Current Pattern for Now
Your CLI pattern works and isn't the main problem. Keep using:
```python
@app.command("command")
def command_name(...):
    asyncio.run(_command_async(...))
```

This pattern is **consistent across both data and training** and can be optimized later if needed.

### Layer 2: API - Keep Current FastAPI Pattern 
Your FastAPI endpoints are properly async and consistent. Keep them as-is:
```python
@router.post("/endpoint")
async def endpoint_handler(request: RequestModel, service: Service = Depends(get_service)):
    return await service.method(...)
```

### Layer 3: Service Layer - **Make Consistent** 
This is where the inconsistency lives. Standardize on the **training pattern** (which is better):

**Standard Service Pattern:**
```python
class StandardService:
    def __init__(self):
        self.manager = AsyncManager()  # Always async manager
    
    async def service_method(self, ...):
        return await self.manager.async_operation(...)  # Always async calls
```

### Layer 4: Manager Layer - **Async Interface Standard**
Standardize on the **TrainingManager async pattern** (which is better than DataManager):

**Standard Manager Pattern:**
```python
class AsyncManager:
    def __init__(self):
        self.adapter = StandardAdapter(
            use_host_service=self._should_use_host_service(),
            host_service_url=self._get_service_url()
        )
    
    async def operation(self, ...):
        return await self.adapter.execute_operation(...)
```

### Layer 5: Adapter Layer - **Unified Host Service Pattern**
Create one standard adapter that both data and training can inherit from:

**Standard Adapter Pattern:**
```python
class HostServiceAdapter:
    """Standard pattern for all host service communication."""
    
    def __init__(self, service_name: str, use_host_service: bool = False, 
                 host_service_url: str = None, fallback_implementation=None):
        self.service_name = service_name
        self.use_host_service = use_host_service
        self.host_service_url = host_service_url
        self.fallback_implementation = fallback_implementation
        self._http_client = None
    
    async def execute_operation(self, operation: str, data: dict):
        if self.use_host_service:
            return await self._call_host_service(operation, data)
        else:
            return await self._call_fallback(operation, data)
    
    async def _call_host_service(self, operation: str, data: dict):
        # Standard HTTP service call
        client = await self._get_client()
        response = await client.post(f"{self.host_service_url}/{operation}", json=data)
        if response.status_code == 200:
            return response.json()
        else:
            raise ServiceError(f"{self.service_name} service error: {response.text}")
    
    async def _call_fallback(self, operation: str, data: dict):
        # Delegate to fallback implementation
        return await self.fallback_implementation.execute(operation, data)
```

## Implementation Plan: Minimal Changes for Maximum Consistency

### Step 1: Create Standard Base Classes (Week 1)
Create the standard base classes that both data and training can use:

```python
# ktrdr/base/host_service_adapter.py
class HostServiceAdapter:
    # Standard implementation above

# ktrdr/base/async_manager.py  
class AsyncManager:
    # Standard async manager pattern

# ktrdr/base/service_base.py
class AsyncService:
    # Standard service pattern
```

### Step 2: Refactor DataManager to Be Async (Week 2)
The biggest change: make DataManager async to match TrainingManager:

```python
# ktrdr/data/data_manager.py - NEW async interface
class DataManager(AsyncManager):
    def __init__(self):
        self.adapter = DataAdapter(
            use_host_service=self._should_use_ib_host_service(),
            host_service_url=self._get_ib_service_url(),
            fallback_implementation=LocalDataProvider()
        )
    
    async def load_data(self, symbol: str, timeframe: str, mode: str = "local"):
        # Now async instead of sync
        return await self.adapter.execute_operation("load_data", {
            "symbol": symbol,
            "timeframe": timeframe,
            "mode": mode
        })
```

### Step 3: Update DataService to Use Async DataManager (Week 2)
Simple change - remove the sync call:

```python
# ktrdr/api/services/data_service.py - FIX the sync bottleneck
async def load_data(self, symbol: str, timeframe: str, ...):
    # Change from sync call to async call
    df = await self.data_manager.load_data(symbol, timeframe, mode)  # Now async!
```

### Step 4: Standardize Both Adapters (Week 3)
Refactor both adapters to inherit from the same base:

```python
# ktrdr/data/data_adapter.py - Inherits from standard
class DataAdapter(HostServiceAdapter):
    def __init__(self, use_host_service=False, host_service_url=None):
        super().__init__(
            service_name="data",
            use_host_service=use_host_service,
            host_service_url=host_service_url or "http://localhost:5001",
            fallback_implementation=LocalDataProvider()
        )

# ktrdr/training/training_adapter.py - Inherits from standard  
class TrainingAdapter(HostServiceAdapter):
    def __init__(self, use_host_service=False, host_service_url=None):
        super().__init__(
            service_name="training", 
            use_host_service=use_host_service,
            host_service_url=host_service_url or "http://localhost:5002",
            fallback_implementation=LocalTrainingProvider()
        )
```

## The Result: One Consistent Pattern

After this standardization:

### Same Pattern Everywhere
- **CLI**: Same `asyncio.run()` pattern for all commands
- **API**: Same FastAPI async pattern for all endpoints  
- **Service**: Same async service pattern for all services
- **Manager**: Same async manager pattern for all managers
- **Adapter**: Same host service adapter pattern for all adapters

### Easy to Understand
- New developers learn **one pattern** and can work on any service
- Code reviews are easier because patterns are consistent
- Testing strategies are reusable across services

### Easy to Maintain
- Bug fixes in the base adapter benefit all services
- Performance improvements benefit all services
- One place to update HTTP client configuration

### Easy to Extend
- Adding new services (futures, options, news, etc.) follows the same pattern
- Host services all follow the same communication protocol
- Error handling is consistent across all services

## Migration Risk: Very Low

This isn't a rewrite - it's **standardization of existing patterns**:

1. **CLI stays the same** - no changes needed
2. **API stays the same** - no changes needed  
3. **Services get simpler** - removing sync bottlenecks
4. **Managers become consistent** - DataManager matches TrainingManager pattern
5. **Adapters share code** - reducing duplication

The only **real change** is making DataManager async, which removes the sync bottleneck that's causing problems anyway.

## Expected Outcome

- **Consistent async patterns** across all services
- **Simpler codebase** with shared base classes
- **Easier debugging** because all services work the same way
- **Better performance** because sync bottlenecks are removed
- **Easier testing** because patterns are consistent

This gives you the **consistency and simplicity** you're looking for while building on the patterns that already work well in your system.