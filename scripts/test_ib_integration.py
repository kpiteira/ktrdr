#!/usr/bin/env python3
"""
IB Integration Test Script

This script tests the complete IB integration stack:
1. IB Configuration loading
2. IB Connection establishment 
3. IB Data fetching
4. DataManager integration with fallback logic
5. Data validation and storage

Usage:
    python scripts/test_ib_integration.py
    
Requirements:
    - IB Gateway/TWS running on configured port
    - Valid .env file with IB settings
    - Network connectivity to IB servers
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ktrdr.config.ib_config import get_ib_config
from ktrdr.data.ib_connection import IbConnectionManager
from ktrdr.data.ib_data_fetcher import IbDataFetcher
from ktrdr.data.data_manager import DataManager
from ktrdr.logging import get_logger

logger = get_logger(__name__)


class IBIntegrationTester:
    """Test suite for IB integration."""
    
    def __init__(self):
        self.config = None
        self.connection = None
        self.fetcher = None
        self.data_manager = None
        self.results = {
            "config": False,
            "connection": False,
            "fetcher": False,
            "data_manager": False,
            "forex_data": False,
            "stock_data": False,
            "fallback": False
        }
        
    def print_header(self, title: str):
        """Print a formatted header."""
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
        
    def print_result(self, test_name: str, success: bool, details: str = ""):
        """Print test result."""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"    {details}")
        self.results[test_name] = success
        
    def test_config_loading(self) -> bool:
        """Test IB configuration loading."""
        self.print_header("Testing IB Configuration")
        
        try:
            self.config = get_ib_config()
            self.print_result("config", True, 
                f"Host: {self.config.host}:{self.config.port}, Client ID: {self.config.client_id}")
            return True
            
        except Exception as e:
            self.print_result("config", False, f"Error: {e}")
            print("\n💡 Troubleshooting:")
            print("   1. Copy .env.template to .env and configure IB settings")
            print("   2. Make sure IB_HOST, IB_PORT, IB_CLIENT_ID are set")
            print("   3. Check that TWS/Gateway is configured with these settings")
            return False
            
    async def test_connection(self) -> bool:
        """Test IB connection."""
        self.print_header("Testing IB Connection")
        
        if not self.config:
            self.print_result("connection", False, "Config not loaded")
            return False
            
        try:
            self.connection = IbConnectionManager(self.config)
            await self.connection.connect()
            
            if await self.connection.is_connected():
                self.print_result("connection", True, 
                    f"Connected to {self.config.host}:{self.config.port}")
                return True
            else:
                self.print_result("connection", False, "Connection status check failed")
                return False
                
        except Exception as e:
            self.print_result("connection", False, f"Error: {e}")
            print("\n💡 Troubleshooting:")
            print("   1. Start IB Gateway/TWS and login")
            print("   2. Enable API connections in configuration")
            print("   3. Check port number (7497 paper, 7496 live)")
            print("   4. Verify client ID is not already in use")
            print("   5. Check firewall settings")
            return False
            
    async def test_data_fetcher(self) -> bool:
        """Test IB data fetcher."""
        self.print_header("Testing IB Data Fetcher")
        
        if not self.connection:
            self.print_result("fetcher", False, "Connection not established")
            return False
            
        try:
            self.fetcher = IbDataFetcher(self.connection, self.config)
            
            # Test with a simple stock symbol
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=5)
            
            data = await self.fetcher.fetch_historical_data(
                "AAPL", "1h", start_date, end_date
            )
            
            if data is not None and len(data) > 0:
                self.print_result("fetcher", True, 
                    f"Fetched {len(data)} bars for AAPL")
                print(f"    Date range: {data.index[0]} to {data.index[-1]}")
                print(f"    Columns: {list(data.columns)}")
                return True
            else:
                self.print_result("fetcher", False, "No data returned")
                return False
                
        except Exception as e:
            self.print_result("fetcher", False, f"Error: {e}")
            return False
            
    def test_data_manager(self) -> bool:
        """Test DataManager integration."""
        self.print_header("Testing DataManager Integration")
        
        try:
            self.data_manager = DataManager()
            
            # Check if IB components were initialized
            has_ib = (self.data_manager.ib_connection is not None and 
                     self.data_manager.ib_fetcher is not None)
            
            if has_ib:
                self.print_result("data_manager", True, 
                    "DataManager initialized with IB integration")
                return True
            else:
                self.print_result("data_manager", False, 
                    "DataManager initialized without IB integration")
                return False
                
        except Exception as e:
            self.print_result("data_manager", False, f"Error: {e}")
            return False
            
    async def test_forex_data(self) -> bool:
        """Test forex data fetching."""
        self.print_header("Testing Forex Data")
        
        if not self.fetcher:
            self.print_result("forex_data", False, "Fetcher not available")
            return False
            
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=2)
            
            data = await self.fetcher.fetch_historical_data(
                "EUR.USD", "1h", start_date, end_date
            )
            
            if data is not None and len(data) > 0:
                self.print_result("forex_data", True, 
                    f"Fetched {len(data)} bars for EUR.USD")
                print(f"    Sample prices: {data['close'].iloc[-3:].tolist()}")
                return True
            else:
                self.print_result("forex_data", False, "No forex data returned")
                return False
                
        except Exception as e:
            self.print_result("forex_data", False, f"Error: {e}")
            print("\n💡 Note: Forex data requires market hours and proper permissions")
            return False
            
    async def test_stock_data(self) -> bool:
        """Test stock data fetching."""
        self.print_header("Testing Stock Data")
        
        if not self.fetcher:
            self.print_result("stock_data", False, "Fetcher not available")
            return False
            
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=2)
            
            data = await self.fetcher.fetch_historical_data(
                "MSFT", "1h", start_date, end_date
            )
            
            if data is not None and len(data) > 0:
                self.print_result("stock_data", True, 
                    f"Fetched {len(data)} bars for MSFT")
                print(f"    Sample prices: {data['close'].iloc[-3:].tolist()}")
                return True
            else:
                self.print_result("stock_data", False, "No stock data returned")
                return False
                
        except Exception as e:
            self.print_result("stock_data", False, f"Error: {e}")
            return False
            
    def test_fallback_logic(self) -> bool:
        """Test DataManager fallback logic."""
        self.print_header("Testing Fallback Logic")
        
        if not self.data_manager:
            self.print_result("fallback", False, "DataManager not available")
            return False
            
        try:
            # Test loading data that might exist locally
            # This will test the fallback chain: IB -> Local CSV -> Merge
            data = self.data_manager.load_data("AAPL", "1d", validate=False)
            
            if data is not None and len(data) > 0:
                self.print_result("fallback", True, 
                    f"Loaded {len(data)} bars through fallback logic")
                return True
            else:
                self.print_result("fallback", False, "No data from fallback logic")
                return False
                
        except Exception as e:
            self.print_result("fallback", False, f"Error: {e}")
            return False
            
    def print_summary(self):
        """Print test summary."""
        self.print_header("Test Summary")
        
        passed = sum(1 for result in self.results.values() if result)
        total = len(self.results)
        
        print(f"Tests passed: {passed}/{total}")
        print(f"Success rate: {passed/total*100:.1f}%")
        
        print("\nDetailed Results:")
        for test_name, success in self.results.items():
            status = "✅" if success else "❌"
            print(f"  {status} {test_name}")
            
        if passed == total:
            print("\n🎉 All tests passed! IB integration is working correctly.")
        elif passed >= total * 0.6:
            print("\n⚠️  Most tests passed. Check failed tests above.")
        else:
            print("\n❌ Many tests failed. Check configuration and IB setup.")
            
        # IB-specific guidance
        if not self.results["connection"]:
            print("\n📋 IB Connection Checklist:")
            print("  1. TWS/Gateway is running and logged in")
            print("  2. API settings enabled (Configure -> API -> Settings)")
            print("  3. Correct port configured (7497 paper, 7496 live)")
            print("  4. Client ID not conflicting with other connections")
            print("  5. 'Read-Only API' disabled if you need write access")
            
    async def run_all_tests(self):
        """Run all integration tests."""
        print("🚀 Starting IB Integration Tests")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Test configuration
        if not self.test_config_loading():
            self.print_summary()
            return
            
        # Test connection
        if not await self.test_connection():
            self.print_summary()
            return
            
        # Test data fetcher
        await self.test_data_fetcher()
        
        # Test data manager
        self.test_data_manager()
        
        # Test specific data types
        await self.test_forex_data()
        await self.test_stock_data()
        
        # Test fallback logic
        self.test_fallback_logic()
        
        # Cleanup
        if self.connection:
            try:
                await self.connection.disconnect()
                print("\n🔌 Disconnected from IB")
            except Exception as e:
                print(f"\n⚠️  Disconnect error: {e}")
                
        self.print_summary()


async def main():
    """Main test function."""
    tester = IBIntegrationTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    # Run the async test suite using ib_insync's util.run to avoid event loop conflicts
    from ib_insync import util
    util.run(main())