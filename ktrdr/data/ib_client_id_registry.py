"""
IB Client ID Registry

Centralized management of Interactive Brokers client IDs to prevent conflicts
and ensure proper allocation across all components.

This registry provides:
- Thread-safe client ID allocation and tracking
- Purpose-based ID ranges (API, backfill, testing, etc.)
- Persistent state to survive application restarts
- Automatic cleanup of stale/abandoned IDs
- Comprehensive monitoring and metrics

Architecture:
- Singleton pattern for global access
- JSON file persistence for state
- Thread-safe operations with proper locking
- Integration with existing IbLimitsRegistry ranges
"""

import json
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum

from ktrdr.logging import get_logger
from ktrdr.config.ib_limits import IbLimitsRegistry

logger = get_logger(__name__)


class ClientIdPurpose(Enum):
    """Purpose categories for client ID allocation."""
    API_SINGLETON = "api_singleton"
    API_POOL = "api_pool"
    GAP_FILLER = "gap_filler"
    DATA_MANAGER = "data_manager"
    SYMBOL_VALIDATION = "symbol_validation"
    CLI_TEMPORARY = "cli_temporary"
    TEST_CONNECTIONS = "test_connections"
    RESERVED = "reserved"


@dataclass
class ClientIdAllocation:
    """Information about a client ID allocation."""
    client_id: int
    purpose: ClientIdPurpose
    allocated_at: float  # timestamp
    allocated_by: str  # component/process identifier
    last_seen: float  # last activity timestamp
    is_active: bool = True
    connection_count: int = 0  # number of times this ID was used for connections
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "client_id": self.client_id,
            "purpose": self.purpose.value,
            "allocated_at": self.allocated_at,
            "allocated_by": self.allocated_by,
            "last_seen": self.last_seen,
            "is_active": self.is_active,
            "connection_count": self.connection_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClientIdAllocation":
        """Create from dictionary loaded from JSON."""
        return cls(
            client_id=data["client_id"],
            purpose=ClientIdPurpose(data["purpose"]),
            allocated_at=data["allocated_at"],
            allocated_by=data["allocated_by"],
            last_seen=data["last_seen"],
            is_active=data.get("is_active", True),
            connection_count=data.get("connection_count", 0)
        )


class IbClientIdRegistry:
    """
    Centralized registry for managing IB client IDs across all components.
    
    This singleton registry ensures no client ID conflicts by:
    1. Tracking all allocated IDs with metadata
    2. Using purpose-based allocation ranges
    3. Detecting and cleaning up stale IDs
    4. Providing comprehensive monitoring
    
    Thread-safe design allows concurrent access from multiple components.
    """
    
    _instance: Optional["IbClientIdRegistry"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "IbClientIdRegistry":
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the registry with persistent state."""
        # Prevent re-initialization of singleton
        if hasattr(self, "_initialized"):
            return
        
        self._initialized = True
        
        # Thread safety
        self._allocation_lock = threading.RLock()
        
        # State management
        self._allocations: Dict[int, ClientIdAllocation] = {}
        self._purpose_allocations: Dict[ClientIdPurpose, Set[int]] = {
            purpose: set() for purpose in ClientIdPurpose
        }
        
        # Configuration
        self._stale_threshold = 3600  # 1 hour - consider ID stale if not seen
        self._persistence_file = self._get_persistence_file()
        
        # Statistics
        self._stats = {
            "total_allocations": 0,
            "total_deallocations": 0,
            "stale_cleanups": 0,
            "conflicts_prevented": 0,
            "load_time": 0.0
        }
        
        # Load persistent state
        self._load_state()
        
        logger.info(f"IbClientIdRegistry initialized with {len(self._allocations)} existing allocations")
    
    def _get_persistence_file(self) -> Path:
        """Get the file path for persistent state storage."""
        try:
            # Try to get data directory from settings
            from ktrdr.config.settings import get_settings
            settings = get_settings()
            data_dir = Path(settings.data_dir) if hasattr(settings, 'data_dir') else Path("data")
        except Exception:
            data_dir = Path("data")
        
        data_dir.mkdir(exist_ok=True)
        return data_dir / "ib_client_id_registry.json"
    
    def _load_state(self) -> None:
        """Load persistent state from JSON file."""
        start_time = time.time()
        
        if not self._persistence_file.exists():
            logger.info("No existing client ID registry state found, starting fresh")
            return
        
        try:
            with open(self._persistence_file, 'r') as f:
                data = json.load(f)
            
            # Load allocations
            allocations_data = data.get("allocations", {})
            for client_id_str, alloc_data in allocations_data.items():
                client_id = int(client_id_str)
                allocation = ClientIdAllocation.from_dict(alloc_data)
                self._allocations[client_id] = allocation
                self._purpose_allocations[allocation.purpose].add(client_id)
            
            # Load statistics
            self._stats.update(data.get("stats", {}))
            
            # Clean up stale allocations on load
            stale_count = self._cleanup_stale_allocations()
            if stale_count > 0:
                logger.info(f"Cleaned up {stale_count} stale client ID allocations on startup")
            
            load_time = time.time() - start_time
            self._stats["load_time"] = load_time
            
            logger.info(f"Loaded {len(self._allocations)} client ID allocations in {load_time:.3f}s")
            
        except Exception as e:
            logger.error(f"Failed to load client ID registry state: {e}")
            logger.warning("Starting with fresh state")
            self._allocations.clear()
            for purpose_set in self._purpose_allocations.values():
                purpose_set.clear()
    
    def _save_state(self) -> None:
        """Save current state to JSON file."""
        try:
            # Prepare data for serialization
            data = {
                "allocations": {
                    str(client_id): allocation.to_dict()
                    for client_id, allocation in self._allocations.items()
                },
                "stats": self._stats,
                "saved_at": time.time(),
                "saved_at_iso": datetime.now(timezone.utc).isoformat()
            }
            
            # Write atomically using temporary file
            temp_file = self._persistence_file.with_suffix(".tmp")
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Atomic move
            temp_file.replace(self._persistence_file)
            
            logger.debug(f"Saved client ID registry state with {len(self._allocations)} allocations")
            
        except Exception as e:
            logger.error(f"Failed to save client ID registry state: {e}")
    
    def allocate_client_id(
        self,
        purpose: ClientIdPurpose,
        allocated_by: str,
        preferred_id: Optional[int] = None
    ) -> Optional[int]:
        """
        Allocate a client ID for the specified purpose.
        
        Args:
            purpose: Purpose category for the allocation
            allocated_by: Component or process requesting the ID
            preferred_id: Specific ID to request (if available)
            
        Returns:
            Allocated client ID or None if no IDs available
        """
        with self._allocation_lock:
            current_time = time.time()
            
            # Clean up stale allocations first
            self._cleanup_stale_allocations()
            
            # Get available IDs for this purpose
            available_ids = self._get_available_ids_for_purpose(purpose)
            
            if not available_ids:
                logger.error(f"No available client IDs for purpose {purpose.value}")
                return None
            
            # Try preferred ID first if specified
            if preferred_id is not None:
                if preferred_id in available_ids:
                    client_id = preferred_id
                    logger.info(f"Allocated preferred client ID {client_id} for {purpose.value}")
                else:
                    logger.warning(f"Preferred client ID {preferred_id} not available for {purpose.value}")
                    if preferred_id in self._allocations:
                        existing = self._allocations[preferred_id]
                        logger.warning(f"Client ID {preferred_id} already allocated to {existing.allocated_by} for {existing.purpose.value}")
                    client_id = min(available_ids)  # Fall back to first available
            else:
                # Use first available ID
                client_id = min(available_ids)
            
            # Create allocation record
            allocation = ClientIdAllocation(
                client_id=client_id,
                purpose=purpose,
                allocated_at=current_time,
                allocated_by=allocated_by,
                last_seen=current_time,
                is_active=True,
                connection_count=0
            )
            
            # Record allocation
            self._allocations[client_id] = allocation
            self._purpose_allocations[purpose].add(client_id)
            self._stats["total_allocations"] += 1
            
            # Save state
            self._save_state()
            
            logger.info(f"✅ Allocated client ID {client_id} to {allocated_by} for {purpose.value}")
            return client_id
    
    def deallocate_client_id(self, client_id: int, deallocated_by: str) -> bool:
        """
        Deallocate a client ID, making it available for reuse.
        
        Args:
            client_id: Client ID to deallocate
            deallocated_by: Component or process deallocating the ID
            
        Returns:
            True if successfully deallocated, False if not found
        """
        with self._allocation_lock:
            if client_id not in self._allocations:
                logger.warning(f"Attempted to deallocate unknown client ID {client_id} by {deallocated_by}")
                return False
            
            allocation = self._allocations[client_id]
            
            # Remove from tracking
            del self._allocations[client_id]
            self._purpose_allocations[allocation.purpose].discard(client_id)
            self._stats["total_deallocations"] += 1
            
            # Save state
            self._save_state()
            
            logger.info(f"🧹 Deallocated client ID {client_id} (was allocated to {allocation.allocated_by}) by {deallocated_by}")
            return True
    
    def update_last_seen(self, client_id: int) -> bool:
        """
        Update the last seen timestamp for a client ID.
        
        Args:
            client_id: Client ID to update
            
        Returns:
            True if updated, False if not found
        """
        with self._allocation_lock:
            if client_id not in self._allocations:
                return False
            
            self._allocations[client_id].last_seen = time.time()
            self._allocations[client_id].connection_count += 1
            return True
    
    def mark_inactive(self, client_id: int) -> bool:
        """
        Mark a client ID as inactive (but keep allocated).
        
        Args:
            client_id: Client ID to mark as inactive
            
        Returns:
            True if marked inactive, False if not found
        """
        with self._allocation_lock:
            if client_id not in self._allocations:
                return False
            
            self._allocations[client_id].is_active = False
            self._save_state()
            
            logger.debug(f"Marked client ID {client_id} as inactive")
            return True
    
    def get_allocation_info(self, client_id: int) -> Optional[ClientIdAllocation]:
        """
        Get allocation information for a client ID.
        
        Args:
            client_id: Client ID to query
            
        Returns:
            Allocation information or None if not found
        """
        with self._allocation_lock:
            return self._allocations.get(client_id)
    
    def get_allocations_by_purpose(self, purpose: ClientIdPurpose) -> List[ClientIdAllocation]:
        """
        Get all allocations for a specific purpose.
        
        Args:
            purpose: Purpose to query
            
        Returns:
            List of allocations for that purpose
        """
        with self._allocation_lock:
            client_ids = self._purpose_allocations[purpose]
            return [self._allocations[cid] for cid in client_ids if cid in self._allocations]
    
    def _get_available_ids_for_purpose(self, purpose: ClientIdPurpose) -> Set[int]:
        """Get available client IDs for a specific purpose."""
        # Get the range for this purpose from IbLimitsRegistry
        try:
            purpose_ranges = IbLimitsRegistry.CLIENT_ID_RANGES
            range_key = purpose.value
            
            if range_key not in purpose_ranges:
                logger.error(f"No client ID range defined for purpose {purpose.value}")
                return set()
            
            all_ids_for_purpose = set(purpose_ranges[range_key])
            allocated_ids_for_purpose = self._purpose_allocations[purpose]
            
            return all_ids_for_purpose - allocated_ids_for_purpose
            
        except Exception as e:
            logger.error(f"Error getting available IDs for purpose {purpose.value}: {e}")
            return set()
    
    def _cleanup_stale_allocations(self) -> int:
        """
        Clean up stale allocations (not seen for > threshold time).
        
        Returns:
            Number of stale allocations cleaned up
        """
        current_time = time.time()
        stale_threshold = current_time - self._stale_threshold
        
        stale_ids = []
        for client_id, allocation in self._allocations.items():
            if allocation.last_seen < stale_threshold and not allocation.is_active:
                stale_ids.append(client_id)
        
        # Remove stale allocations
        for client_id in stale_ids:
            allocation = self._allocations[client_id]
            del self._allocations[client_id]
            self._purpose_allocations[allocation.purpose].discard(client_id)
            logger.info(f"🧹 Cleaned up stale client ID {client_id} (allocated to {allocation.allocated_by})")
        
        if stale_ids:
            self._stats["stale_cleanups"] += len(stale_ids)
            self._save_state()
        
        return len(stale_ids)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive registry statistics."""
        with self._allocation_lock:
            current_time = time.time()
            
            # Calculate purpose distribution
            purpose_stats = {}
            for purpose in ClientIdPurpose:
                allocations = self.get_allocations_by_purpose(purpose)
                active_count = len([a for a in allocations if a.is_active])
                total_count = len(allocations)
                
                purpose_stats[purpose.value] = {
                    "total_allocated": total_count,
                    "active": active_count,
                    "inactive": total_count - active_count,
                    "available": len(self._get_available_ids_for_purpose(purpose))
                }
            
            # Calculate age statistics
            if self._allocations:
                ages = [current_time - a.allocated_at for a in self._allocations.values()]
                avg_age = sum(ages) / len(ages)
                oldest_age = max(ages)
            else:
                avg_age = 0
                oldest_age = 0
            
            return {
                "total_allocations_ever": self._stats["total_allocations"],
                "total_deallocations_ever": self._stats["total_deallocations"],
                "stale_cleanups_ever": self._stats["stale_cleanups"],
                "conflicts_prevented": self._stats["conflicts_prevented"],
                "current_allocations": len(self._allocations),
                "active_allocations": len([a for a in self._allocations.values() if a.is_active]),
                "inactive_allocations": len([a for a in self._allocations.values() if not a.is_active]),
                "purpose_distribution": purpose_stats,
                "average_allocation_age_seconds": avg_age,
                "oldest_allocation_age_seconds": oldest_age,
                "stale_threshold_seconds": self._stale_threshold,
                "load_time_seconds": self._stats["load_time"],
                "persistence_file": str(self._persistence_file)
            }
    
    def force_cleanup(self) -> Dict[str, int]:
        """
        Force cleanup of all inactive and stale allocations.
        
        Returns:
            Dictionary with cleanup counts
        """
        with self._allocation_lock:
            inactive_count = 0
            stale_count = 0
            
            current_time = time.time()
            stale_threshold = current_time - self._stale_threshold
            
            ids_to_remove = []
            for client_id, allocation in self._allocations.items():
                if not allocation.is_active:
                    ids_to_remove.append(client_id)
                    inactive_count += 1
                elif allocation.last_seen < stale_threshold:
                    ids_to_remove.append(client_id)
                    stale_count += 1
            
            # Remove identified allocations
            for client_id in ids_to_remove:
                allocation = self._allocations[client_id]
                del self._allocations[client_id]
                self._purpose_allocations[allocation.purpose].discard(client_id)
                logger.info(f"🧹 Force cleanup: removed client ID {client_id} (allocated to {allocation.allocated_by})")
            
            if ids_to_remove:
                self._stats["stale_cleanups"] += len(ids_to_remove)
                self._save_state()
            
            result = {
                "inactive_cleaned": inactive_count,
                "stale_cleaned": stale_count,
                "total_cleaned": len(ids_to_remove)
            }
            
            logger.info(f"Force cleanup completed: {result}")
            return result


# Global registry instance
_registry: Optional[IbClientIdRegistry] = None


def get_client_id_registry() -> IbClientIdRegistry:
    """Get the global client ID registry instance."""
    global _registry
    if _registry is None:
        _registry = IbClientIdRegistry()
    return _registry


def allocate_client_id(purpose: ClientIdPurpose, allocated_by: str, preferred_id: Optional[int] = None) -> Optional[int]:
    """Convenience function to allocate a client ID."""
    return get_client_id_registry().allocate_client_id(purpose, allocated_by, preferred_id)


def deallocate_client_id(client_id: int, deallocated_by: str) -> bool:
    """Convenience function to deallocate a client ID."""
    return get_client_id_registry().deallocate_client_id(client_id, deallocated_by)


def update_client_id_activity(client_id: int) -> bool:
    """Convenience function to update client ID activity."""
    return get_client_id_registry().update_last_seen(client_id)