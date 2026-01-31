# Unified Type Registry - Implementation Plan

## Reference Documents

- Design: [DESIGN.md](../DESIGN.md)
- Architecture: [ARCHITECTURE.md](../ARCHITECTURE.md)
- Audit: [AUDIT.md](../AUDIT.md)

## Milestone Summary

| # | Name | Tasks | E2E Test | Status |
|---|------|-------|----------|--------|
| M1 | Registry Foundation | 6 | Registry pattern proof with RSI | ⏳ |
| M2 | All Indicators | 9 | 39 indicators + file deletion | ⏳ |
| M3 | Fuzzy System | 7 | Fuzzy registry + v2 deletion | ⏳ |
| M4 | Cleanup | 6 | Grep checks + runtime validation | ⏳ |
| M5 | Documentation | 3 | Skills file updates | ⏳ |

**Total: 31 tasks**

## Dependency Graph

```
M1 (foundation)
 ├──► M2 (all indicators) ──┬──► M4 (cleanup)
 │                          │
 └──► M3 (fuzzy) ───────────┘
                            │
                            ▼
                          M5 (docs)
```

M2 and M3 can run in parallel after M1 completes.

## Architecture Alignment

### Core Patterns

| Pattern | Description | Implementing Tasks |
|---------|-------------|-------------------|
| `TypeRegistry[T]` | Generic registry with case-insensitive lookup | 1.1 |
| `__init_subclass__` | Auto-registration on class definition | 1.2, 3.1 |
| `Params` nested class | Pydantic model for parameter validation | 1.3, 2.1-2.5, 3.2 |
| DataError wrapping | Consistent exception interface | 1.2 |
| V2 deletion | Complete removal, no backward compat | 3.3-3.5 |

### Key Decisions (from validation)

1. **Constructor pattern**: `__init__(**kwargs)` — Params is single source of truth
2. **Exception wrapping**: Pydantic ValidationError → DataError (indicators) / ConfigurationError (fuzzy)
3. **Abstract detection**: `inspect.isabstract(cls)`
4. **Test class detection**: `module.startswith("tests.")` or `".tests." in module`
5. **Name collision**: Fail fast with ValueError
6. **MF params**: Keep `parameters: list[float]` for YAML consistency

### What We Will NOT Do

- Keep both explicit `__init__` params AND Params class (duplication)
- Let Pydantic ValidationError propagate (inconsistent interface)
- Support v2 fuzzy config in any form (dead code)
- Use module scanning or decorators (explicit is better)

## Files to Create

| File | Milestone | Purpose |
|------|-----------|---------|
| `ktrdr/core/type_registry.py` | M1 | Generic TypeRegistry class |
| `tests/unit/core/test_type_registry.py` | M1 | Registry unit tests |
| `tests/unit/indicators/test_registry_rsi_validation.py` | M1 | RSI registration tests |
| `tests/unit/indicators/test_registry_migration_complete.py` | M2 | Full migration tests |
| `tests/unit/fuzzy/test_fuzzy_migration_complete.py` | M3 | Fuzzy migration tests |

## Files to Delete

| File | Milestone | Blocked By |
|------|-----------|------------|
| `ktrdr/indicators/indicator_factory.py` | M2 | All consumers migrated |
| `ktrdr/indicators/schemas.py` | M2 | All Params classes added |
| `ktrdr/fuzzy/config.py` | M3 | V2 code removed |
| `ktrdr/fuzzy/migration.py` | M3 | V2 code removed |

## Files to Modify

| File | Milestone | Changes |
|------|-----------|---------|
| `ktrdr/indicators/base_indicator.py` | M1 | Add `__init_subclass__`, INDICATOR_REGISTRY |
| `ktrdr/indicators/rsi_indicator.py` | M1 | Add Params class |
| `ktrdr/indicators/indicator_engine.py` | M1, M2 | Use registry (with fallback in M1, remove in M2) |
| All 38 remaining indicator files | M2 | Add Params class |
| `ktrdr/config/strategy_validator.py` | M2 | Use INDICATOR_REGISTRY |
| `ktrdr/fuzzy/membership.py` | M3 | Add `__init_subclass__`, MEMBERSHIP_REGISTRY |
| `ktrdr/fuzzy/engine.py` | M3 | Remove v2, use registry |
| 8 indicator files with ValueError | M4 | Exception cleanup |
| `.claude/skills/technical-indicators/SKILL.md` | M5 | Update patterns |
| `.claude/skills/fuzzy-logic-engine/SKILL.md` | M5 | Remove v2, add registry |
