"""
Tests to verify ConfigLoader still works after M7.3 cleanup.

This tests the methods that remain after removing unused domain config methods.
"""

from pathlib import Path

import pytest
import yaml

from ktrdr.config.loader import ConfigLoader
from ktrdr.config.models import KtrdrConfig
from ktrdr.errors import ConfigurationFileError


class TestConfigLoaderAfterCleanup:
    """Verify ConfigLoader works for domain config loading."""

    def test_load_yaml_file(self, tmp_path: Path) -> None:
        """Can load and validate a YAML config file."""
        config_file = tmp_path / "test_config.yaml"
        config_data = {
            "data": {"directory": str(tmp_path / "data")},
            "logging": {"level": "INFO"},
        }
        config_file.write_text(yaml.dump(config_data))

        loader = ConfigLoader()
        config = loader.load(config_file, KtrdrConfig)

        assert config.data.directory == str(tmp_path / "data")
        assert config.logging.level == "INFO"

    def test_load_nonexistent_file_raises(self) -> None:
        """Raises error for nonexistent file."""
        loader = ConfigLoader()

        with pytest.raises(ConfigurationFileError):
            loader.load("/nonexistent/path/config.yaml", KtrdrConfig)

    def test_load_from_env_with_default(self, tmp_path: Path) -> None:
        """Can load from default path when env var not set."""
        config_file = tmp_path / "default_config.yaml"
        config_data = {
            "data": {"directory": str(tmp_path / "data")},
        }
        config_file.write_text(yaml.dump(config_data))

        loader = ConfigLoader()
        config = loader.load_from_env(
            env_var="NONEXISTENT_VAR",
            default_path=str(config_file),
            model_type=KtrdrConfig,
        )

        assert config.data.directory == str(tmp_path / "data")
