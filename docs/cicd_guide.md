# KTRDR CI/CD Guide

This document explains the CI/CD infrastructure implemented for the KTRDR project, including GitHub Actions workflows, testing automation, and deployment processes.

## Overview

KTRDR uses GitHub Actions for continuous integration and deployment, with the following key workflows:

1. **CI Pipeline**: Code quality checks, unit tests, and integration tests
2. **CD Pipeline**: Build, security scan, and deployment
3. **Documentation**: Automated documentation generation and publishing
4. **Regression Testing**: Weekly benchmarks and regression tests
5. **Release Workflow**: Version management and container publishing

## CI Pipeline (Task 6.5)

The CI pipeline runs on every push to main and develop branches, and for all pull requests. It performs:

### Code Quality Checks
- **Linting**: Enforces code style using flake8
- **Type Checking**: Verifies type hints with mypy
- **Style Verification**: Ensures code follows Black formatting rules

### Testing
- **Unit Tests**: Runs all unit tests with pytest
- **Code Coverage**: Measures and reports test coverage
- **Integration Tests**: Verifies component interactions
- **CLI Testing**: Validates CLI functionality

### Docker Verification
- **Build Testing**: Ensures Dockerfiles can be built successfully
- **Health Check Verification**: Tests container health checks
- **Runtime Validation**: Verifies application runs correctly in containers

## CD Pipeline (Task 6.5)

The CD pipeline automates deployment to staging and production environments:

### Build and Push
- Builds Docker images for deployment
- Pushes images to GitHub Container Registry
- Creates deployment packages with configurations

### Security Scan
- Scans dependencies for vulnerabilities with Safety
- Performs static code analysis with Bandit
- Generates security reports for review

### Deployment
- Deploys to specified environments (development, staging, production)
- Performs health checks to verify successful deployment
- Notifies team through Slack on deployment completion or failure

## Documentation Workflow

Documentation is automatically built and published:

### Build Documentation
- Generates API documentation from docstrings
- Builds a complete documentation site with MkDocs
- Includes code examples and usage guides

### Publishing
- Publishes documentation to GitHub Pages
- Updates documentation on changes to docs folder or Python files
- Maintains version-specific documentation

## Regression Testing (Task 6.6)

Regression testing runs weekly to detect performance regressions:

### Performance Benchmarks
- Runs performance tests for critical components
- Compares results against historical benchmarks
- Alerts on significant performance degradation

### Regression Tests
- Tests for backward compatibility
- Verifies critical functionality remains intact
- Generates detailed reports for analysis

## Release Workflow

Facilitates version management and release processes:

### Version Management
- Updates version files across the project
- Creates Git tags for releases
- Maintains version consistency in code and Docker images

### Docker Release
- Builds and tags Docker images for multiple platforms
- Pushes images to GitHub Container Registry
- Creates GitHub releases with release notes

## Secrets and Environment Configuration

The following secrets should be configured in your GitHub repository:

- `DEPLOY_SSH_KEY`: SSH key for server deployment
- `DEPLOY_HOST`: Hostname for deployment target
- `DEPLOY_USER`: Username for deployment SSH connection
- `REDIS_PASSWORD`: Password for Redis service (optional)
- `SLACK_WEBHOOK`: Webhook URL for Slack notifications (optional)

## How to Use the CI/CD System

### For Developers

1. **Running Tests Locally**:
   ```bash
   # Install development dependencies
   uv pip install -r requirements-dev.txt
   
   # Run unit tests
   pytest tests/
   
   # Run with coverage
   pytest tests/ --cov=ktrdr
   ```

2. **Checking Code Quality**:
   ```bash
   # Format code with Black
   black ktrdr/
   
   # Check types with mypy
   mypy ktrdr/
   
   # Lint with flake8
   flake8 ktrdr/
   ```

### For DevOps and Release Management

1. **Creating Releases**:
   - Go to the Actions tab in GitHub
   - Select the "KTRDR Docker Release" workflow
   - Click "Run workflow"
   - Enter the version number (e.g., "1.0.0")
   - Review and publish the created release

2. **Deploying to Production**:
   - Go to the Actions tab in GitHub
   - Select the "KTRDR CD Pipeline" workflow
   - Click "Run workflow"
   - Select "production" environment
   - Monitor the deployment progress

3. **Updating Documentation**:
   - Go to the Actions tab in GitHub
   - Select the "KTRDR Documentation" workflow
   - Click "Run workflow"
   - The documentation will be built and published to GitHub Pages

## Testing Philosophy

The testing strategy is designed to catch issues as early as possible:

- **Unit Tests**: Verify each component in isolation
- **Integration Tests**: Validate component interactions
- **Functional Tests**: Test end-to-end functionality
- **Regression Tests**: Ensure changes don't break existing features
- **Performance Tests**: Track and maintain application performance

## CI/CD System Extensions

Possible future extensions to the CI/CD system:

1. **Automated Feature Branch Deployments**: Deploy feature branches to temporary environments
2. **Canary Deployments**: Implement gradual rollouts with monitoring
3. **A/B Testing Framework**: Test different versions with real users
4. **Blue/Green Deployments**: Zero-downtime deployments with instant rollback

## Related Documentation

- [Docker Infrastructure Guide](docker_infrastructure_guide.md)
- [Development Workflow](development_workflow.md)
- [Testing Strategy](testing_strategy.md)