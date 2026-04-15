"""Transcript logging — persists every turn of every session to JSONL files.

Each session gets a file at {shared_dir}/loop/transcripts/{role}.jsonl.
Each line is a JSON object representing one query→response exchange.
This enables post-hoc analysis of what every agent did and why.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ktrdr import get_logger

logger = get_logger(__name__)


class TranscriptLogger:
    """Writes session transcripts to JSONL files.

    One file per role per loop run, stored at:
        {transcript_dir}/{role}.jsonl

    Each line records one query→response exchange with:
    - timestamp, role, query_num
    - The user message (query)
    - All response blocks (text + tool_use)
    - Cost and turn count for this exchange
    """

    def __init__(self, transcript_dir: Path | str) -> None:
        self._dir = Path(transcript_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def log_exchange(
        self,
        role: str,
        query_num: int,
        query: str,
        transcript: list[dict],
        cost_usd: float,
        turns: int,
    ) -> None:
        """Append one query→response exchange to the role's JSONL file."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "query_num": query_num,
            "query": query,
            "response": _summarize_transcript(transcript),
            "cost_usd": cost_usd,
            "turns": turns,
        }

        file_path = self._dir / f"{role}.jsonl"
        with open(file_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def log_tool_call(
        self,
        tool_name: str,
        tool_input: dict,
        tool_output: dict | str | None = None,
        role: str = "director",
    ) -> None:
        """Log a squad tool call (spawn_agent, validate, execute, cycle_complete)."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "type": "squad_tool_call",
            "tool": tool_name,
            "input": _safe_truncate(tool_input),
            "output": _safe_truncate(tool_output) if tool_output else None,
        }

        file_path = self._dir / f"{role}_tools.jsonl"
        with open(file_path, "a") as f:
            f.write(json.dumps(entry) + "\n")


def _summarize_transcript(transcript: list[dict]) -> list[dict]:
    """Summarize transcript blocks for logging.

    Keeps text blocks (truncated to 500 chars), and tool_use blocks
    with tool name + truncated input.
    """
    summary = []
    for block in transcript:
        if block.get("type") == "text":
            content = block.get("content", "")
            summary.append({
                "type": "text",
                "content": content[:500] + ("..." if len(content) > 500 else ""),
                "length": len(content),
            })
        elif block.get("type") == "tool_use":
            summary.append({
                "type": "tool_use",
                "tool": block.get("tool", "unknown"),
                "input_preview": _safe_truncate(block.get("input", {})),
            })
        else:
            summary.append(block)
    return summary


def _safe_truncate(obj, max_str_len: int = 200) -> dict | str | list | None:
    """Truncate string values in dicts/lists for readable logs."""
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj[:max_str_len] + ("..." if len(obj) > max_str_len else "")
    if isinstance(obj, dict):
        return {k: _safe_truncate(v, max_str_len) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe_truncate(item, max_str_len) for item in obj[:10]]
    return obj


def read_transcript(transcript_dir: Path | str, role: str) -> list[dict]:
    """Read all exchanges for a role from its JSONL file."""
    file_path = Path(transcript_dir) / f"{role}.jsonl"
    if not file_path.exists():
        return []

    entries = []
    for line in file_path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("Corrupt transcript line in %s", file_path)
    return entries


def read_tool_log(transcript_dir: Path | str, role: str = "director") -> list[dict]:
    """Read all squad tool calls for a role."""
    file_path = Path(transcript_dir) / f"{role}_tools.jsonl"
    if not file_path.exists():
        return []

    entries = []
    for line in file_path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("Corrupt tool log line in %s", file_path)
    return entries
