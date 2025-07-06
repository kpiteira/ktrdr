"""
LLM Service implementations for KTRDR Research Agents

Provides OpenAI-based and null object implementations of the LLM service interface.
"""

from typing import Optional, Dict, Any, List
import logging

from .interfaces import LLMService, LLMServiceError

logger = logging.getLogger(__name__)


class OpenAILLMService(LLMService):
    """OpenAI implementation of LLM service"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model
        self.client = None
        
        if api_key:
            try:
                import openai
                self.client = openai.AsyncOpenAI(api_key=api_key)
            except ImportError:
                logger.warning("OpenAI library not available")
                self.client = None
    
    async def generate_hypothesis(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a single hypothesis using OpenAI"""
        if not self.client:
            raise LLMServiceError("OpenAI client not available - check API key and installation")
        
        try:
            prompt = self._build_hypothesis_prompt(context)
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a creative AI researcher specializing in novel neuro-fuzzy trading strategies. Generate innovative, testable hypotheses that go beyond conventional approaches."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.8,
                max_tokens=1000
            )
            
            return self._parse_hypothesis_response(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"OpenAI hypothesis generation failed: {e}")
            raise LLMServiceError(f"Failed to generate hypothesis: {e}") from e
    
    async def generate_hypotheses(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate multiple hypotheses using OpenAI"""
        if not self.client:
            raise LLMServiceError("OpenAI client not available - check API key and installation")
        
        try:
            prompt = self._build_hypotheses_prompt(context)
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a creative AI researcher specializing in novel neuro-fuzzy trading strategies. Generate 3-5 innovative, testable hypotheses."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.8,
                max_tokens=2000
            )
            
            return self._parse_hypotheses_response(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"OpenAI hypotheses generation failed: {e}")
            raise LLMServiceError(f"Failed to generate hypotheses: {e}") from e
    
    def _build_hypothesis_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for single hypothesis generation"""
        prompt_parts = [
            "Generate a novel trading strategy hypothesis based on the following context:",
            "",
            "RECENT EXPERIMENT RESULTS:",
        ]
        
        recent_experiments = context.get("recent_experiments", [])
        for exp in recent_experiments[-3:]:  # Last 3 experiments
            prompt_parts.append(
                f"- {exp.get('name', 'Unknown')}: {exp.get('hypothesis', 'No hypothesis')} "
                f"(Fitness: {exp.get('fitness_score', 0):.3f})"
            )
        
        if context.get("knowledge_insights"):
            prompt_parts.extend([
                "",
                "KNOWN PATTERNS AND INSIGHTS:",
            ])
            for insight in context["knowledge_insights"][:3]:
                prompt_parts.append(f"- {insight.get('title', 'Unknown')}: {insight.get('summary', 'No summary')}")
        
        prompt_parts.extend([
            "",
            "Generate a hypothesis that:",
            "1. Explores novel neuro-fuzzy architecture combinations",
            "2. Addresses unexplored market conditions or timeframes", 
            "3. Is specific enough to be testable",
            "4. Builds on successful patterns while avoiding known failures",
            "",
            "Format your response as a JSON object with keys:",
            "- hypothesis: Detailed hypothesis statement",
            "- experiment_type: Type of experiment (e.g., momentum_strategy, mean_reversion)",
            "- confidence: Confidence level (0.0-1.0)",
            "- rationale: Reasoning behind this hypothesis"
        ])
        
        return "\n".join(prompt_parts)
    
    def _build_hypotheses_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for multiple hypotheses generation"""
        return self._build_hypothesis_prompt(context).replace(
            "Generate a hypothesis",
            "Generate 3-5 hypotheses"
        ).replace(
            "Format your response as a JSON object",
            "Format your response as a JSON array of objects"
        )
    
    def _parse_hypothesis_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM response into structured hypothesis"""
        try:
            import json
            # Try to extract JSON from response
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            
            if start >= 0 and end > start:
                json_text = response_text[start:end]
                return json.loads(json_text)
            else:
                # Fallback parsing if JSON extraction fails
                return self._fallback_parse_hypothesis(response_text)
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return self._fallback_parse_hypothesis(response_text)
    
    def _parse_hypotheses_response(self, response_text: str) -> List[Dict[str, Any]]:
        """Parse LLM response into structured hypotheses list"""
        try:
            import json
            # Try to extract JSON array from response
            start = response_text.find('[')
            end = response_text.rfind(']') + 1
            
            if start >= 0 and end > start:
                json_text = response_text[start:end]
                return json.loads(json_text)
            else:
                # Try single hypothesis and wrap in list
                hypothesis = self._parse_hypothesis_response(response_text)
                return [hypothesis]
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response as JSON array: {e}")
            # Return single fallback hypothesis in list
            return [self._fallback_parse_hypothesis(response_text)]
    
    def _fallback_parse_hypothesis(self, response_text: str) -> Dict[str, Any]:
        """Fallback parsing when JSON parsing fails"""
        return {
            "hypothesis": response_text[:200] + "..." if len(response_text) > 200 else response_text,
            "experiment_type": "momentum_strategy",
            "confidence": 0.6,
            "rationale": "Generated from LLM response without structured parsing",
            "source": "openai_fallback"
        }


class NullLLMService(LLMService):
    """Null object implementation for when LLM service is unavailable"""
    
    def __init__(self):
        logger.info("Using NullLLMService - LLM functionality will use predefined responses")
    
    async def generate_hypothesis(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback hypothesis when LLM is unavailable"""
        return {
            "hypothesis": "Adaptive momentum strategy with dynamic parameter adjustment based on market volatility",
            "experiment_type": "momentum_strategy",
            "confidence": 0.5,
            "rationale": "Momentum strategies have shown consistent performance across different market conditions",
            "source": "null_service_fallback"
        }
    
    async def generate_hypotheses(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate fallback hypotheses when LLM is unavailable"""
        templates = [
            {
                "hypothesis": "Adaptive momentum strategy with dynamic parameter adjustment",
                "experiment_type": "momentum_strategy",
                "confidence": 0.5,
                "rationale": "Momentum strategies show consistent performance"
            },
            {
                "hypothesis": "Mean reversion strategy with volatility-based entry signals",
                "experiment_type": "mean_reversion",
                "confidence": 0.4,
                "rationale": "Mean reversion effective in ranging markets"
            },
            {
                "hypothesis": "Multi-timeframe pattern recognition with neural networks",
                "experiment_type": "pattern_recognition",
                "confidence": 0.6,
                "rationale": "Multi-timeframe analysis can capture different market dynamics"
            }
        ]
        
        # Add source to each template
        for template in templates:
            template["source"] = "null_service_template"
        
        return templates