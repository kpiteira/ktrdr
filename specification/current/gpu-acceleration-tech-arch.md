# GPU Acceleration Training Service Technical Architecture

## 1. Executive Summary

### Technical Vision
We are implementing a **host-based training service** by extracting the existing GPU-enabled training module from Docker containers to the host system. This follows the proven **IB host service pattern**, utilizing our fully-implemented **GPU acceleration infrastructure** (`GPUMemoryManager`) while maintaining seamless integration with the existing KTRDR system through FastAPI proxying.

### Core Technology Stack
- **Service Extraction**: Move existing `ktrdr.training` modules to host without modification
- **GPU Acceleration**: Leverage existing `GPUMemoryManager` with MPS/CUDA support
- **Service Framework**: FastAPI service following IB host service patterns
- **Communication**: HTTP API with Docker container routing via environment toggles
- **State Management**: Existing SQLAlchemy ORM with shared PostgreSQL database
- **Process Management**: Auto-startup capabilities using systemd/launchd (upgrading from manual IB service)
- **Integration**: Seamless fallback to Docker-only mode when host service unavailable

### Architectural Principles
- **Zero Code Duplication**: Extract existing training code, don't reimplement
- **Pattern Consistency**: Follow established IB host service architecture
- **Transparent Operation**: No changes to CLI, frontend, or user workflows
- **Graceful Fallback**: Automatic Docker-only mode when host service unavailable
- **Auto-Recovery**: Service management with automatic startup and restart
- **Performance First**: Utilize existing GPU optimization for 3-5x speed improvement

### Expected Technical Outcomes
- 3-5x faster training execution using existing GPU acceleration
- Zero disruption to existing workflows and interfaces
- Automatic startup and management of both IB and training host services
- Complete backward compatibility with Docker-only operation
- Seamless integration with existing monitoring and logging infrastructure

---

## 2. System Technical Architecture

### 2.1 High-Level Service Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Host System                             │
│  ┌─────────────────┐      ┌─────────────────────────────────┐  │
│  │  IB Host Service │      │   Training Host Service         │  │
│  │   (Port 5001)    │      │      (Port 5002)               │  │
│  │                  │      │                                 │  │
│  │ ┌─────────────┐ │      │ ┌─────────────┐ ┌─────────────┐ │  │
│  │ │ IB Gateway  │ │      │ │GPU Memory   │ │ Training    │ │  │
│  │ │ Integration │ │      │ │ Manager     │ │ Orchestrator│ │  │
│  │ └─────────────┘ │      │ └─────────────┘ └─────────────┘ │  │
│  │ ┌─────────────┐ │      │ ┌─────────────┐ ┌─────────────┐ │  │
│  │ │ Health      │ │      │ │ Model       │ │ Analytics   │ │  │
│  │ │ Monitoring  │ │      │ │ Trainer     │ │ Engine      │ │  │
│  │ └─────────────┘ │      │ └─────────────┘ └─────────────┘ │  │
│  └─────────────────┘      └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                ↑
                                │ HTTP API Calls
                                │
┌─────────────────────────────────────────────────────────────────┐
│                      Docker Environment                          │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                   Backend API Service                    │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │  │
│  │  │Training API │  │  IB API     │  │   Core KTRDR    │  │  │
│  │  │Proxy Router │  │Proxy Router │  │   Services      │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                ↑                               │
│                                │                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                   Frontend Service                       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │  │
│  │  │ Training UI │  │ Research UI │  │   Management    │  │  │
│  │  │ Components  │  │ Components  │  │   Dashboard     │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                ↑
                                │
┌─────────────────────────────────────────────────────────────────┐
│                         Shared Storage                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ PostgreSQL  │  │   Models    │  │   Training Analytics   │  │
│  │  Database   │  │  Directory  │  │      Directory         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Service Communication Architecture

#### Environment-Based Routing Pattern
Following the established IB host service pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│                Environment Variable Configuration                │
│                                                                 │
│  USE_TRAINING_HOST_SERVICE=true                                │
│  TRAINING_HOST_SERVICE_URL=http://host.docker.internal:5002    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Request Flow Logic                         │
│                                                                 │
│  if USE_TRAINING_HOST_SERVICE and host_service_healthy:         │
│      route_to_host_service()                                   │
│  else:                                                         │
│      fallback_to_docker_training()                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Communication Protocols
- **Primary**: HTTP/JSON API following FastAPI patterns
- **Health Checks**: Regular status polling with circuit breaker
- **Error Handling**: Automatic fallback to Docker on host service failure
- **Authentication**: Localhost-only binding for security

### 2.3 GPU Acceleration Integration

The architecture leverages the existing, fully-implemented GPU infrastructure:

```
┌─────────────────────────────────────────────────────────────────┐
│                   Training Host Service                          │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              Existing GPU Infrastructure                │  │
│  │                                                         │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │         GPUMemoryManager                        │  │  │
│  │  │  • MPS (Apple Silicon) Support                  │  │  │
│  │  │  • CUDA Support                                │  │  │
│  │  │  • Memory Optimization                        │  │  │
│  │  │  • Multi-GPU Management                       │  │  │
│  │  │  • Mixed Precision Training                   │  │  │
│  │  │  • Batch Size Optimization                    │  │  │
│  │  │  • Real-time Monitoring                       │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  │                                                         │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │         Training Modules (Unchanged)            │  │  │
│  │  │  • train_strategy.py                           │  │  │
│  │  │  • model_trainer.py                            │  │  │
│  │  │  • fuzzy_neural_processor.py                   │  │  │
│  │  │  • analytics/*.py                              │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  │                                                         │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.4 Service Management Architecture

#### Auto-Startup System (Upgrading Both Services)
```
┌─────────────────────────────────────────────────────────────────┐
│                      System Boot Sequence                       │
│                                                                 │
│  1. System Startup (macOS/Linux)                               │
│                     ↓                                          │
│  2. Service Manager (launchd/systemd)                          │
│                     ↓                                          │
│  3. Host Services Auto-Start                                   │
│     ┌─────────────────────┐  ┌─────────────────────────────┐  │
│     │   IB Host Service   │  │  Training Host Service      │  │
│     │   (Port 5001)       │  │     (Port 5002)            │  │
│     └─────────────────────┘  └─────────────────────────────┘  │
│                     ↓                                          │
│  4. Docker Environment                                         │
│     ┌─────────────────────────────────────────────────────┐  │
│     │           Backend Service                           │  │
│     │    (Auto-detects host services)                    │  │
│     └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

#### Health Monitoring and Recovery
- **Service Health Checks**: `/health` endpoints for both services
- **Automatic Restart**: Systemd/launchd restart on failure
- **Circuit Breaker**: Docker service fallback on host service issues
- **Monitoring Integration**: Existing Prometheus metrics extended

---

## 3. Component Specifications

### 3.1 Training Host Service Core

#### Purpose
Extract existing GPU-enabled training capabilities to host system while maintaining API compatibility and enabling GPU acceleration.

#### Technical Implementation
- **Framework**: FastAPI service (following IB host service pattern)
- **Runtime**: UV Python environment (maintaining project standards)
- **GPU Access**: Direct host GPU via existing `GPUMemoryManager`
- **Code Reuse**: Import existing `ktrdr.training` modules without modification

#### Service Structure
```python
# training_host_service/
├── main.py                    # FastAPI application entry point
├── config.py                  # Configuration management
├── endpoints/
│   ├── training.py           # Training API endpoints (proxy existing)
│   ├── analytics.py          # Training analytics endpoints
│   └── health.py             # Health and monitoring endpoints
├── services/
│   ├── training_proxy.py     # Wrapper for existing training service
│   └── gpu_monitor.py        # GPU status and metrics
├── scripts/
│   ├── start.sh              # Service startup script
│   ├── stop.sh               # Service shutdown script
│   └── health_check.sh       # Service health validation
└── tests/
    ├── integration/          # Integration with existing training
    └── gpu/                  # GPU acceleration validation
```

#### API Endpoint Mapping
```python
# Direct mapping to existing training endpoints
POST /trainings/start                    → ktrdr.api.endpoints.training.start_training
POST /trainings/start-multi-symbol       → ktrdr.api.endpoints.training.start_multi_symbol_training
GET  /trainings/{task_id}/status         → ktrdr.api.endpoints.training.get_training_status
GET  /trainings/{task_id}/performance    → ktrdr.api.endpoints.training.get_performance_metrics
POST /trainings/{task_id}/stop           → ktrdr.api.endpoints.training.stop_training

# Additional GPU-specific endpoints
GET  /gpu/status                         → GPUMemoryManager.get_memory_summary
GET  /gpu/recommendations               → GPUMemoryManager.get_optimization_recommendations
GET  /health                            → Service health with GPU status
GET  /health/detailed                   → Comprehensive system status
```

### 3.2 Docker API Proxy Integration

#### Purpose
Route training requests to host service when available, maintaining transparent operation for all existing interfaces.

#### Technical Implementation
- **Location**: Modify existing `ktrdr/api/endpoints/training.py`
- **Pattern**: Follow established IB host service routing logic
- **Fallback**: Automatic Docker-only mode when host service unavailable

#### Routing Logic Implementation
```python
# ktrdr/api/endpoints/training.py modifications
import httpx
from ktrdr.config import get_settings

async def route_training_request(endpoint: str, method: str, **kwargs):
    """Route training requests to host service or Docker fallback."""
    settings = get_settings()
    
    if settings.use_training_host_service:
        try:
            # Attempt host service
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=f"{settings.training_host_service_url}{endpoint}",
                    **kwargs
                )
                return response.json()
        except (httpx.ConnectError, httpx.TimeoutException):
            logger.warning("Training host service unavailable, falling back to Docker")
            # Fall through to Docker implementation
    
    # Docker-only implementation (existing code)
    return await docker_training_implementation(**kwargs)
```

#### Environment Configuration
```yaml
# config/environment/training_host_service_enabled.yaml
training_host_service:
  enabled: true
  url: "http://host.docker.internal:5002"
  timeout_seconds: 30
  health_check_interval: 10
  circuit_breaker:
    failure_threshold: 3
    recovery_timeout: 60
```

### 3.3 GPU Memory Manager Integration

#### Purpose
Utilize existing GPU acceleration infrastructure without modification, ensuring optimal performance and resource management.

#### Implementation Strategy
The host service directly imports and uses the existing `GPUMemoryManager`:

```python
# training_host_service/services/gpu_monitor.py
from ktrdr.training.gpu_memory_manager import GPUMemoryManager, GPUMemoryConfig

class TrainingGPUService:
    """GPU service wrapper for training host service."""
    
    def __init__(self):
        # Use existing GPU manager with production configuration
        config = GPUMemoryConfig(
            memory_fraction=0.9,
            enable_mixed_precision=True,
            enable_memory_pooling=True,
            enable_memory_profiling=True
        )
        self.gpu_manager = GPUMemoryManager(config=config)
    
    async def get_gpu_status(self) -> dict:
        """Get GPU status for health monitoring."""
        return self.gpu_manager.get_memory_summary()
    
    async def optimize_for_training(self, model, sample_batch) -> int:
        """Find optimal batch size for training."""
        return self.gpu_manager.optimize_batch_size(model, sample_batch)
    
    def get_memory_context(self, device_id: int = 0):
        """Get memory-efficient training context."""
        return self.gpu_manager.memory_efficient_context(device_id)
```

#### GPU Metrics Integration
```python
# Expose existing GPU metrics via FastAPI
@router.get("/gpu/metrics")
async def get_gpu_metrics():
    """Get real-time GPU utilization metrics."""
    summary = gpu_service.gpu_manager.get_memory_summary()
    
    return {
        "gpu_available": summary["gpu_available"],
        "devices": summary["devices"],
        "total_memory_mb": summary["total_memory_mb"],
        "total_allocated_mb": summary["total_allocated_mb"],
        "utilization_percent": calculate_utilization(summary),
        "recommendations": gpu_service.gpu_manager.get_optimization_recommendations()
    }
```

### 3.4 Service Auto-Startup Implementation

#### Purpose
Upgrade both IB and training host services to start automatically on system boot, eliminating manual startup requirements.

#### Technical Approach

**macOS Implementation (launchd)**
```xml
<!-- ~/Library/LaunchAgents/com.ktrdr.training-host-service.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ktrdr.training-host-service</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/uv</string>
        <string>run</string>
        <string>python</string>
        <string>main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/karl/Documents/dev/ktrdr2/training-host-service</string>
    <key>StandardOutPath</key>
    <string>/Users/karl/Documents/dev/ktrdr2/logs/training-host-service.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/karl/Documents/dev/ktrdr2/logs/training-host-service-error.log</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>/Users/karl/Documents/dev/ktrdr2</string>
    </dict>
</dict>
</plist>
```

**Linux Implementation (systemd)**
```ini
# /etc/systemd/user/ktrdr-training-host.service
[Unit]
Description=KTRDR Training Host Service
After=network.target

[Service]
Type=simple
User=ktrdr
WorkingDirectory=/opt/ktrdr2/training-host-service
Environment=PYTHONPATH=/opt/ktrdr2
ExecStart=/usr/local/bin/uv run python main.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/ktrdr/training-host-service.log
StandardError=append:/var/log/ktrdr/training-host-service-error.log

[Install]
WantedBy=default.target
```

#### Installation Scripts
```bash
#!/bin/bash
# training-host-service/scripts/install_service.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

install_macos() {
    echo "Installing macOS service..."
    
    # Create launchd plist
    SERVICE_PLIST="$HOME/Library/LaunchAgents/com.ktrdr.training-host-service.plist"
    
    # Generate plist with correct paths
    cat > "$SERVICE_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ktrdr.training-host-service</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which uv)</string>
        <string>run</string>
        <string>python</string>
        <string>main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_ROOT/training-host-service</string>
    <key>StandardOutPath</key>
    <string>$PROJECT_ROOT/logs/training-host-service.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_ROOT/logs/training-host-service-error.log</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>$PROJECT_ROOT</string>
    </dict>
</dict>
</plist>
EOF

    # Load service
    launchctl load "$SERVICE_PLIST"
    echo "Training host service installed and started"
}

install_linux() {
    echo "Installing Linux service..."
    
    # Create systemd service file
    SERVICE_FILE="/etc/systemd/user/ktrdr-training-host.service"
    
    sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=KTRDR Training Host Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_ROOT/training-host-service
Environment=PYTHONPATH=$PROJECT_ROOT
ExecStart=$(which uv) run python main.py
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_ROOT/logs/training-host-service.log
StandardError=append:$PROJECT_ROOT/logs/training-host-service-error.log

[Install]
WantedBy=default.target
EOF

    # Enable and start service
    systemctl --user daemon-reload
    systemctl --user enable ktrdr-training-host.service
    systemctl --user start ktrdr-training-host.service
    
    echo "Training host service installed and started"
}

# Create log directory
mkdir -p "$PROJECT_ROOT/logs"

# Detect OS and install appropriate service
if [[ "$OSTYPE" == "darwin"* ]]; then
    install_macos
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    install_linux
else
    echo "Unsupported OS: $OSTYPE"
    exit 1
fi
```

### 3.5 Configuration Management

#### Purpose
Harmonize configuration patterns between IB and training host services while maintaining compatibility with existing KTRDR configuration system.

#### Configuration Structure
```
config/
├── training_host_service.yaml          # Primary service configuration
├── environment/
│   └── training_host_service_enabled.yaml  # Environment toggle
└── settings.yaml                       # Integration settings (updated)
```

#### Service Configuration
```yaml
# config/training_host_service.yaml
host_service:
  host: "127.0.0.1"
  port: 5002
  log_level: "INFO"
  workers: 1

gpu:
  memory_fraction: 0.9
  enable_mixed_precision: true
  enable_memory_pooling: true
  enable_profiling: true
  cleanup_threshold_mb: 100

training:
  max_concurrent_jobs: 2
  progress_update_interval: 1.0
  model_storage_path: "../models"
  analytics_storage_path: "../training_analytics"

monitoring:
  health_check_interval: 30
  metrics_enabled: true
  prometheus_port: 9092
```

#### Docker Integration Configuration
```yaml
# config/environment/training_host_service_enabled.yaml
training_host_service:
  enabled: true
  url: "http://host.docker.internal:5002"
  timeout_seconds: 30
  health_check_interval: 10
  circuit_breaker:
    failure_threshold: 3
    recovery_timeout_seconds: 60
    half_open_retry_interval: 30

# Also update IB service for consistency
ib_host_service:
  enabled: true
  url: "http://host.docker.internal:5001"
  timeout_seconds: 30
  health_check_interval: 10
  circuit_breaker:
    failure_threshold: 3
    recovery_timeout_seconds: 60
    half_open_retry_interval: 30
```

### 3.6 Health Monitoring and Observability

#### Purpose
Extend existing monitoring infrastructure to include training host service with GPU-specific metrics and status tracking.

#### Health Check Endpoints
```python
# training_host_service/endpoints/health.py
from fastapi import APIRouter, HTTPException
from ktrdr.training.gpu_memory_manager import GPUMemoryManager

router = APIRouter()

@router.get("/health")
async def health_check():
    """Basic health check for load balancer."""
    try:
        # Quick GPU check
        gpu_available = torch.cuda.is_available() or torch.backends.mps.is_available()
        
        return {
            "status": "healthy",
            "service": "training-host-service",
            "gpu_available": gpu_available,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {e}")

@router.get("/health/detailed")
async def detailed_health_check():
    """Comprehensive health check with GPU details."""
    try:
        gpu_summary = gpu_service.gpu_manager.get_memory_summary()
        
        return {
            "status": "healthy",
            "service": "training-host-service",
            "version": "1.0.0",
            "uptime_seconds": get_uptime(),
            "gpu": gpu_summary,
            "active_trainings": len(training_service.get_active_jobs()),
            "memory_usage": get_memory_usage(),
            "disk_usage": get_disk_usage(),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.exception("Health check failed")
        raise HTTPException(status_code=503, detail=f"Detailed health check failed: {e}")
```

#### Metrics Integration
```python
# Prometheus metrics for GPU training service
from prometheus_client import Counter, Histogram, Gauge

# Training metrics
training_requests_total = Counter(
    'training_requests_total',
    'Total training requests',
    ['method', 'endpoint', 'status']
)

training_duration_seconds = Histogram(
    'training_duration_seconds',
    'Training duration in seconds',
    ['symbol', 'timeframe', 'model_type']
)

# GPU metrics
gpu_memory_usage_bytes = Gauge(
    'gpu_memory_usage_bytes',
    'GPU memory usage in bytes',
    ['device_id', 'type']  # type: allocated, reserved, total
)

gpu_utilization_percent = Gauge(
    'gpu_utilization_percent',
    'GPU utilization percentage',
    ['device_id']
)

gpu_temperature_celsius = Gauge(
    'gpu_temperature_celsius',
    'GPU temperature in Celsius',
    ['device_id']
)
```

### 3.7 Integration Testing Strategy

#### Purpose
Ensure seamless integration between host service, Docker environment, and existing training infrastructure.

#### Test Categories

**Integration Tests**
```python
# tests/integration/test_host_service_integration.py
import pytest
import httpx
from ktrdr.api.endpoints.training import start_training

class TestTrainingHostServiceIntegration:
    """Test integration between Docker API and host service."""
    
    @pytest.mark.asyncio
    async def test_training_request_routing(self):
        """Test that training requests route correctly to host service."""
        # Test with host service enabled
        with override_settings(use_training_host_service=True):
            response = await start_training(
                symbol="AAPL",
                timeframe="1h",
                config={"epochs": 10}
            )
            assert response["routed_to"] == "host_service"
    
    @pytest.mark.asyncio
    async def test_fallback_to_docker(self):
        """Test automatic fallback when host service unavailable."""
        # Simulate host service down
        with mock_host_service_down():
            response = await start_training(
                symbol="AAPL",
                timeframe="1h",
                config={"epochs": 10}
            )
            assert response["routed_to"] == "docker"
    
    async def test_gpu_acceleration_enabled(self):
        """Verify GPU acceleration is active in host service."""
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:5002/gpu/status")
            gpu_status = response.json()
            
            if torch.cuda.is_available() or torch.backends.mps.is_available():
                assert gpu_status["gpu_available"] is True
                assert len(gpu_status["devices"]) > 0
```

**GPU Performance Tests**
```python
# tests/gpu/test_performance_improvement.py
import time
import torch
from ktrdr.training.gpu_memory_manager import GPUMemoryManager

class TestGPUPerformanceImprovement:
    """Validate GPU acceleration provides expected performance gains."""
    
    def test_gpu_vs_cpu_training_speed(self):
        """Measure training speed improvement with GPU."""
        model = create_test_model()
        sample_data = create_test_data(batch_size=128)
        
        # CPU training
        start_time = time.time()
        cpu_result = train_on_cpu(model, sample_data)
        cpu_duration = time.time() - start_time
        
        # GPU training (if available)
        if torch.cuda.is_available() or torch.backends.mps.is_available():
            start_time = time.time()
            gpu_result = train_on_gpu(model, sample_data)
            gpu_duration = time.time() - start_time
            
            speedup = cpu_duration / gpu_duration
            assert speedup >= 2.0, f"Expected 2x speedup, got {speedup:.2f}x"
        
    def test_memory_management_efficiency(self):
        """Test GPU memory management prevents OOM errors."""
        gpu_manager = GPUMemoryManager()
        
        with gpu_manager.memory_efficient_context():
            # Train larger model that would cause OOM without management
            large_model = create_large_test_model()
            large_dataset = create_large_test_data()
            
            # Should complete without OOM
            result = train_model(large_model, large_dataset)
            assert result["status"] == "completed"
```

---

## 4. Implementation Plan

### 4.1 Development Phases

**Phase 1: Service Extraction (Week 1)**
```bash
# Create training host service structure
mkdir training-host-service
cd training-host-service

# Initialize FastAPI service following IB pattern
mkdir -p {endpoints,services,scripts,tests}
touch main.py config.py

# Copy IB service patterns and adapt for training
cp ../ib-host-service/main.py ./main.py
cp ../ib-host-service/config.py ./config.py
# Adapt for training endpoints
```

**Phase 2: API Integration (Week 2)**
```python
# Modify existing training API to support routing
# ktrdr/api/endpoints/training.py

async def route_to_host_or_docker(request_data):
    """Route training requests based on configuration."""
    settings = get_settings()
    
    if settings.use_training_host_service:
        try:
            return await call_host_service(request_data)
        except Exception:
            logger.warning("Host service unavailable, using Docker")
    
    return await existing_docker_training(request_data)
```

**Phase 3: Auto-Startup Implementation (Week 3)**
```bash
# Install service management
./training-host-service/scripts/install_service.sh

# Update IB service for auto-startup
./ib-host-service/scripts/install_service.sh

# Test startup sequence
sudo reboot
# Verify both services start automatically
```

### 4.2 Configuration Updates

**Environment Configuration**
```bash
# Enable training host service
cp config/environment/training_host_service_enabled.yaml config/environment/local.yaml

# Update Docker compose for host service access
# docker-compose.yml
```

**Service Configuration**
```yaml
# config/training_host_service.yaml
host_service:
  host: "127.0.0.1"
  port: 5002
  log_level: "INFO"

gpu:
  memory_fraction: 0.9
  enable_mixed_precision: true
  enable_memory_pooling: true

training:
  max_concurrent_jobs: 2
  analytics_enabled: true
```

### 4.3 Testing and Validation

**Integration Testing**
```bash
# Test host service startup
./training-host-service/scripts/start.sh

# Test GPU acceleration
curl http://localhost:5002/gpu/status

# Test training request routing
curl -X POST http://localhost:8000/api/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "timeframe": "1h"}'

# Verify fallback behavior
./training-host-service/scripts/stop.sh
# Repeat training request - should fallback to Docker
```

**Performance Validation**
```bash
# Run performance benchmarks
uv run pytest tests/gpu/test_performance_improvement.py -v

# Monitor GPU utilization during training
watch -n 1 nvidia-smi  # NVIDIA
sudo powermetrics --show-process-gpu  # Apple Silicon
```

### 4.4 Deployment Checklist

**Pre-Deployment**
- [ ] Training host service starts successfully
- [ ] GPU acceleration confirmed working
- [ ] API routing logic tested
- [ ] Fallback behavior validated
- [ ] Auto-startup configured and tested
- [ ] Health checks returning correctly

**Post-Deployment**
- [ ] Both host services auto-start on reboot
- [ ] Training requests route to host service
- [ ] GPU metrics visible in monitoring
- [ ] Performance improvement confirmed (3x+ speedup)
- [ ] Existing workflows unchanged
- [ ] Error handling and fallback working

### 4.5 Rollback Strategy

**Immediate Rollback**
```bash
# Disable training host service
export USE_TRAINING_HOST_SERVICE=false
docker-compose restart backend

# Stop host service if needed
./training-host-service/scripts/stop.sh
```

**Complete Rollback**
```bash
# Uninstall service management
./training-host-service/scripts/uninstall_service.sh

# Remove configuration
rm config/environment/training_host_service_enabled.yaml

# Restart Docker environment
docker-compose down && docker-compose up -d
```

---

## 5. Expected Outcomes

### 5.1 Performance Improvements
- **Training Speed**: 3-5x improvement using existing GPU acceleration
- **Throughput**: 2-3x more experiments per day due to faster execution
- **Resource Utilization**: 80%+ GPU utilization during training
- **Memory Efficiency**: Optimal batch sizes via existing GPU memory management

### 5.2 Operational Benefits
- **Zero Disruption**: No changes to existing CLI, frontend, or workflows
- **Automatic Management**: Both host services start/restart automatically
- **Transparent Operation**: Seamless fallback to Docker when needed
- **Enhanced Monitoring**: GPU metrics integrated into existing observability

### 5.3 Technical Achievements
- **Code Reuse**: 100% reuse of existing GPU and training code
- **Pattern Consistency**: Aligned with proven IB host service architecture
- **Backward Compatibility**: Full support for Docker-only operation
- **Service Reliability**: Auto-recovery and health monitoring

### 5.4 Future Extensibility
- **Multi-GPU Support**: Framework ready for multiple GPU utilization
- **Distributed Training**: Foundation for cross-machine training
- **Model Serving**: Pattern established for GPU-accelerated inference
- **Research Acceleration**: Faster iteration cycles for algorithm development

The architecture delivers GPU acceleration through service extraction rather than reimplementation, ensuring rapid deployment while maintaining system reliability and extensibility.