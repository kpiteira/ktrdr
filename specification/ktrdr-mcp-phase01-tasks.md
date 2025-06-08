# KTRDR MCP Server - Phase 0 & 1 Detailed Task Breakdown

## Overview
This document provides a step-by-step implementation guide for Phase 0 (Foundation) and Phase 1 (Core Research Tools) of the KTRDR MCP Server.

## Development Setup

### Prerequisites
- [ ] Working KTRDR development environment
- [ ] Docker and docker-compose installed
- [ ] Claude Desktop app installed
- [ ] Python 3.11+ available

### Initial Git Setup
```bash
# Create parallel development directory
mkdir -p ~/Documents/dev/ktrdr2-mcp
cd ~/Documents/dev/ktrdr2-mcp

# Clone repository
git clone [your-repo-url] .

# Create MCP feature branch
git checkout -b feature/mcp-server

# Create phase 0 branch
git checkout -b feature/mcp-phase-0-foundation
```

---

## Phase 0: Foundation Setup (Week 1)

### Task 0.1: Create MCP Directory Structure
**Time Estimate**: 30 minutes

```bash
# Create MCP directory structure
mkdir -p mcp/src/tools
mkdir -p mcp/src/storage
mkdir -p mcp/tests
mkdir -p mcp/config
```

**Files to create**:
- [ ] `mcp/__init__.py`
- [ ] `mcp/src/__init__.py`
- [ ] `mcp/src/tools/__init__.py`
- [ ] `mcp/src/storage/__init__.py`
- [ ] `mcp/README.md`

### Task 0.2: Set Up MCP Dependencies
**Time Estimate**: 1 hour

Create `mcp/requirements.txt`:
```txt
# MCP SDK
mcp>=0.1.0

# Async support
aiohttp>=3.9.0
asyncio>=3.4.3

# API client
httpx>=0.25.0

# Database
aiosqlite>=0.19.0
sqlalchemy>=2.0.0

# Utilities
pydantic>=2.0.0
python-dotenv>=1.0.0
structlog>=23.0.0
pyyaml>=6.0

# Development
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-cov>=4.0.0
black>=23.0.0
mypy>=1.0.0
```

### Task 0.3: Create Basic MCP Server
**Time Estimate**: 2 hours

Create `mcp/src/server.py`:
```python
"""KTRDR MCP Server - Main entry point"""
import asyncio
from typing import Any, Dict
from mcp import Server, Tool
from mcp.server.stdio import stdio_server
import structlog

logger = structlog.get_logger()

class KTRDRMCPServer:
    """MCP Server for KTRDR trading strategy research"""
    
    def __init__(self):
        self.server = Server("ktrdr-mcp")
        self.setup_tools()
        logger.info("KTRDR MCP Server initialized")
    
    def setup_tools(self):
        """Register all available tools"""
        # Phase 0: Just a test tool
        self.server.add_tool(self.create_hello_tool())
    
    def create_hello_tool(self) -> Tool:
        """Test tool to verify MCP connectivity"""
        return Tool(
            name="hello_ktrdr",
            description="Test tool to verify MCP server is working",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name to greet"
                    }
                },
                "required": ["name"]
            },
            handler=self.handle_hello
        )
    
    async def handle_hello(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle hello test request"""
        name = params.get("name", "World")
        logger.info("Hello tool called", name=name)
        return {
            "message": f"Hello {name}! KTRDR MCP Server is working.",
            "version": "0.1.0",
            "status": "connected"
        }
    
    async def run(self):
        """Run the MCP server"""
        logger.info("Starting KTRDR MCP Server")
        async with stdio_server() as streams:
            await self.server.run(
                streams[0],  # stdin
                streams[1],  # stdout
                self.setup_tools()
            )
```

Create `mcp/src/main.py`:
```python
"""Entry point for MCP server"""
import asyncio
import sys
from .server import KTRDRMCPServer
from .config import setup_logging

def main():
    """Main entry point"""
    setup_logging()
    
    try:
        server = KTRDRMCPServer()
        asyncio.run(server.run())
    except KeyboardInterrupt:
        print("\nShutting down MCP server...")
        sys.exit(0)
    except Exception as e:
        print(f"Error running MCP server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Task 0.4: Create Configuration Module
**Time Estimate**: 1 hour

Create `mcp/src/config.py`:
```python
"""Configuration for MCP server"""
import os
from pathlib import Path
import structlog
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Paths
ROOT_DIR = Path(__file__).parent.parent.parent  # Project root
MCP_DIR = ROOT_DIR / "mcp"
DATA_DIR = ROOT_DIR / "data"
MODELS_DIR = ROOT_DIR / "models"
STRATEGIES_DIR = ROOT_DIR / "strategies"

# API Configuration
KTRDR_API_URL = os.getenv("KTRDR_API_URL", "http://backend:8000/api/v1")
KTRDR_API_KEY = os.getenv("KTRDR_API_KEY", "")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))

# Storage Configuration
EXPERIMENT_DB_PATH = os.getenv(
    "EXPERIMENT_DB_PATH", 
    str(MCP_DIR / "experiments.db")
)

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

def setup_logging():
    """Configure structured logging"""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

### Task 0.5: Create Dockerfile for MCP
**Time Estimate**: 1 hour

Create `mcp/Dockerfile`:
```dockerfile
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Runtime stage
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Create non-root user
RUN useradd -m -u 1000 ktrdr && \
    mkdir -p /app/experiments /app/logs && \
    chown -R ktrdr:ktrdr /app

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app /app

# Health check endpoint (we'll add this later)
EXPOSE 3100

USER ktrdr

# MCP uses stdio
CMD ["python", "-m", "src.main"]
```

### Task 0.6: Update Docker Compose
**Time Estimate**: 30 minutes

Update `docker/docker-compose.yml`:
```yaml
# Add to existing services
  mcp:
    profiles: ["research"]
    build:
      context: ../mcp
      dockerfile: Dockerfile
    image: ktrdr-mcp:dev
    container_name: ktrdr-mcp
    restart: unless-stopped
    volumes:
      - ../data:/data:ro
      - ../strategies:/app/strategies:rw
      - ../models:/app/models:rw
      - mcp-experiments:/app/experiments:rw
    environment:
      - ENVIRONMENT=development
      - LOG_LEVEL=INFO
      - KTRDR_API_URL=http://backend:8000/api/v1
    depends_on:
      - backend
    networks:
      - ktrdr-network

# Add to volumes section
volumes:
  mcp-experiments:
```

### Task 0.7: Create MCP Configuration for Claude
**Time Estimate**: 30 minutes

Create `mcp/claude_mcp_config.json`:
```json
{
  "ktrdr": {
    "command": "docker",
    "args": ["exec", "-i", "ktrdr-mcp", "python", "-m", "src.main"],
    "description": "KTRDR Trading Strategy Research Tools"
  }
}
```

### Task 0.8: Test Hello World Connection
**Time Estimate**: 1 hour

**Test Steps**:
1. Build and start containers:
   ```bash
   cd docker
   docker-compose --profile research up --build
   ```

2. Configure Claude Desktop to use MCP server

3. Test in Claude:
   ```
   "Can you test the hello_ktrdr tool with name 'Claude'?"
   ```

4. Verify logs show connection

### Task 0.9: Create Basic Tests
**Time Estimate**: 1 hour

Create `mcp/tests/test_server.py`:
```python
"""Tests for MCP server"""
import pytest
from src.server import KTRDRMCPServer

@pytest.mark.asyncio
async def test_hello_tool():
    """Test hello tool works"""
    server = KTRDRMCPServer()
    
    result = await server.handle_hello({"name": "Test"})
    
    assert result["message"] == "Hello Test! KTRDR MCP Server is working."
    assert result["status"] == "connected"
    assert "version" in result
```

### Task 0.10: Documentation
**Time Estimate**: 30 minutes

Create `mcp/README.md`:
```markdown
# KTRDR MCP Server

MCP (Model Context Protocol) server for autonomous trading strategy research.

## Setup

1. Build the container:
   ```bash
   docker-compose --profile research build
   ```

2. Start the server:
   ```bash
   docker-compose --profile research up
   ```

3. Configure Claude Desktop with the MCP configuration

## Development

Run tests:
```bash
docker exec ktrdr-mcp pytest
```

## Tools

- `hello_ktrdr`: Test connectivity (Phase 0)
```

---

## Phase 1: Core Research Tools (Weeks 2-3)

### Task 1.1: Create API Client
**Time Estimate**: 2 hours

Create `mcp/src/api_client.py`:
```python
"""KTRDR API client for MCP server"""
import httpx
from typing import Dict, Any, Optional
import structlog
from .config import KTRDR_API_URL, KTRDR_API_KEY, API_TIMEOUT

logger = structlog.get_logger()

class KTRDRAPIClient:
    """Client for communicating with KTRDR backend"""
    
    def __init__(self):
        self.base_url = KTRDR_API_URL
        self.timeout = httpx.Timeout(API_TIMEOUT)
        self.headers = {
            "Content-Type": "application/json"
        }
        if KTRDR_API_KEY:
            self.headers["X-API-Key"] = KTRDR_API_KEY
            
    async def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request to API"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}{endpoint}",
                params=params,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def post(self, endpoint: str, json: Dict[str, Any]) -> Dict[str, Any]:
        """Make POST request to API"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}{endpoint}",
                json=json,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def check_connection(self) -> bool:
        """Check if API is reachable"""
        try:
            await self.get("/health")
            return True
        except Exception as e:
            logger.error("API connection failed", error=str(e))
            return False
```

### Task 1.2: Create Storage Manager
**Time Estimate**: 3 hours

Create `mcp/src/storage/database.py`:
```python
"""Database management for experiments"""
import aiosqlite
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import structlog
from ..config import EXPERIMENT_DB_PATH

logger = structlog.get_logger()

class ExperimentDB:
    """SQLite database for experiment tracking"""
    
    def __init__(self):
        self.db_path = EXPERIMENT_DB_PATH
        
    async def initialize(self):
        """Create database tables"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    hypothesis TEXT,
                    status TEXT DEFAULT 'active',
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ended_at TIMESTAMP,
                    metadata TEXT
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tool_executions (
                    id TEXT PRIMARY KEY,
                    experiment_id TEXT,
                    tool_name TEXT NOT NULL,
                    parameters TEXT,
                    result TEXT,
                    error TEXT,
                    duration_ms INTEGER,
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS insights (
                    id TEXT PRIMARY KEY,
                    experiment_id TEXT,
                    category TEXT,
                    content TEXT,
                    tags TEXT,
                    importance INTEGER DEFAULT 5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
                )
            """)
            
            await db.commit()
            logger.info("Database initialized")
    
    async def create_experiment(self, name: str, hypothesis: str) -> str:
        """Create new experiment"""
        import uuid
        experiment_id = str(uuid.uuid4())
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO experiments (id, name, hypothesis) 
                   VALUES (?, ?, ?)""",
                (experiment_id, name, hypothesis)
            )
            await db.commit()
            
        logger.info("Experiment created", experiment_id=experiment_id, name=name)
        return experiment_id
    
    async def log_tool_execution(
        self, 
        experiment_id: Optional[str],
        tool_name: str,
        parameters: Dict[str, Any],
        result: Optional[Dict[str, Any]],
        error: Optional[str],
        duration_ms: int
    ):
        """Log tool execution"""
        import uuid
        execution_id = str(uuid.uuid4())
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO tool_executions 
                   (id, experiment_id, tool_name, parameters, result, error, duration_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    execution_id,
                    experiment_id,
                    tool_name,
                    json.dumps(parameters),
                    json.dumps(result) if result else None,
                    error,
                    duration_ms
                )
            )
            await db.commit()
```

### Task 1.3: Create Data Loading Tool
**Time Estimate**: 2 hours

Create `mcp/src/tools/data_tools.py`:
```python
"""Data loading and management tools"""
from typing import Dict, Any
import structlog
from ..api_client import KTRDRAPIClient

logger = structlog.get_logger()

class DataTools:
    """Tools for market data operations"""
    
    def __init__(self, api_client: KTRDRAPIClient):
        self.api_client = api_client
    
    def get_load_data_tool_config(self) -> Dict[str, Any]:
        """Get tool configuration for load_market_data"""
        return {
            "name": "load_market_data",
            "description": """Load historical market data for analysis.
            
            Modes:
            - 'tail': Load most recent data (default)
            - 'backfill': Load historical data up to cache
            - 'full': Complete data including gap fills
            - 'local': Use only cached data
            
            Common timeframes: 1m, 5m, 15m, 30m, 1h, 4h, 1d
            
            Examples:
            - Recent data: load_market_data("AAPL", "1h")
            - Full history: load_market_data("AAPL", "1d", mode="full")
            """,
            "input_schema": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Trading symbol (e.g., AAPL, MSFT)"
                    },
                    "timeframe": {
                        "type": "string",
                        "enum": ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
                        "description": "Bar size for data"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["tail", "backfill", "full", "local"],
                        "default": "tail",
                        "description": "Data loading mode"
                    },
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Start date (YYYY-MM-DD)"
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "End date (YYYY-MM-DD)"
                    }
                },
                "required": ["symbol", "timeframe"]
            }
        }
    
    async def handle_load_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle market data loading request"""
        symbol = params["symbol"]
        timeframe = params["timeframe"]
        mode = params.get("mode", "tail")
        
        logger.info("Loading market data", 
                   symbol=symbol, 
                   timeframe=timeframe, 
                   mode=mode)
        
        try:
            # Call KTRDR API
            response = await self.api_client.post(
                "/data/load",
                json={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "mode": mode,
                    "start_date": params.get("start_date"),
                    "end_date": params.get("end_date")
                }
            )
            
            data = response.get("data", {})
            return {
                "success": True,
                "symbol": symbol,
                "timeframe": timeframe,
                "mode": mode,
                "data_points": len(data.get("ohlcv", [])),
                "date_range": {
                    "start": data.get("dates", [None])[0],
                    "end": data.get("dates", [None])[-1]
                } if data.get("dates") else None
            }
            
        except Exception as e:
            logger.error("Failed to load market data", 
                        error=str(e), 
                        symbol=symbol)
            return {
                "success": False,
                "error": str(e),
                "symbol": symbol
            }
```

### Task 1.4: Create Strategy Management Tools
**Time Estimate**: 3 hours

Create `mcp/src/tools/strategy_tools.py`:
```python
"""Strategy creation and management tools"""
import os
import yaml
import json
from typing import Dict, Any, List
from pathlib import Path
import structlog
from ..config import STRATEGIES_DIR

logger = structlog.get_logger()

class StrategyTools:
    """Tools for strategy operations"""
    
    def get_create_strategy_tool_config(self) -> Dict[str, Any]:
        """Get tool configuration for create_strategy"""
        return {
            "name": "create_strategy",
            "description": """Create a new trading strategy configuration.
            
            The strategy should include:
            - Indicators to calculate
            - Fuzzy membership functions
            - Neural network architecture
            
            Common patterns:
            - Trend following: Moving averages + ADX
            - Mean reversion: RSI + Bollinger Bands
            - Momentum: MACD + Volume
            
            Example structure:
            {
                "name": "rsi_reversal",
                "description": "Mean reversion on RSI extremes",
                "indicators": [
                    {"name": "rsi", "parameters": {"period": 14}}
                ],
                "fuzzy_sets": {
                    "rsi": {
                        "oversold": [0, 20, 30],
                        "neutral": [25, 50, 75],
                        "overbought": [70, 80, 100]
                    }
                },
                "model": {
                    "type": "mlp",
                    "architecture": {
                        "hidden_layers": [20, 10],
                        "activation": "relu"
                    }
                }
            }
            """,
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "pattern": "^[a-z_]+$",
                        "description": "Strategy identifier (lowercase, underscores)"
                    },
                    "config": {
                        "type": "object",
                        "description": "Complete strategy configuration"
                    }
                },
                "required": ["name", "config"]
            }
        }
    
    def get_list_strategies_tool_config(self) -> Dict[str, Any]:
        """Get tool configuration for list_strategies"""
        return {
            "name": "list_strategies",
            "description": "List all available strategy configurations",
            "input_schema": {
                "type": "object",
                "properties": {}
            }
        }
    
    async def handle_create_strategy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create new strategy configuration"""
        name = params["name"]
        config = params["config"]
        
        # Add name to config if not present
        config["name"] = name
        
        # Validate basic structure
        if "indicators" not in config:
            return {
                "success": False,
                "error": "Strategy must include indicators"
            }
        
        if "fuzzy_sets" not in config:
            return {
                "success": False,
                "error": "Strategy must include fuzzy_sets"
            }
        
        if "model" not in config:
            return {
                "success": False,
                "error": "Strategy must include model configuration"
            }
        
        # Save strategy
        strategy_path = Path(STRATEGIES_DIR) / f"{name}.yaml"
        
        try:
            # Backup if exists
            if strategy_path.exists():
                backup_path = strategy_path.with_suffix(
                    f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
                )
                strategy_path.rename(backup_path)
                logger.info("Created backup", backup_path=str(backup_path))
            
            # Write new strategy
            with open(strategy_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            logger.info("Strategy created", name=name, path=str(strategy_path))
            
            return {
                "success": True,
                "name": name,
                "path": str(strategy_path),
                "config": config
            }
            
        except Exception as e:
            logger.error("Failed to create strategy", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
    
    async def handle_list_strategies(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List available strategies"""
        try:
            strategies = []
            strategy_dir = Path(STRATEGIES_DIR)
            
            for yaml_file in strategy_dir.glob("*.yaml"):
                if yaml_file.name.startswith("."):
                    continue
                    
                with open(yaml_file, 'r') as f:
                    config = yaml.safe_load(f)
                    
                strategies.append({
                    "name": yaml_file.stem,
                    "file": yaml_file.name,
                    "description": config.get("description", ""),
                    "indicators": [ind["name"] for ind in config.get("indicators", [])]
                })
            
            return {
                "success": True,
                "strategies": strategies,
                "count": len(strategies)
            }
            
        except Exception as e:
            logger.error("Failed to list strategies", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
```

### Task 1.5: Create Model Training Tool
**Time Estimate**: 3 hours

Create `mcp/src/tools/model_tools.py`:
```python
"""Neural network training tools"""
import asyncio
import uuid
from typing import Dict, Any, Optional
from pathlib import Path
import structlog
from ..api_client import KTRDRAPIClient
from ..config import MODELS_DIR

logger = structlog.get_logger()

class ModelTools:
    """Tools for model training and management"""
    
    def __init__(self, api_client: KTRDRAPIClient):
        self.api_client = api_client
        self.active_training_tasks = {}
    
    def get_train_model_tool_config(self) -> Dict[str, Any]:
        """Get tool configuration for train_model"""
        return {
            "name": "train_model",
            "description": """Train a neural network for a strategy.
            
            This is a long-running operation (5-15 minutes).
            Returns a task_id to check progress.
            
            Workflow:
            1. Create strategy first
            2. Train model with this tool
            3. Check progress with get_task_status
            4. Run backtest once complete
            
            Training parameters:
            - epochs: 50-200 (default 100)
            - batch_size: 16-64 (default 32)
            - learning_rate: 0.0001-0.01 (default 0.001)
            """,
            "input_schema": {
                "type": "object",
                "properties": {
                    "strategy_name": {
                        "type": "string",
                        "description": "Name of strategy to train"
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Symbol to train on"
                    },
                    "timeframe": {
                        "type": "string",
                        "default": "1h",
                        "description": "Timeframe for training data"
                    },
                    "epochs": {
                        "type": "integer",
                        "default": 100,
                        "minimum": 10,
                        "maximum": 500
                    },
                    "batch_size": {
                        "type": "integer",
                        "default": 32,
                        "minimum": 8,
                        "maximum": 128
                    }
                },
                "required": ["strategy_name", "symbol"]
            }
        }
    
    def get_task_status_tool_config(self) -> Dict[str, Any]:
        """Get tool configuration for checking task status"""
        return {
            "name": "get_task_status",
            "description": "Check status of a long-running task like model training",
            "input_schema": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID returned by train_model"
                    }
                },
                "required": ["task_id"]
            }
        }
    
    async def handle_train_model(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Start model training"""
        strategy_name = params["strategy_name"]
        symbol = params["symbol"]
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Start training task
        task = asyncio.create_task(
            self._train_model_async(task_id, params)
        )
        
        self.active_training_tasks[task_id] = {
            "task": task,
            "strategy_name": strategy_name,
            "symbol": symbol,
            "status": "started",
            "progress": 0,
            "started_at": asyncio.get_event_loop().time()
        }
        
        logger.info("Training started", 
                   task_id=task_id, 
                   strategy=strategy_name,
                   symbol=symbol)
        
        return {
            "success": True,
            "task_id": task_id,
            "status": "training_started",
            "message": "Model training started. Check progress with get_task_status.",
            "estimated_time": "5-15 minutes"
        }
    
    async def _train_model_async(self, task_id: str, params: Dict[str, Any]):
        """Execute model training asynchronously"""
        try:
            # Update status
            self.active_training_tasks[task_id]["status"] = "preparing"
            
            # Call training API
            response = await self.api_client.post(
                "/neural/train",
                json={
                    "strategy_name": params["strategy_name"],
                    "symbol": params["symbol"],
                    "timeframe": params.get("timeframe", "1h"),
                    "training_params": {
                        "epochs": params.get("epochs", 100),
                        "batch_size": params.get("batch_size", 32),
                        "learning_rate": params.get("learning_rate", 0.001)
                    }
                }
            )
            
            # Save model
            model_dir = Path(MODELS_DIR) / params["strategy_name"]
            model_dir.mkdir(exist_ok=True)
            
            # Update task with results
            self.active_training_tasks[task_id].update({
                "status": "completed",
                "result": response,
                "model_path": str(model_dir / "latest.pt")
            })
            
        except Exception as e:
            logger.error("Training failed", task_id=task_id, error=str(e))
            self.active_training_tasks[task_id].update({
                "status": "failed",
                "error": str(e)
            })
    
    async def handle_get_task_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check task status"""
        task_id = params["task_id"]
        
        if task_id not in self.active_training_tasks:
            return {
                "success": False,
                "error": "Task not found"
            }
        
        task_info = self.active_training_tasks[task_id]
        
        if task_info["task"].done():
            # Task completed
            status = task_info["status"]
            if status == "completed":
                return {
                    "success": True,
                    "status": "completed",
                    "result": task_info.get("result", {}),
                    "model_path": task_info.get("model_path")
                }
            else:
                return {
                    "success": False,
                    "status": "failed",
                    "error": task_info.get("error", "Unknown error")
                }
        else:
            # Still running
            elapsed = asyncio.get_event_loop().time() - task_info["started_at"]
            return {
                "success": True,
                "status": "running",
                "progress": task_info.get("progress", 0),
                "elapsed_seconds": int(elapsed),
                "strategy_name": task_info["strategy_name"]
            }
```

### Task 1.6: Create Backtest Tool
**Time Estimate**: 2 hours

Create `mcp/src/tools/backtest_tools.py`:
```python
"""Backtesting tools"""
from typing import Dict, Any
import structlog
from ..api_client import KTRDRAPIClient

logger = structlog.get_logger()

class BacktestTools:
    """Tools for strategy backtesting"""
    
    def __init__(self, api_client: KTRDRAPIClient):
        self.api_client = api_client
    
    def get_run_backtest_tool_config(self) -> Dict[str, Any]:
        """Get tool configuration for run_backtest"""
        return {
            "name": "run_backtest",
            "description": """Run backtest for a trained strategy.
            
            Prerequisites:
            - Strategy must be created
            - Model must be trained
            - Market data available for date range
            
            Returns performance metrics:
            - Total return
            - Sharpe ratio
            - Maximum drawdown
            - Win rate
            - Number of trades
            """,
            "input_schema": {
                "type": "object",
                "properties": {
                    "strategy_name": {
                        "type": "string",
                        "description": "Name of strategy to backtest"
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Symbol to test on"
                    },
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Backtest start date"
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Backtest end date"
                    },
                    "initial_capital": {
                        "type": "number",
                        "default": 10000,
                        "description": "Starting capital"
                    }
                },
                "required": ["strategy_name", "symbol"]
            }
        }
    
    async def handle_run_backtest(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute strategy backtest"""
        strategy_name = params["strategy_name"]
        symbol = params["symbol"]
        
        logger.info("Running backtest", 
                   strategy=strategy_name,
                   symbol=symbol)
        
        try:
            # Call backtest API
            response = await self.api_client.post(
                "/backtest/run",
                json={
                    "strategy_name": strategy_name,
                    "symbol": symbol,
                    "timeframe": "1h",  # TODO: Make configurable
                    "start_date": params.get("start_date", "2023-01-01"),
                    "end_date": params.get("end_date", "2024-01-01"),
                    "initial_capital": params.get("initial_capital", 10000)
                }
            )
            
            metrics = response.get("metrics", {})
            
            return {
                "success": True,
                "strategy_name": strategy_name,
                "symbol": symbol,
                "metrics": {
                    "total_return": metrics.get("total_return", 0),
                    "sharpe_ratio": metrics.get("sharpe_ratio", 0),
                    "max_drawdown": metrics.get("max_drawdown", 0),
                    "win_rate": metrics.get("win_rate", 0),
                    "num_trades": metrics.get("num_trades", 0)
                },
                "backtest_id": response.get("backtest_id")
            }
            
        except Exception as e:
            logger.error("Backtest failed", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
```

### Task 1.7: Update Main Server with All Tools
**Time Estimate**: 1 hour

Update `mcp/src/server.py`:
```python
"""KTRDR MCP Server - Main entry point"""
import asyncio
from typing import Any, Dict
from mcp import Server, Tool
from mcp.server.stdio import stdio_server
import structlog

from .api_client import KTRDRAPIClient
from .storage.database import ExperimentDB
from .tools.data_tools import DataTools
from .tools.strategy_tools import StrategyTools
from .tools.model_tools import ModelTools
from .tools.backtest_tools import BacktestTools

logger = structlog.get_logger()

class KTRDRMCPServer:
    """MCP Server for KTRDR trading strategy research"""
    
    def __init__(self):
        self.server = Server("ktrdr-mcp")
        self.api_client = KTRDRAPIClient()
        self.db = ExperimentDB()
        
        # Initialize tools
        self.data_tools = DataTools(self.api_client)
        self.strategy_tools = StrategyTools()
        self.model_tools = ModelTools(self.api_client)
        self.backtest_tools = BacktestTools(self.api_client)
        
        self.setup_tools()
        logger.info("KTRDR MCP Server initialized")
    
    async def initialize(self):
        """Initialize server components"""
        await self.db.initialize()
        connected = await self.api_client.check_connection()
        if not connected:
            logger.warning("Could not connect to KTRDR API")
    
    def setup_tools(self):
        """Register all available tools"""
        # Data tools
        self._add_tool_from_config(
            self.data_tools.get_load_data_tool_config(),
            self.data_tools.handle_load_data
        )
        
        # Strategy tools
        self._add_tool_from_config(
            self.strategy_tools.get_create_strategy_tool_config(),
            self.strategy_tools.handle_create_strategy
        )
        self._add_tool_from_config(
            self.strategy_tools.get_list_strategies_tool_config(),
            self.strategy_tools.handle_list_strategies
        )
        
        # Model tools
        self._add_tool_from_config(
            self.model_tools.get_train_model_tool_config(),
            self.model_tools.handle_train_model
        )
        self._add_tool_from_config(
            self.model_tools.get_task_status_tool_config(),
            self.model_tools.handle_get_task_status
        )
        
        # Backtest tools
        self._add_tool_from_config(
            self.backtest_tools.get_run_backtest_tool_config(),
            self.backtest_tools.handle_run_backtest
        )
        
        logger.info("Tools registered", count=6)
    
    def _add_tool_from_config(self, config: Dict[str, Any], handler):
        """Add tool from configuration"""
        tool = Tool(
            name=config["name"],
            description=config["description"],
            input_schema=config["input_schema"],
            handler=handler
        )
        self.server.add_tool(tool)
    
    async def run(self):
        """Run the MCP server"""
        logger.info("Starting KTRDR MCP Server")
        await self.initialize()
        
        async with stdio_server() as streams:
            await self.server.run(
                streams[0],  # stdin
                streams[1],  # stdout
                self.setup_tools()
            )
```

### Task 1.8: Create Integration Tests
**Time Estimate**: 2 hours

Create `mcp/tests/test_integration.py`:
```python
"""Integration tests for MCP server"""
import pytest
import tempfile
from pathlib import Path
from src.server import KTRDRMCPServer

@pytest.fixture
async def server():
    """Create server instance for testing"""
    server = KTRDRMCPServer()
    await server.initialize()
    return server

@pytest.mark.asyncio
async def test_complete_workflow(server, tmp_path):
    """Test complete strategy research workflow"""
    
    # 1. Create strategy
    strategy_config = {
        "name": "test_rsi",
        "description": "Test RSI strategy",
        "indicators": [
            {"name": "rsi", "parameters": {"period": 14}}
        ],
        "fuzzy_sets": {
            "rsi": {
                "oversold": [0, 20, 30],
                "neutral": [25, 50, 75],
                "overbought": [70, 80, 100]
            }
        },
        "model": {
            "type": "mlp",
            "architecture": {
                "hidden_layers": [10, 5],
                "activation": "relu"
            }
        }
    }
    
    result = await server.strategy_tools.handle_create_strategy({
        "name": "test_rsi",
        "config": strategy_config
    })
    assert result["success"] is True
    
    # 2. List strategies to verify
    result = await server.strategy_tools.handle_list_strategies({})
    assert result["success"] is True
    assert any(s["name"] == "test_rsi" for s in result["strategies"])
    
    # Add more workflow steps as API endpoints are implemented
```

### Task 1.9: Update Documentation
**Time Estimate**: 1 hour

Update `mcp/README.md` with all Phase 1 tools and examples.

### Task 1.10: Manual Testing Checklist
**Time Estimate**: 2 hours

**Test each tool in Claude**:
- [ ] Load market data for AAPL
- [ ] Create a simple RSI strategy
- [ ] List available strategies
- [ ] Train model for the strategy
- [ ] Check training status
- [ ] Run backtest when complete
- [ ] Verify results make sense

---

## Commit Strategy

### Phase 0 Commits
```bash
git add mcp/
git commit -m "feat(mcp): Initialize MCP server structure"

git add mcp/src/server.py mcp/src/main.py
git commit -m "feat(mcp): Add basic MCP server with hello tool"

git add mcp/Dockerfile docker/docker-compose.yml
git commit -m "feat(mcp): Add Docker configuration for MCP server"

git add mcp/tests/
git commit -m "test(mcp): Add basic test infrastructure"

# Merge phase 0
git checkout feature/mcp-server
git merge feature/mcp-phase-0-foundation
```

### Phase 1 Commits
```bash
git checkout -b feature/mcp-phase-1-tools

git add mcp/src/api_client.py
git commit -m "feat(mcp): Add KTRDR API client"

git add mcp/src/storage/
git commit -m "feat(mcp): Add experiment database"

git add mcp/src/tools/data_tools.py
git commit -m "feat(mcp): Add market data loading tool"

git add mcp/src/tools/strategy_tools.py
git commit -m "feat(mcp): Add strategy management tools"

git add mcp/src/tools/model_tools.py
git commit -m "feat(mcp): Add model training tools"

git add mcp/src/tools/backtest_tools.py
git commit -m "feat(mcp): Add backtesting tool"

git add mcp/src/server.py
git commit -m "feat(mcp): Integrate all Phase 1 tools"

# Merge phase 1
git checkout feature/mcp-server
git merge feature/mcp-phase-1-tools
```

---

## Success Criteria Checklist

### Phase 0 ✓
- [ ] MCP server builds and runs in Docker
- [ ] Claude can connect and execute hello tool
- [ ] Logging works and is readable
- [ ] Basic tests pass

### Phase 1 ✓
- [ ] Can load market data through MCP
- [ ] Can create and list strategies
- [ ] Can train models (async)
- [ ] Can check training progress
- [ ] Can run backtests
- [ ] Complete workflow works end-to-end
- [ ] All tools have proper prompts/descriptions

---

## Notes

- All API endpoints referenced (like `/data/load`, `/neural/train`) need to exist in KTRDR backend
- File paths assume standard KTRDR directory structure
- Error handling is simplified - production code needs more robust error handling
- The experiment database is initialized but not fully utilized in Phase 1 (Phase 2 will add knowledge tools)