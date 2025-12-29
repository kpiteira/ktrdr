"""
Unit tests for memory module.

Tests cover:
- ExperimentRecord and Hypothesis dataclasses
- load_experiments with empty/missing directory
- save_experiment creates valid YAML files
- generate_experiment_id produces unique IDs with correct format
"""

import re
import time

import pytest
import yaml


class TestExperimentRecord:
    """Tests for ExperimentRecord dataclass."""

    def test_experiment_record_fields(self):
        """Test ExperimentRecord has all required fields."""
        from ktrdr.agents.memory import ExperimentRecord

        record = ExperimentRecord(
            id="exp_20251228_143052_abc123",
            timestamp="2025-12-28T14:30:52Z",
            strategy_name="test_strategy",
            context={"indicators": ["RSI"], "timeframe": "1h"},
            results={"test_accuracy": 0.65},
            assessment={"verdict": "strong_signal"},
        )

        assert record.id == "exp_20251228_143052_abc123"
        assert record.timestamp == "2025-12-28T14:30:52Z"
        assert record.strategy_name == "test_strategy"
        assert record.context == {"indicators": ["RSI"], "timeframe": "1h"}
        assert record.results == {"test_accuracy": 0.65}
        assert record.assessment == {"verdict": "strong_signal"}
        assert record.source == "agent"  # default value

    def test_experiment_record_custom_source(self):
        """Test ExperimentRecord accepts custom source."""
        from ktrdr.agents.memory import ExperimentRecord

        record = ExperimentRecord(
            id="exp_v15_test",
            timestamp="2025-12-27T00:00:00Z",
            strategy_name="v15_test",
            context={},
            results={},
            assessment={},
            source="v1.5_bootstrap",
        )

        assert record.source == "v1.5_bootstrap"


class TestHypothesis:
    """Tests for Hypothesis dataclass."""

    def test_hypothesis_fields(self):
        """Test Hypothesis has all required fields."""
        from ktrdr.agents.memory import Hypothesis

        hypothesis = Hypothesis(
            id="H_001",
            text="Multi-timeframe might help",
            source_experiment="exp_v15_test",
            rationale="Single timeframe seems to be a ceiling",
        )

        assert hypothesis.id == "H_001"
        assert hypothesis.text == "Multi-timeframe might help"
        assert hypothesis.source_experiment == "exp_v15_test"
        assert hypothesis.rationale == "Single timeframe seems to be a ceiling"
        assert hypothesis.status == "untested"  # default
        assert hypothesis.tested_by == []  # default
        assert hypothesis.created is not None  # default: datetime.now().isoformat()

    def test_hypothesis_custom_status(self):
        """Test Hypothesis accepts custom status."""
        from ktrdr.agents.memory import Hypothesis

        hypothesis = Hypothesis(
            id="H_002",
            text="Test hypothesis",
            source_experiment="exp_test",
            rationale="Test rationale",
            status="validated",
            tested_by=["exp_001", "exp_002"],
        )

        assert hypothesis.status == "validated"
        assert hypothesis.tested_by == ["exp_001", "exp_002"]


class TestLoadExperiments:
    """Tests for load_experiments function."""

    @pytest.fixture
    def temp_memory_dir(self, tmp_path, monkeypatch):
        """Create temporary memory directory and patch MEMORY_DIR."""
        memory_dir = tmp_path / "memory"
        experiments_dir = memory_dir / "experiments"
        experiments_dir.mkdir(parents=True)

        # Patch the module-level constants
        import ktrdr.agents.memory as memory_module

        monkeypatch.setattr(memory_module, "MEMORY_DIR", memory_dir)
        monkeypatch.setattr(memory_module, "EXPERIMENTS_DIR", experiments_dir)

        return experiments_dir

    def test_load_experiments_empty_dir(self, temp_memory_dir):
        """Test returns [] when directory is empty."""
        from ktrdr.agents.memory import load_experiments

        result = load_experiments()
        assert result == []

    def test_load_experiments_missing_dir(self, tmp_path, monkeypatch):
        """Test returns [] when directory doesn't exist."""
        import ktrdr.agents.memory as memory_module

        # Point to non-existent directory
        monkeypatch.setattr(memory_module, "EXPERIMENTS_DIR", tmp_path / "nonexistent")

        from ktrdr.agents.memory import load_experiments

        result = load_experiments()
        assert result == []

    def test_load_experiments_returns_n_most_recent(self, temp_memory_dir):
        """Test respects n parameter, returns only n experiments."""
        from ktrdr.agents.memory import load_experiments

        # Create 5 experiment files with slight time gaps
        for i in range(5):
            exp_file = temp_memory_dir / f"exp_{i:03d}.yaml"
            exp_file.write_text(
                yaml.dump(
                    {
                        "id": f"exp_{i:03d}",
                        "timestamp": f"2025-12-28T14:{i:02d}:00Z",
                        "strategy_name": f"strategy_{i}",
                        "context": {},
                        "results": {},
                        "assessment": {},
                    }
                )
            )
            # Ensure different modification times
            time.sleep(0.01)

        # Request only 3
        result = load_experiments(n=3)
        assert len(result) == 3

    def test_load_experiments_sorted_by_timestamp(self, temp_memory_dir):
        """Test returns experiments sorted by file modification time (most recent first)."""
        from ktrdr.agents.memory import load_experiments

        # Create files in specific order with controlled modification times
        # Create oldest first
        old_file = temp_memory_dir / "exp_old.yaml"
        old_file.write_text(
            yaml.dump(
                {
                    "id": "exp_old",
                    "timestamp": "2025-12-27T00:00:00Z",
                    "strategy_name": "old_strategy",
                    "context": {},
                    "results": {},
                    "assessment": {},
                }
            )
        )
        time.sleep(0.05)

        # Create newest second (will have later mtime)
        new_file = temp_memory_dir / "exp_new.yaml"
        new_file.write_text(
            yaml.dump(
                {
                    "id": "exp_new",
                    "timestamp": "2025-12-28T00:00:00Z",
                    "strategy_name": "new_strategy",
                    "context": {},
                    "results": {},
                    "assessment": {},
                }
            )
        )

        result = load_experiments(n=2)

        # Most recent file should be first
        assert result[0]["id"] == "exp_new"
        assert result[1]["id"] == "exp_old"

    def test_load_experiments_default_n_is_15(self, temp_memory_dir):
        """Test default n value is 15."""
        from ktrdr.agents.memory import load_experiments

        # Create 20 experiment files
        for i in range(20):
            exp_file = temp_memory_dir / f"exp_{i:03d}.yaml"
            exp_file.write_text(
                yaml.dump(
                    {
                        "id": f"exp_{i:03d}",
                        "timestamp": "2025-12-28T00:00:00Z",
                        "strategy_name": f"strategy_{i}",
                        "context": {},
                        "results": {},
                        "assessment": {},
                    }
                )
            )

        # Default should return 15
        result = load_experiments()
        assert len(result) == 15


class TestSaveExperiment:
    """Tests for save_experiment function."""

    @pytest.fixture
    def temp_memory_dir(self, tmp_path, monkeypatch):
        """Create temporary memory directory and patch EXPERIMENTS_DIR."""
        memory_dir = tmp_path / "memory"
        experiments_dir = memory_dir / "experiments"
        # Don't create directories - let save_experiment do it

        import ktrdr.agents.memory as memory_module

        monkeypatch.setattr(memory_module, "MEMORY_DIR", memory_dir)
        monkeypatch.setattr(memory_module, "EXPERIMENTS_DIR", experiments_dir)

        return experiments_dir

    def test_save_experiment_creates_file(self, temp_memory_dir):
        """Test save_experiment creates YAML file with correct content."""
        from ktrdr.agents.memory import ExperimentRecord, save_experiment

        record = ExperimentRecord(
            id="exp_test_001",
            timestamp="2025-12-28T14:30:00Z",
            strategy_name="test_strategy",
            context={"indicators": ["RSI"], "timeframe": "1h"},
            results={"test_accuracy": 0.65},
            assessment={"verdict": "strong_signal", "observations": ["Good result"]},
        )

        path = save_experiment(record)

        assert path.exists()
        assert path.name == "exp_test_001.yaml"

        # Verify content
        content = yaml.safe_load(path.read_text())
        assert content["id"] == "exp_test_001"
        assert content["timestamp"] == "2025-12-28T14:30:00Z"
        assert content["strategy_name"] == "test_strategy"
        assert content["context"]["indicators"] == ["RSI"]
        assert content["results"]["test_accuracy"] == 0.65
        assert content["assessment"]["verdict"] == "strong_signal"
        assert content["source"] == "agent"

    def test_save_experiment_creates_directories(self, tmp_path, monkeypatch):
        """Test save_experiment creates parent directories if missing."""
        import ktrdr.agents.memory as memory_module

        # Point to deeply nested non-existent directory
        nested_dir = tmp_path / "deep" / "nested" / "memory" / "experiments"
        monkeypatch.setattr(memory_module, "EXPERIMENTS_DIR", nested_dir)

        from ktrdr.agents.memory import ExperimentRecord, save_experiment

        record = ExperimentRecord(
            id="exp_nested_test",
            timestamp="2025-12-28T14:30:00Z",
            strategy_name="test",
            context={},
            results={},
            assessment={},
        )

        path = save_experiment(record)

        assert path.exists()
        assert nested_dir.exists()


class TestGenerateExperimentId:
    """Tests for generate_experiment_id function."""

    def test_generate_experiment_id_unique(self):
        """Test multiple calls return different IDs."""
        from ktrdr.agents.memory import generate_experiment_id

        ids = [generate_experiment_id() for _ in range(10)]
        assert len(set(ids)) == 10  # All unique

    def test_generate_experiment_id_format(self):
        """Test ID matches expected pattern: exp_YYYYMMDD_HHMMSS_xxxx."""
        from ktrdr.agents.memory import generate_experiment_id

        exp_id = generate_experiment_id()

        # Pattern: exp_20251228_143052_abc12345
        pattern = r"^exp_\d{8}_\d{6}_[a-f0-9]{8}$"
        assert re.match(pattern, exp_id), f"ID '{exp_id}' doesn't match pattern"

    def test_generate_experiment_id_has_date_component(self):
        """Test ID contains current date."""
        from datetime import datetime

        from ktrdr.agents.memory import generate_experiment_id

        exp_id = generate_experiment_id()
        today = datetime.now().strftime("%Y%m%d")

        assert today in exp_id, f"ID '{exp_id}' should contain today's date {today}"
