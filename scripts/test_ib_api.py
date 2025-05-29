#!/usr/bin/env python3
"""
Test IB API endpoints.
"""

import requests
import json
import time

# Base URL for the API
BASE_URL = "http://localhost:8000/api/v1"

def test_ib_endpoints():
    """Test all IB API endpoints."""
    print("Testing IB API endpoints...")
    print(f"Base URL: {BASE_URL}")
    print("-" * 60)
    
    # Test 1: Get IB Status
    print("\n1. Testing GET /api/v1/ib/status")
    try:
        response = requests.get(f"{BASE_URL}/ib/status")
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data['success']}")
            if data['success'] and data['data']:
                status = data['data']
                print(f"   IB Available: {status['ib_available']}")
                print(f"   Connected: {status['connection']['connected']}")
                print(f"   Client ID: {status['connection']['client_id']}")
                print(f"   Total Connections: {status['connection_metrics']['total_connections']}")
                print(f"   Data Requests: {status['data_metrics']['total_requests']}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 2: Check IB Health
    print("\n2. Testing GET /api/v1/ib/health")
    try:
        response = requests.get(f"{BASE_URL}/ib/health")
        print(f"   Status Code: {response.status_code}")
        if response.ok:
            data = response.json()
            print(f"   Success: {data.get('success', False)}")
            if 'data' in data and data['data']:
                health = data['data']
                print(f"   Healthy: {health['healthy']}")
                print(f"   Connection OK: {health['connection_ok']}")
                print(f"   Data Fetching OK: {health['data_fetching_ok']}")
                if health.get('error_message'):
                    print(f"   Error: {health['error_message']}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 3: Get IB Config
    print("\n3. Testing GET /api/v1/ib/config")
    try:
        response = requests.get(f"{BASE_URL}/ib/config")
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data['success']}")
            if data['success'] and data['data']:
                config = data['data']
                print(f"   Host: {config['host']}")
                print(f"   Port: {config['port']}")
                print(f"   Client ID Range: {config['client_id_range']}")
                print(f"   Timeout: {config['timeout']}s")
                print(f"   Rate Limit: {config['rate_limit']}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 4: Cleanup IB Connections
    print("\n4. Testing POST /api/v1/ib/cleanup")
    try:
        response = requests.post(f"{BASE_URL}/ib/cleanup")
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data['success']}")
            if data['data']:
                result = data['data']
                print(f"   Message: {result.get('message', 'N/A')}")
                print(f"   Connections Closed: {result.get('connections_closed', 0)}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    print("\n" + "-" * 60)
    print("API tests completed!")

if __name__ == "__main__":
    # Note: Make sure the API server is running before running this test
    print("Note: Make sure the API server is running at http://localhost:8000")
    print("You can start it with: uv run scripts/run_api_server.py")
    input("\nPress Enter to continue with tests...")
    
    test_ib_endpoints()