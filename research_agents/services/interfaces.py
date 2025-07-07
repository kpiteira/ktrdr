"""
Service interfaces for KTRDR Research Agents

Defines clean contracts for all external service dependencies to enable
proper dependency injection and testing without coupling to implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from uuid import UUID


class LLMService(ABC):
    """Interface for Language Model services"""
    
    @abstractmethod
    async def generate_hypothesis(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a single hypothesis based on research context
        
        Args:
            context: Research context including recent experiments, knowledge, etc.
            
        Returns:
            Dictionary containing hypothesis, confidence, experiment_type, etc.
        """
        pass
    
    @abstractmethod
    async def generate_hypotheses(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate multiple hypotheses based on research context
        
        Args:
            context: Research context including recent experiments, knowledge, etc.
            
        Returns:
            List of hypothesis dictionaries
        """
        pass


class KTRDRService(ABC):
    """Interface for KTRDR training and backtesting services"""
    
    @abstractmethod
    async def start_training(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start a training job with given configuration
        
        Args:
            config: Training configuration including strategy, parameters, etc.
            
        Returns:
            Dictionary containing training_id, status, etc.
        """
        pass
    
    @abstractmethod
    async def get_training_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get status of a training job
        
        Args:
            job_id: Training job identifier
            
        Returns:
            Dictionary containing status, progress, metrics, etc.
        """
        pass
    
    @abstractmethod
    async def get_training_results(self, job_id: str) -> Dict[str, Any]:
        """
        Get results from a completed training job
        
        Args:
            job_id: Training job identifier
            
        Returns:
            Dictionary containing final results, metrics, etc.
        """
        pass
    
    @abstractmethod
    async def stop_training(self, job_id: str) -> None:
        """
        Stop a running training job
        
        Args:
            job_id: Training job identifier
        """
        pass


# Use KTRDR's error hierarchy instead of custom exceptions
# LLMServiceError -> ProcessingError with LLM_SERVICE error code
# KTRDRServiceError -> ProcessingError with KTRDR_SERVICE error code