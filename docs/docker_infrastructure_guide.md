# KTRDR Docker Infrastructure Guide

This guide explains how to use the Docker infrastructure for development, testing, and production deployment of KTRDR.

## Overview

KTRDR's Docker infrastructure is designed to provide:

1. **Isolated Components**: Separation of backend API and optional Redis services
2. **Development Workflow**: Hot-reloading, volume mounting, and developer-friendly tooling
3. **Production Readiness**: Optimized containers with proper security and resource constraints
4. **Consistent Environments**: Same behavior across development, testing, and production

## Quick Start

```bash
# Start development environment (with hot-reloading)
./docker_dev.sh start

# View container logs
./docker_dev.sh logs

# Access a shell inside the backend container
./docker_dev.sh shell

# Stop environment
./docker_dev.sh stop
```

## Development Environment

The development environment is optimized for fast iteration with:

- **Hot-Reloading**: Code changes are immediately reflected without restarts
- **Volume Mounting**: Source code, data, logs, and outputs are persisted
- **Developer Tools**: Development dependencies are pre-installed

### Container Configuration

- **Backend Service**: FastAPI application serving the API
  - Port: 8000 (accessible at http://localhost:8000)
  - API Documentation: http://localhost:8000/api/docs
  - Mounted Volumes:
    - `./ktrdr`: Source code (for hot-reloading)
    - `./data`: Persistent data volume
    - `./logs`: Log files
    - `./config`: Configuration files (read-only)
    - `./output`: Output files for visualizations

- **Redis Service** (Optional, commented out by default)
  - Cache and messaging service
  - Port: 6379

### Helper Script Commands

The `docker_dev.sh` script provides convenient commands:

- `start`: Start the development environment
- `stop`: Stop the environment
- `restart`: Restart all containers
- `logs`: View logs from all containers
- `shell`: Open a shell in the backend container
- `rebuild`: Rebuild containers (preserving data)
- `clean`: Stop containers and remove volumes
- `test`: Run tests in the backend container
- `prod`: Start the production environment
- `health`: Check container health status
- `help`: Show help message

## Production Environment

The production environment is optimized for stability, security, and performance:

- **Security Enhancements**:
  - Non-root user execution
  - No development dependencies
  - Security options like `no-new-privileges`
  
- **Resource Management**:
  - CPU and memory limits defined
  - Optimized container size
  
- **Reliability Features**:
  - Health checks on all services
  - Proper restart policies
  - Named volumes for data persistence

### Deployment

To deploy for production:

```bash
# Start production environment
docker-compose -f docker-compose.prod.yml up -d

# Or use the helper script
./docker_dev.sh prod
```

## Environment Variables

Configure the application behavior using environment variables:

- `ENVIRONMENT`: Set to `development` or `production`
- `LOG_LEVEL`: Set logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `REDIS_PASSWORD`: Redis authentication password (if Redis service is enabled)
- `IB_API_KEY`: Interactive Brokers API key (if needed)

For sensitive environment variables, create a `.env` file:

```
REDIS_PASSWORD=mystrongpassword
IB_API_KEY=yourapikey
```

## Component Isolation

The Docker infrastructure implements component isolation as described in the architecture blueprint:

1. **Backend API Container**:
   - Serves the FastAPI application
   - Handles data processing and API endpoints
   - Properly isolated with non-root user

2. **Redis Container** (Optional):
   - Provides caching and messaging capabilities
   - Isolated with Alpine-based minimal image
   - Secured with password authentication

## Volume Management

KTRDR uses the following Docker volumes for data persistence:

- `ktrdr-data`: For market data, configurations, and application state
- `ktrdr-logs`: For application logs
- `redis-data`: For Redis persistence (if enabled)

## Adding New Components

To add additional services (e.g., database, frontend):

1. Define a new service in `docker-compose.yml`
2. Configure appropriate volumes and networks
3. Update the helper script to support the new service

## Troubleshooting

Common issues and solutions:

- **Permission errors**: Docker volume permissions can sometimes cause issues. Run `./docker_dev.sh clean` to reset volumes.
- **Port conflicts**: If port 8000 is already in use, modify the port mapping in the docker-compose file.
- **Container health failures**: Check container logs with `./docker_dev.sh logs` to diagnose issues.

## Best Practices

- Use the helper script for all Docker operations to ensure consistency
- Keep the development and production environments as similar as possible
- Regularly rebuild the development container to pick up dependency changes
- Use health checks to verify container readiness