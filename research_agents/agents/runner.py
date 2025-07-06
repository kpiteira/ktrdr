"""
Agent runner for KTRDR Research Agents

Entry point for running research agent instances in containers.
Supports different agent types and configurations.
"""

import asyncio
import os
import logging
import signal
import sys
from typing import Optional

from .researcher import ResearcherAgent
from .assistant import AssistantAgent
from .research_agent_mvp import ResearchAgentMVP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/agent.log', mode='a')
    ]
)

logger = logging.getLogger(__name__)


class AgentRunner:
    """
    Agent runner that manages agent lifecycle
    """
    
    def __init__(self):
        self.agent = None
        self.shutdown_event = asyncio.Event()
    
    async def create_agent(self, agent_type: str, agent_id: str, **config):
        """Create agent instance based on type"""
        
        database_url = os.getenv("DATABASE_URL")
        coordinator_url = os.getenv("COORDINATOR_URL")
        ktrdr_api_url = os.getenv("KTRDR_API_URL")
        
        common_config = {
            "database_url": database_url,
            "coordinator_url": coordinator_url,
            "ktrdr_api_url": ktrdr_api_url,
            "openai_api_key": os.getenv("OPENAI_API_KEY"),
            "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY"),
            "heartbeat_interval": int(os.getenv("HEARTBEAT_INTERVAL", "30")),
            "max_memory_context": int(os.getenv("MAX_MEMORY_CONTEXT", "50")),
            **config
        }
        
        if agent_type == "researcher":
            self.agent = ResearcherAgent(agent_id, **common_config)
        elif agent_type == "assistant":
            self.agent = AssistantAgent(agent_id, **common_config)
        elif agent_type == "research_mvp":
            self.agent = ResearchAgentMVP(agent_id, **common_config)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        logger.info(f"Created {agent_type} agent: {agent_id}")
        return self.agent
    
    async def run_agent(self):
        """Run the agent with graceful shutdown handling"""
        try:
            if not self.agent:
                raise RuntimeError("No agent created")
            
            # Setup signal handlers for graceful shutdown
            def signal_handler():
                logger.info("Received shutdown signal")
                self.shutdown_event.set()
            
            # Handle SIGTERM and SIGINT
            loop = asyncio.get_event_loop()
            for sig in [signal.SIGTERM, signal.SIGINT]:
                loop.add_signal_handler(sig, signal_handler)
            
            # Start agent in background
            agent_task = asyncio.create_task(self.agent.run())
            
            # Wait for shutdown signal or agent completion
            done, pending = await asyncio.wait(
                [agent_task, asyncio.create_task(self.shutdown_event.wait())],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel any pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # If agent task completed, check for exceptions
            if agent_task in done:
                try:
                    await agent_task
                except Exception as e:
                    logger.error(f"Agent execution failed: {e}")
                    raise
            
            logger.info("Agent runner shutdown completed")
            
        except Exception as e:
            logger.error(f"Agent runner error: {e}")
            raise


async def main():
    """Main entry point for agent runner"""
    try:
        # Get configuration from environment
        agent_id = os.getenv("AGENT_ID", "research-agent-001")
        agent_type = os.getenv("AGENT_TYPE", "research_mvp")  # Default to MVP
        
        logger.info(f"Starting agent runner: {agent_type} ({agent_id})")
        
        # Create and run agent
        runner = AgentRunner()
        await runner.create_agent(agent_type, agent_id)
        await runner.run_agent()
        
    except KeyboardInterrupt:
        logger.info("Agent runner interrupted by user")
    except Exception as e:
        logger.error(f"Agent runner failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())