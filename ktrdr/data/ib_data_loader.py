"""
Unified IB data loading operations.

This module consolidates all IB data fetching, progressive loading, and data merging
logic into a single, reusable component to eliminate code duplication across the codebase.
"""

import time
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

from ktrdr.data.ib_connection_strategy import IbConnectionStrategy
from ktrdr.data.ib_data_fetcher_sync import IbDataFetcherSync
from ktrdr.data.local_data_loader import LocalDataLoader
from ktrdr.config.ib_limits import IbLimitsRegistry
from ktrdr.data.data_quality_validator import DataQualityValidator
from ktrdr.logging import get_logger
from ktrdr.errors import DataError, ConnectionError

logger = get_logger(__name__)


class IbDataLoader:
    """
    Single source of truth for all IB data loading operations.
    
    Replaces duplicate logic in:
    - GapFillerService._fill_gap() and _fill_gap_progressive()
    - IbService._fetch_data_chunk() and _load_data_progressive()
    - DataManager._merge_and_fill_gaps() IB logic
    """
    
    def __init__(self, 
                 connection_strategy: IbConnectionStrategy,
                 data_dir: Optional[str] = None,
                 validate_data: bool = True):
        """
        Initialize IB data loader.
        
        Args:
            connection_strategy: Strategy for managing IB connections
            data_dir: Directory for local data storage (optional)
            validate_data: Whether to validate data quality (default: True)
        """
        self.connection_strategy = connection_strategy
        self.data_dir = Path(data_dir) if data_dir else None
        self.validate_data = validate_data
        
        # Initialize data quality validator if requested
        self.validator = DataQualityValidator(auto_correct=True) if validate_data else None
        
        # Initialize local data loader if data directory provided
        self.local_loader = LocalDataLoader(str(self.data_dir)) if self.data_dir else None
        
        # Performance tracking
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_bars_fetched": 0,
            "total_execution_time": 0.0,
            "progressive_loads": 0,
            "chunks_processed": 0
        }
    
    def load_data_range(self, 
                       symbol: str, 
                       timeframe: str, 
                       start: datetime, 
                       end: datetime,
                       operation_type: str = "api_call") -> pd.DataFrame:
        """
        Load data for a specific date range using single IB request.
        
        This method replaces:
        - GapFillerService._fill_gap()
        - IbService._fetch_data_chunk()
        - Direct IB fetching in DataManager
        
        Args:
            symbol: Trading symbol (e.g., 'AAPL')
            timeframe: Data timeframe (e.g., '1h', '1d')
            start: Start datetime (timezone-aware)
            end: End datetime (timezone-aware)
            operation_type: Type of operation for connection allocation
            
        Returns:
            DataFrame with OHLCV data, empty if no data available
            
        Raises:
            DataError: If data fetching fails
            ConnectionError: If IB connection fails
        """
        start_time = time.time()
        
        try:
            # Validate date range doesn't exceed IB limits
            duration = end - start
            max_duration = IbLimitsRegistry.get_duration_limit(timeframe)
            
            if duration > max_duration:
                raise DataError(
                    f"Date range {duration} exceeds IB limit {max_duration} for {timeframe}. "
                    f"Use load_progressive() for larger ranges."
                )
            
            # Get IB connection for this operation
            connection = self.connection_strategy.get_connection_for_operation(operation_type)
            
            # Create fetcher
            fetcher = IbDataFetcherSync(connection)
            
            # Fetch data from IB
            logger.info(f"Fetching {symbol} {timeframe} from {start} to {end}")
            
            data = fetcher.fetch_historical_data(symbol, timeframe, start, end)
            
            # Update stats
            self.stats["total_requests"] += 1
            bars_fetched = len(data) if data is not None else 0
            self.stats["total_bars_fetched"] += bars_fetched
            
            if data is not None and not data.empty:
                self.stats["successful_requests"] += 1
                
                # Validate data quality if requested
                if self.validator:
                    data, quality_report = self.validator.validate_data(data, symbol, timeframe)
                    if len(quality_report.issues) > 0:
                        logger.warning(f"Data quality issues corrected: {len(quality_report.issues)}")
                
                logger.info(f"Successfully fetched {len(data)} bars for {symbol} {timeframe}")
                return data
            else:
                self.stats["failed_requests"] += 1
                logger.warning(f"No data returned for {symbol} {timeframe} from {start} to {end}")
                return pd.DataFrame()
                
        except Exception as e:
            self.stats["failed_requests"] += 1
            logger.error(f"Failed to fetch {symbol} {timeframe}: {e}")
            raise DataError(f"IB data fetch failed: {e}") from e
            
        finally:
            execution_time = time.time() - start_time
            self.stats["total_execution_time"] += execution_time
            logger.debug(f"Data fetch completed in {execution_time:.2f}s")
    
    def load_progressive(self, 
                        symbol: str, 
                        timeframe: str, 
                        start: datetime, 
                        end: datetime,
                        operation_type: str = "api_call") -> pd.DataFrame:
        """
        Load data for large date ranges using progressive chunking.
        
        This method replaces:
        - GapFillerService._fill_gap_progressive()
        - IbService._load_data_progressive()
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start: Start datetime (timezone-aware)
            end: End datetime (timezone-aware)
            operation_type: Type of operation for connection allocation
            
        Returns:
            Combined DataFrame with all chunks, empty if no data available
            
        Raises:
            DataError: If progressive loading fails
        """
        start_time = time.time()
        
        try:
            # Calculate chunks needed
            total_duration = end - start
            num_chunks = IbLimitsRegistry.calculate_progressive_chunks(timeframe, total_duration)
            
            if num_chunks == 1:
                # Single chunk, use regular load
                return self.load_data_range(symbol, timeframe, start, end, operation_type)
            
            logger.info(f"Progressive loading {symbol} {timeframe}: {num_chunks} chunks for {total_duration}")
            
            # Calculate chunk size
            max_duration = IbLimitsRegistry.get_duration_limit(timeframe)
            chunk_duration = min(max_duration, total_duration / num_chunks)
            
            # Collect all chunks
            all_chunks = []
            current_start = start
            chunk_delay = IbLimitsRegistry.get_safe_delay("progressive_chunk_delay")
            
            for chunk_idx in range(num_chunks):
                # Calculate chunk end time
                chunk_end = min(current_start + chunk_duration, end)
                
                if chunk_end <= current_start:
                    break
                
                try:
                    logger.debug(f"Loading chunk {chunk_idx + 1}/{num_chunks}: {current_start} to {chunk_end}")
                    
                    # Load chunk
                    chunk_data = self.load_data_range(symbol, timeframe, current_start, chunk_end, operation_type)
                    
                    if not chunk_data.empty:
                        all_chunks.append(chunk_data)
                        logger.debug(f"Chunk {chunk_idx + 1} loaded: {len(chunk_data)} bars")
                    else:
                        logger.warning(f"Chunk {chunk_idx + 1} returned no data")
                    
                    # Update stats
                    self.stats["chunks_processed"] += 1
                    
                    # Move to next chunk
                    current_start = chunk_end
                    
                    # Add delay between chunks to respect IB pacing
                    if chunk_idx < num_chunks - 1:  # Don't delay after last chunk
                        time.sleep(chunk_delay)
                        
                except Exception as e:
                    logger.error(f"Failed to load chunk {chunk_idx + 1}: {e}")
                    # Continue with other chunks rather than failing completely
                    current_start = chunk_end
                    continue
            
            # Combine all chunks
            if all_chunks:
                combined_data = pd.concat(all_chunks, ignore_index=False)
                combined_data = combined_data.sort_index()
                
                # Remove any duplicate timestamps
                combined_data = combined_data[~combined_data.index.duplicated(keep='last')]
                
                self.stats["progressive_loads"] += 1
                
                logger.info(f"Progressive loading completed: {len(combined_data)} total bars from {len(all_chunks)} chunks")
                return combined_data
            else:
                logger.warning(f"Progressive loading failed: no chunks returned data")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Progressive loading failed for {symbol} {timeframe}: {e}")
            raise DataError(f"Progressive loading failed: {e}") from e
            
        finally:
            execution_time = time.time() - start_time
            self.stats["total_execution_time"] += execution_time
            logger.debug(f"Progressive loading completed in {execution_time:.2f}s")
    
    def merge_and_save_data(self, 
                           symbol: str, 
                           timeframe: str, 
                           existing_data: Optional[pd.DataFrame], 
                           new_data: pd.DataFrame,
                           save_to_file: bool = True) -> pd.DataFrame:
        """
        Merge new IB data with existing data and optionally save to CSV.
        
        This method replaces:
        - GapFillerService._save_data_to_csv()
        - IbService._save_data_to_csv() and _merge_and_save_data()
        - DataManager merge logic
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            existing_data: Existing DataFrame (can be None/empty)
            new_data: New data from IB
            save_to_file: Whether to save merged data to CSV file
            
        Returns:
            Merged DataFrame with proper timezone handling
            
        Raises:
            DataError: If merging fails
        """
        try:
            if new_data.empty:
                logger.debug("No new data to merge")
                return existing_data if existing_data is not None else pd.DataFrame()
            
            # Ensure new data has timezone-aware index
            if new_data.index.tz is None:
                new_data.index = new_data.index.tz_localize('UTC')
            elif new_data.index.tz != timezone.utc:
                new_data.index = new_data.index.tz_convert('UTC')
            
            # Handle existing data
            if existing_data is None or existing_data.empty:
                merged_data = new_data.copy()
                logger.debug(f"No existing data, using new data: {len(merged_data)} bars")
            else:
                # Ensure existing data has timezone-aware index
                if existing_data.index.tz is None:
                    existing_data.index = existing_data.index.tz_localize('UTC')
                elif existing_data.index.tz != timezone.utc:
                    existing_data.index = existing_data.index.tz_convert('UTC')
                
                # Combine data
                merged_data = pd.concat([existing_data, new_data])
                
                # Remove duplicates (keep newer data)
                merged_data = merged_data[~merged_data.index.duplicated(keep='last')]
                
                # Sort by index
                merged_data = merged_data.sort_index()
                
                logger.debug(f"Merged data: {len(existing_data)} existing + {len(new_data)} new = {len(merged_data)} total")
            
            # Validate merged data if validator available
            if self.validator and not merged_data.empty:
                merged_data, quality_report = self.validator.validate_data(merged_data, symbol, timeframe)
                if len(quality_report.issues) > 0:
                    logger.warning(f"Quality issues in merged data corrected: {len(quality_report.issues)}")
            
            # Save to file if requested and local loader available
            if save_to_file and self.local_loader and not merged_data.empty:
                try:
                    self.local_loader.save(merged_data, symbol, timeframe)
                    logger.debug(f"Saved merged data to file: {symbol}_{timeframe}.csv")
                except Exception as e:
                    logger.warning(f"Failed to save merged data: {e}")
                    # Don't fail the entire operation just because saving failed
            
            return merged_data
            
        except Exception as e:
            logger.error(f"Failed to merge data for {symbol} {timeframe}: {e}")
            raise DataError(f"Data merge failed: {e}") from e
    
    def load_with_existing_check(self, 
                                symbol: str, 
                                timeframe: str, 
                                start: Optional[datetime] = None, 
                                end: Optional[datetime] = None,
                                operation_type: str = "api_call") -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Load data with automatic existing data checking and intelligent gap filling.
        
        This is the high-level method that components should use for most operations.
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe  
            start: Start datetime (optional, defaults to intelligent detection)
            end: End datetime (optional, defaults to now)
            operation_type: Type of operation for connection allocation
            
        Returns:
            Tuple of (final_data, metadata) where metadata contains loading stats
        """
        start_time = time.time()
        metadata = {
            "existing_bars": 0,
            "fetched_bars": 0,
            "cached_before": False,
            "load_method": "unknown",
            "execution_time_seconds": 0.0
        }
        
        try:
            # Set default end time
            if end is None:
                end = datetime.now(timezone.utc)
            
            # Load existing data if local loader available
            existing_data = None
            if self.local_loader:
                try:
                    existing_data = self.local_loader.load(symbol, timeframe)
                    if existing_data is not None and not existing_data.empty:
                        metadata["existing_bars"] = len(existing_data)
                        metadata["cached_before"] = True
                        logger.debug(f"Found existing data: {len(existing_data)} bars")
                except Exception as e:
                    logger.debug(f"No existing data found: {e}")
            
            # Determine what date range to fetch
            if start is None:
                if existing_data is not None and not existing_data.empty:
                    # Start from end of existing data
                    start = existing_data.index[-1]
                    metadata["load_method"] = "tail"
                else:
                    # Default to recent data
                    start = end - timedelta(days=30)  # 30 days of history
                    metadata["load_method"] = "full"
            else:
                metadata["load_method"] = "range"
            
            # Ensure start is before end
            if start >= end:
                logger.debug(f"Start time {start} >= end time {end}, no data to fetch")
                metadata["execution_time_seconds"] = time.time() - start_time
                return existing_data if existing_data is not None else pd.DataFrame(), metadata
            
            # Determine loading strategy based on range size
            duration = end - start
            max_duration = IbLimitsRegistry.get_duration_limit(timeframe)
            
            if duration <= max_duration:
                # Single request
                new_data = self.load_data_range(symbol, timeframe, start, end, operation_type)
            else:
                # Progressive loading
                new_data = self.load_progressive(symbol, timeframe, start, end, operation_type)
                metadata["load_method"] += "_progressive"
            
            metadata["fetched_bars"] = len(new_data) if not new_data.empty else 0
            
            # Merge with existing data
            final_data = self.merge_and_save_data(symbol, timeframe, existing_data, new_data, save_to_file=True)
            
            metadata["execution_time_seconds"] = time.time() - start_time
            
            logger.info(f"Load completed: {metadata['existing_bars']} existing + {metadata['fetched_bars']} fetched = {len(final_data)} total bars")
            
            return final_data, metadata
            
        except Exception as e:
            metadata["execution_time_seconds"] = time.time() - start_time
            logger.error(f"Load with existing check failed: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            **self.stats,
            "success_rate": self.stats["successful_requests"] / max(1, self.stats["total_requests"]),
            "avg_execution_time": self.stats["total_execution_time"] / max(1, self.stats["total_requests"]),
            "avg_bars_per_request": self.stats["total_bars_fetched"] / max(1, self.stats["successful_requests"])
        }
    
    def reset_stats(self):
        """Reset performance statistics."""
        for key in self.stats:
            self.stats[key] = 0 if isinstance(self.stats[key], (int, float)) else self.stats[key]