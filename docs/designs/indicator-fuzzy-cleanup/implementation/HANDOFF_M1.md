# Milestone 1 Handoff: Registry Foundation

## Task 1.1 Complete: Create TypeRegistry generic class

### Implementation Notes

- Created `ktrdr/core/` as new module with `TypeRegistry` generic class
- All names stored lowercase internally for case-insensitive lookup
- Canonical names tracked separately from aliases in `_canonical` set
- `get_params_schema()` uses `getattr(cls, "Params", None)` — safe for classes without Params

### Next Task Notes (1.2)

Task 1.2 adds `__init_subclass__` to `BaseIndicator`. Key imports needed:
```python
from ktrdr.core.type_registry import TypeRegistry
```

The registry instance should be created at module level:
```python
INDICATOR_REGISTRY: TypeRegistry["BaseIndicator"] = TypeRegistry("indicator")
```

Watch for circular imports — the registry module has no dependencies, so importing it from `base_indicator.py` is safe.
