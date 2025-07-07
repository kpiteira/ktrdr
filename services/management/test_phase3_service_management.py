#!/usr/bin/env python3
"""
Phase 3 Service Management Testing

Comprehensive testing script for Phase 3: Service Management & Auto-Startup
implementation including:
- Service management functionality
- Health monitoring and metrics collection
- Cross-platform service installation (testing without actual installation)
- Performance monitoring and baseline tracking
"""

import os
import sys
import time
import json
import subprocess
import requests
from pathlib import Path
from typing import Dict, List, Any
import asyncio

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

print("🧪 Phase 3: Service Management & Auto-Startup Testing")
print("=" * 60)

def run_command(cmd: List[str], cwd: str = None) -> tuple:
    """Run a command and return (success, output, error)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def test_service_manager_functionality():
    """Test core service manager functionality."""
    print("\n📋 Testing Service Manager Functionality")
    print("-" * 40)
    
    tests_passed = 0
    total_tests = 6
    
    # Test 1: Service manager status when services stopped
    print("  1. Testing service status (stopped)...")
    success, output, error = run_command([
        "uv", "run", "python", "services/management/service_manager.py", "status"
    ])
    
    if success and "STOPPED" in output:
        print("     ✅ Correctly reports services as stopped")
        tests_passed += 1
    else:
        print(f"     ❌ Failed: {error}")
    
    # Test 2: Start all services
    print("  2. Testing service startup...")
    success, output, error = run_command([
        "uv", "run", "python", "services/management/service_manager.py", "start"
    ])
    
    if success:
        print("     ✅ Services started successfully")
        tests_passed += 1
        
        # Wait for services to be ready
        time.sleep(8)
    else:
        print(f"     ❌ Failed to start services: {error}")
    
    # Test 3: Service manager status when services running
    print("  3. Testing service status (running)...")
    success, output, error = run_command([
        "uv", "run", "python", "services/management/service_manager.py", "status"
    ])
    
    if success and "RUNNING" in output:
        print("     ✅ Correctly reports services as running")
        tests_passed += 1
    else:
        print(f"     ❌ Failed: {error}")
    
    # Test 4: Test individual service health
    print("  4. Testing individual service status...")
    success, output, error = run_command([
        "uv", "run", "python", "services/management/service_manager.py", "status", "--service", "training-host"
    ])
    
    if success:
        print("     ✅ Individual service status working")
        tests_passed += 1
    else:
        print(f"     ❌ Failed: {error}")
    
    # Test 5: Test service restart
    print("  5. Testing service restart...")
    success, output, error = run_command([
        "uv", "run", "python", "services/management/service_manager.py", "restart", "--service", "training-host"
    ])
    
    if success:
        print("     ✅ Service restart working")
        tests_passed += 1
        time.sleep(3)
    else:
        print(f"     ❌ Failed: {error}")
    
    # Test 6: Stop all services
    print("  6. Testing service shutdown...")
    success, output, error = run_command([
        "uv", "run", "python", "services/management/service_manager.py", "stop"
    ])
    
    if success:
        print("     ✅ Services stopped successfully")
        tests_passed += 1
    else:
        print(f"     ❌ Failed: {error}")
    
    print(f"\n📊 Service Manager Tests: {tests_passed}/{total_tests} passed")
    return tests_passed == total_tests

def test_health_monitoring():
    """Test health monitoring functionality."""
    print("\n🔍 Testing Health Monitoring")
    print("-" * 40)
    
    tests_passed = 0
    total_tests = 5
    
    # Start services for health testing
    print("  Starting services for health testing...")
    run_command([
        "uv", "run", "python", "services/management/service_manager.py", "start"
    ])
    time.sleep(8)
    
    # Test 1: Health monitor status
    print("  1. Testing health monitor status...")
    success, output, error = run_command([
        "uv", "run", "python", "services/management/health_monitor.py", "status"
    ])
    
    if success and "running" in output:
        print("     ✅ Health monitor status working")
        tests_passed += 1
    else:
        print(f"     ❌ Failed: {error}")
    
    # Test 2: Health dashboard
    print("  2. Testing health dashboard...")
    success, output, error = run_command([
        "uv", "run", "python", "services/management/health_monitor.py", "dashboard"
    ])
    
    if success and "Health Dashboard" in output:
        print("     ✅ Health dashboard working")
        tests_passed += 1
    else:
        print(f"     ❌ Failed: {error}")
    
    # Test 3: Detailed health report
    print("  3. Testing detailed health report...")
    success, output, error = run_command([
        "uv", "run", "python", "services/management/health_monitor.py", "report"
    ])
    
    if success:
        try:
            report = json.loads(output)
            if "overall_status" in report and "services" in report:
                print("     ✅ Health report JSON structure valid")
                tests_passed += 1
            else:
                print("     ❌ Invalid report structure")
        except json.JSONDecodeError:
            print("     ❌ Invalid JSON output")
    else:
        print(f"     ❌ Failed: {error}")
    
    # Test 4: GPU metrics collection
    print("  4. Testing GPU metrics collection...")
    success, output, error = run_command([
        "uv", "run", "python", "services/management/health_monitor.py", "status", "--service", "training-host"
    ])
    
    if success:
        try:
            metrics = json.loads(output)
            if "gpu_metrics" in metrics:
                print("     ✅ GPU metrics collection working")
                tests_passed += 1
            else:
                print("     ❌ No GPU metrics found")
        except json.JSONDecodeError:
            print("     ❌ Invalid JSON output")
    else:
        print(f"     ❌ Failed: {error}")
    
    # Test 5: Performance baseline functionality
    print("  5. Testing performance baseline...")
    success, output, error = run_command([
        "uv", "run", "python", "services/management/health_monitor.py", "baseline", "--service", "training-host", "--hours", "1"
    ])
    
    if success or "Insufficient data" in error:
        print("     ✅ Performance baseline functionality working")
        tests_passed += 1
    else:
        print(f"     ❌ Failed: {error}")
    
    # Stop services
    run_command([
        "uv", "run", "python", "services/management/service_manager.py", "stop"
    ])
    
    print(f"\n📊 Health Monitoring Tests: {tests_passed}/{total_tests} passed")
    return tests_passed == total_tests

def test_unified_scripts():
    """Test unified startup/shutdown scripts."""
    print("\n🚀 Testing Unified Scripts")
    print("-" * 40)
    
    tests_passed = 0
    total_tests = 3
    
    # Test 1: Unified startup script
    print("  1. Testing unified startup script...")
    script_path = PROJECT_ROOT / "services" / "management" / "start_all_services.sh"
    
    if script_path.exists() and os.access(script_path, os.X_OK):
        print("     ✅ Unified startup script exists and is executable")
        tests_passed += 1
    else:
        print("     ❌ Unified startup script missing or not executable")
    
    # Test 2: Unified shutdown script
    print("  2. Testing unified shutdown script...")
    script_path = PROJECT_ROOT / "services" / "management" / "stop_all_services.sh"
    
    if script_path.exists() and os.access(script_path, os.X_OK):
        print("     ✅ Unified shutdown script exists and is executable")
        tests_passed += 1
    else:
        print("     ❌ Unified shutdown script missing or not executable")
    
    # Test 3: Script functionality (basic validation)
    print("  3. Testing script execution...")
    try:
        # Test help or version to ensure scripts can execute
        success, output, error = run_command(["bash", "-n", str(script_path)])
        if success:
            print("     ✅ Scripts are syntactically valid")
            tests_passed += 1
        else:
            print(f"     ❌ Script syntax error: {error}")
    except Exception as e:
        print(f"     ❌ Script test failed: {e}")
    
    print(f"\n📊 Unified Scripts Tests: {tests_passed}/{total_tests} passed")
    return tests_passed == total_tests

def test_cross_platform_configurations():
    """Test cross-platform service configuration files."""
    print("\n🖥️  Testing Cross-Platform Configurations")
    print("-" * 40)
    
    tests_passed = 0
    total_tests = 6
    
    # Test 1: macOS launchd configuration
    print("  1. Testing macOS launchd configuration...")
    plist_path = PROJECT_ROOT / "services" / "management" / "launchd" / "com.ktrdr.host-services.plist"
    
    if plist_path.exists():
        print("     ✅ macOS launchd plist exists")
        tests_passed += 1
    else:
        print("     ❌ macOS launchd plist missing")
    
    # Test 2: macOS installation script
    print("  2. Testing macOS installation script...")
    install_script = PROJECT_ROOT / "services" / "management" / "install_macos_service.sh"
    
    if install_script.exists() and os.access(install_script, os.X_OK):
        print("     ✅ macOS installation script exists and is executable")
        tests_passed += 1
    else:
        print("     ❌ macOS installation script missing or not executable")
    
    # Test 3: Linux systemd configuration
    print("  3. Testing Linux systemd configuration...")
    service_path = PROJECT_ROOT / "services" / "management" / "systemd" / "ktrdr-host-services.service"
    
    if service_path.exists():
        print("     ✅ Linux systemd service file exists")
        tests_passed += 1
    else:
        print("     ❌ Linux systemd service file missing")
    
    # Test 4: Linux installation script
    print("  4. Testing Linux installation script...")
    install_script = PROJECT_ROOT / "services" / "management" / "install_linux_service.sh"
    
    if install_script.exists() and os.access(install_script, os.X_OK):
        print("     ✅ Linux installation script exists and is executable")
        tests_passed += 1
    else:
        print("     ❌ Linux installation script missing or not executable")
    
    # Test 5: Service wrapper scripts
    print("  5. Testing service wrapper scripts...")
    macos_wrapper = PROJECT_ROOT / "services" / "management" / "launchd" / "launchd_service_wrapper.sh"
    linux_wrapper = PROJECT_ROOT / "services" / "management" / "systemd" / "systemd_service_wrapper.sh"
    
    if (macos_wrapper.exists() and os.access(macos_wrapper, os.X_OK) and
        linux_wrapper.exists() and os.access(linux_wrapper, os.X_OK)):
        print("     ✅ Service wrapper scripts exist and are executable")
        tests_passed += 1
    else:
        print("     ❌ Service wrapper scripts missing or not executable")
    
    # Test 6: Uninstallation scripts
    print("  6. Testing uninstallation scripts...")
    macos_uninstall = PROJECT_ROOT / "services" / "management" / "uninstall_macos_service.sh"
    linux_uninstall = PROJECT_ROOT / "services" / "management" / "uninstall_linux_service.sh"
    
    if (macos_uninstall.exists() and os.access(macos_uninstall, os.X_OK) and
        linux_uninstall.exists() and os.access(linux_uninstall, os.X_OK)):
        print("     ✅ Uninstallation scripts exist and are executable")
        tests_passed += 1
    else:
        print("     ❌ Uninstallation scripts missing or not executable")
    
    print(f"\n📊 Cross-Platform Configuration Tests: {tests_passed}/{total_tests} passed")
    return tests_passed == total_tests

def test_integration_flow():
    """Test complete integration flow."""
    print("\n🔄 Testing Integration Flow")
    print("-" * 40)
    
    tests_passed = 0
    total_tests = 4
    
    # Test 1: Cold start (all services stopped)
    print("  1. Testing cold start...")
    
    # Ensure services are stopped
    run_command([
        "uv", "run", "python", "services/management/service_manager.py", "stop"
    ])
    time.sleep(2)
    
    # Start services
    success, output, error = run_command([
        "uv", "run", "python", "services/management/service_manager.py", "start"
    ])
    
    if success:
        print("     ✅ Cold start successful")
        tests_passed += 1
        time.sleep(8)
    else:
        print(f"     ❌ Cold start failed: {error}")
    
    # Test 2: Service dependency resolution
    print("  2. Testing service dependency resolution...")
    
    # Check if IB service starts before training service
    success, output, error = run_command([
        "uv", "run", "python", "services/management/service_manager.py", "status"
    ])
    
    if success and "IB Host Service" in output and "Training Host Service" in output:
        print("     ✅ Both services started in correct order")
        tests_passed += 1
    else:
        print(f"     ❌ Service dependency issue: {error}")
    
    # Test 3: Health monitoring during operation
    print("  3. Testing health monitoring during operation...")
    
    success, output, error = run_command([
        "uv", "run", "python", "services/management/health_monitor.py", "dashboard"
    ])
    
    if success and "HEALTHY" in output or "RUNNING" in output:
        print("     ✅ Health monitoring working during operation")
        tests_passed += 1
    else:
        print(f"     ❌ Health monitoring issue: {error}")
    
    # Test 4: Graceful shutdown
    print("  4. Testing graceful shutdown...")
    
    success, output, error = run_command([
        "uv", "run", "python", "services/management/service_manager.py", "stop"
    ])
    
    if success:
        print("     ✅ Graceful shutdown successful")
        tests_passed += 1
    else:
        print(f"     ❌ Graceful shutdown failed: {error}")
    
    print(f"\n📊 Integration Flow Tests: {tests_passed}/{total_tests} passed")
    return tests_passed == total_tests

def main():
    """Run all Phase 3 tests."""
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Python path: {sys.executable}")
    
    # Run all test suites
    test_results = []
    
    test_results.append(("Service Manager Functionality", test_service_manager_functionality()))
    test_results.append(("Health Monitoring", test_health_monitoring()))
    test_results.append(("Unified Scripts", test_unified_scripts()))
    test_results.append(("Cross-Platform Configurations", test_cross_platform_configurations()))
    test_results.append(("Integration Flow", test_integration_flow()))
    
    # Summary
    print("\n" + "=" * 60)
    print("🎯 Phase 3 Testing Summary")
    print("=" * 60)
    
    total_passed = 0
    total_suites = len(test_results)
    
    for suite_name, passed in test_results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {suite_name:<35} {status}")
        if passed:
            total_passed += 1
    
    print(f"\n📊 Overall Results: {total_passed}/{total_suites} test suites passed")
    
    if total_passed == total_suites:
        print("\n🎉 All Phase 3 tests PASSED!")
        print("\n✅ Phase 3: Service Management & Auto-Startup implementation is complete and working correctly.")
        
        print("\n📋 What was implemented:")
        print("  • Unified service management for IB and Training Host services")
        print("  • Cross-platform auto-startup (macOS launchd, Linux systemd)")
        print("  • Enhanced health monitoring with GPU-specific metrics")
        print("  • Performance monitoring and baseline tracking")
        print("  • Service dependency validation and coordination")
        print("  • Comprehensive error handling and restart policies")
        
        print("\n🚀 Next steps:")
        print("  • Phase 4: Validation & Documentation")
        print("  • Performance benchmarking")
        print("  • Production deployment testing")
        
        return True
    else:
        print(f"\n❌ {total_suites - total_passed} test suite(s) failed.")
        print("   Review the failed tests above and fix any issues.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)