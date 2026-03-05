"""Tests for Task 5.4: Old invoker code removal and model resolution extraction.

Verifies:
- Model resolution works from new location (ktrdr.agents.models)
- Old invoker/executor/tools modules are deleted (no imports)
- Agent __init__ no longer exports old symbols
- Agent service uses new model resolution import
- Stub workers still function with dispatch pattern
"""

import importlib

import pytest


class TestModelResolutionExtracted:
    """Model constants and resolve_model moved to ktrdr.agents.models."""

    def test_resolve_model_importable_from_new_location(self):
        """resolve_model can be imported from ktrdr.agents.models."""
        from ktrdr.agents.models import resolve_model

        assert callable(resolve_model)

    def test_model_aliases_available(self):
        """MODEL_ALIASES dict is in ktrdr.agents.models."""
        from ktrdr.agents.models import MODEL_ALIASES

        assert "opus" in MODEL_ALIASES
        assert "sonnet" in MODEL_ALIASES
        assert "haiku" in MODEL_ALIASES

    def test_valid_models_available(self):
        """VALID_MODELS dict is in ktrdr.agents.models."""
        from ktrdr.agents.models import VALID_MODELS

        assert len(VALID_MODELS) >= 3

    def test_default_model_available(self):
        """DEFAULT_MODEL constant is in ktrdr.agents.models."""
        from ktrdr.agents.models import DEFAULT_MODEL

        assert "claude" in DEFAULT_MODEL

    def test_resolve_model_alias(self):
        """resolve_model resolves short aliases."""
        from ktrdr.agents.models import MODEL_ALIASES, resolve_model

        result = resolve_model("opus")
        assert result == MODEL_ALIASES["opus"]

    def test_resolve_model_full_id(self):
        """resolve_model accepts full model IDs."""
        from ktrdr.agents.models import resolve_model

        result = resolve_model("claude-opus-4-5-20251101")
        assert result == "claude-opus-4-5-20251101"

    def test_resolve_model_invalid_raises(self):
        """resolve_model raises ValueError for unknown models."""
        from ktrdr.agents.models import resolve_model

        with pytest.raises(ValueError, match="Invalid model"):
            resolve_model("gpt-4")


class TestOldModulesDeleted:
    """Verify old invoker/executor/tools are gone."""

    def test_invoker_not_importable(self):
        """ktrdr.agents.invoker should not exist."""
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("ktrdr.agents.invoker")

    def test_executor_not_importable(self):
        """ktrdr.agents.executor should not exist."""
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("ktrdr.agents.executor")

    def test_tools_not_importable(self):
        """ktrdr.agents.tools should not exist."""
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("ktrdr.agents.tools")


class TestAgentInitCleaned:
    """Agent __init__ no longer exports old symbols."""

    def test_no_anthropic_invoker_export(self):
        """AnthropicAgentInvoker not in agents __all__."""
        import ktrdr.agents

        assert not hasattr(ktrdr.agents, "AnthropicAgentInvoker")

    def test_no_tool_executor_export(self):
        """ToolExecutor not in agents __all__."""
        import ktrdr.agents

        assert not hasattr(ktrdr.agents, "ToolExecutor")

    def test_no_agent_tools_export(self):
        """AGENT_TOOLS not in agents __all__."""
        import ktrdr.agents

        assert not hasattr(ktrdr.agents, "AGENT_TOOLS")


class TestStubWorkersStillWork:
    """Stub workers function correctly after cleanup."""

    @pytest.mark.asyncio
    async def test_stub_design_worker_returns_result(self):
        """StubDesignWorker.run() still returns expected format."""
        import os

        os.environ["STUB_WORKER_FAST"] = "true"
        try:
            from ktrdr.agents.workers.stubs import StubDesignWorker

            worker = StubDesignWorker()
            result = await worker.run("op_test", brief="test brief")
            assert result["success"] is True
            assert "strategy_name" in result
        finally:
            os.environ.pop("STUB_WORKER_FAST", None)

    @pytest.mark.asyncio
    async def test_stub_assessment_worker_returns_result(self):
        """StubAssessmentWorker.run() still returns expected format."""
        import os

        os.environ["STUB_WORKER_FAST"] = "true"
        try:
            from ktrdr.agents.workers.stubs import StubAssessmentWorker

            worker = StubAssessmentWorker()
            result = await worker.run("op_test", results={"accuracy": 0.6})
            assert result["success"] is True
            assert "verdict" in result
        finally:
            os.environ.pop("STUB_WORKER_FAST", None)
