"""Unit tests for AgentAssessmentWorker.

Tests for Task 5.3: Assessment worker using Claude.
Tests for Task 4.1: Strategy config loading for memory.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ktrdr.agents.workers.assessment_worker import AgentAssessmentWorker, WorkerError
from ktrdr.api.models.operations import OperationStatus, OperationType


@pytest.fixture
def mock_operations_service():
    """Create mock operations service."""
    service = AsyncMock()

    # Mock operation creation
    mock_op = MagicMock()
    mock_op.operation_id = "op_agent_assessment_123"
    mock_op.status = OperationStatus.PENDING
    service.create_operation.return_value = mock_op

    # Mock parent operation lookup
    parent_op = MagicMock()
    parent_op.operation_id = "op_agent_research_456"
    parent_op.metadata = MagicMock()
    parent_op.metadata.parameters = {
        "strategy_name": "test_strategy_v1",
        "strategy_path": "/app/strategies/test_strategy_v1.yaml",
    }
    service.get_operation.return_value = parent_op

    return service


@pytest.fixture
def mock_invoker():
    """Create mock AnthropicAgentInvoker."""
    invoker = MagicMock()
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.error = None
    mock_result.input_tokens = 3000
    mock_result.output_tokens = 1500
    invoker.run = AsyncMock(return_value=mock_result)
    return invoker


@pytest.fixture
def sample_results():
    """Sample training and backtest results."""
    return {
        "training": {
            "accuracy": 0.62,
            "final_loss": 0.38,
            "initial_loss": 0.75,
        },
        "backtest": {
            "sharpe_ratio": 1.5,
            "win_rate": 0.58,
            "max_drawdown": 0.12,
            "total_return": 0.25,
            "total_trades": 42,
        },
    }


class TestAgentAssessmentWorkerCreation:
    """Tests for AssessmentWorker creation."""

    def test_creates_with_operations_service(self, mock_operations_service):
        """Worker can be created with operations service."""
        worker = AgentAssessmentWorker(mock_operations_service)
        assert worker.ops == mock_operations_service

    def test_creates_with_custom_invoker(self, mock_operations_service, mock_invoker):
        """Worker accepts custom invoker."""
        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)
        assert worker.invoker == mock_invoker


class TestAgentAssessmentWorkerRun:
    """Tests for AssessmentWorker.run()."""

    @pytest.mark.asyncio
    async def test_creates_agent_assessment_operation(
        self, mock_operations_service, mock_invoker, sample_results
    ):
        """Creates AGENT_ASSESSMENT operation."""
        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)

        # Mock tool executor to have assessment
        worker.tool_executor.last_saved_assessment = {
            "verdict": "promising",
            "strengths": ["Good"],
            "weaknesses": ["Limited"],
            "suggestions": ["Try more"],
        }
        worker.tool_executor.last_saved_assessment_path = (
            "/app/strategies/test/assessment.json"
        )

        await worker.run("op_agent_research_456", sample_results)

        # Verify operation was created with correct type
        mock_operations_service.create_operation.assert_called_once()
        call_args = mock_operations_service.create_operation.call_args
        assert call_args.kwargs["operation_type"] == OperationType.AGENT_ASSESSMENT

    @pytest.mark.asyncio
    async def test_passes_training_and_backtest_metrics_to_prompt(
        self, mock_operations_service, mock_invoker, sample_results
    ):
        """Training and backtest metrics are passed to prompt builder."""
        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)

        worker.tool_executor.last_saved_assessment = {
            "verdict": "mediocre",
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
        }
        worker.tool_executor.last_saved_assessment_path = "/path/assessment.json"

        await worker.run("op_agent_research_456", sample_results)

        # Verify invoker was called with prompt containing metrics
        mock_invoker.run.assert_called_once()
        call_args = mock_invoker.run.call_args
        prompt = call_args.kwargs.get(
            "prompt", call_args.args[0] if call_args.args else ""
        )

        # Prompt should contain metrics
        assert "62" in prompt or "0.62" in prompt  # accuracy
        assert "1.5" in prompt or "1.50" in prompt  # sharpe_ratio

    @pytest.mark.asyncio
    async def test_returns_verdict_from_save_assessment_tool(
        self, mock_operations_service, mock_invoker, sample_results
    ):
        """Returns verdict from the save_assessment tool."""
        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)

        worker.tool_executor.last_saved_assessment = {
            "verdict": "promising",
            "strengths": ["A", "B"],
            "weaknesses": ["C"],
            "suggestions": ["D"],
        }
        worker.tool_executor.last_saved_assessment_path = "/path/assessment.json"

        result = await worker.run("op_agent_research_456", sample_results)

        assert result["verdict"] == "promising"
        assert result["strengths"] == ["A", "B"]
        assert result["weaknesses"] == ["C"]
        assert result["suggestions"] == ["D"]

    @pytest.mark.asyncio
    async def test_returns_token_counts(
        self, mock_operations_service, mock_invoker, sample_results
    ):
        """Returns input and output token counts."""
        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)

        worker.tool_executor.last_saved_assessment = {
            "verdict": "poor",
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
        }
        worker.tool_executor.last_saved_assessment_path = "/path/assessment.json"

        result = await worker.run("op_agent_research_456", sample_results)

        assert result["input_tokens"] == 3000
        assert result["output_tokens"] == 1500

    @pytest.mark.asyncio
    async def test_raises_worker_error_if_assessment_not_saved(
        self, mock_operations_service, mock_invoker, sample_results
    ):
        """Raises WorkerError if Claude didn't save assessment."""
        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)

        # Don't set last_saved_assessment - simulating Claude not using tool
        worker.tool_executor.last_saved_assessment = None

        with pytest.raises(WorkerError, match="did not save"):
            await worker.run("op_agent_research_456", sample_results)

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates(
        self, mock_operations_service, sample_results
    ):
        """CancelledError propagates correctly."""
        mock_invoker = MagicMock()
        mock_invoker.run = AsyncMock(side_effect=asyncio.CancelledError())

        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)

        with pytest.raises(asyncio.CancelledError):
            await worker.run("op_agent_research_456", sample_results)

        # Should cancel the operation
        mock_operations_service.cancel_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_completes_child_operation_on_success(
        self, mock_operations_service, mock_invoker, sample_results
    ):
        """Completes child operation on success."""
        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)

        worker.tool_executor.last_saved_assessment = {
            "verdict": "promising",
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
        }
        worker.tool_executor.last_saved_assessment_path = "/path/assessment.json"

        await worker.run("op_agent_research_456", sample_results)

        mock_operations_service.complete_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_fails_child_operation_on_error(
        self, mock_operations_service, sample_results
    ):
        """Fails child operation when Claude fails."""
        mock_invoker = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "API error"
        mock_invoker.run = AsyncMock(return_value=mock_result)

        worker = AgentAssessmentWorker(mock_operations_service, invoker=mock_invoker)

        with pytest.raises(WorkerError):
            await worker.run("op_agent_research_456", sample_results)

        mock_operations_service.fail_operation.assert_called_once()


class TestLoadStrategyConfig:
    """Tests for Task 4.1: _load_strategy_config method."""

    def test_load_strategy_config_success(self, mock_operations_service, tmp_path):
        """Load valid YAML strategy config."""
        # Create a valid strategy YAML
        strategy_file = tmp_path / "test_strategy.yaml"
        strategy_file.write_text(
            """
name: test_strategy
indicators:
  - name: RSI
    period: 14
  - name: DI
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
    hidden_layers: [32, 16]
"""
        )

        worker = AgentAssessmentWorker(mock_operations_service)
        config = worker._load_strategy_config(str(strategy_file))

        assert config["name"] == "test_strategy"
        assert len(config["indicators"]) == 2
        assert config["indicators"][0]["name"] == "RSI"
        assert config["training"]["labels"]["zigzag_threshold"] == 0.015

    def test_load_strategy_config_missing(self, mock_operations_service, tmp_path):
        """Return empty dict for missing file."""
        missing_path = tmp_path / "nonexistent.yaml"

        worker = AgentAssessmentWorker(mock_operations_service)
        config = worker._load_strategy_config(str(missing_path))

        assert config == {}

    def test_load_strategy_config_invalid(self, mock_operations_service, tmp_path):
        """Return empty dict for invalid YAML."""
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("{ invalid yaml: [unclosed")

        worker = AgentAssessmentWorker(mock_operations_service)
        config = worker._load_strategy_config(str(invalid_file))

        assert config == {}

    def test_load_strategy_config_none_path(self, mock_operations_service):
        """Return empty dict when path is None."""
        worker = AgentAssessmentWorker(mock_operations_service)
        config = worker._load_strategy_config(None)

        assert config == {}


class TestExtractContext:
    """Tests for Task 4.2: _extract_context method."""

    def test_extract_context_from_config(self, mock_operations_service):
        """Extract correct fields from strategy config."""
        worker = AgentAssessmentWorker(mock_operations_service)

        config = {
            "indicators": [
                {"name": "RSI", "period": 14},
                {"name": "DI", "period": 14},
            ],
            "training_data": {
                "timeframes": {"list": ["1h"]},
                "symbols": {"list": ["EURUSD"]},
            },
            "training": {
                "labels": {"zigzag_threshold": 0.015},
            },
            "model": {
                "architecture": {"hidden_layers": [32, 16]},
            },
        }

        context = worker._extract_context(config)

        assert context["indicators"] == ["RSI", "DI"]
        assert context["composition"] == "pair"
        assert context["timeframe"] == "1h"
        assert context["symbol"] == "EURUSD"
        assert context["zigzag_threshold"] == 0.015
        assert context["nn_architecture"] == [32, 16]

    def test_extract_context_solo_composition(self, mock_operations_service):
        """Detect solo composition with single indicator."""
        worker = AgentAssessmentWorker(mock_operations_service)

        config = {"indicators": [{"name": "RSI"}]}

        context = worker._extract_context(config)

        assert context["composition"] == "solo"

    def test_extract_context_ensemble_composition(self, mock_operations_service):
        """Detect ensemble composition with 3+ indicators."""
        worker = AgentAssessmentWorker(mock_operations_service)

        config = {
            "indicators": [
                {"name": "RSI"},
                {"name": "ADX"},
                {"name": "CCI"},
            ]
        }

        context = worker._extract_context(config)

        assert context["composition"] == "ensemble"

    def test_extract_context_empty_config(self, mock_operations_service):
        """Handle empty config with defaults."""
        worker = AgentAssessmentWorker(mock_operations_service)

        context = worker._extract_context({})

        assert context["indicators"] == []
        assert context["composition"] == "solo"  # empty == solo
        assert context["timeframe"] == "1h"  # default
        assert context["symbol"] == "EURUSD"  # default
        assert context["zigzag_threshold"] == 0.02  # default


class TestExtractResults:
    """Tests for Task 4.2: _extract_results method."""

    def test_extract_results_from_metrics(self, mock_operations_service):
        """Extract correct fields from metrics."""
        worker = AgentAssessmentWorker(mock_operations_service)

        training = {
            "accuracy": 0.648,
            "val_accuracy": 0.665,
        }
        backtest = {
            "sharpe_ratio": 1.5,
            "total_trades": 847,
            "win_rate": 0.52,
        }

        results = worker._extract_results(training, backtest)

        assert results["test_accuracy"] == 0.648
        assert results["val_accuracy"] == 0.665
        assert results["val_test_gap"] == pytest.approx(0.017, abs=0.001)
        assert results["sharpe_ratio"] == 1.5
        assert results["total_trades"] == 847
        assert results["win_rate"] == 0.52

    def test_extract_results_empty_metrics(self, mock_operations_service):
        """Handle empty metrics with defaults."""
        worker = AgentAssessmentWorker(mock_operations_service)

        results = worker._extract_results({}, {})

        assert results["test_accuracy"] == 0
        assert results["val_accuracy"] == 0
        assert results["val_test_gap"] == 0
        assert results["sharpe_ratio"] is None
        assert results["total_trades"] is None
        assert results["win_rate"] is None


class TestSaveToMemory:
    """Tests for Task 4.2: _save_to_memory method."""

    @pytest.mark.asyncio
    async def test_save_to_memory_creates_file(self, mock_operations_service, tmp_path):
        """File exists after save."""
        from unittest.mock import patch

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        parsed = ParsedAssessment(
            verdict="strong_signal",
            observations=["Test observation"],
            hypotheses=[{"text": "Test hypothesis", "status": "untested"}],
            limitations=["Test limitation"],
            capability_requests=[],
            tested_hypothesis_ids=[],
            raw_text="Test raw output",
        )

        # Patch memory directory - need to patch where it's used (memory module)
        with patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path):
            await worker._save_to_memory(
                strategy_name="test_strategy",
                strategy_config={"indicators": [{"name": "RSI"}]},
                training_metrics={"accuracy": 0.65},
                backtest_metrics={"sharpe_ratio": 1.2},
                parsed_assessment=parsed,
            )

        # Verify file was created
        files = list(tmp_path.glob("*.yaml"))
        assert len(files) == 1

    @pytest.mark.asyncio
    async def test_save_to_memory_correct_content(
        self, mock_operations_service, tmp_path
    ):
        """All fields populated correctly."""
        from unittest.mock import patch

        import yaml

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        parsed = ParsedAssessment(
            verdict="strong_signal",
            observations=["Good accuracy"],
            hypotheses=[{"text": "Try more indicators", "status": "untested"}],
            limitations=["Only EURUSD tested"],
            capability_requests=["LSTM support"],
            tested_hypothesis_ids=["H_001"],
            raw_text="Raw assessment text",
        )

        with patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path):
            await worker._save_to_memory(
                strategy_name="rsi_di_v1",
                strategy_config={
                    "indicators": [{"name": "RSI"}, {"name": "DI"}],
                    "training_data": {
                        "timeframes": {"list": ["1h"]},
                        "symbols": {"list": ["EURUSD"]},
                    },
                    "training": {"labels": {"zigzag_threshold": 0.015}},
                },
                training_metrics={"accuracy": 0.65, "val_accuracy": 0.67},
                backtest_metrics={"sharpe_ratio": 1.5, "total_trades": 100},
                parsed_assessment=parsed,
            )

        # Load and verify content
        files = list(tmp_path.glob("*.yaml"))
        content = yaml.safe_load(files[0].read_text())

        assert content["strategy_name"] == "rsi_di_v1"
        assert content["source"] == "agent"
        assert content["context"]["indicators"] == ["RSI", "DI"]
        assert content["context"]["composition"] == "pair"
        assert content["results"]["test_accuracy"] == 0.65
        assert content["assessment"]["verdict"] == "strong_signal"
        assert content["assessment"]["observations"] == ["Good accuracy"]

    @pytest.mark.asyncio
    async def test_save_to_memory_failure_continues(self, mock_operations_service):
        """Memory save failure doesn't raise exception."""
        from unittest.mock import patch

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        parsed = ParsedAssessment(
            verdict="strong_signal",
            observations=[],
            hypotheses=[],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=[],
            raw_text="test",
        )

        # Patch to simulate failure
        with patch(
            "ktrdr.agents.workers.assessment_worker.save_experiment",
            side_effect=Exception("Disk full"),
        ):
            # Should not raise - graceful degradation
            await worker._save_to_memory(
                strategy_name="test",
                strategy_config={},
                training_metrics={},
                backtest_metrics={},
                parsed_assessment=parsed,
            )
