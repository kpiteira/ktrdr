"""Tests for ModelTrainer focal loss support."""

import pytest

torch = pytest.importorskip("torch")
import torch.nn as nn  # noqa: E402

from ktrdr.neural.losses import FocalLoss  # noqa: E402
from ktrdr.training.model_trainer import ModelTrainer  # noqa: E402


def make_config(**overrides) -> dict:
    """Create a classification training config."""
    config = {
        "output_format": "classification",
        "batch_size": 64,
        "gradient_clip": 1.0,
        "optimizer": "adam",
        "learning_rate": 0.01,
        "epochs": 5,
    }
    config.update(overrides)
    return config


def build_model(input_size: int = 8, num_classes: int = 3) -> nn.Module:
    """Build a simple classification model."""
    return nn.Sequential(
        nn.Linear(input_size, 32),
        nn.ReLU(),
        nn.Dropout(0.1),
        nn.Linear(32, num_classes),
    )


@pytest.fixture
def classification_data():
    """Create classification training + validation data."""
    torch.manual_seed(42)
    X_train = torch.randn(200, 8)
    y_train = torch.randint(0, 3, (200,))
    X_val = torch.randn(50, 8)
    y_val = torch.randint(0, 3, (50,))
    return X_train, y_train, X_val, y_val


# ============================================================
# FocalLoss unit tests
# ============================================================


class TestFocalLoss:
    """Test FocalLoss module directly."""

    def test_matches_ce_when_gamma_zero(self):
        """FocalLoss with gamma=0 is equivalent to CrossEntropyLoss."""
        torch.manual_seed(42)
        logits = torch.randn(100, 3)
        targets = torch.randint(0, 3, (100,))

        focal = FocalLoss(gamma=0.0)
        ce = nn.CrossEntropyLoss()

        assert focal(logits, targets).item() == pytest.approx(ce(logits, targets).item(), rel=1e-4)

    def test_downweights_easy_examples(self):
        """Focal loss gives less weight to well-classified examples."""
        # Moderately confident prediction
        logits = torch.tensor([[2.0, -1.0, -1.0]])
        targets = torch.tensor([0])

        ce_loss = FocalLoss(gamma=0.0)(logits, targets).item()
        focal_loss = FocalLoss(gamma=2.0)(logits, targets).item()

        assert focal_loss < ce_loss

    def test_hard_examples_have_higher_relative_weight(self):
        """Hard examples get relatively more weight than easy ones under focal loss."""
        easy_logits = torch.tensor([[5.0, -5.0, -5.0]])
        hard_logits = torch.tensor([[0.2, 0.1, -0.1]])
        targets = torch.tensor([0])

        ce = FocalLoss(gamma=0.0)
        focal = FocalLoss(gamma=2.0)

        ce_ratio = ce(hard_logits, targets).item() / ce(easy_logits, targets).item()
        focal_ratio = focal(hard_logits, targets).item() / focal(easy_logits, targets).item()

        assert focal_ratio > ce_ratio

    def test_alpha_weights_accepted(self):
        """Per-class alpha weights are applied."""
        torch.manual_seed(42)
        logits = torch.randn(100, 3)
        targets = torch.randint(0, 3, (100,))

        alpha = torch.tensor([1.0, 2.0, 1.0])
        focal = FocalLoss(gamma=2.0, alpha=alpha)
        loss = focal(logits, targets)

        assert loss.item() > 0
        assert not torch.isnan(loss)

    def test_gradient_flows(self):
        """Gradients flow correctly through focal loss."""
        logits = torch.randn(10, 3, requires_grad=True)
        targets = torch.randint(0, 3, (10,))

        loss = FocalLoss(gamma=2.0)(logits, targets)
        loss.backward()

        assert logits.grad is not None
        assert not torch.isnan(logits.grad).any()


# ============================================================
# ModelTrainer focal loss integration
# ============================================================


class TestModelTrainerFocalLoss:
    """Test focal loss integration in ModelTrainer."""

    def test_focal_loss_config(self, classification_data):
        """loss='focal' in config selects FocalLoss."""
        X_train, y_train, X_val, y_val = classification_data
        config = make_config(loss="focal", focal_gamma=2.0)
        trainer = ModelTrainer(config=config)
        model = build_model()

        result = trainer.train(
            model=model, X_train=X_train, y_train=y_train, X_val=X_val, y_val=y_val
        )
        assert "final_train_loss" in result
        assert result["final_train_loss"] > 0

    def test_focal_gamma_configurable(self, classification_data, monkeypatch):
        """focal_gamma parameter is passed to FocalLoss."""
        X_train, y_train, X_val, y_val = classification_data

        # Spy on FocalLoss to capture gamma values
        created_gammas: list[float] = []
        original_init = FocalLoss.__init__

        def spy_init(self, gamma=2.0, alpha=None):
            created_gammas.append(gamma)
            return original_init(self, gamma=gamma, alpha=alpha)

        monkeypatch.setattr(FocalLoss, "__init__", spy_init)

        for gamma in [0.0, 1.0, 3.0]:
            torch.manual_seed(42)
            config = make_config(loss="focal", focal_gamma=gamma)
            trainer = ModelTrainer(config=config)
            model = build_model()
            trainer.train(
                model=model, X_train=X_train, y_train=y_train, X_val=X_val, y_val=y_val
            )

        assert created_gammas == [0.0, 1.0, 3.0]

    def test_default_is_cross_entropy(self, classification_data):
        """Without loss config, CrossEntropyLoss is used (backward compatible)."""
        X_train, y_train, X_val, y_val = classification_data
        config = make_config()  # No 'loss' key
        trainer = ModelTrainer(config=config)
        model = build_model()

        result = trainer.train(
            model=model, X_train=X_train, y_train=y_train, X_val=X_val, y_val=y_val
        )
        assert "final_train_loss" in result

    def test_focal_with_imbalanced_data(self):
        """Focal loss trains successfully on imbalanced data."""
        torch.manual_seed(42)
        # 80% class 0, 10% class 1, 10% class 2
        X_train = torch.randn(200, 8)
        y_train = torch.cat([torch.zeros(160), torch.ones(20), torch.full((20,), 2)]).long()
        X_val = torch.randn(50, 8)
        y_val = torch.randint(0, 3, (50,))

        config = make_config(loss="focal", focal_gamma=2.0, epochs=10)
        trainer = ModelTrainer(config=config)
        model = build_model()

        result = trainer.train(
            model=model, X_train=X_train, y_train=y_train, X_val=X_val, y_val=y_val
        )
        assert result["final_train_loss"] > 0
        assert not any(
            torch.isnan(torch.tensor(m.train_loss)) for m in trainer.history
        )
