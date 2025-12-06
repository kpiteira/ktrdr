"""Deployment commands for KTRDR pre-production environment.

This module provides CLI commands for deploying KTRDR services
to the homelab pre-production environment using 1Password for
secrets management.
"""

from typing import Annotated

import typer

from ktrdr.cli.helpers import (
    docker_login_ghcr,
    fetch_secrets_from_1password,
    get_latest_sha_tag,
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
        typer.Argument(help="Target: 'all', 'workers-b', or 'workers-c'"),
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
):
    """Deploy CPU worker services."""
    # Validate target
    valid_targets = ["all", "workers-b", "workers-c"]
    if target not in valid_targets:
        typer.echo(
            f"❌ Invalid target: {target}. Must be one of: {', '.join(valid_targets)}",
            err=True,
        )
        raise typer.Abort() from None

    # Determine which workers to deploy
    if target == "all":
        worker_hosts = ["workers-b", "workers-c"]
    else:
        worker_hosts = [target]

    typer.echo("🚀 Deploying KTRDR CPU Worker Services")
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
            )
            typer.echo(f"   ✅ {worker_name} deployed")
        except Exception as e:
            typer.echo(f"   ❌ {e}", err=True)
            continue

    if dry_run:
        typer.echo("\n✅ Dry run complete - no changes made")
    else:
        typer.echo("\n✅ CPU worker services deployed successfully!")


@deploy_app.command()
def gpu(
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show commands without executing")
    ] = False,
    skip_validation: Annotated[
        bool, typer.Option("--skip-validation", help="Skip prerequisite checks")
    ] = False,
):
    """Deploy GPU worker service (training with GPU acceleration)."""
    host_config = HOSTS["gpu"]
    host = host_config["host"]
    workdir = host_config["workdir"]
    compose_file = host_config["compose_file"]

    typer.echo("🚀 Deploying KTRDR GPU Worker Service")
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

    # Get image tag
    typer.echo("\n🏷️  Getting image tag...")
    try:
        image_tag = get_latest_sha_tag()
    except Exception as e:
        typer.echo(f"   ❌ {e}", err=True)
        raise typer.Abort() from None
    typer.echo(f"   ✅ Using tag: {image_tag}")

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
        "DB_USER": secrets.get("db_username", ""),
        "DB_PASSWORD": secrets.get("db_password", ""),
    }

    # Deploy
    typer.echo("\n🚢 Deploying GPU worker...")
    try:
        ssh_exec_with_env(
            host=host,
            workdir=workdir,
            env_vars=env_vars,
            command=f"docker compose -f {compose_file} pull && docker compose -f {compose_file} up -d",
            dry_run=dry_run,
        )
    except Exception as e:
        typer.echo(f"   ❌ {e}", err=True)
        raise typer.Abort() from None

    if dry_run:
        typer.echo("\n✅ Dry run complete - no changes made")
    else:
        typer.echo("\n✅ GPU worker deployed successfully!")


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
