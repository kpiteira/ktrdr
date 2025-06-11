#!/usr/bin/env python3
"""
Test the clean output of the new load-data command.
"""

import subprocess
import sys

def test_clean_output():
    """Test that load-data has clean output by default."""
    print("🧪 Testing clean output for load-data command...")
    print("=" * 60)
    
    # Test the command without verbose flag
    print("📋 Command: ktrdr load-data CHFUSD --timeframe 1h --mode tail")
    print("📋 Expected: Clean output with minimal logging")
    print("=" * 60)
    
    try:
        # Run the command and capture output
        result = subprocess.run([
            sys.executable, "-m", "ktrdr.cli.commands", 
            "load-data", "CHFUSD", 
            "--timeframe", "1h", 
            "--mode", "tail"
        ], capture_output=True, text=True, timeout=30)
        
        print("📤 STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("\n📤 STDERR:")
            print(result.stderr)
        
        print(f"\n📊 Return code: {result.returncode}")
        
        # Analyze output
        lines = result.stdout.split('\n') + result.stderr.split('\n')
        verbose_indicators = [
            "API configuration loaded",
            "API initialized", 
            "Logging configured",
            "INFO | ktrdr",
            "DEBUG | ktrdr"
        ]
        
        verbose_count = sum(1 for line in lines for indicator in verbose_indicators if indicator in line)
        
        if verbose_count == 0:
            print("✅ SUCCESS: Clean output - no verbose backend logs!")
        else:
            print(f"⚠️  ISSUE: Found {verbose_count} verbose log lines")
            print("These lines should be suppressed unless --verbose is used:")
            for line in lines:
                for indicator in verbose_indicators:
                    if indicator in line:
                        print(f"  - {line.strip()}")
        
    except subprocess.TimeoutExpired:
        print("⏰ Command timed out (expected for IB operations without connection)")
    except Exception as e:
        print(f"❌ Error running command: {e}")

if __name__ == "__main__":
    test_clean_output()