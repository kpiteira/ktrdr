"""
API middleware tests.

This module tests the middleware components of the API.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI, Request, Response
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import Scope

from ktrdr.api.middleware import RequestLoggingMiddleware, add_middleware

class TestRequestLoggingMiddleware:
    """Tests for the RequestLoggingMiddleware class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = MagicMock()
        self.middleware = RequestLoggingMiddleware(self.app)
        
        # Create a mock request
        self.scope: Scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/health",
            "headers": [(b"x-request-id", b"test-id")],  # Use raw list of tuples instead of Headers
            "client": ("127.0.0.1", 8000),
        }
        self.request = Request(scope=self.scope)
        
        # Create a mock response
        self.response = Response(content=b"Test Response", status_code=200)
        
        # Setup a mock call_next function that returns the mock response using AsyncMock
        self.call_next = AsyncMock(return_value=self.response)
    
    @pytest.mark.asyncio
    async def test_successful_request_logging(self):
        """Test that successful requests are properly logged."""
        with patch("ktrdr.api.middleware.logger.info") as mock_logger_info:
            response = await self.middleware.dispatch(self.request, self.call_next)
            
            # Verify call_next was called with the request
            self.call_next.assert_called_once_with(self.request)
            
            # Verify the response was returned
            assert response == self.response
            
            # Verify the response headers contain the process time
            assert "X-Process-Time" in response.headers
            
            # Verify that the logger was called twice (request start and completion)
            assert mock_logger_info.call_count == 2
            
            # Verify the content of the first log message (request started)
            first_call_args = mock_logger_info.call_args_list[0][0][0]
            assert "Request started" in first_call_args
            assert "method=GET" in first_call_args
            assert "path=/api/v1/health" in first_call_args
            assert "request_id=test-id" in first_call_args
            
            # Verify the content of the second log message (request completed)
            second_call_args = mock_logger_info.call_args_list[1][0][0]
            assert "Request completed" in second_call_args
            assert "status_code=200" in second_call_args
            assert "duration=" in second_call_args
    
    @pytest.mark.asyncio
    async def test_failed_request_logging(self):
        """Test that failed requests are properly logged."""
        # Setup a mock call_next function that raises an exception
        error_call_next = AsyncMock(side_effect=ValueError("Test error"))
        
        with patch("ktrdr.api.middleware.logger.info") as mock_logger_info, \
             patch("ktrdr.api.middleware.logger.error") as mock_logger_error, \
             pytest.raises(ValueError):
            
            await self.middleware.dispatch(self.request, error_call_next)
            
            # Verify error_call_next was called with the request
            error_call_next.assert_called_once_with(self.request)
            
            # Verify that the info logger was called once (request start)
            assert mock_logger_info.call_count == 1
            
            # Verify that the error logger was called once (request failed)
            assert mock_logger_error.call_count == 1
            
            # Verify the content of the error log message
            error_call_args = mock_logger_error.call_args[0][0]
            assert "Request failed" in error_call_args
            assert "method=GET" in error_call_args
            assert "path=/api/v1/health" in error_call_args
            assert "error=Test error" in error_call_args
            assert "duration=" in error_call_args
    
    def test_add_middleware(self):
        """Test that add_middleware function adds the middleware to the app."""
        app = FastAPI()
        with patch("ktrdr.api.middleware.logger.info") as mock_logger_info:
            add_middleware(app)
            
            # Verify the logger was called
            mock_logger_info.assert_called_once_with("Custom middleware added to the API application")