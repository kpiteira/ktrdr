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