"""
Knowledge Integrator Component

Handles all aspects of knowledge integration for the research agent system.
Extracted from ResearchAgentMVP to follow Single Responsibility Principle.

Responsibilities:
- Integrate new insights into the knowledge base
- Search and retrieve relevant knowledge for research context
- Identify successful patterns and strategies
- Manage knowledge quality scoring and relevance
"""

from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime, timezone

from ktrdr import get_logger
from ktrdr.errors import ProcessingError, DataError

from .interfaces import (
    KnowledgeIntegratorInterface,
    ResearchContext,
)
from ..services.database import ResearchDatabaseService

logger = get_logger(__name__)


class KnowledgeIntegrator(KnowledgeIntegratorInterface):
    """
    Concrete implementation of knowledge integration.
    
    Manages the integration of research insights, pattern recognition,
    and knowledge base operations for the research agent system.
    """
    
    def __init__(
        self,
        database_service: ResearchDatabaseService,
        min_quality_threshold: float = 0.3,
        max_search_results: int = 50,
        pattern_min_frequency: int = 3
    ):
        self.db_service = database_service
        self.min_quality_threshold = min_quality_threshold
        self.max_search_results = max_search_results
        self.pattern_min_frequency = pattern_min_frequency
        
        # Knowledge cache for performance
        self.knowledge_cache: Dict[str, Any] = {}
        self.cache_timestamp: Optional[datetime] = None
        self.cache_ttl_minutes = 30
        
        logger.info(f"Knowledge integrator initialized with quality_threshold={min_quality_threshold}, max_results={max_search_results}")
    
    async def integrate_insights(
        self,
        insights: List[str],
        context: ResearchContext
    ) -> Dict[str, Any]:
        """Integrate new insights into knowledge base"""
        
        try:
            logger.info(f"Integrating {len(insights)} insights for session {context.session_id}")
            
            integration_results = {
                "integrated_count": 0,
                "rejected_count": 0,
                "knowledge_entry_ids": [],
                "quality_scores": []
            }
            
            for i, insight in enumerate(insights):
                try:
                    # Calculate quality score based on context
                    quality_score = self._calculate_insight_quality(insight, context)
                    
                    if quality_score < self.min_quality_threshold:
                        logger.warning(f"Rejecting insight {i} with quality score {quality_score} below threshold {self.min_quality_threshold}")
                        integration_results["rejected_count"] += 1
                        continue
                    
                    # Create knowledge entry
                    entry_id = await self.db_service.create_knowledge_entry(
                        content=insight,
                        knowledge_type="research_insight",
                        source_experiment_id=context.experiments[0] if context.experiments else None,
                        source_agent_id=context.agent_id,
                        tags=self._generate_tags(insight, context),
                        quality_score=quality_score,
                        metadata={
                            "session_id": str(context.session_id),
                            "cycle_id": str(context.cycle_id),
                            "strategy": context.strategy,
                            "phase": context.current_phase,
                            "integration_timestamp": datetime.now(timezone.utc).isoformat()
                        }
                    )
                    
                    integration_results["integrated_count"] += 1
                    integration_results["knowledge_entry_ids"].append(entry_id)
                    integration_results["quality_scores"].append(quality_score)
                    
                    logger.debug(f"Integrated insight {i} with quality score {quality_score}, entry_id: {entry_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to integrate insight {i}: {e}")
                    integration_results["rejected_count"] += 1
            
            # Refresh knowledge cache after integration
            await self._refresh_cache()
            
            logger.info(f"Knowledge integration completed: {integration_results['integrated_count']} integrated, {integration_results['rejected_count']} rejected")
            return integration_results
            
        except Exception as e:
            logger.error(f"Failed to integrate insights: {e}")
            raise ProcessingError(
                "Knowledge integration failed",
                error_code="KNOWLEDGE_INTEGRATION_FAILED",
                details={
                    "session_id": str(context.session_id),
                    "cycle_id": str(context.cycle_id),
                    "insight_count": len(insights),
                    "original_error": str(e)
                }
            ) from e
    
    async def search_knowledge(
        self,
        query: str,
        context: ResearchContext
    ) -> List[Dict[str, Any]]:
        """Search knowledge base for relevant information"""
        
        try:
            logger.info(f"Searching knowledge base for: '{query}' (session: {context.session_id})")
            
            # Use database service to search knowledge entries
            search_results = await self.db_service.search_knowledge_entries(
                query=query,
                limit=self.max_search_results,
                min_quality_score=self.min_quality_threshold,
                tags=[context.strategy] if context.strategy else None
            )
            
            # Enhance results with relevance scoring
            enhanced_results = []
            for result in search_results:
                relevance_score = self._calculate_relevance(result, query, context)
                enhanced_result = {
                    **result,
                    "relevance_score": relevance_score,
                    "search_context": {
                        "query": query,
                        "session_id": str(context.session_id),
                        "strategy": context.strategy
                    }
                }
                enhanced_results.append(enhanced_result)
            
            # Sort by relevance score (descending)
            enhanced_results.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            logger.info(f"Found {len(enhanced_results)} relevant knowledge entries")
            return enhanced_results
            
        except Exception as e:
            logger.error(f"Failed to search knowledge base: {e}")
            raise ProcessingError(
                "Knowledge search failed",
                error_code="KNOWLEDGE_SEARCH_FAILED",
                details={
                    "query": query,
                    "session_id": str(context.session_id),
                    "original_error": str(e)
                }
            ) from e
    
    async def get_patterns(
        self,
        context: ResearchContext
    ) -> List[Dict[str, Any]]:
        """Get successful patterns from knowledge base"""
        
        try:
            logger.info(f"Retrieving successful patterns for strategy: {context.strategy}")
            
            # Check cache first
            cache_key = f"patterns_{context.strategy}"
            if self._is_cache_valid() and cache_key in self.knowledge_cache:
                logger.debug("Returning patterns from cache")
                return self.knowledge_cache[cache_key]
            
            # Query for high-quality knowledge entries
            high_quality_entries = await self.db_service.get_knowledge_entries(
                knowledge_type="research_insight",
                min_quality_score=0.7,  # High quality threshold for patterns
                tags=[context.strategy] if context.strategy else None,
                limit=100
            )
            
            # Analyze patterns in the entries
            patterns = self._extract_patterns(high_quality_entries, context)
            
            # Cache the results
            self.knowledge_cache[cache_key] = patterns
            
            logger.info(f"Found {len(patterns)} successful patterns")
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to get patterns: {e}")
            raise ProcessingError(
                "Pattern retrieval failed",
                error_code="PATTERN_RETRIEVAL_FAILED",
                details={
                    "strategy": context.strategy,
                    "session_id": str(context.session_id),
                    "original_error": str(e)
                }
            ) from e
    
    def _calculate_insight_quality(
        self,
        insight: str,
        context: ResearchContext
    ) -> float:
        """Calculate quality score for an insight"""
        
        quality_score = 0.5  # Base score
        
        # Length factor (not too short, not too long)
        length = len(insight)
        if 50 <= length <= 500:
            quality_score += 0.1
        elif length < 20:
            quality_score -= 0.2
        
        # Context fitness scores factor
        if context.progress and "avg_fitness_score" in context.progress:
            avg_fitness = context.progress["avg_fitness_score"]
            quality_score += min(avg_fitness * 0.3, 0.3)  # Up to 0.3 boost
        
        # Strategy-specific keywords
        strategy_keywords = {
            "exploratory": ["novel", "innovative", "exploration", "new"],
            "focused": ["optimization", "refinement", "improvement", "focused"],
            "optimization": ["performance", "efficiency", "optimal", "maximize"],
            "validation": ["validation", "confirmation", "verification", "robust"]
        }
        
        keywords = strategy_keywords.get(context.strategy, [])
        keyword_matches = sum(1 for keyword in keywords if keyword.lower() in insight.lower())
        quality_score += keyword_matches * 0.05  # Small boost per keyword
        
        # Ensure score is between 0 and 1
        return max(0.0, min(1.0, quality_score))
    
    def _generate_tags(
        self,
        insight: str,
        context: ResearchContext
    ) -> List[str]:
        """Generate relevant tags for an insight"""
        
        tags = [
            "autonomous_research",
            context.strategy,
            context.current_phase
        ]
        
        # Add content-based tags
        insight_lower = insight.lower()
        
        if any(keyword in insight_lower for keyword in ["profit", "return", "gain"]):
            tags.append("profitability")
        
        if any(keyword in insight_lower for keyword in ["risk", "drawdown", "loss"]):
            tags.append("risk_management")
        
        if any(keyword in insight_lower for keyword in ["volatility", "variance", "stability"]):
            tags.append("volatility")
        
        if any(keyword in insight_lower for keyword in ["trend", "momentum", "direction"]):
            tags.append("trend_following")
        
        if any(keyword in insight_lower for keyword in ["mean", "reversion", "contrarian"]):
            tags.append("mean_reversion")
        
        # Remove duplicates
        return list(set(tags))
    
    def _calculate_relevance(
        self,
        result: Dict[str, Any],
        query: str,
        context: ResearchContext
    ) -> float:
        """Calculate relevance score for a search result"""
        
        relevance = 0.0
        
        # Text similarity (simple keyword matching)
        query_words = set(query.lower().split())
        content_words = set(result.get("content", "").lower().split())
        
        if query_words and content_words:
            overlap = len(query_words.intersection(content_words))
            relevance += (overlap / len(query_words)) * 0.4
        
        # Quality score factor
        quality_score = result.get("quality_score", 0.0)
        relevance += quality_score * 0.3
        
        # Strategy alignment
        result_tags = result.get("tags", [])
        if context.strategy in result_tags:
            relevance += 0.2
        
        # Recency factor (newer insights are more relevant)
        created_at = result.get("created_at")
        if created_at:
            # Simple recency boost - can be made more sophisticated
            relevance += 0.1
        
        return min(1.0, relevance)
    
    def _extract_patterns(
        self,
        entries: List[Dict[str, Any]],
        context: ResearchContext
    ) -> List[Dict[str, Any]]:
        """Extract successful patterns from knowledge entries"""
        
        patterns = []
        
        # Group entries by common characteristics
        # This is a simplified pattern extraction - can be made more sophisticated
        
        # Pattern 1: High-performing strategy types
        strategy_performance = {}
        
        for entry in entries:
            metadata = entry.get("metadata", {})
            strategy = metadata.get("strategy")
            quality = entry.get("quality_score", 0.0)
            
            if strategy and quality > 0.7:
                if strategy not in strategy_performance:
                    strategy_performance[strategy] = []
                strategy_performance[strategy].append(quality)
        
        # Create patterns from strategy performance
        for strategy, scores in strategy_performance.items():
            if len(scores) >= self.pattern_min_frequency:
                avg_score = sum(scores) / len(scores)
                patterns.append({
                    "pattern_type": "successful_strategy",
                    "strategy": strategy,
                    "frequency": len(scores),
                    "average_quality": avg_score,
                    "confidence": min(len(scores) / 10.0, 1.0),  # More occurrences = higher confidence
                    "description": f"Strategy '{strategy}' has shown consistent success with {len(scores)} instances and {avg_score:.2f} average quality"
                })
        
        # Pattern 2: Common keywords in high-quality insights
        all_words = {}
        for entry in entries:
            if entry.get("quality_score", 0.0) > 0.8:
                words = entry.get("content", "").lower().split()
                for word in words:
                    if len(word) > 4:  # Skip short words
                        all_words[word] = all_words.get(word, 0) + 1
        
        # Find frequently occurring words
        frequent_words = [(word, count) for word, count in all_words.items() if count >= self.pattern_min_frequency]
        frequent_words.sort(key=lambda x: x[1], reverse=True)
        
        if frequent_words:
            patterns.append({
                "pattern_type": "common_themes",
                "themes": frequent_words[:10],  # Top 10 themes
                "description": f"Common themes in successful insights: {', '.join([word for word, _ in frequent_words[:5]])}"
            })
        
        logger.debug(f"Extracted {len(patterns)} patterns from {len(entries)} entries")
        return patterns
    
    async def _refresh_cache(self) -> None:
        """Refresh the knowledge cache"""
        
        try:
            self.knowledge_cache.clear()
            self.cache_timestamp = datetime.now(timezone.utc)
            logger.debug("Knowledge cache refreshed")
            
        except Exception as e:
            logger.error(f"Failed to refresh cache: {e}")
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        
        if not self.cache_timestamp:
            return False
        
        age_minutes = (datetime.now(timezone.utc) - self.cache_timestamp).total_seconds() / 60
        return age_minutes < self.cache_ttl_minutes