#!/usr/bin/env python3
"""
MCP Tool Signature Validation Script

Validates MCP tool signatures against backend OpenAPI specification.
"""

import argparse
import json
import sys
from dataclasses import dataclass
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
