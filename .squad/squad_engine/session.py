"""PersistentAgentSession — multi-turn wrapper over claude_agent_sdk.

Provides persistent conversation sessions for squad agents using
ClaudeSDKClient.connect() → query() → receive_response() → disconnect().

Spike gotchas handled:
- connect() with no arguments (passing prompt hangs)
- disconnect() throws CancelledError — wrapped in try/except
- CLAUDECODE env var removed during session to prevent nested blocking
- Working directory isolation to avoid mcp/ package shadowing
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from ktrdr import get_logger
from ktrdr.agents.runtime.protocol import AgentResult

logger = get_logger(__name__)

# Default model for all squad agents — best available
DEFAULT_MODEL = "claude-opus-4-6"


def _get_sdk():
    """Lazy-import claude_agent_sdk to avoid mcp package shadowing in dev.

    The project has a local mcp/ directory that shadows the pip mcp package.
    Temporarily remove the project root from sys.path during import.
    """
    import sys

    project_root = str(Path(__file__).resolve().parent.parent.parent)
    removed = []
    for p in (project_root, ""):
        if p in sys.path:
            sys.path.remove(p)
            removed.append(p)
    try:
        import claude_agent_sdk

        return claude_agent_sdk
    finally:
        for p in reversed(removed):
            sys.path.insert(0, p)


class PersistentAgentSession:
    """Multi-turn persistent session for a squad agent.

    Wraps ClaudeSDKClient to provide:
    - Charter-based identity (system prompt from charter.md)
    - History loading (project-specific memory from history.md)
    - Multi-turn conversation within a cycle
    - Cost and turn tracking
    - Clean teardown with CLAUDECODE env var management

    Sessions are created per-cycle and torn down at cycle end.
    Agent learning persists via history.md files.
    """

    def __init__(
        self,
        role: str,
        charter_path: Path,
        history_path: Path | None = None,
        model: str = DEFAULT_MODEL,
        mcp_servers: dict | None = None,
    ) -> None:
        self.role = role
        self._charter_path = charter_path
        self._history_path = history_path
        self._model = model
        self._mcp_servers = mcp_servers
        self._client = None
        self._alive = False
        self._total_cost_usd = 0.0
        self._total_turns = 0
        self._session_id: str | None = None
        self._saved_claudecode: str | None = None
        self._work_dir: tempfile.TemporaryDirectory | None = None

    @property
    def is_alive(self) -> bool:
        return self._alive

    @property
    def total_cost_usd(self) -> float:
        return self._total_cost_usd

    @property
    def total_turns(self) -> int:
        return self._total_turns

    async def start(self, context_files: list[str] | None = None) -> None:
        """Start a new persistent session.

        Creates a ClaudeSDKClient, connects, then sends the charter
        + history + any context files as the initial message.
        Cleans up resources on failure to avoid env var and temp dir leaks.
        """
        if self._alive:
            logger.warning("Session %s already alive, skipping start", self.role)
            return

        try:
            # Remove CLAUDECODE to prevent nested SDK blocking
            self._saved_claudecode = os.environ.pop("CLAUDECODE", None)

            # Create temp working dir to avoid mcp/ shadowing
            self._work_dir = tempfile.TemporaryDirectory(prefix=f"squad-{self.role}-")

            self._client = self._create_client()
            await self._client.connect()

            # Build initial context message
            initial_msg = self._build_initial_message(context_files)
            await self._client.query(initial_msg)
            # Consume the response to the initial setup
            await self._collect_response()

            self._alive = True
            logger.info("Session %s started (model=%s)", self.role, self._model)
        except Exception:
            # Clean up on partial init failure
            await self._cleanup()
            raise

    async def query(self, message: str) -> AgentResult:
        """Send a message and get a response. Multi-turn within the session."""
        if not self._alive or self._client is None:
            raise RuntimeError(f"Session {self.role} is not alive. Call start() first.")

        await self._client.query(message)
        return await self._collect_response()

    async def stop(self) -> None:
        """Tear down the session. Handles CancelledError from disconnect()."""
        await self._cleanup()
        logger.info(
            "Session %s stopped (cost=$%.4f, turns=%d)",
            self.role,
            self._total_cost_usd,
            self._total_turns,
        )

    async def _cleanup(self) -> None:
        """Clean up session resources (client, temp dir, env var)."""
        if self._client is not None:
            try:
                await self._client.disconnect()
            except asyncio.CancelledError:
                logger.debug("CancelledError on disconnect for %s (expected)", self.role)
            except Exception:
                logger.exception("Error disconnecting session %s", self.role)
            self._client = None

        self._alive = False

        if self._work_dir is not None:
            try:
                self._work_dir.cleanup()
            except Exception:
                pass
            self._work_dir = None

        if self._saved_claudecode is not None:
            os.environ["CLAUDECODE"] = self._saved_claudecode
            self._saved_claudecode = None

    def _create_client(self):
        """Create a ClaudeSDKClient with appropriate options.

        If mcp_servers is provided, registers them so the session has
        access to custom tools alongside standard Claude Code tools.
        """
        sdk = _get_sdk()
        options = sdk.ClaudeAgentOptions(
            model=self._model,
            permission_mode="bypassPermissions",
            cwd=self._work_dir.name if self._work_dir else None,
        )
        if self._mcp_servers:
            options.mcp_servers = self._mcp_servers
        return sdk.ClaudeSDKClient(options=options)

    def _build_initial_message(self, context_files: list[str] | None = None) -> str:
        """Build the initial message containing charter, history, and context."""
        parts = []

        # Charter (identity)
        charter_text = self._charter_path.read_text()
        parts.append(f"# Your Charter\n\n{charter_text}")

        # History (project memory)
        if self._history_path and self._history_path.exists():
            history_text = self._history_path.read_text()
            if history_text.strip():
                parts.append(f"# Your History\n\n{history_text}")

        # Additional context files
        if context_files:
            for file_path in context_files:
                p = Path(file_path)
                if p.exists():
                    content = p.read_text()
                    parts.append(f"# Context: {p.name}\n\n{content}")
                else:
                    logger.warning("Context file not found: %s", file_path)

        return "\n\n---\n\n".join(parts)

    async def _collect_response(self) -> AgentResult:
        """Collect the full response from receive_response() iterator."""
        sdk = _get_sdk()
        output = ""
        transcript: list[dict] = []
        cost_usd = 0.0
        turns = 0
        session_id = self._session_id

        async for message in self._client.receive_response():
            if isinstance(message, sdk.ResultMessage):
                session_id = message.session_id
                cost_usd = message.total_cost_usd or 0.0
                turns = message.num_turns
                output = message.result or ""
            elif isinstance(message, sdk.AssistantMessage):
                for block in message.content:
                    if isinstance(block, sdk.TextBlock):
                        transcript.append(
                            {"role": "assistant", "type": "text", "content": block.text}
                        )
                    elif isinstance(block, sdk.ToolUseBlock):
                        transcript.append(
                            {
                                "role": "assistant",
                                "type": "tool_use",
                                "tool": block.name,
                                "input": block.input,
                                "id": block.id,
                            }
                        )

        self._session_id = session_id
        self._total_cost_usd += cost_usd
        self._total_turns += turns

        return AgentResult(
            output=output,
            cost_usd=cost_usd,
            turns=turns,
            transcript=transcript,
            session_id=session_id,
        )
