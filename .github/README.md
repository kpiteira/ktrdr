# GitHub Actions CI/CD

This directory contains the CI/CD workflows for the KTRDR project.

## Workflows

### `ci.yml` - Main CI Pipeline

**Triggers:**
- Push to `main`, `develop`, or `test-suite-cleanup` branches
- Pull requests to `main` or `develop` branches  
- Manual workflow dispatch

**Jobs:**

#### 1. Unit Tests (Always runs)
- **Purpose**: Fast validation of core functionality
- **Tests**: ~960 unit tests (excludes integration/e2e/container tests)
- **Runtime**: ~5-10 minutes
- **Command**: `pytest tests/ -m "not (integration or real_ib or container_api or container_cli or e2e or container_e2e)"`

#### 2. Code Quality (Always runs)
- **Purpose**: Enforce code standards
- **Checks**: Black formatting, MyPy type checking
- **Runtime**: ~2-3 minutes

#### 3. Container E2E Tests (Selective)
- **Purpose**: Test API endpoints and CLI in containerized environment
- **When**: Only on `main`/`develop` pushes or manual triggers
- **Requirements**: Docker containers (backend + frontend)
- **Runtime**: ~10-15 minutes
- **Command**: `pytest tests/e2e/ --run-container-e2e --run-container-cli`

#### 4. Integration Tests (Manual only)
- **Purpose**: Test with mocked IB connections
- **When**: Only on manual workflow dispatch
- **Note**: Uses mocked IB calls via `disable_retries` fixture
- **Command**: `pytest tests/integration/`

#### 5. Test Summary (Always runs)
- **Purpose**: Aggregate and display test results
- **Artifacts**: Saves test result XML files

## Test Categories

### ✅ CI-Safe Tests (Run automatically)
- **Unit tests**: Core logic, data processing, indicators, fuzzy logic
- **API tests**: Endpoint validation with mocked dependencies  
- **CLI tests**: Command parsing and output formatting
- **Config tests**: Configuration loading and validation
- **Total**: ~960 tests

### ⚠️ Infrastructure-Dependent Tests (Conditional)
- **Container E2E**: Require running Docker containers
- **Integration**: Use mocked IB connections (safe for CI)

### ❌ Real IB Tests (Not run in CI)
- **Real E2E**: Require actual IB Gateway connection
- **Location**: `tests/e2e_real/`
- **Usage**: Local development only via `./scripts/run_real_e2e_tests.sh`

## Local Testing Commands

```bash
# Run the same tests as CI
uv run pytest tests/ -m "not (integration or real_ib or container_api or container_cli or e2e or container_e2e)"

# Run with container tests (requires Docker)
./docker_dev.sh start
uv run pytest tests/e2e/ --run-container-e2e --run-container-cli

# Run all tests including real IB (requires IB Gateway)
./scripts/run_real_e2e_tests.sh
```

## Troubleshooting

### Common CI Failures

1. **Unit Test Failures**
   - Check test output in GitHub Actions logs
   - Run locally: `uv run pytest tests/ -m "not (integration or real_ib or container_api or container_cli or e2e or container_e2e)" -v`

2. **Container Tests Timing Out**
   - Container startup can take 30-60 seconds
   - API health check retries for 2 minutes
   - Check container logs in CI output

3. **Dependency Issues**
   - Ensure `uv.lock` is committed and up to date
   - Update with: `uv lock`

4. **Code Quality Failures**
   - Format code: `uv run black ktrdr tests`
   - Fix type issues: `uv run mypy ktrdr`

### Performance Optimization

- **Unit tests**: Optimized with sleep mocking for retry tests
- **Caching**: UV dependencies cached between runs  
- **Parallel execution**: Jobs run in parallel when possible
- **Selective E2E**: Container tests only run on important branches

## Test Environment Requirements

### GitHub Actions Runner
- **OS**: Ubuntu latest
- **Python**: Set up via uv (uses project Python version)
- **Docker**: Available for container tests
- **Dependencies**: Installed via `uv sync --all-extras --dev`

### Automatically Skipped
- Tests marked with `real_ib`, `integration`, `e2e` markers
- Tests requiring IB Gateway or external services
- Container tests when `--run-container-e2e` flag not provided

### Test Fixtures
- **Global mocking**: `disable_retries` fixture mocks IB connections
- **Automatic skipping**: Tests gracefully skip when dependencies unavailable
- **Environment detection**: Tests detect CI environment and adjust behavior