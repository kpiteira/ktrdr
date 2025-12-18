"""
Unit tests for agent Prometheus metrics.

Tests cover:
- Metric definitions (counters, histograms)
- Cycle outcome counting
- Phase duration recording
- Gate result tracking
- Token usage counting
- Budget spend tracking
- Helper function behavior
"""


class TestAgentMetricsDefinitions:
    """Tests for agent metrics definitions."""

    def test_cycles_total_counter_exists(self):
        """Test that agent_cycles_total counter is defined with outcome label."""
        from ktrdr.agents.metrics import agent_cycles_total

        # Counter should accept outcome labels
        agent_cycles_total.labels(outcome="completed")
        agent_cycles_total.labels(outcome="failed")
        agent_cycles_total.labels(outcome="cancelled")

    def test_cycle_duration_histogram_exists(self):
        """Test that agent_cycle_duration_seconds histogram is defined."""
        from ktrdr.agents.metrics import agent_cycle_duration_seconds

        # Histogram should be callable
        agent_cycle_duration_seconds.observe(60.0)

    def test_phase_duration_histogram_exists(self):
        """Test that agent_phase_duration_seconds histogram is defined with phase label."""
        from ktrdr.agents.metrics import agent_phase_duration_seconds

        # Histogram should accept phase labels
        agent_phase_duration_seconds.labels(phase="designing")
        agent_phase_duration_seconds.labels(phase="training")
        agent_phase_duration_seconds.labels(phase="backtesting")
        agent_phase_duration_seconds.labels(phase="assessing")

    def test_gate_results_counter_exists(self):
        """Test that agent_gate_results_total counter is defined with gate and result labels."""
        from ktrdr.agents.metrics import agent_gate_results_total

        # Counter should accept gate and result labels
        agent_gate_results_total.labels(gate="training", result="pass")
        agent_gate_results_total.labels(gate="training", result="fail")
        agent_gate_results_total.labels(gate="backtest", result="pass")
        agent_gate_results_total.labels(gate="backtest", result="fail")

    def test_tokens_counter_exists(self):
        """Test that agent_tokens_total counter is defined with phase label."""
        from ktrdr.agents.metrics import agent_tokens_total

        # Counter should accept phase labels
        agent_tokens_total.labels(phase="design")
        agent_tokens_total.labels(phase="assessment")

    def test_budget_spend_counter_exists(self):
        """Test that agent_budget_spend_total counter is defined."""
        from ktrdr.agents.metrics import agent_budget_spend_total

        # Counter should be incrementable
        agent_budget_spend_total.inc(0.15)


class TestAgentMetricsRecording:
    """Tests for recording metrics values."""

    def test_record_cycle_outcome_completed(self):
        """Test recording completed cycle outcome."""
        from ktrdr.agents.metrics import agent_cycles_total, record_cycle_outcome

        initial = agent_cycles_total.labels(outcome="completed")._value.get()
        record_cycle_outcome("completed")
        assert (
            agent_cycles_total.labels(outcome="completed")._value.get() == initial + 1
        )

    def test_record_cycle_outcome_failed(self):
        """Test recording failed cycle outcome."""
        from ktrdr.agents.metrics import agent_cycles_total, record_cycle_outcome

        initial = agent_cycles_total.labels(outcome="failed")._value.get()
        record_cycle_outcome("failed")
        assert agent_cycles_total.labels(outcome="failed")._value.get() == initial + 1

    def test_record_cycle_outcome_cancelled(self):
        """Test recording cancelled cycle outcome."""
        from ktrdr.agents.metrics import agent_cycles_total, record_cycle_outcome

        initial = agent_cycles_total.labels(outcome="cancelled")._value.get()
        record_cycle_outcome("cancelled")
        assert (
            agent_cycles_total.labels(outcome="cancelled")._value.get() == initial + 1
        )

    def test_record_cycle_duration(self):
        """Test recording cycle duration."""
        from ktrdr.agents.metrics import (
            agent_cycle_duration_seconds,
            record_cycle_duration,
        )

        initial_sum = agent_cycle_duration_seconds._sum.get()
        record_cycle_duration(120.5)
        assert agent_cycle_duration_seconds._sum.get() == initial_sum + 120.5

    def test_record_phase_duration_designing(self):
        """Test recording designing phase duration."""
        from ktrdr.agents.metrics import (
            agent_phase_duration_seconds,
            record_phase_duration,
        )

        initial_sum = agent_phase_duration_seconds.labels(phase="designing")._sum.get()
        record_phase_duration("designing", 30.0)
        assert (
            agent_phase_duration_seconds.labels(phase="designing")._sum.get()
            == initial_sum + 30.0
        )

    def test_record_phase_duration_training(self):
        """Test recording training phase duration."""
        from ktrdr.agents.metrics import (
            agent_phase_duration_seconds,
            record_phase_duration,
        )

        initial_sum = agent_phase_duration_seconds.labels(phase="training")._sum.get()
        record_phase_duration("training", 300.0)
        assert (
            agent_phase_duration_seconds.labels(phase="training")._sum.get()
            == initial_sum + 300.0
        )

    def test_record_gate_result_pass(self):
        """Test recording gate pass result."""
        from ktrdr.agents.metrics import agent_gate_results_total, record_gate_result

        initial = agent_gate_results_total.labels(
            gate="training", result="pass"
        )._value.get()
        record_gate_result("training", passed=True)
        assert (
            agent_gate_results_total.labels(gate="training", result="pass")._value.get()
            == initial + 1
        )

    def test_record_gate_result_fail(self):
        """Test recording gate fail result."""
        from ktrdr.agents.metrics import agent_gate_results_total, record_gate_result

        initial = agent_gate_results_total.labels(
            gate="backtest", result="fail"
        )._value.get()
        record_gate_result("backtest", passed=False)
        assert (
            agent_gate_results_total.labels(gate="backtest", result="fail")._value.get()
            == initial + 1
        )

    def test_record_tokens_design(self):
        """Test recording tokens for design phase."""
        from ktrdr.agents.metrics import agent_tokens_total, record_tokens

        initial = agent_tokens_total.labels(phase="design")._value.get()
        record_tokens("design", 5000)
        assert agent_tokens_total.labels(phase="design")._value.get() == initial + 5000

    def test_record_tokens_assessment(self):
        """Test recording tokens for assessment phase."""
        from ktrdr.agents.metrics import agent_tokens_total, record_tokens

        initial = agent_tokens_total.labels(phase="assessment")._value.get()
        record_tokens("assessment", 4500)
        assert (
            agent_tokens_total.labels(phase="assessment")._value.get() == initial + 4500
        )

    def test_record_budget_spend(self):
        """Test recording budget spend."""
        from ktrdr.agents.metrics import agent_budget_spend_total, record_budget_spend

        initial = agent_budget_spend_total._value.get()
        record_budget_spend(0.15)
        assert agent_budget_spend_total._value.get() == initial + 0.15


class TestAgentMetricsBuckets:
    """Tests for histogram bucket configurations."""

    def test_cycle_duration_has_appropriate_buckets(self):
        """Test cycle duration histogram has buckets suitable for research cycles.

        Research cycles typically take 5-60 minutes. Buckets should cover
        1 minute to 1 hour range.
        """
        from ktrdr.agents.metrics import agent_cycle_duration_seconds

        # Check buckets attribute exists and has reasonable values
        buckets = agent_cycle_duration_seconds._upper_bounds
        # Should have bucket for ~1 minute
        assert any(b >= 60 and b <= 120 for b in buckets)
        # Should have bucket for ~30 minutes
        assert any(b >= 1800 and b <= 2100 for b in buckets)
        # Should have bucket for ~1 hour
        assert any(b >= 3600 for b in buckets)

    def test_phase_duration_has_appropriate_buckets(self):
        """Test phase duration histogram has buckets suitable for individual phases.

        Individual phases vary: design ~30s, training ~10min, backtest ~5min.
        """
        from ktrdr.agents.metrics import agent_phase_duration_seconds

        # Check buckets exist
        buckets = agent_phase_duration_seconds.labels(phase="designing")._upper_bounds
        # Should have bucket for short operations (~10s)
        assert any(b >= 10 and b <= 30 for b in buckets)
        # Should have bucket for ~5 minutes
        assert any(b >= 300 and b <= 360 for b in buckets)


class TestAgentMetricsIntegration:
    """Integration tests for agent metrics with Prometheus registry."""

    def test_metrics_registered_in_prometheus_registry(self):
        """Test that all agent metrics are registered in Prometheus registry."""
        from prometheus_client import REGISTRY

        # Import to ensure registration
        from ktrdr.agents import metrics  # noqa: F401

        # Get all metric names from registry
        metric_names = [
            metric.name
            for metric in REGISTRY.collect()
            if metric.name.startswith("agent_")
        ]

        # Check our custom metrics are present
        assert "agent_cycles" in metric_names or "agent_cycles_total" in metric_names
        assert "agent_cycle_duration_seconds" in metric_names
        assert "agent_phase_duration_seconds" in metric_names
        assert (
            "agent_gate_results" in metric_names
            or "agent_gate_results_total" in metric_names
        )
        assert "agent_tokens" in metric_names or "agent_tokens_total" in metric_names
        assert (
            "agent_budget_spend" in metric_names
            or "agent_budget_spend_total" in metric_names
        )
