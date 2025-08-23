#!/usr/bin/env python3
"""
Comprehensive validation script for Task 4.5: Test Fuzzy Logic Implementation.

This script demonstrates numerical validation of fuzzy membership functions
and visualizes the membership degrees for different indicator inputs.
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Make sure ktrdr module can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ktrdr.fuzzy import FuzzyEngine, FuzzyConfig, TriangularMF
from ktrdr.fuzzy.config import FuzzyConfigLoader


def validate_triangular_membership_function():
    """Validate triangular membership function behavior with various inputs."""
    print("\n====== Validating Triangular Membership Function ======")

    # Create triangular membership functions with different parameters
    standard_mf = TriangularMF([20, 50, 80])
    left_shoulder_mf = TriangularMF([20, 20, 80])
    right_shoulder_mf = TriangularMF([20, 80, 80])
    singleton_mf = TriangularMF([50, 50, 50])

    print("\nMembership function details:")
    print(f"Standard triangle: {standard_mf}")
    print(f"Left shoulder: {left_shoulder_mf}")
    print(f"Right shoulder: {right_shoulder_mf}")
    print(f"Singleton: {singleton_mf}")

    # Test key points for each membership function
    test_points = [0, 20, 35, 50, 65, 80, 100]

    print("\nMembership values at key points:")
    print("Point  | Standard | Left Shoulder | Right Shoulder | Singleton")
    print("-----------------------------------------------------------")

    for point in test_points:
        std_val = standard_mf.evaluate(point)
        left_val = left_shoulder_mf.evaluate(point)
        right_val = right_shoulder_mf.evaluate(point)
        single_val = singleton_mf.evaluate(point)
        print(
            f"{point:5d} | {std_val:7.3f} | {left_val:13.3f} | {right_val:14.3f} | {single_val:9.3f}"
        )

    # Visualize membership functions
    x = range(0, 100)
    standard_y = [standard_mf.evaluate(val) for val in x]
    left_y = [left_shoulder_mf.evaluate(val) for val in x]
    right_y = [right_shoulder_mf.evaluate(val) for val in x]
    singleton_y = [singleton_mf.evaluate(val) for val in x]

    plt.figure(figsize=(10, 6))
    plt.plot(x, standard_y, label="Standard (20, 50, 80)")
    plt.plot(x, left_y, label="Left Shoulder (20, 20, 80)")
    plt.plot(x, right_y, label="Right Shoulder (20, 80, 80)")
    plt.plot(x, singleton_y, label="Singleton (50, 50, 50)")

    plt.title("Triangular Membership Function Variants")
    plt.xlabel("Input Value")
    plt.ylabel("Membership Degree")
    plt.legend()
    plt.grid(True)
    plt.ylim(-0.05, 1.05)

    # Ensure output directory exists
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    plt.savefig(output_dir / "fuzzy_membership_variants.png")
    print(
        f"\nMembership function visualization saved to output/fuzzy_membership_variants.png"
    )

    # Test with vectorized inputs
    print("\nValidating vectorized evaluation:")

    # Create a pandas Series with various values
    series_input = pd.Series([0, 20, 35, 50, 65, 80, 100])
    series_output = standard_mf.evaluate(series_input)

    print("Series input:  ", series_input.tolist())
    print("Series output: ", [round(x, 3) for x in series_output.tolist()])

    # Create a numpy array
    array_input = np.array([0, 20, 35, 50, 65, 80, 100])
    array_output = standard_mf.evaluate(array_input)

    print("Numpy input:   ", array_input.tolist())
    print("Numpy output:  ", [round(x, 3) for x in array_output.tolist()])

    return True


def validate_fuzzy_engine():
    """Validate the FuzzyEngine with known indicator values and expected outputs."""
    print("\n====== Validating Fuzzy Engine ======")

    # Define a simple fuzzy configuration
    config_dict = {
        "rsi": {
            "low": {"type": "triangular", "parameters": [0.0, 30.0, 50.0]},
            "medium": {"type": "triangular", "parameters": [30.0, 50.0, 70.0]},
            "high": {"type": "triangular", "parameters": [50.0, 70.0, 100.0]},
        },
        "macd": {
            "negative": {"type": "triangular", "parameters": [-10.0, -5.0, 0.0]},
            "neutral": {"type": "triangular", "parameters": [-2.0, 0.0, 2.0]},
            "positive": {"type": "triangular", "parameters": [0.0, 5.0, 10.0]},
        },
    }

    # Create FuzzyConfig and FuzzyEngine
    config = FuzzyConfig.model_validate(config_dict)
    engine = FuzzyEngine(config)

    print("\nAvailable indicators:", engine.get_available_indicators())
    print("RSI fuzzy sets:", engine.get_fuzzy_sets("rsi"))
    print("MACD fuzzy sets:", engine.get_fuzzy_sets("macd"))

    # Test with sample RSI values
    rsi_values = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    rsi_results = []

    print("\nRSI Fuzzification Results:")
    print("RSI Value | Low Membership | Medium Membership | High Membership")
    print("----------------------------------------------------------")

    for rsi in rsi_values:
        result = engine.fuzzify("rsi", rsi)
        rsi_results.append(result)
        print(
            f"{rsi:8} | {result['rsi_low']:13.3f} | {result['rsi_medium']:17.3f} | {result['rsi_high']:14.3f}"
        )

    # Test with sample MACD values
    macd_values = [-10, -7.5, -5, -2.5, 0, 2.5, 5, 7.5, 10]
    macd_results = []

    print("\nMACD Fuzzification Results:")
    print("MACD Value | Negative Membership | Neutral Membership | Positive Membership")
    print("-----------------------------------------------------------------")

    for macd in macd_values:
        result = engine.fuzzify("macd", macd)
        macd_results.append(result)
        print(
            f"{macd:9.1f} | {result['macd_negative']:18.3f} | {result['macd_neutral']:18.3f} | {result['macd_positive']:19.3f}"
        )

    # Visualize RSI fuzzy sets
    plt.figure(figsize=(10, 6))

    # Generate x values for smooth curves
    x_rsi = np.linspace(0, 100, 500)

    # Create a pandas Series for vectorized evaluation
    x_rsi_series = pd.Series(x_rsi)

    # Fuzzify the whole series at once
    rsi_membership = engine.fuzzify("rsi", x_rsi_series)

    # Plot membership functions
    plt.plot(x_rsi, rsi_membership["rsi_low"], label="Low", color="red")
    plt.plot(x_rsi, rsi_membership["rsi_medium"], label="Medium", color="yellow")
    plt.plot(x_rsi, rsi_membership["rsi_high"], label="High", color="green")

    plt.title("RSI Fuzzy Membership Functions")
    plt.xlabel("RSI Value")
    plt.ylabel("Membership Degree")
    plt.legend()
    plt.grid(True)
    plt.ylim(-0.05, 1.05)

    # Save the plot
    plt.savefig(output_dir / "rsi_membership_functions.png")
    print(
        f"\nRSI membership function visualization saved to output/rsi_membership_functions.png"
    )

    # Visualize MACD fuzzy sets
    plt.figure(figsize=(10, 6))

    # Generate x values for smooth curves
    x_macd = np.linspace(-10, 10, 500)

    # Create a pandas Series for vectorized evaluation
    x_macd_series = pd.Series(x_macd)

    # Fuzzify the whole series at once
    macd_membership = engine.fuzzify("macd", x_macd_series)

    # Plot membership functions
    plt.plot(x_macd, macd_membership["macd_negative"], label="Negative", color="red")
    plt.plot(x_macd, macd_membership["macd_neutral"], label="Neutral", color="yellow")
    plt.plot(x_macd, macd_membership["macd_positive"], label="Positive", color="green")

    plt.title("MACD Fuzzy Membership Functions")
    plt.xlabel("MACD Value")
    plt.ylabel("Membership Degree")
    plt.legend()
    plt.grid(True)
    plt.ylim(-0.05, 1.05)

    # Save the plot
    plt.savefig(output_dir / "macd_membership_functions.png")
    print(
        f"MACD membership function visualization saved to output/macd_membership_functions.png"
    )

    return True


def validate_fuzzy_config_loading():
    """Validate loading fuzzy configurations from YAML files."""
    print("\n====== Validating Fuzzy Configuration Loading ======")

    try:
        # Load the default fuzzy configuration
        loader = FuzzyConfigLoader()
        config = loader.load_default_config()

        print("\nSuccessfully loaded default fuzzy configuration from YAML files")
        print(f"Number of indicators: {len(config.root)}")

        # List available indicators and their fuzzy sets
        print("\nAvailable indicators and fuzzy sets:")
        for indicator, fuzzy_sets in config.root.items():
            print(f"  - {indicator}: {', '.join(fuzzy_sets.root.keys())}")

        # Test with a FuzzyEngine
        engine = FuzzyEngine(config)
        print("\nFuzzy engine successfully initialized with loaded configuration")

        # Verify fuzzy output for one indicator
        if "rsi" in engine.get_available_indicators():
            rsi_value = 50.0
            result = engine.fuzzify("rsi", rsi_value)
            print(f"\nFuzzified RSI value {rsi_value}:")
            for key, value in result.items():
                print(f"  {key}: {value:.3f}")

        return True

    except Exception as e:
        print(f"Error validating fuzzy configuration loading: {e}")
        return False


def validate_edge_cases():
    """Validate fuzzy logic edge cases."""
    print("\n====== Validating Edge Cases ======")

    # Create a fuzzy config with edge case scenarios
    config_dict = {
        "rsi": {
            # Standard membership functions
            "standard_low": {"type": "triangular", "parameters": [0.0, 30.0, 50.0]},
            "standard_high": {"type": "triangular", "parameters": [50.0, 70.0, 100.0]},
            # Edge case: singleton (a = b = c)
            "singleton": {"type": "triangular", "parameters": [50.0, 50.0, 50.0]},
            # Edge case: left shoulder (a = b)
            "left_shoulder": {"type": "triangular", "parameters": [0.0, 0.0, 50.0]},
            # Edge case: right shoulder (b = c)
            "right_shoulder": {
                "type": "triangular",
                "parameters": [50.0, 100.0, 100.0],
            },
        }
    }

    config = FuzzyConfig.model_validate(config_dict)
    engine = FuzzyEngine(config)

    # Test with extreme input values
    extreme_values = [-1000, -100, -10, 0, 50, 100, 110, 1000]

    print("\nEdge Case Test Results:")
    print(
        "Value   | Standard Low | Standard High | Singleton | Left Shoulder | Right Shoulder"
    )
    print(
        "----------------------------------------------------------------------------"
    )

    for val in extreme_values:
        result = engine.fuzzify("rsi", val)
        std_low = result["rsi_standard_low"]
        std_high = result["rsi_standard_high"]
        singleton = result["rsi_singleton"]
        left_shoulder = result["rsi_left_shoulder"]
        right_shoulder = result["rsi_right_shoulder"]

        print(
            f"{val:7} | {std_low:11.3f} | {std_high:12.3f} | {singleton:9.3f} | {left_shoulder:13.3f} | {right_shoulder:14.3f}"
        )

    # Test with NaN values
    result_nan = engine.fuzzify("rsi", np.nan)
    print(
        "\nNaN input results in NaN membership degrees:",
        all(np.isnan(val) for val in result_nan.values()),
    )

    # Visualize edge case membership functions
    plt.figure(figsize=(10, 6))

    # Generate x values for smooth curves
    x = np.linspace(0, 100, 500)
    x_series = pd.Series(x)

    # Fuzzify the whole series at once
    membership = engine.fuzzify("rsi", x_series)

    # Plot membership functions
    plt.plot(
        x,
        membership["rsi_standard_low"],
        label="Standard Low",
        linestyle="-",
        color="blue",
    )
    plt.plot(
        x,
        membership["rsi_standard_high"],
        label="Standard High",
        linestyle="-",
        color="green",
    )
    plt.plot(
        x, membership["rsi_singleton"], label="Singleton", linestyle="-.", color="red"
    )
    plt.plot(
        x,
        membership["rsi_left_shoulder"],
        label="Left Shoulder",
        linestyle="--",
        color="orange",
    )
    plt.plot(
        x,
        membership["rsi_right_shoulder"],
        label="Right Shoulder",
        linestyle="--",
        color="purple",
    )

    plt.title("Edge Case Fuzzy Membership Functions")
    plt.xlabel("Input Value")
    plt.ylabel("Membership Degree")
    plt.legend()
    plt.grid(True)
    plt.ylim(-0.05, 1.05)

    # Save the plot
    plt.savefig(output_dir / "edge_case_membership_functions.png")
    print(
        f"\nEdge case visualization saved to output/edge_case_membership_functions.png"
    )

    return True


def validate_performance():
    """Validate the performance of fuzzy logic operations."""
    print("\n====== Validating Performance ======")

    # Define a simple fuzzy configuration
    config_dict = {
        "rsi": {
            "low": {"type": "triangular", "parameters": [0.0, 30.0, 50.0]},
            "medium": {"type": "triangular", "parameters": [30.0, 50.0, 70.0]},
            "high": {"type": "triangular", "parameters": [50.0, 70.0, 100.0]},
        }
    }

    config = FuzzyConfig.model_validate(config_dict)
    engine = FuzzyEngine(config)

    # Test with large datasets of various sizes
    sizes = [1000, 10000, 100000]

    print("\nPerformance Test Results:")
    print("Size    | Time (seconds) | Values per second")
    print("----------------------------------------")

    import time

    for size in sizes:
        # Create a random series of RSI values
        values = pd.Series(np.random.uniform(0, 100, size))

        # Measure execution time
        start_time = time.time()
        result = engine.fuzzify("rsi", values)
        end_time = time.time()

        execution_time = end_time - start_time
        values_per_second = size / execution_time

        print(f"{size:7} | {execution_time:14.6f} | {values_per_second:16.0f}")

    return True


if __name__ == "__main__":
    # Create output directory
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # Run all validation functions and track success
    success = True
    success = validate_triangular_membership_function() and success
    success = validate_fuzzy_engine() and success
    success = validate_fuzzy_config_loading() and success
    success = validate_edge_cases() and success
    success = validate_performance() and success

    # Final results
    if success:
        print("\n✅ All fuzzy logic validation tests completed successfully!")
    else:
        print(
            "\n❌ Some fuzzy logic validation tests failed. Check the output above for details."
        )

    print("\nOutput visualizations saved in the 'output' directory")
