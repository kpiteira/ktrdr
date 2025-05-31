"""
Renderer module for visualization.

This module contains the Renderer class for rendering charts to HTML.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple, Any

from ktrdr.errors import ConfigurationError, DataError
from ktrdr.visualization.template_manager import TemplateManager

# Setup logging
import logging

logger = logging.getLogger(__name__)


class Renderer:
    """
    Renderer for creating interactive financial charts.

    This class handles the rendering of charts to HTML using the TemplateManager.
    It provides methods to render charts with various configurations and save
    them to files.
    """

    def render_chart(
        self,
        title: str = "KTRDR Chart",
        chart_configs: List[Dict] = None,
        chart_data: Dict = None,
        theme: str = "dark",
        has_range_slider: bool = False,
    ) -> str:
        """
        Render a chart to HTML.

        Args:
            title: The title of the chart.
            chart_configs: List of chart configurations.
            chart_data: Dictionary of chart data.
            theme: The theme to use. Either 'dark' or 'light'.
            has_range_slider: Whether the chart includes a range slider.

        Returns:
            The rendered HTML as a string.

        Raises:
            ConfigurationError: If the input configurations are invalid.
        """
        # Validate inputs
        if chart_configs is not None and not isinstance(chart_configs, list):
            raise ConfigurationError(
                "chart_configs must be a list",
                "CONFIG-InvalidChartConfigs",
                {"chart_configs": chart_configs},
            )

        if chart_data is not None and not isinstance(chart_data, dict):
            raise ConfigurationError(
                "chart_data must be a dictionary",
                "CONFIG-InvalidChartData",
                {"chart_data": chart_data},
            )

        if theme not in ["dark", "light"]:
            raise ConfigurationError(
                f"Invalid theme: {theme}. Use 'dark' or 'light'.",
                "CONFIG-InvalidTheme",
                {"theme": theme},
            )

        # Render the chart HTML
        html = TemplateManager.render_chart_html(
            title=title,
            chart_configs=chart_configs,
            chart_data=chart_data,
            theme=theme,
            has_range_slider=has_range_slider,
        )

        return html

    def save_chart(
        self, html_content: str, output_path: Union[str, Path], overwrite: bool = False
    ) -> Path:
        """
        Save a chart to a file.

        Args:
            html_content: The HTML content to save.
            output_path: The path to save the file to.
            overwrite: Whether to overwrite an existing file.

        Returns:
            The path to the saved file.

        Raises:
            DataError: If the file already exists and overwrite is False,
                or if there is an error saving the file.
        """
        # Convert string path to Path object
        if isinstance(output_path, str):
            output_path = Path(output_path)

        # Check if the file already exists
        if output_path.exists() and not overwrite:
            msg = f"File {output_path} already exists and overwrite=False"
            try:
                raise ConfigurationError(
                    msg, "CONFIG-FileExists", {"path": str(output_path)}
                )
            except ConfigurationError as e:
                # Wrap the ConfigurationError in a DataError
                # This maintains backward compatibility with existing code
                raise DataError(
                    msg, "DATA-FileExists", {"path": str(output_path)}
                ) from e

        # Create parent directories if they don't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save the file
        try:
            with open(output_path, "w") as f:
                f.write(html_content)
            logger.info(f"Chart saved successfully to: {output_path}")
            return output_path
        except Exception as e:
            raise DataError(
                f"Error saving chart to {output_path}: {str(e)}",
                "DATA-SaveError",
                {"path": str(output_path), "error": str(e)},
            ) from e

    def update_theme(self, html_content: str, theme: str) -> str:
        """
        Update the theme of an existing HTML chart.

        Args:
            html_content: The HTML content to update.
            theme: The new theme. Either 'dark' or 'light'.

        Returns:
            The updated HTML content.

        Raises:
            ConfigurationError: If an invalid theme is provided.
        """
        if theme not in ["dark", "light"]:
            raise ConfigurationError(
                f"Invalid theme: {theme}. Use 'dark' or 'light'.",
                "CONFIG-InvalidTheme",
                {"theme": theme},
            )

        # Update button states
        if theme == "dark":
            html_content = html_content.replace(
                "document.getElementById('darkTheme').disabled = false",
                "document.getElementById('darkTheme').disabled = true",
            )
            html_content = html_content.replace(
                "document.getElementById('lightTheme').disabled = true",
                "document.getElementById('lightTheme').disabled = false",
            )
        else:  # light
            html_content = html_content.replace(
                "document.getElementById('darkTheme').disabled = true",
                "document.getElementById('darkTheme').disabled = false",
            )
            html_content = html_content.replace(
                "document.getElementById('lightTheme').disabled = false",
                "document.getElementById('lightTheme').disabled = true",
            )

        return html_content

    def generate_standalone_html(
        self,
        title: str,
        chart_configs: List[Dict],
        chart_data: Dict,
        output_dir: Optional[Union[str, Path]] = None,
        theme: str = "dark",
        filename: Optional[str] = None,
        has_range_slider: bool = False,
    ) -> Tuple[str, Path]:
        """
        Generate a standalone HTML file with charts.

        Args:
            title: The title of the chart.
            chart_configs: List of chart configurations.
            chart_data: Dictionary of chart data.
            output_dir: Directory to save the file. Defaults to current directory.
            theme: The theme to use. Either 'dark' or 'light'.
            filename: Custom filename. Defaults to sanitized title.
            has_range_slider: Whether the chart includes a range slider.

        Returns:
            A tuple of (html_content, file_path).
        """
        # Generate the HTML content
        html_content = self.render_chart(
            title=title,
            chart_configs=chart_configs,
            chart_data=chart_data,
            theme=theme,
            has_range_slider=has_range_slider,
        )

        # Determine the output path
        if output_dir is None:
            output_dir = Path.cwd()
        elif isinstance(output_dir, str):
            output_dir = Path(output_dir)

        if filename is None:
            # Sanitize the title for use as a filename
            sanitized_title = "".join(
                c if c.isalnum() or c in [" ", "_", "-"] else "_" for c in title
            )
            sanitized_title = sanitized_title.replace(" ", "_")
            filename = f"{sanitized_title}.html"

        output_path = output_dir / filename

        # Save the file
        path = self.save_chart(html_content, output_path, overwrite=True)

        return html_content, path
