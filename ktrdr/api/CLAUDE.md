# API Module Guidelines

## 🌐 FASTAPI PATTERNS

### Endpoint Structure
```python
@router.post("/data/load", response_model=LoadDataResponse)
async def load_data(request: LoadDataRequest) -> LoadDataResponse:
    """Load data endpoint.
    
    Always return standardized response format.
    Never expose internal errors to client.
    """
```

### Standard Response Format
```python
{
    "success": true,
    "data": {...},
    "error": null
}
# OR
{
    "success": false,
    "data": null,
    "error": {
        "code": "DATA-001",
        "message": "User-friendly message",
        "details": {...}
    }
}
```

## 🚫 API ANTI-PATTERNS

❌ Exposing internal exceptions to client
✅ Transform to user-friendly errors

❌ Business logic in endpoints
✅ Delegate to service/core modules

❌ Synchronous blocking operations
✅ Use async/await properly

❌ Missing input validation
✅ Use Pydantic models for all inputs

## 📝 PYDANTIC MODELS

Location: `ktrdr/api/models/`

Rules:
- One file per domain (data, indicators, etc.)
- Inherit from BaseModel
- Use validators for business rules
- Provide examples in schema

## 🔧 ERROR HANDLING

```python
try:
    result = await service.process()
    return APIResponse(success=True, data=result)
except DataError as e:
    return APIResponse(
        success=False,
        error=APIError(
            code=e.code,
            message=str(e),
            details=e.details
        )
    )
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return APIResponse(
        success=False,
        error=APIError(
            code="INTERNAL-001",
            message="An internal error occurred"
        )
    )
```

## 🧪 API TESTING

- Test with TestClient, not real server
- Validate response schemas
- Test error cases and edge cases
- Mock service layer dependencies