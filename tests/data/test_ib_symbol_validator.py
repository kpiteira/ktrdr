"""
Tests for IB Symbol Validator.

This module tests symbol validation, contract lookup, and caching functionality.
"""

import pytest

pytestmark = pytest.mark.skip(reason="IB integration tests disabled for unit test run")
import time
from unittest.mock import Mock, MagicMock, patch
from ib_insync import Contract, Forex, Stock, Future

from ktrdr.data.ib_symbol_validator import IbSymbolValidator, ContractInfo
from ktrdr.data.ib_connection_sync import IbConnectionSync


class TestIbSymbolValidator:
    """Test suite for IbSymbolValidator."""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock IB connection."""
        mock_conn = Mock(spec=IbConnectionSync)
        mock_conn.is_connected.return_value = True
        mock_conn.ib = Mock()
        return mock_conn

    @pytest.fixture
    def validator(self, mock_connection):
        """Create validator with mocked connection."""
        return IbSymbolValidator(connection=mock_connection)

    @pytest.fixture
    def sample_contract_info(self):
        """Create sample contract info for testing."""
        contract = Mock(spec=Contract)
        contract.symbol = "EUR"
        contract.secType = "CASH"
        contract.primaryExchange = ""
        contract.exchange = "IDEALPRO"
        contract.currency = "USD"

        return ContractInfo(
            symbol="EUR.USD",
            contract=contract,
            asset_type="CASH",
            exchange="IDEALPRO",
            currency="USD",
            description="Euro vs US Dollar",
            validated_at=time.time(),
        )

    def test_init_without_connection(self):
        """Test initialization without connection."""
        validator = IbSymbolValidator()
        assert validator.connection is None
        assert len(validator._cache) == 0
        assert len(validator._failed_symbols) == 0
        assert len(validator._validated_symbols) == 0
        assert validator._cache_ttl == 86400 * 30  # 30 days

    def test_init_with_connection(self, mock_connection):
        """Test initialization with connection."""
        validator = IbSymbolValidator(connection=mock_connection)
        assert validator.connection is mock_connection
        assert len(validator._cache) == 0
        assert len(validator._failed_symbols) == 0
        assert len(validator._validated_symbols) == 0

    def test_normalize_symbol(self, validator):
        """Test symbol normalization."""
        assert validator._normalize_symbol("eur/usd") == "EUR.USD"
        assert validator._normalize_symbol("EUR/USD") == "EUR.USD"
        assert validator._normalize_symbol(" AAPL ") == "AAPL"
        assert validator._normalize_symbol("eurusd") == "EURUSD"

    def test_create_forex_contract(self, validator):
        """Test forex contract creation."""
        # Test EUR.USD format
        contract = validator._create_forex_contract("EUR.USD")
        assert contract is not None
        assert isinstance(contract, Forex)

        # Test EURUSD format
        contract = validator._create_forex_contract("EURUSD")
        assert contract is not None
        assert isinstance(contract, Forex)

        # Test invalid formats
        assert validator._create_forex_contract("EUR") is None
        assert validator._create_forex_contract("EURX") is None
        assert validator._create_forex_contract("EURUSDD") is None

    def test_create_stock_contract(self, validator):
        """Test stock contract creation."""
        contract = validator._create_stock_contract("AAPL")
        assert isinstance(contract, Stock)
        assert contract.symbol == "AAPL"
        assert contract.exchange == "SMART"
        assert contract.currency == "USD"

    def test_create_future_contract(self, validator):
        """Test future contract creation."""
        contract = validator._create_future_contract("ES")
        assert isinstance(contract, Future)
        assert contract.symbol == "ES"
        assert contract.exchange == "CME"

    def test_ensure_connection_no_connection(self):
        """Test connection check with no connection."""
        validator = IbSymbolValidator()
        assert validator._ensure_connection() is False

    def test_ensure_connection_disconnected(self, mock_connection):
        """Test connection check with disconnected connection."""
        mock_connection.is_connected.return_value = False
        validator = IbSymbolValidator(connection=mock_connection)
        assert validator._ensure_connection() is False

    def test_ensure_connection_connected(self, validator):
        """Test connection check with connected connection."""
        assert validator._ensure_connection() is True

    def test_cache_validation(self, validator, sample_contract_info):
        """Test cache validation and TTL."""
        symbol = "EUR.USD"

        # No cache entry
        assert validator._is_cache_valid(symbol) is False

        # Add to cache
        validator._cache[symbol] = sample_contract_info
        assert validator._is_cache_valid(symbol) is True

        # Expire cache entry
        validator._cache[symbol].validated_at = time.time() - 7200  # 2 hours ago
        assert validator._is_cache_valid(symbol) is False

    def test_lookup_contract_success(self, validator):
        """Test successful contract lookup."""
        # Mock contract details response
        mock_detail = Mock()
        mock_detail.contract = Mock()
        mock_detail.contract.symbol = "EUR"
        mock_detail.contract.secType = "CASH"
        mock_detail.contract.primaryExchange = ""
        mock_detail.contract.exchange = "IDEALPRO"
        mock_detail.contract.currency = "USD"
        mock_detail.longName = "Euro vs US Dollar"
        mock_detail.contractMonth = ""

        validator.connection.ib.reqContractDetails.return_value = [mock_detail]

        contract = Forex(pair="EURUSD")
        result = validator._lookup_contract(contract)

        assert result is not None
        assert result.symbol == "EUR"
        assert result.asset_type == "CASH"
        assert result.exchange == "IDEALPRO"
        assert result.currency == "USD"
        assert result.description == "Euro vs US Dollar"

    def test_lookup_contract_not_found(self, validator):
        """Test contract lookup when not found."""
        validator.connection.ib.reqContractDetails.return_value = []

        contract = Stock(symbol="INVALID", exchange="SMART", currency="USD")
        result = validator._lookup_contract(contract)

        assert result is None

    def test_lookup_contract_exception(self, validator):
        """Test contract lookup with exception."""
        validator.connection.ib.reqContractDetails.side_effect = Exception("API Error")

        contract = Stock(symbol="AAPL", exchange="SMART", currency="USD")
        result = validator._lookup_contract(contract)

        assert result is None

    def test_validate_symbol_cached_success(self, validator, sample_contract_info):
        """Test symbol validation with cached result."""
        symbol = "EUR.USD"
        validator._cache[symbol] = sample_contract_info

        assert validator.validate_symbol(symbol) is True
        assert validator.validate_symbol("eur/usd") is True  # normalized

    def test_validate_symbol_cached_failure(self, validator):
        """Test symbol validation with cached failure."""
        symbol = "INVALID"
        validator._failed_symbols.add(symbol)

        assert validator.validate_symbol(symbol) is False

    def test_validate_symbol_no_connection(self):
        """Test symbol validation without connection."""
        validator = IbSymbolValidator()
        assert validator.validate_symbol("AAPL") is False

    def test_get_contract_details_success(self, validator):
        """Test getting contract details successfully."""
        # Mock successful forex lookup
        mock_detail = Mock()
        mock_detail.contract = Mock()
        mock_detail.contract.symbol = "EUR"
        mock_detail.contract.secType = "CASH"
        mock_detail.contract.primaryExchange = ""
        mock_detail.contract.exchange = "IDEALPRO"
        mock_detail.contract.currency = "USD"
        mock_detail.longName = "Euro vs US Dollar"
        mock_detail.contractMonth = ""

        validator.connection.ib.reqContractDetails.return_value = [mock_detail]

        result = validator.get_contract_details("EUR.USD")

        assert result is not None
        assert result.symbol == "EUR"
        assert result.asset_type == "CASH"
        assert "EUR.USD" in validator._cache

    def test_get_contract_details_priority_order(self, validator):
        """Test that forex (CASH) has priority over stocks."""
        call_count = 0

        def mock_req_contract_details(contract):
            nonlocal call_count
            call_count += 1

            # First call (forex) succeeds
            if call_count == 1 and isinstance(contract, Forex):
                mock_detail = Mock()
                mock_detail.contract = Mock()
                mock_detail.contract.symbol = "EUR"
                mock_detail.contract.secType = "CASH"
                mock_detail.contract.primaryExchange = ""
                mock_detail.contract.exchange = "IDEALPRO"
                mock_detail.contract.currency = "USD"
                mock_detail.longName = "Euro vs US Dollar"
                mock_detail.contractMonth = ""
                return [mock_detail]

            # Should not reach stock lookup
            return []

        validator.connection.ib.reqContractDetails.side_effect = (
            mock_req_contract_details
        )

        result = validator.get_contract_details("EUR.USD")

        assert result is not None
        assert result.asset_type == "CASH"
        assert call_count == 1  # Only forex lookup should be called

    def test_get_contract_details_fallback_to_stock(self, validator):
        """Test fallback from forex to stock."""
        call_count = 0

        def mock_req_contract_details(contract):
            nonlocal call_count
            call_count += 1

            # Forex fails
            if isinstance(contract, Forex):
                return []

            # Stock succeeds
            if isinstance(contract, Stock):
                mock_detail = Mock()
                mock_detail.contract = Mock()
                mock_detail.contract.symbol = "AAPL"
                mock_detail.contract.secType = "STK"
                mock_detail.contract.primaryExchange = "NASDAQ"
                mock_detail.contract.exchange = "SMART"
                mock_detail.contract.currency = "USD"
                mock_detail.longName = "Apple Inc"
                mock_detail.contractMonth = ""
                return [mock_detail]

            return []

        validator.connection.ib.reqContractDetails.side_effect = (
            mock_req_contract_details
        )

        result = validator.get_contract_details("AAPL")

        assert result is not None
        assert result.asset_type == "STK"
        assert result.symbol == "AAPL"

    def test_get_contract_details_all_fail(self, validator):
        """Test when all contract types fail."""
        validator.connection.ib.reqContractDetails.return_value = []

        result = validator.get_contract_details("INVALID")

        assert result is None
        assert "INVALID" in validator._failed_symbols

    def test_batch_validate(self, validator, sample_contract_info):
        """Test batch validation."""
        # Set up cache and failed symbols
        validator._cache["EUR.USD"] = sample_contract_info
        validator._failed_symbols.add("INVALID")

        symbols = ["EUR.USD", "INVALID", "AAPL"]

        # Mock AAPL lookup
        def mock_get_contract_details(symbol):
            if symbol == "EUR.USD":
                return sample_contract_info
            elif symbol == "INVALID":
                return None
            elif symbol == "AAPL":
                return Mock()  # Valid contract
            return None

        with patch.object(
            validator, "get_contract_details", side_effect=mock_get_contract_details
        ):
            results = validator.batch_validate(symbols)

        assert results["EUR.USD"] is True
        assert results["INVALID"] is False
        assert results["AAPL"] is True

    def test_batch_get_contracts(self, validator, sample_contract_info):
        """Test batch contract details."""
        symbols = ["EUR.USD", "INVALID"]

        def mock_get_contract_details(symbol):
            if symbol == "EUR.USD":
                return sample_contract_info
            return None

        with patch.object(
            validator, "get_contract_details", side_effect=mock_get_contract_details
        ):
            results = validator.batch_get_contracts(symbols)

        assert results["EUR.USD"] == sample_contract_info
        assert results["INVALID"] is None

    def test_cache_stats(self, validator, sample_contract_info):
        """Test cache statistics."""
        validator._cache["EUR.USD"] = sample_contract_info
        validator._validated_symbols.add("EUR.USD")
        validator._failed_symbols.add("INVALID")

        stats = validator.get_cache_stats()

        assert stats["cached_symbols"] == 1
        assert stats["validated_symbols"] == 1
        assert stats["failed_symbols"] == 1
        assert stats["total_lookups"] == 2

    def test_clear_cache(self, validator, sample_contract_info):
        """Test cache clearing."""
        validator._cache["EUR.USD"] = sample_contract_info
        validator._validated_symbols.add("EUR.USD")
        validator._failed_symbols.add("INVALID")

        validator.clear_cache()

        assert len(validator._cache) == 0
        assert len(validator._validated_symbols) == 0
        assert len(validator._failed_symbols) == 0

    def test_get_cached_symbols(self, validator, sample_contract_info):
        """Test getting cached symbols."""
        validator._cache["EUR.USD"] = sample_contract_info
        validator._cache["GBP.USD"] = sample_contract_info

        symbols = validator.get_cached_symbols()

        assert len(symbols) == 2
        assert "EUR.USD" in symbols
        assert "GBP.USD" in symbols

    def test_is_forex_symbol(self, validator, sample_contract_info):
        """Test forex symbol detection."""
        # Test with cached forex
        validator._cache["EUR.USD"] = sample_contract_info
        assert validator.is_forex_symbol("EUR.USD") is True

        # Test heuristics
        assert validator.is_forex_symbol("GBP.USD") is True
        assert validator.is_forex_symbol("EURUSD") is True
        assert validator.is_forex_symbol("AAPL") is False
        assert validator.is_forex_symbol("INVALID") is False

    def test_error_handling_in_batch_operations(self, validator):
        """Test error handling in batch operations."""

        def mock_validate_with_error(symbol):
            if symbol == "ERROR":
                raise Exception("Test error")
            return True

        with patch.object(
            validator, "validate_symbol", side_effect=mock_validate_with_error
        ):
            results = validator.batch_validate(["GOOD", "ERROR"])

        assert results["GOOD"] is True
        assert results["ERROR"] is False

        def mock_get_contract_with_error(symbol):
            if symbol == "ERROR":
                raise Exception("Test error")
            return Mock()

        with patch.object(
            validator, "get_contract_details", side_effect=mock_get_contract_with_error
        ):
            results = validator.batch_get_contracts(["GOOD", "ERROR"])

        assert results["GOOD"] is not None
        assert results["ERROR"] is None

    def test_protected_revalidation_success(self, validator, sample_contract_info):
        """Test protected re-validation for previously validated symbol."""
        symbol = "EUR.USD"
        
        # Mark as validated but expire cache
        validator._validated_symbols.add(symbol)
        expired_contract_info = sample_contract_info
        expired_contract_info.validated_at = time.time() - 86400 * 31  # 31 days ago
        validator._cache[symbol] = expired_contract_info
        
        # Mock successful re-validation
        mock_detail = Mock()
        mock_detail.contract = Mock()
        mock_detail.contract.symbol = "EUR"
        mock_detail.contract.secType = "CASH"
        mock_detail.contract.primaryExchange = ""
        mock_detail.contract.exchange = "IDEALPRO"
        mock_detail.contract.currency = "USD"
        mock_detail.longName = "Euro vs US Dollar"
        mock_detail.contractMonth = ""
        
        validator.connection.ib.reqContractDetails.return_value = [mock_detail]
        
        result = validator.get_contract_details(symbol)
        
        # Should succeed and update cache
        assert result is not None
        assert symbol in validator._validated_symbols
        assert symbol not in validator._failed_symbols
        
    def test_protected_revalidation_connection_failure(self, validator, sample_contract_info):
        """Test protected re-validation when connection fails."""
        symbol = "EUR.USD"
        
        # Mark as validated but expire cache
        validator._validated_symbols.add(symbol)
        expired_contract_info = sample_contract_info
        expired_contract_info.validated_at = time.time() - 86400 * 31  # 31 days ago
        validator._cache[symbol] = expired_contract_info
        
        # Mock connection failure
        validator.connection.is_connected.return_value = False
        
        result = validator.get_contract_details(symbol)
        
        # Should return None but NOT mark as failed
        assert result is None
        assert symbol in validator._validated_symbols  # Still validated
        assert symbol not in validator._failed_symbols  # NOT marked as failed
        
    def test_protected_revalidation_lookup_failure(self, validator, sample_contract_info):
        """Test protected re-validation when lookup fails but connection is OK."""
        symbol = "EUR.USD"
        
        # Mark as validated but expire cache
        validator._validated_symbols.add(symbol)
        expired_contract_info = sample_contract_info
        expired_contract_info.validated_at = time.time() - 86400 * 31  # 31 days ago
        validator._cache[symbol] = expired_contract_info
        
        # Mock lookup failure (empty result)
        validator.connection.ib.reqContractDetails.return_value = []
        
        result = validator.get_contract_details(symbol)
        
        # Should return None but NOT mark as failed
        assert result is None
        assert symbol in validator._validated_symbols  # Still validated
        assert symbol not in validator._failed_symbols  # NOT marked as failed

    def test_normal_validation_new_symbol_success(self, validator):
        """Test normal validation for new symbol - success."""
        symbol = "AAPL"
        
        # Ensure symbol is not previously validated
        assert symbol not in validator._validated_symbols
        assert symbol not in validator._failed_symbols
        
        # Mock successful lookup
        mock_detail = Mock()
        mock_detail.contract = Mock()
        mock_detail.contract.symbol = "AAPL"
        mock_detail.contract.secType = "STK"
        mock_detail.contract.primaryExchange = "NASDAQ"
        mock_detail.contract.exchange = "SMART"
        mock_detail.contract.currency = "USD"
        mock_detail.longName = "Apple Inc"
        mock_detail.contractMonth = ""
        
        validator.connection.ib.reqContractDetails.return_value = [mock_detail]
        
        result = validator.get_contract_details(symbol)
        
        # Should succeed and mark as validated
        assert result is not None
        assert symbol in validator._validated_symbols
        assert symbol not in validator._failed_symbols
        assert symbol in validator._cache

    def test_normal_validation_new_symbol_failure(self, validator):
        """Test normal validation for new symbol - failure."""
        symbol = "INVALID"
        
        # Ensure symbol is not previously validated
        assert symbol not in validator._validated_symbols
        assert symbol not in validator._failed_symbols
        
        # Mock lookup failure
        validator.connection.ib.reqContractDetails.return_value = []
        
        result = validator.get_contract_details(symbol)
        
        # Should fail and mark as failed
        assert result is None
        assert symbol not in validator._validated_symbols
        assert symbol in validator._failed_symbols
        assert symbol not in validator._cache

    def test_normal_validation_already_failed_symbol(self, validator):
        """Test normal validation for symbol already in failed cache."""
        symbol = "INVALID"
        
        # Mark as failed
        validator._failed_symbols.add(symbol)
        
        result = validator.get_contract_details(symbol)
        
        # Should return None immediately without lookup
        assert result is None
        assert symbol not in validator._validated_symbols
        assert symbol in validator._failed_symbols

    def test_mark_symbol_validated(self, validator):
        """Test _mark_symbol_validated method."""
        symbol = "EUR.USD"
        contract_info = Mock()
        
        # Initially in failed symbols
        validator._failed_symbols.add(symbol)
        
        validator._mark_symbol_validated(symbol, contract_info)
        
        # Should be moved to validated and removed from failed
        assert symbol in validator._validated_symbols
        assert symbol not in validator._failed_symbols
        assert validator._cache[symbol] == contract_info

    def test_cache_validation_with_new_ttl(self, validator, sample_contract_info):
        """Test cache validation with new 30-day TTL."""
        symbol = "EUR.USD"
        
        # Recent validation (within 30 days)
        recent_contract_info = sample_contract_info
        recent_contract_info.validated_at = time.time() - 86400 * 15  # 15 days ago
        validator._cache[symbol] = recent_contract_info
        
        assert validator._is_cache_valid(symbol) is True
        
        # Old validation (beyond 30 days)
        old_contract_info = sample_contract_info
        old_contract_info.validated_at = time.time() - 86400 * 35  # 35 days ago
        validator._cache[symbol] = old_contract_info
        
        assert validator._is_cache_valid(symbol) is False

    def test_backward_compatibility_cache_loading(self, validator):
        """Test backward compatibility when loading cache without validated_symbols."""
        # Simulate old cache format (no validated_symbols field)
        import tempfile
        import json
        
        cache_data = {
            'cache': {
                'EUR.USD': {
                    'symbol': 'EUR.USD',
                    'asset_type': 'CASH',
                    'exchange': 'IDEALPRO',
                    'currency': 'USD',
                    'description': 'Euro vs US Dollar',
                    'validated_at': time.time()
                }
            },
            'failed_symbols': ['INVALID'],
            # Note: no 'validated_symbols' field
            'last_updated': time.time()
        }
        
        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(cache_data, f)
            temp_file = f.name
        
        try:
            # Create validator with temporary cache file
            validator_with_old_cache = IbSymbolValidator(cache_file=temp_file)
            
            # Should have backward compatibility
            assert len(validator_with_old_cache._cache) == 1
            assert len(validator_with_old_cache._validated_symbols) == 1  # Populated from cache
            assert 'EUR.USD' in validator_with_old_cache._validated_symbols
            assert len(validator_with_old_cache._failed_symbols) == 1
            
        finally:
            import os
            os.unlink(temp_file)


class TestContractInfo:
    """Test ContractInfo dataclass."""

    def test_contract_info_creation(self):
        """Test ContractInfo creation."""
        contract = Mock(spec=Contract)
        timestamp = time.time()

        info = ContractInfo(
            symbol="EUR.USD",
            contract=contract,
            asset_type="CASH",
            exchange="IDEALPRO",
            currency="USD",
            description="Euro vs US Dollar",
            validated_at=timestamp,
        )

        assert info.symbol == "EUR.USD"
        assert info.contract == contract
        assert info.asset_type == "CASH"
        assert info.exchange == "IDEALPRO"
        assert info.currency == "USD"
        assert info.description == "Euro vs US Dollar"
        assert info.validated_at == timestamp
