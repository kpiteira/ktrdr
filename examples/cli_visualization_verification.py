#!/usr/bin/env python3
"""
CLI Visualization Verification Script

This script verifies the functionality of the visualization CLI commands
added in Task 3.4. It uses the subprocess module to run the commands
and checks for expected outputs.
"""

import os
import subprocess
import sys
from pathlib import Path

# Create output directory if it doesn't exist
output_dir = Path('output')
output_dir.mkdir(exist_ok=True)

# Define color codes for prettier output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
BLUE = '\033[0;34m'
YELLOW = '\033[0;33m'
NC = '\033[0m'  # No Color

def print_header(text):
    """Print a formatted header."""
    print(f"\n{BLUE}=== {text} ==={NC}")

def print_command(cmd):
    """Print a formatted command."""
    cmd_str = ' '.join(cmd)
    print(f"{YELLOW}Running: {cmd_str}{NC}")

def run_command(cmd, check_success=True):
    """Run a command and return the result."""
    print_command(cmd)
    try:
        result = subprocess.run(cmd, check=check_success, capture_output=True, text=True)
        return result
    except subprocess.CalledProcessError as e:
        print(f"{RED}Command failed with exit code {e.returncode}{NC}")
        print(f"{RED}Error output: {e.stderr}{NC}")
        return e

def check_file_exists(filepath):
    """Check if a file exists and print the result."""
    path = Path(filepath)
    if path.exists():
        size_kb = path.stat().st_size / 1024
        print(f"{GREEN}✓ File {filepath} created successfully ({size_kb:.1f} KB){NC}")
        return True
    else:
        print(f"{RED}✗ File {filepath} was not created{NC}")
        return False

def main():
    """Run the verification tests for CLI visualization commands."""
    print_header("KTRDR CLI Visualization Verification")
    
    # Check if the CLI script exists
    cli_script = Path('ktrdr_cli.py')
    if not cli_script.exists():
        print(f"{RED}Error: ktrdr_cli.py not found. Make sure you run this from the project root.{NC}")
        sys.exit(1)

    # Test 1: Check help for plot command
    print_header("Test 1: Checking help for plot command")
    result = run_command(['python', 'ktrdr_cli.py', 'plot', '--help'])
    if "Create and save interactive price charts" in result.stdout:
        print(f"{GREEN}✓ Help command shows expected documentation{NC}")
    else:
        print(f"{RED}✗ Help command does not show expected documentation{NC}")
    
    # Test 2: Check help for plot-indicators command
    print_header("Test 2: Checking help for plot-indicators command")
    result = run_command(['python', 'ktrdr_cli.py', 'plot-indicators', '--help'])
    if "Create multi-indicator charts" in result.stdout:
        print(f"{GREEN}✓ Help command shows expected documentation{NC}")
    else:
        print(f"{RED}✗ Help command does not show expected documentation{NC}")
    
    # Test 3: Create a simple candlestick chart
    print_header("Test 3: Creating a simple candlestick chart")
    output_file = output_dir / "verification_basic_chart.html"
    run_command(['python', 'ktrdr_cli.py', 'plot', 'MSFT', '--timeframe', '1h', '--output', str(output_file)])
    check_file_exists(output_file)
    
    # Test 4: Create a chart with an SMA indicator overlay
    print_header("Test 4: Creating a chart with an SMA indicator overlay")
    output_file = output_dir / "verification_sma_overlay.html"
    run_command(['python', 'ktrdr_cli.py', 'plot', 'MSFT', '--timeframe', '1h',
                '--indicator', 'SMA', '--period', '20',
                '--output', str(output_file)])
    check_file_exists(output_file)
    
    # Test 5: Create a chart with RSI in a separate panel
    print_header("Test 5: Creating a chart with RSI in a separate panel")
    output_file = output_dir / "verification_rsi_panel.html"
    run_command(['python', 'ktrdr_cli.py', 'plot', 'MSFT', '--timeframe', '1h',
                '--indicator', 'RSI', '--period', '14', '--panel',
                '--output', str(output_file)])
    check_file_exists(output_file)
    
    # Test 6: Create a chart with light theme
    print_header("Test 6: Creating a chart with light theme")
    output_file = output_dir / "verification_light_theme.html"
    run_command(['python', 'ktrdr_cli.py', 'plot', 'MSFT', '--timeframe', '1h', 
                '--theme', 'light',
                '--output', str(output_file)])
    check_file_exists(output_file)
    
    # Test 7: Create a multi-indicator chart
    print_header("Test 7: Creating a multi-indicator chart")
    output_file = output_dir / "verification_multi_indicator.html"
    run_command(['python', 'ktrdr_cli.py', 'plot-indicators', 'MSFT', '--timeframe', '1h',
                '--output', str(output_file)])
    check_file_exists(output_file)

    # Summary
    print_header("Verification Complete")
    print("The HTML files have been generated in the output directory.")
    print("Open them in your browser to verify the visualizations are correct.")
    print(f"For example: open {output_dir}/verification_multi_indicator.html")

if __name__ == "__main__":
    main()