# Training Host Service

A lightweight FastAPI service that runs on the host machine to provide GPU acceleration for KTRDR training, bypassing Docker GPU access limitations.

## Overview

This service extracts the training functionality from the Docker container and runs it directly on the host system, enabling:
- **GPU Acceleration**: Direct access to CUDA/MPS without Docker limitations
- **Memory Management**: Efficient GPU memory management and monitoring
- **Performance Optimization**: Native host performance without container overhead
- **Service Integration**: HTTP API that the containerized backend can call

## Architecture

The service follows the same architecture patterns as the IB Host Service:
- **FastAPI**: Lightweight web framework for HTTP endpoints
- **Endpoint Organization**: Modular endpoint structure in `endpoints/` directory
- **Configuration Management**: YAML-based configuration with fallback defaults
- **Health Monitoring**: Comprehensive health checks and status reporting
- **Resource Management**: GPU memory and system resource monitoring

## Quick Start

### Prerequisites
- Python 3.8+
- PyTorch with CUDA support (for GPU acceleration)
- KTRDR project dependencies

### Starting the Service
```bash
# Preferred (loads host-service secrets from 1Password)
uv run kinfra local-prod start-training-host
```

Legacy startup script (deprecated):
```bash
# Direct script startup is deprecated because it bypasses kinfra's
# 1Password secret injection unless you export DB env vars manually.
# If you still need it for debugging, ensure env is set first.
./start.sh
```

The service will be available at `http://127.0.0.1:5002`

### Stopping the Service
```bash
./stop.sh
```

## API Endpoints

### Health Monitoring
- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed system and GPU status

### Training Operations
- `POST /training/start` - Start a new training session
- `POST /training/stop` - Stop a running training session
- `GET /training/status/{session_id}` - Get training progress and status
- `GET /training/sessions` - List all training sessions
- `POST /training/evaluate` - Evaluate a trained model
- `DELETE /training/sessions/{session_id}` - Cleanup completed sessions

## Configuration

The service uses YAML configuration files in the project's `config/` directory:

```yaml
# config/training_host_service.yaml
host_service:
  host: "127.0.0.1"
  port: 5002
  log_level: "INFO"
  max_concurrent_sessions: 1
  session_timeout_minutes: 60
```

## GPU Support

The service automatically detects and utilizes available GPU resources:
- **CUDA**: NVIDIA GPU support with memory management
- **MPS**: Apple Silicon GPU support
- **Fallback**: CPU-only mode if no GPU is available

GPU memory management includes:
- Memory allocation tracking
- Automatic cleanup and garbage collection
- Memory usage monitoring and alerts
- Mixed precision training support

## Integration with Docker Backend

The containerized KTRDR backend communicates with this service via HTTP:

```python
# Example: Starting a training session from Docker container
import requests

response = requests.post("http://host.docker.internal:5002/training/start", json={
    "model_config": {...},
    "training_config": {...},
    "data_config": {...}
})

session_id = response.json()["session_id"]
```

## Development

### File Structure
```
training-host-service/
├── main.py              # FastAPI application entry point
├── config.py            # Configuration management
├── (uses main project uv.lock for dependencies)
├── start.sh            # Service startup script
├── stop.sh             # Service shutdown script
├── endpoints/          # API endpoint modules
│   ├── __init__.py
│   ├── health.py       # Health check endpoints
│   └── training.py     # Training operation endpoints
├── services/           # Service layer logic
├── scripts/            # Utility scripts
├── tests/              # Test files
├── config/             # Configuration files
└── logs/               # Service logs
```

### Testing

Run the service tests:
```bash
# Unit tests
python -m pytest tests/unit/

# Integration tests (requires service running)
python -m pytest tests/integration/

# Full test suite
python -m pytest tests/
```

### Logging

Service logs are written to:
- `logs/training-host-service.log` - Main service log
- `logs/api_server.log` - API request/response log

## Troubleshooting

### Common Issues

1. **Service won't start**: Check that port 5002 is available
2. **`ModuleNotFoundError: No module named 'torch'`**: Start via `uv run kinfra local-prod start-training-host` (it loads the `ml` extra path)
3. **`password authentication failed for user "ktrdr"`**: Host service started without the right DB secret; restart via `uv run kinfra local-prod start-training-host`
4. **GPU not detected**: Verify PyTorch CUDA installation
5. **Import errors**: Ensure PYTHONPATH includes parent directory
6. **Permission errors**: Check file permissions on scripts

### Health Checks

Monitor service health:
```bash
# Basic health check
curl http://localhost:5002/health

# Detailed status including GPU info
curl http://localhost:5002/health/detailed
```

## Security Considerations

- Service runs on localhost only by default
- No authentication required (internal service)
- CORS enabled for Docker container communication
- Process isolation from containerized components
