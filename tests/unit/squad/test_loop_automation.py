"""Tests for M4 loop automation — cadence, synthesis, stall detection."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Ensure .squad/ is on sys.path
_squad_dir = str(Path(__file__).resolve().parents[3] / ".squad")
if _squad_dir not in sys.path:
    sys.path.insert(0, _squad_dir)


# ---------------------------------------------------------------------------
# Task 4.1: Cadence Management
# ---------------------------------------------------------------------------


class TestCadenceReader:
    """Reading cadence from file."""

    def test_reads_full_squad(self, tmp_path: Path):
        from squad_engine.cadence import read_cadence

        cadence_file = tmp_path / "loop" / "cadence.md"
        cadence_file.parent.mkdir(parents=True)
        cadence_file.write_text("cadence: full_squad\n")
        assert read_cadence(tmp_path) == "full_squad"

    def test_reads_quick_iteration(self, tmp_path: Path):
        from squad_engine.cadence import read_cadence

        cadence_file = tmp_path / "loop" / "cadence.md"
        cadence_file.parent.mkdir(parents=True)
        cadence_file.write_text("cadence: quick_iteration\n")
        assert read_cadence(tmp_path) == "quick_iteration"

    def test_reads_synthesis(self, tmp_path: Path):
        from squad_engine.cadence import read_cadence

        cadence_file = tmp_path / "loop" / "cadence.md"
        cadence_file.parent.mkdir(parents=True)
        cadence_file.write_text("cadence: synthesis\n")
        assert read_cadence(tmp_path) == "synthesis"

    def test_reads_pause(self, tmp_path: Path):
        from squad_engine.cadence import read_cadence

        cadence_file = tmp_path / "loop" / "cadence.md"
        cadence_file.parent.mkdir(parents=True)
        cadence_file.write_text("cadence: pause\n")
        assert read_cadence(tmp_path) == "pause"

    def test_missing_file_defaults_to_full_squad(self, tmp_path: Path):
        from squad_engine.cadence import read_cadence

        assert read_cadence(tmp_path) == "full_squad"

    def test_empty_file_defaults_to_full_squad(self, tmp_path: Path):
        from squad_engine.cadence import read_cadence

        cadence_file = tmp_path / "loop" / "cadence.md"
        cadence_file.parent.mkdir(parents=True)
        cadence_file.write_text("")
        assert read_cadence(tmp_path) == "full_squad"

    def test_writes_cadence(self, tmp_path: Path):
        from squad_engine.cadence import read_cadence, write_cadence

        (tmp_path / "loop").mkdir(parents=True)
        write_cadence(tmp_path, "quick_iteration")
        assert read_cadence(tmp_path) == "quick_iteration"


class TestIterationCounter:
    """Reading/writing iteration counter."""

    def test_reads_counter(self, tmp_path: Path):
        from squad_engine.cadence import read_iteration_count, write_iteration_count

        (tmp_path / "loop").mkdir(parents=True)
        write_iteration_count(tmp_path, 7)
        assert read_iteration_count(tmp_path) == 7

    def test_missing_counter_returns_zero(self, tmp_path: Path):
        from squad_engine.cadence import read_iteration_count

        assert read_iteration_count(tmp_path) == 0

    def test_counter_increments(self, tmp_path: Path):
        from squad_engine.cadence import (
            read_iteration_count,
            write_iteration_count,
        )

        (tmp_path / "loop").mkdir(parents=True)
        write_iteration_count(tmp_path, 3)
        assert read_iteration_count(tmp_path) == 3
        write_iteration_count(tmp_path, 4)
        assert read_iteration_count(tmp_path) == 4


class TestLoopResultDataclass:
    """LoopResult structure."""

    def test_loop_result_defaults(self):
        from squad_engine.loop_runner import LoopResult

        result = LoopResult()
        assert result.iterations_run == 0
        assert result.experiments_completed == 0
        assert result.stall_detected is False
        assert result.final_cadence == "full_squad"
        assert result.total_cost_usd == 0.0
        assert result.status == "completed"


class TestRunLoop:
    """Outer loop cadence behavior."""

    @pytest.mark.asyncio
    async def test_pause_exits_immediately(self, tmp_path: Path):
        """Pause cadence should exit loop with status=paused."""
        from squad_engine.loop_runner import LoopResult, run_loop

        shared_dir = tmp_path / "shared"
        (shared_dir / "loop").mkdir(parents=True)
        (shared_dir / "loop" / "cadence.md").write_text("cadence: pause\n")

        result = await run_loop(
            shared_dir=str(shared_dir),
            charter_dir=str(tmp_path / "charters"),
            max_iterations=10,
        )

        assert isinstance(result, LoopResult)
        assert result.status == "paused"
        assert result.iterations_run == 0

    @pytest.mark.asyncio
    async def test_max_iterations_exits(self, tmp_path: Path):
        """Loop should exit after max_iterations."""
        from squad_engine.loop import CycleResult
        from squad_engine.loop_runner import run_loop

        shared_dir = tmp_path / "shared"
        self._setup_shared_dir(shared_dir)

        mock_cycle_result = CycleResult(
            iteration=1,
            status="COMPLETE",
            total_cost_usd=0.10,
            cadence_next="full_squad",
            experiment_result={"status": "success"},
        )

        with patch(
            "squad_engine.loop_runner.run_cycle",
            new_callable=AsyncMock,
            return_value=mock_cycle_result,
        ):
            result = await run_loop(
                shared_dir=str(shared_dir),
                charter_dir=str(tmp_path / "charters"),
                max_iterations=3,
            )

        assert result.status == "max_iterations"
        assert result.iterations_run == 3

    @pytest.mark.asyncio
    async def test_synthesis_mode_triggers_synthesis(self, tmp_path: Path):
        """Synthesis cadence runs synthesis cycle instead of research."""
        from squad_engine.loop import CycleResult
        from squad_engine.loop_runner import run_loop

        shared_dir = tmp_path / "shared"
        self._setup_shared_dir(shared_dir)
        (shared_dir / "loop" / "cadence.md").write_text("cadence: synthesis\n")

        mock_cycle = CycleResult(
            iteration=1, status="COMPLETE", cadence_next="full_squad"
        )

        with patch(
            "squad_engine.loop_runner.run_synthesis_cycle",
            new_callable=AsyncMock,
            return_value=mock_cycle,
        ) as mock_synth, patch(
            "squad_engine.loop_runner.run_cycle",
            new_callable=AsyncMock,
            return_value=mock_cycle,
        ) as mock_research:
            await run_loop(
                shared_dir=str(shared_dir),
                charter_dir=str(tmp_path / "charters"),
                max_iterations=1,
            )

        # Synthesis was called, not research
        mock_synth.assert_awaited_once()
        mock_research.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_iteration_counter_persists(self, tmp_path: Path):
        """Iteration counter should increment and persist to file."""
        from squad_engine.cadence import read_iteration_count
        from squad_engine.loop import CycleResult
        from squad_engine.loop_runner import run_loop

        shared_dir = tmp_path / "shared"
        self._setup_shared_dir(shared_dir)

        mock_cycle = CycleResult(
            iteration=1, status="COMPLETE", cadence_next="full_squad",
            experiment_result={"status": "success"},
        )

        with patch(
            "squad_engine.loop_runner.run_cycle",
            new_callable=AsyncMock,
            return_value=mock_cycle,
        ):
            await run_loop(
                shared_dir=str(shared_dir),
                charter_dir=str(tmp_path / "charters"),
                max_iterations=3,
            )

        assert read_iteration_count(shared_dir) == 3

    @pytest.mark.asyncio
    async def test_cadence_from_cycle_result_updates_file(self, tmp_path: Path):
        """Cadence from CycleResult should be written for next iteration."""
        from squad_engine.loop import CycleResult
        from squad_engine.loop_runner import run_loop

        shared_dir = tmp_path / "shared"
        self._setup_shared_dir(shared_dir)

        # Cycle returns quick_iteration, then pause on second cycle
        call_count = 0

        async def mock_run_cycle(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return CycleResult(
                    iteration=1, status="COMPLETE", cadence_next="quick_iteration"
                )
            return CycleResult(
                iteration=2, status="COMPLETE", cadence_next="pause"
            )

        with patch(
            "squad_engine.loop_runner.run_cycle",
            side_effect=mock_run_cycle,
        ):
            result = await run_loop(
                shared_dir=str(shared_dir),
                charter_dir=str(tmp_path / "charters"),
                max_iterations=10,
            )

        # Should have stopped after reading pause
        assert result.status == "paused"
        assert result.iterations_run == 2

    @pytest.mark.asyncio
    async def test_cost_accumulates_across_cycles(self, tmp_path: Path):
        """Total cost should sum across all cycles."""
        from squad_engine.loop import CycleResult
        from squad_engine.loop_runner import run_loop

        shared_dir = tmp_path / "shared"
        self._setup_shared_dir(shared_dir)

        mock_cycle = CycleResult(
            iteration=1, status="COMPLETE", total_cost_usd=1.50, cadence_next="full_squad"
        )

        with patch(
            "squad_engine.loop_runner.run_cycle",
            new_callable=AsyncMock,
            return_value=mock_cycle,
        ):
            result = await run_loop(
                shared_dir=str(shared_dir),
                charter_dir=str(tmp_path / "charters"),
                max_iterations=3,
            )

        assert result.total_cost_usd == pytest.approx(4.50)

    def _setup_shared_dir(self, shared_dir: Path):
        """Create minimal shared directory structure."""
        (shared_dir / "loop").mkdir(parents=True)
        (shared_dir / "loop" / "cadence.md").write_text("cadence: full_squad\n")
        (shared_dir / "knowledge").mkdir(parents=True)


# ---------------------------------------------------------------------------
# Task 4.2: Synthesis Triggering
# ---------------------------------------------------------------------------


class TestSynthesisTrigger:
    """Synthesis trigger logic — three paths."""

    def test_director_cadence_triggers_synthesis(self):
        """Direct cadence=synthesis from Director."""
        from squad_engine.synthesis import should_trigger_synthesis

        assert should_trigger_synthesis(
            cadence="synthesis",
            context_tokens=50_000,
            iteration=3,
            synthesis_interval=10,
        )

    def test_emergency_context_budget_triggers(self):
        """Context > 80% of 200K budget → emergency synthesis."""
        from squad_engine.synthesis import should_trigger_synthesis

        # 170K tokens > 80% of 200K = 160K threshold
        assert should_trigger_synthesis(
            cadence="full_squad",
            context_tokens=170_000,
            iteration=3,
            synthesis_interval=10,
        )

    def test_below_budget_no_emergency(self):
        """Context below threshold → no emergency synthesis."""
        from squad_engine.synthesis import should_trigger_synthesis

        assert not should_trigger_synthesis(
            cadence="full_squad",
            context_tokens=100_000,
            iteration=3,
            synthesis_interval=10,
        )

    def test_periodic_interval_triggers(self):
        """Every N cycles → periodic synthesis."""
        from squad_engine.synthesis import should_trigger_synthesis

        # iteration 10, interval 10 → trigger
        assert should_trigger_synthesis(
            cadence="full_squad",
            context_tokens=50_000,
            iteration=10,
            synthesis_interval=10,
        )

    def test_periodic_non_interval_no_trigger(self):
        """Non-interval cycle → no periodic trigger."""
        from squad_engine.synthesis import should_trigger_synthesis

        assert not should_trigger_synthesis(
            cadence="full_squad",
            context_tokens=50_000,
            iteration=7,
            synthesis_interval=10,
        )

    def test_pause_cadence_no_synthesis(self):
        """Pause should not trigger synthesis."""
        from squad_engine.synthesis import should_trigger_synthesis

        assert not should_trigger_synthesis(
            cadence="pause",
            context_tokens=50_000,
            iteration=10,
            synthesis_interval=10,
        )


class TestSynthesisCycle:
    """Synthesis cycle execution."""

    @pytest.mark.asyncio
    async def test_synthesis_spawns_scribe_only(self, tmp_path: Path):
        """Synthesis cycle should use Scribe, not Engineer or consultants."""
        from squad_engine.synthesis import run_synthesis_cycle

        shared_dir = tmp_path / "shared"
        (shared_dir / "knowledge").mkdir(parents=True)
        (shared_dir / "knowledge" / "experiments.md").write_text(
            "## Cycle 1\nGRU experiment\n## Cycle 2\nLSTM experiment\n"
        )
        (shared_dir / "knowledge" / "synthesis.md").write_text("")

        # Mock the scribe session
        mock_scribe_result = AsyncMock()
        mock_scribe_result.output = "Updated synthesis"
        mock_scribe_result.cost_usd = 0.30

        with patch(
            "squad_engine.synthesis._run_scribe_session",
            new_callable=AsyncMock,
            return_value=("Updated synthesis of patterns...", 0.50),
        ) as mock_scribe:
            result = await run_synthesis_cycle(
                iteration=5,
                shared_dir=str(shared_dir),
                charter_dir=str(tmp_path / "charters"),
            )

        mock_scribe.assert_awaited_once()
        assert result.status == "COMPLETE"

    @pytest.mark.asyncio
    async def test_cadence_resets_after_synthesis(self, tmp_path: Path):
        """After synthesis, cadence should reset (not stay in synthesis loop)."""
        from squad_engine.synthesis import run_synthesis_cycle

        shared_dir = tmp_path / "shared"
        (shared_dir / "knowledge").mkdir(parents=True)
        (shared_dir / "knowledge" / "experiments.md").write_text("## Cycle 1\nTest\n")
        (shared_dir / "knowledge" / "synthesis.md").write_text("")

        with patch(
            "squad_engine.synthesis._run_scribe_session",
            new_callable=AsyncMock,
            return_value=("Synthesis output", 0.50),
        ):
            result = await run_synthesis_cycle(
                iteration=5,
                shared_dir=str(shared_dir),
                charter_dir=str(tmp_path / "charters"),
            )

        # Cadence should NOT be synthesis (prevents loop)
        assert result.cadence_next != "synthesis"

    @pytest.mark.asyncio
    async def test_synthesis_updates_file(self, tmp_path: Path):
        """synthesis.md should be updated after cycle."""
        from squad_engine.synthesis import run_synthesis_cycle

        shared_dir = tmp_path / "shared"
        (shared_dir / "knowledge").mkdir(parents=True)
        (shared_dir / "knowledge" / "experiments.md").write_text("## Cycle 1\nData\n")
        (shared_dir / "knowledge" / "synthesis.md").write_text("Old synthesis")

        with patch(
            "squad_engine.synthesis._run_scribe_session",
            new_callable=AsyncMock,
            return_value=("New synthesis with patterns", 0.50),
        ):
            await run_synthesis_cycle(
                iteration=5,
                shared_dir=str(shared_dir),
                charter_dir=str(tmp_path / "charters"),
            )

        updated = (shared_dir / "knowledge" / "synthesis.md").read_text()
        assert "New synthesis with patterns" in updated


class TestLoopWithSynthesis:
    """Integration of synthesis triggering in run_loop."""

    @pytest.mark.asyncio
    async def test_emergency_synthesis_mid_loop(self, tmp_path: Path):
        """Emergency synthesis should fire when context budget exceeded."""
        from squad_engine.loop import CycleResult
        from squad_engine.loop_runner import run_loop

        shared_dir = tmp_path / "shared"
        (shared_dir / "loop").mkdir(parents=True)
        (shared_dir / "loop" / "cadence.md").write_text("cadence: full_squad\n")
        (shared_dir / "knowledge").mkdir(parents=True)
        # Large experiments file to trigger emergency synthesis
        (shared_dir / "knowledge" / "experiments.md").write_text("x" * 700_000)

        mock_cycle = CycleResult(
            iteration=1, status="COMPLETE", cadence_next="full_squad"
        )

        synth_called = False

        async def mock_synthesis(**kwargs):
            nonlocal synth_called
            synth_called = True
            return CycleResult(
                iteration=kwargs.get("iteration", 1),
                status="COMPLETE",
                cadence_next="full_squad",
            )

        with patch(
            "squad_engine.loop_runner.run_cycle",
            new_callable=AsyncMock,
            return_value=mock_cycle,
        ), patch(
            "squad_engine.loop_runner.run_synthesis_cycle",
            side_effect=mock_synthesis,
        ):
            await run_loop(
                shared_dir=str(shared_dir),
                charter_dir=str(tmp_path / "charters"),
                max_iterations=1,
            )

        assert synth_called

    @pytest.mark.asyncio
    async def test_periodic_synthesis_at_interval(self, tmp_path: Path):
        """Periodic synthesis should trigger at configured interval."""
        from squad_engine.loop import CycleResult
        from squad_engine.loop_runner import run_loop

        shared_dir = tmp_path / "shared"
        (shared_dir / "loop").mkdir(parents=True)
        (shared_dir / "loop" / "cadence.md").write_text("cadence: full_squad\n")
        (shared_dir / "knowledge").mkdir(parents=True)
        (shared_dir / "knowledge" / "experiments.md").write_text("")

        call_log: list[str] = []

        async def mock_research(**kwargs):
            call_log.append("research")
            return CycleResult(
                iteration=kwargs.get("iteration", 1),
                status="COMPLETE",
                cadence_next="full_squad",
            )

        async def mock_synthesis(**kwargs):
            call_log.append("synthesis")
            return CycleResult(
                iteration=kwargs.get("iteration", 1),
                status="COMPLETE",
                cadence_next="full_squad",
            )

        with patch(
            "squad_engine.loop_runner.run_cycle",
            side_effect=mock_research,
        ), patch(
            "squad_engine.loop_runner.run_synthesis_cycle",
            side_effect=mock_synthesis,
        ):
            await run_loop(
                shared_dir=str(shared_dir),
                charter_dir=str(tmp_path / "charters"),
                max_iterations=5,
                synthesis_interval=3,
            )

        # iteration 3 should have been synthesis
        assert call_log[2] == "synthesis"
        # iterations 1, 2, 4, 5 should be research
        assert call_log[0] == "research"
        assert call_log[1] == "research"


# ---------------------------------------------------------------------------
# Task 4.3: Stall Detection + De-duplication
# ---------------------------------------------------------------------------


class TestStallDetection:
    """Detect non-productive cycles and stop the loop."""

    def test_no_experiment_is_non_productive(self):
        from squad_engine.loop import CycleResult
        from squad_engine.stall import is_productive_cycle

        cycle = CycleResult(iteration=1, status="COMPLETE", experiment_result=None)
        assert not is_productive_cycle(cycle)

    def test_failed_cycle_is_non_productive(self):
        from squad_engine.loop import CycleResult
        from squad_engine.stall import is_productive_cycle

        cycle = CycleResult(iteration=1, status="FAILED")
        assert not is_productive_cycle(cycle)

    def test_experiment_completed_is_productive(self):
        from squad_engine.loop import CycleResult
        from squad_engine.stall import is_productive_cycle

        cycle = CycleResult(
            iteration=1,
            status="COMPLETE",
            experiment_result={"status": "success"},
        )
        assert is_productive_cycle(cycle)

    def test_three_non_productive_triggers_stall(self):
        from squad_engine.stall import StallDetector

        detector = StallDetector(max_non_productive=3)
        # Three non-productive cycles
        assert not detector.check_stall(productive=False)
        assert not detector.check_stall(productive=False)
        assert detector.check_stall(productive=False)

    def test_productive_cycle_resets_counter(self):
        from squad_engine.stall import StallDetector

        detector = StallDetector(max_non_productive=3)
        detector.check_stall(productive=False)
        detector.check_stall(productive=False)
        # Productive cycle resets
        detector.check_stall(productive=True)
        assert not detector.check_stall(productive=False)
        assert not detector.check_stall(productive=False)

    def test_stall_writes_fatal_error(self, tmp_path: Path):
        from squad_engine.stall import write_fatal_error

        write_fatal_error(tmp_path, "3 consecutive non-productive cycles")
        fatal = (tmp_path / "loop" / "fatal-error.md").read_text()
        assert "3 consecutive non-productive cycles" in fatal


class TestDeduplication:
    """Advisory de-duplication warnings for repeated experiments."""

    def test_exact_name_match_warns(self):
        from squad_engine.stall import check_deduplication

        experiments = "## Cycle 1\nStrategy: gru_eurusd_5m\n## Cycle 2\nStrategy: lstm_eurusd_1h\n"
        warning = check_deduplication("gru_eurusd_5m", experiments)
        assert warning is not None
        assert "gru_eurusd_5m" in warning

    def test_no_match_no_warning(self):
        from squad_engine.stall import check_deduplication

        experiments = "## Cycle 1\nStrategy: gru_eurusd_5m\n"
        warning = check_deduplication("lstm_new_approach", experiments)
        assert warning is None

    def test_deduplication_is_advisory(self):
        """De-duplication should warn, not block."""
        from squad_engine.stall import check_deduplication

        experiments = "## Cycle 1\nStrategy: gru_eurusd_5m\n"
        # Returns a warning string, not an exception
        warning = check_deduplication("gru_eurusd_5m", experiments)
        assert isinstance(warning, str)


class TestCycleHistory:
    """Cycle history JSON log."""

    def test_write_and_read_history(self, tmp_path: Path):
        from squad_engine.stall import (
            CycleHistoryEntry,
            read_cycle_history,
            write_cycle_history_entry,
        )

        (tmp_path / "loop").mkdir(parents=True)

        entry = CycleHistoryEntry(
            iteration=1,
            status="COMPLETE",
            experiment="gru_eurusd_5m",
            agents_spawned=["engineer", "scribe"],
            cost_usd=2.50,
            timestamp="2026-04-05T10:00:00Z",
        )
        write_cycle_history_entry(tmp_path, entry)

        history = read_cycle_history(tmp_path)
        assert len(history) == 1
        assert history[0]["iteration"] == 1
        assert history[0]["experiment"] == "gru_eurusd_5m"

    def test_append_multiple_entries(self, tmp_path: Path):
        from squad_engine.stall import (
            CycleHistoryEntry,
            read_cycle_history,
            write_cycle_history_entry,
        )

        (tmp_path / "loop").mkdir(parents=True)

        for i in range(3):
            entry = CycleHistoryEntry(
                iteration=i + 1,
                status="COMPLETE",
                experiment=f"strategy_{i}",
                agents_spawned=["engineer"],
                cost_usd=1.0,
                timestamp=f"2026-04-05T1{i}:00:00Z",
            )
            write_cycle_history_entry(tmp_path, entry)

        history = read_cycle_history(tmp_path)
        assert len(history) == 3

    def test_empty_history_returns_empty_list(self, tmp_path: Path):
        from squad_engine.stall import read_cycle_history

        assert read_cycle_history(tmp_path) == []


class TestLoopWithStallDetection:
    """Integration of stall detection in run_loop."""

    @pytest.mark.asyncio
    async def test_stall_stops_loop(self, tmp_path: Path):
        """3 non-productive cycles should stop the loop."""
        from squad_engine.loop import CycleResult
        from squad_engine.loop_runner import run_loop

        shared_dir = tmp_path / "shared"
        (shared_dir / "loop").mkdir(parents=True)
        (shared_dir / "loop" / "cadence.md").write_text("cadence: full_squad\n")
        (shared_dir / "knowledge").mkdir(parents=True)
        (shared_dir / "knowledge" / "experiments.md").write_text("")

        # All cycles non-productive (no experiment result)
        mock_cycle = CycleResult(
            iteration=1, status="COMPLETE", cadence_next="full_squad",
            experiment_result=None,
        )

        with patch(
            "squad_engine.loop_runner.run_cycle",
            new_callable=AsyncMock,
            return_value=mock_cycle,
        ):
            result = await run_loop(
                shared_dir=str(shared_dir),
                charter_dir=str(tmp_path / "charters"),
                max_iterations=10,
            )

        assert result.status == "stalled"
        assert result.stall_detected is True
        assert result.iterations_run == 3
        # fatal-error.md should exist
        assert (shared_dir / "loop" / "fatal-error.md").exists()

    @pytest.mark.asyncio
    async def test_productive_cycle_prevents_stall(self, tmp_path: Path):
        """A productive cycle resets stall counter."""
        from squad_engine.loop import CycleResult
        from squad_engine.loop_runner import run_loop

        shared_dir = tmp_path / "shared"
        (shared_dir / "loop").mkdir(parents=True)
        (shared_dir / "loop" / "cadence.md").write_text("cadence: full_squad\n")
        (shared_dir / "knowledge").mkdir(parents=True)
        (shared_dir / "knowledge" / "experiments.md").write_text("")

        call_count = 0

        async def varying_cycles(**kwargs):
            nonlocal call_count
            call_count += 1
            # Cycles 1,2 non-productive, 3 productive, 4,5 non-productive
            if call_count == 3:
                return CycleResult(
                    iteration=call_count, status="COMPLETE",
                    cadence_next="full_squad",
                    experiment_result={"status": "success"},
                )
            return CycleResult(
                iteration=call_count, status="COMPLETE",
                cadence_next="full_squad", experiment_result=None,
            )

        with patch(
            "squad_engine.loop_runner.run_cycle",
            side_effect=varying_cycles,
        ):
            result = await run_loop(
                shared_dir=str(shared_dir),
                charter_dir=str(tmp_path / "charters"),
                max_iterations=5,
            )

        # Should complete all 5 — productive cycle at 3 reset the counter
        assert result.status == "max_iterations"
        assert result.iterations_run == 5


# ---------------------------------------------------------------------------
# Task 4.4: Full Loop Entry Point + Integration
# ---------------------------------------------------------------------------


class TestCycleHistoryIntegration:
    """Cycle history written during loop."""

    @pytest.mark.asyncio
    async def test_cycle_history_written_per_iteration(self, tmp_path: Path):
        """Each iteration should append to cycle-history.json."""
        from squad_engine.loop import CycleResult
        from squad_engine.loop_runner import run_loop
        from squad_engine.stall import read_cycle_history

        shared_dir = tmp_path / "shared"
        (shared_dir / "loop").mkdir(parents=True)
        (shared_dir / "loop" / "cadence.md").write_text("cadence: full_squad\n")
        (shared_dir / "knowledge").mkdir(parents=True)
        (shared_dir / "knowledge" / "experiments.md").write_text("")

        call_count = 0

        async def mock_cycle(**kwargs):
            nonlocal call_count
            call_count += 1
            return CycleResult(
                iteration=call_count,
                status="COMPLETE",
                cadence_next="full_squad",
                total_cost_usd=1.00,
                agents_spawned=["engineer", "scribe"],
                experiment_result={"status": "success"},
            )

        with patch("squad_engine.loop_runner.run_cycle", side_effect=mock_cycle):
            await run_loop(
                shared_dir=str(shared_dir),
                charter_dir=str(tmp_path / "charters"),
                max_iterations=3,
            )

        history = read_cycle_history(shared_dir)
        assert len(history) == 3
        assert history[0]["iteration"] == 1
        assert history[2]["iteration"] == 3
        assert history[0]["cost_usd"] == 1.00


class TestIntegrationThreeCycles:
    """Integration test: 3 mock cycles with varying cadence."""

    @pytest.mark.asyncio
    async def test_varying_cadence_flow(self, tmp_path: Path):
        """full_squad → quick_iteration → synthesis → verify all handled."""
        from squad_engine.loop import CycleResult
        from squad_engine.loop_runner import run_loop
        from squad_engine.stall import read_cycle_history

        shared_dir = tmp_path / "shared"
        (shared_dir / "loop").mkdir(parents=True)
        (shared_dir / "loop" / "cadence.md").write_text("cadence: full_squad\n")
        (shared_dir / "knowledge").mkdir(parents=True)
        (shared_dir / "knowledge" / "experiments.md").write_text("")

        call_count = 0

        async def mock_research(**kwargs):
            nonlocal call_count
            call_count += 1
            # Cycle 1 returns quick_iteration, cycle 2 returns synthesis
            if call_count == 1:
                return CycleResult(
                    iteration=1, status="COMPLETE",
                    cadence_next="quick_iteration",
                    total_cost_usd=2.00,
                    agents_spawned=["engineer", "scribe"],
                    experiment_result={"status": "success"},
                )
            return CycleResult(
                iteration=2, status="COMPLETE",
                cadence_next="synthesis",
                total_cost_usd=1.50,
                agents_spawned=["engineer"],
                experiment_result={"status": "success"},
            )

        async def mock_synthesis(**kwargs):
            return CycleResult(
                iteration=3, status="COMPLETE",
                cadence_next="full_squad",
                total_cost_usd=0.40,
                agents_spawned=["scribe"],
            )

        with patch(
            "squad_engine.loop_runner.run_cycle", side_effect=mock_research,
        ), patch(
            "squad_engine.loop_runner.run_synthesis_cycle", side_effect=mock_synthesis,
        ):
            result = await run_loop(
                shared_dir=str(shared_dir),
                charter_dir=str(tmp_path / "charters"),
                max_iterations=3,
            )

        assert result.iterations_run == 3
        assert result.total_cost_usd == pytest.approx(3.90)
        assert result.experiments_completed == 2  # cycles 1 and 2

        history = read_cycle_history(shared_dir)
        assert len(history) == 3


class TestSignalHandling:
    """SIGINT/SIGTERM clean shutdown."""

    @pytest.mark.asyncio
    async def test_loop_result_on_keyboard_interrupt(self, tmp_path: Path):
        """KeyboardInterrupt should return partial LoopResult."""
        from squad_engine.loop import CycleResult
        from squad_engine.loop_runner import run_loop

        shared_dir = tmp_path / "shared"
        (shared_dir / "loop").mkdir(parents=True)
        (shared_dir / "loop" / "cadence.md").write_text("cadence: full_squad\n")
        (shared_dir / "knowledge").mkdir(parents=True)
        (shared_dir / "knowledge" / "experiments.md").write_text("")

        call_count = 0

        async def interrupt_on_second(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise KeyboardInterrupt
            return CycleResult(
                iteration=1, status="COMPLETE",
                cadence_next="full_squad",
                total_cost_usd=1.00,
                experiment_result={"status": "success"},
            )

        with patch(
            "squad_engine.loop_runner.run_cycle",
            side_effect=interrupt_on_second,
        ):
            result = await run_loop(
                shared_dir=str(shared_dir),
                charter_dir=str(tmp_path / "charters"),
                max_iterations=5,
            )

        assert result.status == "interrupted"
        assert result.iterations_run == 1  # Only first completed


class TestLoopRunnerModule:
    """CLI entry point via python -m."""

    def test_loop_result_has_all_fields(self):
        """LoopResult should have all expected fields."""
        from squad_engine.loop_runner import LoopResult

        result = LoopResult(
            iterations_run=5,
            experiments_completed=3,
            stall_detected=False,
            final_cadence="full_squad",
            total_cost_usd=12.50,
            status="max_iterations",
        )
        assert result.iterations_run == 5
        assert result.experiments_completed == 3
        assert result.total_cost_usd == 12.50


# ---------------------------------------------------------------------------
# Transcript Logging
# ---------------------------------------------------------------------------


class TestTranscriptLogger:
    """Transcript logging to JSONL files."""

    def test_log_exchange_creates_file(self, tmp_path: Path):
        from squad_engine.transcript import TranscriptLogger

        tl = TranscriptLogger(tmp_path / "transcripts")
        tl.log_exchange(
            role="director",
            query_num=1,
            query="What should we explore?",
            transcript=[
                {"type": "text", "content": "Let's explore RSI strategies."},
                {"type": "tool_use", "tool": "spawn_agent", "input": {"role": "engineer"}},
            ],
            cost_usd=0.50,
            turns=3,
        )

        file = tmp_path / "transcripts" / "director.jsonl"
        assert file.exists()
        lines = file.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["role"] == "director"
        assert entry["query_num"] == 1
        assert entry["turns"] == 3
        assert len(entry["response"]) == 2

    def test_log_tool_call(self, tmp_path: Path):
        from squad_engine.transcript import TranscriptLogger

        tl = TranscriptLogger(tmp_path / "transcripts")
        tl.log_tool_call(
            "spawn_agent",
            {"role": "engineer", "message": "Design a strategy"},
            {"output": "Done", "cost_usd": 0.10},
        )

        file = tmp_path / "transcripts" / "director_tools.jsonl"
        assert file.exists()
        entry = json.loads(file.read_text().strip())
        assert entry["tool"] == "spawn_agent"
        assert entry["type"] == "squad_tool_call"

    def test_multiple_exchanges_append(self, tmp_path: Path):
        from squad_engine.transcript import TranscriptLogger

        tl = TranscriptLogger(tmp_path / "transcripts")
        for i in range(3):
            tl.log_exchange(
                role="engineer",
                query_num=i + 1,
                query=f"Query {i}",
                transcript=[{"type": "text", "content": f"Response {i}"}],
                cost_usd=0.10,
                turns=1,
            )

        file = tmp_path / "transcripts" / "engineer.jsonl"
        lines = file.read_text().strip().split("\n")
        assert len(lines) == 3

    def test_read_transcript(self, tmp_path: Path):
        from squad_engine.transcript import TranscriptLogger, read_transcript

        tl = TranscriptLogger(tmp_path / "transcripts")
        tl.log_exchange(
            role="scribe", query_num=1, query="Record this",
            transcript=[{"type": "text", "content": "Recorded."}],
            cost_usd=0.05, turns=1,
        )

        entries = read_transcript(tmp_path / "transcripts", "scribe")
        assert len(entries) == 1
        assert entries[0]["query"] == "Record this"

    def test_read_empty_transcript(self, tmp_path: Path):
        from squad_engine.transcript import read_transcript

        assert read_transcript(tmp_path / "transcripts", "director") == []

    def test_long_text_truncated_in_summary(self, tmp_path: Path):
        from squad_engine.transcript import TranscriptLogger

        tl = TranscriptLogger(tmp_path / "transcripts")
        long_text = "x" * 1000
        tl.log_exchange(
            role="director", query_num=1, query="test",
            transcript=[{"type": "text", "content": long_text}],
            cost_usd=0.01, turns=1,
        )

        entry = json.loads((tmp_path / "transcripts" / "director.jsonl").read_text().strip())
        # Content should be truncated to 500 + "..."
        assert len(entry["response"][0]["content"]) == 503
        assert entry["response"][0]["length"] == 1000
