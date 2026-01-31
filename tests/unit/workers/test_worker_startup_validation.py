"""
Unit tests for worker startup validation.

Tests verify that worker modules call warn_deprecated_env_vars() and
validate_all("worker") at startup, before FastAPI app creation.

Tests follow the same pattern as tests/unit/api/test_main_startup.py.
"""

import inspect


class TestBacktestWorkerStartupValidation:
    """Test that backtest_worker.py has startup validation calls."""

    def test_imports_warn_deprecated_env_vars(self) -> None:
        """backtest_worker.py should import warn_deprecated_env_vars."""
        from ktrdr.backtesting import backtest_worker

        source = inspect.getsource(backtest_worker)

        assert "warn_deprecated_env_vars" in source

    def test_imports_validate_all(self) -> None:
        """backtest_worker.py should import validate_all."""
        from ktrdr.backtesting import backtest_worker

        source = inspect.getsource(backtest_worker)

        assert "validate_all" in source

    def test_calls_warn_deprecated_env_vars(self) -> None:
        """backtest_worker.py should call warn_deprecated_env_vars() at module level."""
        from ktrdr.backtesting import backtest_worker

        source = inspect.getsource(backtest_worker)

        assert "warn_deprecated_env_vars()" in source

    def test_calls_validate_all_worker(self) -> None:
        """backtest_worker.py should call validate_all('worker') at module level."""
        from ktrdr.backtesting import backtest_worker

        source = inspect.getsource(backtest_worker)

        # Should call validate_all("worker") or validate_all('worker')
        assert 'validate_all("worker")' in source or "validate_all('worker')" in source

    def test_validation_happens_before_get_worker_settings(self) -> None:
        """Validation should happen before get_worker_settings() is called."""
        from ktrdr.backtesting import backtest_worker

        source = inspect.getsource(backtest_worker)

        # Find positions of key calls
        warn_pos = source.find("warn_deprecated_env_vars()")
        validate_pos = source.find("validate_all(")
        settings_pos = source.find("get_worker_settings()")

        # All calls should exist
        assert warn_pos != -1, "warn_deprecated_env_vars() not found"
        assert validate_pos != -1, "validate_all() not found"
        assert settings_pos != -1, "get_worker_settings() not found"

        # Validation should come before settings access
        assert (
            warn_pos < settings_pos
        ), "warn_deprecated_env_vars() should be called before get_worker_settings()"
        assert (
            validate_pos < settings_pos
        ), "validate_all() should be called before get_worker_settings()"

    def test_warn_deprecated_called_before_validate_all(self) -> None:
        """warn_deprecated_env_vars() should be called before validate_all()."""
        from ktrdr.backtesting import backtest_worker

        source = inspect.getsource(backtest_worker)

        warn_pos = source.find("warn_deprecated_env_vars()")
        validate_pos = source.find("validate_all(")

        assert warn_pos != -1, "warn_deprecated_env_vars() not found"
        assert validate_pos != -1, "validate_all() not found"

        assert (
            warn_pos < validate_pos
        ), "warn_deprecated_env_vars() should be called before validate_all()"


class TestTrainingWorkerStartupValidation:
    """Test that training_worker.py has startup validation calls."""

    def test_imports_warn_deprecated_env_vars(self) -> None:
        """training_worker.py should import warn_deprecated_env_vars."""
        from ktrdr.training import training_worker

        source = inspect.getsource(training_worker)

        assert "warn_deprecated_env_vars" in source

    def test_imports_validate_all(self) -> None:
        """training_worker.py should import validate_all."""
        from ktrdr.training import training_worker

        source = inspect.getsource(training_worker)

        assert "validate_all" in source

    def test_calls_warn_deprecated_env_vars(self) -> None:
        """training_worker.py should call warn_deprecated_env_vars() at module level."""
        from ktrdr.training import training_worker

        source = inspect.getsource(training_worker)

        assert "warn_deprecated_env_vars()" in source

    def test_calls_validate_all_worker(self) -> None:
        """training_worker.py should call validate_all('worker') at module level."""
        from ktrdr.training import training_worker

        source = inspect.getsource(training_worker)

        # Should call validate_all("worker") or validate_all('worker')
        assert 'validate_all("worker")' in source or "validate_all('worker')" in source

    def test_validation_happens_before_get_worker_settings(self) -> None:
        """Validation should happen before get_worker_settings() is called."""
        from ktrdr.training import training_worker

        source = inspect.getsource(training_worker)

        # Find positions of key calls
        warn_pos = source.find("warn_deprecated_env_vars()")
        validate_pos = source.find("validate_all(")
        settings_pos = source.find("get_worker_settings()")

        # All calls should exist
        assert warn_pos != -1, "warn_deprecated_env_vars() not found"
        assert validate_pos != -1, "validate_all() not found"
        assert settings_pos != -1, "get_worker_settings() not found"

        # Validation should come before settings access
        assert (
            warn_pos < settings_pos
        ), "warn_deprecated_env_vars() should be called before get_worker_settings()"
        assert (
            validate_pos < settings_pos
        ), "validate_all() should be called before get_worker_settings()"

    def test_warn_deprecated_called_before_validate_all(self) -> None:
        """warn_deprecated_env_vars() should be called before validate_all()."""
        from ktrdr.training import training_worker

        source = inspect.getsource(training_worker)

        warn_pos = source.find("warn_deprecated_env_vars()")
        validate_pos = source.find("validate_all(")

        assert warn_pos != -1, "warn_deprecated_env_vars() not found"
        assert validate_pos != -1, "validate_all() not found"

        assert (
            warn_pos < validate_pos
        ), "warn_deprecated_env_vars() should be called before validate_all()"
