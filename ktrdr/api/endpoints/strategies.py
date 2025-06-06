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
            with open(yaml_file, 'r') as f:
                config = yaml.safe_load(f)
            
            strategy_name = config.get("name", yaml_file.stem)
            
            # Extract symbol and timeframe from strategy config
            data_config = config.get('data', {})
            symbols = data_config.get('symbols', [])
            timeframes = data_config.get('timeframes', [])
            
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
                    m for m in all_models 
                    if m.get("symbol") == symbol and m.get("timeframe") == timeframe
                ]
                
                if relevant_models:
                    # Extract version numbers from model paths
                    versions = []
                    for model in relevant_models:
                        try:
                            model_path = Path(model["path"])
                            version_str = model_path.name.split('_v')[-1]
                            version = int(version_str)
                            versions.append(version)
                        except (ValueError, IndexError):
                            continue
                    
                    if versions:
                        available_versions = sorted(versions)
                        latest_version = max(versions)
                        
                        # Get metrics from the latest model
                        latest_model = max(relevant_models, key=lambda x: x.get("created_at", ""))
                        latest_training_date = latest_model.get("created_at")
                        
                        # Try to load detailed metrics
                        try:
                            model_path = Path(latest_model["path"])
                            metrics_file = model_path / "metrics.json"
                            if metrics_file.exists():
                                import json
                                with open(metrics_file, 'r') as f:
                                    metrics_data = json.load(f)
                                    
                                # Extract test metrics
                                test_metrics = metrics_data.get("test_metrics", {})
                                if test_metrics:
                                    latest_metrics = StrategyMetrics(
                                        accuracy=test_metrics.get("accuracy"),
                                        precision=test_metrics.get("precision"),
                                        recall=test_metrics.get("recall"),
                                        f1_score=test_metrics.get("f1_score")
                                    )
                        except Exception as e:
                            logger.warning(f"Could not load detailed metrics for {strategy_name}: {e}")
            
            # Build strategy info
            strategies.append(StrategyInfo(
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
                latest_metrics=latest_metrics
            ))
            
        except Exception as e:
            # Log error but continue with other strategies
            logger.error(f"Error loading strategy {yaml_file}: {e}")
            continue
    
    return StrategiesResponse(strategies=strategies)


@router.get("/{strategy_name}", response_model=StrategyInfo)
async def get_strategy_details(strategy_name: str, version: Optional[int] = None) -> StrategyInfo:
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
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_name}' not found")
    
    # If specific version requested, validate it exists
    if version is not None and version not in strategy.available_versions:
        raise HTTPException(
            status_code=404, 
            detail=f"Version {version} not found for strategy '{strategy_name}'"
        )
    
    return strategy