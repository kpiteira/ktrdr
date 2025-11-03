"""
Unit tests for TrainingPipeline multi-symbol methods.

Tests the symbol-agnostic multi-symbol training design where strategies
operate on patterns (technical indicators + fuzzy memberships) rather than
symbol names.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import torch

from ktrdr.training.training_pipeline import TrainingPipeline


class TestCombineMultiSymbolData:
    """Test TrainingPipeline.combine_multi_symbol_data() - symbol-agnostic design."""

    def test_combine_two_symbols_sequential_concatenation(self):
        """Test combining data from two symbols preserves temporal order."""
        # Arrange
        symbols = ["AAPL", "MSFT"]

        # AAPL: 100 samples
        aapl_features = torch.randn(100, 50)
        aapl_labels = torch.randint(0, 3, (100,))

        # MSFT: 120 samples
        msft_features = torch.randn(120, 50)
        msft_labels = torch.randint(0, 3, (120,))

        all_features = {"AAPL": aapl_features, "MSFT": msft_features}
        all_labels = {"AAPL": aapl_labels, "MSFT": msft_labels}

        # Act
        combined_features, combined_labels = TrainingPipeline.combine_multi_symbol_data(
            all_features, all_labels, symbols
        )

        # Assert - Sequential concatenation (AAPL all data → MSFT all data)
        assert combined_features.shape == (220, 50)  # 100 + 120
        assert combined_labels.shape == (220,)

        # First 100 samples should be AAPL
        assert torch.equal(combined_features[:100], aapl_features)
        assert torch.equal(combined_labels[:100], aapl_labels)

        # Next 120 samples should be MSFT
        assert torch.equal(combined_features[100:], msft_features)
        assert torch.equal(combined_labels[100:], msft_labels)

    def test_combine_three_symbols_uses_all_data(self):
        """Test that ALL data from all symbols is used (no sampling/data loss)."""
        # Arrange
        symbols = ["AAPL", "MSFT", "GOOGL"]

        # Different sample counts
        aapl_features = torch.randn(80, 50)
        aapl_labels = torch.randint(0, 3, (80,))

        msft_features = torch.randn(100, 50)
        msft_labels = torch.randint(0, 3, (100,))

        googl_features = torch.randn(120, 50)
        googl_labels = torch.randint(0, 3, (120,))

        all_features = {
            "AAPL": aapl_features,
            "MSFT": msft_features,
            "GOOGL": googl_features,
        }
        all_labels = {
            "AAPL": aapl_labels,
            "MSFT": msft_labels,
            "GOOGL": googl_labels,
        }

        # Act
        combined_features, combined_labels = TrainingPipeline.combine_multi_symbol_data(
            all_features, all_labels, symbols
        )

        # Assert - ALL data used, NO sampling
        assert combined_features.shape == (300, 50)  # 80 + 100 + 120 = 300
        assert combined_labels.shape == (300,)

        # Verify each symbol's data is present in sequence
        assert torch.equal(combined_features[:80], aapl_features)
        assert torch.equal(combined_features[80:180], msft_features)
        assert torch.equal(combined_features[180:], googl_features)

    def test_returns_only_features_and_labels_no_symbol_indices(self):
        """Test that method returns ONLY features and labels (symbol-agnostic)."""
        # Arrange
        symbols = ["AAPL", "MSFT"]
        all_features = {
            "AAPL": torch.randn(100, 50),
            "MSFT": torch.randn(100, 50),
        }
        all_labels = {
            "AAPL": torch.randint(0, 3, (100,)),
            "MSFT": torch.randint(0, 3, (100,)),
        }

        # Act
        result = TrainingPipeline.combine_multi_symbol_data(
            all_features, all_labels, symbols
        )

        # Assert - Returns tuple of (features, labels) ONLY
        assert isinstance(result, tuple)
        assert len(result) == 2  # NOT 3 (no symbol_indices)
        combined_features, combined_labels = result
        assert isinstance(combined_features, torch.Tensor)
        assert isinstance(combined_labels, torch.Tensor)

    def test_single_symbol_works(self):
        """Test that method works with single symbol (edge case)."""
        # Arrange
        symbols = ["AAPL"]
        aapl_features = torch.randn(100, 50)
        aapl_labels = torch.randint(0, 3, (100,))

        all_features = {"AAPL": aapl_features}
        all_labels = {"AAPL": aapl_labels}

        # Act
        combined_features, combined_labels = TrainingPipeline.combine_multi_symbol_data(
            all_features, all_labels, symbols
        )

        # Assert - Should return the same data
        assert torch.equal(combined_features, aapl_features)
        assert torch.equal(combined_labels, aapl_labels)

    def test_preserves_feature_dimensionality(self):
        """Test that feature dimensionality is preserved during concatenation."""
        # Arrange
        symbols = ["AAPL", "MSFT"]
        feature_dim = 75

        all_features = {
            "AAPL": torch.randn(100, feature_dim),
            "MSFT": torch.randn(120, feature_dim),
        }
        all_labels = {
            "AAPL": torch.randint(0, 3, (100,)),
            "MSFT": torch.randint(0, 3, (120,)),
        }

        # Act
        combined_features, combined_labels = TrainingPipeline.combine_multi_symbol_data(
            all_features, all_labels, symbols
        )

        # Assert
        assert combined_features.shape[1] == feature_dim
        assert combined_features.shape[0] == 220  # 100 + 120

    def test_symbol_order_matters(self):
        """Test that symbols are concatenated in the order provided."""
        # Arrange
        aapl_features = torch.ones(50, 10) * 1.0
        msft_features = torch.ones(50, 10) * 2.0
        googl_features = torch.ones(50, 10) * 3.0

        all_features = {
            "AAPL": aapl_features,
            "MSFT": msft_features,
            "GOOGL": googl_features,
        }
        all_labels = {
            "AAPL": torch.zeros(50),
            "MSFT": torch.ones(50),
            "GOOGL": torch.ones(50) * 2,
        }

        # Act - Different symbol orders
        result1_features, _ = TrainingPipeline.combine_multi_symbol_data(
            all_features, all_labels, ["AAPL", "MSFT", "GOOGL"]
        )
        result2_features, _ = TrainingPipeline.combine_multi_symbol_data(
            all_features, all_labels, ["GOOGL", "MSFT", "AAPL"]
        )

        # Assert - Different orders produce different concatenations
        assert not torch.equal(result1_features, result2_features)
        # First should be AAPL (all 1s), second should be GOOGL (all 3s)
        assert torch.allclose(result1_features[:50], torch.ones(50, 10))
        assert torch.allclose(result2_features[:50], torch.ones(50, 10) * 3.0)


class TestTrainStrategyHighLevel:
    """Test TrainingPipeline.train_strategy() high-level orchestration method."""

    @patch("ktrdr.training.training_pipeline.TrainingPipeline.load_market_data")
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.calculate_indicators")
    @patch(
        "ktrdr.training.training_pipeline.TrainingPipeline.generate_fuzzy_memberships"
    )
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.create_features")
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.create_labels")
    @patch(
        "ktrdr.training.training_pipeline.TrainingPipeline.combine_multi_symbol_data"
    )
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.create_model")
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.train_model")
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.evaluate_model")
    def test_single_symbol_training_flow(
        self,
        mock_evaluate,
        mock_train,
        mock_create_model,
        mock_combine,
        mock_labels,
        mock_features,
        mock_fuzzy,
        mock_indicators,
        mock_load_data,
    ):
        """Test train_strategy() orchestrates single-symbol training correctly."""
        # Arrange
        mock_storage = MagicMock()

        # Mock pipeline methods
        mock_load_data.return_value = {"1d": pd.DataFrame()}
        mock_indicators.return_value = {"1d": pd.DataFrame()}
        mock_fuzzy.return_value = {"1d": pd.DataFrame()}
        mock_features.return_value = (torch.randn(100, 50), ["feature1", "feature2"])
        mock_labels.return_value = torch.randint(0, 3, (100,))

        # For single symbol, combine_multi_symbol_data should just pass through
        mock_combine.return_value = (torch.randn(100, 50), torch.randint(0, 3, (100,)))

        mock_model = MagicMock()
        mock_create_model.return_value = mock_model

        mock_train.return_value = {
            "final_train_loss": 0.5,
            "final_val_loss": 0.6,
            "final_train_accuracy": 0.8,
            "final_val_accuracy": 0.75,
        }

        mock_evaluate.return_value = {
            "test_loss": 0.65,
            "test_accuracy": 0.76,
        }

        mock_storage.save_model.return_value = "models/test_strategy/AAPL_1d_v1.pth"

        strategy_config = {
            "name": "test_strategy",
            "indicators": [],
            "fuzzy_sets": {},
            "model": {"training": {}, "features": {}},
            "training": {
                "labels": {},
                "data_split": {"test_size": 0.1, "validation_size": 0.2},
            },
        }

        # Act
        result = TrainingPipeline.train_strategy(
            symbols=["AAPL"],
            timeframes=["1d"],
            strategy_config=strategy_config,
            start_date="2024-01-01",
            end_date="2024-12-31",
            model_storage=mock_storage,
            progress_callback=None,
            cancellation_token=None,
        )

        # Assert - Verify all steps were called
        mock_load_data.assert_called_once()
        mock_indicators.assert_called_once()
        mock_fuzzy.assert_called_once()
        mock_features.assert_called_once()
        mock_labels.assert_called_once()
        mock_combine.assert_called_once()  # Even for single symbol
        mock_create_model.assert_called_once()
        mock_train.assert_called_once()
        mock_evaluate.assert_called_once()

        # Assert - Verify result structure
        assert "model_path" in result
        assert "training_metrics" in result
        assert "test_metrics" in result
        assert "data_summary" in result
        assert result["data_summary"]["symbols"] == ["AAPL"]

    @patch("ktrdr.training.training_pipeline.TrainingPipeline.load_market_data")
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.calculate_indicators")
    @patch(
        "ktrdr.training.training_pipeline.TrainingPipeline.generate_fuzzy_memberships"
    )
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.create_features")
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.create_labels")
    @patch(
        "ktrdr.training.training_pipeline.TrainingPipeline.combine_multi_symbol_data"
    )
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.create_model")
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.train_model")
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.evaluate_model")
    def test_progress_callback_passed_through_to_train_model(
        self,
        mock_evaluate,
        mock_train,
        mock_create_model,
        mock_combine,
        mock_labels,
        mock_features,
        mock_fuzzy,
        mock_indicators,
        mock_load_data,
    ):
        """Test that progress_callback is passed through to train_model()."""
        # Arrange
        mock_callback = MagicMock()
        mock_storage = MagicMock()

        # Setup minimal mocks
        mock_load_data.return_value = {"1d": pd.DataFrame()}
        mock_indicators.return_value = {"1d": pd.DataFrame()}
        mock_fuzzy.return_value = {"1d": pd.DataFrame()}
        mock_features.return_value = (torch.randn(100, 50), ["f1", "f2"])
        mock_labels.return_value = torch.randint(0, 3, (100,))
        mock_combine.return_value = (torch.randn(100, 50), torch.randint(0, 3, (100,)))
        mock_create_model.return_value = MagicMock()
        mock_train.return_value = {"final_train_loss": 0.5}
        mock_evaluate.return_value = {"test_loss": 0.6}
        mock_storage.save_model.return_value = "models/test.pth"

        # Act
        TrainingPipeline.train_strategy(
            symbols=["AAPL"],
            timeframes=["1d"],
            strategy_config={
                "name": "test",
                "indicators": [],
                "fuzzy_sets": {},
                "model": {"training": {}, "features": {}},
                "training": {
                    "labels": {},
                    "data_split": {"test_size": 0.1, "validation_size": 0.2},
                },
            },
            start_date="2024-01-01",
            end_date="2024-12-31",
            model_storage=mock_storage,
            progress_callback=mock_callback,  # ← Provide callback
        )

        # Assert - train_model() was called with the callback
        call_args = mock_train.call_args
        assert call_args.kwargs.get("progress_callback") == mock_callback

    @patch("ktrdr.training.training_pipeline.TrainingPipeline.load_market_data")
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.calculate_indicators")
    @patch(
        "ktrdr.training.training_pipeline.TrainingPipeline.generate_fuzzy_memberships"
    )
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.create_features")
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.create_labels")
    @patch(
        "ktrdr.training.training_pipeline.TrainingPipeline.combine_multi_symbol_data"
    )
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.create_model")
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.train_model")
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.evaluate_model")
    def test_cancellation_token_passed_through_to_train_model(
        self,
        mock_evaluate,
        mock_train,
        mock_create_model,
        mock_combine,
        mock_labels,
        mock_features,
        mock_fuzzy,
        mock_indicators,
        mock_load_data,
    ):
        """Test that cancellation_token is passed through to train_model()."""
        # Arrange
        mock_token = MagicMock()
        mock_token.is_cancelled.return_value = (
            False  # Not cancelled during preprocessing
        )
        mock_storage = MagicMock()

        # Setup minimal mocks
        mock_load_data.return_value = {"1d": pd.DataFrame()}
        mock_indicators.return_value = {"1d": pd.DataFrame()}
        mock_fuzzy.return_value = {"1d": pd.DataFrame()}
        mock_features.return_value = (torch.randn(100, 50), ["f1", "f2"])
        mock_labels.return_value = torch.randint(0, 3, (100,))
        mock_combine.return_value = (torch.randn(100, 50), torch.randint(0, 3, (100,)))
        mock_create_model.return_value = MagicMock()
        mock_train.return_value = {"final_train_loss": 0.5}
        mock_evaluate.return_value = {"test_loss": 0.6}
        mock_storage.save_model.return_value = "models/test.pth"

        # Act
        TrainingPipeline.train_strategy(
            symbols=["AAPL"],
            timeframes=["1d"],
            strategy_config={
                "name": "test",
                "indicators": [],
                "fuzzy_sets": {},
                "model": {"training": {}, "features": {}},
                "training": {
                    "labels": {},
                    "data_split": {"test_size": 0.1, "validation_size": 0.2},
                },
            },
            start_date="2024-01-01",
            end_date="2024-12-31",
            model_storage=mock_storage,
            cancellation_token=mock_token,  # ← Provide token
        )

        # Assert - train_model() was called with the token
        call_args = mock_train.call_args
        assert call_args.kwargs.get("cancellation_token") == mock_token

    @patch("ktrdr.training.training_pipeline.TrainingPipeline.load_market_data")
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.calculate_indicators")
    @patch(
        "ktrdr.training.training_pipeline.TrainingPipeline.generate_fuzzy_memberships"
    )
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.create_features")
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.create_labels")
    @patch(
        "ktrdr.training.training_pipeline.TrainingPipeline.combine_multi_symbol_data"
    )
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.create_model")
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.train_model")
    @patch("ktrdr.training.training_pipeline.TrainingPipeline.evaluate_model")
    def test_multi_symbol_training_flow(
        self,
        mock_evaluate,
        mock_train,
        mock_create_model,
        mock_combine,
        mock_labels,
        mock_features,
        mock_fuzzy,
        mock_indicators,
        mock_load_data,
    ):
        """Test train_strategy() handles multi-symbol training correctly."""
        # Arrange
        mock_storage = MagicMock()

        # Mock multi-symbol data loading (called once per symbol)
        mock_load_data.side_effect = [
            {"1d": pd.DataFrame()},  # AAPL
            {"1d": pd.DataFrame()},  # MSFT
            {"1d": pd.DataFrame()},  # GOOGL
        ]

        mock_indicators.side_effect = [
            {"1d": pd.DataFrame()},  # AAPL
            {"1d": pd.DataFrame()},  # MSFT
            {"1d": pd.DataFrame()},  # GOOGL
        ]

        mock_fuzzy.side_effect = [
            {"1d": pd.DataFrame()},  # AAPL
            {"1d": pd.DataFrame()},  # MSFT
            {"1d": pd.DataFrame()},  # GOOGL
        ]

        mock_features.side_effect = [
            (torch.randn(100, 50), ["f1", "f2"]),  # AAPL
            (torch.randn(120, 50), ["f1", "f2"]),  # MSFT
            (torch.randn(110, 50), ["f1", "f2"]),  # GOOGL
        ]

        mock_labels.side_effect = [
            torch.randint(0, 3, (100,)),  # AAPL
            torch.randint(0, 3, (120,)),  # MSFT
            torch.randint(0, 3, (110,)),  # GOOGL
        ]

        # combine_multi_symbol_data combines all symbols
        mock_combine.return_value = (
            torch.randn(330, 50),  # 100 + 120 + 110
            torch.randint(0, 3, (330,)),
        )

        mock_model = MagicMock()
        mock_create_model.return_value = mock_model

        mock_train.return_value = {"final_train_loss": 0.5}
        mock_evaluate.return_value = {"test_loss": 0.6}
        mock_storage.save_model.return_value = (
            "models/multi_symbol_strategy/AAPL_MSFT_GOOGL_1d_v1.pth"
        )

        strategy_config = {
            "name": "multi_symbol_strategy",
            "indicators": [],
            "fuzzy_sets": {},
            "model": {"training": {}, "features": {}},
            "training": {
                "labels": {},
                "data_split": {"test_size": 0.1, "validation_size": 0.2},
            },
        }

        # Act
        result = TrainingPipeline.train_strategy(
            symbols=["AAPL", "MSFT", "GOOGL"],
            timeframes=["1d"],
            strategy_config=strategy_config,
            start_date="2024-01-01",
            end_date="2024-12-31",
            model_storage=mock_storage,
        )

        # Assert - Each symbol's data was loaded/processed
        assert mock_load_data.call_count == 3
        assert mock_indicators.call_count == 3
        assert mock_fuzzy.call_count == 3
        assert mock_features.call_count == 3
        assert mock_labels.call_count == 3

        # Assert - Data was combined once
        mock_combine.assert_called_once()

        # Assert - Result includes all symbols
        assert result["data_summary"]["symbols"] == ["AAPL", "MSFT", "GOOGL"]
