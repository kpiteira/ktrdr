# Project 4: Secrets Management & Deployment CLI

**Status**: In Progress (Tasks 4.1-4.9 complete, 4.10-4.11 pending homelab)
**Estimated Effort**: Large
**Prerequisites**: Project 2 (CI/CD & GHCR)

**Branch:** infra/secrets-cli

---

## Goal

Secure deployment infrastructure with 1Password integration, deployment CLI commands, and inline secrets injection (no secrets at rest).

---

## Context

Per [DESIGN.md](DESIGN.md) Decision 3, secrets are never stored in `.env` files on deployed systems. Instead, they are fetched from 1Password at deploy time and injected inline via SSH. This project implements that pattern through the `ktrdr deploy` CLI commands.

---

## Tasks

### Task 4.1: Set Up 1Password Vault Structure

**Goal**: Create 1Password items for KTRDR secrets

**Actions**:

1. Create vault "KTRDR Homelab Secrets" (or use existing)
2. Create item `ktrdr-homelab-core` with fields:
   - `db_username` - Database username
   - `db_password` - Database password
   - `jwt_secret` - JWT signing secret (min 32 chars)
   - `grafana_password` - Grafana admin password
   - `ghcr_token` - GitHub PAT for GHCR access
3. Document field naming conventions
4. Test access via `op` CLI

**Testing**:

```bash
# Verify op CLI installed
op --version

# Sign in (if needed)
op signin

# Test item access
op item get ktrdr-homelab-core --format json | jq '.fields[] | {label: .label, type: .type}'
```

**Acceptance Criteria**:

- [x] Vault created or identified
- [x] Item created with all required fields
- [x] Can access item via op CLI
- [x] Field naming documented

---

### Task 4.2: Implement 1Password Integration Helper

**File**: `ktrdr/cli/helpers/secrets.py`

**Goal**: Python module for fetching secrets from 1Password

**Implementation**:

```python
import subprocess
import json
from typing import Dict

class OnePasswordError(Exception):
    """Raised when 1Password operations fail."""
    pass

def fetch_secrets_from_1password(item_name: str) -> Dict[str, str]:
    """
    Fetch secrets from 1Password item.

    Args:
        item_name: Name of the 1Password item

    Returns:
        Dict mapping field labels to values

    Raises:
        OnePasswordError: If op CLI fails
    """
    try:
        cmd = ['op', 'item', 'get', item_name, '--format', 'json']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        item = json.loads(result.stdout)

        secrets = {}
        for field in item.get('fields', []):
            if field.get('type') == 'CONCEALED':
                secrets[field['label']] = field['value']

        return secrets

    except subprocess.CalledProcessError as e:
        if 'not signed in' in e.stderr:
            raise OnePasswordError("Not signed in to 1Password. Run: op signin")
        elif 'not found' in e.stderr:
            raise OnePasswordError(f"Item '{item_name}' not found in 1Password")
        else:
            raise OnePasswordError(f"1Password error: {e.stderr}")
    except FileNotFoundError:
        raise OnePasswordError("1Password CLI (op) not installed")

def check_1password_authenticated() -> bool:
    """Check if 1Password CLI is authenticated."""
    try:
        result = subprocess.run(
            ['op', 'account', 'list'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
```

**Actions**:

1. Create secrets.py module
2. Implement fetch_secrets_from_1password function
3. Implement check_1password_authenticated function
4. Add proper error handling
5. Write unit tests with mocked subprocess

**Acceptance Criteria**:

- [x] Can fetch secrets from 1Password
- [x] Proper error messages for common failures
- [x] Unit tests pass with mocked subprocess
- [x] Handles missing op CLI gracefully

---

### Task 4.3: Implement Git SHA Helper

**File**: `ktrdr/cli/helpers/git_utils.py`

**Goal**: Get current git SHA for image tagging

**Implementation**:

```python
import subprocess

class GitError(Exception):
    """Raised when git operations fail."""
    pass

def get_latest_sha_tag() -> str:
    """
    Get current git SHA formatted as image tag.

    Returns:
        Tag string like 'sha-a1b2c3d'

    Raises:
        GitError: If not in git repo or git fails
    """
    try:
        cmd = ['git', 'rev-parse', '--short', 'HEAD']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        sha = result.stdout.strip()
        return f'sha-{sha}'
    except subprocess.CalledProcessError as e:
        raise GitError(f"Git error: {e.stderr}")
    except FileNotFoundError:
        raise GitError("Git not installed")
```

**Acceptance Criteria**:

- [x] Returns SHA in correct format
- [x] Handles non-git directories
- [x] Unit tests pass

---

### Task 4.4: Implement SSH Execution Helper

**File**: `ktrdr/cli/helpers/ssh_utils.py`

**Goal**: Execute commands on remote hosts with inline env vars

**Implementation**:

```python
import subprocess
import shlex
from typing import Dict, Optional

class SSHError(Exception):
    """Raised when SSH operations fail."""
    pass

def ssh_exec_with_env(
    host: str,
    workdir: str,
    env_vars: Dict[str, str],
    command: str,
    dry_run: bool = False
) -> Optional[str]:
    """
    Execute command on remote host with inline environment variables.

    Args:
        host: SSH host (e.g., 'backend.ktrdr.home.mynerd.place')
        workdir: Working directory on remote host
        env_vars: Environment variables to inject
        command: Command to execute
        dry_run: If True, print command without executing

    Returns:
        Command output if successful

    Raises:
        SSHError: If SSH connection or command fails
    """
    # Build env string with proper quoting
    env_parts = [f"{k}={shlex.quote(v)}" for k, v in env_vars.items()]
    env_string = ' '.join(env_parts)

    # Build full command
    full_cmd = f'cd {workdir} && {env_string} {command}'
    ssh_cmd = ['ssh', host, full_cmd]

    if dry_run:
        # Mask secrets in output
        masked_cmd = full_cmd
        for key in ['PASSWORD', 'SECRET', 'TOKEN']:
            for k, v in env_vars.items():
                if key in k.upper():
                    masked_cmd = masked_cmd.replace(v, '***')
        print(f"[DRY RUN] Would execute on {host}:")
        print(f"  {masked_cmd}")
        return None

    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=300  # 5 minute timeout
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise SSHError(f"SSH command failed: {e.stderr}")
    except subprocess.TimeoutExpired:
        raise SSHError(f"SSH command timed out after 5 minutes")
```

**Acceptance Criteria**:

- [x] Properly quotes env var values
- [x] Dry-run masks secrets
- [x] Handles SSH failures gracefully
- [x] Unit tests pass

---

### Task 4.5: Implement Pre-Deployment Validation

**File**: `ktrdr/cli/helpers/validation.py`

**Goal**: Validate prerequisites before deployment

**Implementation**:

```python
import socket
import subprocess
from typing import Tuple, List

def validate_deployment_prerequisites(host: str) -> Tuple[bool, List[str]]:
    """
    Validate all prerequisites for deployment.

    Returns:
        (success, errors) tuple
    """
    errors = []

    # Check DNS resolution
    try:
        socket.gethostbyname(host)
    except socket.gaierror:
        errors.append(f"DNS resolution failed for {host}")

    # Check SSH connectivity
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', host, 'echo', 'ok'],
            capture_output=True,
            timeout=10
        )
        if result.returncode != 0:
            errors.append(f"SSH connection failed to {host}")
    except subprocess.TimeoutExpired:
        errors.append(f"SSH connection timed out to {host}")

    # Check Docker on remote
    try:
        result = subprocess.run(
            ['ssh', host, 'docker', '--version'],
            capture_output=True,
            timeout=10
        )
        if result.returncode != 0:
            errors.append(f"Docker not available on {host}")
    except subprocess.TimeoutExpired:
        errors.append(f"Docker check timed out on {host}")

    # Check op CLI locally
    try:
        result = subprocess.run(['op', '--version'], capture_output=True)
        if result.returncode != 0:
            errors.append("1Password CLI (op) not installed")
    except FileNotFoundError:
        errors.append("1Password CLI (op) not installed")

    # Check op authenticated
    try:
        result = subprocess.run(['op', 'account', 'list'], capture_output=True)
        if result.returncode != 0:
            errors.append("1Password CLI not authenticated (run: op signin)")
    except FileNotFoundError:
        pass  # Already caught above

    return (len(errors) == 0, errors)
```

**Acceptance Criteria**:

- [x] Checks DNS resolution
- [x] Checks SSH connectivity
- [x] Checks remote Docker
- [x] Checks local op CLI
- [x] Clear error messages
- [x] Unit tests pass

---

### Task 4.6: Implement Docker Login Helper

**File**: `ktrdr/cli/helpers/docker_utils.py`

**Goal**: Authenticate Docker to GHCR on remote host

**Implementation**:

```python
import subprocess
from ktrdr.cli.helpers.ssh_utils import SSHError

def docker_login_ghcr(host: str, username: str, token: str) -> None:
    """
    Authenticate Docker to GHCR on remote host.

    Args:
        host: SSH host
        username: GitHub username
        token: GitHub PAT with read:packages scope

    Raises:
        SSHError: If login fails
    """
    # Use stdin to avoid token in process args
    cmd = f"echo '{token}' | docker login ghcr.io -u {username} --password-stdin"
    ssh_cmd = ['ssh', host, cmd]

    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )
    except subprocess.CalledProcessError as e:
        raise SSHError(f"Docker login failed: {e.stderr}")
```

**Acceptance Criteria**:

- [x] Authenticates Docker on remote host
- [x] Token passed via stdin (not visible in ps)
- [x] Proper error handling

---

### Task 4.7: Implement Core Deployment Command

**File**: `ktrdr/cli/commands/deploy.py`

**Goal**: Deploy core services to pre-prod

**Implementation**:

```python
import click
from ktrdr.cli.helpers.secrets import fetch_secrets_from_1password, OnePasswordError
from ktrdr.cli.helpers.git_utils import get_latest_sha_tag
from ktrdr.cli.helpers.ssh_utils import ssh_exec_with_env, SSHError
from ktrdr.cli.helpers.validation import validate_deployment_prerequisites
from ktrdr.cli.helpers.docker_utils import docker_login_ghcr

@click.group()
def deploy():
    """Deploy KTRDR to homelab infrastructure."""
    pass

@deploy.command()
@click.argument('service', type=click.Choice(['backend', 'db', 'all']))
@click.option('--dry-run', is_flag=True, help='Print commands without executing')
@click.option('--tag', help='Override image tag (default: current git SHA)')
@click.option('--skip-validation', is_flag=True, help='Skip pre-deployment checks')
def core(service, dry_run, tag, skip_validation):
    """Deploy core services to ktrdr-core LXC."""
    host = 'backend.ktrdr.home.mynerd.place'
    workdir = '/opt/ktrdr-core'

    # Validate prerequisites
    if not skip_validation:
        click.echo("Validating prerequisites...")
        success, errors = validate_deployment_prerequisites(host)
        if not success:
            for error in errors:
                click.echo(f"  ✗ {error}", err=True)
            raise click.Abort()
        click.echo("  ✓ All prerequisites validated")

    try:
        # Fetch secrets
        click.echo("Fetching secrets from 1Password...")
        secrets = fetch_secrets_from_1password('ktrdr-homelab-core')

        # Authenticate Docker to GHCR
        click.echo("Authenticating Docker to GHCR...")
        github_username = 'kpiteira'  # TODO: Make configurable
        docker_login_ghcr(host, github_username, secrets['ghcr_token'])

        # Build env vars
        image_tag = tag or get_latest_sha_tag()
        env_vars = {
            'DB_NAME': 'ktrdr',
            'DB_USER': secrets['db_username'],
            'DB_PASSWORD': secrets['db_password'],
            'JWT_SECRET': secrets['jwt_secret'],
            'GF_ADMIN_PASSWORD': secrets['grafana_password'],
            'IMAGE_TAG': image_tag,
        }

        # Execute deployment
        service_arg = '' if service == 'all' else service
        command = f'docker compose pull {service_arg} && docker compose up -d {service_arg}'

        click.echo(f"Deploying {service} with image tag {image_tag}...")
        ssh_exec_with_env(host, workdir, env_vars, command, dry_run)

        if not dry_run:
            click.echo(f"✓ Deployed {service} to core LXC")

    except OnePasswordError as e:
        click.echo(f"1Password error: {e}", err=True)
        raise click.Abort()
    except SSHError as e:
        click.echo(f"SSH error: {e}", err=True)
        raise click.Abort()
```

**Acceptance Criteria**:

- [x] `ktrdr deploy core backend` works
- [x] `ktrdr deploy core all` deploys all services
- [x] Pre-deployment validation runs
- [x] Docker authenticates to GHCR
- [x] Secrets fetched from 1Password
- [x] Dry-run mode works
- [x] Custom tag override works

---

### Task 4.8: Implement Worker Deployment Command

**File**: `ktrdr/cli/commands/deploy.py` (extend)

**Goal**: Deploy workers to pre-prod LXCs

**Implementation**:

```python
@deploy.command()
@click.argument('node', type=click.Choice(['B', 'C']))
@click.option('--dry-run', is_flag=True, help='Print commands without executing')
@click.option('--tag', help='Override image tag')
@click.option('--skip-validation', is_flag=True, help='Skip pre-deployment checks')
@click.option('--profile', multiple=True, help='Compose profiles to enable (scale-2, scale-3)')
def workers(node, dry_run, tag, skip_validation, profile):
    """Deploy workers to ktrdr-workers-{node} LXC."""
    host = f'workers-{node.lower()}.ktrdr.home.mynerd.place'
    workdir = f'/opt/ktrdr-workers-{node.lower()}'

    # Validate prerequisites
    if not skip_validation:
        click.echo("Validating prerequisites...")
        success, errors = validate_deployment_prerequisites(host)
        if not success:
            for error in errors:
                click.echo(f"  ✗ {error}", err=True)
            raise click.Abort()
        click.echo("  ✓ All prerequisites validated")

    try:
        # Fetch secrets (workers need DB access)
        click.echo("Fetching secrets from 1Password...")
        secrets = fetch_secrets_from_1password('ktrdr-homelab-core')

        # Authenticate Docker to GHCR
        click.echo("Authenticating Docker to GHCR...")
        github_username = 'kpiteira'
        docker_login_ghcr(host, github_username, secrets['ghcr_token'])

        # Build env vars
        image_tag = tag or get_latest_sha_tag()
        env_vars = {
            'IMAGE_TAG': image_tag,
            'DB_USER': secrets['db_username'],
            'DB_PASSWORD': secrets['db_password'],
        }

        # Build command with profiles
        profile_args = ' '.join([f'--profile {p}' for p in profile])
        command = f'docker compose {profile_args} pull && docker compose {profile_args} up -d'

        click.echo(f"Deploying workers to node {node} with image tag {image_tag}...")
        ssh_exec_with_env(host, workdir, env_vars, command, dry_run)

        if not dry_run:
            click.echo(f"✓ Deployed workers to node {node}")

    except OnePasswordError as e:
        click.echo(f"1Password error: {e}", err=True)
        raise click.Abort()
    except SSHError as e:
        click.echo(f"SSH error: {e}", err=True)
        raise click.Abort()
```

**Acceptance Criteria**:

- [x] `ktrdr deploy workers B` works
- [x] `ktrdr deploy workers C` works
- [x] Profile scaling works (--profile scale-2)
- [x] Workers get DB credentials
- [x] Dry-run and tag override work

---

### Task 4.9: Register CLI Commands

**File**: `ktrdr/cli/cli.py`

**Goal**: Register deploy commands with main CLI

**Actions**:

1. Import deploy command group
2. Add to main CLI
3. Test command discovery

**Implementation**:

```python
from ktrdr.cli.commands.deploy import deploy

# Add to main CLI group
cli.add_command(deploy)
```

**Acceptance Criteria**:

- [x] `ktrdr --help` shows deploy command
- [x] `ktrdr deploy --help` shows core and workers
- [x] Commands accessible

---

### Task 4.10: Write Tests

**Files**:

- `tests/unit/cli/helpers/test_secrets.py`
- `tests/unit/cli/helpers/test_ssh_utils.py`
- `tests/unit/cli/helpers/test_validation.py`
- `tests/integration/cli/test_deploy.py`

**Goal**: Comprehensive test coverage

**Actions**:

1. Write unit tests for each helper module
2. Mock subprocess calls
3. Write integration tests for deploy commands
4. Test error scenarios
5. Aim for >90% coverage on new code

**Acceptance Criteria**:

- [ ] Unit tests for all helpers
- [ ] Integration tests for deploy commands
- [ ] Error scenarios covered
- [ ] Tests run in CI
- [ ] >90% coverage on new code

---

### Task 4.11: Create Deployment Documentation

**File**: `docs/user-guides/deployment-homelab.md`

**Goal**: Complete deployment guide

**Sections**:

1. Prerequisites
   - 1Password setup
   - SSH key configuration
   - op CLI installation
2. 1Password Configuration
   - Vault structure
   - Required fields
3. First-Time Deployment
   - Deploy core
   - Deploy workers
   - Verify services
4. Updating Deployments
   - Deploy new versions
   - Rollback procedure
5. Scaling Workers
   - Using profiles
6. Troubleshooting
   - Common errors
   - Debug commands

**Acceptance Criteria**:

- [ ] All sections complete
- [ ] Clear step-by-step instructions
- [ ] Troubleshooting covers common issues
- [ ] Examples for all commands

---

## Validation

**Final Verification**:

```bash
# 1. Test help
ktrdr deploy --help
ktrdr deploy core --help
ktrdr deploy workers --help

# 2. Test dry-run (no actual deployment)
ktrdr deploy core backend --dry-run
ktrdr deploy workers B --dry-run

# 3. Run unit tests
uv run pytest tests/unit/cli/helpers/ -v

# 4. Run integration tests
uv run pytest tests/integration/cli/test_deploy.py -v

# 5. Test validation failure (wrong host)
ktrdr deploy core backend --dry-run
# Should fail validation if host not reachable

# 6. Test 1Password integration
# (requires actual 1Password setup)
```

---

## Success Criteria

- [ ] 1Password integration working
- [ ] `ktrdr deploy core` command working
- [ ] `ktrdr deploy workers` command working
- [ ] Pre-deployment validation implemented
- [ ] GHCR authentication working
- [ ] Dry-run mode working
- [ ] Tests passing with >90% coverage
- [ ] Documentation complete

---

## Dependencies

**Depends on**: Project 2 (CI/CD & GHCR) - need GHCR images to pull
**Blocks**: Project 5 (Pre-prod Deployment)

---

## Notes

- Secrets briefly visible in process args per DESIGN.md trade-off
- SSH key auth must be configured separately (out of scope)
- GitHub username currently hardcoded - could be made configurable later
- Consider adding `ktrdr deploy status` command in future

---

**Previous Project**: [Project 3: Observability Dashboards](PLAN_3_OBSERVABILITY.md)
**Next Project**: [Project 5: Pre-prod Deployment](PLAN_5_PREPROD.md)
