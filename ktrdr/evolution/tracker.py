"""Evolution tracker — YAML state persistence for evolution runs.

Manages the directory structure under data/evolution/run_<id>/ and provides
save/load methods for each state type. Operation IDs are persisted
incrementally for crash safety.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ktrdr.evolution.config import EvolutionConfig
from ktrdr.evolution.genome import Researcher


class EvolutionTracker:
    """Persists evolution state as YAML files.

    Directory structure:
        run_dir/
            config.yaml
            generation_00/
                population.yaml
                operations.yaml
                results.yaml
            generation_01/
                ...
    """

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir

    def _gen_dir(self, generation: int) -> Path:
        """Get the directory for a specific generation."""
        return self.run_dir / f"generation_{generation:02d}"

    def _ensure_dir(self, path: Path) -> None:
        """Create directory and parents if needed."""
        path.mkdir(parents=True, exist_ok=True)

    # --- Config ---

    def save_config(self, config: EvolutionConfig) -> None:
        """Save run configuration."""
        self._ensure_dir(self.run_dir)
        path = self.run_dir / "config.yaml"
        with open(path, "w") as f:
            yaml.dump(config.to_dict(), f, default_flow_style=False, sort_keys=False)

    def load_config(self) -> EvolutionConfig | None:
        """Load run configuration. Returns None if file doesn't exist or is invalid."""
        path = self.run_dir / "config.yaml"
        if not path.exists():
            return None
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError:
            return None
        if data is None:
            return None
        return EvolutionConfig.from_dict(data)

    # --- Population ---

    def save_population(self, generation: int, population: list[Researcher]) -> None:
        """Save population for a generation."""
        gen_dir = self._gen_dir(generation)
        self._ensure_dir(gen_dir)
        path = gen_dir / "population.yaml"
        data = [r.to_dict() for r in population]
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def load_population(self, generation: int) -> list[Researcher]:
        """Load population for a generation. Returns empty list if missing."""
        path = self._gen_dir(generation) / "population.yaml"
        if not path.exists():
            return []
        with open(path) as f:
            data = yaml.safe_load(f) or []
        return [Researcher.from_dict(d) for d in data]

    # --- Results ---

    def save_results(self, generation: int, results: list[dict[str, Any]]) -> None:
        """Save results for a generation."""
        gen_dir = self._gen_dir(generation)
        self._ensure_dir(gen_dir)
        path = gen_dir / "results.yaml"
        with open(path, "w") as f:
            yaml.dump(results, f, default_flow_style=False)

    def load_results(self, generation: int) -> list[dict[str, Any]]:
        """Load results for a generation. Returns empty list if missing."""
        path = self._gen_dir(generation) / "results.yaml"
        if not path.exists():
            return []
        with open(path) as f:
            data = yaml.safe_load(f)
        return data if data else []

    # --- Operations (incremental persistence for crash safety) ---

    def save_operation_id(
        self, generation: int, researcher_id: str, operation_id: str
    ) -> None:
        """Persist a single operation ID immediately after trigger.

        Reads existing operations, adds the new one, writes back.
        This must be called after EACH trigger, not batched.
        """
        gen_dir = self._gen_dir(generation)
        self._ensure_dir(gen_dir)
        path = gen_dir / "operations.yaml"

        # Load existing
        operations: dict[str, str] = {}
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f)
            if data:
                operations = data

        # Add new and write back
        operations[researcher_id] = operation_id
        with open(path, "w") as f:
            yaml.dump(operations, f, default_flow_style=False)

    def load_operations(self, generation: int) -> dict[str, str]:
        """Load operation ID mapping. Returns empty dict if missing."""
        path = self._gen_dir(generation) / "operations.yaml"
        if not path.exists():
            return {}
        with open(path) as f:
            data = yaml.safe_load(f)
        return data if data else {}

    # --- Summary (cross-generation) ---

    def save_summary(self, summary: dict[str, Any]) -> None:
        """Save or update the cross-generation summary."""
        self._ensure_dir(self.run_dir)
        path = self.run_dir / "summary.yaml"
        with open(path, "w") as f:
            yaml.dump(summary, f, default_flow_style=False, sort_keys=False)

    def load_summary(self) -> dict[str, Any]:
        """Load cross-generation summary. Returns empty dict if missing."""
        path = self.run_dir / "summary.yaml"
        if not path.exists():
            return {}
        with open(path) as f:
            data = yaml.safe_load(f)
        return data if data else {}

    # --- Generation tracking ---

    def get_last_completed_generation(self) -> int | None:
        """Find the highest generation number that has results.

        Returns None if no generations have completed.
        """
        if not self.run_dir.exists():
            return None

        last = None
        for gen_dir in sorted(self.run_dir.glob("generation_*")):
            if (gen_dir / "results.yaml").exists():
                # Extract generation number from directory name
                gen_num = int(gen_dir.name.split("_")[1])
                last = gen_num

        return last
