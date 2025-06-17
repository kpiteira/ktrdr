# ADR-006: Deployment Evolution Plan

## Status
**Draft** - December 2024

## Context
KTRDR currently runs as a Docker-based development environment with three containers (backend, frontend, MCP server). As the system matures, we need to evolve the deployment architecture to support:

- Self-hosted deployment on Proxmox cluster
- Distributed training and backtesting workloads
- Enhanced security for Interactive Brokers integration
- Scalable architecture without unnecessary complexity
- Research automation through MCP (Model Context Protocol) server

The key principle is **progressive enhancement** - start simple and add complexity only when needed.

## Decision

### Deployment Evolution Phases

We will evolve the deployment in four phases, each building on the previous one:

```
Phase 1: Single VM Deployment (Current + Improvements)
Phase 2: Service Separation with Basic Distribution
Phase 3: Distributed Workloads with Job Queue
Phase 4: Full Production Architecture (Future)
```

## Phase 1: Single VM Deployment (Immediate)

### Overview
Deploy the current Docker setup to a single Proxmox VM with improved production configuration and basic monitoring.

### Architecture
```
┌─────────────────────── Proxmox VM ───────────────────────┐
│                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │   Frontend   │  │   Backend   │  │  MCP Server │      │
│  │  (nginx/React)│  │  (FastAPI)  │  │  (Research) │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                  │                  │           │
│  ┌──────┴──────────────────┴──────────────────┴───────┐  │
│  │              Docker Network (Bridge)                │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │ PostgreSQL  │  │    Redis    │  │   Traefik   │      │
│  │  Database   │  │   Cache     │  │ Rev. Proxy  │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
│                                                           │
│  Volumes: /data  /logs  /models  /strategies             │
└───────────────────────────────────────────────────────────┘
```

### Implementation Steps

#### 1.1 Infrastructure Setup
```bash
# Proxmox VM Specifications
- OS: Ubuntu 22.04 LTS
- CPU: 8 cores
- RAM: 16GB
- Storage: 500GB SSD
- Network: Bridge mode with static IP
```

#### 1.2 Docker Compose Production Config
```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  traefik:
    image: traefik:v3.0
    container_name: ktrdr-traefik
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"  # Dashboard
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik:/etc/traefik
      - traefik-certs:/certs
    networks:
      - ktrdr-network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.dashboard.rule=Host(`traefik.ktrdr.local`)"
      - "traefik.http.routers.dashboard.service=api@internal"

  postgres:
    image: timescale/timescaledb:latest-pg15
    container_name: ktrdr-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ktrdr
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./init-db:/docker-entrypoint-initdb.d
    networks:
      - ktrdr-network
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "${DB_USER}"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    container_name: ktrdr-redis
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis-data:/data
    networks:
      - ktrdr-network

  backend:
    image: ktrdr-backend:${VERSION:-latest}
    container_name: ktrdr-backend
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/ktrdr
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - IB_GATEWAY_HOST=${IB_GATEWAY_HOST}
      - IB_GATEWAY_PORT=${IB_GATEWAY_PORT}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./models:/app/models
      - ./strategies:/app/strategies
    depends_on:
      - postgres
      - redis
    networks:
      - ktrdr-network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.api.rule=Host(`api.ktrdr.local`)"
      - "traefik.http.services.api.loadbalancer.server.port=8000"

  frontend:
    image: ktrdr-frontend:${VERSION:-latest}
    container_name: ktrdr-frontend
    restart: unless-stopped
    networks:
      - ktrdr-network
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.web.rule=Host(`ktrdr.local`)"
      - "traefik.http.services.web.loadbalancer.server.port=80"

  mcp:
    image: ktrdr-mcp:${VERSION:-latest}
    container_name: ktrdr-mcp
    restart: "no"
    volumes:
      - ./data:/data:ro
      - ./strategies:/app/strategies:rw
      - ./models:/app/models:rw
      - mcp-experiments:/app/experiments:rw
    environment:
      - KTRDR_API_URL=http://backend:8000/api/v1
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/ktrdr
    networks:
      - ktrdr-network

networks:
  ktrdr-network:
    driver: bridge

volumes:
  postgres-data:
  redis-data:
  traefik-certs:
  mcp-experiments:
```

#### 1.3 Deployment Automation
```bash
#!/bin/bash
# deploy.sh - Simple deployment script

# Load environment variables
source .env.production

# Pull latest images
docker-compose -f docker-compose.prod.yml pull

# Run database migrations
docker-compose -f docker-compose.prod.yml run --rm backend python -m ktrdr.db.migrate

# Start services with rolling update
docker-compose -f docker-compose.prod.yml up -d

# Health check
./scripts/health-check.sh
```

#### 1.4 Monitoring Setup
```yaml
# monitoring/docker-compose.monitoring.yml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
    ports:
      - "3001:3000"

  node-exporter:
    image: prom/node-exporter:latest
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
```

### Key Improvements
- **PostgreSQL with TimescaleDB** for time-series data
- **Redis** for caching and job queuing (future)
- **Traefik** as reverse proxy with automatic SSL
- **Prometheus + Grafana** for monitoring
- **Proper secrets management** with .env files
- **Health checks** on all services
- **Automated backups** for data persistence

### Storage Architecture Explanation

#### Why Both Database and File Storage?

The system uses two complementary storage approaches for different types of data:

##### PostgreSQL/TimescaleDB (Structured Data)
**Purpose**: Fast, queryable structured data
- **Market data**: OHLCV time series with efficient time-range queries
- **Trade records**: Orders, executions, positions with ACID guarantees
- **Strategy metadata**: Configurations, performance metrics, experiment results
- **System state**: User sessions, API keys, audit logs

**Example queries enabled**:
```sql
-- Efficient time-series query
SELECT time, close, volume 
FROM market_data 
WHERE symbol = 'AAPL' 
  AND time >= '2024-01-01' 
  AND time < '2024-02-01'
  AND timeframe = '1h'
ORDER BY time;

-- Aggregate performance metrics
SELECT 
  strategy_name,
  AVG(sharpe_ratio) as avg_sharpe,
  MAX(total_return) as best_return,
  COUNT(*) as backtest_count
FROM backtest_results
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY strategy_name;
```

##### Shared File Storage (Binary/Unstructured Data) - Phase 2
**Purpose**: Large binary files and working directories
- **Trained models**: PyTorch .pt files (50-500MB per model)
- **Training checkpoints**: Intermediate states for resuming
- **Feature matrices**: Large NumPy arrays for training
- **Strategy definitions**: YAML files under version control
- **Logs**: Distributed application logs for debugging
- **Data exports**: CSV/Parquet files for external analysis

**Why not store these in the database?**
1. **Size**: Model files can be hundreds of MB - inefficient as DB blobs
2. **Access patterns**: ML frameworks expect file paths, not DB queries
3. **Performance**: Direct file I/O is faster for large binary data
4. **Flexibility**: Easy to manage with standard Unix tools

**Example workflow**:
```python
# Training service
def train_model(strategy_config):
    # 1. Load market data from PostgreSQL
    data = db.query("SELECT * FROM market_data WHERE ...")
    
    # 2. Save checkpoints to shared storage
    checkpoint_path = Path("/mnt/shared/checkpoints/model_epoch_10.pt")
    torch.save(model.state_dict(), checkpoint_path)
    
    # 3. Save final model to shared storage
    model_path = Path("/mnt/shared/models/strategy_v1.pt")
    torch.save(model, model_path)
    
    # 4. Record metadata in PostgreSQL
    db.execute("""
        INSERT INTO models (name, version, file_path, metrics)
        VALUES (%s, %s, %s, %s)
    """, (name, version, str(model_path), metrics))
```

This hybrid approach gives us the best of both worlds:
- **Database**: Fast queries, ACID compliance, structured relationships
- **File storage**: Efficient binary storage, direct file access, easy scaling

## Phase 2: Service Separation (3-6 months)

### Overview
Separate IB Gateway onto isolated VM with VLAN, introduce shared storage, and basic service distribution.

### Architecture
```
┌─────────────── Proxmox Cluster ───────────────────┐
│                                                    │
│  VM1: Frontend & API Services      VM2: IB Gateway│
│  ┌─────────────────────────┐      ┌──────────────┤
│  │ Traefik → Frontend      │      │ IB Gateway   │
│  │       ↓                 │      │ (VLAN 100)   │
│  │ API Gateway → Backend   │◄─────┤              │
│  │       ↓                 │ TLS  │ IB Connector │
│  │ Database & Redis        │      │ Service      │
│  └─────────────────────────┘      └──────────────┤
│                                                    │
│  VM3: Compute Services            Shared Storage  │
│  ┌─────────────────────────┐      ┌──────────────┤
│  │ Training Service        │      │ NFS/GlusterFS│
│  │ Backtesting Service     │◄─────┤ /data        │
│  │ MCP Server              │      │ /models      │
│  └─────────────────────────┘      └──────────────┤
└────────────────────────────────────────────────────┘
```

### Implementation Details

#### 2.1 Network Segmentation
```yaml
# Network Configuration
networks:
  public:
    # Frontend access
    vlan: 10
    subnet: 192.168.10.0/24
    
  services:
    # Internal services
    vlan: 20
    subnet: 192.168.20.0/24
    
  ib_secure:
    # IB Gateway isolation
    vlan: 100
    subnet: 192.168.100.0/24
    firewall_rules:
      - allow from services to ib_secure port 4003
      - deny all other
```

#### 2.2 IB Security Service
```python
# ib_security_service.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta
import logging

app = FastAPI(title="IB Security Gateway")
security = HTTPBearer()
audit_logger = logging.getLogger("ib_audit")

class IBSecurityGateway:
    """
    Security layer for IB Gateway access
    - Authentication via JWT
    - Authorization based on operation type
    - Full audit logging
    - Rate limiting
    """
    
    def __init__(self):
        self.ib_client = None  # Actual IB connection
        
    async def authenticate(self, credentials: HTTPAuthorizationCredentials):
        """Verify JWT token"""
        try:
            payload = jwt.decode(
                credentials.credentials,
                settings.JWT_SECRET,
                algorithms=["HS256"]
            )
            return payload
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
    
    async def authorize_operation(self, user: dict, operation: str):
        """Check if user can perform operation"""
        permissions = {
            "data_download": ["read", "admin"],
            "place_order": ["trade", "admin"],
            "modify_order": ["trade", "admin"],
            "cancel_order": ["trade", "admin"]
        }
        
        required_perms = permissions.get(operation, ["admin"])
        user_perms = user.get("permissions", [])
        
        if not any(perm in user_perms for perm in required_perms):
            audit_logger.warning(
                f"Unauthorized operation attempt: {user['id']} -> {operation}"
            )
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    async def audit_log(self, user: dict, operation: str, details: dict):
        """Log all IB operations"""
        audit_logger.info({
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user["id"],
            "operation": operation,
            "details": details,
            "ip_address": details.get("ip_address"),
            "result": details.get("result", "pending")
        })

@app.post("/api/ib/data/download")
async def download_data(
    request: DataDownloadRequest,
    user=Depends(gateway.authenticate)
):
    await gateway.authorize_operation(user, "data_download")
    await gateway.audit_log(user, "data_download", request.dict())
    # Actual IB operation
    result = await gateway.download_historical_data(request)
    return result

@app.post("/api/ib/orders/place")
async def place_order(
    request: OrderRequest,
    user=Depends(gateway.authenticate)
):
    await gateway.authorize_operation(user, "place_order")
    
    # Additional validation for orders
    if request.quantity > user.get("max_order_size", 1000):
        raise HTTPException(status_code=400, detail="Order size exceeds limit")
    
    await gateway.audit_log(user, "place_order", request.dict())
    # Actual IB operation with double confirmation
    result = await gateway.place_order_with_confirmation(request)
    return result
```

#### 2.3 Shared Storage Setup
```bash
# GlusterFS Setup for Shared Storage
# On each storage node:

# Install GlusterFS
apt-get install glusterfs-server

# Create storage directory
mkdir -p /data/glusterfs/ktrdr

# Create volume (from one node)
gluster volume create ktrdr-data replica 2 \
  node1:/data/glusterfs/ktrdr \
  node2:/data/glusterfs/ktrdr

# Start volume
gluster volume start ktrdr-data

# Mount on compute nodes
mount -t glusterfs node1:/ktrdr-data /mnt/ktrdr-data
```

**Directory Structure for Shared Storage**:
```
/mnt/ktrdr-data/
├── models/                 # Trained model files
│   ├── rsi_mean_reversion/
│   │   └── AAPL_1h_v1/
│   │       ├── model.pt    # 200MB PyTorch model
│   │       └── metadata.json
│   └── bollinger_squeeze/
├── checkpoints/           # Training checkpoints
│   └── training_20241215_142530/
│       ├── epoch_10.pt
│       ├── epoch_20.pt
│       └── best_model.pt
├── features/              # Prepared feature matrices
│   ├── AAPL_1h_features_2024.npz
│   └── MSFT_1h_features_2024.npz
├── exports/               # Data exports for research
│   ├── backtest_results_20241215.csv
│   └── correlation_matrix.parquet
├── strategies/            # Version-controlled YAML files
│   ├── production/
│   └── experimental/
└── logs/                  # Application logs
    ├── training/
    ├── backtesting/
    └── system/
```

#### 2.4 Service Distribution
```yaml
# docker-compose.compute.yml
services:
  training:
    image: ktrdr-backend:${VERSION}
    deploy:
      replicas: 2
      placement:
        constraints:
          - node.labels.type == compute
    environment:
      - SERVICE_MODE=training
      - SHARED_DATA_PATH=/mnt/ktrdr-data
    volumes:
      - /mnt/ktrdr-data:/data
      - ./models:/models
    command: ["python", "-m", "ktrdr.services.training"]

  backtesting:
    image: ktrdr-backend:${VERSION}
    deploy:
      replicas: 4  # More replicas for parallel backtesting
      placement:
        constraints:
          - node.labels.type == compute
    environment:
      - SERVICE_MODE=backtesting
      - SHARED_DATA_PATH=/mnt/ktrdr-data
    volumes:
      - /mnt/ktrdr-data:/data:ro
      - ./results:/results
    command: ["python", "-m", "ktrdr.services.backtesting"]
```

### Self-Hosted CI/CD Setup

#### Option 1: Gitea + Drone (Recommended for Simplicity)
```yaml
# gitea-drone/docker-compose.yml
services:
  gitea:
    image: gitea/gitea:latest
    environment:
      - USER_UID=1000
      - USER_GID=1000
      - GITEA__database__DB_TYPE=postgres
      - GITEA__database__HOST=postgres:5432
    volumes:
      - gitea-data:/data
    ports:
      - "3000:3000"
      - "2222:22"

  drone:
    image: drone/drone:2
    environment:
      - DRONE_GITEA_SERVER=http://gitea:3000
      - DRONE_GITEA_CLIENT_ID=${GITEA_CLIENT_ID}
      - DRONE_GITEA_CLIENT_SECRET=${GITEA_CLIENT_SECRET}
      - DRONE_RPC_SECRET=${DRONE_RPC_SECRET}
      - DRONE_SERVER_HOST=drone.ktrdr.local
      - DRONE_SERVER_PROTO=http
    volumes:
      - drone-data:/data
    ports:
      - "8081:80"

  drone-runner:
    image: drone/drone-runner-docker:1
    environment:
      - DRONE_RPC_PROTO=http
      - DRONE_RPC_HOST=drone
      - DRONE_RPC_SECRET=${DRONE_RPC_SECRET}
      - DRONE_RUNNER_CAPACITY=2
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

#### Drone Pipeline Example
```yaml
# .drone.yml
kind: pipeline
type: docker
name: ktrdr-deploy

steps:
  - name: test
    image: ktrdr-backend:test
    commands:
      - python -m pytest tests/

  - name: build
    image: plugins/docker
    settings:
      repo: registry.ktrdr.local/ktrdr-backend
      tags:
        - ${DRONE_COMMIT_SHA}
        - latest
      registry: registry.ktrdr.local

  - name: deploy
    image: appleboy/drone-ssh
    settings:
      host: ${DEPLOY_HOST}
      username: ${DEPLOY_USER}
      key:
        from_secret: deploy_ssh_key
      script:
        - cd /opt/ktrdr
        - docker-compose pull
        - docker-compose up -d

trigger:
  branch:
    - main
  event:
    - push
```

## Phase 3: Distributed Workloads (6-12 months)

### Overview
Introduce job queue for distributing training/backtesting workloads across multiple nodes.

### Architecture
```
┌────────────────── Job Distribution Layer ─────────────────┐
│                                                           │
│  API Gateway          Job Queue         Worker Pool      │
│  ┌─────────┐         ┌─────────┐       ┌─────────────┐  │
│  │ FastAPI │ ──────> │  Redis  │ <──── │ Celery      │  │
│  │         │         │ Streams │       │ Workers     │  │
│  └─────────┘         └─────────┘       └─────────────┘  │
│       │                                      │           │
│       └──────────────────┬───────────────────┘           │
│                          ▼                               │
│  ┌─────────────────────────────────────────────────────┐ │
│  │          Kubernetes Cluster (k3s)                   │ │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐            │ │
│  │  │Training │  │Backtest │  │ Data    │            │ │
│  │  │ Pod 1   │  │ Pod 1   │  │ Sync    │            │ │
│  │  └─────────┘  └─────────┘  └─────────┘            │ │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐            │ │
│  │  │Training │  │Backtest │  │ MCP     │            │ │
│  │  │ Pod 2   │  │ Pod 2   │  │ Server  │            │ │
│  │  └─────────┘  └─────────┘  └─────────┘            │ │
│  └─────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────┘
```

### Implementation with Celery

#### 3.1 Job Queue Setup
```python
# ktrdr/tasks/celery_app.py
from celery import Celery
from kombu import Queue
import os

app = Celery('ktrdr')

app.conf.update(
    broker_url=os.getenv('REDIS_URL'),
    result_backend=os.getenv('REDIS_URL'),
    
    # Task routing
    task_routes={
        'ktrdr.tasks.training.*': {'queue': 'training'},
        'ktrdr.tasks.backtesting.*': {'queue': 'backtesting'},
        'ktrdr.tasks.data.*': {'queue': 'data'}
    },
    
    # Queue definitions
    task_queues=(
        Queue('training', routing_key='training', priority=5),
        Queue('backtesting', routing_key='backtesting', priority=3),
        Queue('data', routing_key='data', priority=10),
    ),
    
    # Performance settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# ktrdr/tasks/training.py
from celery import Task
from ktrdr.training.train_strategy import StrategyTrainer

class TrainingTask(Task):
    """Base class for training tasks with progress tracking"""
    
    def __init__(self):
        self.trainer = None
        
    def run(self, strategy_config_path: str, symbol: str, **kwargs):
        # Initialize trainer
        self.trainer = StrategyTrainer(strategy_config_path)
        
        # Training with progress updates
        def progress_callback(epoch, total_epochs, metrics):
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': epoch,
                    'total': total_epochs,
                    'metrics': metrics
                }
            )
        
        # Run training
        result = self.trainer.train(
            symbol=symbol,
            progress_callback=progress_callback,
            **kwargs
        )
        
        return {
            'model_path': result['model_path'],
            'metrics': result['test_metrics']
        }

# Register task
train_strategy = app.register_task(TrainingTask())

# ktrdr/tasks/backtesting.py
@app.task(bind=True)
def run_backtest(self, backtest_config: dict):
    """Run backtesting with progress tracking"""
    engine = BacktestingEngine(BacktestConfig(**backtest_config))
    
    # Progress tracking
    def on_progress(current_bar, total_bars):
        self.update_state(
            state='PROGRESS',
            meta={
                'current': current_bar,
                'total': total_bars,
                'percentage': (current_bar / total_bars) * 100
            }
        )
    
    engine.set_progress_callback(on_progress)
    results = engine.run()
    
    return results.to_dict()
```

#### 3.2 Worker Deployment
```yaml
# k3s/ktrdr-workers.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: training-workers
spec:
  replicas: 2
  selector:
    matchLabels:
      app: training-worker
  template:
    metadata:
      labels:
        app: training-worker
    spec:
      containers:
      - name: worker
        image: ktrdr-backend:latest
        command: ["celery", "-A", "ktrdr.tasks", "worker", "-Q", "training", "-n", "training@%h"]
        env:
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: ktrdr-secrets
              key: redis-url
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
          limits:
            memory: "8Gi"
            cpu: "4"
        volumeMounts:
        - name: shared-data
          mountPath: /data
      volumes:
      - name: shared-data
        persistentVolumeClaim:
          claimName: ktrdr-shared-data

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backtesting-workers
spec:
  replicas: 4  # More workers for parallel backtesting
  selector:
    matchLabels:
      app: backtesting-worker
  template:
    metadata:
      labels:
        app: backtesting-worker
    spec:
      containers:
      - name: worker
        image: ktrdr-backend:latest
        command: ["celery", "-A", "ktrdr.tasks", "worker", "-Q", "backtesting", "-n", "backtest@%h"]
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
```

#### 3.3 MCP Server Integration
```python
# mcp/research_coordinator.py
class ResearchCoordinator:
    """
    Coordinates research activities through MCP
    Launches multiple training and backtesting jobs
    """
    
    def __init__(self):
        self.celery_app = celery_app
        self.results_db = ExperimentDatabase()
    
    async def run_strategy_experiment(self, strategy_config: dict):
        """
        Full research pipeline:
        1. Train model on primary instrument
        2. Backtest on multiple instruments
        3. Analyze results
        4. Document findings
        """
        # Launch training
        training_task = train_strategy.delay(
            strategy_config_path=strategy_config['path'],
            symbol=strategy_config['primary_symbol']
        )
        
        # Wait for training completion
        training_result = training_task.get(timeout=3600)
        
        # Launch parallel backtests
        backtest_tasks = []
        for symbol in strategy_config['test_symbols']:
            task = run_backtest.delay({
                'model_path': training_result['model_path'],
                'symbol': symbol,
                'timeframe': strategy_config['timeframe'],
                'start_date': strategy_config['test_start'],
                'end_date': strategy_config['test_end']
            })
            backtest_tasks.append((symbol, task))
        
        # Collect results
        backtest_results = {}
        for symbol, task in backtest_tasks:
            result = task.get(timeout=1800)
            backtest_results[symbol] = result
        
        # Analyze and store
        analysis = self.analyze_results(training_result, backtest_results)
        self.results_db.store_experiment(strategy_config, analysis)
        
        return analysis
```

### Data Synchronization Strategy

#### 3.4 Distributed Data Management
```python
# ktrdr/data/distributed_manager.py
class DistributedDataManager:
    """
    Manages data across distributed nodes
    Uses Redis for coordination and GlusterFS for storage
    """
    
    def __init__(self):
        self.redis = Redis.from_url(os.getenv('REDIS_URL'))
        self.data_path = Path('/mnt/ktrdr-data')
        self.db = DatabaseConnection()  # PostgreSQL connection
        
    async def sync_market_data(self, symbol: str, timeframe: str):
        """Ensures all nodes have latest data"""
        
        # Acquire distributed lock
        lock = self.redis.lock(f"data_sync:{symbol}:{timeframe}", timeout=300)
        
        try:
            if lock.acquire(blocking=False):
                # Check if update needed
                last_update = self.get_last_update(symbol, timeframe)
                if self.needs_update(last_update):
                    # Download new data
                    new_data = await self.download_from_ib(symbol, timeframe)
                    
                    # Write to PostgreSQL for structured queries
                    await self.db.insert_market_data(symbol, timeframe, new_data)
                    
                    # Export to shared storage for ML processing
                    export_path = self.data_path / f"exports/{symbol}_{timeframe}_latest.parquet"
                    new_data.to_parquet(export_path)
                    
                    # Update metadata
                    self.redis.set(
                        f"data_updated:{symbol}:{timeframe}",
                        datetime.utcnow().isoformat()
                    )
                    
                    # Publish update event
                    self.redis.publish('data_updates', json.dumps({
                        'symbol': symbol,
                        'timeframe': timeframe,
                        'timestamp': datetime.utcnow().isoformat()
                    }))
        finally:
            if lock.owned():
                lock.release()
    
    def save_model(self, model: torch.nn.Module, metadata: dict) -> str:
        """
        Save model to shared storage and register in database
        """
        # Generate unique model path
        model_id = str(uuid.uuid4())
        model_path = self.data_path / f"models/{metadata['strategy']}/{metadata['symbol']}_{metadata['timeframe']}_v{metadata['version']}/model.pt"
        
        # Ensure directory exists
        model_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to shared storage
        torch.save({
            'model_state_dict': model.state_dict(),
            'model_config': metadata['model_config'],
            'feature_names': metadata['feature_names'],
            'timestamp': datetime.utcnow().isoformat()
        }, model_path)
        
        # Register in database
        self.db.execute("""
            INSERT INTO models (id, strategy_name, symbol, timeframe, version, 
                              file_path, metrics, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (model_id, metadata['strategy'], metadata['symbol'], 
              metadata['timeframe'], metadata['version'], 
              str(model_path), json.dumps(metadata['metrics']), 
              datetime.utcnow()))
        
        return model_id
    
    def load_model(self, model_id: str) -> Tuple[torch.nn.Module, dict]:
        """
        Load model from shared storage using database metadata
        """
        # Get model info from database
        model_info = self.db.query_one(
            "SELECT file_path, strategy_name FROM models WHERE id = %s", 
            model_id
        )
        
        # Load from shared storage
        model_data = torch.load(model_info['file_path'])
        
        # Reconstruct model
        model = self.create_model_from_config(model_data['model_config'])
        model.load_state_dict(model_data['model_state_dict'])
        
        return model, model_data
```

### Storage Decision Matrix

| Data Type | Storage Location | Reason | Example Size |
|-----------|-----------------|---------|--------------|
| OHLCV Market Data | PostgreSQL | Fast time-series queries, aggregations | ~100KB per symbol-day |
| Trade Records | PostgreSQL | ACID compliance, relational queries | ~1KB per trade |
| Model Files (.pt) | Shared FS | Large binaries, direct ML framework access | 50-500MB per model |
| Training Checkpoints | Shared FS | Temporary large files, resume capability | 100MB+ per checkpoint |
| Feature Matrices | Shared FS | Large arrays, batch processing | 1-10GB per dataset |
| Strategy YAMLs | Shared FS + Git | Version control, easy editing | <10KB per file |
| Backtest Results | PostgreSQL | Structured queries, performance analytics | ~10KB per backtest |
| Detailed Logs | Shared FS | Large text files, grep/tail access | 10-100MB per day |
| System Metrics | PostgreSQL | Time-series analysis, alerting | ~1KB per metric |

## Phase 4: Production Architecture (Future)

### Overview
Full production setup with auto-scaling, advanced monitoring, and disaster recovery.

### Advanced Features (When Needed)
- **Kubernetes with HPA** (Horizontal Pod Autoscaler)
- **Service Mesh** (Istio) for advanced traffic management
- **Distributed Tracing** (Jaeger)
- **GitOps** with ArgoCD
- **Multi-region backup** with automated failover
- **ML Model Registry** (MLflow)
- **A/B Testing** for strategies

## Implementation Roadmap

### Immediate Actions (Phase 1)
1. Set up Proxmox VM with Ubuntu 22.04
2. Migrate to PostgreSQL/TimescaleDB
3. Implement Traefik reverse proxy
4. Set up basic monitoring with Prometheus/Grafana
5. Create deployment scripts

### 3-Month Goals (Phase 2)
1. Separate IB Gateway to isolated VM
2. Implement IB security service
3. Set up shared storage (GlusterFS)
4. Deploy Gitea + Drone for CI/CD
5. Basic service distribution

### 6-Month Goals (Phase 3)
1. Implement Celery job queue
2. Deploy k3s for container orchestration
3. Set up distributed workers
4. Enhanced MCP research automation
5. Comprehensive monitoring

## Key Design Decisions

### 1. Technology Choices
- **k3s over k8s**: Lighter weight, easier to manage
- **GlusterFS**: Simple distributed storage
- **Celery + Redis**: Proven job queue solution
- **Gitea + Drone**: Self-hosted, lightweight CI/CD
- **TimescaleDB**: Optimized for time-series data

### 2. Security Principles
- **Network segmentation**: VLANs for isolation
- **Zero-trust**: All services authenticate
- **Audit everything**: Especially IB operations
- **Least privilege**: Minimal permissions
- **Secrets management**: Never in code

### 3. Simplicity First
- Start with docker-compose, evolve to k3s
- Use managed solutions where possible
- Automate gradually
- Monitor before optimizing
- Document everything

## Monitoring and Observability

### Metrics to Track
```yaml
# Key Performance Indicators
system:
  - CPU, Memory, Disk usage
  - Network throughput
  - Container health

application:
  - API response times
  - Training job duration
  - Backtest performance
  - Data sync latency

business:
  - Models trained per day
  - Backtests completed
  - Strategy performance
  - System availability
```

### Alerting Rules
```yaml
# Prometheus alerting rules
groups:
  - name: ktrdr_alerts
    rules:
      - alert: HighMemoryUsage
        expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.9
        for: 5m
        
      - alert: IBConnectionLost
        expr: ib_gateway_connected == 0
        for: 1m
        annotations:
          severity: critical
          
      - alert: DataSyncDelayed
        expr: time() - data_last_sync_timestamp > 3600
        for: 10m
```

## Disaster Recovery

### Backup Strategy
```bash
#!/bin/bash
# backup.sh - Daily backup script

# Database backup
docker exec ktrdr-postgres pg_dump -U $DB_USER ktrdr | \
  gzip > /backup/db/ktrdr_$(date +%Y%m%d).sql.gz

# Data files backup
rsync -av /mnt/ktrdr-data/ /backup/data/

# Models backup
rsync -av /app/models/ /backup/models/

# Rotate old backups
find /backup -name "*.gz" -mtime +30 -delete
```

### Recovery Procedures
1. **Database**: Restore from latest SQL dump
2. **Data files**: Rsync from backup location
3. **Models**: Restore trained models
4. **Configuration**: Git pull latest configs

## Cost Optimization

### Resource Allocation
- **Phase 1**: Single VM (8 CPU, 16GB RAM) ~$50/month
- **Phase 2**: 3 VMs + storage ~$150/month
- **Phase 3**: 5-7 VMs with k3s ~$300/month
- **Phase 4**: Auto-scaling cluster ~$500+/month

### Optimization Strategies
1. Use spot instances for training
2. Schedule intensive jobs during off-peak
3. Implement resource quotas
4. Regular cleanup of old data
5. Compress historical data

## Conclusion

This deployment evolution plan provides a **practical path** from the current development setup to a production-ready distributed system. Each phase builds on the previous one, allowing you to:

1. **Start simple** with a single VM deployment
2. **Add security** with network isolation for IB
3. **Scale horizontally** with job distribution
4. **Evolve to production** when needed

The key is **incremental improvement** - implement what you need when you need it, always keeping simplicity as a guiding principle.