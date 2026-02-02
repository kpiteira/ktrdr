"""Tests for slot compose templates.

Tests validate that compose templates are valid YAML and have required variables.
"""


class TestComposeTemplate:
    """Tests for the compose template."""

    def test_template_exists(self) -> None:
        """Template directory and files exist."""

        from ktrdr.cli.kinfra.templates import TEMPLATE_DIR, get_compose_template

        assert TEMPLATE_DIR.exists()
        template = get_compose_template()
        assert template is not None

    def test_template_valid_yaml(self) -> None:
        """Template parses as valid YAML."""
        import yaml

        from ktrdr.cli.kinfra.templates import get_compose_template

        template = get_compose_template()
        # Should parse without error
        parsed = yaml.safe_load(template)
        assert isinstance(parsed, dict)

    def test_template_has_services(self) -> None:
        """Template has required services defined."""
        import yaml

        from ktrdr.cli.kinfra.templates import get_compose_template

        template = get_compose_template()
        parsed = yaml.safe_load(template)

        assert "services" in parsed
        services = parsed["services"]

        # Core services required
        assert "db" in services
        assert "backend" in services
        assert "jaeger" in services

    def test_template_has_port_variables(self) -> None:
        """Template uses port variables for substitution."""
        from ktrdr.cli.kinfra.templates import get_compose_template

        template = get_compose_template()

        # Should have port variable placeholders
        assert "${KTRDR_API_PORT" in template or "${KTRDR_API_PORT:-" in template
        assert "${KTRDR_DB_PORT" in template or "${KTRDR_DB_PORT:-" in template

    def test_template_has_networks(self) -> None:
        """Template defines networks."""
        import yaml

        from ktrdr.cli.kinfra.templates import get_compose_template

        template = get_compose_template()
        parsed = yaml.safe_load(template)

        assert "networks" in parsed

    def test_template_has_volumes(self) -> None:
        """Template defines volumes."""
        import yaml

        from ktrdr.cli.kinfra.templates import get_compose_template

        template = get_compose_template()
        parsed = yaml.safe_load(template)

        assert "volumes" in parsed
