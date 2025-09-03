# KTRDR MCP Server Compatibility Upgrade Plan

**Date**: 2025-01-09  
**Objective**: Update MCP server to work with multi-symbol/multi-timeframe training API  
**Scope**: Fix 3 critical issues + 1 minor issue to achieve 100% compatibility  
**Estimated Duration**: 6-8 hours implementation + 2-4 hours testing

## Executive Summary

The recent introduction of multi-symbol and multi-timeframe training in the KTRDR backend API has created compatibility issues with the MCP server. This plan provides a structured approach to update the MCP server while maintaining backward compatibility and improving the user experience.

**Current Status**: 20/25 tools (80%) compatible  
**Target Status**: 25/25 tools (100%) compatible  
**Risk Level**: LOW - Well-defined changes with clear rollback paths

## Problem Analysis

### Root Cause
The backend API was enhanced to support training across multiple symbols and timeframes simultaneously, but the MCP server still assumes single-symbol/single-timeframe training from the previous API version.

### Impact Assessment
- **HIGH**: Neural network training pipeline completely broken (3 tools)
- **MEDIUM**: Response format parsing issue (1 tool)  
- **LOW**: Dependency cleanup and optimization opportunities

## Implementation Strategy

### Approach: Evolutionary Upgrade
- **Maintain MCP user interface** - Users continue to specify single symbol/timeframe
- **Internal adaptation layer** - Convert single values to arrays for backend compatibility
- **Preserve all existing functionality** - No breaking changes to MCP tool signatures
- **Add enhancement opportunities** - Support multi-symbol training in future versions

## Phase 1: Critical Fixes (Priority: HIGH)

### 1.1 Training Payload Structure Update

**Issue**: MCP sends `{"symbol": str, "timeframe": str}`, backend expects `{"symbols": list[str], "timeframes": list[str], "strategy_name": str}`

**Files to Modify**:
- `mcp/src/api_client.py:249-267` (API client method)
- `mcp/src/server.py:387-466` (MCP tool implementation)

**Implementation**:

```python
# File: mcp/src/api_client.py
# BEFORE (lines 249-267):
async def start_neural_training(
    self,
    symbol: str,
    timeframe: str,
    config: dict[str, Any],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    task_id: Optional[str] = None,
) -> dict[str, Any]:
    payload = {"symbol": symbol, "timeframe": timeframe, "config": config}
    if start_date:
        payload["start_date"] = start_date
    if end_date:
        payload["end_date"] = end_date
    if task_id:
        payload["task_id"] = task_id
    return await self._request("POST", "/trainings/start", json=payload)

# AFTER:
async def start_neural_training(
    self,
    symbols: list[str],  # Changed to list
    timeframes: list[str],  # Changed to list
    strategy_name: str,  # Added required field
    config: Optional[dict[str, Any]] = None,  # Made optional
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    task_id: Optional[str] = None,
    detailed_analytics: bool = False,  # Added backend field
) -> dict[str, Any]:
    """Start neural network training with multi-symbol/multi-timeframe support"""
    payload = {
        "symbols": symbols,
        "timeframes": timeframes,
        "strategy_name": strategy_name,
        "detailed_analytics": detailed_analytics
    }
    
    # Optional fields
    if config:
        payload["config"] = config
    if start_date:
        payload["start_date"] = start_date
    if end_date:
        payload["end_date"] = end_date
    if task_id:
        payload["task_id"] = task_id
    
    return await self._request("POST", "/trainings/start", json=payload)
```

```python
# File: mcp/src/server.py
# BEFORE (lines 387-466):
async def start_model_training(
    experiment_id: str,
    symbol: str,
    timeframe: str = "1h",
    training_config: Optional[dict[str, Any]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    # ... existing logic ...
    training_result = await client.start_neural_training(
        symbol=symbol,
        timeframe=timeframe,
        config=default_config,
        start_date=start_date,
        end_date=end_date,
        task_id=task_id,
    )

# AFTER:
async def start_model_training(
    experiment_id: str,
    symbol: str,  # Keep single symbol for MCP user interface
    timeframe: str = "1h",  # Keep single timeframe for MCP user interface
    strategy_name: Optional[str] = None,  # Add optional strategy name
    training_config: Optional[dict[str, Any]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    detailed_analytics: bool = False,  # Add analytics option
) -> dict[str, Any]:
    """Start neural network model training for a trading strategy
    
    Maintains single-symbol interface for MCP users while supporting
    the backend's multi-symbol/multi-timeframe training API.
    """
    try:
        # Generate strategy name if not provided
        if not strategy_name:
            strategy_name = f"mcp_strategy_{symbol}_{timeframe}_{int(time.time())}"
        
        # Default training configuration
        default_config = {
            "model_type": "mlp",
            "hidden_layers": [64, 32, 16],
            "epochs": 100,
            "learning_rate": 0.001,
            "batch_size": 32,
            "validation_split": 0.2,
            "early_stopping": {"patience": 10, "monitor": "val_accuracy"},
            "optimizer": "adam",
            "dropout_rate": 0.2,
        }
        
        # Merge user config with defaults
        if training_config:
            default_config.update(training_config)
        
        # Generate unique task ID
        task_id = f"train_{symbol}_{timeframe}_{uuid.uuid4().hex[:8]}"
        
        # Convert single values to arrays for backend API
        training_result = await client.start_neural_training(
            symbols=[symbol],  # Convert to array
            timeframes=[timeframe],  # Convert to array
            strategy_name=strategy_name,  # Pass strategy name
            config=default_config,
            start_date=start_date,
            end_date=end_date,
            task_id=task_id,
            detailed_analytics=detailed_analytics,
        )
        
        # ... rest of implementation
```

### 1.2 Training Status Endpoint Fix

**Issue**: MCP calls `GET /trainings/{task_id}` which doesn't exist, only `GET /trainings/{task_id}/performance` exists

**Solution A** (Recommended): Update MCP to use existing endpoint

```python
# File: mcp/src/api_client.py
# BEFORE (lines 269-271):
async def get_training_status(self, task_id: str) -> dict[str, Any]:
    return await self._request("GET", f"/trainings/{task_id}")

# AFTER:
async def get_training_status(self, task_id: str) -> dict[str, Any]:
    """Get training status using the performance endpoint"""
    try:
        # Try the performance endpoint first (more detailed info)
        performance_response = await self._request("GET", f"/trainings/{task_id}/performance")
        
        # Extract status from performance response
        if performance_response.get("success"):
            return {
                "success": True,
                "status": performance_response.get("status", "unknown"),
                "task_id": performance_response.get("task_id", task_id),
                "performance": performance_response
            }
        else:
            return {
                "success": False,
                "status": "error",
                "task_id": task_id,
                "error": performance_response.get("error", "Unknown error")
            }
    except Exception as e:
        logger.error(f"Failed to get training status for {task_id}: {e}")
        return {
            "success": False,
            "status": "error", 
            "task_id": task_id,
            "error": str(e)
        }
```

**Solution B** (Alternative): Add missing endpoint to backend

```python
# File: ktrdr/api/endpoints/training.py
# ADD after line 177 (before start_training endpoint):

class TrainingStatusResponse(BaseModel):
    """Response model for training status check."""
    success: bool
    task_id: str
    status: str  # "pending", "training", "completed", "failed"
    progress: int = 0  # 0-100
    started_at: Optional[str] = None
    estimated_completion: Optional[str] = None
    error: Optional[str] = None

@router.get("/{task_id}/status", response_model=TrainingStatusResponse)
async def get_training_status(
    task_id: str, service: TrainingService = Depends(get_training_service)
) -> TrainingStatusResponse:
    """Get training task status and progress"""
    try:
        status = await service.get_training_status(task_id)
        return TrainingStatusResponse(
            success=True,
            task_id=status["task_id"],
            status=status["status"],
            progress=status.get("progress", 0),
            started_at=status.get("started_at"),
            estimated_completion=status.get("estimated_completion"),
        )
    except ValidationError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to get training status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get training status") from e
```

**Recommendation**: Use **Solution A** to minimize backend changes and leverage existing functionality.

### 1.3 Model Performance Endpoint Verification

**Issue**: Verify `/trainings/{task_id}/performance` works correctly with MCP expectations

**Implementation**: Add robust error handling and response parsing

```python
# File: mcp/src/api_client.py
# BEFORE (lines 273-275):
async def get_model_performance(self, task_id: str) -> dict[str, Any]:
    return await self._request("GET", f"/trainings/{task_id}/performance")

# AFTER:
async def get_model_performance(self, task_id: str) -> dict[str, Any]:
    """Get detailed model performance metrics with robust error handling"""
    try:
        response = await self._request("GET", f"/trainings/{task_id}/performance")
        
        # Validate response structure
        if not response.get("success"):
            return {
                "success": False,
                "task_id": task_id,
                "error": response.get("error", "Performance data not available")
            }
        
        # Ensure all expected fields are present
        performance_data = response.copy()
        performance_data["task_id"] = task_id  # Ensure task_id is included
        
        return performance_data
        
    except Exception as e:
        logger.error(f"Failed to get performance for task {task_id}: {e}")
        return {
            "success": False,
            "task_id": task_id,
            "error": f"Failed to retrieve performance metrics: {str(e)}"
        }
```

**Estimated Time**: 3-4 hours

## Phase 2: Response Format Fixes (Priority: MEDIUM)

### 2.1 Indicators Response Parsing Fix

**Issue**: MCP expects `response.get("indicators", [])` but backend returns standard envelope with `data` key

```python
# File: mcp/src/api_client.py
# BEFORE (lines 167-170):
async def get_indicators(self) -> list[dict[str, Any]]:
    response = await self._request("GET", "/indicators")
    return response.get("indicators", [])

# AFTER:
async def get_indicators(self) -> list[dict[str, Any]]:
    """Get available indicators with correct response parsing"""
    response = await self._request("GET", "/indicators") 
    
    # Handle both old and new response formats for compatibility
    if "data" in response:
        return response.get("data", [])  # Standard envelope format
    elif "indicators" in response:
        return response.get("indicators", [])  # Legacy format
    else:
        logger.warning("Unexpected indicators response format", response=response)
        return []
```

**Estimated Time**: 30 minutes

## Phase 3: Code Quality & Optimization (Priority: LOW)

### 3.1 Dependency Cleanup

**Issue**: Unused dependencies increase Docker image size and maintenance burden

```diff
# File: mcp/requirements.txt
# Remove unused dependencies:
- aiohttp>=3.9.0     # Unused: httpx is used for HTTP client
- asyncio>=3.4.3     # Redundant: built into Python 3.11+

# Keep essential dependencies:
+ httpx>=0.25.0       # Primary HTTP client
+ mcp[cli]>=1.2.0     # MCP framework
+ aiosqlite>=0.19.0   # SQLite storage
+ pydantic>=2.0.0     # Data validation
+ structlog>=23.0.0   # Structured logging
```

### 3.2 Error Handling Enhancement

**Enhancement**: Add comprehensive error handling and user-friendly messages

```python
# File: mcp/src/server.py
# Add to multiple tools that make API calls:

async def with_api_error_handling(api_call_func, operation_name: str):
    """Wrapper for consistent API error handling across MCP tools"""
    try:
        return await api_call_func()
    except ConnectionError as e:
        logger.error(f"{operation_name} failed - backend connection error", error=str(e))
        return {
            "success": False,
            "error": f"Cannot connect to KTRDR backend. Please check if the backend is running.",
            "operation": operation_name
        }
    except TimeoutError as e:
        logger.error(f"{operation_name} timed out", error=str(e))
        return {
            "success": False, 
            "error": f"Backend request timed out. The operation may still be running.",
            "operation": operation_name
        }
    except Exception as e:
        logger.error(f"{operation_name} failed unexpectedly", error=str(e))
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "operation": operation_name
        }
```

**Estimated Time**: 1-2 hours

## Phase 4: Testing & Validation

### 4.1 Unit Testing Strategy

**Create**: `mcp/tests/test_training_compatibility.py`

```python
import pytest
from unittest.mock import AsyncMock, patch
from mcp.src.server import start_model_training
from mcp.src.api_client import KTRDRAPIClient

@pytest.mark.asyncio
async def test_start_model_training_payload_format():
    """Test that training request uses correct multi-symbol format"""
    mock_client = AsyncMock()
    mock_response = {
        "success": True,
        "task_id": "test-task-123",
        "status": "training",
        "message": "Training started"
    }
    mock_client.start_neural_training.return_value = mock_response
    
    with patch('mcp.src.server.get_api_client') as mock_get_client:
        mock_get_client.return_value.__aenter__.return_value = mock_client
        
        result = await start_model_training(
            experiment_id="exp-123",
            symbol="AAPL", 
            timeframe="1h",
            strategy_name="test_strategy"
        )
        
        # Verify client was called with correct format
        mock_client.start_neural_training.assert_called_once()
        call_args = mock_client.start_neural_training.call_args
        
        # Check that single values were converted to arrays
        assert call_args[1]["symbols"] == ["AAPL"]
        assert call_args[1]["timeframes"] == ["1h"]
        assert call_args[1]["strategy_name"] == "test_strategy"
        
        # Verify response
        assert result["success"] == True
        assert result["task_id"] == "test-task-123"

@pytest.mark.asyncio  
async def test_get_training_status_endpoint_adaptation():
    """Test that training status uses performance endpoint correctly"""
    mock_client = AsyncMock()
    mock_response = {
        "success": True,
        "task_id": "test-task-123", 
        "status": "completed",
        "training_metrics": {"accuracy": 0.85}
    }
    mock_client.get_training_status.return_value = mock_response
    
    # Test implementation here...
```

### 4.2 Integration Testing

**Test Scenarios**:
1. **Training Pipeline**: Start training → Check status → Get performance → Save model
2. **Error Handling**: Network failures, invalid responses, backend errors
3. **Backward Compatibility**: Ensure existing working tools still function

**Test Environment Setup**:
```bash
# Set up test backend with docker-compose
docker-compose -f docker/docker-compose.test.yml up -d backend

# Run MCP integration tests
cd mcp
uv run pytest tests/integration/ -v

# Verify MCP server startup
./mcp/build_mcp.sh
docker logs ktrdr-mcp --tail 50
```

### 4.3 End-to-End Validation

**Manual Test Protocol**:
1. **MCP Server Startup**: Verify container builds and starts without errors
2. **Claude Integration**: Test MCP tools through Claude Desktop
3. **Training Workflow**: Complete ML pipeline from data loading to model evaluation
4. **Error Recovery**: Test graceful handling of backend disconnection

**Estimated Time**: 2-4 hours

## Implementation Timeline

### Week 1: Core Compatibility
- **Day 1-2**: Phase 1 (Critical Fixes) - Training payload & status endpoints
- **Day 3**: Phase 2 (Response Format) - Indicators parsing fix  
- **Day 4**: Unit testing and code review
- **Day 5**: Integration testing and bug fixes

### Week 2: Polish & Deployment
- **Day 1**: Phase 3 (Optimization) - Dependency cleanup & error handling
- **Day 2**: End-to-end testing with Claude Desktop
- **Day 3**: Documentation updates and deployment preparation
- **Day 4**: Production deployment and monitoring
- **Day 5**: Buffer time for any issues

## Risk Mitigation

### High Risks
1. **Backend API Changes**: Solution - Verify current API contracts before implementation
2. **Breaking Existing Tools**: Solution - Comprehensive regression testing
3. **Docker Environment Issues**: Solution - Test in clean environment

### Medium Risks  
1. **Response Format Inconsistencies**: Solution - Defensive parsing with fallbacks
2. **Storage Manager Compatibility**: Solution - Database schema validation tests
3. **Performance Degradation**: Solution - Performance benchmarking before/after

### Rollback Plan
1. **Git branch strategy**: Feature branch with atomic commits
2. **Docker image tagging**: Keep previous working image tagged
3. **Config rollback**: Environment variables for API compatibility mode
4. **Database backup**: SQLite database backup before testing

## Success Criteria

### Functional Requirements
- ✅ All 25 MCP tools execute without errors
- ✅ Neural network training pipeline works end-to-end  
- ✅ Multi-symbol/multi-timeframe API compatibility
- ✅ Existing tool functionality preserved

### Performance Requirements  
- ✅ MCP server startup time < 10 seconds
- ✅ API response times within 2x of current performance
- ✅ Memory usage remains stable during extended use

### Quality Requirements
- ✅ Unit test coverage > 80% for modified code
- ✅ Integration tests pass for all tool categories
- ✅ No regression in existing functionality
- ✅ Error messages are user-friendly and actionable

## Monitoring & Maintenance

### Post-Deployment Monitoring
1. **MCP Tool Usage**: Track which tools are used most frequently
2. **Error Rates**: Monitor API call success/failure rates
3. **Performance Metrics**: Response times, memory usage, CPU utilization
4. **User Feedback**: Claude Desktop interaction success rates

### Maintenance Schedule
1. **Weekly**: Review error logs and performance metrics
2. **Monthly**: Update dependencies and security patches  
3. **Quarterly**: Review and optimize based on usage patterns
4. **Annually**: Major version updates and architecture review

## Conclusion

This compatibility upgrade plan provides a structured approach to bringing the MCP server to 100% compatibility with your updated multi-symbol/multi-timeframe training API. The phased approach minimizes risk while ensuring all functionality is restored and enhanced.

**Key Benefits**:
- **100% tool compatibility** - All 25 MCP tools will function correctly
- **Backward compatibility** - No breaking changes to existing workflows
- **Enhanced error handling** - Better user experience with clear error messages
- **Code quality improvements** - Cleaner dependencies and better testing

**Next Steps**:
1. Review and approve this plan
2. Create feature branch: `feature/mcp-multi-symbol-compatibility`
3. Begin Phase 1 implementation
4. Set up continuous integration for MCP testing

The estimated 6-8 hour implementation time should resolve all critical compatibility issues and restore full MCP functionality with your enhanced training API.