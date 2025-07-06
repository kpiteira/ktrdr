"""
Basic Import Tests

Simple tests to verify our modules can be imported and basic functionality works.
"""

import pytest
from uuid import uuid4


def test_import_research_orchestrator():
    """Test that research orchestrator can be imported"""
    from research_agents.services.research_orchestrator import (
        ResearchOrchestrator,
        ExperimentConfig,
        ExperimentType,
        ExperimentStatus
    )
    
    assert ResearchOrchestrator is not None
    assert ExperimentType.NEURO_FUZZY_STRATEGY == "neuro_fuzzy_strategy"
    assert ExperimentStatus.PENDING == "pending"


def test_import_ktrdr_integration():
    """Test that KTRDR integration can be imported"""
    from research_agents.services.ktrdr_integration import (
        KTRDRIntegrationService,
        TrainingConfig,
        TrainingStatus
    )
    
    assert KTRDRIntegrationService is not None
    assert TrainingStatus.COMPLETED == "completed"


def test_import_results_analyzer():
    """Test that results analyzer can be imported"""
    from research_agents.services.results_analyzer import (
        ResultsAnalyzer,
        RiskProfile,
        create_results_analyzer
    )
    
    assert ResultsAnalyzer is not None
    assert RiskProfile.CONSERVATIVE == "conservative"
    
    # Test factory function
    analyzer = create_results_analyzer()
    assert analyzer is not None


def test_import_research_agent_mvp():
    """Test that research agent MVP can be imported"""
    from research_agents.agents.research_agent_mvp import (
        ResearchAgentMVP,
        ResearchPhase,
        ResearchStrategy
    )
    
    assert ResearchAgentMVP is not None
    assert ResearchPhase.IDLE == "idle"
    assert ResearchStrategy.EXPLORATORY == "exploratory"


def test_basic_config_creation():
    """Test basic configuration object creation"""
    from research_agents.services.research_orchestrator import ExperimentConfig, ExperimentType
    
    config = ExperimentConfig(
        experiment_name="Test",
        hypothesis="Test hypothesis",
        experiment_type=ExperimentType.NEURO_FUZZY_STRATEGY,
        parameters={},
        data_requirements={},
        training_config={},
        validation_config={}
    )
    
    assert config.experiment_name == "Test"
    assert config.experiment_type == ExperimentType.NEURO_FUZZY_STRATEGY


@pytest.mark.asyncio
async def test_basic_async_functionality():
    """Test basic async functionality works"""
    from research_agents.services.results_analyzer import ResultsAnalyzer
    
    analyzer = ResultsAnalyzer()
    
    # Test a simple async method
    skewness = await analyzer._calculate_skewness([0.1, 0.2, 0.1, -0.1, 0.0])
    assert isinstance(skewness, float)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])