"""Tests for stub workers.

Task 1.2 of M1: Verify stub workers return expected mock results.

Note: Only StubDesignWorker and StubAssessmentWorker exist now.
Training and Backtest are handled by services directly.
"""

import time

import pytest

from ktrdr.agents.workers.stubs import (
    StubAssessmentWorker,
    StubDesignWorker,
)


class TestStubDesignWorker:
    """Test StubDesignWorker returns expected design results."""

    @pytest.mark.asyncio
    async def test_returns_strategy_name(self):
        """Design worker should return a strategy name."""
        worker = StubDesignWorker()
        result = await worker.run("op_test_123")

        assert result["success"] is True
        assert "strategy_name" in result
        assert isinstance(result["strategy_name"], str)
        assert len(result["strategy_name"]) > 0

    @pytest.mark.asyncio
    async def test_returns_strategy_path(self):
        """Design worker should return a strategy path."""
        worker = StubDesignWorker()
        result = await worker.run("op_test_123")

        assert "strategy_path" in result
        assert result["strategy_path"].endswith(".yaml")

    @pytest.mark.asyncio
    async def test_returns_token_counts(self):
        """Design worker should return token usage."""
        worker = StubDesignWorker()
        result = await worker.run("op_test_123")

        assert "input_tokens" in result
        assert "output_tokens" in result
        assert isinstance(result["input_tokens"], int)
        assert isinstance(result["output_tokens"], int)

    @pytest.mark.asyncio
    async def test_has_delay(self, monkeypatch):
        """Design worker should have ~500ms delay when STUB_WORKER_FAST=true."""
        # Set STUB_WORKER_FAST to get predictable 500ms delay
        monkeypatch.setenv("STUB_WORKER_FAST", "true")

        worker = StubDesignWorker()
        start = time.time()
        await worker.run("op_test_123")
        elapsed = time.time() - start

        # Allow some tolerance (400ms to 700ms)
        assert 0.4 <= elapsed <= 0.7, f"Expected ~500ms delay, got {elapsed*1000:.0f}ms"


class TestStubAssessmentWorker:
    """Test StubAssessmentWorker returns expected assessment results."""

    @pytest.mark.asyncio
    async def test_returns_verdict(self):
        """Assessment worker should return a verdict."""
        worker = StubAssessmentWorker()
        result = await worker.run(
            "op_test_123",
            {"training": {"accuracy": 0.65}, "backtest": {"sharpe_ratio": 1.2}},
        )

        assert result["success"] is True
        assert "verdict" in result
        assert result["verdict"] in ["promising", "mediocre", "poor"]

    @pytest.mark.asyncio
    async def test_returns_strengths_and_weaknesses(self):
        """Assessment worker should return strengths and weaknesses."""
        worker = StubAssessmentWorker()
        result = await worker.run("op_test_123", {})

        assert "strengths" in result
        assert "weaknesses" in result
        assert "suggestions" in result
        assert isinstance(result["strengths"], list)
        assert isinstance(result["weaknesses"], list)

    @pytest.mark.asyncio
    async def test_returns_token_counts(self):
        """Assessment worker should return token usage."""
        worker = StubAssessmentWorker()
        result = await worker.run("op_test_123", {})

        assert "input_tokens" in result
        assert "output_tokens" in result

    @pytest.mark.asyncio
    async def test_has_delay(self, monkeypatch):
        """Assessment worker should have ~500ms delay when STUB_WORKER_FAST=true."""
        monkeypatch.setenv("STUB_WORKER_FAST", "true")

        worker = StubAssessmentWorker()
        start = time.time()
        await worker.run("op_test_123", {})
        elapsed = time.time() - start

        assert 0.4 <= elapsed <= 0.7, f"Expected ~500ms delay, got {elapsed*1000:.0f}ms"

    @pytest.mark.asyncio
    async def test_returns_assessment_path(self):
        """Assessment worker should return assessment_path per ARCHITECTURE.md."""
        worker = StubAssessmentWorker()
        result = await worker.run("op_test_123", {})

        assert "assessment_path" in result
        assert result["assessment_path"].endswith(".json")
