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


class TestM4DeprecatedNamesMapping:
    """Test M4 (Worker Settings) deprecated name mappings."""

    # WorkerSettings deprecated names
    def test_deprecated_names_contains_worker_id(self):
        """DEPRECATED_NAMES should map WORKER_ID to KTRDR_WORKER_ID."""
        assert "WORKER_ID" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["WORKER_ID"] == "KTRDR_WORKER_ID"

    def test_deprecated_names_contains_worker_port(self):
        """DEPRECATED_NAMES should map WORKER_PORT to KTRDR_WORKER_PORT."""
        assert "WORKER_PORT" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["WORKER_PORT"] == "KTRDR_WORKER_PORT"

    def test_deprecated_names_contains_worker_endpoint_url(self):
        """DEPRECATED_NAMES should map WORKER_ENDPOINT_URL to KTRDR_WORKER_ENDPOINT_URL."""
        assert "WORKER_ENDPOINT_URL" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["WORKER_ENDPOINT_URL"] == "KTRDR_WORKER_ENDPOINT_URL"

    def test_deprecated_names_contains_worker_public_base_url(self):
        """DEPRECATED_NAMES should map WORKER_PUBLIC_BASE_URL to KTRDR_WORKER_PUBLIC_BASE_URL."""
        assert "WORKER_PUBLIC_BASE_URL" in DEPRECATED_NAMES
        assert (
            DEPRECATED_NAMES["WORKER_PUBLIC_BASE_URL"] == "KTRDR_WORKER_PUBLIC_BASE_URL"
        )

    # CheckpointSettings deprecated names
    def test_deprecated_names_contains_checkpoint_epoch_interval(self):
        """DEPRECATED_NAMES should map CHECKPOINT_EPOCH_INTERVAL to KTRDR_CHECKPOINT_EPOCH_INTERVAL."""
        assert "CHECKPOINT_EPOCH_INTERVAL" in DEPRECATED_NAMES
        assert (
            DEPRECATED_NAMES["CHECKPOINT_EPOCH_INTERVAL"]
            == "KTRDR_CHECKPOINT_EPOCH_INTERVAL"
        )

    def test_deprecated_names_contains_checkpoint_time_interval_seconds(self):
        """DEPRECATED_NAMES should map CHECKPOINT_TIME_INTERVAL_SECONDS to KTRDR_CHECKPOINT_TIME_INTERVAL_SECONDS."""
        assert "CHECKPOINT_TIME_INTERVAL_SECONDS" in DEPRECATED_NAMES
        assert (
            DEPRECATED_NAMES["CHECKPOINT_TIME_INTERVAL_SECONDS"]
            == "KTRDR_CHECKPOINT_TIME_INTERVAL_SECONDS"
        )

    def test_deprecated_names_contains_checkpoint_dir(self):
        """DEPRECATED_NAMES should map CHECKPOINT_DIR to KTRDR_CHECKPOINT_DIR."""
        assert "CHECKPOINT_DIR" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["CHECKPOINT_DIR"] == "KTRDR_CHECKPOINT_DIR"

    def test_deprecated_names_contains_checkpoint_max_age_days(self):
        """DEPRECATED_NAMES should map CHECKPOINT_MAX_AGE_DAYS to KTRDR_CHECKPOINT_MAX_AGE_DAYS."""
        assert "CHECKPOINT_MAX_AGE_DAYS" in DEPRECATED_NAMES
        assert (
            DEPRECATED_NAMES["CHECKPOINT_MAX_AGE_DAYS"]
            == "KTRDR_CHECKPOINT_MAX_AGE_DAYS"
        )

    # OrphanDetectorSettings deprecated names
    def test_deprecated_names_contains_orphan_timeout_seconds(self):
        """DEPRECATED_NAMES should map ORPHAN_TIMEOUT_SECONDS to KTRDR_ORPHAN_TIMEOUT_SECONDS."""
        assert "ORPHAN_TIMEOUT_SECONDS" in DEPRECATED_NAMES
        assert (
            DEPRECATED_NAMES["ORPHAN_TIMEOUT_SECONDS"] == "KTRDR_ORPHAN_TIMEOUT_SECONDS"
        )

    def test_deprecated_names_contains_orphan_check_interval_seconds(self):
        """DEPRECATED_NAMES should map ORPHAN_CHECK_INTERVAL_SECONDS to KTRDR_ORPHAN_CHECK_INTERVAL_SECONDS."""
        assert "ORPHAN_CHECK_INTERVAL_SECONDS" in DEPRECATED_NAMES
        assert (
            DEPRECATED_NAMES["ORPHAN_CHECK_INTERVAL_SECONDS"]
            == "KTRDR_ORPHAN_CHECK_INTERVAL_SECONDS"
        )

    # OperationsSettings deprecated names
    def test_deprecated_names_contains_operations_cache_ttl(self):
        """DEPRECATED_NAMES should map OPERATIONS_CACHE_TTL to KTRDR_OPS_CACHE_TTL."""
        assert "OPERATIONS_CACHE_TTL" in DEPRECATED_NAMES
        assert DEPRECATED_NAMES["OPERATIONS_CACHE_TTL"] == "KTRDR_OPS_CACHE_TTL"


class TestM4DeprecatedNamesWarnings:
    """Test M4 deprecated name warnings."""

    def test_warns_for_worker_port(self):
        """Should emit warning when WORKER_PORT is set."""
        with patch.dict(os.environ, {"WORKER_PORT": "5003"}, clear=True):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = warn_deprecated_env_vars()
                assert "WORKER_PORT" in result
                dep_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                assert len(dep_warnings) == 1
                assert "WORKER_PORT" in str(dep_warnings[0].message)
                assert "KTRDR_WORKER_PORT" in str(dep_warnings[0].message)

    def test_warns_for_checkpoint_epoch_interval(self):
        """Should emit warning when CHECKPOINT_EPOCH_INTERVAL is set."""
        with patch.dict(os.environ, {"CHECKPOINT_EPOCH_INTERVAL": "5"}, clear=True):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = warn_deprecated_env_vars()
                assert "CHECKPOINT_EPOCH_INTERVAL" in result
                dep_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                assert len(dep_warnings) == 1
                assert "CHECKPOINT_EPOCH_INTERVAL" in str(dep_warnings[0].message)
                assert "KTRDR_CHECKPOINT_EPOCH_INTERVAL" in str(dep_warnings[0].message)

    def test_warns_for_orphan_timeout_seconds(self):
        """Should emit warning when ORPHAN_TIMEOUT_SECONDS is set."""
        with patch.dict(os.environ, {"ORPHAN_TIMEOUT_SECONDS": "120"}, clear=True):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = warn_deprecated_env_vars()
                assert "ORPHAN_TIMEOUT_SECONDS" in result
                dep_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                assert len(dep_warnings) == 1
                assert "ORPHAN_TIMEOUT_SECONDS" in str(dep_warnings[0].message)
                assert "KTRDR_ORPHAN_TIMEOUT_SECONDS" in str(dep_warnings[0].message)

    def test_warns_for_operations_cache_ttl(self):
        """Should emit warning when OPERATIONS_CACHE_TTL is set."""
        with patch.dict(os.environ, {"OPERATIONS_CACHE_TTL": "2.0"}, clear=True):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = warn_deprecated_env_vars()
                assert "OPERATIONS_CACHE_TTL" in result
                dep_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                assert len(dep_warnings) == 1
                assert "OPERATIONS_CACHE_TTL" in str(dep_warnings[0].message)
                assert "KTRDR_OPS_CACHE_TTL" in str(dep_warnings[0].message)

    def test_does_not_warn_for_new_worker_names(self):
        """Should not warn when new KTRDR_WORKER_* names are used."""
        with patch.dict(
            os.environ,
            {"KTRDR_WORKER_PORT": "5003", "KTRDR_WORKER_ID": "test-worker"},
            clear=True,
        ):
            result = warn_deprecated_env_vars()
            assert result == []

    def test_does_not_warn_for_new_checkpoint_names(self):
        """Should not warn when new KTRDR_CHECKPOINT_* names are used."""
        with patch.dict(
            os.environ,
            {
                "KTRDR_CHECKPOINT_EPOCH_INTERVAL": "5",
                "KTRDR_CHECKPOINT_DIR": "/data/checkpoints",
            },
            clear=True,
        ):
            result = warn_deprecated_env_vars()
            assert result == []

    def test_does_not_warn_for_new_orphan_names(self):
        """Should not warn when new KTRDR_ORPHAN_* names are used."""
        with patch.dict(
            os.environ,
            {"KTRDR_ORPHAN_TIMEOUT_SECONDS": "120"},
            clear=True,
        ):
            result = warn_deprecated_env_vars()
            assert result == []

    def test_does_not_warn_for_new_ops_names(self):
        """Should not warn when new KTRDR_OPS_* names are used."""
        with patch.dict(
            os.environ,
            {"KTRDR_OPS_CACHE_TTL": "2.0"},
            clear=True,
        ):
            result = warn_deprecated_env_vars()
            assert result == []
