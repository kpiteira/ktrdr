<!--
Version Change: none → 1.0.0
Modified Principles: none (initial creation)
Added Sections: I. Root Cause Analysis First, II. Test-Driven Development, III. Architectural Purity, IV. Performance Standards, V. Archon-First Development, VI. Quality Gates, VII. Development Workflow
Removed Sections: none
Templates Requiring Updates: ✅ updated plan-template.md, ✅ updated spec-template.md, ✅ updated tasks-template.md
Follow-up TODOs: none
-->

# KTRDR Constitution

## Core Principles

### I. Root Cause Analysis First

Every problem must be understood at its core before implementing any solution. Symptoms are diagnosed, not treated. Quick fixes that suppress errors or add workarounds are forbidden. Before writing any code, developers MUST understand the root cause, consider architectural implications, and propose solutions for review. Bandaid fixes that make code work but harder to understand violate this principle.

**Rationale**: Trading systems require absolute reliability. Surface-level fixes introduce hidden dependencies and technical debt that can cause catastrophic failures during market operations.

### II. Test-Driven Development (NON-NEGOTIABLE)

All code development follows strict TDD methodology: write tests first, confirm they fail, then implement functionality. Test categories are strictly enforced: Unit tests (<2s total), Integration tests (<30s total), E2E tests (<5min total). Tests MUST pass before any commit. No functionality ships without comprehensive test coverage including edge cases and error conditions.

**Rationale**: Financial systems demand absolute correctness. TDD ensures behavior is specified before implementation and prevents regressions that could lead to trading losses.

### III. Architectural Purity

System follows strict layered architecture: UI → API → Core → Data. No circular dependencies or tight coupling permitted. Each module has exactly ONE clear responsibility. Dependencies flow unidirectionally. Data flow follows defined patterns: IB Gateway → Data Manager → Indicators → Fuzzy → Neural → Decisions. Error handling bubbles up with context; errors are never silently swallowed.

**Rationale**: Complex trading systems require clear separation of concerns to maintain reliability, enable testing, and facilitate debugging during live trading operations.

### IV. Performance Standards

Unit tests complete in <2 seconds total. Integration tests complete in <30 seconds. E2E tests complete in <5 minutes. Code changes that violate performance thresholds require architectural review. Memory usage and computational efficiency are monitored. Real-time trading operations cannot be delayed by poorly performing code.

**Rationale**: Trading systems operate in real-time markets where milliseconds matter. Performance degradation can result in missed opportunities or execution delays.

## Quality Gates

Quality gates are checkpoints that MUST be satisfied before code progression. These are non-negotiable barriers that ensure system reliability and maintainability.

### Pre-Commit Quality Gate

1. `make test-unit` passes (<2s)
2. `make quality` passes (lint + format + typecheck)
3. No debug code, secrets, or TODO comments
4. Commit message clearly describes changes and impact
5. Changes limited to <30 files per commit

### Pre-Merge Quality Gate

1. All quality checks pass in CI
2. Integration tests pass (<30s)
3. Code review approval from qualified reviewer
4. No architectural principle violations
5. Performance benchmarks maintained

### Production Release Gate

1. E2E tests pass (<5min)
2. Security scan completed
3. Performance testing validates real-time requirements
4. Documentation updated for user-facing changes
5. Rollback plan documented

## Development Workflow

### UV Dependency Management

This project uses UV for Python dependency management. Direct Python execution is forbidden. All Python commands MUST use `uv run` prefix. Violation of this requirement breaks environment isolation and can cause dependency conflicts.

### Commit Discipline

Commits are atomic units of change. Large commits (>30 files) are prohibited as they are unmanageable and difficult to review. Each commit represents one logical change with clear description. Failing tests prevent commits. Quality checks are enforced pre-commit.

### Code Style Standards

Clarity over cleverness in all implementations. Explicit behavior over implicit assumptions. Type hints required for all functions. Docstrings explain "why" not just "what". Functions remain focused and under 50 lines. Existing codebase patterns MUST be followed for consistency.

## Governance

This constitution supersedes all other development practices and guidelines. Any conflicts between this constitution and other documentation must be resolved in favor of constitutional requirements.

### Amendment Process

Constitutional amendments require:

1. Documentation of proposed changes with rationale
2. Impact analysis on existing development workflows
3. Review and approval by project maintainers
4. Migration plan for existing code that conflicts with changes
5. Update of all dependent templates and documentation

### Compliance Review

All pull requests and code reviews MUST verify constitutional compliance. Violations require immediate correction before merge. Complexity that appears to violate principles must be explicitly justified with business rationale. When in doubt, development teams must choose simpler approaches that align with constitutional requirements.

### Runtime Guidance

Use `CLAUDE.md` for detailed runtime development guidance and implementation patterns. The constitution defines non-negotiable principles; runtime guidance provides practical implementation advice within constitutional constraints.

**Version**: 1.0.0 | **Ratified**: 2025-09-20 | **Last Amended**: 2025-09-20
