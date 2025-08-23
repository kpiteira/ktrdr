"""
Tests for fuzzy overlay API models.
"""

import pytest
from pydantic import ValidationError

from ktrdr.api.models.fuzzy import (
    FuzzyMembershipPoint,
    FuzzyOverlayResponse,
    FuzzySetMembership,
)


class TestFuzzyMembershipPoint:
    """Test cases for FuzzyMembershipPoint model."""

    def test_valid_membership_point(self):
        """Test creating a valid membership point."""
        point = FuzzyMembershipPoint(timestamp="2023-01-01T09:00:00", value=0.75)

        assert point.timestamp == "2023-01-01T09:00:00"
        assert point.value == 0.75

    def test_membership_point_with_none_value(self):
        """Test membership point with None value (missing data)."""
        point = FuzzyMembershipPoint(timestamp="2023-01-01T09:00:00", value=None)

        assert point.timestamp == "2023-01-01T09:00:00"
        assert point.value is None

    def test_membership_point_boundary_values(self):
        """Test membership point with boundary values."""
        # Test 0.0
        point_zero = FuzzyMembershipPoint(timestamp="2023-01-01T09:00:00", value=0.0)
        assert point_zero.value == 0.0

        # Test 1.0
        point_one = FuzzyMembershipPoint(timestamp="2023-01-01T09:00:00", value=1.0)
        assert point_one.value == 1.0

    def test_invalid_membership_value_too_low(self):
        """Test validation failure for membership value < 0."""
        with pytest.raises(ValidationError) as exc_info:
            FuzzyMembershipPoint(timestamp="2023-01-01T09:00:00", value=-0.1)

        assert "Membership value must be between 0.0 and 1.0" in str(exc_info.value)

    def test_invalid_membership_value_too_high(self):
        """Test validation failure for membership value > 1."""
        with pytest.raises(ValidationError) as exc_info:
            FuzzyMembershipPoint(timestamp="2023-01-01T09:00:00", value=1.1)

        assert "Membership value must be between 0.0 and 1.0" in str(exc_info.value)

    def test_missing_required_fields(self):
        """Test validation failure for missing required fields."""
        with pytest.raises(ValidationError):
            FuzzyMembershipPoint()


class TestFuzzySetMembership:
    """Test cases for FuzzySetMembership model."""

    def test_valid_fuzzy_set_membership(self):
        """Test creating a valid fuzzy set membership."""
        membership_points = [
            FuzzyMembershipPoint(timestamp="2023-01-01T09:00:00", value=0.8),
            FuzzyMembershipPoint(timestamp="2023-01-01T10:00:00", value=0.6),
            FuzzyMembershipPoint(timestamp="2023-01-01T11:00:00", value=0.4),
        ]

        fuzzy_set = FuzzySetMembership(set="low", membership=membership_points)

        assert fuzzy_set.set == "low"
        assert len(fuzzy_set.membership) == 3
        assert fuzzy_set.membership[0].value == 0.8

    def test_empty_membership_list(self):
        """Test fuzzy set with empty membership list."""
        fuzzy_set = FuzzySetMembership(set="neutral", membership=[])

        assert fuzzy_set.set == "neutral"
        assert len(fuzzy_set.membership) == 0

    def test_set_name_whitespace_trimming(self):
        """Test that set names are trimmed of whitespace."""
        fuzzy_set = FuzzySetMembership(set="  high  ", membership=[])

        assert fuzzy_set.set == "high"

    def test_empty_set_name(self):
        """Test validation failure for empty set name."""
        with pytest.raises(ValidationError) as exc_info:
            FuzzySetMembership(set="", membership=[])

        assert "Fuzzy set name cannot be empty" in str(exc_info.value)

    def test_whitespace_only_set_name(self):
        """Test validation failure for whitespace-only set name."""
        with pytest.raises(ValidationError) as exc_info:
            FuzzySetMembership(set="   ", membership=[])

        assert "Fuzzy set name cannot be empty" in str(exc_info.value)


class TestFuzzyOverlayResponse:
    """Test cases for FuzzyOverlayResponse model."""

    def test_valid_fuzzy_overlay_response(self):
        """Test creating a valid fuzzy overlay response."""
        # Create sample data
        rsi_low = FuzzySetMembership(
            set="low",
            membership=[
                FuzzyMembershipPoint(timestamp="2023-01-01T09:00:00", value=0.8),
                FuzzyMembershipPoint(timestamp="2023-01-01T10:00:00", value=0.6),
            ],
        )
        rsi_high = FuzzySetMembership(
            set="high",
            membership=[
                FuzzyMembershipPoint(timestamp="2023-01-01T09:00:00", value=0.2),
                FuzzyMembershipPoint(timestamp="2023-01-01T10:00:00", value=0.4),
            ],
        )

        response = FuzzyOverlayResponse(
            symbol="AAPL", timeframe="1h", data={"rsi": [rsi_low, rsi_high]}
        )

        assert response.symbol == "AAPL"
        assert response.timeframe == "1h"
        assert "rsi" in response.data
        assert len(response.data["rsi"]) == 2
        assert response.warnings is None

    def test_fuzzy_overlay_response_with_warnings(self):
        """Test fuzzy overlay response with warnings."""
        response = FuzzyOverlayResponse(
            symbol="AAPL",
            timeframe="1h",
            data={},
            warnings=["Unknown indicator 'invalid_indicator' - skipping"],
        )

        assert response.symbol == "AAPL"
        assert response.timeframe == "1h"
        assert response.data == {}
        assert len(response.warnings) == 1
        assert "invalid_indicator" in response.warnings[0]

    def test_symbol_case_normalization(self):
        """Test that symbols are normalized to uppercase."""
        response = FuzzyOverlayResponse(symbol="aapl", timeframe="1h", data={})

        assert response.symbol == "AAPL"

    def test_symbol_whitespace_trimming(self):
        """Test that symbols are trimmed of whitespace."""
        response = FuzzyOverlayResponse(symbol="  AAPL  ", timeframe="1h", data={})

        assert response.symbol == "AAPL"

    def test_timeframe_whitespace_trimming(self):
        """Test that timeframes are trimmed of whitespace."""
        response = FuzzyOverlayResponse(symbol="AAPL", timeframe="  1h  ", data={})

        assert response.timeframe == "1h"

    def test_empty_symbol_validation(self):
        """Test validation failure for empty symbol."""
        with pytest.raises(ValidationError) as exc_info:
            FuzzyOverlayResponse(symbol="", timeframe="1h", data={})

        assert "Symbol cannot be empty" in str(exc_info.value)

    def test_empty_timeframe_validation(self):
        """Test validation failure for empty timeframe."""
        with pytest.raises(ValidationError) as exc_info:
            FuzzyOverlayResponse(symbol="AAPL", timeframe="", data={})

        assert "Timeframe cannot be empty" in str(exc_info.value)

    def test_empty_data_is_valid(self):
        """Test that empty data is allowed."""
        response = FuzzyOverlayResponse(symbol="AAPL", timeframe="1h", data={})

        assert response.data == {}

    def test_indicator_with_empty_fuzzy_sets(self):
        """Test validation failure for indicator with empty fuzzy sets."""
        with pytest.raises(ValidationError) as exc_info:
            FuzzyOverlayResponse(
                symbol="AAPL",
                timeframe="1h",
                data={"rsi": []},  # Empty list of fuzzy sets
            )

        assert "must have at least one fuzzy set" in str(exc_info.value)

    def test_duplicate_fuzzy_set_names(self):
        """Test validation failure for duplicate fuzzy set names."""
        rsi_low1 = FuzzySetMembership(set="low", membership=[])
        rsi_low2 = FuzzySetMembership(set="low", membership=[])  # Duplicate name

        with pytest.raises(ValidationError) as exc_info:
            FuzzyOverlayResponse(
                symbol="AAPL", timeframe="1h", data={"rsi": [rsi_low1, rsi_low2]}
            )

        assert "Fuzzy set names must be unique" in str(exc_info.value)

    def test_multiple_indicators(self):
        """Test response with multiple indicators."""
        rsi_fuzzy_set = FuzzySetMembership(set="low", membership=[])
        macd_fuzzy_set = FuzzySetMembership(set="negative", membership=[])

        response = FuzzyOverlayResponse(
            symbol="AAPL",
            timeframe="1h",
            data={"rsi": [rsi_fuzzy_set], "macd": [macd_fuzzy_set]},
        )

        assert "rsi" in response.data
        assert "macd" in response.data
        assert len(response.data) == 2

    def test_json_serialization(self):
        """Test that the model can be serialized to JSON."""
        membership_point = FuzzyMembershipPoint(
            timestamp="2023-01-01T09:00:00", value=0.75
        )
        fuzzy_set = FuzzySetMembership(set="low", membership=[membership_point])
        response = FuzzyOverlayResponse(
            symbol="AAPL", timeframe="1h", data={"rsi": [fuzzy_set]}
        )

        # Test serialization
        json_data = response.model_dump()

        assert json_data["symbol"] == "AAPL"
        assert json_data["timeframe"] == "1h"
        assert "rsi" in json_data["data"]
        assert json_data["data"]["rsi"][0]["set"] == "low"
        assert json_data["data"]["rsi"][0]["membership"][0]["value"] == 0.75

    def test_json_deserialization(self):
        """Test that the model can be created from JSON."""
        json_data = {
            "symbol": "AAPL",
            "timeframe": "1h",
            "data": {
                "rsi": [
                    {
                        "set": "low",
                        "membership": [
                            {"timestamp": "2023-01-01T09:00:00", "value": 0.75}
                        ],
                    }
                ]
            },
        }

        response = FuzzyOverlayResponse(**json_data)

        assert response.symbol == "AAPL"
        assert response.timeframe == "1h"
        assert "rsi" in response.data
        assert response.data["rsi"][0].set == "low"
        assert response.data["rsi"][0].membership[0].value == 0.75
