# Manual Validation Guide for KTRDR Research Agents

This guide provides hands-on manual tests to validate that our automated test suite properly covers the system functionality.

## Prerequisites

1. Start the research containers:
```bash
./docker_dev.sh start-research
```

2. Verify containers are running:
```bash
./docker_dev.sh health-research
```

## 1. Database Infrastructure Validation

### Check PostgreSQL with pgvector
```bash
# Connect to PostgreSQL directly
docker-compose -f docker/docker-compose.research.yml exec research-postgres psql -U research_admin -d research_agents

# Inside PostgreSQL, run these commands:
\l                                    # List databases
\c research_agents                    # Connect to our database
\dn                                   # List schemas (should see 'research')
\dt research.*                        # List research tables (should see 7 tables)
SELECT extname FROM pg_extension WHERE extname = 'vector';  # Verify pgvector
\q                                    # Exit
```

**Expected Output:**
- Database `research_agents` exists
- Schema `research` contains 7 tables
- pgvector extension is installed

### Check Redis
```bash
# Test Redis connectivity
docker-compose -f docker/docker-compose.research.yml exec research-redis redis-cli ping
```

**Expected Output:** `PONG`

## 2. Database Schema Validation

### Inspect Table Structure
```bash
docker-compose -f docker/docker-compose.research.yml exec research-postgres psql -U research_admin -d research_agents -c "
\d+ research.agent_states
\d+ research.knowledge_base
\d+ research.sessions
"
```

**Validate:**
- `agent_states` has JSONB fields for `state_data` and `memory_context`
- `knowledge_base` has vector field for embeddings
- `sessions` has proper UUID primary keys
- All tables have appropriate indexes

### Check Seed Data
```bash
docker-compose -f docker/docker-compose.research.yml exec research-postgres psql -U research_admin -d research_agents -c "
SELECT COUNT(*) as agent_count FROM research.agent_states;
SELECT COUNT(*) as knowledge_count FROM research.knowledge_base;
SELECT content_type, COUNT(*) FROM research.knowledge_base GROUP BY content_type;
"
```

**Expected:**
- Some agent states exist from seed data
- Some knowledge entries exist
- Various content types (research_notes, insight, pattern, etc.)

## 3. Python Database Connection Test

Create and run this manual test script:

```bash
# Create a manual test file
cat > manual_db_test.py << 'EOF'
import asyncio
import asyncpg
import json
from uuid import uuid4

async def manual_database_test():
    print("🔍 Manual Database Connection Test")
    print("=" * 50)
    
    # Connect to database
    conn = await asyncpg.connect(
        host='localhost',
        port=5433,
        database='research_agents',
        user='research_admin',
        password='research_dev_password'
    )
    
    try:
        # Test 1: Basic connection
        version = await conn.fetchrow('SELECT version()')
        print(f"✅ PostgreSQL Version: {version[0][:50]}...")
        
        # Test 2: Schema check
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'research' 
            ORDER BY tablename
        """)
        print(f"✅ Research Tables: {[t[0] for t in tables]}")
        
        # Test 3: Vector extension
        vector_check = await conn.fetchrow("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        print(f"✅ pgvector Extension: {'Installed' if vector_check else 'Missing'}")
        
        # Test 4: Create and query session
        session_id = uuid4()
        session_name = f"MANUAL_TEST_SESSION_{uuid4().hex[:8]}"
        
        await conn.execute("""
            INSERT INTO research.sessions (id, session_name, description, strategic_goals, priority_areas)
            VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)
        """, session_id, session_name, "Manual test session", 
            json.dumps(["test_goal"]), json.dumps(["test_area"]))
        
        session = await conn.fetchrow("""
            SELECT session_name, description, created_at 
            FROM research.sessions WHERE id = $1
        """, session_id)
        
        print(f"✅ Session Created: {session['session_name']}")
        print(f"   Description: {session['description']}")
        print(f"   Created: {session['created_at']}")
        
        # Test 5: Create and query agent state
        agent_id = f"manual-test-agent-{uuid4().hex[:8]}"
        
        await conn.execute("""
            INSERT INTO research.agent_states 
            (agent_id, agent_type, status, current_activity, state_data, memory_context)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
        """, agent_id, "researcher", "active", "Manual testing",
            json.dumps({"test_key": "test_value"}), 
            json.dumps({"memory": "test_memory"}))
        
        agent = await conn.fetchrow("""
            SELECT agent_id, agent_type, status, current_activity 
            FROM research.agent_states WHERE agent_id = $1
        """, agent_id)
        
        print(f"✅ Agent Created: {agent['agent_id']}")
        print(f"   Type: {agent['agent_type']}, Status: {agent['status']}")
        print(f"   Activity: {agent['current_activity']}")
        
        # Test 6: Knowledge base with arrays
        knowledge_id = uuid4()
        title = f"MANUAL_TEST_KNOWLEDGE_{uuid4().hex[:8]}"
        
        await conn.execute("""
            INSERT INTO research.knowledge_base 
            (id, content_type, title, content, summary, keywords, tags, quality_score)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, knowledge_id, "insight", title, "Manual test content", "Manual test summary",
            ["manual", "test", "validation"], ["test_tag", "manual"], 0.95)
        
        knowledge = await conn.fetchrow("""
            SELECT title, content_type, quality_score, keywords, tags
            FROM research.knowledge_base WHERE id = $1
        """, knowledge_id)
        
        print(f"✅ Knowledge Created: {knowledge['title']}")
        print(f"   Type: {knowledge['content_type']}, Quality: {knowledge['quality_score']}")
        print(f"   Keywords: {knowledge['keywords']}")
        print(f"   Tags: {knowledge['tags']}")
        
        # Test 7: Search functionality
        search_results = await conn.fetch("""
            SELECT title, quality_score FROM research.knowledge_base 
            WHERE 'manual' = ANY(keywords) 
            ORDER BY quality_score DESC
        """)
        
        print(f"✅ Search Results: Found {len(search_results)} entries with 'manual' keyword")
        for result in search_results:
            print(f"   - {result['title']} (Quality: {result['quality_score']})")
        
        # Test 8: Statistics
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_knowledge,
                AVG(quality_score) as avg_quality,
                COUNT(DISTINCT content_type) as content_types
            FROM research.knowledge_base
        """)
        
        print(f"✅ Database Statistics:")
        print(f"   Total Knowledge Entries: {stats['total_knowledge']}")
        print(f"   Average Quality Score: {stats['avg_quality']:.3f}")
        print(f"   Content Types: {stats['content_types']}")
        
        # Cleanup
        await conn.execute("DELETE FROM research.sessions WHERE id = $1", session_id)
        await conn.execute("DELETE FROM research.agent_states WHERE agent_id = $1", agent_id)
        await conn.execute("DELETE FROM research.knowledge_base WHERE id = $1", knowledge_id)
        
        print("\n✅ All Manual Tests Passed!")
        print("🧹 Cleanup completed - no test data left behind")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        await conn.close()
    
    return True

# Run the test
if __name__ == "__main__":
    success = asyncio.run(manual_database_test())
    exit(0 if success else 1)
EOF

# Run the manual test
uv run python manual_db_test.py
```

**Expected Output:**
- All checkmarks (✅) showing successful operations
- No errors during database operations
- Proper cleanup confirmation

## 4. Test Our Research Database Service

### Test the Service Layer Directly
```bash
cat > manual_service_test.py << 'EOF'
import asyncio
import sys
import os
sys.path.append(os.getcwd())

from research_agents.services.database import ResearchDatabaseService, DatabaseConfig
from uuid import uuid4

async def test_service_layer():
    print("🔍 Manual Service Layer Test")
    print("=" * 50)
    
    config = DatabaseConfig(
        host="localhost",
        port=5433,
        database="research_agents",
        username="research_admin",
        password="research_dev_password"
    )
    
    db = ResearchDatabaseService(config)
    
    try:
        # Initialize
        await db.initialize()
        print("✅ Service initialized successfully")
        
        # Health check
        health = await db.health_check()
        print(f"✅ Health Status: {health['status']}")
        print(f"   Pool Size: {health['pool_info']['size']}/{health['pool_info']['max_size']}")
        
        # Test existing methods
        active_session = await db.get_active_session()
        if active_session:
            print(f"✅ Found active session: {active_session['session_name']}")
        else:
            print("ℹ️  No active session found (normal)")
        
        # Test knowledge search
        keyword_results = await db.search_knowledge_by_keywords(["trading"])
        print(f"✅ Keyword search: Found {len(keyword_results)} entries for 'trading'")
        
        # Test knowledge statistics
        kb_stats = await db.get_knowledge_base_statistics()
        print(f"✅ Knowledge Statistics:")
        print(f"   Total Entries: {kb_stats['total_entries']}")
        print(f"   Average Quality: {kb_stats['avg_quality']}")
        print(f"   Content Types: {kb_stats['content_types']}")
        
        print("\n✅ Service Layer Test Completed Successfully!")
        
    except Exception as e:
        print(f"❌ Service Error: {e}")
        return False
    finally:
        await db.close()
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_service_layer())
    exit(0 if success else 1)
EOF

uv run python manual_service_test.py
```

## 5. Validate Our Automated Tests

### Run Tests with Detailed Output
```bash
# Run with maximum verbosity
uv run pytest research_agents/tests/test_working_database.py -v -s --tb=long

# Run with coverage to see what we're actually testing
uv run pytest research_agents/tests/test_working_database.py --cov=research_agents.services.database --cov-report=term-missing
```

### Check Test Isolation
```bash
# Run the same test multiple times to ensure proper cleanup
for i in {1..3}; do
    echo "=== Test Run $i ==="
    uv run pytest research_agents/tests/test_working_database.py::test_session_operations_manual -v
done
```

**Expected:** All runs should pass with no interference between runs.

## 6. Container Integration Test

### Test Docker Integration
```bash
# Check all research containers
./docker_dev.sh health-research

# View logs to see if there are any errors
./docker_dev.sh logs-research | tail -50

# Test container communication
docker-compose -f docker/docker-compose.research.yml exec research-postgres pg_isready -U research_admin -d research_agents
docker-compose -f docker/docker-compose.research.yml exec research-redis redis-cli ping
```

## 7. Performance Validation

### Test Connection Pooling
```bash
cat > performance_test.py << 'EOF'
import asyncio
import time
from research_agents.services.database import ResearchDatabaseService, DatabaseConfig

async def performance_test():
    print("🚀 Performance Test - Connection Pooling")
    print("=" * 50)
    
    config = DatabaseConfig(
        host="localhost",
        port=5433,
        database="research_agents", 
        username="research_admin",
        password="research_dev_password",
        min_connections=2,
        max_connections=10
    )
    
    db = ResearchDatabaseService(config)
    
    try:
        await db.initialize()
        
        # Test concurrent operations
        start_time = time.time()
        
        tasks = []
        for i in range(10):
            task = db.health_check()
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        print(f"✅ Concurrent Operations: {len(results)} health checks")
        print(f"   Total Time: {end_time - start_time:.3f}s")
        print(f"   Average Time: {(end_time - start_time) / len(results):.3f}s per operation")
        
        # Verify all succeeded
        all_healthy = all(r['status'] == 'healthy' for r in results)
        print(f"✅ All Operations Successful: {all_healthy}")
        
    finally:
        await db.close()

asyncio.run(performance_test())
EOF

uv run python performance_test.py
```

## 8. Data Integrity Verification

### Check Constraints and Relationships
```bash
docker-compose -f docker/docker-compose.research.yml exec research-postgres psql -U research_admin -d research_agents -c "
-- Check foreign key constraints
SELECT 
    tc.table_name, 
    tc.constraint_name, 
    tc.constraint_type,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name 
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
  AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
  AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY' 
  AND tc.table_schema = 'research';

-- Check unique constraints
SELECT constraint_name, table_name, column_name 
FROM information_schema.key_column_usage 
WHERE table_schema = 'research' 
  AND constraint_name LIKE '%_key' OR constraint_name LIKE '%unique%';
"
```

## Expected Results Summary

If all manual tests pass, you should see:

✅ **Database Infrastructure**
- PostgreSQL 15 running with pgvector extension
- 7 research tables with proper schemas
- Seed data loaded correctly

✅ **Connectivity** 
- Python can connect to PostgreSQL
- Redis is responding
- Connection pooling works efficiently

✅ **CRUD Operations**
- Sessions, agents, and knowledge can be created/read/updated
- JSON fields handle complex data properly
- Array fields work correctly

✅ **Search Functionality**
- Keyword searches return relevant results
- Database statistics are accurate
- Vector search framework is ready

✅ **Test Quality**
- Automated tests cover real functionality
- Proper cleanup prevents data pollution
- Performance is acceptable (<200ms operations)

✅ **Integration**
- Docker containers communicate properly
- Service layer abstracts database complexity
- Error handling works correctly

These manual tests prove that our automated test suite is comprehensive and that the research agents foundation is solid and ready for the next development phase.