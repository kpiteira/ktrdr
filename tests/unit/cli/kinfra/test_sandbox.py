"""Tests for kinfra sandbox commands.

Tests that sandbox commands are registered under kinfra and work correctly.
"""


class TestKinfraSandboxRegistration:
    """Tests that sandbox subcommands are registered under kinfra."""

    def test_sandbox_subgroup_registered(self, runner) -> None:
        """kinfra --help should show sandbox subcommand."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "sandbox" in result.output.lower()

    def test_sandbox_help_works(self, runner) -> None:
        """kinfra sandbox --help should return without error."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["sandbox", "--help"])
        assert result.exit_code == 0

    def test_sandbox_help_shows_subcommands(self, runner) -> None:
        """kinfra sandbox --help should list available commands."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["sandbox", "--help"])
        assert result.exit_code == 0
        help_lower = result.output.lower()
        # Should have key subcommands
        assert "status" in help_lower
        assert "list" in help_lower
        assert "up" in help_lower
        assert "down" in help_lower


class TestKinfraSandboxStatusCommand:
    """Tests for kinfra sandbox status command."""

    def test_status_command_exists(self, runner) -> None:
        """kinfra sandbox status --help should work."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["sandbox", "status", "--help"])
        assert result.exit_code == 0


class TestKinfraSandboxListCommand:
    """Tests for kinfra sandbox list command."""

    def test_list_command_exists(self, runner) -> None:
        """kinfra sandbox list --help should work."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["sandbox", "list", "--help"])
        assert result.exit_code == 0


# =============================================================================
# Provision Command Tests
# =============================================================================


class TestProvisionCommand:
    """Tests for kinfra sandbox provision command."""

    def test_provision_command_exists(self, runner) -> None:
        """kinfra sandbox provision --help should work."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["sandbox", "provision", "--help"])
        assert result.exit_code == 0
        assert "dry-run" in result.output.lower()

    def test_provision_dry_run_no_files_created(
        self, runner, tmp_path, monkeypatch
    ) -> None:
        """--dry-run shows what would be created without creating files."""
        from ktrdr.cli.kinfra.main import app

        # Use temp directory as sandboxes base
        sandboxes_path = tmp_path / "sandboxes"
        monkeypatch.setattr("ktrdr.cli.kinfra.sandbox.SANDBOXES_DIR", sandboxes_path)

        result = runner.invoke(app, ["sandbox", "provision", "--dry-run"])
        assert result.exit_code == 0
        assert "would create" in result.output.lower()
        # No directories should be created
        assert not sandboxes_path.exists()

    def test_provision_creates_six_slots(self, runner, tmp_path, monkeypatch) -> None:
        """provision creates 6 slot directories."""
        from ktrdr.cli.kinfra.main import app

        sandboxes_path = tmp_path / "sandboxes"
        monkeypatch.setattr("ktrdr.cli.kinfra.sandbox.SANDBOXES_DIR", sandboxes_path)
        # Also mock registry path to avoid polluting real registry
        registry_path = tmp_path / "registry.json"
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_FILE", registry_path)
        registry_dir = tmp_path
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_DIR", registry_dir)

        result = runner.invoke(app, ["sandbox", "provision"])
        assert result.exit_code == 0

        # All 6 slots should exist
        for slot_id in range(1, 7):
            slot_path = sandboxes_path / f"slot-{slot_id}"
            assert slot_path.exists(), f"Slot {slot_id} directory not created"

    def test_provision_idempotent(self, runner, tmp_path, monkeypatch) -> None:
        """Running provision twice doesn't overwrite existing slots."""
        from ktrdr.cli.kinfra.main import app

        sandboxes_path = tmp_path / "sandboxes"
        monkeypatch.setattr("ktrdr.cli.kinfra.sandbox.SANDBOXES_DIR", sandboxes_path)
        registry_path = tmp_path / "registry.json"
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_FILE", registry_path)
        registry_dir = tmp_path
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_DIR", registry_dir)

        # First run
        result1 = runner.invoke(app, ["sandbox", "provision"])
        assert result1.exit_code == 0

        # Create a marker file in slot-1
        marker = sandboxes_path / "slot-1" / "marker.txt"
        marker.write_text("original")

        # Second run
        result2 = runner.invoke(app, ["sandbox", "provision"])
        assert result2.exit_code == 0
        assert "already exists" in result2.output.lower()

        # Marker should still exist (not overwritten)
        assert marker.read_text() == "original"

    def test_provision_slot_profiles_correct(
        self, runner, tmp_path, monkeypatch
    ) -> None:
        """Slots have correct profiles: 1-4 light, 5 standard, 6 heavy."""
        from ktrdr.cli.kinfra.main import app
        from ktrdr.cli.sandbox_registry import load_registry

        sandboxes_path = tmp_path / "sandboxes"
        monkeypatch.setattr("ktrdr.cli.kinfra.sandbox.SANDBOXES_DIR", sandboxes_path)
        registry_path = tmp_path / "registry.json"
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_FILE", registry_path)
        registry_dir = tmp_path
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_DIR", registry_dir)

        result = runner.invoke(app, ["sandbox", "provision"])
        assert result.exit_code == 0

        # Check registry for profiles
        registry = load_registry()
        assert registry.slots["1"].profile == "light"
        assert registry.slots["2"].profile == "light"
        assert registry.slots["3"].profile == "light"
        assert registry.slots["4"].profile == "light"
        assert registry.slots["5"].profile == "standard"
        assert registry.slots["6"].profile == "heavy"

    def test_provision_port_allocation(self, runner, tmp_path, monkeypatch) -> None:
        """Slots have correct port allocations."""
        from ktrdr.cli.kinfra.main import app
        from ktrdr.cli.sandbox_registry import load_registry

        sandboxes_path = tmp_path / "sandboxes"
        monkeypatch.setattr("ktrdr.cli.kinfra.sandbox.SANDBOXES_DIR", sandboxes_path)
        registry_path = tmp_path / "registry.json"
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_FILE", registry_path)
        registry_dir = tmp_path
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_DIR", registry_dir)

        result = runner.invoke(app, ["sandbox", "provision"])
        assert result.exit_code == 0

        registry = load_registry()
        # Slot 1: API=8001, DB=5433
        assert registry.slots["1"].ports["api"] == 8001
        assert registry.slots["1"].ports["db"] == 5433
        # Slot 6: API=8006, DB=5438
        assert registry.slots["6"].ports["api"] == 8006
        assert registry.slots["6"].ports["db"] == 5438


# =============================================================================
# Slots Command Tests
# =============================================================================


class TestSlotsCommand:
    """Tests for kinfra sandbox slots command."""

    def test_slots_command_exists(self, runner) -> None:
        """kinfra sandbox slots --help should work."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["sandbox", "slots", "--help"])
        assert result.exit_code == 0

    def test_slots_shows_all_slots(self, runner, tmp_path, monkeypatch) -> None:
        """slots command displays all 6 slots."""
        from ktrdr.cli.kinfra.main import app

        # Provision slots first
        sandboxes_path = tmp_path / "sandboxes"
        monkeypatch.setattr("ktrdr.cli.kinfra.sandbox.SANDBOXES_DIR", sandboxes_path)
        registry_path = tmp_path / "registry.json"
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_FILE", registry_path)
        registry_dir = tmp_path
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_DIR", registry_dir)

        # Provision slots
        runner.invoke(app, ["sandbox", "provision"])

        # Now run slots command
        result = runner.invoke(app, ["sandbox", "slots"])
        assert result.exit_code == 0

        # Should show all 6 slots
        for slot_id in range(1, 7):
            assert str(slot_id) in result.output

    def test_slots_shows_profiles(self, runner, tmp_path, monkeypatch) -> None:
        """slots command shows profile for each slot."""
        from ktrdr.cli.kinfra.main import app

        sandboxes_path = tmp_path / "sandboxes"
        monkeypatch.setattr("ktrdr.cli.kinfra.sandbox.SANDBOXES_DIR", sandboxes_path)
        registry_path = tmp_path / "registry.json"
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_FILE", registry_path)
        registry_dir = tmp_path
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_DIR", registry_dir)

        runner.invoke(app, ["sandbox", "provision"])
        result = runner.invoke(app, ["sandbox", "slots"])

        assert result.exit_code == 0
        # Should show profile names
        assert "light" in result.output.lower()
        assert "standard" in result.output.lower()
        assert "heavy" in result.output.lower()

    def test_slots_shows_ports(self, runner, tmp_path, monkeypatch) -> None:
        """slots command shows API port for each slot."""
        from ktrdr.cli.kinfra.main import app

        sandboxes_path = tmp_path / "sandboxes"
        monkeypatch.setattr("ktrdr.cli.kinfra.sandbox.SANDBOXES_DIR", sandboxes_path)
        registry_path = tmp_path / "registry.json"
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_FILE", registry_path)
        registry_dir = tmp_path
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_DIR", registry_dir)

        runner.invoke(app, ["sandbox", "provision"])
        result = runner.invoke(app, ["sandbox", "slots"])

        assert result.exit_code == 0
        # Should show API ports
        assert "8001" in result.output
        assert "8006" in result.output

    def test_slots_shows_status(self, runner, tmp_path, monkeypatch) -> None:
        """slots command shows running/stopped status."""
        from ktrdr.cli.kinfra.main import app

        sandboxes_path = tmp_path / "sandboxes"
        monkeypatch.setattr("ktrdr.cli.kinfra.sandbox.SANDBOXES_DIR", sandboxes_path)
        registry_path = tmp_path / "registry.json"
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_FILE", registry_path)
        registry_dir = tmp_path
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_DIR", registry_dir)

        runner.invoke(app, ["sandbox", "provision"])
        result = runner.invoke(app, ["sandbox", "slots"])

        assert result.exit_code == 0
        # All slots should be stopped initially
        assert "stopped" in result.output.lower()

    def test_slots_empty_registry(self, runner, tmp_path, monkeypatch) -> None:
        """slots command handles empty registry gracefully."""
        from ktrdr.cli.kinfra.main import app

        # Use empty temp registry
        registry_path = tmp_path / "registry.json"
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_FILE", registry_path)
        registry_dir = tmp_path
        monkeypatch.setattr("ktrdr.cli.sandbox_registry.REGISTRY_DIR", registry_dir)

        result = runner.invoke(app, ["sandbox", "slots"])

        assert result.exit_code == 0
        # Should indicate no slots
        assert (
            "no slots" in result.output.lower() or "provision" in result.output.lower()
        )
