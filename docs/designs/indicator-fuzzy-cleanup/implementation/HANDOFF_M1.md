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

---

## Task 1.3 Complete: Add Params to RSIIndicator

### Implementation Notes

- Added `Params(BaseIndicator.Params)` with `period` and `source` fields
- Used `strict=True` on Fields to prevent Pydantic type coercion (e.g., "14" → 14)
- Removed `__init__` and `_validate_params` methods (BaseIndicator handles validation)
- Added `display_as_overlay = False` as class attribute

### Gotchas

**Mypy and pd.Series type inference**: Adding a `Params` class can confuse mypy about local variable types. Fix by adding explicit type annotations:
```python
gain: pd.Series = delta.copy()  # Explicit annotation fixes mypy
```

**display_as_overlay class attribute**: BaseIndicator.__init__ checks `"display_as_overlay" in self.__class__.__dict__` to respect subclass overrides. Define it as a class attribute in indicators that need non-default values.

**Backward compatible access**: Both patterns work:
- `self.period` (new style, direct attribute)
- `self.params["period"]` (old style, dict access)

---

## Task 1.4 Complete: Update IndicatorEngine with registry fallback

### Implementation Notes

- Modified `_create_indicator()` in `indicator_engine.py` to try `INDICATOR_REGISTRY.get()` first
- Falls back to `BUILT_IN_INDICATORS.get()` for non-migrated indicators
- Error messages combine available types from both registry and fallback

### Key Pattern

```python
# Try registry first, then fallback
indicator_class = INDICATOR_REGISTRY.get(definition.type)
if indicator_class is None:
    indicator_class = BUILT_IN_INDICATORS.get(definition.type.lower())
```

---

## Task 1.5 Complete: Update `__init__.py` exports

### Implementation Notes

- Added `INDICATOR_REGISTRY` to import from `base_indicator`
- Added `INDICATOR_REGISTRY` to `__all__` list
- Now `from ktrdr.indicators import INDICATOR_REGISTRY` works

---

## Task 1.6 Complete: M1 E2E Validation

### Validation Results

All E2E success criteria passed:
- ✓ INDICATOR_REGISTRY exists with get, list_types, get_params_schema methods
- ✓ 'rsi' in list_types()
- ✓ All case variants (RSI, rsi, RSIIndicator, rsiindicator) resolve to RSIIndicator
- ✓ get_params_schema('rsi') returns Pydantic model with period, source fields
- ✓ RSI() with defaults creates instance with period=14, source='close'
- ✓ RSI(period=-1) raises DataError with error_code
- ✓ IndicatorEngine creates RSI for all type name variants
- ✓ Engine.compute() produces valid RSI column

### Quality Gates

- ✓ `make test-unit` — 4513 passed
- ✓ `make quality` — All checks passed

---

## M1 Complete: Registry Foundation

**Summary:** TypeRegistry pattern proven end-to-end with RSI indicator.

**Key deliverables:**
1. `TypeRegistry[T]` generic class in `ktrdr/core/type_registry.py`
2. `INDICATOR_REGISTRY` with auto-registration via `__init_subclass__`
3. RSI migrated to Params-based validation
4. IndicatorEngine uses registry-first lookup
5. Package exports INDICATOR_REGISTRY

**Ready for M2:** Migrate remaining indicators to Params pattern.
