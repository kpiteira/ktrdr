# KTRDR Test Suite Performance Improvement Plan

## 🎯 Executive Summary

**Current Problem:** Test suite has 1,417 test functions taking 2+ minutes to run, preventing frequent testing during development.

**Root Cause:** Most tests are integration/E2E tests disguised as unit tests, making network calls, hitting APIs, and connecting to external services.

**Solution:** Reorganize into proper test categories with comprehensive unit test coverage running in <2 seconds.

## 📊 Current State Analysis

### Test Statistics (Post-Cleanup)

- **Total test files:** 149 (removed 2 obsolete files)
- **Total test functions:** ~1,360 (after cleanup)
- **True unit tests:** 32 (run in 0.47s)
- **Collection time:** 4.8 seconds
- **Ruff violations:** 158 (down from 216, no more F821 errors)

### Test Categories Found

1. **True Unit Tests:** `tests/unit/` (32 tests, 0.47s) ✅
2. **API Integration:** `tests/api/` - HTTP requests to services
3. **IB Integration:** Various IB connection tests (many obsolete)
4. **Training/ML Tests:** Model training, GPU operations
5. **Database Tests:** Real database operations
6. **File System Tests:** Heavy file I/O operations
7. **Network Tests:** HTTP/WebSocket connections

## 🏗️ New Test Architecture

```text
tests/
├── unit/                        # <2s total, no external deps, comprehensive mocking
│   ├── api/                     # API models, validation, business logic
│   ├── cli/                     # CLI command parsing, validation, logic
│   ├── config/                  # Configuration loading and validation
│   ├── data/                    # Data adapters, managers, transformations
│   ├── fuzzy/                   # Fuzzy logic calculations and algorithms
│   ├── host_services/           # Host service internal logic (mocked externals)
│   ├── indicators/              # Technical indicator calculations
│   ├── neural/                  # Neural network model logic (no training)
│   └── utils/                   # Utility functions and helpers
├── integration/                 # 10-30s, component interactions, mocked externals
│   ├── api/                     # API service integration tests
│   ├── data_pipeline/           # Data flow integration tests
│   ├── host_services/           # Host service API integration (mocked backends)
│   └── workflows/               # Multi-component workflows
├── e2e/                         # 2-5min, full system tests with mocked externals
│   ├── api_endpoints/           # Complete API workflow tests
│   ├── cli_commands/            # Full CLI operation tests
│   └── trading_workflows/       # End-to-end trading scenarios
├── host_service/                # Tests requiring real host services
│   ├── ib_integration/          # Real IB host service tests
│   └── training_service/        # Real training host service tests
└── manual/                      # Manual/nightly tests only
    ├── performance/             # Performance benchmarks
    ├── stress/                  # Stress testing
    └── real_trading/            # Real market tests
```

## 🎯 Implementation Plan

### Phase 1: Foundation & Cleanup (Days 1-2)

**Goal:** Get a working, fast test suite foundation with proper tooling

#### Day 1: Environment & CI Setup

- [ ] **1.1** Create new test directory structure
- [ ] **1.2** Set up pytest configuration with comprehensive markers
- [ ] **1.3** Update GitHub Actions workflow for new test structure
- [ ] **1.4** Configure test coverage measurement with pytest-cov
- [ ] **1.5** Create Makefile with standard test commands

**Validation Checks for Day 1:**
- [ ] **V1.1** Verify directory structure exists: `ls tests/{unit,integration,e2e,host_service,manual}`
- [ ] **V1.2** Test pytest markers work: `uv run pytest --markers | grep "unit\|integration\|e2e"`
- [ ] **V1.3** Verify Makefile commands work: `make test-unit`, `make quality`
- [ ] **V1.4** Check coverage integration: `make test-coverage` generates HTML report
- [ ] **V1.5** Validate GitHub Actions syntax: Check workflow file loads without errors

#### Day 2: Test Categorization Audit

- [ ] **2.1** Audit all `tests/api/` files - categorize unit vs integration
- [ ] **2.2** Audit all `tests/data/` files - identify true unit tests
- [ ] **2.3** Audit all `tests/indicators/` files - most should be unit tests
- [ ] **2.4** Audit all `tests/fuzzy/` files - separate unit from integration
- [ ] **2.5** Fix remaining ruff violations (158 → <20)
- [ ] **2.6** Create detailed inventory document of test migration targets
- [ ] **2.7** Update CLAUDE.md with Makefile testing standards  
- [ ] **2.8** Update .agent-os/standards/development-workflow.md with test commands
- [ ] **2.9** Update .agent-os/standards/testing-standards.md with new structure

**Validation Checks for Day 2:**
- [ ] **V2.1** Verify ruff violations reduced: `uv run ruff check tests/ | wc -l` < 50
- [ ] **V2.2** Check documentation updated: grep "make test-unit" CLAUDE.md
- [ ] **V2.3** Validate standards files: verify .agent-os/standards contain Makefile commands
- [ ] **V2.4** Test audit completion: inventory document created with categorized tests
- [ ] **V2.5** Performance baseline: `time make test-unit` completes in reasonable time

### Phase 2: Comprehensive Unit Test Creation (Days 3-6)

**Goal:** Create comprehensive <2s unit test suite covering ALL modules

#### Day 3: Core Logic & Calculations

- [ ] **3.1** Move/create indicator calculation unit tests (comprehensive coverage)
- [ ] **3.2** Create fuzzy logic unit tests with full algorithm coverage
- [ ] **3.3** Create neural network unit tests (architecture, not training)
- [ ] **3.4** Target: 150+ unit tests in <1s

#### Day 4: Data & Config Layer

- [ ] **4.1** Create comprehensive data adapter unit tests (heavily mocked)
- [ ] **4.2** Create config loading and validation unit tests
- [ ] **4.3** Create data transformation and utility unit tests
- [ ] **4.4** Target: 250+ unit tests in <1.5s

#### Day 5: API & Service Layer

- [ ] **5.1** Create API model validation and serialization unit tests
- [ ] **5.2** Create API business logic unit tests (no HTTP calls)
- [ ] **5.3** Create service layer unit tests with dependency injection
- [ ] **5.4** Target: 350+ unit tests in <1.8s

#### Day 6: CLI & Host Services

- [ ] **6.1** Create CLI command parsing and validation unit tests
- [ ] **6.2** Create CLI business logic unit tests (no subprocess calls)
- [ ] **6.3** Create host service internal logic unit tests (mock external connections)
- [ ] **6.4** Create host service API client unit tests (mock HTTP)
- [ ] **6.5** Target: 500+ unit tests in <2s

**Phase 2 Validation Checks:**
- [ ] **V2.A** Unit test count: `make test-unit --collect-only | grep "<Function" | wc -l` ≥ 500
- [ ] **V2.B** Performance target: `time make test-unit` < 2 seconds  
- [ ] **V2.C** Coverage target: `make test-coverage` shows >80% overall coverage
- [ ] **V2.D** No external calls: Unit tests run without network/database dependencies
- [ ] **V2.E** All modules covered: Each major module (api/, cli/, data/, etc.) has unit tests

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

1. **Days 1-2:** Complete Phase 1 (foundation and audit)
2. **Days 3-4:** Start Phase 2 (core unit test creation)
3. **Day 5:** Continue Phase 2 (API and service unit tests)

### Success Criteria for Week 1

- [ ] Test collection time <2 seconds
- [ ] Unit test suite runs in <2 seconds with 300+ tests
- [ ] Integration test suite runs in <30 seconds
- [ ] Ruff violations <50
- [ ] Coverage measurement integrated into CI
- [ ] GitHub Actions workflow updated and working

### Week 2 Goals

- [ ] Complete Phase 2 (500+ unit tests)
- [ ] Complete Phase 3 (optimized integration tests)
- [ ] Complete Phase 4 (E2E and full CI integration)
- [ ] Achieve >80% overall test coverage
- [ ] Document and train team on new test structure

---

*This plan transforms the test suite from a development blocker into a comprehensive quality assurance system with sub-second feedback loops for unit tests and proper test pyramid structure.*
