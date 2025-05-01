# KTRDR API Documentation

## Overview

The KTRDR API provides a RESTful interface for accessing KTRDR trading system functionality. The API is built with FastAPI and follows modern API design principles.

## Getting Started

### Installing Dependencies

The API dependencies are listed in the main `requirements.txt` file. You can install them with:

```bash
uv pip install -r requirements.txt
```

For development and testing, also install the development dependencies:

```bash
uv pip install -r requirements-dev.txt
```

### Running the API Server

There are multiple ways to run the API server:

#### 1. Using the provided script

```bash
# From the project root directory
./scripts/run_api_server.py
```

Command line options:
- `--host`: Host to bind the server (default: 127.0.0.1)
- `--port`: Port to bind the server (default: 8000)
- `--reload`: Enable auto-reload for development
- `--log-level`: Logging level (choices: debug, info, warning, error, critical)
- `--env`: Deployment environment (choices: development, staging, production)

Example:
```bash
./scripts/run_api_server.py --host 0.0.0.0 --port 8080 --log-level debug
```

#### 2. Using Python directly

```bash
# From the project root directory
python -m uvicorn ktrdr.api.main:app --reload
```

#### 3. Using the main module

```bash
# From the project root directory
python -m ktrdr.api.main
```

### API Documentation

Once the server is running, you can access the auto-generated API documentation:

- Swagger UI: http://127.0.0.1:8000/api/v1/docs
- ReDoc: http://127.0.0.1:8000/api/v1/redoc
- OpenAPI JSON: http://127.0.0.1:8000/api/v1/openapi.json

## Environment Variables

The API can be configured using environment variables. These can be set in your shell or in a `.env` file in the project root:

| Variable | Description | Default |
|----------|-------------|---------|
| KTRDR_API_TITLE | API title | "KTRDR API" |
| KTRDR_API_DESCRIPTION | API description | "REST API for KTRDR trading system" |
| KTRDR_API_VERSION | API version | "1.0.5" |
| KTRDR_API_HOST | Host to bind | "127.0.0.1" |
| KTRDR_API_PORT | Port to bind | 8000 |
| KTRDR_API_RELOAD | Enable auto-reload | True |
| KTRDR_API_LOG_LEVEL | Logging level | "INFO" |
| KTRDR_API_ENVIRONMENT | Deployment environment | "development" |
| KTRDR_API_API_PREFIX | API endpoint prefix | "/api/v1" |
| KTRDR_API_CORS_ORIGINS | Allowed CORS origins | ["*"] |

## API Structure

- `/api/v1/health`: Health check endpoint
- More endpoints will be added in subsequent tasks

## Error Handling

The API provides consistent error responses with the following structure:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "additional": "error details"
    }
  }
}
```

## Testing

To run the API tests:

```bash
# From the project root directory
python -m pytest tests/api/
```