"""Tests for pre-deployment validation helper module."""

import re
import socket
import subprocess
from unittest.mock import MagicMock, patch

from ktrdr.cli.helpers.validation import validate_deployment_prerequisites


class TestValidateDeploymentPrerequisites:
    """Tests for validate_deployment_prerequisites function."""

    def test_all_checks_pass(self):
        """Test successful validation when all checks pass."""
        with (
            patch("socket.gethostbyname") as mock_dns,
            patch("subprocess.run") as mock_run,
        ):
            mock_dns.return_value = "192.168.1.100"
            mock_run.return_value = MagicMock(returncode=0)

            success, errors = validate_deployment_prerequisites("test.host.com")

            assert success is True
            assert errors == []

    def test_dns_resolution_failure(self):
        """Test error when DNS resolution fails."""
        with (
            patch("socket.gethostbyname") as mock_dns,
            patch("subprocess.run") as mock_run,
        ):
            mock_dns.side_effect = socket.gaierror("DNS lookup failed")
            mock_run.return_value = MagicMock(returncode=0)

            success, errors = validate_deployment_prerequisites("invalid.host.com")

            assert success is False
            assert any("DNS resolution failed" in e for e in errors)
            # Check error contains the hostname with word boundary (prevents partial matches)
            assert any(re.search(r"\binvalid\.host\.com\b", e) for e in errors)

    def test_ssh_connection_failure(self):
        """Test error when SSH connection fails."""
        with (
            patch("socket.gethostbyname") as mock_dns,
            patch("subprocess.run") as mock_run,
        ):
            mock_dns.return_value = "192.168.1.100"

            def run_side_effect(cmd, *args, **kwargs):
                if cmd[0] == "ssh" and "echo" in cmd:
                    return MagicMock(returncode=1)
                return MagicMock(returncode=0)

            mock_run.side_effect = run_side_effect

            success, errors = validate_deployment_prerequisites("test.host.com")

            assert success is False
            assert any("SSH connection failed" in e for e in errors)

    def test_ssh_timeout(self):
        """Test error when SSH connection times out."""
        with (
            patch("socket.gethostbyname") as mock_dns,
            patch("subprocess.run") as mock_run,
        ):
            mock_dns.return_value = "192.168.1.100"

            def run_side_effect(cmd, *args, **kwargs):
                if cmd[0] == "ssh" and "echo" in cmd:
                    raise subprocess.TimeoutExpired("ssh", 10)
                return MagicMock(returncode=0)

            mock_run.side_effect = run_side_effect

            success, errors = validate_deployment_prerequisites("test.host.com")

            assert success is False
            assert any("timed out" in e.lower() for e in errors)

    def test_docker_not_available(self):
        """Test error when Docker is not available on remote."""
        with (
            patch("socket.gethostbyname") as mock_dns,
            patch("subprocess.run") as mock_run,
        ):
            mock_dns.return_value = "192.168.1.100"

            def run_side_effect(cmd, *args, **kwargs):
                if "docker" in str(cmd) and "--version" in str(cmd):
                    return MagicMock(returncode=1)
                return MagicMock(returncode=0)

            mock_run.side_effect = run_side_effect

            success, errors = validate_deployment_prerequisites("test.host.com")

            assert success is False
            assert any("Docker not available" in e for e in errors)

    def test_op_cli_not_installed(self):
        """Test error when 1Password CLI is not installed locally."""
        with (
            patch("socket.gethostbyname") as mock_dns,
            patch("subprocess.run") as mock_run,
        ):
            mock_dns.return_value = "192.168.1.100"

            def run_side_effect(cmd, *args, **kwargs):
                if cmd[0] == "op" and "--version" in cmd:
                    raise FileNotFoundError()
                return MagicMock(returncode=0)

            mock_run.side_effect = run_side_effect

            success, errors = validate_deployment_prerequisites("test.host.com")

            assert success is False
            assert any("1Password CLI" in e and "not installed" in e for e in errors)

    def test_op_not_authenticated(self):
        """Test error when 1Password CLI is not authenticated."""
        with (
            patch("socket.gethostbyname") as mock_dns,
            patch("subprocess.run") as mock_run,
        ):
            mock_dns.return_value = "192.168.1.100"

            def run_side_effect(cmd, *args, **kwargs):
                if cmd[0] == "op" and "account" in cmd:
                    return MagicMock(returncode=1)
                return MagicMock(returncode=0)

            mock_run.side_effect = run_side_effect

            success, errors = validate_deployment_prerequisites("test.host.com")

            assert success is False
            assert any("not authenticated" in e.lower() for e in errors)

    def test_multiple_failures(self):
        """Test that multiple failures are collected."""
        with (
            patch("socket.gethostbyname") as mock_dns,
            patch("subprocess.run") as mock_run,
        ):
            mock_dns.side_effect = socket.gaierror("DNS lookup failed")

            def run_side_effect(cmd, *args, **kwargs):
                if cmd[0] == "op":
                    raise FileNotFoundError()
                return MagicMock(returncode=1)

            mock_run.side_effect = run_side_effect

            success, errors = validate_deployment_prerequisites("test.host.com")

            assert success is False
            assert len(errors) >= 2  # At least DNS and op CLI errors

    def test_returns_tuple(self):
        """Test that function returns correct tuple format."""
        with (
            patch("socket.gethostbyname") as mock_dns,
            patch("subprocess.run") as mock_run,
        ):
            mock_dns.return_value = "192.168.1.100"
            mock_run.return_value = MagicMock(returncode=0)

            result = validate_deployment_prerequisites("test.host.com")

            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], bool)
            assert isinstance(result[1], list)
