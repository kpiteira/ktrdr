# Phase 2: Training Integration

**Goal**: Replace training stub with real training API polling

**Prerequisite**: Phase 1 complete (real design phase working)
**Branch**: `feature/agent-mvp`

---

## Task 2.1: Extract training config from strategy YAML

When design completes, we need to read the saved strategy to get symbols/timeframes for training.

**File**: `ktrdr/agents/strategy_loader.py` (new file)

```python
"""
Strategy configuration loader.

Reads strategy YAML files and extracts configuration for training/backtest.
"""

from pathlib import Path
from typing import Any

import yaml

from ktrdr import get_logger

logger = get_logger(__name__)

# Default strategies directory
STRATEGIES_DIR = Path("strategies")


def load_strategy_config(strategy_name: str) -> dict[str, Any]:
    """Load a strategy configuration from disk.

    Args:
        strategy_name: Name of the strategy (without .yaml extension)

    Returns:
        Parsed strategy configuration dict

    Raises:
        FileNotFoundError: If strategy file doesn't exist
        ValueError: If YAML is invalid
    """
    path = STRATEGIES_DIR / f"{strategy_name}.yaml"

    if not path.exists():
        raise FileNotFoundError(f"Strategy not found: {path}")

    with open(path) as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid strategy YAML: {e}")

    return config


def extract_training_params(config: dict[str, Any]) -> dict[str, Any]:
    """Extract training parameters from strategy config.

    Handles both v2 (nested training_data) and legacy v1 formats.

    Args:
        config: Strategy configuration dict

    Returns:
        Dict with:
        - symbols: list[str]
        - timeframes: list[str]
        - start_date: str | None
        - end_date: str | None
    """
    # v2 format: nested under training_data
    training_data = config.get("training_data", {})

    # Extract symbols
    symbols_config = training_data.get("symbols", {})
    if isinstance(symbols_config, dict):
        symbols = symbols_config.get("list", [])
    elif isinstance(symbols_config, list):
        # v1 format: direct list
        symbols = symbols_config
    else:
        symbols = []

    # Extract timeframes
    timeframes_config = training_data.get("timeframes", {})
    if isinstance(timeframes_config, dict):
        timeframes = timeframes_config.get("list", [])
    elif isinstance(timeframes_config, list):
        # v1 format: direct list
        timeframes = timeframes_config
    else:
        timeframes = []

    # Date range (optional)
    date_range = training_data.get("date_range", {})
    start_date = date_range.get("start")
    end_date = date_range.get("end")

    return {
        "symbols": symbols,
        "timeframes": timeframes,
        "start_date": start_date,
        "end_date": end_date,
    }
```

**Test file**: `tests/unit/agents/test_strategy_loader.py`

```python
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from ktrdr.agents.strategy_loader import load_strategy_config, extract_training_params


class TestExtractTrainingParams:
    """Tests for extract_training_params."""

    def test_v2_format_nested(self):
        """Should extract from v2 nested training_data format."""
        config = {
            "training_data": {
                "symbols": {
                    "mode": "multi_symbol",
                    "list": ["EURUSD", "GBPUSD"],
                },
                "timeframes": {
                    "mode": "single",
                    "list": ["4h"],
                },
            }
        }

        result = extract_training_params(config)

        assert result["symbols"] == ["EURUSD", "GBPUSD"]
        assert result["timeframes"] == ["4h"]

    def test_v1_format_direct_list(self):
        """Should handle v1 direct list format."""
        config = {
            "training_data": {
                "symbols": ["AAPL", "MSFT"],
                "timeframes": ["1h", "1d"],
            }
        }

        result = extract_training_params(config)

        assert result["symbols"] == ["AAPL", "MSFT"]
        assert result["timeframes"] == ["1h", "1d"]

    def test_missing_training_data(self):
        """Should return empty lists if training_data missing."""
        config = {"name": "test_strategy"}

        result = extract_training_params(config)

        assert result["symbols"] == []
        assert result["timeframes"] == []
```

---

## Task 2.2: Add training phase to AgentService

**File**: `ktrdr/api/services/agent_service.py`

Add training phase method and update cycle runner:

```python
async def _run_research_cycle(self, operation_id: str) -> None:
    """Execute a research cycle."""
    try:
        # Phase 1: Design
        await self._update_phase(operation_id, "designing")
        design_result = await self._run_design_phase(operation_id)

        if not design_result.get("success"):
            await self._ops.fail_operation(
                operation_id,
                error_message=design_result.get("error", "Design failed"),
            )
            return

        strategy_name = design_result.get("strategy_name")
        await self._update_metadata(operation_id, {
            "strategy_name": strategy_name,
            "strategy_path": design_result.get("strategy_path"),
        })

        # Phase 2: Training (NEW)
        await self._update_phase(operation_id, "training")
        train_result = await self._run_training_phase(operation_id, strategy_name)

        if not train_result.get("success"):
            await self._ops.fail_operation(
                operation_id,
                error_message=train_result.get("error", "Training failed"),
            )
            return

        # Check training gate
        gate_passed, gate_reason = self._check_training_gate(train_result)
        if not gate_passed:
            await self._ops.fail_operation(
                operation_id,
                error_message=f"Training gate failed: {gate_reason}",
            )
            return

        await self._update_metadata(operation_id, {
            "training_result": train_result,
            "model_path": train_result.get("model_path"),
        })

        # Phase 2 complete - mark done
        # (Phases 3-4 will add backtest, assessment here)
        await self._ops.complete_operation(
            operation_id,
            result_summary={
                "phase": "trained",
                "strategy_name": strategy_name,
                "model_path": train_result.get("model_path"),
            },
        )

        logger.info(f"Research cycle {operation_id} completed (training)")

    except asyncio.CancelledError:
        logger.info(f"Research cycle {operation_id} cancelled")
        raise
    except Exception as e:
        logger.error(f"Research cycle {operation_id} failed: {e}")
        await self._ops.fail_operation(operation_id, error_message=str(e))


async def _run_training_phase(
    self,
    operation_id: str,
    strategy_name: str,
) -> dict[str, Any]:
    """Run training for the designed strategy.

    Args:
        operation_id: Current operation ID
        strategy_name: Name of strategy to train

    Returns:
        Dict with success, model_path, metrics, or error
    """
    from ktrdr.agents.strategy_loader import load_strategy_config, extract_training_params
    from ktrdr.agents.executor import start_training_via_api

    # Update progress
    await self._ops.update_progress(
        operation_id,
        percentage=30,
        current_step="Loading strategy configuration",
    )

    # Load strategy and extract training params
    try:
        config = load_strategy_config(strategy_name)
        params = extract_training_params(config)
    except Exception as e:
        return {"success": False, "error": f"Failed to load strategy: {e}"}

    if not params["symbols"]:
        return {"success": False, "error": "Strategy has no training symbols defined"}

    if not params["timeframes"]:
        return {"success": False, "error": "Strategy has no training timeframes defined"}

    # Start training
    await self._ops.update_progress(
        operation_id,
        percentage=35,
        current_step=f"Starting training for {strategy_name}",
    )

    train_response = await start_training_via_api(
        strategy_name=strategy_name,
        symbols=params["symbols"],
        timeframes=params["timeframes"],
        start_date=params.get("start_date"),
        end_date=params.get("end_date"),
    )

    if not train_response.get("success"):
        return {"success": False, "error": train_response.get("error")}

    training_op_id = train_response.get("operation_id")
    if not training_op_id:
        return {"success": False, "error": "No training operation ID returned"}

    # Poll for training completion
    return await self._poll_training_completion(operation_id, training_op_id)


async def _poll_training_completion(
    self,
    agent_op_id: str,
    training_op_id: str,
) -> dict[str, Any]:
    """Poll training operation until completion.

    Args:
        agent_op_id: Agent research operation ID (for progress updates)
        training_op_id: Training operation ID to poll

    Returns:
        Dict with training results or error
    """
    import httpx
    import os

    base_url = os.getenv("KTRDR_API_URL", "http://localhost:8000")
    poll_interval = 5  # seconds
    max_polls = 360  # 30 minutes max

    async with httpx.AsyncClient(timeout=30.0) as client:
        for poll_count in range(max_polls):
            # Check if we've been cancelled
            try:
                await asyncio.sleep(0)  # Yield to allow cancellation
            except asyncio.CancelledError:
                # Try to cancel the training operation too
                try:
                    await client.delete(
                        f"{base_url}/api/v1/operations/{training_op_id}/cancel"
                    )
                except Exception:
                    pass
                raise

            # Poll training status
            try:
                response = await client.get(
                    f"{base_url}/api/v1/operations/{training_op_id}"
                )
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logger.warning(f"Failed to poll training status: {e}")
                await asyncio.sleep(poll_interval)
                continue

            op_data = data.get("data", data)
            status = op_data.get("status", "unknown")
            progress = op_data.get("progress", {})

            # Update agent operation progress
            training_pct = progress.get("percentage", 0)
            # Training is 35-85% of overall cycle
            overall_pct = 35 + (training_pct * 0.5)
            await self._ops.update_progress(
                agent_op_id,
                percentage=overall_pct,
                current_step=progress.get("current_step", "Training..."),
            )

            # Check completion
            if status == "completed":
                result_summary = op_data.get("result_summary", {})
                return {
                    "success": True,
                    "training_operation_id": training_op_id,
                    "model_path": result_summary.get("model_path"),
                    "metrics": result_summary.get("metrics", {}),
                    "accuracy": result_summary.get("accuracy"),
                    "final_loss": result_summary.get("final_loss"),
                }

            if status == "failed":
                return {
                    "success": False,
                    "error": op_data.get("error_message", "Training failed"),
                }

            if status == "cancelled":
                return {
                    "success": False,
                    "error": "Training was cancelled",
                }

            await asyncio.sleep(poll_interval)

    return {"success": False, "error": "Training timed out after 30 minutes"}
```

---

## Task 2.3: Implement training gate

**File**: `ktrdr/agents/gates.py` (new file)

```python
"""
Quality gates for research cycle phases.

Gates are simple threshold checks that determine whether to proceed
to the next phase or fail the cycle.
"""

from typing import Any


def check_training_gate(metrics: dict[str, Any]) -> tuple[bool, str]:
    """Check if training results pass the quality gate.

    Thresholds are intentionally loose for MVP - we want to gather data
    on what fails before tightening them.

    Args:
        metrics: Training result metrics dict. Expected keys:
            - accuracy: float (0-1)
            - final_loss: float
            - initial_loss: float (optional, for loss decrease check)

    Returns:
        Tuple of (passed: bool, reason: str)
    """
    accuracy = metrics.get("accuracy")
    final_loss = metrics.get("final_loss")
    initial_loss = metrics.get("initial_loss")

    # Check accuracy threshold
    if accuracy is not None and accuracy < 0.45:
        return False, f"accuracy_below_threshold ({accuracy:.2%} < 45%)"

    # Check loss threshold
    if final_loss is not None and final_loss > 0.8:
        return False, f"loss_too_high ({final_loss:.3f} > 0.8)"

    # Check loss decrease (if initial_loss available)
    if initial_loss is not None and final_loss is not None:
        if initial_loss > 0:
            decrease_pct = (initial_loss - final_loss) / initial_loss
            if decrease_pct < 0.2:
                return False, f"insufficient_loss_decrease ({decrease_pct:.1%} < 20%)"

    return True, "passed"


def check_backtest_gate(metrics: dict[str, Any]) -> tuple[bool, str]:
    """Check if backtest results pass the quality gate.

    Args:
        metrics: Backtest result metrics dict. Expected keys:
            - win_rate: float (0-1)
            - max_drawdown: float (0-1, as percentage)
            - sharpe_ratio: float

    Returns:
        Tuple of (passed: bool, reason: str)
    """
    win_rate = metrics.get("win_rate")
    max_drawdown = metrics.get("max_drawdown")
    sharpe = metrics.get("sharpe_ratio")

    # Check win rate
    if win_rate is not None and win_rate < 0.45:
        return False, f"win_rate_too_low ({win_rate:.1%} < 45%)"

    # Check max drawdown
    if max_drawdown is not None and max_drawdown > 0.4:
        return False, f"drawdown_too_high ({max_drawdown:.1%} > 40%)"

    # Check Sharpe ratio
    if sharpe is not None and sharpe < -0.5:
        return False, f"sharpe_too_low ({sharpe:.2f} < -0.5)"

    return True, "passed"
```

**Test file**: `tests/unit/agents/test_gates.py`

```python
import pytest
from ktrdr.agents.gates import check_training_gate, check_backtest_gate


class TestTrainingGate:
    """Tests for training quality gate."""

    def test_passes_good_metrics(self):
        """Should pass with good metrics."""
        metrics = {
            "accuracy": 0.65,
            "final_loss": 0.3,
            "initial_loss": 0.9,
        }
        passed, reason = check_training_gate(metrics)
        assert passed is True
        assert reason == "passed"

    def test_fails_low_accuracy(self):
        """Should fail if accuracy below 45%."""
        metrics = {"accuracy": 0.40, "final_loss": 0.3}
        passed, reason = check_training_gate(metrics)
        assert passed is False
        assert "accuracy" in reason

    def test_fails_high_loss(self):
        """Should fail if loss above 0.8."""
        metrics = {"accuracy": 0.60, "final_loss": 0.85}
        passed, reason = check_training_gate(metrics)
        assert passed is False
        assert "loss_too_high" in reason

    def test_fails_insufficient_decrease(self):
        """Should fail if loss didn't decrease enough."""
        metrics = {
            "accuracy": 0.60,
            "initial_loss": 0.5,
            "final_loss": 0.45,  # Only 10% decrease
        }
        passed, reason = check_training_gate(metrics)
        assert passed is False
        assert "insufficient_loss_decrease" in reason

    def test_handles_missing_metrics(self):
        """Should pass if metrics are missing (can't check)."""
        metrics = {}
        passed, reason = check_training_gate(metrics)
        assert passed is True


class TestBacktestGate:
    """Tests for backtest quality gate."""

    def test_passes_good_metrics(self):
        """Should pass with good metrics."""
        metrics = {
            "win_rate": 0.55,
            "max_drawdown": 0.15,
            "sharpe_ratio": 0.8,
        }
        passed, reason = check_backtest_gate(metrics)
        assert passed is True

    def test_fails_low_win_rate(self):
        """Should fail if win rate below 45%."""
        metrics = {"win_rate": 0.40}
        passed, reason = check_backtest_gate(metrics)
        assert passed is False
        assert "win_rate" in reason

    def test_fails_high_drawdown(self):
        """Should fail if drawdown above 40%."""
        metrics = {"win_rate": 0.55, "max_drawdown": 0.45}
        passed, reason = check_backtest_gate(metrics)
        assert passed is False
        assert "drawdown" in reason

    def test_fails_negative_sharpe(self):
        """Should fail if Sharpe below -0.5."""
        metrics = {"win_rate": 0.55, "sharpe_ratio": -0.8}
        passed, reason = check_backtest_gate(metrics)
        assert passed is False
        assert "sharpe" in reason
```

---

## Task 2.4: Wire training gate into AgentService

**File**: `ktrdr/api/services/agent_service.py`

Add gate check method:

```python
def _check_training_gate(self, train_result: dict[str, Any]) -> tuple[bool, str]:
    """Check if training results pass the quality gate.

    Args:
        train_result: Training result dict from _run_training_phase

    Returns:
        Tuple of (passed: bool, reason: str)
    """
    from ktrdr.agents.gates import check_training_gate

    # Extract metrics for gate check
    metrics = {
        "accuracy": train_result.get("accuracy"),
        "final_loss": train_result.get("final_loss"),
    }

    # Also check nested metrics if present
    result_metrics = train_result.get("metrics", {})
    if result_metrics:
        metrics["accuracy"] = metrics.get("accuracy") or result_metrics.get("accuracy")
        metrics["final_loss"] = metrics.get("final_loss") or result_metrics.get("final_loss")
        metrics["initial_loss"] = result_metrics.get("initial_loss")

    return check_training_gate(metrics)
```

---

## Phase 2 Verification

### Integration Test Sequence (MANDATORY)

**Focus**: Verify real training API integration works and gate logic is correct.

```bash
# 1. Start services (including training workers)
docker compose up -d
docker compose ps  # Verify all healthy
# Also start GPU host service if available:
# cd training-host-service && ./start.sh
```

```bash
# 2. Trigger full cycle and monitor
ktrdr agent trigger
watch -n 5 "ktrdr agent status"
# ✅ Expected: Phase progresses: designing → training → (stubs)
# ✅ Expected: Training takes real time (varies by GPU/CPU, typically 2-15 min)
# ✅ Expected: Progress updates show epoch/loss info
```

```bash
# 3. Verify training actually ran (check model output)
# After training completes:
ls models/<strategy_name>/
# ✅ Expected: model.pt file exists
# ✅ Expected: metadata.json with training metrics
```

```bash
# 4. Test training gate PASS scenario
# View operation result:
ktrdr operations status <op_id>
# ✅ Expected: training_result shows accuracy >= 45%, loss <= 0.8
# ✅ Expected: Phase continued to "backtesting"
```

```bash
# 5. Test training gate FAIL scenario
# Option A: Train on random/poor data
# Option B: Temporarily lower gate thresholds and use stub training
# ✅ Expected: Cycle FAILED with "Training gate failed: <reason>"
# ✅ Expected: No orphaned operations
```

```bash
# 6. Test cancellation during real training
ktrdr agent trigger
# Wait for "training" phase
ktrdr agent status  # Verify phase is "training"
ktrdr agent cancel <op_id>
# ✅ Expected: Training operation cancelled on remote worker
# ✅ Expected: Agent status shows "idle"
# ✅ Expected: No orphaned remote training operation
```

```bash
# 7. Check logs
docker compose logs backend --since 15m | grep -i error
# ✅ Expected: No unexpected errors
```

### State Consistency Checks

- [ ] After training, model files exist at expected path
- [ ] Training metrics stored in operation metadata
- [ ] Gate failure produces clear error message
- [ ] Cancelled training cleans up remote operation
- [ ] Full cycle still works (design → train → stub backtest → stub assess)

### Acceptance Criteria

**Unit tests**:

- [ ] All unit tests pass (`make test-unit`)
- [ ] Strategy loader tests pass
- [ ] Gate logic tests pass

**Integration tests**:

- [ ] Real training starts after design completes
- [ ] Training progress updates visible in status
- [ ] Model files created at correct path
- [ ] Training metrics captured (accuracy, loss)
- [ ] Gate PASS allows cycle to continue
- [ ] Gate FAIL marks cycle FAILED with reason
- [ ] Cancellation during training works cleanly
- [ ] Backtest/assessment phases still use stubs
- [ ] No errors in logs
- [ ] State consistent throughout

**If ANY checkbox is unchecked**: Fix before proceeding to Phase 3.

---

## Files Created/Modified Summary

| File | Action |
|------|--------|
| `ktrdr/agents/strategy_loader.py` | Create new |
| `ktrdr/agents/gates.py` | Create new |
| `ktrdr/api/services/agent_service.py` | Modify - add training phase |
| `tests/unit/agents/test_strategy_loader.py` | Create new |
| `tests/unit/agents/test_gates.py` | Create new |
