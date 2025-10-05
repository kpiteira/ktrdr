"""Tests for MCP signature validation script"""

import pytest

from scripts.validate_mcp_signatures import ValidationConfig, main


class TestValidationConfig:
    """Test configuration loading"""

    def test_load_config_from_file(self):
        """Should load endpoint mapping from JSON file"""
        config = ValidationConfig.from_file("mcp/endpoint_mapping.json")

        assert "start_training" in config.tools
        assert config.tools["start_training"]["endpoint"] == "/api/v1/trainings/start"
        assert config.tools["start_training"]["critical"] is True

    def test_config_validation(self):
        """Should validate config structure"""
        with pytest.raises(ValueError, match="missing required fields"):
            # Missing required fields
            ValidationConfig(tools={"invalid": {}})

    def test_config_missing_tools_section(self):
        """Should raise error if 'tools' section missing"""
        import json
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"no_tools": {}}, f)
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Config missing 'tools' section"):
                ValidationConfig.from_file(temp_path)
        finally:
            import os

            os.unlink(temp_path)


class TestCLI:
    """Test command-line interface"""

    def test_help_message(self, capsys):
        """Should display help message"""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Validate MCP tool signatures" in captured.out

    def test_default_arguments(self):
        """Should use default values for arguments"""
        # This will fail since we don't have full implementation yet
        # but it defines the expected behavior
        pass

    def test_strict_flag(self):
        """Should support --strict flag"""
        # Will be implemented when we have full validation logic
        pass
