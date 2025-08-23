"""
Example demonstrating the extended fuzzy configuration system with strategy overrides.

This script shows how to:
1. Load the default fuzzy configuration
2. Load strategy-specific fuzzy configurations
3. Merge default and strategy-specific configurations
4. Compare fuzzy configurations from different strategies
"""

import logging
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ktrdr.fuzzy.config import FuzzyConfigLoader
from ktrdr.fuzzy.membership import TriangularMF

# Set up logging for this example
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Define project directories
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


def plot_membership_functions(config_dict, title, indicator="rsi"):
    """
    Plot membership functions for a specific indicator from a configuration.

    Args:
        config_dict: Fuzzy configuration dictionary
        title: Plot title
        indicator: Indicator name to plot (default: rsi)
    """
    if indicator not in config_dict:
        logger.warning(f"Indicator '{indicator}' not found in configuration.")
        return

    indicator_config = config_dict[indicator].root

    # Create a range of indicator values to plot
    x = np.linspace(0, 100, 1000) if indicator == "rsi" else np.linspace(-10, 10, 1000)

    plt.figure(figsize=(10, 6))

    # Plot each membership function
    for set_name, mf_config in indicator_config.items():
        # Create membership function from config
        if mf_config.type == "triangular":
            # Pass parameters as a list to match the TriangularMF constructor
            mf = TriangularMF(mf_config.parameters)

            # Calculate membership degrees for the range of values
            y = [mf.evaluate(val) for val in x]

            # Plot the membership function
            plt.plot(x, y, label=f"{set_name}")

    plt.title(f"{title} - {indicator.upper()} Fuzzy Sets")
    plt.xlabel(f"{indicator} value")
    plt.ylabel("Membership degree")
    plt.legend()
    plt.grid(True)
    return plt


def main():
    """Run the fuzzy configuration demonstration."""
    logger.info("Starting fuzzy configuration demonstration")

    # Initialize the loader with the project's config directory
    loader = FuzzyConfigLoader(config_dir=CONFIG_DIR)

    # 1. Load the default fuzzy configuration
    default_config = loader.load_default()
    logger.info(
        f"Loaded default fuzzy configuration with indicators: {list(default_config.root.keys())}"
    )

    # 2. Load strategy-specific configurations
    strategies = ["trend_momentum_strategy", "mean_reversion_strategy"]
    strategy_configs = {}

    for strategy in strategies:
        try:
            # Load strategy config with default overrides
            strategy_config = loader.load_with_strategy_override(strategy)
            strategy_configs[strategy] = strategy_config
            logger.info(
                f"Loaded '{strategy}' configuration with indicators: {list(strategy_config.root.keys())}"
            )

            # Count the total number of fuzzy sets across all indicators
            total_sets = sum(
                len(ind_config.root) for ind_config in strategy_config.root.values()
            )
            logger.info(
                f"'{strategy}' has {len(strategy_config.root)} indicators with {total_sets} total fuzzy sets"
            )

        except Exception as e:
            logger.error(f"Failed to load '{strategy}': {e}")

    # 3. Display RSI fuzzy sets for each configuration
    plt.figure(figsize=(15, 10))

    # Plot default configuration
    plt1 = plot_membership_functions(default_config.root, "Default Config", "rsi")
    plt1.savefig(PROJECT_ROOT / "output" / "default_rsi_fuzzy_sets.png")

    # Plot strategy configurations
    for strategy, config in strategy_configs.items():
        plt2 = plot_membership_functions(
            config.root, f"{strategy.replace('_', ' ').title()}", "rsi"
        )
        plt2.savefig(PROJECT_ROOT / "output" / f"{strategy}_rsi_fuzzy_sets.png")

    # 4. Show unique indicators in each strategy
    for strategy, config in strategy_configs.items():
        unique_indicators = set(config.root.keys()) - set(default_config.root.keys())
        if unique_indicators:
            logger.info(f"'{strategy}' adds these new indicators: {unique_indicators}")

            # Plot an example of a unique indicator if present
            if unique_indicators:
                unique_ind = list(unique_indicators)[0]
                plt3 = plot_membership_functions(
                    config.root, f"{strategy.replace('_', ' ').title()}", unique_ind
                )
                plt3.savefig(
                    PROJECT_ROOT / "output" / f"{strategy}_{unique_ind}_fuzzy_sets.png"
                )

    logger.info(
        "Fuzzy configuration demonstration completed. Check the 'output' directory for visualization results."
    )


if __name__ == "__main__":
    main()
