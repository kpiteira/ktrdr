"""Tests for N-class generalization of DecisionFunction.

Verifies that DecisionFunction handles 4-class regime classification
and 3-class context classification with correctly labeled outputs,
while maintaining backward compatibility for default 3-class signal output.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from ktrdr.backtesting.decision_function import DecisionFunction
from ktrdr.backtesting.position_manager import PositionStatus
from ktrdr.decision.base import Signal

# Re-use test helpers from existing tests
from tests.unit.backtesting.test_decision_function import _make_bar


def _make_predict_output_n(
    class_names: list[str], dominant_idx: int, confidence: float = 0.8
) -> dict[str, Any]:
    """Create a _predict() return dict for N-class output."""
    n = len(class_names)
    remaining = 1.0 - confidence
    probs_dict = {}
    for i, name in enumerate(class_names):
        if i == dominant_idx:
            probs_dict[name] = confidence
        else:
            probs_dict[name] = remaining / (n - 1)

    return {
        "signal": Signal.HOLD,  # Non-signal output types return HOLD
        "confidence": confidence,
        "probabilities": probs_dict,
    }


def _make_df(
    output_type: str = "classification",
    decisions_config: dict | None = None,
) -> DecisionFunction:
    """Create a DecisionFunction with mocked _predict, for a given output_type."""
    if decisions_config is None:
        decisions_config = {
            "output_format": "classification",
            "confidence_threshold": 0.5,
        }
    model = MagicMock()
    df = DecisionFunction(model, ["f1"], decisions_config, output_type=output_type)
    return df


class TestBackwardCompatibility:
    """Default 3-class output must produce BUY/HOLD/SELL — no regression."""

    def test_default_3class_probabilities_keys(self) -> None:
        df = _make_df()
        predict_output = {
            "signal": Signal.BUY,
            "confidence": 0.7,
            "probabilities": {"BUY": 0.7, "HOLD": 0.2, "SELL": 0.1},
        }
        df._predict = MagicMock(return_value=predict_output)  # type: ignore[method-assign]
        result = df({"f1": 0.5}, PositionStatus.FLAT, _make_bar())
        probs = result.reasoning["nn_probabilities"]
        assert set(probs.keys()) == {"BUY", "HOLD", "SELL"}

    def test_default_3class_signal_mapping(self) -> None:
        df = _make_df()
        predict_output = {
            "signal": Signal.BUY,
            "confidence": 0.7,
            "probabilities": {"BUY": 0.7, "HOLD": 0.2, "SELL": 0.1},
        }
        df._predict = MagicMock(return_value=predict_output)  # type: ignore[method-assign]
        result = df({"f1": 0.5}, PositionStatus.FLAT, _make_bar())
        assert result.signal == Signal.BUY


class TestRegimeClassification:
    """4-class regime classification output."""

    def test_regime_probabilities_keys(self) -> None:
        df = _make_df(output_type="regime_classification")
        predict_output = _make_predict_output_n(
            ["TRENDING_UP", "TRENDING_DOWN", "RANGING", "VOLATILE"], 0, 0.6
        )
        df._predict = MagicMock(return_value=predict_output)  # type: ignore[method-assign]
        result = df({"f1": 0.5}, PositionStatus.FLAT, _make_bar())
        probs = result.reasoning["nn_probabilities"]
        assert set(probs.keys()) == {
            "TRENDING_UP",
            "TRENDING_DOWN",
            "RANGING",
            "VOLATILE",
        }

    def test_regime_argmax_4class(self) -> None:
        df = _make_df(output_type="regime_classification")
        predict_output = _make_predict_output_n(
            ["TRENDING_UP", "TRENDING_DOWN", "RANGING", "VOLATILE"], 2, 0.7
        )
        df._predict = MagicMock(return_value=predict_output)  # type: ignore[method-assign]
        result = df({"f1": 0.5}, PositionStatus.FLAT, _make_bar())
        probs = result.reasoning["nn_probabilities"]
        assert max(probs, key=probs.get) == "RANGING"  # type: ignore[arg-type]

    def test_regime_signal_is_hold(self) -> None:
        """Regime classification always returns HOLD signal."""
        df = _make_df(output_type="regime_classification")
        predict_output = _make_predict_output_n(
            ["TRENDING_UP", "TRENDING_DOWN", "RANGING", "VOLATILE"], 0, 0.8
        )
        df._predict = MagicMock(return_value=predict_output)  # type: ignore[method-assign]
        result = df({"f1": 0.5}, PositionStatus.FLAT, _make_bar())
        assert result.signal == Signal.HOLD


class TestContextClassification:
    """3-class context classification output."""

    def test_context_probabilities_keys(self) -> None:
        df = _make_df(output_type="context_classification")
        predict_output = _make_predict_output_n(
            ["BULLISH", "BEARISH", "NEUTRAL"], 0, 0.7
        )
        df._predict = MagicMock(return_value=predict_output)  # type: ignore[method-assign]
        result = df({"f1": 0.5}, PositionStatus.FLAT, _make_bar())
        probs = result.reasoning["nn_probabilities"]
        assert set(probs.keys()) == {"BULLISH", "BEARISH", "NEUTRAL"}

    def test_context_signal_is_hold(self) -> None:
        df = _make_df(output_type="context_classification")
        predict_output = _make_predict_output_n(
            ["BULLISH", "BEARISH", "NEUTRAL"], 0, 0.8
        )
        df._predict = MagicMock(return_value=predict_output)  # type: ignore[method-assign]
        result = df({"f1": 0.5}, PositionStatus.FLAT, _make_bar())
        assert result.signal == Signal.HOLD


class TestPredictNClass:
    """Test that _predict() uses dynamic class names for probabilities.

    Uses unittest.mock.patch to inject a fake torch module, avoiding the
    real torch dependency (same approach as existing decision function tests
    which mock _predict entirely — but here we test the probabilities
    dict construction inside _predict).
    """

    def test_predict_default_classification_probs(self) -> None:
        """Default classification _predict() returns BUY/HOLD/SELL keys."""
        from unittest.mock import patch

        mock_torch = MagicMock()
        mock_tensor = MagicMock()
        mock_tensor.unsqueeze.return_value = mock_tensor

        # Model output: 3-class softmax
        mock_model_output = MagicMock()
        mock_model_output.shape = [1, 3]
        mock_row = MagicMock()
        mock_row.cpu.return_value.numpy.return_value = np.array([0.7, 0.2, 0.1])
        mock_model_output.__getitem__ = lambda self, idx: mock_row

        mock_torch.tensor.return_value = mock_tensor
        mock_torch.no_grad.return_value.__enter__ = MagicMock()
        mock_torch.no_grad.return_value.__exit__ = MagicMock()

        model = MagicMock()
        model.return_value = mock_model_output
        df = DecisionFunction(model, ["f1"], {"output_format": "classification"})

        with patch.dict("sys.modules", {"torch": mock_torch}):
            result = df._predict({"f1": 0.5})

        assert set(result["probabilities"].keys()) == {"BUY", "HOLD", "SELL"}
        assert result["signal"] == Signal.BUY

    def test_predict_regime_classification_probs(self) -> None:
        """Regime classification _predict() returns regime label keys."""
        from unittest.mock import patch

        mock_torch = MagicMock()
        mock_tensor = MagicMock()
        mock_tensor.unsqueeze.return_value = mock_tensor

        # Model output: 4-class softmax
        mock_model_output = MagicMock()
        mock_model_output.shape = [1, 4]
        mock_row = MagicMock()
        mock_row.cpu.return_value.numpy.return_value = np.array([0.1, 0.1, 0.7, 0.1])
        mock_model_output.__getitem__ = lambda self, idx: mock_row

        mock_torch.tensor.return_value = mock_tensor
        mock_torch.no_grad.return_value.__enter__ = MagicMock()
        mock_torch.no_grad.return_value.__exit__ = MagicMock()

        model = MagicMock()
        model.return_value = mock_model_output
        df = DecisionFunction(
            model,
            ["f1"],
            {"output_format": "classification"},
            output_type="regime_classification",
        )

        with patch.dict("sys.modules", {"torch": mock_torch}):
            result = df._predict({"f1": 0.5})

        assert set(result["probabilities"].keys()) == {
            "TRENDING_UP",
            "TRENDING_DOWN",
            "RANGING",
            "VOLATILE",
        }
        assert result["signal"] == Signal.HOLD
        assert result["confidence"] == pytest.approx(0.7, abs=0.01)
