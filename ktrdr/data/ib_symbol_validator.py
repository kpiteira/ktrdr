"""
IB Symbol Validator for Interactive Brokers contract lookups.

This module provides symbol validation and contract lookup functionality
with priority order support for different asset types (CASH, STK, FUT).
"""

import time
from typing import Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass
from ib_insync import Contract, Forex, Stock, Future

from ktrdr.logging import get_logger
from ktrdr.data.ib_connection_sync import IbConnectionSync

logger = get_logger(__name__)


@dataclass
class ContractInfo:
    """
    Information about a validated IB contract.

    Attributes:
        symbol: The symbol as requested
        contract: The IB contract object
        asset_type: Type of asset (CASH, STK, FUT, etc.)
        exchange: Primary exchange
        currency: Contract currency
        description: Contract description
        validated_at: Timestamp when validation occurred
    """

    symbol: str
    contract: Contract
    asset_type: str
    exchange: str
    currency: str
    description: str
    validated_at: float


class IbSymbolValidator:
    """
    IB symbol validation and contract lookup with caching.

    This class provides methods to validate symbols against IB's contract
    database with priority ordering (forex first, then stocks, then futures).
    Results are cached to avoid repeated lookups.
    """

    def __init__(self, connection: Optional[IbConnectionSync] = None):
        """
        Initialize the symbol validator.

        Args:
            connection: Optional IB connection. If not provided, will create one.
        """
        self.connection = connection
        self._cache: Dict[str, ContractInfo] = {}
        self._failed_symbols: Set[str] = set()
        self._cache_ttl = 3600  # 1 hour cache TTL

        logger.info("IbSymbolValidator initialized")

    def _ensure_connection(self) -> bool:
        """
        Ensure we have a valid IB connection.

        Returns:
            True if connection is available, False otherwise
        """
        if not self.connection:
            logger.warning("No IB connection provided to symbol validator")
            return False

        if not self.connection.is_connected():
            logger.warning("IB connection is not active")
            return False

        return True

    def _is_cache_valid(self, symbol: str) -> bool:
        """
        Check if cached result is still valid.

        Args:
            symbol: Symbol to check

        Returns:
            True if cache entry exists and is not expired
        """
        if symbol not in self._cache:
            return False

        cache_entry = self._cache[symbol]
        age = time.time() - cache_entry.validated_at
        return age < self._cache_ttl

    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol format for consistent lookups.

        Args:
            symbol: Raw symbol string

        Returns:
            Normalized symbol string
        """
        # Convert to uppercase and strip whitespace
        normalized = symbol.upper().strip()

        # Handle forex pairs - convert EUR/USD to EUR.USD format
        if "/" in normalized:
            normalized = normalized.replace("/", ".")

        return normalized

    def _create_forex_contract(self, symbol: str) -> Optional[Contract]:
        """
        Create forex contract for symbol.

        Args:
            symbol: Symbol like EUR.USD or EURUSD

        Returns:
            Forex contract or None if invalid format
        """
        try:
            # Handle different forex formats
            if "." in symbol:
                base, quote = symbol.split(".", 1)
            elif len(symbol) == 6:
                # EURUSD -> EUR, USD
                base, quote = symbol[:3], symbol[3:]
            else:
                return None

            if len(base) != 3 or len(quote) != 3:
                return None

            return Forex(pair=f"{base}{quote}")

        except Exception as e:
            logger.debug(f"Failed to create forex contract for {symbol}: {e}")
            return None

    def _create_stock_contract(self, symbol: str) -> Contract:
        """
        Create stock contract for symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Stock contract
        """
        return Stock(symbol=symbol, exchange="SMART", currency="USD")

    def _create_future_contract(self, symbol: str) -> Contract:
        """
        Create future contract for symbol.

        Args:
            symbol: Future symbol

        Returns:
            Future contract (basic, may need exchange specification)
        """
        return Future(symbol=symbol, exchange="CME")

    def _lookup_contract(self, contract: Contract) -> Optional[ContractInfo]:
        """
        Look up contract details from IB.

        Args:
            contract: Contract to look up

        Returns:
            ContractInfo if found, None otherwise
        """
        try:
            if not self._ensure_connection():
                return None

            # Request contract details
            details = self.connection.ib.reqContractDetails(contract)

            if not details:
                return None

            # Use first result
            detail = details[0]
            contract_details = detail.contract

            return ContractInfo(
                symbol=contract_details.symbol,
                contract=contract_details,
                asset_type=contract_details.secType,
                exchange=contract_details.primaryExchange or contract_details.exchange,
                currency=contract_details.currency,
                description=detail.longName or detail.contractMonth or "",
                validated_at=time.time(),
            )

        except Exception as e:
            logger.debug(f"Contract lookup failed for {contract}: {e}")
            return None

    def validate_symbol(self, symbol: str) -> bool:
        """
        Validate if a symbol exists in IB's database.

        Args:
            symbol: Symbol to validate

        Returns:
            True if symbol is valid, False otherwise
        """
        normalized = self._normalize_symbol(symbol)

        # Check cache first
        if self._is_cache_valid(normalized):
            return True

        # Check failed symbols cache
        if normalized in self._failed_symbols:
            return False

        # Try to get contract details
        contract_info = self.get_contract_details(normalized)
        return contract_info is not None

    def get_contract_details(self, symbol: str) -> Optional[ContractInfo]:
        """
        Get contract details with priority order: CASH -> STK -> FUT.

        Args:
            symbol: Symbol to look up

        Returns:
            ContractInfo if found, None otherwise
        """
        normalized = self._normalize_symbol(symbol)

        # Check cache first
        if self._is_cache_valid(normalized):
            return self._cache[normalized]

        # Check failed symbols cache
        if normalized in self._failed_symbols:
            return None

        if not self._ensure_connection():
            return None

        # Priority order: Forex (CASH) -> Stocks (STK) -> Futures (FUT)
        contract_types = [
            ("CASH", self._create_forex_contract),
            ("STK", self._create_stock_contract),
            ("FUT", self._create_future_contract),
        ]

        for asset_type, contract_creator in contract_types:
            try:
                contract = contract_creator(normalized)
                if contract is None:
                    continue

                contract_info = self._lookup_contract(contract)
                if contract_info:
                    # Cache successful result
                    self._cache[normalized] = contract_info
                    logger.info(
                        f"Validated {normalized} as {asset_type}: {contract_info.description}"
                    )
                    return contract_info

            except Exception as e:
                logger.debug(f"Failed to lookup {normalized} as {asset_type}: {e}")
                continue

        # Mark as failed and cache the failure
        self._failed_symbols.add(normalized)
        logger.warning(f"Symbol validation failed for {normalized}")
        return None

    def batch_validate(self, symbols: List[str]) -> Dict[str, bool]:
        """
        Validate multiple symbols in batch.

        Args:
            symbols: List of symbols to validate

        Returns:
            Dictionary mapping symbol to validation result
        """
        results = {}

        for symbol in symbols:
            try:
                results[symbol] = self.validate_symbol(symbol)
            except Exception as e:
                logger.error(f"Error validating symbol {symbol}: {e}")
                results[symbol] = False

        return results

    def batch_get_contracts(
        self, symbols: List[str]
    ) -> Dict[str, Optional[ContractInfo]]:
        """
        Get contract details for multiple symbols in batch.

        Args:
            symbols: List of symbols to look up

        Returns:
            Dictionary mapping symbol to ContractInfo (or None if failed)
        """
        results = {}

        for symbol in symbols:
            try:
                results[symbol] = self.get_contract_details(symbol)
            except Exception as e:
                logger.error(f"Error getting contract details for {symbol}: {e}")
                results[symbol] = None

        return results

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "cached_symbols": len(self._cache),
            "failed_symbols": len(self._failed_symbols),
            "total_lookups": len(self._cache) + len(self._failed_symbols),
        }

    def clear_cache(self):
        """Clear all cached results."""
        self._cache.clear()
        self._failed_symbols.clear()
        logger.info("Symbol validation cache cleared")

    def get_cached_symbols(self) -> List[str]:
        """
        Get list of successfully cached symbols.

        Returns:
            List of symbol names that are cached
        """
        return list(self._cache.keys())

    def is_forex_symbol(self, symbol: str) -> bool:
        """
        Check if symbol is likely a forex pair.

        Args:
            symbol: Symbol to check

        Returns:
            True if symbol appears to be forex
        """
        normalized = self._normalize_symbol(symbol)

        # Check cache first
        if self._is_cache_valid(normalized):
            return self._cache[normalized].asset_type == "CASH"

        # Basic heuristics for forex detection
        if "." in normalized and len(normalized.replace(".", "")) == 6:
            return True

        if len(normalized) == 6 and normalized.isalpha():
            return True

        return False
