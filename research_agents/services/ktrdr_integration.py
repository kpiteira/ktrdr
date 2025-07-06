"""
KTRDR API Integration Layer

This module provides a clean integration interface between the research agents
and the existing KTRDR training/backtesting APIs, with robust error handling
and comprehensive logging.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Union
from uuid import UUID, uuid4
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum

import aiohttp
import logging
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TrainingStatus(str, Enum):
    """KTRDR training status states"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BacktestStatus(str, Enum):
    """KTRDR backtesting status states"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TrainingConfig:
    """Configuration for neural network training"""
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    
    # Neural network configuration
    architecture: Dict[str, Any]
    training_params: Dict[str, Any]
    
    # Fuzzy logic configuration
    fuzzy_config: Dict[str, Any]
    
    # Data configuration
    indicators: List[str]
    lookback_period: int
    validation_split: float = 0.2


@dataclass
class BacktestConfig:
    """Configuration for strategy backtesting"""
    strategy_name: str
    model_path: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    
    # Trading configuration
    initial_capital: float = 100000.0
    commission: float = 0.001
    slippage: float = 0.0001
    
    # Risk management
    max_position_size: float = 1.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class TrainingResults:
    """Results from neural network training"""
    training_id: str
    status: TrainingStatus
    model_path: Optional[str]
    
    # Training metrics
    epochs_completed: int
    final_loss: float
    validation_loss: float
    training_time_minutes: float
    
    # Performance metrics
    accuracy: Optional[float]
    precision: Optional[float]
    recall: Optional[float]
    f1_score: Optional[float]
    
    # Additional data
    loss_history: List[float]
    validation_history: List[float]
    error_info: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]


@dataclass
class BacktestResults:
    """Results from strategy backtesting"""
    backtest_id: str
    status: BacktestStatus
    
    # Performance metrics
    total_trades: int
    profitable_trades: int
    losing_trades: int
    win_rate: float
    
    # Financial metrics
    total_return: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    avg_trade_return: float
    
    # Risk metrics
    volatility: float
    var_95: float  # Value at Risk 95%
    max_consecutive_losses: int
    
    # Trade analysis
    trade_details: List[Dict[str, Any]]
    equity_curve: List[Dict[str, Any]]
    drawdown_periods: List[Dict[str, Any]]
    
    # Execution info
    execution_time_minutes: float
    error_info: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]


class KTRDRIntegrationError(Exception):
    """Base exception for KTRDR integration"""
    pass


class TrainingError(KTRDRIntegrationError):
    """Exception raised during training operations"""
    pass


class BacktestError(KTRDRIntegrationError):
    """Exception raised during backtesting operations"""
    pass


class ConnectionError(KTRDRIntegrationError):
    """Exception raised for connection issues"""
    pass


class KTRDRIntegrationService:
    """
    Service for integrating with KTRDR training and backtesting APIs.
    
    Provides a clean, async interface for submitting training jobs and backtests,
    monitoring their progress, and retrieving results.
    """
    
    def __init__(
        self,
        ktrdr_api_base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout_seconds: int = 300,
        max_retries: int = 3
    ):
        self.api_base_url = ktrdr_api_base_url.rstrip('/')
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        
        # API endpoints
        self.training_endpoint = f"{self.api_base_url}/api/training"
        self.backtest_endpoint = f"{self.api_base_url}/api/backtest"
        self.health_endpoint = f"{self.api_base_url}/api/health"
        
        # Session management
        self._session: Optional[aiohttp.ClientSession] = None
        self._is_initialized = False
        
        logger.info("KTRDR integration service initialized",
                   api_base_url=ktrdr_api_base_url)
    
    async def initialize(self) -> None:
        """Initialize the integration service"""
        if self._is_initialized:
            return
        
        # Create HTTP session with appropriate configuration
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        headers = {"Content-Type": "application/json"}
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            headers=headers
        )
        
        # Verify KTRDR API connectivity
        await self._verify_api_connection()
        
        self._is_initialized = True
        logger.info("KTRDR integration service ready")
    
    async def close(self) -> None:
        """Close the integration service"""
        if self._session:
            await self._session.close()
            self._session = None
        
        self._is_initialized = False
        logger.info("KTRDR integration service closed")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check KTRDR API health"""
        if not self._is_initialized:
            raise KTRDRIntegrationError("Service not initialized")
        
        try:
            async with self._session.get(self.health_endpoint) as response:
                if response.status == 200:
                    health_data = await response.json()
                    return {
                        "status": "healthy",
                        "ktrdr_api": health_data,
                        "integration_service": "operational"
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "error": f"API returned status {response.status}",
                        "integration_service": "degraded"
                    }
        
        except Exception as e:
            logger.error(f"KTRDR health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "integration_service": "error"
            }
    
    async def submit_training(self, config: TrainingConfig) -> str:
        """Submit a neural network training job"""
        if not self._is_initialized:
            raise KTRDRIntegrationError("Service not initialized")
        
        training_payload = {
            "strategy_name": config.strategy_name,
            "symbol": config.symbol,
            "timeframe": config.timeframe,
            "start_date": config.start_date,
            "end_date": config.end_date,
            "architecture": config.architecture,
            "training_params": config.training_params,
            "fuzzy_config": config.fuzzy_config,
            "indicators": config.indicators,
            "lookback_period": config.lookback_period,
            "validation_split": config.validation_split
        }
        
        try:
            logger.info(f"Submitting training job: {config.strategy_name} {config.symbol} {config.timeframe}")
            
            async with self._session.post(
                f"{self.training_endpoint}/submit",
                json=training_payload
            ) as response:
                
                if response.status == 201:
                    result = await response.json()
                    training_id = result["training_id"]
                    
                    logger.info(f"Training job submitted successfully: {training_id} for {config.strategy_name}")
                    
                    return training_id
                
                elif response.status == 400:
                    error_data = await response.json()
                    raise TrainingError(f"Invalid training configuration: {error_data.get('detail', 'Unknown error')}")
                
                elif response.status == 422:
                    error_data = await response.json()
                    raise TrainingError(f"Validation error: {error_data.get('detail', 'Unknown error')}")
                
                else:
                    error_text = await response.text()
                    raise TrainingError(f"Training submission failed with status {response.status}: {error_text}")
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error during training submission: {e}")
            raise ConnectionError(f"Failed to connect to KTRDR API: {e}") from e
        
        except Exception as e:
            logger.error(f"Unexpected error during training submission: {e}")
            raise TrainingError(f"Training submission failed: {e}") from e
    
    async def get_training_status(self, training_id: str) -> TrainingResults:
        """Get status and results of a training job"""
        if not self._is_initialized:
            raise KTRDRIntegrationError("Service not initialized")
        
        try:
            async with self._session.get(
                f"{self.training_endpoint}/{training_id}/status"
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    return TrainingResults(
                        training_id=training_id,
                        status=TrainingStatus(data["status"]),
                        model_path=data.get("model_path"),
                        epochs_completed=data.get("epochs_completed", 0),
                        final_loss=data.get("final_loss", float('inf')),
                        validation_loss=data.get("validation_loss", float('inf')),
                        training_time_minutes=data.get("training_time_minutes", 0.0),
                        accuracy=data.get("accuracy"),
                        precision=data.get("precision"),
                        recall=data.get("recall"),
                        f1_score=data.get("f1_score"),
                        loss_history=data.get("loss_history", []),
                        validation_history=data.get("validation_history", []),
                        error_info=data.get("error_info"),
                        metadata=data.get("metadata", {})
                    )
                
                elif response.status == 404:
                    raise TrainingError(f"Training job {training_id} not found")
                
                else:
                    error_text = await response.text()
                    raise TrainingError(f"Failed to get training status: {error_text}")
        
        except aiohttp.ClientError as e:
            raise ConnectionError(f"Network error getting training status: {e}") from e
        except json.JSONDecodeError as e:
            raise TrainingError(f"Invalid JSON response from training status API: {e}") from e
    
    async def wait_for_training_completion(
        self,
        training_id: str,
        poll_interval_seconds: int = 30,
        max_wait_minutes: int = 240
    ) -> TrainingResults:
        """Wait for training to complete with polling"""
        if not self._is_initialized:
            raise KTRDRIntegrationError("Service not initialized")
        
        logger.info("Waiting for training completion",
                   training_id=training_id,
                   max_wait_minutes=max_wait_minutes)
        
        start_time = datetime.now(timezone.utc)
        max_wait_seconds = max_wait_minutes * 60
        
        while True:
            # Check if we've exceeded maximum wait time
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed > max_wait_seconds:
                raise TrainingError(f"Training {training_id} exceeded maximum wait time of {max_wait_minutes} minutes")
            
            # Get current status
            results = await self.get_training_status(training_id)
            
            if results.status == TrainingStatus.COMPLETED:
                logger.info("Training completed successfully",
                           training_id=training_id,
                           final_loss=results.final_loss,
                           training_time_minutes=results.training_time_minutes)
                return results
            
            elif results.status == TrainingStatus.FAILED:
                error_msg = results.error_info.get("message", "Unknown error") if results.error_info else "Training failed"
                raise TrainingError(f"Training {training_id} failed: {error_msg}")
            
            elif results.status == TrainingStatus.CANCELLED:
                raise TrainingError(f"Training {training_id} was cancelled")
            
            # Training still running, wait before next poll
            await asyncio.sleep(poll_interval_seconds)
    
    async def submit_backtest(self, config: BacktestConfig) -> str:
        """Submit a strategy backtesting job"""
        if not self._is_initialized:
            raise KTRDRIntegrationError("Service not initialized")
        
        backtest_payload = {
            "strategy_name": config.strategy_name,
            "model_path": config.model_path,
            "symbol": config.symbol,
            "timeframe": config.timeframe,
            "start_date": config.start_date,
            "end_date": config.end_date,
            "initial_capital": config.initial_capital,
            "commission": config.commission,
            "slippage": config.slippage,
            "max_position_size": config.max_position_size,
            "stop_loss": config.stop_loss,
            "take_profit": config.take_profit
        }
        
        try:
            logger.info("Submitting backtest job",
                       strategy_name=config.strategy_name,
                       model_path=config.model_path,
                       symbol=config.symbol)
            
            async with self._session.post(
                f"{self.backtest_endpoint}/submit",
                json=backtest_payload
            ) as response:
                
                if response.status == 201:
                    result = await response.json()
                    backtest_id = result["backtest_id"]
                    
                    logger.info("Backtest job submitted successfully",
                               backtest_id=backtest_id,
                               strategy_name=config.strategy_name)
                    
                    return backtest_id
                
                elif response.status == 400:
                    error_data = await response.json()
                    raise BacktestError(f"Invalid backtest configuration: {error_data.get('detail', 'Unknown error')}")
                
                else:
                    error_text = await response.text()
                    raise BacktestError(f"Backtest submission failed with status {response.status}: {error_text}")
        
        except aiohttp.ClientError as e:
            raise ConnectionError(f"Network error during backtest submission: {e}") from e
    
    async def get_backtest_results(self, backtest_id: str) -> BacktestResults:
        """Get results of a backtesting job"""
        if not self._is_initialized:
            raise KTRDRIntegrationError("Service not initialized")
        
        try:
            async with self._session.get(
                f"{self.backtest_endpoint}/{backtest_id}/results"
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    return BacktestResults(
                        backtest_id=backtest_id,
                        status=BacktestStatus(data["status"]),
                        total_trades=data.get("total_trades", 0),
                        profitable_trades=data.get("profitable_trades", 0),
                        losing_trades=data.get("losing_trades", 0),
                        win_rate=data.get("win_rate", 0.0),
                        total_return=data.get("total_return", 0.0),
                        profit_factor=data.get("profit_factor", 0.0),
                        sharpe_ratio=data.get("sharpe_ratio", 0.0),
                        sortino_ratio=data.get("sortino_ratio", 0.0),
                        max_drawdown=data.get("max_drawdown", 0.0),
                        avg_trade_return=data.get("avg_trade_return", 0.0),
                        volatility=data.get("volatility", 0.0),
                        var_95=data.get("var_95", 0.0),
                        max_consecutive_losses=data.get("max_consecutive_losses", 0),
                        trade_details=data.get("trade_details", []),
                        equity_curve=data.get("equity_curve", []),
                        drawdown_periods=data.get("drawdown_periods", []),
                        execution_time_minutes=data.get("execution_time_minutes", 0.0),
                        error_info=data.get("error_info"),
                        metadata=data.get("metadata", {})
                    )
                
                elif response.status == 404:
                    raise BacktestError(f"Backtest job {backtest_id} not found")
                
                else:
                    error_text = await response.text()
                    raise BacktestError(f"Failed to get backtest results: {error_text}")
        
        except aiohttp.ClientError as e:
            raise ConnectionError(f"Network error getting backtest results: {e}") from e
    
    async def wait_for_backtest_completion(
        self,
        backtest_id: str,
        poll_interval_seconds: int = 10,
        max_wait_minutes: int = 60
    ) -> BacktestResults:
        """Wait for backtest to complete with polling"""
        if not self._is_initialized:
            raise KTRDRIntegrationError("Service not initialized")
        
        logger.info("Waiting for backtest completion",
                   backtest_id=backtest_id,
                   max_wait_minutes=max_wait_minutes)
        
        start_time = datetime.now(timezone.utc)
        max_wait_seconds = max_wait_minutes * 60
        
        while True:
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed > max_wait_seconds:
                raise BacktestError(f"Backtest {backtest_id} exceeded maximum wait time of {max_wait_minutes} minutes")
            
            results = await self.get_backtest_results(backtest_id)
            
            if results.status == BacktestStatus.COMPLETED:
                logger.info("Backtest completed successfully",
                           backtest_id=backtest_id,
                           total_trades=results.total_trades,
                           profit_factor=results.profit_factor)
                return results
            
            elif results.status == BacktestStatus.FAILED:
                error_msg = results.error_info.get("message", "Unknown error") if results.error_info else "Backtest failed"
                raise BacktestError(f"Backtest {backtest_id} failed: {error_msg}")
            
            await asyncio.sleep(poll_interval_seconds)
    
    async def cancel_training(self, training_id: str) -> None:
        """Cancel a running training job"""
        if not self._is_initialized:
            raise KTRDRIntegrationError("Service not initialized")
        
        try:
            async with self._session.post(
                f"{self.training_endpoint}/{training_id}/cancel"
            ) as response:
                
                if response.status == 200:
                    logger.info(f"Training cancelled successfully: {training_id}")
                elif response.status == 404:
                    raise TrainingError(f"Training job {training_id} not found")
                else:
                    error_text = await response.text()
                    raise TrainingError(f"Failed to cancel training: {error_text}")
        
        except aiohttp.ClientError as e:
            raise ConnectionError(f"Network error cancelling training: {e}") from e
    
    # Private methods
    
    async def _verify_api_connection(self) -> None:
        """Verify connection to KTRDR API"""
        try:
            async with self._session.get(self.health_endpoint) as response:
                if response.status != 200:
                    raise ConnectionError(f"KTRDR API health check failed with status {response.status}")
                
                health_data = await response.json()
                logger.info(f"KTRDR API connection verified: {health_data}")
        
        except aiohttp.ClientError as e:
            raise ConnectionError(f"Failed to connect to KTRDR API at {self.api_base_url}: {e}") from e


# Factory function for creating KTRDR integration service
async def create_ktrdr_integration_service(
    ktrdr_api_base_url: str = "http://localhost:8000",
    api_key: Optional[str] = None
) -> KTRDRIntegrationService:
    """Create and initialize a KTRDR integration service instance"""
    service = KTRDRIntegrationService(
        ktrdr_api_base_url=ktrdr_api_base_url,
        api_key=api_key
    )
    
    await service.initialize()
    return service