# Handoff: M6 — External Data FRED Training

## Task 6.1 Complete: FRED API Key Setup and Validation

**What was done:**
- Added `FredSettings` class to `ktrdr/config/settings.py` with `KTRDR_FRED_` prefix
- Fields: `api_key`, `base_url`, `rate_limit` (gt=0), `cache_dir`
- `has_api_key` computed field for checking key availability without exposing value
- `deprecated_field()` pattern for `FRED_API_KEY` → `KTRDR_FRED_API_KEY` migration
- Added `get_fred_settings()` cached getter, wired into `clear_settings_cache()`
- Exported from `ktrdr/config/__init__.py`
- Documented in `.env.example`

**Emergent patterns:**
- API key defaults to empty string (not required at load time) — validated at point of use in FRED provider
- `has_api_key` computed property avoids exposing key value in boolean checks

**Next task notes (6.2):**
- Import `get_fred_settings` from `ktrdr.config` when FRED provider needs settings
- `cache_dir` defaults to `data/context/fred` — provider should use this for local caching

## Task 6.2 Complete: Context Data Provider Interface and Registry

**What was done:**
- Created `ktrdr/data/context/` package with `base.py` and `registry.py`
- `ContextDataProvider` ABC with `fetch()`, `validate()`, `get_source_ids()`
- `ContextDataResult` dataclass (source_id, data, frequency, provider, metadata)
- `ContextDataAligner.align()` handles reindex + ffill + dropna for daily/weekly→hourly
- `ContextDataProviderRegistry` maps names to classes, instantiates on `get()`

**Emergent patterns:**
- Used `dataclass` for `ContextDataResult` (not Pydantic) since it holds a DataFrame
- `config` parameter typed as `Any` in ABC — concrete providers will use `ContextDataEntry` from Task 6.4
- Aligner drops leading NaNs before first context observation (handles context data starting after primary)

**Next task notes (6.3):**
- `FredDataProvider` implements `ContextDataProvider` — import from `ktrdr.data.context.base`
- Use `get_fred_settings()` for API key, base_url, cache_dir
- Register with `ContextDataProviderRegistry` after implementation

## Task 6.3 Complete: FRED Provider Implementation

**What was done:**
- `FredDataProvider` in `ktrdr/data/context/fred_provider.py`
- Fetches via httpx async, parses FRED JSON, handles "." as NaN + ffill
- CSV caching with metadata.json tracking date ranges for cache hits
- Spread computation: `series[0] - series[1]` for multi-series configs
- Tests mock `_fetch_series` (internal HTTP method) for clean unit testing

**Gotchas:**
- FRED returns `value` as string — must convert to float, "." → NaN
- Cache check compares requested date range against stored range for cache hits

## Task 6.4 Complete: Grammar Extension — context_data and data_source

**What was done:**
- Added `ContextDataEntry` model to `ktrdr/config/models.py` with all provider-specific fields
- Added `context_data: Optional[list[ContextDataEntry]]` to `StrategyConfigurationV3`
- Added `_validate_data_source_references()` to `strategy_validator.py`
- Validation checks: data_source → context_data source ID resolution, unused context_data warnings

**Gotchas:**
- `IndicatorDefinition` uses `extra="allow"` — `data_source` lives in `model_extra`, not as a declared field
- Test fixture with `output_format: regression` fails without `cost_model` — use classification for simpler tests
- `_validate_data_source_references` imports FredDataProvider lazily to compute source IDs from config

**Next task notes (6.5):**
- `indicator_def.model_extra.get("data_source")` is how to extract data_source from an indicator
- IndicatorEngine needs `context_data: Optional[dict[str, pd.DataFrame]]` parameter

## Task 6.5 Complete: IndicatorEngine Context Data Routing

**What was done:**
- Added `_data_sources: dict[str, str]` to `IndicatorEngine.__init__()` — maps indicator_id to data_source key
- Extracts `data_source` from `IndicatorDefinition.model_extra` during init
- Added `context_data: Optional[dict[str, pd.DataFrame]]` param to `compute()` and `apply()`
- `compute()` routes indicators with `data_source` to the context DataFrame, raises `KeyError` if missing
- `apply()` passes `context_data` through to `compute()`

**Emergent patterns:**
- No need to store full `IndicatorDefinition` objects — just extract and store the `data_source` mapping at init time
- `_create_indicator()` already filters `data_source` out of params (it's not in any indicator's Params class), so no change needed there

**Next task notes (6.6):**
- `IndicatorEngine.compute()` and `apply()` now accept `context_data` — training pipeline needs to pass it
- Context data keys must match the `data_source` values in indicator definitions (e.g., `yield_spread_DGS2_IRLTLT01DEM156N`)

## Task 6.6 Complete: Training Pipeline Context Data Loading

**What was done:**
- Added `context_data` param to `compute_for_timeframe()` in indicator_engine.py (passthrough to `compute()`)
- Added `context_data` param to `TrainingPipelineV3.prepare_features()` — passes through to `compute_for_timeframe()`
- Added `_load_context_data()` async method to both local_orchestrator.py and training-host-service/orchestrator.py (DUAL DISPATCH)
- Both orchestrators use `asyncio.run()` to call async context loading from sync `_execute_v3_training()`
- Updated `_save_v3_metadata()` in both orchestrators to serialize context_data_config and context_source_ids
- Added `context_data_config` and `context_source_ids` fields to `ModelMetadata` with full roundtrip (to_dict/from_dict)

**Gotchas:**
- `_execute_v3_training()` is sync in both orchestrators — context data loading (async) needs `asyncio.run()`
- training-host-service/orchestrator.py doesn't import pandas — use `dict[str, Any]` for type hints
- `pytest.importorskip("torch")` at module level skips ALL tests in file — use `try/except` + `@skipif` instead

**Next task notes (6.7):**
- All infrastructure is ready for E2E validation
- Needs real FRED API key for live test
- Strategy must declare `context_data` with FRED provider and indicators with `data_source`

## Task 6.7 Partial: Validation

**What was done:**
- E2E test designed and added to catalog: `.claude/skills/ke2e/tests/training/fred-context-data.md`
- 8-step test covering: strategy creation, training start, completion poll, metadata verification, feature count, FRED cache check
- Full unit test suite passes: 5328 passed, 41 skipped

**E2E validation (5 steps, all PASSED):**
1. FRED API key loaded from 1Password
2. Real FRED fetch: DGS2 (370 rows) + IRLTLT01DEM156N (18 rows) → spread (13 rows)
3. Alignment: 13 daily → 11,665 hourly rows via forward-fill
4. Indicator routing: price RSI=49.7 vs yield RSI=65.9 (confirms different data sources)
5. ModelMetadata roundtrip: 3 source IDs preserved through to_dict/from_dict

**Bug found during E2E:**
- FRED provider returned `value` column but indicators expect `close`
- Fixed: `_parse_observations()` now renames `value` → `close` at source
- Stale cache with old column names caused KeyError — cleared cache resolved it
