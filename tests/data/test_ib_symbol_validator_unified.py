"""
Unit tests for Unified IB Symbol Validator

Tests comprehensive functionality including:
- Integration with IB connection pool
- IB pace manager integration
- Enhanced error handling and retries
- Connection reuse and proper cleanup
- Concurrent symbol validation
- Metrics tracking and monitoring
- Backward compatibility
- Head timestamp fetching
"""

import pytest
import asyncio
import time
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from pathlib import Path
from tempfile import TemporaryDirectory

from ktrdr.data.ib_symbol_validator_unified import (
    IbSymbolValidatorUnified,
    ContractInfo,
    validate_symbol_unified,
    get_contract_details_unified,
)
from ktrdr.data.ib_client_id_registry import ClientIdPurpose
from ktrdr.errors import DataError


class TestIbSymbolValidatorUnified:
    """Test the unified IB symbol validator."""

    @pytest.fixture
    def mock_connection_pool(self):
        """Mock connection pool."""
        pool_connection = Mock()
        pool_connection.client_id = 123
        pool_connection.ib = Mock()
        pool_connection.state = Mock()
        pool_connection.state.name = "CONNECTED"

        mock_pool = Mock()
        mock_pool.acquire_connection = AsyncMock()
        mock_pool.acquire_connection.return_value.__aenter__ = AsyncMock(
            return_value=pool_connection
        )
        mock_pool.acquire_connection.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        return mock_pool, pool_connection

    @pytest.fixture
    def mock_pace_manager(self):
        """Mock pace manager."""
        pace_manager = Mock()
        pace_manager.check_pace_limits_async = AsyncMock()
        pace_manager.handle_ib_error_async = AsyncMock(
            return_value=(False, 0.0)
        )  # No retry by default
        pace_manager.get_pace_statistics = Mock(
            return_value={"component_statistics": {}}
        )
        return pace_manager

    @pytest.fixture
    def mock_contract_details(self):
        """Mock IB contract details response."""
        contract = Mock()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.exchange = "NASDAQ"
        contract.primaryExchange = "NASDAQ"
        contract.currency = "USD"

        detail = Mock()
        detail.contract = contract
        detail.longName = "Apple Inc"
        detail.contractMonth = ""

        return [detail]

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary directory for cache testing."""
        with TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def validator(self, mock_pace_manager, temp_cache_dir):
        """Create a test validator with mocked dependencies."""
        cache_file = temp_cache_dir / "test_cache.json"

        with patch(
            "ktrdr.data.ib_symbol_validator_unified.get_pace_manager",
            return_value=mock_pace_manager,
        ):
            return IbSymbolValidatorUnified(
                component_name="test_validator", cache_file=str(cache_file)
            )

    def test_initialization(self, validator):
        """Test validator initialization."""
        assert validator.component_name == "test_validator"
        assert validator.metrics["total_validations"] == 0
        assert validator.metrics["successful_validations"] == 0
        assert validator.metrics["failed_validations"] == 0
        assert len(validator._cache) == 0
        assert len(validator._validated_symbols) == 0
        assert len(validator._failed_symbols) == 0

    def test_symbol_normalization(self, validator):
        """Test symbol normalization."""
        # Basic normalization
        assert validator._normalize_symbol("aapl") == "AAPL"
        assert validator._normalize_symbol(" MSFT ") == "MSFT"

        # Forex pair normalization
        assert validator._normalize_symbol("EUR/USD") == "EUR.USD"
        assert validator._normalize_symbol("GBP/JPY") == "GBP.JPY"

    def test_instrument_type_detection(self, validator):
        """Test automatic instrument type detection."""
        # Test forex detection
        assert validator._detect_instrument_type("EURUSD") == "forex"
        assert validator._detect_instrument_type("GBPJPY") == "forex"
        assert validator._detect_instrument_type("EUR.USD") == "forex"

        # Test stock detection
        assert validator._detect_instrument_type("AAPL") == "stock"
        assert validator._detect_instrument_type("MSFT") == "stock"
        assert validator._detect_instrument_type("GOOGL") == "stock"

    def test_forex_contract_creation(self, validator):
        """Test forex contract creation."""
        # Test dot notation
        contract = validator._create_forex_contract("EUR.USD")
        assert contract is not None
        assert contract.secType == "CASH"

        # Test 6-character format
        contract = validator._create_forex_contract("EURUSD")
        assert contract is not None
        assert contract.secType == "CASH"

        # Test invalid format
        contract = validator._create_forex_contract("INVALID")
        assert contract is None

    def test_stock_contract_creation(self, validator):
        """Test stock contract creation."""
        contract = validator._create_stock_contract("AAPL")
        assert contract is not None
        assert contract.secType == "STK"
        assert contract.symbol == "AAPL"
        assert contract.exchange == "SMART"
        assert contract.currency == "USD"

    def test_future_contract_creation(self, validator):
        """Test future contract creation."""
        contract = validator._create_future_contract("ES")
        assert contract is not None
        assert contract.secType == "FUT"
        assert contract.symbol == "ES"
        assert contract.exchange == "CME"

    @pytest.mark.asyncio
    async def test_contract_lookup_success(
        self, validator, mock_connection_pool, mock_contract_details
    ):
        """Test successful contract lookup."""
        mock_pool, pool_connection = mock_connection_pool

        # Mock IB API calls
        pool_connection.ib.reqContractDetailsAsync = AsyncMock(
            return_value=mock_contract_details
        )

        contract = validator._create_stock_contract("AAPL")

        with patch(
            "ktrdr.data.ib_symbol_validator_unified.acquire_ib_connection",
            return_value=mock_pool.acquire_connection.return_value,
        ):
            with patch(
                "ktrdr.data.ib_symbol_validator_unified.IBTradingHoursParser.create_from_contract_details",
                return_value=None,
            ):
                with patch(
                    "ktrdr.data.ib_symbol_validator_unified.TradingHoursManager.get_trading_hours",
                    return_value=None,
                ):
                    contract_info = await validator._lookup_contract_async(contract)

        # Verify contract info
        assert contract_info is not None
        assert contract_info.symbol == "AAPL"
        assert contract_info.asset_type == "STK"
        assert contract_info.exchange == "NASDAQ"
        assert contract_info.currency == "USD"
        assert contract_info.description == "Apple Inc"

        # Verify metrics
        assert validator.metrics["total_validations"] == 1
        assert validator.metrics["successful_validations"] == 1

    @pytest.mark.asyncio
    async def test_contract_lookup_empty_response(
        self, validator, mock_connection_pool
    ):
        """Test contract lookup with empty response."""
        mock_pool, pool_connection = mock_connection_pool

        # Mock empty response
        pool_connection.ib.reqContractDetailsAsync = AsyncMock(return_value=[])

        contract = validator._create_stock_contract("INVALID")

        with patch(
            "ktrdr.data.ib_symbol_validator_unified.acquire_ib_connection",
            return_value=mock_pool.acquire_connection.return_value,
        ):
            contract_info = await validator._lookup_contract_async(contract)

        # Should return None
        assert contract_info is None
        assert validator.metrics["failed_validations"] == 1

    @pytest.mark.asyncio
    async def test_contract_lookup_with_retries(
        self, validator, mock_connection_pool, mock_contract_details
    ):
        """Test contract lookup with retry logic."""
        mock_pool, pool_connection = mock_connection_pool

        # Mock IB API to fail then succeed
        call_count = 0

        async def failing_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                error = Exception("IB Error 162: pacing violation")
                error.errorCode = 162
                raise error
            else:
                return mock_contract_details

        pool_connection.ib.reqContractDetailsAsync = AsyncMock(
            side_effect=failing_request
        )

        # Mock pace manager to allow retry
        validator.pace_manager.handle_ib_error_async = AsyncMock(
            return_value=(True, 1.0)
        )

        contract = validator._create_stock_contract("AAPL")

        with patch(
            "ktrdr.data.ib_symbol_validator_unified.acquire_ib_connection",
            return_value=mock_pool.acquire_connection.return_value,
        ):
            with patch(
                "ktrdr.data.ib_symbol_validator_unified.IBTradingHoursParser.create_from_contract_details",
                return_value=None,
            ):
                with patch(
                    "ktrdr.data.ib_symbol_validator_unified.TradingHoursManager.get_trading_hours",
                    return_value=None,
                ):
                    contract_info = await validator._lookup_contract_async(
                        contract, max_retries=2
                    )

        # Should have retried and succeeded
        assert contract_info is not None
        assert call_count == 2
        assert validator.metrics["retries_performed"] == 1
        assert validator.metrics["pace_violations_handled"] == 1
        assert validator.metrics["successful_validations"] == 1

        # Verify pace manager was called
        validator.pace_manager.handle_ib_error_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, validator, mock_connection_pool):
        """Test behavior when max retries are exceeded."""
        mock_pool, pool_connection = mock_connection_pool

        # Mock IB API to always fail
        error = Exception("IB Error 162: pacing violation")
        error.errorCode = 162
        pool_connection.ib.reqContractDetailsAsync = AsyncMock(side_effect=error)

        # Mock pace manager to allow retry
        validator.pace_manager.handle_ib_error_async = AsyncMock(
            return_value=(True, 1.0)
        )

        contract = validator._create_stock_contract("AAPL")

        with patch(
            "ktrdr.data.ib_symbol_validator_unified.acquire_ib_connection",
            return_value=mock_pool.acquire_connection.return_value,
        ):
            contract_info = await validator._lookup_contract_async(
                contract, max_retries=2
            )

        # Should have failed after retries
        assert contract_info is None
        assert validator.metrics["retries_performed"] == 2
        assert validator.metrics["failed_validations"] == 1

    @pytest.mark.asyncio
    async def test_pace_manager_integration(
        self, validator, mock_connection_pool, mock_contract_details
    ):
        """Test integration with pace manager."""
        mock_pool, pool_connection = mock_connection_pool

        # Mock IB API calls
        pool_connection.ib.reqContractDetailsAsync = AsyncMock(
            return_value=mock_contract_details
        )

        contract = validator._create_stock_contract("AAPL")

        with patch(
            "ktrdr.data.ib_symbol_validator_unified.acquire_ib_connection",
            return_value=mock_pool.acquire_connection.return_value,
        ):
            with patch(
                "ktrdr.data.ib_symbol_validator_unified.IBTradingHoursParser.create_from_contract_details",
                return_value=None,
            ):
                with patch(
                    "ktrdr.data.ib_symbol_validator_unified.TradingHoursManager.get_trading_hours",
                    return_value=None,
                ):
                    await validator._lookup_contract_async(contract)

        # Verify pace manager was called
        validator.pace_manager.check_pace_limits_async.assert_called_once()
        call_args = validator.pace_manager.check_pace_limits_async.call_args[1]
        assert call_args["symbol"] == "AAPL"
        assert call_args["timeframe"] == "contract_lookup"
        assert call_args["component"] == "test_validator"
        assert call_args["operation"] == "contract_details"

    @pytest.mark.asyncio
    async def test_validate_symbol_async_success(
        self, validator, mock_connection_pool, mock_contract_details
    ):
        """Test successful async symbol validation."""
        mock_pool, pool_connection = mock_connection_pool

        # Mock IB API calls
        pool_connection.ib.reqContractDetailsAsync = AsyncMock(
            return_value=mock_contract_details
        )

        with patch(
            "ktrdr.data.ib_symbol_validator_unified.acquire_ib_connection",
            return_value=mock_pool.acquire_connection.return_value,
        ):
            with patch(
                "ktrdr.data.ib_symbol_validator_unified.IBTradingHoursParser.create_from_contract_details",
                return_value=None,
            ):
                with patch(
                    "ktrdr.data.ib_symbol_validator_unified.TradingHoursManager.get_trading_hours",
                    return_value=None,
                ):
                    is_valid = await validator.validate_symbol_async("AAPL")

        assert is_valid is True
        assert "AAPL" in validator._validated_symbols
        assert "AAPL" in validator._cache

    @pytest.mark.asyncio
    async def test_validate_symbol_async_cache_hit(self, validator):
        """Test async validation with cache hit."""
        # Pre-populate cache
        validator._validated_symbols.add("AAPL")
        contract_info = ContractInfo(
            symbol="AAPL",
            contract=Mock(),
            asset_type="STK",
            exchange="NASDAQ",
            currency="USD",
            description="Apple Inc",
            validated_at=time.time(),
        )
        validator._cache["AAPL"] = contract_info

        is_valid = await validator.validate_symbol_async("AAPL")

        assert is_valid is True
        assert validator.metrics["cache_hits"] == 1

    @pytest.mark.asyncio
    async def test_validate_symbol_async_failed_cache(self, validator):
        """Test async validation with failed symbol cache."""
        # Pre-populate failed symbols
        validator._failed_symbols.add("INVALID")

        is_valid = await validator.validate_symbol_async("INVALID")

        assert is_valid is False

    def test_validate_symbol_sync_cache_only(self, validator):
        """Test sync validation (cache only)."""
        # Pre-populate cache
        validator._validated_symbols.add("AAPL")
        contract_info = ContractInfo(
            symbol="AAPL",
            contract=Mock(),
            asset_type="STK",
            exchange="NASDAQ",
            currency="USD",
            description="Apple Inc",
            validated_at=time.time(),
        )
        validator._cache["AAPL"] = contract_info

        is_valid = validator.validate_symbol("AAPL")
        assert is_valid is True

        # Test unknown symbol
        is_valid = validator.validate_symbol("UNKNOWN")
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_get_contract_details_async_success(
        self, validator, mock_connection_pool, mock_contract_details
    ):
        """Test successful async contract details retrieval."""
        mock_pool, pool_connection = mock_connection_pool

        # Mock IB API calls
        pool_connection.ib.reqContractDetailsAsync = AsyncMock(
            return_value=mock_contract_details
        )

        with patch(
            "ktrdr.data.ib_symbol_validator_unified.acquire_ib_connection",
            return_value=mock_pool.acquire_connection.return_value,
        ):
            with patch(
                "ktrdr.data.ib_symbol_validator_unified.IBTradingHoursParser.create_from_contract_details",
                return_value=None,
            ):
                with patch(
                    "ktrdr.data.ib_symbol_validator_unified.TradingHoursManager.get_trading_hours",
                    return_value=None,
                ):
                    contract_info = await validator.get_contract_details_async("AAPL")

        assert contract_info is not None
        assert contract_info.symbol == "AAPL"
        assert "AAPL" in validator._validated_symbols
        assert "AAPL" in validator._cache

    def test_get_contract_details_sync_cache_only(self, validator):
        """Test sync contract details (cache only)."""
        # Pre-populate cache
        contract_info = ContractInfo(
            symbol="AAPL",
            contract=Mock(),
            asset_type="STK",
            exchange="NASDAQ",
            currency="USD",
            description="Apple Inc",
            validated_at=time.time(),
        )
        validator._cache["AAPL"] = contract_info

        result = validator.get_contract_details("AAPL")
        assert result is not None
        assert result.symbol == "AAPL"

        # Test unknown symbol
        result = validator.get_contract_details("UNKNOWN")
        assert result is None

    @pytest.mark.asyncio
    async def test_revalidation_logic(
        self, validator, mock_connection_pool, mock_contract_details
    ):
        """Test re-validation of previously validated symbols."""
        # Mark symbol as validated but with expired cache
        validator._validated_symbols.add("AAPL")
        old_contract_info = ContractInfo(
            symbol="AAPL",
            contract=Mock(),
            asset_type="STK",
            exchange="NASDAQ",
            currency="USD",
            description="Apple Inc",
            validated_at=time.time() - 86400 * 31,  # Expired
        )
        validator._cache["AAPL"] = old_contract_info

        mock_pool, pool_connection = mock_connection_pool
        pool_connection.ib.reqContractDetailsAsync = AsyncMock(
            return_value=mock_contract_details
        )

        with patch(
            "ktrdr.data.ib_symbol_validator_unified.acquire_ib_connection",
            return_value=mock_pool.acquire_connection.return_value,
        ):
            with patch(
                "ktrdr.data.ib_symbol_validator_unified.IBTradingHoursParser.create_from_contract_details",
                return_value=None,
            ):
                with patch(
                    "ktrdr.data.ib_symbol_validator_unified.TradingHoursManager.get_trading_hours",
                    return_value=None,
                ):
                    contract_info = await validator.get_contract_details_async("AAPL")

        # Should have re-validated
        assert contract_info is not None
        assert contract_info.validated_at > old_contract_info.validated_at

    @pytest.mark.asyncio
    async def test_head_timestamp_fetching(
        self, validator, mock_connection_pool, mock_contract_details
    ):
        """Test head timestamp fetching."""
        mock_pool, pool_connection = mock_connection_pool

        # Mock contract lookup
        pool_connection.ib.reqContractDetailsAsync = AsyncMock(
            return_value=mock_contract_details
        )

        # Mock head timestamp API
        head_timestamp = datetime(2020, 1, 1, tzinfo=timezone.utc)
        pool_connection.ib.reqHeadTimeStampAsync = AsyncMock(
            return_value=head_timestamp
        )

        with patch(
            "ktrdr.data.ib_symbol_validator_unified.acquire_ib_connection",
            return_value=mock_pool.acquire_connection.return_value,
        ):
            with patch(
                "ktrdr.data.ib_symbol_validator_unified.IBTradingHoursParser.create_from_contract_details",
                return_value=None,
            ):
                with patch(
                    "ktrdr.data.ib_symbol_validator_unified.TradingHoursManager.get_trading_hours",
                    return_value=None,
                ):
                    # First ensure symbol is validated
                    await validator.get_contract_details_async("AAPL")

                    # Then fetch head timestamp
                    timestamp_str = await validator.fetch_head_timestamp_async("AAPL")

        assert timestamp_str is not None
        assert "2020-01-01" in timestamp_str

        # Verify cache was updated
        contract_info = validator._cache["AAPL"]
        assert contract_info.head_timestamp is not None
        assert contract_info.head_timestamp_fetched_at is not None

    @pytest.mark.asyncio
    async def test_head_timestamp_cache_hit(self, validator):
        """Test head timestamp with cache hit."""
        # Pre-populate cache with head timestamp
        contract_info = ContractInfo(
            symbol="AAPL",
            contract=Mock(),
            asset_type="STK",
            exchange="NASDAQ",
            currency="USD",
            description="Apple Inc",
            validated_at=time.time(),
            head_timestamp="2020-01-01T00:00:00+00:00",
            head_timestamp_fetched_at=time.time(),
        )
        validator._cache["AAPL"] = contract_info

        timestamp_str = await validator.fetch_head_timestamp_async("AAPL")

        assert timestamp_str == "2020-01-01T00:00:00+00:00"

    def test_date_range_validation(self, validator):
        """Test date range validation against head timestamp."""
        # Pre-populate cache with head timestamp
        contract_info = ContractInfo(
            symbol="AAPL",
            contract=Mock(),
            asset_type="STK",
            exchange="NASDAQ",
            currency="USD",
            description="Apple Inc",
            validated_at=time.time(),
            head_timestamp="2020-01-01T00:00:00+00:00",
            head_timestamp_fetched_at=time.time(),
        )
        validator._cache["AAPL"] = contract_info

        # Test date before head timestamp
        start_date = datetime(2019, 12, 1, tzinfo=timezone.utc)
        is_valid, warning, suggested = (
            validator.validate_date_range_against_head_timestamp("AAPL", start_date)
        )

        assert is_valid is True
        assert warning is not None  # Should warn about adjustment
        assert suggested is not None
        assert suggested.year == 2020

        # Test date after head timestamp
        start_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
        is_valid, warning, suggested = (
            validator.validate_date_range_against_head_timestamp("AAPL", start_date)
        )

        assert is_valid is True
        assert warning is None  # No warning needed
        assert suggested is None

    @pytest.mark.asyncio
    async def test_batch_validate_async(
        self, validator, mock_connection_pool, mock_contract_details
    ):
        """Test batch async validation."""
        mock_pool, pool_connection = mock_connection_pool

        # Mock IB API calls
        pool_connection.ib.reqContractDetailsAsync = AsyncMock(
            return_value=mock_contract_details
        )

        symbols = ["AAPL", "MSFT", "GOOGL"]

        with patch(
            "ktrdr.data.ib_symbol_validator_unified.acquire_ib_connection",
            return_value=mock_pool.acquire_connection.return_value,
        ):
            with patch(
                "ktrdr.data.ib_symbol_validator_unified.IBTradingHoursParser.create_from_contract_details",
                return_value=None,
            ):
                with patch(
                    "ktrdr.data.ib_symbol_validator_unified.TradingHoursManager.get_trading_hours",
                    return_value=None,
                ):
                    results = await validator.batch_validate_async(
                        symbols, max_concurrent=2
                    )

        # Should have results for all symbols
        assert len(results) == 3
        assert all(results[symbol] for symbol in symbols)

    def test_batch_validate_sync(self, validator):
        """Test batch sync validation (cache only)."""
        # Pre-populate cache
        for symbol in ["AAPL", "MSFT"]:
            validator._validated_symbols.add(symbol)
            contract_info = ContractInfo(
                symbol=symbol,
                contract=Mock(),
                asset_type="STK",
                exchange="NASDAQ",
                currency="USD",
                description=f"{symbol} Inc",
                validated_at=time.time(),
            )
            validator._cache[symbol] = contract_info

        symbols = ["AAPL", "MSFT", "UNKNOWN"]
        results = validator.batch_validate(symbols)

        assert results["AAPL"] is True
        assert results["MSFT"] is True
        assert results["UNKNOWN"] is False

    @pytest.mark.asyncio
    async def test_batch_get_contracts_async(
        self, validator, mock_connection_pool, mock_contract_details
    ):
        """Test batch async contract retrieval."""
        mock_pool, pool_connection = mock_connection_pool

        # Mock IB API calls
        pool_connection.ib.reqContractDetailsAsync = AsyncMock(
            return_value=mock_contract_details
        )

        symbols = ["AAPL", "MSFT"]

        with patch(
            "ktrdr.data.ib_symbol_validator_unified.acquire_ib_connection",
            return_value=mock_pool.acquire_connection.return_value,
        ):
            with patch(
                "ktrdr.data.ib_symbol_validator_unified.IBTradingHoursParser.create_from_contract_details",
                return_value=None,
            ):
                with patch(
                    "ktrdr.data.ib_symbol_validator_unified.TradingHoursManager.get_trading_hours",
                    return_value=None,
                ):
                    results = await validator.batch_get_contracts_async(
                        symbols, max_concurrent=2
                    )

        # Should have results for all symbols
        assert len(results) == 2
        assert all(results[symbol] is not None for symbol in symbols)

    def test_metrics_calculation(self, validator):
        """Test metrics calculation including success rate."""
        # Simulate some validations
        validator.metrics["total_validations"] = 10
        validator.metrics["successful_validations"] = 8
        validator.metrics["failed_validations"] = 2
        validator.metrics["cache_hits"] = 5

        metrics = validator.get_metrics()

        assert metrics["success_rate"] == 0.8
        assert metrics["total_validations"] == 10
        assert metrics["successful_validations"] == 8
        assert metrics["component_name"] == "test_validator"

    def test_metrics_reset(self, validator):
        """Test metrics reset functionality."""
        # Set some metrics
        validator.metrics["total_validations"] = 5
        validator.metrics["successful_validations"] = 3

        # Reset
        validator.reset_metrics()

        # Should be back to zero
        assert validator.metrics["total_validations"] == 0
        assert validator.metrics["successful_validations"] == 0
        assert validator.metrics["failed_validations"] == 0

    def test_cache_persistence(self, temp_cache_dir, mock_pace_manager):
        """Test cache persistence to file."""
        cache_file = temp_cache_dir / "test_cache.json"

        with patch(
            "ktrdr.data.ib_symbol_validator_unified.get_pace_manager",
            return_value=mock_pace_manager,
        ):
            # Create validator and add some data
            validator1 = IbSymbolValidatorUnified(
                component_name="test_validator", cache_file=str(cache_file)
            )

            validator1._validated_symbols.add("AAPL")
            validator1._failed_symbols.add("INVALID")

            contract_info = ContractInfo(
                symbol="AAPL",
                contract=Mock(),
                asset_type="STK",
                exchange="NASDAQ",
                currency="USD",
                description="Apple Inc",
                validated_at=time.time(),
            )
            validator1._cache["AAPL"] = contract_info
            validator1._save_cache_to_file()

            # Create new validator and verify data was loaded
            validator2 = IbSymbolValidatorUnified(
                component_name="test_validator2", cache_file=str(cache_file)
            )

            assert "AAPL" in validator2._validated_symbols
            assert "INVALID" in validator2._failed_symbols
            assert "AAPL" in validator2._cache
            assert validator2._cache["AAPL"].description == "Apple Inc"

    def test_cache_stats(self, validator):
        """Test cache statistics."""
        # Add some test data
        validator._validated_symbols.add("AAPL")
        validator._failed_symbols.add("INVALID")

        contract_info = ContractInfo(
            symbol="AAPL",
            contract=Mock(),
            asset_type="STK",
            exchange="NASDAQ",
            currency="USD",
            description="Apple Inc",
            validated_at=time.time(),
        )
        validator._cache["AAPL"] = contract_info

        stats = validator.get_cache_stats()

        assert stats["cached_symbols"] == 1
        assert stats["validated_symbols"] == 1
        assert stats["failed_symbols"] == 1
        assert stats["total_lookups"] == 2

    def test_clear_cache(self, validator, temp_cache_dir):
        """Test cache clearing."""
        # Add some test data
        validator._validated_symbols.add("AAPL")
        validator._failed_symbols.add("INVALID")

        contract_info = ContractInfo(
            symbol="AAPL",
            contract=Mock(),
            asset_type="STK",
            exchange="NASDAQ",
            currency="USD",
            description="Apple Inc",
            validated_at=time.time(),
        )
        validator._cache["AAPL"] = contract_info
        validator._save_cache_to_file()

        # Clear cache
        validator.clear_cache()

        # Verify cleared
        assert len(validator._cache) == 0
        assert len(validator._validated_symbols) == 0
        assert len(validator._failed_symbols) == 0

    def test_forex_symbol_detection(self, validator):
        """Test forex symbol detection."""
        # Pre-populate cache
        forex_contract_info = ContractInfo(
            symbol="EURUSD",
            contract=Mock(),
            asset_type="CASH",
            exchange="IDEALPRO",
            currency="USD",
            description="EUR/USD",
            validated_at=time.time(),
        )
        validator._cache["EURUSD"] = forex_contract_info

        stock_contract_info = ContractInfo(
            symbol="AAPL",
            contract=Mock(),
            asset_type="STK",
            exchange="NASDAQ",
            currency="USD",
            description="Apple Inc",
            validated_at=time.time(),
        )
        validator._cache["AAPL"] = stock_contract_info

        # Test cached symbols
        assert validator.is_forex_symbol("EURUSD") is True
        assert validator.is_forex_symbol("AAPL") is False

        # Test heuristics for non-cached symbols
        assert validator.is_forex_symbol("GBPJPY") is True
        assert validator.is_forex_symbol("EUR.USD") is True
        assert validator.is_forex_symbol("MSFT") is False


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_validate_symbol_unified(self, mock_contract_details):
        """Test convenience function for symbol validation."""
        with patch(
            "ktrdr.data.ib_symbol_validator_unified.IbSymbolValidatorUnified"
        ) as mock_validator_class:
            mock_validator = Mock()
            mock_validator.validate_symbol_async = AsyncMock(return_value=True)
            mock_validator_class.return_value = mock_validator

            is_valid = await validate_symbol_unified("AAPL")

            assert is_valid is True
            mock_validator.validate_symbol_async.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_get_contract_details_unified(self, mock_contract_details):
        """Test convenience function for contract details."""
        with patch(
            "ktrdr.data.ib_symbol_validator_unified.IbSymbolValidatorUnified"
        ) as mock_validator_class:
            mock_validator = Mock()
            mock_contract_info = ContractInfo(
                symbol="AAPL",
                contract=Mock(),
                asset_type="STK",
                exchange="NASDAQ",
                currency="USD",
                description="Apple Inc",
                validated_at=time.time(),
            )
            mock_validator.get_contract_details_async = AsyncMock(
                return_value=mock_contract_info
            )
            mock_validator_class.return_value = mock_validator

            contract_info = await get_contract_details_unified("AAPL")

            assert contract_info is not None
            assert contract_info.symbol == "AAPL"
            mock_validator.get_contract_details_async.assert_called_once_with("AAPL")


class TestBackwardCompatibility:
    """Test backward compatibility features."""

    def test_backward_compatibility_alias(self):
        """Test that IbSymbolValidator is aliased to unified version."""
        from ktrdr.data.ib_symbol_validator_unified import IbSymbolValidator

        # Should be the same class
        assert IbSymbolValidator == IbSymbolValidatorUnified

    def test_contract_info_dataclass(self):
        """Test ContractInfo dataclass functionality."""
        contract_info = ContractInfo(
            symbol="AAPL",
            contract=Mock(),
            asset_type="STK",
            exchange="NASDAQ",
            currency="USD",
            description="Apple Inc",
            validated_at=time.time(),
        )

        # Test basic attributes
        assert contract_info.symbol == "AAPL"
        assert contract_info.asset_type == "STK"
        assert contract_info.exchange == "NASDAQ"

        # Test optional attributes
        assert contract_info.trading_hours is None
        assert contract_info.head_timestamp is None
        assert contract_info.head_timestamp_timeframes is None
        assert contract_info.head_timestamp_fetched_at is None


class TestConcurrencyAndStress:
    """Test concurrency and stress scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_validation_operations(
        self,
        mock_connection_pool,
        mock_contract_details,
        mock_pace_manager,
        temp_cache_dir,
    ):
        """Test concurrent validation operations."""
        cache_file = temp_cache_dir / "concurrent_test_cache.json"

        with patch(
            "ktrdr.data.ib_symbol_validator_unified.get_pace_manager",
            return_value=mock_pace_manager,
        ):
            validator = IbSymbolValidatorUnified(
                component_name="concurrent_test", cache_file=str(cache_file)
            )

        mock_pool, pool_connection = mock_connection_pool
        pool_connection.ib.reqContractDetailsAsync = AsyncMock(
            return_value=mock_contract_details
        )

        async def validate_worker(symbol_id):
            with patch(
                "ktrdr.data.ib_symbol_validator_unified.acquire_ib_connection",
                return_value=mock_pool.acquire_connection.return_value,
            ):
                with patch(
                    "ktrdr.data.ib_symbol_validator_unified.IBTradingHoursParser.create_from_contract_details",
                    return_value=None,
                ):
                    with patch(
                        "ktrdr.data.ib_symbol_validator_unified.TradingHoursManager.get_trading_hours",
                        return_value=None,
                    ):
                        return await validator.validate_symbol_async(
                            f"STOCK{symbol_id}"
                        )

        # Run concurrent validations
        tasks = [validate_worker(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 10
        assert all(results)

        # Verify all symbols were validated
        assert len(validator._validated_symbols) == 10

    @pytest.mark.asyncio
    async def test_large_batch_operations(
        self,
        mock_connection_pool,
        mock_contract_details,
        mock_pace_manager,
        temp_cache_dir,
    ):
        """Test large batch operations."""
        cache_file = temp_cache_dir / "batch_test_cache.json"

        with patch(
            "ktrdr.data.ib_symbol_validator_unified.get_pace_manager",
            return_value=mock_pace_manager,
        ):
            validator = IbSymbolValidatorUnified(
                component_name="batch_test", cache_file=str(cache_file)
            )

        mock_pool, pool_connection = mock_connection_pool
        pool_connection.ib.reqContractDetailsAsync = AsyncMock(
            return_value=mock_contract_details
        )

        # Create large batch of symbols
        symbols = [f"STOCK{i}" for i in range(50)]

        with patch(
            "ktrdr.data.ib_symbol_validator_unified.acquire_ib_connection",
            return_value=mock_pool.acquire_connection.return_value,
        ):
            with patch(
                "ktrdr.data.ib_symbol_validator_unified.IBTradingHoursParser.create_from_contract_details",
                return_value=None,
            ):
                with patch(
                    "ktrdr.data.ib_symbol_validator_unified.TradingHoursManager.get_trading_hours",
                    return_value=None,
                ):
                    results = await validator.batch_validate_async(
                        symbols, max_concurrent=5
                    )

        # All should succeed
        assert len(results) == 50
        assert all(results.values())


if __name__ == "__main__":
    pytest.main([__file__])
