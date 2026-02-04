"""Workers command implementation.

Implements the `ktrdr workers` command that displays worker status.

PERFORMANCE NOTE: Heavy imports (AsyncCLIClient, Console, Table) are deferred
inside the function body to keep CLI startup fast.
"""

import typer

from ktrdr.cli.telemetry import trace_cli_command


@trace_cli_command("workers")
def workers(ctx: typer.Context) -> None:
    """Show available workers and their status.

    Displays a table of all registered workers with their type, status,
    GPU capability, endpoint, and current operation.

    Examples:
        ktrdr workers              # Table output

        ktrdr --json workers       # JSON output
    """
    # Lazy imports for fast CLI startup
    import asyncio
    import json

    from rich.console import Console
    from rich.table import Table

    from ktrdr.cli.client import AsyncCLIClient
    from ktrdr.cli.output import print_error
    from ktrdr.cli.state import CLIState

    state: CLIState = ctx.obj
    console = Console()

    async def _fetch_workers() -> list:
        """Fetch workers from the API."""
        async with AsyncCLIClient() as client:
            result = await client.get("/workers")
            # Workers endpoint returns list directly
            return result if isinstance(result, list) else []

    try:
        workers_list = asyncio.run(_fetch_workers())

        if state.json_mode:
            print(json.dumps(workers_list))
        else:
            if not workers_list:
                console.print("No workers registered")
                return

            table = Table(title="Workers")
            table.add_column("TYPE", style="cyan")
            table.add_column("STATUS", style="green")
            table.add_column("GPU")
            table.add_column("ENDPOINT")
            table.add_column("OPERATION")

            for worker in workers_list:
                worker_type = worker.get("worker_type", "-")
                status = worker.get("status", "-")
                capabilities = worker.get("capabilities", {})
                gpu = capabilities.get("gpu_type") or "-"
                endpoint = worker.get("endpoint_url", "-")
                # Shorten endpoint if too long
                if len(endpoint) > 30:
                    endpoint = endpoint[:27] + "..."
                operation = worker.get("current_operation_id") or "-"

                table.add_row(worker_type, status, gpu, endpoint, operation)

            console.print(table)

    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None
