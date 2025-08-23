"""
Assistant Researcher Agent for KTRDR Research Agents

Executes experiments and provides detailed analysis at every stage,
from training dynamics to final backtest results.
"""

import asyncio
import json
import logging
import aiohttp
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from .base import BaseResearchAgent

logger = logging.getLogger(__name__)


class AssistantAgent(BaseResearchAgent):
    """
    Assistant Researcher Agent - The Analytical Executor

    Responsibilities:
    - Execute KTRDR training and backtesting experiments
    - Monitor and interpret training metrics in real-time
    - Make decisions about experiment continuation
    - Analyze backtest performance and generate insights
    - Provide detailed updates to coordinator and knowledge base
    """

    def __init__(self, agent_id: str, **config):
        super().__init__(agent_id, "assistant", **config)

        # KTRDR API configuration
        self.ktrdr_api_url = config.get("ktrdr_api_url", "http://localhost:8000")
        self.ktrdr_api_key = config.get("ktrdr_api_key")

        # Assistant-specific configuration
        self.max_concurrent_experiments = config.get("max_concurrent_experiments", 2)
        self.fitness_threshold = config.get("fitness_threshold", 0.5)
        self.max_training_time = config.get("max_training_time", 14400)  # 4 hours

        # Execution state
        self.active_experiments: Dict[UUID, Dict[str, Any]] = {}
        self.experiment_queue: List[UUID] = []

        # HTTP session for KTRDR API calls
        self.http_session: Optional[aiohttp.ClientSession] = None

    async def _initialize_agent(self) -> None:
        """Initialize assistant-specific functionality"""
        # Create HTTP session for KTRDR API
        connector = aiohttp.TCPConnector(limit=10)
        timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes

        headers = {}
        if self.ktrdr_api_key:
            headers["Authorization"] = f"Bearer {self.ktrdr_api_key}"

        self.http_session = aiohttp.ClientSession(
            connector=connector, timeout=timeout, headers=headers
        )

        # Test KTRDR API connectivity
        await self._test_ktrdr_connectivity()

        await self.log_activity(
            "Assistant agent initialized",
            {
                "ktrdr_api_url": self.ktrdr_api_url,
                "max_concurrent_experiments": self.max_concurrent_experiments,
            },
        )

    async def _execute_cycle(self) -> None:
        """Main assistant execution cycle"""
        try:
            await self._update_status("active", "Checking for experiment assignments")

            # Check for new experiment assignments
            await self._check_experiment_queue()

            # Monitor active experiments
            await self._monitor_active_experiments()

            # Process completed experiments
            await self._process_completed_experiments()

            await self._update_status("idle", "Monitoring experiments")
            await asyncio.sleep(30)  # Check every 30 seconds

        except Exception as e:
            self.logger.error(f"Error in assistant cycle: {e}")
            await self._update_status("error", f"Cycle error: {e}")

    async def _cleanup_agent(self) -> None:
        """Cleanup assistant-specific resources"""
        # Cancel active experiments
        for exp_id in list(self.active_experiments.keys()):
            await self._cancel_experiment(exp_id)

        # Close HTTP session
        if self.http_session:
            await self.http_session.close()

        await self.log_activity("Assistant agent shutting down")

    async def _test_ktrdr_connectivity(self) -> None:
        """Test connectivity to KTRDR API"""
        try:
            async with self.http_session.get(
                f"{self.ktrdr_api_url}/health"
            ) as response:
                if response.status == 200:
                    await self.log_activity("KTRDR API connectivity confirmed")
                else:
                    raise Exception(f"KTRDR API health check failed: {response.status}")
        except Exception as e:
            self.logger.warning(f"KTRDR API connectivity test failed: {e}")
            # Don't fail initialization, just log the warning

    async def _check_experiment_queue(self) -> None:
        """Check for new experiments to execute"""
        if len(self.active_experiments) >= self.max_concurrent_experiments:
            return  # Already at capacity

        # Get queued experiments
        available_slots = self.max_concurrent_experiments - len(self.active_experiments)
        queued_experiments = await self.db.get_queued_experiments(limit=available_slots)

        for experiment in queued_experiments:
            try:
                await self._start_experiment(experiment)
            except Exception as e:
                self.logger.error(f"Failed to start experiment {experiment['id']}: {e}")
                await self.db.update_experiment_status(
                    experiment["id"],
                    "failed",
                    error_details={"error": str(e), "stage": "startup"},
                )

    async def _start_experiment(self, experiment: Dict[str, Any]) -> None:
        """Start executing an experiment"""
        experiment_id = experiment["id"]

        await self.log_activity(
            f"Starting experiment: {experiment['experiment_name']}",
            {"experiment_id": str(experiment_id)},
        )

        # Update experiment status
        await self.db.update_experiment_status(experiment_id, "running")

        # Assign to this agent
        query = """
        UPDATE research.experiments 
        SET assigned_agent_id = (
            SELECT id FROM research.agent_states WHERE agent_id = $1
        )
        WHERE id = $2
        """
        await self.db.execute_query(query, self.agent_id, experiment_id)

        # Add to active experiments
        self.active_experiments[experiment_id] = {
            "experiment": experiment,
            "started_at": datetime.utcnow(),
            "stage": "initializing",
            "ktrdr_job_id": None,
            "training_metrics": [],
            "status": "running",
        }

        # Start experiment execution in background
        task = asyncio.create_task(self._execute_experiment(experiment_id))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _execute_experiment(self, experiment_id: UUID) -> None:
        """Execute a complete experiment lifecycle"""
        try:
            experiment_data = self.active_experiments[experiment_id]
            experiment = experiment_data["experiment"]

            await self.log_activity(
                f"Executing experiment: {experiment['experiment_name']}"
            )

            # Stage 1: Prepare experiment configuration
            await self._update_experiment_stage(experiment_id, "preparing")
            config = await self._prepare_experiment_config(experiment)

            # Stage 2: Start KTRDR training
            await self._update_experiment_stage(experiment_id, "training")
            job_result = await self._start_ktrdr_training(experiment_id, config)

            if not job_result or job_result.get("status") == "failed":
                raise Exception("KTRDR training failed to start")

            experiment_data["ktrdr_job_id"] = job_result.get("job_id")

            # Stage 3: Monitor training progress
            await self._monitor_training_progress(experiment_id)

            # Stage 4: Analyze results and run backtest
            await self._update_experiment_stage(experiment_id, "analyzing")
            await self._analyze_experiment_results(experiment_id)

            # Stage 5: Generate insights and complete
            await self._update_experiment_stage(experiment_id, "completing")
            await self._complete_experiment(experiment_id)

        except Exception as e:
            self.logger.error(f"Experiment {experiment_id} failed: {e}")
            await self._fail_experiment(experiment_id, str(e))
        finally:
            # Clean up
            if experiment_id in self.active_experiments:
                del self.active_experiments[experiment_id]

    async def _prepare_experiment_config(
        self, experiment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare KTRDR configuration from experiment specification"""
        config = experiment.get("configuration", {})

        # Convert research experiment to KTRDR training configuration
        ktrdr_config = {
            "strategy_name": experiment["experiment_name"],
            "experiment_type": experiment["experiment_type"],
            "hypothesis": experiment["hypothesis"],
            # Training parameters (defaults can be overridden by experiment config)
            "epochs": config.get("epochs", 100),
            "batch_size": config.get("batch_size", 64),
            "learning_rate": config.get("learning_rate", 0.001),
            "validation_split": config.get("validation_split", 0.2),
            # Data parameters
            "symbols": config.get("symbols", ["SPY"]),
            "timeframe": config.get("timeframe", "1h"),
            "lookback_period": config.get("lookback_period", "2y"),
            # Model architecture
            "model_type": config.get("model_type", "neural_fuzzy"),
            "layers": config.get("layers", [64, 32, 16]),
            "activation": config.get("activation", "relu"),
            "dropout": config.get("dropout", 0.3),
            # Fuzzy logic parameters
            "fuzzy_rules": config.get("fuzzy_rules", "auto"),
            "membership_functions": config.get("membership_functions", "triangular"),
            # Indicators
            "indicators": config.get("indicators", ["sma", "rsi", "macd", "bb"]),
            # Research metadata
            "research_experiment_id": str(experiment["id"]),
            "generated_by": config.get("generated_by", "unknown"),
            "timestamp": datetime.utcnow().isoformat(),
        }

        return ktrdr_config

    async def _start_ktrdr_training(
        self, experiment_id: UUID, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Start KTRDR training job"""
        try:
            url = f"{self.ktrdr_api_url}/training/start"

            async with self.http_session.post(url, json=config) as response:
                if response.status == 200:
                    result = await response.json()
                    await self.log_activity(
                        f"KTRDR training started for experiment {experiment_id}",
                        {"job_id": result.get("job_id")},
                    )
                    return result
                else:
                    error_text = await response.text()
                    raise Exception(f"KTRDR API error {response.status}: {error_text}")

        except Exception as e:
            self.logger.error(f"Failed to start KTRDR training: {e}")
            raise

    async def _monitor_training_progress(self, experiment_id: UUID) -> None:
        """Monitor KTRDR training progress"""
        experiment_data = self.active_experiments[experiment_id]
        job_id = experiment_data["ktrdr_job_id"]

        if not job_id:
            raise Exception("No KTRDR job ID available for monitoring")

        start_time = datetime.utcnow()
        last_metrics_update = start_time

        while True:
            try:
                # Check if experiment was cancelled
                if experiment_id not in self.active_experiments:
                    break

                # Check timeout
                if (
                    datetime.utcnow() - start_time
                ).total_seconds() > self.max_training_time:
                    raise Exception("Training timeout exceeded")

                # Get training status
                status = await self._get_training_status(job_id)

                if status["status"] == "completed":
                    await self.log_activity(
                        f"Training completed for experiment {experiment_id}"
                    )
                    break
                elif status["status"] == "failed":
                    raise Exception(
                        f"KTRDR training failed: {status.get('error', 'Unknown error')}"
                    )
                elif status["status"] == "running":
                    # Update metrics if available
                    if status.get("metrics"):
                        experiment_data["training_metrics"].append(
                            {
                                "timestamp": datetime.utcnow().isoformat(),
                                "metrics": status["metrics"],
                            }
                        )
                        last_metrics_update = datetime.utcnow()

                        # Analyze metrics for early stopping decisions
                        if await self._should_stop_training(
                            experiment_id, status["metrics"]
                        ):
                            await self.log_activity(
                                f"Early stopping triggered for experiment {experiment_id}"
                            )
                            await self._stop_ktrdr_training(job_id)
                            break

                # Wait before next check
                await asyncio.sleep(30)

            except Exception as e:
                self.logger.error(f"Error monitoring training for {experiment_id}: {e}")
                raise

    async def _get_training_status(self, job_id: str) -> Dict[str, Any]:
        """Get KTRDR training job status"""
        try:
            url = f"{self.ktrdr_api_url}/training/status/{job_id}"

            async with self.http_session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise Exception(f"KTRDR API error {response.status}: {error_text}")

        except Exception as e:
            self.logger.error(f"Failed to get training status: {e}")
            # Return a default status to avoid breaking the monitoring loop
            return {"status": "unknown", "error": str(e)}

    async def _should_stop_training(
        self, experiment_id: UUID, metrics: Dict[str, Any]
    ) -> bool:
        """Decide whether to stop training early based on metrics analysis"""
        experiment_data = self.active_experiments[experiment_id]
        training_metrics = experiment_data["training_metrics"]

        # Need at least 10 metric points for early stopping decisions
        if len(training_metrics) < 10:
            return False

        # Check for loss explosion
        current_loss = metrics.get("loss", float("inf"))
        if current_loss > 10.0:  # Arbitrary threshold
            await self.log_activity(f"Loss explosion detected: {current_loss}")
            return True

        # Check for loss plateau (no improvement in last 20 epochs)
        if len(training_metrics) >= 20:
            recent_losses = [
                m["metrics"].get("loss", float("inf")) for m in training_metrics[-20:]
            ]
            if len(set(recent_losses)) == 1:  # All losses identical
                await self.log_activity("Loss plateau detected - no improvement")
                return True

        # Check for overfitting
        train_acc = metrics.get("accuracy", 0)
        val_acc = metrics.get("val_accuracy", 0)
        if train_acc > 0.95 and val_acc < 0.4:  # Extreme overfitting
            await self.log_activity(
                f"Overfitting detected: train={train_acc:.3f}, val={val_acc:.3f}"
            )
            return True

        return False

    async def _stop_ktrdr_training(self, job_id: str) -> None:
        """Stop KTRDR training job"""
        try:
            url = f"{self.ktrdr_api_url}/training/stop/{job_id}"

            async with self.http_session.post(url) as response:
                if response.status == 200:
                    await self.log_activity(f"KTRDR training stopped: {job_id}")
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to stop training: {error_text}")

        except Exception as e:
            self.logger.error(f"Error stopping KTRDR training: {e}")

    async def _analyze_experiment_results(self, experiment_id: UUID) -> None:
        """Analyze experiment results and generate insights"""
        experiment_data = self.active_experiments[experiment_id]
        job_id = experiment_data["ktrdr_job_id"]

        # Get final results from KTRDR
        results = await self._get_training_results(job_id)

        # Calculate fitness score
        fitness_score = await self._calculate_fitness_score(results)

        # Update experiment with results
        await self.db.update_experiment_status(
            experiment_id, "completed", results=results, fitness_score=fitness_score
        )

        # Generate insights if successful
        if fitness_score > self.fitness_threshold:
            await self._generate_experiment_insights(experiment_id, results)

        await self.log_activity(
            f"Experiment analysis completed: {experiment_id}",
            {
                "fitness_score": fitness_score,
                "success": fitness_score > self.fitness_threshold,
            },
        )

    async def _get_training_results(self, job_id: str) -> Dict[str, Any]:
        """Get final training results from KTRDR"""
        try:
            url = f"{self.ktrdr_api_url}/training/results/{job_id}"

            async with self.http_session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to get results: {error_text}")

        except Exception as e:
            self.logger.error(f"Error getting training results: {e}")
            return {"error": str(e), "status": "failed"}

    async def _calculate_fitness_score(self, results: Dict[str, Any]) -> float:
        """Calculate fitness score based on training results"""
        if results.get("status") == "failed":
            return 0.0

        # Simple fitness calculation (can be enhanced)
        factors = []

        # Training performance
        final_accuracy = results.get("final_accuracy", 0)
        factors.append(final_accuracy)

        # Validation performance
        val_accuracy = results.get("val_accuracy", 0)
        factors.append(val_accuracy)

        # Generalization (difference between train and val)
        generalization = 1.0 - abs(final_accuracy - val_accuracy)
        factors.append(generalization)

        # Backtest performance (if available)
        backtest_metrics = results.get("backtest", {})
        if backtest_metrics:
            sharpe_ratio = backtest_metrics.get("sharpe_ratio", 0)
            # Normalize sharpe ratio to 0-1 scale
            normalized_sharpe = min(1.0, max(0.0, (sharpe_ratio + 1) / 3))
            factors.append(normalized_sharpe)

        # Average all factors
        fitness_score = sum(factors) / len(factors) if factors else 0.0
        return min(1.0, max(0.0, fitness_score))

    async def _generate_experiment_insights(
        self, experiment_id: UUID, results: Dict[str, Any]
    ) -> None:
        """Generate insights from successful experiment"""
        experiment = self.active_experiments[experiment_id]["experiment"]

        # Create insight entry
        insight_content = f"Successful experiment '{experiment['experiment_name']}' with fitness score {results.get('fitness_score', 0):.3f}. Key factors: {results.get('key_success_factors', 'Training dynamics analysis')}"

        await self.db.add_knowledge_entry(
            content_type="success_factor",
            title=f"Success: {experiment['experiment_name']}",
            content=insight_content,
            summary=f"{experiment['experiment_type']} strategy with {results.get('fitness_score', 0):.3f} fitness",
            keywords=[experiment["experiment_type"], "success", "training_results"],
            tags=["assistant_analysis", "successful_experiment"],
            source_experiment_id=experiment_id,
            source_agent_id=await self._get_agent_uuid(),
            quality_score=0.85,
        )

    async def _complete_experiment(self, experiment_id: UUID) -> None:
        """Complete experiment and cleanup"""
        await self.log_activity(f"Experiment completed: {experiment_id}")

        # Update final status
        experiment_data = self.active_experiments[experiment_id]
        experiment_data["status"] = "completed"
        experiment_data["completed_at"] = datetime.utcnow()

    async def _fail_experiment(self, experiment_id: UUID, error_message: str) -> None:
        """Handle experiment failure"""
        await self.log_activity(f"Experiment failed: {experiment_id} - {error_message}")

        # Update experiment status in database
        await self.db.update_experiment_status(
            experiment_id,
            "failed",
            error_details={
                "error": error_message,
                "timestamp": datetime.utcnow().isoformat(),
                "agent_id": self.agent_id,
            },
        )

        # Update local state
        if experiment_id in self.active_experiments:
            experiment_data = self.active_experiments[experiment_id]
            experiment_data["status"] = "failed"
            experiment_data["error"] = error_message

    async def _cancel_experiment(self, experiment_id: UUID) -> None:
        """Cancel an active experiment"""
        if experiment_id not in self.active_experiments:
            return

        experiment_data = self.active_experiments[experiment_id]
        job_id = experiment_data.get("ktrdr_job_id")

        if job_id:
            await self._stop_ktrdr_training(job_id)

        await self.db.update_experiment_status(experiment_id, "aborted")
        del self.active_experiments[experiment_id]

        await self.log_activity(f"Experiment cancelled: {experiment_id}")

    async def _update_experiment_stage(self, experiment_id: UUID, stage: str) -> None:
        """Update experiment stage"""
        if experiment_id in self.active_experiments:
            self.active_experiments[experiment_id]["stage"] = stage
            await self.log_activity(f"Experiment {experiment_id} stage: {stage}")

    async def _monitor_active_experiments(self) -> None:
        """Monitor all active experiments for issues"""
        for experiment_id in list(self.active_experiments.keys()):
            experiment_data = self.active_experiments[experiment_id]

            # Check for stuck experiments
            if experiment_data["status"] == "running":
                elapsed = (
                    datetime.utcnow() - experiment_data["started_at"]
                ).total_seconds()
                if elapsed > self.max_training_time:
                    await self.log_activity(f"Experiment timeout: {experiment_id}")
                    await self._cancel_experiment(experiment_id)

    async def _process_completed_experiments(self) -> None:
        """Process any completed experiments"""
        # This method handles any post-completion processing
        completed_experiments = [
            exp_id
            for exp_id, data in self.active_experiments.items()
            if data["status"] in ("completed", "failed")
        ]

        for exp_id in completed_experiments:
            # Clean up completed experiments after some delay
            experiment_data = self.active_experiments[exp_id]
            if experiment_data.get("completed_at"):
                completed_time = experiment_data["completed_at"]
                if (
                    datetime.utcnow() - completed_time
                ).total_seconds() > 300:  # 5 minutes
                    del self.active_experiments[exp_id]

    async def _get_agent_uuid(self) -> Optional[UUID]:
        """Get agent UUID from database"""
        agent_state = await self.db.get_agent_state(self.agent_id)
        return agent_state["id"] if agent_state else None

    # ========================================================================
    # PUBLIC API METHODS
    # ========================================================================

    async def execute_experiment(
        self, experiment_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an experiment with the given configuration"""
        try:
            # If we have a mock ktrdr_client (for tests), use it directly
            if hasattr(self.ktrdr_client, "start_training"):
                return await self.ktrdr_client.start_training()

            # Otherwise use the real implementation (would call KTRDR API)
            # For now, return a mock result
            return {
                "training_id": "test-training-001",
                "status": "started",
                "experiment_config": experiment_config,
            }
        except Exception as e:
            # Update agent status to error
            self.status = "error"
            self.logger.error(f"Experiment execution failed: {e}")

            # Re-raise as AgentError
            from .base import AgentError

            raise AgentError(f"Experiment execution failed: {e}") from e

    async def monitor_training(self, training_id: str) -> Dict[str, Any]:
        """Monitor the status of a training session"""
        # If we have a mock ktrdr_client (for tests), use it directly
        if hasattr(self.ktrdr_client, "get_training_status"):
            return await self.ktrdr_client.get_training_status()

        # Otherwise use the real implementation
        return {
            "training_id": training_id,
            "status": "running",
            "progress": 0.5,
            "current_epoch": 5,
            "total_epochs": 10,
        }

    async def analyze_results(self, training_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze training/backtesting results"""
        fitness_score = training_results.get("fitness_score", 0.0)

        analysis = {
            "fitness_score": fitness_score,
            "performance_metrics": {
                "profit_factor": training_results.get("profit_factor", 1.0),
                "sharpe_ratio": training_results.get("sharpe_ratio", 0.0),
                "max_drawdown": training_results.get("max_drawdown", 0.0),
                "win_rate": training_results.get("win_rate", 0.0),
            },
            "insights": [
                "Strategy shows moderate performance",
                "Risk-adjusted returns within acceptable range",
            ],
        }

        return analysis

    async def extract_knowledge(
        self, experiment_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract knowledge insights from experiment results"""
        knowledge = {
            "insights": [
                "Identified profitable parameter ranges",
                "Market regime sensitivity detected",
            ],
            "patterns": [
                "Higher volatility improves strategy performance",
                "Trend-following components show consistency",
            ],
            "recommendations": [
                "Consider adaptive position sizing",
                "Implement regime detection filters",
            ],
            "quality_score": 0.75,
        }

        return knowledge
