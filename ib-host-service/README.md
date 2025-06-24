# IB Host Service

Host-based IB Gateway connector that resolves Docker networking issues while providing stable, direct connectivity to Interactive Brokers Gateway.

## Quick Start

```bash
# Start the service
./start.sh

# Verify it's working
curl http://localhost:5001/health
```

## Directory Structure

```
ib-host-service/
├── README.md                 # This file
├── main.py                   # FastAPI application entry point
├── config.yaml              # Service configuration
├── start.sh                  # Service startup script
├── endpoints/                # API endpoints
│   ├── __init__.py
│   ├── data.py              # Data fetching endpoints
│   └── health.py            # Health check endpoints
├── scripts/                  # Operational scripts
│   ├── monitor-stability.sh          # 24-hour stability test
│   └── check-stability-progress.sh   # Monitor test progress
└── tests/                    # Testing scripts
    ├── validate-integration.sh       # Quick validation
    ├── test-real-ib-gateway.sh      # Real IB Gateway tests
    └── test-monitoring.sh           # Test monitoring system
```

## Scripts Usage

### Testing & Validation

```bash
# Quick integration validation
./tests/validate-integration.sh

# Comprehensive real IB Gateway test
./tests/test-real-ib-gateway.sh

# Test monitoring system
./tests/test-monitoring.sh
```

### Monitoring & Operations

```bash
# Start 24-hour stability test
./scripts/monitor-stability.sh

# Check stability test progress
./scripts/check-stability-progress.sh

# View live stability logs
tail -f ../stability-test.log
```

## API Endpoints

### Health & Status
- `GET /` - Service information
- `GET /health` - Basic health check
- `GET /health/detailed` - Comprehensive status

### Data Operations
- `POST /data/historical` - Fetch historical OHLCV data
- `POST /data/validate` - Validate symbol
- `GET /data/head-timestamp` - Get earliest data timestamp

## Configuration

The service uses `config.yaml` for configuration:

```yaml
ib:
  host: "127.0.0.1"
  port: 4002
  client_id_range:
    min: 1
    max: 999
  timeout: 30

service:
  host: "127.0.0.1"
  port: 5001
  log_level: "INFO"
```

## Backend Integration

To enable backend integration with this host service:

### Option 1: Environment Variable
```bash
USE_IB_HOST_SERVICE=true docker-compose up backend -d
```

### Option 2: Configuration File
Edit `config/settings.yaml`:
```yaml
ib_host_service:
  enabled: true
  url: "http://localhost:5001"
```

## Monitoring

### Service Health
```bash
# Basic health
curl http://localhost:5001/health

# Detailed status with IB Gateway connection info
curl http://localhost:5001/health/detailed
```

### Performance Metrics
- Response times typically < 10ms
- Memory usage typically < 1%
- Zero errors expected during normal operation

## Troubleshooting

### Service Won't Start
```bash
# Check port availability
lsof -i :5001

# Check IB Gateway connectivity
telnet localhost 4002

# Check logs
tail -20 ../stability-monitor-output.log
```

### IB Gateway Connection Issues
```bash
# Verify IB Gateway is running
lsof -i :4002

# Test direct connection
curl -X POST http://localhost:5001/data/historical \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "timeframe": "1d", "start": "2025-06-22T00:00:00Z", "end": "2025-06-23T23:59:59Z"}'
```

### Backend Integration Issues
```bash
# Check backend environment
docker exec ktrdr-backend env | grep IB

# Test backend-to-host connectivity
docker exec ktrdr-backend curl http://host.docker.internal:5001/health

# Check backend IB status
curl http://localhost:8000/api/v1/ib/status
```

## Development

### Adding New Endpoints
1. Create endpoint in `endpoints/` directory
2. Import and include router in `main.py`
3. Add tests in `tests/` directory
4. Update documentation

### Testing Changes
```bash
# Run all validation tests
./tests/validate-integration.sh
./tests/test-real-ib-gateway.sh

# Test with real IB Gateway
./tests/test-real-ib-gateway.sh
```

## Production Deployment

### Prerequisites
- IB Gateway running on port 4002
- Python environment with required dependencies
- Network access between Docker containers and host

### Startup
```bash
# Start service
./start.sh

# Enable backend integration
USE_IB_HOST_SERVICE=true docker-compose up backend -d

# Validate deployment
./tests/validate-integration.sh
```

### Monitoring
```bash
# Start long-term monitoring
./scripts/monitor-stability.sh

# Check progress
./scripts/check-stability-progress.sh
```

### Emergency Rollback
```bash
# Disable host service mode
USE_IB_HOST_SERVICE=false docker-compose up backend -d

# Rollback time: < 30 seconds
```

---

## Architecture

This service provides a bridge between Docker containers and IB Gateway, resolving networking issues while maintaining system reliability:

```
IB Gateway (4002) ←→ IB Host Service (5001) ←→ Docker Backend (8000)
     ↑                      ↑                         ↑
  Direct TCP         FastAPI HTTP            Docker Network
```

**Key Benefits:**
- ✅ Eliminates Docker networking issues
- ✅ Maintains direct IB Gateway connectivity  
- ✅ Provides HTTP API for easy integration
- ✅ Enables fast rollback capability
- ✅ Supports comprehensive monitoring