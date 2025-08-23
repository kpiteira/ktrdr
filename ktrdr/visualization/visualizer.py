"""
Visualizer for KTRDR visualization module.

This module contains the Visualizer class that provides a high-level API
for creating and manipulating charts using the KTRDR visualization framework.
"""

# Setup logging
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from ktrdr.errors import ConfigurationError
from ktrdr.visualization.config_builder import ConfigBuilder
from ktrdr.visualization.data_adapter import DataAdapter
from ktrdr.visualization.renderer import Renderer

logger = logging.getLogger(__name__)


class Visualizer:
    """
    High-level API for creating and manipulating financial charts.

    This class provides a simplified interface for creating interactive charts
    using the lightweight-charts library. It abstracts away the details of
    chart configuration and rendering, allowing users to quickly create
    charts with minimal code.

    Attributes:
        theme (str): The theme to use for charts ('dark' or 'light').
        renderer (Renderer): The renderer instance used to create charts.
    """

    def __init__(self, theme: str = "dark"):
        """
        Initialize the visualizer with a theme.

        Args:
            theme (str): The theme to use for charts ('dark' or 'light').
                Default is 'dark'.

        Raises:
            ConfigurationError: If the theme is not 'dark' or 'light'.
        """
        if theme not in ["dark", "light"]:
            raise ConfigurationError(
                f"Invalid theme: {theme}. Use 'dark' or 'light'.",
                "CONFIG-InvalidTheme",
                {"theme": theme},
            )

        self.theme = theme
        self.renderer = Renderer()
        logger.info(f"Visualizer initialized with {theme} theme")

    def create_chart(
        self,
        data: pd.DataFrame,
        title: Optional[str] = None,
        chart_type: str = "candlestick",
        height: int = 400,
    ) -> dict[str, Any]:
        """
        Create a basic chart from a DataFrame.

        Args:
            data (pd.DataFrame): The DataFrame containing OHLCV data.
            title (Optional[str]): The title for the chart. If None, a default
                title will be generated.
            chart_type (str): The type of chart to create ('candlestick', 'line',
                'bar', 'area', 'histogram'). Default is 'candlestick'.
            height (int): The height of the chart in pixels. Default is 400.

        Returns:
            Dict[str, Any]: A dictionary containing the chart configuration
                and data needed to render the chart.

        Raises:
            ConfigurationError: If chart_type is not supported.
        """
        supported_chart_types = ["candlestick", "line", "bar", "area", "histogram"]
        if chart_type not in supported_chart_types:
            raise ConfigurationError(
                f"Unsupported chart type: {chart_type}. Use {', '.join(supported_chart_types)}.",
                "CONFIG-UnsupportedChartType",
                {"chart_type": chart_type, "supported_types": supported_chart_types},
            )

        # Create a default title if none provided
        if title is None:
            title = f"KTRDR Chart ({chart_type})"

        # Generate a unique ID for the chart
        chart_id = f"main_chart"

        # Transform data based on chart type
        transformed_data = {}
        if chart_type == "candlestick":
            chart_options = ConfigBuilder.create_price_chart_options(
                theme=self.theme, height=height
            )
            series_options = ConfigBuilder.create_series_options(
                series_type="candlestick"
            )
            chart_data = DataAdapter.transform_ohlc(data)
            chart_type_config = "price"
        elif chart_type == "histogram":
            chart_options = ConfigBuilder.create_indicator_chart_options(
                theme=self.theme, height=height
            )
            series_options = ConfigBuilder.create_series_options(
                series_type="histogram"
            )
            # Use 'volume' column if it exists, otherwise use 'close'
            value_column = "volume" if "volume" in data.columns else "close"
            chart_data = DataAdapter.transform_histogram(
                data, time_column="date", value_column=value_column
            )
            chart_type_config = "histogram"
        else:  # line, bar, area
            chart_options = ConfigBuilder.create_indicator_chart_options(
                theme=self.theme, height=height
            )
            series_options = ConfigBuilder.create_series_options(series_type=chart_type)
            # Use 'close' column for line charts if 'value' doesn't exist
            value_column = "close" if "close" in data.columns else data.columns[1]
            chart_data = DataAdapter.transform_line(
                data, time_column="date", value_column=value_column
            )
            chart_type_config = "indicator"

        # Create chart configuration
        chart_config = [
            {
                "id": chart_id,
                "type": chart_type_config,
                "title": title,
                "height": height,
                "options": chart_options,
                "series_options": series_options,
            }
        ]

        # Create chart data structure
        transformed_data[chart_id] = chart_data

        # Return the chart configuration and data
        chart = {
            "title": title,
            "configs": chart_config,
            "data": transformed_data,
            "overlay_series": [],
            "panels": [],
        }

        logger.info(f"Created {chart_type} chart with title: {title}")
        return chart

    def add_indicator_overlay(
        self,
        chart: dict[str, Any],
        data: pd.DataFrame,
        column: str,
        color: str = "#2962FF",
        title: Optional[str] = None,
        line_width: float = 1.5,
        panel_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Add an indicator as an overlay on the price chart or a specific panel.

        Args:
            chart (Dict[str, Any]): The chart dictionary returned by create_chart.
            data (pd.DataFrame): The DataFrame containing the indicator data.
            column (str): The column in the DataFrame containing the indicator values.
            color (str): The color to use for the indicator line. Default is "#2962FF".
            title (Optional[str]): The title for the indicator. If None, the column
                name will be used.
            line_width (float): The width of the indicator line. Default is 1.5.
            panel_id (Optional[str]): The ID of the panel to add the overlay to.
                If None, adds to the main chart (first panel).

        Returns:
            Dict[str, Any]: The updated chart dictionary.

        Raises:
            ConfigurationError: If the input chart is invalid or column is not found.
        """
        # Validate chart format
        if not isinstance(chart, dict) or "configs" not in chart or "data" not in chart:
            raise ConfigurationError(
                "Invalid chart format. Use the output of create_chart().",
                "CONFIG-InvalidChart",
                {"chart": chart},
            )

        # Validate column existence
        if column not in data.columns:
            raise ConfigurationError(
                f"Column '{column}' not found in DataFrame. Available columns: {', '.join(data.columns)}",
                "CONFIG-ColumnNotFound",
                {"column": column, "available_columns": list(data.columns)},
            )

        # Use column name as title if not provided
        if title is None:
            title = column

        # Generate unique ID for this overlay
        overlay_id = f"{column.lower().replace(' ', '_')}_overlay"

        # Transform indicator data to line series
        indicator_data = DataAdapter.transform_line(
            data, time_column="date", value_column=column
        )

        # Create series options for the overlay
        series_options = ConfigBuilder.create_series_options(
            series_type="line", color=color, line_width=line_width, title=title
        )

        # Find the target panel to add the overlay to
        target_config = None

        if panel_id:
            # Look for the specified panel by ID
            for config in chart["configs"]:
                if config.get("id") == panel_id:
                    target_config = config
                    break

            if not target_config:
                # If specified panel ID was not found, look for panels that contain the target ID in their name
                # This helps with finding a panel like "macd_panel" when looking for "macd"
                for config in chart["configs"]:
                    config_id = config.get("id", "")
                    if panel_id.lower() in config_id.lower():
                        target_config = config
                        break

        # If no panel specified or not found, default to main chart (first panel)
        if not target_config:
            target_config = chart["configs"][0]

        # Add overlay to the target panel
        if "overlay_series" not in target_config:
            target_config["overlay_series"] = []

        # Add overlay configuration
        target_config["overlay_series"].append(
            {"id": overlay_id, "type": "line", "options": series_options}
        )

        # Add overlay data
        chart["data"][overlay_id] = indicator_data

        # Track overlay in chart object for reference
        chart["overlay_series"].append(
            {
                "id": overlay_id,
                "column": column,
                "color": color,
                "title": title,
                "panel_id": target_config.get(
                    "id", "main"
                ),  # Record which panel this was added to
            }
        )

        logger.info(
            f"Added {title} indicator overlay to {target_config.get('id', 'chart')}"
        )
        return chart

    def add_indicator_panel(
        self,
        chart: dict[str, Any],
        data: pd.DataFrame,
        column: str,
        panel_type: str = "line",
        height: int = 150,
        color: str = "#9C27B0",
        title: Optional[str] = None,
        visible: bool = True,
    ) -> dict[str, Any]:
        """
        Add an indicator as a separate panel below the main chart.

        Args:
            chart (Dict[str, Any]): The chart dictionary returned by create_chart.
            data (pd.DataFrame): The DataFrame containing the indicator data.
            column (str): The column in the DataFrame containing the indicator values.
            panel_type (str): The type of panel to create ('line', 'histogram', 'area').
                Default is 'line'.
            height (int): The height of the panel in pixels. Default is 150.
            color (str): The color to use for the indicator. Default is "#9C27B0".
            title (Optional[str]): The title for the panel. If None, the column name
                will be used.
            visible (bool): Whether the panel should be visible initially. Default is True.

        Returns:
            Dict[str, Any]: The updated chart dictionary.

        Raises:
            ConfigurationError: If the input chart is invalid, panel_type is not
                supported, or column is not found.
        """
        # Validate chart format
        if not isinstance(chart, dict) or "configs" not in chart or "data" not in chart:
            raise ConfigurationError(
                "Invalid chart format. Use the output of create_chart().",
                "CONFIG-InvalidChart",
                {"chart": chart},
            )

        # Validate column existence
        if column not in data.columns:
            raise ConfigurationError(
                f"Column '{column}' not found in DataFrame. Available columns: {', '.join(data.columns)}",
                "CONFIG-ColumnNotFound",
                {"column": column, "available_columns": list(data.columns)},
            )

        # Validate panel type
        supported_panel_types = ["line", "histogram", "area"]
        if panel_type not in supported_panel_types:
            raise ConfigurationError(
                f"Unsupported panel type: {panel_type}. Use {', '.join(supported_panel_types)}.",
                "CONFIG-UnsupportedPanelType",
                {"panel_type": panel_type, "supported_types": supported_panel_types},
            )

        # Use column name as title if not provided
        if title is None:
            title = f"{column} ({panel_type})"

        # Generate unique ID for this panel
        panel_id = f"{column.lower().replace(' ', '_')}_panel"

        # Transform data based on panel type
        if panel_type == "histogram":
            indicator_data = DataAdapter.transform_histogram(
                data, time_column="date", value_column=column
            )
            chart_type_config = "histogram"
        else:  # line or area
            indicator_data = DataAdapter.transform_line(
                data, time_column="date", value_column=column
            )
            chart_type_config = "indicator"

        # Create chart options for the panel
        chart_options = ConfigBuilder.create_indicator_chart_options(
            theme=self.theme, height=height
        )

        # Create series options for the panel
        series_options = ConfigBuilder.create_series_options(
            series_type=panel_type,
            color=color,
            title=title,
            line_width=1.5 if panel_type == "line" else 1.0,
        )

        # Find the ID of the main chart to sync with
        main_chart_id = chart["configs"][0]["id"]

        # Create panel configuration
        panel_config = {
            "id": panel_id,
            "type": chart_type_config,
            "title": title,
            "height": height,
            "options": chart_options,
            "series_options": series_options,
            "sync": {"target": main_chart_id},
            "is_panel": True,
            "visible": visible,
        }

        # Add panel configuration to chart configs
        chart["configs"].append(panel_config)

        # Add panel data
        chart["data"][panel_id] = indicator_data

        # Track panel in chart object for reference
        chart["panels"].append(
            {
                "id": panel_id,
                "column": column,
                "type": panel_type,
                "color": color,
                "title": title,
                "height": height,
                "visible": visible,
            }
        )

        logger.info(
            f"Added {title} indicator panel to chart with visibility: {visible}"
        )
        return chart

    def set_panel_visibility(
        self, chart: dict[str, Any], panel_id: str, visible: bool = True
    ) -> dict[str, Any]:
        """
        Set the visibility of an indicator panel.

        Args:
            chart (Dict[str, Any]): The chart dictionary returned by create_chart.
            panel_id (str): The ID of the panel to adjust visibility for.
            visible (bool): Whether the panel should be visible. Default is True.

        Returns:
            Dict[str, Any]: The updated chart dictionary.

        Raises:
            ConfigurationError: If the input chart is invalid or panel is not found.
        """
        # Validate chart format
        if not isinstance(chart, dict) or "configs" not in chart or "data" not in chart:
            raise ConfigurationError(
                "Invalid chart format. Use the output of create_chart().",
                "CONFIG-InvalidChart",
                {"chart": chart},
            )

        # Find the panel in the configuration
        panel_config = None
        for config in chart["configs"]:
            if config.get("id") == panel_id:
                panel_config = config
                break

        if not panel_config:
            raise ConfigurationError(
                f"Panel with ID '{panel_id}' not found in chart.",
                "CONFIG-PanelNotFound",
                {"panel_id": panel_id},
            )

        # Update visibility in config
        panel_config["visible"] = visible

        # Update visibility in panel reference
        for panel in chart["panels"]:
            if panel.get("id") == panel_id:
                panel["visible"] = visible
                break

        logger.info(f"Set panel {panel_id} visibility to: {visible}")
        return chart

    def toggle_overlay_visibility(
        self, chart: dict[str, Any], overlay_id: str
    ) -> dict[str, Any]:
        """
        Toggle the visibility of an indicator overlay.

        Args:
            chart (Dict[str, Any]): The chart dictionary returned by create_chart.
            overlay_id (str): The ID of the overlay to toggle.

        Returns:
            Dict[str, Any]: The updated chart dictionary.

        Raises:
            ConfigurationError: If the input chart is invalid or overlay is not found.
        """
        # Validate chart format
        if not isinstance(chart, dict) or "configs" not in chart or "data" not in chart:
            raise ConfigurationError(
                "Invalid chart format. Use the output of create_chart().",
                "CONFIG-InvalidChart",
                {"chart": chart},
            )

        # Find the overlay in the chart overlays
        overlay = None
        for ovr in chart.get("overlay_series", []):
            if ovr.get("id") == overlay_id:
                overlay = ovr
                break

        if not overlay:
            raise ConfigurationError(
                f"Overlay with ID '{overlay_id}' not found in chart.",
                "CONFIG-OverlayNotFound",
                {"overlay_id": overlay_id},
            )

        # Toggle visibility state
        current_state = overlay.get("visible", True)
        overlay["visible"] = not current_state

        logger.info(f"Toggled overlay {overlay_id} visibility to: {not current_state}")
        return chart

    def reorganize_panels(
        self, chart: dict[str, Any], order: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """
        Reorganize indicator panels in the specified order.

        Args:
            chart (Dict[str, Any]): The chart dictionary returned by create_chart.
            order (Optional[List[str]]): List of panel IDs in the desired order.
                If None, all panels will be sorted by their creation order.

        Returns:
            Dict[str, Any]: The updated chart dictionary.

        Raises:
            ConfigurationError: If the input chart is invalid or any panel ID is not found.
        """
        # Validate chart format
        if not isinstance(chart, dict) or "configs" not in chart or "data" not in chart:
            raise ConfigurationError(
                "Invalid chart format. Use the output of create_chart().",
                "CONFIG-InvalidChart",
                {"chart": chart},
            )

        # Get the main chart (first panel) and any range slider
        main_chart = chart["configs"][0]
        range_slider = next(
            (c for c in chart["configs"] if c.get("is_range_slider", False)), None
        )

        # Filter out panels (not the main chart or range slider)
        panel_configs = [
            c
            for c in chart["configs"]
            if c.get("id") != main_chart.get("id")
            and not c.get("is_range_slider", False)
        ]

        if not panel_configs:
            # No panels to reorganize
            return chart

        # If no order specified, use the existing order
        if order is None:
            # Keep existing order
            pass
        else:
            # Validate the provided order
            for panel_id in order:
                if not any(c.get("id") == panel_id for c in panel_configs):
                    raise ConfigurationError(
                        f"Panel with ID '{panel_id}' not found in chart.",
                        "CONFIG-PanelNotFound",
                        {"panel_id": panel_id},
                    )

            # Sort panels according to the specified order
            panel_configs.sort(
                key=lambda c: (
                    order.index(c.get("id")) if c.get("id") in order else float("inf")
                )
            )

        # Reconstruct the chart configs in the correct order
        new_configs = [main_chart]
        new_configs.extend(panel_configs)
        if range_slider:
            new_configs.append(range_slider)

        chart["configs"] = new_configs

        logger.info(f"Reorganized {len(panel_configs)} panels in chart")
        return chart

    def configure_range_slider(
        self, chart: dict[str, Any], height: int = 60, show: bool = True
    ) -> dict[str, Any]:
        """
        Configure a range slider for the chart.

        Args:
            chart (Dict[str, Any]): The chart dictionary returned by create_chart.
            height (int): The height of the range slider in pixels. Default is 60.
            show (bool): Whether to show the range slider. Default is True.

        Returns:
            Dict[str, Any]: The updated chart dictionary.

        Raises:
            ConfigurationError: If the input chart is invalid.
        """
        # Validate chart format
        if not isinstance(chart, dict) or "configs" not in chart or "data" not in chart:
            raise ConfigurationError(
                "Invalid chart format. Use the output of create_chart().",
                "CONFIG-InvalidChart",
                {"chart": chart},
            )

        if not show:
            # Remove any existing range slider
            chart["configs"] = [
                c for c in chart["configs"] if not c.get("is_range_slider", False)
            ]
            return chart

        # Check if range slider already exists
        existing_slider = next(
            (c for c in chart["configs"] if c.get("is_range_slider", False)), None
        )
        if existing_slider:
            # Update existing slider height
            existing_slider["height"] = height
            return chart

        # Get main chart ID and data
        main_chart_id = chart["configs"][0]["id"]
        main_chart_data = chart["data"].get(main_chart_id, [])

        # Create range slider configuration
        range_slider_options = ConfigBuilder.create_indicator_chart_options(
            theme=self.theme,
            height=height,
            visible_time_scale=True,
            handle_scale=True,
            handle_scroll=True,
        )

        # Default semi-transparent color based on theme
        slider_color = "#2962FF80" if self.theme == "dark" else "#2196F380"

        range_slider_series_options = ConfigBuilder.create_series_options(
            series_type="area", color=slider_color, line_width=1
        )

        # Create range slider configuration
        slider_id = "range_slider"
        range_slider_config = {
            "id": slider_id,
            "type": "range",
            "title": "Range Selector",
            "height": height,
            "options": range_slider_options,
            "series_options": range_slider_series_options,
            "is_range_slider": True,
            "sync": {"target": main_chart_id, "mode": "range"},
        }

        # Add range slider configuration to chart configs
        chart["configs"].append(range_slider_config)

        # Add range slider data (reuse main chart data)
        chart["data"][slider_id] = main_chart_data

        logger.info(f"Added range slider to chart with height: {height}")
        return chart

    def save(
        self, chart: dict[str, Any], filename: Union[str, Path], overwrite: bool = False
    ) -> Path:
        """
        Save the chart to an HTML file.

        Args:
            chart (Dict[str, Any]): The chart dictionary returned by create_chart.
            filename (Union[str, Path]): The path to save the HTML file.
            overwrite (bool): Whether to overwrite the file if it exists.
                Default is False.

        Returns:
            Path: The path to the saved HTML file.

        Raises:
            ConfigurationError: If the input chart is invalid.
        """
        # Validate chart format
        if not isinstance(chart, dict) or "configs" not in chart or "data" not in chart:
            raise ConfigurationError(
                "Invalid chart format. Use the output of create_chart().",
                "CONFIG-InvalidChart",
                {"chart": chart},
            )

        # Check for range slider
        has_range_slider = any(
            c.get("is_range_slider", False) for c in chart["configs"]
        )

        # Render the chart
        html_content = self.renderer.render_chart(
            title=chart.get("title", "KTRDR Chart"),
            chart_configs=chart["configs"],
            chart_data=chart["data"],
            theme=self.theme,
            has_range_slider=has_range_slider,
        )

        # Save the chart to file
        output_path = self.renderer.save_chart(html_content, filename, overwrite)

        logger.info(f"Saved chart to: {output_path}")
        return output_path

    def show(self, chart: dict[str, Any]) -> str:
        """
        Generate HTML content for displaying the chart.

        This method is particularly useful in Jupyter notebooks or
        integrated development environments that can display HTML.

        Args:
            chart (Dict[str, Any]): The chart dictionary returned by create_chart.

        Returns:
            str: HTML content that can be displayed in a Jupyter notebook
                or other HTML-capable environment.

        Raises:
            ConfigurationError: If the input chart is invalid.
        """
        # Validate chart format
        if not isinstance(chart, dict) or "configs" not in chart or "data" not in chart:
            raise ConfigurationError(
                "Invalid chart format. Use the output of create_chart().",
                "CONFIG-InvalidChart",
                {"chart": chart},
            )

        # Check for range slider
        has_range_slider = any(
            c.get("is_range_slider", False) for c in chart["configs"]
        )

        # Render the chart
        html_content = self.renderer.render_chart(
            title=chart.get("title", "KTRDR Chart"),
            chart_configs=chart["configs"],
            chart_data=chart["data"],
            theme=self.theme,
            has_range_slider=has_range_slider,
        )

        logger.info(f"Generated HTML content for interactive display")
        return html_content
