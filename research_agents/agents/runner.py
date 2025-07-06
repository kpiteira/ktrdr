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
log_handlers = [logging.StreamHandler(sys.stdout)]

# Add file handler if log directory exists
log_file_path = os.getenv("AGENT_LOG_FILE", "/app/logs/agent.log")
log_dir = os.path.dirname(log_file_path)
if log_dir and os.path.exists(log_dir):
    log_handlers.append(logging.FileHandler(log_file_path, mode='a'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
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
        """Create agent instance with proper dependency injection"""
        
        database_url = os.getenv("DATABASE_URL")
        
        # Create services based on configuration
        llm_service = None
        ktrdr_service = None
        
        # Initialize LLM service if API key available
        openai_api_key = config.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            from ..services.llm_service import OpenAILLMService
            llm_service = OpenAILLMService(
                api_key=openai_api_key,
                model=config.get("llm_model", "gpt-4")
            )
            logger.info("Created OpenAI LLM service")
        
        # Initialize KTRDR service if URL available
        ktrdr_api_url = config.get("ktrdr_api_url") or os.getenv("KTRDR_API_URL")
        if ktrdr_api_url:
            from ..services.ktrdr_service import HTTPKTRDRService
            ktrdr_service = HTTPKTRDRService(
                api_url=ktrdr_api_url,
                api_key=config.get("ktrdr_api_key") or os.getenv("KTRDR_API_KEY")
            )
            logger.info("Created HTTP KTRDR service")
        
        # Common configuration
        common_config = {
            "database_url": database_url,
            "heartbeat_interval": int(os.getenv("HEARTBEAT_INTERVAL", "30")),
            "max_memory_context": int(os.getenv("MAX_MEMORY_CONTEXT", "50")),
            **config
        }
        
        # Create agent with appropriate services
        if agent_type == "researcher":
            self.agent = ResearcherAgent(
                agent_id, 
                llm_service=llm_service, 
                **common_config
            )
        elif agent_type == "assistant":
            self.agent = AssistantAgent(
                agent_id, 
                ktrdr_service=ktrdr_service, 
                **common_config
            )
        elif agent_type == "research_mvp":
            self.agent = ResearchAgentMVP(agent_id, **common_config)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        logger.info(f"Created {agent_type} agent: {agent_id} with injected services")
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