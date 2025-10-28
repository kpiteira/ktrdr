"""
IB Symbol Validator

Migrated from the proven IbSymbolValidatorUnified to work with the new IB architecture.
Updated to use the new connection pool and pace manager while preserving all the
sophisticated validation logic, caching, and error handling.

This validator provides:
- Integration with new IbConnectionPool for connection management
- New IbPaceManager for pace violation prevention and handling
- Enhanced error handling with intelligent retry strategies
- Support for both sync and async operations
- Comprehensive caching and persistent storage
- Head timestamp fetching with connection pool

Key Features:
- Uses connection pool for efficient connection management
- Proactive pace limiting to prevent violations
- Enhanced error classification and handling
- Contract lookup with automatic instrument detection
- Persistent caching with JSON storage
- Trading hours metadata integration
- Head timestamp API integration
"""

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
from typing import Optional

from ib_insync import Contract, Forex, Future, Stock

from ib.pace_manager import IbPaceManager
from ib.pool_manager import get_shared_ib_pool
from ib.trading_hours_parser import IBTradingHoursParser
from ktrdr.logging import get_logger

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
        trading_hours: Trading hours metadata for this contract
        head_timestamp: Earliest available data timestamp for this symbol (ISO format)
        head_timestamp_timeframes: Dict of timeframe -> earliest timestamp mapping
        head_timestamp_fetched_at: When head timestamp was last fetched
    """

    symbol: str
    contract: Contract
    asset_type: str
    exchange: str
    currency: str
    description: str
    validated_at: float
    trading_hours: Optional[dict] = None  # Serialized TradingHours
    head_timestamp: Optional[str] = None  # ISO format for JSON serialization
    head_timestamp_timeframes: Optional[dict[str, str]] = (
        None  # timeframe -> ISO timestamp
    )
    head_timestamp_fetched_at: Optional[float] = (
        None  # Timestamp when head data was fetched
    )


@dataclass
class ValidationResult:
    """Result of symbol validation with metadata."""

    is_valid: bool
    symbol: str
    error_message: Optional[str] = None
    contract_info: Optional[ContractInfo] = None
    head_timestamps: Optional[dict[str, str]] = None  # timeframe -> ISO timestamp
    suggested_symbol: Optional[str] = (
        None  # For format corrections like USDJPY -> USD.JPY
    )


class IbSymbolValidator:
    """
    IB symbol validator using the new connection pool and pace manager.

    This validator provides enhanced functionality while maintaining
    compatibility with existing patterns, but updated for the new architecture.
    """

    def __init__(
        self, component_name: str = "symbol_validator", cache_file: Optional[str] = None
    ):
        """
        Initialize the symbol validator with new architecture.

        Args:
            component_name: Name for this component (used in metrics and logging)
            cache_file: Optional path to cache file for persistent storage
        """
        self.component_name = component_name
        self.pace_manager = IbPaceManager()

        # Cache management
        self._cache: dict[str, ContractInfo] = {}
        self._validated_symbols: set[str] = set()  # Permanently validated symbols
        self._cache_ttl = 86400 * 30  # 30 days for re-validation

        # Metrics tracking
        self.metrics = {
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0,
            "cache_hits": 0,
            "pace_violations_handled": 0,
            "retries_performed": 0,
            "total_validation_time": 0.0,
            "avg_validation_time": 0.0,
        }

        # Set up persistent cache file
        if cache_file:
            self._cache_file = Path(cache_file)
        else:
            # Default cache file in data directory
            try:
                from ktrdr.config.settings import get_api_settings

                settings = get_api_settings()
                data_dir = (
                    Path(settings.data_dir)
                    if hasattr(settings, "data_dir")
                    else Path("data")
                )
            except Exception:
                data_dir = Path("data")
            self._cache_file = data_dir / "symbol_discovery_cache.json"

        # Ensure cache directory exists
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing cache from file
        self._load_cache_from_file()

        logger.info(f"IbSymbolValidator initialized (component: {component_name})")
        logger.info(f"Cache file: {self._cache_file}")
        logger.info(
            f"Loaded {len(self._cache)} cached symbols, {len(self._validated_symbols)} validated"
        )

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

    def _detect_instrument_type(self, symbol: str) -> str:
        """
        Auto-detect instrument type (forex vs stock) based on symbol patterns.

        Args:
            symbol: Symbol to analyze

        Returns:
            "forex" for forex pairs, "stock" for stocks
        """
        normalized = symbol.upper().replace("/", "").replace(".", "")

        # Forex detection heuristics
        # 6-character currency pairs like USDJPY, EURUSD
        if len(normalized) == 6 and normalized.isalpha():
            # Common forex pairs
            common_forex = {
                "EURUSD",
                "GBPUSD",
                "USDJPY",
                "USDCHF",
                "AUDUSD",
                "USDCAD",
                "NZDUSD",
                "EURJPY",
                "GBPJPY",
                "AUDJPY",
                "CADJPY",
                "CHFJPY",
                "NZDJPY",
                "EURGBP",
                "EURAUD",
                "EURCAD",
                "EURCHF",
                "EURNZD",
                "GBPAUD",
                "GBPCAD",
                "GBPCHF",
                "GBPNZD",
                "AUDCAD",
                "AUDCHF",
                "AUDNZD",
                "CADCHF",
                "NZDCAD",
                "NZDCHF",
            }
            if normalized in common_forex:
                return "forex"

            # Additional pattern: if it looks like XXXYYY where both XXX and YYY are currency codes
            major_currencies = {
                "USD",
                "EUR",
                "GBP",
                "JPY",
                "CHF",
                "AUD",
                "CAD",
                "NZD",
                "SEK",
                "NOK",
                "DKK",
            }
            base = normalized[:3]
            quote = normalized[3:]
            if base in major_currencies and quote in major_currencies:
                return "forex"

        # Symbol with dot notation like EUR.USD
        if "." in symbol and len(symbol.replace(".", "")) == 6:
            return "forex"

        # Default to stock for everything else
        return "stock"

    def _suggest_forex_format(self, symbol: str) -> Optional[str]:
        """
        Suggest proper forex format for a symbol.

        Args:
            symbol: Original symbol like USDJPY

        Returns:
            Suggested format like USD.JPY or None if not forex
        """
        normalized = symbol.upper().replace("/", "").replace(".", "")

        if len(normalized) == 6 and normalized.isalpha():
            # Check if it looks like a forex pair
            major_currencies = {
                "USD",
                "EUR",
                "GBP",
                "JPY",
                "CHF",
                "AUD",
                "CAD",
                "NZD",
                "SEK",
                "NOK",
                "DKK",
            }
            base = normalized[:3]
            quote = normalized[3:]
            if base in major_currencies and quote in major_currencies:
                return f"{base}.{quote}"

        return None

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

    async def _lookup_contract_async(
        self, contract: Contract, max_retries: int = 3
    ) -> Optional[ContractInfo]:
        """
        Look up contract details from IB using synchronous connection pool.

        Args:
            contract: Contract to look up
            max_retries: Maximum number of retry attempts

        Returns:
            ContractInfo if found, None otherwise
        """
        retry_count = 0
        last_error = None
        connection_pool = get_shared_ib_pool()

        while retry_count <= max_retries:
            try:
                # Check pace limits before making request
                await self.pace_manager.wait_if_needed(
                    is_historical=False,
                    contract_key=f"{getattr(contract, 'symbol', 'unknown')}_contract_lookup",
                )

                # Use synchronous connection pool execution to match our architecture
                details = await connection_pool.execute_with_connection_sync(
                    self._lookup_contract_impl, contract
                )

                self.metrics["total_validations"] += 1

                logger.debug(
                    f"IB returned {len(details) if details else 0} contract details"
                )

                if not details:
                    logger.debug(f"No contract details returned for: {contract}")
                    logger.debug(
                        "   This means IB has no security definition for this contract specification"
                    )
                    self.metrics["failed_validations"] += 1
                    return None

                # Use first result
                detail = details[0]
                contract_details = detail.contract

                logger.debug(
                    f"Contract found: {contract_details.symbol} ({contract_details.secType}) on {contract_details.exchange}"
                )
                logger.debug(f"   Full name: {detail.longName or 'N/A'}")
                logger.debug(f"   Currency: {contract_details.currency}")

                # Get trading hours metadata from IB contract details
                exchange = contract_details.primaryExchange or contract_details.exchange
                trading_hours_dict = None

                # Try to parse real IB trading hours first
                try:
                    trading_hours = IBTradingHoursParser.create_from_contract_details(
                        detail
                    )
                    if trading_hours:
                        # Convert trading hours to dict ensuring JSON serializability
                        trading_hours_dict = {
                            "timezone": str(getattr(trading_hours, "timezone", "UTC")),
                            "regular_hours": {
                                "start": "09:30",  # Use simple default instead of complex objects
                                "end": "16:00",
                                "name": "Regular",
                            },
                            "extended_hours": [],  # Use simple default instead of complex objects
                            "trading_days": [0, 1, 2, 3, 4],  # Monday to Friday default
                            "holidays": [],
                        }
                        logger.debug(
                            f"Added simplified trading hours for {contract_details.symbol} on {exchange}"
                        )
                except Exception as e:
                    logger.debug(f"Failed to parse IB trading hours: {e}")
                    # Fall back to basic structure
                    trading_hours_dict = {
                        "timezone": "UTC",
                        "regular_hours": {
                            "start": "09:30",
                            "end": "16:00",
                            "name": "Regular",
                        },
                        "extended_hours": [],
                        "trading_days": [0, 1, 2, 3, 4],  # Monday to Friday
                        "holidays": [],
                    }

                contract_info = ContractInfo(
                    symbol=contract_details.symbol,
                    contract=contract_details,
                    asset_type=contract_details.secType,
                    exchange=exchange,
                    currency=contract_details.currency,
                    description=detail.longName or detail.contractMonth or "",
                    validated_at=time.time(),
                    trading_hours=trading_hours_dict,
                )

                self.metrics["successful_validations"] += 1
                return contract_info

            except asyncio.TimeoutError:
                retry_count += 1
                last_error = asyncio.TimeoutError(
                    f"Contract lookup timeout for {getattr(contract, 'symbol', 'unknown')}"
                )
                logger.warning(
                    f"Contract lookup timeout for {getattr(contract, 'symbol', 'unknown')} (attempt {retry_count}/{max_retries})"
                )

                # Wait before retry
                if retry_count < max_retries:
                    await asyncio.sleep(2.0)
                continue

            except Exception as e:
                retry_count += 1
                last_error = e  # type: ignore

                logger.warning(f"Contract lookup error: {e}")

                # Wait before retry
                if retry_count < max_retries:
                    # Exponential backoff for additional delay
                    backoff_delay = min(2 ** (retry_count - 1), 30)  # Cap at 30 seconds
                    if backoff_delay > 0:
                        logger.debug(f" {backoff_delay}s")
                        await asyncio.sleep(backoff_delay)

                    self.metrics["retries_performed"] += 1
                    logger.warning(
                        f"Retrying contract lookup (attempt {retry_count}/{max_retries}): {e}"
                    )

        # All retries failed
        self.metrics["failed_validations"] += 1
        logger.error(f"CONTRACT LOOKUP FAILED after {retry_count} retries")
        logger.error(f"   Final error: {last_error}")
        return None

    def _lookup_contract_impl(self, ib, contract: Contract):
        """
        Synchronous implementation of contract lookup for use with connection pool.

        Args:
            ib: IB connection instance
            contract: Contract to look up

        Returns:
            List of contract details
        """
        logger.debug(f"🔍 Requesting contract details for: {contract}")
        logger.debug(f"   Contract type: {type(contract).__name__}")
        logger.debug(
            f"   Contract details: symbol={getattr(contract, 'symbol', 'N/A')}, secType={getattr(contract, 'secType', 'N/A')}, exchange={getattr(contract, 'exchange', 'N/A')}"
        )

        # Make synchronous IB API call
        details = ib.reqContractDetails(contract)

        logger.debug(f"IB returned {len(details) if details else 0} contract details")
        return details

    def _fetch_head_timestamp_impl(self, ib, contract, asset_type: str):
        """
        Synchronous implementation of head timestamp fetching for use with connection pool.

        Args:
            ib: IB connection instance
            contract: Contract to get head timestamp for
            asset_type: Asset type to determine whatToShow options

        Returns:
            Head timestamp if found, None otherwise
        """
        logger.debug(f"Requesting head timestamp for {contract}")

        # For forex pairs, use same logic as data fetcher
        if asset_type == "CASH":
            # Forex instruments - IB doesn't support TRADES for forex, use BID first
            whatToShow_options = ["BID", "ASK", "MIDPOINT"]
        else:
            # Stocks, futures, options - use TRADES data
            whatToShow_options = ["TRADES"]

        head_timestamp = None
        for whatToShow in whatToShow_options:
            try:
                logger.debug(f"Trying head timestamp with whatToShow={whatToShow}")

                # Make synchronous IB API call
                head_timestamp = ib.reqHeadTimeStamp(
                    contract=contract,
                    whatToShow=whatToShow,
                    useRTH=False,  # Include all trading hours
                    formatDate=1,  # Return as datetime
                )

                if head_timestamp:
                    logger.debug(f" {head_timestamp}")
                    break
                else:
                    logger.warning(f"No head timestamp with {whatToShow}")
            except Exception as e:
                logger.warning(f"Error with {whatToShow}: {e}")
                continue

        return head_timestamp

    async def validate_symbol_with_metadata(
        self, symbol: str, timeframes: list[str]
    ) -> ValidationResult:
        """
        Validate symbol and get all metadata including head timestamps for timeframes.

        Args:
            symbol: Symbol to validate
            timeframes: List of timeframes to get head timestamps for

        Returns:
            ValidationResult with validation status and metadata
        """
        normalized = self._normalize_symbol(symbol)

        # Check cache first
        if self._is_cache_valid(normalized):
            self.metrics["cache_hits"] += 1
            contract_info = self._cache[normalized]

            # Get head timestamps for requested timeframes
            head_timestamps = {}
            for tf in timeframes:
                if (
                    contract_info.head_timestamp_timeframes
                    and tf in contract_info.head_timestamp_timeframes
                ):
                    head_timestamps[tf] = contract_info.head_timestamp_timeframes[tf]
                elif contract_info.head_timestamp:
                    head_timestamps[tf] = contract_info.head_timestamp

            return ValidationResult(
                is_valid=True,
                symbol=normalized,
                contract_info=contract_info,
                head_timestamps=head_timestamps,
            )

        # Try to get contract details
        contract_info = await self.get_contract_details_async(normalized)  # type: ignore
        if not contract_info:
            # Check for format suggestions
            suggested = self._suggest_forex_format(normalized)
            error_msg = f"Symbol {symbol} not found"
            if suggested and suggested != normalized:
                error_msg += f". Did you mean {suggested}?"

            return ValidationResult(
                is_valid=False,
                symbol=normalized,
                error_message=error_msg,
                suggested_symbol=suggested,
            )

        # Get head timestamps for requested timeframes
        head_timestamps = {}
        for timeframe in timeframes:
            head_ts = await self.fetch_head_timestamp_async(normalized, timeframe)
            if head_ts:
                head_timestamps[timeframe] = head_ts

        return ValidationResult(
            is_valid=True,
            symbol=normalized,
            contract_info=contract_info,
            head_timestamps=head_timestamps,
        )

    async def validate_symbol_async(self, symbol: str) -> bool:
        """
        Validate if a symbol exists in IB's database asynchronously.

        Args:
            symbol: Symbol to validate

        Returns:
            True if symbol is valid, False otherwise
        """
        result = await self.validate_symbol_with_metadata(symbol, [])
        return result.is_valid

    async def get_contract_details_async(self, symbol: str) -> Optional[ContractInfo]:
        """
        Get contract details with protected re-validation logic (async version).
        Never marks previously validated symbols as failed.

        Args:
            symbol: Symbol to look up

        Returns:
            ContractInfo if found, None otherwise
        """
        start_time = time.time()
        normalized = self._normalize_symbol(symbol)

        try:
            # Check if symbol was ever validated successfully
            if normalized in self._validated_symbols:
                # Previously validated - NEVER mark as failed, only re-validate on TTL
                if self._is_cache_valid(normalized):
                    self.metrics["cache_hits"] += 1
                    return self._cache[normalized]
                else:
                    # Cache expired - attempt re-validation but don't fail on connection issues
                    logger.info(
                        f"Re-validating previously validated symbol: {normalized}"
                    )
                    return await self._attempt_revalidation_async(normalized)
            else:
                # Never validated before - use normal validation with failure tracking
                return await self._normal_validation_async(normalized)

        finally:
            # Update metrics
            elapsed = time.time() - start_time
            self.metrics["total_validation_time"] += elapsed
            if self.metrics["total_validations"] > 0:
                self.metrics["avg_validation_time"] = (
                    self.metrics["total_validation_time"]
                    / self.metrics["total_validations"]
                )

    async def _attempt_revalidation_async(self, symbol: str) -> Optional[ContractInfo]:
        """Attempt re-validation for previously validated symbol (async)."""
        try:
            contract_info = await self._attempt_validation_async(symbol)
            if contract_info:
                self._cache[symbol] = contract_info
                self._save_cache_to_file()
                logger.info(f"Re-validation successful for {symbol}")
                return contract_info
            else:
                # Connection issue - return None but DON'T mark as failed
                logger.warning(
                    f"Re-validation failed for {symbol} (connection issue), keeping as valid"
                )
                return None
        except Exception as e:
            logger.warning(f"Re-validation error for {symbol}: {e}")
            return None

    async def _normal_validation_async(self, symbol: str) -> Optional[ContractInfo]:
        """Normal validation for never-before-validated symbols (async)."""
        logger.debug(f"Starting async symbol validation for {symbol}")

        # Attempt validation...
        contract_info = await self._attempt_validation_async(symbol)
        if contract_info:
            self._mark_symbol_validated(symbol, contract_info)
            return contract_info
        else:
            logger.warning(f"Symbol validation failed for {symbol}")
            return None

    async def _attempt_validation_async(self, symbol: str) -> Optional[ContractInfo]:
        """Attempt validation with IB contract lookup (async)."""
        # Priority order: Forex (CASH) -> Stocks (STK) -> Futures (FUT)
        contract_types = [
            ("CASH", self._create_forex_contract),
            ("STK", self._create_stock_contract),
            ("FUT", self._create_future_contract),
        ]

        for asset_type, contract_creator in contract_types:
            try:
                logger.debug(f"Attempting to validate {symbol} as {asset_type}")
                contract = contract_creator(symbol)
                if contract is None:
                    logger.debug(f"Could not create {asset_type} contract for {symbol}")
                    continue

                logger.debug(
                    f"Created {asset_type} contract for {symbol}, performing lookup..."
                )
                contract_info = await self._lookup_contract_async(contract)
                if contract_info:
                    logger.info(
                        f"Validated {symbol} as {asset_type}: {contract_info.description}"
                    )
                    return contract_info
                else:
                    logger.debug(f"Lookup failed for {symbol} as {asset_type}")

            except Exception as e:
                logger.warning(f"Failed to lookup {symbol} as {asset_type}: {e}")
                continue

        return None

    def _mark_symbol_validated(self, symbol: str, contract_info: ContractInfo):
        """Mark symbol as permanently validated."""
        self._validated_symbols.add(symbol)
        self._cache[symbol] = contract_info
        # Save cache to persistent storage
        self._save_cache_to_file()
        logger.info(f"Symbol {symbol} marked as permanently validated")

    async def fetch_head_timestamp_async(
        self,
        symbol: str,
        timeframe: Optional[str] = None,
        force_refresh: bool = False,
        max_retries: int = 3,
    ) -> Optional[str]:
        """
        Fetch the earliest available data timestamp for a symbol using IB's head timestamp API.

        Args:
            symbol: Symbol to fetch head timestamp for
            timeframe: Specific timeframe to fetch for (optional, uses default if not provided)
            force_refresh: If True, ignore cache and fetch fresh data
            max_retries: Maximum number of retry attempts

        Returns:
            ISO formatted earliest timestamp string or None if unavailable
        """
        normalized = self._normalize_symbol(symbol)

        # Check if we have valid cached head timestamp for this timeframe
        if not force_refresh and normalized in self._cache:
            contract_info = self._cache[normalized]
            if (
                contract_info.head_timestamp_fetched_at
                and time.time() - contract_info.head_timestamp_fetched_at < 86400
            ):  # 24 hour cache
                # Try to get timeframe-specific timestamp first
                if timeframe and contract_info.head_timestamp_timeframes:
                    timeframe_timestamp = contract_info.head_timestamp_timeframes.get(
                        timeframe
                    )
                    if timeframe_timestamp:
                        logger.debug(
                            f"📅 Using cached head timestamp for {symbol} ({timeframe}): {timeframe_timestamp}"
                        )
                        return timeframe_timestamp

                # Fall back to default head timestamp
                if contract_info.head_timestamp:
                    logger.debug(
                        f"📅 Using cached default head timestamp for {symbol}: {contract_info.head_timestamp}"
                    )
                    return contract_info.head_timestamp

        # Need to fetch from IB
        logger.info(f"📅 Fetching head timestamp from IB for {symbol}")

        # Get contract info first
        contract_info = await self.get_contract_details_async(normalized)  # type: ignore
        if not contract_info:
            logger.warning(
                f"Cannot fetch head timestamp for {symbol} - contract not found"
            )
            return None

        # Attempt to fetch head timestamp with retries
        retry_count = 0
        last_error = None
        connection_pool = get_shared_ib_pool()

        while retry_count <= max_retries:
            try:
                # Check pace limits before making request
                await self.pace_manager.wait_if_needed(
                    is_historical=True, contract_key=f"{symbol}_head_timestamp"
                )

                # Use synchronous connection pool execution to match our architecture
                head_timestamp = await connection_pool.execute_with_connection_sync(
                    self._fetch_head_timestamp_impl,
                    contract_info.contract,
                    contract_info.asset_type,
                )

                if head_timestamp:
                    # Ensure timezone awareness
                    if (
                        hasattr(head_timestamp, "tzinfo")
                        and head_timestamp.tzinfo is None
                    ):
                        head_timestamp = head_timestamp.replace(tzinfo=timezone.utc)

                    # Convert to ISO format for storage
                    head_timestamp_iso = head_timestamp.isoformat()

                    # Update the cached contract info
                    contract_info.head_timestamp = head_timestamp_iso
                    contract_info.head_timestamp_fetched_at = time.time()

                    # Initialize timeframes dict if not present
                    if contract_info.head_timestamp_timeframes is None:
                        contract_info.head_timestamp_timeframes = {}

                    # Store the head timestamp for the requested timeframe or default
                    cache_key = timeframe if timeframe else "default"
                    contract_info.head_timestamp_timeframes[cache_key] = (
                        head_timestamp_iso
                    )

                    # Also store as default if this is the first time we're fetching
                    if "default" not in contract_info.head_timestamp_timeframes:
                        contract_info.head_timestamp_timeframes["default"] = (
                            head_timestamp_iso
                        )

                    # Update cache
                    self._cache[normalized] = contract_info
                    self._save_cache_to_file()

                    logger.info(f"📅 HEAD TIMESTAMP for {symbol}: {head_timestamp_iso}")
                    return head_timestamp_iso
                else:
                    logger.warning(f"📅 No head timestamp available for {symbol}")
                    return None

            except Exception as e:
                retry_count += 1
                last_error = e  # type: ignore

                logger.warning(f"Head timestamp error: {e}")

                # Wait before retry
                if retry_count < max_retries:
                    # Exponential backoff for additional delay
                    backoff_delay = min(2 ** (retry_count - 1), 30)  # Cap at 30 seconds
                    if backoff_delay > 0:
                        logger.debug(f" {backoff_delay}s")
                        await asyncio.sleep(backoff_delay)

                    self.metrics["retries_performed"] += 1
                    logger.warning(
                        f"Retrying head timestamp fetch (attempt {retry_count}/{max_retries}): {e}"
                    )

        # All retries failed
        logger.error(
            f"Failed to fetch head timestamp for {symbol} after {retry_count} retries: {last_error}"
        )
        return None

    def _load_cache_from_file(self):
        """
        Load symbol cache from persistent storage file.
        """
        try:
            if self._cache_file.exists():
                with open(self._cache_file) as f:
                    cache_data = json.load(f)

                # Convert loaded data back to ContractInfo objects
                for symbol, data in cache_data.get("cache", {}).items():
                    # Skip expired entries
                    if time.time() - data["validated_at"] > self._cache_ttl:
                        continue

                    # Recreate Contract object based on asset type
                    contract = self._recreate_contract_from_data(data)
                    if contract:
                        contract_info = ContractInfo(
                            symbol=data["symbol"],
                            contract=contract,
                            asset_type=data["asset_type"],
                            exchange=data["exchange"],
                            currency=data["currency"],
                            description=data["description"],
                            validated_at=data["validated_at"],
                            trading_hours=data.get("trading_hours"),
                            head_timestamp=data.get("head_timestamp"),
                            head_timestamp_timeframes=data.get(
                                "head_timestamp_timeframes"
                            ),
                            head_timestamp_fetched_at=data.get(
                                "head_timestamp_fetched_at"
                            ),
                        )
                        self._cache[symbol] = contract_info

                # Load validated symbols (new field)
                self._validated_symbols = set(cache_data.get("validated_symbols", []))

                # For backward compatibility: assume any cached symbol was validated
                if not self._validated_symbols and self._cache:
                    self._validated_symbols = set(self._cache.keys())
                    logger.info(
                        f"Backward compatibility: marked {len(self._validated_symbols)} cached symbols as validated"
                    )

                logger.info(
                    f"Loaded {len(self._cache)} cached symbols and {len(self._validated_symbols)} validated symbols from {self._cache_file}"
                )
            else:
                logger.info(f"No existing cache file found at {self._cache_file}")

        except Exception as e:
            logger.warning(f"Failed to load cache from {self._cache_file}: {e}")
            # Continue with empty cache
            self._cache = {}
            self._validated_symbols = set()

    def _recreate_contract_from_data(self, data: dict) -> Optional[Contract]:
        """
        Recreate Contract object from cached data.

        Args:
            data: Cached contract data

        Returns:
            Contract object or None if recreation fails
        """
        try:
            asset_type = data["asset_type"]
            symbol = data["symbol"]

            if asset_type == "CASH":
                # Forex contract
                if len(symbol) == 6:
                    return Forex(pair=symbol)
                else:
                    return None
            elif asset_type == "STK":
                # Stock contract
                return Stock(
                    symbol=symbol,
                    exchange=data.get("exchange", "SMART"),
                    currency=data.get("currency", "USD"),
                )
            elif asset_type == "FUT":
                # Future contract
                return Future(symbol=symbol, exchange=data.get("exchange", "CME"))
            else:
                logger.warning(f"Unknown asset type for recreation: {asset_type}")
                return None

        except Exception as e:
            logger.warning(f"Failed to recreate contract from data: {e}")
            return None

    def _save_cache_to_file(self):
        """
        Save current symbol cache to persistent storage file.
        """
        try:
            # Prepare data for JSON serialization
            cache_data = {
                "cache": {},
                "validated_symbols": list(
                    self._validated_symbols
                ),  # Save validated symbols
                "last_updated": time.time(),
            }

            # Convert ContractInfo objects to JSON-serializable format
            for symbol, contract_info in self._cache.items():
                cache_data["cache"][symbol] = {
                    "symbol": symbol,  # Use the cache key (original requested symbol) not the IB-returned symbol
                    "asset_type": contract_info.asset_type,
                    "exchange": contract_info.exchange,
                    "currency": contract_info.currency,
                    "description": contract_info.description,
                    "validated_at": contract_info.validated_at,
                    "trading_hours": contract_info.trading_hours,
                    "head_timestamp": contract_info.head_timestamp,
                    "head_timestamp_timeframes": contract_info.head_timestamp_timeframes,
                    "head_timestamp_fetched_at": contract_info.head_timestamp_fetched_at,
                }

            # Write to temporary file first, then rename for atomic operation
            temp_file = self._cache_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(cache_data, f, indent=2)

            # Atomic rename
            temp_file.rename(self._cache_file)

            logger.debug(
                f"Saved {len(self._cache)} cached symbols to {self._cache_file}"
            )

        except Exception as e:
            logger.error(f"Failed to save cache to {self._cache_file}: {e}")
            # Debug: Show which symbol/field is causing the issue
            for symbol, contract_info in self._cache.items():
                try:
                    test_data = {
                        "symbol": symbol,
                        "trading_hours": contract_info.trading_hours,
                    }
                    json.dumps(test_data)
                except Exception as debug_e:
                    logger.error(
                        f"JSON serialization failed for symbol {symbol}: {debug_e}"
                    )
                    logger.error(
                        f"Trading hours type: {type(contract_info.trading_hours)}"
                    )
                    if hasattr(contract_info.trading_hours, "__dict__"):
                        logger.error(
                            f"Trading hours content: {contract_info.trading_hours.__dict__}"
                        )
                    break

    def get_cache_stats(self) -> dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "cached_symbols": len(self._cache),
            "validated_symbols": len(self._validated_symbols),
            "total_lookups": len(self._cache),
        }


# Backward compatibility alias
IbSymbolValidatorUnified = IbSymbolValidator
