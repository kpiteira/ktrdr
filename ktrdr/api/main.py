"""
KTRDR API entry point.

This module initializes the FastAPI application and serves as the main entry point
for the KTRDR API backend.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from ktrdr.api.config import APIConfig
from ktrdr.api.middleware import add_middleware
from ktrdr.api.startup import lifespan
from ktrdr.errors import (
    ConfigurationError,
    ConnectionError,
    DataError,
    DataNotFoundError,
    ProcessingError,
)

# Setup module-level logger
logger = logging.getLogger(__name__)

# Set up templates directory
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI application instance
    """
    # Load API configuration
    config = APIConfig()
    logger.info(f"API configuration loaded: environment={config.environment}")

    # Create FastAPI app with configured title, description, and version
    app = FastAPI(
        title=config.title,
        description=config.description,
        version=config.version,
        docs_url=f"{config.api_prefix}/docs",
        # We'll use custom redoc route instead of the default
        redoc_url=None,
        openapi_url=f"{config.api_prefix}/openapi.json",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=config.cors_allow_credentials,
        allow_methods=config.cors_allow_methods,
        allow_headers=config.cors_allow_headers,
        max_age=config.cors_max_age,
    )

    # Add custom middleware
    add_middleware(app)

    # Add exception handlers
    @app.exception_handler(DataNotFoundError)
    async def data_not_found_error_handler(
        request: Request, exc: DataNotFoundError
    ) -> JSONResponse:
        """Handle DataNotFoundError exceptions with 404 response."""
        logger.error(f"DataNotFoundError: {exc.message}", exc_info=True)
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": {
                    "code": exc.error_code or "DATA_NOT_FOUND",
                    "message": exc.message,
                    "details": exc.details or {},
                },
            },
        )

    @app.exception_handler(DataError)
    async def data_error_handler(request: Request, exc: DataError) -> JSONResponse:
        """Handle DataError exceptions with appropriate response."""
        logger.error(f"DataError: {exc.message}", exc_info=True)
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {
                    "code": exc.error_code or "DATA_ERROR",
                    "message": exc.message,
                    "details": exc.details or {},
                },
            },
        )

    @app.exception_handler(ConnectionError)
    async def connection_error_handler(
        request: Request, exc: ConnectionError
    ) -> JSONResponse:
        """Handle ConnectionError exceptions with appropriate response."""
        logger.error(f"ConnectionError: {exc.message}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {
                    "code": exc.error_code or "CONNECTION_ERROR",
                    "message": exc.message,
                    "details": exc.details or {},
                },
            },
        )

    @app.exception_handler(ConfigurationError)
    async def config_error_handler(
        request: Request, exc: ConfigurationError
    ) -> JSONResponse:
        """Handle ConfigurationError exceptions with appropriate response."""
        logger.error(f"ConfigurationError: {exc.message}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": exc.error_code or "CONFIGURATION_ERROR",
                    "message": exc.message,
                    "details": exc.details or {},
                },
            },
        )

    @app.exception_handler(ProcessingError)
    async def processing_error_handler(
        request: Request, exc: ProcessingError
    ) -> JSONResponse:
        """Handle ProcessingError exceptions with appropriate response."""
        logger.error(f"ProcessingError: {exc.message}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": exc.error_code or "PROCESSING_ERROR",
                    "message": exc.message,
                    "details": exc.details or {},
                },
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle general exceptions with appropriate response."""
        logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {"type": str(type(exc).__name__)},
                },
            },
        )

    # API root endpoint
    @app.get("/")
    async def root():
        """Root endpoint redirects to API documentation."""
        return {
            "message": f"KTRDR API is running. Visit {config.api_prefix}/docs for documentation"
        }

    # Include API version prefix router
    from ktrdr.api.endpoints import api_router

    app.include_router(api_router, prefix=config.api_prefix)

    # Custom Redoc route
    @app.get(f"{config.api_prefix}/redoc", include_in_schema=False)
    async def custom_redoc(request: Request):
        """Custom Redoc documentation with enhanced styling."""
        from ktrdr.api.docs_config import docs_config

        return templates.TemplateResponse(
            "redoc.html",
            {
                "request": request,
                "title": app.title,
                "description": app.description,
                "version": app.version,
                "openapi_url": app.openapi_url,
                "api_prefix": config.api_prefix,
                "branding": docs_config.branding,
                "organization": docs_config.organization,
            },
        )

    # Custom OpenAPI schema generator
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        # Import docs configuration
        from ktrdr.api.docs_config import docs_config

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        # Add API metadata
        openapi_schema["info"]["x-logo"] = {
            "url": docs_config.branding.logo_url,
            "altText": docs_config.branding.logo_alt,
        }

        openapi_schema["info"]["contact"] = {
            "name": f"{docs_config.organization.name} API Support",
            "email": docs_config.organization.email,
            "url": docs_config.organization.docs_url,
        }

        # Add custom tags with descriptions for better organization
        openapi_schema["tags"] = [
            {
                "name": "Data",
                "description": "Operations related to market data retrieval and management.",
                "externalDocs": {
                    "description": "Data API Documentation",
                    "url": f"{config.api_prefix}/redoc#tag/Data",
                },
            },
            {
                "name": "indicators",
                "description": "Operations related to technical indicators calculation and configuration.",
                "externalDocs": {
                    "description": "Indicators API Documentation",
                    "url": f"{config.api_prefix}/redoc#tag/indicators",
                },
            },
            {
                "name": "Fuzzy",
                "description": "Operations related to fuzzy logic and fuzzy set evaluation.",
                "externalDocs": {
                    "description": "Fuzzy Logic API Documentation",
                    "url": f"{config.api_prefix}/redoc#tag/Fuzzy",
                },
            },
            {
                "name": "IB",
                "description": "Operations related to Interactive Brokers connection status and management.",
                "externalDocs": {
                    "description": "IB API Documentation",
                    "url": f"{config.api_prefix}/redoc#tag/IB",
                },
            },
        ]

        # Add security schemes
        openapi_schema["components"] = openapi_schema.get("components", {})
        openapi_schema["components"]["securitySchemes"] = {
            "APIKeyHeader": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key to authorize requests. Will be required in future versions.",
            }
        }

        # Add response examples
        if "components" not in openapi_schema:
            openapi_schema["components"] = {}

        if "examples" not in openapi_schema["components"]:
            openapi_schema["components"]["examples"] = {}

        # Add error response examples
        openapi_schema["components"]["examples"]["ValidationError"] = {
            "summary": "Validation Error Example",
            "value": {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid input parameters",
                    "details": {
                        "symbol": "Symbol is required",
                        "timeframe": "Timeframe must be one of ['1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w', '1M']",
                    },
                },
            },
        }

        openapi_schema["components"]["examples"]["DataError"] = {
            "summary": "Data Error Example",
            "value": {
                "success": False,
                "error": {
                    "code": "DATA-NotFound",
                    "message": "No data available for UNKNOWN (1d)",
                    "details": {"symbol": "UNKNOWN", "timeframe": "1d"},
                },
            },
        }

        # Override specific endpoint documentation
        for path in openapi_schema["paths"]:
            for method in openapi_schema["paths"][path]:
                if method.lower() != "get" and method.lower() != "post":
                    continue

                # Add authentication information to all endpoints
                if "security" not in openapi_schema["paths"][path][method]:
                    openapi_schema["paths"][path][method]["security"] = []

                # Add standard error responses to all operations
                if "responses" not in openapi_schema["paths"][path][method]:
                    openapi_schema["paths"][path][method]["responses"] = {}

                responses = openapi_schema["paths"][path][method]["responses"]

                # Add validation error response
                if "422" not in responses:
                    responses["422"] = {
                        "description": "Validation Error",
                        "content": {
                            "application/json": {
                                "examples": {
                                    "ValidationError": {
                                        "$ref": "#/components/examples/ValidationError"
                                    }
                                }
                            }
                        },
                    }

                # Add server error response
                if "500" not in responses:
                    responses["500"] = {
                        "description": "Internal Server Error",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": False,
                                        },
                                        "error": {
                                            "type": "object",
                                            "properties": {
                                                "code": {
                                                    "type": "string",
                                                    "example": "INTERNAL_SERVER_ERROR",
                                                },
                                                "message": {
                                                    "type": "string",
                                                    "example": "An unexpected error occurred",
                                                },
                                                "details": {"type": "object"},
                                            },
                                        },
                                    },
                                }
                            }
                        },
                    }

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    logger.info(
        f"KTRDR API initialized: version={config.version}, environment={config.environment}"
    )
    return app


# Create FastAPI application instance
app = create_application()

if __name__ == "__main__":
    import uvicorn

    config = APIConfig()
    uvicorn.run(
        "ktrdr.api.main:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        log_level=config.log_level.lower(),
    )
