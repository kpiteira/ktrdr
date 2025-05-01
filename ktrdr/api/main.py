"""
KTRDR API entry point.

This module initializes the FastAPI application and serves as the main entry point
for the KTRDR API backend.
"""
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi

from ktrdr.api.config import APIConfig
from ktrdr.api.middleware import add_middleware
from ktrdr.errors import (
    DataError, 
    ConnectionError, 
    ConfigurationError, 
    ProcessingError
)

# Setup module-level logger
logger = logging.getLogger(__name__)

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
        redoc_url=f"{config.api_prefix}/redoc",
        openapi_url=f"{config.api_prefix}/openapi.json",
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
                    "details": exc.details or {}
                }
            }
        )
    
    @app.exception_handler(ConnectionError)
    async def connection_error_handler(request: Request, exc: ConnectionError) -> JSONResponse:
        """Handle ConnectionError exceptions with appropriate response."""
        logger.error(f"ConnectionError: {exc.message}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {
                    "code": exc.error_code or "CONNECTION_ERROR",
                    "message": exc.message,
                    "details": exc.details or {}
                }
            }
        )
    
    @app.exception_handler(ConfigurationError)
    async def config_error_handler(request: Request, exc: ConfigurationError) -> JSONResponse:
        """Handle ConfigurationError exceptions with appropriate response."""
        logger.error(f"ConfigurationError: {exc.message}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": exc.error_code or "CONFIGURATION_ERROR",
                    "message": exc.message,
                    "details": exc.details or {}
                }
            }
        )
    
    @app.exception_handler(ProcessingError)
    async def processing_error_handler(request: Request, exc: ProcessingError) -> JSONResponse:
        """Handle ProcessingError exceptions with appropriate response."""
        logger.error(f"ProcessingError: {exc.message}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": exc.error_code or "PROCESSING_ERROR",
                    "message": exc.message,
                    "details": exc.details or {}
                }
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle general exceptions with appropriate response."""
        logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {"type": str(type(exc).__name__)}
                }
            }
        )
    
    # API root endpoint
    @app.get("/")
    async def root():
        """Root endpoint redirects to API documentation."""
        return {"message": f"KTRDR API is running. Visit {config.api_prefix}/docs for documentation"}
    
    # Include API version prefix router
    from ktrdr.api.endpoints import api_router
    app.include_router(api_router, prefix=config.api_prefix)
    
    # Custom OpenAPI schema generator
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        
        # Add custom schema components here if needed
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    app.openapi = custom_openapi
    
    logger.info(f"KTRDR API initialized: version={config.version}, environment={config.environment}")
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