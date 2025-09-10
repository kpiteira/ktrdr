# filepath: /Users/karl/Documents/dev/ktrdr2/scripts/build_prompt.py
"""
Assemble a self‑contained prompt for "Implement task X.Y".

Usage:
    python build_prompt.py 1.5 | pbcopy   # macOS: copies prompt to clipboard
"""

import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "specification"
TASK_FILE = SPEC / "ktrdr_phase1_task_breakdown_v2.md"
DIR_FILE = SPEC / "ai_director.md"
ARCH_FILE = SPEC / "ktrdr-architecture-blueprint.md"
REQ_FILE = SPEC / "ktrdr_product_requirements_v2.md"


def slice_task(task_code: str) -> str:
    block, capture = [], False
    for line in TASK_FILE.read_text().splitlines():
        if task_code in line:
            capture = True
        if capture:
            block.append(line)
            # stop on the first blank line **after** we’ve collected ≥5 lines
            if line.strip() == "" and len(block) >= 5:
                break
    return "\n".join(block)


def head(path: Path, max_chars: int = 7500) -> str:
    """Return the first *max_chars* characters (≈ token‑safe)."""
    return path.read_text()[:max_chars]


def copy_to_clipboard(text: str) -> None:
    """
    Copy *text* to clipboard on macOS (uses pbcopy).
    Falls back to printing if pbcopy is not available.
    """
    try:
        subprocess.run(["pbcopy"], input=text.encode(), check=True)
        print("✅ Prompt copied to clipboard.")
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("⚠️  pbcopy unavailable ‑‑ prompt printed below:\n")
        print(text)


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Usage: build_prompt.py <task‑code>  [--print]")

    task = sys.argv[1]
    force_print = "--print" in sys.argv[2:]

    prompt = textwrap.dedent(
        f"""
    ### SYSTEM
    {head(DIR_FILE)}

    ### USER
    {slice_task(task)}

    # Relevant architecture (truncated)
    {head(ARCH_FILE, 2000)}

    # Relevant requirements (truncated)
    {head(REQ_FILE, 2000)}

    ### ASSISTANT
    (awaiting PLAN)
    """
    ).strip()

    # copy to clipboard unless user explicitly asks for --print
    if force_print:
        print(prompt)
    else:
        copy_to_clipboard(prompt)


if __name__ == "__main__":
    main()
