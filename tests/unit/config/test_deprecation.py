"""
Unit tests for deprecation module.

Tests verify:
- warn_deprecated_env_vars() returns empty list when no deprecated vars set
- warn_deprecated_env_vars() returns list of found deprecated vars
- warn_deprecated_env_vars() emits DeprecationWarning for each found var
- Warning message includes both old and new name
"""

import os
import warnings
from unittest.mock import patch

from ktrdr.config.deprecation import DEPRECATED_NAMES, warn_deprecated_env_vars


class TestDeprecatedNamesMapping:
    """Test the DEPRECATED_NAMES dict configuration."""

    def test_deprecated_names_contains_db_host(self):
        """DEPRECATED_NAMES should map DB_HOST to KTRDR_DB_HOST."""
        assert "DB_HOST" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["DB_HOST"] == "KTRDR_DB_HOST"

    def test_deprecated_names_contains_db_port(self):
        """DEPRECATED_NAMES should map DB_PORT to KTRDR_DB_PORT."""
        assert "DB_PORT" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["DB_PORT"] == "KTRDR_DB_PORT"

    def test_deprecated_names_contains_db_name(self):
        """DEPRECATED_NAMES should map DB_NAME to KTRDR_DB_NAME."""
        assert "DB_NAME" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["DB_NAME"] == "KTRDR_DB_NAME"

    def test_deprecated_names_contains_db_user(self):
        """DEPRECATED_NAMES should map DB_USER to KTRDR_DB_USER."""
        assert "DB_USER" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["DB_USER"] == "KTRDR_DB_USER"

    def test_deprecated_names_contains_db_password(self):
        """DEPRECATED_NAMES should map DB_PASSWORD to KTRDR_DB_PASSWORD."""
        assert "DB_PASSWORD" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["DB_PASSWORD"] == "KTRDR_DB_PASSWORD"

    def test_deprecated_names_contains_db_echo(self):
        """DEPRECATED_NAMES should map DB_ECHO to KTRDR_DB_ECHO."""
        assert "DB_ECHO" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["DB_ECHO"] == "KTRDR_DB_ECHO"


class TestWarnDeprecatedEnvVarsNoDeprecated:
    """Test warn_deprecated_env_vars() when no deprecated vars are set."""

    def test_returns_empty_list_when_no_deprecated_vars(self):
        """Should return empty list when no deprecated env vars are set."""
        # Ensure no deprecated vars are set
        with patch.dict(os.environ, {}, clear=True):
            result = warn_deprecated_env_vars()
            assert result == []

    def test_no_warnings_when_no_deprecated_vars(self):
        """Should not emit warnings when no deprecated env vars are set."""
        with patch.dict(os.environ, {}, clear=True):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                warn_deprecated_env_vars()
                # Filter to only DeprecationWarnings about env vars
                dep_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                assert len(dep_warnings) == 0


class TestWarnDeprecatedEnvVarsFound:
    """Test warn_deprecated_env_vars() when deprecated vars are set."""

    def test_returns_list_with_single_deprecated_var(self):
        """Should return list containing the deprecated var name."""
        with patch.dict(os.environ, {"DB_HOST": "somehost"}, clear=True):
            result = warn_deprecated_env_vars()
            assert "DB_HOST" in result

    def test_returns_list_with_multiple_deprecated_vars(self):
        """Should return list containing all deprecated var names found."""
        with patch.dict(
            os.environ,
            {"DB_HOST": "somehost", "DB_PASSWORD": "secret"},
            clear=True,
        ):
            result = warn_deprecated_env_vars()
            assert "DB_HOST" in result
            assert "DB_PASSWORD" in result
            assert len(result) == 2

    def test_emits_deprecation_warning_for_single_var(self):
        """Should emit DeprecationWarning for deprecated var."""
        with patch.dict(os.environ, {"DB_PASSWORD": "test"}, clear=True):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                warn_deprecated_env_vars()
                dep_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                assert len(dep_warnings) == 1

    def test_emits_deprecation_warning_for_each_deprecated_var(self):
        """Should emit one DeprecationWarning per deprecated var found."""
        with patch.dict(
            os.environ,
            {"DB_HOST": "host", "DB_PORT": "5432", "DB_NAME": "db"},
            clear=True,
        ):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                warn_deprecated_env_vars()
                dep_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                assert len(dep_warnings) == 3


class TestWarnDeprecatedEnvVarsMessage:
    """Test warning message content."""

    def test_warning_includes_old_name(self):
        """Warning message should include the deprecated env var name."""
        with patch.dict(os.environ, {"DB_HOST": "somehost"}, clear=True):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                warn_deprecated_env_vars()
                dep_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                assert len(dep_warnings) == 1
                assert "DB_HOST" in str(dep_warnings[0].message)

    def test_warning_includes_new_name(self):
        """Warning message should include the new env var name."""
        with patch.dict(os.environ, {"DB_HOST": "somehost"}, clear=True):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                warn_deprecated_env_vars()
                dep_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                assert len(dep_warnings) == 1
                assert "KTRDR_DB_HOST" in str(dep_warnings[0].message)

    def test_warning_provides_migration_guidance(self):
        """Warning message should include guidance to migrate."""
        with patch.dict(os.environ, {"DB_PASSWORD": "secret"}, clear=True):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                warn_deprecated_env_vars()
                dep_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                assert len(dep_warnings) == 1
                msg = str(dep_warnings[0].message)
                # Should mention deprecation and provide guidance
                assert "deprecated" in msg.lower()


class TestWarnDeprecatedEnvVarsIsolation:
    """Test that only known deprecated vars trigger warnings."""

    def test_ignores_unknown_vars(self):
        """Should not warn about vars not in DEPRECATED_NAMES."""
        with patch.dict(
            os.environ,
            {"SOME_RANDOM_VAR": "value", "ANOTHER_VAR": "value2"},
            clear=True,
        ):
            result = warn_deprecated_env_vars()
            assert result == []

    def test_only_warns_for_deprecated_vars(self):
        """Should only return deprecated vars, not new-style vars."""
        with patch.dict(
            os.environ,
            {
                "DB_HOST": "oldhost",  # deprecated
                "KTRDR_DB_PORT": "5432",  # new (should not trigger)
                "RANDOM": "value",  # unrelated (should not trigger)
            },
            clear=True,
        ):
            result = warn_deprecated_env_vars()
            assert result == ["DB_HOST"]
