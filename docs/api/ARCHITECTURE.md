# KTRDR API Architecture

This document provides a detailed overview of the KTRDR API architecture, design patterns, and implementation guidelines.

## 1. API Architecture Overview

The KTRDR API follows a modern, layered architecture that integrates with existing KTRDR modules:

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│                 │      │                 │      │                 │
│  Client         │      │  FastAPI        │      │  Existing       │
│  Applications   │◄────►│  Backend        │◄────►│  KTRDR Modules  │
│                 │      │  (API Layer)    │      │  (Core Logic)   │
│                 │      │                 │      │                 │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

### 1.1 Core Architectural Principles

The API follows these key design principles:

1. **Separation of Concerns**: Clear boundaries between data management, business logic, and presentation
2. **API-First Design**: All functionality is available through a well-defined API
3. **Service-Based Architecture**: Core functionality is exposed through service adapters
4. **Consistent Patterns**: Standardized request/response formats and error handling
5. **Performance-Focused**: Efficient data transfer and transformation

### 1.2 Directory Structure

```
ktrdr/
├── api/                  # API module
│   ├── __init__.py       # Module initialization
│   ├── main.py           # FastAPI app entry point
│   ├── dependencies.py   # Dependency injection
│   ├── config.py         # API configuration
│   ├── middleware.py     # Custom middleware
│   ├── endpoints/        # API endpoints
│   │   ├── __init__.py
│   │   ├── data.py       # Data loading endpoints
│   │   ├── indicators.py # Indicator calculation endpoints
│   │   └── fuzzy.py      # Fuzzy logic endpoints
│   ├── models/           # Pydantic models for API
│   │   ├── __init__.py
│   │   ├── data.py
│   │   ├── indicators.py
│   │   └── fuzzy.py
│   └── services/         # Services connecting to core modules
│       ├── __init__.py
│       ├── data_service.py
│       ├── indicator_service.py
│       └── fuzzy_service.py
```

## 2. Key API Components

### 2.1 Endpoint Layer

Endpoints in the API are organized into logical groups, with each group handling a specific domain of functionality:

- **Data Endpoints**: Access to market data, symbols, and timeframes
- **Indicator Endpoints**: Technical indicator calculations
- **Fuzzy Logic Endpoints**: Fuzzy set operations and evaluations

Endpoints follow these design guidelines:
- Use consistent route naming conventions
- Implement proper HTTP methods (GET, POST)
- Return standardized response formats
- Include comprehensive validation
- Provide detailed error messages

### 2.2 Service Layer

The service layer serves as an adapter between the API endpoints and the core KTRDR modules:

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│                 │      │                 │      │                 │
│  API Endpoints  │◄────►│  Service Layer  │◄────►│  Core KTRDR     │
│  (FastAPI)      │      │  (Adapters)     │      │  Modules        │
│                 │      │                 │      │                 │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

Key responsibilities of service adapters:
- Transform request data to the format expected by core modules
- Call appropriate core functionality
- Transform response data to the API response format
- Handle errors and exceptions appropriately
- Provide performance monitoring
- Implement caching where appropriate

### 2.3 Data Models

The API uses Pydantic models for:
- Request validation
- Response formatting
- Documentation generation

Models follow these principles:
- Clear validation rules with descriptive error messages
- Proper typing for all fields
- Default values where appropriate
- Comprehensive documentation

### 2.4 Middleware

Custom middleware components provide cross-cutting functionality:

- **Request Logging**: Log all API requests with timing information
- **Error Handling**: Transform exceptions into standardized API responses
- **CORS**: Enable cross-origin resource sharing with proper configuration
- **Authentication**: (Planned) API key verification and rate limiting

## 3. API Patterns and Standards

### 3.1 Response Envelope

All API responses follow a standard envelope pattern:

```json
{
  "success": true,
  "data": {
    // Response data specific to the endpoint
  }
}
```

Or for errors:

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

This consistent structure allows clients to:
- Easily check if a request succeeded
- Handle errors uniformly
- Access standardized metadata

### 3.2 Naming Conventions

- **Endpoints**: Use noun-based paths (/symbols, /indicators) rather than verbs
- **Parameters**: Use camelCase for JSON request parameters
- **Response Fields**: Use snake_case for JSON response fields
- **Error Codes**: Use CATEGORY-SpecificError format (e.g., DATA-NotFound)

### 3.3 Pagination Pattern

Large response datasets use a standard pagination pattern:

```json
{
  "success": true,
  "data": [...],
  "metadata": {
    "total_items": 100,
    "total_pages": 10,
    "current_page": 1,
    "page_size": 10,
    "has_next": true,
    "has_prev": false
  }
}
```

Pagination is controlled via query parameters:
- `page`: Page number (1-based)
- `page_size`: Number of items per page

### 3.4 Error Handling Pattern

Errors are categorized by type and source:
- **Validation Errors**: Invalid input parameters (HTTP 422)
- **Data Errors**: Problems with requested data (HTTP 400/404)
- **Configuration Errors**: Issues with system configuration (HTTP 500)
- **Processing Errors**: Calculation or processing failures (HTTP 500)
- **System Errors**: Infrastructure or unexpected issues (HTTP 500)

### 3.5 Versioning

The API uses URL-based versioning with the pattern:
- `/api/v1/endpoint`

This allows for:
- Clear indication of API version
- Maintaining backward compatibility
- Future version upgrades without breaking existing clients

## 4. API Configuration

The API is configurable through:
- Environment variables
- Command-line parameters
- Configuration files

Key configuration areas include:
- Server settings (host, port)
- CORS configuration
- Logging levels
- Performance tuning
- Authentication (planned)

## 5. API Security (Planned)

Future security enhancements:
- API key authentication
- Rate limiting
- Request validation
- HTTPS enforcement
- Security headers

## 6. API Evolution

Guidelines for future API development:
- Maintain backward compatibility within a version
- Use feature flags for gradual rollout
- Implement proper deprecation notices
- Provide migration paths for breaking changes
- Maintain comprehensive documentation