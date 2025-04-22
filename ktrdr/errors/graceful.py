"""
Graceful degradation support for KTRDR.

This module provides utilities for implementing graceful degradation
when non-critical components fail, allowing the application to continue
operating with reduced functionality.
"""

import functools
import logging
from enum import Enum, auto
from typing import Callable, TypeVar, Any, Optional, Dict, List, Union, Tuple, cast

from ktrdr.errors.exceptions import FallbackNotAvailableError


# Type variable for functions that can use fallback strategies
T = TypeVar('T')


class FallbackStrategy(Enum):
    """Enum defining different fallback strategies for graceful degradation."""
    
    # Return a default value
    DEFAULT_VALUE = auto()
    
    # Use a fallback function
    FALLBACK_FUNCTION = auto()
    
    # Return the last known good result
    LAST_KNOWN_GOOD = auto()
    
    # Continue without the result (return None)
    CONTINUE_WITHOUT = auto()


def fallback(
    strategy: FallbackStrategy = FallbackStrategy.CONTINUE_WITHOUT,
    default_value: Any = None,
    fallback_function: Optional[Callable[..., Any]] = None,
    max_cache_size: int = 10,
    logger: Optional[logging.Logger] = None
) -> Callable[[Callable[..., T]], Callable[..., Any]]:
    """
    Decorator to add graceful degradation to a function.
    
    If the function fails, the decorator will apply the specified fallback
    strategy to allow the application to continue operating.
    
    Args:
        strategy: The fallback strategy to use
        default_value: Value to return if the strategy is DEFAULT_VALUE
        fallback_function: Function to call if the strategy is FALLBACK_FUNCTION
        max_cache_size: Maximum number of entries to keep in the cache for LAST_KNOWN_GOOD
        logger: Optional logger to log fallback events
        
    Returns:
        Decorator function that adds graceful degradation to the decorated function
        
    Example:
        @fallback(strategy=FallbackStrategy.DEFAULT_VALUE, default_value=[])
        def fetch_items():
            # Function that might fail but should return empty list as fallback
            pass
    """
    # Cache for last known good results, keyed by args hash
    result_cache: Dict[int, Any] = {}
    
    # Get logger reference
    log = logger or logging.getLogger()
    
    def decorator(func: Callable[..., T]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate a simple hash for args and kwargs to use as cache key
            # Note: This is a simplified approach for demonstration
            args_hash = hash(str(args) + str(sorted(kwargs.items())))
            
            try:
                # Try to execute the function normally
                result = func(*args, **kwargs)
                
                # If successful and using LAST_KNOWN_GOOD strategy, cache the result
                if strategy == FallbackStrategy.LAST_KNOWN_GOOD:
                    # Simple LRU cache implementation - remove oldest if at capacity
                    if len(result_cache) >= max_cache_size:
                        # Remove first (oldest) item
                        first_key = next(iter(result_cache))
                        result_cache.pop(first_key)
                    
                    # Store the new result
                    result_cache[args_hash] = result
                
                return result
            
            except Exception as e:
                # Log the error
                log.warning(
                    f"Function {func.__name__} failed with {type(e).__name__}: {str(e)}. "
                    f"Applying fallback strategy: {strategy.name}"
                )
                
                # Apply the appropriate fallback strategy
                if strategy == FallbackStrategy.DEFAULT_VALUE:
                    return default_value
                
                elif strategy == FallbackStrategy.FALLBACK_FUNCTION:
                    if fallback_function is None:
                        raise FallbackNotAvailableError(
                            f"Fallback function strategy specified for {func.__name__}, but no function provided"
                        )
                    return fallback_function(*args, **kwargs)
                
                elif strategy == FallbackStrategy.LAST_KNOWN_GOOD:
                    if args_hash in result_cache:
                        log.info(f"Returning last known good result for {func.__name__}")
                        return result_cache[args_hash]
                    else:
                        log.warning(f"No last known good result available for {func.__name__}")
                        # Fall through to CONTINUE_WITHOUT if no cached result
                
                elif strategy == FallbackStrategy.CONTINUE_WITHOUT:
                    return None
                
                # If we get here, the strategy is not handled
                raise ValueError(f"Unhandled fallback strategy: {strategy}")
                
        return wrapper
        
    return decorator


def with_partial_results(
    logger: Optional[logging.Logger] = None
) -> Callable[[Callable[..., List[Any]]], Callable[..., List[Any]]]:
    """
    Decorator for functions that return lists, allowing partial results even if some items fail.
    
    This is useful for operations like batch processing where some items might fail
    but you still want to return the successful ones.
    
    Args:
        logger: Optional logger to log item failures
        
    Returns:
        Decorator function that enables partial results
        
    Example:
        @with_partial_results()
        def process_batch(items):
            return [process_item(item) for item in items]  # Some might fail
    """
    # Get logger reference
    log = logger or logging.getLogger()
    
    def decorator(func: Callable[..., List[Any]]) -> Callable[..., List[Any]]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> List[Any]:
            try:
                # First try the normal execution
                return func(*args, **kwargs)
            except Exception as e:
                # If we got here, the whole operation failed
                # Let's try processing items one by one to get partial results
                
                log.warning(
                    f"Batch operation {func.__name__} failed with {type(e).__name__}: {str(e)}. "
                    f"Attempting to process items individually for partial results."
                )
                
                # Extract the list of items to process
                # Assumes the first argument is the list of items
                if not args or not isinstance(args[0], (list, tuple)):
                    # If we can't identify the items, re-raise the original exception
                    log.error(f"Cannot apply partial results strategy: first argument is not a list")
                    raise
                
                items = args[0]
                other_args = args[1:]
                results = []
                failures = 0
                
                # Process each item individually
                for i, item in enumerate(items):
                    try:
                        # Call the function with a single item
                        single_result = func([item], *other_args, **kwargs)
                        # Append the result (should be a list with one item)
                        if single_result:
                            results.extend(single_result)
                    except Exception as item_error:
                        log.warning(
                            f"Processing item {i} failed with {type(item_error).__name__}: {str(item_error)}"
                        )
                        failures += 1
                
                log.info(
                    f"Partial results strategy completed: {len(results)} successes, {failures} failures"
                )
                
                # If everything failed, raise the original exception
                if not results:
                    log.error("All items failed processing, raising original exception")
                    raise
                
                return results
                
        return wrapper
        
    return decorator
