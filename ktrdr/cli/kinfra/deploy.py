"""Deployment commands for KTRDR pre-production environment.

This module provides CLI commands for deploying KTRDR services
to the homelab pre-production environment using 1Password for
secrets management.
"""

from pathlib import Path
from typing import Annotated

import typer

from ktrdr.cli.helpers import (
    docker_login_ghcr,
    fetch_secrets_from_1password,
    scp_file,
    ssh_exec_with_env,
    validate_deployment_prerequisites,
)

# Create the deploy app
deploy_app = typer.Typer(help="Deploy KTRDR services to pre-production environment")

# Constants
ONEPASSWORD_ITEM = "ktrdr-homelab-core"
GITHUB_USERNAME = "kpiteira"

# Host configurations - consistent naming throughout
HOSTS = {
    "core": {
        "host": "backend.ktrdr.home.mynerd.place",
        "workdir": "/opt/ktrdr-core",
        "compose_file": "docker-compose.core.yml",
    },
    "workers-b": {
        "host": "workers-b.ktrdr.home.mynerd.place",
        "workdir": "/opt/ktrdr-workers-b",
        "compose_file": "docker-compose.workers.yml",
    },
    "workers-c": {
        "host": "workers-c.ktrdr.home.mynerd.place",
        "workdir": "/opt/ktrdr-workers-c",
        "compose_file": "docker-compose.workers.yml",
    },
    "gpu": {
        "host": "ktrdr-gpuworker.ktrdr.home.mynerd.place",
        "workdir": "/opt/ktrdr-gpu-worker",
        "compose_file": "docker-compose.gpu-worker.yml",
    },
}


@deploy_app.command()
def core(
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show commands without executing")
    ] = False,
    skip_validation: Annotated[
        bool, typer.Option("--skip-validation", help="Skip prerequisite checks")
    ] = False,
    tag: Annotated[
        str, typer.Option("--tag", "-t", help="Image tag to deploy (default: latest)")
    ] = "latest",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v", help="Show detailed output from remote commands"
        ),
    ] = False,
):
    """Deploy core services (backend, db, observability)."""
    host_config = HOSTS["core"]
    host = host_config["host"]
    workdir = host_config["workdir"]
    compose_file = host_config["compose_file"]

    typer.echo("🚀 Deploying KTRDR Core Services")
    typer.echo(f"   Target: {host}")

    # Validate prerequisites
    if not skip_validation:
        typer.echo("\n📋 Validating prerequisites...")
        success, errors = validate_deployment_prerequisites(host)
        if not success:
            for error in errors:
                typer.echo(f"   ❌ {error}", err=True)
            raise typer.Abort() from None
        typer.echo("   ✅ All prerequisites validated")

    # Fetch secrets
    typer.echo("\n🔐 Fetching secrets from 1Password...")
    try:
        secrets = fetch_secrets_from_1password(ONEPASSWORD_ITEM)
    except Exception as e:
        typer.echo(f"   ❌ {e}", err=True)
        raise typer.Abort() from None
    typer.echo(f"   ✅ Retrieved {len(secrets)} secrets")

    # Use provided tag or default to latest
    image_tag = tag
    typer.echo(f"\n🏷️  Using image tag: {image_tag}")

    # Docker login
    typer.echo("\n🐳 Logging in to GHCR...")
    try:
        docker_login_ghcr(
            host=host,
            username=GITHUB_USERNAME,
            token=secrets.get("ghcr_token", ""),
            dry_run=dry_run,
        )
    except Exception as e:
        typer.echo(f"   ❌ {e}", err=True)
        raise typer.Abort() from None
    if not dry_run:
        typer.echo("   ✅ Logged in to ghcr.io")

    # Build environment variables
    env_vars = {
        "IMAGE_TAG": image_tag,
        "DB_NAME": "ktrdr",
        "DB_USER": secrets.get("db_username", ""),
        "DB_PASSWORD": secrets.get("db_password", ""),
        "JWT_SECRET": secrets.get("jwt_secret", ""),
        "GF_ADMIN_PASSWORD": secrets.get("grafana_password", ""),
    }

    # Deploy
    typer.echo("\n🚢 Deploying services...")
    try:
        ssh_exec_with_env(
            host=host,
            workdir=workdir,
            env_vars=env_vars,
            command=f"docker compose -f {compose_file} pull && docker compose -f {compose_file} up -d",
            dry_run=dry_run,
            verbose=verbose,
        )
    except Exception as e:
        typer.echo(f"   ❌ {e}", err=True)
        raise typer.Abort() from None

    if dry_run:
        typer.echo("\n✅ Dry run complete - no changes made")
    else:
        typer.echo("\n✅ Core services deployed successfully!")


@deploy_app.command()
def workers(
    target: Annotated[
        str,
        typer.Argument(help="Target: 'all', 'workers-b', 'workers-c', or 'gpu'"),
    ],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show commands without executing")
    ] = False,
    skip_validation: Annotated[
        bool, typer.Option("--skip-validation", help="Skip prerequisite checks")
    ] = False,
    tag: Annotated[
        str, typer.Option("--tag", "-t", help="Image tag to deploy (default: latest)")
    ] = "latest",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v", help="Show detailed output from remote commands"
        ),
    ] = False,
):
    """Deploy worker services (CPU and GPU)."""
    # Validate target
    valid_targets = ["all", "workers-b", "workers-c", "gpu"]
    if target not in valid_targets:
        typer.echo(
            f"❌ Invalid target: {target}. Must be one of: {', '.join(valid_targets)}",
            err=True,
        )
        raise typer.Abort() from None

    # Determine which workers to deploy
    if target == "all":
        worker_hosts = ["workers-b", "workers-c", "gpu"]
    else:
        worker_hosts = [target]

    typer.echo("🚀 Deploying KTRDR Worker Services")
    typer.echo(f"   Targets: {', '.join(worker_hosts)}")

    # Fetch secrets once
    typer.echo("\n🔐 Fetching secrets from 1Password...")
    try:
        secrets = fetch_secrets_from_1password(ONEPASSWORD_ITEM)
    except Exception as e:
        typer.echo(f"   ❌ {e}", err=True)
        raise typer.Abort() from None
    typer.echo(f"   ✅ Retrieved {len(secrets)} secrets")

    # Use provided tag
    image_tag = tag
    typer.echo(f"\n🏷️  Using image tag: {image_tag}")

    # Deploy to each worker host
    for worker_name in worker_hosts:
        host_config = HOSTS[worker_name]
        host = host_config["host"]
        workdir = host_config["workdir"]
        compose_file = host_config["compose_file"]

        typer.echo(f"\n📦 Deploying to {worker_name} ({host})...")

        # Validate prerequisites
        if not skip_validation:
            success, errors = validate_deployment_prerequisites(host)
            if not success:
                for error in errors:
                    typer.echo(f"   ❌ {error}", err=True)
                typer.echo(f"   ⚠️  Skipping {worker_name} due to validation errors")
                continue
            typer.echo("   ✅ Prerequisites validated")

        # Docker login
        try:
            docker_login_ghcr(
                host=host,
                username=GITHUB_USERNAME,
                token=secrets.get("ghcr_token", ""),
                dry_run=dry_run,
            )
        except Exception as e:
            typer.echo(f"   ❌ {e}", err=True)
            continue

        # Build environment variables (workers need DB credentials for checkpointing)
        env_vars = {
            "IMAGE_TAG": image_tag,
            "DB_USER": secrets.get("db_username", ""),
            "DB_PASSWORD": secrets.get("db_password", ""),
        }

        # Deploy
        try:
            ssh_exec_with_env(
                host=host,
                workdir=workdir,
                env_vars=env_vars,
                command=f"docker compose -f {compose_file} pull && docker compose -f {compose_file} up -d",
                dry_run=dry_run,
                verbose=verbose,
            )
            typer.echo(f"   ✅ {worker_name} deployed")
        except Exception as e:
            typer.echo(f"   ❌ {e}", err=True)
            continue

    if dry_run:
        typer.echo("\n✅ Dry run complete - no changes made")
    else:
        typer.echo("\n✅ Worker services deployed successfully!")


@deploy_app.command()
def status(
    target: Annotated[
        str, typer.Argument(help="Target: 'core', 'workers', 'gpu', or 'all'")
    ],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show commands without executing")
    ] = False,
):
    """Check deployment status."""
    # Validate target
    valid_targets = ["core", "workers", "gpu", "all"]
    if target not in valid_targets:
        typer.echo(
            f"❌ Invalid target: {target}. Must be one of: {', '.join(valid_targets)}",
            err=True,
        )
        raise typer.Abort() from None

    if target in ["core", "all"]:
        host = HOSTS["core"]["host"]
        workdir = HOSTS["core"]["workdir"]
        compose_file = HOSTS["core"]["compose_file"]
        typer.echo(f"\n📊 Core services status ({host}):")
        try:
            output = ssh_exec_with_env(
                host=host,
                workdir=workdir,
                env_vars={},
                command=f"docker compose -f {compose_file} ps --format 'table {{{{.Service}}}}\\t{{{{.Status}}}}'",
                dry_run=dry_run,
            )
            if output:
                typer.echo(output)
        except Exception as e:
            typer.echo(f"   ❌ {e}", err=True)

    if target in ["workers", "all"]:
        for worker_name in ["workers-b", "workers-c"]:
            host = HOSTS[worker_name]["host"]
            workdir = HOSTS[worker_name]["workdir"]
            compose_file = HOSTS[worker_name]["compose_file"]
            typer.echo(f"\n📊 {worker_name} status ({host}):")
            try:
                output = ssh_exec_with_env(
                    host=host,
                    workdir=workdir,
                    env_vars={},
                    command=f"docker compose -f {compose_file} ps --format 'table {{{{.Service}}}}\\t{{{{.Status}}}}'",
                    dry_run=dry_run,
                )
                if output:
                    typer.echo(output)
            except Exception as e:
                typer.echo(f"   ❌ {e}", err=True)

    if target in ["gpu", "all"]:
        host = HOSTS["gpu"]["host"]
        workdir = HOSTS["gpu"]["workdir"]
        compose_file = HOSTS["gpu"]["compose_file"]
        typer.echo(f"\n📊 GPU worker status ({host}):")
        try:
            output = ssh_exec_with_env(
                host=host,
                workdir=workdir,
                env_vars={},
                command=f"docker compose -f {compose_file} ps --format 'table {{{{.Service}}}}\\t{{{{.Status}}}}'",
                dry_run=dry_run,
            )
            if output:
                typer.echo(output)
        except Exception as e:
            typer.echo(f"   ❌ {e}", err=True)


# =============================================================================
# Patch Deployment - Fast local builds for preprod hotfixes
# =============================================================================

# Hosts to deploy patches to (excludes GPU worker - it needs CUDA)
PATCH_HOSTS = ["core", "workers-b", "workers-c"]
PATCH_TARBALL = "ktrdr-patch.tar.gz"
PATCH_IMAGE_TAG = "patch"


@deploy_app.command()
def patch(
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show commands without executing")
    ] = False,
    skip_validation: Annotated[
        bool, typer.Option("--skip-validation", help="Skip prerequisite checks")
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v", help="Show detailed output from remote commands"
        ),
    ] = False,
):
    """Deploy a locally-built patch image to preprod (core + workers).

    This command deploys a CPU-only patch image that was built locally
    using 'make docker-build-patch'. It's faster than the full CI/CD
    pipeline for quick iteration during debugging.

    The patch is deployed to:
      - core (backend, mcp)
      - workers-b (backtest + training workers)
      - workers-c (backtest + training workers)

    GPU worker is excluded as it requires CUDA.

    Usage:
        make docker-build-patch   # Build the patch image first
        make deploy-patch         # Deploy (calls this command)
    """
    # Check tarball exists
    tarball_path = Path(PATCH_TARBALL)
    if not tarball_path.exists():
        typer.echo(f"❌ Patch tarball not found: {PATCH_TARBALL}", err=True)
        typer.echo("   Run 'make docker-build-patch' first", err=True)
        raise typer.Abort() from None

    tarball_size = tarball_path.stat().st_size / (1024 * 1024)  # MB
    typer.echo("🔧 Deploying KTRDR Patch Image")
    typer.echo(f"   Tarball: {PATCH_TARBALL} ({tarball_size:.1f} MB)")
    typer.echo(f"   Targets: {', '.join(PATCH_HOSTS)}")

    # Fetch secrets (needed for DB credentials in compose)
    typer.echo("\n🔐 Fetching secrets from 1Password...")
    try:
        secrets = fetch_secrets_from_1password(ONEPASSWORD_ITEM)
    except Exception as e:
        typer.echo(f"   ❌ {e}", err=True)
        raise typer.Abort() from None
    typer.echo(f"   ✅ Retrieved {len(secrets)} secrets")

    # Deploy to each host
    success_count = 0
    for host_name in PATCH_HOSTS:
        host_config = HOSTS[host_name]
        host = host_config["host"]
        workdir = host_config["workdir"]
        compose_file = host_config["compose_file"]

        typer.echo(f"\n📦 Deploying to {host_name} ({host})...")

        # Validate prerequisites
        if not skip_validation:
            success, errors = validate_deployment_prerequisites(host)
            if not success:
                for error in errors:
                    typer.echo(f"   ❌ {error}", err=True)
                typer.echo(f"   ⚠️  Skipping {host_name} due to validation errors")
                continue
            typer.echo("   ✅ Prerequisites validated")

        # Step 1: Transfer tarball
        typer.echo(f"   📤 Transferring {PATCH_TARBALL}...")
        try:
            scp_file(
                local_path=tarball_path,
                host=host,
                remote_path=f"/tmp/{PATCH_TARBALL}",
                dry_run=dry_run,
            )
            if not dry_run:
                typer.echo("   ✅ Tarball transferred")
        except Exception as e:
            typer.echo(f"   ❌ Transfer failed: {e}", err=True)
            continue

        # Step 2: Load image
        typer.echo("   📥 Loading Docker image...")
        try:
            ssh_exec_with_env(
                host=host,
                workdir=workdir,
                env_vars={},
                command=f"gunzip -c /tmp/{PATCH_TARBALL} | docker load",
                dry_run=dry_run,
                verbose=verbose,
            )
            if not dry_run:
                typer.echo("   ✅ Image loaded")
        except Exception as e:
            typer.echo(f"   ❌ Load failed: {e}", err=True)
            continue

        # Step 3: Restart services with patch image
        typer.echo("   🔄 Restarting services...")

        # Build environment variables (same as regular deploy, but with patch tag)
        env_vars = {
            "IMAGE_TAG": PATCH_IMAGE_TAG,
            "DB_NAME": "ktrdr",
            "DB_USER": secrets.get("db_username", ""),
            "DB_PASSWORD": secrets.get("db_password", ""),
        }
        # Core needs additional secrets
        if host_name == "core":
            env_vars["JWT_SECRET"] = secrets.get("jwt_secret", "")
            env_vars["GF_ADMIN_PASSWORD"] = secrets.get("grafana_password", "")

        try:
            ssh_exec_with_env(
                host=host,
                workdir=workdir,
                env_vars=env_vars,
                command=f"docker compose -f {compose_file} up -d",
                dry_run=dry_run,
                verbose=verbose,
            )
            if not dry_run:
                typer.echo(f"   ✅ {host_name} restarted with patch")
            success_count += 1
        except Exception as e:
            typer.echo(f"   ❌ Restart failed: {e}", err=True)
            continue

        # Cleanup tarball on remote
        if not dry_run:
            try:
                ssh_exec_with_env(
                    host=host,
                    workdir="/tmp",
                    env_vars={},
                    command=f"rm -f {PATCH_TARBALL}",
                    dry_run=False,
                )
            except Exception:
                pass  # Ignore cleanup errors

    # Summary
    typer.echo("")
    if dry_run:
        typer.echo("✅ Dry run complete - no changes made")
    elif success_count == len(PATCH_HOSTS):
        typer.echo(f"✅ Patch deployed successfully to all {success_count} hosts!")
        typer.echo("")
        typer.echo("To verify:")
        typer.echo("  uv run ktrdr deploy status all")
    elif success_count > 0:
        typer.echo(
            f"⚠️  Patch deployed to {success_count}/{len(PATCH_HOSTS)} hosts (some failed)"
        )
    else:
        typer.echo("❌ Patch deployment failed on all hosts", err=True)
        raise typer.Abort() from None
