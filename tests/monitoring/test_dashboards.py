"""Tests for Grafana dashboard JSON files."""

import json
from pathlib import Path

import pytest

DASHBOARDS_DIR = (
    Path(__file__).parent.parent.parent / "monitoring" / "grafana" / "dashboards"
)


class TestSystemOverviewDashboard:
    """Tests for the System Overview dashboard."""

    @pytest.fixture
    def dashboard(self) -> dict:
        """Load the system overview dashboard JSON."""
        dashboard_path = DASHBOARDS_DIR / "system-overview.json"
        assert dashboard_path.exists(), f"Dashboard file not found: {dashboard_path}"
        with open(dashboard_path) as f:
            return json.load(f)

    def test_dashboard_has_required_fields(self, dashboard: dict) -> None:
        """Dashboard must have required Grafana fields."""
        required_fields = ["uid", "title", "panels", "schemaVersion", "timezone"]
        for field in required_fields:
            assert field in dashboard, f"Missing required field: {field}"

    def test_dashboard_has_valid_uid(self, dashboard: dict) -> None:
        """Dashboard UID must be a non-empty string."""
        assert isinstance(dashboard["uid"], str)
        assert len(dashboard["uid"]) > 0

    def test_dashboard_title_is_system_overview(self, dashboard: dict) -> None:
        """Dashboard title must identify it as System Overview."""
        assert "System" in dashboard["title"] or "Overview" in dashboard["title"]

    def test_dashboard_has_panels(self, dashboard: dict) -> None:
        """Dashboard must have at least one panel."""
        assert len(dashboard["panels"]) > 0

    def test_all_panels_have_required_fields(self, dashboard: dict) -> None:
        """Each panel must have required fields."""
        required_panel_fields = ["id", "type", "title", "gridPos"]
        for i, panel in enumerate(dashboard["panels"]):
            # Skip row panels
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

    def test_stat_panels_have_targets(self, dashboard: dict) -> None:
        """Stat panels must have query targets."""
        for i, panel in enumerate(dashboard["panels"]):
            if panel.get("type") == "stat":
                assert "targets" in panel, f"Stat panel {i} missing targets"
                assert len(panel["targets"]) > 0, f"Stat panel {i} has no targets"

    def test_timeseries_panels_have_targets(self, dashboard: dict) -> None:
        """Time series panels must have query targets."""
        for i, panel in enumerate(dashboard["panels"]):
            if panel.get("type") == "timeseries":
                assert "targets" in panel, f"Timeseries panel {i} missing targets"
                assert len(panel["targets"]) > 0, f"Timeseries panel {i} has no targets"

    def test_dashboard_has_refresh_interval(self, dashboard: dict) -> None:
        """Dashboard must have auto-refresh configured."""
        assert "refresh" in dashboard, "Dashboard missing refresh interval"
        # Refresh should be a string like "30s" or "1m"
        assert isinstance(dashboard["refresh"], str)

    def test_dashboard_has_service_health_panel(self, dashboard: dict) -> None:
        """Dashboard must have a service health panel."""
        panel_titles = [p.get("title", "").lower() for p in dashboard["panels"]]
        health_panels = [t for t in panel_titles if "health" in t or "service" in t]
        assert len(health_panels) > 0, "No service health panel found"

    def test_prometheus_targets_have_expr(self, dashboard: dict) -> None:
        """Prometheus targets must have expr field."""
        for panel in dashboard["panels"]:
            if panel.get("type") in ["stat", "timeseries", "table", "gauge"]:
                for target in panel.get("targets", []):
                    if target.get("datasource", {}).get("type") == "prometheus":
                        assert (
                            "expr" in target
                        ), f"Prometheus target in '{panel.get('title')}' missing expr"


class TestWorkerStatusDashboard:
    """Tests for the Worker Status dashboard."""

    @pytest.fixture
    def dashboard(self) -> dict:
        """Load the worker status dashboard JSON."""
        dashboard_path = DASHBOARDS_DIR / "worker-status.json"
        assert dashboard_path.exists(), f"Dashboard file not found: {dashboard_path}"
        with open(dashboard_path) as f:
            return json.load(f)

    def test_dashboard_has_required_fields(self, dashboard: dict) -> None:
        """Dashboard must have required Grafana fields."""
        required_fields = ["uid", "title", "panels", "schemaVersion", "timezone"]
        for field in required_fields:
            assert field in dashboard, f"Missing required field: {field}"

    def test_dashboard_title_contains_worker(self, dashboard: dict) -> None:
        """Dashboard title must identify it as Worker Status."""
        assert "Worker" in dashboard["title"]

    def test_dashboard_has_worker_count_panel(self, dashboard: dict) -> None:
        """Dashboard must have a worker count panel."""
        panel_titles = [p.get("title", "").lower() for p in dashboard["panels"]]
        worker_panels = [t for t in panel_titles if "worker" in t]
        assert len(worker_panels) > 0, "No worker count panel found"

    def test_dashboard_has_health_matrix_panel(self, dashboard: dict) -> None:
        """Dashboard must have a health matrix or table panel."""
        panel_types = [p.get("type") for p in dashboard["panels"]]
        assert "table" in panel_types or any(
            "health" in p.get("title", "").lower() for p in dashboard["panels"]
        ), "No health matrix/table panel found"

    def test_worker_queries_filter_by_port(self, dashboard: dict) -> None:
        """Worker queries should filter by worker ports (5003-5008)."""
        found_port_filter = False
        for panel in dashboard["panels"]:
            for target in panel.get("targets", []):
                expr = target.get("expr", "")
                if "500[3-8]" in expr or "5003" in expr or "500" in expr:
                    found_port_filter = True
                    break
        assert found_port_filter, "No worker port filtering found in queries"

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


class TestOperationsDashboard:
    """Tests for the Operations dashboard."""

    @pytest.fixture
    def dashboard(self) -> dict:
        """Load the operations dashboard JSON."""
        dashboard_path = DASHBOARDS_DIR / "operations.json"
        assert dashboard_path.exists(), f"Dashboard file not found: {dashboard_path}"
        with open(dashboard_path) as f:
            return json.load(f)

    def test_dashboard_has_required_fields(self, dashboard: dict) -> None:
        """Dashboard must have required Grafana fields."""
        required_fields = ["uid", "title", "panels", "schemaVersion", "timezone"]
        for field in required_fields:
            assert field in dashboard, f"Missing required field: {field}"

    def test_dashboard_title_contains_operations(self, dashboard: dict) -> None:
        """Dashboard title must identify it as Operations."""
        assert "Operation" in dashboard["title"]

    def test_dashboard_has_operation_count_panel(self, dashboard: dict) -> None:
        """Dashboard must have an operation count panel."""
        panel_titles = [p.get("title", "").lower() for p in dashboard["panels"]]
        ops_panels = [
            t for t in panel_titles if "operation" in t or "ops" in t or "backtest" in t
        ]
        assert len(ops_panels) > 0, "No operation count panel found"

    def test_dashboard_has_success_rate_panel(self, dashboard: dict) -> None:
        """Dashboard must have a success rate panel."""
        panel_titles = [p.get("title", "").lower() for p in dashboard["panels"]]
        success_panels = [t for t in panel_titles if "success" in t or "rate" in t]
        assert len(success_panels) > 0, "No success rate panel found"

    def test_operation_queries_filter_by_endpoint(self, dashboard: dict) -> None:
        """Operation queries should filter by operation endpoints."""
        found_endpoint_filter = False
        for panel in dashboard["panels"]:
            for target in panel.get("targets", []):
                expr = target.get("expr", "")
                if "backtest" in expr or "training" in expr or "http_target" in expr:
                    found_endpoint_filter = True
                    break
        assert found_endpoint_filter, "No operation endpoint filtering found in queries"

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


class TestDashboardProvisioning:
    """Tests for dashboard provisioning configuration."""

    def test_dashboards_directory_exists(self) -> None:
        """Dashboards directory must exist."""
        assert (
            DASHBOARDS_DIR.exists()
        ), f"Dashboards directory not found: {DASHBOARDS_DIR}"

    def test_dashboards_yml_exists(self) -> None:
        """Dashboards provisioning config must exist."""
        config_path = DASHBOARDS_DIR.parent / "dashboards.yml"
        assert config_path.exists(), f"dashboards.yml not found: {config_path}"
