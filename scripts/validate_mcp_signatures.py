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
class ValidationError:
    """Validation error details"""

    tool: str
    error_type: str  # missing_required, type_mismatch, etc.
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    severity: str = "CRITICAL"  # CRITICAL, HIGH, MEDIUM, LOW


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


class SignatureComparator:
    """Compare MCP tool signatures against OpenAPI spec"""

    def __init__(self, openapi_fetcher: OpenAPIFetcher, config: ValidationConfig):
        self.fetcher = openapi_fetcher
        self.config = config

    def compare_all(self, tools: dict[str, ToolSignature]) -> list[ValidationError]:
        """Compare all tools against their endpoints"""
        all_errors = []

        for tool_name, tool_sig in tools.items():
            if tool_name not in self.config.tools:
                # Tool not in mapping - skip (might be helper tool)
                continue

            tool_config = self.config.tools[tool_name]
            endpoint = tool_config["endpoint"]
            method = tool_config["method"]

            # Get schema from OpenAPI
            schema = self.fetcher.get_request_schema(endpoint, method)
            if not schema:
                # GET requests have no body - that's OK
                if method.upper() == "GET":
                    continue
                all_errors.append(
                    ValidationError(
                        tool=tool_name,
                        error_type="no_schema",
                        message=f"No schema found for {method} {endpoint}",
                        severity="MEDIUM",
                    )
                )
                continue

            # Compare parameters
            errors = self._compare_parameters(tool_sig, schema, tool_config)
            all_errors.extend(errors)

        return all_errors

    def _compare_parameters(
        self,
        tool_sig: ToolSignature,
        schema: dict[str, Any],
        tool_config: dict[str, Any],
    ) -> list[ValidationError]:
        """Compare tool parameters against schema properties"""
        errors = []

        # Get required fields from schema
        required_fields = set(schema.get("required", []))
        tool_params = set(tool_sig.parameters.keys())
        tool_required = {
            name
            for name, param in tool_sig.parameters.items()
            if param.required
        }

        # Check for missing required parameters
        missing = required_fields - tool_params
        if missing:
            errors.append(
                ValidationError(
                    tool=tool_sig.name,
                    error_type="missing_required",
                    message=f"Missing required parameters: {', '.join(missing)}",
                    details={
                        "schema_requires": list(required_fields),
                        "tool_has": list(tool_required),
                        "missing": list(missing),
                    },
                    severity="CRITICAL",
                )
            )

        # Check for type mismatches
        for param_name, param_info in tool_sig.parameters.items():
            if param_name not in schema.get("properties", {}):
                continue  # Extra params OK if optional

            schema_prop = schema["properties"][param_name]
            schema_type = self._openapi_to_python_type(schema_prop)

            if param_info.type != schema_type:
                errors.append(
                    ValidationError(
                        tool=tool_sig.name,
                        error_type="type_mismatch",
                        message=f"Parameter '{param_name}' type mismatch",
                        details={
                            "parameter": param_name,
                            "schema_expects": schema_type,
                            "tool_has": param_info.type,
                        },
                        severity="CRITICAL"
                        if tool_config.get("critical", False)
                        else "HIGH",
                    )
                )

        return errors

    def _openapi_to_python_type(self, schema: dict) -> str:
        """Convert OpenAPI type to Python type annotation"""
        if "type" not in schema:
            return "Any"

        openapi_type = schema["type"]

        if openapi_type == "array":
            if "items" in schema:
                item_type = self._openapi_to_python_type(schema["items"])
                return f"list[{item_type}]"
            return "list[Any]"
        elif openapi_type == "object":
            return "dict[str, Any]"
        else:
            type_map = {
                "string": "str",
                "integer": "int",
                "number": "float",
                "boolean": "bool",
            }
            return type_map.get(openapi_type, "Any")


class ReportGenerator:
    """Generate human-readable validation reports"""

    def generate_report(
        self, errors: list[ValidationError], total_tools: int
    ) -> tuple[str, int]:
        """
        Generate colored terminal report.

        Returns:
            (report_string, exit_code)
        """
        if not errors:
            return self._success_report(total_tools), 0

        return self._error_report(errors, total_tools), 1

    def _success_report(self, total_tools: int) -> str:
        """Generate success report"""
        lines = [
            "=" * 70,
            "MCP TOOL SIGNATURE VALIDATION PASSED",
            "=" * 70,
            "",
            f"✅ All {total_tools} MCP tools match backend API contracts",
            "",
            "=" * 70,
        ]
        return "\n".join(lines)

    def _error_report(self, errors: list[ValidationError], total_tools: int) -> str:
        """Generate error report"""
        lines = [
            "=" * 70,
            "MCP TOOL SIGNATURE VALIDATION FAILED",
            "=" * 70,
            "",
        ]

        # Group errors by tool
        errors_by_tool: dict[str, list[ValidationError]] = {}
        for error in errors:
            if error.tool not in errors_by_tool:
                errors_by_tool[error.tool] = []
            errors_by_tool[error.tool].append(error)

        # Report each tool's errors
        for tool_name, tool_errors in errors_by_tool.items():
            lines.append(f"❌ {tool_name}")
            for error in tool_errors:
                lines.append(f"   ERROR: {error.message}")
                if error.details:
                    for key, value in error.details.items():
                        lines.append(f"     {key}: {value}")
            lines.append("")

        # Summary
        invalid_tools = len(errors_by_tool)
        valid_tools = total_tools - invalid_tools
        lines.extend(
            [
                "SUMMARY:",
                f"  Total tools validated: {total_tools}",
                f"  ✅ Valid tools:         {valid_tools}",
                f"  ❌ Invalid tools:       {invalid_tools}",
                "",
                "VALIDATION FAILED - Fix errors above before committing.",
                "=" * 70,
            ]
        )

        return "\n".join(lines)


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

    # 1. Load configuration
    try:
        config = ValidationConfig.from_file(args.config)
    except Exception as e:
        print(f"❌ Failed to load config: {e}", file=sys.stderr)
        return 1

    # 2. Fetch OpenAPI spec
    try:
        fetcher = OpenAPIFetcher(args.backend_url)
        fetcher.fetch()
    except ConnectionError as e:
        print(f"❌ {e}", file=sys.stderr)
        print("Ensure backend is running at", args.backend_url, file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Failed to fetch OpenAPI spec: {e}", file=sys.stderr)
        return 1

    # 3. Parse MCP tools
    try:
        parser_obj = MCPToolParser()
        tools = parser_obj.parse_tools(args.server)
    except Exception as e:
        print(f"❌ Failed to parse MCP tools: {e}", file=sys.stderr)
        return 1

    # 4. Compare signatures
    comparator = SignatureComparator(fetcher, config)
    errors = comparator.compare_all(tools)

    # 5. Generate report
    reporter = ReportGenerator()
    report, exit_code = reporter.generate_report(errors, len(tools))

    print(report)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
