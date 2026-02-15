"""Compose templates for slot infrastructure.

This module provides Docker Compose templates that can be copied to slot
directories. Templates use ${VARIABLE} substitution with defaults, allowing
.env.sandbox files to override port assignments.
"""

from pathlib import Path

# Directory containing template files
TEMPLATE_DIR = Path(__file__).parent


def get_compose_template() -> str:
    """Get the base Docker Compose template for slots.

    The template uses ${VARIABLE:-default} syntax for port substitution.
    When copied to a slot directory, the .env.sandbox file provides
    slot-specific port values.

    Returns:
        The template content as a string
    """
    template_path = TEMPLATE_DIR / "docker-compose.base.yml"
    return template_path.read_text()


def get_prometheus_config() -> str:
    """Get the Prometheus configuration template for slots.

    Returns:
        The prometheus.yml content as a string
    """
    config_path = TEMPLATE_DIR / "prometheus.yml"
    return config_path.read_text()
