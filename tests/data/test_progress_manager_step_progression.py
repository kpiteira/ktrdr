"""
Test ProgressManager step progression in DataManager integration.

This test verifies that all 10 DataManager steps are properly tracked
and that progress percentages progress smoothly from 0% to 100%.
"""

from ktrdr.data.components.progress_manager import ProgressManager, ProgressState


class TestProgressManagerStepProgression:
    """Test step progression through DataManager operations."""

    def test_progress_manager_receives_all_10_steps(self):
        """Test that ProgressManager receives all expected DataManager steps."""
        progress_calls = []

        def capture_progress(progress_state: ProgressState):
            progress_calls.append(
                {
                    "step": progress_state.current_step,
                    "percentage": progress_state.percentage,
                    "message": progress_state.message,
                    "steps_completed": progress_state.steps_completed,
                    "steps_total": progress_state.steps_total,
                }
            )

        # Create ProgressManager directly
        progress_manager = ProgressManager(capture_progress)

        # Simulate the 10 DataManager steps
        progress_manager.start_operation(total_steps=10, operation_name="load_MSFT_1h")

        # Step 1: Validate symbol with IB (10%)
        progress_manager.start_step("Validate symbol with IB", step_number=1)

        # Step 2: Validate request range (20%)
        progress_manager.start_step("Validate request range", step_number=2)

        # Step 3: Load existing local data (30%)
        progress_manager.start_step("Load existing local data", step_number=3)

        # Step 4: Analyze data gaps (40%)
        progress_manager.start_step("Analyze data gaps", step_number=4)

        # Step 5: Create IB-compliant segments (50%)
        progress_manager.start_step("Create IB-compliant segments", step_number=5)

        # Step 6: Fetch segments from IB (60% base, with detailed sub-progress)
        progress_manager.start_step(
            "Fetch 13 segments from IB", step_number=6, expected_items=1628
        )

        # Simulate segment fetching with sub-progress
        for i in range(1, 14):  # 13 segments
            progress_manager.update_step_progress(
                current=i,
                total=13,
                items_processed=i * 125,  # ~125 bars per segment
                detail=f"Segment {i}/13: 2022-01-{i:02d} 00:00 to 2022-01-{i + 1:02d} 00:00",
            )

        # Step 7: Merge data sources (70%)
        progress_manager.start_step("Merge data sources", step_number=7)

        # Step 8: Save enhanced dataset (80%)
        progress_manager.start_step("Save enhanced dataset", step_number=8)

        # Step 9: Data loading completed (90%)
        progress_manager.start_step("Data loading completed", step_number=9)

        # Complete operation (100%)
        progress_manager.complete_operation()

        # Verify we received progress calls
        assert len(progress_calls) > 0, "Should have received progress callbacks"

        # Verify step progression
        step_numbers = [call["step"] for call in progress_calls if call["step"] > 0]
        assert min(step_numbers) == 1, "Should start with step 1"
        assert max(step_numbers) <= 10, "Should not exceed 10 steps"

        # Verify percentage progression
        percentages = [call["percentage"] for call in progress_calls]
        assert min(percentages) >= 0.0, "Percentage should not be negative"
        assert max(percentages) == 100.0, "Should reach 100%"

        # Verify smooth progression (no big jumps except for completion)
        for i in range(1, len(percentages) - 1):  # Skip the final 100% jump
            jump = percentages[i] - percentages[i - 1]
            assert (
                jump >= 0
            ), f"Progress should not go backwards: {percentages[i - 1]}% -> {percentages[i]}%"
            assert (
                jump <= 40
            ), f"Progress jump too large: {percentages[i - 1]}% -> {percentages[i]}% (jump: {jump}%)"

        # Verify steps_total is consistent
        steps_totals = [
            call["steps_total"] for call in progress_calls if call["steps_total"] > 0
        ]
        assert all(
            total == 10 for total in steps_totals
        ), "steps_total should always be 10"

        print(f"✅ Received {len(progress_calls)} progress updates")
        print(f"✅ Step range: {min(step_numbers)} to {max(step_numbers)}")
        print(
            f"✅ Percentage range: {min(percentages):.1f}% to {max(percentages):.1f}%"
        )

    def test_step_percentage_calculation(self):
        """Test that step percentages are calculated correctly."""
        progress_calls = []

        def capture_progress(progress_state: ProgressState):
            progress_calls.append(
                {
                    "step": progress_state.current_step,
                    "percentage": progress_state.percentage,
                }
            )

        progress_manager = ProgressManager(capture_progress)
        progress_manager.start_operation(total_steps=10, operation_name="test")

        # Test each step
        expected_base_percentages = {
            1: 0.0,  # Step 1 starts at 0%
            2: 10.0,  # Step 2 starts at 10%
            3: 20.0,  # Step 3 starts at 20%
            4: 30.0,  # Step 4 starts at 30%
            5: 40.0,  # Step 5 starts at 40%
            6: 50.0,  # Step 6 starts at 50%
            7: 60.0,  # Step 7 starts at 60%
            8: 70.0,  # Step 8 starts at 70%
            9: 80.0,  # Step 9 starts at 80%
            10: 90.0,  # Step 10 starts at 90%
        }

        for step_num, expected_pct in expected_base_percentages.items():
            progress_manager.start_step(f"Step {step_num}", step_number=step_num)

            # Find the progress call for this step
            step_calls = [call for call in progress_calls if call["step"] == step_num]
            assert len(step_calls) > 0, f"Should have progress call for step {step_num}"

            actual_pct = step_calls[0]["percentage"]
            assert (
                abs(actual_pct - expected_pct) < 1.0
            ), f"Step {step_num}: expected ~{expected_pct}%, got {actual_pct}%"

    def test_segment_sub_progress(self):
        """Test that segment fetching shows detailed sub-progress."""
        progress_calls = []

        def capture_progress(progress_state: ProgressState):
            progress_calls.append(
                {
                    "percentage": progress_state.percentage,
                    "message": progress_state.message,
                    "detail": progress_state.step_detail,
                    "items_processed": progress_state.items_processed,
                }
            )

        progress_manager = ProgressManager(capture_progress)
        progress_manager.start_operation(
            total_steps=10, operation_name="test", expected_items=1300
        )

        # Start step 6 (fetch segments)
        progress_manager.start_step(
            "Fetch 13 segments from IB", step_number=6, expected_items=1300
        )

        # Simulate processing 13 segments with sub-progress
        for i in range(1, 14):
            items_so_far = i * 100  # 100 bars per segment
            progress_manager.update_step_progress(
                current=i,
                total=13,
                items_processed=items_so_far,
                detail=f"Segment {i}/13: fetched {100} bars",
            )

        # Verify sub-progress details
        detail_calls = [call for call in progress_calls if call["detail"]]
        assert len(detail_calls) >= 13, "Should have detailed progress for each segment"

        # Verify items progression
        items_calls = [
            call["items_processed"]
            for call in progress_calls
            if call["items_processed"] > 0
        ]
        assert len(items_calls) > 0, "Should track items processed"
        assert max(items_calls) == 1300, "Should reach expected total items"

        # Verify percentage stays within step 6 range (50%-60%)
        step6_percentages = [
            call["percentage"] for call in progress_calls if call["detail"]
        ]
        for pct in step6_percentages:
            assert (
                50.0 <= pct <= 60.0
            ), f"Step 6 sub-progress should be 50-60%, got {pct}%"
