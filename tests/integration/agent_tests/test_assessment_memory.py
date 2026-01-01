"""Integration tests for assessment → memory flow.

Task 4.4: Verify assessments are parsed and saved to memory.
Tests the full flow: assessment worker → memory.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from ktrdr.agents.assessment_parser import ParsedAssessment
from ktrdr.agents.workers.assessment_worker import AgentAssessmentWorker
from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
    OperationType,
)


class MockOperationsService:
    """In-memory operations service for testing."""

    def __init__(self):
        self._operations: dict[str, OperationInfo] = {}
        self._counter = 0

    async def create_operation(
        self, operation_type, metadata=None, parent_operation_id=None
    ):
        """Create a new operation."""
        self._counter += 1
        op_id = f"op_{operation_type.value}_{self._counter}"
        op = OperationInfo(
            operation_id=op_id,
            operation_type=operation_type,
            status=OperationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            metadata=metadata or OperationMetadata(),
            parent_operation_id=parent_operation_id,
        )
        self._operations[op_id] = op
        return op

    async def get_operation(self, operation_id):
        """Get operation by ID."""
        return self._operations.get(operation_id)

    async def complete_operation(self, operation_id, result=None):
        """Mark operation as completed."""
        if operation_id in self._operations:
            self._operations[operation_id].status = OperationStatus.COMPLETED
            self._operations[operation_id].result_summary = result

    async def fail_operation(self, operation_id, error=None):
        """Mark operation as failed."""
        if operation_id in self._operations:
            self._operations[operation_id].status = OperationStatus.FAILED
            self._operations[operation_id].error_message = error

    async def cancel_operation(self, operation_id, reason=None):
        """Mark operation as cancelled."""
        if operation_id in self._operations:
            self._operations[operation_id].status = OperationStatus.CANCELLED


@pytest.fixture
def ops_service():
    """Create mock operations service."""
    return MockOperationsService()


@pytest.fixture
def mock_invoker():
    """Create mock invoker that simulates Claude returning assessment."""
    invoker = MagicMock()
    result = MagicMock()
    result.success = True
    result.error = None
    result.output = (
        "## Assessment\n### Verdict\nstrong_signal\n### Observations\n- Good accuracy"
    )
    result.input_tokens = 3000
    result.output_tokens = 1500
    invoker.run = AsyncMock(return_value=result)
    return invoker


@pytest.fixture
def sample_results():
    """Sample training and backtest results."""
    return {
        "training": {
            "accuracy": 0.65,
            "val_accuracy": 0.63,
            "final_loss": 0.35,
        },
        "backtest": {
            "sharpe_ratio": 1.2,
            "win_rate": 0.55,
            "total_trades": 150,
        },
    }


async def create_parent_operation(ops_service, strategy_path=None):
    """Create parent AGENT_RESEARCH operation with strategy info."""
    return await ops_service.create_operation(
        operation_type=OperationType.AGENT_RESEARCH,
        metadata=OperationMetadata(
            parameters={
                "phase": "assessing",
                "strategy_name": "test_rsi_strategy",
                "strategy_path": strategy_path,
            }
        ),
    )


class TestAssessmentMemoryIntegration:
    """Integration tests for assessment → memory flow."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_assessment_saves_experiment_to_memory(
        self, ops_service, mock_invoker, sample_results, tmp_path
    ):
        """Assessment worker saves experiment record to memory directory."""
        parent_op = await create_parent_operation(ops_service)
        worker = AgentAssessmentWorker(ops_service, invoker=mock_invoker)

        # Pre-set the assessment as if Claude saved it
        worker.tool_executor.last_saved_assessment = {
            "verdict": "promising",
            "strengths": ["Good accuracy", "Stable performance"],
            "weaknesses": ["Limited sample size"],
            "suggestions": ["Test more symbols"],
        }
        worker.tool_executor.last_saved_assessment_path = "/app/assessment.json"

        # Mock parse_assessment to return structured assessment
        mock_parsed = ParsedAssessment(
            verdict="strong_signal",
            observations=["Test accuracy of 65% exceeds threshold"],
            hypotheses=[
                {"text": "RSI works well for mean reversion", "status": "untested"}
            ],
            limitations=["Only tested on EURUSD"],
            capability_requests=[],
            tested_hypothesis_ids=[],
            raw_text="Assessment output text",
        )

        with patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path):
            with patch(
                "ktrdr.agents.workers.assessment_worker.parse_assessment"
            ) as mock_parse:
                mock_parse.return_value = mock_parsed

                await worker.run(parent_op.operation_id, sample_results)

        # Verify experiment file was created
        exp_files = list(tmp_path.glob("exp_*.yaml"))
        assert (
            len(exp_files) == 1
        ), f"Expected 1 experiment file, found {len(exp_files)}"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_experiment_has_correct_content(
        self, ops_service, mock_invoker, sample_results, tmp_path
    ):
        """Experiment record has all required fields with correct values."""
        parent_op = await create_parent_operation(ops_service)
        worker = AgentAssessmentWorker(ops_service, invoker=mock_invoker)

        worker.tool_executor.last_saved_assessment = {
            "verdict": "promising",
            "strengths": ["Good"],
            "weaknesses": ["Limited"],
            "suggestions": ["More tests"],
        }
        worker.tool_executor.last_saved_assessment_path = "/app/assessment.json"

        mock_parsed = ParsedAssessment(
            verdict="strong_signal",
            observations=["Accuracy is good", "Sharpe ratio positive"],
            hypotheses=[{"text": "Hypothesis 1", "status": "untested"}],
            limitations=["Limited data"],
            capability_requests=["LSTM support"],
            tested_hypothesis_ids=["H_001"],
            raw_text="Full assessment text here",
        )

        with patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path):
            with patch(
                "ktrdr.agents.workers.assessment_worker.parse_assessment"
            ) as mock_parse:
                mock_parse.return_value = mock_parsed

                await worker.run(parent_op.operation_id, sample_results)

        # Load and verify content
        exp_files = list(tmp_path.glob("exp_*.yaml"))
        content = yaml.safe_load(exp_files[0].read_text())

        # Verify structure
        assert "id" in content
        assert content["id"].startswith("exp_")
        assert "timestamp" in content
        assert "strategy_name" in content
        assert content["strategy_name"] == "test_rsi_strategy"
        assert content["source"] == "agent"

        # Verify context
        assert "context" in content
        assert "indicators" in content["context"]

        # Verify results
        assert "results" in content
        assert content["results"]["test_accuracy"] == 0.65
        assert content["results"]["sharpe_ratio"] == 1.2

        # Verify assessment
        assert "assessment" in content
        assert content["assessment"]["verdict"] == "strong_signal"
        assert content["assessment"]["observations"] == [
            "Accuracy is good",
            "Sharpe ratio positive",
        ]
        assert "raw_text" in content["assessment"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_malformed_assessment_still_saves_experiment(
        self, ops_service, mock_invoker, sample_results, tmp_path
    ):
        """Malformed assessment still creates experiment with unknown verdict."""
        parent_op = await create_parent_operation(ops_service)
        worker = AgentAssessmentWorker(ops_service, invoker=mock_invoker)

        worker.tool_executor.last_saved_assessment = {
            "verdict": "promising",
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
        }
        worker.tool_executor.last_saved_assessment_path = "/app/assessment.json"

        # Simulate malformed assessment that couldn't be parsed
        mock_parsed = ParsedAssessment.empty(
            raw_text="This output was malformed and couldn't be parsed properly"
        )

        with patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path):
            with patch(
                "ktrdr.agents.workers.assessment_worker.parse_assessment"
            ) as mock_parse:
                mock_parse.return_value = mock_parsed

                await worker.run(parent_op.operation_id, sample_results)

        # Verify experiment still saved
        exp_files = list(tmp_path.glob("exp_*.yaml"))
        assert len(exp_files) == 1

        content = yaml.safe_load(exp_files[0].read_text())
        assert content["assessment"]["verdict"] == "unknown"
        assert "could not be parsed" in content["assessment"]["observations"][0].lower()
        assert "malformed" in content["assessment"]["raw_text"].lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_memory_failure_does_not_fail_assessment(
        self, ops_service, mock_invoker, sample_results
    ):
        """Memory save failure doesn't fail the assessment operation."""
        parent_op = await create_parent_operation(ops_service)
        worker = AgentAssessmentWorker(ops_service, invoker=mock_invoker)

        worker.tool_executor.last_saved_assessment = {
            "verdict": "promising",
            "strengths": ["Good"],
            "weaknesses": [],
            "suggestions": [],
        }
        worker.tool_executor.last_saved_assessment_path = "/app/assessment.json"

        mock_parsed = ParsedAssessment(
            verdict="strong_signal",
            observations=["Good"],
            hypotheses=[],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=[],
            raw_text="test",
        )

        # Patch save_experiment to fail
        with patch(
            "ktrdr.agents.workers.assessment_worker.save_experiment",
            side_effect=Exception("Disk full"),
        ):
            with patch(
                "ktrdr.agents.workers.assessment_worker.parse_assessment"
            ) as mock_parse:
                mock_parse.return_value = mock_parsed

                # Should NOT raise - assessment succeeds even if memory fails
                result = await worker.run(parent_op.operation_id, sample_results)

        # Assessment should still succeed
        assert result["success"] is True
        assert result["verdict"] == "promising"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_strategy_config_loaded_for_context(
        self, ops_service, mock_invoker, sample_results, tmp_path
    ):
        """Strategy config is loaded and used for experiment context."""
        # Create strategy file
        strategy_file = tmp_path / "strategies" / "test_strategy.yaml"
        strategy_file.parent.mkdir(parents=True, exist_ok=True)
        strategy_file.write_text(
            """
name: test_rsi_strategy
indicators:
  - name: RSI
    period: 14
  - name: ADX
    period: 14
training_data:
  timeframes:
    list: ["1h"]
  symbols:
    list: ["EURUSD"]
training:
  labels:
    zigzag_threshold: 0.015
model:
  architecture:
    hidden_layers: [64, 32]
"""
        )

        parent_op = await create_parent_operation(
            ops_service, strategy_path=str(strategy_file)
        )
        worker = AgentAssessmentWorker(ops_service, invoker=mock_invoker)

        worker.tool_executor.last_saved_assessment = {
            "verdict": "promising",
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
        }
        worker.tool_executor.last_saved_assessment_path = "/app/assessment.json"

        mock_parsed = ParsedAssessment(
            verdict="strong_signal",
            observations=["Test"],
            hypotheses=[],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=[],
            raw_text="test",
        )

        exp_dir = tmp_path / "experiments"
        with patch("ktrdr.agents.memory.EXPERIMENTS_DIR", exp_dir):
            with patch(
                "ktrdr.agents.workers.assessment_worker.parse_assessment"
            ) as mock_parse:
                mock_parse.return_value = mock_parsed

                await worker.run(parent_op.operation_id, sample_results)

        # Verify context extracted from strategy config
        exp_files = list(exp_dir.glob("exp_*.yaml"))
        content = yaml.safe_load(exp_files[0].read_text())

        assert content["context"]["indicators"] == ["RSI", "ADX"]
        assert content["context"]["composition"] == "pair"
        assert content["context"]["timeframe"] == "1h"
        assert content["context"]["symbol"] == "EURUSD"
        assert content["context"]["zigzag_threshold"] == 0.015
        assert content["context"]["nn_architecture"] == [64, 32]
