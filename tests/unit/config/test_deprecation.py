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

    # M1: Database deprecated names
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

    # M2: Observability deprecated names
    def test_deprecated_names_contains_otlp_endpoint(self):
        """DEPRECATED_NAMES should map OTLP_ENDPOINT to KTRDR_OTEL_OTLP_ENDPOINT."""
        assert "OTLP_ENDPOINT" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["OTLP_ENDPOINT"] == "KTRDR_OTEL_OTLP_ENDPOINT"


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


class TestM2DeprecatedNames:
    """Test M2 (API, Auth, Logging, Observability) deprecated name warnings."""

    def test_warns_for_otlp_endpoint(self):
        """Should emit warning when OTLP_ENDPOINT is set."""
        with patch.dict(
            os.environ, {"OTLP_ENDPOINT": "http://localhost:4317"}, clear=True
        ):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = warn_deprecated_env_vars()
                assert "OTLP_ENDPOINT" in result
                dep_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                assert len(dep_warnings) == 1
                assert "OTLP_ENDPOINT" in str(dep_warnings[0].message)
                assert "KTRDR_OTEL_OTLP_ENDPOINT" in str(dep_warnings[0].message)

    def test_does_not_warn_for_new_otel_name(self):
        """Should not warn when new KTRDR_OTEL_* names are used."""
        with patch.dict(
            os.environ,
            {"KTRDR_OTEL_OTLP_ENDPOINT": "http://localhost:4317"},
            clear=True,
        ):
            result = warn_deprecated_env_vars()
            assert result == []


class TestM3DeprecatedNamesMapping:
    """Test M3 (IB & Host Services) deprecated name mappings."""

    # IB Settings deprecated names
    def test_deprecated_names_contains_ib_host(self):
        """DEPRECATED_NAMES should map IB_HOST to KTRDR_IB_HOST."""
        assert "IB_HOST" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["IB_HOST"] == "KTRDR_IB_HOST"

    def test_deprecated_names_contains_ib_port(self):
        """DEPRECATED_NAMES should map IB_PORT to KTRDR_IB_PORT."""
        assert "IB_PORT" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["IB_PORT"] == "KTRDR_IB_PORT"

    def test_deprecated_names_contains_ib_client_id(self):
        """DEPRECATED_NAMES should map IB_CLIENT_ID to KTRDR_IB_CLIENT_ID."""
        assert "IB_CLIENT_ID" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["IB_CLIENT_ID"] == "KTRDR_IB_CLIENT_ID"

    def test_deprecated_names_contains_ib_timeout(self):
        """DEPRECATED_NAMES should map IB_TIMEOUT to KTRDR_IB_TIMEOUT."""
        assert "IB_TIMEOUT" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["IB_TIMEOUT"] == "KTRDR_IB_TIMEOUT"

    def test_deprecated_names_contains_ib_readonly(self):
        """DEPRECATED_NAMES should map IB_READONLY to KTRDR_IB_READONLY."""
        assert "IB_READONLY" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["IB_READONLY"] == "KTRDR_IB_READONLY"

    def test_deprecated_names_contains_ib_rate_limit(self):
        """DEPRECATED_NAMES should map IB_RATE_LIMIT to KTRDR_IB_RATE_LIMIT."""
        assert "IB_RATE_LIMIT" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["IB_RATE_LIMIT"] == "KTRDR_IB_RATE_LIMIT"

    def test_deprecated_names_contains_ib_rate_period(self):
        """DEPRECATED_NAMES should map IB_RATE_PERIOD to KTRDR_IB_RATE_PERIOD."""
        assert "IB_RATE_PERIOD" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["IB_RATE_PERIOD"] == "KTRDR_IB_RATE_PERIOD"

    def test_deprecated_names_contains_ib_max_retries(self):
        """DEPRECATED_NAMES should map IB_MAX_RETRIES to KTRDR_IB_MAX_RETRIES."""
        assert "IB_MAX_RETRIES" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["IB_MAX_RETRIES"] == "KTRDR_IB_MAX_RETRIES"

    def test_deprecated_names_contains_ib_retry_delay(self):
        """DEPRECATED_NAMES should map IB_RETRY_DELAY to KTRDR_IB_RETRY_BASE_DELAY."""
        assert "IB_RETRY_DELAY" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["IB_RETRY_DELAY"] == "KTRDR_IB_RETRY_BASE_DELAY"

    def test_deprecated_names_contains_ib_retry_max_delay(self):
        """DEPRECATED_NAMES should map IB_RETRY_MAX_DELAY to KTRDR_IB_RETRY_MAX_DELAY."""
        assert "IB_RETRY_MAX_DELAY" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["IB_RETRY_MAX_DELAY"] == "KTRDR_IB_RETRY_MAX_DELAY"

    def test_deprecated_names_contains_ib_pacing_delay(self):
        """DEPRECATED_NAMES should map IB_PACING_DELAY to KTRDR_IB_PACING_DELAY."""
        assert "IB_PACING_DELAY" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["IB_PACING_DELAY"] == "KTRDR_IB_PACING_DELAY"

    def test_deprecated_names_contains_ib_max_requests_10min(self):
        """DEPRECATED_NAMES should map IB_MAX_REQUESTS_10MIN to KTRDR_IB_MAX_REQUESTS_PER_10MIN."""
        assert "IB_MAX_REQUESTS_10MIN" in DEPRECATED_NAMES
        assert (
            DEPRECATED_NAMES["IB_MAX_REQUESTS_10MIN"]
            == "KTRDR_IB_MAX_REQUESTS_PER_10MIN"
        )

    # IB Host Service deprecated names
    def test_deprecated_names_contains_use_ib_host_service(self):
        """DEPRECATED_NAMES should map USE_IB_HOST_SERVICE to KTRDR_IB_HOST_ENABLED."""
        assert "USE_IB_HOST_SERVICE" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["USE_IB_HOST_SERVICE"] == "KTRDR_IB_HOST_ENABLED"

    # Training Host Service deprecated names
    def test_deprecated_names_contains_use_training_host_service(self):
        """DEPRECATED_NAMES should map USE_TRAINING_HOST_SERVICE to KTRDR_TRAINING_HOST_ENABLED."""
        assert "USE_TRAINING_HOST_SERVICE" in DEPRECATED_NAMES
        assert (
            DEPRECATED_NAMES["USE_TRAINING_HOST_SERVICE"]
            == "KTRDR_TRAINING_HOST_ENABLED"
        )


class TestM3DeprecatedNamesWarnings:
    """Test M3 deprecated name warnings."""

    def test_warns_for_ib_host(self):
        """Should emit warning when IB_HOST is set."""
        with patch.dict(os.environ, {"IB_HOST": "192.168.1.1"}, clear=True):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = warn_deprecated_env_vars()
                assert "IB_HOST" in result
                dep_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                assert len(dep_warnings) == 1
                assert "IB_HOST" in str(dep_warnings[0].message)
                assert "KTRDR_IB_HOST" in str(dep_warnings[0].message)

    def test_warns_for_use_ib_host_service(self):
        """Should emit warning when USE_IB_HOST_SERVICE is set."""
        with patch.dict(os.environ, {"USE_IB_HOST_SERVICE": "true"}, clear=True):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = warn_deprecated_env_vars()
                assert "USE_IB_HOST_SERVICE" in result
                dep_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                assert len(dep_warnings) == 1
                assert "USE_IB_HOST_SERVICE" in str(dep_warnings[0].message)
                assert "KTRDR_IB_HOST_ENABLED" in str(dep_warnings[0].message)

    def test_warns_for_use_training_host_service(self):
        """Should emit warning when USE_TRAINING_HOST_SERVICE is set."""
        with patch.dict(os.environ, {"USE_TRAINING_HOST_SERVICE": "true"}, clear=True):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = warn_deprecated_env_vars()
                assert "USE_TRAINING_HOST_SERVICE" in result
                dep_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                assert len(dep_warnings) == 1
                assert "USE_TRAINING_HOST_SERVICE" in str(dep_warnings[0].message)
                assert "KTRDR_TRAINING_HOST_ENABLED" in str(dep_warnings[0].message)

    def test_does_not_warn_for_new_ib_names(self):
        """Should not warn when new KTRDR_IB_* names are used."""
        with patch.dict(
            os.environ,
            {"KTRDR_IB_HOST": "192.168.1.1", "KTRDR_IB_PORT": "4002"},
            clear=True,
        ):
            result = warn_deprecated_env_vars()
            assert result == []

    def test_does_not_warn_for_new_host_service_names(self):
        """Should not warn when new KTRDR_*_HOST_ENABLED names are used."""
        with patch.dict(
            os.environ,
            {
                "KTRDR_IB_HOST_ENABLED": "true",
                "KTRDR_TRAINING_HOST_ENABLED": "true",
            },
            clear=True,
        ):
            result = warn_deprecated_env_vars()
            assert result == []
