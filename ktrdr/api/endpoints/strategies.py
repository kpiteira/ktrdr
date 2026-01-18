"""
Strategies endpoints for the KTRDR API.

This module implements the API endpoints for listing and managing trading strategies.

HTTP Status Code Mapping
------------------------
The endpoints in this module follow these status code conventions:

200 OK:
    - Successful retrieval of strategy list
    - Successful retrieval of strategy details
    - Successful retrieval of available indicators

400 Bad Request (ConfigurationError):
    - Strategy file has invalid format or structure
    - Strategy validation fails (missing fields, invalid values)
    - Fuzzy sets reference invalid indicators
    - Feature IDs are missing, duplicate, or invalid format
    Fix: Edit the strategy YAML file to correct the configuration

422 Unprocessable Entity (ValidationError):
    - Request parameters are invalid (e.g., invalid strategy name format)
    - Query parameters don't match expected schema
    Fix: Correct the API request parameters

404 Not Found:
    - Strategy file doesn't exist at specified path
    - Requested strategy name doesn't match any known strategy
    Fix: Check strategy name or create the strategy file

500 Internal Server Error:
    - Unexpected errors during file system operations
    - Python exceptions not caught by specific handlers
    Fix: Check server logs for stack trace

Error Response Format
--------------------
All errors return JSON with this structure:
    {
        "message": "Human-readable error description",
        "error_code": "CATEGORY-ErrorName",
        "context": {"file": "path/to/file.yaml", ...},
        "details": {...},
        "suggestion": "How to fix this error"
    }
"""

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ktrdr import get_logger
from ktrdr.errors import ConfigurationError
from ktrdr.indicators.indicator_factory import BUILT_IN_INDICATORS
from ktrdr.training.model_storage import ModelStorage

logger = get_logger(__name__)

# Base directory for strategy files (resolved to absolute path)
STRATEGIES_DIR = os.path.abspath("strategies")


def _safe_strategy_path(strategy_name: str) -> str:
    """Safely resolve a strategy file path, preventing path traversal attacks.

    Uses os.path.abspath() normalization combined with startswith() prefix check,
    which is the sanitization pattern recognized by CodeQL for path injection.

    Args:
        strategy_name: The strategy name (without .yaml extension)

    Returns:
        Absolute path string to the strategy file

    Raises:
        HTTPException: If the path would escape the strategies directory
    """
    if not strategy_name:
        raise HTTPException(
            status_code=400,
            detail="Strategy name cannot be empty",
        )

    # Normalize the path using os.path.abspath (CodeQL-recognized sanitizer)
    strategy_file = os.path.abspath(
        os.path.join(STRATEGIES_DIR, f"{strategy_name}.yaml")
    )

    # Verify path stays within STRATEGIES_DIR (CodeQL-recognized guard)
    if not strategy_file.startswith(STRATEGIES_DIR + os.sep):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy name: '{strategy_name}'",
        )

    return strategy_file


# Create router for strategies endpoints
router = APIRouter(prefix="/strategies")


# Response models
class StrategyMetrics(BaseModel):
    """Training metrics for a strategy."""

    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None


class StrategyInfo(BaseModel):
    """Information about a trading strategy."""

    name: str
    description: str
    symbol: str
    timeframe: str
    indicators: list[dict[str, Any]]
    fuzzy_config: dict[str, Any]
    training_status: str  # 'untrained', 'training', 'trained', 'failed'
    available_versions: list[int]
    latest_version: Optional[int] = None
    latest_training_date: Optional[str] = None
    latest_metrics: Optional[StrategyMetrics] = None


class StrategiesResponse(BaseModel):
    """Response model for strategies list."""

    success: bool = True
    strategies: list[StrategyInfo]


class ValidationIssue(BaseModel):
    """A validation issue found in a strategy."""

    severity: str  # 'error', 'warning'
    category: str  # 'indicators', 'fuzzy_sets', 'structure', 'configuration'
    message: str
    details: Optional[dict[str, Any]] = None


class StrategyValidationResponse(BaseModel):
    """Response model for strategy validation."""

    success: bool
    valid: bool
    strategy_name: str
    issues: list[ValidationIssue]
    available_indicators: list[str]
    message: str


class FeatureInfo(BaseModel):
    """Information about a resolved NN input feature."""

    feature_id: str
    timeframe: str
    fuzzy_set: str
    membership: str
    indicator_id: str
    indicator_output: Optional[str] = None


class StrategyFeaturesResponse(BaseModel):
    """Response model for strategy features."""

    success: bool = True
    strategy_name: str
    features: list[FeatureInfo]
    count: int


@router.get("/", response_model=StrategiesResponse)
async def list_strategies() -> StrategiesResponse:
    """
    List all available strategies with their training status.

    This endpoint scans the strategies directory for YAML configurations
    and uses the existing ModelStorage system to check training status.
    """
    strategies = []
    strategy_dir = Path("strategies")

    if not strategy_dir.exists():
        return StrategiesResponse(strategies=[])

    # Initialize existing systems
    model_storage = ModelStorage()

    for yaml_file in strategy_dir.glob("*.yaml"):
        try:
            # Load strategy configuration using existing loader
            with open(yaml_file) as f:
                config = yaml.safe_load(f)

            strategy_name = config.get("name", yaml_file.stem)

            # Extract symbol and timeframe from strategy config
            data_config = config.get("data", {})
            symbols = data_config.get("symbols", [])
            timeframes = data_config.get("timeframes", [])

            # For MVP, use first symbol and timeframe
            symbol = symbols[0] if symbols else ""
            timeframe = timeframes[0] if timeframes else ""

            # Use existing model storage to check training status
            training_status = "untrained"
            available_versions = []
            latest_version = None
            latest_training_date = None
            latest_metrics = None

            # Get all models for this strategy using existing system
            all_models = model_storage.list_models(strategy_name)

            if all_models:
                training_status = "trained"

                # Filter models for the first symbol/timeframe combo
                relevant_models = [
                    m
                    for m in all_models
                    if m.get("symbol") == symbol and m.get("timeframe") == timeframe
                ]

                if relevant_models:
                    # Extract version numbers from model paths
                    versions = []
                    for model in relevant_models:
                        try:
                            model_path = Path(model["path"])
                            version_str = model_path.name.split("_v")[-1]
                            version = int(version_str)
                            versions.append(version)
                        except (ValueError, IndexError):
                            continue

                    if versions:
                        available_versions = sorted(versions)
                        latest_version = max(versions)

                        # Get metrics from the latest model
                        latest_model = max(
                            relevant_models, key=lambda x: x.get("created_at", "")
                        )
                        latest_training_date = latest_model.get("created_at")

                        # Try to load detailed metrics
                        try:
                            model_path = Path(latest_model["path"])
                            metrics_file = model_path / "metrics.json"
                            if metrics_file.exists():
                                import json

                                with open(metrics_file) as f:
                                    metrics_data = json.load(f)

                                # Extract test metrics
                                test_metrics = metrics_data.get("test_metrics", {})
                                if test_metrics:
                                    latest_metrics = StrategyMetrics(
                                        accuracy=test_metrics.get("accuracy"),
                                        precision=test_metrics.get("precision"),
                                        recall=test_metrics.get("recall"),
                                        f1_score=test_metrics.get("f1_score"),
                                    )
                        except Exception as e:
                            logger.warning(
                                f"Could not load detailed metrics for {strategy_name}: {e}"
                            )

            # Build strategy info
            strategies.append(
                StrategyInfo(
                    name=strategy_name,
                    description=config.get("description", ""),
                    symbol=symbol,
                    timeframe=timeframe,
                    indicators=config.get("indicators", []),
                    fuzzy_config=config.get("fuzzy_sets", {}),
                    training_status=training_status,
                    available_versions=available_versions,
                    latest_version=latest_version,
                    latest_training_date=latest_training_date,
                    latest_metrics=latest_metrics,
                )
            )

        except Exception as e:
            # Log error but continue with other strategies
            logger.error(f"Error loading strategy {yaml_file}: {e}")
            continue

    return StrategiesResponse(strategies=strategies)


@router.get("/{strategy_name}", response_model=StrategyInfo)
async def get_strategy_details(
    strategy_name: str, version: Optional[int] = None
) -> StrategyInfo:
    """
    Get detailed information about a specific strategy.

    Args:
        strategy_name: Name of the strategy
        version: Specific model version (latest if not specified)
    """
    # First, get all strategies
    all_strategies = await list_strategies()

    # Find the requested strategy
    strategy = None
    for s in all_strategies.strategies:
        if s.name == strategy_name:
            strategy = s
            break

    if not strategy:
        raise HTTPException(
            status_code=404, detail=f"Strategy '{strategy_name}' not found"
        )

    # If specific version requested, validate it exists
    if version is not None and version not in strategy.available_versions:
        raise HTTPException(
            status_code=404,
            detail=f"Version {version} not found for strategy '{strategy_name}'",
        )

    return strategy


def _validate_strategy_config(
    config: dict[str, Any], strategy_name: str
) -> list[ValidationIssue]:
    """
    Validate a strategy configuration and return list of issues.

    Args:
        config: Strategy configuration dictionary
        strategy_name: Name of the strategy being validated

    Returns:
        List of validation issues found
    """
    issues = []

    # Get name mapping for strategy indicators
    name_mapping = {
        # Common aliases to official names (both snake_case and camelCase variants)
        "bollinger_bands": "BollingerBands",
        "bbands": "BollingerBands",
        "keltner_channels": "KeltnerChannels",
        "keltnerchannels": "KeltnerChannels",
        "momentum": "Momentum",
        "volume_sma": "SMA",
        "atr": "ATR",
        "rsi": "RSI",
        "sma": "SMA",
        "ema": "EMA",
        "macd": "MACD",
        "stoch": "Stochastic",
        "stochastic": "Stochastic",
        "adx": "ADX",
        "zigzag": "ZigZag",
        "williams_r": "WilliamsR",
        "williamsr": "WilliamsR",  # camelCase variant
        "obv": "OBV",
        "cci": "CCI",
        "roc": "ROC",
        "vwap": "VWAP",
        "parabolic_sar": "ParabolicSAR",
        "parabolicsar": "ParabolicSAR",  # camelCase variant
        "psar": "ParabolicSAR",
        "ichimoku": "Ichimoku",
        "rvi": "RVI",
        "mfi": "MFI",
        "aroon": "Aroon",
        "donchian_channels": "DonchianChannels",
        "donchianchannels": "DonchianChannels",  # camelCase variant
        "donchian": "DonchianChannels",
        "ad_line": "ADLine",
        "accumulation_distribution": "AccumulationDistribution",
        "cmf": "CMF",
        "chaikin_money_flow": "ChaikinMoneyFlow",
        "supertrend": "SuperTrend",
        "fisher_transform": "FisherTransform",
        "fishertransform": "FisherTransform",  # camelCase variant
        "bollinger_band_width": "BollingerBandWidth",
        "bollingerbandwidth": "BollingerBandWidth",  # camelCase variant
        "bb_width": "BollingerBandWidth",
        "volume_ratio": "VolumeRatio",
        "volumeratio": "VolumeRatio",  # camelCase variant
        "squeeze_intensity": "SqueezeIntensity",
        "distance_from_ma": "DistanceFromMA",
        "distancefromma": "DistanceFromMA",  # camelCase variant
    }

    # 1. Check basic structure
    required_sections = ["indicators", "fuzzy_sets"]
    for section in required_sections:
        if section not in config:
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="structure",
                    message=f"Missing required section: '{section}'",
                    details={"section": section},
                )
            )

    # 2. Validate indicators
    if "indicators" in config:
        indicator_configs = config["indicators"]
        if not isinstance(indicator_configs, list):
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="indicators",
                    message="'indicators' section must be a list",
                    details={"type": str(type(indicator_configs))},
                )
            )
        else:
            strategy_indicators = []
            missing_indicators = []

            for idx, indicator_config in enumerate(indicator_configs):
                if not isinstance(indicator_config, dict):
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            category="indicators",
                            message=f"Indicator at index {idx} must be a dictionary",
                            details={"index": idx, "type": str(type(indicator_config))},
                        )
                    )
                    continue

                if "name" not in indicator_config:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            category="indicators",
                            message=f"Indicator at index {idx} missing 'name' field",
                            details={"index": idx},
                        )
                    )
                    continue

                indicator_name = indicator_config["name"]
                strategy_indicators.append(indicator_name)

                # Check if indicator exists in registry
                mapped_name = name_mapping.get(indicator_name.lower())

                if mapped_name is None:
                    # Try the original name as-is (for PascalCase names like "BollingerBands")
                    if indicator_name in BUILT_IN_INDICATORS:
                        mapped_name = indicator_name
                    else:
                        # Fallback: convert snake_case to PascalCase
                        mapped_name = "".join(
                            word.capitalize() for word in indicator_name.split("_")
                        )

                if mapped_name not in BUILT_IN_INDICATORS:
                    missing_indicators.append(indicator_name)

            # Report missing indicators
            if missing_indicators:
                available_indicators = sorted(set(BUILT_IN_INDICATORS.keys()))
                issues.append(
                    ValidationIssue(
                        severity="error",
                        category="indicators",
                        message=f"Missing indicators: {', '.join(missing_indicators)} referenced by the strategy. Available indicators are: {', '.join(available_indicators)}",
                        details={
                            "missing_indicators": missing_indicators,
                            "available_indicators": available_indicators,
                            "strategy_indicators": strategy_indicators,
                        },
                    )
                )

    # 3. Validate fuzzy sets
    if "fuzzy_sets" in config and "indicators" in config:
        fuzzy_configs = config["fuzzy_sets"]
        indicator_configs = config["indicators"]

        if not isinstance(fuzzy_configs, dict):
            issues.append(
                ValidationIssue(
                    severity="error",
                    category="fuzzy_sets",
                    message="'fuzzy_sets' section must be a dictionary",
                    details={"type": str(type(fuzzy_configs))},
                )
            )
        else:
            # Get list of indicator names, feature_ids, and expected derived metrics
            # feature_id is the source of truth for fuzzy set keys
            indicator_names = []
            indicator_feature_ids = []
            if isinstance(indicator_configs, list):
                for indicator_config in indicator_configs:
                    if isinstance(indicator_config, dict):
                        if "name" in indicator_config:
                            indicator_names.append(indicator_config["name"])
                        if "feature_id" in indicator_config:
                            indicator_feature_ids.append(indicator_config["feature_id"])

            # Expected derived metrics from complex indicators
            # Multi-output indicators produce additional columns beyond the primary feature_id
            expected_derived = set()
            for name in indicator_names:
                if name == "bollinger_bands":
                    expected_derived.add("bb_width")
                elif name == "volume_sma":
                    expected_derived.add("volume_ratio")
                elif name in ["bollinger_bands", "keltner_channels"]:
                    # Both needed for squeeze_intensity
                    if (
                        "bollinger_bands" in indicator_names
                        and "keltner_channels" in indicator_names
                    ):
                        expected_derived.add("squeeze_intensity")
                # ADX produces DI_Plus and DI_Minus as secondary outputs
                elif name == "adx":
                    expected_derived.add("ADX")
                    expected_derived.add("DI_Plus")
                    expected_derived.add("DI_Minus")
                # Aroon produces aroon_up and aroon_down
                elif name == "aroon":
                    expected_derived.add("aroon_up")
                    expected_derived.add("aroon_down")

            # Build set of all possible valid targets for fuzzy sets
            # Includes: feature_ids (primary), indicator names, derived metrics, and price data columns
            # feature_id is the source of truth - fuzzy set keys should match feature_ids directly
            all_possible_targets = (
                set(
                    indicator_feature_ids
                )  # Primary: feature_ids are the source of truth
                | set(
                    indicator_names
                )  # Fallback: indicator names for backward compatibility
                | expected_derived
                | {
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                }
            )

            # Check if fuzzy sets reference valid indicators/metrics
            # Note: Fuzzy set names may have suffixes like _14, _standard, _fast to distinguish
            # between multiple instances of the same indicator with different parameters.
            invalid_fuzzy_refs = []
            for fuzzy_name in fuzzy_configs.keys():
                # Check direct match first
                if fuzzy_name in all_possible_targets:
                    continue

                # Extract base indicator name (e.g., "rsi_14" -> "rsi", "macd_standard" -> "macd")
                base_name = fuzzy_name.split("_")[0]
                if base_name in all_possible_targets:
                    continue

                # Check if fuzzy_name starts with any valid target prefix
                # This handles multi-output indicators like ADX producing DI_Plus_14, DI_Minus_14
                matched = False
                for target in all_possible_targets:
                    if fuzzy_name.startswith(f"{target}_"):
                        matched = True
                        break

                if not matched:
                    invalid_fuzzy_refs.append(fuzzy_name)

            if invalid_fuzzy_refs:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        category="fuzzy_sets",
                        message=f"Fuzzy sets reference invalid indicators/metrics: {', '.join(invalid_fuzzy_refs)}. Valid targets are: {', '.join(sorted(all_possible_targets))}",
                        details={
                            "invalid_references": invalid_fuzzy_refs,
                            "valid_targets": sorted(all_possible_targets),
                            "indicator_feature_ids": indicator_feature_ids,
                            "strategy_indicators": indicator_names,
                            "derived_metrics": sorted(expected_derived),
                        },
                    )
                )

            # Validate fuzzy set structure
            for fuzzy_name, fuzzy_config in fuzzy_configs.items():
                if not isinstance(fuzzy_config, dict):
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            category="fuzzy_sets",
                            message=f"Fuzzy set '{fuzzy_name}' must be a dictionary",
                            details={
                                "fuzzy_set": fuzzy_name,
                                "type": str(type(fuzzy_config)),
                            },
                        )
                    )
                    continue

                # Check fuzzy set structure - should have membership functions
                if not fuzzy_config:
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            category="fuzzy_sets",
                            message=f"Fuzzy set '{fuzzy_name}' is empty",
                            details={"fuzzy_set": fuzzy_name},
                        )
                    )
                    continue

                # Validate each membership function (skip input_transform - it's not a membership function)
                for member_name, member_config in fuzzy_config.items():
                    # Skip input_transform - it's a special configuration field, not a membership function
                    if member_name == "input_transform":
                        continue

                    if not isinstance(member_config, dict):
                        issues.append(
                            ValidationIssue(
                                severity="error",
                                category="fuzzy_sets",
                                message=f"Membership function '{member_name}' in fuzzy set '{fuzzy_name}' must be a dictionary",
                                details={
                                    "fuzzy_set": fuzzy_name,
                                    "membership_function": member_name,
                                },
                            )
                        )
                        continue

                    # Check required fields for membership functions
                    if "type" not in member_config:
                        issues.append(
                            ValidationIssue(
                                severity="error",
                                category="fuzzy_sets",
                                message=f"Membership function '{member_name}' in fuzzy set '{fuzzy_name}' missing 'type' field",
                                details={
                                    "fuzzy_set": fuzzy_name,
                                    "membership_function": member_name,
                                },
                            )
                        )

                    if "parameters" not in member_config:
                        issues.append(
                            ValidationIssue(
                                severity="error",
                                category="fuzzy_sets",
                                message=f"Membership function '{member_name}' in fuzzy set '{fuzzy_name}' missing 'parameters' field",
                                details={
                                    "fuzzy_set": fuzzy_name,
                                    "membership_function": member_name,
                                },
                            )
                        )

    return issues


@router.post("/validate/{strategy_name}", response_model=StrategyValidationResponse)
async def validate_strategy(strategy_name: str) -> StrategyValidationResponse:
    """
    Validate a strategy configuration for completeness and correctness.

    This endpoint performs comprehensive validation of a strategy file:
    - Checks that all referenced indicators exist in the system
    - Validates fuzzy sets configuration
    - Verifies strategy file structure
    - Provides detailed error messages for issues found

    Args:
        strategy_name: Name of the strategy file (without .yaml extension)

    Returns:
        Validation response with issues found and available indicators
    """
    try:
        # Load strategy file (with path traversal protection)
        strategy_file = _safe_strategy_path(strategy_name)
        if not os.path.exists(strategy_file):
            raise HTTPException(
                status_code=404, detail=f"Strategy file not found: {strategy_name}.yaml"
            )

        with open(strategy_file) as f:
            config = yaml.safe_load(f)

        # Validate the configuration
        issues = _validate_strategy_config(config, strategy_name)

        # Get available indicators for reference
        available_indicators = sorted(set(BUILT_IN_INDICATORS.keys()))

        # Determine if validation passed
        has_errors = any(issue.severity == "error" for issue in issues)
        is_valid = not has_errors

        # Create response message
        if is_valid:
            if issues:  # Has warnings but no errors
                message = (
                    f"Strategy '{strategy_name}' is valid with {len(issues)} warning(s)"
                )
            else:
                message = f"Strategy '{strategy_name}' is valid"
        else:
            error_count = sum(1 for issue in issues if issue.severity == "error")
            warning_count = len(issues) - error_count
            message = f"Strategy '{strategy_name}' has {error_count} error(s)"
            if warning_count > 0:
                message += f" and {warning_count} warning(s)"

        return StrategyValidationResponse(
            success=True,
            valid=is_valid,
            strategy_name=strategy_name,
            issues=issues,
            available_indicators=available_indicators,
            message=message,
        )

    except HTTPException:
        raise
    except ConfigurationError as e:
        # Log error with full context before responding
        logger.error(f"Configuration error: {e.format_user_message()}")
        # Return structured error response with all details
        raise HTTPException(status_code=400, detail=e.to_dict()) from e
    except Exception as e:
        logger.error(f"Error validating strategy {strategy_name}: {e}")
        return StrategyValidationResponse(
            success=False,
            valid=False,
            strategy_name=strategy_name,
            issues=[
                ValidationIssue(
                    severity="error",
                    category="system",
                    message=f"Failed to validate strategy: {str(e)}",
                    details={"error": str(e)},
                )
            ],
            available_indicators=sorted(set(BUILT_IN_INDICATORS.keys())),
            message="Validation failed due to system error",
        )


@router.get("/{strategy_name}/features", response_model=StrategyFeaturesResponse)
async def get_strategy_features(strategy_name: str) -> StrategyFeaturesResponse:
    """
    Get resolved NN input features for a v3 strategy.

    This endpoint loads a v3 strategy and resolves the nn_inputs specification
    into concrete feature definitions. This is useful for understanding what
    features will be generated from a strategy's fuzzy sets and indicators.

    Args:
        strategy_name: Name of the strategy file (without .yaml extension)

    Returns:
        List of resolved features with their identifiers and metadata
    """
    from ktrdr.config.feature_resolver import FeatureResolver
    from ktrdr.config.strategy_loader import StrategyConfigurationLoader

    try:
        # Load strategy file (with path traversal protection)
        strategy_file = _safe_strategy_path(strategy_name)
        if not os.path.exists(strategy_file):
            raise HTTPException(
                status_code=404, detail=f"Strategy file not found: {strategy_name}.yaml"
            )

        # Load as v3 strategy
        loader = StrategyConfigurationLoader()
        try:
            config = loader.load_v3_strategy(strategy_file)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Strategy '{strategy_name}' is not v3 format or invalid: {e}",
            ) from e

        # Resolve features
        resolver = FeatureResolver()
        resolved_features = resolver.resolve(config)

        # Convert to response format
        features = [
            FeatureInfo(
                feature_id=f.feature_id,
                timeframe=f.timeframe,
                fuzzy_set=f.fuzzy_set_id,
                membership=f.membership_name,
                indicator_id=f.indicator_id,
                indicator_output=f.indicator_output,
            )
            for f in resolved_features
        ]

        return StrategyFeaturesResponse(
            success=True,
            strategy_name=strategy_name,
            features=features,
            count=len(features),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting features for strategy {strategy_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get strategy features: {str(e)}",
        ) from e
