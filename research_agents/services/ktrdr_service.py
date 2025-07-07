"""
KTRDR Service implementations for KTRDR Research Agents

Provides HTTP-based and null object implementations of the KTRDR service interface.
"""

from typing import Optional, Dict, Any
import aiohttp
from datetime import datetime

from ktrdr import get_logger
from ktrdr.errors import (
    ProcessingError, 
    ConnectionError as KtrdrConnectionError,
    retry_with_backoff,
    RetryConfig
)
from .interfaces import KTRDRService

logger = get_logger(__name__)


class HTTPKTRDRService(KTRDRService):
    """HTTP-based implementation of KTRDR service"""
    
    def __init__(
        self, 
        api_url: str, 
        api_key: Optional[str] = None,
        timeout: int = 300
    ):
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self.session is None:
            connector = aiohttp.TCPConnector(limit=10)
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=headers
            )
        
        return self.session
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def start_training(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Start a training job via HTTP API"""
        try:
            session = await self._get_session()
            url = f"{self.api_url}/training/start"
            
            async with session.post(url, json=config) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"KTRDR training started: {result.get('job_id')}")
                    return result
                else:
                    error_text = await response.text()
                    raise ProcessingError(
                        "KTRDR training start failed",
                        error_code="KTRDR_TRAINING_START_FAILED",
                        details={"status_code": response.status, "error_text": error_text}
                    )
                    
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error starting KTRDR training: {e}")
            raise KtrdrConnectionError(
                "Network error starting KTRDR training",
                error_code="KTRDR_NETWORK_ERROR",
                details={"api_url": self.api_url, "original_error": str(e)}
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error starting KTRDR training: {e}")
            raise ProcessingError(
                "Failed to start KTRDR training",
                error_code="KTRDR_TRAINING_START_ERROR",
                details={"original_error": str(e)}
            ) from e
    
    async def get_training_status(self, job_id: str) -> Dict[str, Any]:
        """Get training job status via HTTP API"""
        try:
            session = await self._get_session()
            url = f"{self.api_url}/training/status/{job_id}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    raise ProcessingError(
                        "KTRDR training job not found",
                        error_code="KTRDR_JOB_NOT_FOUND",
                        details={"job_id": job_id}
                    )
                else:
                    error_text = await response.text()
                    raise ProcessingError(
                        "KTRDR training status check failed",
                        error_code="KTRDR_STATUS_CHECK_FAILED",
                        details={"job_id": job_id, "status_code": response.status, "error_text": error_text}
                    )
                    
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error getting training status: {e}")
            # Return a default status to avoid breaking monitoring loops
            return {
                "job_id": job_id,
                "status": "unknown",
                "error": str(e)
            }
        except ProcessingError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting training status: {e}")
            return {
                "job_id": job_id,
                "status": "error", 
                "error": str(e)
            }
    
    async def get_training_results(self, job_id: str) -> Dict[str, Any]:
        """Get training job results via HTTP API"""
        try:
            session = await self._get_session()
            url = f"{self.api_url}/training/results/{job_id}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    raise ProcessingError(
                        "KTRDR training results not found",
                        error_code="KTRDR_RESULTS_NOT_FOUND",
                        details={"job_id": job_id}
                    )
                else:
                    error_text = await response.text()
                    raise ProcessingError(
                        "KTRDR results retrieval failed",
                        error_code="KTRDR_RESULTS_RETRIEVAL_FAILED",
                        details={"job_id": job_id, "status_code": response.status, "error_text": error_text}
                    )
                    
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error getting training results: {e}")
            raise KtrdrConnectionError(
                "Network error getting KTRDR results",
                error_code="KTRDR_NETWORK_ERROR",
                details={"job_id": job_id, "api_url": self.api_url, "original_error": str(e)}
            ) from e
        except ProcessingError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting training results: {e}")
            raise ProcessingError(
                "Failed to get KTRDR training results",
                error_code="KTRDR_RESULTS_ERROR",
                details={"job_id": job_id, "original_error": str(e)}
            ) from e
    
    async def stop_training(self, job_id: str) -> None:
        """Stop a training job via HTTP API"""
        try:
            session = await self._get_session()
            url = f"{self.api_url}/training/stop/{job_id}"
            
            async with session.post(url) as response:
                if response.status in (200, 404):  # 404 is OK - job might already be stopped
                    logger.info(f"KTRDR training stopped: {job_id}")
                else:
                    error_text = await response.text()
                    logger.warning(f"Failed to stop training {job_id}: {response.status} - {error_text}")
                    
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error stopping training: {e}")
            # Don't raise - stopping is best effort
        except Exception as e:
            logger.error(f"Unexpected error stopping training: {e}")
            # Don't raise - stopping is best effort


class NullKTRDRService(KTRDRService):
    """Null object implementation for when KTRDR service is unavailable"""
    
    def __init__(self):
        logger.info("Using NullKTRDRService - KTRDR functionality will use mock responses")
        self._job_counter = 0
        self._active_jobs: Dict[str, Dict[str, Any]] = {}
    
    async def start_training(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Mock training start when KTRDR is unavailable"""
        self._job_counter += 1
        job_id = f"null-job-{self._job_counter:03d}"
        
        # Store job for status tracking
        self._active_jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "progress": 0.0,
            "started_at": datetime.utcnow(),
            "config": config,
            "current_epoch": 1,
            "total_epochs": config.get("epochs", 10)
        }
        
        logger.info(f"Mock KTRDR training started: {job_id}")
        
        return {
            "job_id": job_id,
            "status": "started",
            "message": "Mock training job created - KTRDR service not available",
            "experiment_config": config
        }
    
    async def get_training_status(self, job_id: str) -> Dict[str, Any]:
        """Mock training status when KTRDR is unavailable"""
        if job_id not in self._active_jobs:
            return {
                "job_id": job_id,
                "status": "not_found",
                "error": "Job not found in mock service"
            }
        
        job = self._active_jobs[job_id]
        
        # Simulate progress
        if job["status"] == "running":
            elapsed = (datetime.utcnow() - job["started_at"]).total_seconds()
            
            # Complete after 60 seconds for testing
            if elapsed > 60:
                job["status"] = "completed"
                job["progress"] = 1.0
                job["current_epoch"] = job["total_epochs"]
            else:
                # Linear progress
                job["progress"] = min(0.95, elapsed / 60.0)
                job["current_epoch"] = min(
                    job["total_epochs"], 
                    int(job["progress"] * job["total_epochs"]) + 1
                )
        
        return {
            "job_id": job_id,
            "status": job["status"],
            "progress": job["progress"],
            "current_epoch": job["current_epoch"],
            "total_epochs": job["total_epochs"],
            "metrics": {
                "loss": max(0.1, 1.0 - job["progress"]),
                "accuracy": min(0.95, job["progress"] * 0.8 + 0.2),
                "val_accuracy": min(0.9, job["progress"] * 0.7 + 0.2)
            } if job["status"] == "running" else None
        }
    
    async def get_training_results(self, job_id: str) -> Dict[str, Any]:
        """Mock training results when KTRDR is unavailable"""
        if job_id not in self._active_jobs:
            return {
                "job_id": job_id,
                "status": "failed",
                "error": "Job not found in mock service"
            }
        
        job = self._active_jobs[job_id]
        
        if job["status"] != "completed":
            return {
                "job_id": job_id,
                "status": job["status"],
                "error": f"Job not completed, current status: {job['status']}"
            }
        
        # Generate mock results
        return {
            "job_id": job_id,
            "status": "completed",
            "final_accuracy": 0.82,
            "val_accuracy": 0.78,
            "final_loss": 0.15,
            "training_time_seconds": 60,
            "backtest": {
                "sharpe_ratio": 1.45,
                "profit_factor": 1.28,
                "max_drawdown": 0.08,
                "total_trades": 125,
                "win_rate": 0.64
            },
            "fitness_score": 0.75,
            "model_path": f"/mock/models/{job_id}.pkl",
            "training_config": job["config"],
            "message": "Mock training results - KTRDR service not available"
        }
    
    async def stop_training(self, job_id: str) -> None:
        """Mock training stop when KTRDR is unavailable"""
        if job_id in self._active_jobs:
            self._active_jobs[job_id]["status"] = "stopped"
            logger.info(f"Mock KTRDR training stopped: {job_id}")
        else:
            logger.warning(f"Attempted to stop unknown mock job: {job_id}")
    
    async def close(self):
        """Close mock service (no-op)"""
        pass