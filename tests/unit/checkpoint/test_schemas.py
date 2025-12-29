"""Unit tests for checkpoint schemas."""

from ktrdr.checkpoint.schemas import (
    TRAINING_ARTIFACTS,
    TrainingCheckpointState,
)


class TestTrainingCheckpointState:
    """Tests for TrainingCheckpointState dataclass."""

    def test_required_fields(self):
        """Should require epoch, train_loss, val_loss."""
        state = TrainingCheckpointState(
            epoch=5,
            train_loss=0.5,
            val_loss=0.4,
        )
        assert state.epoch == 5
        assert state.train_loss == 0.5
        assert state.val_loss == 0.4

    def test_optional_fields_have_defaults(self):
        """Optional fields should have sensible defaults."""
        state = TrainingCheckpointState(
            epoch=5,
            train_loss=0.5,
            val_loss=0.4,
        )
        assert state.train_accuracy is None
        assert state.val_accuracy is None
        assert state.learning_rate == 0.001
        assert state.best_val_loss == float("inf")
        assert state.training_history == {}
        assert state.original_request == {}

    def test_all_fields(self):
        """Should accept all fields."""
        history = {"train_loss": [0.5, 0.4], "val_loss": [0.45, 0.35]}
        request = {"symbol": "BTCUSD", "epochs": 100}

        state = TrainingCheckpointState(
            epoch=10,
            train_loss=0.3,
            val_loss=0.25,
            train_accuracy=0.85,
            val_accuracy=0.82,
            learning_rate=0.0005,
            best_val_loss=0.22,
            training_history=history,
            original_request=request,
        )

        assert state.epoch == 10
        assert state.train_loss == 0.3
        assert state.val_loss == 0.25
        assert state.train_accuracy == 0.85
        assert state.val_accuracy == 0.82
        assert state.learning_rate == 0.0005
        assert state.best_val_loss == 0.22
        assert state.training_history == history
        assert state.original_request == request

    def test_to_dict(self):
        """Should be convertible to dict for JSON serialization."""
        state = TrainingCheckpointState(
            epoch=5,
            train_loss=0.5,
            val_loss=0.4,
        )

        d = state.to_dict()

        assert isinstance(d, dict)
        assert d["epoch"] == 5
        assert d["train_loss"] == 0.5
        assert d["val_loss"] == 0.4

    def test_from_dict(self):
        """Should be creatable from dict (for deserialization)."""
        data = {
            "epoch": 5,
            "train_loss": 0.5,
            "val_loss": 0.4,
            "train_accuracy": 0.8,
            "val_accuracy": 0.75,
            "learning_rate": 0.001,
            "best_val_loss": 0.35,
            "training_history": {"train_loss": [0.5]},
            "original_request": {"symbol": "BTCUSD"},
        }

        state = TrainingCheckpointState.from_dict(data)

        assert state.epoch == 5
        assert state.train_loss == 0.5
        assert state.train_accuracy == 0.8
        assert state.training_history == {"train_loss": [0.5]}

    def test_from_dict_with_missing_optional_fields(self):
        """from_dict should handle missing optional fields gracefully."""
        data = {
            "epoch": 5,
            "train_loss": 0.5,
            "val_loss": 0.4,
        }

        state = TrainingCheckpointState.from_dict(data)

        assert state.epoch == 5
        assert state.train_accuracy is None
        assert state.learning_rate == 0.001


class TestTrainingArtifacts:
    """Tests for TRAINING_ARTIFACTS manifest."""

    def test_required_artifacts(self):
        """model.pt and optimizer.pt should be required."""
        assert TRAINING_ARTIFACTS["model.pt"] == "required"
        assert TRAINING_ARTIFACTS["optimizer.pt"] == "required"

    def test_optional_artifacts(self):
        """scheduler.pt and best_model.pt should be optional."""
        assert TRAINING_ARTIFACTS["scheduler.pt"] == "optional"
        assert TRAINING_ARTIFACTS["best_model.pt"] == "optional"

    def test_all_expected_artifacts_present(self):
        """Should have exactly 4 artifact types."""
        expected = {"model.pt", "optimizer.pt", "scheduler.pt", "best_model.pt"}
        assert set(TRAINING_ARTIFACTS.keys()) == expected


class TestBacktestCheckpointState:
    """Tests for BacktestCheckpointState dataclass."""

    def test_required_fields(self):
        """Should require operation_type, bar_index, current_date, cash."""
        from ktrdr.checkpoint.schemas import BacktestCheckpointState

        state = BacktestCheckpointState(
            bar_index=1000,
            current_date="2023-06-15T14:30:00",
            cash=95000.0,
        )
        assert state.operation_type == "backtesting"
        assert state.bar_index == 1000
        assert state.current_date == "2023-06-15T14:30:00"
        assert state.cash == 95000.0

    def test_optional_fields_have_defaults(self):
        """Optional fields should have sensible defaults."""
        from ktrdr.checkpoint.schemas import BacktestCheckpointState

        state = BacktestCheckpointState(
            bar_index=1000,
            current_date="2023-06-15T14:30:00",
            cash=95000.0,
        )
        assert state.positions == []
        assert state.trades == []
        assert state.equity_samples == []
        assert state.original_request == {}

    def test_all_fields(self):
        """Should accept all fields."""
        from ktrdr.checkpoint.schemas import BacktestCheckpointState

        positions = [
            {
                "symbol": "EURUSD",
                "quantity": 100,
                "entry_price": 1.0850,
                "entry_date": "2023-06-10T10:00:00",
            }
        ]
        trades = [
            {
                "trade_id": 1,
                "symbol": "EURUSD",
                "side": "BUY",
                "quantity": 100,
                "price": 1.0800,
                "date": "2023-06-05T09:00:00",
                "pnl": 150.0,
            }
        ]
        equity_samples = [
            {"bar_index": 0, "equity": 100000.0},
            {"bar_index": 500, "equity": 102000.0},
            {"bar_index": 1000, "equity": 105000.0},
        ]
        original_request = {
            "symbol": "EURUSD",
            "timeframe": "1h",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
        }

        state = BacktestCheckpointState(
            bar_index=1000,
            current_date="2023-06-15T14:30:00",
            cash=95000.0,
            positions=positions,
            trades=trades,
            equity_samples=equity_samples,
            original_request=original_request,
        )

        assert state.operation_type == "backtesting"
        assert state.bar_index == 1000
        assert state.current_date == "2023-06-15T14:30:00"
        assert state.cash == 95000.0
        assert state.positions == positions
        assert state.trades == trades
        assert state.equity_samples == equity_samples
        assert state.original_request == original_request

    def test_to_dict(self):
        """Should be convertible to dict for JSON serialization."""
        from ktrdr.checkpoint.schemas import BacktestCheckpointState

        state = BacktestCheckpointState(
            bar_index=1000,
            current_date="2023-06-15T14:30:00",
            cash=95000.0,
        )

        d = state.to_dict()

        assert isinstance(d, dict)
        assert d["operation_type"] == "backtesting"
        assert d["bar_index"] == 1000
        assert d["current_date"] == "2023-06-15T14:30:00"
        assert d["cash"] == 95000.0
        assert d["positions"] == []
        assert d["trades"] == []
        assert d["equity_samples"] == []

    def test_from_dict(self):
        """Should be creatable from dict (for deserialization)."""
        from ktrdr.checkpoint.schemas import BacktestCheckpointState

        data = {
            "operation_type": "backtesting",
            "bar_index": 1000,
            "current_date": "2023-06-15T14:30:00",
            "cash": 95000.0,
            "positions": [{"symbol": "EURUSD", "quantity": 100}],
            "trades": [{"trade_id": 1, "pnl": 150.0}],
            "equity_samples": [{"bar_index": 0, "equity": 100000.0}],
            "original_request": {"symbol": "EURUSD"},
        }

        state = BacktestCheckpointState.from_dict(data)

        assert state.operation_type == "backtesting"
        assert state.bar_index == 1000
        assert state.cash == 95000.0
        assert len(state.positions) == 1
        assert len(state.trades) == 1
        assert len(state.equity_samples) == 1

    def test_from_dict_with_missing_optional_fields(self):
        """from_dict should handle missing optional fields gracefully."""
        from ktrdr.checkpoint.schemas import BacktestCheckpointState

        data = {
            "bar_index": 1000,
            "current_date": "2023-06-15T14:30:00",
            "cash": 95000.0,
        }

        state = BacktestCheckpointState.from_dict(data)

        assert state.operation_type == "backtesting"
        assert state.bar_index == 1000
        assert state.positions == []
        assert state.trades == []

    def test_operation_type_is_always_backtesting(self):
        """operation_type should always be 'backtesting' (hardcoded default)."""
        from ktrdr.checkpoint.schemas import BacktestCheckpointState

        state = BacktestCheckpointState(
            bar_index=0,
            current_date="2023-01-01T00:00:00",
            cash=100000.0,
        )
        assert state.operation_type == "backtesting"

        # Even if you try to override it, default should be backtesting
        # (This tests the dataclass field default)
