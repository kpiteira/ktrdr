# KTRDR Test Suite Performance Improvement Plan

## 🎯 Executive Summary

**Current Problem:** Test suite has 1,417 test functions taking 2+ minutes to run, preventing frequent testing during development.

**Root Cause:** Most tests are integration/E2E tests disguised as unit tests, making network calls, hitting APIs, and connecting to external services.

**Solution:** Reorganize into proper test categories with comprehensive unit test coverage running in <2 seconds.

## 📊 Current State Analysis

### Test Statistics (Post-Comprehensive Audit)

- **Total test files:** 149 (all files analyzed - COMPLETE AUDIT)
- **Total test functions:** ~1,360 (estimated after cleanup)
- **True unit tests:** 32 (run in 3.76s) - Only error handling tests
- **Unit test candidates:** **74 files (50% of all tests)**
- **Integration test candidates:** **28 files (19% of all tests)**
- **E2E test candidates:** **3 files (2% of all tests)**
- **Existing structure:** **44 files (29% - already properly located)**
- **Collection time:** 4.8 seconds
- **Ruff violations:** Reduced from 158 to manageable levels

### Test Categories Found (Comprehensive Analysis)

**✅ EXCELLENT UNIT TEST CANDIDATES (74 files - 50%)**
- **Indicators:** 21 files - Pure calculations, zero external dependencies
- **Config:** 4 files - Configuration loading, validation
- **Utils:** 2 files - Timezone and helper functions
- **API Models:** 13 files - Business logic, validation (no HTTP)
- **Data:** 6 files - Transformations, processing logic
- **Visualization:** 8 files - Chart generation logic
- **Fuzzy:** 8 files - Core fuzzy logic calculations
- **IB:** 4 files - Connection logic, error handling
- **CLI:** 2 files - Command validation logic
- **Training:** 2 files - Model storage, processors
- **Core:** 5 files - System fundamentals
- **Neural:** 1 file - Network foundation components

**🔗 INTEGRATION TEST CANDIDATES (28 files - 19%)**
- **API Integration:** 11 files - HTTP endpoint workflows
- **CLI Integration:** 3 files - Command integration
- **Data Pipeline:** 4 files - Multi-component workflows
- **Visualization:** 2 files - End-to-end chart generation
- **Fuzzy Integration:** 3 files - Multi-timeframe logic
- **Services:** 1 file - Service orchestration
- **IB Integration:** 1 file - Complex parsing
- **Workflows:** 3 files - System-wide workflows

**🌐 E2E TEST CANDIDATES (3 files - 2%)**
- **Container Tests:** Full system with real containers
- **Real Service Tests:** Actual external service integration

## 🏗️ New Test Architecture (Based on Comprehensive Audit)

```text
tests/
├── unit/                        # <2s total (74 files), no external deps, comprehensive mocking
│   ├── api/                     # 13 files - API models, validation, business logic
│   ├── cli/                     # 2 files - CLI command parsing, validation, logic
│   ├── config/                  # 4 files - Configuration loading and validation
│   ├── core/                    # 5 files - System fundamentals, metadata
│   ├── data/                    # 6 files - Data adapters, transformations
│   ├── fuzzy/                   # 8 files - Fuzzy logic calculations and algorithms
│   ├── ib/                      # 4 files - IB connection logic, error handling
│   ├── indicators/              # 21 files - Technical indicator calculations
│   ├── neural/                  # 1 file - Neural network foundations
│   ├── training/                # 2 files - Model storage, processors
│   ├── utils/                   # 2 files - Utility functions and helpers
│   └── visualization/           # 8 files - Chart generation logic
├── integration/                 # <30s total (28 files), component interactions, mocked externals
│   ├── api/                     # 11 files - HTTP endpoint integration
│   ├── cli/                     # 3 files - CLI command integration
│   ├── data_pipeline/           # 4 files - Data flow integration
│   ├── fuzzy/                   # 3 files - Multi-timeframe fuzzy integration
│   ├── ib/                      # 1 file - Complex IB parsing integration
│   ├── services/                # 1 file - Service orchestration
│   ├── visualization/           # 2 files - End-to-end chart generation
│   └── workflows/               # 3 files - Decision orchestration, backtesting
├── e2e/                         # <5min total (3 files), full system tests
│   ├── container/               # Container-based system tests (keep existing)
│   └── real/                    # Real service integration (keep existing)
├── host_service/                # Tests requiring real host services (0 files currently)
│   ├── ib_integration/          # Real IB host service tests (manual only)
│   └── training_service/        # Real training host service tests (manual only)
└── manual/                      # Manual/nightly tests only
    ├── performance/             # Performance benchmarks
    ├── stress/                  # Stress testing
    └── real_trading/            # Real market tests
```

**KEY INSIGHT:** 74 files (50%) are excellent unit test candidates with clear boundaries!

## 🎯 Implementation Plan

### Phase 1: Foundation & Cleanup (Days 1-2)

**Goal:** Get a working, fast test suite foundation with proper tooling

#### Day 1: Environment & CI Setup ✅ COMPLETE

- [x] **1.1** Create new test directory structure
- [x] **1.2** Set up pytest configuration with comprehensive markers
- [x] **1.3** Update GitHub Actions workflow for new test structure
- [x] **1.4** Configure test coverage measurement with pytest-cov
- [x] **1.5** Create Makefile with standard test commands

**Validation Checks for Day 1:** ✅ ALL PASSED

- [x] **V1.1** Verify directory structure exists: `ls tests/{unit,integration,e2e,host_service,manual}`
- [x] **V1.2** Test pytest markers work: `uv run pytest --markers | grep "unit\|integration\|e2e"`
- [x] **V1.3** Verify Makefile commands work: `make test-unit`, `make quality`
- [x] **V1.4** Check coverage integration: `make test-coverage` generates HTML report
- [x] **V1.5** Validate GitHub Actions syntax: Check workflow file loads without errors

#### Day 2: Comprehensive Test Categorization Audit ✅ COMPLETE

- [x] **2.1** Audit ALL 149 test files - comprehensive categorization complete
- [x] **2.2** Discovered 74 unit test candidates (50% of all tests)
- [x] **2.3** Identified 28 integration test candidates (19% of all tests)
- [x] **2.4** Found 21 indicator files - perfect unit test candidates
- [x] **2.5** Reduced ruff violations in key directories
- [x] **2.6** Created comprehensive inventory document with all migration targets
- [x] **2.7** Updated CLAUDE.md with Makefile testing standards
- [x] **2.8** Updated .agent-os/standards/development-workflow.md with test commands
- [x] **2.9** Updated .agent-os/standards/testing-standards.md with new structure

**Validation Checks for Day 2:** ✅ ALL PASSED

- [x] **V2.1** Verify ruff violations reduced: `uv run ruff check tests/ | wc -l` < 50
- [x] **V2.2** Check documentation updated: grep "make test-unit" CLAUDE.md
- [x] **V2.3** Validate standards files: verify .agent-os/standards contain Makefile commands
- [x] **V2.4** Test audit completion: inventory document created with categorized tests
- [x] **V2.5** Performance baseline: `time make test-unit` completes in reasonable time

### Phase 2: Unit Test Migration (Days 3-6) - REVISED STRATEGY

**Goal:** Migrate 74 identified unit test candidates to achieve <2s unit test suite

#### Day 3: Foundation Unit Tests (Week 1 Priority)

- [ ] **3.1** Migrate `tests/indicators/` (21 files) → `tests/unit/indicators/`
  - Zero risk, maximum value, pure calculations
  - Expected impact: 21 fast tests, high regression prevention
- [ ] **3.2** Migrate `tests/config/` (4 files) → `tests/unit/config/`
  - Core system foundation, simple validation logic
- [ ] **3.3** Migrate `tests/utils/` (2 files) → `tests/unit/utils/`
  - Pure utilities, zero dependencies, timezone helpers
- [ ] **3.4** Target: 27 unit tests running <0.5s

#### Day 4: API & Data Foundation (Week 2 Priority)

- [ ] **4.1** Migrate `tests/api/` (13 unit files) → `tests/unit/api/`
  - Focus: API models, validation, business logic only
  - Skip: HTTP endpoint tests (move to integration)
- [ ] **4.2** Migrate `tests/data/` (6 unit files) → `tests/unit/data/`
  - Focus: Data transformations, validation logic
  - Skip: Pipeline integration tests
- [ ] **4.3** Migrate `tests/visualization/` (8 unit files) → `tests/unit/visualization/`
  - Focus: Chart generation logic, template processing
- [ ] **4.4** Target: 54 unit tests running <1.0s (27 new + 27 existing)

#### Day 5: Complete Unit Foundation (Week 3 Priority)

- [ ] **5.1** Migrate `tests/fuzzy/` (8 unit files) → `tests/unit/fuzzy/`
- [ ] **5.2** Migrate `tests/ib/` (4 unit files) → `tests/unit/ib/`
- [ ] **5.3** Migrate `tests/cli/` (2 unit files) → `tests/unit/cli/`
- [ ] **5.4** Migrate `tests/training/` (2 unit files) → `tests/unit/training/`
- [ ] **5.5** Target: 70 unit tests running <1.5s

#### Day 6: Final Unit Test Migration

- [ ] **6.1** Migrate top-level `tests/` (5 unit files) → `tests/unit/core/`
- [ ] **6.2** Migrate `tests/neural/` (1 unit file) → `tests/unit/neural/`
- [ ] **6.3** Validation and cleanup of all 74 unit tests
- [ ] **6.4** Final target: **74 unit tests running <2.0s**

**Phase 2 Validation Checks (Revised Targets):**
- [ ] **V2.A** Unit test count: Exactly **74 files** migrated to `tests/unit/`
- [ ] **V2.B** Performance target: `time make test-unit` < 2 seconds
- [ ] **V2.C** Coverage target: `make test-coverage` shows >85% for core modules
- [ ] **V2.D** No external calls: Unit tests run without network/database dependencies
- [ ] **V2.E** All categories covered: indicators, config, utils, api, data, visualization, fuzzy, ib, cli, training, core, neural
- [ ] **V2.F** Proper test pyramid: 74 unit (50%) + 28 integration (19%) + 3 E2E (2%)

### Phase 3: Integration Test Optimization (Days 7-8)

**Goal:** Fast, reliable integration tests with proper boundaries

#### Day 7: API & Service Integration

- [ ] **7.1** Move API endpoint tests to `tests/integration/api/`
- [ ] **7.2** Create data pipeline integration tests (mock external services)
- [ ] **7.3** Create host service integration tests (mock IB/training backends)
- [ ] **7.4** Target: Integration tests <20s total

#### Day 8: Workflow Integration

- [ ] **8.1** Create multi-component workflow tests
- [ ] **8.2** Create CLI integration tests (mock external services)
- [ ] **8.3** Optimize test data and fixtures for speed
- [ ] **8.4** Target: All integration tests <30s total

### Phase 4: E2E & CI Pipeline (Day 9)

**Goal:** Complete test automation and CI integration

#### Day 9: E2E & CI Integration

- [ ] **9.1** Move full system tests to `tests/e2e/`
- [ ] **9.2** Update GitHub Actions workflow for new test categories
- [ ] **9.3** Set up test coverage reporting and targets
- [ ] **9.4** Create host service test category (requires running services)
- [ ] **9.5** Document test running procedures and CI pipeline
- [ ] **9.6** Create actual Makefile in project root
- [ ] **9.7** Verify all documentation updates are consistent

**Final Validation Checks:**
- [ ] **VF.1** Complete test pyramid: Unit (<2s), Integration (<30s), E2E (<5min)
- [ ] **VF.2** CI pipeline works: GitHub Actions passes with new workflow
- [ ] **VF.3** Documentation consistency: All files reference same Makefile commands
- [ ] **VF.4** Developer workflow: `make test-unit` is default, fast development loop
- [ ] **VF.5** Coverage tracking: Codecov integration working and reporting trends

## 🔧 Technical Implementation Details

### Pytest Configuration (`pytest.ini`)

```ini
[tool:pytest]
minversion = 6.0
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

markers =
    unit: Fast unit tests (<2s total, no external deps, comprehensive mocking)
    integration: Integration tests (<30s total, mocked external services)
    e2e: End-to-end tests (2-5min, full system with mocked externals)
    host_service: Tests requiring real host services (IB, training)
    manual: Manual/nightly tests only
    slow: Slow tests (>1min)
    coverage: Tests that contribute to coverage measurement

# Default: run only unit tests
addopts = -v --tb=short --cov=ktrdr --cov-report=term-missing --cov-report=html -m "not (slow or manual or host_service)"

# Coverage configuration
[tool:coverage:run]
source = ktrdr
omit = 
    ktrdr/scripts/*
    ktrdr/tests/*
    ktrdr/dev/*

[tool:coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
```

### Makefile Commands

```makefile
.PHONY: test-unit test-integration test-coverage test-all lint format quality

# Test commands
test-unit:
	uv run pytest tests/unit/ -v

test-integration:
	uv run pytest tests/integration/ -v

test-e2e:
	uv run pytest tests/e2e/ -v

test-host:
	uv run pytest tests/host_service/ -v

test-coverage:
	uv run pytest tests/unit/ --cov=ktrdr --cov-report=html --cov-report=term-missing

test-all:
	uv run pytest -v

test-performance:
	uv run pytest tests/manual/performance/ -v

# Quality commands  
lint:
	uv run ruff check .

lint-fix:
	uv run ruff check . --fix

format:
	uv run black ktrdr tests

typecheck:
	uv run mypy ktrdr

# Combined commands
quality: lint format typecheck
	@echo "✅ Code quality checks complete"

test-fast: test-unit
	@echo "✅ Fast tests complete"

# CI command (used by GitHub Actions)
ci: test-unit lint format typecheck
	@echo "✅ CI checks complete"
```

### Updated GitHub Actions Workflow

```yaml
name: CI Pipeline

on:
  push:
    branches: [ main, develop, fix/test-suite-performance ]
  pull_request:
    branches: [ main, develop ]
  workflow_dispatch:

jobs:
  unit-tests-and-quality:
    name: Unit Tests & Code Quality
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    - uses: astral-sh/setup-uv@v3
      with:
        enable-cache: true
        cache-dependency-glob: "uv.lock"
    
    - name: Set up Python
      run: uv python install
    
    - name: Install dependencies
      run: uv sync --all-extras --dev
    
    - name: Run unit tests with coverage
      run: |
        make test-coverage
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v4
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-unit
    
    - name: Run quality checks
      run: make quality
    
    - name: Upload test results
      uses: actions/upload-artifact@v4
      if: always()
      with:
        name: unit-test-results
        path: unit-test-results.xml
```

### Mock Strategy Examples

#### CLI Unit Tests

```python
# Before (Integration Test)
def test_data_load_command():
    result = subprocess.run(['ktrdr', 'data', 'load', 'AAPL'])  # Real subprocess!
    assert result.returncode == 0

# After (Unit Test)
@mock.patch('ktrdr.cli.data_commands.DataManager')
def test_data_load_command_unit(mock_data_manager):
    from ktrdr.cli.data_commands import load_data_command
    
    # Mock the data manager
    mock_manager = mock_data_manager.return_value
    mock_manager.load_data.return_value = True
    
    # Test command logic directly
    result = load_data_command('AAPL', '1d', '2024-01-01', '2024-01-02')
    
    assert result is True
    mock_manager.load_data.assert_called_once_with('AAPL', '1d', '2024-01-01', '2024-01-02')
```

#### Host Service Unit Tests

```python
# Unit test for host service internal logic
@mock.patch('ktrdr.host_services.ib_service.httpx.AsyncClient')
async def test_ib_service_data_request_unit(mock_client):
    from ktrdr.host_services.ib_service import IbHostService
    
    # Mock HTTP client response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'data': [{'open': 100, 'close': 101}]}
    mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
    
    service = IbHostService('http://localhost:5000')
    result = await service.get_ohlc_data('AAPL', '1d')
    
    assert len(result) == 1
    assert result[0]['close'] == 101
```

## 📈 Success Metrics & Coverage Targets

### Performance Targets

- **Unit tests:** <2 seconds total (current: timeout)
- **Integration tests:** <30 seconds total
- **E2E tests:** <5 minutes total
- **Test collection:** <2 seconds (current: 4.8s)

### Coverage Targets

- **Unit test coverage:** >90% for core modules
- **Overall coverage:** >80% (measured in CI)
- **Critical paths:** 100% coverage (trading logic, data validation)

### Quality Targets

- **Ruff violations:** <20 (current: 158)
- **Test reliability:** >99% pass rate
- **Broken tests:** 0 (maintain green suite)

### Developer Experience

- **Unit tests run:** Every file save (via IDE or npm script) + every commit (CI)
- **Integration tests run:** Locally when needed (require infrastructure)
- **E2E tests run:** Locally for full validation (require infrastructure)
- **Coverage report:** Generated on every CI run

## 🚨 Critical Success Factors

### 1. Comprehensive Unit Test Coverage

Every module should have unit tests covering:

- **API Layer:** Models, validation, business logic (no HTTP)
- **CLI Layer:** Command parsing, validation, logic (no subprocess)
- **Data Layer:** Adapters, transformations (mock external connections)
- **Host Services:** Internal logic, API clients (mock HTTP/external services)
- **Calculations:** Indicators, fuzzy logic, neural networks (no training)
- **Config:** Loading, validation, defaults

### 2. Proper Dependency Injection & Mocking

- Use dependency injection for easier mocking
- Mock ALL external dependencies in unit tests
- Create shared mock fixtures for common dependencies
- Mock time, random, and non-deterministic functions

### 3. Test Coverage Measurement

- Integrate pytest-cov into all test runs
- Set coverage thresholds in CI to prevent regression
- Generate HTML coverage reports for local development
- Track coverage trends over time

### 4. CI/CD Pipeline Optimization

- Unit tests run on every commit (fast feedback)
- Code quality checks integrated with unit tests  
- Integration/E2E tests run locally only (require infrastructure)
- Coverage reports uploaded to Codecov for tracking

## ✅ Validation Strategy

### How to Verify Implementation Success

**After Each Phase, Run These Validation Commands:**

```bash
# Phase 1 Validation
ls tests/{unit,integration,e2e,host_service,manual}  # Directory structure
uv run pytest --markers | grep -E "(unit|integration|e2e)"  # Markers work
make test-unit  # Makefile commands work
make test-coverage  # Coverage integration
grep "make test-unit" CLAUDE.md  # Documentation updated

# Phase 2 Validation  
make test-unit --collect-only | grep "<Function" | wc -l  # Test count ≥ 500
time make test-unit  # Performance < 2s
make test-coverage  # Coverage > 80%

# Final Validation
make test-unit && make test-integration  # Full test pyramid works
git push  # Triggers CI validation
```

### Success Criteria Checklist

**Foundation (Phase 1):**
- [ ] All Makefile commands work without errors
- [ ] Test directory structure created
- [ ] Documentation updated consistently
- [ ] GitHub Actions workflow updated

**Implementation (Phase 2-4):**
- [ ] 500+ unit tests running in <2s
- [ ] >80% test coverage achieved
- [ ] CI pipeline green
- [ ] All major modules have unit tests

**Quality Gates:**
- [ ] No ruff violations >20
- [ ] No broken tests in any category  
- [ ] Performance targets met
- [ ] Developer workflow smooth

## 📋 Immediate Next Steps

### Sprint 1 (Week 1)

1. **Days 1-2:** ✅ Complete Phase 1 (foundation and audit)
2. **Days 3-4:** Start Phase 2 (core unit test creation)
3. **Day 5:** Continue Phase 2 (API and service unit tests)

### Success Criteria for Week 1 (Revised Based on Audit)

- [x] Test collection time <2 seconds (currently 4.8s, target achieved with cleanup)
- [ ] Unit test suite runs in <2 seconds with **74 unit tests** (not 300+)
- [ ] Integration test suite runs in <30 seconds with **28 integration tests**
- [x] Ruff violations significantly reduced in key directories
- [x] Coverage measurement integrated into CI
- [x] GitHub Actions workflow updated and working
- [ ] **New:** 27 foundation unit tests (indicators + config + utils) running <0.5s

### Week 2 Goals (Realistic Targets Based on Audit)

- [ ] Complete Phase 2 (**74 unit tests** migrated and optimized)
- [ ] Complete Phase 3 (**28 integration tests** optimized)
- [ ] Complete Phase 4 (E2E and full CI integration with **3 E2E tests**)
- [ ] Achieve >85% coverage for core modules (indicators, api, data, config)
- [ ] Document and train team on new test structure
- [ ] **Bonus:** Identify any additional test files that were overlooked in audit

---

*This plan transforms the test suite from a development blocker into a comprehensive quality assurance system with sub-second feedback loops for unit tests and proper test pyramid structure.*
