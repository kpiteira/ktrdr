# KTRDR API Workflow Sequences

This document contains sequence diagrams showing common API workflows in the KTRDR system.

## 1. Data Loading Workflow

The following sequence diagram shows the workflow for loading market data through the API:

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant DataEndpoints
    participant DataService
    participant DataManager
    
    Client->>API: POST /api/v1/data/load
    Note over Client,API: Request with symbol, timeframe, dates
    
    API->>DataEndpoints: Route request
    DataEndpoints->>DataService: load_data()
    
    Note over DataService: Convert request to DataManager format
    DataService->>DataManager: load()
    
    alt Data exists locally
        DataManager-->>DataService: Return data
    else Data needs to be fetched
        DataManager->>DataManager: fetch_from_source()
        DataManager-->>DataService: Return data
    end
    
    Note over DataService: Transform to API response format
    DataService-->>DataEndpoints: Return formatted data
    DataEndpoints-->>API: Return response
    API-->>Client: JSON Response
```

## 2. Indicator Calculation Workflow

The following sequence diagram shows the workflow for calculating technical indicators:

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant IndicatorEndpoints
    participant DataService
    participant IndicatorService
    participant IndicatorEngine
    
    Client->>API: POST /api/v1/indicators/calculate
    Note over Client,API: Request with symbol, timeframe, indicators
    
    API->>IndicatorEndpoints: Route request
    
    IndicatorEndpoints->>DataService: load_data()
    DataService-->>IndicatorEndpoints: Return OHLCV data
    
    IndicatorEndpoints->>IndicatorService: calculate_indicators()
    
    Note over IndicatorService: Convert to IndicatorEngine format
    IndicatorService->>IndicatorEngine: apply()
    
    loop For each indicator
        IndicatorEngine->>IndicatorEngine: calculate()
    end
    
    IndicatorEngine-->>IndicatorService: Return calculated values
    
    Note over IndicatorService: Transform to API response format
    IndicatorService-->>IndicatorEndpoints: Return formatted data
    IndicatorEndpoints-->>API: Return response
    API-->>Client: JSON Response
```

## 3. Fuzzy Logic Evaluation Workflow

The following sequence diagram shows the workflow for fuzzifying indicator data:

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant FuzzyEndpoints
    participant DataService
    participant IndicatorService
    participant FuzzyService
    participant FuzzyEngine
    
    Client->>API: POST /api/v1/fuzzy/data
    Note over Client,API: Request with symbol, timeframe, indicators
    
    API->>FuzzyEndpoints: Route request
    
    FuzzyEndpoints->>DataService: load_data()
    DataService-->>FuzzyEndpoints: Return OHLCV data
    
    FuzzyEndpoints->>IndicatorService: calculate_indicators()
    IndicatorService-->>FuzzyEndpoints: Return indicator values
    
    FuzzyEndpoints->>FuzzyService: fuzzify_data()
    
    Note over FuzzyService: Convert data for FuzzyEngine
    FuzzyService->>FuzzyEngine: apply_membership()
    
    loop For each indicator
        FuzzyEngine->>FuzzyEngine: fuzzify()
    end
    
    FuzzyEngine-->>FuzzyService: Return fuzzy values
    
    Note over FuzzyService: Transform to API response format
    FuzzyService-->>FuzzyEndpoints: Return formatted data
    FuzzyEndpoints-->>API: Return response
    API-->>Client: JSON Response
```

## 4. Error Handling Workflow

The following sequence diagram shows how errors are handled in the API:

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant Endpoints
    participant Service
    participant ExceptionHandler
    
    Client->>API: API Request
    API->>Endpoints: Route request
    
    alt Success path
        Endpoints->>Service: Call service
        Service-->>Endpoints: Return data
        Endpoints-->>API: Return response
        API-->>Client: 200 OK with data
    else Error path: Data Error
        Endpoints->>Service: Call service
        Service--xEndpoints: Raise DataError
        Endpoints->>ExceptionHandler: Handle DataError
        ExceptionHandler-->>API: Create error response
        API-->>Client: 404/400 with error details
    else Error path: Validation Error
        API-xEndpoints: Request validation fails
        API->>ExceptionHandler: Handle ValidationError
        ExceptionHandler-->>API: Create error response
        API-->>Client: 422 with validation details
    else Error path: Processing Error
        Endpoints->>Service: Call service
        Service--xEndpoints: Raise ProcessingError
        Endpoints->>ExceptionHandler: Handle ProcessingError
        ExceptionHandler-->>API: Create error response
        API-->>Client: 500 with error details
    end
```

## 5. Authentication Workflow (Planned)

The following sequence diagram shows the planned authentication workflow:

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant AuthMiddleware
    participant Endpoints
    participant Service
    
    Client->>API: API Request with X-API-Key header
    API->>AuthMiddleware: Intercept request
    
    alt Valid API Key
        AuthMiddleware->>AuthMiddleware: Validate API Key
        AuthMiddleware-->>API: Allow request
        API->>Endpoints: Route request
        Endpoints->>Service: Call service
        Service-->>Endpoints: Return data
        Endpoints-->>API: Return response
        API-->>Client: 200 OK with data
    else Invalid API Key
        AuthMiddleware->>AuthMiddleware: Validate API Key
        AuthMiddleware--xAPI: Deny request
        API-->>Client: 401 Unauthorized
    else Missing API Key
        AuthMiddleware->>AuthMiddleware: Check for API Key
        AuthMiddleware--xAPI: Deny request
        API-->>Client: 401 Unauthorized
    end
```