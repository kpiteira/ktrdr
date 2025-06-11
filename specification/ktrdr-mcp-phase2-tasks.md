# KTRDR MCP Server - Phase 2 Knowledge Management Task Breakdown

## Overview
Phase 2 implements the Knowledge Management system, including research session tracking, insight accumulation, Obsidian vault integration, and unified state management with progress notifications.

## Prerequisites
- [ ] Phase 0 & 1 completed and working
- [ ] PostgreSQL installed (via Docker)
- [ ] Obsidian installed (for viewing knowledge vault)

---

## Task 2.1: PostgreSQL Setup
**Time Estimate**: 2 hours

### Update Docker Compose
Update `docker/docker-compose.yml`:
```yaml
services:
  # ... existing services ...
  
  postgres:
    image: postgres:16-alpine
    container_name: ktrdr-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ktrdr_research
      POSTGRES_USER: ktrdr
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-ktrdr_dev_password}
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./docker/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "5432:5432"
    networks:
      - ktrdr-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ktrdr -d ktrdr_research"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres-data:
  # ... other volumes ...
```

### Create Database Schema
Create `docker/postgres/init.sql`:
```sql
-- Research sessions (main workflow units)
CREATE TABLE research_sessions (
    id UUID PRIMARY KEY,
    theme TEXT NOT NULL,
    hypothesis TEXT,
    status VARCHAR(50) DEFAULT 'active',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    total_strategies_tested INTEGER DEFAULT 0,
    successful_strategies INTEGER DEFAULT 0,
    key_findings TEXT,
    metadata JSONB DEFAULT '{}'
);

-- Session checkpoints for state recovery
CREATE TABLE session_checkpoints (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES research_sessions(id),
    checkpoint_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insights with Obsidian integration
CREATE TABLE insights (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES research_sessions(id),
    type VARCHAR(50) NOT NULL, -- success, failure, pattern, hypothesis
    title TEXT NOT NULL,
    summary TEXT,
    obsidian_path TEXT,
    tags TEXT[],
    importance INTEGER DEFAULT 5 CHECK (importance >= 1 AND importance <= 10),
    quality_score FLOAT DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    superseded_by UUID REFERENCES insights(id)
);

-- Insight relationships for knowledge graph
CREATE TABLE insight_relationships (
    from_insight_id UUID REFERENCES insights(id),
    to_insight_id UUID REFERENCES insights(id),
    relationship_type VARCHAR(50), -- supports, contradicts, extends, replaces
    strength FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (from_insight_id, to_insight_id)
);

-- Pattern library
CREATE TABLE patterns (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    conditions JSONB,
    success_rate FLOAT,
    sample_size INTEGER DEFAULT 0,
    discovered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    obsidian_path TEXT,
    session_id UUID REFERENCES research_sessions(id)
);

-- Strategy success tracking
CREATE TABLE strategy_outcomes (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES research_sessions(id),
    strategy_name TEXT NOT NULL,
    backtest_metrics JSONB,
    success BOOLEAN,
    insights_generated UUID[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_insights_session ON insights(session_id);
CREATE INDEX idx_insights_tags ON insights USING GIN(tags);
CREATE INDEX idx_insights_created ON insights(created_at);
CREATE INDEX idx_patterns_session ON patterns(session_id);
```

### Update MCP Requirements
Update `mcp/requirements.txt`:
```txt
# ... existing requirements ...

# PostgreSQL
asyncpg>=0.29.0
sqlalchemy[asyncio]>=2.0.0

# Markdown generation
markdown>=3.5.0
frontmatter>=3.0.0
```

---

## Task 2.2: Create Knowledge Directory Structure
**Time Estimate**: 30 minutes

```bash
# Create knowledge directory structure
mkdir -p knowledge/sessions
mkdir -p knowledge/insights  
mkdir -p knowledge/patterns
mkdir -p knowledge/strategies/successful
mkdir -p knowledge/strategies/failed
mkdir -p knowledge/templates

# Add to .gitignore
echo "/knowledge/" >> .gitignore
```

Create `knowledge/templates/insight-template.md`:
```markdown
---
id: {{insight_id}}
type: {{type}}
date: {{date}}
session: {{session_id}}
tags: [{{tags}}]
importance: {{importance}}
quality_score: {{quality_score}}
---

# {{title}}

## Summary
{{summary}}

## Evidence
- Strategy: `{{strategy_name}}`
- Backtest Period: {{start_date}} to {{end_date}}
- Symbol: {{symbol}}
- Result: {{key_metrics}}

## Analysis
{{detailed_analysis}}

## Lessons Learned
{{lessons}}

## Related Insights
{{related_links}}

## Next Steps
{{next_steps}}
```

---

## Task 2.3: Create Database Connection Manager
**Time Estimate**: 2 hours

Create `mcp/src/storage/postgres.py`:
```python
"""PostgreSQL database connection and operations"""
import asyncpg
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from ..config import POSTGRES_URL
import structlog

logger = structlog.get_logger()

class PostgresDB:
    """PostgreSQL database manager for research data"""
    
    def __init__(self):
        self.pool = None
        
    async def initialize(self):
        """Create connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                POSTGRES_URL,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("PostgreSQL connection pool created")
        except Exception as e:
            logger.error("Failed to connect to PostgreSQL", error=str(e))
            raise
    
    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
    
    # Research Session Operations
    async def create_session(self, theme: str, hypothesis: str) -> str:
        """Create new research session"""
        session_id = str(uuid.uuid4())
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO research_sessions (id, theme, hypothesis)
                VALUES ($1, $2, $3)
            """, session_id, theme, hypothesis)
        
        logger.info("Research session created", session_id=session_id, theme=theme)
        return session_id
    
    async def update_session(self, session_id: str, updates: Dict[str, Any]):
        """Update session information"""
        # Build dynamic update query
        set_clauses = []
        values = []
        for i, (key, value) in enumerate(updates.items(), 1):
            set_clauses.append(f"{key} = ${i+1}")
            values.append(value)
        
        query = f"""
            UPDATE research_sessions 
            SET {', '.join(set_clauses)}
            WHERE id = $1
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(query, session_id, *values)
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session details"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM research_sessions WHERE id = $1",
                session_id
            )
            return dict(row) if row else None
    
    # Checkpoint Operations
    async def save_checkpoint(self, session_id: str, checkpoint_data: Dict[str, Any]):
        """Save session checkpoint for recovery"""
        checkpoint_id = str(uuid.uuid4())
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO session_checkpoints (id, session_id, checkpoint_data)
                VALUES ($1, $2, $3)
            """, checkpoint_id, session_id, json.dumps(checkpoint_data))
    
    async def get_latest_checkpoint(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get most recent checkpoint for session"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT checkpoint_data 
                FROM session_checkpoints 
                WHERE session_id = $1 
                ORDER BY created_at DESC 
                LIMIT 1
            """, session_id)
            
            return json.loads(row['checkpoint_data']) if row else None
    
    # Insight Operations
    async def save_insight(self, insight_data: Dict[str, Any]) -> str:
        """Save new insight"""
        insight_id = str(uuid.uuid4())
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO insights 
                (id, session_id, type, title, summary, obsidian_path, tags, importance)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, 
                insight_id,
                insight_data['session_id'],
                insight_data['type'],
                insight_data['title'],
                insight_data['summary'],
                insight_data['obsidian_path'],
                insight_data.get('tags', []),
                insight_data.get('importance', 5)
            )
        
        logger.info("Insight saved", insight_id=insight_id, title=insight_data['title'])
        return insight_id
    
    async def search_insights(self, query: str = None, tags: List[str] = None, 
                            type: str = None) -> List[Dict[str, Any]]:
        """Search insights with various filters"""
        conditions = []
        params = []
        param_count = 0
        
        if query:
            param_count += 1
            conditions.append(f"(title ILIKE ${param_count} OR summary ILIKE ${param_count})")
            params.append(f"%{query}%")
        
        if tags:
            param_count += 1
            conditions.append(f"tags && ${param_count}")
            params.append(tags)
        
        if type:
            param_count += 1
            conditions.append(f"type = ${param_count}")
            params.append(type)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
            SELECT * FROM insights 
            {where_clause}
            ORDER BY importance DESC, created_at DESC
            LIMIT 50
        """
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    # Pattern Operations
    async def save_pattern(self, pattern_data: Dict[str, Any]) -> str:
        """Save discovered pattern"""
        pattern_id = str(uuid.uuid4())
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO patterns 
                (id, name, description, conditions, success_rate, sample_size, 
                 obsidian_path, session_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
                pattern_id,
                pattern_data['name'],
                pattern_data['description'],
                json.dumps(pattern_data.get('conditions', {})),
                pattern_data.get('success_rate', 0.0),
                pattern_data.get('sample_size', 0),
                pattern_data.get('obsidian_path'),
                pattern_data.get('session_id')
            )
        
        return pattern_id
```

Update `mcp/src/config.py`:
```python
# Add PostgreSQL configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "ktrdr_research")
POSTGRES_USER = os.getenv("POSTGRES_USER", "ktrdr")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "ktrdr_dev_password")

POSTGRES_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Knowledge vault configuration
KNOWLEDGE_BASE_PATH = os.getenv("KNOWLEDGE_BASE_PATH", str(ROOT_DIR / "knowledge"))
```

---

## Task 2.4: Create Unified State Manager
**Time Estimate**: 3 hours

Create `mcp/src/state_manager.py`:
```python
"""Unified state management with progress tracking"""
import uuid
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import structlog
from .storage.postgres import PostgresDB
from .notifier import Notifier

logger = structlog.get_logger()

class ResearchStateManager:
    """Central state management with progress tracking and persistence"""
    
    def __init__(self, db: PostgresDB, notifier: Notifier):
        self.db = db
        self.notifier = notifier
        self.current_session = None
        self.active_operations = {}
    
    async def start_session(self, theme: str, hypothesis: str) -> str:
        """Begin new research session"""
        session_id = await self.db.create_session(theme, hypothesis)
        
        self.current_session = {
            'id': session_id,
            'theme': theme,
            'hypothesis': hypothesis,
            'status': 'active',
            'started_at': datetime.utcnow(),
            'strategies_tested': [],
            'strategies_in_progress': {},
            'insights_generated': [],
            'patterns_discovered': []
        }
        
        await self._emit_progress("session_started", {
            'session_id': session_id,
            'theme': theme,
            'hypothesis': hypothesis
        })
        
        return session_id
    
    async def checkpoint(self, event: str = None, data: Dict = None):
        """Save state checkpoint for recovery"""
        if not self.current_session:
            return
            
        checkpoint_data = {
            'session_state': self.current_session,
            'active_operations': self.active_operations,
            'timestamp': datetime.utcnow().isoformat(),
            'event': event,
            'event_data': data
        }
        
        await self.db.save_checkpoint(self.current_session['id'], checkpoint_data)
    
    async def update_progress(self, event: str, data: Dict = None):
        """Update progress and emit notification"""
        if not self.current_session:
            logger.warning("No active session for progress update", event=event)
            return
        
        # Update session state based on event
        if event == "strategy_started":
            strategy_name = data['strategy_name']
            self.current_session['strategies_in_progress'][strategy_name] = {
                'started_at': datetime.utcnow().isoformat(),
                'status': 'running'
            }
            
        elif event == "strategy_completed":
            strategy_name = data['strategy_name']
            if strategy_name in self.current_session['strategies_in_progress']:
                del self.current_session['strategies_in_progress'][strategy_name]
            self.current_session['strategies_tested'].append({
                'name': strategy_name,
                'success': data.get('success', False),
                'metrics': data.get('metrics', {})
            })
            
        elif event == "training_started":
            self.active_operations[data['task_id']] = {
                'type': 'training',
                'strategy': data['strategy_name'],
                'started_at': datetime.utcnow()
            }
            
        elif event == "insight_saved":
            self.current_session['insights_generated'].append({
                'id': data['insight_id'],
                'title': data['title'],
                'type': data['type']
            })
            
        elif event == "pattern_discovered":
            self.current_session['patterns_discovered'].append({
                'id': data['pattern_id'],
                'name': data['name']
            })
        
        # Save checkpoint
        await self.checkpoint(event, data)
        
        # Update database
        await self._update_session_metrics()
        
        # Emit notification
        await self._emit_progress(event, data)
    
    async def restore_session(self, session_id: str) -> Dict[str, Any]:
        """Restore session after disconnect"""
        # Get session from database
        session_data = await self.db.get_session(session_id)
        if not session_data:
            raise ValueError(f"Session {session_id} not found")
        
        # Get latest checkpoint
        checkpoint = await self.db.get_latest_checkpoint(session_id)
        
        if checkpoint:
            # Restore from checkpoint
            self.current_session = checkpoint['session_state']
            self.active_operations = checkpoint.get('active_operations', {})
        else:
            # Restore from session data only
            self.current_session = {
                'id': session_id,
                'theme': session_data['theme'],
                'hypothesis': session_data['hypothesis'],
                'status': session_data['status'],
                'started_at': session_data['started_at'],
                'strategies_tested': [],
                'strategies_in_progress': {},
                'insights_generated': [],
                'patterns_discovered': []
            }
        
        # Determine what needs to be resumed
        resume_actions = []
        
        # Check for incomplete strategies
        for strategy_name, strategy_data in self.current_session['strategies_in_progress'].items():
            resume_actions.append({
                'action': 'check_strategy_status',
                'strategy': strategy_name,
                'data': strategy_data
            })
        
        # Check for active operations
        for task_id, operation in self.active_operations.items():
            resume_actions.append({
                'action': 'check_operation_status',
                'task_id': task_id,
                'operation': operation
            })
        
        await self._emit_progress("session_restored", {
            'session_id': session_id,
            'strategies_completed': len(self.current_session['strategies_tested']),
            'insights_generated': len(self.current_session['insights_generated']),
            'resume_actions': resume_actions
        })
        
        return {
            'session': self.current_session,
            'resume_actions': resume_actions
        }
    
    async def complete_session(self, key_findings: str = None):
        """Mark session as complete"""
        if not self.current_session:
            return
        
        await self.db.update_session(self.current_session['id'], {
            'status': 'completed',
            'completed_at': datetime.utcnow(),
            'key_findings': key_findings
        })
        
        await self._emit_progress("session_completed", {
            'session_id': self.current_session['id'],
            'total_strategies': len(self.current_session['strategies_tested']),
            'insights_generated': len(self.current_session['insights_generated']),
            'patterns_discovered': len(self.current_session['patterns_discovered'])
        })
        
        self.current_session = None
    
    async def _update_session_metrics(self):
        """Update session metrics in database"""
        if not self.current_session:
            return
            
        successful_strategies = sum(
            1 for s in self.current_session['strategies_tested'] 
            if s.get('success', False)
        )
        
        await self.db.update_session(self.current_session['id'], {
            'total_strategies_tested': len(self.current_session['strategies_tested']),
            'successful_strategies': successful_strategies,
            'metadata': json.dumps({
                'insights_count': len(self.current_session['insights_generated']),
                'patterns_count': len(self.current_session['patterns_discovered'])
            })
        })
    
    async def _emit_progress(self, event: str, data: Dict):
        """Send progress notification"""
        await self.notifier.send({
            'type': 'research_progress',
            'event': event,
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': self.current_session['id'] if self.current_session else None,
            'data': data
        })
    
    def get_current_session_id(self) -> Optional[str]:
        """Get current session ID if active"""
        return self.current_session['id'] if self.current_session else None
```

---

## Task 2.5: Create Notification System
**Time Estimate**: 1 hour

Create `mcp/src/notifier.py`:
```python
"""Simple HTTP notification system"""
import aiohttp
import json
from typing import Dict, Any
import structlog
from .config import NOTIFICATION_URL

logger = structlog.get_logger()

class Notifier:
    """Send notifications via HTTP POST"""
    
    def __init__(self):
        self.url = NOTIFICATION_URL
        self.enabled = bool(self.url)
        
    async def send(self, notification: Dict[str, Any]):
        """Send notification to configured endpoint"""
        if not self.enabled:
            logger.debug("Notifications disabled", notification=notification)
            return
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.url,
                    json=notification,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status != 200:
                        logger.warning(
                            "Notification failed",
                            status=response.status,
                            notification=notification
                        )
        except Exception as e:
            logger.error("Failed to send notification", error=str(e))
```

Update `mcp/src/config.py`:
```python
# Notification configuration
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "")  # Empty = disabled
```

---

## Task 2.6: Create Knowledge Management Tools
**Time Estimate**: 4 hours

Create `mcp/src/tools/knowledge_tools.py`:
```python
"""Knowledge management and insight tools"""
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import frontmatter
import structlog
from ..config import KNOWLEDGE_BASE_PATH
from ..storage.postgres import PostgresDB
from ..state_manager import ResearchStateManager

logger = structlog.get_logger()

class KnowledgeTools:
    """Tools for knowledge management and insights"""
    
    def __init__(self, db: PostgresDB, state_manager: ResearchStateManager):
        self.db = db
        self.state_manager = state_manager
        self.knowledge_path = Path(KNOWLEDGE_BASE_PATH)
        
    def get_save_insight_tool_config(self) -> Dict[str, Any]:
        """Tool configuration for saving insights"""
        return {
            "name": "save_insight",
            "description": """Save a research insight or learning.
            
            Use this to build a knowledge base of what works and doesn't work.
            Each insight should be specific and actionable.
            
            Types:
            - 'failure': What didn't work and why
            - 'success': What worked well
            - 'pattern': Recurring market patterns
            - 'hypothesis': Ideas for future testing
            
            Good insights are:
            - Specific with evidence
            - Actionable for future strategies
            - Well-tagged for retrieval
            
            Examples:
            - Failure: "RSI reversal fails when ADX > 40 (strong trends)"
            - Success: "Volume spike + RSI divergence = 73% win rate"
            - Pattern: "First hour breakouts sustain 65% of time"
            """,
            "input_schema": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["failure", "success", "pattern", "hypothesis"],
                        "description": "Type of insight"
                    },
                    "title": {
                        "type": "string",
                        "description": "Short, descriptive title"
                    },
                    "content": {
                        "type": "string", 
                        "description": "Detailed insight with evidence"
                    },
                    "evidence": {
                        "type": "object",
                        "description": "Supporting data (strategy, metrics, etc.)"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags for categorization"
                    },
                    "importance": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5
                    }
                },
                "required": ["type", "title", "content"]
            }
        }
    
    async def handle_save_insight(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Save insight to database and Obsidian vault"""
        insight_type = params["type"]
        title = params["title"]
        content = params["content"]
        
        # Get current session
        session_id = self.state_manager.get_current_session_id()
        if not session_id:
            return {
                "success": False,
                "error": "No active research session"
            }
        
        # Generate filename
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_title = "".join(c for c in title.lower() if c.isalnum() or c in " -")
        safe_title = safe_title.replace(" ", "-")[:50]
        filename = f"{date_str}-{safe_title}.md"
        
        # Create Obsidian note
        insight_id = str(uuid.uuid4())
        obsidian_path = f"insights/{filename}"
        full_path = self.knowledge_path / obsidian_path
        
        # Ensure directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create markdown content with frontmatter
        post = frontmatter.Post(
            content=self._format_insight_content(params),
            id=insight_id,
            type=insight_type,
            date=date_str,
            session=session_id,
            tags=params.get("tags", []),
            importance=params.get("importance", 5),
            quality_score=0.5
        )
        
        # Write to file
        with open(full_path, 'w') as f:
            f.write(frontmatter.dumps(post))
        
        # Save to database
        db_insight_id = await self.db.save_insight({
            'session_id': session_id,
            'type': insight_type,
            'title': title,
            'summary': content[:200] + "..." if len(content) > 200 else content,
            'obsidian_path': obsidian_path,
            'tags': params.get("tags", []),
            'importance': params.get("importance", 5)
        })
        
        # Update state
        await self.state_manager.update_progress("insight_saved", {
            'insight_id': db_insight_id,
            'title': title,
            'type': insight_type
        })
        
        logger.info("Insight saved", 
                   insight_id=db_insight_id,
                   title=title,
                   path=obsidian_path)
        
        return {
            "success": True,
            "insight_id": db_insight_id,
            "title": title,
            "path": obsidian_path,
            "message": f"Insight saved: {title}"
        }
    
    def _format_insight_content(self, params: Dict[str, Any]) -> str:
        """Format insight content for Obsidian"""
        content = params["content"]
        evidence = params.get("evidence", {})
        
        formatted = f"""# {params['title']}

## Summary
{content}

"""
        
        if evidence:
            formatted += "## Evidence\n"
            if "strategy" in evidence:
                formatted += f"- Strategy: `{evidence['strategy']}`\n"
            if "metrics" in evidence:
                formatted += f"- Metrics: {evidence['metrics']}\n"
            if "period" in evidence:
                formatted += f"- Period: {evidence['period']}\n"
            formatted += "\n"
        
        if "lessons" in params:
            formatted += f"## Lessons Learned\n{params['lessons']}\n\n"
            
        if "next_steps" in params:
            formatted += f"## Next Steps\n{params['next_steps']}\n\n"
            
        return formatted
    
    def get_search_insights_tool_config(self) -> Dict[str, Any]:
        """Tool configuration for searching insights"""
        return {
            "name": "search_insights",
            "description": """Search the knowledge base for insights.
            
            Search by:
            - Query text (searches title and summary)
            - Tags (exact match)
            - Type (failure, success, pattern, hypothesis)
            
            Returns most relevant insights sorted by importance.
            """,
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Text to search for"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tags"
                    },
                    "type": {
                        "type": "string",
                        "enum": ["failure", "success", "pattern", "hypothesis"],
                        "description": "Filter by insight type"
                    }
                }
            }
        }
    
    async def handle_search_insights(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search insights in knowledge base"""
        results = await self.db.search_insights(
            query=params.get("query"),
            tags=params.get("tags"),
            type=params.get("type")
        )
        
        # Enrich with file content if needed
        enriched_results = []
        for result in results[:20]:  # Limit to top 20
            enriched = {
                "id": str(result["id"]),
                "title": result["title"],
                "type": result["type"],
                "summary": result["summary"],
                "tags": result["tags"],
                "importance": result["importance"],
                "created_at": result["created_at"].isoformat(),
                "obsidian_path": result["obsidian_path"]
            }
            enriched_results.append(enriched)
        
        return {
            "success": True,
            "count": len(enriched_results),
            "insights": enriched_results,
            "query": params.get("query", ""),
            "filters": {
                "tags": params.get("tags", []),
                "type": params.get("type")
            }
        }
    
    def get_start_research_tool_config(self) -> Dict[str, Any]:
        """Tool configuration for starting research session"""
        return {
            "name": "start_research_session",
            "description": """Start a new research session.
            
            Use this when beginning a focused research effort.
            Each session should have a clear theme and hypothesis.
            
            Examples:
            - Theme: "Momentum strategies in tech stocks"
              Hypothesis: "RSI + Volume can identify momentum breakouts"
            
            - Theme: "Mean reversion in range-bound markets"  
              Hypothesis: "Bollinger Band extremes predict reversals when ADX < 20"
            """,
            "input_schema": {
                "type": "object",
                "properties": {
                    "theme": {
                        "type": "string",
                        "description": "Research focus area"
                    },
                    "hypothesis": {
                        "type": "string",
                        "description": "What you're trying to prove/disprove"
                    }
                },
                "required": ["theme", "hypothesis"]
            }
        }
    
    async def handle_start_research_session(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Start new research session"""
        theme = params["theme"]
        hypothesis = params["hypothesis"]
        
        session_id = await self.state_manager.start_session(theme, hypothesis)
        
        # Create session folder
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_theme = "".join(c for c in theme.lower() if c.isalnum() or c in " -")
        safe_theme = safe_theme.replace(" ", "-")[:30]
        session_folder = f"sessions/{date_str}-{safe_theme}"
        
        session_path = self.knowledge_path / session_folder
        session_path.mkdir(parents=True, exist_ok=True)
        
        # Create session overview file
        overview_path = session_path / "overview.md"
        with open(overview_path, 'w') as f:
            f.write(f"""# Research Session: {theme}

**Date**: {date_str}  
**Session ID**: {session_id}  
**Status**: Active

## Hypothesis
{hypothesis}

## Progress
- Started: {datetime.now().strftime("%Y-%m-%d %H:%M")}
- Strategies tested: 0
- Insights generated: 0

## Notes
""")
        
        return {
            "success": True,
            "session_id": session_id,
            "theme": theme,
            "hypothesis": hypothesis,
            "session_folder": session_folder,
            "message": f"Research session started: {theme}"
        }
```

---

## Task 2.7: Update Server with Phase 2 Tools
**Time Estimate**: 1 hour

Update `mcp/src/server.py` to include knowledge tools:
```python
# Add imports
from .storage.postgres import PostgresDB
from .state_manager import ResearchStateManager
from .notifier import Notifier
from .tools.knowledge_tools import KnowledgeTools

class KTRDRMCPServer:
    def __init__(self):
        self.server = Server("ktrdr-mcp")
        self.api_client = KTRDRAPIClient()
        self.sqlite_db = ExperimentDB()  # Keep for Phase 1 compatibility
        self.postgres_db = PostgresDB()
        self.notifier = Notifier()
        self.state_manager = ResearchStateManager(self.postgres_db, self.notifier)
        
        # Initialize tools
        self.data_tools = DataTools(self.api_client)
        self.strategy_tools = StrategyTools()
        self.model_tools = ModelTools(self.api_client)
        self.backtest_tools = BacktestTools(self.api_client)
        self.knowledge_tools = KnowledgeTools(self.postgres_db, self.state_manager)
        
        self.setup_tools()
        logger.info("KTRDR MCP Server initialized with knowledge management")
    
    async def initialize(self):
        """Initialize server components"""
        await self.sqlite_db.initialize()
        await self.postgres_db.initialize()
        connected = await self.api_client.check_connection()
        if not connected:
            logger.warning("Could not connect to KTRDR API")
    
    def setup_tools(self):
        """Register all available tools"""
        # ... existing tools ...
        
        # Knowledge tools
        self._add_tool_from_config(
            self.knowledge_tools.get_start_research_tool_config(),
            self.knowledge_tools.handle_start_research_session
        )
        self._add_tool_from_config(
            self.knowledge_tools.get_save_insight_tool_config(),
            self.knowledge_tools.handle_save_insight
        )
        self._add_tool_from_config(
            self.knowledge_tools.get_search_insights_tool_config(),
            self.knowledge_tools.handle_search_insights
        )
        
        logger.info("Tools registered", count=9)  # Updated count
```

---

## Task 2.8: Create Integration Tests
**Time Estimate**: 2 hours

Create `mcp/tests/test_knowledge.py`:
```python
"""Tests for knowledge management"""
import pytest
import tempfile
from pathlib import Path
from src.server import KTRDRMCPServer

@pytest.fixture
async def server_with_session(tmp_path):
    """Create server with active session"""
    # Use temp directory for knowledge base
    knowledge_path = tmp_path / "knowledge"
    knowledge_path.mkdir()
    
    server = KTRDRMCPServer()
    await server.initialize()
    
    # Start research session
    result = await server.knowledge_tools.handle_start_research_session({
        "theme": "Test research",
        "hypothesis": "Testing works"
    })
    
    assert result["success"] is True
    return server, result["session_id"]

@pytest.mark.asyncio
async def test_save_and_search_insight(server_with_session):
    """Test saving and searching insights"""
    server, session_id = server_with_session
    
    # Save insight
    save_result = await server.knowledge_tools.handle_save_insight({
        "type": "failure",
        "title": "RSI fails in strong trends",
        "content": "RSI reversal strategies lose money when trend is strong",
        "evidence": {
            "strategy": "rsi_reversal",
            "metrics": {"sharpe": -0.5, "return": -0.15}
        },
        "tags": ["rsi", "trend", "reversal"],
        "importance": 8
    })
    
    assert save_result["success"] is True
    
    # Search for insight
    search_result = await server.knowledge_tools.handle_search_insights({
        "query": "RSI",
        "type": "failure"
    })
    
    assert search_result["success"] is True
    assert search_result["count"] >= 1
    assert any(i["title"] == "RSI fails in strong trends" 
              for i in search_result["insights"])
```

---

## Task 2.9: Update Documentation
**Time Estimate**: 1 hour

Update `mcp/README.md` with Phase 2 features.

---

## Task 2.10: Manual Testing Checklist
**Time Estimate**: 2 hours

**Test workflow in Claude**:
- [ ] Start research session with theme and hypothesis
- [ ] Create and test a strategy
- [ ] Save insight about the results
- [ ] Search for insights by tag
- [ ] Test session recovery after "disconnect"
- [ ] Verify Obsidian files are created correctly
- [ ] Check PostgreSQL data is persisted

---

## Commit Strategy

```bash
# Create Phase 2 branch
git checkout feature/mcp-server
git pull origin main  # Sync if needed
git checkout -b feature/mcp-phase-2-knowledge

# PostgreSQL setup
git add docker/docker-compose.yml docker/postgres/
git commit -m "feat(mcp): Add PostgreSQL for knowledge management"

# Knowledge structure
git add knowledge/templates/
git commit -m "feat(mcp): Add knowledge vault structure"

# Core components
git add mcp/src/storage/postgres.py
git commit -m "feat(mcp): Add PostgreSQL database manager"

git add mcp/src/state_manager.py mcp/src/notifier.py
git commit -m "feat(mcp): Add unified state management with notifications"

git add mcp/src/tools/knowledge_tools.py
git commit -m "feat(mcp): Add knowledge management tools"

# Integration
git add mcp/src/server.py
git commit -m "feat(mcp): Integrate Phase 2 knowledge tools"

# Tests
git add mcp/tests/test_knowledge.py
git commit -m "test(mcp): Add knowledge management tests"

# Merge
git checkout feature/mcp-server
git merge feature/mcp-phase-2-knowledge
```

---

## Success Criteria

### Phase 2 ✓
- [ ] PostgreSQL database running and accessible
- [ ] Can start/restore research sessions
- [ ] Can save insights to Obsidian vault
- [ ] Can search insights by various criteria
- [ ] Progress notifications working
- [ ] State persistence handles disconnects
- [ ] Knowledge accumulates over multiple sessions
- [ ] Obsidian can browse the knowledge vault

---

## Notes

- PostgreSQL password should be properly secured in production
- Knowledge folder could be backed up separately
- Obsidian vault can be synced to other devices if desired
- The notification URL is optional - leave empty to disable
- Consider adding PostgreSQL backup strategy later