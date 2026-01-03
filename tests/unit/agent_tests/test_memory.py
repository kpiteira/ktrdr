"""
Unit tests for memory module.

Tests cover:
- ExperimentRecord and Hypothesis dataclasses
- load_experiments with empty/missing directory
- save_experiment creates valid YAML files
- generate_experiment_id produces unique IDs with correct format
- Hypothesis functions: get_all, get_open, save, update_status
- generate_hypothesis_id sequential numbering
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

    def test_experiment_record_status_default(self):
        """Test ExperimentRecord status defaults to 'completed'."""
        from ktrdr.agents.memory import ExperimentRecord

        record = ExperimentRecord(
            id="exp_test",
            timestamp="2025-12-28T00:00:00Z",
            strategy_name="test",
            context={},
            results={},
            assessment={},
        )

        assert record.status == "completed"
        assert record.gate_rejection_reason is None

    def test_experiment_record_gate_rejected_training(self):
        """Test ExperimentRecord with gate_rejected_training status."""
        from ktrdr.agents.memory import ExperimentRecord

        record = ExperimentRecord(
            id="exp_rejected",
            timestamp="2025-12-28T00:00:00Z",
            strategy_name="test",
            context={},
            results={"test_accuracy": 0.05},
            assessment={"verdict": "weak_signal"},
            status="gate_rejected_training",
            gate_rejection_reason="accuracy_too_low (5% < 10%)",
        )

        assert record.status == "gate_rejected_training"
        assert record.gate_rejection_reason == "accuracy_too_low (5% < 10%)"

    def test_experiment_record_gate_rejected_backtest(self):
        """Test ExperimentRecord with gate_rejected_backtest status."""
        from ktrdr.agents.memory import ExperimentRecord

        record = ExperimentRecord(
            id="exp_rejected",
            timestamp="2025-12-28T00:00:00Z",
            strategy_name="test",
            context={},
            results={"test_accuracy": 0.65, "sharpe_ratio": -0.5},
            assessment={"verdict": "weak_signal"},
            status="gate_rejected_backtest",
            gate_rejection_reason="sharpe_ratio_too_low (-0.5 < 0.0)",
        )

        assert record.status == "gate_rejected_backtest"
        assert record.gate_rejection_reason == "sharpe_ratio_too_low (-0.5 < 0.0)"


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

    def test_load_experiments_backward_compat_missing_status(self, temp_memory_dir):
        """Test old experiments without status field default to 'completed'."""
        from ktrdr.agents.memory import load_experiments

        # Create an old-format experiment without status fields
        old_file = temp_memory_dir / "exp_old_format.yaml"
        old_file.write_text(
            yaml.dump(
                {
                    "id": "exp_old_format",
                    "timestamp": "2025-12-27T00:00:00Z",
                    "strategy_name": "old_strategy",
                    "context": {},
                    "results": {"test_accuracy": 0.65},
                    "assessment": {"verdict": "strong_signal"},
                    "source": "agent",
                    # Note: No 'status' or 'gate_rejection_reason' fields
                }
            )
        )

        result = load_experiments(n=1)
        assert len(result) == 1
        # Should default to "completed" for backward compatibility
        assert result[0].get("status", "completed") == "completed"
        assert result[0].get("gate_rejection_reason") is None


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

    def test_save_experiment_with_status_field(self, temp_memory_dir):
        """Test save_experiment serializes status field correctly."""
        from ktrdr.agents.memory import ExperimentRecord, save_experiment

        record = ExperimentRecord(
            id="exp_gate_rejected",
            timestamp="2025-12-28T14:30:00Z",
            strategy_name="test_strategy",
            context={"indicators": ["RSI"]},
            results={"test_accuracy": 0.05},
            assessment={"verdict": "weak_signal"},
            status="gate_rejected_training",
            gate_rejection_reason="accuracy_too_low (5% < 10%)",
        )

        path = save_experiment(record)

        content = yaml.safe_load(path.read_text())
        assert content["status"] == "gate_rejected_training"
        assert content["gate_rejection_reason"] == "accuracy_too_low (5% < 10%)"

    def test_save_experiment_with_none_gate_rejection_reason(self, temp_memory_dir):
        """Test save_experiment serializes None gate_rejection_reason correctly."""
        from ktrdr.agents.memory import ExperimentRecord, save_experiment

        record = ExperimentRecord(
            id="exp_completed",
            timestamp="2025-12-28T14:30:00Z",
            strategy_name="test_strategy",
            context={},
            results={"test_accuracy": 0.65},
            assessment={"verdict": "strong_signal"},
            # Default status and gate_rejection_reason
        )

        path = save_experiment(record)

        content = yaml.safe_load(path.read_text())
        assert content["status"] == "completed"
        assert content["gate_rejection_reason"] is None


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


class TestGetAllHypotheses:
    """Tests for get_all_hypotheses function."""

    @pytest.fixture
    def temp_memory_dir(self, tmp_path, monkeypatch):
        """Create temporary memory directory and patch HYPOTHESES_FILE."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir(parents=True)
        hypotheses_file = memory_dir / "hypotheses.yaml"

        import ktrdr.agents.memory as memory_module

        monkeypatch.setattr(memory_module, "MEMORY_DIR", memory_dir)
        monkeypatch.setattr(memory_module, "HYPOTHESES_FILE", hypotheses_file)

        return hypotheses_file

    def test_get_all_hypotheses_empty(self, tmp_path, monkeypatch):
        """Test returns [] when no file exists."""
        import ktrdr.agents.memory as memory_module

        monkeypatch.setattr(
            memory_module, "HYPOTHESES_FILE", tmp_path / "nonexistent.yaml"
        )

        from ktrdr.agents.memory import get_all_hypotheses

        result = get_all_hypotheses()
        assert result == []

    def test_get_all_hypotheses_returns_all(self, temp_memory_dir):
        """Test returns all hypotheses from file."""
        # Create file with hypotheses
        temp_memory_dir.write_text(
            yaml.dump(
                {
                    "hypotheses": [
                        {"id": "H_001", "text": "First", "status": "untested"},
                        {"id": "H_002", "text": "Second", "status": "validated"},
                        {"id": "H_003", "text": "Third", "status": "untested"},
                    ]
                }
            )
        )

        from ktrdr.agents.memory import get_all_hypotheses

        result = get_all_hypotheses()
        assert len(result) == 3
        assert result[0]["id"] == "H_001"
        assert result[1]["id"] == "H_002"
        assert result[2]["id"] == "H_003"


class TestGetOpenHypotheses:
    """Tests for get_open_hypotheses function."""

    @pytest.fixture
    def temp_memory_dir(self, tmp_path, monkeypatch):
        """Create temporary memory directory and patch HYPOTHESES_FILE."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir(parents=True)
        hypotheses_file = memory_dir / "hypotheses.yaml"

        import ktrdr.agents.memory as memory_module

        monkeypatch.setattr(memory_module, "MEMORY_DIR", memory_dir)
        monkeypatch.setattr(memory_module, "HYPOTHESES_FILE", hypotheses_file)

        return hypotheses_file

    def test_get_open_hypotheses_filters(self, temp_memory_dir):
        """Test only returns hypotheses with status='untested'."""
        temp_memory_dir.write_text(
            yaml.dump(
                {
                    "hypotheses": [
                        {"id": "H_001", "text": "First", "status": "untested"},
                        {"id": "H_002", "text": "Second", "status": "validated"},
                        {"id": "H_003", "text": "Third", "status": "untested"},
                        {"id": "H_004", "text": "Fourth", "status": "refuted"},
                    ]
                }
            )
        )

        from ktrdr.agents.memory import get_open_hypotheses

        result = get_open_hypotheses()
        assert len(result) == 2
        assert result[0]["id"] == "H_001"
        assert result[1]["id"] == "H_003"

    def test_get_open_hypotheses_empty_when_all_tested(self, temp_memory_dir):
        """Test returns [] when no untested hypotheses."""
        temp_memory_dir.write_text(
            yaml.dump(
                {
                    "hypotheses": [
                        {"id": "H_001", "text": "First", "status": "validated"},
                        {"id": "H_002", "text": "Second", "status": "refuted"},
                    ]
                }
            )
        )

        from ktrdr.agents.memory import get_open_hypotheses

        result = get_open_hypotheses()
        assert result == []


class TestSaveHypothesis:
    """Tests for save_hypothesis function."""

    @pytest.fixture
    def temp_memory_dir(self, tmp_path, monkeypatch):
        """Create temporary memory directory and patch HYPOTHESES_FILE."""
        memory_dir = tmp_path / "memory"
        # Don't create - let save_hypothesis create it
        hypotheses_file = memory_dir / "hypotheses.yaml"

        import ktrdr.agents.memory as memory_module

        monkeypatch.setattr(memory_module, "MEMORY_DIR", memory_dir)
        monkeypatch.setattr(memory_module, "HYPOTHESES_FILE", hypotheses_file)

        return hypotheses_file

    def test_save_hypothesis_creates_file(self, temp_memory_dir):
        """Test save_hypothesis creates file if it doesn't exist."""
        from ktrdr.agents.memory import Hypothesis, save_hypothesis

        hypothesis = Hypothesis(
            id="H_001",
            text="Test hypothesis",
            source_experiment="exp_test",
            rationale="Test rationale",
        )

        save_hypothesis(hypothesis)

        assert temp_memory_dir.exists()
        content = yaml.safe_load(temp_memory_dir.read_text())
        assert len(content["hypotheses"]) == 1
        assert content["hypotheses"][0]["id"] == "H_001"

    def test_save_hypothesis_appends(self, temp_memory_dir):
        """Test save_hypothesis appends to existing list without overwriting."""
        # Create initial file
        temp_memory_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_memory_dir.write_text(
            yaml.dump(
                {
                    "hypotheses": [
                        {
                            "id": "H_001",
                            "text": "First",
                            "source_experiment": "exp_1",
                            "rationale": "R1",
                            "status": "untested",
                            "tested_by": [],
                            "created": "2025-12-28T00:00:00",
                        }
                    ]
                }
            )
        )

        from ktrdr.agents.memory import Hypothesis, save_hypothesis

        hypothesis = Hypothesis(
            id="H_002",
            text="Second hypothesis",
            source_experiment="exp_2",
            rationale="R2",
        )

        save_hypothesis(hypothesis)

        content = yaml.safe_load(temp_memory_dir.read_text())
        assert len(content["hypotheses"]) == 2
        assert content["hypotheses"][0]["id"] == "H_001"  # Original preserved
        assert content["hypotheses"][1]["id"] == "H_002"  # New appended


class TestUpdateHypothesisStatus:
    """Tests for update_hypothesis_status function."""

    @pytest.fixture
    def temp_memory_dir(self, tmp_path, monkeypatch):
        """Create temporary memory directory with hypotheses file."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir(parents=True)
        hypotheses_file = memory_dir / "hypotheses.yaml"

        # Create initial hypotheses
        hypotheses_file.write_text(
            yaml.dump(
                {
                    "hypotheses": [
                        {
                            "id": "H_001",
                            "text": "First",
                            "source_experiment": "exp_1",
                            "rationale": "R1",
                            "status": "untested",
                            "tested_by": [],
                            "created": "2025-12-28T00:00:00",
                        },
                        {
                            "id": "H_002",
                            "text": "Second",
                            "source_experiment": "exp_2",
                            "rationale": "R2",
                            "status": "untested",
                            "tested_by": [],
                            "created": "2025-12-28T00:00:00",
                        },
                    ]
                }
            )
        )

        import ktrdr.agents.memory as memory_module

        monkeypatch.setattr(memory_module, "MEMORY_DIR", memory_dir)
        monkeypatch.setattr(memory_module, "HYPOTHESES_FILE", hypotheses_file)

        return hypotheses_file

    def test_update_hypothesis_status_modifies(self, temp_memory_dir):
        """Test status is correctly modified."""
        from ktrdr.agents.memory import update_hypothesis_status

        update_hypothesis_status("H_001", "validated", "exp_test_001")

        content = yaml.safe_load(temp_memory_dir.read_text())
        h1 = next(h for h in content["hypotheses"] if h["id"] == "H_001")
        assert h1["status"] == "validated"

    def test_update_hypothesis_status_adds_tested_by(self, temp_memory_dir):
        """Test experiment is added to tested_by list."""
        from ktrdr.agents.memory import update_hypothesis_status

        update_hypothesis_status("H_001", "validated", "exp_test_001")

        content = yaml.safe_load(temp_memory_dir.read_text())
        h1 = next(h for h in content["hypotheses"] if h["id"] == "H_001")
        assert "exp_test_001" in h1["tested_by"]

    def test_update_hypothesis_status_preserves_others(self, temp_memory_dir):
        """Test other hypotheses are not modified."""
        from ktrdr.agents.memory import update_hypothesis_status

        update_hypothesis_status("H_001", "validated", "exp_test_001")

        content = yaml.safe_load(temp_memory_dir.read_text())
        h2 = next(h for h in content["hypotheses"] if h["id"] == "H_002")
        assert h2["status"] == "untested"  # Unchanged
        assert h2["tested_by"] == []  # Unchanged


class TestGenerateHypothesisId:
    """Tests for generate_hypothesis_id function."""

    @pytest.fixture
    def temp_memory_dir(self, tmp_path, monkeypatch):
        """Create temporary memory directory and patch HYPOTHESES_FILE."""
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir(parents=True)
        hypotheses_file = memory_dir / "hypotheses.yaml"

        import ktrdr.agents.memory as memory_module

        monkeypatch.setattr(memory_module, "MEMORY_DIR", memory_dir)
        monkeypatch.setattr(memory_module, "HYPOTHESES_FILE", hypotheses_file)

        return hypotheses_file

    def test_generate_hypothesis_id_first(self, temp_memory_dir):
        """Test first ID is H_001 when no hypotheses exist."""
        from ktrdr.agents.memory import generate_hypothesis_id

        result = generate_hypothesis_id()
        assert result == "H_001"

    def test_generate_hypothesis_id_sequential(self, temp_memory_dir):
        """Test IDs are sequential: H_001, H_002, etc."""
        temp_memory_dir.write_text(
            yaml.dump(
                {
                    "hypotheses": [
                        {"id": "H_001", "text": "First"},
                        {"id": "H_002", "text": "Second"},
                        {"id": "H_003", "text": "Third"},
                    ]
                }
            )
        )

        from ktrdr.agents.memory import generate_hypothesis_id

        result = generate_hypothesis_id()
        assert result == "H_004"

    def test_generate_hypothesis_id_zero_padded(self, temp_memory_dir):
        """Test IDs are zero-padded to 3 digits."""
        from ktrdr.agents.memory import generate_hypothesis_id

        result = generate_hypothesis_id()
        assert re.match(r"^H_\d{3}$", result), f"ID '{result}' should be zero-padded"

    def test_generate_hypothesis_id_handles_gaps(self, temp_memory_dir):
        """Test ID generation handles gaps in numbering."""
        temp_memory_dir.write_text(
            yaml.dump(
                {
                    "hypotheses": [
                        {"id": "H_001", "text": "First"},
                        {"id": "H_005", "text": "Fifth"},  # Gap
                    ]
                }
            )
        )

        from ktrdr.agents.memory import generate_hypothesis_id

        result = generate_hypothesis_id()
        # Should use max + 1, not fill gaps
        assert result == "H_006"
