"""Impl worktree command for kinfra.

Creates git worktrees for implementation work and claims a sandbox slot.
"""

import subprocess
from pathlib import Path

import typer

from ktrdr.cli.sandbox_registry import load_registry

impl_app = typer.Typer(
    name="impl",
    help="Create impl worktree with sandbox slot",
)


def _is_git_repo(path: Path) -> bool:
    """Check if path is inside a git repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        cwd=path,
    )
    return result.returncode == 0


def _parse_feature_milestone(value: str) -> tuple[str, str]:
    """Parse 'feature/milestone' into (feature, milestone).

    Args:
        value: String in format "feature/milestone"

    Returns:
        Tuple of (feature_name, milestone_name)

    Raises:
        ValueError: If format is invalid (no slash)
    """
    if "/" not in value:
        raise ValueError(f"Expected format: feature/milestone, got: {value}")
    parts = value.split("/", 1)
    return parts[0], parts[1]


def _find_milestone_file(
    feature: str, milestone: str, base_path: Path | None = None
) -> Path | None:
    """Find milestone file in docs/designs/<feature>/implementation/.

    Args:
        feature: Feature name (e.g., "genome")
        milestone: Milestone identifier (e.g., "M1")
        base_path: Base path to search from (defaults to cwd)

    Returns:
        Path to milestone file if found, None otherwise
    """
    if base_path is None:
        base_path = Path.cwd()

    impl_dir = base_path / "docs" / "designs" / feature / "implementation"
    if not impl_dir.exists():
        return None

    # Look for M<N>_*.md pattern (case-insensitive for milestone prefix)
    for pattern in [
        f"{milestone}_*.md",
        f"{milestone.upper()}_*.md",
        f"{milestone.lower()}_*.md",
    ]:
        for f in impl_dir.glob(pattern):
            return f

    return None


@impl_app.callback(invoke_without_command=True)
def impl(
    feature_milestone: str = typer.Argument(
        ..., help="Feature/milestone (e.g., genome/M1)"
    ),
    profile: str = typer.Option(
        "light",
        "--profile",
        "-p",
        help="Minimum worker profile (light/standard/heavy)",
    ),
) -> None:
    """Create impl worktree and claim sandbox slot.

    Creates a git worktree at ../ktrdr-impl-<feature>-<milestone>/ and claims
    an available sandbox slot. Generates docker-compose.override.yml and
    starts containers.
    """
    # Import here to allow mocking
    from ktrdr.cli.kinfra.override import generate_override
    from ktrdr.cli.kinfra.slots import start_slot_containers

    repo_root = Path.cwd()

    # Validate we're in a git repository
    if not _is_git_repo(repo_root):
        typer.secho(
            "Error: Not in a git repository. Run this command from the repo root.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # 1. Parse feature/milestone
    try:
        feature, milestone = _parse_feature_milestone(feature_milestone)
    except ValueError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None

    # 2. Find milestone file
    milestone_file = _find_milestone_file(feature, milestone)
    if not milestone_file:
        typer.secho(
            f"Error: No milestone matching '{milestone}' found in "
            f"docs/designs/{feature}/implementation/",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # 3. Check slot availability FIRST (GAP-6: fail fast)
    registry = load_registry()
    slot = registry.get_available_slot(min_profile=profile)
    if not slot:
        typer.secho(
            "Error: All 6 slots in use. Run `kinfra worktrees` to see active worktrees.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # 4. Define worktree path and check if exists
    worktree_name = f"ktrdr-impl-{feature}-{milestone}"
    worktree_path = repo_root.parent / worktree_name
    branch_name = f"impl/{feature}-{milestone}"

    if worktree_path.exists():
        typer.secho(
            f"Error: Worktree {worktree_name} already exists at {worktree_path}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # 5. Check if branch exists
    result = subprocess.run(
        ["git", "branch", "--list", branch_name],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    branch_exists = bool(result.stdout.strip())

    # 6. Create worktree
    try:
        if branch_exists:
            subprocess.run(
                ["git", "worktree", "add", str(worktree_path), branch_name],
                check=True,
                cwd=repo_root,
            )
        else:
            subprocess.run(
                ["git", "worktree", "add", "-b", branch_name, str(worktree_path)],
                check=True,
                cwd=repo_root,
            )
    except subprocess.CalledProcessError:
        typer.secho("Error: Failed to create git worktree.", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None

    typer.echo(f"Created worktree at {worktree_path}")

    # 7. Claim slot and start containers
    try:
        registry.claim_slot(slot.slot_id, worktree_path)
        typer.echo(f"Claimed slot {slot.slot_id} ({slot.profile})")

        generate_override(slot, worktree_path)
        typer.echo("Generated docker-compose.override.yml")

        start_slot_containers(slot)
        typer.echo(f"Started containers (API: http://localhost:{slot.ports['api']})")

    except Exception as e:
        # GAP-7: Release slot, keep worktree
        typer.secho(f"Error starting sandbox: {e}", fg=typer.colors.RED, err=True)
        registry.release_slot(slot.slot_id)
        typer.secho(
            f"Slot released. Worktree kept at {worktree_path}. "
            f"Fix issue and run `kinfra sandbox up`.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(code=1) from None

    typer.echo(f"\nReady! cd {worktree_path}")
