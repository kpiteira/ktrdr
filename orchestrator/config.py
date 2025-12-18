"""Configuration for the Orchestrator.

Provides centralized configuration with sensible defaults and environment
variable overrides for sandbox settings, Claude Code parameters, and telemetry.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class OrchestratorConfig:
    """Configuration for orchestrator execution.

    All settings have sensible defaults but can be overridden via environment
    variables using the from_env() factory method.
    """

    # Sandbox settings
    sandbox_container: str = "ktrdr-sandbox"
    workspace_path: str = "/workspace"

    # Claude Code settings
    max_turns: int = 50
    task_timeout_seconds: int = 600
    allowed_tools: list[str] = field(
        default_factory=lambda: ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]
    )

    # Telemetry settings
    otlp_endpoint: str = field(
        default_factory=lambda: os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
    )
    service_name: str = "orchestrator"

    # State persistence
    state_dir: Path = field(default_factory=lambda: Path("state"))

    @classmethod
    def from_env(cls) -> "OrchestratorConfig":
        """Load config with environment variable overrides.

        Environment variables:
            ORCHESTRATOR_MAX_TURNS: Override max_turns (default: 50)
            ORCHESTRATOR_TASK_TIMEOUT: Override task_timeout_seconds (default: 600)
            OTLP_ENDPOINT: Override otlp_endpoint (default: http://localhost:4317)
        """
        return cls(
            max_turns=int(os.getenv("ORCHESTRATOR_MAX_TURNS", "50")),
            task_timeout_seconds=int(os.getenv("ORCHESTRATOR_TASK_TIMEOUT", "600")),
            otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://localhost:4317"),
        )
