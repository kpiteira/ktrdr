# Docker Infrastructure Guide

## Overview

This document provides instructions for working with the KTRDR Docker infrastructure, which containerizes the application components for consistent, reproducible environments across development and deployment scenarios.

## Key Components

The Docker infrastructure consists of the following key components:

1. **Dockerfile**: Multi-stage build process that creates an optimized container image
2. **.dockerignore**: Configures which files are excluded from the Docker build context
3. **docker-compose.yml**: Defines services, networks, and volumes for the application
4. **Logging Configuration**: JSON-based logging setup for containerized environments

## Prerequisites

Before using the Docker infrastructure, ensure you have:

1. Docker installed (version 20.10.0 or newer recommended)
2. Docker Compose installed (version 2.0.0 or newer recommended)
3. Git (for source code management)
4. Basic familiarity with Docker commands

## Getting Started

### Building the Docker Image

To build the KTRDR backend Docker image:

```bash
# From the project root directory
docker build -t ktrdr-backend .
```

This command builds a multi-stage Docker image that:
- Compiles dependencies in a builder stage
- Creates an optimized runtime image
- Sets up a non-root user for security
- Configures proper volume mounts and health checks

### Starting Services with Docker Compose

To start all the services defined in the Docker Compose file:

```bash
# Start services in detached mode
docker-compose up -d

# View logs from all containers
docker-compose logs

# View logs from a specific service
docker-compose logs backend
```

## Container Architecture

### Multi-Stage Build

The Dockerfile uses a multi-stage build approach for several benefits:

1. **Smaller Final Image**: Only runtime dependencies are included
2. **Enhanced Security**: Build tools are excluded from the runtime image
3. **Efficient Caching**: Better layer caching for faster rebuilds

### Security Features

The Docker infrastructure includes several security enhancements:

1. **Non-Root User**: The container runs as a non-root user `ktrdr`
2. **Minimal Base Image**: Uses python:3.11-slim for a smaller attack surface
3. **Tini Init Process**: Proper signal handling and zombie process reaping
4. **Health Checks**: Regular verification of application health

### Volume Management

The infrastructure defines persistent volumes for:

1. **Data**: Application data storage (`/home/ktrdr/app/data`)
2. **Logs**: Centralized logging directory (`/home/ktrdr/app/logs`)

These volumes ensure data persistence across container restarts and updates.

## Configuration

### Environment Variables

The container accepts several environment variables for configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Application environment (development, production) | development |
| `LOG_LEVEL` | Logging verbosity (DEBUG, INFO, WARNING, ERROR) | INFO |
| `PYTHONPATH` | Python module search path | /home/ktrdr/app |

Example of setting environment variables in docker-compose.yml:

```yaml
services:
  backend:
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=WARNING
```

### Configuration Files

For more complex configuration, you can mount configuration files:

```yaml
services:
  backend:
    volumes:
      - ./config:/home/ktrdr/app/config:ro
```

## Testing and Validation

### Health Check

The container includes a built-in health check that verifies the application is responding correctly:

```bash
# View container health status
docker ps --format "table {{.Names}}\t{{.Status}}"

# Manually test the health check endpoint
curl http://localhost:8000/api/health
```

Expected response from health check:
```json
{"status":"ok","version":"1.0.5.5"}
```

### Testing Container Functionality

To verify the container is working properly:

```bash
# Start the containers
docker-compose up -d

# Check if the container is running
docker ps | grep ktrdr-backend

# Test the health check endpoint
curl http://localhost:8000/api/health

# View the logs to verify logging configuration
docker-compose logs backend

# Stop the containers when done
docker-compose down
```

### Verifying Container Security

To confirm the container is running with the correct security settings:

```bash
# Check the user the container is running as
docker exec ktrdr-backend id

# Expected output should show uid and gid for non-root user "ktrdr"
# Example: uid=1000(ktrdr) gid=1000(ktrdr) groups=1000(ktrdr)
```

## Common Operations

### Rebuilding After Code Changes

After making changes to the application code:

```bash
# Rebuild the image
docker-compose build

# Restart the services
docker-compose up -d
```

### Accessing Container Logs

To view container logs:

```bash
# View logs for all services
docker-compose logs

# View logs for a specific service
docker-compose logs backend

# Follow logs in real-time
docker-compose logs -f backend
```

### Container Shell Access

To access a shell inside the container:

```bash
docker exec -it ktrdr-backend /bin/bash
```

### Cleaning Up Resources

To clean up Docker resources:

```bash
# Stop and remove containers, networks, and volumes
docker-compose down -v

# Remove the built image if desired
docker rmi ktrdr-backend:latest
```

## Advanced Usage

### Extending the Dockerfile

If you need to customize the Dockerfile for specific use cases, you can create an extended version:

```dockerfile
# Extend from the base image
FROM ktrdr-backend:latest

# Add custom dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    your-package-name \
    && rm -rf /var/lib/apt/lists/*

# Add custom files
COPY custom_files/ /home/ktrdr/app/custom_files/

# Custom entrypoint or command if needed
CMD ["custom-command"]
```

### Custom Docker Compose Setup

For more complex setups, you can create environment-specific docker-compose files:

```bash
# Create a development setup
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Create a production setup
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Common Issues

1. **Container fails to start**:
   - Check logs with `docker-compose logs backend`
   - Verify port 8000 is not already in use
   - Check container health with `docker ps --format "{{.Names}}: {{.Status}}"`

2. **Health check fails**:
   - Verify API is running with `docker exec ktrdr-backend ps aux`
   - Check logs for application errors
   - Test endpoint directly with `docker exec ktrdr-backend curl -f http://localhost:8000/api/health`

3. **Permission issues with volumes**:
   - Check ownership of volume directories
   - Verify the container user has appropriate permissions

4. **Performance issues**:
   - Check resource usage with `docker stats`
   - Verify host system has sufficient resources
   - Consider adjusting container resource limits

## Best Practices

1. **Use Volumes for Persistence**: Always use named volumes for data that should persist between container restarts.

2. **Version Control Docker Files**: Keep your Dockerfile and docker-compose.yml in version control.

3. **Optimize Build Context**: Use .dockerignore to exclude unnecessary files from the build context.

4. **Update Base Images Regularly**: Periodically rebuild images to incorporate security updates.

5. **Monitor Container Health**: Implement monitoring for container health checks.

6. **Backup Volume Data**: Regularly backup data stored in Docker volumes.

7. **Use Environment-Specific Configs**: Maintain separate configuration files for different environments.

## Further Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [FastAPI in Containers](https://fastapi.tiangolo.com/deployment/docker/)
- [Docker Security Best Practices](https://docs.docker.com/develop/security-best-practices/)