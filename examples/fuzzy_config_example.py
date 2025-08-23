#!/usr/bin/env python
"""
Example script demonstrating how to load and validate fuzzy set configurations.
"""

import yaml
from pprint import pprint

from ktrdr.fuzzy.config import FuzzyConfigLoader
from ktrdr.errors import ConfigurationError


def main():
    """
    Load fuzzy configuration from a YAML file and display the validated configuration.
    """
    print("Loading fuzzy configuration from config/fuzzy.yaml...")

    try:
        # Load YAML file
        with open("config/fuzzy.yaml", "r") as file:
            config_dict = yaml.safe_load(file)

        # Validate configuration
        fuzzy_config = FuzzyConfigLoader.load(config_dict)
        print("\nFuzzy configuration loaded successfully!")

        # Print indicator names
        print(f"\nConfigured indicators: {list(fuzzy_config.root.keys())}")

        # For each indicator, print its fuzzy sets
        for indicator, fuzzy_sets in fuzzy_config.root.items():
            print(f"\n{indicator.upper()} Fuzzy Sets:")

            for set_name, membership_func in fuzzy_sets.root.items():
                a, b, c = membership_func.parameters
                print(f"  - {set_name}: Triangular MF [a={a}, b={b}, c={c}]")

        # Try with an invalid configuration to demonstrate validation
        print("\nTrying with an invalid configuration (b < a):")
        invalid_config = {
            "rsi": {
                "invalid": {
                    "type": "triangular",
                    "parameters": [50, 30, 70],  # Invalid: b < a
                }
            }
        }

        try:
            FuzzyConfigLoader.load(invalid_config)
            print("This should not print as an error should be raised!")
        except ConfigurationError as e:
            print(f"Correctly caught error: {e}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
