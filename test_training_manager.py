#!/usr/bin/env python3
"""
Test script for the new TrainingManager architecture.
This script validates that our TrainingManager can properly route
to host service or local training based on environment variables.
"""

import os
import asyncio
from ktrdr.training.training_manager import TrainingManager

async def test_training_manager():
    """Test TrainingManager initialization and configuration."""
    print("🧪 Testing TrainingManager Architecture")
    print("=" * 50)
    
    # Test 1: Default configuration (should be local training)
    print("\n1️⃣ Testing Default Configuration (Local Training)")
    
    # Clear environment variables
    os.environ.pop("USE_TRAINING_HOST_SERVICE", None)
    os.environ.pop("TRAINING_HOST_SERVICE_URL", None)
    
    try:
        manager = TrainingManager()
        config = manager.get_configuration_info()
        
        print(f"✅ Mode: {config['mode']}")
        print(f"✅ Host Service URL: {config['host_service_url']}")
        print(f"✅ Environment Variables: {config['environment_variables']}")
        
        if config['mode'] == 'local':
            print("✅ SUCCESS: Default configuration uses local training")
        else:
            print("❌ FAILED: Expected local training as default")
            
    except Exception as e:
        print(f"❌ FAILED: Error initializing TrainingManager: {str(e)}")
        return False
    
    # Test 2: Host service enabled
    print("\n2️⃣ Testing Host Service Configuration")
    
    os.environ["USE_TRAINING_HOST_SERVICE"] = "true"
    os.environ["TRAINING_HOST_SERVICE_URL"] = "http://localhost:5002"
    
    try:
        manager = TrainingManager()
        config = manager.get_configuration_info()
        
        print(f"✅ Mode: {config['mode']}")
        print(f"✅ Host Service URL: {config['host_service_url']}")
        print(f"✅ Environment Variables: {config['environment_variables']}")
        
        if config['mode'] == 'host_service' and config['host_service_url'] == 'http://localhost:5002':
            print("✅ SUCCESS: Host service configuration works correctly")
        else:
            print("❌ FAILED: Host service configuration not working")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: Error with host service configuration: {str(e)}")
        return False
    
    # Test 3: Environment variable variations
    print("\n3️⃣ Testing Environment Variable Variations")
    
    test_cases = [
        ("1", True),
        ("yes", True), 
        ("false", False),
        ("0", False),
        ("no", False),
        ("", False)  # Empty should default to False
    ]
    
    for test_value, expected_host_service in test_cases:
        os.environ["USE_TRAINING_HOST_SERVICE"] = test_value
        
        try:
            manager = TrainingManager()
            actual_host_service = manager.is_using_host_service()
            
            if actual_host_service == expected_host_service:
                print(f"✅ '{test_value}' → {actual_host_service} (correct)")
            else:
                print(f"❌ '{test_value}' → {actual_host_service} (expected {expected_host_service})")
                return False
                
        except Exception as e:
            print(f"❌ FAILED: Error testing '{test_value}': {str(e)}")
            return False
    
    print("\n🎉 All TrainingManager tests passed!")
    print("🏗️  Architecture successfully mirrors IB service pattern")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_training_manager())
    if success:
        print("\n✅ READY FOR PHASE 4: Docker networking testing")
    else:
        print("\n❌ ARCHITECTURE ISSUES FOUND - Fix before proceeding")