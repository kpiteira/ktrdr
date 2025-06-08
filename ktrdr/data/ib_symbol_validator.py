"""
IB Symbol Validator for Interactive Brokers contract lookups.

This module provides symbol validation and contract lookup functionality
with priority order support for different asset types (CASH, STK, FUT).
"""

import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, asdict
from ib_insync import Contract, Forex, Stock, Future

from ktrdr.logging import get_logger
from ktrdr.data.ib_connection_sync import IbConnectionSync
from ktrdr.data.trading_hours import TradingHoursManager, TradingHours

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
    """

    symbol: str
    contract: Contract
    asset_type: str
    exchange: str
    currency: str
    description: str
    validated_at: float
    trading_hours: Optional[Dict] = None  # Serialized TradingHours


class IbSymbolValidator:
    """
    IB symbol validation and contract lookup with caching.

    This class provides methods to validate symbols against IB's contract
    database with priority ordering (forex first, then stocks, then futures).
    Results are cached to avoid repeated lookups.
    """

    def __init__(self, connection: Optional[IbConnectionSync] = None, cache_file: Optional[str] = None):
        """
        Initialize the symbol validator.

        Args:
            connection: Optional IB connection. If not provided, will create one.
            cache_file: Optional path to cache file for persistent storage
        """
        self.connection = connection
        self._cache: Dict[str, ContractInfo] = {}
        self._failed_symbols: Set[str] = set()
        self._validated_symbols: Set[str] = set()  # Permanently validated symbols
        self._cache_ttl = 86400 * 30  # 30 days for re-validation (was 1 hour)
        
        # Set up persistent cache file
        if cache_file:
            self._cache_file = Path(cache_file)
        else:
            # Default cache file in data directory
            try:
                from ktrdr.config.settings import get_settings
                settings = get_settings()
                data_dir = Path(settings.data_dir) if hasattr(settings, 'data_dir') else Path("data")
            except:
                data_dir = Path("data")
            self._cache_file = data_dir / "symbol_discovery_cache.json"
        
        # Ensure cache directory exists
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing cache from file
        self._load_cache_from_file()
        
        logger.info(f"IbSymbolValidator initialized with cache file: {self._cache_file}")

    def _ensure_connection(self) -> bool:
        """
        Ensure we have a valid IB connection.

        Returns:
            True if connection is available, False otherwise
        """
        if not self.connection:
            logger.warning("No IB connection provided to symbol validator")
            return False

        try:
            is_connected = self.connection.is_connected()
            logger.debug(f"IB connection status check: {is_connected}")
            
            if not is_connected:
                logger.warning("IB connection is not active - attempting to reconnect")
                # Try to reconnect
                try:
                    self.connection.ensure_connection()
                    is_connected = self.connection.is_connected()
                    logger.info(f"Reconnection attempt result: {is_connected}")
                except Exception as e:
                    logger.error(f"Failed to reconnect IB: {e}")
                    return False
            
            if is_connected:
                logger.debug("IB connection is available for symbol validation")
                return True
            else:
                logger.warning("IB connection is still not active after reconnection attempt")
                return False
                
        except Exception as e:
            logger.error(f"Error checking IB connection status: {e}")
            return False

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
                logger.info(f"❌ No connection available for contract lookup: {contract}")
                return None

            # Request contract details using async method to avoid event loop conflicts
            logger.info(f"🔍 Requesting contract details for: {contract}")
            logger.info(f"   Contract type: {type(contract).__name__}")
            logger.info(f"   Contract details: symbol={getattr(contract, 'symbol', 'N/A')}, secType={getattr(contract, 'secType', 'N/A')}, exchange={getattr(contract, 'exchange', 'N/A')}")
            
            # Use synchronous method but run it in a separate thread to avoid event loop conflicts
            details = self._run_sync_in_thread(contract)
            
            logger.info(f"📋 IB returned {len(details) if details else 0} contract details")

            if not details:
                logger.info(f"❌ No contract details returned for: {contract}")
                logger.info(f"   This means IB has no security definition for this contract specification")
                return None

            # Use first result
            detail = details[0]
            contract_details = detail.contract
            
            logger.info(f"✅ Contract found: {contract_details.symbol} ({contract_details.secType}) on {contract_details.exchange}")
            logger.info(f"   Full name: {detail.longName or 'N/A'}")
            logger.info(f"   Currency: {contract_details.currency}")

            # Get trading hours metadata
            exchange = contract_details.primaryExchange or contract_details.exchange
            trading_hours = TradingHoursManager.get_trading_hours(exchange, contract_details.secType)
            trading_hours_dict = None
            if trading_hours:
                trading_hours_dict = TradingHoursManager.to_dict(trading_hours)
                logger.debug(f"Added trading hours for {contract_details.symbol} on {exchange}")
            else:
                logger.debug(f"No trading hours found for {exchange} ({contract_details.secType})")

            return ContractInfo(
                symbol=contract_details.symbol,
                contract=contract_details,
                asset_type=contract_details.secType,
                exchange=exchange,
                currency=contract_details.currency,
                description=detail.longName or detail.contractMonth or "",
                validated_at=time.time(),
                trading_hours=trading_hours_dict,
            )

        except Exception as e:
            logger.error(f"❌ Contract lookup failed for {contract}: {e}")
            logger.error(f"   Exception type: {type(e).__name__}")
            logger.error(f"   Full error: {str(e)}")
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
        Get contract details with protected re-validation logic.
        Never marks previously validated symbols as failed.

        Args:
            symbol: Symbol to look up

        Returns:
            ContractInfo if found, None otherwise
        """
        normalized = self._normalize_symbol(symbol)

        # Check if symbol was ever validated successfully
        if normalized in self._validated_symbols:
            # Previously validated - NEVER mark as failed, only re-validate on TTL
            if self._is_cache_valid(normalized):
                return self._cache[normalized]
            else:
                # Cache expired - attempt re-validation but don't fail on connection issues
                logger.info(f"🔄 Re-validating previously validated symbol: {normalized}")
                return self._attempt_revalidation(normalized)
        else:
            # Never validated before - use normal validation with failure tracking
            return self._normal_validation(normalized)

    def _attempt_revalidation(self, symbol: str) -> Optional[ContractInfo]:
        """Attempt re-validation for previously validated symbol."""
        try:
            if not self._ensure_connection():
                logger.warning(f"Re-validation failed for {symbol} (no connection), keeping as valid")
                return None
            
            contract_info = self._attempt_validation(symbol)
            if contract_info:
                self._cache[symbol] = contract_info
                self._save_cache_to_file()
                logger.info(f"✅ Re-validation successful for {symbol}")
                return contract_info
            else:
                # Connection issue - return None but DON'T mark as failed
                logger.warning(f"Re-validation failed for {symbol} (connection issue), keeping as valid")
                return None
        except Exception as e:
            logger.warning(f"Re-validation error for {symbol}: {e}")
            return None

    def _normal_validation(self, symbol: str) -> Optional[ContractInfo]:
        """Normal validation for never-before-validated symbols."""
        # Check failed symbols cache (only for new symbols)
        if symbol in self._failed_symbols:
            logger.debug(f"Symbol {symbol} found in failed symbols cache")
            return None

        logger.info(f"🔍 Starting symbol validation for {symbol}")
        if not self._ensure_connection():
            logger.warning(f"Symbol validation skipped for {symbol} - no IB connection available")
            return None
        
        logger.info(f"✅ IB connection confirmed, proceeding with contract validation for {symbol}")

        # Attempt validation...
        contract_info = self._attempt_validation(symbol)
        if contract_info:
            self._mark_symbol_validated(symbol, contract_info)
            return contract_info
        else:
            # Mark as failed (only for new symbols)
            self._failed_symbols.add(symbol)
            self._save_cache_to_file()
            logger.warning(f"Symbol validation failed for {symbol}")
            return None

    def _attempt_validation(self, symbol: str) -> Optional[ContractInfo]:
        """Attempt validation with IB contract lookup."""
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

                logger.debug(f"Created {asset_type} contract for {symbol}, performing lookup...")
                contract_info = self._lookup_contract(contract)
                if contract_info:
                    logger.info(f"Validated {symbol} as {asset_type}: {contract_info.description}")
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

    def _load_cache_from_file(self):
        """
        Load symbol cache from persistent storage file.
        """
        try:
            if self._cache_file.exists():
                with open(self._cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                # Convert loaded data back to ContractInfo objects
                for symbol, data in cache_data.get('cache', {}).items():
                    # Skip expired entries
                    if time.time() - data['validated_at'] > self._cache_ttl:
                        continue
                    
                    # Recreate Contract object based on asset type
                    contract = self._recreate_contract_from_data(data)
                    if contract:
                        contract_info = ContractInfo(
                            symbol=data['symbol'],
                            contract=contract,
                            asset_type=data['asset_type'],
                            exchange=data['exchange'],
                            currency=data['currency'],
                            description=data['description'],
                            validated_at=data['validated_at'],
                            trading_hours=data.get('trading_hours')
                        )
                        self._cache[symbol] = contract_info
                
                # Load failed symbols
                self._failed_symbols = set(cache_data.get('failed_symbols', []))
                
                # Load validated symbols (new field)
                self._validated_symbols = set(cache_data.get('validated_symbols', []))
                
                # For backward compatibility: assume any cached symbol was validated
                if not self._validated_symbols and self._cache:
                    self._validated_symbols = set(self._cache.keys())
                    logger.info(f"Backward compatibility: marked {len(self._validated_symbols)} cached symbols as validated")
                
                logger.info(f"Loaded {len(self._cache)} cached symbols, {len(self._validated_symbols)} validated symbols, and {len(self._failed_symbols)} failed symbols from {self._cache_file}")
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
            asset_type = data['asset_type']
            symbol = data['symbol']
            
            if asset_type == 'CASH':
                # Forex contract
                if len(symbol) == 6:
                    return Forex(pair=symbol)
                else:
                    return None
            elif asset_type == 'STK':
                # Stock contract
                return Stock(symbol=symbol, exchange=data.get('exchange', 'SMART'), currency=data.get('currency', 'USD'))
            elif asset_type == 'FUT':
                # Future contract
                return Future(symbol=symbol, exchange=data.get('exchange', 'CME'))
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
                'cache': {},
                'failed_symbols': list(self._failed_symbols),
                'validated_symbols': list(self._validated_symbols),  # Save validated symbols
                'last_updated': time.time()
            }
            
            # Convert ContractInfo objects to JSON-serializable format
            for symbol, contract_info in self._cache.items():
                cache_data['cache'][symbol] = {
                    'symbol': symbol,  # Use the cache key (original requested symbol) not the IB-returned symbol
                    'asset_type': contract_info.asset_type,
                    'exchange': contract_info.exchange,
                    'currency': contract_info.currency,
                    'description': contract_info.description,
                    'validated_at': contract_info.validated_at,
                    'trading_hours': contract_info.trading_hours
                }
            
            # Write to temporary file first, then rename for atomic operation
            temp_file = self._cache_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            # Atomic rename
            temp_file.rename(self._cache_file)
            
            logger.debug(f"Saved {len(self._cache)} cached symbols to {self._cache_file}")
            
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
    
    def _run_sync_in_thread(self, contract):
        """Run contract lookup in a separate thread to avoid event loop conflicts."""
        import threading
        import time
        
        result = {"details": None, "error": None, "completed": False}
        
        def thread_lookup():
            """Lookup function to run in separate thread."""
            try:
                # Create a new temporary IB connection just for this lookup
                from ib_insync import IB
                import asyncio
                
                # Create a new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Create IB instance
                ib = IB()
                
                async def do_lookup():
                    """Async lookup function."""
                    try:
                        # Connect to IB using same config as the main connection
                        await ib.connectAsync(
                            self.connection.config.host,
                            self.connection.config.port,
                            clientId=self.connection.config.client_id + 1000,  # Use different client ID
                            readonly=True,
                            timeout=15
                        )
                        
                        # Request contract details
                        logger.info(f"🔍 Thread: Requesting contract details for {contract}")
                        details = await ib.reqContractDetailsAsync(contract)
                        logger.info(f"🔍 Thread: Got {len(details) if details else 0} contract details")
                        
                        result["details"] = details
                        
                    except Exception as e:
                        logger.warning(f"Thread contract lookup failed: {e}")
                        result["error"] = str(e)
                    finally:
                        # Always disconnect
                        try:
                            if ib.isConnected():
                                ib.disconnect()
                        except:
                            pass
                
                # Run the lookup
                loop.run_until_complete(do_lookup())
                result["completed"] = True
                
            except Exception as e:
                result["error"] = str(e)
                result["completed"] = True
            finally:
                # Clean up the loop
                try:
                    loop.close()
                    asyncio.set_event_loop(None)
                except:
                    pass
        
        # Run in thread with timeout
        thread = threading.Thread(target=thread_lookup, daemon=True)
        thread.start()
        
        # Wait for completion with timeout
        timeout_seconds = 30
        start_time = time.time()
        
        while not result["completed"] and (time.time() - start_time) < timeout_seconds:
            time.sleep(0.1)
        
        if not result["completed"]:
            logger.error("Contract lookup timed out")
            return None
        
        if result["error"]:
            logger.error(f"Contract lookup failed: {result['error']}")
            return None
        
        return result["details"]
