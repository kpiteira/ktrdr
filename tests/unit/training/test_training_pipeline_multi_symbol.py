"""
Unit tests for TrainingPipeline multi-symbol methods.

Tests the symbol-agnostic multi-symbol training design where strategies
operate on patterns (technical indicators + fuzzy memberships) rather than
symbol names.
"""

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
