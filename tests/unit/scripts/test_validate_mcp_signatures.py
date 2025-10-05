"""Tests for MCP signature validation script"""

from unittest.mock import Mock, patch

import httpx
import pytest

from scripts.validate_mcp_signatures import (
    MCPToolParser,
    OpenAPIFetcher,
    ValidationConfig,
    main,
)


class TestValidationConfig:
    """Test configuration loading"""

    def test_load_config_from_file(self):
        """Should load endpoint mapping from JSON file"""
        config = ValidationConfig.from_file("mcp/endpoint_mapping.json")

        assert "start_training" in config.tools
        assert config.tools["start_training"]["endpoint"] == "/api/v1/trainings/start"
        assert config.tools["start_training"]["critical"] is True

    def test_config_validation(self):
        """Should validate config structure"""
        with pytest.raises(ValueError, match="missing required fields"):
            # Missing required fields
            ValidationConfig(tools={"invalid": {}})

    def test_config_missing_tools_section(self):
        """Should raise error if 'tools' section missing"""
        import json
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"no_tools": {}}, f)
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Config missing 'tools' section"):
                ValidationConfig.from_file(temp_path)
        finally:
            import os

            os.unlink(temp_path)


class TestCLI:
    """Test command-line interface"""

    def test_help_message(self, capsys):
        """Should display help message"""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Validate MCP tool signatures" in captured.out

    def test_default_arguments(self):
        """Should use default values for arguments"""
        # This will fail since we don't have full implementation yet
        # but it defines the expected behavior
        pass

    def test_strict_flag(self):
        """Should support --strict flag"""
        # Will be implemented when we have full validation logic
        pass


class TestOpenAPIFetcher:
    """Test OpenAPI spec fetching"""

    @patch("httpx.get")
    def test_fetch_spec_from_backend(self, mock_get):
        """Should fetch OpenAPI spec from backend"""
        mock_response = Mock()
        mock_response.json.return_value = {"openapi": "3.1.0", "paths": {}}
        mock_get.return_value = mock_response

        fetcher = OpenAPIFetcher("http://localhost:8000")
        spec = fetcher.fetch()

        assert spec["openapi"] == "3.1.0"
        assert "paths" in spec
        mock_get.assert_called_once_with(
            "http://localhost:8000/api/v1/openapi.json", timeout=10.0
        )

    @patch("httpx.get")
    def test_fetch_handles_connection_error(self, mock_get):
        """Should raise clear error if backend not reachable"""
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        fetcher = OpenAPIFetcher("http://localhost:9999")

        with pytest.raises(ConnectionError, match="Backend not reachable"):
            fetcher.fetch()

    def test_get_request_schema(self):
        """Should extract request schema for endpoint"""
        spec = {
            "paths": {
                "/api/v1/trainings/start": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/TrainingStartRequest"
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "components": {
                "schemas": {
                    "TrainingStartRequest": {
                        "type": "object",
                        "properties": {
                            "symbols": {"type": "array", "items": {"type": "string"}},
                            "strategy_name": {"type": "string"},
                        },
                        "required": ["symbols", "strategy_name"],
                    }
                }
            },
        }

        fetcher = OpenAPIFetcher("http://localhost:8000")
        fetcher.spec = spec

        schema = fetcher.get_request_schema("/api/v1/trainings/start", "POST")

        assert schema["type"] == "object"
        assert "symbols" in schema["properties"]
        assert "strategy_name" in schema["required"]

    def test_get_request_schema_no_body(self):
        """Should return None for GET requests with no body"""
        spec = {
            "paths": {
                "/api/v1/operations": {
                    "get": {
                        "parameters": [
                            {
                                "name": "operation_type",
                                "in": "query",
                                "schema": {"type": "string"},
                            }
                        ]
                    }
                }
            }
        }

        fetcher = OpenAPIFetcher("http://localhost:8000")
        fetcher.spec = spec

        schema = fetcher.get_request_schema("/api/v1/operations", "GET")
        assert schema is None


class TestMCPToolParser:
    """Test MCP tool signature parsing"""

    def test_parse_tools_from_server(self):
        """Should parse all @mcp.tool() decorated functions"""
        parser = MCPToolParser()
        tools = parser.parse_tools("mcp/src/server.py")

        # Should find multiple tools
        assert len(tools) > 0
        assert "start_training" in tools
        assert "check_backend_health" in tools

    def test_parse_start_training_signature(self):
        """Should correctly parse start_training tool signature"""
        parser = MCPToolParser()
        tools = parser.parse_tools("mcp/src/server.py")

        start_training = tools["start_training"]

        assert start_training.name == "start_training"
        assert "symbols" in start_training.parameters
        assert "timeframes" in start_training.parameters
        assert "strategy_name" in start_training.parameters

        # Check parameter types
        assert start_training.parameters["symbols"].type == "list[str]"
        assert start_training.parameters["timeframes"].type == "list[str]"
        assert start_training.parameters["strategy_name"].type == "str"

        # Check required vs optional
        assert start_training.parameters["symbols"].required is True
        assert start_training.parameters["start_date"].required is False

        # Check defaults
        assert start_training.parameters["start_date"].default is None

    def test_parse_simple_tool_signature(self):
        """Should parse simple tools with basic types"""
        parser = MCPToolParser()
        tools = parser.parse_tools("mcp/src/server.py")

        # Check health check tool (no params)
        health_check = tools["check_backend_health"]
        assert health_check.name == "check_backend_health"
        assert len(health_check.parameters) == 0  # async tools have no self

    def test_ignore_non_tool_functions(self):
        """Should only parse @mcp.tool() decorated functions"""
        # Create a temporary test file
        import tempfile

        test_code = """
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("test")

@mcp.tool()
def tool_function(x: int) -> int:
    return x

def regular_function(x: int) -> int:
    return x

@some_other_decorator()
def other_decorated(x: int) -> int:
    return x
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_code)
            temp_path = f.name

        try:
            parser = MCPToolParser()
            tools = parser.parse_tools(temp_path)

            assert len(tools) == 1
            assert "tool_function" in tools
            assert "regular_function" not in tools
            assert "other_decorated" not in tools
        finally:
            import os

            os.unlink(temp_path)
