# KTRDR API Reference

This section provides comprehensive documentation for the KTRDR API, including endpoints, models, and usage examples.

## Overview

The KTRDR API is built using FastAPI and provides a complete interface for interacting with the KTRDR trading system. The API follows RESTful principles with standardized request and response formats.

## Getting Started

To use the KTRDR API, you need to:

1. Start the API server (see [Installation Guide](../getting-started/installation.md))
2. Access the API endpoints via HTTP requests
3. Process the JSON responses

The API server runs by default on `http://localhost:8000` when started locally.

## API Documentation

Once the server is running, you can access the auto-generated API documentation:

- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc
- OpenAPI JSON: http://localhost:8000/api/v1/openapi.json

## API Structure

The API is organized into these main sections:

- [Data API](./data-api.md): Endpoints for retrieving market data and symbols
- [Indicator API](./indicator-api.md): Endpoints for calculating technical indicators
- [Fuzzy Logic API](./fuzzy-api.md): Endpoints for working with fuzzy logic sets
- [Visualization API](./visualization-api.md): Endpoints for generating charts and visualizations

## Authentication

The API currently uses API key authentication. Include your API key in the `X-API-Key` header with each request:

```bash
curl -X GET "http://localhost:8000/api/v1/symbols" \
     -H "X-API-Key: your-api-key"
```

## Response Format

All API responses follow a standard envelope format:

### Success Response

```json
{
  "success": true,
  "data": {
    // Response data specific to the endpoint
  }
}
```

### Error Response

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      // Additional error details
    }
  }
}
```

## Error Codes

Common error codes you might encounter:

| Code | Description |
|------|-------------|
| `DATA_NOT_FOUND` | The requested data does not exist |
| `INVALID_PARAMETERS` | The request contains invalid parameters |
| `CALCULATION_ERROR` | Error during indicator calculation |
| `AUTHENTICATION_ERROR` | Authentication failed or missing |
| `INTERNAL_ERROR` | Internal server error |

## Rate Limiting

The API implements rate limiting to prevent abuse. The current limits are:

- 100 requests per minute per API key
- 5,000 requests per day per API key

Rate limit information is included in the response headers:

- `X-Rate-Limit-Limit`: Maximum number of requests allowed in the period
- `X-Rate-Limit-Remaining`: Remaining requests in the current period
- `X-Rate-Limit-Reset`: Seconds until the rate limit resets

## API Versioning

The API uses URL-based versioning in the format `/api/v{version}/...`. The current version is v1.