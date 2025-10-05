#!/usr/bin/env python3
"""
MCP Tool Signature Validation Script

Validates MCP tool signatures against backend OpenAPI specification.
"""

import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx


@dataclass
class ValidationConfig:
    """Validation configuration from endpoint_mapping.json"""

    tools: dict[str, dict[str, Any]]

    def __post_init__(self):
        """Validate configuration structure"""
        for tool_name, tool_config in self.tools.items():
            required = ["endpoint", "method", "critical", "description"]
            missing = [f for f in required if f not in tool_config]
            if missing:
                raise ValueError(
                    f"Tool '{tool_name}' missing required fields: {missing}"
                )

    @classmethod
    def from_file(cls, path: str) -> "ValidationConfig":
        """Load configuration from JSON file"""
        with open(path) as f:
            data = json.load(f)

        if "tools" not in data:
            raise ValueError("Config missing 'tools' section")

        return cls(tools=data["tools"])


class OpenAPIFetcher:
    """Fetch and parse OpenAPI specification from backend"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.spec: Optional[dict] = None

    def fetch(self) -> dict[str, Any]:
        """
        Fetch OpenAPI spec from backend.

        Returns:
            OpenAPI specification dict

        Raises:
            ConnectionError: If backend not reachable
        """
        url = f"{self.base_url}/openapi.json"

        try:
            response = httpx.get(url, timeout=10.0)
            response.raise_for_status()
            self.spec = response.json()
            return self.spec
        except httpx.ConnectError as e:
            raise ConnectionError(
                f"Backend not reachable at {url}. Ensure backend is running."
            ) from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Failed to fetch OpenAPI spec: HTTP {e.response.status_code}"
            ) from e

    def get_request_schema(
        self, endpoint: str, method: str
    ) -> Optional[dict[str, Any]]:
        """
        Get request schema for endpoint.

        Resolves $ref references to actual schemas.

        Args:
            endpoint: API endpoint path
            method: HTTP method (uppercase)

        Returns:
            Schema dict or None if not found
        """
        if not self.spec:
            raise ValueError("Must call fetch() first")

        # Get endpoint definition
        path_item = self.spec.get("paths", {}).get(endpoint)
        if not path_item:
            return None

        operation = path_item.get(method.lower())
        if not operation:
            return None

        # Get request body schema
        request_body = operation.get("requestBody")
        if not request_body:
            return None  # GET requests have no body

        content = request_body.get("content", {})
        json_content = content.get("application/json")
        if not json_content:
            return None

        schema = json_content.get("schema")
        if not schema:
            return None

        # Resolve $ref if present
        if "$ref" in schema:
            return self._resolve_ref(schema["$ref"])

        return schema

    def _resolve_ref(self, ref: str) -> dict[str, Any]:
        """
        Resolve $ref to actual schema.

        Args:
            ref: Reference string like "#/components/schemas/TrainingStartRequest"

        Returns:
            Resolved schema dict
        """
        if not ref.startswith("#/"):
            raise ValueError(f"External refs not supported: {ref}")

        # Parse ref path
        parts = ref[2:].split("/")  # Remove "#/" prefix

        # Navigate spec
        current = self.spec
        for part in parts:
            current = current[part]

        return current


@dataclass
class ParameterInfo:
    """Information about a function parameter"""

    name: str
    type: str  # Python type annotation as string
    required: bool
    default: Any = None


@dataclass
class ToolSignature:
    """Signature of an MCP tool"""

    name: str
    parameters: dict[str, ParameterInfo] = field(default_factory=dict)
    return_type: str = "None"
    line_number: int = 0


class MCPToolParser:
    """Parse MCP tool signatures from server.py using AST"""

    def parse_tools(self, server_file: str) -> dict[str, ToolSignature]:
        """
        Extract all @mcp.tool() decorated functions.

        Args:
            server_file: Path to MCP server file

        Returns:
            Dict mapping tool names to their signatures
        """
        with open(server_file) as f:
            tree = ast.parse(f.read())

        tools = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) or isinstance(
                node, ast.FunctionDef
            ):
                # Check for @mcp.tool() decorator
                if self._has_mcp_decorator(node):
                    sig = self._extract_signature(node)
                    tools[node.name] = sig

        return tools

    def _has_mcp_decorator(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> bool:
        """Check if function has @mcp.tool() decorator"""
        for decorator in func_node.decorator_list:
            # Handle @mcp.tool()
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    if (
                        isinstance(decorator.func.value, ast.Name)
                        and decorator.func.value.id == "mcp"
                        and decorator.func.attr == "tool"
                    ):
                        return True
        return False

    def _extract_signature(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> ToolSignature:
        """
        Extract parameter names, types, and defaults.

        Returns:
            ToolSignature with parameters and metadata
        """
        params = {}

        # Get defaults - they align from the right
        num_args = len(func_node.args.args)
        num_defaults = len(func_node.args.defaults)
        defaults_offset = num_args - num_defaults

        for i, arg in enumerate(func_node.args.args):
            # Skip 'self' parameter
            if arg.arg == "self":
                continue

            # Determine if parameter has a default
            has_default = i >= defaults_offset
            default_value = None
            if has_default:
                default_node = func_node.args.defaults[i - defaults_offset]
                default_value = self._get_default_value(default_node)

            param_info = ParameterInfo(
                name=arg.arg,
                type=self._get_type_annotation(arg.annotation),
                required=not has_default,
                default=default_value,
            )
            params[arg.arg] = param_info

        return ToolSignature(
            name=func_node.name,
            parameters=params,
            return_type=self._get_type_annotation(func_node.returns),
            line_number=func_node.lineno,
        )

    def _get_type_annotation(self, annotation_node: Optional[ast.expr]) -> str:
        """Extract type annotation as string"""
        if annotation_node is None:
            return "Any"

        # Handle simple types: str, int, bool, etc.
        if isinstance(annotation_node, ast.Name):
            return annotation_node.id

        # Handle list[T], dict[K, V], etc.
        if isinstance(annotation_node, ast.Subscript):
            if isinstance(annotation_node.value, ast.Name):
                base_type = annotation_node.value.id
                # Get the subscript type
                if isinstance(annotation_node.slice, ast.Name):
                    inner = annotation_node.slice.id
                    return f"{base_type}[{inner}]"
                elif isinstance(annotation_node.slice, ast.Tuple):
                    # Handle dict[str, Any]
                    inner_types = [
                        self._get_type_annotation(elt)
                        for elt in annotation_node.slice.elts
                    ]
                    return f"{base_type}[{', '.join(inner_types)}]"

        # Handle Optional[T]
        if isinstance(annotation_node, ast.Subscript):
            if isinstance(annotation_node.value, ast.Name):
                if annotation_node.value.id == "Optional":
                    return self._get_type_annotation(annotation_node.slice)

        # Fallback
        return ast.unparse(annotation_node)

    def _get_default_value(self, default_node: ast.expr) -> Any:
        """Extract default value from AST node"""
        if isinstance(default_node, ast.Constant):
            return default_node.value
        elif isinstance(default_node, ast.Name):
            if default_node.id == "None":
                return None
            return default_node.id
        elif isinstance(default_node, ast.List):
            return []
        elif isinstance(default_node, ast.Dict):
            return {}
        else:
            # For complex defaults, return string representation
            return ast.unparse(default_node)


def main(argv: list[str] | None = None) -> int:
    """
    Main entry point for validation script.

    Returns:
        Exit code (0 = success, 1 = validation failed)
    """
    parser = argparse.ArgumentParser(
        description="Validate MCP tool signatures against backend OpenAPI spec"
    )
    parser.add_argument(
        "--config",
        default="mcp/endpoint_mapping.json",
        help="Path to endpoint mapping config"
    )
    parser.add_argument(
        "--server",
        default="mcp/src/server.py",
        help="Path to MCP server file"
    )
    parser.add_argument(
        "--backend-url",
        default="http://localhost:8000",
        help="Backend API base URL"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors"
    )

    args = parser.parse_args(argv)

    # Load configuration
    try:
        config = ValidationConfig.from_file(args.config)
    except Exception as e:
        print(f"❌ Failed to load config: {e}", file=sys.stderr)
        return 1

    print(f"✅ Loaded config for {len(config.tools)} tools")

    # TODO: Implement validation logic
    return 0


if __name__ == "__main__":
    sys.exit(main())
