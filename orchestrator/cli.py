"""CLI for the Orchestrator.

Provides command-line interface for autonomous task execution.
"""

import click


@click.group()
@click.version_option(package_name="orchestrator")
def cli() -> None:
    """Orchestrator - Autonomous task execution for KTRDR."""
    pass


def main() -> None:
    """Main entry point for the orchestrator CLI."""
    cli()


if __name__ == "__main__":
    main()
