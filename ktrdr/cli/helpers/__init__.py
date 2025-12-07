"""CLI helper modules for deployment and operations."""

from ktrdr.cli.helpers.docker_utils import DockerError, docker_login_ghcr
from ktrdr.cli.helpers.git_utils import GitError, get_latest_sha_tag
from ktrdr.cli.helpers.secrets import (
    OnePasswordError,
    check_1password_authenticated,
    fetch_secrets_from_1password,
)
from ktrdr.cli.helpers.ssh_utils import SSHError, scp_file, ssh_exec_with_env
from ktrdr.cli.helpers.validation import validate_deployment_prerequisites

__all__ = [
    "DockerError",
    "GitError",
    "OnePasswordError",
    "SSHError",
    "check_1password_authenticated",
    "docker_login_ghcr",
    "fetch_secrets_from_1password",
    "get_latest_sha_tag",
    "scp_file",
    "ssh_exec_with_env",
    "validate_deployment_prerequisites",
]
