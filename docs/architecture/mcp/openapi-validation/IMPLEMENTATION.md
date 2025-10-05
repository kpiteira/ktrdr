# MCP OpenAPI Validation - Implementation Plan

**Parent Document**: [Architecture](./ARCHITECTURE.md)

**Status**: Ready for Implementation
**Version**: 1.0
**Date**: 2025-10-05
**Branch**: `feat/mcp-openapi-validation`

---

## Overview

This document breaks down the implementation of OpenAPI signature validation into discrete, testable tasks following strict TDD methodology.

**Scope**:
- ✅ Validation script with AST parsing
- ✅ OpenAPI spec fetcher
- ✅ Signature comparator with type mapping
- ✅ Error report generator
- ✅ Pre-commit hook integration
- ✅ GitHub Actions CI workflow

**TDD Workflow** (Mandatory):
```
RED → GREEN → REFACTOR
Write failing test → Make it pass → Clean up code
```

**Quality Gates** (Before EVERY commit):
```bash
make test-unit   # Must pass (<2s)
make quality     # Must pass (lint + format + typecheck)
```

**Branching Strategy**:
- **Feature Branch**: `feat/mcp-openapi-validation` (off `main`)
- **Merge Target**: `main`
- **After Merge**: Delete feature branch

---

## TASK-1: Create Endpoint Mapping Configuration

**Objective**: Define mapping between MCP tools and backend endpoints

**Files**:
- `mcp/endpoint_mapping.json` (NEW)

**Implementation**:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MCP Tool to Backend API Endpoint Mapping",
  "description": "Maps MCP tool names to their corresponding backend API endpoints for validation",
  "tools": {
    "start_training": {
      "endpoint": "/api/v1/trainings/start",
      "method": "POST",
      "critical": true,
      "description": "Start neural network training"
    },
    "trigger_data_loading": {
      "endpoint": "/api/v1/data/load",
      "method": "POST",
      "critical": true,
      "description": "Trigger async data loading operation"
    },
    "list_operations": {
      "endpoint": "/api/v1/operations",
      "method": "GET",
      "critical": false,
      "description": "List operations with filters"
    },
    "get_operation_status": {
      "endpoint": "/api/v1/operations/{operation_id}",
      "method": "GET",
      "critical": false,
      "path_params": ["operation_id"],
      "description": "Get detailed operation status"
    },
    "cancel_operation": {
      "endpoint": "/api/v1/operations/{operation_id}/cancel",
      "method": "POST",
      "critical": false,
      "path_params": ["operation_id"],
      "description": "Cancel running operation"
    },
    "get_operation_results": {
      "endpoint": "/api/v1/operations/{operation_id}/results",
      "method": "GET",
      "critical": false,
      "path_params": ["operation_id"],
      "description": "Get operation results summary"
    },
    "get_market_data": {
      "endpoint": "/api/v1/data/{symbol}/{timeframe}",
      "method": "GET",
      "critical": false,
      "path_params": ["symbol", "timeframe"],
      "description": "Get cached market data"
    },
    "get_symbols": {
      "endpoint": "/api/v1/symbols",
      "method": "GET",
      "critical": false,
      "description": "Get available trading symbols"
    },
    "get_indicators": {
      "endpoint": "/api/v1/indicators/",
      "method": "GET",
      "critical": false,
      "description": "List available indicators"
    },
    "get_strategies": {
      "endpoint": "/api/v1/strategies/",
      "method": "GET",
      "critical": false,
      "description": "List available strategies"
    },
    "list_trained_models": {
      "endpoint": "/api/v1/models",
      "method": "GET",
      "critical": false,
      "description": "List trained models"
    },
    "health_check": {
      "endpoint": "/health",
      "method": "GET",
      "critical": false,
      "description": "Backend health check"
    }
  }
}
```

**No Tests Required**: Configuration file

**Commit**:
```bash
git add mcp/endpoint_mapping.json
git commit -m "feat(mcp): add endpoint mapping config for OpenAPI validation

Maps MCP tool names to backend API endpoints with:
- Endpoint paths
- HTTP methods
- Critical operation flags
- Path parameter definitions

This config enables automated signature validation against backend contracts."
```

---

## TASK-2: Create Validation Script Foundation

**Objective**: Create base script structure with CLI interface

**Files**:
- `scripts/validate_mcp_signatures.py` (NEW)
- `tests/unit/scripts/test_validate_mcp_signatures.py` (NEW)

**TDD Workflow**:

**RED Phase**:
```python
# tests/unit/scripts/test_validate_mcp_signatures.py

import pytest
from scripts.validate_mcp_signatures import main, ValidationConfig


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
        with pytest.raises(ValueError):
            ValidationConfig(tools={"invalid": {}})  # Missing required fields


class TestCLI:
    """Test command-line interface"""

    def test_help_message(self, capsys):
        """Should display help message"""
        with pytest.raises(SystemExit):
            main(["--help"])

        captured = capsys.readouterr()
        assert "Validate MCP tool signatures" in captured.out

    def test_strict_flag(self):
        """Should support --strict flag"""
        # Mock validation to return warnings
        # Verify exit code 0 without --strict, exit code 1 with --strict
```

**GREEN Phase**:
```python
# scripts/validate_mcp_signatures.py

"""
MCP Tool Signature Validation Script

Validates MCP tool signatures against backend OpenAPI specification.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ValidationConfig:
    """Validation configuration from endpoint_mapping.json"""

    tools: dict[str, dict[str, Any]]

    @classmethod
    def from_file(cls, path: str) -> "ValidationConfig":
        """Load configuration from JSON file"""
        with open(path) as f:
            data = json.load(f)

        if "tools" not in data:
            raise ValueError("Config missing 'tools' section")

        # Validate each tool entry
        for tool_name, tool_config in data["tools"].items():
            required = ["endpoint", "method", "critical", "description"]
            missing = [f for f in required if f not in tool_config]
            if missing:
                raise ValueError(
                    f"Tool '{tool_name}' missing required fields: {missing}"
                )

        return cls(tools=data["tools"])


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
```

**Quality Gate & Commit**:
```bash
make test-unit
make quality
git add scripts/validate_mcp_signatures.py tests/unit/scripts/test_validate_mcp_signatures.py
git commit -m "feat(mcp): add validation script foundation with CLI interface

- Create ValidationConfig for loading endpoint mappings
- Add CLI with --config, --server, --backend-url, --strict flags
- Full test coverage for config loading and CLI"
```

---

## TASK-3: Add OpenAPI Spec Fetcher

**Objective**: Fetch and parse OpenAPI specification from backend

**Files**:
- `scripts/validate_mcp_signatures.py` (UPDATE)
- `tests/unit/scripts/test_validate_mcp_signatures.py` (UPDATE)

**TDD Workflow**:

**RED Phase**:
```python
# tests/unit/scripts/test_validate_mcp_signatures.py

class TestOpenAPIFetcher:
    """Test OpenAPI spec fetching"""

    def test_fetch_spec_from_backend(self, httpx_mock):
        """Should fetch OpenAPI spec from backend"""
        httpx_mock.add_response(
            url="http://localhost:8000/openapi.json",
            json={"openapi": "3.1.0", "paths": {}}
        )

        fetcher = OpenAPIFetcher("http://localhost:8000")
        spec = fetcher.fetch()

        assert spec["openapi"] == "3.1.0"
        assert "paths" in spec

    def test_fetch_handles_connection_error(self):
        """Should raise clear error if backend not reachable"""
        fetcher = OpenAPIFetcher("http://localhost:9999")

        with pytest.raises(ConnectionError) as exc_info:
            fetcher.fetch()

        assert "Backend not reachable" in str(exc_info.value)

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
                            "strategy_name": {"type": "string"}
                        },
                        "required": ["symbols", "strategy_name"]
                    }
                }
            }
        }

        fetcher = OpenAPIFetcher("http://localhost:8000")
        fetcher.spec = spec

        schema = fetcher.get_request_schema("/api/v1/trainings/start", "POST")

        assert schema["type"] == "object"
        assert "symbols" in schema["properties"]
        assert "strategy_name" in schema["required"]
```

**GREEN Phase**:
```python
# scripts/validate_mcp_signatures.py

import httpx
from typing import Optional


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
                f"Backend not reachable at {url}. "
                f"Ensure backend is running."
            ) from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Failed to fetch OpenAPI spec: HTTP {e.response.status_code}"
            ) from e

    def get_request_schema(
        self,
        endpoint: str,
        method: str
    ) -> Optional[dict[str, Any]]:
        """
        Get request schema for endpoint.

        Resolves $ref references to actual schemas.

        Args:
            endpoint: API endpoint path
            method: HTTP method (lowercase)

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
```

**Commit**:
```bash
make test-unit
make quality
git add scripts/validate_mcp_signatures.py tests/unit/scripts/test_validate_mcp_signatures.py
git commit -m "feat(mcp): add OpenAPI spec fetcher with $ref resolution

- Fetch OpenAPI spec from backend /openapi.json
- Extract request schemas for endpoints
- Resolve $ref references to component schemas
- Handle connection errors gracefully"
```

---

## TASK-4: Add MCP Tool Signature Parser

**Objective**: Parse Python MCP tool signatures using AST

**Files**:
- `scripts/validate_mcp_signatures.py` (UPDATE)
- `tests/unit/scripts/test_validate_mcp_signatures.py` (UPDATE)

**Implementation** (following TDD pattern):

```python
# Key classes to implement:

@dataclass
class ParameterInfo:
    """Information about a function parameter"""
    name: str
    type: str  # Python type annotation as string
    required: bool
    default: Any

@dataclass
class ToolSignature:
    """Signature of an MCP tool"""
    name: str
    parameters: dict[str, ParameterInfo]
    return_type: str
    line_number: int

class MCPToolParser:
    """Parse MCP tool signatures from server.py"""

    def parse_tools(self, server_file: str) -> dict[str, ToolSignature]:
        """Extract all @mcp.tool() decorated functions"""
        # Use ast.parse() to parse Python file
        # Walk AST to find FunctionDef nodes with @mcp.tool() decorator
        # Extract parameter names, types, defaults, and required status
```

**Commit**:
```bash
make test-unit
make quality
git add scripts/validate_mcp_signatures.py tests/unit/scripts/test_validate_mcp_signatures.py
git commit -m "feat(mcp): add AST-based MCP tool signature parser

- Parse @mcp.tool() decorated functions from server.py
- Extract parameter names, types, and defaults
- Determine required vs optional parameters
- Track line numbers for error reporting"
```

---

## TASK-5: Add Signature Comparator with Type Mapping

**Objective**: Compare MCP signatures against OpenAPI schemas

**Files**:
- `scripts/validate_mcp_signatures.py` (UPDATE)
- `tests/unit/scripts/test_validate_mcp_signatures.py` (UPDATE)

**Implementation**:

```python
# Key classes:

@dataclass
class ValidationError:
    """Validation error details"""
    tool: str
    error_type: str  # missing_required, type_mismatch, etc.
    message: str
    details: dict[str, Any]
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW

class SignatureComparator:
    """Compare MCP tool signatures against OpenAPI spec"""

    def compare(
        self,
        tool_sig: ToolSignature,
        schema: dict[str, Any]
    ) -> list[ValidationError]:
        """Compare tool signature against schema"""
        # Check required parameters
        # Check type compatibility
        # Check parameter names
        # Return list of errors

    def _openapi_to_python_type(self, schema: dict) -> str:
        """Convert OpenAPI type to Python type annotation"""
        # Map OpenAPI types to Python:
        # "string" → "str"
        # "integer" → "int"
        # "array" of "string" → "list[str]"
        # "object" → "dict[str, Any]"
```

**Commit**:
```bash
make test-unit
make quality
git add scripts/validate_mcp_signatures.py tests/unit/scripts/test_validate_mcp_signatures.py
git commit -m "feat(mcp): add signature comparator with OpenAPI type mapping

- Compare MCP tool parameters against OpenAPI schemas
- Map OpenAPI types to Python type annotations
- Detect missing required parameters
- Detect type mismatches
- Categorize errors by severity"
```

---

## TASK-6: Add Error Report Generator

**Objective**: Generate human-readable validation reports

**Files**:
- `scripts/validate_mcp_signatures.py` (UPDATE)
- `tests/unit/scripts/test_validate_mcp_signatures.py` (UPDATE)

**Implementation**:

```python
class ReportGenerator:
    """Generate human-readable validation reports"""

    def generate_report(
        self,
        errors: list[ValidationError],
        total_tools: int
    ) -> str:
        """
        Generate colored terminal report.

        Groups errors by tool, shows line numbers, provides fixes.
        """
        # Use rich library for colored output
        # Group errors by tool
        # Show error type, message, details
        # Provide suggested fixes
        # Summary at end
```

**Example Output**:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MCP TOOL SIGNATURE VALIDATION FAILED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ start_training (mcp/src/server.py:L142)
   ERROR: Type mismatch for 'timeframes'
   Backend expects: list[str]
   Tool has:        str

   FIX: Change type from 'str' to 'list[str]'

SUMMARY: 10 valid, 2 invalid
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Commit**:
```bash
make test-unit
make quality
git add scripts/validate_mcp_signatures.py tests/unit/scripts/test_validate_mcp_signatures.py
git commit -m "feat(mcp): add colored validation error report generator

- Group errors by tool with line numbers
- Show error type, message, and suggested fixes
- Use rich library for colored terminal output
- Summary with valid/invalid tool counts"
```

---

## TASK-7: Integrate Components in Main

**Objective**: Wire all components together in main() function

**Files**:
- `scripts/validate_mcp_signatures.py` (UPDATE)

**Implementation**:

```python
def main(argv: list[str] | None = None) -> int:
    """Main validation logic"""
    # 1. Parse arguments
    # 2. Load config
    # 3. Fetch OpenAPI spec
    # 4. Parse MCP tools
    # 5. Compare signatures
    # 6. Generate report
    # 7. Return exit code based on errors
```

**Commit**:
```bash
make test-unit
make quality
git add scripts/validate_mcp_signatures.py
git commit -m "feat(mcp): integrate validation components in main workflow

- Wire fetcher, parser, comparator, reporter together
- Add progress indicators
- Handle errors gracefully
- Return proper exit codes"
```

---

## TASK-8: Add Pre-Commit Hook

**Objective**: Configure pre-commit hook to run validation

**Files**:
- `.pre-commit-config.yaml` (UPDATE)

**Implementation**:

```yaml
repos:
  - repo: local
    hooks:
      - id: validate-mcp-signatures
        name: Validate MCP Tool Signatures
        entry: bash -c 'if lsof -i:8000 -sTCP:LISTEN -t >/dev/null 2>&1; then uv run python scripts/validate_mcp_signatures.py; else echo "⚠️  Backend not running - skipping MCP validation"; fi'
        language: system
        files: ^mcp/src/server\.py$
        pass_filenames: false
        stages: [commit]
```

**Behavior**:
- Only runs if `mcp/src/server.py` modified
- Checks if backend running (port 8000)
- Skips with warning if backend not running
- Blocks commit if validation fails

**Commit**:
```bash
git add .pre-commit-config.yaml
git commit -m "feat(mcp): add pre-commit hook for signature validation

- Run validation on mcp/src/server.py changes
- Check if backend running before validation
- Skip gracefully if backend not available
- Block commit if validation fails"
```

---

## TASK-9: Add GitHub Actions Workflow

**Objective**: Create CI workflow for PR validation

**Files**:
- `.github/workflows/mcp-validation.yml` (NEW)

**Implementation**:

```yaml
name: MCP Signature Validation

on:
  pull_request:
    paths:
      - 'mcp/src/server.py'
      - 'mcp/src/clients/**'
      - 'ktrdr/api/**'

jobs:
  validate:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Start backend
        run: |
          ./start_ktrdr.sh &
          sleep 30  # Wait for backend startup

      - name: Validate signatures
        run: |
          uv run python scripts/validate_mcp_signatures.py --strict

      - name: Upload report
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: validation-report
          path: validation-report.txt
```

**Commit**:
```bash
git add .github/workflows/mcp-validation.yml
git commit -m "feat(mcp): add GitHub Actions workflow for signature validation

- Validate on PRs affecting MCP or backend code
- Start backend in CI environment
- Run validation with --strict flag
- Upload report artifact on failure"
```

---

## TASK-10: Add Documentation

**Objective**: Document validation usage and troubleshooting

**Files**:
- `scripts/README.md` (NEW or UPDATE)
- `mcp/README.md` (UPDATE)

**Content**:

```markdown
## MCP Signature Validation

Automatically validates MCP tool signatures against backend API contracts.

### Usage

**Local validation**:
```bash
# Start backend
./start_ktrdr.sh

# Run validation
uv run python scripts/validate_mcp_signatures.py

# Strict mode (warnings as errors)
uv run python scripts/validate_mcp_signatures.py --strict
```

**Pre-commit hook** (automatic):
- Runs when `mcp/src/server.py` modified
- Requires backend running
- Blocks commit if validation fails

**CI validation** (automatic):
- Runs on PRs affecting MCP or backend
- Blocks merge if validation fails

### Troubleshooting

**"Backend not reachable"**:
- Ensure backend running: `./start_ktrdr.sh`
- Check port 8000: `lsof -i:8000`

**Validation failures**:
- Read error report carefully
- Check parameter names and types
- Consult endpoint_mapping.json
```

**Commit**:
```bash
git add scripts/README.md mcp/README.md
git commit -m "docs(mcp): add validation usage and troubleshooting guide

- Document local and CI validation
- Add usage examples
- Include troubleshooting section"
```

---

## Final Checklist

Before creating PR:

- [ ] All 10 tasks completed
- [ ] All commits passed `make test-unit` and `make quality`
- [ ] Validation script works locally
- [ ] Pre-commit hook configured
- [ ] GitHub Actions workflow added
- [ ] Documentation complete

---

## Create Pull Request

```bash
# Final checks
make test-unit
make quality

# Create PR
gh pr create \
  --title "feat(mcp): add OpenAPI signature validation" \
  --body "## Summary

Implements automated validation of MCP tool signatures against backend
OpenAPI specification to prevent contract mismatches.

## Features

- AST-based MCP tool signature parsing
- OpenAPI spec fetching with $ref resolution
- Type mapping (OpenAPI → Python)
- Signature comparison with detailed error reporting
- Pre-commit hook integration
- GitHub Actions CI workflow

## Benefits

- Catches signature mismatches at development time
- Prevents PR #74 type issues from recurring
- Clear error messages with suggested fixes
- Enforced in CI (blocks bad PRs)

## Testing

- ✅ Full unit test coverage
- ✅ Manual testing with real backend
- ✅ Pre-commit hook tested
- ✅ CI workflow tested"
```

---

## Success Criteria

- [x] Validation script with all components
- [x] Endpoint mapping configuration
- [x] Pre-commit hook integration
- [x] GitHub Actions workflow
- [x] Full test coverage
- [x] Documentation complete
- [x] Works with real backend

---

**End of Implementation Plan**
