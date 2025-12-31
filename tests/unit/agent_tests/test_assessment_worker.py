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
        assert not missing_path.exists()  # Verify file doesn't exist

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

        hypotheses_file = tmp_path / "hypotheses.yaml"

        # Patch both EXPERIMENTS_DIR and HYPOTHESES_FILE to use tmp_path
        with (
            patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path / "experiments"),
            patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file),
        ):
            await worker._save_to_memory(
                strategy_name="test_strategy",
                strategy_config={"indicators": [{"name": "RSI"}]},
                training_metrics={"accuracy": 0.65},
                backtest_metrics={"sharpe_ratio": 1.2},
                parsed_assessment=parsed,
            )

        # Verify file was created
        files = list((tmp_path / "experiments").glob("*.yaml"))
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

        hypotheses_file = tmp_path / "hypotheses.yaml"

        with (
            patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path / "experiments"),
            patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file),
        ):
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
        exp_files = list((tmp_path / "experiments").glob("*.yaml"))
        content = yaml.safe_load(exp_files[0].read_text())

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


class TestMalformedAssessmentHandling:
    """Tests for Task 4.3: Handle malformed assessment gracefully."""

    @pytest.mark.asyncio
    async def test_malformed_assessment_still_saves(
        self, mock_operations_service, tmp_path
    ):
        """Record created with unknown verdict when parsing fails."""
        from unittest.mock import patch

        import yaml

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        # Simulate malformed assessment - ParsedAssessment.empty() returns this
        parsed = ParsedAssessment.empty(
            raw_text="Malformed output that couldn't be parsed"
        )

        assert parsed.verdict == "unknown"  # Sanity check

        hypotheses_file = tmp_path / "hypotheses.yaml"

        with (
            patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path / "experiments"),
            patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file),
        ):
            await worker._save_to_memory(
                strategy_name="test_strategy",
                strategy_config={"indicators": [{"name": "RSI"}]},
                training_metrics={"accuracy": 0.55},
                backtest_metrics={"sharpe_ratio": 0.5},
                parsed_assessment=parsed,
            )

        # Verify file was created
        files = list((tmp_path / "experiments").glob("*.yaml"))
        assert len(files) == 1

        # Verify content has unknown verdict
        content = yaml.safe_load(files[0].read_text())
        assert content["assessment"]["verdict"] == "unknown"

    @pytest.mark.asyncio
    async def test_malformed_assessment_has_raw_text(
        self, mock_operations_service, tmp_path
    ):
        """Raw text preserved in the assessment for debugging."""
        from unittest.mock import patch

        import yaml

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        raw_output = "This is some malformed output\nthat couldn't be parsed correctly."
        parsed = ParsedAssessment.empty(raw_text=raw_output)

        hypotheses_file = tmp_path / "hypotheses.yaml"

        with (
            patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path / "experiments"),
            patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file),
        ):
            await worker._save_to_memory(
                strategy_name="test_strategy",
                strategy_config={},
                training_metrics={},
                backtest_metrics={},
                parsed_assessment=parsed,
            )

        files = list((tmp_path / "experiments").glob("*.yaml"))
        content = yaml.safe_load(files[0].read_text())

        # raw_text should be preserved in the assessment
        assert "raw_text" in content["assessment"]
        assert raw_output in content["assessment"]["raw_text"]

    @pytest.mark.asyncio
    async def test_malformed_assessment_preserves_full_raw_text(
        self, mock_operations_service, tmp_path
    ):
        """Full raw text is preserved for debugging (no truncation)."""
        from unittest.mock import patch

        import yaml

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        # Create long raw text - should be preserved in full
        raw_output = "A" * 5000
        parsed = ParsedAssessment.empty(raw_text=raw_output)

        hypotheses_file = tmp_path / "hypotheses.yaml"

        with (
            patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path / "experiments"),
            patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file),
        ):
            await worker._save_to_memory(
                strategy_name="test_strategy",
                strategy_config={},
                training_metrics={},
                backtest_metrics={},
                parsed_assessment=parsed,
            )

        files = list((tmp_path / "experiments").glob("*.yaml"))
        content = yaml.safe_load(files[0].read_text())

        # Full raw_text preserved - no truncation
        assert len(content["assessment"]["raw_text"]) == 5000

    @pytest.mark.asyncio
    async def test_malformed_assessment_has_fallback_observations(
        self, mock_operations_service, tmp_path
    ):
        """Empty observations get a fallback when verdict is unknown."""
        from unittest.mock import patch

        import yaml

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        # Malformed assessment has empty observations
        parsed = ParsedAssessment.empty(raw_text="Malformed output")
        assert parsed.observations == []  # Sanity check

        hypotheses_file = tmp_path / "hypotheses.yaml"

        with (
            patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path / "experiments"),
            patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file),
        ):
            await worker._save_to_memory(
                strategy_name="test_strategy",
                strategy_config={},
                training_metrics={},
                backtest_metrics={},
                parsed_assessment=parsed,
            )

        files = list((tmp_path / "experiments").glob("*.yaml"))
        content = yaml.safe_load(files[0].read_text())

        # Should have fallback observation, not empty list
        assert len(content["assessment"]["observations"]) > 0
        assert "could not be parsed" in content["assessment"]["observations"][0].lower()

    @pytest.mark.asyncio
    async def test_malformed_assessment_logs_warning(
        self, mock_operations_service, tmp_path, caplog
    ):
        """Warning logged for unknown verdict."""
        import logging
        from unittest.mock import patch

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)
        parsed = ParsedAssessment.empty(raw_text="Malformed")

        hypotheses_file = tmp_path / "hypotheses.yaml"

        with (
            patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path / "experiments"),
            patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file),
        ):
            with caplog.at_level(logging.WARNING):
                await worker._save_to_memory(
                    strategy_name="test_strategy",
                    strategy_config={},
                    training_metrics={},
                    backtest_metrics={},
                    parsed_assessment=parsed,
                )

        # Check warning was logged
        assert any(
            "unknown verdict" in record.message.lower() for record in caplog.records
        )


class TestSaveHypotheses:
    """Tests for Task 5.1: _save_hypotheses method."""

    @pytest.mark.asyncio
    async def test_save_hypotheses_extracts_new(
        self, mock_operations_service, tmp_path
    ):
        """New hypotheses are saved from ParsedAssessment."""
        from unittest.mock import patch

        import yaml

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        parsed = ParsedAssessment(
            verdict="strong_signal",
            observations=["Good accuracy"],
            hypotheses=[
                {"text": "Multi-timeframe might help", "status": "untested"},
                {"text": "ADX as filter could work", "status": "untested"},
            ],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=[],
            raw_text="Test output",
        )

        hypotheses_file = tmp_path / "hypotheses.yaml"

        with (
            patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path / "experiments"),
            patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file),
        ):
            await worker._save_hypotheses(
                parsed_assessment=parsed,
                experiment_id="exp_20251230_001",
            )

        # Verify hypotheses were saved
        assert hypotheses_file.exists()
        data = yaml.safe_load(hypotheses_file.read_text())
        assert len(data["hypotheses"]) == 2
        assert data["hypotheses"][0]["text"] == "Multi-timeframe might help"
        assert data["hypotheses"][1]["text"] == "ADX as filter could work"

    @pytest.mark.asyncio
    async def test_save_hypotheses_generates_id(
        self, mock_operations_service, tmp_path
    ):
        """Unique IDs are assigned to new hypotheses."""
        from unittest.mock import patch

        import yaml

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        parsed = ParsedAssessment(
            verdict="strong_signal",
            observations=[],
            hypotheses=[
                {"text": "First hypothesis", "status": "untested"},
                {"text": "Second hypothesis", "status": "untested"},
            ],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=[],
            raw_text="Test",
        )

        hypotheses_file = tmp_path / "hypotheses.yaml"

        with (
            patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path / "experiments"),
            patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file),
        ):
            await worker._save_hypotheses(
                parsed_assessment=parsed,
                experiment_id="exp_test_001",
            )

        data = yaml.safe_load(hypotheses_file.read_text())
        ids = [h["id"] for h in data["hypotheses"]]

        # IDs should be sequential and unique
        assert ids[0] == "H_001"
        assert ids[1] == "H_002"
        assert ids[0] != ids[1]

    @pytest.mark.asyncio
    async def test_save_hypotheses_links_experiment(
        self, mock_operations_service, tmp_path
    ):
        """Source experiment is linked to each hypothesis."""
        from unittest.mock import patch

        import yaml

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        parsed = ParsedAssessment(
            verdict="weak_signal",
            observations=[],
            hypotheses=[{"text": "Test hypothesis", "status": "untested"}],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=[],
            raw_text="Test",
        )

        hypotheses_file = tmp_path / "hypotheses.yaml"

        with (
            patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path / "experiments"),
            patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file),
        ):
            await worker._save_hypotheses(
                parsed_assessment=parsed,
                experiment_id="exp_source_123",
            )

        data = yaml.safe_load(hypotheses_file.read_text())
        assert data["hypotheses"][0]["source_experiment"] == "exp_source_123"

    @pytest.mark.asyncio
    async def test_save_hypotheses_empty_list(self, mock_operations_service, tmp_path):
        """No error when hypotheses list is empty."""
        from unittest.mock import patch

        import yaml

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        parsed = ParsedAssessment(
            verdict="no_signal",
            observations=["No patterns found"],
            hypotheses=[],  # Empty list
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=[],
            raw_text="Test",
        )

        hypotheses_file = tmp_path / "hypotheses.yaml"

        with (
            patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path / "experiments"),
            patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file),
        ):
            # Should not raise
            await worker._save_hypotheses(
                parsed_assessment=parsed,
                experiment_id="exp_test_002",
            )

        # File should not exist (or be empty) since no hypotheses
        if hypotheses_file.exists():
            data = yaml.safe_load(hypotheses_file.read_text())
            assert len(data.get("hypotheses", [])) == 0

    @pytest.mark.asyncio
    async def test_save_hypotheses_failure_continues(
        self, mock_operations_service, tmp_path, caplog
    ):
        """Hypothesis save failure doesn't raise exception."""
        import logging
        from unittest.mock import patch

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        parsed = ParsedAssessment(
            verdict="strong_signal",
            observations=[],
            hypotheses=[{"text": "Test", "status": "untested"}],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=[],
            raw_text="Test",
        )

        # Patch to simulate failure
        with patch(
            "ktrdr.agents.workers.assessment_worker.save_hypothesis",
            side_effect=Exception("Disk full"),
        ):
            with caplog.at_level(logging.WARNING):
                # Should not raise - graceful degradation
                await worker._save_hypotheses(
                    parsed_assessment=parsed,
                    experiment_id="exp_test_003",
                )

        # Should log warning about failure
        assert any("hypotheses" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_save_hypotheses_skips_empty_text(
        self, mock_operations_service, tmp_path
    ):
        """Hypotheses with empty text are skipped."""
        from unittest.mock import patch

        import yaml

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        parsed = ParsedAssessment(
            verdict="strong_signal",
            observations=[],
            hypotheses=[
                {"text": "", "status": "untested"},  # Empty text - skip
                {"text": "Valid hypothesis", "status": "untested"},
                {"status": "untested"},  # Missing text - skip
            ],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=[],
            raw_text="Test",
        )

        hypotheses_file = tmp_path / "hypotheses.yaml"

        with (
            patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path / "experiments"),
            patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file),
        ):
            await worker._save_hypotheses(
                parsed_assessment=parsed,
                experiment_id="exp_test_004",
            )

        # Only valid hypothesis should be saved
        data = yaml.safe_load(hypotheses_file.read_text())
        assert len(data["hypotheses"]) == 1
        assert data["hypotheses"][0]["text"] == "Valid hypothesis"


class TestUpdateTestedHypotheses:
    """Tests for Task 5.2: _update_tested_hypotheses method."""

    @pytest.mark.asyncio
    async def test_update_tested_hypotheses_validated(
        self, mock_operations_service, tmp_path
    ):
        """Status set to validated when assessment says 'validated'."""
        from unittest.mock import patch

        import yaml

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        # Pre-populate hypotheses file with an untested hypothesis
        hypotheses_file = tmp_path / "hypotheses.yaml"
        hypotheses_file.write_text(
            yaml.dump(
                {
                    "hypotheses": [
                        {
                            "id": "H_001",
                            "text": "Multi-timeframe might help",
                            "status": "untested",
                            "source_experiment": "exp_old",
                            "rationale": "Initial hypothesis",
                            "tested_by": [],
                        }
                    ]
                }
            )
        )

        parsed = ParsedAssessment(
            verdict="strong_signal",
            observations=["Great results"],
            hypotheses=[],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=["H_001"],
            raw_text="Testing H_001. The hypothesis H_001 validated - multi-timeframe improved accuracy.",
        )

        with patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file):
            await worker._update_tested_hypotheses(
                parsed_assessment=parsed,
                experiment_id="exp_new_123",
            )

        # Verify status was updated
        data = yaml.safe_load(hypotheses_file.read_text())
        assert data["hypotheses"][0]["status"] == "validated"

    @pytest.mark.asyncio
    async def test_update_tested_hypotheses_refuted(
        self, mock_operations_service, tmp_path
    ):
        """Status set to refuted when assessment says 'refuted'."""
        from unittest.mock import patch

        import yaml

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        hypotheses_file = tmp_path / "hypotheses.yaml"
        hypotheses_file.write_text(
            yaml.dump(
                {
                    "hypotheses": [
                        {
                            "id": "H_002",
                            "text": "ADX as filter",
                            "status": "untested",
                            "source_experiment": "exp_old",
                            "rationale": "Test",
                            "tested_by": [],
                        }
                    ]
                }
            )
        )

        parsed = ParsedAssessment(
            verdict="no_signal",
            observations=["No improvement"],
            hypotheses=[],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=["H_002"],
            raw_text="Testing ADX filter. H_002 refuted - no improvement with ADX filter.",
        )

        with patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file):
            await worker._update_tested_hypotheses(
                parsed_assessment=parsed,
                experiment_id="exp_new_456",
            )

        data = yaml.safe_load(hypotheses_file.read_text())
        assert data["hypotheses"][0]["status"] == "refuted"

    @pytest.mark.asyncio
    async def test_update_tested_hypotheses_inconclusive(
        self, mock_operations_service, tmp_path
    ):
        """Status set to inconclusive when assessment is unclear."""
        from unittest.mock import patch

        import yaml

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        hypotheses_file = tmp_path / "hypotheses.yaml"
        hypotheses_file.write_text(
            yaml.dump(
                {
                    "hypotheses": [
                        {
                            "id": "H_003",
                            "text": "LSTM might work",
                            "status": "untested",
                            "source_experiment": "exp_old",
                            "rationale": "Test",
                            "tested_by": [],
                        }
                    ]
                }
            )
        )

        parsed = ParsedAssessment(
            verdict="weak_signal",
            observations=["Mixed results"],
            hypotheses=[],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=["H_003"],
            raw_text="Testing LSTM. H_003 inconclusive - need more data.",
        )

        with patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file):
            await worker._update_tested_hypotheses(
                parsed_assessment=parsed,
                experiment_id="exp_new_789",
            )

        data = yaml.safe_load(hypotheses_file.read_text())
        assert data["hypotheses"][0]["status"] == "inconclusive"

    @pytest.mark.asyncio
    async def test_update_tested_hypotheses_adds_experiment(
        self, mock_operations_service, tmp_path
    ):
        """Experiment ID added to tested_by list."""
        from unittest.mock import patch

        import yaml

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        hypotheses_file = tmp_path / "hypotheses.yaml"
        hypotheses_file.write_text(
            yaml.dump(
                {
                    "hypotheses": [
                        {
                            "id": "H_001",
                            "text": "Test hypothesis",
                            "status": "untested",
                            "source_experiment": "exp_old",
                            "rationale": "Test",
                            "tested_by": [],
                        }
                    ]
                }
            )
        )

        parsed = ParsedAssessment(
            verdict="strong_signal",
            observations=[],
            hypotheses=[],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=["H_001"],
            raw_text="H_001 validated by this experiment.",
        )

        with patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file):
            await worker._update_tested_hypotheses(
                parsed_assessment=parsed,
                experiment_id="exp_testing_abc",
            )

        data = yaml.safe_load(hypotheses_file.read_text())
        assert "exp_testing_abc" in data["hypotheses"][0]["tested_by"]

    @pytest.mark.asyncio
    async def test_update_tested_hypotheses_no_ids(
        self, mock_operations_service, tmp_path
    ):
        """No error when tested_hypothesis_ids is empty."""
        from unittest.mock import patch

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        hypotheses_file = tmp_path / "hypotheses.yaml"

        parsed = ParsedAssessment(
            verdict="strong_signal",
            observations=["Good results"],
            hypotheses=[],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=[],  # Empty
            raw_text="No hypotheses referenced.",
        )

        with patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file):
            # Should not raise
            await worker._update_tested_hypotheses(
                parsed_assessment=parsed,
                experiment_id="exp_test_empty",
            )

    @pytest.mark.asyncio
    async def test_update_tested_hypotheses_failure_continues(
        self, mock_operations_service, tmp_path, caplog
    ):
        """Hypothesis update failure doesn't raise exception."""
        import logging
        from unittest.mock import patch

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        parsed = ParsedAssessment(
            verdict="strong_signal",
            observations=[],
            hypotheses=[],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=["H_001"],
            raw_text="H_001 validated.",
        )

        # Patch to simulate failure
        with patch(
            "ktrdr.agents.workers.assessment_worker.update_hypothesis_status",
            side_effect=Exception("File locked"),
        ):
            with caplog.at_level(logging.WARNING):
                # Should not raise - graceful degradation
                await worker._update_tested_hypotheses(
                    parsed_assessment=parsed,
                    experiment_id="exp_test_fail",
                )

        # Should log warning about failure
        assert any("hypothes" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_update_tested_hypotheses_infers_from_verdict(
        self, mock_operations_service, tmp_path
    ):
        """Status inferred from verdict when no explicit statement."""
        from unittest.mock import patch

        import yaml

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        hypotheses_file = tmp_path / "hypotheses.yaml"
        hypotheses_file.write_text(
            yaml.dump(
                {
                    "hypotheses": [
                        {
                            "id": "H_001",
                            "text": "Test hypothesis",
                            "status": "untested",
                            "source_experiment": "exp_old",
                            "rationale": "Test",
                            "tested_by": [],
                        }
                    ]
                }
            )
        )

        # No explicit "validated" or "refuted" in text, but strong_signal verdict
        parsed = ParsedAssessment(
            verdict="strong_signal",
            observations=["Great accuracy"],
            hypotheses=[],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=["H_001"],
            raw_text="Testing the hypothesis. Accuracy was 68%.",
        )

        with patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file):
            await worker._update_tested_hypotheses(
                parsed_assessment=parsed,
                experiment_id="exp_infer",
            )

        data = yaml.safe_load(hypotheses_file.read_text())
        # Should infer validated from strong_signal verdict
        assert data["hypotheses"][0]["status"] == "validated"

    @pytest.mark.asyncio
    async def test_update_tested_hypotheses_no_signal_infers_refuted(
        self, mock_operations_service, tmp_path
    ):
        """no_signal verdict infers refuted status."""
        from unittest.mock import patch

        import yaml

        from ktrdr.llm.haiku_brain import ParsedAssessment

        worker = AgentAssessmentWorker(mock_operations_service)

        hypotheses_file = tmp_path / "hypotheses.yaml"
        hypotheses_file.write_text(
            yaml.dump(
                {
                    "hypotheses": [
                        {
                            "id": "H_001",
                            "text": "Test hypothesis",
                            "status": "untested",
                            "source_experiment": "exp_old",
                            "rationale": "Test",
                            "tested_by": [],
                        }
                    ]
                }
            )
        )

        parsed = ParsedAssessment(
            verdict="no_signal",
            observations=["Random noise"],
            hypotheses=[],
            limitations=[],
            capability_requests=[],
            tested_hypothesis_ids=["H_001"],
            raw_text="No predictive signal found.",
        )

        with patch("ktrdr.agents.memory.HYPOTHESES_FILE", hypotheses_file):
            await worker._update_tested_hypotheses(
                parsed_assessment=parsed,
                experiment_id="exp_no_signal",
            )

        data = yaml.safe_load(hypotheses_file.read_text())
        assert data["hypotheses"][0]["status"] == "refuted"
