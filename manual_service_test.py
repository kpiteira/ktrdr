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