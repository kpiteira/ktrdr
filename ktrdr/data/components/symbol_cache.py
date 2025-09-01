"""
Backend Symbol Cache Component for DataLoadingOrchestrator.

This component provides intelligent symbol validation caching at the data management
layer to reduce redundant host service calls while maintaining the same cancellation
patterns as data loading.
"""

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from ktrdr import get_logger
from ktrdr.ib import ValidationResult

logger = get_logger(__name__)


@dataclass
class CachedSymbolInfo:
    """Cached symbol validation information."""
    validation_result: Dict[str, Any]  # Serialized ValidationResult
    cached_at: float
    ttl_seconds: int = 86400 * 30  # 30 days like IB cache
    
    def is_expired(self) -> bool:
        """Check if cached data has expired."""
        return time.time() - self.cached_at > self.ttl_seconds
        
    def to_validation_result(self) -> ValidationResult:
        """Convert back to ValidationResult object."""
        data = self.validation_result
        return ValidationResult(
            is_valid=data["is_valid"],
            symbol=data["symbol"],
            error_message=data.get("error_message"),
            contract_info=data.get("contract_info"),
            head_timestamps=data.get("head_timestamps"),
            suggested_symbol=data.get("suggested_symbol")
        )


class SymbolCache:
    """Backend symbol validation cache managed by DataManager layer."""
    
    def __init__(self, cache_file: str = "data/backend_symbol_cache.json"):
        """Initialize symbol cache with persistent storage."""
        self._cache: Dict[str, CachedSymbolInfo] = {}
        self._cache_file = Path(cache_file)
        self._load_cache()
        logger.info(f"💾 SymbolCache initialized with {len(self._cache)} cached symbols")
    
    def get(self, symbol: str) -> Optional[CachedSymbolInfo]:
        """Get cached symbol info if valid and not expired."""
        symbol_key = symbol.upper()
        info = self._cache.get(symbol_key)
        if info and not info.is_expired():
            logger.debug(f"💾 Cache hit for {symbol_key}")
            return info
        elif info:
            logger.debug(f"💾 Cache expired for {symbol_key}")
            # Remove expired entry
            del self._cache[symbol_key]
            self._save_cache()
        else:
            logger.debug(f"💾 Cache miss for {symbol_key}")
        return None
    
    def store(self, symbol: str, validation_result: ValidationResult) -> None:
        """Cache validation result with TTL."""
        symbol_key = symbol.upper()
        
        # Convert ValidationResult to serializable format
        serialized_result = {
            "is_valid": validation_result.is_valid,
            "symbol": validation_result.symbol,
            "error_message": validation_result.error_message,
            "contract_info": validation_result.contract_info,
            "head_timestamps": validation_result.head_timestamps,
            "suggested_symbol": validation_result.suggested_symbol
        }
        
        info = CachedSymbolInfo(
            validation_result=serialized_result,
            cached_at=time.time()
        )
        
        self._cache[symbol_key] = info
        self._save_cache()
        logger.info(f"💾 Cached validation result for {symbol_key}")
    
    def clear(self) -> None:
        """Clear all cached symbols."""
        self._cache.clear()
        self._save_cache()
        logger.info("💾 Cleared all cached symbols")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = len(self._cache)
        expired = sum(1 for info in self._cache.values() if info.is_expired())
        return {
            "cached_symbols": total,
            "expired_symbols": expired,
            "valid_symbols": total - expired,
            "cache_file": str(self._cache_file)
        }
    
    def _load_cache(self) -> None:
        """Load cache from persistent storage."""
        if not self._cache_file.exists():
            logger.debug(f"💾 Cache file {self._cache_file} does not exist, starting fresh")
            return
        
        try:
            with open(self._cache_file, 'r') as f:
                data = json.load(f)
            
            for symbol, cached_data in data.items():
                self._cache[symbol] = CachedSymbolInfo(
                    validation_result=cached_data["validation_result"],
                    cached_at=cached_data["cached_at"],
                    ttl_seconds=cached_data.get("ttl_seconds", 86400 * 30)
                )
            
            logger.info(f"💾 Loaded {len(self._cache)} symbols from cache file")
            
        except Exception as e:
            logger.error(f"💾 Failed to load cache from {self._cache_file}: {e}")
            self._cache = {}
    
    def _save_cache(self) -> None:
        """Save cache to persistent storage."""
        try:
            # Ensure directory exists
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to serializable format
            data = {}
            for symbol, info in self._cache.items():
                data[symbol] = asdict(info)
            
            with open(self._cache_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"💾 Saved {len(self._cache)} symbols to cache file")
            
        except Exception as e:
            logger.error(f"💾 Failed to save cache to {self._cache_file}: {e}")