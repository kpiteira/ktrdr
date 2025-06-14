"""
Unified IB Symbol Validator

Enhanced symbol validator that uses the new IB connection pool and pace manager.

This unified validator provides:
- Integration with IbConnectionPool for connection management
- IbPaceManager for pace violation prevention and handling
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
import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from ib_insync import Contract, Forex, Stock, Future

from ktrdr.logging import get_logger
from ktrdr.errors import DataError
from ktrdr.data.ib_connection_pool import acquire_ib_connection, PooledConnection
from ktrdr.data.ib_client_id_registry import ClientIdPurpose
from ktrdr.data.ib_pace_manager import get_pace_manager
from ktrdr.data.trading_hours import TradingHoursManager, TradingHours
from ktrdr.data.ib_trading_hours_parser import IBTradingHoursParser
from ktrdr.utils.timezone_utils import TimestampManager

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
    trading_hours: Optional[Dict] = None  # Serialized TradingHours
    head_timestamp: Optional[str] = None  # ISO format for JSON serialization
    head_timestamp_timeframes: Optional[Dict[str, str]] = (
        None  # timeframe -> ISO timestamp
    )
    head_timestamp_fetched_at: Optional[float] = (
        None  # Timestamp when head data was fetched
    )


class IbSymbolValidatorUnified:
    """
    Unified IB symbol validator using connection pool and pace manager.

    This validator provides enhanced functionality while maintaining
    compatibility with existing patterns.
    """

    def __init__(
        self, component_name: str = "symbol_validator", cache_file: Optional[str] = None
    ):
        """
        Initialize the unified symbol validator.

        Args:
            component_name: Name for this component (used in metrics and logging)
            cache_file: Optional path to cache file for persistent storage
        """
        self.component_name = component_name
        self.pace_manager = get_pace_manager()

        # Cache management
        self._cache: Dict[str, ContractInfo] = {}
        self._failed_symbols: Set[str] = set()
        self._validated_symbols: Set[str] = set()  # Permanently validated symbols
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
                from ktrdr.config.settings import get_settings

                settings = get_settings()
                data_dir = (
                    Path(settings.data_dir)
                    if hasattr(settings, "data_dir")
                    else Path("data")
                )
            except:
                data_dir = Path("data")
            self._cache_file = data_dir / "symbol_discovery_cache.json"

        # Ensure cache directory exists
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing cache from file
        self._load_cache_from_file()

        logger.info(
            f"IbSymbolValidatorUnified initialized (component: {component_name})"
        )
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
        Look up contract details from IB asynchronously.

        Args:
            contract: Contract to look up
            max_retries: Maximum number of retry attempts

        Returns:
            ContractInfo if found, None otherwise
        """
        retry_count = 0
        last_error = None

        while retry_count <= max_retries:
            try:
                # Check pace limits before making request
                await self.pace_manager.check_pace_limits_async(
                    symbol=getattr(contract, "symbol", "unknown"),
                    timeframe="contract_lookup",
                    component=self.component_name,
                    operation="contract_details",
                )

                # Use connection pool for connection management
                async with await acquire_ib_connection(
                    purpose=ClientIdPurpose.API_POOL, requested_by=self.component_name
                ) as connection:

                    ib = connection.ib

                    logger.debug(f"🔍 Requesting contract details for: {contract}")
                    logger.debug(f"   Contract type: {type(contract).__name__}")
                    logger.debug(
                        f"   Contract details: symbol={getattr(contract, 'symbol', 'N/A')}, secType={getattr(contract, 'secType', 'N/A')}, exchange={getattr(contract, 'exchange', 'N/A')}"
                    )

                    # Make IB API call with circuit breaker protection
                    self.metrics["total_validations"] += 1

                    logger.info(
                        f"🔗 Making IB contract lookup (client_id: {connection.client_id})..."
                    )
                    
                    # Make IB API call with enhanced timeout protection
                    details = await asyncio.wait_for(
                        ib.reqContractDetailsAsync(contract),
                        timeout=15.0  # 15 second timeout for contract lookup
                    )

                    logger.debug(
                        f"📋 IB returned {len(details) if details else 0} contract details"
                    )

                    if not details:
                        logger.debug(f"❌ No contract details returned for: {contract}")
                        logger.debug(
                            f"   This means IB has no security definition for this contract specification"
                        )
                        self.metrics["failed_validations"] += 1
                        return None

                    # Use first result
                    detail = details[0]
                    contract_details = detail.contract

                    logger.debug(
                        f"✅ Contract found: {contract_details.symbol} ({contract_details.secType}) on {contract_details.exchange}"
                    )
                    logger.debug(f"   Full name: {detail.longName or 'N/A'}")
                    logger.debug(f"   Currency: {contract_details.currency}")

                    # Get trading hours metadata from IB contract details
                    exchange = (
                        contract_details.primaryExchange or contract_details.exchange
                    )
                    trading_hours_dict = None

                    # Try to parse real IB trading hours first
                    trading_hours = IBTradingHoursParser.create_from_contract_details(
                        detail
                    )
                    if trading_hours:
                        trading_hours_dict = TradingHoursManager.to_dict(trading_hours)
                        logger.debug(
                            f"Added IB trading hours for {contract_details.symbol} on {exchange}"
                        )
                    else:
                        # Fall back to static trading hours if IB parsing fails
                        trading_hours = TradingHoursManager.get_trading_hours(
                            exchange, contract_details.secType
                        )
                        if trading_hours:
                            trading_hours_dict = TradingHoursManager.to_dict(
                                trading_hours
                            )
                            logger.debug(
                                f"Added static trading hours for {contract_details.symbol} on {exchange}"
                            )
                        else:
                            logger.debug(
                                f"No trading hours available for {exchange} ({contract_details.secType})"
                            )

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
                last_error = asyncio.TimeoutError(f"Contract lookup timeout for {getattr(contract, 'symbol', 'unknown')}")
                logger.warning(f"⏰ Contract lookup timeout for {getattr(contract, 'symbol', 'unknown')} (attempt {retry_count}/{max_retries})")
                
                # Wait before retry
                if retry_count < max_retries:
                    await asyncio.sleep(2.0)
                continue

            except Exception as e:
                retry_count += 1
                last_error = e

                # Handle IB errors with pace manager
                request_key = (
                    f"{getattr(contract, 'symbol', 'unknown')}:contract_lookup"
                )
                should_retry, wait_time = await self.pace_manager.handle_ib_error_async(
                    error_code=getattr(e, "errorCode", 0),
                    error_message=str(e),
                    component=self.component_name,
                    request_key=request_key,
                )

                if not should_retry or retry_count > max_retries:
                    logger.error(
                        f"❌ Giving up contract lookup after {retry_count} retries"
                    )
                    break

                # Wait before retry
                if wait_time > 0:
                    logger.info(
                        f"⏳ Waiting {wait_time}s before retry {retry_count}/{max_retries}"
                    )
                    await asyncio.sleep(wait_time)
                    self.metrics["pace_violations_handled"] += 1

                # Exponential backoff for additional delay
                backoff_delay = min(2 ** (retry_count - 1), 30)  # Cap at 30 seconds
                if backoff_delay > 0:
                    logger.info(f"⏳ Additional backoff delay: {backoff_delay}s")
                    await asyncio.sleep(backoff_delay)

                self.metrics["retries_performed"] += 1
                logger.warning(
                    f"🔄 Retrying contract lookup (attempt {retry_count}/{max_retries}): {e}"
                )

        # All retries failed
        self.metrics["failed_validations"] += 1
        logger.error(f"❌ CONTRACT LOOKUP FAILED after {retry_count} retries")
        logger.error(f"   Final error: {last_error}")
        return None

    async def validate_symbol_async(self, symbol: str) -> bool:
        """
        Validate if a symbol exists in IB's database asynchronously.

        Args:
            symbol: Symbol to validate

        Returns:
            True if symbol is valid, False otherwise
        """
        normalized = self._normalize_symbol(symbol)

        # Check cache first
        if self._is_cache_valid(normalized):
            self.metrics["cache_hits"] += 1
            return True

        # Check failed symbols cache
        if normalized in self._failed_symbols:
            return False

        # Try to get contract details
        contract_info = await self.get_contract_details_async(normalized)
        return contract_info is not None

    def validate_symbol(self, symbol: str) -> bool:
        """
        Validate if a symbol exists in IB's database (sync wrapper).

        Args:
            symbol: Symbol to validate

        Returns:
            True if symbol is valid, False otherwise
        """
        # For sync usage, just check cache and validated symbols
        normalized = self._normalize_symbol(symbol)

        # Check cache first
        if self._is_cache_valid(normalized):
            self.metrics["cache_hits"] += 1
            return True

        # Check if it was ever validated
        if normalized in self._validated_symbols:
            return True

        # Check failed symbols cache
        if normalized in self._failed_symbols:
            return False

        # For sync calls, we can't do network operations, so return based on what we know
        logger.warning(
            f"Sync validation for {symbol} - use async version for network lookup"
        )
        return False

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
                        f"🔄 Re-validating previously validated symbol: {normalized}"
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

    def get_contract_details(self, symbol: str) -> Optional[ContractInfo]:
        """
        Get contract details (sync wrapper - returns cached data only).

        Args:
            symbol: Symbol to look up

        Returns:
            ContractInfo if found in cache, None otherwise
        """
        normalized = self._normalize_symbol(symbol)

        # Check cache first
        if self._is_cache_valid(normalized):
            self.metrics["cache_hits"] += 1
            return self._cache[normalized]

        # For sync calls, we can't do network operations
        logger.warning(
            f"Sync contract details for {symbol} - use async version for network lookup"
        )
        return None

    async def _attempt_revalidation_async(self, symbol: str) -> Optional[ContractInfo]:
        """Attempt re-validation for previously validated symbol (async)."""
        try:
            contract_info = await self._attempt_validation_async(symbol)
            if contract_info:
                self._cache[symbol] = contract_info
                self._save_cache_to_file()
                logger.info(f"✅ Re-validation successful for {symbol}")
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
        # Check failed symbols cache (only for new symbols)
        if symbol in self._failed_symbols:
            logger.debug(f"Symbol {symbol} found in failed symbols cache")
            return None

        logger.info(f"🔍 Starting async symbol validation for {symbol}")

        # Attempt validation...
        contract_info = await self._attempt_validation_async(symbol)
        if contract_info:
            self._mark_symbol_validated(symbol, contract_info)
            return contract_info
        else:
            # Mark as failed (only for new symbols)
            self._failed_symbols.add(symbol)
            self._save_cache_to_file()
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
        # Remove from failed symbols if it was there
        self._failed_symbols.discard(symbol)
        # Save cache to persistent storage
        self._save_cache_to_file()
        logger.info(f"✅ Symbol {symbol} marked as permanently validated")

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
        contract_info = await self.get_contract_details_async(normalized)
        if not contract_info:
            logger.warning(
                f"Cannot fetch head timestamp for {symbol} - contract not found"
            )
            return None

        # Attempt to fetch head timestamp with retries
        retry_count = 0
        last_error = None

        while retry_count <= max_retries:
            try:
                # Check pace limits before making request
                await self.pace_manager.check_pace_limits_async(
                    symbol=symbol,
                    timeframe="head_timestamp",
                    component=self.component_name,
                    operation="head_timestamp",
                )

                # Use connection pool for connection management
                async with await acquire_ib_connection(
                    purpose=ClientIdPurpose.API_POOL, requested_by=self.component_name
                ) as connection:

                    ib = connection.ib

                    logger.info(
                        f"🔍 Requesting head timestamp for {contract_info.contract}"
                    )

                    # For forex pairs, try different whatToShow options
                    whatToShow_options = (
                        ["TRADES", "BID", "ASK", "MIDPOINT"]
                        if contract_info.asset_type == "CASH"
                        else ["TRADES"]
                    )

                    head_timestamp = None
                    for whatToShow in whatToShow_options:
                        try:
                            logger.info(
                                f"🔍 Trying head timestamp with whatToShow={whatToShow}"
                            )
                            
                            # Make IB API call with enhanced timeout protection
                            head_timestamp = await asyncio.wait_for(
                                ib.reqHeadTimeStampAsync(
                                    contract=contract_info.contract,
                                    whatToShow=whatToShow,
                                    useRTH=False,  # Include all trading hours
                                    formatDate=1,  # Return as datetime
                                ),
                                timeout=30.0  # 30 second timeout for head timestamp
                            )

                            if head_timestamp:
                                logger.info(
                                    f"🔍 SUCCESS with {whatToShow}: {head_timestamp}"
                                )
                                break
                            else:
                                logger.warning(
                                    f"🔍 No head timestamp with {whatToShow}"
                                )
                        except asyncio.TimeoutError:
                            logger.warning(f"⏰ Head timestamp timeout with {whatToShow} (30s timeout)")
                            continue
                        except Exception as e:
                            logger.warning(f"🔍 Error with {whatToShow}: {e}")
                            continue

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

                        logger.info(
                            f"📅 HEAD TIMESTAMP for {symbol}: {head_timestamp_iso}"
                        )
                        return head_timestamp_iso
                    else:
                        logger.warning(f"📅 No head timestamp available for {symbol}")
                        return None

            except Exception as e:
                retry_count += 1
                last_error = e

                # Handle IB errors with pace manager
                request_key = f"{symbol}:head_timestamp"
                should_retry, wait_time = await self.pace_manager.handle_ib_error_async(
                    error_code=getattr(e, "errorCode", 0),
                    error_message=str(e),
                    component=self.component_name,
                    request_key=request_key,
                )

                if not should_retry or retry_count > max_retries:
                    logger.error(
                        f"❌ Giving up head timestamp fetch after {retry_count} retries"
                    )
                    break

                # Wait before retry
                if wait_time > 0:
                    logger.info(
                        f"⏳ Waiting {wait_time}s before retry {retry_count}/{max_retries}"
                    )
                    await asyncio.sleep(wait_time)
                    self.metrics["pace_violations_handled"] += 1

                # Exponential backoff for additional delay
                backoff_delay = min(2 ** (retry_count - 1), 30)  # Cap at 30 seconds
                if backoff_delay > 0:
                    logger.info(f"⏳ Additional backoff delay: {backoff_delay}s")
                    await asyncio.sleep(backoff_delay)

                self.metrics["retries_performed"] += 1
                logger.warning(
                    f"🔄 Retrying head timestamp fetch (attempt {retry_count}/{max_retries}): {e}"
                )

        # All retries failed
        logger.error(
            f"Failed to fetch head timestamp for {symbol} after {retry_count} retries: {last_error}"
        )
        return None

    def get_head_timestamp(
        self, symbol: str, timeframe: Optional[str] = None
    ) -> Optional[str]:
        """
        Get cached head timestamp for a symbol (sync version - cache only).

        Args:
            symbol: Symbol to get head timestamp for
            timeframe: Optional specific timeframe to check

        Returns:
            ISO formatted earliest timestamp string or None if unavailable
        """
        normalized = self._normalize_symbol(symbol)

        # Try to get from cache first
        if normalized in self._cache:
            contract_info = self._cache[normalized]

            # Try timeframe-specific timestamp first
            if timeframe and contract_info.head_timestamp_timeframes:
                timeframe_timestamp = contract_info.head_timestamp_timeframes.get(
                    timeframe
                )
                if timeframe_timestamp:
                    return timeframe_timestamp

            # Fall back to default head timestamp
            if contract_info.head_timestamp:
                return contract_info.head_timestamp

        # For sync calls, we can't do network operations
        logger.warning(
            f"Sync head timestamp for {symbol} - use async version for network lookup"
        )
        return None

    def validate_date_range_against_head_timestamp(
        self, symbol: str, start_date: datetime, timeframe: Optional[str] = None
    ) -> tuple[bool, Optional[str], Optional[datetime]]:
        """
        Validate if a requested start date is within available data range.

        Args:
            symbol: Symbol to validate
            start_date: Requested start date
            timeframe: Optional timeframe (currently uses default)

        Returns:
            Tuple of (is_valid, error_message, suggested_start_date)
        """
        head_timestamp_str = self.get_head_timestamp(symbol, timeframe)

        if not head_timestamp_str:
            # No head timestamp available, allow the request
            logger.debug(f"📅 No head timestamp for {symbol}, allowing request")
            return True, None, None

        try:
            # Parse head timestamp
            head_timestamp = datetime.fromisoformat(
                head_timestamp_str.replace("Z", "+00:00")
            )

            # Compare dates
            if start_date < head_timestamp:
                days_before = (head_timestamp - start_date).days

                # Always suggest adjustment to head timestamp instead of failing
                if days_before > 7:  # More than a week difference, warn user
                    warning_msg = f"Data for {symbol} starts from {head_timestamp.date()}, requested from {start_date.date()} ({days_before} days earlier)"
                    logger.warning(f"📅 VALIDATION ADJUSTED: {warning_msg}")
                    logger.warning(
                        f"📅 Adjusting start date to earliest available: {head_timestamp.date()}"
                    )
                    return True, warning_msg, head_timestamp
                else:
                    # Small gap, just adjust quietly
                    logger.info(
                        f"📅 VALIDATION ADJUSTED: Moving start date from {start_date.date()} to {head_timestamp.date()}"
                    )
                    return True, None, head_timestamp

            # Request is within available range
            return True, None, None

        except Exception as e:
            logger.warning(f"Error validating date range for {symbol}: {e}")
            # Allow request if validation fails
            return True, None, None

    async def batch_validate_async(
        self, symbols: List[str], max_concurrent: int = 3
    ) -> Dict[str, bool]:
        """
        Validate multiple symbols in batch asynchronously.

        Args:
            symbols: List of symbols to validate
            max_concurrent: Maximum concurrent validations

        Returns:
            Dictionary mapping symbol to validation result
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def validate_with_limit(symbol):
            async with semaphore:
                try:
                    result = await self.validate_symbol_async(symbol)
                    return symbol, result
                except Exception as e:
                    logger.error(f"Error validating symbol {symbol}: {e}")
                    return symbol, False

        # Execute all validations concurrently
        logger.info(
            f"🚀 Starting concurrent validation for {len(symbols)} symbols (max_concurrent={max_concurrent})"
        )
        tasks = [validate_with_limit(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)

        successful_count = sum(1 for _, result in results if result)
        logger.info(
            f"✅ Concurrent validation completed: {successful_count}/{len(symbols)} successful"
        )

        return dict(results)

    def batch_validate(self, symbols: List[str]) -> Dict[str, bool]:
        """
        Validate multiple symbols in batch (sync version - cache only).

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

    async def batch_get_contracts_async(
        self, symbols: List[str], max_concurrent: int = 3
    ) -> Dict[str, Optional[ContractInfo]]:
        """
        Get contract details for multiple symbols in batch asynchronously.

        Args:
            symbols: List of symbols to look up
            max_concurrent: Maximum concurrent lookups

        Returns:
            Dictionary mapping symbol to ContractInfo (or None if failed)
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def get_contract_with_limit(symbol):
            async with semaphore:
                try:
                    result = await self.get_contract_details_async(symbol)
                    return symbol, result
                except Exception as e:
                    logger.error(f"Error getting contract details for {symbol}: {e}")
                    return symbol, None

        # Execute all lookups concurrently
        logger.info(
            f"🚀 Starting concurrent contract lookup for {len(symbols)} symbols (max_concurrent={max_concurrent})"
        )
        tasks = [get_contract_with_limit(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)

        successful_count = sum(1 for _, result in results if result is not None)
        logger.info(
            f"✅ Concurrent contract lookup completed: {successful_count}/{len(symbols)} successful"
        )

        return dict(results)

    def get_metrics(self) -> Dict[str, any]:
        """Get comprehensive validator metrics."""
        metrics = self.metrics.copy()

        # Calculate success rate
        total = metrics["total_validations"]
        if total > 0:
            metrics["success_rate"] = metrics["successful_validations"] / total
        else:
            metrics["success_rate"] = 0.0

        # Get pace manager statistics for this component
        pace_stats = self.pace_manager.get_pace_statistics()
        component_pace_stats = pace_stats.get("component_statistics", {}).get(
            self.component_name, {}
        )

        # Merge pace statistics
        metrics.update(
            {
                "pace_requests": component_pace_stats.get("total_requests", 0),
                "pace_violations": component_pace_stats.get("pace_violations", 0),
                "pace_wait_time": component_pace_stats.get("total_wait_time", 0.0),
                "component_name": self.component_name,
            }
        )

        return metrics

    def reset_metrics(self):
        """Reset validator metrics."""
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
        logger.info(f"Reset metrics for {self.component_name}")

    def _load_cache_from_file(self):
        """
        Load symbol cache from persistent storage file.
        """
        try:
            if self._cache_file.exists():
                with open(self._cache_file, "r") as f:
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

                # Load failed symbols
                self._failed_symbols = set(cache_data.get("failed_symbols", []))

                # Load validated symbols (new field)
                self._validated_symbols = set(cache_data.get("validated_symbols", []))

                # For backward compatibility: assume any cached symbol was validated
                if not self._validated_symbols and self._cache:
                    self._validated_symbols = set(self._cache.keys())
                    logger.info(
                        f"Backward compatibility: marked {len(self._validated_symbols)} cached symbols as validated"
                    )

                logger.info(
                    f"Loaded {len(self._cache)} cached symbols, {len(self._validated_symbols)} validated symbols, and {len(self._failed_symbols)} failed symbols from {self._cache_file}"
                )
            else:
                logger.info(f"No existing cache file found at {self._cache_file}")

        except Exception as e:
            logger.warning(f"Failed to load cache from {self._cache_file}: {e}")
            # Continue with empty cache
            self._cache = {}
            self._failed_symbols = set()
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
                "failed_symbols": list(self._failed_symbols),
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

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "cached_symbols": len(self._cache),
            "validated_symbols": len(self._validated_symbols),
            "failed_symbols": len(self._failed_symbols),
            "total_lookups": len(self._cache) + len(self._failed_symbols),
        }

    def clear_cache(self):
        """Clear all cached results."""
        self._cache.clear()
        self._failed_symbols.clear()
        self._validated_symbols.clear()
        # Clear persistent cache file
        try:
            if self._cache_file.exists():
                self._cache_file.unlink()
                logger.info(f"Deleted persistent cache file: {self._cache_file}")
        except Exception as e:
            logger.warning(f"Failed to delete cache file {self._cache_file}: {e}")
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


# Convenience functions for simple usage
async def validate_symbol_unified(
    symbol: str, component_name: str = "simple_validation"
) -> bool:
    """
    Simple function to validate a symbol using unified architecture.

    Usage:
        is_valid = await validate_symbol_unified("AAPL")
    """
    validator = IbSymbolValidatorUnified(component_name=component_name)
    return await validator.validate_symbol_async(symbol)


async def get_contract_details_unified(
    symbol: str, component_name: str = "simple_contract_lookup"
) -> Optional[ContractInfo]:
    """
    Simple function to get contract details using unified architecture.

    Usage:
        contract_info = await get_contract_details_unified("AAPL")
    """
    validator = IbSymbolValidatorUnified(component_name=component_name)
    return await validator.get_contract_details_async(symbol)


# Backward compatibility alias
IbSymbolValidator = IbSymbolValidatorUnified
