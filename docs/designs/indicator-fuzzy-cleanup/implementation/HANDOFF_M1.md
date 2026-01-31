# Milestone 1 Handoff: Registry Foundation

## Task 1.1 Complete: Create TypeRegistry generic class

### Implementation Notes

- Created `ktrdr/core/` as new module with `TypeRegistry` generic class
- All names stored lowercase internally for case-insensitive lookup
- Canonical names tracked separately from aliases in `_canonical` set
- `get_params_schema()` uses `getattr(cls, "Params", None)` — safe for classes without Params

---

## Task 1.2 Complete: Add `__init_subclass__` to BaseIndicator

### Implementation Notes

- Added `INDICATOR_REGISTRY` at module level before class definition
- Added `Params(BaseModel)` nested class for Pydantic validation
- Added `_aliases: list[str] = []` class attribute for optional aliases
- Added `__init_subclass__` with auto-registration (skips abstract/test classes)

### Gotchas

**Test class module detection**: Pytest rewrites test modules, so `__module__` can be just `test_foo` instead of `tests.unit.foo.test_foo`. The check now handles:
- `tests.` prefix
- `.tests.` in path
- `test_` prefix
- `_test` in name

**Pydantic model_fields deprecation**: Access `model_fields` from the class, not the instance:
```python
# Wrong (deprecated)
for field in validated.model_fields:

# Correct
for field in self.__class__.Params.model_fields:
```

**Backward compatibility**: The new `__init__` supports both patterns:
- Old style: `super().__init__(name="RSI", period=14)` — uses `_validate_params`
- New style: `MyIndicator(period=14)` — uses `Params` validation, derives name from class

### Next Task Notes (1.3)

Task 1.3 adds Params to RSIIndicator. Key changes:
- Add `class Params(BaseIndicator.Params)` with `period` and `source` fields
- Remove explicit `__init__` (inherited from BaseIndicator handles it)
- Keep `compute()` unchanged — it can access `self.period` directly now
