"""Tests for the Orchestrator Grafana dashboard."""

import json
from pathlib import Path

import pytest

DASHBOARDS_DIR = (
    Path(__file__).parent.parent.parent / "deploy" / "shared" / "grafana" / "dashboards"
)


class TestOrchestratorDashboard:
    """Tests for the Orchestrator dashboard."""

    @pytest.fixture
    def dashboard(self) -> dict:
        """Load the orchestrator dashboard JSON."""
        dashboard_path = DASHBOARDS_DIR / "orchestrator.json"
        assert dashboard_path.exists(), f"Dashboard file not found: {dashboard_path}"
        with open(dashboard_path) as f:
            return json.load(f)

    def test_dashboard_has_required_fields(self, dashboard: dict) -> None:
        """Dashboard must have required Grafana fields."""
        required_fields = ["uid", "title", "panels", "schemaVersion", "timezone"]
        for field in required_fields:
            assert field in dashboard, f"Missing required field: {field}"

    def test_dashboard_uid_is_orchestrator(self, dashboard: dict) -> None:
        """Dashboard UID must be orchestrator for easy access."""
        assert dashboard["uid"] == "orchestrator"

    def test_dashboard_title_contains_orchestrator(self, dashboard: dict) -> None:
        """Dashboard title must identify it as Orchestrator."""
        assert "Orchestrator" in dashboard["title"]

    def test_dashboard_has_refresh_interval(self, dashboard: dict) -> None:
        """Dashboard must have auto-refresh configured."""
        assert "refresh" in dashboard, "Dashboard missing refresh interval"
        assert isinstance(dashboard["refresh"], str)

    def test_all_panels_have_required_fields(self, dashboard: dict) -> None:
        """Each panel must have required fields."""
        required_panel_fields = ["id", "type", "title", "gridPos"]
        for i, panel in enumerate(dashboard["panels"]):
            if panel.get("type") == "row":
                continue
            for field in required_panel_fields:
                assert field in panel, f"Panel {i} missing field: {field}"

    def test_panels_have_valid_grid_positions(self, dashboard: dict) -> None:
        """Panel grid positions must be valid."""
        for i, panel in enumerate(dashboard["panels"]):
            if panel.get("type") == "row":
                continue
            grid = panel["gridPos"]
            assert "x" in grid and "y" in grid, f"Panel {i} missing x/y position"
            assert "w" in grid and "h" in grid, f"Panel {i} missing w/h dimensions"
            assert 0 <= grid["x"] < 24, f"Panel {i} x position out of range"
            assert grid["w"] > 0 and grid["h"] > 0, f"Panel {i} invalid dimensions"

    def test_prometheus_targets_have_expr(self, dashboard: dict) -> None:
        """Prometheus targets must have expr field."""
        for panel in dashboard["panels"]:
            if panel.get("type") in ["stat", "timeseries", "table", "gauge", "piechart"]:
                for target in panel.get("targets", []):
                    if target.get("datasource", {}).get("type") == "prometheus":
                        assert (
                            "expr" in target
                        ), f"Prometheus target in '{panel.get('title')}' missing expr"

    # Panel-specific tests based on Task 5.7 requirements

    def test_has_cost_over_time_panel(self, dashboard: dict) -> None:
        """Dashboard must have a cost over time panel."""
        panel_titles = [p.get("title", "").lower() for p in dashboard["panels"]]
        cost_panels = [t for t in panel_titles if "cost" in t]
        assert len(cost_panels) > 0, "No cost panel found"

    def test_has_task_success_rate_panel(self, dashboard: dict) -> None:
        """Dashboard must have a task success rate panel."""
        panel_titles = [p.get("title", "").lower() for p in dashboard["panels"]]
        success_panels = [t for t in panel_titles if "success" in t and "rate" in t]
        assert len(success_panels) > 0, "No task success rate panel found"

    def test_has_escalation_panel(self, dashboard: dict) -> None:
        """Dashboard must have an escalation panel."""
        panel_titles = [p.get("title", "").lower() for p in dashboard["panels"]]
        escalation_panels = [t for t in panel_titles if "escalation" in t]
        assert len(escalation_panels) > 0, "No escalation panel found"

    def test_has_duration_p95_panel(self, dashboard: dict) -> None:
        """Dashboard must have a task duration P95 panel."""
        panel_titles = [p.get("title", "").lower() for p in dashboard["panels"]]
        duration_panels = [t for t in panel_titles if "duration" in t or "p95" in t]
        assert len(duration_panels) > 0, "No duration P95 panel found"

    def test_has_e2e_pass_rate_panel(self, dashboard: dict) -> None:
        """Dashboard must have an E2E pass rate panel."""
        panel_titles = [p.get("title", "").lower() for p in dashboard["panels"]]
        e2e_panels = [t for t in panel_titles if "e2e" in t]
        assert len(e2e_panels) > 0, "No E2E panel found"

    def test_has_loop_detection_panel(self, dashboard: dict) -> None:
        """Dashboard must have a loop detection panel."""
        panel_titles = [p.get("title", "").lower() for p in dashboard["panels"]]
        loop_panels = [t for t in panel_titles if "loop" in t]
        assert len(loop_panels) > 0, "No loop detection panel found"

    def test_has_tokens_panel(self, dashboard: dict) -> None:
        """Dashboard must have a tokens panel."""
        panel_titles = [p.get("title", "").lower() for p in dashboard["panels"]]
        token_panels = [t for t in panel_titles if "token" in t]
        assert len(token_panels) > 0, "No tokens panel found"

    def test_has_table_panel(self, dashboard: dict) -> None:
        """Dashboard must have a table panel for active milestones."""
        panel_types = [p.get("type") for p in dashboard["panels"]]
        assert "table" in panel_types, "No table panel found for active milestones"

    # Variable tests
    def test_has_milestone_variable(self, dashboard: dict) -> None:
        """Dashboard must have a milestone filter variable."""
        assert "templating" in dashboard, "Dashboard missing templating section"
        assert "list" in dashboard["templating"], "Dashboard missing variable list"

        variable_names = [v.get("name", "").lower() for v in dashboard["templating"]["list"]]
        assert "milestone" in variable_names, "No milestone variable found"

    # Metric-specific tests based on telemetry.py
    def test_queries_use_orchestrator_metrics(self, dashboard: dict) -> None:
        """Dashboard queries must use orchestrator_* metrics."""
        found_orchestrator_metrics = False
        for panel in dashboard["panels"]:
            for target in panel.get("targets", []):
                expr = target.get("expr", "")
                if "orchestrator_" in expr:
                    found_orchestrator_metrics = True
                    break
        assert found_orchestrator_metrics, "No orchestrator_* metrics found in queries"

    def test_cost_query_uses_cost_usd_total(self, dashboard: dict) -> None:
        """Cost panel must query orchestrator_cost_usd_total."""
        for panel in dashboard["panels"]:
            if "cost" in panel.get("title", "").lower():
                for target in panel.get("targets", []):
                    expr = target.get("expr", "")
                    if "orchestrator_cost_usd_total" in expr:
                        return  # Found it
        pytest.fail("Cost panel doesn't query orchestrator_cost_usd_total")

    def test_tasks_query_uses_tasks_total(self, dashboard: dict) -> None:
        """Task panels must query orchestrator_tasks_total."""
        for panel in dashboard["panels"]:
            if "success" in panel.get("title", "").lower():
                for target in panel.get("targets", []):
                    expr = target.get("expr", "")
                    if "orchestrator_tasks_total" in expr:
                        return  # Found it
        pytest.fail("Task success panel doesn't query orchestrator_tasks_total")

    def test_e2e_query_uses_e2e_tests_total(self, dashboard: dict) -> None:
        """E2E panel must query orchestrator_e2e_tests_total."""
        for panel in dashboard["panels"]:
            if "e2e" in panel.get("title", "").lower():
                for target in panel.get("targets", []):
                    expr = target.get("expr", "")
                    if "orchestrator_e2e_tests_total" in expr:
                        return  # Found it
        pytest.fail("E2E panel doesn't query orchestrator_e2e_tests_total")
