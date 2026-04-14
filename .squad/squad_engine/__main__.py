"""CLI entry point: python -m squad_engine

Runs the squad loop with default settings, or via .squad/run_v2.sh wrapper.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from ktrdr import get_logger

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Squad v2 loop runner")
    parser.add_argument(
        "--max-iterations", type=int, default=20,
        help="Maximum iterations before stopping (default: 20)",
    )
    parser.add_argument(
        "--synthesis-interval", type=int, default=10,
        help="Run synthesis every N cycles (default: 10, 0 to disable periodic synthesis)",
    )
    parser.add_argument(
        "--shared-dir", type=str, default=None,
        help="Override shared directory (default: ~/.ktrdr/shared/squad)",
    )
    parser.add_argument(
        "--charter-dir", type=str, default=None,
        help="Override charter directory (default: .squad/agents)",
    )
    args = parser.parse_args()

    from squad_engine.loop_runner import run_loop

    result = asyncio.run(
        run_loop(
            shared_dir=args.shared_dir,
            charter_dir=args.charter_dir,
            max_iterations=args.max_iterations,
            synthesis_interval=args.synthesis_interval,
        )
    )

    logger.info(
        "Loop finished: status=%s, iterations=%d, experiments=%d, cost=$%.2f",
        result.status,
        result.iterations_run,
        result.experiments_completed,
        result.total_cost_usd,
    )

    # Exit with appropriate code
    if result.status in ("completed", "max_iterations", "paused"):
        sys.exit(0)
    elif result.status == "interrupted":
        sys.exit(130)  # Standard SIGINT exit code
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
