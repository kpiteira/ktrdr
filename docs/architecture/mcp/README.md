# MCP Architecture Documentation

This directory contains comprehensive architecture and implementation documentation for the KTRDR MCP (Model Context Protocol) integration.

---

## 📚 Documentation Structure

### Core Response Handling & Docstrings

**Location**: [./ARCHITECTURE.md](./ARCHITECTURE.md) | [./IMPLEMENTATION.md](./IMPLEMENTATION.md)

**Status**: Ready for Implementation

**What**: Standardize response handling across API clients and massively improve MCP tool docstrings

**Why**:
- Inconsistent response extraction patterns across domain clients
- Tool docstrings are the primary interface for LLM agents
- Better docstrings = better agent performance

**Approach**:
- Hybrid response handling (simple extractors + strict validation)
- Comprehensive docstring standard (Args, Returns, Examples, See Also)
- Backward compatible, gradual migration

**Branch**: `feat/mcp-response-handling-and-docstrings`

---

### Async Operations Integration

**Location**: [./async/REQUIREMENTS.md](./async/REQUIREMENTS.md) | [./async/ARCHITECTURE.md](./async/ARCHITECTURE.md) | [./async/IMPLEMENTATION.md](./async/IMPLEMENTATION.md)

**Status**: Completed (Merged in PR #74)

**What**: Enable AI agents to manage KTRDR's async operations through MCP tools

**Why**:
- Agents couldn't track long-running operations (training, data loading)
- No operation discovery or cancellation capabilities
- Fire-and-forget pattern needed for token efficiency

**Delivered**:
- 4 new MCP tools (list, status, cancel, results)
- 2 updated tools (trigger_data_loading, start_training)
- Domain-specific API clients (Data, Training, Operations)
- Minimal backend enhancements (~27 lines)

**Branch**: Merged to `main`

---

### OpenAPI Signature Validation

**Location**: [./openapi-validation/ARCHITECTURE.md](./openapi-validation/ARCHITECTURE.md) | [./openapi-validation/IMPLEMENTATION.md](./openapi-validation/IMPLEMENTATION.md)

**Status**: Ready for Implementation

**What**: Automated validation of MCP tool signatures against backend API contracts

**Why**:
- MCP signatures can drift from backend contracts (PR #74 example)
- Runtime errors that could be caught at development time
- No automated verification of API contracts

**Approach**:
- AST parsing of MCP tool signatures
- OpenAPI spec fetching from backend
- Signature comparison with type mapping
- Pre-commit hook + CI integration

**Branch**: `feat/mcp-openapi-validation`

---

## 🎯 Architecture Principles (Shared)

All MCP architecture follows these core principles:

1. **Backward Compatibility** - No breaking changes
2. **Gradual Migration** - Incremental improvements
3. **Type Safety** - Strong typing throughout
4. **LLM-Friendly** - Optimize for AI agent interaction
5. **Fail Fast** - Catch errors early in development

---

## 📖 Reading Guide

### For Understanding Current System

Start here if you want to understand how MCP currently works:

1. **Async Operations Requirements** - What problems async operations solve
2. **Async Operations Architecture** - How the system is structured
3. Review merged PR #74 for actual implementation

### For Implementing New Features

Start here if you're adding new MCP tools or improving the system:

1. **Core Architecture** - Response handling patterns and docstring standards
2. **Core Implementation** - TDD workflow and task breakdown
3. **OpenAPI Validation** - How to validate your changes

### For Contributing

Before making changes:

1. Read relevant architecture document
2. Follow implementation plan (TDD workflow)
3. Run validation: `make test-unit && make quality`
4. Check OpenAPI validation if modifying tool signatures

---

## 🔄 Implementation Status

| Feature | Status | Branch | PR |
|---------|--------|--------|-----|
| Async Operations | ✅ Merged | `feature/mcp-async-operations` | #74 |
| Response Handling | 📋 Ready | `feat/mcp-response-handling-and-docstrings` | TBD |
| OpenAPI Validation | 📋 Ready | `feat/mcp-openapi-validation` | TBD |

---

## 🛠️ Development Workflow

### Standard TDD Pattern

All implementations follow strict TDD:

```bash
# RED - Write failing tests
uv run pytest tests/unit/... -v
# Tests FAIL (expected)

# GREEN - Implement to pass tests
# Edit code...
make test-unit
# Tests PASS

# REFACTOR - Clean up
# Improve code quality...
make test-unit  # Still pass
make quality    # Lint, format, typecheck

# COMMIT
git commit -m "feat(mcp): describe change"
```

### Quality Gates (Before Every Commit)

```bash
make test-unit   # Must pass (<2s)
make quality     # Must pass (lint + format + typecheck)
```

### Branch Strategy

- Feature branches off `main`
- One feature = one branch
- Delete branch after merge
- Use descriptive names: `feat/mcp-{feature-name}`

---

## 📐 Architecture Patterns

### Domain-Specific Clients (Established)

```python
# Separation of concerns by domain
class DataAPIClient(BaseAPIClient): ...
class TrainingAPIClient(BaseAPIClient): ...
class OperationsAPIClient(BaseAPIClient): ...

# Unified facade for backward compatibility
class KTRDRAPIClient:
    def __init__(self):
        self.data = DataAPIClient(...)
        self.training = TrainingAPIClient(...)
        self.operations = OperationsAPIClient(...)
```

### Response Handling (Proposed)

```python
# Simple extraction (common cases)
items = self._extract_list(response)  # Empty list if missing

# Strict validation (critical operations)
data = self._extract_or_raise(response, operation="training start")  # Raises if missing
```

### Tool Docstrings (Proposed)

```python
@mcp.tool()
async def tool_name(...) -> dict[str, Any]:
    """
    One-line summary

    Extended description

    Args:
        param: Description with valid values

    Returns:
        Complete structure with field descriptions

    Raises:
        Errors with scenarios

    Examples:
        Working code examples

    See Also:
        - related_tool(): When to use
    """
```

---

## 🔗 Related Documentation

- **MCP Server**: [../../mcp/README.md](../../mcp/README.md) - MCP server usage
- **MCP Tools**: [../../mcp/MCP_TOOLS.md](../../mcp/MCP_TOOLS.md) - Tool reference
- **Backend API**: [../../ktrdr/api/](../../ktrdr/api/) - Backend endpoints
- **Project Guide**: [../../CLAUDE.md](../../CLAUDE.md) - Development guidelines

---

## 💡 Contributing

When adding new MCP features:

1. **Create architecture document first** - Follow existing patterns
2. **Write implementation plan** - Break down into TDD tasks
3. **Get approval** - Discuss with team before coding
4. **Follow TDD strictly** - RED → GREEN → REFACTOR
5. **Update this README** - Add your feature to the status table

Questions? Check existing docs or ask in discussions.

---

**Last Updated**: 2025-10-05
