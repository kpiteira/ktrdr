#!/usr/bin/env python
"""
API Documentation Generator

This script extracts OpenAPI documentation from the FastAPI application
and generates Markdown files for each endpoint.

Usage:
    python -m scripts.generate_api_docs
"""

import json
import os
import sys
from pathlib import Path

# Add the project root to the path so we can import the application
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from ktrdr.api.main import app
except ImportError:
    print("Error: Could not import the FastAPI application.")
    print("Make sure you're running this script from the project root.")
    sys.exit(1)

# Directory where API documentation will be generated
DOCS_DIR = project_root / "docs" / "api-reference"
os.makedirs(DOCS_DIR, exist_ok=True)


def generate_api_docs():
    """Generate API documentation from the FastAPI application."""
    print("Generating API documentation...")

    # Get the OpenAPI schema from FastAPI
    openapi_schema = app.openapi()

    # Create an index file for the API reference
    with open(DOCS_DIR / "index.md", "w") as f:
        f.write("# KTRDR API Reference\n\n")
        f.write("This documentation is automatically generated from the API code.\n\n")
        f.write("## Endpoints\n\n")

    # Process each endpoint in the OpenAPI schema
    paths = openapi_schema.get("paths", {})
    for path, path_item in paths.items():
        for method, operation in path_item.items():
            if method in ["get", "post", "put", "delete", "patch"]:
                generate_endpoint_doc(path, method, operation)

                # Add entry to the index file
                with open(DOCS_DIR / "index.md", "a") as f:
                    operation.get("tags", ["Other"])[0]
                    endpoint_id = f"{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}"
                    endpoint_file = f"{endpoint_id}.md"
                    f.write(
                        f"- [{method.upper()} {path}](./{endpoint_file}) - {operation.get('summary', 'No description')}\n"
                    )

    print(f"API documentation generated successfully in {DOCS_DIR}")


def generate_endpoint_doc(path, method, operation):
    """Generate documentation for a single API endpoint."""
    # Create a unique identifier for the endpoint file
    endpoint_id = f"{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}"
    endpoint_file = DOCS_DIR / f"{endpoint_id}.md"

    with open(endpoint_file, "w") as f:
        # Write the title
        summary = operation.get("summary", "No description")
        f.write(f"# {summary}\n\n")

        # Write the endpoint information
        f.write(f"**Endpoint:** `{method.upper()} {path}`\n\n")

        # Write the description
        description = operation.get("description", "")
        if description:
            f.write(f"## Description\n\n{description}\n\n")

        # Write the request parameters
        parameters = operation.get("parameters", [])
        if parameters:
            path_params = [p for p in parameters if p.get("in") == "path"]
            query_params = [p for p in parameters if p.get("in") == "query"]

            if path_params:
                f.write("## Path Parameters\n\n")
                f.write("| Parameter | Type | Required | Description |\n")
                f.write("|-----------|------|----------|-------------|\n")
                for param in path_params:
                    param_name = param.get("name", "")
                    param_type = param.get("schema", {}).get("type", "")
                    required = "Yes" if param.get("required", False) else "No"
                    desc = param.get("description", "")
                    f.write(
                        f"| `{param_name}` | {param_type} | {required} | {desc} |\n"
                    )
                f.write("\n")

            if query_params:
                f.write("## Query Parameters\n\n")
                f.write("| Parameter | Type | Required | Description |\n")
                f.write("|-----------|------|----------|-------------|\n")
                for param in query_params:
                    param_name = param.get("name", "")
                    param_type = param.get("schema", {}).get("type", "")
                    required = "Yes" if param.get("required", False) else "No"
                    desc = param.get("description", "")
                    f.write(
                        f"| `{param_name}` | {param_type} | {required} | {desc} |\n"
                    )
                f.write("\n")

        # Write the request body
        request_body = operation.get("requestBody", {})
        if request_body:
            f.write("## Request Body\n\n")
            content = request_body.get("content", {}).get("application/json", {})
            schema = content.get("schema", {})

            # Write example if available
            example = content.get("example")
            if example:
                f.write("```json\n")
                f.write(json.dumps(example, indent=2))
                f.write("\n```\n\n")

            # Extract properties from schema
            properties = schema.get("properties", {})
            if properties:
                f.write("| Property | Type | Required | Description |\n")
                f.write("|----------|------|----------|-------------|\n")
                required_props = schema.get("required", [])
                for prop_name, prop in properties.items():
                    prop_type = prop.get("type", "")
                    required = "Yes" if prop_name in required_props else "No"
                    desc = prop.get("description", "")
                    f.write(f"| `{prop_name}` | {prop_type} | {required} | {desc} |\n")
                f.write("\n")

        # Write the responses
        responses = operation.get("responses", {})
        if responses:
            f.write("## Responses\n\n")
            for status_code, response in responses.items():
                f.write(f"### {status_code}\n\n")
                desc = response.get("description", "")
                f.write(f"{desc}\n\n")

                content = response.get("content", {}).get("application/json", {})
                example = content.get("example")
                if example:
                    f.write("```json\n")
                    f.write(json.dumps(example, indent=2))
                    f.write("\n```\n\n")


if __name__ == "__main__":
    generate_api_docs()
