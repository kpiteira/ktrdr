"""
Unit tests for IB Client ID Registry

Tests comprehensive functionality including:
- Thread-safe allocation and deallocation
- Purpose-based ID management
- Persistent state handling
- Stale ID cleanup
- Concurrent access scenarios
- Registry statistics and monitoring
"""

import pytest
import threading
import time
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed

from ktrdr.data.ib_client_id_registry import (
    IbClientIdRegistry,
    ClientIdPurpose,
    ClientIdAllocation,
    get_client_id_registry,
    allocate_client_id,
    deallocate_client_id,
    update_client_id_activity
)


class TestClientIdAllocation:
    """Test the ClientIdAllocation data class."""
    
    def test_to_dict_conversion(self):
        """Test conversion to dictionary for JSON serialization."""
        allocation = ClientIdAllocation(
            client_id=123,
            purpose=ClientIdPurpose.API_POOL,
            allocated_at=1234567890.0,
            allocated_by="test_component",
            last_seen=1234567900.0,
            is_active=True,
            connection_count=5
        )
        
        expected = {
            "client_id": 123,
            "purpose": "api_pool",
            "allocated_at": 1234567890.0,
            "allocated_by": "test_component",
            "last_seen": 1234567900.0,
            "is_active": True,
            "connection_count": 5
        }
        
        assert allocation.to_dict() == expected
    
    def test_from_dict_conversion(self):
        """Test creation from dictionary loaded from JSON."""
        data = {
            "client_id": 123,
            "purpose": "api_pool",
            "allocated_at": 1234567890.0,
            "allocated_by": "test_component",
            "last_seen": 1234567900.0,
            "is_active": True,
            "connection_count": 5
        }
        
        allocation = ClientIdAllocation.from_dict(data)
        
        assert allocation.client_id == 123
        assert allocation.purpose == ClientIdPurpose.API_POOL
        assert allocation.allocated_at == 1234567890.0
        assert allocation.allocated_by == "test_component"
        assert allocation.last_seen == 1234567900.0
        assert allocation.is_active is True
        assert allocation.connection_count == 5
    
    def test_from_dict_with_defaults(self):
        """Test creation from dictionary with missing optional fields."""
        data = {
            "client_id": 123,
            "purpose": "api_pool",
            "allocated_at": 1234567890.0,
            "allocated_by": "test_component",
            "last_seen": 1234567900.0
        }
        
        allocation = ClientIdAllocation.from_dict(data)
        
        assert allocation.is_active is True  # default
        assert allocation.connection_count == 0  # default


class TestIbClientIdRegistry:
    """Test the main IB Client ID Registry functionality."""
    
    @pytest.fixture
    def temp_registry_file(self):
        """Create a temporary file for registry persistence."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        yield temp_path
        if temp_path.exists():
            temp_path.unlink()
    
    @pytest.fixture
    def registry(self, temp_registry_file):
        """Create a fresh registry instance with temporary persistence."""
        # Reset singleton
        IbClientIdRegistry._instance = None
        
        with patch.object(IbClientIdRegistry, '_get_persistence_file', return_value=temp_registry_file):
            registry = IbClientIdRegistry()
        
        yield registry
        
        # Clean up singleton
        IbClientIdRegistry._instance = None
    
    def test_singleton_pattern(self, temp_registry_file):
        """Test that registry follows singleton pattern."""
        # Reset singleton
        IbClientIdRegistry._instance = None
        
        with patch.object(IbClientIdRegistry, '_get_persistence_file', return_value=temp_registry_file):
            registry1 = IbClientIdRegistry()
            registry2 = IbClientIdRegistry()
        
        assert registry1 is registry2
        
        # Clean up
        IbClientIdRegistry._instance = None
    
    def test_basic_allocation_and_deallocation(self, registry):
        """Test basic client ID allocation and deallocation."""
        # Allocate a client ID
        client_id = registry.allocate_client_id(
            purpose=ClientIdPurpose.API_POOL,
            allocated_by="test_component"
        )
        
        assert client_id is not None
        assert client_id in range(11, 51)  # API_POOL range
        
        # Check allocation info
        allocation = registry.get_allocation_info(client_id)
        assert allocation is not None
        assert allocation.client_id == client_id
        assert allocation.purpose == ClientIdPurpose.API_POOL
        assert allocation.allocated_by == "test_component"
        assert allocation.is_active is True
        
        # Deallocate the client ID
        success = registry.deallocate_client_id(client_id, "test_component")
        assert success is True
        
        # Verify it's deallocated
        allocation = registry.get_allocation_info(client_id)
        assert allocation is None
    
    def test_preferred_id_allocation(self, registry):
        """Test allocation with preferred client ID."""
        preferred_id = 15  # Within API_POOL range
        
        client_id = registry.allocate_client_id(
            purpose=ClientIdPurpose.API_POOL,
            allocated_by="test_component",
            preferred_id=preferred_id
        )
        
        assert client_id == preferred_id
        
        # Try to allocate the same preferred ID again
        client_id2 = registry.allocate_client_id(
            purpose=ClientIdPurpose.API_POOL,
            allocated_by="test_component2",
            preferred_id=preferred_id
        )
        
        # Should get a different ID since preferred is taken
        assert client_id2 != preferred_id
        assert client_id2 is not None
    
    def test_purpose_based_allocation(self, registry):
        """Test that allocation respects purpose-based ranges."""
        # Allocate from different purposes
        api_id = registry.allocate_client_id(
            purpose=ClientIdPurpose.API_POOL,
            allocated_by="api_component"
        )
        
        gap_filler_id = registry.allocate_client_id(
            purpose=ClientIdPurpose.GAP_FILLER,
            allocated_by="gap_component"
        )
        
        cli_id = registry.allocate_client_id(
            purpose=ClientIdPurpose.CLI_TEMPORARY,
            allocated_by="cli_component"
        )
        
        # Verify they're in correct ranges
        assert api_id in range(11, 51)  # API_POOL range
        assert gap_filler_id in range(101, 111)  # GAP_FILLER range
        assert cli_id in range(201, 251)  # CLI_TEMPORARY range
    
    def test_allocations_by_purpose(self, registry):
        """Test getting allocations by purpose."""
        # Allocate multiple IDs for the same purpose
        id1 = registry.allocate_client_id(ClientIdPurpose.API_POOL, "component1")
        id2 = registry.allocate_client_id(ClientIdPurpose.API_POOL, "component2")
        id3 = registry.allocate_client_id(ClientIdPurpose.GAP_FILLER, "component3")
        
        # Get allocations by purpose
        api_allocations = registry.get_allocations_by_purpose(ClientIdPurpose.API_POOL)
        gap_allocations = registry.get_allocations_by_purpose(ClientIdPurpose.GAP_FILLER)
        
        assert len(api_allocations) == 2
        assert len(gap_allocations) == 1
        
        api_ids = {alloc.client_id for alloc in api_allocations}
        assert api_ids == {id1, id2}
        
        assert gap_allocations[0].client_id == id3
    
    def test_last_seen_update(self, registry):
        """Test updating last seen timestamp."""
        client_id = registry.allocate_client_id(
            purpose=ClientIdPurpose.API_POOL,
            allocated_by="test_component"
        )
        
        original_allocation = registry.get_allocation_info(client_id)
        original_last_seen = original_allocation.last_seen
        original_count = original_allocation.connection_count
        
        # Wait a bit and update
        time.sleep(0.1)
        success = registry.update_last_seen(client_id)
        assert success is True
        
        # Verify update
        updated_allocation = registry.get_allocation_info(client_id)
        assert updated_allocation.last_seen > original_last_seen
        assert updated_allocation.connection_count == original_count + 1
    
    def test_mark_inactive(self, registry):
        """Test marking client ID as inactive."""
        client_id = registry.allocate_client_id(
            purpose=ClientIdPurpose.API_POOL,
            allocated_by="test_component"
        )
        
        # Mark as inactive
        success = registry.mark_inactive(client_id)
        assert success is True
        
        # Verify it's marked inactive
        allocation = registry.get_allocation_info(client_id)
        assert allocation.is_active is False
    
    def test_stale_cleanup(self, registry):
        """Test cleanup of stale allocations."""
        # Set a very short stale threshold for testing
        registry._stale_threshold = 0.1  # 100ms
        
        # Allocate and mark inactive
        client_id = registry.allocate_client_id(
            purpose=ClientIdPurpose.API_POOL,
            allocated_by="test_component"
        )
        
        registry.mark_inactive(client_id)
        
        # Wait for it to become stale
        time.sleep(0.2)
        
        # Run cleanup
        cleaned_count = registry._cleanup_stale_allocations()
        
        assert cleaned_count == 1
        assert registry.get_allocation_info(client_id) is None
    
    def test_force_cleanup(self, registry):
        """Test force cleanup functionality."""
        # Allocate multiple IDs
        id1 = registry.allocate_client_id(ClientIdPurpose.API_POOL, "component1")
        id2 = registry.allocate_client_id(ClientIdPurpose.API_POOL, "component2")
        id3 = registry.allocate_client_id(ClientIdPurpose.GAP_FILLER, "component3")
        
        # Mark some as inactive
        registry.mark_inactive(id1)
        registry.mark_inactive(id2)
        
        # Make one stale
        registry._stale_threshold = 0.1
        time.sleep(0.2)
        
        # Force cleanup
        result = registry.force_cleanup()
        
        assert result["inactive_cleaned"] == 2
        assert result["total_cleaned"] >= 2
    
    def test_persistence_save_and_load(self, temp_registry_file):
        """Test that registry state persists across instances."""
        # Create registry and allocate some IDs
        IbClientIdRegistry._instance = None
        with patch.object(IbClientIdRegistry, '_get_persistence_file', return_value=temp_registry_file):
            registry1 = IbClientIdRegistry()
            
            id1 = registry1.allocate_client_id(ClientIdPurpose.API_POOL, "component1")
            id2 = registry1.allocate_client_id(ClientIdPurpose.GAP_FILLER, "component2")
            
            # Verify persistence file was created
            assert temp_registry_file.exists()
        
        # Create new registry instance
        IbClientIdRegistry._instance = None
        with patch.object(IbClientIdRegistry, '_get_persistence_file', return_value=temp_registry_file):
            registry2 = IbClientIdRegistry()
            
            # Verify state was loaded
            allocation1 = registry2.get_allocation_info(id1)
            allocation2 = registry2.get_allocation_info(id2)
            
            assert allocation1 is not None
            assert allocation1.client_id == id1
            assert allocation1.purpose == ClientIdPurpose.API_POOL
            
            assert allocation2 is not None
            assert allocation2.client_id == id2
            assert allocation2.purpose == ClientIdPurpose.GAP_FILLER
    
    def test_statistics(self, registry):
        """Test registry statistics functionality."""
        # Initial stats
        stats = registry.get_stats()
        initial_allocations = stats["total_allocations_ever"]
        
        # Allocate some IDs
        id1 = registry.allocate_client_id(ClientIdPurpose.API_POOL, "component1")
        id2 = registry.allocate_client_id(ClientIdPurpose.GAP_FILLER, "component2")
        
        # Check updated stats
        stats = registry.get_stats()
        assert stats["total_allocations_ever"] == initial_allocations + 2
        assert stats["current_allocations"] == 2
        assert stats["active_allocations"] == 2
        assert stats["inactive_allocations"] == 0
        
        # Check purpose distribution
        api_stats = stats["purpose_distribution"]["api_pool"]
        assert api_stats["total_allocated"] == 1
        assert api_stats["active"] == 1
        
        # Mark one inactive and check stats
        registry.mark_inactive(id1)
        stats = registry.get_stats()
        assert stats["active_allocations"] == 1
        assert stats["inactive_allocations"] == 1
    
    def test_concurrent_allocation(self, registry):
        """Test thread-safe concurrent allocation."""
        num_threads = 10
        allocations_per_thread = 5
        
        def allocate_worker(thread_id):
            allocated_ids = []
            for i in range(allocations_per_thread):
                client_id = registry.allocate_client_id(
                    purpose=ClientIdPurpose.TEST_CONNECTIONS,
                    allocated_by=f"thread_{thread_id}_alloc_{i}"
                )
                if client_id is not None:
                    allocated_ids.append(client_id)
                    time.sleep(0.001)  # Small delay to increase contention
            return allocated_ids
        
        # Run concurrent allocations
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(allocate_worker, i) for i in range(num_threads)]
            all_allocated_ids = []
            
            for future in as_completed(futures):
                allocated_ids = future.result()
                all_allocated_ids.extend(allocated_ids)
        
        # Verify no duplicate allocations
        assert len(all_allocated_ids) == len(set(all_allocated_ids))
        
        # Verify all IDs are in correct range
        test_range = range(251, 299)  # TEST_CONNECTIONS range
        for client_id in all_allocated_ids:
            assert client_id in test_range
    
    def test_invalid_purpose_handling(self, registry):
        """Test handling of invalid purpose ranges."""
        # Mock IbLimitsRegistry to return empty range for a purpose
        with patch('ktrdr.data.ib_client_id_registry.IbLimitsRegistry.CLIENT_ID_RANGES', 
                   {"api_pool": []}):  # Empty range
            
            client_id = registry.allocate_client_id(
                purpose=ClientIdPurpose.API_POOL,
                allocated_by="test_component"
            )
            
            assert client_id is None
    
    def test_deallocation_of_unknown_id(self, registry):
        """Test deallocation of unknown client ID."""
        success = registry.deallocate_client_id(999, "test_component")
        assert success is False
    
    def test_update_last_seen_unknown_id(self, registry):
        """Test updating last seen for unknown client ID."""
        success = registry.update_last_seen(999)
        assert success is False


class TestConvenienceFunctions:
    """Test the convenience functions for registry access."""
    
    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset the global registry before each test."""
        # Reset global registry
        import ktrdr.data.ib_client_id_registry
        ktrdr.data.ib_client_id_registry._registry = None
        yield
        ktrdr.data.ib_client_id_registry._registry = None
    
    def test_convenience_functions(self):
        """Test convenience functions work correctly."""
        # Test allocation
        client_id = allocate_client_id(
            purpose=ClientIdPurpose.API_POOL,
            allocated_by="test_component"
        )
        
        assert client_id is not None
        
        # Test activity update
        success = update_client_id_activity(client_id)
        assert success is True
        
        # Test deallocation
        success = deallocate_client_id(client_id, "test_component")
        assert success is True
        
        # Test activity update on deallocated ID
        success = update_client_id_activity(client_id)
        assert success is False
    
    def test_get_client_id_registry_singleton(self):
        """Test that get_client_id_registry returns singleton."""
        registry1 = get_client_id_registry()
        registry2 = get_client_id_registry()
        
        assert registry1 is registry2


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.fixture
    def registry_with_io_error(self, temp_registry_file):
        """Create registry that will have I/O errors."""
        IbClientIdRegistry._instance = None
        
        with patch.object(IbClientIdRegistry, '_get_persistence_file', return_value=temp_registry_file):
            registry = IbClientIdRegistry()
        
        yield registry
        
        IbClientIdRegistry._instance = None
    
    def test_persistence_io_error_handling(self, registry_with_io_error):
        """Test handling of I/O errors during persistence."""
        registry = registry_with_io_error
        
        # Mock file operations to raise IOError
        with patch('builtins.open', side_effect=IOError("Disk full")):
            # This should not crash, just log error
            client_id = registry.allocate_client_id(
                purpose=ClientIdPurpose.API_POOL,
                allocated_by="test_component"
            )
            
            # Allocation should still work in memory
            assert client_id is not None
    
    def test_corrupted_persistence_file(self, temp_registry_file):
        """Test handling of corrupted persistence file."""
        # Write invalid JSON to file
        with open(temp_registry_file, 'w') as f:
            f.write("invalid json content {")
        
        IbClientIdRegistry._instance = None
        
        with patch.object(IbClientIdRegistry, '_get_persistence_file', return_value=temp_registry_file):
            # Should not crash, should start with fresh state
            registry = IbClientIdRegistry()
            
            # Should still be able to allocate
            client_id = registry.allocate_client_id(
                purpose=ClientIdPurpose.API_POOL,
                allocated_by="test_component"
            )
            
            assert client_id is not None


if __name__ == "__main__":
    pytest.main([__file__])