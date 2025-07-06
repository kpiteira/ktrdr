"""
Mock KTRDR service for testing

Provides a clean, stateful mock that implements the KTRDRService interface.
"""

from typing import Dict, Any, List
from datetime import datetime
from ...services.interfaces import KTRDRService


class MockKTRDRService(KTRDRService):
    """Mock KTRDR service for testing"""
    
    def __init__(self):
        self.call_history: List[Dict[str, Any]] = []
        self.responses: Dict[str, Any] = {}
        self.call_count = 0
        self.errors: Dict[str, Exception] = {}
        
        # Mock job tracking
        self._job_counter = 0
        self._active_jobs: Dict[str, Dict[str, Any]] = {}
    
    def set_response(self, method: str, response: Any):
        """Set predefined response for a method"""
        self.responses[method] = response
    
    def set_error(self, method: str, error: Exception):
        """Set error to raise for a method"""
        self.errors[method] = error
    
    def clear_history(self):
        """Clear call history"""
        self.call_history.clear()
        self.call_count = 0
        self._active_jobs.clear()
    
    async def start_training(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Start training job (mock)"""
        self.call_count += 1
        self._job_counter += 1
        
        self.call_history.append({
            "method": "start_training",
            "config": config,
            "call_number": self.call_count
        })
        
        # Check for error injection
        if "start_training" in self.errors:
            raise self.errors["start_training"]
        
        # Generate mock job
        job_id = f"mock-job-{self._job_counter:03d}"
        
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
        
        # Return predefined response or default
        return self.responses.get("start_training", {
            "job_id": job_id,
            "status": "started",
            "message": "Mock training job started",
            "training_id": job_id,  # Alias for compatibility
            "experiment_config": config
        })
    
    async def get_training_status(self, job_id: str) -> Dict[str, Any]:
        """Get training status (mock)"""
        self.call_count += 1
        self.call_history.append({
            "method": "get_training_status", 
            "job_id": job_id,
            "call_number": self.call_count
        })
        
        # Check for error injection
        if "get_training_status" in self.errors:
            raise self.errors["get_training_status"]
        
        # Return predefined response if set
        if "get_training_status" in self.responses:
            return self.responses["get_training_status"]
        
        # Mock job tracking
        if job_id not in self._active_jobs:
            return {
                "job_id": job_id,
                "training_id": job_id,  # Alias
                "status": "not_found",
                "error": "Job not found in mock service"
            }
        
        job = self._active_jobs[job_id]
        
        # Simulate progress based on time elapsed
        if job["status"] == "running":
            elapsed = (datetime.utcnow() - job["started_at"]).total_seconds()
            
            # Complete after 30 seconds for testing
            if elapsed > 30:
                job["status"] = "completed"
                job["progress"] = 1.0
                job["current_epoch"] = job["total_epochs"]
            else:
                # Linear progress
                job["progress"] = min(0.95, elapsed / 30.0)
                job["current_epoch"] = min(
                    job["total_epochs"],
                    int(job["progress"] * job["total_epochs"]) + 1
                )
        
        return {
            "job_id": job_id,
            "training_id": job_id,  # Alias
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
        """Get training results (mock)"""
        self.call_count += 1
        self.call_history.append({
            "method": "get_training_results",
            "job_id": job_id,
            "call_number": self.call_count
        })
        
        # Check for error injection
        if "get_training_results" in self.errors:
            raise self.errors["get_training_results"]
        
        # Return predefined response if set
        if "get_training_results" in self.responses:
            return self.responses["get_training_results"]
        
        # Check if job exists and is completed
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
            "final_accuracy": 0.85,
            "val_accuracy": 0.82,
            "final_loss": 0.12,
            "training_time_seconds": 30,
            "backtest": {
                "sharpe_ratio": 1.52,
                "profit_factor": 1.34,
                "max_drawdown": 0.06,
                "total_trades": 142,
                "win_rate": 0.68
            },
            "fitness_score": 0.78,
            "model_path": f"/mock/models/{job_id}.pkl",
            "training_config": job["config"],
            "message": "Mock training completed successfully"
        }
    
    async def stop_training(self, job_id: str) -> None:
        """Stop training job (mock)"""
        self.call_count += 1
        self.call_history.append({
            "method": "stop_training",
            "job_id": job_id,
            "call_number": self.call_count
        })
        
        # Check for error injection
        if "stop_training" in self.errors:
            raise self.errors["stop_training"]
        
        # Update job status if it exists
        if job_id in self._active_jobs:
            self._active_jobs[job_id]["status"] = "stopped"
    
    def assert_called_with(self, method: str, expected_arg: Any):
        """Assert method was called with expected argument"""
        calls = [call for call in self.call_history if call["method"] == method]
        assert len(calls) > 0, f"Method {method} was not called"
        
        latest_call = calls[-1]
        if method == "start_training":
            assert latest_call["config"] == expected_arg, f"Method {method} called with wrong config"
        elif method in ("get_training_status", "get_training_results", "stop_training"):
            assert latest_call["job_id"] == expected_arg, f"Method {method} called with wrong job_id"
    
    def assert_called_once(self, method: str):
        """Assert method was called exactly once"""
        calls = [call for call in self.call_history if call["method"] == method]
        assert len(calls) == 1, f"Method {method} was called {len(calls)} times, expected 1"
    
    def assert_not_called(self, method: str):
        """Assert method was not called"""
        calls = [call for call in self.call_history if call["method"] == method]
        assert len(calls) == 0, f"Method {method} was called {len(calls)} times, expected 0"
    
    def get_call_count(self, method: str) -> int:
        """Get number of times method was called"""
        return len([call for call in self.call_history if call["method"] == method])
    
    def get_last_call(self, method: str) -> Dict[str, Any]:
        """Get the last call for a method"""
        calls = [call for call in self.call_history if call["method"] == method]
        if not calls:
            raise AssertionError(f"Method {method} was never called")
        return calls[-1]
    
    def get_job_status(self, job_id: str) -> str:
        """Get current job status (test helper)"""
        if job_id in self._active_jobs:
            return self._active_jobs[job_id]["status"]
        return "not_found"
    
    def set_job_status(self, job_id: str, status: str):
        """Set job status manually (test helper)"""
        if job_id in self._active_jobs:
            self._active_jobs[job_id]["status"] = status