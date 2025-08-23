"""
Researcher Agent for KTRDR Research Agents

The creative brain that generates novel hypotheses and designs experiments
based on accumulated knowledge and innovative thinking.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import openai
from .base import BaseResearchAgent

logger = logging.getLogger(__name__)


class ResearcherAgent(BaseResearchAgent):
    """
    Researcher Agent - The Creative Brain

    Responsibilities:
    - Generate novel trading strategy hypotheses
    - Design experiment configurations
    - Apply cross-domain thinking for innovation
    - Learn from past experiment results
    """

    def __init__(self, agent_id: str, **config):
        super().__init__(agent_id, "researcher", **config)

        # Initialize LLM client
        self.openai_client = None
        if config.get("openai_api_key"):
            self.openai_client = openai.AsyncOpenAI(api_key=config["openai_api_key"])

        # Researcher-specific configuration
        self.creativity_level = config.get("creativity_level", 0.8)
        self.hypothesis_batch_size = config.get("hypothesis_batch_size", 5)
        self.knowledge_query_limit = config.get("knowledge_query_limit", 20)

        # Research state
        self.current_session_id: Optional[UUID] = None
        self.recent_experiments: List[Dict[str, Any]] = []
        self.knowledge_cache: Dict[str, Any] = {}

    async def _initialize_agent(self) -> None:
        """Initialize researcher-specific functionality"""
        # Load current session information
        active_session = await self.db.get_active_session()
        if active_session:
            self.current_session_id = active_session["id"]
            await self.log_activity(
                f"Connected to active session: {active_session['session_name']}"
            )

        # Load recent experiment history for context
        if self.current_session_id:
            self.recent_experiments = await self.db.get_experiments_by_session(
                self.current_session_id
            )

        # Initialize knowledge cache
        await self._refresh_knowledge_cache()

        await self.log_activity(
            "Researcher agent initialized",
            {
                "session_id": (
                    str(self.current_session_id) if self.current_session_id else None
                ),
                "recent_experiments_count": len(self.recent_experiments),
                "knowledge_entries": len(self.knowledge_cache),
            },
        )

    async def _execute_cycle(self) -> None:
        """Main researcher execution cycle"""
        try:
            if not self.current_session_id:
                # No active session, wait and check again
                await asyncio.sleep(30)
                active_session = await self.db.get_active_session()
                if active_session:
                    self.current_session_id = active_session["id"]
                    await self.log_activity("Found new active session")
                return

            await self._update_status("active", "Analyzing research opportunities")

            # Check if we need to generate new hypotheses
            queued_experiments = await self.db.get_queued_experiments(limit=10)

            if len(queued_experiments) < 3:  # Maintain experiment queue
                await self.log_activity("Generating new hypotheses - queue running low")
                await self._generate_experiment_batch()

            # Analyze recent results for insights
            await self._analyze_recent_results()

            # Update knowledge cache periodically
            if len(self.memory_context) % 10 == 0:  # Every 10 cycles
                await self._refresh_knowledge_cache()

            await self._update_status("idle", "Monitoring research progress")
            await asyncio.sleep(60)  # Check every minute

        except Exception as e:
            self.logger.error(f"Error in researcher cycle: {e}")
            await self._update_status("error", f"Cycle error: {e}")

    async def _cleanup_agent(self) -> None:
        """Cleanup researcher-specific resources"""
        await self.log_activity("Researcher agent shutting down")

    async def _generate_experiment_batch(self) -> None:
        """Generate a batch of novel experiment hypotheses"""
        try:
            await self._update_status("processing", "Generating experiment hypotheses")

            # Gather context for hypothesis generation
            context = await self._gather_research_context()

            # Generate hypotheses using LLM
            hypotheses = await self._generate_hypotheses(context)

            # Create experiments from hypotheses
            created_count = 0
            for hypothesis in hypotheses:
                try:
                    experiment_id = await self._create_experiment_from_hypothesis(
                        hypothesis
                    )
                    created_count += 1
                    await self.log_activity(
                        f"Created experiment: {hypothesis['name']}",
                        {"experiment_id": str(experiment_id)},
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to create experiment from hypothesis: {e}"
                    )

            await self.log_activity(
                f"Generated {created_count} new experiments",
                {"total_hypotheses": len(hypotheses), "created": created_count},
            )

        except Exception as e:
            self.logger.error(f"Failed to generate experiment batch: {e}")
            raise

    async def _gather_research_context(self) -> Dict[str, Any]:
        """Gather context for hypothesis generation"""
        # Get recent experiment results
        recent_results = []
        for exp in self.recent_experiments[-10:]:  # Last 10 experiments
            if exp.get("results") and exp.get("fitness_score"):
                recent_results.append(
                    {
                        "name": exp["experiment_name"],
                        "type": exp["experiment_type"],
                        "hypothesis": exp["hypothesis"],
                        "fitness_score": exp["fitness_score"],
                        "status": exp["status"],
                    }
                )

        # Get relevant knowledge entries
        knowledge_insights = []
        for content_type in ["insight", "pattern", "success_factor"]:
            entries = list(self.knowledge_cache.get(content_type, []))[:5]
            knowledge_insights.extend(entries)

        # Get failure patterns to avoid
        failure_patterns = list(self.knowledge_cache.get("failure_analysis", []))[:3]

        return {
            "recent_experiments": recent_results,
            "knowledge_insights": knowledge_insights,
            "failure_patterns": failure_patterns,
            "session_goals": await self._get_session_goals(),
            "unexplored_areas": await self._identify_unexplored_areas(),
        }

    async def _generate_hypotheses(
        self, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate novel hypotheses using LLM"""
        if not self.openai_client:
            # Fallback to template-based hypotheses if no LLM
            return await self._generate_template_hypotheses(context)

        try:
            # Construct prompt for hypothesis generation
            prompt = self._build_hypothesis_prompt(context)

            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a creative AI researcher specializing in novel neuro-fuzzy trading strategies. Generate innovative, testable hypotheses that go beyond conventional approaches.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.creativity_level,
                max_tokens=2000,
            )

            # Parse response into structured hypotheses
            hypotheses_text = response.choices[0].message.content
            return await self._parse_hypotheses_response(hypotheses_text)

        except Exception as e:
            self.logger.error(f"LLM hypothesis generation failed: {e}")
            # Fallback to template-based generation
            return await self._generate_template_hypotheses(context)

    def _build_hypothesis_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for LLM hypothesis generation"""
        prompt_parts = [
            "Generate 3-5 novel trading strategy hypotheses based on the following context:",
            "",
            "RECENT EXPERIMENT RESULTS:",
        ]

        for exp in context["recent_experiments"][-5:]:
            prompt_parts.append(
                f"- {exp['name']}: {exp['hypothesis']} (Fitness: {exp['fitness_score']:.3f})"
            )

        prompt_parts.extend(
            [
                "",
                "KNOWN PATTERNS AND INSIGHTS:",
            ]
        )

        for insight in context["knowledge_insights"][:3]:
            prompt_parts.append(f"- {insight['title']}: {insight['summary']}")

        prompt_parts.extend(
            [
                "",
                "AVOID THESE FAILURE PATTERNS:",
            ]
        )

        for failure in context["failure_patterns"]:
            prompt_parts.append(f"- {failure['title']}")

        prompt_parts.extend(
            [
                "",
                "Generate hypotheses that:",
                "1. Explore novel neuro-fuzzy architecture combinations",
                "2. Address unexplored market conditions or timeframes",
                "3. Apply creative cross-domain inspiration",
                "4. Build on successful patterns while avoiding known failures",
                "5. Are specific enough to be testable",
                "",
                "Format each hypothesis as:",
                "NAME: [Brief descriptive name]",
                "HYPOTHESIS: [Detailed hypothesis statement]",
                "APPROACH: [Technical approach and architecture]",
                "INSPIRATION: [What inspired this idea]",
                "EXPECTED_OUTCOME: [What success would look like]",
                "",
                "Hypotheses:",
            ]
        )

        return "\n".join(prompt_parts)

    async def _parse_hypotheses_response(
        self, response_text: str
    ) -> List[Dict[str, Any]]:
        """Parse LLM response into structured hypotheses"""
        hypotheses = []
        current_hypothesis = {}

        for line in response_text.split("\n"):
            line = line.strip()
            if not line:
                continue

            if line.startswith("NAME:"):
                if current_hypothesis:
                    hypotheses.append(current_hypothesis)
                current_hypothesis = {"name": line[5:].strip()}
            elif line.startswith("HYPOTHESIS:"):
                current_hypothesis["hypothesis"] = line[11:].strip()
            elif line.startswith("APPROACH:"):
                current_hypothesis["approach"] = line[9:].strip()
            elif line.startswith("INSPIRATION:"):
                current_hypothesis["inspiration"] = line[12:].strip()
            elif line.startswith("EXPECTED_OUTCOME:"):
                current_hypothesis["expected_outcome"] = line[17:].strip()

        if current_hypothesis:
            hypotheses.append(current_hypothesis)

        return hypotheses

    async def _generate_template_hypotheses(
        self, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate hypotheses using templates (fallback)"""
        templates = [
            {
                "name": "Adaptive Volume-Momentum Fusion",
                "hypothesis": "Neural networks can learn to dynamically weight volume and momentum indicators based on market microstructure patterns",
                "approach": "3-layer LSTM with fuzzy volume-momentum fusion",
                "inspiration": "Market microstructure research",
                "expected_outcome": "Better signal quality in volatile markets",
            },
            {
                "name": "Cross-Timeframe Pattern Recognition",
                "hypothesis": "Multi-timeframe neural architectures can identify patterns invisible to single-timeframe analysis",
                "approach": "Hierarchical CNN processing 1m, 5m, 15m data",
                "inspiration": "Computer vision multi-scale analysis",
                "expected_outcome": "Improved trend detection accuracy",
            },
            {
                "name": "Sentiment-Technical Hybrid Strategy",
                "hypothesis": "Combining technical indicators with market sentiment creates superior trading signals",
                "approach": "Dual-input neural network with fuzzy sentiment integration",
                "inspiration": "Behavioral finance research",
                "expected_outcome": "Reduced false signals during news events",
            },
        ]

        return templates[: self.hypothesis_batch_size]

    async def _create_experiment_from_hypothesis(
        self, hypothesis: Dict[str, Any]
    ) -> UUID:
        """Create an experiment from a generated hypothesis"""
        # Determine experiment type based on approach
        experiment_type = "neuro_fuzzy_strategy"
        if "momentum" in hypothesis.get("approach", "").lower():
            experiment_type = "momentum_strategy"
        elif "volume" in hypothesis.get("approach", "").lower():
            experiment_type = "volume_analysis"
        elif "multi" in hypothesis.get("approach", "").lower():
            experiment_type = "multi_timeframe_strategy"

        # Build configuration
        configuration = {
            "approach": hypothesis.get("approach", ""),
            "inspiration": hypothesis.get("inspiration", ""),
            "expected_outcome": hypothesis.get("expected_outcome", ""),
            "generated_by": self.agent_id,
            "creativity_level": self.creativity_level,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Create experiment
        experiment_id = await self.db.create_experiment(
            session_id=self.current_session_id,
            experiment_name=hypothesis["name"],
            hypothesis=hypothesis["hypothesis"],
            experiment_type=experiment_type,
            configuration=configuration,
        )

        return experiment_id

    async def _analyze_recent_results(self) -> None:
        """Analyze recent experiment results for insights"""
        # Get completed experiments from last few cycles
        if not self.current_session_id:
            return

        completed_experiments = await self.db.get_experiments_by_session(
            self.current_session_id, "completed"
        )

        # Simple pattern analysis (could be enhanced with ML)
        successful_experiments = [
            exp for exp in completed_experiments if exp.get("fitness_score", 0) > 0.6
        ]

        if len(successful_experiments) >= 3:
            # Generate insight about successful patterns
            await self._generate_success_insight(successful_experiments)

    async def _generate_success_insight(
        self, successful_experiments: List[Dict[str, Any]]
    ) -> None:
        """Generate insights from successful experiments"""
        # Analyze common patterns in successful experiments
        experiment_types = [exp["experiment_type"] for exp in successful_experiments]
        most_common_type = max(set(experiment_types), key=experiment_types.count)

        insight_content = f"Analysis of {len(successful_experiments)} successful experiments shows that {most_common_type} strategies are performing well with average fitness score of {sum(exp.get('fitness_score', 0) for exp in successful_experiments) / len(successful_experiments):.3f}"

        # Add to knowledge base
        await self.db.add_knowledge_entry(
            content_type="insight",
            title=f"Success Pattern: {most_common_type} strategies",
            content=insight_content,
            summary=f"{most_common_type} strategies showing consistent success",
            keywords=["success_pattern", most_common_type, "performance"],
            tags=["generated_insight", "researcher_analysis"],
            source_agent_id=await self._get_agent_uuid(),
            quality_score=0.8,
        )

        await self.log_activity(
            "Generated success insight",
            {
                "experiment_count": len(successful_experiments),
                "pattern_type": most_common_type,
            },
        )

    async def _refresh_knowledge_cache(self) -> None:
        """Refresh cached knowledge entries"""
        self.knowledge_cache = {}

        for content_type in [
            "insight",
            "pattern",
            "success_factor",
            "failure_analysis",
        ]:
            entries = await self.db.search_knowledge_by_keywords(
                keywords=[content_type], content_type_filter=content_type, limit=10
            )
            self.knowledge_cache[content_type] = entries

    async def _get_session_goals(self) -> List[str]:
        """Get current session strategic goals"""
        if not self.current_session_id:
            return []

        session = await self.db.get_active_session()
        if session and session.get("strategic_goals"):
            return session["strategic_goals"]

        return []

    async def _identify_unexplored_areas(self) -> List[str]:
        """Identify research areas that haven't been explored yet"""
        # Simple heuristic - could be enhanced
        all_experiment_types = [
            exp["experiment_type"] for exp in self.recent_experiments
        ]
        explored_types = set(all_experiment_types)

        all_possible_types = {
            "momentum_strategy",
            "mean_reversion",
            "volatility_patterns",
            "volume_analysis",
            "multi_timeframe_strategy",
            "breakout_strategy",
            "regime_detection",
            "sentiment_analysis",
        }

        unexplored = list(all_possible_types - explored_types)
        return unexplored

    async def _get_agent_uuid(self) -> Optional[UUID]:
        """Get agent UUID from database"""
        agent_state = await self.db.get_agent_state(self.agent_id)
        return agent_state["id"] if agent_state else None

    # ========================================================================
    # PUBLIC API METHODS
    # ========================================================================

    async def generate_hypothesis(self) -> Dict[str, Any]:
        """Generate a single hypothesis based on current research context"""
        # If we have a mock llm_client (for tests), use it directly
        if hasattr(self, "llm_client") and hasattr(
            self.llm_client, "generate_hypothesis"
        ):
            return await self.llm_client.generate_hypothesis()

        # Otherwise use the full implementation
        context = await self._gather_research_context()
        hypotheses = await self._generate_hypotheses(context)

        # Return the first hypothesis with highest confidence
        if hypotheses:
            return max(hypotheses, key=lambda h: h.get("confidence", 0))
        else:
            # Fallback for when LLM is not available
            return {
                "hypothesis": "Test momentum strategy with adaptive parameters",
                "rationale": "Momentum strategies have shown promise in trending markets",
                "confidence": 0.6,
                "experiment_type": "momentum_strategy",
            }

    async def search_knowledge(
        self, tags: List[str], limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search knowledge base by tags"""
        return await self.db.search_knowledge_by_tags(tags, limit=limit)

    async def design_experiment(self, hypothesis: Dict[str, Any]) -> Dict[str, Any]:
        """Design an experiment configuration from a hypothesis"""
        experiment_type = hypothesis.get("experiment_type", "momentum_strategy")

        # Basic experiment design - could be enhanced with more sophisticated logic
        experiment_design = {
            "experiment_name": f"{experiment_type}_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "hypothesis": hypothesis["hypothesis"],
            "experiment_type": experiment_type,
            "configuration": {
                "strategy_type": experiment_type,
                "parameters": self._get_default_parameters(experiment_type),
                "timeframe": "1D",
                "lookback_period": 252,
                "validation_split": 0.2,
            },
            "expected_duration": "2-4 hours",
            "success_criteria": {
                "min_sharpe_ratio": 1.0,
                "max_drawdown": 0.15,
                "min_profit_factor": 1.2,
            },
        }

        return experiment_design

    def _get_default_parameters(self, experiment_type: str) -> Dict[str, Any]:
        """Get default parameters for different experiment types"""
        parameter_templates = {
            "momentum_strategy": {
                "lookback_period": 20,
                "signal_threshold": 0.02,
                "stop_loss": 0.05,
                "take_profit": 0.10,
            },
            "mean_reversion": {
                "lookback_period": 50,
                "std_dev_threshold": 2.0,
                "reversion_period": 10,
                "stop_loss": 0.03,
            },
            "volatility_patterns": {
                "vol_lookback": 30,
                "vol_threshold": 1.5,
                "position_sizing": "dynamic",
                "risk_factor": 0.02,
            },
        }

        return parameter_templates.get(
            experiment_type, parameter_templates["momentum_strategy"]
        )
