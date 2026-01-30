"""
Unit tests for main.py startup validation.

Tests verify that main.py calls warn_deprecated_env_vars() and
validate_all("backend") at startup, before FastAPI app creation.
"""

import inspect


class TestMainStartupValidation:
    """Test that main.py has startup validation calls."""

    def test_main_imports_warn_deprecated_env_vars(self):
        """main.py should import warn_deprecated_env_vars from ktrdr.config."""
        from ktrdr.api import main

        source = inspect.getsource(main)

        # Should import warn_deprecated_env_vars
        assert "warn_deprecated_env_vars" in source
        assert "from ktrdr.config import" in source or "from ktrdr.config" in source

    def test_main_imports_validate_all(self):
        """main.py should import validate_all from ktrdr.config."""
        from ktrdr.api import main

        source = inspect.getsource(main)

        # Should import validate_all
        assert "validate_all" in source

    def test_main_calls_warn_deprecated_env_vars(self):
        """main.py should call warn_deprecated_env_vars() at module level."""
        from ktrdr.api import main

        source = inspect.getsource(main)

        # Should call warn_deprecated_env_vars()
        assert "warn_deprecated_env_vars()" in source

    def test_main_calls_validate_all_backend(self):
        """main.py should call validate_all('backend') at module level."""
        from ktrdr.api import main

        source = inspect.getsource(main)

        # Should call validate_all("backend") or validate_all('backend')
        assert (
            'validate_all("backend")' in source or "validate_all('backend')" in source
        )

    def test_validation_happens_before_monitoring_setup(self):
        """Validation should happen before setup_monitoring() is called."""
        from ktrdr.api import main

        source = inspect.getsource(main)

        # Find positions of key calls
        warn_pos = source.find("warn_deprecated_env_vars()")
        validate_pos = source.find("validate_all(")
        monitoring_pos = source.find("setup_monitoring(")

        # Both validation calls should exist
        assert warn_pos != -1, "warn_deprecated_env_vars() not found"
        assert validate_pos != -1, "validate_all() not found"
        assert monitoring_pos != -1, "setup_monitoring() not found"

        # Validation should come before monitoring
        assert (
            warn_pos < monitoring_pos
        ), "warn_deprecated_env_vars() should be called before setup_monitoring()"
        assert (
            validate_pos < monitoring_pos
        ), "validate_all() should be called before setup_monitoring()"

    def test_warn_deprecated_called_before_validate_all(self):
        """warn_deprecated_env_vars() should be called before validate_all()."""
        from ktrdr.api import main

        source = inspect.getsource(main)

        warn_pos = source.find("warn_deprecated_env_vars()")
        validate_pos = source.find("validate_all(")

        assert warn_pos != -1, "warn_deprecated_env_vars() not found"
        assert validate_pos != -1, "validate_all() not found"

        # warn_deprecated should come first
        assert (
            warn_pos < validate_pos
        ), "warn_deprecated_env_vars() should be called before validate_all()"
