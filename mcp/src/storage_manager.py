"""Storage Manager for MCP Experiments and Knowledge Accumulation"""

import json
import sqlite3
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import aiosqlite
import structlog
from .config import get_config

logger = structlog.get_logger()


class ExperimentStorage:
    """Manages experiment data and knowledge accumulation in SQLite"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_config(
            "EXPERIMENT_DB_PATH", "/app/experiments/experiments.db"
        )
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        logger.info("Experiment storage initialized", db_path=self.db_path)

    async def initialize(self):
        """Initialize database tables"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(
                """
                -- Experiments table - stores research experiments
                CREATE TABLE IF NOT EXISTS experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'running',  -- running, completed, failed
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    config TEXT,  -- JSON configuration
                    results TEXT,  -- JSON results
                    metadata TEXT  -- JSON metadata
                );
                
                -- Strategies table - stores strategy configurations
                CREATE TABLE IF NOT EXISTS strategies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    config TEXT NOT NULL,  -- JSON strategy config
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    performance_metrics TEXT,  -- JSON performance data
                    tags TEXT  -- JSON array of tags
                );
                
                -- Models table - stores trained model information
                CREATE TABLE IF NOT EXISTS models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    model_type TEXT NOT NULL,  -- neural, fuzzy, etc.
                    strategy_id INTEGER,
                    file_path TEXT,  -- path to saved model
                    config TEXT,  -- JSON model config
                    training_metrics TEXT,  -- JSON training results
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (strategy_id) REFERENCES strategies (id)
                );
                
                -- Backtests table - stores backtest results
                CREATE TABLE IF NOT EXISTS backtests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    results TEXT,  -- JSON backtest results
                    metrics TEXT,  -- JSON performance metrics
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (strategy_id) REFERENCES strategies (id)
                );
                
                -- Training tasks - tracks neural network training jobs
                CREATE TABLE IF NOT EXISTS training_tasks (
                    id TEXT PRIMARY KEY,  -- UUID task identifier
                    experiment_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    config TEXT NOT NULL,  -- JSON training configuration
                    start_date TEXT,
                    end_date TEXT,
                    status TEXT DEFAULT 'pending',  -- pending, training, completed, failed
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    progress TEXT,  -- JSON progress information
                    FOREIGN KEY (experiment_id) REFERENCES experiments (id)
                );
                
                -- Model records - tracks saved neural network models
                CREATE TABLE IF NOT EXISTS model_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    task_id TEXT,  -- Reference to training task
                    description TEXT,
                    config TEXT,  -- JSON model configuration
                    symbol TEXT,
                    timeframe TEXT,
                    performance_metrics TEXT,  -- JSON performance data
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES training_tasks (id)
                );
                
                -- Knowledge base - stores research insights and learnings
                CREATE TABLE IF NOT EXISTS knowledge_base (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_type TEXT,  -- experiment, backtest, manual
                    source_id INTEGER,  -- reference to source record
                    tags TEXT,  -- JSON array of tags
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Create indexes for better performance
                CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);
                CREATE INDEX IF NOT EXISTS idx_experiments_created ON experiments(created_at);
                CREATE INDEX IF NOT EXISTS idx_strategies_name ON strategies(name);
                CREATE INDEX IF NOT EXISTS idx_backtests_strategy ON backtests(strategy_id);
                CREATE INDEX IF NOT EXISTS idx_training_tasks_experiment ON training_tasks(experiment_id);
                CREATE INDEX IF NOT EXISTS idx_training_tasks_status ON training_tasks(status);
                CREATE INDEX IF NOT EXISTS idx_model_records_name ON model_records(name);
                CREATE INDEX IF NOT EXISTS idx_knowledge_topic ON knowledge_base(topic);
            """
            )
            await db.commit()
            logger.info("Database initialized successfully")

    # Experiment Management
    async def create_experiment(
        self, name: str, description: str = "", config: Optional[Dict] = None
    ) -> int:
        """Create a new experiment"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO experiments (name, description, config) VALUES (?, ?, ?)",
                (name, description, json.dumps(config) if config else None),
            )
            await db.commit()
            experiment_id = cursor.lastrowid
            logger.info("Experiment created", id=experiment_id, name=name)
            return experiment_id

    async def update_experiment(
        self,
        experiment_id: int,
        status: Optional[str] = None,
        results: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ):
        """Update experiment status and results"""
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        values = []

        if status:
            updates.append("status = ?")
            values.append(status)
        if results:
            updates.append("results = ?")
            values.append(json.dumps(results))
        if metadata:
            updates.append("metadata = ?")
            values.append(json.dumps(metadata))

        values.append(experiment_id)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE experiments SET {', '.join(updates)} WHERE id = ?", values
            )
            await db.commit()
            logger.info("Experiment updated", id=experiment_id, status=status)

    async def get_experiment(self, experiment_id: int) -> Optional[Dict]:
        """Get experiment by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM experiments WHERE id = ?", (experiment_id,)
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def list_experiments(
        self, status: Optional[str] = None, limit: int = 50
    ) -> List[Dict]:
        """List experiments with optional status filter"""
        query = "SELECT * FROM experiments"
        params = []

        if status:
            query += " WHERE status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # Strategy Management
    async def save_strategy(
        self, name: str, config: Dict, description: str = ""
    ) -> int:
        """Save or update a strategy"""
        async with aiosqlite.connect(self.db_path) as db:
            # Try to update existing strategy
            cursor = await db.execute(
                "UPDATE strategies SET config = ?, description = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
                (json.dumps(config), description, name),
            )
            await db.commit()

            if cursor.rowcount == 0:
                # Create new strategy
                cursor = await db.execute(
                    "INSERT INTO strategies (name, description, config) VALUES (?, ?, ?)",
                    (name, description, json.dumps(config)),
                )
                await db.commit()
                strategy_id = cursor.lastrowid
            else:
                # Get existing strategy ID
                cursor = await db.execute(
                    "SELECT id FROM strategies WHERE name = ?", (name,)
                )
                row = await cursor.fetchone()
                strategy_id = row[0]

            logger.info("Strategy saved", id=strategy_id, name=name)
            return strategy_id

    async def get_strategy(self, name: str) -> Optional[Dict]:
        """Get strategy by name"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM strategies WHERE name = ?", (name,)
            )
            row = await cursor.fetchone()
            if row:
                strategy = dict(row)
                strategy["config"] = json.loads(strategy["config"])
                if strategy["performance_metrics"]:
                    strategy["performance_metrics"] = json.loads(
                        strategy["performance_metrics"]
                    )
                return strategy
            return None

    async def list_strategies(self) -> List[Dict]:
        """List all strategies"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, name, description, created_at, updated_at FROM strategies ORDER BY updated_at DESC"
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # Backtest Management
    async def save_backtest(
        self,
        strategy_id: int,
        symbol: str,
        start_date: str,
        end_date: str,
        results: Dict,
        metrics: Dict,
    ) -> int:
        """Save backtest results"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO backtests 
                   (strategy_id, symbol, start_date, end_date, results, metrics) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    strategy_id,
                    symbol,
                    start_date,
                    end_date,
                    json.dumps(results),
                    json.dumps(metrics),
                ),
            )
            await db.commit()
            backtest_id = cursor.lastrowid
            logger.info(
                "Backtest saved", id=backtest_id, strategy_id=strategy_id, symbol=symbol
            )
            return backtest_id

    async def get_backtest_history(
        self, strategy_id: Optional[int] = None, symbol: Optional[str] = None
    ) -> List[Dict]:
        """Get backtest history with optional filters"""
        query = "SELECT * FROM backtests"
        params = []
        conditions = []

        if strategy_id:
            conditions.append("strategy_id = ?")
            params.append(strategy_id)
        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC"

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # Knowledge Base
    async def add_knowledge(
        self,
        topic: str,
        content: str,
        source_type: str = "manual",
        source_id: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> int:
        """Add knowledge to the base"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO knowledge_base (topic, content, source_type, source_id, tags) VALUES (?, ?, ?, ?, ?)",
                (
                    topic,
                    content,
                    source_type,
                    source_id,
                    json.dumps(tags) if tags else None,
                ),
            )
            await db.commit()
            knowledge_id = cursor.lastrowid
            logger.info("Knowledge added", id=knowledge_id, topic=topic)
            return knowledge_id

    async def search_knowledge(
        self, topic: Optional[str] = None, tags: Optional[List[str]] = None
    ) -> List[Dict]:
        """Search knowledge base"""
        query = "SELECT * FROM knowledge_base"
        params = []
        conditions = []

        if topic:
            conditions.append("topic LIKE ?")
            params.append(f"%{topic}%")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC"

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            knowledge = [dict(row) for row in rows]

            # Filter by tags if specified
            if tags:
                filtered = []
                for item in knowledge:
                    if item["tags"]:
                        item_tags = json.loads(item["tags"])
                        if any(tag in item_tags for tag in tags):
                            filtered.append(item)
                knowledge = filtered

            return knowledge

    # Training Task Management
    async def create_training_task(
        self,
        experiment_id: int,
        symbol: str,
        timeframe: str,
        config: Dict,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> str:
        """Create a new training task"""
        import uuid

        task_id = str(uuid.uuid4())

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO training_tasks 
                   (id, experiment_id, symbol, timeframe, config, start_date, end_date) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    task_id,
                    experiment_id,
                    symbol,
                    timeframe,
                    json.dumps(config),
                    start_date,
                    end_date,
                ),
            )
            await db.commit()
            logger.info(
                "Training task created", task_id=task_id, experiment_id=experiment_id
            )
            return task_id

    async def update_training_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        progress: Optional[Dict] = None,
        error_message: Optional[str] = None,
    ):
        """Update training task status and progress"""
        updates = []
        values = []

        if status:
            updates.append("status = ?")
            values.append(status)
            if status == "training" and not updates.__contains__(
                "started_at = CURRENT_TIMESTAMP"
            ):
                updates.append("started_at = CURRENT_TIMESTAMP")
            elif status in ["completed", "failed"]:
                updates.append("completed_at = CURRENT_TIMESTAMP")

        if progress:
            updates.append("progress = ?")
            values.append(json.dumps(progress))

        if error_message:
            updates.append("error_message = ?")
            values.append(error_message)

        if not updates:
            return

        values.append(task_id)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE training_tasks SET {', '.join(updates)} WHERE id = ?", values
            )
            await db.commit()
            logger.info("Training task updated", task_id=task_id, status=status)

    async def get_training_task(self, task_id: str) -> Optional[Dict]:
        """Get training task by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM training_tasks WHERE id = ?", (task_id,)
            )
            row = await cursor.fetchone()
            if row:
                task = dict(row)
                task["config"] = json.loads(task["config"])
                if task["progress"]:
                    task["progress"] = json.loads(task["progress"])
                return task
            return None

    async def list_training_tasks(
        self,
        experiment_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """List training tasks with optional filters"""
        query = "SELECT * FROM training_tasks"
        params = []
        conditions = []

        if experiment_id:
            conditions.append("experiment_id = ?")
            params.append(experiment_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            tasks = []
            for row in rows:
                task = dict(row)
                task["config"] = json.loads(task["config"])
                if task["progress"]:
                    task["progress"] = json.loads(task["progress"])
                tasks.append(task)
            return tasks

    # Model Record Management
    async def save_model_record(
        self,
        name: str,
        task_id: str,
        description: str,
        config: Dict,
        symbol: str,
        timeframe: str,
        performance_metrics: Optional[Dict] = None,
    ) -> int:
        """Save a model record"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO model_records 
                   (name, task_id, description, config, symbol, timeframe, performance_metrics) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    task_id,
                    description,
                    json.dumps(config),
                    symbol,
                    timeframe,
                    json.dumps(performance_metrics) if performance_metrics else None,
                ),
            )
            await db.commit()
            model_id = cursor.lastrowid
            logger.info("Model record saved", model_id=model_id, name=name)
            return model_id

    async def get_model_record(self, name: str) -> Optional[Dict]:
        """Get model record by name"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM model_records WHERE name = ?", (name,)
            )
            row = await cursor.fetchone()
            if row:
                model = dict(row)
                model["config"] = json.loads(model["config"])
                if model["performance_metrics"]:
                    model["performance_metrics"] = json.loads(
                        model["performance_metrics"]
                    )
                return model
            return None

    async def list_model_records(self) -> List[Dict]:
        """List all model records"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM model_records ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()
            models = []
            for row in rows:
                model = dict(row)
                model["config"] = json.loads(model["config"])
                if model["performance_metrics"]:
                    model["performance_metrics"] = json.loads(
                        model["performance_metrics"]
                    )
                models.append(model)
            return models


# Singleton instance
_storage: Optional[ExperimentStorage] = None


async def get_storage() -> ExperimentStorage:
    """Get singleton storage instance"""
    global _storage
    if _storage is None:
        _storage = ExperimentStorage()
        await _storage.initialize()
    return _storage
