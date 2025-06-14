# Container End-to-End Testing

This document describes the comprehensive container-based end-to-end testing system for KTRDR, which validates the complete system functionality including the refactored IB components.

## Overview

The E2E testing system provides comprehensive validation of:
- **API Endpoints**: All REST API functionality in container environment
- **CLI Commands**: Complete CLI functionality within containers
- **IB Integration**: Refactored IB connection management and functionality
- **Performance**: Response times and resource usage validation
- **System Integration**: Cross-component communication and error handling

## Test Structure

```
tests/e2e/
├── __init__.py                           # Package initialization
├── conftest.py                          # E2E test configuration and fixtures
├── test_container_api_endpoints.py      # Comprehensive API endpoint tests
└── test_container_cli_commands.py       # Complete CLI functionality tests

scripts/
├── run_container_e2e_tests.py          # Python test orchestrator
└── test_container.sh                   # Bash wrapper script
```

## Quick Start

### Prerequisites

1. **Container Running**: Ensure the KTRDR backend container is running:
   ```bash
   ./docker_dev.sh start
   ```

2. **Dependencies**: Ensure you have the required tools:
   - Docker
   - uv (Python package manager)
   - Python 3.9+

### Running Tests

#### Option 1: Quick Tests (Recommended for Development)
```bash
# Run quick smoke tests
./scripts/test_container.sh quick

# Or directly:
./scripts/test_container.sh
```

#### Option 2: Comprehensive Test Suite
```bash
# Run full E2E test suite
./scripts/test_container.sh full
```

#### Option 3: Specific Test Categories
```bash
# API endpoints only
./scripts/test_container.sh api

# CLI commands only
./scripts/test_container.sh cli
```

#### Option 4: Direct pytest Execution
```bash
# API endpoint tests
uv run pytest tests/e2e/test_container_api_endpoints.py --run-container-e2e -v

# CLI functionality tests
uv run pytest tests/e2e/test_container_cli_commands.py --run-container-cli -v
```

## Test Categories

### 1. Container API Endpoint Tests

**File**: `tests/e2e/test_container_api_endpoints.py`

Tests all API endpoints in the container environment:

#### Health & System Tests
- API health endpoint validation
- System status and configuration
- API documentation availability
- OpenAPI specification

#### IB Integration Tests
- IB status and health endpoints
- Connection pool status validation
- Symbol discovery functionality
- Configuration management
- Cleanup operations

#### Data Management Tests
- Data loading endpoints
- Local vs IB data modes
- Parameter validation
- Error handling

#### Performance Tests
- Response time validation
- Concurrent request handling
- Resource usage monitoring
- Error handling under load

### 2. Container CLI Command Tests

**File**: `tests/e2e/test_container_cli_commands.py`

Tests complete CLI functionality within containers:

#### Basic CLI Tests
- Help command functionality
- Version information
- Command listing and discovery

#### IB CLI Commands
- `ib-cleanup` command
- `test-ib` command with various options
- Connection testing and validation

#### Data CLI Commands
- `show-data` command in various modes
- Parameter validation
- Error handling for invalid inputs

#### Strategy CLI Commands
- `strategy-list` command
- Strategy validation
- Configuration access

#### Integration Tests
- CLI access to container services
- Configuration and data directory access
- Cross-component communication

### 3. System Integration Tests

Validates complete system functionality:

#### Connection Pool Integration
- Multiple concurrent API requests
- CLI and API simultaneous usage
- Resource sharing and cleanup

#### Error Handling
- Graceful degradation testing
- Error propagation validation
- Recovery mechanism testing

#### Performance Validation
- Response time thresholds
- Memory usage monitoring
- Resource leak detection

## Configuration

### Environment Variables

```bash
# Container configuration
CONTAINER_NAME=ktrdr-backend        # Container name to test
API_BASE_URL=http://localhost:8000  # API base URL

# Test behavior
RUN_INTEGRATION_TESTS=true          # Enable integration tests
TEST_TIMEOUT=30                     # Test timeout in seconds
```

### Command Line Options

```bash
# Pytest options
--run-container-e2e                 # Enable container API tests
--run-container-cli                 # Enable container CLI tests
--api-base-url=URL                  # API base URL
--container-name=NAME               # Container name

# Test runner options
--wait-timeout=SECONDS              # Service readiness timeout
--output-json=FILE                  # JSON output file
```

## Test Results and Reporting

### Console Output
The test runner provides real-time colored output:
- 🔍 **Info**: General information and progress
- ✅ **Success**: Passed tests and validations
- ❌ **Error**: Failed tests and issues
- ⚡ **Performance**: Timing and performance data

### JSON Output
Comprehensive test results in JSON format:
```json
{
  "container_status": {
    "running": true,
    "api_ready": true
  },
  "api_tests": {
    "success": true,
    "output": "..."
  },
  "cli_tests": {
    "success": true,
    "output": "..."
  },
  "performance_tests": {
    "success": true,
    "api_endpoints": {
      "/health": {
        "status_code": 200,
        "response_time": 0.045,
        "passed": true
      }
    }
  },
  "overall_success": true
}
```

### Test Report
Comprehensive summary with:
- Container status validation
- API endpoint test results
- CLI functionality test results
- Performance validation
- Integration smoke tests
- Overall success/failure status

## Troubleshooting

### Common Issues

#### Container Not Running
```
Error: Container 'ktrdr-backend' is not running
Solution: Start container with ./docker_dev.sh start
```

#### API Not Ready
```
Error: API not ready after 120s
Solution: Check container logs: docker logs ktrdr-backend
```

#### Permission Issues
```
Error: Permission denied accessing data directory
Solution: Check container volume mounts and permissions
```

#### Test Timeouts
```
Error: Test execution timed out after 5 minutes
Solution: Increase timeout or check system resources
```

### Debug Mode

Enable detailed logging:
```bash
# Verbose pytest output
uv run pytest tests/e2e/ --run-container-e2e -v -s

# Container logs
docker logs -f ktrdr-backend

# Test runner debug
python scripts/run_container_e2e_tests.py --wait-timeout=300
```

### Manual Validation

Verify individual components:
```bash
# Check container status
docker ps | grep ktrdr-backend

# Test API manually
curl http://localhost:8000/health

# Test CLI manually
docker exec ktrdr-backend uv run ktrdr --help
```

## Integration with CI/CD

### GitHub Actions Example
```yaml
- name: Run Container E2E Tests
  run: |
    ./docker_dev.sh start
    ./scripts/test_container.sh full
    ./docker_dev.sh stop
```

### Test Artifacts
- Save `test_results.json` for analysis
- Capture container logs on failure
- Export performance metrics

## Performance Benchmarks

### Expected Performance
- API health endpoint: < 100ms
- System status: < 500ms
- IB status (no IB): < 1s
- CLI help command: < 2s
- Symbol discovery: < 5s

### Performance Monitoring
The test suite monitors:
- Response times for all endpoints
- Memory usage during operations
- Resource cleanup effectiveness
- Concurrent operation handling

## Best Practices

### Test Development
1. **Container Independence**: Tests should not depend on external state
2. **Graceful Degradation**: Handle missing services appropriately
3. **Timeout Management**: Use appropriate timeouts for different operations
4. **Error Validation**: Verify both success and failure scenarios

### Test Execution
1. **Clean Environment**: Start with fresh container state
2. **Parallel Safety**: Ensure tests can run concurrently
3. **Resource Cleanup**: Verify proper cleanup after tests
4. **Monitoring**: Track performance trends over time

### Maintenance
1. **Regular Updates**: Keep tests current with API changes
2. **Performance Baselines**: Update expected performance metrics
3. **Error Scenarios**: Add tests for new error conditions
4. **Documentation**: Keep test documentation current

## Related Documentation

- [IB Connection Refactoring](IB_CONNECTION_REFACTOR_PLAN.md)
- [API Documentation](../api/README.md)
- [CLI Documentation](../cli/README.md)
- [Docker Development](../docker/README.md)