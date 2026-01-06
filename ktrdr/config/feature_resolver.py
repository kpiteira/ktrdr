"""Feature resolver for v3 strategy configuration.

This module provides the FeatureResolver class that resolves nn_inputs
specifications into concrete ResolvedFeature objects. This is the single
source of truth for feature ordering used by both training and backtest.
"""

from dataclasses import dataclass

from ktrdr.config.models import StrategyConfigurationV3


@dataclass
class ResolvedFeature:
    """A fully resolved NN input feature.

    Attributes:
        feature_id: Full feature identifier (e.g., "5m_rsi_fast_oversold")
        timeframe: Timeframe for this feature (e.g., "5m")
        fuzzy_set_id: Fuzzy set this feature belongs to (e.g., "rsi_fast")
        membership_name: Membership function name (e.g., "oversold")
        indicator_id: Base indicator ID (e.g., "rsi_14")
        indicator_output: Output name for multi-output indicators (e.g., "upper"),
                         None for single-output indicators
    """

    feature_id: str
    timeframe: str
    fuzzy_set_id: str
    membership_name: str
    indicator_id: str
    indicator_output: str | None


class FeatureResolver:
    """Resolves nn_inputs into concrete feature specifications.

    This class is responsible for:
    - Expanding "all" timeframes to the full list from training_data
    - Parsing dot notation for multi-output indicators
    - Maintaining deterministic feature ordering
    - Providing helper methods to query features by timeframe

    The feature ordering is CRITICAL and must be preserved:
    1. nn_inputs list order (YAML order preserved)
    2. Within each nn_input: timeframes order × membership function order
    """

    def resolve(self, config: StrategyConfigurationV3) -> list[ResolvedFeature]:
        """Resolve nn_inputs to concrete features.

        The returned list order IS the canonical feature order.
        This order must be stored in ModelMetadataV3 and validated at backtest.

        Args:
            config: V3 strategy configuration

        Returns:
            Ordered list of resolved features
        """
        features: list[ResolvedFeature] = []

        # Get available timeframes from training data config
        available_timeframes = config.training_data.timeframes.timeframes

        # Process each nn_input in order
        for nn_input in config.nn_inputs:
            fuzzy_set_id = nn_input.fuzzy_set

            # Get fuzzy set definition
            fuzzy_set = config.fuzzy_sets[fuzzy_set_id]

            # Parse indicator reference (handle dot notation)
            indicator_id, indicator_output = self._parse_indicator_reference(
                fuzzy_set.indicator
            )

            # Get membership function names in order
            membership_names = fuzzy_set.get_membership_names()

            # Expand timeframes
            timeframes_to_use: list[str]
            if nn_input.timeframes == "all":
                timeframes_to_use = available_timeframes or []
            else:
                timeframes_to_use = nn_input.timeframes  # type: ignore[assignment]

            # Generate features in order: timeframes × memberships
            for timeframe in timeframes_to_use:
                for membership_name in membership_names:
                    feature_id = f"{timeframe}_{fuzzy_set_id}_{membership_name}"
                    features.append(
                        ResolvedFeature(
                            feature_id=feature_id,
                            timeframe=timeframe,
                            fuzzy_set_id=fuzzy_set_id,
                            membership_name=membership_name,
                            indicator_id=indicator_id,
                            indicator_output=indicator_output,
                        )
                    )

        return features

    def get_indicators_for_timeframe(
        self, resolved: list[ResolvedFeature], timeframe: str
    ) -> set[str]:
        """Get indicator_ids needed for a specific timeframe.

        Args:
            resolved: List of resolved features
            timeframe: Timeframe to query

        Returns:
            Set of indicator IDs needed for this timeframe
        """
        return {f.indicator_id for f in resolved if f.timeframe == timeframe}

    def get_fuzzy_sets_for_timeframe(
        self, resolved: list[ResolvedFeature], timeframe: str
    ) -> set[str]:
        """Get fuzzy_set_ids needed for a specific timeframe.

        Args:
            resolved: List of resolved features
            timeframe: Timeframe to query

        Returns:
            Set of fuzzy set IDs needed for this timeframe
        """
        return {f.fuzzy_set_id for f in resolved if f.timeframe == timeframe}

    def _parse_indicator_reference(self, indicator_ref: str) -> tuple[str, str | None]:
        """Parse indicator reference to extract indicator_id and output name.

        Handles dot notation for multi-output indicators.

        Args:
            indicator_ref: Indicator reference (e.g., "rsi_14" or "bbands_20_2.upper")

        Returns:
            Tuple of (indicator_id, indicator_output)
            - For single-output: ("rsi_14", None)
            - For multi-output: ("bbands_20_2", "upper")
        """
        if "." in indicator_ref:
            parts = indicator_ref.split(".", 1)
            return parts[0], parts[1]
        return indicator_ref, None
