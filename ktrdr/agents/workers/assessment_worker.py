"""Assessment worker that uses Claude to evaluate strategy results.

Task 5.3: Real assessment worker using AnthropicAgentInvoker.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from ktrdr import get_logger
from ktrdr.agents.assessment_parser import ParsedAssessment, parse_assessment
from ktrdr.agents.executor import ToolExecutor
from ktrdr.agents.invoker import (
    AnthropicAgentInvoker,
    AnthropicInvokerConfig,
    resolve_model,
)
from ktrdr.agents.memory import (
    ExperimentRecord,
    Hypothesis,
    generate_experiment_id,
    generate_hypothesis_id,
    save_experiment,
    save_hypothesis,
    update_hypothesis_status,
)
from ktrdr.agents.prompts import (
    ASSESSMENT_SYSTEM_PROMPT,
    AssessmentContext,
    get_assessment_prompt,
)
from ktrdr.agents.tools import AGENT_TOOLS
from ktrdr.api.models.operations import OperationMetadata, OperationType

if TYPE_CHECKING:
    from ktrdr.api.services.operations_service import OperationsService

logger = get_logger(__name__)


class WorkerError(Exception):
    """Error during worker execution."""

    pass


def _parse_assessment_from_text(text: str) -> dict[str, Any] | None:
    """Parse assessment from Claude's text response when tool wasn't called.

    This is a fallback for when smaller models like Haiku respond with text
    instead of calling the save_assessment tool.

    Args:
        text: Claude's text response.

    Returns:
        Assessment dict with verdict, strengths, weaknesses, suggestions, or None if parsing fails.
    """
    if not text:
        return None

    # Try to extract verdict
    verdict_match = re.search(
        r'\b(verdict|overall)[:\s]*["\']?(promising|mediocre|poor)["\']?',
        text,
        re.IGNORECASE,
    )
    if not verdict_match:
        # Also check for verdict in bold or headers
        verdict_match = re.search(
            r"\*\*(promising|mediocre|poor)\*\*", text, re.IGNORECASE
        )
    if not verdict_match:
        return None

    verdict = (
        verdict_match.group(2)
        if verdict_match.lastindex == 2
        else verdict_match.group(1)
    )
    verdict = verdict.lower()

    # Extract lists (strengths, weaknesses, suggestions)
    def extract_list(section_name: str) -> list[str]:
        # Look for section header followed by bullet points
        pattern = rf"{section_name}[:\s]*\n((?:[-•*]\s*.+\n?)+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            items = re.findall(r"[-•*]\s*(.+)", match.group(1))
            return [item.strip() for item in items if item.strip()][:4]
        # Fallback: look for numbered lists
        pattern = rf"{section_name}[:\s]*\n((?:\d+[.)]\s*.+\n?)+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            items = re.findall(r"\d+[.)]\s*(.+)", match.group(1))
            return [item.strip() for item in items if item.strip()][:4]
        return []

    strengths = extract_list("strengths")
    weaknesses = extract_list("weaknesses")
    suggestions = extract_list("suggestions") or extract_list("improvements")

    # Require at least some content
    if not strengths and not weaknesses:
        return None

    # Provide defaults if some sections are empty
    if not strengths:
        strengths = ["Unable to extract strengths from response"]
    if not weaknesses:
        weaknesses = ["Unable to extract weaknesses from response"]
    if not suggestions:
        suggestions = ["Review and refine strategy parameters"]

    return {
        "verdict": verdict,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suggestions": suggestions,
    }


class AgentAssessmentWorker:
    """Worker that uses Claude to assess strategy results.

    This worker:
    1. Creates a child AGENT_ASSESSMENT operation
    2. Builds assessment prompt with training and backtest metrics
    3. Calls Claude via AnthropicAgentInvoker
    4. Saves assessment via save_assessment tool
    5. Returns verdict, assessment_path, and token counts

    Attributes:
        ops: Operations service for tracking operations.
        invoker: Claude API invoker.
        tool_executor: Executor for tool calls.
    """

    def __init__(
        self,
        operations_service: OperationsService,
        invoker: AnthropicAgentInvoker | None = None,
    ):
        """Initialize the assessment worker.

        Args:
            operations_service: Service for tracking operations.
            invoker: Optional invoker instance for testing. If provided, this
                     invoker will be used in run() instead of creating a new one
                     with the resolved model config.
        """
        self.ops = operations_service
        # Store injected invoker (for testing) - if provided, run() will use it
        self._injected_invoker = invoker
        # Also keep self.invoker for backward compatibility with init tests
        self.invoker = invoker or AnthropicAgentInvoker()
        self.tool_executor = ToolExecutor()

    def _load_strategy_config(self, strategy_path: str | None) -> dict:
        """Load strategy configuration from YAML file.

        Args:
            strategy_path: Path to strategy YAML file. Can be None.

        Returns:
            Strategy configuration dict, or empty dict if loading fails.
        """
        if not strategy_path:
            return {}
        try:
            path = Path(strategy_path)
            if path.exists():
                return yaml.safe_load(path.read_text()) or {}
        except Exception as e:
            logger.warning(f"Failed to load strategy config: {e}")
        return {}

    def _extract_context(self, strategy_config: dict) -> dict:
        """Extract context fields from strategy config.

        Args:
            strategy_config: Full strategy configuration dict.

        Returns:
            Context dict with indicators, composition, timeframe, etc.
        """
        indicators = [ind.get("name") for ind in strategy_config.get("indicators", [])]
        training_data = strategy_config.get("training_data", {})
        training = strategy_config.get("training", {})

        # Determine composition based on number of indicators
        indicator_count = len(indicators)
        if indicator_count <= 1:
            composition = "solo"
        elif indicator_count == 2:
            composition = "pair"
        else:
            composition = "ensemble"

        # Safely get timeframe and symbol with fallbacks for empty lists
        timeframes_list = training_data.get("timeframes", {}).get("list") or []
        symbols_list = training_data.get("symbols", {}).get("list") or []

        return {
            "indicators": indicators,
            "composition": composition,
            "timeframe": timeframes_list[0] if timeframes_list else "1h",
            "symbol": symbols_list[0] if symbols_list else "EURUSD",
            "zigzag_threshold": training.get("labels", {}).get(
                "zigzag_threshold", 0.02
            ),
            "nn_architecture": strategy_config.get("model", {})
            .get("architecture", {})
            .get("hidden_layers", []),
        }

    def _extract_results(
        self, training_metrics: dict, backtest_metrics: dict | None
    ) -> dict:
        """Extract results fields from metrics.

        Args:
            training_metrics: Training results (accuracy, val_accuracy, etc.)
            backtest_metrics: Backtest results (sharpe_ratio, total_trades, etc.)
                              May be None for gate rejections.

        Returns:
            Results dict with standardized fields.
        """
        test_accuracy = training_metrics.get("accuracy", 0)
        val_accuracy = training_metrics.get("val_accuracy", 0)

        # Handle None backtest_metrics for gate rejections
        if backtest_metrics is None:
            backtest_metrics = {}

        return {
            "test_accuracy": test_accuracy,
            "val_accuracy": val_accuracy,
            "val_test_gap": abs(val_accuracy - test_accuracy),
            "sharpe_ratio": backtest_metrics.get("sharpe_ratio"),
            "total_trades": backtest_metrics.get("total_trades"),
            "win_rate": backtest_metrics.get("win_rate"),
        }

    async def _save_to_memory(
        self,
        strategy_name: str,
        strategy_config: dict,
        training_metrics: dict,
        backtest_metrics: dict | None,
        parsed_assessment: ParsedAssessment,
        status: str = "completed",
        gate_rejection_reason: str | None = None,
    ) -> None:
        """Save experiment record to memory.

        This is a best-effort operation - failures are logged but don't
        fail the assessment. Memory is enhancement, not requirement.

        Args:
            strategy_name: Name of the strategy.
            strategy_config: Full strategy configuration.
            training_metrics: Training results.
            backtest_metrics: Backtest results. May be None for gate rejections.
            parsed_assessment: Structured assessment from parse_assessment().
            status: Experiment status ("completed", "gate_rejected_training",
                    "gate_rejected_backtest"). Defaults to "completed".
            gate_rejection_reason: Reason for gate rejection, e.g.,
                    "accuracy_too_low (5% < 10%)". None for completed experiments.
        """
        try:
            context = self._extract_context(strategy_config)
            results = self._extract_results(training_metrics, backtest_metrics)

            # Handle malformed assessment - provide fallback observations
            observations = parsed_assessment.observations
            if not observations and parsed_assessment.verdict == "unknown":
                observations = ["Assessment could not be parsed"]

            # Preserve full raw_text for debugging malformed assessments
            raw_text = parsed_assessment.raw_text or ""

            record = ExperimentRecord(
                id=generate_experiment_id(),
                timestamp=datetime.now(timezone.utc).isoformat(),
                strategy_name=strategy_name or "unknown",
                context=context,
                results=results,
                assessment={
                    "verdict": parsed_assessment.verdict,
                    "observations": observations,
                    "hypotheses": parsed_assessment.hypotheses,
                    "limitations": parsed_assessment.limitations,
                    "raw_text": raw_text,
                },
                source="agent",
                status=status,
                gate_rejection_reason=gate_rejection_reason,
            )

            path = save_experiment(record)

            if parsed_assessment.verdict == "unknown":
                logger.warning(f"Saved experiment with unknown verdict: {path}")
            else:
                logger.info(f"Saved experiment to memory: {path}")

            # Save new hypotheses from assessment (Task 5.1)
            await self._save_hypotheses(
                parsed_assessment=parsed_assessment,
                experiment_id=record.id,
            )

            # Update tested hypotheses (Task 5.2)
            await self._update_tested_hypotheses(
                parsed_assessment=parsed_assessment,
                experiment_id=record.id,
            )

        except Exception as e:
            # Memory save failure should not fail the assessment
            logger.error(f"Failed to save experiment to memory: {e}")

    async def _save_hypotheses(
        self,
        parsed_assessment: ParsedAssessment,
        experiment_id: str,
    ) -> None:
        """Extract and save new hypotheses from assessment.

        This is a best-effort operation - failures are logged but don't
        fail the assessment. Memory is enhancement, not requirement.

        Args:
            parsed_assessment: Structured assessment from parse_assessment().
            experiment_id: ID of the experiment that generated these hypotheses.
        """
        try:
            for hyp_data in parsed_assessment.hypotheses:
                text = hyp_data.get("text", "")
                if not text:
                    continue

                hypothesis = Hypothesis(
                    id=generate_hypothesis_id(),
                    text=text,
                    source_experiment=experiment_id,
                    rationale=hyp_data.get("rationale", "Generated during assessment"),
                    status="untested",
                )

                save_hypothesis(hypothesis)
                logger.info(f"Saved new hypothesis: {hypothesis.id}")

        except Exception as e:
            logger.warning(f"Failed to save hypotheses: {e}")

    def _infer_hypothesis_status(
        self,
        parsed_assessment: ParsedAssessment,
        hyp_id: str,
    ) -> str:
        """Infer hypothesis status from assessment.

        Checks raw_text for explicit statements about the hypothesis,
        then falls back to verdict-based inference.

        Args:
            parsed_assessment: Structured assessment from parse_assessment().
            hyp_id: Hypothesis ID being tested (e.g., "H_001").

        Returns:
            Status string: "validated", "refuted", or "inconclusive".
        """
        raw_text = parsed_assessment.raw_text.lower()
        hyp_id_lower = hyp_id.lower()

        # Check for explicit statements, allowing up to 5 words between ID and status
        def matches_status(keywords: list[str]) -> bool:
            """Check if hyp_id is followed by any keyword within ~5 words."""
            keywords_pattern = "|".join(keywords)
            # Match: hyp_id, then up to 5 words, then a status keyword
            pattern = rf"{re.escape(hyp_id_lower)}\b(?:\W+\w+){{0,5}}?\W+(?:{keywords_pattern})\b"
            return re.search(pattern, raw_text) is not None

        if matches_status(["validated", "confirmed"]):
            return "validated"
        elif matches_status(["refuted", "disproved"]):
            return "refuted"
        elif matches_status(["inconclusive", "unclear"]):
            return "inconclusive"

        # Fall back to verdict-based inference
        if parsed_assessment.verdict == "strong_signal":
            return "validated"
        elif parsed_assessment.verdict == "no_signal":
            return "refuted"
        else:
            return "inconclusive"

    async def _update_tested_hypotheses(
        self,
        parsed_assessment: ParsedAssessment,
        experiment_id: str,
    ) -> None:
        """Update status of hypotheses that were tested in this experiment.

        This is a best-effort operation - failures are logged but don't
        fail the assessment. Memory is enhancement, not requirement.

        Args:
            parsed_assessment: Structured assessment from parse_assessment().
            experiment_id: ID of the experiment that tested these hypotheses.
        """
        try:
            for hyp_id in parsed_assessment.tested_hypothesis_ids:
                # Determine status from verdict and observations
                status = self._infer_hypothesis_status(parsed_assessment, hyp_id)

                update_hypothesis_status(
                    hypothesis_id=hyp_id,
                    status=status,
                    tested_by_experiment=experiment_id,
                )
                logger.info(f"Updated hypothesis {hyp_id}: status={status}")

        except Exception as e:
            logger.warning(f"Failed to update hypotheses: {e}")

    async def run(
        self,
        parent_operation_id: str,
        results: dict[str, Any],
        model: str | None = None,
        gate_rejection_reason: str | None = None,
    ) -> dict[str, Any]:
        """Run assessment phase using Claude.

        Args:
            parent_operation_id: Parent AGENT_RESEARCH operation ID.
            results: Dict with 'training' and 'backtest' result dicts.
                     'backtest' may be None for training gate rejections.
            model: Model to use ('opus', 'sonnet', 'haiku' or full ID).
                   If None, uses AGENT_MODEL env var or default.
            gate_rejection_reason: Reason for gate rejection, e.g.,
                   "accuracy_too_low (5% < 10%)". None for normal flow.

        Returns:
            Dict with verdict, assessment_path, and token counts.

        Raises:
            WorkerError: If assessment fails or Claude doesn't save assessment.
            asyncio.CancelledError: If cancelled.
        """
        # Resolve model (allows runtime switching via API/CLI)
        resolved_model = resolve_model(model)
        logger.info(
            f"Starting assessment phase: {parent_operation_id}, model={resolved_model}"
        )

        # Get parent operation for strategy info
        parent_op = await self.ops.get_operation(parent_operation_id)
        if parent_op is None:
            raise WorkerError(f"Parent operation not found: {parent_operation_id}")
        strategy_name = parent_op.metadata.parameters.get("strategy_name")
        strategy_path = parent_op.metadata.parameters.get("strategy_path")

        # Load strategy config for memory context (Task 4.1)
        strategy_config = self._load_strategy_config(strategy_path)

        # Set strategy name in executor for save_assessment tool
        self.tool_executor._current_strategy_name = strategy_name

        # Create child operation
        op = await self.ops.create_operation(
            operation_type=OperationType.AGENT_ASSESSMENT,
            metadata=OperationMetadata(
                parameters={"parent_operation_id": parent_operation_id}
            ),
            parent_operation_id=parent_operation_id,
        )

        # Store child op ID in parent metadata for tracking by orchestrator
        parent_op.metadata.parameters["assessment_op_id"] = op.operation_id

        try:
            # Build context for prompt
            # Note: use `or {}` because .get() returns None if key exists with None value
            context = AssessmentContext(
                operation_id=op.operation_id,
                strategy_name=strategy_name or "unknown",
                strategy_path=strategy_path or "unknown",
                training_metrics=results.get("training") or {},
                backtest_metrics=results.get("backtest") or {},
            )
            prompt = get_assessment_prompt(context)

            # Use injected invoker (for testing) or create new with resolved model
            if self._injected_invoker is not None:
                invoker = self._injected_invoker
            else:
                # Create invoker with resolved model config (Task 8.3 runtime selection)
                config = AnthropicInvokerConfig(model=resolved_model)
                invoker = AnthropicAgentInvoker(config=config)

            # Run Claude
            result = await invoker.run(
                prompt=prompt,
                tools=AGENT_TOOLS,
                system_prompt=ASSESSMENT_SYSTEM_PROMPT,
                tool_executor=self.tool_executor,
            )

            if not result.success:
                raise WorkerError(f"Claude assessment failed: {result.error}")

            # Get assessment from tool executor
            assessment = self.tool_executor.last_saved_assessment
            assessment_path = self.tool_executor.last_saved_assessment_path

            # Fallback: parse from text if tool wasn't called (common with Haiku)
            if not assessment and result.output and isinstance(result.output, str):
                logger.warning(
                    "Claude did not call save_assessment tool, attempting to parse from text"
                )
                assessment = _parse_assessment_from_text(result.output)
                if assessment:
                    # Save the parsed assessment to disk
                    try:
                        from ktrdr.agents.executor import ToolExecutor

                        temp_executor = ToolExecutor()
                        temp_executor._current_strategy_name = strategy_name
                        save_result = await temp_executor._handle_save_assessment(
                            verdict=assessment["verdict"],
                            strengths=assessment["strengths"],
                            weaknesses=assessment["weaknesses"],
                            suggestions=assessment["suggestions"],
                        )
                        if save_result.get("success"):
                            assessment_path = save_result.get("path")
                            logger.info(
                                f"Parsed assessment from text and saved: {assessment_path}"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to save parsed assessment: {e}")
                        assessment_path = None

            if not assessment:
                raise WorkerError("Claude did not save an assessment")

            # Parse assessment for structured memory record (Task 4.2)
            # Use API-based parsing (not CLI) for production reliability
            raw_output = (
                result.output
                if hasattr(result, "output") and result.output
                else str(assessment)
            )
            parsed_assessment = parse_assessment(
                output=raw_output,
                context={
                    "strategy_config": strategy_config,
                    "training_results": results.get("training") or {},
                    "backtest_results": results.get("backtest") or {},
                },
            )

            # Determine status for memory record
            if gate_rejection_reason:
                if results.get("backtest") is None:
                    status = "gate_rejected_training"
                else:
                    status = "gate_rejected_backtest"
            else:
                status = "completed"

            # Save to memory (best-effort, failures don't fail assessment)
            await self._save_to_memory(
                strategy_name=strategy_name or "unknown",
                strategy_config=strategy_config,
                training_metrics=results.get("training", {}),
                backtest_metrics=results.get("backtest"),
                parsed_assessment=parsed_assessment,
                status=status,
                gate_rejection_reason=gate_rejection_reason,
            )

            # Build result
            assessment_result = {
                "success": True,
                "verdict": assessment["verdict"],
                "strengths": assessment["strengths"],
                "weaknesses": assessment["weaknesses"],
                "suggestions": assessment["suggestions"],
                "assessment_path": assessment_path,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            }

            # Complete child operation
            await self.ops.complete_operation(op.operation_id, assessment_result)

            logger.info(
                f"Assessment phase completed: verdict={assessment['verdict']}, "
                f"input_tokens={result.input_tokens}, output_tokens={result.output_tokens}"
            )

            return assessment_result

        except asyncio.CancelledError:
            await self.ops.cancel_operation(op.operation_id, "Parent cancelled")
            raise
        except WorkerError as e:
            await self.ops.fail_operation(op.operation_id, str(e))
            raise
        except Exception as e:
            await self.ops.fail_operation(op.operation_id, str(e))
            raise WorkerError(f"Assessment failed: {e}") from e
