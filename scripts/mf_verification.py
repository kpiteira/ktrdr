"""
Verification script for triangular membership functions.
"""

import matplotlib.pyplot as plt
import pandas as pd

from ktrdr.fuzzy.config import TriangularMFConfig
from ktrdr.fuzzy.membership import TriangularMF


def verify_triangular_mf():
    """Verify the triangular membership function implementation with visualization."""
    # Create several triangular membership functions
    standard_mf = TriangularMF([20, 50, 80])
    left_shoulder_mf = TriangularMF([20, 20, 80])
    right_shoulder_mf = TriangularMF([20, 80, 80])
    singleton_mf = TriangularMF([50, 50, 50])

    # Create input values for visualization
    x = range(0, 100)

    # Evaluate each membership function for all x values
    standard_y = [standard_mf.evaluate(val) for val in x]
    left_shoulder_y = [left_shoulder_mf.evaluate(val) for val in x]
    right_shoulder_y = [right_shoulder_mf.evaluate(val) for val in x]
    singleton_y = [singleton_mf.evaluate(val) for val in x]

    # Create visualization
    plt.figure(figsize=(10, 6))
    plt.plot(x, standard_y, label="Standard Triangle (20, 50, 80)")
    plt.plot(x, left_shoulder_y, label="Left Shoulder (20, 20, 80)")
    plt.plot(x, right_shoulder_y, label="Right Shoulder (20, 80, 80)")
    plt.plot(x, singleton_y, label="Singleton (50, 50, 50)")

    plt.xlabel("Input Value")
    plt.ylabel("Membership Degree")
    plt.title("Triangular Membership Function Examples")
    plt.grid(True)
    plt.legend()
    plt.ylim(-0.05, 1.05)

    # Save visualization
    plt.savefig("output/triangular_mf_examples.png")
    print("Visualization saved to 'output/triangular_mf_examples.png'")

    # Test with Series for vectorized evaluation
    series_x = pd.Series(x)
    standard_series_y = standard_mf.evaluate(series_x)

    print("\nVectorized evaluation with Series:")
    print(f"Input shape: {series_x.shape}")
    print(f"Output shape: {standard_series_y.shape}")

    # Demonstrate integration with config system
    config = TriangularMFConfig(type="triangular", parameters=[10, 30, 60])
    mf = TriangularMF(config.parameters)

    print("\nCreated from config:")
    print(f"Config: {config}")
    print(f"MF: {mf}")

    # Print membership values at key points
    print("\nMembership values at key points:")
    print(f"At a=10: {mf.evaluate(10)}")
    print(f"At b=30: {mf.evaluate(30)}")
    print(f"At c=60: {mf.evaluate(60)}")
    print(f"At midpoint between a and b: {mf.evaluate(20)}")
    print(f"At midpoint between b and c: {mf.evaluate(45)}")


if __name__ == "__main__":
    verify_triangular_mf()
