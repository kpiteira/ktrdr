# [Endpoint Name]

**Endpoint:** `[HTTP Method] /api/v1/path/to/endpoint`

## Description

Detailed description of what this endpoint does and its purpose in the system.

## Request Parameters

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `param1` | string | Yes | Description of param1 |
| `param2` | integer | No | Description of param2 |

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `param1` | string | No | Description of param1 |
| `param2` | integer | No | Description of param2 |

### Request Body

```json
{
  "property1": "value1",
  "property2": 42,
  "nested": {
    "property3": "value3"
  }
}
```

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `property1` | string | Yes | Description of property1 |
| `property2` | integer | No | Description of property2 |
| `nested.property3` | string | No | Description of nested property3 |

## Response

### Success Response

**Code:** `200 OK`

```json
{
  "success": true,
  "data": {
    "property1": "value1",
    "property2": 42
  }
}
```

| Property | Type | Description |
|----------|------|-------------|
| `success` | boolean | Always true for successful responses |
| `data.property1` | string | Description of property1 |
| `data.property2` | integer | Description of property2 |

### Error Responses

**Code:** `400 Bad Request`

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "property1": "Error details about property1"
    }
  }
}
```

**Code:** `404 Not Found`

```json
{
  "success": false,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested resource was not found",
    "details": null
  }
}
```

## Examples

### Example Request

```bash
curl -X POST \
  "https://api.example.com/api/v1/path/to/endpoint" \
  -H "Content-Type: application/json" \
  -d '{
    "property1": "value1",
    "property2": 42
  }'
```

### Example Response

```json
{
  "success": true,
  "data": {
    "property1": "value1",
    "property2": 42
  }
}
```

## Notes

Additional information, caveats, or considerations when using this endpoint.

## Related Endpoints

- [`GET /api/v1/related/endpoint`](link-to-related-endpoint.md): Brief description
- [`POST /api/v1/another/endpoint`](link-to-another-endpoint.md): Brief description