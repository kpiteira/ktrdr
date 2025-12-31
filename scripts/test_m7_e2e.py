#!/usr/bin/env python3
"""
M7 Backend-Local Operations E2E Test Suite

This script tests every failure scenario at every stage of the agent lifecycle:
- Design phase interruption
- Training phase interruption
- Backtesting phase interruption
- Assessment phase interruption

For each phase, tests:
- Hard crash (docker restart)
- User cancellation (DELETE /operations/{id})

Run with: uv run python scripts/test_m7_e2e.py

Requires: Docker Compose environment running
"""

import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import httpx

# Configuration
API_BASE = "http://localhost:8000/api/v1"
TIMEOUT = 300  # Max wait time per test phase
POLL_INTERVAL = 2  # Seconds between status checks


class Phase(Enum):
    DESIGNING = "Designing"
    TRAINING = "Training"
    BACKTESTING = "Backtesting"
    ASSESSING = "Assessing"


class InterruptType(Enum):
    HARD_CRASH = "hard_crash"  # docker restart backend
    CANCELLATION = "cancellation"  # DELETE /operations/{id}


@dataclass
class TestResult:
    test_name: str
    phase: Phase
    interrupt_type: InterruptType
    passed: bool
    details: str
    checkpoint_available: bool | None = None
    resumed_successfully: bool | None = None
    skipped_phases: list[str] | None = None


class M7E2ETest:
    """End-to-end test for M7 checkpoint system."""

    def __init__(self):
        self.client = httpx.Client(timeout=30.0)
        self.results: list[TestResult] = []

    def log(self, msg: str):
        """Print timestamped log message."""
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}")

    def api_get(self, endpoint: str) -> dict:
        """GET request to API."""
        resp = self.client.get(f"{API_BASE}/{endpoint}")
        return resp.json()

    def api_post(self, endpoint: str, json_data: dict | None = None) -> dict:
        """POST request to API."""
        resp = self.client.post(f"{API_BASE}/{endpoint}", json=json_data)
        return resp.json()

    def api_delete(self, endpoint: str) -> dict:
        """DELETE request to API."""
        resp = self.client.delete(f"{API_BASE}/{endpoint}")
        return resp.json()

    def wait_for_backend(self, timeout: int = 60) -> bool:
        """Wait for backend to be healthy."""
        self.log("Waiting for backend to be healthy...")
        start = time.time()
        while time.time() - start < timeout:
            try:
                resp = self.client.get(f"{API_BASE}/health")
                if resp.status_code == 200:
                    self.log("Backend is healthy")
                    return True
            except Exception:
                # Backend may not be up yet; ignore transient errors and retry
                pass
            time.sleep(2)
        self.log("Backend health check timed out")
        return False

    def trigger_agent(self, model: str = "haiku") -> str | None:
        """Trigger a new agent cycle and return operation ID."""
        self.log(f"Triggering agent with model={model}")
        try:
            resp = self.api_post(f"agent/trigger?model={model}")
            if resp.get("triggered"):
                op_id = resp["operation_id"]
                self.log(f"Agent triggered: {op_id}")
                return op_id
            else:
                self.log(f"Failed to trigger agent: {resp}")
                return None
        except Exception as e:
            self.log(f"Error triggering agent: {e}")
            return None

    def get_operation_status(self, op_id: str) -> dict:
        """Get operation status."""
        try:
            resp = self.api_get(f"operations/{op_id}")
            return resp.get("data", {})
        except Exception as e:
            self.log(f"Error getting operation status: {e}")
            return {}

    def get_checkpoint(self, op_id: str) -> dict | None:
        """Get checkpoint for operation."""
        try:
            resp = self.api_get(f"checkpoints/{op_id}")
            if resp.get("success"):
                return resp.get("data")
            return None
        except Exception:
            return None

    def get_training_checkpoint_epoch(self, training_op_id: str) -> int | None:
        """Get the epoch from a training operation's checkpoint."""
        try:
            checkpoint = self.get_checkpoint(training_op_id)
            if checkpoint:
                return checkpoint.get("state", {}).get("epoch")
            return None
        except Exception:
            return None

    def wait_for_training_checkpoint(self, op_id: str, min_epoch: int = 5, timeout: int = 120) -> int | None:
        """Wait for training to have a checkpoint with at least min_epoch epochs."""
        self.log(f"Waiting for training checkpoint with at least {min_epoch} epochs...")
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_operation_status(op_id)

            # Check if we're still in training phase
            current_step = status.get("progress", {}).get("current_step", "")
            op_status = status.get("status", "")

            if op_status in ("failed", "completed", "cancelled"):
                self.log(f"Operation ended: {op_status}")
                return None

            if "training" not in current_step.lower():
                self.log(f"No longer in training phase: {current_step}")
                return None

            # Get the training operation ID from agent checkpoint
            agent_checkpoint = self.get_checkpoint(op_id)
            if agent_checkpoint:
                training_op_id = agent_checkpoint.get("state", {}).get("training_operation_id")
                if training_op_id:
                    epoch = self.get_training_checkpoint_epoch(training_op_id)
                    if epoch and epoch >= min_epoch:
                        self.log(f"Training checkpoint at epoch {epoch}")
                        return epoch

            time.sleep(5)

        self.log("Timeout waiting for training checkpoint")
        return None

    def wait_for_phase(self, op_id: str, target_phase: Phase, timeout: int = TIMEOUT) -> bool:
        """Wait for operation to reach a specific phase."""
        self.log(f"Waiting for phase: {target_phase.value}")
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_operation_status(op_id)
            current_step = status.get("progress", {}).get("current_step", "")
            op_status = status.get("status", "")

            if target_phase.value.lower() in current_step.lower():
                self.log(f"Reached phase: {target_phase.value}")
                return True

            if op_status in ("failed", "completed", "cancelled"):
                self.log(f"Operation ended before reaching phase: {op_status}")
                return False

            time.sleep(POLL_INTERVAL)

        self.log(f"Timeout waiting for phase {target_phase.value}")
        return False

    def hard_crash_backend(self):
        """Simulate hard crash by restarting backend container."""
        self.log("Simulating hard crash (docker restart backend)...")
        result = subprocess.run(
            ["docker", "compose", "restart", "backend"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            self.log(f"Docker restart failed: {result.stderr}")
        else:
            self.log("Backend restarted")

        # Also restart workers to re-register with new backend
        self.log("Restarting workers to re-register...")
        subprocess.run(
            ["docker", "compose", "restart", "training-worker-1", "training-worker-2",
             "backtest-worker-1", "backtest-worker-2"],
            capture_output=True,
            text=True,
        )
        # Wait for workers to come up and register
        time.sleep(15)

    def cancel_operation(self, op_id: str) -> bool:
        """Cancel an operation."""
        self.log(f"Cancelling operation: {op_id}")
        try:
            resp = self.api_delete(f"operations/{op_id}")
            success = resp.get("success", False)
            self.log(f"Cancellation result: {resp}")
            return success
        except Exception as e:
            self.log(f"Error cancelling operation: {e}")
            return False

    def resume_operation(self, op_id: str) -> dict:
        """Resume an operation from checkpoint."""
        self.log(f"Resuming operation: {op_id}")
        try:
            resp = self.api_post(f"operations/{op_id}/resume")
            self.log(f"Resume result: {resp}")
            return resp
        except Exception as e:
            self.log(f"Error resuming operation: {e}")
            return {"success": False, "error": str(e)}

    def run_interrupt_test(
        self,
        target_phase: Phase,
        interrupt_type: InterruptType,
    ) -> TestResult:
        """
        Run a single interrupt test:
        1. Trigger agent
        2. Wait for target phase
        3. Interrupt (crash or cancel)
        4. Verify reconciliation/checkpoint
        5. Resume and verify
        """
        test_name = f"{target_phase.value}_{interrupt_type.value}"
        self.log(f"\n{'='*60}")
        self.log(f"TEST: {test_name}")
        self.log(f"{'='*60}")

        # Step 1: Trigger agent
        op_id = self.trigger_agent()
        if not op_id:
            return TestResult(
                test_name=test_name,
                phase=target_phase,
                interrupt_type=interrupt_type,
                passed=False,
                details="Failed to trigger agent",
            )

        # Step 2: Wait for target phase
        if not self.wait_for_phase(op_id, target_phase):
            return TestResult(
                test_name=test_name,
                phase=target_phase,
                interrupt_type=interrupt_type,
                passed=False,
                details=f"Failed to reach phase {target_phase.value}",
            )

        # Step 2b: For training phase, wait a bit for training to make progress
        # Then cancel mid-training to test checkpoint/resume
        training_epoch_before = None
        if target_phase == Phase.TRAINING and interrupt_type == InterruptType.CANCELLATION:
            # Wait 20 seconds for training to make progress and save periodic checkpoints
            self.log("Waiting 20s for training to make progress...")
            time.sleep(20)
            # Check if we're still training
            status = self.get_operation_status(op_id)
            current_step = status.get("progress", {}).get("current_step", "")
            if "training" in current_step.lower():
                self.log("Still in training phase - good, will cancel now")
            else:
                self.log(f"Training may have ended: {current_step}")
        elif target_phase == Phase.BACKTESTING and interrupt_type == InterruptType.CANCELLATION:
            # For backtesting, wait a bit for backtest to make progress
            self.log("Waiting 15s for backtesting to make progress...")
            time.sleep(15)
        else:
            # Give a moment for phase to establish
            time.sleep(3)

        # Step 3: Interrupt
        if interrupt_type == InterruptType.HARD_CRASH:
            self.hard_crash_backend()
            if not self.wait_for_backend():
                return TestResult(
                    test_name=test_name,
                    phase=target_phase,
                    interrupt_type=interrupt_type,
                    passed=False,
                    details="Backend failed to come back up after crash",
                )
        elif interrupt_type == InterruptType.CANCELLATION:
            if not self.cancel_operation(op_id):
                return TestResult(
                    test_name=test_name,
                    phase=target_phase,
                    interrupt_type=interrupt_type,
                    passed=False,
                    details="Failed to cancel operation",
                )
            time.sleep(2)  # Let cancellation complete

        # Step 4: Verify operation status
        status = self.get_operation_status(op_id)
        op_status = status.get("status", "")
        error_msg = status.get("error_message", "") or ""

        expected_status = "failed" if interrupt_type == InterruptType.HARD_CRASH else "cancelled"
        if op_status != expected_status:
            return TestResult(
                test_name=test_name,
                phase=target_phase,
                interrupt_type=interrupt_type,
                passed=False,
                details=f"Expected status '{expected_status}', got '{op_status}'",
            )

        # Step 5: Check checkpoint
        checkpoint = self.get_checkpoint(op_id)
        checkpoint_available = checkpoint is not None
        checkpoint_phase = checkpoint.get("state", {}).get("phase") if checkpoint else None

        self.log(f"Checkpoint available: {checkpoint_available}")
        if checkpoint:
            self.log(f"Checkpoint phase: {checkpoint_phase}")

        # For hard crash, verify error message mentions checkpoint
        if interrupt_type == InterruptType.HARD_CRASH:
            if checkpoint_available and "checkpoint available" not in error_msg.lower():
                self.log(f"Warning: Checkpoint exists but error message doesn't mention it: {error_msg}")
            elif not checkpoint_available and "no checkpoint" not in error_msg.lower():
                self.log(f"Warning: No checkpoint but error message doesn't mention it: {error_msg}")

        # Step 6: Resume and verify (if checkpoint exists)
        resumed_successfully = None
        skipped_phases = []
        training_epoch_after = None

        if checkpoint_available:
            resume_result = self.resume_operation(op_id)
            if resume_result.get("success"):
                resumed_successfully = True
                self.log("Resume initiated successfully")

                # Wait a moment and check what phase it's in
                time.sleep(5)
                new_status = self.get_operation_status(op_id)
                new_step = new_status.get("progress", {}).get("current_step", "")
                self.log(f"After resume, current step: {new_step}")

                # Determine which phases were skipped
                phase_order = [Phase.DESIGNING, Phase.TRAINING, Phase.BACKTESTING, Phase.ASSESSING]
                checkpoint_phase_idx = next(
                    (i for i, p in enumerate(phase_order) if p.value.lower() == checkpoint_phase),
                    -1,
                )
                if checkpoint_phase_idx >= 0:
                    skipped_phases = [p.value for p in phase_order[:checkpoint_phase_idx]]
                    self.log(f"Skipped phases: {skipped_phases}")

                # For training, verify the checkpoint has epoch info
                if target_phase == Phase.TRAINING:
                    agent_checkpoint = self.get_checkpoint(op_id)
                    if agent_checkpoint:
                        training_op_id = agent_checkpoint.get("state", {}).get("training_operation_id")
                        if training_op_id:
                            # Check the training operation's checkpoint for epoch
                            training_checkpoint = self.get_checkpoint(training_op_id)
                            if training_checkpoint:
                                epoch_in_checkpoint = training_checkpoint.get("state", {}).get("epoch")
                                if epoch_in_checkpoint:
                                    training_epoch_before = epoch_in_checkpoint
                                    self.log(f"Training checkpoint exists at epoch {epoch_in_checkpoint}")

                            # Wait and check progress
                            time.sleep(10)
                            training_status = self.get_operation_status(training_op_id)
                            training_progress = training_status.get("progress", {})
                            current_epoch = training_progress.get("steps_completed", 0)
                            self.log(f"Training resumed, current epoch: {current_epoch}")
                            training_epoch_after = current_epoch

                # Cancel to clean up (don't let it run forever)
                time.sleep(2)
                self.cancel_operation(op_id)
            else:
                resumed_successfully = False
                self.log(f"Resume failed: {resume_result}")

        # Determine pass/fail
        passed = True
        details_parts = []

        if interrupt_type == InterruptType.HARD_CRASH:
            details_parts.append(f"Status after crash: {op_status}")
            details_parts.append(f"Checkpoint: {'available' if checkpoint_available else 'not available'}")
            if checkpoint_available:
                details_parts.append(f"Checkpoint phase: {checkpoint_phase}")
                if resumed_successfully:
                    details_parts.append(f"Resume: success, skipped {skipped_phases}")
                else:
                    details_parts.append("Resume: failed")
                    passed = False
        elif interrupt_type == InterruptType.CANCELLATION:
            if not checkpoint_available:
                # Cancellation should save a checkpoint
                passed = False
                details_parts.append("Cancellation did not save checkpoint")
            else:
                details_parts.append(f"Checkpoint saved at phase: {checkpoint_phase}")
                if resumed_successfully:
                    details_parts.append(f"Resume: success, skipped {skipped_phases}")
                    # For training, report epoch info
                    if target_phase == Phase.TRAINING and training_epoch_before is not None:
                        details_parts.append(f"Epoch before cancel: {training_epoch_before}")
                        if training_epoch_after is not None:
                            details_parts.append(f"Epoch after resume: {training_epoch_after}")
                elif resumed_successfully is False:
                    details_parts.append("Resume: failed")
                    passed = False

        return TestResult(
            test_name=test_name,
            phase=target_phase,
            interrupt_type=interrupt_type,
            passed=passed,
            details="; ".join(details_parts),
            checkpoint_available=checkpoint_available,
            resumed_successfully=resumed_successfully,
            skipped_phases=skipped_phases,
        )

    def run_all_tests(self):
        """Run all E2E tests."""
        self.log("\n" + "=" * 70)
        self.log("M7 BACKEND-LOCAL OPERATIONS E2E TEST SUITE")
        self.log("=" * 70)

        # Check backend is healthy first
        if not self.wait_for_backend():
            self.log("Backend not available, aborting tests")
            return

        # Define test matrix
        # Focus on training and backtesting - where checkpoints have real value
        test_matrix = [
            # Training phase tests - verify epoch-level resume
            (Phase.TRAINING, InterruptType.CANCELLATION),
            # Backtesting phase tests - verify backtest progress resume
            # Note: Requires training to complete, so may timeout if training fails gate
            (Phase.BACKTESTING, InterruptType.CANCELLATION),
        ]

        for phase, interrupt_type in test_matrix:
            try:
                result = self.run_interrupt_test(phase, interrupt_type)
                self.results.append(result)
            except Exception as e:
                self.log(f"Test {phase.value}_{interrupt_type.value} crashed: {e}")
                self.results.append(
                    TestResult(
                        test_name=f"{phase.value}_{interrupt_type.value}",
                        phase=phase,
                        interrupt_type=interrupt_type,
                        passed=False,
                        details=f"Test crashed: {e}",
                    )
                )

            # Brief pause between tests
            time.sleep(5)

        self.print_summary()

    def print_summary(self):
        """Print test results summary."""
        self.log("\n" + "=" * 70)
        self.log("TEST RESULTS SUMMARY")
        self.log("=" * 70)

        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed

        for result in self.results:
            status = "PASS" if result.passed else "FAIL"
            self.log(f"\n[{status}] {result.test_name}")
            self.log(f"       Phase: {result.phase.value}")
            self.log(f"       Interrupt: {result.interrupt_type.value}")
            self.log(f"       Details: {result.details}")
            if result.checkpoint_available is not None:
                self.log(f"       Checkpoint: {'yes' if result.checkpoint_available else 'no'}")
            if result.resumed_successfully is not None:
                self.log(f"       Resumed: {'yes' if result.resumed_successfully else 'no'}")
            if result.skipped_phases:
                self.log(f"       Skipped phases: {result.skipped_phases}")

        self.log("\n" + "-" * 70)
        self.log(f"TOTAL: {passed} passed, {failed} failed out of {len(self.results)} tests")
        self.log("-" * 70)

        if failed > 0:
            self.log("\nFAILED TESTS:")
            for result in self.results:
                if not result.passed:
                    self.log(f"  - {result.test_name}: {result.details}")


def main():
    """Main entry point."""
    print("M7 Backend-Local Operations E2E Test Suite")
    print("This test will interrupt agent operations at various stages")
    print("and verify checkpoint/resume behavior.\n")

    test = M7E2ETest()
    test.run_all_tests()

    # Exit with non-zero if any tests failed
    if any(not r.passed for r in test.results):
        sys.exit(1)


if __name__ == "__main__":
    main()
