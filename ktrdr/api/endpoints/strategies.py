"""
Strategies endpoints for the KTRDR API.

This module implements the API endpoints for listing and managing trading strategies.
"""

from fastapi import APIRouter, HTTPException
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import yaml

from ktrdr import get_logger
from ktrdr.config.loader import ConfigLoader
from ktrdr.training.model_storage import ModelStorage
from ktrdr.backtesting.model_loader import ModelLoader
from ktrdr.indicators.indicator_factory import BUILT_IN_INDICATORS

logger = get_logger(__name__)

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
    indicators: List[Dict[str, Any]]
    fuzzy_config: Dict[str, Any]
    training_status: str  # 'untrained', 'training', 'trained', 'failed'
    available_versions: List[int]
    latest_version: Optional[int] = None
    latest_training_date: Optional[str] = None
    latest_metrics: Optional[StrategyMetrics] = None


class StrategiesResponse(BaseModel):
    """Response model for strategies list."""

    success: bool = True
    strategies: List[StrategyInfo]


class ValidationIssue(BaseModel):
    """A validation issue found in a strategy."""
    
    severity: str  # 'error', 'warning'
    category: str  # 'indicators', 'fuzzy_sets', 'structure', 'configuration'
    message: str
    details: Optional[Dict[str, Any]] = None


class StrategyValidationResponse(BaseModel):
    """Response model for strategy validation."""
    
    success: bool
    valid: bool
    strategy_name: str
    issues: List[ValidationIssue]
    available_indicators: List[str]
    message: str


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
            with open(yaml_file, "r") as f:
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

                                with open(metrics_file, "r") as f:
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


def _validate_strategy_config(config: Dict[str, Any], strategy_name: str) -> List[ValidationIssue]:
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
        "bollinger_bands": "BollingerBands",
        "keltner_channels": "KeltnerChannels", 
        "momentum": "Momentum",
        "volume_sma": "SMA",
        "atr": "ATR",
        "rsi": "RSI",
        "sma": "SMA",
        "ema": "EMA",
        "macd": "MACD"
    }
    
    # 1. Check basic structure
    required_sections = ["indicators", "fuzzy_sets"]
    for section in required_sections:
        if section not in config:
            issues.append(ValidationIssue(
                severity="error",
                category="structure",
                message=f"Missing required section: '{section}'",
                details={"section": section}
            ))
    
    # 2. Validate indicators
    if "indicators" in config:
        indicator_configs = config["indicators"]
        if not isinstance(indicator_configs, list):
            issues.append(ValidationIssue(
                severity="error",
                category="indicators",
                message="'indicators' section must be a list",
                details={"type": str(type(indicator_configs))}
            ))
        else:
            strategy_indicators = []
            missing_indicators = []
            
            for idx, indicator_config in enumerate(indicator_configs):
                if not isinstance(indicator_config, dict):
                    issues.append(ValidationIssue(
                        severity="error",
                        category="indicators", 
                        message=f"Indicator at index {idx} must be a dictionary",
                        details={"index": idx, "type": str(type(indicator_config))}
                    ))
                    continue
                
                if "name" not in indicator_config:
                    issues.append(ValidationIssue(
                        severity="error",
                        category="indicators",
                        message=f"Indicator at index {idx} missing 'name' field",
                        details={"index": idx}
                    ))
                    continue
                
                indicator_name = indicator_config["name"]
                strategy_indicators.append(indicator_name)
                
                # Check if indicator exists in registry
                mapped_name = name_mapping.get(indicator_name.lower(), 
                                               "".join(word.capitalize() for word in indicator_name.split("_")))
                
                if mapped_name not in BUILT_IN_INDICATORS:
                    missing_indicators.append(indicator_name)
            
            # Report missing indicators
            if missing_indicators:
                available_indicators = sorted(set(BUILT_IN_INDICATORS.keys()))
                issues.append(ValidationIssue(
                    severity="error",
                    category="indicators",
                    message=f"Missing indicators: {', '.join(missing_indicators)} referenced by the strategy. Available indicators are: {', '.join(available_indicators)}",
                    details={
                        "missing_indicators": missing_indicators,
                        "available_indicators": available_indicators,
                        "strategy_indicators": strategy_indicators
                    }
                ))
    
    # 3. Validate fuzzy sets
    if "fuzzy_sets" in config and "indicators" in config:
        fuzzy_configs = config["fuzzy_sets"] 
        indicator_configs = config["indicators"]
        
        if not isinstance(fuzzy_configs, dict):
            issues.append(ValidationIssue(
                severity="error",
                category="fuzzy_sets",
                message="'fuzzy_sets' section must be a dictionary",
                details={"type": str(type(fuzzy_configs))}
            ))
        else:
            # Get list of indicator names and expected derived metrics
            indicator_names = []
            if isinstance(indicator_configs, list):
                for indicator_config in indicator_configs:
                    if isinstance(indicator_config, dict) and "name" in indicator_config:
                        indicator_names.append(indicator_config["name"])
            
            # Expected derived metrics from complex indicators
            expected_derived = set()
            for name in indicator_names:
                if name == "bollinger_bands":
                    expected_derived.add("bb_width")
                elif name == "volume_sma":
                    expected_derived.add("volume_ratio")
                elif name in ["bollinger_bands", "keltner_channels"]:
                    # Both needed for squeeze_intensity
                    if "bollinger_bands" in indicator_names and "keltner_channels" in indicator_names:
                        expected_derived.add("squeeze_intensity")
            
            # All possible fuzzy targets: direct indicators + derived metrics
            all_possible_targets = set(indicator_names) | expected_derived
            
            # Check if fuzzy sets reference valid indicators/metrics
            invalid_fuzzy_refs = []
            for fuzzy_name in fuzzy_configs.keys():
                if fuzzy_name not in all_possible_targets:
                    invalid_fuzzy_refs.append(fuzzy_name)
            
            if invalid_fuzzy_refs:
                issues.append(ValidationIssue(
                    severity="error",
                    category="fuzzy_sets",
                    message=f"Fuzzy sets reference invalid indicators/metrics: {', '.join(invalid_fuzzy_refs)}. Valid targets are: {', '.join(sorted(all_possible_targets))}",
                    details={
                        "invalid_references": invalid_fuzzy_refs,
                        "valid_targets": sorted(all_possible_targets),
                        "strategy_indicators": indicator_names,
                        "derived_metrics": sorted(expected_derived)
                    }
                ))
            
            # Validate fuzzy set structure
            for fuzzy_name, fuzzy_config in fuzzy_configs.items():
                if not isinstance(fuzzy_config, dict):
                    issues.append(ValidationIssue(
                        severity="error",
                        category="fuzzy_sets",
                        message=f"Fuzzy set '{fuzzy_name}' must be a dictionary",
                        details={"fuzzy_set": fuzzy_name, "type": str(type(fuzzy_config))}
                    ))
                    continue
                
                # Check fuzzy set structure - should have membership functions
                if not fuzzy_config:
                    issues.append(ValidationIssue(
                        severity="warning",
                        category="fuzzy_sets",
                        message=f"Fuzzy set '{fuzzy_name}' is empty",
                        details={"fuzzy_set": fuzzy_name}
                    ))
                    continue
                
                # Validate each membership function
                for member_name, member_config in fuzzy_config.items():
                    if not isinstance(member_config, dict):
                        issues.append(ValidationIssue(
                            severity="error", 
                            category="fuzzy_sets",
                            message=f"Membership function '{member_name}' in fuzzy set '{fuzzy_name}' must be a dictionary",
                            details={"fuzzy_set": fuzzy_name, "membership_function": member_name}
                        ))
                        continue
                    
                    # Check required fields for membership functions
                    if "type" not in member_config:
                        issues.append(ValidationIssue(
                            severity="error",
                            category="fuzzy_sets", 
                            message=f"Membership function '{member_name}' in fuzzy set '{fuzzy_name}' missing 'type' field",
                            details={"fuzzy_set": fuzzy_name, "membership_function": member_name}
                        ))
                    
                    if "parameters" not in member_config:
                        issues.append(ValidationIssue(
                            severity="error",
                            category="fuzzy_sets",
                            message=f"Membership function '{member_name}' in fuzzy set '{fuzzy_name}' missing 'parameters' field", 
                            details={"fuzzy_set": fuzzy_name, "membership_function": member_name}
                        ))
    
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
        # Load strategy file
        strategy_file = Path(f"strategies/{strategy_name}.yaml")
        if not strategy_file.exists():
            raise HTTPException(
                status_code=404, 
                detail=f"Strategy file not found: {strategy_name}.yaml"
            )
        
        with open(strategy_file, "r") as f:
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
                message = f"Strategy '{strategy_name}' is valid with {len(issues)} warning(s)"
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
            message=message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating strategy {strategy_name}: {e}")
        return StrategyValidationResponse(
            success=False,
            valid=False,
            strategy_name=strategy_name,
            issues=[ValidationIssue(
                severity="error",
                category="system",
                message=f"Failed to validate strategy: {str(e)}",
                details={"error": str(e)}
            )],
            available_indicators=sorted(set(BUILT_IN_INDICATORS.keys())),
            message=f"Validation failed due to system error"
        )
