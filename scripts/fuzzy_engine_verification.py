#!/usr/bin/env python3
"""
Verification example for Task 4.3: FuzzyEngine implementation.

This script demonstrates the functionality of the FuzzyEngine class for
transforming indicator values into fuzzy membership degrees.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from ktrdr.fuzzy import FuzzyConfig, FuzzyEngine, TriangularMF

# Create a simple fuzzy configuration for RSI indicator
fuzzy_config_dict = {
    "rsi": {
        "low": {"type": "triangular", "parameters": [0.0, 30.0, 50.0]},
        "medium": {"type": "triangular", "parameters": [30.0, 50.0, 70.0]},
        "high": {"type": "triangular", "parameters": [50.0, 70.0, 100.0]}
    }
}

# Create the FuzzyConfig object
fuzzy_config = FuzzyConfig.model_validate(fuzzy_config_dict)

# Initialize the FuzzyEngine with the configuration
engine = FuzzyEngine(fuzzy_config)

print(f"Available indicators: {engine.get_available_indicators()}")
print(f"Fuzzy sets for RSI: {engine.get_fuzzy_sets('rsi')}")
print(f"Output column names: {engine.get_output_names('rsi')}")

# Create a series of RSI values spanning the range 0-100
rsi_values = pd.Series([i * 10 for i in range(11)], name="RSI")
print("\nInput RSI values:")
print(rsi_values)

# Fuzzify the RSI values
membership_degrees = engine.fuzzify("rsi", rsi_values)
print("\nFuzzified membership degrees:")
print(membership_degrees)

# Simple visualization of the membership degrees
try:
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    plt.figure(figsize=(10, 6))
    
    # Plot membership degrees for each fuzzy set
    plt.plot(rsi_values, membership_degrees["rsi_low"], label="Low")
    plt.plot(rsi_values, membership_degrees["rsi_medium"], label="Medium")
    plt.plot(rsi_values, membership_degrees["rsi_high"], label="High")
    
    plt.xlabel("RSI Value")
    plt.ylabel("Membership Degree")
    plt.title("RSI Fuzzy Membership Functions")
    plt.legend()
    plt.grid(True)
    
    # Save the plot
    output_path = output_dir / "fuzzy_engine_verification.png"
    plt.savefig(output_path)
    print(f"\nPlot saved to: {output_path}")
    
    # Show the plot if run interactively
    plt.show()
except Exception as e:
    print(f"Could not create visualization: {e}")

# Demonstrate scalar fuzzification
scalar_rsi = 45.0
scalar_result = engine.fuzzify("rsi", scalar_rsi)
print(f"\nFuzzifying scalar RSI value {scalar_rsi}:")
print(f"Low membership: {scalar_result['rsi_low']:.2f}")
print(f"Medium membership: {scalar_result['rsi_medium']:.2f}")
print(f"High membership: {scalar_result['rsi_high']:.2f}")

# Demonstrate error handling for unknown indicator
try:
    engine.fuzzify("unknown", 50.0)
except Exception as e:
    print(f"\nCorrect error handling: {e}")

print("\nVerification complete!")